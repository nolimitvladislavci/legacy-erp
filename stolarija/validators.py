"""
AI Measurement Validator — "Drugi par očiju"

Tri sloja:
1. SANITY CHECK (rule-based, instant) — nemoguće dimenzije
2. SESSION COHERENCE (statistički) — outlier detekcija unutar sesije
3. HISTORICAL PATTERN (AI, async) — usporedba s prethodnim sesijama

Svaki sloj vraća warnings s razinom: error, warn, info.
"""
import logging
from statistics import mean, stdev

logger = logging.getLogger(__name__)


def validate_measurement(measurement, session=None):
    """
    Validacija jednog mjerenja. Poziva se PRIJE spremanja.
    Vraća: list of {'level': 'error'|'warn'|'info', 'message': str, 'code': str}
    """
    warnings = []
    w = measurement.width_mm
    h = measurement.height_mm
    q = measurement.quantity
    etype = measurement.element_type
    wing = measurement.wing_config

    # ═══ SLOJ 1: SANITY CHECK (rule-based) ═══

    # Nemoguće dimenzije
    if w < 300:
        warnings.append({
            'level': 'error',
            'code': 'width_too_small',
            'message': f'Širina {w}mm je premala. Minimalni prozor je ~300mm. Jeste li mislili {w*10}mm?',
        })
    elif w > 4000:
        warnings.append({
            'level': 'warn',
            'code': 'width_too_large',
            'message': f'Širina {w}mm ({w/1000:.1f}m) je neuobičajeno velika. Provjerite.',
        })

    if h < 300:
        warnings.append({
            'level': 'error',
            'code': 'height_too_small',
            'message': f'Visina {h}mm je premala. Jeste li mislili {h*10}mm?',
        })
    elif h > 3500:
        warnings.append({
            'level': 'warn',
            'code': 'height_too_large',
            'message': f'Visina {h}mm ({h/1000:.1f}m) je neuobičajeno velika. Provjerite.',
        })

    # Nelogičan omjer
    if w > 0 and h > 0:
        ratio = max(w, h) / min(w, h)
        if ratio > 5:
            warnings.append({
                'level': 'warn',
                'code': 'extreme_ratio',
                'message': f'Omjer {w}×{h}mm je {ratio:.1f}:1. To izgleda kao otvor, ne prozor.',
            })

    # Količina
    if q > 20:
        warnings.append({
            'level': 'warn',
            'code': 'high_quantity',
            'message': f'{q} komada istog otvora — jeste li sigurni?',
        })

    # Tip + dimenzija mismatch
    if etype == 'door' and h < 1800:
        warnings.append({
            'level': 'warn',
            'code': 'door_too_short',
            'message': f'Vrata od {h}mm ({h/1000:.1f}m) — uobičajeno je 2000-2200mm.',
        })

    if etype == 'window' and h > 2500:
        warnings.append({
            'level': 'info',
            'code': 'tall_window',
            'message': f'Prozor od {h}mm — možda su balkonska vrata?',
        })

    # Kat + tip
    floor = getattr(measurement, 'floor', 0) or 0
    if floor >= 3 and etype == 'door':
        warnings.append({
            'level': 'warn',
            'code': 'door_high_floor',
            'message': f'Vrata na {floor}. katu — jeste li sigurni da nisu balkonska vrata?',
        })

    # Profil + dimenzija
    profile = getattr(measurement, 'profile', None)
    if profile:
        material = getattr(profile, 'material', '')
        area_m2 = (w * h) / 1_000_000
        if material == 'pvc' and max(w, h) > 2500:
            warnings.append({
                'level': 'warn',
                'code': 'pvc_too_large',
                'message': f'PVC profil na otvoru {w}×{h}mm — za otvore > 2.5m preporuča se ALU.',
            })
        if material == 'wood' and area_m2 > 4:
            warnings.append({
                'level': 'info',
                'code': 'wood_large',
                'message': f'Drveni profil na {area_m2:.1f}m² — osigurajte strukturalnu nosivost.',
            })

    # Wing config + dimenzija
    if wing == 'single' and w > 1200:
        warnings.append({
            'level': 'info',
            'code': 'single_wide',
            'message': 'Jednokrilni prozor širi od 1200mm — razmislite o dvokrilnom.',
        })
    if wing == 'fixed' and etype == 'door':
        warnings.append({
            'level': 'error',
            'code': 'fixed_door',
            'message': 'Fiksna vrata nemaju smisla — promijenite konfiguraciju ili tip.',
        })

    # ═══ SLOJ 2: SESSION COHERENCE ═══

    if session:
        others = list(
            session.measurements
            .exclude(pk=measurement.pk if measurement.pk else None)
            .values_list('width_mm', 'height_mm')
        )
        if len(others) >= 3:
            widths = [o[0] for o in others]
            heights = [o[1] for o in others]

            # Outlier detection (2σ)
            if len(widths) >= 3:
                w_mean = mean(widths)
                w_std = stdev(widths) if len(widths) > 1 else 0
                if w_std > 0 and abs(w - w_mean) > 2 * w_std:
                    warnings.append({
                        'level': 'warn',
                        'code': 'width_outlier',
                        'message': f'Širina {w}mm značajno odstupa od ostalih u sesiji (prosj. {w_mean:.0f}mm). Tipfeler?',
                    })

            if len(heights) >= 3:
                h_mean = mean(heights)
                h_std = stdev(heights) if len(heights) > 1 else 0
                if h_std > 0 and abs(h - h_mean) > 2 * h_std:
                    warnings.append({
                        'level': 'warn',
                        'code': 'height_outlier',
                        'message': f'Visina {h}mm značajno odstupa od ostalih u sesiji (prosj. {h_mean:.0f}mm). Tipfeler?',
                    })

            # Ukupna površina provjera
            total_area = sum(ow * oh / 1_000_000 for ow, oh in others) + (w * h / 1_000_000) * q
            if total_area > 100:
                warnings.append({
                    'level': 'warn',
                    'code': 'total_area_excessive',
                    'message': f'Ukupna površina sesije je {total_area:.1f}m² — neobično mnogo za jednu lokaciju.',
                })

    return warnings


def validate_measurement_ai(measurement, session):
    """
    Sloj 3: AI provjera s Gemini/Haiku — async poziv.
    Uspoređuje s historijskim podacima firme.
    Vraća dodatne warnings ili prazan list.
    """
    warnings = []

    # Provjeri ima li dovoljno historije
    from .models import Measurement
    company = session.company
    historical = Measurement.objects.filter(
        session__company=company, confirmed=True
    ).exclude(session=session).count()

    if historical < 10:
        return []  # Premalo podataka za AI analizu

    # Statistika firme
    from django.db.models import Avg, StdDev
    stats = Measurement.objects.filter(
        session__company=company, confirmed=True
    ).exclude(session=session).aggregate(
        avg_w=Avg('width_mm'), avg_h=Avg('height_mm'),
        std_w=StdDev('width_mm'), std_h=StdDev('height_mm'),
    )

    avg_w = stats['avg_w'] or 1200
    std_w = stats['std_w'] or 200
    avg_h = stats['avg_h'] or 1400
    std_h = stats['std_h'] or 200

    w = measurement.width_mm
    h = measurement.height_mm

    # 3σ od historijskog prosjeka
    if std_w > 0 and abs(w - avg_w) > 3 * std_w:
        warnings.append({
            'level': 'info',
            'code': 'hist_width_unusual',
            'message': f'Širina {w}mm je neuobičajena za vašu firmu (prosj. {avg_w:.0f}±{std_w:.0f}mm).',
        })
    if std_h > 0 and abs(h - avg_h) > 3 * std_h:
        warnings.append({
            'level': 'info',
            'code': 'hist_height_unusual',
            'message': f'Visina {h}mm je neuobičajena za vašu firmu (prosj. {avg_h:.0f}±{std_h:.0f}mm).',
        })

    return warnings
