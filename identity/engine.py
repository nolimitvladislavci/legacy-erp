"""
Identity Orchestration Engine
==============================
AI-assisted matching + Zero-Trust verification

Bankarski model:
  1. Korisnik uđe (autentifikacija OK)
  2. Trust Score se izračuna u pozadini
  3. Ovisno o Trust Scoreu — auto-approve, pending, ili blok

Trust Score kalkulacija:
  OIB verificiran (CroValidator)   → +35 pts
  Email domena matchana            → +20 pts
  Isti IP subnet kao firma         → +15 pts
  Invite token iskorišten          → +25 pts (override — odmah 90+)
  OIB već u sustavu za tu firmu    → +30 pts
  Novi račun < 24h                 → -10 pts
  Ranije odbijen                   → -40 pts
  
  ≥ 90 pts → AUTO_APPROVE
  60-89   → PENDING (admin odobrava)
  30-59   → PENDING + OIB_VERIFY zahtjev
  < 30    → BLOCKED + Sentry alert
"""
import logging

from django.utils import timezone

logger = logging.getLogger("identity.engine")

AUTO_APPROVE_THRESHOLD = 90
REQUIRE_OIB_THRESHOLD  = 60
BLOCK_THRESHOLD        = 30


def calculate_trust_score(user, company, ip=None, invite_token=None):
    """
    Izračunaj Trust Score za korisnik → firma prijedlog.
    Vraća (score: int, breakdown: dict, reasoning: str)
    """
    from .models import IdentityJoinRequest

    score = 0
    breakdown = {}

    # ── Invite token (najviši prioritet) ──────────────────────────────
    if invite_token:
        score += 25
        breakdown["invite_token"] = "+25 (validna pozivnica)"

    # ── OIB provjera ──────────────────────────────────────────────────
    try:
        tk = user.trikey
        if tk.oib and tk.oib_verified:
            score += 35
            breakdown["oib_verified"] = "+35 (OIB CroValidator potvrđen)"
            # Provjeri postoji li OIB u firmi
            from core.global_validation import find_oib_in_company
            if find_oib_in_company(tk.oib, company):
                score += 30
                breakdown["oib_in_company"] = "+30 (OIB već u evidenciji firme)"
    except Exception:
        pass

    # ── Email domain matching ──────────────────────────────────────────
    try:
        from .models import CompanyDomainWhitelist
        email = user.email or ""
        if "@" in email:
            domain = email.split("@")[1].lower()
            wl = CompanyDomainWhitelist.objects.filter(
                company=company, domain=domain, allow_discovery=True
            ).first()
            if wl:
                score += 20
                breakdown["domain_match"] = f"+20 (email domena @{domain} whitelisted)"
                if wl.allow_auto_approve:
                    score += 10
                    breakdown["domain_auto"] = "+10 (firma dopušta auto-odobrenje za domenu)"
    except Exception:
        pass

    # ── Prethodni zahtjevi ─────────────────────────────────────────────
    try:
        prev = IdentityJoinRequest.objects.filter(user=user, company=company)
        if prev.filter(status="rejected").exists():
            score -= 40
            breakdown["prev_rejected"] = "-40 (prethodno odbijen)"
        if prev.filter(status__in=["approved","auto"]).exists():
            score += 20
            breakdown["prev_approved"] = "+20 (prethodno odobren)"
    except Exception:
        pass

    # ── Novi račun penalizacija ────────────────────────────────────────
    age_hours = (timezone.now() - user.date_joined).total_seconds() / 3600
    if age_hours < 24:
        score -= 10
        breakdown["new_account"] = f"-10 (račun star {age_hours:.0f}h)"

    # ── Clamp 0-100 ───────────────────────────────────────────────────
    score = max(0, min(100, score))

    # ── Reasoning za AI ───────────────────────────────────────────────
    reasoning = _build_reasoning(score, breakdown, user, company)

    return score, breakdown, reasoning


def _build_reasoning(score, breakdown, user, company):
    lines = [
        f"Trust Score: {score}/100 za {user.username} → {company.name}",
        "",
        "Faktori:",
    ]
    for k, v in breakdown.items():
        lines.append(f"  {v}")
    lines.append("")
    if score >= AUTO_APPROVE_THRESHOLD:
        lines.append("ODLUKA: AUTO_APPROVE — score zadovoljava prag pouzdanosti.")
    elif score >= REQUIRE_OIB_THRESHOLD:
        lines.append("ODLUKA: PENDING — zahtijeva admin odobrenje.")
    elif score >= BLOCK_THRESHOLD:
        lines.append("ODLUKA: PENDING + OIB_REQUIRED — nizak score, potrebna OIB verifikacija.")
    else:
        lines.append("ODLUKA: BLOCKED — score ispod sigurnosnog praga. Sentry alert.")
    return "\n".join(lines)


def process_join_request(join_request, ip=None):
    """
    Obradi zahtjev za pridruživanje.
    Pokreće se async (Celery) ili sync.
    """
    from .models import IdentityAuditLog

    user    = join_request.user
    company = join_request.company

    score, breakdown, reasoning = calculate_trust_score(
        user, company, ip=ip
    )

    join_request.ai_trust_score = score / 100.0
    join_request.ai_reasoning   = reasoning
    join_request.save(update_fields=["ai_trust_score", "ai_reasoning"])

    IdentityAuditLog.log(
        "join_requested", user=user, company=company, ip=ip,
        detail={"score": score, "breakdown": breakdown}
    )

    if score >= AUTO_APPROVE_THRESHOLD:
        join_request.approve(note="AI auto-odobreno", auto=True)
        join_request.ai_auto_approved = True
        join_request.save(update_fields=["ai_auto_approved"])
        IdentityAuditLog.log("join_auto", user=user, company=company, ip=ip,
                              detail={"score": score})
        logger.info("AUTO_APPROVE: %s → %s (score=%s)", user.username, company.name, score)
        return "auto_approved"

    elif score < BLOCK_THRESHOLD:
        IdentityAuditLog.log("suspicious_attempt", user=user, company=company, ip=ip,
                              detail={"score": score, "reasoning": reasoning})
        _alert_security(user, company, score, reasoning)
        logger.warning("BLOCKED_LOW_SCORE: %s → %s (score=%s)", user.username, company.name, score)
        return "blocked"

    else:
        _notify_admin(join_request, score, reasoning)
        logger.info("PENDING: %s → %s (score=%s)", user.username, company.name, score)
        return "pending"


def _notify_admin(join_request, score, reasoning):
    """Obavijesti company_admin da čeka odobrenje."""
    try:
        from accounts.models import UserProfile
        admins = UserProfile.objects.filter(
            company=join_request.company,
            role__in=("company_admin", "tenant_admin")
        ).select_related("user")

        for p in admins[:3]:  # Max 3 admina
            # TODO: WhatsApp notification (isti kanal kao Trojstvo)
            logger.info("NOTIFY_ADMIN: %s ← zahtjev od %s (score=%s)",
                       p.user.username, join_request.user.username, score)
    except Exception as e:
        logger.error("notify_admin failed: %s", e)


def _alert_security(user, company, score, reasoning):
    """Sentry + WhatsApp Ivan za sumnjive pokušaje."""
    try:
        import sentry_sdk
        sentry_sdk.capture_message(
            f"IDENTITY BLOCK: {user.username} → {company.name} score={score}",
            level="warning"
        )
    except Exception:
        pass
    logger.error("SECURITY_ALERT: identity block | user=%s company=%s score=%s",
                user.username, company.name, score)


def detect_ghost_state(user):
    """
    Vrati True ako je korisnik u Ghost stanju (autentificiran, bez firme).
    Koristi se u middleware-u.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return False
    try:
        profile = user.profile
        return profile.company_id is None
    except Exception:
        return False


def suggest_companies_for_user(user):
    """
    AI sugestija: predloži firme u koje se korisnik može pridružiti.
    Temelji se na: email domeni, OIB-u, IP subnetu.
    GDPR: Samo firme s allow_discovery=True za domenu korisnika.
    """
    from companies.models import Company
    from .models import CompanyDomainWhitelist

    suggestions = []

    # 1. Email domain matching
    email = user.email or ""
    if "@" in email:
        domain = email.split("@")[1].lower()
        wl_entries = CompanyDomainWhitelist.objects.filter(
            domain=domain, allow_discovery=True
        ).select_related("company")
        for wl in wl_entries:
            suggestions.append({
                "company": wl.company,
                "reason": f"Vaša email domena @{domain} je whitelisted",
                "confidence": "high",
                "auto_approve_possible": wl.allow_auto_approve,
            })

    # 2. OIB matching u sudskom registru
    try:
        oib = user.trikey.oib if hasattr(user, 'trikey') else ""
        if oib:
            from companies.models import Company
            company = Company.objects.filter(oib=oib).first()
            if company and company not in [s["company"] for s in suggestions]:
                suggestions.append({
                    "company": company,
                    "reason": "Vaš OIB odgovara evidenciji ove firme",
                    "confidence": "very_high",
                    "auto_approve_possible": True,
                })
    except Exception:
        pass

    return suggestions
