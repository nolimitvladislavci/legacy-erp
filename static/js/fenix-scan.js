/**
 * FenixScan v1.0 — Universalni AI Document Scanner
 * ══════════════════════════════════════════════════════════════════
 *
 * Jedan drop-in widget za sve module sustava.
 * Rješava: golub prsten, osobna iskaznica, račun, knjiga prigovora...
 *
 * USAGE:
 * ───────
 * var scanner = FenixScan.create({
 *   container:  '#scan-container',     // CSS selector ili DOM element
 *   docType:    'ring',                // ring|golub|id_card|invoice|complaint|general
 *   maxImages:  4,                     // max slika (default 4)
 *   label:      'Skeniraj prsten',     // naslov sekcije
 *   hint:       'Dodaj više slika...',
 *   fieldMap: {                        // mapiranje AI polja → form elementi
 *     prsten_broj: '#prsten_broj',
 *     godina:      '[name=godina]',
 *   },
 *   onResult: function(fields, confidence, imagesUsed) {},
 *   onError:  function(msg) {},
 *   autoFill: true,                    // automatski popuni fieldMap (default true)
 *   minConfidence: 0.4,               // ispod ovog: warn, ne popunjava
 * });
 *
 * scanner.reset();                     // čisti sve
 * scanner.addImage(file);              // programatski dodaj file
 * scanner.getImages();                 // vraća [b64, ...]
 * scanner.rescan();                    // ponovi analizu
 *
 * ══════════════════════════════════════════════════════════════════
 */
(function(root) {
  'use strict';

  // ─── Konstante ──────────────────────────────────────────────────
  var ENDPOINT    = '/api/fenix/scan/';
  var MAX_PX      = { ring: 1800, id_card: 1800, invoice: 2400, golub: 1800, complaint: 2400, general: 2400 };
  var MAX_IMAGES  = 5;
  var QUALITY     = 0.92;
  var MAX_B64_KB  = 5000;  // KB — povećano za bolju kvalitetu

  // ─── CSRF helper ────────────────────────────────────────────────
  function csrf() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  // ─── Canvas resize → b64 ────────────────────────────────────────
  function resizeFile(file, docType, cb) {
    var maxPx = MAX_PX[docType] || 1400;
    var reader = new FileReader();
    reader.onload = function(e) {
      var img = new Image();
      img.onload = function() {
        var w = img.width, h = img.height;
        if (w > maxPx || h > maxPx) {
          var r = Math.min(maxPx / w, maxPx / h);
          w = Math.round(w * r);
          h = Math.round(h * r);
        }
        var canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);

        // Adaptivna kvaliteta — ako je još uvijek prevelika
        var q = QUALITY;
        var tryBlob = function(quality, attempt) {
          canvas.toBlob(function(blob) {
            var sizeKB = Math.round(blob.size / 1024);
            if (sizeKB > MAX_B64_KB && quality > 0.4 && attempt < 4) {
              tryBlob(quality - 0.12, attempt + 1);
              return;
            }
            var r2 = new FileReader();
            r2.onload = function() {
              var dataUrl = r2.result;
              cb(dataUrl.split(',')[1], dataUrl, sizeKB);
            };
            r2.readAsDataURL(blob);
          }, 'image/jpeg', quality);
        };
        tryBlob(q, 0);
      };
      img.onerror = function() { cb(null, null, 0); };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  // ─── Status helper ───────────────────────────────────────────────
  function statusEl(el, cls, html) {
    el.className = 'fs-status fs-' + cls;
    el.innerHTML = html;
    el.style.display = html ? 'block' : 'none';
  }

  // ─── Confidence bar ──────────────────────────────────────────────
  function confidenceBar(pct) {
    var color = pct >= 0.75 ? '#22c55e' : pct >= 0.45 ? '#f59e0b' : '#ef4444';
    return '<div style="margin-top:6px;height:4px;border-radius:2px;background:rgba(255,255,255,.1);overflow:hidden">' +
      '<div style="height:100%;width:' + Math.round(pct*100) + '%;background:' + color + ';transition:width .5s"></div></div>' +
      '<span style="font-size:.68rem;color:' + color + '">' + Math.round(pct*100) + '% pouzdanost</span>';
  }

  // ─── Core: FenixScan instance ────────────────────────────────────
  function Scanner(opts) {
    this.opts       = opts;
    this.images     = [];   // [{b64, dataUrl, sizeKB, name}]
    this.lastResult = null;
    this._el        = null;
    this._statusEl  = null;
    this._stripEl   = null;
    this._init();
  }

  Scanner.prototype._init = function() {
    var o = this.opts;
    var container = typeof o.container === 'string'
      ? document.querySelector(o.container)
      : o.container;
    if (!container) { console.error('FenixScan: container not found', o.container); return; }

    // Injekcija CSS jednom
    if (!document.getElementById('fenix-scan-css')) {
      var style = document.createElement('style');
      style.id = 'fenix-scan-css';
      style.textContent = [
        '.fs-wrap{font-family:inherit}',
        '.fs-label{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#c9a84c;margin-bottom:.5rem;padding-bottom:.3rem;border-bottom:1px solid rgba(201,168,76,.2)}',
        '.fs-drop{border:2px dashed var(--border,#334155);border-radius:10px;padding:14px 12px;cursor:pointer;transition:all .2s;text-align:center;user-select:none;background:var(--bg-card,#111214)}',
        '.fs-drop:hover,.fs-drop.dragover{border-color:#c9a84c;background:rgba(201,168,76,.05)}',
        '.fs-drop.ring-mode:hover,.fs-drop.ring-mode.dragover{border-color:#3b82f6;background:rgba(59,130,246,.05)}',
        '.fs-drop .fs-icon{font-size:1.4rem;margin-bottom:4px}',
        '.fs-drop .fs-hint{font-size:.75rem;color:var(--text-muted,#6b7280)}',
        '.fs-drop .fs-count{font-size:.7rem;color:var(--text-muted,#6b7280);margin-top:3px}',
        '.fs-strip{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;min-height:0}',
        '.fs-thumb{position:relative;display:inline-block;flex-shrink:0}',
        '.fs-thumb img{width:64px;height:64px;object-fit:cover;border-radius:6px;border:2px solid transparent;transition:border-color .2s;display:block}',
        '.fs-thumb img.primary{border-color:#c9a84c}',
        '.fs-thumb img.ring-primary{border-color:#3b82f6}',
        '.fs-thumb .fs-rm{position:absolute;top:-5px;right:-5px;width:18px;height:18px;border-radius:50%;background:#ef4444;border:none;color:#fff;font-size:.6rem;cursor:pointer;display:flex;align-items:center;justify-content:center;line-height:1}',
        '.fs-thumb .fs-badge{position:absolute;bottom:2px;left:2px;font-size:.55rem;background:rgba(0,0,0,.7);color:#fff;padding:1px 4px;border-radius:3px}',
        '.fs-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}',
        '.fs-btn{display:inline-flex;align-items:center;gap:5px;padding:7px 12px;border-radius:7px;font-size:.78rem;font-weight:600;cursor:pointer;border:1px solid;transition:all .2s}',
        '.fs-btn-add{border-color:rgba(201,168,76,.4);background:rgba(201,168,76,.07);color:#c9a84c}',
        '.fs-btn-add:hover{background:rgba(201,168,76,.15)}',
        '.fs-btn-ring{border-color:rgba(59,130,246,.4);background:rgba(59,130,246,.06);color:#3b82f6}',
        '.fs-btn-ring:hover{background:rgba(59,130,246,.15)}',
        '.fs-btn-scan{border-color:rgba(34,197,94,.4);background:rgba(34,197,94,.06);color:#22c55e}',
        '.fs-btn-scan:hover{background:rgba(34,197,94,.15)}',
        '.fs-btn-reset{border-color:var(--border,#334155);background:transparent;color:var(--text-muted,#6b7280);font-size:.72rem;padding:5px 10px}',
        '.fs-status{font-size:.8rem;padding:9px 12px;border-radius:8px;margin-top:8px;display:none;line-height:1.5}',
        '.fs-loading{display:block!important;background:rgba(59,130,246,.08);color:#3b82f6;border:1px solid rgba(59,130,246,.2)}',
        '.fs-success{display:block!important;background:rgba(34,197,94,.08);color:#22c55e;border:1px solid rgba(34,197,94,.2)}',
        '.fs-warn{display:block!important;background:rgba(245,158,11,.08);color:#f59e0b;border:1px solid rgba(245,158,11,.2)}',
        '.fs-error{display:block!important;background:rgba(239,68,68,.08);color:#ef4444;border:1px solid rgba(239,68,68,.2)}',
        '.fs-result-fields{margin-top:8px;display:none}',
        '.fs-result-fields table{width:100%;border-collapse:collapse;font-size:.78rem}',
        '.fs-result-fields td{padding:4px 6px;border-bottom:1px solid rgba(255,255,255,.05);color:var(--text,#e8e8e8)}',
        '.fs-result-fields td:first-child{color:var(--text-muted,#6b7280);width:38%;font-size:.72rem}',
      ].join('\n');
      document.head.appendChild(style);
    }

    // HTML skeleton
    var docType = o.docType || 'general';
    var isRing  = docType === 'ring';
    var dropClass = isRing ? 'fs-drop ring-mode' : 'fs-drop';
    var icon  = { ring:'💍', golub:'🕊️', id_card:'🪪', invoice:'🧾', complaint:'📖', general:'📄' }[docType] || '📄';
    var label = o.label || { ring:'Fotografije prstena', golub:'Fotografija goluba', id_card:'Dokument (prednja + stražnja)', invoice:'Fotografije računa', complaint:'Stranice dokumenta', general:'Dokumenti' }[docType] || 'Skeniranje';
    var hint  = o.hint  || { ring:'Slikaj prsten s više kutova za bolje očitavanje', golub:'Dodaj fotografiju goluba', id_card:'Prednja i stražnja strana daju bolji rezultat', invoice:'Sve stranice računa', complaint:'Svaka stranica zasebno', general:'Dodaj do 5 fotografija' }[docType] || 'Dodaj fotografije';

    var maxImg = Math.min(o.maxImages || 4, MAX_IMAGES);

    container.innerHTML =
      '<div class="fs-wrap">' +
      (o.showLabel !== false ? '<div class="fs-label">' + icon + ' ' + label + '</div>' : '') +
      '<div class="' + dropClass + '" id="fs-drop-' + this._uid() + '" data-uid="' + this._uid() + '">' +
        '<div class="fs-icon">' + icon + '</div>' +
        '<div class="fs-hint">' + hint + '</div>' +
        '<div class="fs-count" id="fs-count-' + this._uid() + '">Tapni ili povuci fotografije · max ' + maxImg + '</div>' +
      '</div>' +
      '<div class="fs-strip" id="fs-strip-' + this._uid() + '"></div>' +
      '<div class="fs-actions" id="fs-actions-' + this._uid() + '" style="display:none">' +
        '<button type="button" class="fs-btn fs-btn-add" id="fs-add-' + this._uid() + '"><i class="fas fa-plus"></i> Dodaj foto</button>' +
        '<button type="button" class="fs-btn fs-btn-scan" id="fs-scan-' + this._uid() + '"><i class="fas fa-bolt"></i> Analiziraj</button>' +
        '<button type="button" class="fs-btn fs-btn-reset" id="fs-reset-' + this._uid() + '">✕ Reset</button>' +
      '</div>' +
      '<div class="fs-status" id="fs-status-' + this._uid() + '"></div>' +
      '<div class="fs-result-fields" id="fs-result-' + this._uid() + '"></div>' +
      '</div>';

    var uid = this._uid();
    this._dropEl    = document.getElementById('fs-drop-' + uid);
    this._stripEl   = document.getElementById('fs-strip-' + uid);
    this._actionsEl = document.getElementById('fs-actions-' + uid);
    this._statusEl  = document.getElementById('fs-status-' + uid);
    this._resultEl  = document.getElementById('fs-result-' + uid);
    this._countEl   = document.getElementById('fs-count-' + uid);
    this._addBtn    = document.getElementById('fs-add-' + uid);
    this._scanBtn   = document.getElementById('fs-scan-' + uid);
    this._resetBtn  = document.getElementById('fs-reset-' + uid);

    this._maxImages = maxImg;
    this._bindEvents();
  };

  Scanner.prototype._uid = function() {
    if (!this.__uid) this.__uid = 'fs' + Math.random().toString(36).slice(2,7);
    return this.__uid;
  };

  Scanner.prototype._bindEvents = function() {
    var self = this;

    // Drop zone: click → file input
    this._dropEl.addEventListener('click', function() { self._pickFile(); });

    // Drag & drop
    this._dropEl.addEventListener('dragover', function(e) {
      e.preventDefault();
      self._dropEl.classList.add('dragover');
    });
    this._dropEl.addEventListener('dragleave', function() {
      self._dropEl.classList.remove('dragover');
    });
    this._dropEl.addEventListener('drop', function(e) {
      e.preventDefault();
      self._dropEl.classList.remove('dragover');
      var files = Array.from(e.dataTransfer.files).filter(function(f) {
        return f.type.startsWith('image/');
      });
      files.forEach(function(f) { self.addFile(f); });
    });

    // Akcijski gumbi
    this._addBtn.addEventListener('click', function() { self._pickFile(); });
    this._scanBtn.addEventListener('click', function() { self.rescan(); });
    this._resetBtn.addEventListener('click', function() { self.reset(); });
  };

  Scanner.prototype._pickFile = function() {
    if (this.images.length >= this._maxImages) {
      statusEl(this._statusEl, 'warn', '⚠ Maksimum ' + this._maxImages + ' fotografija dostignut. Ukloni neku za dodavanje nove.');
      return;
    }
    var self = this;
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = (this._maxImages > 1);
    // Samsung fallback
    var isSamsung = /SamsungBrowser|SM-/i.test(navigator.userAgent || '');
    if (!isSamsung) input.setAttribute('capture', 'environment');
    input.onchange = function() {
      Array.from(input.files || []).forEach(function(f) {
        self.addFile(f);
      });
    };
    input.click();
  };

  Scanner.prototype.addFile = function(file) {
    if (this.images.length >= this._maxImages) return;
    var self = this;
    statusEl(this._statusEl, 'loading', '<i class="fas fa-spinner fa-spin me-1"></i> Obrađujem sliku...');
    resizeFile(file, this.opts.docType || 'general', function(b64, dataUrl, sizeKB) {
      if (!b64) {
        statusEl(self._statusEl, 'error', '✕ Slika se ne može učitati.');
        return;
      }
      self.images.push({ b64: b64, dataUrl: dataUrl, sizeKB: sizeKB, name: file.name });
      self._renderStrip();
      self._updateCount();
      statusEl(self._statusEl, '', '');

      // Auto-scan ako je prva slika ili uvijek
      if (self.opts.autoScan !== false) {
        self.rescan();
      } else {
        self._actionsEl.style.display = 'flex';
      }
    });
  };

  Scanner.prototype.addImage = function(file) { this.addFile(file); };

  Scanner.prototype._renderStrip = function() {
    var self = this;
    var docType = self.opts.docType || 'general';
    var isRing  = docType === 'ring';
    var primaryClass = isRing ? 'ring-primary' : 'primary';

    this._stripEl.innerHTML = '';
    this.images.forEach(function(img, i) {
      var thumb = document.createElement('div');
      thumb.className = 'fs-thumb';
      thumb.innerHTML =
        '<img src="' + img.dataUrl + '" class="' + (i === 0 ? primaryClass : '') + '" title="' + Math.round(img.sizeKB) + ' KB">' +
        '<button type="button" class="fs-rm" data-idx="' + i + '" title="Ukloni">✕</button>' +
        '<span class="fs-badge">' + (i+1) + '</span>';
      thumb.querySelector('.fs-rm').addEventListener('click', function(e) {
        e.stopPropagation();
        self.images.splice(parseInt(this.dataset.idx), 1);
        self._renderStrip();
        self._updateCount();
        if (self.images.length === 0) {
          self._actionsEl.style.display = 'none';
          self._resultEl.style.display  = 'none';
          statusEl(self._statusEl, '', '');
        } else if (self.opts.autoScan !== false) {
          self.rescan();
        }
      });
      self._stripEl.appendChild(thumb);
    });

    if (this.images.length > 0) {
      this._actionsEl.style.display = 'flex';
    }

    // Sakrij drop zone ako je pun
    this._dropEl.style.display = this.images.length >= this._maxImages ? 'none' : 'block';
    this._addBtn.style.display = this.images.length >= this._maxImages ? 'none' : 'inline-flex';
  };

  Scanner.prototype._updateCount = function() {
    var n = this.images.length;
    var max = this._maxImages;
    this._countEl.textContent = n > 0
      ? n + '/' + max + ' fotografij' + (n === 1 ? 'a' : 'e') + ' · Tapni za dodavanje'
      : 'Tapni ili povuci fotografije · max ' + max;
  };

  Scanner.prototype.rescan = function() {
    if (!this.images.length) {
      statusEl(this._statusEl, 'warn', '⚠ Dodaj fotografiju za analizu.');
      return;
    }
    var self = this;
    var n = this.images.length;
    var docType = this.opts.docType || 'general';

    statusEl(this._statusEl, 'loading',
      '<i class="fas fa-spinner fa-spin me-1"></i> AI analizira ' +
      (n > 1 ? n + ' fotografij' + (n <= 4 ? 'e' : 'a') : 'fotografiju') + '...');

    fetch(ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify({
        doc_type: docType,
        images:   this.images.map(function(i) { return i.b64; }),
        context:  self.opts.context || {},
      }),
    })
    .then(function(r) {
      if (!r.ok) return r.json().then(function(e) { throw new Error(e.error || ('HTTP ' + r.status)); });
      return r.json();
    })
    .then(function(data) {
      if (!data.ok) throw new Error(data.error || 'Greška pri analizi');
      self.lastResult = data;
      self._onResult(data);
    })
    .catch(function(err) {
      var msg = err.message || 'Greška pri AI analizi';
      statusEl(self._statusEl, 'error',
        '✕ ' + msg +
        ' <button type="button" onclick="this.closest(\'.fs-wrap\').querySelector(\'.fs-btn-scan\').click()" ' +
        'style="margin-left:8px;font-size:.75rem;cursor:pointer;background:none;border:none;color:inherit;text-decoration:underline">↺ Ponovi</button>');
      if (self.opts.onError) self.opts.onError(msg);
    });
  };

  Scanner.prototype._onResult = function(data) {
    var fields     = data.fields || {};
    var confidence = data.confidence || 0;
    var imagesUsed = data.images_used || 1;
    var warning    = data.warning;
    var minConf    = this.opts.minConfidence !== undefined ? this.opts.minConfidence : 0.35;

    // Status poruka
    var statusHtml = '';
    if (confidence >= 0.75) {
      statusHtml = '✓ Analiza završena';
    } else if (confidence >= minConf) {
      statusHtml = '⚠ Niska pouzdanost — provjeri ili dodaj više fotografija';
    } else {
      statusHtml = '✕ Pouzdanost preniska. Dodaj jasnije fotografije.';
    }
    statusHtml += confidenceBar(confidence);
    if (warning) statusHtml += '<br><small style="opacity:.7">' + warning + '</small>';
    if (imagesUsed > 1) statusHtml += '<br><small style="opacity:.7">Korišteno ' + imagesUsed + ' fotografij' + (imagesUsed <= 4 ? 'e' : 'a') + '</small>';

    statusEl(this._statusEl,
      confidence >= 0.75 ? 'success' : confidence >= minConf ? 'warn' : 'error',
      statusHtml);

    // Prikaz rezultata
    this._showResultTable(fields);

    // Auto-fill form
    if (this.opts.autoFill !== false && confidence >= minConf) {
      this._fillFields(fields, confidence);
    }

    // Callback
    if (this.opts.onResult) {
      this.opts.onResult(fields, confidence, imagesUsed);
    }
  };

  Scanner.prototype._showResultTable = function(fields) {
    var LABELS = {
      prsten_broj:'Broj prstena', godina:'Godina', ime:'Ime', prezime:'Prezime',
      datum_rodjenja:'Datum rođenja', spol:'Spol', broj_dokumenta:'Broj dokumenta',
      nacionalnost:'Nacionalnost', vrijedi_do:'Vrijedi do', doc_type:'Tip dokumenta',
      broj_racuna:'Broj računa', datum:'Datum', dobavljac:'Dobavljač',
      iznos_ukupno:'Iznos ukupno', valuta:'Valuta', opis_boje:'Boja',
      tekst:'Tekst', kategorija:'Kategorija', sentiment:'Sentiment',
      opis:'Opis', confidence:'Pouzdanost'
    };
    var skip = ['confidence', 'boja_kod'];
    var rows = '';
    for (var k in fields) {
      if (skip.indexOf(k) !== -1) continue;
      var v = fields[k];
      if (v === null || v === undefined || v === '') continue;
      if (k === 'confidence') v = Math.round(v * 100) + '%';
      rows += '<tr><td>' + (LABELS[k] || k) + '</td><td><strong>' + v + '</strong></td></tr>';
    }
    if (rows) {
      this._resultEl.style.display = 'block';
      this._resultEl.innerHTML = '<div class="fs-result-fields"><table>' + rows + '</table></div>';
    }
  };

  Scanner.prototype._fillFields = function(fields, confidence) {
    var map = this.opts.fieldMap || {};
    for (var fieldKey in map) {
      if (!fields[fieldKey] && fields[fieldKey] !== 0) continue;
      var val = fields[fieldKey];
      var selector = map[fieldKey];
      var el = typeof selector === 'string' ? document.querySelector(selector) : selector;
      if (!el) continue;

      if (el.tagName === 'SELECT') {
        // Pokušaj match po value
        for (var i = 0; i < el.options.length; i++) {
          if (el.options[i].value.toLowerCase() === String(val).toLowerCase()) {
            el.selectedIndex = i; break;
          }
        }
      } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        // Ne prepisuj ako korisnik ručno unio
        if (el.dataset.manualEdit === '1') continue;
        el.value = val;
        el.dataset.aiGenerated = '1';
        // Trigger change event za reactive framework
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
  };

  Scanner.prototype.reset = function() {
    this.images     = [];
    this.lastResult = null;
    this._renderStrip();
    this._updateCount();
    this._actionsEl.style.display = 'none';
    this._resultEl.style.display  = 'none';
    statusEl(this._statusEl, '', '');
    this._dropEl.style.display = 'block';
  };

  Scanner.prototype.getImages = function() {
    return this.images.map(function(i) { return i.b64; });
  };

  Scanner.prototype.getResult = function() {
    return this.lastResult;
  };

  // ─── Public API ──────────────────────────────────────────────────
  root.FenixScan = {
    create: function(opts) {
      return new Scanner(opts);
    },
    version: '1.0.0',
  };

})(window);
