#!/usr/bin/env python3
"""Generira revidiranu ponudu VIS-AN-2026-002-R1 s materijalom, Hansgrohe UP armat., LED korekcijom."""
import sys
sys.path.insert(0, '/var/www/fina-connect')
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from weasyprint import HTML
from datetime import date
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

# ─── KALKULACIJA ─────────────────────────────────────────────────────────────
# Cilj: kupac plaća 17.000 EUR brutto (inkl. 19% MwSt.)
# => netto = 17.000 / 1.19 = 14.286 EUR
# Radovi + materijal mora stati u 14.286 EUR netto

# MATERIJAL — stvarne cijene Fachhandel 2026 (bez montaže)
materijal = [
    # Armature Hansgrohe — UP podžbukne
    ("Hansgrohe iBox universal 2 Grundkörper DN15 (01500180)",
     "Unterputz-Einbaukörper für Thermostat und Mischer — passend für ShowerSelect Comfort",
     1, "Stk", 79.00),
    ("Hansgrohe ShowerSelect Comfort Q Thermostat UP (15583000)",
     "Unterputz-Thermostat für 2 Verbraucher, SafetyStop 40°C, chrom — für Dusche",
     1, "Stk", 495.00),
    ("Hansgrohe Metris UP-Grundkörper Waschtischmischer Wandmontage (13622180)",
     "Unterputz-Grundkörper für Waschtischmischer Wandmontage, inkl. Anschlüsse",
     1, "Stk", 138.00),
    ("Hansgrohe Metris Einhebel-Waschtischmischer UP Wandmontage 225mm (31086000)",
     "Unterputz, Ausladung 225 mm, EcoSmart 5 l/min, chrom",
     1, "Stk", 298.00),
    # Sanitärkeramik
    ("WC-Komplett-Set Wand-WC + Geberit UP-Spülkasten",
     "Wand-WC spülrandlos, Tiefspüler, Soft-Close Sitz + Geberit UP320 Spülkasten + Betätigungsplatte weiß",
     1, "pau", 480.00),
    ("Waschtisch Aufsatz/Unterbau 60 cm",
     "Keramik-Aufsatzwaschtisch 60x42 cm, Hahnloch mittig, mit Unterschrank optional — Kupac bira model",
     1, "pau", 220.00),
    ("Einhebelmischer WC-Zulauf (Kalt) für Küche ab Wasserzähler",
     "Absperrventil DN15 + Eckventil + Flexschlauch 50 cm — Kaltwasser für Küche vom Wasserzähler",
     1, "pau", 45.00),
    # Rohre und Fittings
    ("Kupferrohr Cu 15mm für Heizung (Radiator versetzen)",
     "Cu-Rohr weich Ø15mm, 3m Rolle + 4 Löt-Bögen 90° + 2 Muffen + Lot/Flussmittel — Nastavak na postojeću Cu-instalaciju grijanja",
     1, "pau", 65.00),
    ("PE-X/AL-PE Verbundrohr 16mm für Sanitär (KW+WW)",
     "Mehrschichtverbundrohr Ø16mm, 25m Rolle + Pressfittinge (Schellen, Bögen, T-Stücke) für KW+WW-Leitungen",
     1, "pau", 185.00),
    ("HT-Abflussrohre DN50/DN100 + Formteile",
     "HT-Rohr DN100 2m, DN50 3m + Bögen + T-Stücke + Revisionsdeckel — Abwasser komplett",
     1, "pau", 120.00),
    ("Bodenablauf DN50 Edelstahl Design (für Dusche)",
     "Flacher Bodenablauf DN50, Edelstahl-Rost bündig, Geruchsverschluss, Tiefe 70mm",
     1, "Stk", 85.00),
    # Elektro
    ("FI-Schutzschalter RCD Typ A 40A/30mA",
     "Fehlerstromschutzschalter Typ A (Pflicht für Bad/WC nach VDE 0100-701) — montieren in Verteiler",
     1, "Stk", 68.00),
    ("LED RGB Einbaustrahler 12V IP44 für Nischen x3",
     "3× LED-Einbaustrahler RGB+W, 12V, IP44, Ø68mm Schnitt, dimmbar per Schalter — für 3 Nischen (obrnuta piramida)",
     3, "Stk", 38.00),
    ("LED-Trafo 12V 60W Unterputz",
     "Konstantspannungstrafo 12V DC, 60W, IP20, für Nischen-LED und optional Lichtband",
     1, "Stk", 42.00),
    ("Lichtschalter + Schalterdose für RGB-Steuerung",
     "Unterputz-Schalterdose + Tastschalter für LED-RGB (dimmen/Farbwahl per Wandschalter)",
     1, "pau", 35.00),
    # Trockenbau Material
    ("Rigipsplatten GKBI 12.5mm Feuchtraum (für Decke + Wand)",
     "Rigips RB/RBI 12.5mm Feuchtraum, 10 Platten = ca. 30 m² — Decke Bad+WC + neuer Rigipszid",
     10, "Stk", 18.50),
    ("UK-Profile CW/UW 75 + Abhänger (für Decke + Zusatzwand)",
     "Stahlprofile verzinkt für Deckenkonstruktion + neuer Rigipszid 10-15cm (LED-Effektwand)",
     1, "pau", 95.00),
    ("Spachtelmasse + Bewehrungsstreifen + Grundierung",
     "Knauf Uniflott 10kg + Glasfasergewebe Tapete Anschlüsse + Tiefengrund 5L — Q2 Spachtelung komplett",
     1, "pau", 55.00),
    # Fliesen Material
    ("Feinsteinzeug Großformat 120×60 cm, rektifiziert (58.41 m² brutto)",
     "1. Wahl, Farbton Auftraggeber (Beton/Marmor/Hell), inkl. 10% Verschnitt — Wände + Boden Bad+WC+Vorsatzschale",
     58.41, "m2", 42.00),
    ("Flexkleber S1 Mapei Granirapid (für Großformat)",
     "Hochleistungskleber S1 weiß, 25kg Sack × 4 = 100kg — für Wand + Boden Großformat",
     4, "Sack", 38.00),
    ("Fugenmasse Mapei Ultracolor Plus grau 5kg × 4",
     "Zementäre Verfugung 2mm Fuge, wasserabweisend, für alle Flächen",
     4, "Stk", 22.00),
    ("Mapei Mapelastic 2K-Abdichtung 10kg",
     "Flexible Verbundabdichtung Wand/Boden-Anschluss, Duschbereich, Bodenfläche",
     1, "Eimer", 68.00),
    ("Nivelliersystem Raimondi (Keile + Clips 200 Stk)",
     "Verlegehilfe für Großformat 120×60 — verhindert Kantenversatz",
     1, "Set", 35.00),
    ("Edelstahl-Winkelprofile + Übergangsprofil",
     "Außeneck-Fliesenprofil Edelstahl 10mm × 6 Stk + Übergang Fliese/Laminat Türbereich × 2",
     1, "pau", 48.00),
]

# RADOVI — ažurirane cijene 2026 (+10% vs 2025)
radovi = [
    # Abbruch
    ("ABBRUCH | Demontage Wand- und Bodenfliesen + Rigipsdecke",
     "Abschlagen Wandfliesen 37.90 m², Aufnehmen Bodenfliesen 8.24 m², Abbau Rigipsdecke 8.24 m² — komplett inkl. Entsorgung",
     1, "pau", 2_200.00),
    ("ABBRUCH | Ausbau Sanitärobjekte + Radiator",
     "WC, Waschtisch, Badewanne, alle Armaturen + Radiator ausbauen, abschiebern, Leitungen sichern",
     1, "pau", 660.00),
    # Trockenbau
    ("TROCKENBAU | Neue Rigipsdecke Bad + WC (8.24 m²)",
     "UK 50 verzinkt, GKBI 12.5mm Feuchtraum, gespachtelt Q2 — inkl. Aussparungen für 3 LED-Nischen-Öffnungen",
     8.24, "m2", 72.00),
    ("TROCKENBAU | Vorsatzschale 15 cm (290×240 cm) mit 3 Nischen",
     "CW/UW 75, doppelt beplankt GKBI 2×12.5mm, 3 Nischen 30×30×15cm obrnuta piramida, LED-Leerrohre je Nische, Q2",
     6.96, "m2", 132.00),
    ("TROCKENBAU | Neuer Rigipszid 10-15 cm für LED-Effektwand",
     "Zusätzliche Vorsatzschale zwischen Dusche/WM und über WM ca. 2.5 m² — für RGB-Nischen und Effektlicht. Nicht in ursprünglicher Planung.",
     2.50, "m2", 145.00),
    # Sanitär
    ("SANITÄR | Trinkwasserinstallation neu — PE-X/AL-PE",
     "KW+WW ab Wasserzähleranschluss, Verlegung in Boden/Wand, Anschlüsse: WC, Waschtisch, Dusche, Absperrventile, Druckprüfung",
     1, "pau", 1_950.00),
    ("SANITÄR | Abwasserinstallation neu — HT-System",
     "DN50/DN100 Abflussrohre, Geruchsverschlüsse, Bodenablauf DN50 Edelstahl, Gefälle 2%, Dichtheitsprüfung",
     1, "pau", 880.00),
    ("SANITÄR | Radiator versetzen — KUPFERLÖSUNG",
     "Heizleitung Cu Ø15mm verlängern und anpassen (Nastavak na Cu-instalaciju, NE press-bijele), Radiator neu montieren, befüllen, entlüften. Aufpreis vs. Press-Lösung bereits eingerechnet.",
     1, "pau", 680.00),
    ("SANITÄR | Kaltwasserleitung Küche ab Wasserzähler",
     "Neue KW-Leitung DN15 PE-X vom Wasserzähler zur Küche, Absperrventil + Übergabe an Küche",
     1, "pau", 320.00),
    ("SANITÄR | Montage Sanitärobjekte komplett",
     "WC Wand-WC + Spülkasten montieren, Waschtisch + UP-Armatur Hansgrohe Metris montieren, Dusch-Thermostat ShowerSelect montieren, alle Anschlüsse, Dichtheitskontrolle",
     1, "pau", 680.00),
    # Elektro
    ("ELEKTRO | FI-Schutzschalter RCD einbauen",
     "Typ A 40A/30mA in bestehenden Verteiler einbauen, alle Feuchtraumkreise absichern, Messprotokoll VDE 0100-701. OPTION: Kunde kann bei altem System bleiben — Einsparung 320 EUR brutto.",
     1, "pau", 280.00),
    ("ELEKTRO | 3× RGB LED-Nischen 12V — auf Schalter",
     "3× LED-Einbaustrahler RGB+W 12V IP44 in Nischen einbauen, Trafo 12V UP, Wandschalter für Farbsteuerung, Leitungsverlegung. 12V Pflicht für Zone 1 (EN 60364-7-701).",
     3, "Stk", 165.00),
    # KEINE LED-Lichtkanal auf H=120cm — na zahtjev kupca isključen
    # Fliesen
    ("FLIESEN | Untergrundvorbereitung Wände + Boden",
     "Egalisieren, Unebenheiten ausgleichen, Haftgrundierung (37.90 m² Wand + 8.24 m² Boden)",
     46.14, "m2", 24.00),
    ("FLIESEN | Abdichtung Duschbereich (Mapelastic)",
     "2K-Abdichtung Wand-Boden-Anschluss umlaufend, Duschfläche, Bodenablaumanschluss",
     1, "pau", 220.00),
    ("FLIESEN | Verlegen Wandfliesen 120×60 cm",
     "Bad 24.04 m² + WC 13.86 m² + Vorsatzschale 6.96 m² = 44.86 m² | Nivelliersystem, Flexkleber S1, Fuge 2mm",
     44.86, "m2", 82.00),
    ("FLIESEN | Verlegen Bodenfliesen 120×60 cm mit Gefälle",
     "Bad 5.95 m² + WC 2.29 m² = 8.24 m² | Gefälle 1.5% zu Ablauf, Nivelliersystem",
     8.24, "m2", 90.00),
    ("FLIESEN | 3 Nischen verfliesen (Mosaik/Kleinstformat)",
     "Alle 5 Seiten je Nische 30×30×15cm, Kontrast-Mosaik oder Kleinstformat, Edelstahl-Winkelprofile",
     3, "Stk", 210.00),
    # Finish
    ("FINISH | Silikonfugen + Übergangsprofil + Endreinigung",
     "Siliconfugen alle Anschlüsse (18 lfm), 2× Edelstahl-Übergang Tür (Fliese/Laminat), komplette Bauendreinigung",
     1, "pau", 720.00),
]

# ─── KALKULACIJA ─────────────────────────────────────────────────────────────
mat_total = sum(q * ep for _, _, q, _, ep in materijal)
rad_total = sum(q * ep for _, _, q, _, ep in radovi)
netto = mat_total + rad_total
mwst = netto * 0.19
brutto = netto + mwst

print(f"Material netto:  {mat_total:>10,.2f} €")
print(f"Arbeiten netto:  {rad_total:>10,.2f} €")
print(f"NETTO gesamt:    {netto:>10,.2f} €")
print(f"MwSt 19%:        {mwst:>10,.2f} €")
print(f"BRUTTO:          {brutto:>10,.2f} €")
print(f"Ziel (Nikša):    {17_000.00:>10,.2f} €")
print(f"Differenz:       {brutto - 17_000:>+10,.2f} €")

# ─── PDF GENERIRANJE ─────────────────────────────────────────────────────────
def fmt(v): return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

html = f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;font-size:9.5pt;color:#111;margin:0;padding:16px}}
  .hdr{{display:flex;justify-content:space-between;border-bottom:3px solid #1a3a5c;padding-bottom:12px;margin-bottom:14px}}
  .logo{{font-size:17pt;font-weight:bold;color:#1a3a5c}}.logo-s{{font-size:8pt;color:#888;margin-top:2px}}
  .ang{{font-size:15pt;font-weight:bold;color:#1a3a5c;text-align:right}}.ang-s{{font-size:9pt;color:#666;text-align:right}}
  .two{{display:flex;justify-content:space-between;margin:10px 0 14px}}
  .box{{background:#f5f7fa;border-left:3px solid #1a3a5c;padding:8px 12px;width:47%}}
  .bl{{font-size:7pt;color:#999;text-transform:uppercase;margin-bottom:3px}}.bv{{font-weight:bold;font-size:9.5pt}}
  .info{{background:#fffbea;border-left:3px solid #f59e0b;padding:8px 12px;margin:8px 0;font-size:8.5pt}}
  .opt{{background:#e8f4fd;border-left:3px solid #2563eb;padding:7px 12px;margin:6px 0;font-size:8.5pt}}
  .cat{{background:#1a3a5c;color:white;padding:5px 8px;font-weight:bold;font-size:8.5pt;margin-top:10px}}
  table{{width:100%;border-collapse:collapse}}
  th{{background:#e8edf3;font-size:7.5pt;text-transform:uppercase;padding:4px 5px;text-align:left}}
  th.r{{text-align:right}}td{{padding:4px 5px;font-size:8.5pt;border-bottom:1px solid #eee;vertical-align:top}}
  td.r{{text-align:right;white-space:nowrap}}td.sub{{font-size:7.5pt;color:#666;padding-top:1px}}
  .sum-row td{{background:#f0f4f8;font-weight:bold}}
  .tot{{margin-top:12px;float:right;width:260px}}
  .tot table td{{border:none;padding:3px 7px;font-size:9pt}}
  .trow{{background:#1a3a5c;color:white;font-weight:bold;font-size:11pt}}
  .warn{{background:#fff3cd;border:1px solid #ffc107;padding:7px 10px;font-size:8pt;margin:8px 0;border-radius:3px}}
  .green{{background:#d1fae5;border:1px solid #34d399;padding:7px 10px;font-size:8.5pt;margin:8px 0;border-radius:3px}}
  .foot{{margin-top:20px;font-size:7.5pt;color:#999;border-top:1px solid #ddd;padding-top:8px;clear:both}}
  .validity{{color:#dc2626;font-weight:bold}}
</style></head><body>

<div class="hdr">
  <div><div class="logo">VISKOVIC BAU</div>
  <div class="logo-s">Bauunternehmen &bull; Stuttgart &bull; Deutschland</div>
  <div class="logo-s">Nikša Visković &bull; niksa.viskovic@limit-connect.com</div></div>
  <div><div class="ang">ANGEBOT (REVIDIERT)</div>
  <div class="ang-s">Nr. VIS-AN-2026-002-R1</div>
  <div class="ang-s">Stuttgart, {date.today().strftime('%d.%m.%Y')}</div>
  <div class="ang-s" style="color:#666;font-size:7.5pt">Ersetzt Angebot VIS-AN-2026-002 vom 13.03.2026</div></div>
</div>

<div class="two">
  <div class="box"><div class="bl">Auftraggeber</div>
  <div class="bv">Zlatan Islamovic</div>
  <div>James-F.-Byrnes-Strasse 12</div><div>70376 Stuttgart</div></div>
  <div class="box"><div class="bl">Angebotsdaten</div>
  <div>Datum: <strong>{date.today().strftime('%d.%m.%Y')}</strong></div>
  <div>Gültig bis: <strong class="validity">{date(2026,4,30).strftime('%d.%m.%Y')}</strong></div>
  <div style="font-size:8pt;margin-top:4px">Objekt: James-F.-Byrnes-Str. 12, 70376 Stuttgart<br>
  Bad ca. 6 m² + WC ca. 2 m²  &bull;  H=240 cm</div></div>
</div>

<div class="info">
  <strong>Leistungsumfang (revidiert):</strong> Komplettsanierung Bad + WC — schlüsselfertig inkl. Material.<br>
  Armature: <strong>Hansgrohe iBox-System (Unterputz)</strong> — Dusche: ShowerSelect Comfort Q Thermostat,
  Waschtisch: Metris Einhebelmischer UP Wandmontage.<br>
  LED-Effektbeleuchtung: 3× RGB-Einbaustrahler 12V in Nischen (Pflicht Zone 1, EN 60364-7-701) auf Wandschalter.
  Umlaufender LED-Kanal H=120cm <strong>entfällt</strong> auf Kundenwunsch.<br>
  Alle Preise netto zzgl. 19% MwSt. &bull; Zahlungsziel: 14 Tage netto &bull; Ausführung nach Freigabe und Versicherungsbestätigung.
</div>

<div class="opt">
  💡 <strong>OPTION FI-Schutzschalter:</strong> Nach VDE 0100-701 (§ 701) ist ein RCD Typ A für alle Stromkreise in Bad und WC 
  <strong>vorgeschrieben</strong>. Falls der Kunde das bestehende System behalten möchte, kann dieser Posten 
  entfallen — <strong>Einsparung ca. 320 € brutto</strong>. Wir empfehlen den Einbau dringend (Sicherheit, Versicherungsschutz).
</div>

<div class="opt">
  🔧 <strong>HEIZUNG / RADIATOR:</strong> Bestehende Installation mit Kupferrohr Cu Ø15mm (Innen-Ø ca. 13mm). 
  Wir verlängern <strong>mit Kupferrohr</strong> (Löt-Verbindung) — kein Übergang auf Press-Weiß (Innen-Ø nur 5-6mm = 
  stark reduzierter Durchfluss). Mehraufwand gegenüber Press-Lösung bereits einkalkuliert.
</div>

"""

# Materijal sekcija
html += '<div class="cat">A — MATERIAL (Lieferung und Bereitstellung)</div>'
html += '<table><tr><th style="width:48%">Bezeichnung</th><th style="width:26%">Spezifikation</th><th class="r" style="width:7%">Mge</th><th style="width:5%">Einh.</th><th class="r" style="width:7%">EP €</th><th class="r" style="width:7%">GP €</th></tr>\n'
mat_sum = 0
for name, spec, qty, unit, ep in materijal:
    gp = qty * ep
    mat_sum += gp
    html += f'<tr><td><strong>{name}</strong></td><td class="sub">{spec[:90]}{"…" if len(spec)>90 else ""}</td>'
    html += f'<td class="r">{qty:g}</td><td>{unit}</td><td class="r">{fmt(ep)}</td><td class="r"><strong>{fmt(gp)}</strong></td></tr>\n'
html += f'<tr class="sum-row"><td colspan="5">Zwischensumme Material</td><td class="r">{fmt(mat_sum)} €</td></tr>'
html += '</table>\n'

# Radovi sekcija
html += '<div class="cat">B — ARBEITEN (Lohn und Montage)</div>'
html += '<table><tr><th style="width:48%">Leistung</th><th style="width:26%">Details</th><th class="r" style="width:7%">Mge</th><th style="width:5%">Einh.</th><th class="r" style="width:7%">EP €</th><th class="r" style="width:7%">GP €</th></tr>\n'
rad_sum = 0
for name, spec, qty, unit, ep in radovi:
    gp = qty * ep
    rad_sum += gp
    html += f'<tr><td><strong>{name}</strong></td><td class="sub">{spec[:90]}{"…" if len(spec)>90 else ""}</td>'
    html += f'<td class="r">{qty:g}</td><td>{unit}</td><td class="r">{fmt(ep)}</td><td class="r"><strong>{fmt(gp)}</strong></td></tr>\n'
html += f'<tr class="sum-row"><td colspan="5">Zwischensumme Arbeiten</td><td class="r">{fmt(rad_sum)} €</td></tr>'
html += '</table>\n'

# Totali
html += f'''
<div class="green" style="clear:both;margin-top:12px">
  ✅ <strong>Gesamtpreis inkl. aller Materialien und Arbeiten — schlüsselfertig:</strong>
  Netto {fmt(netto)} € + 19% MwSt. {fmt(mwst)} € = <strong style="font-size:11pt">{fmt(brutto)} € BRUTTO</strong>
</div>

<div class="tot">
  <table>
    <tr><td>Material netto</td><td class="r">{fmt(mat_sum)} €</td></tr>
    <tr><td>Arbeiten netto</td><td class="r">{fmt(rad_sum)} €</td></tr>
    <tr><td><strong>Netto gesamt</strong></td><td class="r"><strong>{fmt(netto)} €</strong></td></tr>
    <tr><td>MwSt. 19%</td><td class="r">{fmt(mwst)} €</td></tr>
    <tr class="trow"><td>BRUTTO GESAMT</td><td class="r">{fmt(brutto)} €</td></tr>
  </table>
</div>

<div class="warn" style="clear:both;margin-top:12px">
  ⚠️ Nicht enthalten: Sanitärkeramik nach Kundenwahl (WC, Waschtisch, Wannenmodell wenn gewünscht — Preisindikation in Material bereits inkl. Standardauswahl).
  Eventuelle Zusatzleistungen (Schimmelbehandlung, statische Eingriffe, Sonderwünsche Fliesen Aufpreis) werden separat berechnet.
  Versicherungsabwicklung: Abrechnung direkt nach schriftlicher Versicherungsfreigabe.
  Zahlungsplan: 40% bei Auftragserteilung, 40% nach Rohbaufertigstellung, 20% bei Abnahme.
</div>

<div class="foot">
  Viskovic Bau &bull; Stuttgart &bull; Angebot Nr. VIS-AN-2026-002-R1 &bull; {date.today().strftime('%d.%m.%Y')}<br>
  Dieses Angebot ersetzt alle vorherigen Angebote für dieses Objekt. Gültig bis 30.04.2026.
  Auftragserteilung schriftlich per E-Mail oder Unterschrift auf dieser Seite.<br><br>
  Auftraggeber: __________________________ Datum: __________&nbsp;&nbsp;&nbsp;&nbsp;
  Auftragnehmer: Viskovic Bau, Nikša Visković
</div>
</body></html>'''

pdf = HTML(string=html).write_pdf()
out = '/tmp/VIS-AN-2026-002-R1_MIT_MATERIAL_Islamovic.pdf'
with open(out, 'wb') as f:
    f.write(pdf)
print(f'\nPDF: {out}  ({len(pdf)/1024:.0f} KB)')
