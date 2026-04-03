# CC_TASK: UI Revolution 10/10 — Globalni Design System
**Datum:** 03.04.2026. | **Rok:** 07.04.2026. (4 dana)
**Vođa:** Sonnet | **Izvršava:** CC Code
**Cilj:** Svjetska klasa UI — 3 teme, AI sufljer, kamera na svakoj formi

---

## FILOZOFIJA — TESLA 3

```
TAMNO   = Noć, fokus, produkcija, moć        (trenutno = poboljšati)
SVIJETLO = Dan, klijent, preglednost, čistoća (trenutno = poboljšati)
DOKUMENT = Papir, ispis, bilježnik, službenost (NOVO — treća dimenzija)
```

Broj 3 nije slučajan:
- 3 teme = 3 tipa korisnika (računovođa noću / klijent danju / bilježnik koji tiska)
- 3 AI modela (Haiku suflira / Sonnet koordinira / Gemini gradi)
- 3 portala (LIMIT Connect / sati / AION)

---

## OBVEZNO PRIJE PISANJA KODA

```bash
# Provjeri postojeće CSS varijable
cat static/css/global_themes.css
cat static/css/fenix-ui.css | head -50
grep -n "data-theme\|theme-toggle\|toggleTheme" templates/base.html
grep -n "FenixScan\|fenix-smart-fab\|fenix-fab" templates/base.html
grep -n "AI\|ai-cockpit\|sufljer\|sufler\|cockpit" templates/base.html | head -20
wc -l static/js/fenix-scan.js
```

---

## SPRINT 1 — TREĆA TEMA: DOKUMENT (DAN 1)
**Fajl:** `static/css/global_themes.css` — dodati na kraj

### 1.1 CSS varijable za "Dokument" temu

```css
/* ═══════════════════════════════════════════════════════
   TEMA 3: DOKUMENT — Izgled ispisa, bilježnički papir
   Aktivira se: html[data-theme="dokument"]
   Filozofija: kao da gledaš A4 stranicu s tintom
   ═══════════════════════════════════════════════════════ */
html[data-theme="dokument"] {
    /* Papir i tinta */
    --gold: #1a1a2e;          /* Akcent = tamna tinta, ne zlato */
    --gold2: #2d2d44;
    --gold-dim: rgba(26,26,46,0.08);
    --gold-border: rgba(26,26,46,0.2);

    /* Podloge — kremasti papir */
    --black: #faf8f4;         /* Pozadina stranice = off-white papir */
    --dark: #f5f2ec;          /* Topla krema */
    --surface: #ffffff;       /* Čista bijela za kartice */
    --surface2: #f9f7f3;
    --surface3: #f0ede5;

    /* Rubovi — suptilni grafitni */
    --border: #d4cfc6;
    --border-light: rgba(0,0,0,0.07);

    /* Tekst — tinta na papiru */
    --text: #1a1209;          /* Gotovo crno, toplo */
    --text-dim: #4a3f32;
    --muted: #8c7b6b;
    --muted2: #b8a898;
    --border2: #c8c2b8;
    --surface-deep: #ece8e0;
    --text-muted3: #9e8e7e;

    /* Statusne boje — prigušene, kao tiskano */
    --green: #2d6a4f;
    --red: #9b2335;
    --amber: #b5860d;
    --blue: #1a3f6f;

    /* Tipografija — serif za dokument osjećaj */
    --font-heading: 'Cormorant Garamond', 'Georgia', serif;
    --font-body: 'Barlow', 'Georgia', serif;

    /* Specifično za dokument */
    --doc-line: rgba(26,26,46,0.12);     /* Linije između redova */
    --doc-stamp: rgba(155,35,53,0.15);   /* Pečat boja */
    --doc-watermark: rgba(26,26,46,0.03);/* Watermark */
    --shadow: 0 2px 12px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08);
    --radius: 4px;            /* Manji radius = dokumentarni osjećaj */
}

/* Dokument tema — specifični overrideovi */
html[data-theme="dokument"] .f-card {
    border: 1px solid var(--doc-line);
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
html[data-theme="dokument"] .f-card:hover {
    border-color: var(--gold);
    transform: none;   /* Dokumenti se ne dižu */
}
html[data-theme="dokument"] .f-heading,
html[data-theme="dokument"] .f-gold {
    color: var(--gold);
    font-family: var(--font-heading);
}
html[data-theme="dokument"] table th {
    border-bottom: 2px solid var(--gold);
    font-family: var(--font-heading);
    letter-spacing: 0.03em;
}
html[data-theme="dokument"] .sidebar {
    background: var(--surface3);
    border-right: 1px solid var(--border);
}
/* Redovi tablice — linije poput papira s linijama */
html[data-theme="dokument"] table tr {
    border-bottom: 1px solid var(--doc-line);
}
/* Topbar u dokument temi — bijeli sa sjenom */
html[data-theme="dokument"] .topbar,
html[data-theme="dokument"] nav {
    background: var(--surface);
    border-bottom: 2px solid var(--gold);
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}
/* Forme u dokument temi — klasični izgled */
html[data-theme="dokument"] input,
html[data-theme="dokument"] select,
html[data-theme="dokument"] textarea {
    background: var(--surface);
    border: 1px solid var(--border);
    border-bottom: 2px solid var(--doc-line);
    border-radius: 2px;
    font-family: var(--font-body);
}
html[data-theme="dokument"] input:focus,
html[data-theme="dokument"] select:focus,
html[data-theme="dokument"] textarea:focus {
    border-bottom: 2px solid var(--gold);
    outline: none;
    box-shadow: 0 2px 0 var(--gold);
}
/* Print u dokument temi — već gotovo za tisak */
html[data-theme="dokument"] .no-print { display: none !important; }
```

---

## SPRINT 2 — THEME SWITCHER 3-WAY (DAN 1)
**Fajl:** `templates/base.html` — zamijeni postojeći theme-toggle

### 2.1 HTML — zamijeniti stari `theme-toggle` button s ovim:

```html
<!-- NOVA 3-WAY TEMA SKLOPKA — zamjenjuje stari theme-toggle button -->
<div id="theme-switcher" style="display:flex;align-items:center;gap:2px;
     background:var(--surface2);border:1px solid var(--border);
     border-radius:20px;padding:3px;transition:all .3s">
    <button class="theme-btn" data-theme="dark" title="Tamna tema"
        onclick="setTheme('dark')"
        style="border:none;background:none;cursor:pointer;padding:4px 8px;
               border-radius:16px;color:var(--text-dim);font-size:.8rem;
               transition:all .2s;display:flex;align-items:center;gap:4px">
        <i class="fas fa-moon"></i>
    </button>
    <button class="theme-btn" data-theme="light" title="Svijetla tema"
        onclick="setTheme('light')"
        style="border:none;background:none;cursor:pointer;padding:4px 8px;
               border-radius:16px;color:var(--text-dim);font-size:.8rem;
               transition:all .2s;display:flex;align-items:center;gap:4px">
        <i class="fas fa-sun"></i>
    </button>
    <button class="theme-btn" data-theme="dokument" title="Dokument tema (ispis)"
        onclick="setTheme('dokument')"
        style="border:none;background:none;cursor:pointer;padding:4px 8px;
               border-radius:16px;color:var(--text-dim);font-size:.8rem;
               transition:all .2s;display:flex;align-items:center;gap:4px">
        <i class="fas fa-file-alt"></i>
    </button>
</div>
```

### 2.2 JS — zamijeniti `toggleTheme()` s novim `setTheme()`:

```javascript
// Zamijeni stari toggleTheme() u base.html
function setTheme(theme) {
    // theme = 'dark' | 'light' | 'dokument'
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('fina-theme', theme);
    
    // Highlight aktivan gumb
    document.querySelectorAll('.theme-btn').forEach(function(btn) {
        var isActive = btn.getAttribute('data-theme') === theme;
        btn.style.background = isActive ? 'var(--gold-dim)' : 'none';
        btn.style.color = isActive ? 'var(--gold)' : 'var(--text-dim)';
        btn.style.fontWeight = isActive ? '700' : 'normal';
    });
    
    // FAB boja po temi
    var fab = document.getElementById('fenix-smart-fab');
    if (fab) {
        if (theme === 'dokument') {
            fab.style.background = 'linear-gradient(135deg,#f5f2ec,#ffffff)';
            fab.style.color = '#1a1a2e';
            fab.style.border = '1px solid #d4cfc6';
        }
    }
    
    // AI Sufljer ažuriraj boju
    if (window.FenixAI) window.FenixAI.updateTheme(theme);
}

// Init — čitaj temu iz localStorage (3 opcije)
(function() {
    var saved = localStorage.getItem('fina-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    // Highlight aktivan gumb (kad DOM bude spreman)
    document.addEventListener('DOMContentLoaded', function() {
        setTheme(saved);
    });
})();
```

---

## SPRINT 3 — KAMERA NA SVAKOJ FORMI (DAN 2)
**Fajl:** `static/js/fenix-form-camera.js` (NOVI FAJL)

### 3.1 Filozofija

Svaki `<input>` i `<textarea>` koji ima `data-scan` atribut dobiva
kameru ikonu desno. Klik → otvara kameru → AI čita → popunjava polje.

```javascript
// static/js/fenix-form-camera.js
// FenixFormCamera v1 — kamera na svakom polju forme

(function() {
    'use strict';
    
    window.FenixFormCamera = {
        
        // Koja polja auto-dobivaju kameru (po name/id/type)
        AUTO_SCAN_FIELDS: [
            'oib', 'iban', 'mbs', 'zip', 'postanski',
            'partner_oib', 'vlasnik_oib', 'duznik_oib',
            'adresa', 'naziv', 'ime', 'prezime',
            'broj_racuna', 'iznos', 'datum'
        ],
        
        init: function() {
            // 1. Polja s data-scan atributom — uvijek
            document.querySelectorAll('[data-scan]').forEach(function(field) {
                FenixFormCamera.attachCamera(field, field.dataset.scan);
            });
            
            // 2. Auto-detect po imenu polja
            document.querySelectorAll('input, textarea').forEach(function(field) {
                var name = (field.name || field.id || '').toLowerCase();
                FenixFormCamera.AUTO_SCAN_FIELDS.forEach(function(keyword) {
                    if (name.includes(keyword) && !field.dataset.cameraAttached) {
                        FenixFormCamera.attachCamera(field, 'auto');
                    }
                });
            });
        },
        
        attachCamera: function(field, docType) {
            if (field.dataset.cameraAttached) return;
            field.dataset.cameraAttached = '1';
            
            // Wrapper
            var parent = field.parentNode;
            var wrapper = document.createElement('div');
            wrapper.style.cssText = 'position:relative;display:flex;align-items:center;';
            parent.insertBefore(wrapper, field);
            wrapper.appendChild(field);
            field.style.paddingRight = '36px';
            
            // Kamera gumb
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.title = 'Skeniraj kamerom';
            btn.innerHTML = '<i class="fas fa-camera"></i>';
            btn.style.cssText = [
                'position:absolute;right:6px;top:50%;transform:translateY(-50%);',
                'background:none;border:none;cursor:pointer;',
                'color:var(--text-dim);font-size:.85rem;',
                'padding:4px;border-radius:4px;',
                'transition:color .2s, opacity .2s;opacity:.6;',
                'z-index:10;'
            ].join('');
            btn.onmouseenter = function() { this.style.opacity = '1'; this.style.color = 'var(--gold)'; };
            btn.onmouseleave = function() { this.style.opacity = '.6'; this.style.color = 'var(--text-dim)'; };
            wrapper.appendChild(btn);
            
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                FenixFormCamera.openCamera(field, docType || 'general');
            });
        },
        
        openCamera: function(targetField, docType) {
            // Reuse FenixScan ako postoji
            if (window.FenixScan && window.FenixScan.openForField) {
                window.FenixScan.openForField(targetField, docType);
                return;
            }
            
            // Fallback — file input
            var input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.capture = 'environment';
            input.onchange = function() {
                if (!this.files[0]) return;
                FenixFormCamera.processImage(this.files[0], targetField, docType);
            };
            input.click();
        },
        
        processImage: function(file, targetField, docType) {
            // Pokazi loading stanje na polju
            targetField.classList.add('scanning');
            targetField.placeholder = '⏳ AI čita...';
            
            var formData = new FormData();
            formData.append('images', file);
            formData.append('doc_type', docType);
            formData.append('target_field', targetField.name || targetField.id);
            
            // CSRF
            var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
            
            fetch('/api/fenix/scan/', {
                method: 'POST',
                headers: csrf ? {'X-CSRFToken': csrf.value} : {},
                body: formData
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                targetField.classList.remove('scanning');
                targetField.placeholder = '';
                
                if (data.extracted) {
                    // Pokušaj mapirati ekstrakciju na ciljno polje
                    var fieldName = (targetField.name || targetField.id || '').toLowerCase();
                    var value = data.extracted[fieldName] 
                             || data.extracted.oib 
                             || data.extracted.raw_text 
                             || '';
                    
                    if (value) {
                        targetField.value = value;
                        targetField.dispatchEvent(new Event('change', {bubbles: true}));
                        // Flash zeleno
                        targetField.style.borderColor = 'var(--green)';
                        setTimeout(function() { targetField.style.borderColor = ''; }, 2000);
                        // AI Sufljer — obavijesti
                        if (window.FenixAI) {
                            window.FenixAI.notify('Polje popunjeno: ' + value);
                        }
                    }
                }
            })
            .catch(function() {
                targetField.classList.remove('scanning');
                targetField.placeholder = '';
            });
        }
    };
    
    // Auto-init kad DOM bude spreman
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            FenixFormCamera.init();
        });
    } else {
        FenixFormCamera.init();
    }
    
})();
```

### 3.2 Dodati u `templates/base.html` — NAKON fenix-scan.js:

```html
<script src="/static/js/fenix-form-camera.js"></script>
```

### 3.3 CSS za scanning stanje — dodati u `fenix-ui.css`:

```css
/* Polje koje se skenira */
input.scanning, textarea.scanning {
    animation: scanPulse 0.8s ease-in-out infinite;
    border-color: var(--blue) !important;
}
@keyframes scanPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
```

---

## SPRINT 4 — AI SUFLJER (DAN 2-3)
**Fajl:** `static/js/fenix-ai-sufler.js` (NOVI FAJL)
**URL:** `/api/fenix/ai-hint/` (NOVI endpoint)

### 4.1 Što AI Sufljer radi:
- Prati aktivnu stranicu (URL + formu)
- Svake 30 sekundi (ili na promjenu forme) pita Haiku za kontekstualni savjet
- Prikazuje hint kao mali floating panel (ne popup, ne modal)
- Korisnik može zatvoriti ili prihvatiti sugestiju
- "Prihvati" → popunjava formu / otvara link / izvršava akciju

### 4.2 Backend endpoint:

```python
# core/views_ai.py — dodati ovu view

@login_required
@require_POST
def ai_hint(request):
    """
    POST /api/fenix/ai-hint/
    Body: {
        "page_url": "/hr/invoicing/123/",
        "page_title": "Faktura INV-2026-123",
        "form_fields": ["partner", "iznos", "datum_valute"],
        "form_values": {"partner": "Kruljac Ivica", "iznos": ""},
        "context": {...}
    }
    Response: {
        "hint": "Iznos nije unesen. Zadnji račun Kruljac Ivici bio je 1.250,00 EUR.",
        "action": {"label": "Kopiraj iznos", "type": "fill_field", 
                   "field": "iznos", "value": "1250.00"},
        "confidence": 0.85
    }
    """
    import json
    from django.http import JsonResponse
    
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'hint': '', 'action': None}, status=200)
    
    page_url = data.get('page_url', '')
    form_fields = data.get('form_fields', [])
    form_values = data.get('form_values', {})
    
    # Kontekst iz baze — zadnje transakcije, otvorene fakture, itd.
    # PROVJERI: koje modele imaš za partnera/fakturu
    context_info = []
    
    partner_name = form_values.get('partner', '') or form_values.get('klijent', '')
    if partner_name:
        # Zadnji iznos tog partnera
        from invoicing.models import Invoice  # PROVJERI model name
        try:
            last_inv = Invoice.objects.filter(
                company=request.user.profile.company,
                buyer_name__icontains=partner_name
            ).order_by('-date').first()
            if last_inv:
                context_info.append(
                    f"Zadnji račun za '{partner_name}': "
                    f"{last_inv.total} EUR, datum {last_inv.date}"
                )
        except Exception:
            pass
    
    # Haiku prompt
    import anthropic
    from django.conf import settings
    
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    system = """Ti si AI asistent unutar LIMIT Connect ERP sustava.
Korisnik radi na formi. Daj JEDAN konkretan, kratak savjet (max 2 rečenice).
Ako možeš predložiti konkretnu akciju (popuni polje, otvori stranicu), predloži je.
Odgovori SAMO u JSON formatu:
{"hint": "...", "action": {"label": "...", "type": "fill_field|open_url|none", 
 "field": "...", "value": "..."} | null, "confidence": 0.0-1.0}
Jezik: hrvatski. Ton: konkretan, kolegijalan. Bez uvoda."""
    
    user_msg = f"""Stranica: {page_url}
Polja forme: {', '.join(form_fields)}
Popunjeno: {json.dumps(form_values, ensure_ascii=False)}
Kontekst iz baze: {'; '.join(context_info) if context_info else 'nema'}
Što savjetuješ?"""
    
    try:
        resp = client.messages.create(
            model=settings.HAIKU_MODEL,
            max_tokens=200,
            system=system,
            messages=[{'role': 'user', 'content': user_msg}]
        )
        result = json.loads(resp.content[0].text)
    except Exception:
        result = {'hint': '', 'action': None, 'confidence': 0}
    
    return JsonResponse(result)
```

### 4.3 URL u `core/urls.py`:
```python
path('api/fenix/ai-hint/', views_ai.ai_hint, name='ai_hint'),
```

### 4.4 Frontend — `static/js/fenix-ai-sufler.js`:

```javascript
// FenixAI Sufljer v1 — kontekstualni AI asistent
// Floating panel, ne blokira rad

(function() {
    'use strict';
    
    var HINT_INTERVAL = 45000; // 45 sekundi
    var MIN_CONFIDENCE = 0.6;
    var timer = null;
    var panelEl = null;
    var lastUrl = '';
    var enabled = localStorage.getItem('fenix-ai-sufler') !== 'off';
    
    window.FenixAI = {
        
        notify: function(msg) {
            showHint(msg, null);
        },
        
        updateTheme: function(theme) {
            if (!panelEl) return;
            applyThemeToPanel(theme);
        },
        
        toggle: function() {
            enabled = !enabled;
            localStorage.setItem('fenix-ai-sufler', enabled ? 'on' : 'off');
            if (!enabled && panelEl) hidePanel();
        }
    };
    
    function buildPanel() {
        if (panelEl) return;
        panelEl = document.createElement('div');
        panelEl.id = 'fenix-ai-sufler-panel';
        panelEl.style.cssText = [
            'position:fixed;bottom:160px;right:20px;',
            'max-width:280px;min-width:220px;',
            'background:var(--surface);',
            'border:1px solid var(--border);',
            'border-left:3px solid var(--blue);',
            'border-radius:10px;',
            'padding:12px 14px;',
            'box-shadow:0 4px 20px rgba(0,0,0,0.25);',
            'z-index:9990;',
            'display:none;',
            'font-size:.82rem;',
            'transition:all .3s ease;',
            'animation:slideInRight .3s ease;'
        ].join('');
        panelEl.innerHTML = [
            '<div style="display:flex;justify-content:space-between;',
                'align-items:center;margin-bottom:8px">',
                '<span style="font-weight:700;color:var(--blue);font-size:.78rem;',
                    'letter-spacing:.03em">',
                    '<i class="fas fa-robot" style="margin-right:4px"></i>',
                    'AI SUFLJER</span>',
                '<button onclick="FenixAI.dismiss()" ',
                    'style="background:none;border:none;cursor:pointer;',
                    'color:var(--text-dim);font-size:.9rem;padding:0 2px;',
                    'line-height:1">',
                    '&times;</button>',
            '</div>',
            '<p id="fenix-ai-hint-text" style="margin:0 0 10px;',
                'color:var(--text);line-height:1.5;"></p>',
            '<div id="fenix-ai-action-wrap" style="display:none">',
                '<button id="fenix-ai-action-btn" ',
                    'style="background:var(--blue);color:#fff;border:none;',
                    'border-radius:6px;padding:5px 12px;cursor:pointer;',
                    'font-size:.78rem;font-weight:600;width:100%;',
                    'transition:opacity .2s" ',
                    'onmouseenter="this.style.opacity=\'.85\'" ',
                    'onmouseleave="this.style.opacity=\'1\'">',
                '</button>',
            '</div>',
        ].join('');
        document.body.appendChild(panelEl);
        
        // CSS animacija
        var style = document.createElement('style');
        style.textContent = '@keyframes slideInRight{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}';
        document.head.appendChild(style);
    }
    
    FenixAI.dismiss = function() { hidePanel(); };
    
    function showHint(hintText, action) {
        if (!enabled || !hintText) return;
        buildPanel();
        
        document.getElementById('fenix-ai-hint-text').textContent = hintText;
        
        var actionWrap = document.getElementById('fenix-ai-action-wrap');
        var actionBtn = document.getElementById('fenix-ai-action-btn');
        
        if (action && action.type !== 'none' && action.label) {
            actionWrap.style.display = 'block';
            actionBtn.textContent = action.label;
            actionBtn.onclick = function() {
                executeAction(action);
                hidePanel();
            };
        } else {
            actionWrap.style.display = 'none';
        }
        
        panelEl.style.display = 'block';
        panelEl.style.animation = 'none';
        panelEl.offsetHeight; // reflow
        panelEl.style.animation = 'slideInRight .3s ease';
        
        // Auto-sakrij za 12 sekundi
        clearTimeout(window._fenixAiHideTimer);
        window._fenixAiHideTimer = setTimeout(hidePanel, 12000);
    }
    
    function hidePanel() {
        if (panelEl) panelEl.style.display = 'none';
    }
    
    function executeAction(action) {
        if (action.type === 'fill_field' && action.field && action.value) {
            var field = document.querySelector(
                '[name="' + action.field + '"],[id="' + action.field + '"]'
            );
            if (field) {
                field.value = action.value;
                field.dispatchEvent(new Event('change', {bubbles: true}));
                field.style.borderColor = 'var(--green)';
                setTimeout(function() { field.style.borderColor = ''; }, 2000);
            }
        } else if (action.type === 'open_url' && action.value) {
            window.location.href = action.value;
        }
    }
    
    function applyThemeToPanel(theme) {
        if (!panelEl) return;
        var color = theme === 'dokument' ? '#1a3f6f' : 'var(--blue)';
        panelEl.style.borderLeftColor = color;
        var label = panelEl.querySelector('#fenix-ai-sufler-panel span');
        if (label) label.style.color = color;
    }
    
    function collectFormData() {
        var fields = [];
        var values = {};
        document.querySelectorAll('form input, form select, form textarea').forEach(function(el) {
            if (el.name && el.type !== 'hidden' && el.type !== 'submit' && el.type !== 'password') {
                fields.push(el.name);
                if (el.value) values[el.name] = el.value;
            }
        });
        return {fields: fields, values: values};
    }
    
    function requestHint() {
        if (!enabled) return;
        if (location.pathname === lastUrl) {
            // Ista stranica — provjeri ima li forme
            var fd = collectFormData();
            if (fd.fields.length === 0) return; // Nema forme, nema sufliranja
        }
        lastUrl = location.pathname;
        
        var fd = collectFormData();
        var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrf) return;
        
        fetch('/api/fenix/ai-hint/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf.value
            },
            body: JSON.stringify({
                page_url: location.pathname,
                page_title: document.title,
                form_fields: fd.fields,
                form_values: fd.values,
                context: {
                    theme: document.documentElement.getAttribute('data-theme') || 'dark',
                    viewport: window.innerWidth + 'x' + window.innerHeight
                }
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.hint && data.confidence >= MIN_CONFIDENCE) {
                showHint(data.hint, data.action);
            }
        })
        .catch(function() {}); // Tiho ignoriraj greške
    }
    
    // Pokretanje
    document.addEventListener('DOMContentLoaded', function() {
        buildPanel();
        
        // Hint na promjenu stranice
        setTimeout(requestHint, 3000);
        
        // Ponavljanje
        timer = setInterval(requestHint, HINT_INTERVAL);
        
        // Hint na submit forme — provjera prije slanja
        document.addEventListener('submit', function(e) {
            clearTimeout(window._fenixAiHideTimer);
            hidePanel();
        }, true);
    });
    
})();
```

### 4.5 Dodati u `templates/base.html` — ZADNJE u `<body>`:

```html
<script src="/static/js/fenix-ai-sufler.js"></script>
```

---

## SPRINT 5 — POLISH & DETALJI (DAN 3-4)

### 5.1 Sidebar — tema ikona i glatkoća

```css
/* Dodati u fenix-ui.css */

/* Sidebar glatki tranzicija između tema */
.sidebar, .topbar, .f-card, input, select, textarea, button {
    transition: background-color .3s ease, border-color .3s ease, color .3s ease;
}

/* Dokument tema — sidebar s linijama kao papir */
html[data-theme="dokument"] .sidebar-item:hover {
    background: var(--doc-watermark);
    border-left: 3px solid var(--gold);
}

/* Fokus ring — vidljiv u svim temama */
:focus-visible {
    outline: 2px solid var(--blue);
    outline-offset: 2px;
}
```

### 5.2 Tipografija — Dokument tema

```html
<!-- Dodati u base.html <head> — Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Barlow:wght@400;600;700&display=swap" rel="stylesheet">
```

### 5.3 Print optimizacija (dokument tema)

```css
/* Dodati u fenix-ui.css */
@media print {
    .sidebar, .topbar, .f-fab, #fenix-smart-fab, 
    #fenix-ai-sufler-panel, #theme-switcher,
    .no-print { display: none !important; }
    
    body { background: white !important; color: black !important; }
    .f-card { box-shadow: none !important; border: 1px solid #ccc !important; }
    
    html[data-theme="dokument"] .f-card {
        break-inside: avoid;
    }
}
```

---

## COMMIT FORMAT

```bash
# Sprint 1+2
git add static/css/global_themes.css templates/base.html
git commit -m "feat(ui): tema 3 'Dokument' + 3-way theme switcher (dark/light/dokument)"

# Sprint 3
git add static/js/fenix-form-camera.js static/css/fenix-ui.css
git commit -m "feat(ui): FenixFormCamera — kamera ikona na svakom polju forme, AI auto-fill"

# Sprint 4
git add static/js/fenix-ai-sufler.js core/views_ai.py core/urls.py
git commit -m "feat(ui): AI Sufljer — Haiku u pozadini prati formu i suflira (45s interval)"

# Sprint 5
git add static/css/fenix-ui.css templates/base.html
git commit -m "feat(ui): polish — tranzicije, print, tipografija, fokus ring"
```

---

## DEPLOY REDOSLIJED

```bash
# Nema migracija — sve CSS/JS/template
# 1. CSS teme
# 2. Theme switcher JS
# 3. fenix-form-camera.js
# 4. AI hint endpoint + fenix-ai-sufler.js
# 5. Polish
systemctl restart gunicorn-fina  # samo jednom na kraju
```

---

## REZULTAT — 10/10 CHECKLIST

| Feature | Status |
|---------|--------|
| Tamna tema (poboljšana) | ✅ postojeće + tranzicije |
| Svijetla tema (poboljšana) | ✅ postojeće + tranzicije |
| Dokument tema (NOVO) | ⏳ Sprint 1 |
| 3-way theme switcher | ⏳ Sprint 2 |
| Kamera na FAB (globalna) | ✅ postoji |
| Kamera na svakom polju forme | ⏳ Sprint 3 |
| AI Sufljer u pozadini | ⏳ Sprint 4 |
| AI auto-fill polja iz kamere | ⏳ Sprint 3+4 |
| Print / Dokument optimizacija | ⏳ Sprint 5 |
| Glatke tranzicije tema | ⏳ Sprint 5 |
| Tipografija — Cormorant serif | ⏳ Sprint 5 |

---

## TESLA 3-6-9 ZAVRŠNICA

```
3 = Tri teme (tamno / svjetlo / dokument)
6 = Šest sprintova do kraja (S0→S5)
9 = Devet dana do go-live 15.04.

Svaka tema = jedna misija:
  TAMNO    → Računovođa u 23:00 koji zatvara knjige
  SVIJETLO → Klijent koji gleda ponudu na suncu
  DOKUMENT → Bilježnik koji tiska akt za potpis
```
