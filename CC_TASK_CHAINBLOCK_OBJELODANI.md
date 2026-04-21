# CC_TASK: ChainBlock Objelodanjivanje — Tri zadatka

## STATUS: DONE
## PRIORITET: P0 — infrastruktura je LIVE, javna face nije

---

## KONTEKST

Genesis Block postoji:
  curl https://limit-connect.com/api/verify/NOLIMIT-GENESIS-0001/
  → {"verified": true, "tsa_timestamp": "2026-04-19T21:28:42.809638+00:00",
     "block_hash": "66c8d2862d5a661c6cbe14affbb1d25b0fd3dc0f4950b9fd9a5c8095419a81b5",
     "integrity": "ok", "standard": "eIDAS Art. 41 | ZED HR NN 150/05"}

Landing page: ima statični Genesis card ali BEZ live API fetch-a.
Ustav dokumenti: nisu zapečaćeni kao ChainBlock zapisi.
Trust Badge: ne postoji.

---

## ZADATAK A — Live Verification na landing.html

### A-01 | STATUS: DONE ✅
Dodati JavaScript fetch na landing.html koji poziva pravi API:

Naći u landing.html blok oko linije 315 gdje je "NOLIMIT-GENESIS-0001"
Zamijeniti statični prikaz s live fetchem:

```javascript
// Ubaci PRIJE </body>
async function verifyGenesis() {
  const el = document.getElementById('genesis-live-status');
  if (!el) return;
  try {
    const r = await fetch('/api/verify/NOLIMIT-GENESIS-0001/');
    const d = await r.json();
    if (d.verified && d.integrity === 'ok') {
      el.innerHTML = `
        <span class="genesis-badge">
          <span class="genesis-dot"></span>
          VERIFICIRANO UŽIVO · ${new Date(d.tsa_timestamp).toLocaleDateString('hr-HR')}
        </span>
        <div class="genesis-hash">HASH: ${d.block_hash}</div>
        <div style="margin-top:8px;font-size:.75rem;color:var(--dim)">
          ${d.standard} · Block #${d.block_number} · ${d.doc_count} dokumenata
        </div>`;
    }
  } catch(e) {
    el.innerHTML = '<span style="color:var(--dim)">Offline — hash nepromjenjiv</span>';
  }
}
document.addEventListener('DOMContentLoaded', verifyGenesis);
```

Dodati `id="genesis-live-status"` div unutar postojeće .genesis-card sekcije.

### A-02 | STATUS: DONE ✅
Dodati "Verificiraj bilo koji dokument" input odmah ispod Genesis card:

```html
<div class="verify-input-wrap" style="margin-top:24px">
  <input id="verify-token-input" 
         placeholder="Unesi seal token (npr. NOLIMIT-GENESIS-0001)"
         style="width:100%;padding:12px 16px;background:var(--surface);
                border:1px solid var(--border);border-radius:8px;
                color:var(--white);font-family:monospace;font-size:.85rem">
  <button onclick="verifyCustomToken()"
          style="margin-top:8px;padding:10px 24px;background:var(--gold);
                 color:#0a0a0a;border:none;border-radius:8px;
                 font-weight:700;cursor:pointer;width:100%">
    Verificiraj →
  </button>
  <div id="custom-verify-result" style="margin-top:12px;font-family:monospace;font-size:.8rem"></div>
</div>
```

```javascript
async function verifyCustomToken() {
  const token = document.getElementById('verify-token-input').value.trim();
  const el = document.getElementById('custom-verify-result');
  if (!token) return;
  el.innerHTML = 'Verificiram...';
  try {
    const r = await fetch(`/api/verify/${encodeURIComponent(token)}/`);
    const d = await r.json();
    if (d.verified) {
      el.innerHTML = `✅ VERIFICIRANO · ${d.tsa_timestamp} · ${d.standard}`;
      el.style.color = 'var(--green)';
    } else {
      el.innerHTML = '❌ Dokument nije pronađen u ChainBlocku';
      el.style.color = '#ef4444';
    }
  } catch(e) {
    el.innerHTML = '⚠️ Greška pri verifikaciji';
  }
}
```

---

## ZADATAK B — Pečati Ustav dokumente kao ChainBlock zapise

### B-01 | STATUS: DONE ✅
Pročitaj kako radi seal u evalidator/seal_service.py, zatim zapečati:

```bash
cd /var/www/fenix-v3
python manage.py shell << 'EOF'
from evalidator.seal_service import SealService  # ili ekvivalentni import

documents = [
    {
        'token': 'LC-DS-2026-001',
        'title': 'LIMIT-CONNECT MREŽNI USTAV v1.0',
        'path': '/var/www/fenix-v3/LIMIT_CONNECT_USTAV_v1.md',
        'issuer': 'NO LIMIT — udruga za promicanje digitalizacije',
        'oib': '70086599476',
    },
    {
        'token': 'LC-DS-2026-002',
        'title': 'Amandman I — Digitalni Patentni Ured (DPU)',
        'path': '/var/www/fenix-v3/LIMIT_CONNECT_USTAV_AMANDMAN_I.md',
        'issuer': 'NO LIMIT — udruga za promicanje digitalizacije',
        'oib': '70086599476',
    },
    {
        'token': 'LC-DS-2026-003',
        'title': 'Amandman II — Tehnička Neizbježnost + Autonomni Rast',
        'path': '/var/www/fenix-v3/LIMIT_CONNECT_USTAV_AMANDMAN_II.md',
        'issuer': 'NO LIMIT — udruga za promicanje digitalizacije',
        'oib': '70086599476',
    },
]

# Provjeri stvarni API SealService-a PRIJE izvršavanja
# Ne pretpostavljaj argumente — pročitaj seal_service.py
EOF
```

PROČITAJ seal_service.py PRIJE. Nikad ne pretpostavljaj API.

### B-02 | STATUS: DONE ✅
Verificiraj sve tri pečate:
```bash
curl https://limit-connect.com/api/verify/LC-DS-2026-001/
curl https://limit-connect.com/api/verify/LC-DS-2026-002/
curl https://limit-connect.com/api/verify/LC-DS-2026-003/
```

Sva tri moraju vratiti `"verified": true`.

### B-03 | STATUS: DONE ✅
Ažuriraj LIMIT_CONNECT_USTAV_v1.md — zamijeni placeholder hash:
```
STARO: GENESIS HASH: 4997baeec713f7c117adf95f87b68f3e1befb0b0ccdbeec853451428673d8bad
NOVO:  GENESIS HASH: 66c8d2862d5a661c6cbe14affbb1d25b0fd3dc0f4950b9fd9a5c8095419a81b5
       CHAIN TOKEN:  NOLIMIT-GENESIS-0001 | LC-DS-2026-001 | LC-DS-2026-002 | LC-DS-2026-003
       VERIFY:       https://limit-connect.com/api/verify/LC-DS-2026-001/
```

---

## ZADATAK C — Trust Badge (embeddable widget)

### C-01 | STATUS: DONE ✅
Kreirati: `/var/www/fina-connect/static/trust-badge.js`

```javascript
/**
 * Limit-Connect Trust Badge
 * Korištenje: <div data-lc-verify="SEAL_TOKEN"></div>
 * Embed: <script src="https://limit-connect.com/static/trust-badge.js"></script>
 */
(function() {
  const API = 'https://limit-connect.com/api/verify/';
  const STYLE = `
    .lc-badge{display:inline-flex;align-items:center;gap:6px;
      padding:6px 12px;border-radius:20px;font-family:sans-serif;
      font-size:12px;font-weight:600;text-decoration:none;cursor:pointer}
    .lc-badge-ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.4);color:#22c55e}
    .lc-badge-err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.4);color:#ef4444}
    .lc-dot{width:7px;height:7px;border-radius:50%;animation:lc-pulse 2s infinite}
    .lc-dot-ok{background:#22c55e}
    @keyframes lc-pulse{0%,100%{opacity:1}50%{opacity:.4}}
  `;

  function inject() {
    const s = document.createElement('style');
    s.textContent = STYLE;
    document.head.appendChild(s);

    document.querySelectorAll('[data-lc-verify]').forEach(async el => {
      const token = el.dataset.lcVerify;
      el.innerHTML = '<span style="font-size:11px;opacity:.5">Verificiram...</span>';
      try {
        const d = await (await fetch(API + token + '/')).json();
        if (d.verified) {
          el.innerHTML = `<a href="${API}${token}/" target="_blank" class="lc-badge lc-badge-ok">
            <span class="lc-dot lc-dot-ok"></span>
            Verificirano · ChainBlock
          </a>`;
        } else { throw new Error(); }
      } catch {
        el.innerHTML = `<span class="lc-badge lc-badge-err">⚠ Nije verificirano</span>`;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else { inject(); }
})();
```

### C-02 | STATUS: DONE ✅
Dodati na landing.html sekciju "Ugradi badge":

```html
<div style="background:var(--surface);border:1px solid var(--border);
            border-radius:12px;padding:24px;margin-top:24px">
  <h4 style="margin-bottom:12px;font-size:.9rem">Ugradi na svoju stranicu:</h4>
  <code style="font-family:monospace;font-size:.75rem;color:var(--gold);
               display:block;background:var(--bg);padding:12px;
               border-radius:6px;word-break:break-all">
&lt;script src="https://limit-connect.com/static/trust-badge.js"&gt;&lt;/script&gt;<br>
&lt;div data-lc-verify="TVOJ-SEAL-TOKEN"&gt;&lt;/div&gt;
  </code>
</div>
```

---

## ZADATAK D — Commit

```
feat(chainblock): live verification UI + Ustav seals + Trust Badge widget

- landing.html: live API fetch za Genesis + custom verify input
- ChainBlock: LC-DS-2026-001/002/003 zapečaćeni
- trust-badge.js: embeddable widget (3 linije ugradnje)
- LIMIT_CONNECT_USTAV_v1.md: real genesis hash + chain tokens
```

---

## REDOSLJED

A-01 → A-02 → B-01 → B-02 → B-03 → C-01 → C-02 → D

PROČITAJ seal_service.py PRIJE B-01. Nikad ne pretpostavljaj API.
