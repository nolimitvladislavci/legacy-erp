# CC Task — Notification sustav: ugodna komunikacija

## Pravila (ne mijenjaj bez razloga)
- SUCCESS  → toast 3s, gore desno desktop / dole mobitel, nestane sama
- INFO     → toast 6s, nestane sama  
- WARNING  → toast ostaje, korisnik zatvara
- ERROR    → toast ostaje + akcijski gumb ("Pokušaj ponovo" / "Razumijem")
- INLINE   → uz formu, nikad leti, nestane kad korisnik ispravi
- Max 3 toasta odjednom — 4. potiskuje najstariji

## Korak 1 — Popravi core.js: initToasts()

Pronađi funkciju initToasts() i zamijeni:

```javascript
function initToasts(){
  var MAX_VISIBLE = 3;
  var toasts = Array.from(document.querySelectorAll('.toast-msg'));
  
  // Sakrij višak
  if (toasts.length > MAX_VISIBLE) {
    toasts.slice(0, toasts.length - MAX_VISIBLE).forEach(function(el) {
      el.remove();
    });
    toasts = toasts.slice(-MAX_VISIBLE);
  }

  toasts.forEach(function(el) {
    var duration = 3000; // default success
    if (el.classList.contains('alert-info')) duration = 6000;
    if (el.classList.contains('alert-warning') || 
        el.classList.contains('alert-danger')) duration = 0; // ne gasi
    
    // Progress bar
    if (duration > 0) {
      var bar = document.createElement('div');
      bar.style.cssText = 'position:absolute;bottom:0;left:0;height:2px;border-radius:1px;' +
        'background:currentColor;opacity:.3;width:100%;' +
        'transition:width ' + duration + 'ms linear';
      el.style.position = 'relative';
      el.appendChild(bar);
      setTimeout(function() { bar.style.width = '0'; }, 50);
      
      setTimeout(function(){
        el.style.transition = 'all 0.4s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateX(16px)';
        setTimeout(function(){ el.remove(); }, 400);
      }, duration);
    }
  });
}
```

## Korak 2 — Popravi base.html: mobitel pozicija

Pronađi #toast-container i dodaj mobile override:

```html
<div id="toast-container" style="position:fixed;top:60px;right:12px;z-index:9999;width:340px;max-width:calc(100vw - 24px)">
```

Dodaj CSS u base.html <style> ili core.css:
```css
@media (max-width: 600px) {
  #toast-container {
    top: auto !important;
    bottom: 72px !important;
    right: 8px !important;
    left: 8px !important;
    width: auto !important;
  }
}
```

## Korak 3 — window.showToast() — globalna JS funkcija

Pronađi showToast u core.js i nadogradi (ili dodaj ako ne postoji):

```javascript
window.showToast = function(message, type, opts) {
  type = type || 'info';
  opts = opts || {};
  var duration = {success:3000, info:6000, warning:0, error:0}[type] || 4000;
  if (opts.duration !== undefined) duration = opts.duration;

  var container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;top:60px;right:12px;z-index:9999;width:340px;max-width:calc(100vw - 24px)';
    document.body.appendChild(container);
  }

  // Max 3
  var existing = container.querySelectorAll('.toast-msg');
  if (existing.length >= 3) existing[0].remove();

  var colors = {
    success: 'background:rgba(240,253,244,.97);border:1px solid #bbf7d0;color:#166534',
    info:    'background:rgba(239,246,255,.97);border:1px solid #bfdbfe;color:#1e40af',
    warning: 'background:rgba(255,251,235,.97);border:1px solid #fed7aa;color:#92400e',
    error:   'background:rgba(254,242,242,.97);border:1px solid #fecaca;color:#991b1b',
  };

  var el = document.createElement('div');
  el.className = 'toast-msg alert alert-' + type;
  el.style.cssText = 'border-radius:10px;padding:.6rem .9rem;font-size:.82rem;' +
    'margin-bottom:8px;position:relative;overflow:hidden;' + (colors[type]||colors.info);

  var html = '<span>' + message + '</span>';
  if (opts.action) {
    html += ' <button onclick="' + opts.action.fn + '" style="margin-left:8px;background:none;' +
      'border:none;font-weight:600;cursor:pointer;color:inherit;text-decoration:underline;font-size:.82rem">' +
      opts.action.label + '</button>';
  }
  html += '<button onclick="this.parentElement.remove()" style="float:right;background:none;' +
    'border:none;font-size:1rem;cursor:pointer;color:inherit;margin-left:8px;opacity:.6">&times;</button>';
  
  if (duration > 0) {
    html += '<div style="position:absolute;bottom:0;left:0;height:2px;background:currentColor;' +
      'opacity:.25;width:100%;transition:width ' + duration + 'ms linear" id="tp_' + Date.now() + '"></div>';
  }
  
  el.innerHTML = html;
  container.appendChild(el);

  if (duration > 0) {
    var bar = el.querySelector('[id^="tp_"]');
    if (bar) setTimeout(function(){ bar.style.width='0'; }, 50);
    setTimeout(function(){
      el.style.transition = 'all .4s';
      el.style.opacity = '0';
      el.style.transform = 'translateX(16px)';
      setTimeout(function(){ el.remove(); }, 400);
    }, duration);
  }
  
  return el;
};
```

## Korak 4 — Primjeri korištenja u templateima

Zamijeni inline alert() i console.log() s showToast():

```javascript
// Umjesto: alert('Greška')
showToast('Greška uploada. Provjeri vezu.', 'error', {
  action: { label: 'Pokušaj ponovo', fn: 'location.reload()' }
});

// Umjesto: console.log('OK')  
showToast('Dokument arhiviran', 'success');

// Upozorenje koje ostaje
showToast('Ovaj dokument već postoji u arhivi.', 'warning', {
  action: { label: 'Pogledaj', fn: 'window.location="/hr/documents/arhiva/"' }
});

// Info s custom trajanjem
showToast('Obrađujem sliku u pozadini...', 'info', { duration: 8000 });

// Offline poruka
if (!navigator.onLine) {
  showToast('Nema interneta. Radite u offline modu.', 'warning');
}
```

## Korak 5 — Arhiva upload: uskladi poruke

U templates/documents/arhiva_upload.html, u submit handleru:

```javascript
// Kad upload počne:
showToast('Primam dokument...', 'info', { duration: 10000 });

// Kad uspije (redirect znači success — Django message):
// (Django messages već rade — samo provjeri da su usklađene)

// Kad padne:
showToast('Upload nije uspio. ' + (navigator.onLine ? 'Pokušaj ponovo.' : 'Nema interneta.'), 
  'error', { action: { label: 'Ponovi', fn: 'document.getElementById("uploadForm").requestSubmit()' }});
```

## Provjere
```bash
cd /var/www/fina-connect
grep -n "showToast\|initToasts\|toast-msg" static/js/core.js | head -10
grep -n "toast-container\|@media.*600" templates/base.html | head -5
venv/bin/python manage.py check 2>&1 | tail -2
```

## Javi
- Broj linija showToast funkcije
- Je li mobile CSS dodan
- Je li progress bar u initToasts
