/**
 * FENIX VOICE — Globalni continuous voice modul
 * ================================================
 * Radi na SVIM modulima: stolarija, livestock, POS, arhiva...
 *
 * Uporaba:
 *   FenixVoice.start({
 *     lang: 'hr',                    // 'hr', 'de', 'en'
 *     onResult: function(text) {},    // callback kad prepozna rečenicu
 *     onInterim: function(text) {},   // callback za interim tekst (dok govori)
 *     silenceMs: 2000,               // ms tišine = kraj jedne izjave
 *     autoStart: true,                // automatski pokreni
 *     indicator: '#voiceIndicator',   // CSS selector za status indikator
 *   });
 *
 *   FenixVoice.stop();
 *   FenixVoice.toggle();
 *   FenixVoice.isListening;
 *
 * Globalni indikator:
 *   Dodaj u HTML: <div id="fenixVoiceGlobal"></div>
 *   Automatski se kreira ako ne postoji (float top-right, pulsing mic)
 */

(function(window) {
  'use strict';

  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    window.FenixVoice = {
      start: function() { console.warn('FenixVoice: SpeechRecognition not supported'); },
      stop: function() {},
      toggle: function() {},
      isListening: false,
      supported: false
    };
    return;
  }

  var recognition = null;
  var isListening = false;
  var config = {};
  var silenceTimer = null;
  var interimBuffer = '';
  var restartCount = 0;
  var maxRestarts = 50;
  var indicatorEl = null;

  function createIndicator() {
    var el = document.getElementById('fenixVoiceGlobal');
    if (!el) {
      el = document.createElement('div');
      el.id = 'fenixVoiceGlobal';
      document.body.appendChild(el);
    }
    el.innerHTML =
      '<div class="fv-dot" id="fvDot"></div>' +
      '<span class="fv-text" id="fvText">🎙</span>';

    // Inject CSS if not already
    if (!document.getElementById('fenixVoiceCSS')) {
      var style = document.createElement('style');
      style.id = 'fenixVoiceCSS';
      style.textContent =
        '#fenixVoiceGlobal{position:fixed;top:12px;right:12px;z-index:9999;' +
        'display:flex;align-items:center;gap:6px;background:rgba(0,0,0,.7);' +
        'backdrop-filter:blur(8px);padding:6px 12px;border-radius:20px;' +
        'font-family:"Space Grotesk",system-ui,sans-serif;font-size:.75rem;' +
        'color:#ccc;cursor:pointer;transition:all .3s;user-select:none;' +
        '-webkit-tap-highlight-color:transparent}' +
        '#fenixVoiceGlobal:hover{background:rgba(0,0,0,.85)}' +
        '#fenixVoiceGlobal.listening{border:1px solid rgba(201,168,76,.4)}' +
        '#fenixVoiceGlobal.listening .fv-dot{background:#22c55e;box-shadow:0 0 8px rgba(34,197,94,.5);animation:fvPulse 1.5s infinite}' +
        '#fenixVoiceGlobal.paused .fv-dot{background:#f59e0b}' +
        '#fenixVoiceGlobal.error .fv-dot{background:#ef4444}' +
        '.fv-dot{width:8px;height:8px;border-radius:50%;background:#64748b;transition:all .3s;flex-shrink:0}' +
        '.fv-text{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
        '@keyframes fvPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.3)}}' +
        '.fv-interim{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
        'background:rgba(0,0,0,.85);color:#e0e0e0;padding:10px 20px;border-radius:12px;' +
        'font-size:.9rem;font-family:system-ui;max-width:90vw;text-align:center;' +
        'z-index:9998;border:1px solid rgba(201,168,76,.2);display:none;' +
        'backdrop-filter:blur(8px);transition:opacity .3s}';
      document.head.appendChild(style);
    }

    el.onclick = function() { window.FenixVoice.toggle(); };
    indicatorEl = el;
    return el;
  }

  function getInterimBubble() {
    var el = document.getElementById('fvInterim');
    if (!el) {
      el = document.createElement('div');
      el.id = 'fvInterim';
      el.className = 'fv-interim';
      document.body.appendChild(el);
    }
    return el;
  }

  function updateIndicator(state, text) {
    if (!indicatorEl) return;
    indicatorEl.className = state; // 'listening', 'paused', 'error', ''
    var textEl = document.getElementById('fvText');
    if (textEl) textEl.textContent = text || '🎙';
  }

  function start(opts) {
    config = opts || {};
    config.lang = config.lang || document.documentElement.lang || 'hr';
    config.silenceMs = config.silenceMs || 2000;
    config.autoStart = config.autoStart !== false;

    if (recognition) { try { recognition.stop(); } catch(e) {} }

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    // Language mapping
    var langMap = {
      'hr': 'hr-HR', 'de': 'de-DE', 'en': 'en-US',
      'sl': 'sl-SI', 'it': 'it-IT', 'fr': 'fr-FR'
    };
    recognition.lang = langMap[config.lang] || config.lang;

    createIndicator();

    recognition.onresult = function(event) {
      var interim = '';
      var final_text = '';

      for (var i = event.resultIndex; i < event.results.length; i++) {
        var transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final_text += transcript;
        } else {
          interim += transcript;
        }
      }

      // Show interim
      if (interim) {
        interimBuffer = interim;
        var bubble = getInterimBubble();
        bubble.textContent = '🎙 ' + interim;
        bubble.style.display = 'block';
        updateIndicator('listening', '🎙 ' + interim.substring(0, 30));

        if (config.onInterim) config.onInterim(interim);

        // Reset silence timer
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(function() {
          // Silence detected — finalize
          if (interimBuffer) {
            if (config.onResult) config.onResult(interimBuffer);
            interimBuffer = '';
            bubble.style.display = 'none';
            updateIndicator('listening', '🎙 Slušam...');
          }
        }, config.silenceMs);
      }

      // Final result
      if (final_text) {
        clearTimeout(silenceTimer);
        interimBuffer = '';
        var bubble = getInterimBubble();
        bubble.style.display = 'none';

        if (config.onResult) config.onResult(final_text.trim());

        updateIndicator('listening', '✅ ' + final_text.substring(0, 25));
        setTimeout(function() {
          updateIndicator('listening', '🎙 Slušam...');
        }, 2000);
      }
    };

    recognition.onerror = function(event) {
      if (event.error === 'no-speech') {
        // Normal — just no speech detected, keep listening
        return;
      }
      if (event.error === 'aborted' || event.error === 'network') {
        updateIndicator('error', '❌ ' + event.error);
        // Auto-restart after error
        if (restartCount < maxRestarts) {
          setTimeout(function() { doStart(); }, 1000);
          restartCount++;
        }
        return;
      }
      console.warn('FenixVoice error:', event.error);
      updateIndicator('error', '❌ ' + event.error);
    };

    recognition.onend = function() {
      // Auto-restart if still supposed to be listening
      if (isListening && restartCount < maxRestarts) {
        setTimeout(function() { doStart(); }, 300);
        restartCount++;
      } else {
        updateIndicator('paused', '⏸ Pauza');
      }
    };

    if (config.autoStart) {
      doStart();
    }
  }

  function doStart() {
    try {
      recognition.start();
      isListening = true;
      updateIndicator('listening', '🎙 Slušam...');
    } catch(e) {
      // Already started
      if (e.message && e.message.includes('already started')) return;
      console.warn('FenixVoice start error:', e);
    }
  }

  function stop() {
    isListening = false;
    restartCount = 0;
    clearTimeout(silenceTimer);
    if (recognition) {
      try { recognition.stop(); } catch(e) {}
    }
    updateIndicator('paused', '⏸ Zaustavljeno');
    var bubble = document.getElementById('fvInterim');
    if (bubble) bubble.style.display = 'none';
  }

  function toggle() {
    if (isListening) { stop(); }
    else { doStart(); }
  }

  // Public API
  window.FenixVoice = {
    start: start,
    stop: stop,
    toggle: toggle,
    get isListening() { return isListening; },
    supported: true,
    // Parse helpers for common patterns
    parseDimensions: function(text) {
      // "1654 puta 1205" or "1654 × 1205" or "1654 sa 1205"
      var m = text.match(/(\d{2,5})\s*(?:puta|×|x|sa|s|na|po|s\s*a)\s*(\d{2,5})/i);
      if (m) return { width: parseInt(m[1]), height: parseInt(m[2]) };
      // "širina 1654 visina 1205"
      m = text.match(/(?:širina|sirina|breit)\s*(\d{2,5}).*(?:visina|hohe|höhe)\s*(\d{2,5})/i);
      if (m) return { width: parseInt(m[1]), height: parseInt(m[2]) };
      // Just two numbers
      var nums = text.match(/\d{3,5}/g);
      if (nums && nums.length >= 2) return { width: parseInt(nums[0]), height: parseInt(nums[1]) };
      return null;
    },
    parsePosition: function(text) {
      var m = text.match(/pozicija\s*(\d+)/i);
      return m ? parseInt(m[1]) : null;
    }
  };

})(window);
