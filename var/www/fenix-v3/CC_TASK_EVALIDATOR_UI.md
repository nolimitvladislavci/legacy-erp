# CC_TASK: eValidaTor UI — Blockchain Explorer Grade Frontend

## STATUS: TODO
## Datum: 2026-04-22
## Agent: CC (slobodan slot)
## Prioritet: HIGH — evalidator.eu je javni produkt, trenutni HTML je "sentimental"

---

## KONTEKST

`evalidator.eu` je javna platforma za kriptografsku verifikaciju dokumenata i
Defensive Publication (IP zaštita). Trenutno koristi Django `base.html` template
s inline stilovima — izgleda kao interni alat, ne kao produkt.

Cilj: **Etherscan-level UI** — dark theme, monospace, kriptografski ozbiljan.
Referenca vizualno: Etherscan.io + VirusTotal + Certificate Transparency Log.

Server: 37.27.248.86 (ssh -p 2222 root@37.27.248.86)
App dir: /var/www/fenix-v3/
Templates: /var/www/fenix-v3/templates/evalidator/
Static: /var/www/fenix-v3/static/
Reload: systemctl reload gunicorn-fenix-v3.service
URL: https://evalidator.eu/evalidator/

---

## DIZAJN SPECIFIKACIJA

### Paleta boja
```css
--ev-bg:        #0a0f1e;   /* deep navy — pozadina */
--ev-surface:   #0f1729;   /* card površine */
--ev-border:    #1e2d4a;   /* border */
--ev-gold:      #f59e0b;   /* akcent — chain/hash */
--ev-green:     #10b981;   /* verified/ok */
--ev-red:       #ef4444;   /* tamper/error */
--ev-purple:    #8b5cf6;   /* DP pločice */
--ev-blue:      #3b82f6;   /* linkovi */
--ev-text:      #e2e8f0;   /* primarni tekst */
--ev-muted:     #64748b;   /* sekundarni */
--ev-mono:      'JetBrains Mono', 'DM Mono', 'Fira Code', monospace;
```

### Tipografija
- Naslovi: `Inter` ili `system-ui`, bold
- Hash/kod vrijednosti: `JetBrains Mono` (Google Fonts CDN)
- Veličina base: 14px desktop, 13px mobile

### Layout
- Max-width: 1100px, centrirano
- Topbar: fiksiran, visina 52px, logo + navigacija + chain status
- Mobilni: hamburger menu, stacked layout

---

## KORAK 1 — Zajednički base template (evalidator_base.html)

Kreiraj `/var/www/fenix-v3/templates/evalidator/evalidator_base.html`:

```html
<!DOCTYPE html>
<html lang="hr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}eValidaTor{% endblock %} — Proof of Existence</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    /* CSS varijable + reset + topbar + cards + hash blocks + badges + tablice */
    /* Pogledaj DIZAJN SPECIFIKACIJU gore */
  </style>
</head>
<body>
  <!-- Topbar: fiksiran -->
  <header class="ev-topbar">
    <div class="ev-topbar-inner">
      <a href="/evalidator/" class="ev-logo">
        <span class="ev-logo-icon">⬡</span>
        <span class="ev-logo-text">eValidaTor</span>
        <span class="ev-logo-sub">POE Chain</span>
      </a>
      <nav class="ev-nav">
        <a href="/evalidator/" class="ev-nav-link {% block nav_dashboard %}{% endblock %}">Dashboard</a>
        <a href="/evalidator/bunker/" class="ev-nav-link {% block nav_bunker %}{% endblock %}">🔐 Bunker</a>
        <a href="/evalidator/dp/" class="ev-nav-link {% block nav_dp %}{% endblock %}">🪨 DP Pločice</a>
        <a href="/evalidator/dp/novo/" class="ev-nav-link ev-nav-cta">+ Zapečati</a>
      </nav>
      <!-- Chain live status: Block #N | hash[:8] -->
      <div class="ev-chain-status" id="ev-chain-status">
        <span class="ev-pulse"></span>
        <span id="ev-block-num">Block #—</span>
      </div>
    </div>
  </header>

  <main class="ev-main">
    {% block content %}{% endblock %}
  </main>

  <footer class="ev-footer">
    <div>Konjik d.o.o. — TDS Layer 0 | ChainBlock POE Standard v1.0</div>
    <div class="ev-footer-hash">Chain root: <span id="ev-footer-hash">—</span></div>
  </footer>

  <script>
    // Live chain status: fetch /evalidator/api/ za zadnji block
    // Ažuriraj ev-block-num i ev-footer-hash svakih 30s
  </script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

Svi ostali evalidator templatei moraju koristiti `{% extends "evalidator/evalidator_base.html" %}`.

---

## KORAK 2 — Dashboard (dashboard.html)

**Trenutno**: 299 linija, extends base.html, miješa ERP UI s chain UI.
**Nova verzija**:

```
[ Chain Stats Row ]
  Blokova: 14    DP Pločica: 9    Pečata: 1    Uptime: 99.9%

[ Search bar ] — pretraži po seal_token, hash, dp_id, naslovu

[ Zadnjih 10 blokova — lista ]
  #14 | BNK-20260421-... | Bunker Seal   | 2026-04-21 22:01 | ✓
  #13 | KONJ-DP-2026-009 | DP Seal       | 2026-04-21 22:01 | ✓
  ...

[ ChainBlock vizualizacija ]
  Block #0 ←→ Block #1 ←→ ... ←→ Block #14
  Horizontalni scroll, svaki blok klikabilan
```

Implementacija:
- Context: `ChainBlockPOE.objects.order_by('-block_number')[:10]`
- Search: JS filter na stranici (ne server-side, blokova je malo)
- Chain vizualizacija: `<div class="ev-chain-viz">` s horizontal scroll

---

## KORAK 3 — Bunker page (bunker.html)

**Trenutno**: 138 linija, extends base.html.
**Nova verzija** (extends evalidator_base.html):

```
[ Hero: zadnji pečat ]
  ╔══════════════════════════════════════════════════════╗
  ║  🔐 BUNKER SEAL #1 — INITIAL              ✓ ČIST   ║
  ║  Block: #13 | BNK-20260421-215902-D2FEB592          ║
  ║  Merkle: d2feb592623ed103d40f5ed39820f06a...        ║
  ║  Files: 9/10 ok  |  Plates: 8  |  2026-04-21 22:01 ║
  ╚══════════════════════════════════════════════════════╝

[ File integrity table ]
  PATH                                    HASH (SHA-256)         SIZE  OK
  /var/www/fenix-v3/config/settings.py   78ec9cd7ee8f...        42KB  ✓
  ...
  Merkle path: leaf → node → root (collapsible)

[ Plates locked ]
  KONJ-DP-2026-001  KONJ-DP-2026-002  ...  (klikabilni badges)

[ Seal history timeline ]
  ●─── Initial 2026-04-21 ─── (više pečata se pojavljuje s vremenom)

[ TDS arhitektura diagram ]
  Layer 0: Bunker   →  Layer 1-7: F1-F7  →  Layer 8: Joker  →  Layer 9-10: Civ
```

---

## KORAK 4 — DP pločice lista (dp_list.html)

**Trenutno**: 37 linija, skoro prazan.
**Nova verzija**:

```
[ Header: "DP Pločice — Prior Art Registar" ]
[ Stats: 9 zapečaćenih | zadnji: KONJ-DP-2026-009 ]

[ Tabela/Grid ]
  ID              NASLOV                        IPC      DATUM      CHAINBLOCK
  KONJ-DP-2026-001  QBP-32 Quantum Bela Prot...  H04L9/32  2026-04-20  #4   →
  KONJ-DP-2026-009  Fenix Bunker Integrity...     H04L9/32  2026-04-21  #14  →

[ Gumb: "+ Zapečati novu inovaciju" ]
```

Model fields (provjeri u models.py):
`dp_id, title, abstract, ipc_class, chainblock.block_number, chainblock.timestamp`

---

## KORAK 5 — DP detalj (dp_detail.html)

**Trenutno**: 69 linija, nedovršeno.
**Nova verzija** (JAVNA stranica — bez loginRequired):

```
[ Header: KONJ-DP-2026-001 ]
[ Status badge: SEALED ]

[ Proof block — dark monospace ]
  Title:        QBP-32 Quantum Bela Protocol...
  IPC Class:    H04L9/32
  Datum:        2026-04-20T18:00:00Z
  ChainBlock:   #4 | KONJ-DP-2026-001
  Merkle root:  abc123...
  Block hash:   def456...

[ Abstract ]

[ Claims — numbered list ]
  1. VDF-based adut selection...
  2. FROST-Ed448 DKG threshold...

[ Merkle leaves — revealed vs blank ]
  Leaf 0: REVEALED — [content hash]
  Leaf 1-31: BLANK (reserved future claims)

[ Download PDF gumb ]
[ Copy proof link gumb ]
[ Verify on chain gumb → /evalidator/verify/TOKEN/ ]
```

---

## KORAK 6 — Seal innovation form (seal_innovation.html)

**Trenutno**: 133 linija, AJAX form.
**Nova verzija**:

```
[ Breadcrumb: Dashboard → DP Pločice → Nova pločica ]

[ Form — dark card ]
  Naslov inovacije *
  Abstract (opis tehničkog doprinosa) *
  IPC klasa [default: H04L9/32]
  Tvrdnje (claims) — textarea, jedna po liniji *

[ Live preview: blank leaf counter ]
  "32 leafova: X revealed + Y blank (reserved)" — ažurira se dok tipkaš

[ Submit button: "🔒 Zapečati inovaciju" ]

[ Po submitu — result panel ]
  ✅ KONJ-DP-2026-XXX zapečaćen
  ChainBlock: #N
  Merkle root: ...
  [ Gumb: Preuzmi PDF ] [ Gumb: Pregledaj pločicu ]
```

---

## KORAK 7 — Verify chain (verify_chain.html)

**Trenutno**: 216 linija, extends base.html, radi okej.
**Refaktor** na evalidator_base.html — zadržati funkcionalnost, samo vizual.

---

## KORAK 8 — API endpoint za live chain status

U `evalidator/views.py` dodaj:

```python
class ChainStatusAPIView(View):
    def get(self, request):
        last = ChainBlockPOE.objects.order_by('-block_number').first()
        if not last:
            return JsonResponse({'block': 0, 'hash': 'genesis'})
        return JsonResponse({
            'block': last.block_number,
            'hash': last.block_hash[:16],
            'token': last.seal_token,
            'ts': last.timestamp.isoformat(),
        })
```

URL: `path("api/chain-status/", ChainStatusAPIView.as_view(), name="chain_status")`

Topbar JS fetcha ovo svakih 30s → live block broj.

---

## REDOSLIJED IZVRŠAVANJA

```
1. Kreiraj evalidator_base.html (CSS vars + topbar + footer)
2. Kreiraj static/css/evalidator.css (sve klase)
3. Refaktoriraj dashboard.html
4. Refaktoriraj bunker.html
5. Refaktoriraj dp_list.html + dp_detail.html
6. Refaktoriraj seal_innovation.html
7. Refaktoriraj verify_chain.html
8. Dodaj ChainStatusAPIView
9. manage.py check — 0 errors
10. systemctl reload gunicorn-fenix-v3.service
11. Ručno testiraj: evalidator.eu/ + /bunker/ + /dp/ + /dp/KONJ-DP-2026-001/ + /dp/novo/
```

---

## PRAVILA (obvezna)

1. **Nikad `{% extends "base.html" %}`** za evalidator templatee — uvijek `evalidator_base.html`
2. **Provjeri field nazive** u `evalidator/models.py` PRIJE svakog queryseta
3. **dp_detail.html** je JAVNA stranica (bez LoginRequiredMixin) — provjeri view
4. **manage.py check** mora biti 0 errors između svakog koraka
5. **Ne diraj** ostale Django templatee (base.html, dashboard, etc.)
6. **Mobilni** — svaka stranica mora raditi na 375px širini
7. **Commit** po završenom koraku: `feat(evalidator): redesign [stranica] — blockchain explorer UI`

---

## FINALNI TEST CHECKLIST

- [ ] `evalidator.eu/evalidator/` — dashboard s chain stats + blocklista
- [ ] `evalidator.eu/evalidator/bunker/` — file integrity + plates
- [ ] `evalidator.eu/evalidator/dp/` — lista svih 9 DP pločica
- [ ] `evalidator.eu/evalidator/dp/KONJ-DP-2026-001/` — javna detalj stranica
- [ ] `evalidator.eu/evalidator/dp/novo/` — forma (login required)
- [ ] `evalidator.eu/evalidator/verify/BNK-20260421-215902-D2FEB592/` — verify radi
- [ ] Mobilni (375px) — nema horizontal scroll, čitljivo
- [ ] Dark mode — svi elementi vidljivi, kontrast OK
- [ ] Live chain status u topbaru se ažurira

---

## PO ZAVRŠETKU

Ažuriraj ovaj fajl: STATUS → DONE
Ažuriraj /var/www/fenix-v3/FENIX_STATUS.md sekcija KONTEKST SESIJE
Commit: `feat(evalidator): blockchain explorer UI — complete redesign`
