/**
 * FenixCamera — Globalni modul za kameru/galeriju.
 * Jedan API za sve module: arhiva, POS, widget, cockpit, assessment.
 *
 * Usage:
 *   FenixCamera.quick('previewEl', { onReady: function(r) { ... } });
 *   FenixCamera.pick({ onCapture: function(r) { ... } });
 *
 * Result objekt:
 *   r.b64       — base64 bez prefix
 *   r.dataUrl   — data:image/jpeg;base64,...
 *   r.blob      — Blob objekt
 *   r.filename  — fenix_YYYYMMDD_HHMMSS.jpg
 *   r.size_kb   — velicina u KB
 */
(function() {
  'use strict';

  var DEFAULTS = {
    quality: 0.85,
    maxWidth: 1920,
    maxHeight: 1920,
    format: 'image/jpeg',
  };

  // Samsung browser detection — some Samsung Internet versions don't support
  // capture attribute properly. Fallback: don't set capture, let user choose.
  var isSamsung = /SamsungBrowser/i.test(navigator.userAgent || '');
  var isSamsungGalaxy = /SM-/i.test(navigator.userAgent || '') && /Android/i.test(navigator.userAgent || '');

  function timestamp() {
    var d = new Date();
    return d.getFullYear() +
      ('0'+(d.getMonth()+1)).slice(-2) +
      ('0'+d.getDate()).slice(-2) + '_' +
      ('0'+d.getHours()).slice(-2) +
      ('0'+d.getMinutes()).slice(-2) +
      ('0'+d.getSeconds()).slice(-2);
  }

  function resizeAndCompress(file, opts, callback) {
    var reader = new FileReader();
    reader.onload = function(e) {
      var img = new Image();
      img.onload = function() {
        var w = img.width;
        var h = img.height;
        var maxW = opts.maxWidth || DEFAULTS.maxWidth;
        var maxH = opts.maxHeight || DEFAULTS.maxHeight;

        if (w > maxW || h > maxH) {
          var ratio = Math.min(maxW / w, maxH / h);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
        }

        var canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);

        var quality = opts.quality || DEFAULTS.quality;
        var format = opts.format || DEFAULTS.format;

        canvas.toBlob(function(blob) {
          var readerB64 = new FileReader();
          readerB64.onload = function() {
            var dataUrl = readerB64.result;
            var b64 = dataUrl.split(',')[1];
            callback({
              b64: b64,
              dataUrl: dataUrl,
              blob: blob,
              filename: 'fenix_' + timestamp() + '.jpg',
              size_kb: Math.round(blob.size / 1024),
              width: w,
              height: h,
            });
          };
          readerB64.readAsDataURL(blob);
        }, format, quality);
      };
      img.onerror = function() {
        if (opts.onError) opts.onError('Slika se ne moze ucitati');
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  // ── PICK: odabir iz kamere/galerije ────────────────────────────

  function pick(opts) {
    opts = opts || {};
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';

    var source = opts.source || 'any';
    if (source === 'camera') {
      // Samsung browser fallback: capture attribute causes black screen on some models
      if (isSamsung || isSamsungGalaxy) {
        // Don't set capture — let Samsung's native picker handle it
        input.setAttribute('accept', 'image/*');
      } else {
        input.setAttribute('capture', 'environment');
      }
    }

    input.onchange = function() {
      var file = input.files[0];
      if (!file) {
        if (opts.onError) opts.onError('Nema odabrane datoteke');
        return;
      }

      // Check file size (max 20MB raw)
      if (file.size > 20 * 1024 * 1024) {
        if (opts.onError) opts.onError('Datoteka prevelika (max 20MB)');
        return;
      }

      resizeAndCompress(file, opts, function(result) {
        if (opts.onCapture) opts.onCapture(result);
      });
    };

    input.click();
  }

  // ── PREVIEW: prikaz u elementu ─────────────────────────────────

  function showPreview(b64OrDataUrl, elementId, opts) {
    opts = opts || {};
    var el = typeof elementId === 'string' ? document.getElementById(elementId) : elementId;
    if (!el) return;

    var dataUrl = b64OrDataUrl;
    if (dataUrl && dataUrl.indexOf('data:') !== 0) {
      dataUrl = 'data:image/jpeg;base64,' + b64OrDataUrl;
    }

    el.innerHTML = '';
    el.style.display = 'block';

    var img = document.createElement('img');
    img.src = dataUrl;
    img.style.maxWidth = '100%';
    img.style.maxHeight = (opts.maxHeight || 120) + 'px';
    img.style.borderRadius = '6px';
    img.style.border = '1px solid #334155';
    el.appendChild(img);

    if (opts.clearBtn !== false) {
      var btn = document.createElement('button');
      btn.textContent = '\u2715';
      btn.style.cssText = 'position:absolute;top:4px;right:4px;background:rgba(0,0,0,.6);color:#fff;border:none;border-radius:50%;width:24px;height:24px;cursor:pointer;font-size:14px;line-height:1';
      btn.onclick = function() {
        el.innerHTML = '';
        el.style.display = 'none';
        if (opts.onClear) opts.onClear();
      };
      el.style.position = 'relative';
      el.appendChild(btn);
    }
  }

  // ── UPLOAD: posalji na server ──────────────────────────────────

  function upload(b64, filename, opts) {
    opts = opts || {};
    var url = opts.url || '/documents/arhiva/convert/';

    var formData = new FormData();
    // Convert b64 to blob
    var byteString = atob(b64);
    var ab = new ArrayBuffer(byteString.length);
    var ia = new Uint8Array(ab);
    for (var i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    var blob = new Blob([ab], { type: 'image/jpeg' });

    formData.append('file', blob, filename || 'fenix_photo.jpg');

    // Extra data
    if (opts.extraData) {
      for (var key in opts.extraData) {
        formData.append(key, opts.extraData[key]);
      }
    }

    // CSRF
    var csrf = document.cookie.match('csrftoken=([^;]+)');
    csrf = csrf ? csrf[1] : '';

    fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf },
      body: formData,
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (opts.onSuccess) opts.onSuccess(data);
    })
    .catch(function(err) {
      if (opts.onError) opts.onError(err.message || 'Upload error');
    });
  }

  // ── ANALYZE WITH AI ────────────────────────────────────────────

  function analyzeWithAI(b64, opts) {
    opts = opts || {};
    var csrf = document.cookie.match('csrftoken=([^;]+)');
    csrf = csrf ? csrf[1] : '';

    fetch('/ai/api/analyze-image/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
      },
      body: JSON.stringify({
        image_b64: b64,
        prompt: opts.prompt || 'Sto je na slici?',
        module: opts.module || 'general',
      }),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) {
        if (opts.onError) opts.onError(data.error);
      } else {
        if (opts.onResult) opts.onResult(data.response || data.content || '');
      }
    })
    .catch(function(err) {
      if (opts.onError) opts.onError(err.message || 'AI analyze error');
    });
  }

  // ── QUICK: pick + preview + callback u jednom ──────────────────

  function quick(previewElementId, opts) {
    opts = opts || {};
    pick({
      source: opts.source || 'any',
      quality: opts.quality || DEFAULTS.quality,
      maxWidth: opts.maxWidth || DEFAULTS.maxWidth,
      onCapture: function(result) {
        if (previewElementId) {
          showPreview(result.dataUrl, previewElementId, {
            maxHeight: opts.maxHeight || 120,
            onClear: function() {
              if (opts.onClear) opts.onClear();
            },
          });
        }
        if (opts.onReady) opts.onReady(result);
      },
      onError: function(err) {
        if (opts.onError) opts.onError(err);
      },
    });
  }

  // ── PUBLIC API ─────────────────────────────────────────────────

  window.FenixCamera = {
    pick: pick,
    showPreview: showPreview,
    upload: upload,
    analyzeWithAI: analyzeWithAI,
    quick: quick,
    version: '1.0.0',
  };

})();
