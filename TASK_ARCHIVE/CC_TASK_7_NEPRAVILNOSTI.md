# CC_TASK: MEMIO.PET POLIRANJE — Dark/Light toggle + UI 10/10
# Datum: 05.04.2026. | Prioritet: P0 — vidljivo korisnicima odmah
#
# Problem:
#   1. profile.html NEMA theme toggle gumb (ni sunce ni mjesec)
#   2. Nema CSS dark mode varijabli → OS dark mode = kaos
#   3. breeder.html, barf_listings.html — isti problem
#   4. memio.world/index.html — nema toggle
#
# Rješenje:
#   Dodati toggle u svaki standalone template + localStorage sync

PRAVILO: NE diras base.html portala — ovi su STANDALONE htmli.
PRAVILO: CSS varijable su sve u :root — dark mode mijenja samo te varijable.
PRAVILO: localStorage key = 'memio-theme' (odvojen od portal 'fina-theme')

---

## KORAK 1 — PROVJERI sve memio.pet templates

```bash
ls templates/memio_pet/
wc -l templates/memio_pet/*.html
grep -l "data-theme\|toggleTheme\|localStorage.*theme" templates/memio_pet/*.html
cat /var/www/memio/index.html | grep -c "theme"
```

---

## KORAK 2 — CSS za profile.html

READ: templates/memio_pet/profile.html

U `<style>` bloku, DODAJ odmah iza `:root { ... }`:

```css
/* ── DARK MODE ── */
[data-theme="dark"]{
  --bg:   #0d0f11;
  --ink:  #f0ede5;
  --ink2: #b8b0a0;
  --line: #2a2a3a;
  --dim:  #6b6b80;
  --green:#34d058;
  --red:  #f87171;
}
[data-theme="dark"] .hero-card,
[data-theme="dark"] .trust-card,
[data-theme="dark"] .info-section,
[data-theme="dark"] .qr-section {
  background: #181a1d;
  box-shadow: 0 2px 20px rgba(0,0,0,.3);
}
[data-theme="dark"] .trust-bar { background: #2a2a3a; }
[data-theme="dark"] .timeline li::before { border-color: var(--bg); }

/* ── TOGGLE GUMB ── */
.theme-toggle {
  background: transparent;
  border: 1px solid rgba(255,255,255,.2);
  border-radius: 20px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 1rem;
  color: #f8f6f0;
  transition: background .2s;
  display: flex; align-items: center; gap: 6px;
}
.theme-toggle:hover { background: rgba(255,255,255,.1); }
```

---

## KORAK 3 — Toggle gumb u top-bar

READ: profile.html — top-bar div

ZAMIJENI top-bar:
```html
<div class="top-bar">
  <a href="https://memio.pet">Memio<span>.pet</span></a>
  <div style="display:flex;align-items:center;gap:12px;">
    {% if verified %}
      <span class="verified-tag">✓ VERIFICIRAN</span>
    {% else %}
      <span class="unverified-tag">NEVERIFICIRAN</span>
    {% endif %}
    <button class="theme-toggle" onclick="toggleTheme()" id="themeBtn" title="Promijeni temu">
      🌙
    </button>
  </div>
</div>
```

---

## KORAK 4 — JavaScript (na dnu, prije </body>)

DODAJ u profile.html:
```html
<script>
(function(){
  // Inicijalizacija pri učitavanju
  const saved = localStorage.getItem('memio-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  updateBtn(theme);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('memio-theme', next);
  updateBtn(next);
}

function updateBtn(theme) {
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}
</script>
```

---

## KORAK 5 — ISTI PATTERN za breeder.html

READ: templates/memio_pet/breeder.html

PRIMIJENI isti pattern:
1. Dark mode CSS varijable u :root
2. Toggle gumb u header/nav
3. JS snippet (isti kod)

---

## KORAK 6 — ISTI PATTERN za barf_listings.html, pet_hotel_booking.html, training_list.html

Sve memio_pet/*.html stranice koje imaju vlastiti <head> — dodaj isti dark mode CSS + toggle gumb.

```bash
# Provjeri koje imaju vlastiti <!DOCTYPE html>
grep -l "<!DOCTYPE html>" templates/memio_pet/*.html
```

---

## KORAK 7 — memio.world/index.html

READ: /var/www/memio/index.html

Ova stranica ima --paper, --ink, --cream varijable.

DODAJ dark mode CSS iza :root:
```css
[data-theme="dark"] {
  --paper: #0d0f11;
  --cream: #141618;
  --ink:   #f0ede5;
  --ink2:  #b8b0a0;
  --gold:  #e2c36d;
  --dim:   #7a7060;
  --line:  #2a2a3a;
}
[data-theme="dark"] nav {
  background: rgba(13,15,17,0.95);
  border-bottom-color: #2a2a3a;
}
[data-theme="dark"] .hero-card,
[data-theme="dark"] .problem-card,
[data-theme="dark"] .feature-card {
  background: #181a1d;
}
```

U NAV — dodaj toggle:
```html
<nav>
  <a href="/" class="nav-logo">Me<span>m</span>io</a>
  <div style="display:flex;align-items:center;gap:12px;">
    <button id="themeBtn" onclick="toggleTheme()"
      style="background:transparent;border:1px solid var(--line);
      border-radius:20px;padding:6px 14px;cursor:pointer;
      font-size:1rem;color:var(--ink);transition:.2s;">
      🌙
    </button>
    <a href="#waitlist" class="nav-cta">Prijavi se</a>
  </div>
</nav>
```

JS — isti snippet na dnu (iza waitlist script):
```html
<script>
(function(){
  const saved = localStorage.getItem('memio-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  updateBtn(theme);
})();
function toggleTheme(){
  const c = document.documentElement.getAttribute('data-theme') || 'light';
  const n = c === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', n);
  localStorage.setItem('memio-theme', n);
  updateBtn(n);
}
function updateBtn(t){
  const b = document.getElementById('themeBtn');
  if(b) b.textContent = t === 'dark' ? '☀️' : '🌙';
}
</script>
```

---

## KORAK 8 — POLIRANJE: profile.html sitni UI bugovi

Dok si u tom fajlu, ispravi i:

1. `<title>` encoding — specijalni znakovi
2. QR sekcija: ako qr_url ne postoji → sakrij sekciju
3. Hero placeholder emoji — provjeri da se prikazuje na iOS
4. Trust score boja logika:
   ```html
   <!-- Dodaj u view ili template: -->
   <!-- 0-40=crvena, 41-70=narančasta, 71-100=zelena -->
   ```
5. Meta color-scheme za ispravan browser dark mode hint:
   ```html
   <!-- U <head>, odmah iza <meta charset>: -->
   <meta name="color-scheme" content="light dark">
   ```

---

## KORAK 9 — VERIFIKACIJA

```bash
# Django check
venv/bin/python manage.py check 2>&1 | tail -3

# Provjeri postoji li toggle u svim templateima
grep -l "toggleTheme\|themeBtn" templates/memio_pet/*.html /var/www/memio/index.html

# Gunicorn restart (templates su statički, ne treba, ali za sigurnost)
systemctl restart gunicorn-fina && sleep 2

git add -A
git commit -m "feat(memio-pet): dark/light toggle, OS dark mode fix, memio.world theme"
```

---

## DONE KRITERIJI:
- [ ] profile.html: 🌙/☀️ gumb u top-bar, reagira na klik
- [ ] profile.html: dark mode CSS varijable postoje
- [ ] profile.html: localStorage pamti izbor
- [ ] profile.html: OS dark mode → automatski dark pri prvom posjetu
- [ ] breeder.html: isti pattern
- [ ] barf/hotel/training: isti pattern
- [ ] memio.world: toggle u nav, dark CSS vars
- [ ] meta color-scheme na svim memio stranicama
- [ ] 0 JS errora u konzoli
