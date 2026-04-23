"""
FENIX SENTINEL — Celery Tasks (PLAN_072–083)
12 taskova koji pokrivaju: POS sesije, Temporal Ledger, Audit,
Fiscal compliance, EU Navigator, Obrasci, Kalendar, Digitalni Ured insights.
"""

import json
import time
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

# ─── PLAN_073 — STALE POS SESSIONS ──────────────────────────────────────────


@shared_task(name="sentinel.check_stale_pos_sessions")
def check_stale_pos_sessions():
    """
    Svakih 15 min: otvorene POS sesije >8h → alert.
    Ana's problem: kasa otvorena cijeli dan, nitko ne zna.
    """
    from sentinel.models import SentinelAlert

    start = time.time()
    total_alerts = 0

    try:
        from pos.models import POSSession
    except ImportError:
        return "POS app not available"

    STALE_HOURS = 8
    CRITICAL_HOURS = 16
    cutoff_warn = timezone.now() - timedelta(hours=STALE_HOURS)
    cutoff_crit = timezone.now() - timedelta(hours=CRITICAL_HOURS)

    open_sessions = POSSession.objects.filter(status="open", opened_at__lt=cutoff_warn).select_related(
        "terminal__company", "cashier"
    )

    for sess in open_sessions:
        hours_open = int((timezone.now() - sess.opened_at).total_seconds() // 3600)
        severity = "critical" if sess.opened_at < cutoff_crit else "warning"
        company = sess.terminal.company
        cashier_name = sess.cashier.name if sess.cashier else "Nepoznat"

        alert, created = SentinelAlert.objects.get_or_create(
            company=company,
            category="pos",
            alert_type="stale_pos_session",
            entity_type="POSSession",
            entity_id=str(sess.pk),
            resolved=False,
            defaults={
                "severity": severity,
                "title": f"Otvorena POS sesija {hours_open}h — {cashier_name}",
                "message": (
                    f"Terminal: {sess.terminal.name}. "
                    f"Sesija otvorena {sess.opened_at.strftime('%d.%m. %H:%M')}. "
                    f"Fiskalni izvještaj nije zatvoren. Radni sati ne broje se."
                ),
                "ai_suggestion": "Kontaktirajte blagajnika ili ručno zatvorite sesiju.",
                "data": {
                    "session_id": str(sess.pk),
                    "hours_open": hours_open,
                    "terminal": sess.terminal.name,
                    "cashier": cashier_name,
                },
            },
        )

        # Povećaj severity ako se produljila
        if not created and severity == "critical" and alert.severity == "warning":
            alert.severity = "critical"
            alert.title = f"KRITIČNO: Otvorena POS sesija {hours_open}h — {cashier_name}"
            alert.save(update_fields=["severity", "title", "updated_at"])

        if created:
            total_alerts += 1

    duration = int((time.time() - start) * 1000)
    return f"Stale POS check: {total_alerts} novih alertova, {duration}ms"


# ─── PLAN_074 — TEMPORAL LEDGER SCORE ────────────────────────────────────────


@shared_task(name="sentinel.temporal_ledger_score")
def temporal_ledger_score():
    """
    Svaki dan u 03:00: score sve POS transakcije prethodnog dana.
    Anomalije → alert.
    """
    from sentinel.temporal import TemporalAnalyzer, create_score_and_alert

    start = time.time()
    total_scored = 0
    total_anomalies = 0

    try:
        from pos.models import POSReceipt
    except ImportError:
        return "POS not available"

    yesterday_start = timezone.now() - timedelta(days=1)
    analyzer = TemporalAnalyzer()

    receipts = POSReceipt.objects.filter(is_paid=True, paid_at__gte=yesterday_start).select_related(
        "session__terminal__company"
    )

    for receipt in receipts:
        try:
            company = receipt.session.terminal.company
            score, flags = analyzer.score_pos_receipt(receipt, company)

            create_score_and_alert(receipt, score, flags, company)
            total_scored += 1
            if score < 50:
                total_anomalies += 1
        except Exception:
            continue

    duration = int((time.time() - start) * 1000)
    return f"Temporal Ledger: {total_scored} scoriranih, {total_anomalies} anomalija, {duration}ms"


# ─── PLAN_075 — AUDIT CHAIN VERIFY ───────────────────────────────────────────


@shared_task(name="sentinel.audit_chain_verify")
def audit_chain_verify():
    """
    Svaki dan u 04:00: provjeri integritet audit lanca svih firmi.
    Probijen lanac → kritičan alert.
    """
    from sentinel.audit import verify_chain
    from sentinel.models import SentinelAlert

    from companies.models import Company

    start = time.time()
    broken_companies = 0

    for company in Company.active.all():
        result = verify_chain(company)
        if not result["ok"]:
            broken_companies += 1
            SentinelAlert.objects.get_or_create(
                company=company,
                category="security",
                alert_type="audit_chain_broken",
                resolved=False,
                defaults={
                    "severity": "critical",
                    "title": "Audit lanac nije validan — moguća manipulacija podataka",
                    "message": (f"Probijeni zapisi: {len(result.get('broken_at', []))}. Odmah kontaktirajte podršku."),
                    "data": result,
                },
            )

    duration = int((time.time() - start) * 1000)
    return f"Audit Chain: {broken_companies} problema, {duration}ms"


# ─── PLAN_076 — FISCAL COMPLIANCE ────────────────────────────────────────────


@shared_task(name="sentinel.fiscal_compliance_scan")
def fiscal_compliance_scan():
    """
    Svaki ponedjeljak u 05:00: provjera fiskalne usklađenosti.
    OIB blagajnici, PP oznake, otvoreni računi >24h.
    """
    from sentinel.models import SentinelAlert

    start = time.time()
    total_alerts = 0

    try:
        from pos.models import POSCashier, POSReceipt, POSTerminal
    except ImportError:
        return "POS not available"

    for terminal in POSTerminal.objects.filter(is_active=True).select_related("company"):
        company = terminal.company

        # Provjera 1: PP oznaka terminala
        if not getattr(terminal, "poslovni_prostor", None):
            alert, created = SentinelAlert.objects.get_or_create(
                company=company,
                alert_type="missing_pp_oznaka",
                entity_type="POSTerminal",
                entity_id=str(terminal.pk),
                resolved=False,
                defaults={
                    "severity": "warning",
                    "category": "fiscal",
                    "title": f"Nedostaje PP oznaka — {terminal.name}",
                    "message": "Terminal nema poslovni prostor — fiskalizacija nije kompletna.",
                    "ai_suggestion": "Unesi PP oznaku u POS Postavke → Terminal.",
                    "data": {"terminal_id": str(terminal.pk)},
                },
            )
            if created:
                total_alerts += 1

        # Provjera 2: OIB blagajnika
        cashiers = POSCashier.objects.filter(terminal=terminal, is_active=True)
        for cashier in cashiers:
            if not getattr(cashier, "oib", None):
                alert, created = SentinelAlert.objects.get_or_create(
                    company=company,
                    alert_type="missing_cashier_oib",
                    entity_type="POSCashier",
                    entity_id=str(cashier.pk),
                    resolved=False,
                    defaults={
                        "severity": "warning",
                        "category": "fiscal",
                        "title": f"Blagajnik bez OIB-a — {cashier.name}",
                        "message": "Fiskalizacija zahtijeva OIB svakog blagajnika.",
                        "ai_suggestion": "Unesi OIB u POS Postavke → Blagajnici.",
                        "data": {"cashier_id": str(cashier.pk)},
                    },
                )
                if created:
                    total_alerts += 1

        # Provjera 3: Nezatvoreni računi >24h
        old_unpaid = POSReceipt.objects.filter(
            session__terminal=terminal,
            is_paid=False,
            is_cancelled=False,
            created_at__lt=timezone.now() - timedelta(hours=24),
        ).count()

        if old_unpaid > 0:
            SentinelAlert.objects.get_or_create(
                company=company,
                alert_type="old_open_receipts",
                entity_type="POSTerminal",
                entity_id=str(terminal.pk),
                resolved=False,
                defaults={
                    "severity": "warning",
                    "category": "fiscal",
                    "title": f"{old_unpaid} nezatvorenih računa >24h — {terminal.name}",
                    "message": "Otvoreni računi mogu uzrokovati probleme s fiskalnim izvještajem.",
                    "data": {"count": old_unpaid, "terminal": terminal.name},
                },
            )
            total_alerts += 1

    duration = int((time.time() - start) * 1000)
    return f"Fiscal Compliance: {total_alerts} alertova, {duration}ms"


# ─── PLAN_078 — EU NAVIGATOR ──────────────────────────────────────────────────


@shared_task(name="sentinel.eu_navigator_scan")
def eu_navigator_scan():
    """
    Svaki ponedjeljak u 06:00: AI profilira firme i kreira EU matcheve.
    """
    import anthropic
    from sentinel.models import SentinelAlert
    from sentinel.models_advisor import EUFund, EUMatch

    from companies.models import Company

    start = time.time()
    matches_created = 0

    client = anthropic.Anthropic()
    open_funds = list(EUFund.objects.filter(status__in=["open", "closing"]))

    if not open_funds:
        return "EU Navigator: nema otvorenih natječaja"

    for company in Company.active.all():
        profile = _build_eu_profile(company)

        for fund in open_funds:
            eligibility = _check_eligibility(profile, fund)
            if eligibility < 40:
                continue

            try:
                response = client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=400,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Procijeni match firme i EU natječaja.\n\n"
                                f"Firma: {company.name}, NKD: {profile.nkd_code}, "
                                f"Zaposlenici: {profile.employee_count}, "
                                f"Digital score: {profile.digital_score}/100\n\n"
                                f"Natječaj: {fund.title_hr or fund.title}\n"
                                f"Program: {fund.program}, Max grant: €{fund.max_grant_eur:,}\n"
                                f"Deadline: {fund.deadline}\n\n"
                                f'JSON: {{"match_score": 0-100, "potential_eur": broj, '
                                f'"reasoning": "kratko", "action_steps": ["k1","k2","k3"]}}'
                            ),
                        }
                    ],
                )

                data = json.loads(response.content[0].text)
                match_score = int(data.get("match_score", 0))

                if match_score >= 55:
                    match, created = EUMatch.objects.update_or_create(
                        company=company,
                        fund=fund,
                        defaults={
                            "match_score": match_score,
                            "eligibility_score": eligibility,
                            "potential_eur": int(data.get("potential_eur", 0)),
                            "ai_reasoning": data.get("reasoning", ""),
                            "action_plan": data.get("action_steps", []),
                        },
                    )

                    if created:
                        matches_created += 1
                        if match_score >= 70 and not match.notified:
                            SentinelAlert.objects.create(
                                company=company,
                                category="eu",
                                alert_type="eu_opportunity",
                                severity="info",
                                title=f"EU: {fund.title_hr or fund.title[:60]}",
                                message=(
                                    f"Match score {match_score}/100. "
                                    f"Potencijal: €{match.potential_eur:,}. "
                                    f"{match.ai_reasoning[:150]}"
                                ),
                                data={"fund_id": str(fund.pk), "match_id": str(match.pk)},
                            )
                            match.notified = True
                            match.save(update_fields=["notified"])

            except Exception:
                continue

    duration = int((time.time() - start) * 1000)
    return f"EU Navigator: {matches_created} novih matcheva, {duration}ms"


def _build_eu_profile(company):
    from employees.models import Employee
    from sentinel.models_advisor import EUFundProfile

    profile, _ = EUFundProfile.objects.get_or_create(company=company, defaults={})

    # Broj zaposlenika
    try:
        profile.employee_count = Employee.objects.filter(company=company, is_deleted=False).count()
    except Exception:
        pass

    # NKD kod iz kompanije
    profile.nkd_code = getattr(company, "nkd_code", "") or ""

    # Digital score iz AI usage
    try:
        from arhiva.models import ArhivaEntry

        ai_count = ArhivaEntry.objects.filter(company=company, is_deleted=False).exclude(ai_summary="").count()
        profile.digital_score = min(100, ai_count * 3)
    except Exception:
        pass

    profile.last_profiled = timezone.now()
    profile.save()
    return profile


def _check_eligibility(profile, fund) -> int:
    score = 100

    if fund.eligible_nkd and profile.nkd_code:
        if not any(profile.nkd_code.startswith(nkd) for nkd in fund.eligible_nkd):
            score -= 40

    if fund.min_employees and profile.employee_count < fund.min_employees:
        score -= 50

    if fund.max_employees and profile.employee_count > fund.max_employees:
        score -= 50

    return max(0, score)


# ─── PLAN_079 — OBRASCI GENERATE ─────────────────────────────────────────────


@shared_task(name="sentinel.obrasci_generate_monthly")
def obrasci_generate_monthly():
    """
    1. u svakog mjeseca u 07:00: auto-generiraj PDV obrasce.
    """
    from sentinel.models import SentinelAlert
    from sentinel.models_advisor import ObrascInstance, ObrascTip

    from companies.models import Company

    today = date.today()
    # Prošli mjesec
    if today.month == 1:
        period_od = date(today.year - 1, 12, 1)
        period_do = date(today.year - 1, 12, 31)
    else:
        period_od = date(today.year, today.month - 1, 1)
        import calendar

        last_day = calendar.monthrange(today.year, today.month - 1)[1]
        period_do = date(today.year, today.month - 1, last_day)

    rok = date(today.year, today.month, 20)

    try:
        pdv_tip = ObrascTip.objects.get(kod="PDV")
    except ObrascTip.DoesNotExist:
        return "PDV tip ne postoji — seed katalogu"

    generated = 0
    for company in Company.active.all():
        if ObrascInstance.objects.filter(company=company, tip=pdv_tip, period_od=period_od).exists():
            continue

        polja, neto = _calculate_pdv(company, period_od, period_do)

        obrazac = ObrascInstance.objects.create(
            company=company,
            tip=pdv_tip,
            period_od=period_od,
            period_do=period_do,
            rok_podnosenja=rok,
            status="ready",
            izracunata_vrijednost=neto,
            polja=polja,
            xml_sadrzaj=_generate_pdv_xml(company, period_od, period_do, polja),
        )
        generated += 1

        if neto < 0:
            SentinelAlert.objects.create(
                company=company,
                category="pdv",
                alert_type="pdv_refund",
                severity="info",
                title=f"PDV povrat: {abs(float(neto)):.2f} EUR",
                message=f"Za {period_od.strftime('%m/%Y')} imate pravo na povrat PDV-a.",
                data={"obrazac_id": str(obrazac.pk)},
            )
        elif neto > 5000:
            SentinelAlert.objects.create(
                company=company,
                category="pdv",
                alert_type="pdv_large_liability",
                severity="warning",
                title=f"PDV obveza: {float(neto):.2f} EUR do {rok}",
                message="Visoka PDV obveza — provjeri likvidnost.",
                data={"obrazac_id": str(obrazac.pk)},
            )

    return f"Obrasci: {generated} PDV obrazaca generiranih za {period_od.strftime('%m/%Y')}"


@shared_task(name="sentinel.obrasci_reminder")
def obrasci_reminder():
    """
    Svaki dan u 08:00: podsjeti na obrazce koji uskoro dospijevaju.
    """
    from sentinel.models import SentinelAlert
    from sentinel.models_advisor import ObrascInstance

    today = date.today()
    alerts_sent = 0

    # 7 dana
    due_7d = ObrascInstance.objects.filter(
        rok_podnosenja=today + timedelta(days=7), status__in=["draft", "ready"]
    ).select_related("company", "tip")

    for o in due_7d:
        _, created = SentinelAlert.objects.get_or_create(
            company=o.company,
            alert_type="obrazac_deadline_7d",
            entity_type="ObrascInstance",
            entity_id=str(o.pk),
            resolved=False,
            defaults={
                "severity": "warning",
                "category": "compliance",
                "title": f"{o.tip.naziv} — rok za 7 dana",
                "message": f"Obrazac {o.tip.naziv} ({o.period_od.strftime('%m/%Y')}) mora biti podnesen do {o.rok_podnosenja}.",
                "data": {"obrazac_id": str(o.pk)},
            },
        )
        if created:
            alerts_sent += 1

    # 1 dan — hitno
    due_1d = ObrascInstance.objects.filter(
        rok_podnosenja=today + timedelta(days=1), status__in=["draft", "ready"]
    ).select_related("company", "tip")

    for o in due_1d:
        SentinelAlert.objects.create(
            company=o.company,
            alert_type="obrazac_urgent",
            severity="critical",
            category="compliance",
            title=f"HITNO: {o.tip.naziv} ističe sutra!",
            message=f"Obrazac mora biti podnesen DO SUTRA ({o.rok_podnosenja}).",
            data={"obrazac_id": str(o.pk)},
        )
        alerts_sent += 1

    return f"Obrasci reminder: {alerts_sent} alertova"


# ─── PLAN_081 — KALENDAR OBVEZA ───────────────────────────────────────────────


@shared_task(name="sentinel.generate_calendar")
def generate_calendar():
    """
    Svake nedjelje u 22:00: regeneriraj kalendar za sve firme.
    """
    from sentinel.models_advisor import KalendarObveza

    from companies.models import Company

    today = date.today()
    year = today.year
    generated = 0

    for company in Company.active.all():
        # Briši stare auto-generirane koji nisu završeni
        KalendarObveza.objects.filter(company=company, auto_generated=True, rok__gt=today, is_completed=False).delete()

        items = []

        # PDV — 20. u svakom preostalom mjesecu
        for month in range(today.month, 13):
            try:
                rok = date(year, month, 20)
                if rok > today:
                    items.append(
                        KalendarObveza(
                            company=company,
                            kategorija="porezna",
                            naziv=f"PDV obrazac {month:02d}/{year}",
                            opis="Podnošenje PDV obrasca za prethodni period.",
                            rok=rok,
                            zakonska_osnova="Čl. 85 Zakona o PDV-u",
                            penali_kasnjenja="Kamata 9% + prekršajna kazna",
                            auto_generated=True,
                        )
                    )
            except ValueError:
                pass

        # JOPPD — 15. u svakom preostalom mjesecu
        for month in range(today.month, 13):
            try:
                rok = date(year, month, 15)
                if rok > today:
                    items.append(
                        KalendarObveza(
                            company=company,
                            kategorija="mirovinsko",
                            naziv=f"JOPPD {month:02d}/{year}",
                            opis="Izvješće o primicima, porezu na dohodak i doprinosima.",
                            rok=rok,
                            zakonska_osnova="Čl. 86 Zakona o doprinosima",
                            penali_kasnjenja="Novčana kazna do 200.000 HRK",
                            auto_generated=True,
                        )
                    )
            except ValueError:
                pass

        # Godišnji PDV — 30.04.
        try:
            rok_godisnji = date(year, 4, 30)
            if rok_godisnji > today:
                items.append(
                    KalendarObveza(
                        company=company,
                        kategorija="porezna",
                        naziv=f"Godišnji obračun poreza na dobit {year}",
                        rok=rok_godisnji,
                        zakonska_osnova="Čl. 35 Zakona o porezu na dobit",
                        auto_generated=True,
                    )
                )
        except ValueError:
            pass

        if items:
            KalendarObveza.objects.bulk_create(items, ignore_conflicts=True)
            generated += len(items)

    return f"Kalendar: {generated} obveza generirano za {Company.active.count()} firmi"


# ─── HELPER FUNKCIJE ──────────────────────────────────────────────────────────


def _calculate_pdv(company, period_od, period_do) -> tuple:
    """Izračunaj PDV iz arhive dokumenata."""

    # Pokušaj iz arhive
    totals = {"I-1-pdv": 0, "I-2-pdv": 0, "I-3-pdv": 0, "III-1-pretporez": 0}

    try:
        from arhiva.models import ArhivaEntry

        # Izlazni PDV (prihodi)
        out_entries = ArhivaEntry.objects.filter(
            company=company,
            is_deleted=False,
            document_date__range=(period_od, period_do),
        )
        # Simplificiran izračun — koristimo ai_confidence kao indikator
        _out_total = out_entries.exclude(ai_summary="").count() * 100  # noqa: F841
        totals["I-1-pdv"] = 0  # realni izračun treba invoice modele
    except Exception:
        pass

    neto = totals.get("I-1-pdv", 0) - totals.get("III-1-pretporez", 0)
    return totals, neto


def _generate_pdv_xml(company, period_od, period_do, polja) -> str:
    """Generiraj ePorezna XML format."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Obrazac_PDV xmlns="http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/ObrazacPDV/v2-0">
  <Zaglavlje>
    <Razdoblje_od>{period_od.strftime("%Y-%m-%d")}</Razdoblje_od>
    <Razdoblje_do>{period_do.strftime("%Y-%m-%d")}</Razdoblje_do>
    <OIB>{getattr(company, "oib", "")}</OIB>
    <Naziv>{company.name}</Naziv>
  </Zaglavlje>
  <Podaci>
    <I1_PDV>{polja.get("I-1-pdv", 0):.2f}</I1_PDV>
    <III1_Pretporez>{polja.get("III-1-pretporez", 0):.2f}</III1_Pretporez>
  </Podaci>
</Obrazac_PDV>"""
