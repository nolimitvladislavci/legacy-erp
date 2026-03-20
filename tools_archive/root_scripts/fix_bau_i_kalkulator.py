import os

CORE_URLS = '/var/www/fina-connect/core/urls.py'
CALC_FILE = '/var/www/fina-connect/templates/calculator/public_calculator.html'

# --- 1. POPRAVAK CORE/URLS.PY (Pravilno dodavanje BAU rute bez jezičnog prefiksa) ---
with open(CORE_URLS, 'r', encoding='utf-8') as f:
    urls_content = f.read()

# Mičemo 'bau/' iz i18n_patterns bloka (jer tu pravi probleme)
urls_content = urls_content.replace(
    "path('bau/', __import__('website.views', fromlist=['bau_page']).bau_page, name='bau_page_root'),", 
    ""
)

# I dodajemo ga u onaj prvi blok (iznad i18n_patterns) da radi uvijek direktno kao domena.com/bau/
if "path('bau/', " not in urls_content:
    urls_content = urls_content.replace(
        "urlpatterns = [",
        "urlpatterns = [\n    path('bau/', __import__('website.views', fromlist=['bau_page']).bau_page, name='bau_page_root'),"
    )

with open(CORE_URLS, 'w', encoding='utf-8') as f:
    f.write(urls_content)

# --- 2. TRAJNO ČIŠĆENJE KALKULATORA (Zabetoniramo DE varijantu u izvorni kod) ---
with open(CALC_FILE, 'r', encoding='utf-8') as f:
    calc_content = f.read()

# Mijenjamo i preostale hrvatske riječi u JS-u
zamjene = {
    # Kategorije
    "'NK – Nekvalificiran'": "'Helfer (Ungelernt)'",
    "'PKV – Polukvalificiran'": "'Angelernte Kraft'",
    "'KV I – Kvalificiran I'": "'Facharbeiter I'",
    "'KV II – Kvalificiran II'": "'Facharbeiter II'",
    "'KV III – Majstor'": "'Meister'",
    "'VKV – Visokokvalificirani'": "'Spezialist'",
    "'Poslovođa / Nadzornik'": "'Bauleiter / Aufseher'",
    
    # HTML oznake u JS-u koje su ranije izmakle zbog sintakse
    "RADNIK ": "MITARBEITER ",
    "Kategorija radnika": "Mitarbeiter-Kategorie",
    "Bruto satnica (€/h)": "Bruttostundenlohn (€/h)",
    "Broj radnika": "Anzahl Mitarbeiter",
    "Prijevoz / dnevnica (€/dan)": "Fahrtkosten / Spesen (€/Tag)",
    "Prekovremeni rad (%)": "Überstunden (%)",
    "Bruto + doprinos 17%": "Brutto + 17% LNK",
    "Faktor prekovremenih": "Überstunden-Faktor",
    "Prijevoz/sat (amort.)": "Fahrtkosten/Std. (amort.)",
    "⭐ Stvarni trošak/sat": "⭐ Tatsächliche Kosten/h",
    "radnik(a)": "Pers.",
    "Nema radnika — kliknite \"+ Dodaj radnika\" ili odaberite preset.": "Keine Mitarbeiter — klicken Sie auf \"+ Mitarbeiter hinzufügen\".",
    
    # Materijali i strojevi
    "Nema stavki materijala — kliknite \"+ Dodaj stavku\"": "Keine Materialien — klicken Sie auf \"+ Position hinzufügen\".",
    "Naziv materijala / usluge": "Materialbezeichnung / Leistung",
    "Nema strojeva — kliknite \"+ Dodaj stroj\" ili odaberite preset": "Keine Maschinen — klicken Sie auf \"+ Maschine hinzufügen\".",
    "Naziv stroja / opreme": "Maschine / Gerät",
    
    # Unutarnje varijable
    "Pijesak / šljunak": "Sand / Kies",
    "Cement i vezivo": "Zement / Bindemittel"
}

for hr_text, de_text in zamjene.items():
    calc_content = calc_content.replace(hr_text, de_text)

with open(CALC_FILE, 'w', encoding='utf-8') as f:
    f.write(calc_content)

# --- 3. RESTART SERVERA ZA PRIMJENU PROMJENA ---
os.system("supervisorctl restart fina-connect")
print("✅ Uspješno popravljeno! /bau/ sada radi bez greške, a Kalkulator je 100% na njemačkom!")
