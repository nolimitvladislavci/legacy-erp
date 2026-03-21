# CC_TASK_ROBOT_PRODAVAC_KOMPLET
# Izvršava: CC Code
# Koordinira: Sonnet
# Prioritet: VISOK — Robot Prodavač Šeki pilot
# Datum: 2026-03-21
#
# CILJ: Pekara Uvijek Friško, Čepin — autonomna prodavaonica
# Kupac uđe, skenira QR ili otvori link, naruči, plati online, pokupi.
# Nula blagajničara u procesu narudžbe.
#
# OBAVEZNO PROČITAJ PRIJE:
# 1. pos/pickup_views.py (227 linija) — pickup flow
# 2. templates/pos/pickup_menu.html — postojeći mobitel template
# 3. templates/pos/webshop_public.html — postojeći katalog
# 4. pos/views.py :: pos_qr_open, qr_session — QR pristup
# 5. ROBOT_PRODAVAC_PLAN.md — kontekst

---

## ZADATAK 1 — Webshop artikli (5 minuta, SQL)

Problem: 617 artikala, samo 3 su webshop_visible=True.
Šeki mora imati sve food, dessert, drink artikle vidljive na kiosku.

```python
# management command ili shell:
from inventory.models import InventoryItem
from companies.models import Company
seki = Company.objects.filter(name__icontains='FRIŠKO').first()
updated = InventoryItem.objects.filter(
    company=seki, is_active=True,
    category__in=['food', 'dessert', 'drink']
).update(webshop_visible=True)
print(f'Ažurirano: {updated} artikala')
```

Kreiraj management command: `python manage.py activate_kiosk_items --company "UVIJEK FRIŠKO"`
Generički — može se koristiti za bilo kojeg klijenta.

---

## ZADATAK 2 — Kiosk template (touchscreen 15", full-screen)

Novi template: `templates/pos/kiosk.html`
Nova view: `pos/views.py :: kiosk_view`
Novi URL: `/pos/kiosk/<str:token>/` (koristi access_token kao QR)

### Dizajn specifikacija:

**Dimenzije:** 15" touchscreen = 1024×768 ili 1280×800 landscape.
**Filozofija:** Kupac stoji ispred ekrana. Nema miš. Prsti su veliki.

```
┌─────────────────────────────────────┐
│  UVIJEK FRIŠKO  [Kategorije filter] │  <- header 80px
├──────────┬──────────┬───────────────┤
│          │          │  KOŠARICA     │
│  BUREK   │ KROASAN  │  ─────────────│  <- glavni grid
│  2.50 €  │  1.20 €  │  Burek x2    │
│  [+] [-] │  [+] [-] │  Kroasan x1  │
│          │          │  ─────────────│
├──────────┴──────────┤  UKUPNO:      │
│  (grid artikala)    │  6.20 EUR     │
│                     │  [PLATI >>>]  │
└─────────────────────┴───────────────┘
```

**Konkretne specifikacije:**
- Layout: 2 kolumne — lijevo 65% grid artikala, desno 35% košarica
- Kartice artikala: min 160px visine, font 18px, gumbi +/- min 44px
- Košarica stalno vidljiva (nije popup/modal)
- Kategorije: horizontal tab bar na vrhu (Sve / Kruh i peciva / Kolači / Pića)
- PLATI gumb: cijela širina desne kolumne, 72px visine, kontrastna boja
- Nema navigacije, nema headera s linkovima, nema footera
- Idle screen (ako 3 min bez aktivnosti): screensaver s cijenama/logom

**Plaćanje (za sada — faza 1):**
- "Plati karticom na blagajni" → kreira GastroOrder → prikazuje pickup broj
- "Plati gotovinom" → isti flow
- Stripe prepayment → FAZA 2 (zaseban task)

**Kod za view:**
```python
def kiosk_view(request, token):
    """
    Kiosk mode — touchscreen 15", full-screen, bez logina.
    Koristi isti access_token kao pos_qr_open.
    """
    from pos.models import POSTerminal
    terminal = get_object_or_404(POSTerminal, access_token=token, is_active=True)
    company = terminal.company
    
    from inventory.models import InventoryItem
    items = InventoryItem.objects.filter(
        company=company, is_active=True, webshop_visible=True
    ).order_by('category', 'name')
    
    categories = sorted(set(i.category or 'ostalo' for i in items))
    
    return render(request, 'pos/kiosk.html', {
        'company': company,
        'terminal': terminal,
        'items': items,
        'categories': categories,
    })
```

URL dodati u pos/urls.py:
```python
path('kiosk/<str:token>/', views.kiosk_view, name='kiosk'),
```

---

## ZADATAK 3 — Stripe prepayment za pickup

Problem: Šeki nema PaymentConfig. Plaćanje unaprijed nije moguće.

### 3.1 Kreiraj PaymentConfig za Šekija
```python
from payments.models import PaymentConfig
from companies.models import Company
seki = Company.objects.filter(name__icontains='FRIŠKO').first()
# Provjeri PaymentConfig fields PRIJE
print([f.name for f in PaymentConfig._meta.get_fields() if hasattr(f,'name')])
```
OBAVEZNO pročitaj payments/models.py prije nego napišeš išta.

### 3.2 Stripe intent u pickup_order view
U pos/pickup_views.py :: pickup_order:
- Ako `payment == 'stripe'` → kreiraj Stripe PaymentIntent
- Vrati `client_secret` u JSON response
- Frontend: Stripe.js confirmCardPayment
- Nakon uspješnog plaćanja → kreira GastroOrder s `payment_status='paid'`

### 3.3 Stripe gumb u pickup_menu.html i kiosk.html
Dodaj opciju:
```html
<option value="stripe">Plati karticom odmah (online)</option>
```
Stripe.js loadati iz CDN: `https://js.stripe.com/v3/`

---

## ZADATAK 4 — PDF QR plakati za Šekija (A6, print-ready)

5 PDF fajlova, jedan po terminalu.

Format A6 (105×148mm), portrait:
```
┌─────────────────────┐
│   UVIJEK FRIŠKO     │
│   [lokacija naziv]  │
│                     │
│   [QR KOD 6x6 cm]  │
│                     │
│  Skeniraj za        │
│  narudžbu           │
│                     │
│  limit-connect.com  │
└─────────────────────┘
```

Koristiti qrcode library + reportlab (provjeri dostupnost).
Spremi u: `/var/www/fina-connect/media/pos_qr/frisko/`

URLs:
- Čepin: https://limit-connect.com/pos/pickup/pekara-uvijek-frisko/ (za narudžbu unaprijed)
- ILI: https://limit-connect.com/pos/qr/{token}/ (za direktnu blagajnu)

Šeki dobiva oba tipa — jedan za "naruči unaprijed", jedan za "otvori blagajnu".

---

## ZADATAK 5 — Vidljivost na internetu (SEO za robot prodavača)

Kreiraj javnu landing stranicu: `https://limit-connect.com/robot-pekara/`

Sadržaj:
- H1: "Robot prodavač za vašu pekarnu — LIMIT Connect"
- Opis: što je, kako radi, zašto
- Screenshots/mockup kiosk sučelja
- CTA: "Zatražite demo"
- Meta tags: robot prodavač, kiosk pekara, POS blagajna automatska, fiskalizacija HR

Ovo je SEO stranica — Google mora znati da LIMIT Connect radi robot prodavač.
Template u website/ app ili direktno u templates/landing/.

---

## GOTOVO KAD

- [ ] manage.py activate_kiosk_items radi za Šekija → 600+ artikala vidljivo
- [ ] /pos/kiosk/{token}/ radi → touchscreen layout
- [ ] Stripe u pickup flow (barem test mode)
- [ ] 5 PDF QR plakata generirani u media/pos_qr/frisko/
- [ ] /robot-pekara/ landing stranica live
- [ ] git commit: "Robot prodavač: kiosk template + webshop items + QR plakati + landing"
- [ ] FENIX_STATUS.md ažuriran
