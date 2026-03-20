/**
 * LIMIT CONNECT — Smart Input Module (Globalni)
 *
 * Jedan modul za sve vrste unosa, poziva se iz bilo kojeg templatea.
 * Uključuje: glasovni unos, kamera scan, digitalni potpis, AI anomaly check.
 *
 * Korištenje:
 *   <script src="/static/js/smart-input.js"></script>
 *   SmartInput.voice(textareaId, {lang: 'hr-HR'})
 *   SmartInput.camera(previewId, {mode: 'barcode|photo|document'})
 *   SmartInput.signature(canvasId, {color: '#c9a84c'})
 *   SmartInput.aiCheck(data, {module: 'pos', company_id: '...'})
 */

window.SmartInput = (function() {
  'use strict';

  // ═══════════════════════════════════════════════
  // VOICE — Speech-to-Text (Web Speech API)
  // ═══════════════════════════════════════════════
  var _recognition = null;
  var _isListening = false;

  function voice(targetId, opts) {
    opts = opts || {};
    var lang = opts.lang || 'hr-HR';
    var onResult = opts.onResult || null;
    var onEnd = opts.onEnd || null;

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      return {supported: false, error: 'Speech API nije podržan. Koristite Chrome ili Edge.'};
    }

    return {
      supported: true,
      start: function() {
        if (_isListening) return;
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        _recognition = new SR();
        _recognition.lang = lang;
        _recognition.continuous = true;
        _recognition.interimResults = true;

        var target = document.getElementById(targetId);
        var baseText = target ? target.value : '';

        _recognition.onresult = function(e) {
          var interim = '';
          for (var i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) {
              baseText += e.results[i][0].transcript + '. ';
              if (target) target.value = baseText;
              if (onResult) onResult(baseText, true);
            } else {
              interim += e.results[i][0].transcript;
              if (onResult) onResult(interim, false);
            }
          }
        };

        _recognition.onerror = function(e) {
          console.warn('Speech error:', e.error);
          if (e.error !== 'no-speech') voice.stop();
        };

        _recognition.onend = function() {
          if (_isListening) _recognition.start(); // auto-restart
          if (onEnd) onEnd(baseText);
        };

        _recognition.start();
        _isListening = true;
        return true;
      },
      stop: function() {
        if (_recognition) { _recognition.stop(); _recognition = null; }
        _isListening = false;
      },
      isListening: function() { return _isListening; },
      toggle: function() {
        if (_isListening) this.stop(); else this.start();
        return _isListening;
      }
    };
  }


  // ═══════════════════════════════════════════════
  // CAMERA — Photo, Barcode, Document scan
  // ═══════════════════════════════════════════════
  function camera(previewId, opts) {
    opts = opts || {};
    var mode = opts.mode || 'photo';   // photo | barcode | document
    var facing = opts.facing || 'environment';
    var onCapture = opts.onCapture || null;
    var onBarcode = opts.onBarcode || null;
    var _stream = null;
    var _videoEl = null;
    var _scanner = null;

    return {
      start: function(videoElId) {
        _videoEl = document.getElementById(videoElId);
        if (!_videoEl) return Promise.reject('Video element not found');

        return navigator.mediaDevices.getUserMedia({
          video: {facingMode: facing, width: {ideal: 1280}}
        }).then(function(stream) {
          _stream = stream;
          _videoEl.srcObject = stream;
          _videoEl.play();

          // Barcode mode — use html5-qrcode if available
          if (mode === 'barcode' && window.Html5Qrcode) {
            _scanner = new Html5Qrcode(videoElId);
            return _scanner.start(
              {facingMode: facing},
              {fps: 10, qrbox: {width: 280, height: 120},
               formatsToSupport: [
                 Html5QrcodeSupportedFormats.EAN_13,
                 Html5QrcodeSupportedFormats.EAN_8,
                 Html5QrcodeSupportedFormats.CODE_128,
                 Html5QrcodeSupportedFormats.CODE_39,
                 Html5QrcodeSupportedFormats.QR_CODE,
                 Html5QrcodeSupportedFormats.UPC_A,
               ]},
              function(decoded) {
                if (onBarcode) onBarcode(decoded);
                // Audio beep
                try {
                  var ctx = new (window.AudioContext || window.webkitAudioContext)();
                  var osc = ctx.createOscillator();
                  osc.frequency.value = 1200;
                  osc.connect(ctx.destination);
                  osc.start(); osc.stop(ctx.currentTime + 0.1);
                } catch(e) {}
              },
              function() {} // ignore errors
            );
          }
        });
      },

      capture: function() {
        if (!_videoEl) return null;
        var canvas = document.createElement('canvas');
        canvas.width = _videoEl.videoWidth;
        canvas.height = _videoEl.videoHeight;
        canvas.getContext('2d').drawImage(_videoEl, 0, 0);
        var data = canvas.toDataURL('image/jpeg', 0.8);

        // Show preview
        var preview = document.getElementById(previewId);
        if (preview) {
          if (preview.tagName === 'IMG') {
            preview.src = data;
            preview.style.display = 'block';
          } else {
            preview.innerHTML = '<img src="' + data + '" style="max-width:100%;border-radius:8px">';
          }
        }
        if (onCapture) onCapture(data);
        return data;
      },

      stop: function() {
        if (_scanner) { _scanner.stop().catch(function(){}); _scanner = null; }
        if (_stream) { _stream.getTracks().forEach(function(t){t.stop()}); _stream = null; }
      },

      // File input fallback
      fromFile: function(fileInput, callback) {
        if (!fileInput.files || !fileInput.files[0]) return;
        var reader = new FileReader();
        reader.onload = function(e) {
          var data = e.target.result;
          var preview = document.getElementById(previewId);
          if (preview) {
            if (preview.tagName === 'IMG') { preview.src = data; preview.style.display = 'block'; }
            else { preview.innerHTML = '<img src="' + data + '" style="max-width:100%;border-radius:8px">'; }
          }
          if (callback) callback(data);
          if (onCapture) onCapture(data);
        };
        reader.readAsDataURL(fileInput.files[0]);
      }
    };
  }


  // ═══════════════════════════════════════════════
  // SIGNATURE — Touch/Mouse digital signature
  // ═══════════════════════════════════════════════
  function signature(canvasId, opts) {
    opts = opts || {};
    var color = opts.color || '#c9a84c';
    var lineWidth = opts.lineWidth || 2.5;
    var bgColor = opts.bgColor || 'transparent';

    var canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    var ctx = canvas.getContext('2d');
    var rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    if (bgColor !== 'transparent') {
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    var drawing = false;

    function getPos(e) {
      var r = canvas.getBoundingClientRect();
      var touch = e.touches ? e.touches[0] : e;
      return {x: touch.clientX - r.left, y: touch.clientY - r.top};
    }

    canvas.addEventListener('mousedown', function(e) { drawing = true; ctx.beginPath(); var p = getPos(e); ctx.moveTo(p.x, p.y); });
    canvas.addEventListener('mousemove', function(e) { if (!drawing) return; var p = getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); });
    canvas.addEventListener('mouseup', function() { drawing = false; });
    canvas.addEventListener('mouseleave', function() { drawing = false; });
    canvas.addEventListener('touchstart', function(e) { e.preventDefault(); drawing = true; ctx.beginPath(); var p = getPos(e); ctx.moveTo(p.x, p.y); }, {passive: false});
    canvas.addEventListener('touchmove', function(e) { e.preventDefault(); if (!drawing) return; var p = getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }, {passive: false});
    canvas.addEventListener('touchend', function() { drawing = false; });

    return {
      clear: function() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (bgColor !== 'transparent') {
          ctx.fillStyle = bgColor;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
      },
      getData: function() {
        var data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
        for (var i = 3; i < data.length; i += 4) {
          if (data[i] > 0) return canvas.toDataURL('image/png');
        }
        return null; // Empty
      },
      isEmpty: function() {
        return this.getData() === null;
      }
    };
  }


  // ═══════════════════════════════════════════════
  // AI CHECK — Anomaly detection via AI Agent Gateway
  // ═══════════════════════════════════════════════
  function aiCheck(data, opts) {
    opts = opts || {};
    var module = opts.module || 'general';
    var checks = opts.checks || ['anomaly', 'duplicate', 'range'];
    var token = opts.token || '';
    var onResult = opts.onResult || null;

    var warnings = [];

    // Client-side quick checks
    if (checks.indexOf('range') >= 0) {
      // Amount range check
      if (data.amount !== undefined) {
        var amt = parseFloat(data.amount);
        if (amt < 0) warnings.push({level: 'danger', message: 'Negativan iznos: ' + amt});
        if (amt > 10000) warnings.push({level: 'warning', message: 'Veliki iznos: ' + amt + ' EUR — provjeriti'});
        if (amt === 0) warnings.push({level: 'info', message: 'Iznos je 0 EUR'});
      }
    }

    if (checks.indexOf('anomaly') >= 0) {
      // Time anomaly
      var hour = new Date().getHours();
      if (hour < 5 || hour > 23) {
        warnings.push({level: 'warning', message: 'Transakcija izvan radnog vremena (' + hour + ':00)'});
      }
      // Discount anomaly
      if (data.discount && parseFloat(data.discount) > 30) {
        warnings.push({level: 'warning', message: 'Popust > 30% (' + data.discount + '%) — treba autorizacija'});
      }
    }

    if (checks.indexOf('duplicate') >= 0) {
      // Check localStorage for recent similar transactions
      var recentKey = 'ai_recent_' + module;
      try {
        var recent = JSON.parse(localStorage.getItem(recentKey) || '[]');
        var now = Date.now();
        // Clean old entries (>5 min)
        recent = recent.filter(function(r) { return now - r.ts < 300000; });
        // Check for duplicate
        var isDupe = recent.some(function(r) {
          return r.amount === data.amount && r.name === data.name;
        });
        if (isDupe) {
          warnings.push({level: 'danger', message: 'Moguci duplikat! Ista stavka i iznos u zadnjih 5 min.'});
        }
        // Save current
        recent.push({amount: data.amount, name: data.name, ts: now});
        localStorage.setItem(recentKey, JSON.stringify(recent.slice(-20)));
      } catch(e) {}
    }

    // Server-side AI check (if token provided)
    if (token && warnings.length === 0 && checks.indexOf('server') >= 0) {
      return fetch('/api/ai-agent/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
        body: JSON.stringify({action: 'query', module: module, payload: {type: 'anomaly_check', data: data}})
      })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.warnings) warnings = warnings.concat(d.warnings);
        if (onResult) onResult(warnings);
        return warnings;
      })
      .catch(function() {
        if (onResult) onResult(warnings);
        return warnings;
      });
    }

    if (onResult) onResult(warnings);
    return Promise.resolve(warnings);
  }


  // ═══════════════════════════════════════════════
  // OFFLINE QUEUE — Universal offline save/sync
  // ═══════════════════════════════════════════════
  function offlineQueue(key) {
    key = key || 'smart_input_queue';
    return {
      push: function(item) {
        var q = JSON.parse(localStorage.getItem(key) || '[]');
        item._ts = Date.now();
        item._id = 'SI-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);
        q.push(item);
        localStorage.setItem(key, JSON.stringify(q));
        return item._id;
      },
      getAll: function() {
        return JSON.parse(localStorage.getItem(key) || '[]');
      },
      count: function() {
        return this.getAll().length;
      },
      flush: function(url, headers) {
        var q = this.getAll();
        if (!q.length) return Promise.resolve(0);
        var self = this;
        var ok = 0;
        return Promise.all(q.map(function(item) {
          return fetch(url, {
            method: 'POST',
            headers: headers || {'Content-Type': 'application/json'},
            body: JSON.stringify(item)
          }).then(function() { ok++; }).catch(function() {});
        })).then(function() {
          if (ok === q.length) localStorage.setItem(key, '[]');
          return ok;
        });
      },
      clear: function() { localStorage.setItem(key, '[]'); }
    };
  }


  // ═══════════════════════════════════════════════
  // PUBLIC API
  // ═══════════════════════════════════════════════
  return {
    voice: voice,
    camera: camera,
    signature: signature,
    aiCheck: aiCheck,
    offlineQueue: offlineQueue,
    version: '1.0.0',
  };

})();
