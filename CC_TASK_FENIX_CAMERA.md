## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — FenixCamera: globalna kamera za sve module

## Problem
Kamera implementirana 8+ puta, svako drugačije:
- arhiva-convert.js → file input + FileReader
- pos-receipt.js → getUserMedia direktno  
- pos-scanner.js → file input + AI
- chat_widget.html → inline photoSelected()
- assessment templates → handlePhotos() lokalno
- smart-input.js → SmartInput.camera() (postoji ali nije konzistentno korišten)

## Rješenje: window.FenixCamera

Napiši: `/var/www/fina-connect/static/js/fenix-camera.js`

### API (što mora podržavati)

```javascript
// 1. Foto iz kamere ili galerije → base64 + blob
FenixCamera.pick({
  mode: 'photo',        // 'photo' | 'document' | 'barcode'
  source: 'any',        // 'camera' | 'gallery' | 'any'
  quality: 0.85,        // 0-1, JPEG kompresija
  maxWidth: 1920,       // resize ako veće
  onCapture: function(result) {
    // result.b64      → base64 string (bez data: prefix)
    // result.dataUrl  → "data:image/jpeg;base64,..."
    // result.blob     → Blob objekt
    // result.filename → "fenix_20260320_143022.jpg"
    // result.size_kb  → veličina u KB
  },
  onError: function(err) { console.warn(err); }
});

// 2. AI analiza slike → šalje na /ai/api/analyze-image/
FenixCamera.analyzeWithAI(b64, {
  prompt: 'Što je na slici?',
  module: 'arhiva',     // context za AI
  onResult: function(aiText) { ... },
  onError: function(err) { ... }
});

// 3. Preview u elementu
FenixCamera.showPreview(b64, elementId, {
  maxHeight: 120,
  clearBtn: true,
  onClear: function() { ... }
});

// 4. Upload na server
FenixCamera.upload(b64, filename, {
  url: '/documents/arhiva/upload/',
  extraData: { source_type: 'invoice', company_id: '...' },
  onSuccess: function(response) { ... },
  onError: function(err) { ... }
});

// 5. Brzi shortcut — Pick + Preview + callback
FenixCamera.quick(previewElementId, {
  onReady: function(result) {
    // Korisnik je odabrao sliku, preview prikazan
    // result.b64 dostupan za daljnje korištenje
  }
});
```

### Interna implementacija

```javascript
window.FenixCamera = (function() {
  'use strict';
  
  // Kompresija slike na canvas
  function _compress(file, maxWidth, quality, callback) {
    var reader = new FileReader();
    reader.onload = function(e) {
      var img = new Image();
      img.onload = function() {
        var canvas = document.createElement('canvas');
        var w = img.width, h = img.height;
        if (w > maxWidth) { h = Math.round(h * maxWidth / w); w = maxWidth; }
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        var dataUrl = canvas.toDataURL('image/jpeg', quality);
        canvas.toBlob(function(blob) {
          callback({
            b64: dataUrl.split(',')[1],
            dataUrl: dataUrl,
            blob: blob,
            filename: 'fenix_' + new Date().toISOString().replace(/[:.]/g,'').slice(0,15) + '.jpg',
            size_kb: Math.round(blob.size / 1024)
          });
        }, 'image/jpeg', quality);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }
  
  function pick(opts) {
    opts = opts || {};
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    if (opts.source !== 'gallery') input.capture = 'environment';
    input.style.display = 'none';
    document.body.appendChild(input);
    
    input.onchange = function() {
      if (!input.files[0]) return;
      _compress(input.files[0], opts.maxWidth || 1920, opts.quality || 0.85, function(result) {
        document.body.removeChild(input);
        if (opts.onCapture) opts.onCapture(result);
      });
    };
    
    // Android: ako se stranica reload-a nakon kamere, provjeri sessionStorage
    var key = '_fc_pending_' + Date.now();
    sessionStorage.setItem(key, '1');
    input.click();
    setTimeout(function() { sessionStorage.removeItem(key); }, 30000);
  }
  
  function showPreview(b64, elementId, opts) {
    opts = opts || {};
    var el = typeof elementId === 'string' ? document.getElementById(elementId) : elementId;
    if (!el) return;
    var dataUrl = b64.startsWith('data:') ? b64 : 'data:image/jpeg;base64,' + b64;
    el.innerHTML = '<div style="position:relative;display:inline-block">' +
      '<img src="' + dataUrl + '" style="max-width:100%;max-height:' + (opts.maxHeight||120) + 'px;border-radius:8px;border:1px solid #334155">' +
      (opts.clearBtn !== false ? '<button onclick="this.parentElement.parentElement.innerHTML=\'\';if(window._fc_onClear)window._fc_onClear()" style="position:absolute;top:4px;right:4px;background:rgba(0,0,0,.7);color:#fff;border:none;border-radius:50%;width:22px;height:22px;cursor:pointer;font-size:12px">✕</button>' : '') +
      '</div>';
    if (opts.onClear) window._fc_onClear = opts.onClear;
    el.style.display = 'block';
  }
  
  function analyzeWithAI(b64, opts) {
    opts = opts || {};
    fetch('/ai/api/analyze-image/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
      body: JSON.stringify({
        image_b64: b64,
        prompt: opts.prompt || 'Opiši što je na slici.',
        module: opts.module || 'general'
      })
    })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (opts.onResult) opts.onResult(d.response || d.text || ''); })
    .catch(function(e) { if (opts.onError) opts.onError(e); });
  }
  
  function upload(b64, filename, opts) {
    opts = opts || {};
    var fd = new FormData();
    // b64 → Blob
    var binary = atob(b64);
    var arr = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
    var blob = new Blob([arr], { type: 'image/jpeg' });
    fd.append('file', blob, filename || 'fenix_upload.jpg');
    if (opts.extraData) {
      Object.keys(opts.extraData).forEach(function(k) { fd.append(k, opts.extraData[k]); });
    }
    fd.append('csrfmiddlewaretoken', _csrf());
    
    fetch(opts.url || '/documents/arhiva/upload/', {
      method: 'POST',
      body: fd
    })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (opts.onSuccess) opts.onSuccess(d); })
    .catch(function(e) { if (opts.onError) opts.onError(e); });
  }
  
  function quick(previewElementId, opts) {
    opts = opts || {};
    pick({
      source: opts.source || 'any',
      quality: opts.quality || 0.85,
      maxWidth: opts.maxWidth || 1600,
      onCapture: function(result) {
        if (previewElementId) showPreview(result.b64, previewElementId, { onClear: opts.onClear });
        if (opts.onReady) opts.onReady(result);
      },
      onError: opts.onError
    });
  }
  
  function _csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
  
  return { pick, showPreview, analyzeWithAI, upload, quick };
})();
```

## Dodaj u base.html
Odmah ispod core.js i smart-input.js:
```html
<script src="/static/js/fenix-camera.js"></script>
```

Pronađi gdje su drugi JS fajlovi u base.html i dodaj tamo.

## Refaktoriziraj 3 najvažnija mjesta (ostala later)

### 1. chat_widget.html — zamijeni inline photoSelected
Pronađi photoSelected funkciju i zamijeni:
```javascript
// STARO:
window.photoSelected = function(input) { var file=input.files[0]; ... FileReader ... }

// NOVO:
document.getElementById('aiwPhotoInput').addEventListener('change', function() {
  if (!this.files[0]) return;
  FenixCamera._compressInternal(this.files[0], 1600, 0.85, function(r) {
    window._aiwPhotoB64 = r.b64;
    FenixCamera.showPreview(r.b64, 'aiwPhotoPreview', {maxHeight:60});
  });
});
```

Ili još lakše — koristi quick():
```javascript
// 📷 gumb u widgetu:
document.getElementById('aiwPhotoBtn').onclick = function() {
  FenixCamera.quick('aiwPhotoPreview', {
    onReady: function(r) { window._aiwPhotoB64 = r.b64; },
    onClear: function() { window._aiwPhotoB64 = null; }
  });
};
```

### 2. arhiva_upload.html — zamijeni file input logiku
```javascript
// STARO: inline FileReader u arhiva-upload.js

// NOVO:
document.getElementById('fenix-photo-btn').onclick = function() {
  FenixCamera.quick('photo-preview', {
    onReady: function(r) {
      window._arhivaPhoto = r;
      document.getElementById('photo-size').textContent = r.size_kb + 'KB';
    }
  });
};
```

### 3. cockpit okrugli stol — foto za seat
```javascript
// U seat-camera input:
document.getElementById('seat-camera').onchange = function() {
  FenixCamera.quick('seat-photo-preview', {
    onReady: function(r) { window._seatPhoto = r.b64; }
  });
};
```

## Dodaj /ai/api/analyze-image/ endpoint (ako ne postoji)
```bash
grep -rn "analyze.image\|analyze_image" /var/www/fina-connect/ai_assistant/urls.py
```
Ako ne postoji, dodaj u ai_assistant/views.py:
```python
@login_required
@require_POST
def analyze_image(request):
    import json, base64
    from django.http import JsonResponse
    data = json.loads(request.body)
    b64 = data.get('image_b64','')
    prompt = data.get('prompt', 'Što je na slici?')
    module = data.get('module', 'general')
    # Koristi postojeći AI chat mehanizam s image
    from ai_assistant.services import chat_with_image
    try:
        response = chat_with_image(b64, prompt, module, request.user)
        return JsonResponse({'response': response})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

## Provjere
```bash
cd /var/www/fina-connect

# Fajl kreiran?
ls -la static/js/fenix-camera.js

# Sintaksa OK?
node -e "eval(require('fs').readFileSync('static/js/fenix-camera.js','utf8')); console.log('OK')" 2>/dev/null || echo "Node nije dostupan - provjeri ručno"

# Django check
venv/bin/python manage.py check 2>&1 | tail -2

# Collectstatic
venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -3
```

## Javi
- Broj linija fenix-camera.js
- Je li dodan u base.html
- Je li analyze_image endpoint dodan/pronađen
- Django check status
