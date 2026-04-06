/**
 * FenixInput — Univerzalni ulazni widget za LIMIT Connect
 *
 * Kanali: Glas (Web Speech API), Bluetooth (Web Bluetooth), SMS (webhook), Manual
 * Upotreba:  FenixInput.init('#my-container')  — ili data-fenix-input atribut
 *
 * Pero pčelar pritisne mikrofon, kaže "košnica tri, dvanaest kila",
 * AI parsira, Pero potvrdi, podatak ide u knjige.
 *
 * @author  Claude Opus 4.6 + Ivan Brtan
 * @version 1.0.0 — 2026-04-06
 * @license LIMIT Connect — Konjik d.o.o. & NO LIMIT udruga
 */
(function(window) {
  'use strict';

  var API_BASE = '/api/fenix-input';

  // ═══════════════════════════════════════════════════════
  // VOICE — Web Speech API (besplatno, browser-native)
  // ═══════════════════════════════════════════════════════

  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function createVoiceEngine(lang) {
    if (!SpeechRecognition) return null;
    var recognition = new SpeechRecognition();
    recognition.lang = lang || 'hr-HR';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    return recognition;
  }

  // ═══════════════════════════════════════════════════════
  // BLUETOOTH — Web Bluetooth API (chip readers)
  // ═══════════════════════════════════════════════════════

  var BT = {
    device: null,
    characteristic: null,

    isSupported: function() {
      return !!navigator.bluetooth;
    },

    connect: async function(serviceUUID, charUUID) {
      if (!this.isSupported()) throw new Error('Bluetooth nije podržan u ovom pregledniku');

      this.device = await navigator.bluetooth.requestDevice({
        filters: [{ services: [serviceUUID] }],
        optionalServices: [serviceUUID],
      });

      var server = await this.device.gatt.connect();
      var service = await server.getPrimaryService(serviceUUID);
      this.characteristic = await service.getCharacteristic(charUUID);
      return this.device.name || 'Bluetooth uređaj';
    },

    listen: function(callback) {
      if (!this.characteristic) return;
      this.characteristic.startNotifications();
      this.characteristic.addEventListener('characteristicvaluechanged', function(event) {
        var decoder = new TextDecoder('utf-8');
        var value = decoder.decode(event.target.value);
        callback(value.trim());
      });
    },

    disconnect: function() {
      if (this.device && this.device.gatt.connected) {
        this.device.gatt.disconnect();
      }
      this.device = null;
      this.characteristic = null;
    }
  };

  // ═══════════════════════════════════════════════════════
  // WIDGET UI
  // ═══════════════════════════════════════════════════════

  function createWidget(container, options) {
    options = options || {};
    var lang = options.lang || 'hr-HR';
    var onResult = options.onResult || function() {};
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    csrfToken = csrfToken ? csrfToken.value : '';

    // State
    var isRecording = false;
    var recognition = createVoiceEngine(lang);

    // Build UI
    var widget = document.createElement('div');
    widget.className = 'fenix-input-widget';
    widget.innerHTML = [
      '<div class="fi-bar">',
      '  <button class="fi-btn fi-mic" title="Pritisni za govor" type="button">',
      '    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">',
      '      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>',
      '      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>',
      '      <line x1="12" y1="19" x2="12" y2="23"/>',
      '      <line x1="8" y1="23" x2="16" y2="23"/>',
      '    </svg>',
      '  </button>',
      '  <div class="fi-text-wrap">',
      '    <input class="fi-text" type="text" placeholder="Govori ili tipkaj..." autocomplete="off">',
      '  </div>',
      '  <button class="fi-btn fi-send" title="Pošalji" type="button">',
      '    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">',
      '      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>',
      '    </svg>',
      '  </button>',
      (BT.isSupported() ? '  <button class="fi-btn fi-bt" title="Bluetooth čitač" type="button">BT</button>' : ''),
      '</div>',
      '<div class="fi-status" style="display:none"></div>',
      '<div class="fi-result" style="display:none"></div>',
    ].join('\n');

    container.appendChild(widget);

    var micBtn = widget.querySelector('.fi-mic');
    var sendBtn = widget.querySelector('.fi-send');
    var btBtn = widget.querySelector('.fi-bt');
    var textInput = widget.querySelector('.fi-text');
    var statusEl = widget.querySelector('.fi-status');
    var resultEl = widget.querySelector('.fi-result');

    // ── Mikrofon ──
    if (micBtn && recognition) {
      var finalTranscript = '';

      recognition.onresult = function(event) {
        var interim = '';
        finalTranscript = '';
        for (var i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        textInput.value = finalTranscript || interim;
      };

      recognition.onend = function() {
        isRecording = false;
        micBtn.classList.remove('fi-recording');
        statusEl.style.display = 'none';
        if (finalTranscript) {
          sendToAI(finalTranscript, 'voice');
        }
      };

      recognition.onerror = function(event) {
        isRecording = false;
        micBtn.classList.remove('fi-recording');
        if (event.error === 'not-allowed') {
          showStatus('Mikrofon nije dozvoljen. Omogući pristup u postavkama preglednika.', 'error');
        } else if (event.error !== 'aborted') {
          showStatus('Greška: ' + event.error, 'error');
        }
      };

      micBtn.addEventListener('click', function() {
        if (isRecording) {
          recognition.stop();
        } else {
          finalTranscript = '';
          textInput.value = '';
          recognition.start();
          isRecording = true;
          micBtn.classList.add('fi-recording');
          showStatus('Slušam... govori.', 'listening');
        }
      });
    } else if (micBtn) {
      micBtn.style.opacity = '0.3';
      micBtn.title = 'Govor nije podržan u ovom pregledniku';
    }

    // ── Send ──
    sendBtn.addEventListener('click', function() {
      var text = textInput.value.trim();
      if (text) sendToAI(text, 'manual');
    });

    textInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        var text = textInput.value.trim();
        if (text) sendToAI(text, 'manual');
      }
    });

    // ── Bluetooth ──
    if (btBtn) {
      btBtn.addEventListener('click', async function() {
        try {
          showStatus('Tražim Bluetooth uređaj...', 'info');
          var config = await fetch(API_BASE + '/bluetooth/config/').then(function(r) { return r.json(); });
          var dev = config.supported_devices[0];
          var name = await BT.connect(dev.service_uuid, dev.characteristic_uuid);
          showStatus('Spojeno: ' + name + ' — skeniraj čip', 'success');
          BT.listen(function(chipNumber) {
            textInput.value = chipNumber;
            showStatus('Čip očitan: ' + chipNumber, 'success');
            onResult({ channel: 'bluetooth', raw_text: chipNumber, chip_number: chipNumber });
          });
        } catch (err) {
          showStatus('BT greška: ' + err.message, 'error');
        }
      });
    }

    // ── API ──
    function sendToAI(text, channel) {
      showStatus('AI analizira...', 'processing');
      textInput.disabled = true;

      fetch(API_BASE + '/voice/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ text: text, lang: lang, channel: channel }),
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        textInput.disabled = false;
        if (data.parsed && data.parsed.confidence >= 0.3) {
          showResult(data);
          onResult(data);
        } else {
          showStatus('Nisam razumio. Pokušaj ponovo ili preformuliraj.', 'error');
        }
      })
      .catch(function(err) {
        textInput.disabled = false;
        showStatus('Greška: ' + err.message, 'error');
      });
    }

    function showStatus(text, type) {
      statusEl.textContent = text;
      statusEl.className = 'fi-status fi-status-' + type;
      statusEl.style.display = 'block';
      if (type !== 'listening' && type !== 'processing') {
        setTimeout(function() { statusEl.style.display = 'none'; }, 5000);
      }
    }

    function showResult(data) {
      var p = data.parsed;
      var fields = p.fields || {};
      var fieldRows = Object.keys(fields).map(function(k) {
        return '<div class="fi-field"><span class="fi-field-key">' + k + '</span> <span class="fi-field-val">' + fields[k] + '</span></div>';
      }).join('');

      resultEl.innerHTML = [
        '<div class="fi-result-header">',
        '  <span class="fi-intent">' + (p.intent || '?') + '</span>',
        '  <span class="fi-confidence">' + Math.round((p.confidence || 0) * 100) + '%</span>',
        '  <span class="fi-module">' + (p.target_module || '') + ' / ' + (p.target_action || '') + '</span>',
        '</div>',
        '<div class="fi-fields">' + fieldRows + '</div>',
        '<div class="fi-actions">',
        '  <button class="fi-btn fi-confirm" data-id="' + data.id + '">Potvrdi</button>',
        '  <button class="fi-btn fi-reject" data-id="' + data.id + '">Odbaci</button>',
        '</div>',
      ].join('\n');
      resultEl.style.display = 'block';
      statusEl.style.display = 'none';

      resultEl.querySelector('.fi-confirm').onclick = function() {
        confirmMsg(data.id);
      };
      resultEl.querySelector('.fi-reject').onclick = function() {
        resultEl.style.display = 'none';
        textInput.value = '';
      };
    }

    function confirmMsg(msgId) {
      fetch(API_BASE + '/confirm/' + msgId + '/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: '{}',
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        resultEl.innerHTML = '<div class="fi-confirmed">Spremljeno.</div>';
        setTimeout(function() { resultEl.style.display = 'none'; textInput.value = ''; }, 2000);
      })
      .catch(function(err) {
        showStatus('Greška pri potvrdi: ' + err.message, 'error');
      });
    }

    return widget;
  }

  // ═══════════════════════════════════════════════════════
  // CSS (inline — nema vanjskih zavisnosti)
  // ═══════════════════════════════════════════════════════

  var style = document.createElement('style');
  style.textContent = [
    '.fenix-input-widget{font-family:"Space Grotesk",system-ui,sans-serif;max-width:100%}',
    '.fi-bar{display:flex;align-items:center;gap:6px;background:#fff;border:1.5px solid #ddd9cc;border-radius:12px;padding:6px 8px}',
    '.fi-btn{border:none;background:none;cursor:pointer;padding:8px;border-radius:8px;color:#1a1a2e;transition:all .2s;flex-shrink:0;font-size:.82rem;font-weight:600}',
    '.fi-btn:hover{background:rgba(201,168,76,.12)}',
    '.fi-mic{color:#c9a84c}',
    '.fi-mic.fi-recording{color:#e05252;animation:fi-pulse 1s infinite}',
    '@keyframes fi-pulse{0%,100%{opacity:1}50%{opacity:.4}}',
    '.fi-text-wrap{flex:1;min-width:0}',
    '.fi-text{width:100%;border:none;outline:none;font-size:.9rem;font-family:inherit;padding:6px 4px;background:transparent;color:#1a1a2e}',
    '.fi-send{color:#c9a84c}',
    '.fi-bt{color:#4caf7d;font-size:.7rem;letter-spacing:.05em}',
    '.fi-status{padding:8px 12px;border-radius:8px;font-size:.8rem;margin-top:6px;transition:all .2s}',
    '.fi-status-listening{background:rgba(201,168,76,.1);color:#c9a84c}',
    '.fi-status-processing{background:rgba(59,130,246,.1);color:#3b82f6}',
    '.fi-status-success{background:rgba(76,175,125,.1);color:#4caf7d}',
    '.fi-status-error{background:rgba(224,82,82,.08);color:#e05252}',
    '.fi-status-info{background:rgba(59,130,246,.08);color:#3b82f6}',
    '.fi-result{background:#fafaf7;border:1px solid #ddd9cc;border-radius:10px;padding:14px;margin-top:8px}',
    '.fi-result-header{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}',
    '.fi-intent{font-weight:700;font-size:.88rem;color:#1a1a2e}',
    '.fi-confidence{font-size:.72rem;padding:2px 8px;border-radius:12px;background:rgba(76,175,125,.12);color:#4caf7d;font-weight:600}',
    '.fi-module{font-size:.72rem;color:#7a7a8c}',
    '.fi-fields{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}',
    '.fi-field{display:flex;gap:8px;font-size:.82rem}',
    '.fi-field-key{color:#7a7a8c;min-width:100px;text-transform:uppercase;font-size:.7rem;letter-spacing:.04em;padding-top:2px}',
    '.fi-field-val{color:#1a1a2e;font-weight:500}',
    '.fi-actions{display:flex;gap:8px}',
    '.fi-confirm{background:#c9a84c !important;color:#fff !important;padding:8px 20px !important;border-radius:6px !important;font-weight:700 !important}',
    '.fi-reject{background:transparent !important;border:1px solid #ddd9cc !important;padding:8px 16px !important;border-radius:6px !important;color:#7a7a8c !important}',
    '.fi-confirmed{text-align:center;color:#4caf7d;font-weight:600;padding:8px}',
    /* Dark mode */
    '[data-theme="dark"] .fi-bar{background:#1e293b;border-color:#334155}',
    '[data-theme="dark"] .fi-text{color:#e2e8f0}',
    '[data-theme="dark"] .fi-result{background:#1e293b;border-color:#334155}',
    '[data-theme="dark"] .fi-intent{color:#e2e8f0}',
    '[data-theme="dark"] .fi-field-val{color:#e2e8f0}',
  ].join('\n');
  document.head.appendChild(style);

  // ═══════════════════════════════════════════════════════
  // PUBLIC API
  // ═══════════════════════════════════════════════════════

  window.FenixInput = {
    version: '1.0.0',

    init: function(selector, options) {
      var el = typeof selector === 'string' ? document.querySelector(selector) : selector;
      if (!el) { console.error('FenixInput: element not found:', selector); return null; }
      return createWidget(el, options);
    },

    // Programmatic voice
    startVoice: function(callback) {
      var engine = createVoiceEngine('hr-HR');
      if (!engine) { callback(null, 'Speech API not supported'); return; }
      engine.onresult = function(e) {
        var text = '';
        for (var i = 0; i < e.results.length; i++) {
          if (e.results[i].isFinal) text += e.results[i][0].transcript;
        }
        callback(text);
      };
      engine.onerror = function(e) { callback(null, e.error); };
      engine.start();
      return engine;
    },

    // Programmatic BT
    bluetooth: BT,

    // Send text directly to AI
    interpret: function(text) {
      return fetch(API_BASE + '/voice/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text }),
      }).then(function(r) { return r.json(); });
    },

    // Check capabilities
    capabilities: {
      voice: !!SpeechRecognition,
      bluetooth: !!navigator.bluetooth,
      camera: !!navigator.mediaDevices,
    },
  };

  // Auto-init: data-fenix-input atribut
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-fenix-input]').forEach(function(el) {
      var opts = {};
      try { opts = JSON.parse(el.getAttribute('data-fenix-input-options') || '{}'); } catch(e) {}
      window.FenixInput.init(el, opts);
    });
  });

})(window);
