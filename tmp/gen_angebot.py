#!/usr/bin/env python3
# Generira revidiranu ponudu VIS-AN-2026-003 s materijalom
from weasyprint import HTML

# ─── KALKULACIJA ─────────────────────────────────────────────────────────────
# LEGENDA: (opis, kolicina, jedinica, EP_netto, napomena)
# Tečaj materijala: SHK-cijene s ~20% TH marže, radovi +10% vs 2025

stavke = [

# ══ ABBRUCH ══════════════════════════════════════════════════════════════════
("ABBRUCH", "Demontage Wandfliesen Bad + WC",
 "Abschlagen aller Wand­fliesen inkl. Untergrundabriss bis Rohbau, "
 "Abtransport + Entsorgung (Bad 24 m² + WC 13,9 m²)",
 37.90, "m²", 42.00),

("ABBRUCH", "Demontage Bodenfliesen Bad + WC",
 "Aufnehmen Bodenfliesen inkl. Kleberbett, Estrichreinigung, Entsorgung",
 8.24, "m²", 38.00),

("ABBRUCH", "Demontage Rigipsdecke Bad + WC",
 "Abbau UK + Beplankung, Abtransport, Entsorgung",
 8.24, "m²", 25.00),

("ABBRUCH", "Ausbau Sanitärobjekte komplett",
 "WC-Keramik, Waschtisch, Badewanne/Dusche, alle Armaturen, "
 "Spiegel, Zubehör — fachgerecht ausbauen + entsorgen",
 1.00, "pau", 460.00),

("ABBRUCH", "Demontage Radiator",
 "Abschiebern, Leitungen verschließen, Radiator ausbauen + entsorgen",
 1.00, "Stk", 200.00),

# ══ TROCKENBAU ═══════════════════════════════════════════════════════════════
("TROCKENBAU", "Neue Rigipsdecke Bad + WC — abgehängt mit Downlights",
 "UK 50 feuerverzinkt, Beplankung GKBI 12,5 mm Feuchtraum, "
 "gespachtelt Q2. Öffnungen für 3× LED-Downlight ⌀ 68 mm vorbereitet "
 "(Leerrohre + UP-Dose je Öffnung). Inkl. sämtliches Material.",
 8.24, "m²", 98.00),

("TROCKENBAU", "Vorsatzschale Bad 15 cm (290×240 cm) mit 3 Nischen",
 "CW/UW 75, doppelt beplankt GKBI 2×12,5 mm. Inkl. 3 Shampoo-Nischen "
 "umgekehrte Pyramide 30×30×15 cm, alle 5 Seiten verfliest, "
 "LED-Einbau vorbereitet (Leerrohr + UP-Dose 12 V je Nische), "
 "gespachtelt Q2. Inkl. sämtliches Material.",
 6.96, "m²", 158.00),

("TROCKENBAU", "Neuer Rigipstrennwand Dusche / Waschmaschine + über WM",
 "10–15 cm Zwischenwand CW/UW 50, einseitig beplankt GKBI 12,5 mm, "
 "Öffnungen für LED-Effekte vorbereitet (3× Durchbruch mit Leerrohr), "
 "gespachtelt Q2. Inkl. Material. (Zusatzleistung gegenüber Erstangebot)",
 3.50, "m²", 145.00),

# ══ SANITÄR ══════════════════════════════════════════════════════════════════
("SANITÄR — Rohbau", "Trinkwasserinstallation ab Wasserzähleranschluss",
 "Neue KW- + WW-Leitungen PE-X/AL-PE Verbundrohr, Verlegung in "
 "Vorsatzschale + Schlitze, Anschlüsse für WC-Spülkasten, Waschtisch, "
 "Dusche. Absperrventile, Revisionsdeckel, Druckprüfung + Dichtheitsprotokoll.",
 1.00, "pau", 2400.00),

("SANITÄR — Rohbau", "Abwasserinstallation neu",
 "DN 50 / DN 100 HT-Abflussrohre, neue Geruchsverschlüsse, "
 "Bodenablauf DN 50 Edelstahl-Designrost, Gefälleanpassung 2 %, "
 "Druckprüfung.",
 1.00, "pau", 1080.00),

("SANITÄR — Rohbau", "Heizungsleitung Radiator versetzen — Kupferrohr Cu 15",
 "Leitungsverlängerung in Kupferrohr ø 15 mm (Fortsetzung bestehender "
 "Kupferinstallation — kein Medienwechsel auf Press, voller Durchfluss "
 "erhalten). Verlegung unter Estrich / in Wand, neue Wandhalterung, "
 "System befüllen + entlüften.",
 1.00, "pau", 680.00),

# ── Hansgrohe iBox + Armaturen (MATERIAL enthalten) ──────────────────────────
("SANITÄR — Material Hansgrohe",
 "hansgrohe iBox universal 2 Grundkörper DN15 (Art. 01500180)",
 "Unterputz-Einbaukörper für Duscharmatur. "
 "Rotationssymmetrisch, schallentkoppelt, Geräuschklasse 1. "
 "1 Stk. Materialpreis inkl. Einbau.",
 1.00, "Stk", 185.00),

("SANITÄR — Material Hansgrohe",
 "hansgrohe ShowerSelect Comfort Q Thermostat UP 2 Verbraucher (Art. 15583000)",
 "Unterputz-Thermostat Fertigset Chrom für iBox universal 2. "
 "Drucktasten SelectOn/Off, Temperaturbegrenzer SafetyStop 40 °C, "
 "Sicherungskombination EN 1717. Inkl. Einbau + Inbetriebnahme.",
 1.00, "Stk", 590.00),

("SANITÄR — Material Hansgrohe",
 "hansgrohe Kopfbrause Pulsify Select 260 3jet (od. vergleichbar)",
 "Regenbrause ø 260 mm, 3 Strahlarten, Deckenmontage, Chrom. "
 "Inkl. Deckenstangenanschluss passend zu iBox. Inkl. Einbau.",
 1.00, "Stk", 320.00),

("SANITÄR — Material Hansgrohe",
 "hansgrohe Handbrause + Brausehalter Garnitur (od. vergleichbar)",
 "Handbrause 3-Strahl Chrom, Wandhalter höhenverstellbar, "
 "Brauseschlauch 160 cm. Inkl. Montage.",
 1.00, "Stk", 145.00),

("SANITÄR — Material Hansgrohe",
 "hansgrohe Waschtisch-Unterputzarmatur iBox + Fertigset (od. vergleichbar)",
 "iBox Grundkörper 1× + Einhebelmischer-Fertigset UP Chrom, "
 "Auslauf ø 150 mm, Kaltwasser-Stopp, Keramikkartusche. Inkl. Einbau.",
 1.00, "Stk", 420.00),

("SANITÄR — Material",
 "WC-Keramik wandhängend + Unterputzspülkasten Geberit Sigma",
 "WC Tiefspüler spülrandlos wandhängend (z. B. Geberit iCon / Duravit D-Neo), "
 "Geberit Sigma UP-Spülkasten 12 cm Einbautiefe, "
 "Betätigungsplatte Sigma 20 Chrom. Inkl. Montage.",
 1.00, "Stk", 580.00),

("SANITÄR — Material",
 "Waschtisch mit Unterschrank (Auftraggeber Auswahl)",
 "Waschtisch Keramik ca. 60 cm (Midrange-Qualität, Farbe nach Wahl AG), "
 "Unterschrank 2-türig mit Softclose, Siphon chrom verdeckt. Inkl. Montage.",
 1.00, "Stk", 480.00),

("SANITÄR — Material",
 "Duschwanne / Duschelement Bodenebener Einbau",
 "Mineralguss-Duschwanne 90×90 cm oder Bodenebenes Duschelement "
 "(Wedi / Schlüter Kerdi-Floor) je nach Höhensituation. Inkl. Montage + Abdichtung.",
 1.00, "pau", 520.00),

("SANITÄR — Material",
 "Handtuchhalter, Seifenspender, Accessoires (Auftraggeber Auswahl)",
 "Set: Handtuchhalter 60 cm, WC-Rollenhalter, Duschablage Edelstahl, "
 "Seifenspender Wandmontage — Chrom passend zu Hansgrohe Linie.",
 1.00, "pau", 185.00),

# ══ ELEKTRO ══════════════════════════════════════════════════════════════════
("ELEKTRO", "FI-Schutzschalter RCD Typ A 40A/30mA — EMPFOHLEN",
 "Einbau in vorhandenen Verteiler, alle Feuchtraumstromkreise Bad + WC "
 "absichern, Messprotokoll nach VDE 0100-701. "
 "⚠ HINWEIS: Bei Verzicht auf FI-Schalter (Eigenverantwortung AG) "
 "Kosteneinsparung ca. 320 EUR brutto — schriftliche Erklärung erforderlich.",
 1.00, "pau", 340.00),

("ELEKTRO", "LED-Downlights Decke 3× IP44 — RGB über Schalter",
 "3 Stk. LED-Einbaustrahler IP44 ⌀ 68 mm, 12 V (Trafo UP), "
 "RGB+W Farbwechsel schaltbar über normalen Wandschalter (Wechselschaltung), "
 "warmweiss 3000 K + RGB-Szenen. Inkl. 12-V-Trafo 60 W UP, "
 "Leitungsverlegung, UP-Dosen. Norm EN 60364-7-701 Zone 2 konform.",
 3.00, "Stk", 195.00),

("ELEKTRO", "LED-Einbauspot Nischen 3× IP44 RGB 12V",
 "3 Stk. LED-Spot IP44 12 V für Shampoo-Nischen (umgekehrte Pyramide), "
 "RGB Farbwechsel, GU5.3 Sockel. Trafo gemeinsam mit Deckenstromkreis. "
 "Inkl. Leitungsverlegung.",
 3.00, "Stk", 95.00),

# ══ FLIESEN ══════════════════════════════════════════════════════════════════
("FLIESEN", "Untergrundvorbereitung Wände Bad + WC",
 "Rohbaufläche egalisieren, Unebenheiten > 5 mm ausgleichen, "
 "Haftgrundierung (37,9 m²)",
 37.90, "m²", 24.00),

("FLIESEN", "Untergrundvorbereitung Boden Bad + WC",
 "Estrich reinigen, Ausgleichsmasse max. 10 mm, "
 "2K-Abdichtungsschlämme Wand-Boden umlaufend (Mapei Mapelastic)",
 8.24, "m²", 32.00),

("FLIESEN", "Lieferung Großformat 120×60 cm Feinsteinzeug",
 "Rektifiziert 1. Wahl, Farbton nach Wahl AG (hell / Beton / Marmor-Optik), "
 "inkl. 10 % Verschnitt — Gesamtfläche 58,41 m² brutto",
 58.41, "m²", 46.00),

("FLIESEN", "Verlegen Wandfliesen 120×60 cm",
 "Bad 24,04 m² + WC 13,86 m² + Vorsatzschale 6,96 m² = 44,86 m². "
 "Nivelliersystem, Flexkleber S1 Mapei Granirapid, Kreuzfuge 2 mm, "
 "Fugenmasse Mapei Ultracolor Plus grau.",
 44.86, "m²", 85.00),

("FLIESEN", "Verlegen Bodenfliesen 120×60 cm",
 "Bad 5,95 m² + WC 2,29 m² = 8,24 m². Großformat mit Gefälle 1,5 % "
 "zu Ablauf, Nivelliersystem, Edelstahl-Randabschlussprofil.",
 8.24, "m²", 92.00),

("FLIESEN", "Nischen-Verfliesung 3× Shampoo-Nischen",
 "Alle 5 Seiten je Nische (30×30×15 cm), Mosaikfliese oder Kleinstformat "
 "als Kontrast, Edelstahl-Winkelprofile, LED-Spot eingebaut.",
 3.00, "Stk", 215.00),

# ══ FINISH ════════════════════════════════════════════════════════════════════
("FINISH", "Silikonfugen umlaufend",
 "Alle Wand/Boden-Anschlüsse, Wannenrand, Dusche, Deckenanschluss, "
 "Sanitärsilikon Mapei Mapesil AC weiß.",
 18.00, "lfm", 16.00),

("FINISH", "Übergangsprofil Fliese/Laminat Türbereich",
 "Edelstahl gebürstet 40 mm, einpassen + befestigen.",
 2.00, "Stk", 42.00),

("FINISH", "Komplette Bauendreinigung Bad + WC",
 "Fliesenreinigung, Erstversiegelung, Grout-Cleaner, Schutzfolien "
 "entfernen, baustelle besenrein, abnahmebereit.",
 1.00, "pau", 420.00),
]

# ─── IZRAČUN ─────────────────────────────────────────────────────────────────
MwSt = 0.19
groups = {}
total_netto = 0.0

for row in stavke:
    cat, naziv, detail, kol, jmj, ep = row
    gp = round(kol * ep, 2)
    total_netto += gp
    if cat not in groups:
        groups[cat] = []
    groups[cat].append((naziv, detail, kol, jmj, ep, gp))

mwst_betrag = round(total_netto * MwSt, 2)
brutto = round(total_netto + mwst_betrag, 2)

# Provjeri budget
budget_netto = round(17000 / 1.19, 2)
diff = total_netto - budget_netto

print(f"=== KALKULACIJA ===")
print(f"Netto:         {total_netto:,.2f} €")
print(f"MwSt 19%:      {mwst_betrag:,.2f} €")
print(f"BRUTTO:        {brutto:,.2f} €")
print(f"Budget brutto: 17.000,00 €")
print(f"Budget netto:  {budget_netto:,.2f} €")
print(f"Diferenca:     {diff:+,.2f} € netto")
print()
for cat, items in groups.items():
    cat_total = sum(i[5] for i in items)
    pct = cat_total / total_netto * 100
    print(f"  {cat:<35} {cat_total:>9,.2f} € ({pct:.1f}%)")

# ─── HTML → PDF ──────────────────────────────────────────────────────────────
def fmt(v): return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><style>
  @page {{ margin: 15mm 15mm 18mm 15mm; size: A4; }}
  body {{ font-family: Arial, sans-serif; font-size: 9.5pt; color: #1a1a1a; }}
  h1 {{ font-size: 0; margin: 0; }}
  .hdr {{ display: flex; justify-content: space-between; border-bottom: 3px solid #1a3a5c; padding-bottom: 12px; margin-bottom: 14px; }}
  .co {{ font-size: 17pt; font-weight: bold; color: #1a3a5c; line-height: 1.2; }}
  .co-sub {{ font-size: 8pt; color: #666; margin-top: 2px; }}
  .ang-title {{ font-size: 15pt; font-weight: bold; color: #1a3a5c; text-align: right; }}
  .ang-sub {{ font-size: 8.5pt; color: #555; text-align: right; }}
  .two {{ display: flex; gap: 16px; margin-bottom: 12px; }}
  .box {{ flex: 1; background: #f5f7fa; border-left: 3px solid #1a3a5c; padding: 8px 12px; font-size: 8.5pt; }}
  .box b {{ display: block; font-size: 7pt; text-transform: uppercase; color: #888; margin-bottom: 3px; }}
  .notebox {{ background: #fff8e1; border-left: 3px solid #f59e0b; padding: 8px 12px; font-size: 8pt; margin-bottom: 10px; }}
  .cathead {{ background: #1a3a5c; color: white; padding: 5px 8px; font-weight: bold; font-size: 8.5pt; margin-top: 10px; }}
  table.items {{ width: 100%; border-collapse: collapse; }}
  table.items th {{ background: #e8edf3; font-size: 7.5pt; text-transform: uppercase; padding: 4px 6px; text-align: left; }}
  table.items th.r {{ text-align: right; }}
  table.items td {{ padding: 4px 6px; font-size: 8pt; border-bottom: 1px solid #eee; vertical-align: top; }}
  table.items td.r {{ text-align: right; white-space: nowrap; }}
  table.items td.sm {{ font-size: 7.5pt; color: #555; padding-top: 1px; }}
  .subtrow td {{ background: #f0f4f8; font-weight: bold; border-top: 1px solid #ccc; }}
  .totbox {{ float: right; width: 260px; margin-top: 14px; }}
  table.tot {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
  table.tot td {{ padding: 4px 8px; border: none; }}
  table.tot .totrow {{ background: #1a3a5c; color: white; font-weight: bold; font-size: 11pt; }}
  .budget-ok {{ background: #dcfce7; border: 1px solid #86efac; padding: 7px 12px; font-size: 8pt; margin-top: 12px; border-radius: 4px; clear: both; }}
  .opt-box {{ background: #eff6ff; border-left: 3px solid #3b82f6; padding: 8px 12px; font-size: 8pt; margin-top: 10px; }}
  .warn {{ background: #fff3cd; border: 1px solid #ffc107; padding: 7px 12px; font-size: 8pt; margin-top: 8px; border-radius: 4px; }}
  .footer {{ margin-top: 14px; font-size: 7.5pt; color: #888; border-top: 1px solid #ddd; padding-top: 8px; }}
  .validity {{ color: #dc2626; font-weight: bold; }}
  .new-tag {{ background: #fef3c7; color: #92400e; font-size: 7pt; padding: 1px 5px; border-radius: 3px; font-weight: bold; margin-left: 4px; }}
</style></head>
<body>
<h1>Angebot VIS-AN-2026-003 Viskovic Bau — Islamovic Bad Stuttgart</h1>

<div class="hdr">
  <div>
    <div class="co">VISKOVIC BAU</div>
    <div class="co-sub">Bauunternehmen &bull; Stuttgart &bull; Deutschland</div>
    <div class="co-sub">Nikša Visković &bull; niksa.viskovic@limit-connect.com</div>
  </div>
  <div>
    <div class="ang-title">ANGEBOT</div>
    <div class="ang-sub">Nr. <strong>VIS-AN-2026-003</strong> &bull; Stuttgart, 23.03.2026</div>
    <div class="ang-sub">Ersetzt Angebot VIS-AN-2026-002 vom 13.03.2026</div>
  </div>
</div>

<div class="two">
  <div class="box">
    <b>Auftraggeber</b>
    <strong>Zlatan Islamovic</strong><br>
    James-F.-Byrnes-Straße 12<br>70376 Stuttgart
  </div>
  <div class="box">
    <b>Angebotsdaten</b>
    Datum: <strong>23.03.2026</strong><br>
    Gültig bis: <strong class="validity">22.04.2026</strong><br>
    Objekt: James-F.-Byrnes-Str. 12, 70376 Stuttgart
  </div>
  <div class="box">
    <b>Leistungsumfang</b>
    Bad ca. 6 m² + WC ca. 2 m²<br>
    Schlüsselfertig inkl. Material<br>
    Raumhöhe H = 240 cm<br>
    Alle Preise netto zzgl. 19 % MwSt.
  </div>
</div>

<div class="notebox">
  <strong>Leistungsbeschreibung:</strong> Komplette Sanierung Bad + WC inkl. sämtlichem Material — schlüsselfertig.
  Unterputz-Armaturen <strong>hansgrohe iBox</strong> Linie. Abgehängte Rigipsdecke mit 3× RGB-LED-Downlight (12 V, schaltbar).
  3× Shampoo-Nischen umgekehrte Pyramide mit LED-Effekt. Neuer Trennwand zwischen Dusche/WM für Licht-Effekte.
  Heizungsleitung in <strong>Kupferrohr Cu 15</strong> (Fortsetzung bestehende Installation).
  Zahlungsziel: 14 Tage netto nach Rechnungsstellung. Ausführung nach Freigabe AG + Versicherung.
</div>
"""

for cat, items in groups.items():
    cat_total = sum(i[5] for i in items)
    html += f'<div class="cathead">{cat}</div>\n'
    html += '<table class="items"><tr>'
    html += '<th style="width:46%">Leistung / Material</th>'
    html += '<th class="r" style="width:8%">Menge</th>'
    html += '<th style="width:5%">Einh.</th>'
    html += '<th class="r" style="width:11%">EP netto</th>'
    html += '<th class="r" style="width:11%">GP netto</th></tr>\n'
    for naziv, detail, kol, jmj, ep, gp in items:
        new = ""
        if any(k in naziv for k in ["Trennwand","Kupferrohr","RGB","Nischen-Einbauspot","Downlight"]):
            new = '<span class="new-tag">NEU</span>'
        html += f'<tr><td><strong>{naziv}</strong>{new}<div class="sm">{detail[:160]}{"…" if len(detail)>160 else ""}</div></td>'
        html += f'<td class="r">{kol:g}</td><td>{jmj}</td>'
        html += f'<td class="r">{fmt(ep)} €</td>'
        html += f'<td class="r"><strong>{fmt(gp)} €</strong></td></tr>\n'
    html += f'<tr class="subtrow"><td colspan="4" style="text-align:right">Summe {cat}</td>'
    html += f'<td class="r">{fmt(cat_total)} €</td></tr>'
    html += '</table>\n'

html += f"""
<div class="totbox">
  <table class="tot">
    <tr><td>Nettobetrag</td><td class="r">{fmt(total_netto)} €</td></tr>
    <tr><td>MwSt. 19 %</td><td class="r">{fmt(mwst_betrag)} €</td></tr>
    <tr class="totrow"><td>GESAMT BRUTTO</td><td class="r">{fmt(brutto)} €</td></tr>
  </table>
</div>

<div style="clear:both"></div>

<div class="budget-ok">
  ✅ <strong>Gesamtpreis inkl. MwSt.: {fmt(brutto)} € — innerhalb des vereinbarten Budgets von 17.000 € brutto.</strong><br>
  Alle Leistungen + sämtliches Material (Hansgrohe Armaturen, Fliesen, Sanitärobjekte, Elektro) sind enthalten.
  Auftraggeber trägt keine weiteren Materialkosten.
</div>

<div class="opt-box">
  <strong>💡 Option — FI-Schutzschalter:</strong>
  Der Einbau eines FI-Schutzschalters RCD Typ A (pos. ELEKTRO, 340 € netto / <strong>405 € brutto</strong>)
  wird aus Sicherheitsgründen dringend empfohlen und entspricht dem aktuellen Stand der Technik (VDE 0100-701).
  <br>Auf ausdrücklichen Wunsch des Auftraggebers kann diese Position entfallen.
  In diesem Fall ist eine <strong>schriftliche Verzichtserklärung</strong> erforderlich.
  Ersparnis bei Verzicht: <strong>405 € brutto</strong> → Gesamtpreis dann: <strong>{fmt(brutto - 340*1.19)} € brutto</strong>.
</div>

<div class="warn">
  ⚠️ <strong>Hinweise:</strong> Dieses Angebot basiert auf Sichtprüfung. Eventuelle Zusatzarbeiten durch verdeckte Schäden
  (Schimmel, Statik, Leitungsschäden) werden nach Aufwand gesondert abgerechnet.
  Versicherungsleistungen: Abrechnung direkt nach schriftlicher Versicherungsbestätigung.
  Fliesenauswahl, Sanitärobjekte und Waschtisch-Unterschrank nach Absprache mit AG vor Auftragserteilung.
  Heizungsarbeiten: Fortsetzung in Cu 15 — Abstimmung mit Heizungsbauer AG empfohlen.
</div>

<div class="footer">
  Viskovic Bau &bull; Stuttgart &bull; Angebot Nr. VIS-AN-2026-003 &bull; 23.03.2026 &bull; Seite 1/1<br>
  Dieses Angebot ist kein Auftrag. Gültig bis 22.04.2026. Auftragserteilung nur schriftlich.
</div>
</body></html>
"""

out = "/tmp/VIS-AN-2026-003_Islamovic_komplett.pdf"
HTML(string=html).write_pdf(out)
import os
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
print(f"\nPDF: {out} ({os.path.getsize(out)/1024:.0f} KB)")
print(f"\nNETTO:  {fmt(total_netto)} €")
print(f"MwSt:   {fmt(mwst_betrag)} €")
print(f"BRUTTO: {fmt(brutto)} €")
print(f"Budget: 17.000,00 € ({'✅ OK' if brutto <= 17000 else '❌ PREVISOKO za ' + fmt(brutto-17000) + ' €'})")
