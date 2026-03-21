## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — DE Promotion Pack za Antonija

## Što gradiš
4 stranice na njemačkom jeziku. Dark gold tema. Standalone HTML (bez extends).
Sve na: `/var/www/fina-connect/templates/website/`
URLs u core/urls.py (javne, bez logina).

---

## STRANICA 1 — Landing page: `landing_de.html`
URL: `/de/` ili `/hr/de-landing/`

### Sadržaj:

**Hero:**
```
LIMIT Connect
Ihre digitale Kasse — ohne Hardware, ohne Papier
Für deutsche Unternehmen. Nach deutschem Recht.
[Kostenlos testen] [Mehr erfahren]
```

**3 Hauptvorteile (zlatne kartice):**
```
📱 Ohne Kasse
Smartphone oder Tablet genügt.
Keine Hardware-Investition. Sofort einsatzbereit.

📄 Ohne Papier  
Digitale Belege per WhatsApp oder E-Mail.
Archivierung nach GoBD — 10 Jahre automatisch.

⚖️ Nach deutschem Recht
KassenSichV konform. TSE-zertifiziert (Fiskaly).
DSFinV-K Export auf Knopfdruck.
```

**Zitate (simulirani):**
```
"Endlich eine Kasse die auf dem Handy läuft."
— Gastronom, München

"Mein Steuerberater bekommt alles automatisch."  
— Bäckerei, Stuttgart
```

**Pakete Übersicht** (nur Preise, Link zu Seite 2):
```
Starter    19 €/Monat   — 1 Gerät, Grundfunktionen
Business   49 €/Monat   — 3 Geräte, alle Module ⭐
Enterprise 99 €/Monat   — Unbegrenzt, DATEV-Export
```

---

## STRANICA 2 — Pakete: `pakete_de.html`  
URL: `/hr/de-pakete/`

### 3 Pakete detaljno:

**STARTER — 19 €/Monat**
```
✅ POS Kasse (1 Gerät)
✅ Digitale Belege (PDF/WhatsApp)
✅ Tagesabschluss / Z-Bericht
✅ KassenSichV (TSE via Fiskaly Sandbox)
✅ GoBD-konforme Archivierung
✅ Grundberichte
❌ DATEV Export
❌ Mehrere Standorte
```

**BUSINESS — 49 €/Monat** ⭐ Empfohlen
```
Alles aus Starter, plus:
✅ 3 Geräte / Kassen
✅ Warenwirtschaft (Bestand, Lieferanten)
✅ E-Rechnung (EN 16931 / XRechnung)
✅ Mitarbeiter & Zeiterfassung
✅ WhatsApp Benachrichtigungen
✅ Offline-Modus (arbeitet ohne Internet)
✅ KI-Assistent
```

**ENTERPRISE — 99 €/Monat**
```
Alles aus Business, plus:
✅ Unbegrenzte Geräte & Standorte
✅ DATEV SKR03/04 Export
✅ DSFinV-K Export (Betriebsprüfung)
✅ Multi-Mandant (mehrere Firmen)
✅ API-Zugang
✅ Persönlicher Support
```

---

## STRANICA 3 — Upute za korištenje: `anleitung_de.html`
URL: `/hr/de-anleitung/`

**Titel:** *So einfach geht's — in 3 Schritten*

**Schritt 1 — Anmelden & Einrichten** (5 Minuten)
```
1. Konto erstellen auf limit-connect.com
2. Firma anlegen (Name, Steuernummer, USt-ID)
3. Kasse konfigurieren — Gerät registrieren
4. Artikel eingeben oder importieren (Excel)
```

**Schritt 2 — Erster Verkauf**
```
1. App öffnen (Browser, kein Download nötig)
2. Schicht öffnen
3. Artikel antippen oder Barcode scannen
4. Bezahlung: Bar / Karte / Revolut
5. Beleg: Druck / WhatsApp / E-Mail / Ohne
```

**Schritt 3 — Tagesabschluss**
```
1. Z-Bericht generieren (1 Klick)
2. Kassenbuch automatisch aktuell
3. Export für Steuerberater (DATEV / PDF)
4. Alles GoBD-konform archiviert
```

**FAQ:**
```
Q: Brauche ich spezielle Hardware?
A: Nein. Smartphone, Tablet oder PC genügt.

Q: Was passiert bei Internetausfall?
A: Offline-Modus. Alle Verkäufe werden lokal gespeichert 
   und automatisch synchronisiert.

Q: Ist das TSE-konform nach KassenSichV?
A: Ja. Wir nutzen Fiskaly Cloud-TSE. 
   Zertifikat auf Anfrage.

Q: Wie bekommt mein Steuerberater die Daten?
A: DATEV-Export (SKR03/SKR04) mit 1 Klick.
   Oder DSFinV-K CSV für Betriebsprüfung.

Q: Wie lange werden Daten aufbewahrt?
A: 10 Jahre automatisch. GoBD-konform.
```

---

## STRANICA 4 — Ohne Papier specijalna: `ohne_papier_de.html`
URL: `/hr/de-ohne-papier/`

**Ovo je Antonijeva prodajna priča — emocionalni landing**

```
Schluß mit Papier.
Schluß mit Druckerpatronen.  
Schluß mit vollem Papierkorb.

LIMIT Connect.
Ihr Beleg kommt per WhatsApp.
Ihre Archivierung läuft automatisch.
Ihr Steuerberater freut sich.

[Jetzt 30 Tage kostenlos testen]
```

Prikaz na mobitelu (screenshot simulacija):
```
┌─────────────────┐
│  LIMIT-POS  🧾  │
│  Bäckerei Müller│
│─────────────────│
│ 2x Croissant    │
│ 1x Kaffee       │
│─────────────────│
│ GESAMT: 6,50 €  │
│ BAR: 10,00 €    │
│ RÜCKGELD: 3,50 €│
│─────────────────│
│ TSE: ✅ Signiert│
│ Beleg: WhatsApp │
└─────────────────┘
```

---

## URLs koje dodaješ u core/urls.py

```python
# DE Promotion (javne stranice, bez logina)
path('de/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/landing_de.html'), name='landing_de'),
path('de/pakete/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/pakete_de.html'), name='pakete_de'),  
path('de/anleitung/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/anleitung_de.html'), name='anleitung_de'),
path('de/ohne-papier/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/ohne_papier_de.html'), name='ohne_papier_de'),
```

Dodaj u JAVNI blok (bez i18n_patterns, bez login_required).

---

## Design zahtjevi za sve 4 stranice

```css
/* Isti stil kao pricing.html */
--gold: #c9a84c
--black: #0a0a0a  
--dark: #1a1a2e
Font: Cormorant Garamond (naslovi) + Barlow (tekst)
Mobile-first. Max-width: 1200px.
CTA gumbi: zlatna pozadina, crni tekst, border-radius: 8px
```

## Sve stranice moraju imati

```html
<!-- Header -->
<nav>LIMIT Connect | DE | [Anmelden] [Testen]</nav>

<!-- Footer -->
<footer>
  © 2026 LIMIT Connect | Datenschutz | Impressum
  Kontakt: antonio@limit-connect.com | limit-connect.com
</footer>
```

## Provjera
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2

# Test URLs
curl -s -o /dev/null -w "landing_de:%{http_code}\n" https://limit-connect.com/de/
curl -s -o /dev/null -w "pakete:%{http_code}\n" https://limit-connect.com/de/pakete/
curl -s -o /dev/null -w "anleitung:%{http_code}\n" https://limit-connect.com/de/anleitung/
curl -s -o /dev/null -w "ohne_papier:%{http_code}\n" https://limit-connect.com/de/ohne-papier/
# Sve mora biti 200
```

## Javi
- HTTP status svih 4 URL-ova
- Screenshote nisu potrebni — Ivan provjerava u browseru
