#!/usr/bin/env python3
"""
BORG-0: Rule-based klasifikacija "other" artikala.
Direktno ažurira item_class + fiscal_treatment u bazi.

Pokretanje:
  ./venv/bin/python scripts/borg0_classify.py --dry-run
  ./venv/bin/python scripts/borg0_classify.py --execute
"""
import django, os, sys, re
from collections import Counter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from inventory.models import InventoryItem
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

# ─── RULES ────────────────────────────────────────────────────────────
# (keywords, item_class, fiscal_treatment, new_category)
# Redoslijed je bitan: prvi match pobjeđuje!
RULES = [
    # ── USLUGE ───────────────────────────────────────────────────────
    (['uslug', 'servis', 'montaž', 'instalac', 'popravak', 'remont',
      'adaptac', 'naknada', 'provizij', 'konzultac', 'savjet',
      'prijevoz', 'transport', 'dostava', 'najam', 'zakup',
      'održavan', 'čišćen', 'certifikac', 'kontrola',
      'ispitivan', 'puštanje', 'dimnjačar', 'nadzor',
      'projekt', 'izrada proj', 'rad stroj', 'rad na',
      'akontacija', 'uplata', 'avans', 'predujam',
      'utovar', 'istovar', 'iskop', 'rušenj', 'demontaž'],
     'service', 'service_cash', 'service'),

    # ── ALKOHOLNA PIĆA (AL. prefix = povratna ambalaža/alkohol) ──────
    (['al.amaro', 'al.ballant', 'al.brandy', 'al.jager', 'al.kruškov',
      'al.lavov', 'al.liker', 'al.pelinkov', 'al.rum', 'al.šljivo',
      'al.stock', 'al.travar', 'al.vekija', 'al.vodka', 'al.whiskey',
      'al. liker', 'al. rum', 'al. brandy'],
     'tangible', 'standard', 'drink'),

    # ── PIĆE ─────────────────────────────────────────────────────────
    (['cappuccin', 'cappucin', 'cappy', 'cedevita', 'coca cola', 'coca-cola',
      'fanta', 'sprite', 'pepsi', 'juice', 'sok ', 'sok-', 'ledeni čaj',
      'jana ', 'jamnica', 'gaziran', 'mineralna', 'kisela voda',
      'voda 0,', 'voda 1,', 'nescafe', 'kava ', 'čaj ', 'espresso',
      'tonik', 'red bull', 'energetsk', 'pivo ', 'heineken', 'pan ',
      'karlovačk', 'ožujsk', 'laško', 'vino ', 'prosecco', 'gemišt',
      'radler', 'bevanda', 'rakija', 'šljivov', 'travarica', 'loza',
      'medica', 'biska', 'viljamov', 'pelinkov', 'orahovac',
      'viski', 'votka', 'gin ', 'tequila', 'brandy', 'konjak',
      'aperol', 'jäger', 'campari', 'bailey', 'limunada'],
     'tangible', 'standard', 'drink'),

    # ── HRANA (pripremljena) ─────────────────────────────────────────
    (['ćevap', 'pljeskav', 'burger', 'pizza', 'sendvič', 'salata',
      'juha', 'čorba', 'gulaš', 'paprikaš', 'sarma', 'burek',
      'pita', 'kroasan', 'pecivo', 'kruh', 'pogača', 'lepinja',
      'torta', 'kolač', 'sladoled', 'palačink', 'pomfrit',
      'tost ', 'hot dog', 'kebab', 'gyros', 'wrap',
      'ajvar', 'ketchup', 'majonez', 'senf ', 'dresing'],
     'tangible', 'standard', 'food'),

    # ── HRANA (namirnice/sirovine) ───────────────────────────────────
    (['brašno', 'šećer', 'sol ', 'ulje ', 'ocat', 'mlijeko',
      'sir ', 'vrhnje', 'jogurt', 'maslac', 'jaje', 'jaja',
      'meso ', 'svinj', 'govedina', 'piletina', 'puretina',
      'riba', 'šunka', 'kobasic', 'salama', 'pršut',
      'voće', 'jabuka', 'banana', 'naranča', 'limun',
      'povrće', 'krumpir', 'luk ', 'mrkva', 'paprika',
      'paradajz', 'rajčica', 'krastavac', 'kupus',
      'riža', 'tjestenina', 'špageti', 'gnocchi',
      'začin', 'papar', 'vegeta', 'cimet', 'vanilija',
      'čokolad', 'bombon', 'keks', 'grickalice', 'čips',
      'med ', 'marmelad', 'džem', 'nutella', 'namaz'],
     'tangible', 'standard', 'food'),

    # ── AGROHEMIJA / ZAŠTITNA SREDSTVA ───────────────────────────────
    (['agrofol', 'agrosol', 'aminogreen', 'aminoton', 'aminovital',
      'amistar', 'calisto', 'champion', 'chromorel', 'chromovit',
      'afalon', 'caramb', 'cash 480', 'agil ', 'agil-',
      'herbicid', 'fungicid', 'insekticid', 'pesticid',
      'gnojivo', 'đubrivo', 'amcopaste', 'amco potato',
      'agromaster', 'sjeme', 'sjem.', 'certificiran',
      'uljana repica', 'pšenica', 'kukuruz', 'ječam', 'soja',
      'suncokret', 'lucerna', 'djetelin', 'trava ',
      'sadnica', 'biljka', 'stablo'],
     'tangible', 'standard', 'material'),

    # ── GRAĐEVINSKI MATERIJAL ────────────────────────────────────────
    (['cement', 'beton', 'cigla', 'blok ', 'opeka',
      'agregat', 'šljunak', 'pijesak', 'kamen ',
      'armatur', 'čelik', 'željez', 'profil', 'lim ',
      'čavl', 'vijak', 'matica', 'podložn',
      'cijev', 'čep ', 'koljen', 'redukcij', 'spojnic',
      'ventil', 'slavina', 'kuglast', 'zaporni',
      'izolac', 'stiropor', 'kamena vuna', 'staklena vuna',
      'foli', 'traka samolj', 'brtva', 'silikon',
      'ljepilo', 'mort', 'žbuka', 'glet', 'fasada',
      'disperzij', 'boja ', 'lak ', 'premaz',
      'pločic', 'keramik', 'fuga', 'hidroizolac',
      'knauf', 'gips', 'rigips', 'suhomontaž',
      'ploča', 'panel', 'daska', 'greda', 'laminat',
      'parket', 'brodski pod',
      'rozeta', 'nosač', 'baserail', 'unirail',
      'trapezn', 'limeni', 'oluk', 'žljeb',
      'geotekstil', 'geomreža', 'drenažn',
      'šahtov', 'revizion', 'poklopac',
      'cijev kan', 'kanalsk', 'pvc cijevi'],
     'tangible', 'standard', 'material'),

    # ── INSTALATERSKI / VODOINSTALATERSKI MATERIJAL ──────────────────
    (['radijator', 'kotao', 'peć ', 'dimnjak', 'kalorimati',
      'kalormat', 'termost', 'bojler', 'grijač',
      'pumpa', 'cirkulac', 'ekspanzion',
      'solarni', 'fotonapons', 'inverter',
      'kabel', 'prekidač', 'utičnic', 'osigurac',
      'led žarulja', 'žarulj', 'rasvjet', 'reflektor',
      'vaill', 'vaillant', 'junkers', 'buderus', 'viessmann',
      'caleffi', 'giacomini', 'danfoss',
      'adapter reg', 'regulator', 'plinsk'],
     'tangible', 'standard', 'material'),

    # ── ALATI / OPREMA ───────────────────────────────────────────────
    (['alat', 'bušilica', 'brusilica', 'pila ', 'čekić',
      'odvijač', 'kliješta', 'ključ ', 'set ključ',
      'mjerač', 'vaga', 'termometar', 'manometar',
      'ljestve', 'skela',
      'četka', 'čistač'],
     'tangible', 'standard', 'tool'),

    # ── AUTO DIJELOVI / VOZILA ───────────────────────────────────────
    (['alternator', 'akumulator', 'filtar ', 'filter ',
      'ulje motor', 'antifriz', 'kočion', 'disk kočn',
      'ležaj', 'remen', 'svjećic', 'brisač',
      'guma ', 'pneumatik', 'felga',
      'auto ', 'kamion', 'kombi', 'prikolica', 'traktor'],
     'tangible', 'standard', 'equipment'),

    # ── IT / ELEKTRONIKA ─────────────────────────────────────────────
    (['adapter tp-link', 'router', 'switch', 'monitor',
      'računal', 'laptop', 'printer', 'tonер', 'tinta',
      'kabel usb', 'kabel hdmi', 'mobitel', 'tablet'],
     'tangible', 'standard', 'equipment'),

    # ── AMBALAŽA ─────────────────────────────────────────────────────
    (['čaše to go', 'čaša', 'vrećic', 'ambalaž',
      'folija stretch', 'karton', 'kutija', 'sanduk',
      'paleta ', 'euro paleta', 'kontejner'],
     'tangible', 'standard', 'consumable'),

    # ── STOČARSTVO ───────────────────────────────────────────────────
    (['krava', 'junad', 'june', 'tele', 'svinja', 'prase',
      'ovca', 'janje', 'koza', 'jarac', 'kokoš', 'pile',
      'stočna hrana', 'sijeno', 'slama', 'silaž',
      'koncentriran', 'premiks'],
     'tangible', 'standard', 'food'),

    # ── DRVA / ENERGENTI ─────────────────────────────────────────────
    (['drva', 'peleta', 'peleti', 'briket', 'piljevina',
      'ogrev', 'ogrjev'],
     'tangible', 'standard', 'material'),

    # ── OPTIKA / NAOČALE (Konjik komitent) ───────────────────────────
    (['dptr.o.', 'dptr. o.', 'dioptr', 'leća ', 'leća-',
      'sunč.n.', 'suncane naocale', 'sunčane',
      'centrostyle', 'sunoptic', 'aboriginal', 'tom tailor',
      'christies', 'massimo', 'julia', 'clark', 'backer',
      'clip on', 'sportske naočale', 'dječje naočale',
      'okvir ', 'kontaktne leće', 'otopina za leće',
      'etui ', 'futrola za', 'krpica za'],
     'tangible', 'standard', 'product'),

    # ── VAILLANT / ARISTON / KOTLOVI (generički) ────────────────────
    (['ariston', 'vaillant', 'junkers', 'buderus', 'viessmann',
      'baxi', 'bosch', 'wolf ', 'protherm', 'beretta',
      'anoda', 'aqua senzor', 'antifog', 'ntc',
      'produžetak 80', 'dimovodni', 'ekspanzion',
      'izmjenjivač', 'plamen', 'herz ',
      'elektroda', 'plamenik', 'gorionik'],
     'tangible', 'standard', 'equipment'),

    # ── ADAPTER / OPĆENITI MATERIJAL ─────────────────────────────────
    (['adapter', 'adaoter', 'prijelaz', 'obujmica', 'spojka',
      'redukcija', 'nastavak', 'produžetak', 'kolčak',
      'crijevo', 'gibljiv', 'fleksibil',
      'posuda', 'sifon', 'odvod', 'preljev',
      'manžeta', 'gumena', 'brtveni',
      'nosač', 'držač', 'konzola', 'stezaljk',
      'opruga', 'osovina', 'zupčanik',
      'armirana', 'mreža ', 'žica '],
     'tangible', 'standard', 'material'),

    # ── KLIMA / VENTILACIJA ──────────────────────────────────────────
    (['klima', 'ventilator', 'rekuperat', 'kanalni',
      'odvlaživ', 'ovlaživ', 'usisavač'],
     'tangible', 'standard', 'equipment'),

    # ── RADOVI (usluge) ──────────────────────────────────────────────
    (['radovi', 'rad str', 'dobava i mont', 'dobava',
      'oblaganj', 'betoniran', 'zidanj', 'malterisan',
      'armirač', 'tesarsk', 'elektroinstal',
      'vodoinstal', 'strojarsk', 'hidroinstal',
      'analiza kvalit', 'ispitiv', 'mjerenje'],
     'service', 'service_cash', 'service'),

    # ── PIZZA / FAST FOOD ────────────────────────────────────────────
    (['margherit', 'capriccios', 'funghi', 'quattro',
      'calzone', 'focaccia', 'bruschett',
      'cheeseburger', 'chicken burger', 'cheese burger',
      'nuggets', 'wings', 'ražnjić', 'čevapčić',
      'punjena', 'pohovan', 'na žaru', 'grill'],
     'tangible', 'standard', 'food'),

    # ── OSNOVNA SREDSTVA (eksplicitno) ───────────────────────────────
    (['osnovna sredstv', 'os-', 'inventar br',
      'ares rt', 'ups ', 'server ', 'fotokopirn'],
     'asset', 'no_fiscal', 'equipment'),

    # ── OSTATAK — GENERIČKI ARTIKL ───────────────────────────────────
    (['aluminij', 'bakar', 'mesing', 'inox',
      'pp-r', 'pvc', 'pe cijev', 'hdpe',
      'mocoa', 'agada', 'amaro',
      'plinska', 'plinski'],
     'tangible', 'standard', 'material'),

    # ── VAILLANT REZERVNI DIJELOVI (skraćenice) ──────────────────────
    (['osjetnik', 'membran', 'presostat', 'p.c.b.',
      'gumb', 'sklopka', 'termoelement', 'razdjelnik',
      'regulacij', 'modul', 'glava', 'kolj.',
      'račva', 'wavin', 'wav.', 'viega', 'itap',
      'vartec', 'lampart', 'sivi', 'pe-line',
      'okom.', 'kug.', 'ven.', 'rad.',
      'dimovod', 'turbulen', 'zaporna'],
     'tangible', 'standard', 'material'),

    # ── AUTOMOBILI / VOZILA (osnovna sredstva) ───────────────────────
    (['automobil', 'mercedes', 'volkswagen', 'peugeot',
      'opel', 'nissan', 'toyota', 'renault', 'fiat',
      'citroën', 'citroen', 'ford ', 'bmw', 'audi',
      'škoda', 'skoda', 'polo vw', 'passat', 'golf ',
      'kamion man', 'navara', 'boxer', 'korsa',
      'insignia'],
     'asset', 'no_fiscal', 'equipment'),

    # ── UDRUGE / ČLANARINA ───────────────────────────────────────────
    (['članarin', 'clanarin', 'donacija', 'dotacija',
      'kotizacij', 'sponzorstvo', 'bonifikacij'],
     'tangible', 'exempt_pdv', 'service'),

    # ── USLUGE (prošireno) ───────────────────────────────────────────
    (['izmjena', 'zamjena', 'ugradnja', 'izrada',
      'program', 'asfaltiran', 'balansiraj',
      'odzračivan', 'čišćenj', 'punjenje',
      'trošak', 'razlika u cij', 'doprema',
      'pranje', 'sortiranj', 'sušenje',
      'sijačic', 'bacanje gnojiv'],
     'service', 'service_cash', 'service'),

    # ── AGROHEMIJA (dodatno) ─────────────────────────────────────────
    (['artea', 'axial', 'azocip', 'aztek', 'backrow',
      'algacifo', 'aminoigreen', 'amister', 'amosulfan',
      'aquafol', 'arvalin', 'ascoleg', 'acuna',
      'okvašivač', 'sredstvo za zaš'],
     'tangible', 'standard', 'material'),

    # ── HRANA (dodatno) ───────────────────────────────────────────────
    (['baklava', 'b-aktiv', 'dukat', 'aurora umak',
      'badel', 'lančić', 'impala',
      'rum 1,0', 'rum domaći'],
     'tangible', 'standard', 'food'),

    # ── MATERIJAL FALLBACK (generički) ───────────────────────────────
    (['materijal', 'jed.', 'povratna', 'automat',
      'lančić', 'bala', 'bale'],
     'tangible', 'standard', 'material'),

    # ── STOČARSTVO (prošireno) ───────────────────────────────────────
    (['bik', 'bikovi', 'junica', 'krmača', 'prasad',
      'steona', 'muzna', 'tovljen', 'grlo',
      'biljna masa', 'smilje', 'lavanda',
      'balirka', 'berač kamili', 'sijačic'],
     'tangible', 'standard', 'food'),

    # ── BEZALKOHOLNA PIĆA ────────────────────────────────────────────
    (['bezalkoholn', 'bijela kava', 'topla čoko',
      'shake', 'smoothie', 'frappe'],
     'tangible', 'standard', 'drink'),

    # ── HRANA (restoran) ─────────────────────────────────────────────
    (['odrezak', 'bečki', 'miješano meso', 'miješana sal',
      'prilog', 'pommes', 'njoki', 'gnocchi', 'rižoto',
      'cordon bleu', 'schnitzel', 'steak'],
     'tangible', 'standard', 'food'),

    # ── AGROHEMIJA (još veći popis) ──────────────────────────────────
    (['banvel', 'barrier', 'bastional', 'bazano', 'beetup',
      'benta', 'betanal', 'betha', 'biofixin', 'biolife',
      'brodifacoum', 'bumper', 'butisan', 'callisto',
      'chorus', 'corum', 'decis', 'dual gold',
      'eclipse', 'elumis', 'equip', 'falcon',
      'focus ultra', 'fusilade', 'galaxy', 'gardo gold',
      'harmony', 'husar', 'laudis', 'lontrel',
      'lumax', 'merlin', 'metafol', 'milagro',
      'motivell', 'mustang', 'nativo', 'opera',
      'orius', 'pictor', 'prosaro', 'proteus',
      'pulsar', 'racer', 'retengo', 'roundup',
      'safari', 'sekator', 'select', 'sencor',
      'starane', 'stomp', 'stratos', 'successor',
      'sultan', 'tango', 'tarot', 'terbis',
      'toprex', 'trend', 'venzar', 'wing-p',
      'amistar opti'],
     'tangible', 'standard', 'material'),

    # ── KAMEN (Bianco Sardo itd.) ────────────────────────────────────
    (['bianco sardo', 'granit', 'mramor', 'travertin',
      'oniks', 'bazalt', 'porfir', 'kvarcit'],
     'tangible', 'standard', 'material'),

    # ── ANTIFREEZE / KEMIJA ──────────────────────────────────────────
    (['antifreeze', 'antifriz', 'adh', 'baza rehau',
      'konstrukcija', 'asvaltiran', 'atypika'],
     'tangible', 'standard', 'material'),
]

# Kompajliraj regex verzije za brži match
COMPILED_RULES = []
for keywords, item_class, fiscal, category in RULES:
    pattern = re.compile('|'.join(re.escape(k) for k in keywords), re.IGNORECASE)
    COMPILED_RULES.append((pattern, item_class, fiscal, category))


def classify(name):
    """Klasificiraj po imenu. Vraca (item_class, fiscal, category) ili None."""
    name_lower = name.lower()
    for pattern, item_class, fiscal, category in COMPILED_RULES:
        if pattern.search(name_lower):
            return item_class, fiscal, category
    return None


def run(dry_run=True):
    others = InventoryItem.objects.filter(category='other')
    total = others.count()
    print(f'BORG-0: {total} "other" artikala')

    classified = 0
    unmatched = 0
    stats = Counter()
    unmatched_names = []

    for item in others.only('id', 'name', 'category', 'item_class', 'fiscal_treatment'):
        result = classify(item.name)
        if result:
            item_class, fiscal, category = result
            stats[category] += 1
            classified += 1
            if not dry_run:
                item.item_class = item_class
                item.fiscal_treatment = fiscal
                item.category = category
                item.save(update_fields=['item_class', 'fiscal_treatment', 'category'])
        else:
            unmatched += 1
            unmatched_names.append(item.name)

    print(f'\nKlasificirano: {classified} ({classified*100/total:.1f}%)')
    print(f'Neprepoznato:  {unmatched} ({unmatched*100/total:.1f}%)')
    print(f'\nPo kategoriji:')
    for cat, count in stats.most_common():
        print(f'  {cat}: {count}')

    if dry_run:
        print(f'\n--- DRY RUN — baza NIJE promijenjena ---')
        # Pokazi uzorak neprepoznatih
        print(f'\nUzorak neprepoznatih (prvih 50):')
        for n in unmatched_names[:50]:
            print(f'  {n}')

    return classified, unmatched, unmatched_names


if __name__ == '__main__':
    dry = '--execute' not in sys.argv
    run(dry_run=dry)
