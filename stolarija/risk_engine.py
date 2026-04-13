"""
Predictive Service Risk Engine — Phase 1 (Rule-based).

Calculates risk score 0-100 for each warranty based on:
  - Material type (PVC degrades faster in heat, ALU corrodes near sea)
  - Location zone (coastal, continental, mountain, urban)
  - Age since installation
  - Hardware configuration (sliding = higher wear)
  - Service history (overdue = penalty)
  - Season factor (risk peaks before winter)

Phase 2 will add ML model trained on actual service outcomes.
"""
import logging
from datetime import date

logger = logging.getLogger('stolarija')

# ═══════════════════════════════════════════════════════════════════════════
# RISK FACTOR WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════

# Material degradation rates (annual risk points)
MATERIAL_RISK = {
    'pvc':  {'base': 3, 'coastal': 5, 'continental': 4, 'mountain': 4, 'urban': 3},
    'alu':  {'base': 2, 'coastal': 6, 'continental': 2, 'mountain': 3, 'urban': 2},
    'wood': {'base': 5, 'coastal': 7, 'continental': 5, 'mountain': 6, 'urban': 4},
}

# Hardware wear by configuration (annual risk points)
HARDWARE_RISK = {
    'fixed':     0,
    'single':    2,
    'double':    3,
    'triple':    4,
    'sliding':   6,  # Sliding mechanisms wear fastest
    'tilt_turn': 4,
}

# Issue prediction by material + zone
ISSUE_MATRIX = {
    ('pvc', 'coastal'):     ('deformation', 'PVC omekšava na UV + sol ubrzava starenje brtvi'),
    ('pvc', 'continental'): ('seal', 'Velike temperaturne amplitude ubrzavaju starenje brtvi'),
    ('pvc', 'mountain'):    ('condensation', 'Niske temperature + vlaga = kondenzacija'),
    ('pvc', 'urban'):       ('seal', 'Standardno starenje brtvi nakon 5-7 godina'),
    ('alu', 'coastal'):     ('hardware', 'Slana sredina korodira okovne dijelove 2-3x brže'),
    ('alu', 'continental'): ('drainage', 'Prljavština + lišće začepljuju odvodne kanale'),
    ('alu', 'mountain'):    ('glass', 'Termički šok na staklu pri naglim promjenama'),
    ('alu', 'urban'):       ('hardware', 'Standardno habanje okova'),
    ('wood', 'coastal'):    ('frame', 'Sol + vlaga uništavaju drveni okvir'),
    ('wood', 'continental'):('frame', 'Vlaga + mraz = pucanje drveta'),
    ('wood', 'mountain'):   ('frame', 'Snijeg + vjetar = mehanička oštećenja'),
    ('wood', 'urban'):      ('seal', 'Brtve na drvenim okvirima stare brže'),
}

# Season multipliers (1.0 = neutral)
SEASON_MULTIPLIER = {
    1: 1.2, 2: 1.1, 3: 1.0, 4: 0.9, 5: 0.8, 6: 0.8,
    7: 0.9, 8: 0.9, 9: 1.0, 10: 1.1, 11: 1.3, 12: 1.2,
}

# Coastal cities/regions in Croatia
COASTAL_KEYWORDS = [
    'rijeka', 'split', 'dubrovnik', 'zadar', 'šibenik', 'sibenik',
    'pula', 'rovinj', 'opatija', 'makarska', 'trogir', 'hvar',
    'korčula', 'korcula', 'rab', 'cres', 'krk', 'mali lošinj',
    'senj', 'biograd', 'vodice', 'primošten', 'omiš', 'omis',
    'kaštela', 'kastela', 'solin', 'sinj', 'metković', 'metkovic',
    'ploče', 'ploce', 'neum', 'cavtat', 'kotor', 'herceg novi',
    'bar', 'budva', 'podgorica',
]
MOUNTAIN_KEYWORDS = [
    'gorski kotar', 'delnice', 'čabar', 'cabar', 'lokve',
    'lika', 'gospić', 'gospic', 'otočac', 'otocac', 'plitvice',
    'slavonski brod', 'papuk', 'psunj',
]


def classify_location(address: str) -> str:
    """Classify address into location zone."""
    if not address:
        return 'urban'
    addr_lower = address.lower()
    for kw in COASTAL_KEYWORDS:
        if kw in addr_lower:
            return 'coastal'
    for kw in MOUNTAIN_KEYWORDS:
        if kw in addr_lower:
            return 'mountain'
    # Continental cities
    continental_kw = ['zagreb', 'osijek', 'varaždin', 'varazdin', 'čakovec', 'cakovec',
                      'koprivnica', 'bjelovar', 'sisak', 'karlovac', 'virovitica',
                      'požega', 'pozega', 'slavonski', 'vukovar', 'vinkovci',
                      'đakovo', 'djakovo', 'nova gradiška', 'nova gradiska']
    for kw in continental_kw:
        if kw in addr_lower:
            return 'continental'
    return 'urban'


def calculate_risk(warranty) -> dict:
    """
    Calculate risk score for a single WindowWarranty.
    Returns dict ready to update/create ServiceRiskProfile.
    """
    today = date.today()
    session = warranty.session
    if not session:
        return {'risk_score': 0, 'risk_level': 'low', 'factors': {}}

    address = session.address or ''
    zone = classify_location(address)
    handover = warranty.handover_date or (session.created_at.date() if session.created_at else today)
    age_days = (today - handover).days
    age_years = age_days / 365.25

    # Collect measurements for material/hardware analysis
    measurements = list(session.measurements.filter(confirmed=True).select_related('profile'))
    if not measurements:
        return {'risk_score': 0, 'risk_level': 'low', 'factors': {}}

    # Determine dominant material
    materials = {}
    for m in measurements:
        mat = m.profile.material if m.profile else 'pvc'
        materials[mat] = materials.get(mat, 0) + 1
    dominant_material = max(materials, key=materials.get)

    # Determine dominant hardware config
    configs = {}
    for m in measurements:
        configs[m.wing_config] = configs.get(m.wing_config, 0) + 1
    dominant_config = max(configs, key=configs.get)

    factors = {}

    # ── Factor 1: Material + Zone degradation ──
    mat_risk = MATERIAL_RISK.get(dominant_material, MATERIAL_RISK['pvc'])
    zone_annual = mat_risk.get(zone, mat_risk['base'])
    material_score = min(zone_annual * age_years, 40)
    factors['material'] = {
        'type': dominant_material,
        'zone': zone,
        'annual_rate': zone_annual,
        'years': round(age_years, 1),
        'score': round(material_score, 1),
    }

    # ── Factor 2: Hardware wear ──
    hw_annual = HARDWARE_RISK.get(dominant_config, 2)
    hardware_score = min(hw_annual * age_years, 25)
    factors['hardware'] = {
        'config': dominant_config,
        'annual_rate': hw_annual,
        'score': round(hardware_score, 1),
    }

    # ── Factor 3: Service history ──
    visits = list(warranty.service_visits.all())
    overdue_count = sum(1 for v in visits if not v.completed and v.scheduled < today)
    completed_count = sum(1 for v in visits if v.completed)
    last_service = max((v.completed for v in visits if v.completed), default=None)
    days_since_service = (today - last_service).days if last_service else age_days

    service_score = 0
    if overdue_count > 0:
        service_score += overdue_count * 10  # 10 points per overdue visit
    if days_since_service > 365:
        service_score += min((days_since_service - 365) / 30, 15)  # Max 15 for no service

    service_score = min(service_score, 25)
    factors['service'] = {
        'overdue': overdue_count,
        'completed': completed_count,
        'days_since_last': days_since_service,
        'score': round(service_score, 1),
    }

    # ── Factor 4: Season ──
    month = today.month
    season_mult = SEASON_MULTIPLIER.get(month, 1.0)
    factors['season'] = {
        'month': month,
        'multiplier': season_mult,
    }

    # ── Total score ──
    raw_score = (material_score + hardware_score + service_score) * season_mult
    risk_score = min(int(round(raw_score)), 100)

    # ── Risk level ──
    if risk_score >= 75:
        risk_level = 'critical'
    elif risk_score >= 50:
        risk_level = 'high'
    elif risk_score >= 25:
        risk_level = 'medium'
    else:
        risk_level = 'low'

    # ── Predicted issue ──
    issue_key = (dominant_material, zone)
    predicted_issue, issue_detail = ISSUE_MATRIX.get(issue_key, ('seal', 'Standardno starenje'))

    # Confidence based on data quality
    confidence = 0.5
    if age_years > 1:
        confidence += 0.1
    if completed_count > 0:
        confidence += 0.15
    if len(measurements) > 3:
        confidence += 0.1
    if warranty.handover_date:
        confidence += 0.15
    confidence = min(confidence, 0.95)

    # ── Recommendation ──
    recommendations = {
        'seal':         f'Preporučamo pregled i zamjenu brtvi. {issue_detail}.',
        'hardware':     f'Preporučamo podmazivanje i provjeru okova. {issue_detail}.',
        'condensation': f'Preporučamo provjeru ventilacije i IZO stakla. {issue_detail}.',
        'deformation':  f'Preporučamo provjeru ravnosti okvira i brtvljenja. {issue_detail}.',
        'glass':        f'Preporučamo provjeru IZO stakla na propuštanje plina. {issue_detail}.',
        'frame':        f'Preporučamo provjeru stanja okvira i zaštitnog premaza. {issue_detail}.',
        'drainage':     f'Preporučamo čišćenje odvodnih kanala. {issue_detail}.',
    }

    # Optimal service window
    if risk_score >= 50:
        window = 'Što prije — unutar 30 dana'
    elif month >= 9:
        window = f'Prije zime {today.year}'
    elif month <= 3:
        window = f'Prije proljeća {today.year}'
    else:
        window = f'Jesen {today.year}'

    return {
        'risk_score': risk_score,
        'risk_level': risk_level,
        'predicted_issue': predicted_issue,
        'issue_confidence': round(confidence, 2),
        'factors': factors,
        'location_zone': zone,
        'recommendation': recommendations.get(predicted_issue, ''),
        'optimal_service_window': window,
        'version': 1,
    }


def recalculate_all_risks():
    """Recalculate risk profiles for all active warranties."""
    from stolarija.models import WindowWarranty, ServiceRiskProfile

    warranties = WindowWarranty.objects.filter(
        handover_date__isnull=False,
    ).select_related('session').prefetch_related(
        'service_visits', 'session__measurements__profile'
    )

    updated = 0
    for w in warranties:
        data = calculate_risk(w)
        ServiceRiskProfile.objects.update_or_create(
            warranty=w,
            defaults=data,
        )
        updated += 1

    logger.info('recalculate_all_risks: updated %d profiles', updated)
    return updated
