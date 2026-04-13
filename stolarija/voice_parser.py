import re

WORD_TO_NUM = {
    "tisuću": 1000,
    "tisuća": 1000,
    "tisuc": 1000,
    "devetsto": 900,
    "osamsto": 800,
    "sedamsto": 700,
    "šesto": 600,
    "sesto": 600,
    "petsto": 500,
    "četiristo": 400,
    "cetiristo": 400,
    "tristo": 300,
    "dvjesto": 200,
    "dvesto": 200,
    "sto": 100,
    "devedeset": 90,
    "osamdeset": 80,
    "sedamdeset": 70,
    "šezdeset": 60,
    "sezdeset": 60,
    "pedeset": 50,
    "četrdeset": 40,
    "cetrdeset": 40,
    "trideset": 30,
    "dvadeset": 20,
    "devetnaest": 19,
    "osamnaest": 18,
    "sedamnaest": 17,
    "šesnaest": 16,
    "sesnaest": 16,
    "petnaest": 15,
    "četrnaest": 14,
    "cetmnaest": 14,
    "trinaest": 13,
    "dvanaest": 12,
    "jedanaest": 11,
    "deset": 10,
    "devet": 9,
    "osam": 8,
    "sedam": 7,
    "šest": 6,
    "sest": 6,
    "pet": 5,
    "četiri": 4,
    "cetiri": 4,
    "tri": 3,
    "dva": 2,
    "jedan": 1,
}

ELEMENT_MAP = {
    # Sobna / unutarnja vrata — MORA biti prije 'vrata'
    "sobna vrata": "interior_door",
    "sobna": "interior_door",
    "unutarnja": "interior_door",
    "unutarnji": "interior_door",
    "interijer": "interior_door",
    # Balkonska vrata
    "balkonska": "balcony_door",
    "balkon": "balcony_door",
    # Ulazna vrata
    "ulazna": "door",
    "ulazni": "door",
    "vrata": "door",
    # Prozor (default)
    "prozor": "window",
    # Komarnik
    "komarnik": "mosquito",
    "mreža": "mosquito",
    "mreza": "mosquito",
    "mrežica": "mosquito",
    "mrezica": "mosquito",
    # Roleta
    "roleta": "roller",
    "rolete": "roller",
    # Fasada
    "fasada": "facade",
    "fasadna": "facade",
}

WING_MAP = {
    "jednokrilni": "single",
    "jednokrilna": "single",
    "jednokrilno": "single",
    "dvokrilni": "double",
    "dvokrilna": "double",
    "dvokrilno": "double",
    "trokrilni": "triple",
    "trokrilna": "triple",
    "trokrilno": "triple",
    "fiksni": "fixed",
    "fiksna": "fixed",
    "fiksno": "fixed",
    "klizni": "sliding",
    "klizna": "sliding",
    "klizno": "sliding",
    "kip": "tilt_turn",
    "nagibno": "tilt_turn",
    "kip-turn": "tilt_turn",
    # Sobna vrata specifično
    "lijeva": "single_left",
    "lijevo": "single_left",
    "lijevi": "single_left",
    "desna": "single_right",
    "desno": "single_right",
    "desni": "single_right",
    "pivotirajuca": "pivot",
    "pivotirajuce": "pivot",
    "klizna na zid": "barn",
    "barn": "barn",
}

SWING_MAP = {
    "u prostoriju": "inward",
    "unutra": "inward",
    "prema unutra": "inward",
    "van": "outward",
    "prema van": "outward",
    "prema vani": "outward",
}

DOOR_POSITION_MAP = {
    "kupaonica": "bathroom",
    "kupatilo": "bathroom",
    "wc": "wc",
    "spavaća": "bedroom",
    "spavaca": "bedroom",
    "soba": "bedroom",
    "kuhinja": "kitchen",
    "dnevni": "living",
    "boravak": "living",
    "hodnik": "hallway",
    "ostava": "storage",
    "predsoblje": "hallway",
}

MESH_MAP = {
    "pvc mrež": "pvc",
    "alu mrež": "alu",
    "aluminij": "alu",
    "fiberglass": "fiberglass",
    "fiber": "fiberglass",
    "plise": "plisse",
    "pliše": "plisse",
}

MOUNTING_MAP = {
    "fiksni okvir": "fixed_frame",
    "fiksni": "fixed_frame",
    "roletni": "roller",
    "na roletu": "roller",
    "plise": "plisse",
    "pliše": "plisse",
    "magnetni": "magnetic",
    "magnet": "magnetic",
    "velcro": "velcro",
    "čičak": "velcro",
    "cicak": "velcro",
}


def words_to_number(text: str) -> str:
    """Pretvori pisane brojeve u znamenke."""
    result = text.lower()
    for word, num in sorted(WORD_TO_NUM.items(), key=lambda x: -len(x[0])):
        result = re.sub(r"\b" + word + r"\b", f" {num} ", result)

    # Spoji susjedne brojeve (sto dvadeset → 120)
    def combine_numbers(m):
        nums = [int(x) for x in m.group().split()]
        if len(nums) == 2:
            a, b = nums
            if a in (100, 200, 300, 400, 500, 600, 700, 800, 900) and b < 100:
                return str(a + b)
            if a in (10, 20, 30, 40, 50, 60, 70, 80, 90) and b < 10:
                return str(a + b)
        return m.group()

    result = re.sub(r"(\b\d+\s+){1,2}\d+\b", combine_numbers, result)
    return result


def parse_voice_input(text: str) -> dict:
    """
    Parsira glasovni unos na HR jeziku u strukturirane podatke za Measurement.

    Primjeri:
      "prozor sto dvadeset puta sto četrdeset bijeli dvokrilni dva komada"
      "vrata 900x2100 antracit"
      "komarnik 80 puta 120"
      "sobna vrata 80 puta 200 lijeva kupaonica"
      "komarnik 120 puta 140 plise magnetni"

    Vraća dict s poljima za Measurement model + confidence + warnings.
    """
    original = text.strip()
    normalized = words_to_number(original)
    lower = normalized.lower()

    result = {
        "raw": original,
        "element_type": "window",
        "width_mm": None,
        "height_mm": None,
        "wing_config": "double",
        "quantity": 1,
        "color_hint": "",
        "confidence": 0.0,
        "warnings": [],
        # Sobna vrata
        "swing_direction": "",
        "door_position": "",
        "wall_thickness_mm": 0,
        # Komarnik
        "mesh_type": "",
        "mounting_type": "",
    }

    # Tip elementa — duži stringovi prvo (sobna vrata > vrata)
    for kw, val in ELEMENT_MAP.items():
        if kw in lower:
            result["element_type"] = val
            break

    # Default wing config po tipu
    if result["element_type"] in ("door", "interior_door", "balcony_door"):
        result["wing_config"] = "single"
    elif result["element_type"] == "mosquito":
        result["wing_config"] = "fixed"
    elif result["element_type"] == "roller":
        result["wing_config"] = "fixed"

    # Konfiguracija krila — duži stringovi prvo
    for kw, val in sorted(WING_MAP.items(), key=lambda x: -len(x[0])):
        if kw in lower:
            result["wing_config"] = val
            break

    # Smjer otvaranja (sobna vrata)
    if result["element_type"] == "interior_door":
        for kw, val in sorted(SWING_MAP.items(), key=lambda x: -len(x[0])):
            if kw in lower:
                result["swing_direction"] = val
                break
        if not result["swing_direction"]:
            result["swing_direction"] = "inward"  # default

    # Pozicija vrata (prostorija)
    if result["element_type"] in ("interior_door", "door"):
        for kw, val in DOOR_POSITION_MAP.items():
            if kw in lower:
                result["door_position"] = val
                break

    # Debljina zida
    wall_match = re.search(r"(?:zid|stjena|stijena)\s*(\d{2,3})\s*(?:mm|milimetar)?", lower)
    if wall_match:
        result["wall_thickness_mm"] = int(wall_match.group(1))

    # Komarnik specifika
    if result["element_type"] == "mosquito":
        for kw, val in MESH_MAP.items():
            if kw in lower:
                result["mesh_type"] = val
                break
        for kw, val in sorted(MOUNTING_MAP.items(), key=lambda x: -len(x[0])):
            if kw in lower:
                result["mounting_type"] = val
                break

    # Boja
    colors = [
        "bijeli",
        "bijela",
        "sivi",
        "siva",
        "crni",
        "crna",
        "antracit",
        "zlatni",
        "zlatna",
        "smeđi",
        "smeđa",
        "boja",
        "ral",
        "orah",
        "hrast",
        "mahagonij",
        "wenge",
        "brijest",
        "jasen",
    ]
    for c in colors:
        if c in lower:
            result["color_hint"] = c
            break

    # Dimenzije — prioritet: direktni brojevi "NNN x MMM" ili "NNN puta MMM"
    dim = re.search(r"(\d{2,4})\s*(?:x|×|puta|[xX])\s*(\d{2,4})", lower)
    if dim:
        result["width_mm"] = int(dim.group(1))
        result["height_mm"] = int(dim.group(2))
    else:
        # Pokušaj iz slobodnog teksta — uzmi prva dva 2-4 znamenkasta broja
        nums = re.findall(r"\b(\d{2,4})\b", lower)
        # Filtriraj poznate "šumove" (godina, cijena...)
        nums = [int(n) for n in nums if 200 <= int(n) <= 5000]
        if len(nums) >= 2:
            result["width_mm"] = nums[0]
            result["height_mm"] = nums[1]

    # Auto-scale cm → mm za sobna vrata (80x200 → 800x2000)
    if result["width_mm"] and result["height_mm"]:
        w, h = result["width_mm"], result["height_mm"]
        if result["element_type"] in ("door", "interior_door", "balcony_door"):
            if w < 200 and h < 300:
                result["width_mm"] = w * 10
                result["height_mm"] = h * 10
                result["warnings"].append(
                    f"Interpretirano kao {result['width_mm']}x{result['height_mm']}mm (pretvoreno iz cm)"
                )
        elif result["element_type"] == "window":
            if w < 200 and h < 200:
                result["width_mm"] = w * 10
                result["height_mm"] = h * 10
                result["warnings"].append(
                    f"Interpretirano kao {result['width_mm']}x{result['height_mm']}mm (pretvoreno iz cm)"
                )

    # Količina
    qty = re.search(r"(\d+)\s*(?:kom|komad|komada|kos|piece|kos\.)", lower)
    if qty:
        result["quantity"] = int(qty.group(1))
    # "dva komada", "tri komada" — word form
    qty_words = {"dva": 2, "tri": 3, "četiri": 4, "cetiri": 4, "pet": 5, "šest": 6, "sedam": 7, "osam": 8}
    for w, n in qty_words.items():
        if re.search(w + r"\s*(?:kom|komada?|kos)?", lower):
            result["quantity"] = n
            break

    # Confidence i validacija
    warnings = result["warnings"]
    conf = 0.4

    if result["width_mm"] and result["height_mm"]:
        conf += 0.4
        w, h = result["width_mm"], result["height_mm"]

        # Tip-specifične provjere
        if result["element_type"] == "interior_door":
            # Standardna sobna vrata: 600-1000mm × 1970-2100mm
            if w < 500 or w > 1200:
                warnings.append(f"Neuobicajena sirina sobnih vrata: {w}mm (standard: 600-1000mm)")
                conf -= 0.1
            if h < 1900 or h > 2300:
                warnings.append(f"Neuobicajena visina sobnih vrata: {h}mm (standard: 1970-2100mm)")
                conf -= 0.1
        elif result["element_type"] == "door":
            if h < 1800:
                warnings.append(f"Ulazna vrata od {h}mm su niska (standard: 2000-2200mm)")
                conf -= 0.1
        else:
            if w < 300 or w > 5000:
                warnings.append(f"Neobicna sirina: {w}mm!")
                conf -= 0.15
            if h < 300 or h > 4000:
                warnings.append(f"Neobicna visina: {h}mm!")
                conf -= 0.15

        if w == h and result["element_type"] not in ("mosquito",):
            warnings.append("Sirina = visina (kvadrat) — je li ispravno?")
        if w > h and result["element_type"] in ("door", "interior_door", "balcony_door"):
            warnings.append("Vrata su sira nego visa — provjeri orijentaciju!")
    else:
        warnings.append("Dimenzije nisu prepoznate — unesi rucno")
        conf -= 0.2

    if result["element_type"] != "window":
        conf += 0.05

    # Bonus confidence za prepoznate detalje
    if result["door_position"]:
        conf += 0.05
    if result["swing_direction"]:
        conf += 0.05
    if result["mesh_type"]:
        conf += 0.05

    result["confidence"] = round(min(max(conf, 0.0), 1.0), 2)
    result["warnings"] = warnings
    return result
