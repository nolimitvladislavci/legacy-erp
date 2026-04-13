"""
AI Measurement Validator — "Drugi par ociju"

Tri sloja:
1. SANITY CHECK (rule-based, instant) — nemoguce dimenzije
2. SESSION COHERENCE (statisticki) — outlier detekcija unutar sesije
3. HISTORICAL PATTERN (AI, async) — usporedba s prethodnim sesijama

Svaki sloj vraca warnings s razinom: error, warn, info.
"""

import logging
from statistics import mean, stdev

logger = logging.getLogger(__name__)

# DIN standardi za sobna vrata (mm)
DOOR_STANDARD_SIZES = {
    "DIN": {
        "widths": [625, 750, 875, 1000],
        "heights": [1985, 2110],
    },
    "HR": {
        "widths": [600, 700, 800, 900, 1000],
        "heights": [1970, 2000, 2050, 2100],
    },
}


def validate_measurement(measurement, session=None):
    """
    Validacija jednog mjerenja. Poziva se PRIJE spremanja.
    Vraca: list of {'level': 'error'|'warn'|'info', 'message': str, 'code': str}
    """
    warnings = []
    w = measurement.width_mm
    h = measurement.height_mm
    q = measurement.quantity
    etype = measurement.element_type
    wing = measurement.wing_config

    # ═══ SLOJ 1: SANITY CHECK (rule-based) ═══

    if etype == "interior_door":
        # Sobna vrata — specifična pravila
        if w < 500:
            warnings.append(
                {
                    "level": "error",
                    "code": "door_width_too_small",
                    "message": f"Sirina sobnih vrata {w}mm je premala. Minimum je 600mm (DIN 625mm).",
                }
            )
        elif w > 1200:
            warnings.append(
                {
                    "level": "warn",
                    "code": "door_width_large",
                    "message": f"Sobna vrata {w}mm sira od 1200mm — dvokrila ili klizna?",
                }
            )

        if h < 1900:
            warnings.append(
                {
                    "level": "error",
                    "code": "door_height_too_small",
                    "message": f"Visina sobnih vrata {h}mm je premala. Standard je 1970-2100mm.",
                }
            )
        elif h > 2300:
            warnings.append(
                {
                    "level": "warn",
                    "code": "door_height_large",
                    "message": f"Sobna vrata od {h}mm su neuobicajeno visoka. Standard je do 2110mm.",
                }
            )

        # DIN provjera — najbliži standard
        closest_w = min(DOOR_STANDARD_SIZES["DIN"]["widths"], key=lambda x: abs(x - w))
        closest_h = min(DOOR_STANDARD_SIZES["DIN"]["heights"], key=lambda x: abs(x - h))
        if abs(w - closest_w) > 20:
            warnings.append(
                {
                    "level": "info",
                    "code": "door_non_standard_width",
                    "message": f"Sirina {w}mm nije standardna DIN mjera. Najblizi: {closest_w}mm.",
                }
            )
        if abs(h - closest_h) > 20:
            warnings.append(
                {
                    "level": "info",
                    "code": "door_non_standard_height",
                    "message": f"Visina {h}mm nije standardna DIN mjera. Najblizi: {closest_h}mm.",
                }
            )

        # Debljina zida za obuhvatni stok
        wall = getattr(measurement, "wall_thickness_mm", 0) or 0
        if wall and (wall < 60 or wall > 400):
            warnings.append(
                {
                    "level": "warn",
                    "code": "wall_thickness_unusual",
                    "message": f"Debljina zida {wall}mm je neuobicajena (tipicno 70-300mm).",
                }
            )

        # Fiksna vrata nema smisla
        if wing == "fixed":
            warnings.append(
                {
                    "level": "error",
                    "code": "fixed_door",
                    "message": "Fiksna sobna vrata nemaju smisla — promijenite konfiguraciju.",
                }
            )

    elif etype == "door":
        # Ulazna vrata
        if h < 1800:
            warnings.append(
                {
                    "level": "warn",
                    "code": "door_too_short",
                    "message": f"Ulazna vrata od {h}mm ({h / 1000:.1f}m) — uobicajeno je 2000-2200mm.",
                }
            )
        if w < 600:
            warnings.append(
                {
                    "level": "error",
                    "code": "door_too_narrow",
                    "message": f"Ulazna vrata od {w}mm su preuska. Minimum 600mm.",
                }
            )
        if wing == "fixed":
            warnings.append(
                {
                    "level": "error",
                    "code": "fixed_door",
                    "message": "Fiksna vrata nemaju smisla — promijenite konfiguraciju ili tip.",
                }
            )

    elif etype == "mosquito":
        # Komarnik
        if w < 200:
            warnings.append(
                {
                    "level": "error",
                    "code": "mosquito_too_small",
                    "message": f"Komarnik od {w}mm je premali. Minimum ~300mm.",
                }
            )
        if h < 200:
            warnings.append(
                {
                    "level": "error",
                    "code": "mosquito_too_small",
                    "message": f"Komarnik visina {h}mm je premala.",
                }
            )

    else:
        # Prozor / balkonska vrata / fasada / roleta
        if w < 300:
            warnings.append(
                {
                    "level": "error",
                    "code": "width_too_small",
                    "message": f"Sirina {w}mm je premala. Minimalni prozor je ~300mm. Jeste li mislili {w * 10}mm?",
                }
            )
        elif w > 4000:
            warnings.append(
                {
                    "level": "warn",
                    "code": "width_too_large",
                    "message": f"Sirina {w}mm ({w / 1000:.1f}m) je neuobicajeno velika. Provjerite.",
                }
            )

        if h < 300:
            warnings.append(
                {
                    "level": "error",
                    "code": "height_too_small",
                    "message": f"Visina {h}mm je premala. Jeste li mislili {h * 10}mm?",
                }
            )
        elif h > 3500:
            warnings.append(
                {
                    "level": "warn",
                    "code": "height_too_large",
                    "message": f"Visina {h}mm ({h / 1000:.1f}m) je neuobicajeno velika. Provjerite.",
                }
            )

        if etype == "window" and h > 2500:
            warnings.append(
                {
                    "level": "info",
                    "code": "tall_window",
                    "message": f"Prozor od {h}mm — mozda su balkonska vrata?",
                }
            )

        if wing == "fixed" and etype in ("door", "balcony_door"):
            warnings.append(
                {
                    "level": "error",
                    "code": "fixed_door",
                    "message": "Fiksna vrata nemaju smisla — promijenite konfiguraciju ili tip.",
                }
            )

    # Zajednicke provjere (svi tipovi)
    if w > 0 and h > 0:
        ratio = max(w, h) / min(w, h)
        if ratio > 5:
            warnings.append(
                {
                    "level": "warn",
                    "code": "extreme_ratio",
                    "message": f"Omjer {w}x{h}mm je {ratio:.1f}:1. Neobicno.",
                }
            )

    if q > 20:
        warnings.append(
            {
                "level": "warn",
                "code": "high_quantity",
                "message": f"{q} komada istog otvora — jeste li sigurni?",
            }
        )

    floor = getattr(measurement, "floor", 0) or 0
    if floor >= 3 and etype in ("door", "interior_door"):
        warnings.append(
            {
                "level": "warn",
                "code": "door_high_floor",
                "message": f"Vrata na {floor}. katu — jeste li sigurni da nisu balkonska vrata?",
            }
        )

    # Profil + dimenzija
    profile = getattr(measurement, "profile", None)
    if profile:
        material = getattr(profile, "material", "")
        area_m2 = (w * h) / 1_000_000
        if material == "pvc" and max(w, h) > 2500:
            warnings.append(
                {
                    "level": "warn",
                    "code": "pvc_too_large",
                    "message": f"PVC profil na otvoru {w}x{h}mm — za otvore > 2.5m preporuca se ALU.",
                }
            )
        if material == "wood" and area_m2 > 4:
            warnings.append(
                {
                    "level": "info",
                    "code": "wood_large",
                    "message": f"Drveni profil na {area_m2:.1f}m2 — osigurajte strukturalnu nosivost.",
                }
            )

    # Wing config + dimenzija
    if wing == "single" and w > 1200 and etype in ("window",):
        warnings.append(
            {
                "level": "info",
                "code": "single_wide",
                "message": "Jednokrilni prozor siri od 1200mm — razmislite o dvokrilnom.",
            }
        )

    # ═══ SLOJ 2: SESSION COHERENCE ═══

    if session:
        # Samo uspoređujemo s istim tipom elementa
        others = list(
            session.measurements.filter(element_type=etype)
            .exclude(pk=measurement.pk if measurement.pk else None)
            .values_list("width_mm", "height_mm")
        )
        if len(others) >= 3:
            widths = [o[0] for o in others]
            heights = [o[1] for o in others]

            if len(widths) >= 3:
                w_mean = mean(widths)
                w_std = stdev(widths) if len(widths) > 1 else 0
                if w_std > 0 and abs(w - w_mean) > 2 * w_std:
                    warnings.append(
                        {
                            "level": "warn",
                            "code": "width_outlier",
                            "message": f"Sirina {w}mm znacajno odstupa od ostalih {etype} u sesiji (prosj. {w_mean:.0f}mm).",
                        }
                    )

            if len(heights) >= 3:
                h_mean = mean(heights)
                h_std = stdev(heights) if len(heights) > 1 else 0
                if h_std > 0 and abs(h - h_mean) > 2 * h_std:
                    warnings.append(
                        {
                            "level": "warn",
                            "code": "height_outlier",
                            "message": f"Visina {h}mm znacajno odstupa od ostalih {etype} u sesiji (prosj. {h_mean:.0f}mm).",
                        }
                    )

        # Ukupna povrsina provjera (svi tipovi zajedno)
        all_others = list(
            session.measurements.exclude(pk=measurement.pk if measurement.pk else None).values_list(
                "width_mm", "height_mm", "quantity"
            )
        )
        if all_others:
            total_area = sum(ow * oh * oq / 1_000_000 for ow, oh, oq in all_others) + (w * h * q / 1_000_000)
            if total_area > 100:
                warnings.append(
                    {
                        "level": "warn",
                        "code": "total_area_excessive",
                        "message": f"Ukupna povrsina sesije je {total_area:.1f}m2 — neobicno mnogo za jednu lokaciju.",
                    }
                )

    return warnings


def validate_measurement_ai(measurement, session):
    """
    Sloj 3: AI provjera — usporedba s historijskim podacima firme.
    """
    warnings = []

    from .models import Measurement

    company = session.company
    etype = measurement.element_type

    historical = (
        Measurement.objects.filter(session__company=company, confirmed=True, element_type=etype)
        .exclude(session=session)
        .count()
    )

    if historical < 10:
        return []

    from django.db.models import Avg, StdDev

    stats = (
        Measurement.objects.filter(session__company=company, confirmed=True, element_type=etype)
        .exclude(session=session)
        .aggregate(
            avg_w=Avg("width_mm"),
            avg_h=Avg("height_mm"),
            std_w=StdDev("width_mm"),
            std_h=StdDev("height_mm"),
        )
    )

    avg_w = stats["avg_w"] or 1200
    std_w = stats["std_w"] or 200
    avg_h = stats["avg_h"] or 1400
    std_h = stats["std_h"] or 200

    w = measurement.width_mm
    h = measurement.height_mm
    type_display = dict(Measurement.ELEMENT_TYPES).get(etype, etype)

    if std_w > 0 and abs(w - avg_w) > 3 * std_w:
        warnings.append(
            {
                "level": "info",
                "code": "hist_width_unusual",
                "message": f"Sirina {w}mm je neuobicajena za {type_display} u vasoj firmi (prosj. {avg_w:.0f}+-{std_w:.0f}mm).",
            }
        )
    if std_h > 0 and abs(h - avg_h) > 3 * std_h:
        warnings.append(
            {
                "level": "info",
                "code": "hist_height_unusual",
                "message": f"Visina {h}mm je neuobicajena za {type_display} u vasoj firmi (prosj. {avg_h:.0f}+-{std_h:.0f}mm).",
            }
        )

    return warnings
