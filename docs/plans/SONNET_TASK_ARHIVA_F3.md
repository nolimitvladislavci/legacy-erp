# SONNET_TASK_ARHIVA_F3 — scan_batch.html UI (2 tipke filozofija)
## Agent: Sonnet | Prioritet: P0 | Danas
## Preduvjet: CC_TASK_ARHIVA_F1 (skeleton template mora postojati)

---

## MISIJA

Napravi `documents/templates/documents/scan_batch.html` —  
Marija uzme mobitel, slika 30 računa s poda, klikne 2 tipke, arhiva popunjena.

**Filozofija:** Manje je više. Svaka faza ima maksimalno 2 primarne akcije.

---

## 3 FAZE UI-a

### FAZA 1 — Prazan (čeka slike)

```
┌─────────────────────────────────────────────────────────┐
│  ← Arhiva        📋 Novi batch skeniranja               │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                                                     │ │
│  │          📷                                         │ │
│  │   Povuci slike ovdje ili klikni                     │ │
│  │   Podržano: JPG, PNG, WebP, HEIC (iPhone)           │ │
│  │   Max 100 slika · Kompresija automatska             │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  [  📷 Snimi kamerom  ]    [  📁 Odaberi fajlove  ]      │
│      (primarno)                 (sekundarno)            │
│                                                          │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░  0 / 100 slika               │
└─────────────────────────────────────────────────────────┘
```

### FAZA 2 — Slike dodane (čeka obradu)

```
┌─────────────────────────────────────────────────────────┐
│  ← Arhiva        📋 Batch #7 · 23 slike                 │
│                                                          │
│  [🖼][🖼][🖼][🖼][🖼]  ← mini grid, 5 po redu             │
│  [🖼][🖼][🖼][🖼][🖼]     badge "2str" za višestranične  │
│  [🖼][🖼][🖼]                                            │
│                                                          │
│  ████████████████████░░░░░░  23 / 100 slika              │
│                                                          │
│  [  ✓ Analiziraj sve (AI)  ]   [  📷 Dodaj još  ]        │
│      (primary, navy)              (secondary)           │
│                                                          │
│  Sporedne: [⚙ Spoji stranice]  [🗑 Očisti sve]           │
└─────────────────────────────────────────────────────────┘
```

### FAZA 3 — AI završio (spreman za arhiviranje)

```
┌─────────────────────────────────────────────────────────┐
│  ← Arhiva        ✅ AI pronašao 18 dokumenata             │
│                                                          │
│  Račun #1 · Kaufland · 23.03.2026 · 142,80 EUR   [✓][✗] │
│  Račun #2 · DM · 22.03.2026 · 28,50 EUR           [✓][✗] │
│  Račun #3 · [?] · 21.03.2026 · 78,00 EUR  ⚠       [✓][✗] │
│    └── ⚠ Nedostaje OIB dobavljača                       │
│  ...                                                     │
│                                                          │
│  [  ✅ Spremi u arhivu (18)  ]  [  ↩ Pregledaj  ]        │
│      (primary, success)          (secondary)            │
└─────────────────────────────────────────────────────────┘
```

---

## HTML TEMPLATE

```html
{% extends 'base.html' %}
{% load i18n static %}

{% block title %}Batch skeniranje — LIMIT Connect{% endblock %}
{% block page_title %}Skeniranje računa{% endblock %}

{% block content %}
<div class="scan-batch-app" id="scanApp"
     data-batch-id="{{ batch.pk }}"
     data-upload-url="{% url 'documents:scan_batch_upload' batch.pk %}"
     data-process-url="{% url 'documents:scan_batch_process' batch.pk %}"
     data-status-url="{% url 'documents:scan_batch_status' batch.pk %}"
     data-archive-url="{% url 'documents:scan_batch_archive' batch.pk %}"
     data-csrf="{{ csrf_token }}">

  <!-- ── HEADER ─────────────────────────────────── -->
  <div class="sb-header">
    <a href="{% url 'documents:arhiva_list' %}" class="sb-back">
      ← Arhiva
    </a>
    <div class="sb-title" id="sb-title">
      {% if batch.total_images > 0 %}
        Batch #{{ batch.pk }} · {{ batch.total_images }} slik{{ batch.total_images|pluralize:"a,e" }}
      {% else %}
        Novi batch skeniranja
      {% endif %}
    </div>
    <div class="sb-status-badge" id="sb-status-badge">
      {% if batch.status == 'collecting' %}⏳ Prikupljanje
      {% elif batch.status == 'processing' %}🔄 AI analizira
      {% elif batch.status == 'grouping' %}🧩 Grupiranje
      {% elif batch.status == 'ready' %}✅ Spreman
      {% elif batch.status == 'done' %}✓ Arhivirano
      {% endif %}
    </div>
  </div>

  <!-- ── PROGRESS BAR ───────────────────────────── -->
  <div class="sb-progress-wrap">
    <div class="sb-progress-bar" id="sb-progress-bar"
         style="width: {{ batch.total_images }}%"></div>
  </div>
  <div class="sb-progress-text" id="sb-progress-text">
    <span id="img-count">{{ batch.total_images }}</span> / 100 slika
  </div>

  <!-- ══ FAZA 1: UPLOAD ZONA (prazno) ══════════════ -->
  <div class="sb-phase" id="phase-upload"
       {% if batch.total_images > 0 %}style="display:none"{% endif %}>

    <div class="sb-dropzone" id="dropzone">
      <div class="sb-drop-icon">📷</div>
      <div class="sb-drop-title">Povuci račune ovdje</div>
      <div class="sb-drop-sub">ili koristi tipke ispod</div>
      <div class="sb-drop-hint">JPG · PNG · WebP · HEIC (iPhone) · max 100 slika</div>
    </div>

    <div class="sb-actions">
      <label class="sb-btn sb-btn-primary" for="camera-input">
        📷 Snimi kamerom
        <input type="file" id="camera-input" accept="image/*" capture="environment" multiple style="display:none">
      </label>
      <label class="sb-btn sb-btn-secondary" for="file-input">
        📁 Odaberi fajlove
        <input type="file" id="file-input" accept="image/*,.heic,.heif" multiple style="display:none">
      </label>
    </div>
  </div>

  <!-- ══ FAZA 2: PREGLED SLIKA ═════════════════════ -->
  <div class="sb-phase" id="phase-preview"
       {% if batch.total_images == 0 or batch.status not in 'collecting' %}style="display:none"{% endif %}>

    <div class="sb-grid" id="sb-grid">
      {% for img in images %}
      <div class="sb-thumb" data-id="{{ img.pk }}">
        <img src="{% url 'documents:arhiva_thumbnail' img.pk %}"
             onerror="this.src='{% static 'img/doc-placeholder.svg' %}'"
             alt="Slika {{ img.order }}">
        {% if img.document_group and img.page_in_group > 1 %}
        <span class="sb-badge-page">{{ img.page_in_group }}str</span>
        {% endif %}
        <button class="sb-thumb-del" data-id="{{ img.pk }}">✕</button>
      </div>
      {% empty %}
      <div class="sb-empty-grid">Nema slika još...</div>
      {% endfor %}
    </div>

    <div class="sb-actions">
      <button class="sb-btn sb-btn-primary" id="btn-process">
        ✓ Analiziraj sve (AI)
      </button>
      <label class="sb-btn sb-btn-secondary" for="file-input-more">
        📷 Dodaj još
        <input type="file" id="file-input-more" accept="image/*" multiple style="display:none">
      </label>
    </div>

    <div class="sb-actions sb-actions-secondary">
      <button class="sb-btn sb-btn-ghost" id="btn-clear">🗑 Očisti sve</button>
    </div>
  </div>

  <!-- ══ FAZA 3: AI PROCESSING (spinner) ═══════════ -->
  <div class="sb-phase" id="phase-processing"
       {% if batch.status not in 'processing,grouping' %}style="display:none"{% endif %}>

    <div class="sb-processing-anim">
      <div class="sb-spinner"></div>
      <div class="sb-processing-title">AI analizira račune...</div>
      <div class="sb-processing-sub" id="processing-msg">
        {{ batch.error_message|default:"Priprema..." }}
      </div>
    </div>

    <div class="sb-processing-grid" id="processing-grid">
      {% for img in images %}
      <div class="sb-proc-item" id="proc-{{ img.pk }}">
        <div class="sb-proc-spinner">⏳</div>
        <div class="sb-proc-name">{{ img.original_filename|default:img.pk }}</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- ══ FAZA 4: REZULTATI (spreman za arhiviranje) ═ -->
  <div class="sb-phase" id="phase-results"
       {% if batch.status != 'ready' %}style="display:none"{% endif %}>

    <div class="sb-results-summary">
      ✅ AI pronašao <strong id="doc-count">{{ batch.total_documents }}</strong> 
      dokumenata iz {{ batch.total_images }} slika
    </div>

    <div class="sb-results-list" id="results-list">
      {% regroup images by document_group as groups %}
      {% for group in groups %}
      {% with first=group.list.0 %}
      <div class="sb-result-item" data-group="{{ group.grouper }}">
        <div class="sb-result-icon">
          {% if group.list|length > 1 %}📄📄{% else %}📄{% endif %}
        </div>
        <div class="sb-result-info">
          <div class="sb-result-vendor">
            {{ first.extracted_data.seller.name|default:"Nepoznat dobavljač" }}
          </div>
          <div class="sb-result-meta">
            {{ first.extracted_data.issue_date|default:"?" }} ·
            {{ first.extracted_data.total|default:"??" }} {{ first.extracted_data.currency|default:"EUR" }}
            {% if group.list|length > 1 %}
            · <span class="sb-pages">{{ group.list|length }} stranice</span>
            {% endif %}
          </div>
          {% if not first.extracted_data.seller.oib %}
          <div class="sb-result-warning">⚠ Nedostaje OIB dobavljača</div>
          {% endif %}
        </div>
        <div class="sb-result-actions">
          <button class="sb-check active" title="Uključi">✓</button>
          <button class="sb-exclude" title="Isključi">✗</button>
        </div>
      </div>
      {% endwith %}
      {% endfor %}
    </div>

    <div class="sb-actions">
      <button class="sb-btn sb-btn-success" id="btn-archive">
        ✅ Spremi u arhivu (<span id="archive-count">{{ batch.total_documents }}</span>)
      </button>
      <button class="sb-btn sb-btn-secondary" id="btn-review">
        ↩ Pregledaj
      </button>
    </div>
  </div>

  <!-- ══ FAZA 5: GOTOVO ════════════════════════════ -->
  <div class="sb-phase" id="phase-done"
       {% if batch.status != 'done' %}style="display:none"{% endif %}>
    <div class="sb-done">
      <div class="sb-done-icon">✅</div>
      <div class="sb-done-title">Arhivirano!</div>
      <div class="sb-done-sub">
        {{ batch.total_documents }} dokumenata spremljeno u arhivu.
      </div>
      <a href="{% url 'documents:arhiva_list' %}" class="sb-btn sb-btn-primary">
        → Otvori arhivu
      </a>
    </div>
  </div>

</div>
{% endblock %}

{% block extra_js %}
<script>
/* ══ SCAN BATCH APP ══════════════════════════════════════════════ */
(function() {
  const app    = document.getElementById('scanApp');
  const BATCH  = app.dataset.batchId;
  const URLS   = {
    upload:  app.dataset.uploadUrl,
    process: app.dataset.processUrl,
    status:  app.dataset.statusUrl,
    archive: app.dataset.archiveUrl,
  };
  const CSRF   = app.dataset.csrf;
  let pollTimer = null;

  /* ── HELPERS ─────────────────────────────────────────────── */
  function showPhase(name) {
    document.querySelectorAll('.sb-phase').forEach(p => p.style.display = 'none');
    const el = document.getElementById('phase-' + name);
    if (el) el.style.display = '';
  }

  function updateProgress(count) {
    document.getElementById('img-count').textContent = count;
    document.getElementById('sb-progress-bar').style.width = Math.min(count, 100) + '%';
    document.getElementById('sb-title').textContent =
      count > 0 ? `Batch #${BATCH} · ${count} slik${count === 1 ? 'a' : 'e'}` : 'Novi batch skeniranja';
  }

  /* ── CLIENT-SIDE KOMPRESIJA ──────────────────────────────── */
  async function compressImage(file, maxPx = 1200, quality = 0.8) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        let w = img.width, h = img.height;
        if (w > maxPx || h > maxPx) {
          const ratio = Math.min(maxPx/w, maxPx/h);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        canvas.toBlob(blob => blob ? resolve(blob) : reject('compress failed'), 'image/webp', quality);
      };
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  }

  /* ── UPLOAD ──────────────────────────────────────────────── */
  async function uploadFiles(files) {
    if (!files.length) return;

    const fd = new FormData();
    let count = 0;

    for (const file of files) {
      try {
        const blob = await compressImage(file);
        fd.append('images', blob, file.name.replace(/\.\w+$/, '.webp'));
        count++;
      } catch(e) {
        // Fallback: pošalji original
        fd.append('images', file);
        count++;
      }
    }

    fd.append('csrfmiddlewaretoken', CSRF);

    const res = await fetch(URLS.upload, { method: 'POST', body: fd });
    const data = await res.json();

    if (data.ok) {
      updateProgress(data.total_images);
      showPhase('preview');
      // Refresh grid
      window.location.reload();
    } else {
      alert(data.error || 'Upload nije uspio');
    }
  }

  /* ── EVENT LISTENERS ─────────────────────────────────────── */
  ['camera-input', 'file-input', 'file-input-more'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', e => uploadFiles([...e.target.files]));
  });

  // Drag & drop
  const dropzone = document.getElementById('dropzone');
  if (dropzone) {
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      uploadFiles([...e.dataTransfer.files]);
    });
  }

  // Process button
  const btnProcess = document.getElementById('btn-process');
  if (btnProcess) {
    btnProcess.addEventListener('click', async () => {
      btnProcess.disabled = true;
      btnProcess.textContent = '🔄 Pokrećem AI...';

      const fd = new FormData();
      fd.append('csrfmiddlewaretoken', CSRF);
      const res = await fetch(URLS.process, { method: 'POST', body: fd });
      const data = await res.json();

      if (data.ok) {
        showPhase('processing');
        startPolling();
      } else {
        alert(data.error || 'Greška');
        btnProcess.disabled = false;
        btnProcess.textContent = '✓ Analiziraj sve (AI)';
      }
    });
  }

  // Archive button
  const btnArchive = document.getElementById('btn-archive');
  if (btnArchive) {
    btnArchive.addEventListener('click', async () => {
      btnArchive.disabled = true;
      btnArchive.textContent = '⏳ Arhiviranje...';

      const fd = new FormData();
      fd.append('csrfmiddlewaretoken', CSRF);
      const res = await fetch(URLS.archive, { method: 'POST', body: fd });
      const data = await res.json();

      if (data.ok) {
        showPhase('done');
      } else {
        alert(data.error || 'Greška pri arhiviranju');
        btnArchive.disabled = false;
      }
    });
  }

  /* ── POLLING STATUS ──────────────────────────────────────── */
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const res = await fetch(URLS.status);
        const data = await res.json();
        const msg = document.getElementById('processing-msg');
        if (msg) msg.textContent = data.message || '';

        if (data.status === 'ready') {
          clearInterval(pollTimer);
          // Reload da dobijemo svježe template
          window.location.reload();
        } else if (data.status === 'error') {
          clearInterval(pollTimer);
          alert('Greška u obradi: ' + (data.error || ''));
        }
      } catch(e) {
        console.error('Polling error:', e);
      }
    }, 3000); // poll svakih 3 sekunde
  }

  /* ── INIT ────────────────────────────────────────────────── */
  const currentStatus = '{{ batch.status }}';
  if (currentStatus === 'processing' || currentStatus === 'grouping') {
    startPolling();
  }

})();
</script>

<style>
/* ── SCAN BATCH STYLES ────────────────────────────── */
.scan-batch-app { max-width: 680px; margin: 0 auto; padding: 0 12px; }

.sb-header { display:flex; align-items:center; gap:12px; padding:12px 0 16px; border-bottom:1px solid #e2e8f0; margin-bottom:16px; }
.sb-back { color:#64748b; text-decoration:none; font-size:.9rem; }
.sb-title { flex:1; font-weight:700; color:#1e3a5f; font-size:1rem; }
.sb-status-badge { font-size:.75rem; background:#f1f5f9; padding:3px 8px; border-radius:20px; color:#475569; }

.sb-progress-wrap { height:6px; background:#e2e8f0; border-radius:3px; margin-bottom:6px; }
.sb-progress-bar { height:100%; background:#1e3a5f; border-radius:3px; transition:width .3s; }
.sb-progress-text { text-align:right; font-size:.75rem; color:#94a3b8; margin-bottom:20px; }

/* Drop zone */
.sb-dropzone { border:2px dashed #c9a84c; border-radius:12px; padding:40px 20px; text-align:center; background:#fffbeb; cursor:pointer; transition:all .2s; margin-bottom:20px; }
.sb-dropzone.dragover { background:#fef3c7; border-color:#1e3a5f; }
.sb-drop-icon { font-size:2.5rem; margin-bottom:8px; }
.sb-drop-title { font-size:1.1rem; font-weight:600; color:#1e3a5f; }
.sb-drop-sub { color:#64748b; margin:4px 0; }
.sb-drop-hint { font-size:.75rem; color:#94a3b8; margin-top:8px; }

/* Actions */
.sb-actions { display:flex; gap:12px; margin-bottom:12px; }
.sb-actions-secondary { justify-content:center; }
.sb-btn { padding:12px 20px; border-radius:8px; font-weight:600; font-size:.9rem; cursor:pointer; border:none; display:inline-flex; align-items:center; gap:6px; justify-content:center; flex:1; transition:all .2s; text-decoration:none; }
.sb-btn-primary { background:#1e3a5f; color:white; }
.sb-btn-primary:hover { background:#162d4a; }
.sb-btn-secondary { background:#f1f5f9; color:#475569; }
.sb-btn-success { background:#22c55e; color:white; }
.sb-btn-ghost { background:transparent; color:#94a3b8; font-size:.85rem; flex:0; }
.sb-btn:disabled { opacity:.5; cursor:not-allowed; }

/* Grid */
.sb-grid { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }
.sb-thumb { width:60px; height:60px; position:relative; border-radius:6px; overflow:hidden; background:#f1f5f9; }
.sb-thumb img { width:100%; height:100%; object-fit:cover; }
.sb-badge-page { position:absolute; bottom:2px; right:2px; background:rgba(30,58,95,.85); color:white; font-size:9px; padding:1px 4px; border-radius:3px; }
.sb-thumb-del { position:absolute; top:2px; right:2px; background:rgba(239,68,68,.85); color:white; border:none; width:16px; height:16px; border-radius:50%; font-size:9px; cursor:pointer; display:none; line-height:1; padding:0; }
.sb-thumb:hover .sb-thumb-del { display:flex; align-items:center; justify-content:center; }

/* Processing */
.sb-processing-anim { text-align:center; padding:30px 0; }
.sb-spinner { width:48px; height:48px; border:4px solid #e2e8f0; border-top-color:#1e3a5f; border-radius:50%; animation:spin 1s linear infinite; margin:0 auto 16px; }
@keyframes spin { to { transform:rotate(360deg) } }
.sb-processing-title { font-size:1.1rem; font-weight:700; color:#1e3a5f; }
.sb-processing-sub { color:#64748b; font-size:.9rem; margin-top:6px; }

/* Results */
.sb-results-summary { background:#f0fdf4; border:1px solid #86efac; border-radius:8px; padding:10px 14px; margin-bottom:14px; font-size:.9rem; color:#166534; }
.sb-result-item { display:flex; align-items:flex-start; gap:10px; padding:10px 0; border-bottom:1px solid #f1f5f9; }
.sb-result-icon { font-size:1.2rem; width:32px; text-align:center; flex-shrink:0; }
.sb-result-info { flex:1; min-width:0; }
.sb-result-vendor { font-weight:600; color:#0f172a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sb-result-meta { font-size:.8rem; color:#64748b; margin-top:2px; }
.sb-result-warning { font-size:.75rem; color:#dc2626; margin-top:2px; }
.sb-result-actions { display:flex; gap:6px; }
.sb-check, .sb-exclude { width:28px; height:28px; border-radius:50%; border:2px solid; font-size:.8rem; cursor:pointer; background:transparent; display:flex; align-items:center; justify-content:center; }
.sb-check { border-color:#22c55e; color:#22c55e; }
.sb-check.active { background:#22c55e; color:white; }
.sb-exclude { border-color:#e2e8f0; color:#94a3b8; }

/* Done */
.sb-done { text-align:center; padding:40px 20px; }
.sb-done-icon { font-size:3rem; margin-bottom:12px; }
.sb-done-title { font-size:1.4rem; font-weight:700; color:#1e3a5f; }
.sb-done-sub { color:#64748b; margin:8px 0 20px; }

@media (max-width: 480px) {
  .sb-actions { flex-direction: column; }
  .sb-btn { flex:none; }
}
</style>
{% endblock %}
```

---

## DONE kriterij

```
1. curl https://limit-connect.com/hr/documents/scan/batch/new/ → redirect na /scan/batch/1/
2. Template se renderira bez grešaka
3. Upload jedne slike → success JSON
4. Na mobitelu: kamera gumb otvara kameru direktno
```
