import os

CALC_FILE = '/var/www/fina-connect/templates/calculator/public_calculator.html'

with open(CALC_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Rječnik zamjena (Hrvatski -> Njemački) samo za JS i preostali HTML
replacements = {
    # 1. Riječi unutar renderWorkers()
    "RADNIK '": "MITARBEITER '",
    "'Kategorija radnika'": "'Mitarbeiter-Kategorie'",
    "'Bruto satnica (€/h)'": "'Bruttostundenlohn (€/h)'",
    "'Broj radnika'": "'Anzahl Mitarbeiter'",
    "'Prijevoz / dnevnica (€/dan)'": "'Fahrtkosten / Spesen (€/Tag)'",
    "'Prekovremeni rad (%)'": "'Überstunden (%)'",
    "'Bruto + doprinos 17%'": "'Brutto + 17% LNK'",
    "'Faktor prekovremenih'": "'Überstunden-Faktor'",
    "'Prijevoz/sat (amort.)'": "'Fahrtkosten/Std. (amort.)'",
    "'⭐ Stvarni trošak/sat'": "'⭐ Tatsächliche Kosten/h'",
    "radnik(a)": "Pers.",
    "radnika(a)": "Pers.",

    # 2. Riječi unutar renderMaterials()
    "'Nema stavki materijala — kliknite \"+ Dodaj stavku\"'": "'Keine Materialien — klicken Sie auf \"+ Position hinzufügen\"'",
    "'Naziv materijala / usluge'": "'Materialbezeichnung / Leistung'",

    # 3. Riječi unutar renderStrojevi()
    "'Nema strojeva — kliknite \"+ Dodaj stroj\" ili odaberite preset'": "'Keine Maschinen — klicken Sie auf \"+ Maschine hinzufügen\"'",
    "'Naziv stroja / opreme'": "'Maschine / Gerät'",

    # 4. Gumbi (koji su možda ostali na HR)
    "+ Dodaj radnika": "+ Mitarbeiter hinzufügen",
    "Brzi unos:": "Schnelleingabe:",
    "Poslovođa": "Bauleiter",
    "+ Dodaj stavku": "+ Position hinzufügen",
    "+ Dodaj stroj": "+ Maschine hinzufügen",
    "Mini bager / pila": "Minibagger / Säge",
    "Mini bager €35/dan": "Minibagger €35/Tag",
    "Srednji bager": "Bagger mittel",
    "Bager €65/dan": "Bagger €65/Tag",
    "Autodizalica": "Kran",
    "Dizalica €90/dan": "Kran €90/Tag",
    "Kamion / šleper": "LKW / Sattelzug",
    "Kamion €55/dan": "LKW €55/Tag",
    
    # 5. Preostali tekstovi u UI-u
    "Ukupno radnika": "Gesamtzahl Mitarbeiter",
    "Trošak rada/sat": "Arbeitskosten/Stunde",
    "Trošak rada/dan": "Arbeitskosten/Tag",
    "Trošak prijevoza/dan": "Fahrtkosten/Tag"
}

# Primjena zamjena
for hr_text, de_text in replacements.items():
    content = content.replace(hr_text, de_text)

# Zapisivanje promjena
with open(CALC_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ JS PRIJEVOD ODRADEN! Osvježite stranicu (Ctrl+F5) za čisti njemački.")
