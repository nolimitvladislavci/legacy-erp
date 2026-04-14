# CC TASK — KORAK 3: RouteRegistry — Javne i AJAX rute
**Datum: 14.04.2026.**
**Executor: CC Code | Reviewer: Gemini | Koordinator: Sonnet**

---

## Kontekst
RouteRegistry ima DEFAULT_LEVEL = COMPANY. To je sigurno za interne rute.
Problem su samo:
1. Javne rute (bez logina) koje se blokiraju za vanjske posjetitelje
2. AJAX endpointi koji trebaju AUTHENTICATED (ne COMPANY)

Ukupno URL-ova: 3600. U registru: 169. NE treba registrirati svih 3471 —
samo one koje su stvarno javne ili AJAX.

---

## ZADATAK 1 — Dodaj ove PUBLIC rute u ROUTE_REGISTRY

Datoteka: `/var/www/fina-connect/permissions/route_registry.py`

Dodaj u ROUTE_REGISTRY dict (ispod postojećih):

```python
# ── Javne rute koje nedostaju ─────────────────────────────────────
"receipt_public_short": AccessLevel.PUBLIC,      # POS bon javni link
"receipt_public_noslash": AccessLevel.PUBLIC,    # POS bon bez /
"whatsapp_webhook": AccessLevel.PUBLIC,          # WAHA webhook
"whatsapp_health": AccessLevel.PUBLIC,           # WAHA health
"inbound_webhook_direct": AccessLevel.PUBLIC,    # Smart import webhook
"set_language": AccessLevel.PUBLIC,              # i18n language switch
"set_language_profile": AccessLevel.PUBLIC,      # naš custom set_language
"pet_profile": AccessLevel.PUBLIC,               # memio.pet profil
"pet_qr": AccessLevel.PUBLIC,                    # memio.pet QR
"pet_hotel_booking": AccessLevel.PUBLIC,         # memio.pet hotel
"barf_listings": AccessLevel.PUBLIC,             # memio.pet BARF
"registracija": AccessLevel.PUBLIC,              # memio.pet registracija
"njuskalo_badge": AccessLevel.PUBLIC,            # memio.pet badge
"breeder_profile": AccessLevel.PUBLIC,           # memio.pet uzgajivač
"company_site_public": AccessLevel.PUBLIC,       # Javni site firme
"company_site_contact_public": AccessLevel.PUBLIC,
"public_booking_by_slug": AccessLevel.PUBLIC,    # Javno bookiranje
"inspection_tracking": AccessLevel.PUBLIC,       # Praćenje intervencije
"intervention_tracking": AccessLevel.PUBLIC,
"borg_ops:public_trace": AccessLevel.PUBLIC,     # Javni trace QR
"gastro_reviews_public": AccessLevel.PUBLIC,     # Javne recenzije
"gastro_order_public": AccessLevel.PUBLIC,       # Javna narudžba
"gastro_qr": AccessLevel.PUBLIC,                 # Gastro QR stol
"booking_track": AccessLevel.PUBLIC,             # Praćenje rezervacije
"pickup_track": AccessLevel.PUBLIC,              # Praćenje preuzimanja
"email_tracking_pixel": AccessLevel.PUBLIC,      # Email tracking pixel
"btcpay_webhook": AccessLevel.PUBLIC,            # BTC Pay webhook
"public_sos": AccessLevel.PUBLIC,                # SOS javna forma
"distributor_apply": AccessLevel.PUBLIC,         # Postani distributer
"claim_company": AccessLevel.PUBLIC,             # Preuzimanje firme
"submit_claim": AccessLevel.PUBLIC,
"activate_invite": AccessLevel.PUBLIC,           # Aktivacija pozivnice
"magic_login": AccessLevel.PUBLIC,               # Magic link login
"smart_entry": AccessLevel.PUBLIC,               # Pocni/onboarding
"api_detect_email": AccessLevel.PUBLIC,          # Provjera emaila
"device_token_login_api": AccessLevel.PUBLIC,    # POS device login
"tc_accept": AccessLevel.PUBLIC,                 # T&C prihvat
"datenschutz": AccessLevel.PUBLIC,               # GDPR DE
"privatnost": AccessLevel.PUBLIC,                # Privatnost HR
"grosmarkt_anfrage_direct": AccessLevel.PUBLIC,  # Grosmarkt kontakt
"digitalni_posrednik": AccessLevel.PUBLIC,
"memio_waitlist": AccessLevel.PUBLIC,
"memio_pet_profile": AccessLevel.PUBLIC,
"memio_stats": AccessLevel.PUBLIC,
"ai_agent_gateway": AccessLevel.PUBLIC,          # AI gateway (ima vlastitu auth)
```

---

## ZADATAK 2 — Dodaj AUTHENTICATED rute (AJAX bez company)

```python
# ── AJAX/API koji trebaju login ali ne company ─────────────────────
"global_search": AccessLevel.AUTHENTICATED,
"system_improvement_api": AccessLevel.AUTHENTICATED,
"feedback_count_api": AccessLevel.AUTHENTICATED,
"alerts_api": AccessLevel.AUTHENTICATED,
"notification_mark_read": AccessLevel.AUTHENTICATED,
"notification_mark_all_read": AccessLevel.AUTHENTICATED,
"push_subscribe": AccessLevel.AUTHENTICATED,
"push_unsubscribe": AccessLevel.AUTHENTICATED,
"api_clock_in": AccessLevel.AUTHENTICATED,
"api_clock_out": AccessLevel.AUTHENTICATED,
```

---

## ZADATAK 3 — Provjeri namespace rute

Neke rute imaju namespace (borg_ops:borg_hub, memio_pet:landing itd.).
RouteRegistry.get_access_level() već traži `namespace:view_name`.
Dodaj:
```python
"borg_ops:borg_hub": AccessLevel.COMPANY,    # Operativni centar - treba firmu
"borg_ops:operations_dashboard": AccessLevel.COMPANY,
"memio_pet:landing": AccessLevel.PUBLIC,
"memio_pet:pet_profile": AccessLevel.PUBLIC,
"memio_pet:pet_qr": AccessLevel.PUBLIC,
"client_portal:portal_home": AccessLevel.PUBLIC,
"no_limit:no_limit_web": AccessLevel.PUBLIC,
```

---

## PROTOKOL

1. Dodaj u ROUTE_REGISTRY — NE BRIŠI postojeće
2. Pazi na duplikate — ruff F601 će baciti grešku
3. `python manage.py check` mora proći
4. Commit: `fix(korak3): RouteRegistry — javne i AJAX rute`
5. `systemctl reload gunicorn-fina`

## ZAVRŠNI TEST

```bash
# Svaki od ovih mora biti 200 ili redirect na login (ne 302 na /)
python manage.py shell -c "
from django.test import Client
tests = [
    '/pas/12345/',      # memio.pet - javno
    '/ponuda/test/',    # nepostojeća ponuda - mora biti 404 ne 302
    '/sw.js',           # service worker - javno
]
c = Client()
for url in tests:
    r = c.get(url, HTTP_HOST='limit-connect.com')
    print(url, r.status_code)
"
```

