# Verfahrensdokumentation — LIMIT Connect ERP / POS

## Kassensystem gemäß GoBD, KassenSichV und DSFinV-K

**Hersteller:** LIMIT Connect d.o.o. (Konjik d.o.o.)
**Software:** LIMIT Connect ERP — Cloud POS
**Version:** 2026.03
**Datum:** 20.03.2026
**Kontakt:** info@limit-connect.com | https://limit-connect.com

---

## 1. Allgemeine Beschreibung des Kassensystems

### 1.1 Systemübersicht

LIMIT Connect ist ein cloud-basiertes ERP-System mit integriertem POS-Modul (Point of Sale). Das System wird als Software-as-a-Service (SaaS) betrieben und ist über jeden modernen Webbrowser zugänglich — auf Desktop, Tablet oder Smartphone.

### 1.2 Einsatzbereiche

- Gastronomie (Restaurant, Café, Bar)
- Einzelhandel (Maloprodaja)
- Dienstleistungen (Friseur, Werkstatt)
- Vereine und gemeinnützige Organisationen (Udruge)
- Handwerk und Bau

### 1.3 Systemkomponenten

| Komponente | Beschreibung |
|-----------|-------------|
| **POS-Frontend** | Progressive Web App (PWA), HTML5/JavaScript |
| **Backend** | Django 5.1 (Python 3.12), PostgreSQL 16 |
| **TSE** | Fiskaly Cloud TSE v2 (KassenSichV-konform) |
| **Hosting** | Hetzner Cloud (Helsinki), TLS 1.3, HSTS |
| **Backup** | Tägliches automatisches Backup, 14 Tage Aufbewahrung |

---

## 2. Technische Sicherheitseinrichtung (TSE)

### 2.1 TSE-Typ

- **Anbieter:** Fiskaly GmbH (Wien)
- **Typ:** Cloud-TSE gemäß BSI-TR-03153
- **Zertifizierung:** BSI-K-TR-0493-2021 (Fiskaly)
- **API-Version:** KASSENSICHV API v2

### 2.2 Transaktionsablauf

```
1. Kassierer erstellt Beleg im POS
2. Backend startet TSE-Transaktion (API: PUT /tss/{id}/tx/{tx_id})
3. TSE signiert Transaktion kryptographisch
4. Backend erhält: Transaktionsnummer, Signaturzähler, Hash, Seriennummer
5. Daten werden auf dem Beleg gedruckt (QR-Code oder Textblock)
6. Bei TSE-Ausfall: Beleg wird mit Klausel "TSE AUSGEFALLEN" gedruckt
7. Nacherfassung erfolgt automatisch per Retry-Task (alle 2 Minuten)
```

### 2.3 TSE-Datenfelder auf dem Beleg

| Feld | Beschreibung |
|------|-------------|
| TSE-Sig | Kryptographischer Signaturwert (SHA-256) |
| TSE-TxNr | Transaktionsnummer |
| TSE-SigZ | Signaturzähler |
| TSE-SN | Seriennummer der TSE |
| TSE-Start | Startzeitpunkt der Transaktion |
| TSE-Ende | Endzeitpunkt der Transaktion |

### 2.4 TSE-Ausfall

Bei Nichterreichbarkeit der Cloud-TSE:
- Der Beleg wird mit der Klausel **"TSE AUSGEFALLEN — Nacherfassung erfolgt automatisch gem. KassenSichV §146a AO"** gedruckt
- Die Transaktion wird in der Datenbank als `tse_error = 'TSE_AUSFALL: ...'` gespeichert
- Ein automatischer Celery-Task versucht alle 2 Minuten die Nacherfassung
- Maximale Nacherfassungsfrist: 48 Stunden

---

## 3. Datenerfassung und -speicherung

### 3.1 Belegstruktur (POSReceipt)

Jeder Beleg enthält:
- Eindeutige UUID
- Belegnummer (fortlaufend pro Terminal)
- Datum und Uhrzeit
- Artikelpositionen (Bezeichnung, Menge, Einzelpreis, USt-Satz)
- Zahlungsart(en)
- TSE-Signaturdaten
- Bediener-ID
- Optional: Käufer-OIB (für R1-Belege)

### 3.2 Zahlungsarten (DSFinV-K konform)

| Interne Bezeichnung | DSFinV-K Typ | Beschreibung |
|---------------------|-------------|-------------|
| CASH | Bar | Barzahlung |
| CARD | Unbar | Kartenzahlung |
| REVOLUT | Unbar | Revolut Tap to Pay |
| VOUCHER | Keine | Gutschein |
| PAYPAL | Unbar | PayPal |
| CRYPTO | Unbar | Kryptowährung |

### 3.3 Umsatzsteuer-Schlüssel

| USt-Satz | DSFinV-K Schlüssel | Bezeichnung |
|---------|-------------------|-------------|
| 19% | 1 (NORMAL) | Allgemeiner Steuersatz |
| 7% | 2 (REDUCED_1) | Ermäßigter Steuersatz |
| 0% | 5 (NULL) | Nicht steuerbar |

### 3.4 Geschäftsvorfälle (GV_TYP)

| GV_TYP | Beschreibung |
|--------|-------------|
| Umsatz | Regulärer Verkauf |
| TrinkgeldAN | Trinkgeld Arbeitnehmer (steuerfrei) |
| TrinkgeldAG | Trinkgeld Arbeitgeber (USt-pflichtig) |
| Pfandrueckzahlung | Pfandrückgabe |
| Storno | Stornierung |

---

## 4. Unveränderbarkeit der Daten (GoBD §146)

### 4.1 Maßnahmen zur Unveränderbarkeit

1. **TSE-Signatur:** Jede Transaktion wird kryptographisch signiert. Nachträgliche Änderungen würden die Signaturkette brechen.
2. **Datenbank-Audit:** Alle Änderungen an Belegen werden protokolliert (client_ip, client_ua, Zeitstempel).
3. **Keine Löschfunktion:** Bezahlte und fiskalisierte Belege können nicht gelöscht werden — nur storniert.
4. **Stornierung:** Erzeugt einen neuen Beleg vom Typ "Storno" mit Referenz auf den Originalbeleg.

### 4.2 Aufbewahrungsfristen

- Belege: 10 Jahre (§147 AO)
- TSE-Daten: 10 Jahre
- DSFinV-K Exporte: 10 Jahre
- Tägliche Backups: 14 Tage rotierend, Langzeitarchiv auf Anfrage

---

## 5. DSFinV-K Export (Digitale Schnittstelle der Finanzverwaltung für Kassensysteme)

### 5.1 Export-Format

Das System generiert auf Knopfdruck einen DSFinV-K v2.3 konformen ZIP-Export:

| Datei | Inhalt |
|-------|--------|
| bonkopf.csv | Belegköpfe |
| bonpos.csv | Belegpositionen mit USt-Schlüssel |
| tse.csv | TSE-Signaturdaten |
| businesscases.csv | Geschäftsvorfalltypen |
| stamm_kassen.csv | Kassenstammdaten |
| stamm_orte.csv | Betriebsstättendaten |
| index.json | Metadaten und Zeitraum |

### 5.2 Export-Zugang

- **Dashboard:** POS Dashboard → Button "DSFinV-K Export"
- **CLI:** `python manage.py export_dsfinvk <company_id> --from YYYY-MM-DD --to YYYY-MM-DD`
- **Zeitraum:** Frei wählbar, Standardmäßig letzter Monat

### 5.3 Kassennachschau

Bei einer unangekündigten Kassennachschau (§146b AO):
1. Kassierer klickt auf "DSFinV-K Export" im POS Dashboard
2. System generiert ZIP-Datei im Arbeitsspeicher (kein Schreiben auf Festplatte)
3. ZIP wird als Download angeboten (USB-Stick des Prüfers)
4. Prüfer lädt ZIP in IDEA-Software

---

## 6. Kassenbuch (§146 AO)

Das System generiert ein tägliches Kassenbuch (XLSX-Format):

| Spalte | Beschreibung |
|--------|-------------|
| Datum | Geschäftstag |
| Anfangsbestand | Kassenbestand bei Eröffnung |
| Bareinnahmen | Summe Barverkäufe |
| Barausgaben | Summe Barrückgaben/Stornos |
| Einzahlung | Bankeinzahlungen |
| Entnahme | Privatentnahmen |
| Endbestand | Rechnerischer Kassenbestand |
| Belege | Anzahl der Belege |

Zugang: POS Dashboard → "Kassenbuch" oder `/pos/kassenbuch/`

---

## 7. E-Rechnung (E-Rechnungspflicht ab 2025)

### 7.1 Unterstützte Formate

| Format | Beschreibung | Zugang |
|--------|-------------|--------|
| **XRechnung** | CII-XML (EN 16931, CIUS-DE) | `/eracun/<uuid>/xrechnung/` |
| **ZUGFeRD 2.2** | Hybrid-PDF (PDF/A-3 + eingebettetes factur-x.xml) | `/eracun/<uuid>/zugferd/` |

### 7.2 Automatische B2B-Erkennung

Wenn auf dem POS-Beleg eine Käufer-OIB/USt-IdNr. eingetragen wird (R1-Beleg), erkennt das System automatisch eine B2B-Transaktion.

---

## 8. Gutscheine (§3 Abs. 13-15 UStG)

### 8.1 Mehrzweckgutschein (Standardfall)

- Bei Verkauf: **Keine USt**, Buchung auf Verbindlichkeitskonto (Klasse 2)
- Bei Einlösung: USt wird auf die konsumierten Artikel erhoben

### 8.2 Einzweckgutschein

- Bei Verkauf: USt wird sofort erhoben (bekannter Steuersatz)
- Bei Einlösung: Keine weitere USt

---

## 9. Trinkgeld

| Typ | Steuerliche Behandlung |
|-----|----------------------|
| Arbeitnehmer-Trinkgeld | 100% steuerfrei (kein Limit in DE) |
| Arbeitgeber-Trinkgeld | USt-pflichtig |

DSFinV-K: `GV_TYP = TrinkgeldAN` (Arbeitnehmer) bzw. `TrinkgeldAG` (Arbeitgeber)

---

## 10. Offline-Betrieb

### 10.1 Funktionsumfang im Offline-Modus

| Funktion | Offline verfügbar |
|---------|:-:|
| Verkauf/Belegdruck | Ja (IndexedDB Queue) |
| Barzahlung | Ja |
| Kartenzahlung | Ja (Terminal-abhängig) |
| TSE-Signatur | Nein → "TSE AUSGEFALLEN" Klausel |
| Schichtbericht | Ja (lokale Berechnung) |
| Synchronisation | Automatisch bei Wiederverbindung |

### 10.2 Nacherfassung

- Offline-Belege werden in IndexedDB gespeichert (unbegrenzte Kapazität)
- Bei Wiederherstellung der Internetverbindung: automatische Synchronisation
- TSE-Nacherfassung: Celery-Task alle 2 Minuten, max. 48 Stunden

---

## 11. Datenschutz (DSGVO)

- Datenverarbeitung: Auftragsverarbeitung gemäß Art. 28 DSGVO
- Serverstandort: EU (Hetzner Cloud, Helsinki, Finnland)
- Verschlüsselung: TLS 1.3 (HTTPS), AES-256 für Zertifikate
- Zugangskontrolle: Rollenbasiert (Admin, Manager, Kassierer)
- Löschung: Auf Anfrage, unter Berücksichtigung steuerlicher Aufbewahrungsfristen

---

## 12. Kontakt und Support

**LIMIT Connect**
Website: https://limit-connect.com
E-Mail: info@limit-connect.com
Telefon: +385 97 609 1655

**Technischer Support:** 24/7 automatisches Monitoring, E-Mail-Alerts bei Systemausfällen

---

*Dieses Dokument beschreibt den Stand vom 20.03.2026. Änderungen werden versioniert und den Nutzern mitgeteilt.*
