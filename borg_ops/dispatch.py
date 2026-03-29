"""
BORG Faza 3 — Smart Dispatch Engine

Automatsko predlaganje najboljeg radnika za intervenciju/nalog
na temelju: udaljenosti, workloada, kategorije i SLA urgentnosti.

Matematika, ne magija:
  score = w_dist * distance_score + w_load * workload_score + w_cat * category_score

Niži score = bolji kandidat.
"""
import math
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count

logger = logging.getLogger('borg.dispatch')


# ═══════════════════════════════════════════════════════════════
#  HAVERSINE — udaljenost između dva GPS para (km)
# ═══════════════════════════════════════════════════════════════

def haversine(lat1, lon1, lat2, lon2):
    """
    Udaljenost u km između dva GPS para.
    Haversine formula — earth radius 6371 km.
    """
    if None in (lat1, lon1, lat2, lon2):
        return None

    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ═══════════════════════════════════════════════════════════════
#  WORKLOAD — koliko aktivnih zadataka ima radnik
# ═══════════════════════════════════════════════════════════════

def get_worker_workload(user):
    """
    Vraća dict s brojem aktivnih zadataka po tipu.
    Aktivni = nije u terminalnom statusu.
    """
    from interventions.models import HitnaIntervencija
    from work_orders.models import WorkOrder

    active_interventions = HitnaIntervencija.objects.filter(
        assigned_to=user,
    ).exclude(
        status__in=['RIJESENO', 'FAKTURIRANO']
    ).count()

    active_work_orders = WorkOrder.objects.filter(
        assigned_to=user,
    ).exclude(
        status__in=['completed', 'invoiced', 'cancelled']
    ).count()

    return {
        'interventions': active_interventions,
        'work_orders': active_work_orders,
        'total': active_interventions + active_work_orders,
    }


# ═══════════════════════════════════════════════════════════════
#  CATEGORY MATCH — može li radnik obaviti ovaj tip posla
# ═══════════════════════════════════════════════════════════════

def get_worker_categories(user):
    """
    Vraća set kategorija koje je radnik radio u zadnjih 90 dana.
    Bazira se na povijesnim dodjelama, ne na statičkim skillovima.
    """
    from interventions.models import HitnaIntervencija
    cutoff = timezone.now() - timedelta(days=90)

    cats = HitnaIntervencija.objects.filter(
        assigned_to=user,
        assigned_at__gte=cutoff,
    ).values_list('category', flat=True).distinct()

    return set(cats)


# ═══════════════════════════════════════════════════════════════
#  SMART DISPATCH — scoring i rangiranje kandidata
# ═══════════════════════════════════════════════════════════════

# Težinski faktori (ukupno 1.0)
W_DISTANCE  = 0.40   # Blizina je najvažnija za hitne
W_WORKLOAD  = 0.35   # Ne preoptereti nikoga
W_CATEGORY  = 0.15   # Iskustvo u kategoriji
W_FRESHNESS = 0.10   # Kad je zadnji put radio (ne zaboravi nove ljude)


def score_worker(user, intervention, company_lat=None, company_lng=None):
    """
    Računa dispatch score za jednog radnika i jednu intervenciju.
    Niži score = bolji kandidat.

    Returns: dict {user, score, distance_km, workload, has_category, breakdown}
    """
    # ── Distance score (0-1) ──────────────────────────────
    dist_km = None
    dist_score = 0.5  # default ako nema GPS

    if intervention.last_lat and intervention.last_lng:
        # Pokušaj GPS radnika (iz zadnje intervencije)
        worker_lat, worker_lng = _get_worker_location(user)
        if worker_lat and worker_lng:
            dist_km = haversine(worker_lat, worker_lng,
                                intervention.last_lat, intervention.last_lng)
        elif company_lat and company_lng:
            # Fallback: udaljenost od firme
            dist_km = haversine(company_lat, company_lng,
                                intervention.last_lat, intervention.last_lng)

    if dist_km is not None:
        # Normalizacija: 0km=0.0, 50+km=1.0
        dist_score = min(dist_km / 50.0, 1.0)

    # ── Workload score (0-1) ──────────────────────────────
    workload = get_worker_workload(user)
    # 0 zadataka = 0.0, 5+ = 1.0
    load_score = min(workload['total'] / 5.0, 1.0)

    # ── Category score — Dron #2 fix: hard filter + history tie-breaker ──
    # 1. Hard filter: certified_categories (eksplicitni certifikat)
    certified = []
    try:
        certified = list(user.profile.certified_categories or [])
    except Exception:
        pass

    # Ako ima certifikate i kategorija intervencije nije u njima — diskvaliﬁciraj
    if certified and intervention.category not in certified:
        return None   # Signal za suggest_workers() da isključi ovog radnika

    # 2. Tie-breaker: history iz 90 dana (Luka-novi dobiva 0.5 neutral umjesto 1.0 penalty)
    worker_cats = get_worker_categories(user)
    has_cat_history = intervention.category in worker_cats

    if certified and intervention.category in certified:
        # Certificiran — puni bonus bez obzira na history
        cat_score = 0.0
    elif has_cat_history:
        # Nije certificiran ali ima iskustvo — blagi bonus
        cat_score = 0.2
    else:
        # Novi radnik bez certifikata i bez history — neutral (ne penaliziramo)
        cat_score = 0.5

    # ── Freshness score (0-1) ─────────────────────────────
    # Kad je zadnji put radio nešto? Idle radnici dobivaju prednost.
    from interventions.models import HitnaIntervencija
    last_job = HitnaIntervencija.objects.filter(
        assigned_to=user,
    ).order_by('-assigned_at').values_list('assigned_at', flat=True).first()

    if last_job:
        hours_idle = (timezone.now() - last_job).total_seconds() / 3600
        # 0h idle = 1.0 (loše, upravo radio), 24h+ idle = 0.0 (dobro, odmoran)
        fresh_score = max(0, 1.0 - hours_idle / 24.0)
    else:
        fresh_score = 0.0  # Nikad nije radio = potpuno fresh

    # ── Ukupni score ──────────────────────────────────────
    total = (W_DISTANCE * dist_score +
             W_WORKLOAD * load_score +
             W_CATEGORY * cat_score +
             W_FRESHNESS * fresh_score)

    return {
        'user': user,
        'score': round(total, 3),
        'distance_km': round(dist_km, 1) if dist_km is not None else None,
        'workload': workload,
        'has_category': has_cat,
        'breakdown': {
            'distance': round(dist_score, 3),
            'workload': round(load_score, 3),
            'category': round(cat_score, 3),
            'freshness': round(fresh_score, 3),
        },
    }


def suggest_workers(intervention, limit=5):
    """
    Vraća sortirani popis radnika za intervenciju.
    Top kandidat = najniži score.

    Returns: list of dicts [{user, score, distance_km, workload, ...}]
    """
    from django.contrib.auth.models import User

    # Radnici iz iste firme koji su aktivni
    company = intervention.company
    workers = User.objects.filter(
        Q(profile__company=company) | Q(company_memberships__company=company),
        is_active=True,
    ).distinct()

    # Exclude already assigned
    if intervention.assigned_to:
        workers = workers.exclude(pk=intervention.assigned_to.pk)

    # Company GPS za fallback
    company_lat = getattr(company, 'latitude', None) if company else None
    company_lng = getattr(company, 'longitude', None) if company else None

    scored = []
    disqualified = 0
    for worker in workers:
        try:
            result = score_worker(worker, intervention, company_lat, company_lng)
            if result is None:
                # Dron #2: certified_categories hard filter — radnik nije kvalificiran
                disqualified += 1
                continue
            scored.append(result)
        except Exception as e:
            logger.warning('Dispatch score failed for user %s: %s', worker.pk, e)
    if disqualified:
        logger.info('Dispatch: %d radnika diskvaliﬁcirano (no cert za kategoriju %s)',
                    disqualified, intervention.category)

    # Sort: niži score = bolji
    scored.sort(key=lambda x: x['score'])

    logger.info(
        'Dispatch suggest [%s #%s %s]: %d kandidata, top=%s (%.3f)',
        intervention.category, intervention.pk, intervention.address[:30],
        len(scored),
        scored[0]['user'].username if scored else '-',
        scored[0]['score'] if scored else 0,
    )

    return scored[:limit]


def _get_worker_location(user):
    """
    Pokušaj pronaći zadnju GPS lokaciju radnika.
    Dron #1 fix: UserProfile.last_lat je canonički izvor — ažurira se
    pri svakom FSM tranziciji s JS Geolocation API.

    Izvori (prioritetni):
    1. UserProfile.last_lat (ažurirano pri FSM tranziciji) ← NOVI PRIMARNI
    2. Zadnja aktivna intervencija s GPS-om (fallback)
    3. None
    """
    # 1. UserProfile GPS (pravi terenska lokacija)
    try:
        profile = user.profile
        if profile.last_lat and profile.last_lng:
            from django.utils import timezone
            age_minutes = None
            if profile.last_gps_update:
                age_minutes = (timezone.now() - profile.last_gps_update).total_seconds() / 60
            # Koristimo GPS samo ako nije stariji od 4h
            if age_minutes is None or age_minutes < 240:
                return profile.last_lat, profile.last_lng
            else:
                logger.debug('GPS radnika %s star %.0f min — koristim fallback',
                             user.username, age_minutes)
    except Exception:
        pass

    # 2. Fallback: zadnja intervencija s GPS-om
    from interventions.models import HitnaIntervencija
    last = HitnaIntervencija.objects.filter(
        assigned_to=user,
        last_lat__isnull=False,
    ).order_by('-last_gps_update').values_list('last_lat', 'last_lng').first()

    if last:
        return last[0], last[1]

    return None, None


# ═══════════════════════════════════════════════════════════════
#  AI BUDGET ESTIMATOR — procjena troškova
# ═══════════════════════════════════════════════════════════════

def estimate_budget(category, company=None, percentile=75):
    """
    Procjena troškova za intervenciju na temelju povijesnih podataka.
    Bazira se na fakturiranim intervencijama u istoj kategoriji.

    Args:
        category: str (voda, struja, plin, kljucar, ostalo)
        company: Company instance (opcijalno, za per-company prosjek)
        percentile: int (default 75 = "realno visoka" procjena)

    Returns: dict {
        estimate: Decimal, median: Decimal, min: Decimal, max: Decimal,
        sample_size: int, percentile: int
    }
    """
    from interventions.models import HitnaIntervencija
    from decimal import Decimal

    qs = HitnaIntervencija.objects.filter(
        status='FAKTURIRANO',
        category=category,
    )

    if company:
        qs = qs.filter(company=company)

    # Pokupi iznose iz POS receiptova
    amounts = []
    for iv in qs.select_related('pos_receipt').only('pk', 'pos_receipt'):
        if iv.pos_receipt and hasattr(iv.pos_receipt, 'total_amount'):
            amt = iv.pos_receipt.total_amount
            if amt and amt > 0:
                amounts.append(float(amt))

    if not amounts:
        # Fallback: prosječni hourly rate * 2h
        from worktime.models import EmployeeProfile
        avg_rate_qs = EmployeeProfile.objects.filter(company=company) if company else EmployeeProfile.objects.all()
        avg_rate = avg_rate_qs.values_list('hourly_rate', flat=True)
        rates = [float(r) for r in avg_rate if r]
        if rates:
            avg = sum(rates) / len(rates)
            return {
                'estimate': Decimal(str(round(avg * 2, 2))),
                'median': Decimal(str(round(avg * 2, 2))),
                'min': Decimal(str(round(avg, 2))),
                'max': Decimal(str(round(avg * 4, 2))),
                'sample_size': 0,
                'percentile': percentile,
                'source': 'hourly_rate_estimate',
            }
        return {
            'estimate': Decimal('100.00'),
            'median': Decimal('100.00'),
            'min': Decimal('50.00'),
            'max': Decimal('300.00'),
            'sample_size': 0,
            'percentile': percentile,
            'source': 'default',
        }

    amounts.sort()
    n = len(amounts)

    # Dron #3 fix: IQR anomaly detection — izbaci outliere prije percentile računanja
    if n >= 4:
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = amounts[q1_idx]
        q3 = amounts[q3_idx]
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        clean = [a for a in amounts if lower_fence <= a <= upper_fence]
        if len(clean) >= 2:
            outliers_removed = n - len(clean)
            if outliers_removed > 0:
                logger.info('Budget estimator: %d outliera uklonjeno (IQR metoda). '
                            'Raspon čist: %.0f–%.0f EUR',
                            outliers_removed, clean[0], clean[-1])
            amounts = clean
            n = len(amounts)

    # Percentile calculation na očišćenim podacima
    idx = int(n * percentile / 100)
    idx = min(idx, n - 1)

    return {
        'estimate': Decimal(str(round(amounts[idx], 2))),
        'median': Decimal(str(round(amounts[n // 2], 2))),
        'min': Decimal(str(round(amounts[0], 2))),
        'max': Decimal(str(round(amounts[-1], 2))),
        'sample_size': n,
        'percentile': percentile,
        'source': 'historical',
    }
