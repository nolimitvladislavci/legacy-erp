# CC Task — Pricing restruktura: POS vs e-Račun split

## Kontekst (PROČITAJ PRVO)
Gemini je otkrio ključni uvid:
- POS bon (fiskalizacija 1.0) → FINA CIS → BESPLATNO, ne treba posrednik
- e-Račun (fiskalizacija 2.0) → Porezna uprava → 0.08€/račun, treba posrednik

Šeki (kafić/pekara) → nikad ne treba e-Račun → plaća 12-25€/mj
Nikša (B2B usluge) → treba e-Račun → plaća 79-219€/mj

## Zadatak 1 — Ažuriraj /hr/pricing/ i /hr/de/pakete/

### Novi paketi (zamijeni stare):

```
MICRO     12 €/mj   — Kafić, pekara, frizerski salon
                      POS + fiskalizacija + Z-izvještaj + offline mod
                      DO 1 terminal, DO 500 bonova/mj
                      BEZ e-Računa (tag: "Nije potrebno")

STARTER   25 €/mj   — Maloprodaja, obrt
                      Sve iz Micro + inventory + WhatsApp bonovi + 3 terminala
                      BEZ e-Računa

PROFESSIONAL 79 €/mj — Veleprodaja, B2B usluge ← NOVO POZICIONIRANJE
                      Sve iz Starter + e-Račun UBL 2.1 + DATEV export
                      Neograničeni e-Računi uključeni
                      Preporučeno za: firme koje fakturiraju B2B

ENTERPRISE 219 €/mj — Višestruke lokacije, javna nabava
                      Sve + API + multi-tenant + ISO ready + SLA podrška
```

### Visual hint na karticama:
- Micro + Starter: zelena oznaka "✓ Savršeno za blagajnu"
- Professional + Enterprise: plava oznaka "✓ e-Račun uključen"

## Zadatak 2 — Kalkulator na pricing stranicu

Dodaj interaktivni kalkulator IZNAD paketa:

```
"Koji paket trebam?"

Pitanje 1: Prodaješ li fizički kupcima na licu mjesta?
  [Da, imam blagajnu] → nastavi
  [Ne, samo fakturiram] → skoči na Professional

Pitanje 2: Šalješ li fakture firmama (B2B)?
  [Da, B2B] → Professional
  [Ne, samo fizička prodaja] → Micro/Starter

Pitanje 3 (ako B2B): Koliko B2B faktura mjesečno?
  Slider: 1 — 500
  Prikaz: "Na pay-per-use: X × 0.08€ = Y€/mj | Professional: 79€/mj sve uključeno"
  Break-even poruka: ako Y > 20€ → "Professional se isplati od [N] faktura"
```

JavaScript kalkulator, bez page reload. Inline u pricing.html.

## Zadatak 3 — DE verzija (/hr/de/pakete/)

Isti model ali s DE terminologijom:
```
MICRO      12 €/Monat  — Gastro, Bäckerei, Friseur
STARTER    25 €/Monat  — Einzelhandel, Handwerk
PROFESSIONAL 79 €/Monat — B2B, Dienstleistungen + E-Rechnung (EN 16931/XRechnung)
ENTERPRISE 219 €/Monat — Mehrere Standorte, öffentliche Aufträge
```

DE kalkulator:
"Wie viele B2B-Rechnungen pro Monat?" → break-even kalkulacija

## Zadatak 4 — Sidebar badge u aplikaciji

U base.html, za korisnike na Micro/Starter paketu koji kreiraju fakturu:
Dodaj subtle info bar:
```html
{% if subscription.plan in 'micro starter' and invoice_count_b2b > 5 %}
<div class="info-bar">
  💡 Šaljete više od 5 B2B faktura — Professional paket uključuje neograničene e-Račune za 79€/mj.
  <a href="/pricing/">Pogledaj</a>
</div>
{% endif %}
```

## Provjere
```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -2
curl -s -o /dev/null -w "pricing:%{http_code}\n" https://limit-connect.com/hr/pricing/
curl -s -o /dev/null -w "de-pakete:%{http_code}\n" https://limit-connect.com/hr/de/pakete/
```

## Javi
- HTTP status oba URL-a
- Broj linija pricing.html nakon izmjene
- Je li kalkulator dodan (grep "kalkulator\|calculator\|slider" pricing.html)
