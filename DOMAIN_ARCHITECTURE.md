# Arhitektura domena — FINA-Connect / Viskovic Group

> Odlučeno: 2026-03-08
> Potvrđeno: Ivan Brtan

## Tri domene — raspored

### 1. fina-connect.online — ERP Platforma
**Primarna aplikacija. Sve ostaje ovdje.**

```
fina-connect.online/              → redirect na /hr/login/
fina-connect.online/hr/           → HR lokalizacija (default)
fina-connect.online/de/           → DE lokalizacija
fina-connect.online/dashboard/    → Company dashboard
fina-connect.online/invoicing/    → Fakture
fina-connect.online/eracun/       → e-Račun (FINA CIS)
fina-connect.online/propter/      → Propter Hub (per-company)
fina-connect.online/propter/eko/  → Eko statistika + badge
fina-connect.online/register/propter/ → Propter SaaS operator dashboard
fina-connect.online/payroll/      → Payroll
fina-connect.online/pos/          → POS / Gastro
fina-connect.online/bank/         → Bankovne transakcije
fina-connect.online/dunning/      → Opomene
```

**Propter SaaS landing:**
- NE treba zasebna domena
- Landing page sekcija na `fina-connect.online/#propter` ili `/propter-saas/`
- Tier bookkeeper: 150-200 EUR/mj
- Tier client: 30-80 EUR/mj
- Eko badge kao marketing differentiator

---

### 2. grosmarkt-online.eu — Tržnica Online (HR)
**Javna B2B marketplace stranica na HR jeziku.**

```
grosmarkt-online.eu/              → Tržnica Online landing
grosmarkt-online.eu/kategorije/   → Kategorije proizvoda
grosmarkt-online.eu/proizvodi/    → Listing
grosmarkt-online.eu/ponuda/<slug>/→ Detalj ponude
grosmarkt-online.eu/kontakt/      → Kontakt / Upit
```

**Implementacija:**
- Nginx virtual host → isti Django app (fina-connect) ili zasebni
- Dijeli `marketplace/` i `partners/` modele s fina-connect
- Jezik: HR primarno, DE sekundarno
- Authenticated korisnici (firme) vide B2B cijene
- Javni posjetitelji vide javne listinge

**Nginx config koji treba:**
```nginx
server {
    server_name grosmarkt-online.eu www.grosmarkt-online.eu;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```
**ALLOWED_HOSTS treba dodati:** `grosmarkt-online.eu`, `www.grosmarkt-online.eu`

---

### 3. viskovic-group.de — Holding / Corporate
**Korporativna stranica Viskovic Group.**

```
viskovic-group.de/                → Holding landing
viskovic-group.de/firme/          → Popis firmi u grupi
viskovic-group.de/_dev/           → Dev API (interno, zaštićeno tokenom)
```

---

## Nginx virtualhosti (potrebno dodati — root)

### Za grosmarkt-online.eu:
```bash
# /etc/nginx/sites-available/grosmarkt-online
server {
    listen 80;
    server_name grosmarkt-online.eu www.grosmarkt-online.eu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name grosmarkt-online.eu www.grosmarkt-online.eu;
    ssl_certificate /etc/letsencrypt/live/grosmarkt-online.eu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/grosmarkt-online.eu/privkey.pem;

    location /static/ {
        alias /var/www/fina-connect/static/;
    }
    location /media/ {
        alias /var/www/fina-connect/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

## Django ALLOWED_HOSTS (dodati)
```python
ALLOWED_HOSTS = [
    'fina-connect.online', 'www.fina-connect.online',
    'viskovic-group.de', 'www.viskovic-group.de',
    'grosmarkt-online.eu', 'www.grosmarkt-online.eu',  # DODATI
    'localhost', '127.0.0.1',
]
```

## SSL certifikati (Let's Encrypt — root)
```bash
certbot --nginx -d grosmarkt-online.eu -d www.grosmarkt-online.eu
```

---

## Sljedeći koraci implementacije

### Faza C — Propter (trenutno u tijeku)
- [ ] Javna eko stranica: `fina-connect.online/propter/eko/public/<slug>/`
- [ ] ESG PDF godišnje izvješće (WeasyPrint)
- [ ] Propter SaaS landing page sekcija

### Faza D — Tržnica Online (grosmarkt-online.eu)
- [ ] Nginx virtualhost za grosmarkt-online.eu (root)
- [ ] SSL certifikat (certbot)
- [ ] ALLOWED_HOSTS update
- [ ] Tržnica landing page (HR jezik)
- [ ] Integracija s marketplace/ modulom
- [ ] URL routing po Host headeru

*Dokument kreiran: 2026-03-08*
*Autor: Claude (na osnovu odluke Ivana Brtana)*
