## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — HITNO: Arhiva mobile UX + duplicate fix

## Bugs s terena (Ivan testirao na mobitelu, bez interneta)

### BUG 1 — KRITIČNO: Dupli upload bez upozorenja
Isti račun uploadiran 2× — sustav prihvatio oba bez ikakve poruke.

**Fix u documents/views.py, funkcija arhiva_upload:**
PRIJE kreiranja ArhivaEntry, provjeri hash:
```python
file_bytes = uploaded.read()
import hashlib
file_hash = hashlib.sha256(file_bytes).hexdigest()

# Provjeri duplikat
duplicate = ArhivaEntry.objects.filter(
    company=company,
    source_id=file_hash
).first()

if duplicate:
    messages.warning(request,
        f'⚠️ Ovaj dokument je već arhiviran {duplicate.archived_at.strftime("%d.%m.%Y")} '
        f'kao "{duplicate.doc_number or duplicate.file_path.split("/")[-1]}". '
        f'Nije potrebno ponovo učitavati.'
    )
    return redirect('documents:arhiva_list')
```

Zatim proslijedi `file_bytes` u `store_document()` umjesto `uploaded.read()` (već pročitano).

### BUG 2 — Forma zbunjuje korisnika na mobitelu
Forma nema vodič — korisnik ne zna što je obavezno, što nije.

**Fix u templates/documents/arhiva_upload.html:**

1. Dodaj progress indicator na vrh:
```html
<div style="display:flex;gap:8px;margin-bottom:1.5rem;align-items:center">
  <div style="width:28px;height:28px;border-radius:50%;background:#c9a84c;color:#000;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;flex-shrink:0">1</div>
  <div style="font-size:.9rem;color:#c9a84c;font-weight:600">Odaberi ili fotografiraj dokument</div>
</div>
```

2. Kamera/upload gumb mora biti PRVI i VELIK (min 60px visine):
```html
<label for="file" style="display:block;background:#1e293b;border:2px dashed #c9a84c;border-radius:12px;padding:2rem;text-align:center;cursor:pointer;margin-bottom:1rem">
  <div style="font-size:2rem;margin-bottom:.5rem">📷</div>
  <div style="color:#c9a84c;font-weight:700">Fotografiraj ili odaberi fajl</div>
  <div style="font-size:.75rem;color:#64748b;margin-top:.25rem">PDF, slika, XML</div>
</label>
<input type="file" id="file" name="file" accept="image/*,application/pdf,.xml" capture="environment" style="display:none" required>
```

3. Ostala polja (doc_number, partner_name, amount) — označi jasno što je obavezno:
```html
<label>Broj računa <span style="color:#ef4444">*</span></label>
```

4. Submit gumb — jasna povratna informacija:
```html
<button type="submit" id="submit-btn" 
  style="width:100%;background:#c9a84c;color:#000;border:none;padding:1rem;border-radius:10px;font-weight:700;font-size:1rem;margin-top:1rem">
  📤 Spremi u arhivu
</button>
```

JS — disable button nakon klika da spriječi dupli submit:
```javascript
document.querySelector('form').addEventListener('submit', function() {
  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Spremam...';
});
```

### BUG 3 — Offline mod ne radi za upload
Upload zahtijeva server. Na mobitelu bez interneta → forma se otvori ali submit pada.

**Fix — detektiraj offline i obavijesti korisnika:**
```javascript
// Na vrhu arhiva_upload.html
if (!navigator.onLine) {
  document.getElementById('offline-warning').style.display = 'block';
  document.getElementById('submit-btn').disabled = true;
  document.getElementById('submit-btn').textContent = '📵 Nema interneta';
}

window.addEventListener('online', function() {
  document.getElementById('offline-warning').style.display = 'none';
  document.getElementById('submit-btn').disabled = false;
  document.getElementById('submit-btn').textContent = '📤 Spremi u arhivu';
});
window.addEventListener('offline', function() {
  document.getElementById('offline-warning').style.display = 'block';
  document.getElementById('submit-btn').disabled = true;
  document.getElementById('submit-btn').textContent = '📵 Nema interneta';
});
```

HTML poruka:
```html
<div id="offline-warning" style="display:none;background:#1a2e1a;border:1px solid #ef4444;border-radius:8px;padding:.75rem;margin-bottom:1rem;font-size:.85rem;color:#ef4444">
  📵 Nema internetske veze. Upload nije moguć. Dokument možeš fotografirati i učitati kad se vrati internet.
</div>
```

### BUG 4 — Neskladne tipke (mobile)
Tipke različitih veličina, premale za prst.

**Fix — dodaj u CSS arhiva_upload.html:**
```css
button, .btn, input[type="submit"] {
  min-height: 48px;
  font-size: 1rem;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}
```

## Redoslijed fixa
1. BUG 1 (duplikat) — views.py — NAJHITNIJE
2. BUG 3 (offline warning) — template — HITNO
3. BUG 4 (tipke) — CSS — brzo
4. BUG 2 (forma vodič) — template — kad stigneš

## Provjere
```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -2
# Test duplikat:
venv/bin/python manage.py shell -c "
from documents.views import arhiva_upload
print('source_id hash check:', 'source_id=file_hash' in open('documents/views.py').read() or 'sha256' in open('documents/views.py').read())
"
systemctl reload gunicorn-fina
```

## Javi
- Je li sha256 duplikat check dodan
- Je li offline warning u templateu
- Django check status
