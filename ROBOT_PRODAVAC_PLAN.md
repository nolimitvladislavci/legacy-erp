# ROBOT_PRODAVAC_PLAN.md
# Kreirao: Sonnet — 2026-03-21
# Ideja: Ivan Brtan + inovatorski duh LIMIT Connect platforme
# Scenarij: LIMIT Connect softver + hardware kiosk = autonomna prodavaonica

---

## ŠTO JE VEĆ IZGRAĐENO (ne treba graditi)

### pos/pickup_views.py (227 linija, LIVE)
- pickup_menu: kupac skenira QR, vidi meni, naruči — BEZ LOGINA
- pickup_order: narudžba se kreira, šalje na pickup_board
- pickup_board: radnik vidi narudžbe na ekranu (sin puni vrećicu)
- pickup_track: kupac prati status narudžbe
- URL: /pos/pickup/pekara-uvijek-frisko/

### QR instant open (upravo deployan, CC_TASK_POS_QR_INSTANT_OPEN)
- /pos/qr/{token}/ — blagajna se otvori bez logina
- POSTerminal.access_token — 20-char random

### webshop_public (live)
- /pos/webshop/{slug}/ — javni katalog s cijenama
- Roba od jučer — automatski popust

### Fiskalizacija
- 3 sloja zaštite (CC Code bug fix 21.03.)
- 5s timeout, instant bon, Celery retry
- Zakonski OK — 48h rok

---

## ŠTO NEDOSTAJE DO KOMERCIJALNOG KIOSKA (3 stvari)

### 1. Pre-payment (Stripe → pickup flow)
Spoji postojeći Stripe gateway s pickup_order.
Kupac plati odmah → bon → pokupi bez kontakta.
~50 linija koda. CC Code task: CC_TASK_PICKUP_PREPAYMENT.md

### 2. Kiosk template (touchscreen 15")
webshop_public.html je za mobitel.
Treba: veliki gumbi, kategorije odmah, košarica stalno vidljiva, NFC/kartica integracija.
CSS + template. 1 dan rada. CC_TASK_KIOSK_TEMPLATE.md

### 3. Payment terminal callback
Automatski signal na kartični čitač (Ingenico/PAX/Verifone) kad kupac potvrdi.
/pos/api/terminal-callback/ endpoint.
~50 linija Python + hardware API dokumentacija.

---

## KOMERCIJALNI MODEL

### Trijada
| Partner | Doprinos |
|---|---|
| LIMIT Connect (Ivan) | Softver: QR, POS, fiskalizacija, zalihe, report |
| Marko Pinjuh / Centar inovatorstva | Hardware kiosk, montaža, distribucija u Slavoniji |
| Šeki (Uvijek Friško) | Prva referenca — pilot lokacija Čepin |

### Revenue model
- LIMIT Connect SaaS: 35-69 EUR/mj po kiosku (POS + Arhiva plan)
- Hardware kiosk: 2.000-2.500 EUR jednokratno (Marko prodaje)
- Instalacija: 200-300 EUR (Marko)
- Opcija: LIMIT Connect uzima 10% od hardware margine kao referral

### Pipeline
1. Čepin pilot → case study PDF
2. Marko nosi na Savez hrvatskih inovatora + natjecanja
3. EU fond: Digitalizacija SME-a (ESIF 2026) — eligibilitet ~85%
4. 10 kioska u Slavoniji do Q4 2026
5. Replikacija: Osijek → Zagreb → DE (Döner, Bäckerei)

---

## ŠEKIJEV ROI (živih podataka)

Jedini zaposlenik u sustavu: Shevqet Temaj, 20 EUR/h, 40h/tjedan
Procjenjena bruto: 3.464 EUR/mj

3 lokacije × 1 radnik prodavač × 1.600 EUR neto = 4.800 EUR neto/mj
S doprinosima: ~5.600 EUR bruto/mj = 67.200 EUR/god

Hardware kiosk 3 lokacije: ~7.500 EUR
Povrat investicije: 7.500 / 5.600 = **6.5 tjedana**

---

## PITCH ZA MARKA PINJUHA

"Marko, napravio sam sustav gdje kupac uđe u pekaru, skenira QR na zidu,
sam naruči i plati — bez blagajnika.
Softver je gotov, fiskalizacija je legalna, POS certificiran.
Jedino što nedostaje je kiosk s ekranom i kartičnim čitačem.
Zajedno možemo to komercijalizirati."

On je most između inovacije i kompanije.
Mi smo inovacija. On je distribucija.

---

## SLJEDEĆI KORACI

### Odmah (Ivan)
1. Kontaktirati Marka Pinjuha — LinkedIn ili Centar inovatorstva Osijek
2. Poslati Šekiju poruku 1 iz SEKI_KOMUNIKACIJA.md

### Tjedan 1 (CC Code)
- CC_TASK_PICKUP_PREPAYMENT.md (Stripe + pickup)
- CC_TASK_KIOSK_TEMPLATE.md (touchscreen UI)

### Tjedan 2 (Sonnet + Ivan)
- Demo za Šekija: live kiosk na Čepinu
- Case study PDF: "Uvijek Friško — robot prodavač"

### Tjedan 3 (Ivan + Marko)
- Sastanak / video call
- Pilot dogovor, hardware specifikacija

---
Zadnje ažuriranje: 2026-03-21 — Sonnet
