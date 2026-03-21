## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — HITNO: AI Widget foto gumb (5 minuta)

## Problem
chat_widget.html ima CSS za foto gumb ali HTML nije dodan u input bar.
Marija čeka. Brzo.

## Točna lokacija u fajlu
```bash
grep -n "aiw-input-bar\|aiwInput\|aiw-send" \
  /var/www/fina-connect/templates/ai_assistant/chat_widget.html
```

## Fix — zamijeni input bar

Nađi ovaj blok (otprilike linije 102-107):
```html
    <div class="aiw-input-bar">
        <input class="aiw-input" id="aiwInput" placeholder="Pitajte nesto..."
               onkeydown="if(event.key==='Enter'){event.preventDefault();sendWidgetMsg()}">
        <button class="aiw-send" onclick="sendWidgetMsg()"><i class="fas fa-paper-plane"></i></button>
    </div>
```

Zamijeni s:
```html
    <div id="aiwPhotoPreview" style="display:none;padding:4px 12px 6px;background:#0f172a;">
        <button onclick="clearPhoto()" style="float:right;background:none;border:none;color:#888;cursor:pointer;">✕</button>
        <img id="aiwPhotoThumb" src="" style="max-width:100%;max-height:60px;border-radius:4px;border:1px solid #334155;">
    </div>
    <div class="aiw-input-bar">
        <input type="file" id="aiwPhotoInput" accept="image/*" capture="environment" style="display:none" onchange="photoSelected(this)">
        <button class="aiw-photo-btn" onclick="document.getElementById('aiwPhotoInput').click()" title="Uslikaj problem">📷</button>
        <input class="aiw-input" id="aiwInput" placeholder="Pitaj ili uslikaj problem..."
               onkeydown="if(event.key==='Enter'){event.preventDefault();sendWidgetMsg()}">
        <button class="aiw-send" onclick="sendWidgetMsg()"><i class="fas fa-paper-plane"></i></button>
    </div>
```

## Dodaj JS funkcije (ako ne postoje već)

Provjeri postoji li `photoSelected` u fajlu:
```bash
grep -c "photoSelected" /var/www/fina-connect/templates/ai_assistant/chat_widget.html
```

Ako je 0 — dodaj PRIJE `})();` na kraju script bloka:
```javascript
    window.photoSelected = function(input) {
        var file = input.files[0]; if (!file) return;
        var reader = new FileReader();
        reader.onload = function(e) {
            window._aiwPhotoB64 = e.target.result.split(',')[1];
            document.getElementById('aiwPhotoThumb').src = e.target.result;
            document.getElementById('aiwPhotoPreview').style.display = 'block';
        };
        reader.readAsDataURL(file);
    };
    window.clearPhoto = function() {
        window._aiwPhotoB64 = null;
        document.getElementById('aiwPhotoInput').value = '';
        document.getElementById('aiwPhotoPreview').style.display = 'none';
    };
    // Provjeri u sendWidgetMsg - ako ima _aiwPhotoB64, pošalji ga
    var _orig = window.sendWidgetMsg;
    window.sendWidgetMsg = function() {
        if (!window._aiwPhotoB64) { _orig(); return; }
        if(wSending) return; wSending = true;
        var text = inp.value.trim() || 'Imam problem — pogledaj sliku';
        inp.value = '';
        addWMsg('user', '📷 ' + text);
        var b64 = window._aiwPhotoB64;
        window.clearPhoto();
        fetch('/ai/api/chat/', {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRFToken':getCsrf()},
            body:JSON.stringify({message:text, image_b64:b64, conversation_id:wConvId})
        }).then(r=>r.json()).then(function(d){
            wSending=false;
            if(d.conversation_id) wConvId=d.conversation_id;
            addWMsg('assistant', d.response||d.message||'📷 Problem primljen. Tim pregledava.');
        }).catch(function(){ wSending=false; addWMsg('assistant','📷 Slika primljena — tim reagira.'); });
    };
```

## Provjera
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
# Templates ne trebaju restart — samo browser hard refresh (Ctrl+Shift+R)
grep -c "aiwPhotoInput" templates/ai_assistant/chat_widget.html
# Mora biti > 0
```

## Javi
- Broj linija fajla nakon promjene
- Je li `aiwPhotoInput` u HTML-u
