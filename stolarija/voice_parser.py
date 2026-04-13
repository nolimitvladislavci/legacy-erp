import re

WORD_TO_NUM = {
    'tisuću': 1000, 'tisuća': 1000, 'tisuc': 1000,
    'devetsto': 900, 'osamsto': 800, 'sedamsto': 700,
    'šesto': 600, 'sesto': 600, 'petsto': 500, 'četiristo': 400,
    'cetiristo': 400, 'tristo': 300, 'dvjesto': 200, 'dvesto': 200,
    'sto': 100,
    'devedeset': 90, 'osamdeset': 80, 'sedamdeset': 70,
    'šezdeset': 60, 'sezdeset': 60, 'pedeset': 50,
    'četrdeset': 40, 'cetrdeset': 40, 'trideset': 30, 'dvadeset': 20,
    'devetnaest': 19, 'osamnaest': 18, 'sedamnaest': 17, 'šesnaest': 16,
    'sesnaest': 16, 'petnaest': 15, 'četrnaest': 14, 'cetmnaest': 14,
    'trinaest': 13, 'dvanaest': 12, 'jedanaest': 11, 'deset': 10,
    'devet': 9, 'osam': 8, 'sedam': 7, 'šest': 6, 'sest': 6,
    'pet': 5, 'četiri': 4, 'cetiri': 4, 'tri': 3, 'dva': 2, 'jedan': 1,
}

ELEMENT_MAP = {
    'prozor': 'window', 'balkon': 'door', 'balkonska': 'door',
    'vrata': 'door', 'ulazna': 'door', 'ulazni': 'door',
    'komarnik': 'mosquito', 'mreža': 'mosquito', 'mreza': 'mosquito',
    'fasada': 'facade',
}

WING_MAP = {
    'jednokrilni': 'single', 'jednokrilna': 'single',
    'dvokrilni': 'double', 'dvokrilna': 'double',
    'trokrilni': 'triple', 'trokrilna': 'triple',
    'fiksni': 'fixed', 'fiksna': 'fixed', 'fiksno': 'fixed',
    'klizni': 'sliding', 'klizna': 'sliding',
    'kip': 'tilt_turn', 'nagibno': 'tilt_turn',
}


def words_to_number(text: str) -> str:
    """Pretvori pisane brojeve u znamenke."""
    result = text.lower()
    for word, num in sorted(WORD_TO_NUM.items(), key=lambda x: -len(x[0])):
        result = re.sub(r'\b' + word + r'\b', f' {num} ', result)
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
    result = re.sub(r'(\b\d+\s+){1,2}\d+\b', combine_numbers, result)
    return result


def parse_voice_input(text: str) -> dict:
    """
    Parsira glasovni unos na HR jeziku u strukturirane podatke za Measurement.

    Primjeri:
      "prozor sto dvadeset puta sto četrdeset bijeli dvokrilni dva komada"
      "vrata 900x2100 antracit"
      "komarnik 80 puta 120"

    Vraća dict s poljima za Measurement model + confidence + warnings.
    """
    original = text.strip()
    normalized = words_to_number(original)
    lower = normalized.lower()

    result = {
        'raw': original,
        'element_type': 'window',
        'width_mm': None,
        'height_mm': None,
        'wing_config': 'double',
        'quantity': 1,
        'color_hint': '',
        'confidence': 0.0,
        'warnings': [],
    }

    # Tip elementa
    for kw, val in ELEMENT_MAP.items():
        if kw in lower:
            result['element_type'] = val
            break

    # Konfiguracija krila
    for kw, val in WING_MAP.items():
        if kw in lower:
            result['wing_config'] = val
            break

    # Boja
    colors = ['bijeli', 'bijela', 'sivi', 'siva', 'crni', 'crna',
              'antracit', 'zlatni', 'zlatna', 'smeđi', 'smeđa',
              'boja', 'ral']
    for c in colors:
        if c in lower:
            result['color_hint'] = c
            break

    # Dimenzije — prioritet: direktni brojevi "NNN x MMM" ili "NNN puta MMM"
    dim = re.search(r'(\d{2,4})\s*(?:x|×|puta|[xX])\s*(\d{2,4})', lower)
    if dim:
        result['width_mm'] = int(dim.group(1))
        result['height_mm'] = int(dim.group(2))
    else:
        # Pokušaj iz slobodnog teksta — uzmi prva dva 2-4 znamenkasta broja
        nums = re.findall(r'\b(\d{2,4})\b', lower)
        # Filtriraj poznate "šumove" (godina, cijena...)
        nums = [int(n) for n in nums if 200 <= int(n) <= 5000]
        if len(nums) >= 2:
            result['width_mm'] = nums[0]
            result['height_mm'] = nums[1]

    # Količina
    qty = re.search(r'(\d+)\s*(?:kom|komad|komada|kos|piece|kos\.)', lower)
    if qty:
        result['quantity'] = int(qty.group(1))
    # "dva komada", "tri komada" — word form
    qty_words = {'dva': 2, 'tri': 3, 'četiri': 4, 'cetiri': 4,
                 'pet': 5, 'šest': 6, 'sedam': 7, 'osam': 8}
    for w, n in qty_words.items():
        if re.search(w + r'\s*(?:kom|komada?|kos)?', lower):
            result['quantity'] = n
            break

    # Confidence i validacija
    warnings = []
    conf = 0.4

    if result['width_mm'] and result['height_mm']:
        conf += 0.4
        w, h = result['width_mm'], result['height_mm']
        if w < 300 or w > 5000:
            warnings.append(f"Neobična širina: {w}mm — provjeri!")
            conf -= 0.15
        if h < 300 or h > 4000:
            warnings.append(f"Neobična visina: {h}mm — provjeri!")
            conf -= 0.15
        if w == h:
            warnings.append("Širina = visina (kvadrat) — je li ispravno?")
        if w > h and result['element_type'] == 'door':
            warnings.append("Vrata su šira nego viša — provjeri orijentaciju!")
    else:
        warnings.append("Dimenzije nisu prepoznate — unesi ručno")
        conf -= 0.2

    if result['element_type'] != 'window':
        conf += 0.05

    result['confidence'] = round(min(max(conf, 0.0), 1.0), 2)
    result['warnings'] = warnings
    return result
