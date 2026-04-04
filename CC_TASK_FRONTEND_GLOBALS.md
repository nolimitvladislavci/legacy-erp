# CC_TASK: FRONTEND GLOBALNE FUNKCIJE — konsolidacija
# Datum: 05.04.2026. | Prioritet: P1 | Rok: 07.04.2026.
#
# Problem: 5 toast implementacija, getCsrf duplikat, window.showToast conflict

PRAVILO: NE diras base.html strukturu. Samo JS datoteke.
PRAVILO: Svaka izmjena mora biti backwardno kompatibilna.

---

## F1 — window.showToast conflict [KRITIČNO za POS]

```bash
grep -n "window.showToast\s*=" static/js/pos/pos-quick.js static/js/pos/pos-receipt.js
```

Problem: obje datoteke definiraju window.showToast — koja se posljednja učita, ona ostaje.

FIX — pos-receipt.js:
```javascript
// ZAMIJENI u pos-receipt.js:
// window.showToast = function(msg, type) { ... }
// SA:
if (!window.showToast) {
  window.showToast = function(msg, type) {
    // ... ista implementacija
  };
}
```

FIX — pos-quick.js (ista promjena):
```javascript
if (!window.showToast) {
  window.showToast = function(msg, duration) {
    // ... ista implementacija
  };
}
```

Dugoročno: sve POS toast pozive unificirati na window.fenixToast.

---

## F2 — getCsrf duplikat: dokumentiraj namjeru

```bash
grep -n "function getCsrf" static/js/core.js static/js/pos/pos-core.js
```

POS kontekst ne učitava core.js (teži paket), pos-core.js je standalone.
Ovo je NAMJERNA arhitekturalna odluka.

FIX — dodaj komentar u pos-core.js:
```javascript
// getCsrf: lokalna kopija za POS context (ne učitava core.js)
// Izmjene ovdje treba replicirati u static/js/core.js i obratno
function getCsrf() { ... }
```

---

## F3 — FC objekt: proširi

READ: templates/base.html (window.FC definicija, ~linija 316)

DODAJ u window.FC:
```javascript
window.FC = {
  ...existing...,
  companyId: {{ company.pk|default:'null' }},
  userId: {{ request.user.pk|default:'null' }},
  csrfToken: '{{ csrf_token }}',  // Alternativa getCsrf() parsiranju
  apiPrefix: '{% get_current_language as LANGUAGE_CODE %}/{{ LANGUAGE_CODE }}',
};
```

---

## VERIFIKACIJA

```bash
# Conflict test
node -e "
var w = {};
// Simulacija pos-quick.js
if (!w.showToast) { w.showToast = function(m){ return 'quick:' + m; }; }
// Simulacija pos-receipt.js
if (!w.showToast) { w.showToast = function(m){ return 'receipt:' + m; }; }
console.log(w.showToast('test')); // Treba biti 'quick:test'
"

# JS syntax check
find static/js -name "*.js" ! -name "*.min.*" ! -name "*.bak*" | \
  xargs -I{} node --check {} 2>&1 | grep "SyntaxError\|parse error" | head -10
```
