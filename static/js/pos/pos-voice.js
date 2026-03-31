/* ═══ POS Voice Input — Web Speech API ═══
 * Sprint 3+5+6: AI Voice Input for mobile POS
 * "Dodaj 3 bureka", "kava", "dva soka"
 * + Audio wave visualizer (background noise feedback)
 * + Confidence indicator
 * + Sprint 6: Low confidence fallback — "Jeste li mislili?"
 */
(function(){
  var _recognition = null;
  var _voiceActive = false;
  var _audioCtx = null;
  var _analyser = null;
  var _animFrame = null;
  var _micStream = null;

  window.toggleVoice = function() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      if (typeof fenixToast === 'function') fenixToast('Preglednik ne podržava glasovni unos', 'error');
      return;
    }
    if (_voiceActive) { stopVoice(); return; }

    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    _recognition = new SR();
    _recognition.lang = 'hr-HR';
    _recognition.interimResults = true;
    _recognition.maxAlternatives = 3;
    _recognition.continuous = false;

    _recognition.onstart = function() {
      _voiceActive = true;
      var btn = document.getElementById('voiceBtn');
      if (btn) btn.classList.add('recording');
      var overlay = document.getElementById('voiceResult');
      if (overlay) overlay.classList.add('show');
      _setVoice('Slušam...', 'Recite npr: "3 bureka" ili "kava"', '');
      if (navigator.vibrate) navigator.vibrate(20);
      _startAudioVisualizer();
    };

    _recognition.onresult = function(e) {
      var transcript = '';
      var confidence = 0;
      for (var i = e.resultIndex; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript;
        confidence = Math.max(confidence, e.results[i][0].confidence || 0);
      }
      var textEl = document.getElementById('voiceText');
      if (textEl) textEl.textContent = transcript;

      // Show confidence
      var confEl = document.getElementById('voiceConfidence');
      if (confEl && confidence > 0) {
        var pct = Math.round(confidence * 100);
        confEl.textContent = pct + '% sigurnost';
        confEl.style.color = pct >= 80 ? '#4ade80' : pct >= 50 ? '#facc15' : '#f87171';
        confEl.style.display = 'block';
      }

      if (e.results[e.resultIndex].isFinal) {
        _processVoiceCommand(transcript.trim(), confidence);
      }
    };

    _recognition.onerror = function(e) {
      var msg = 'Greška';
      if (e.error === 'no-speech') msg = 'Niste ništa rekli — previše buke?';
      else if (e.error === 'not-allowed') msg = 'Mikrofon nije dozvoljen';
      else if (e.error === 'network') msg = 'Nema mrežne veze za prepoznavanje';
      else if (e.error === 'aborted') msg = 'Prekinuto';
      else msg = 'Greška: ' + e.error;
      _setVoice(null, msg, 'error');
      setTimeout(stopVoice, 2500);
    };

    _recognition.onend = function() {
      // Don't auto-close if waiting for confirmation
      if (window._voicePendingBtn) return;
      stopVoice();
    };

    try {
      _recognition.start();
    } catch(e) {
      if (typeof fenixToast === 'function') fenixToast('Ne mogu pokrenuti mikrofon', 'error');
    }
  };

  // ── Audio Wave Visualizer ─────────────────────────────
  function _startAudioVisualizer() {
    var canvas = document.getElementById('voiceWave');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth * 2;
    canvas.height = canvas.offsetHeight * 2;

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
      _micStream = stream;
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var source = _audioCtx.createMediaStreamSource(stream);
      _analyser = _audioCtx.createAnalyser();
      _analyser.fftSize = 256;
      source.connect(_analyser);

      var bufLen = _analyser.frequencyBinCount;
      var data = new Uint8Array(bufLen);

      function draw() {
        if (!_voiceActive) return;
        _animFrame = requestAnimationFrame(draw);
        _analyser.getByteFrequencyData(data);

        var w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        // Volume level (average)
        var sum = 0;
        for (var i = 0; i < bufLen; i++) sum += data[i];
        var avg = sum / bufLen;

        // Draw waveform bars
        var barW = w / 32;
        var barGap = 2;
        for (var j = 0; j < 32; j++) {
          var idx = Math.floor(j * bufLen / 32);
          var val = data[idx] / 255;
          var barH = Math.max(4, val * h * 0.8);
          var x = j * (barW + barGap) + (w - 32 * (barW + barGap)) / 2;
          var y = (h - barH) / 2;

          // Color: gold when hearing voice, dim when quiet
          if (avg > 30) {
            ctx.fillStyle = 'rgba(201, 168, 76, ' + (0.4 + val * 0.6) + ')';
          } else {
            ctx.fillStyle = 'rgba(148, 163, 184, 0.3)';
          }
          ctx.fillRect(x, y, barW, barH);
        }

        // Noise indicator
        var noiseEl = document.getElementById('voiceNoise');
        if (noiseEl) {
          if (avg > 80) {
            noiseEl.textContent = '🔊 Bučno — govorite glasnije';
            noiseEl.style.color = '#facc15';
            noiseEl.style.display = 'block';
          } else if (avg > 30) {
            noiseEl.textContent = '🎤 Čujem vas';
            noiseEl.style.color = '#4ade80';
            noiseEl.style.display = 'block';
          } else {
            noiseEl.textContent = '🔇 Tiho — govorite';
            noiseEl.style.color = '#94a3b8';
            noiseEl.style.display = 'block';
          }
        }
      }
      draw();
    }).catch(function() {
      // Can't get audio stream for visualizer — voice still works via Speech API
    });
  }

  function _stopAudioVisualizer() {
    if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
    if (_micStream) { _micStream.getTracks().forEach(function(t){ t.stop(); }); _micStream = null; }
    if (_audioCtx) { try { _audioCtx.close(); } catch(e){} _audioCtx = null; }
    _analyser = null;
  }

  function stopVoice() {
    _voiceActive = false;
    if (_recognition) { try { _recognition.stop(); } catch(e){} _recognition = null; }
    var btn = document.getElementById('voiceBtn');
    if (btn) btn.classList.remove('recording');
    _stopAudioVisualizer();
    setTimeout(function() {
      var overlay = document.getElementById('voiceResult');
      if (overlay) overlay.classList.remove('show');
      var confEl = document.getElementById('voiceConfidence');
      if (confEl) confEl.style.display = 'none';
      var noiseEl = document.getElementById('voiceNoise');
      if (noiseEl) noiseEl.style.display = 'none';
    }, 1800);
  }

  function _setVoice(text, status, statusClass) {
    if (text !== null) {
      var el = document.getElementById('voiceText');
      if (el) el.textContent = text;
    }
    var sEl = document.getElementById('voiceStatus');
    if (sEl) {
      if (status) sEl.textContent = status;
      sEl.className = 'voice-status' + (statusClass ? ' ' + statusClass : '');
    }
  }

  function _processVoiceCommand(text, confidence) {
    if (!text) { _setVoice('Ništa prepoznato', 'Pokušajte ponovo', 'error'); return; }

    var words = text.toLowerCase().replace(/[.,!?]/g, '').split(/\s+/);
    var qty = 1;
    var searchTerm = text.toLowerCase().replace(/[.,!?]/g, '');

    var numWords = {
      'jedan':1,'jedna':1,'jedno':1,'dva':2,'dvije':2,'tri':3,
      'četiri':4,'cetiri':4,'pet':5,'šest':6,'sest':6,'sedam':7,
      'osam':8,'devet':9,'deset':10,'jedanaest':11,'dvanaest':12,
      'trinaest':13,'dvadeset':20,'trideset':30
    };

    if (words.length > 1) {
      var firstWord = words[0];
      // "dodaj/stavi" prefix
      if (firstWord === 'dodaj' || firstWord === 'stavi' || firstWord === 'daj') {
        words = words.slice(1);
        firstWord = words[0] || '';
      }
      if (!isNaN(parseInt(firstWord)) && parseInt(firstWord) > 0 && parseInt(firstWord) <= 999) {
        qty = parseInt(firstWord);
        searchTerm = words.slice(1).join(' ');
      } else if (numWords[firstWord]) {
        qty = numWords[firstWord];
        searchTerm = words.slice(1).join(' ');
      } else {
        searchTerm = words.join(' ');
      }
    }

    searchTerm = searchTerm.trim();
    if (!searchTerm) { _setVoice(null, 'Nisam razumio artikl', 'error'); return; }

    _setVoice(null, 'Tražim: "' + searchTerm + '" × ' + qty, '');

    // 1. Exact match
    var found = _findInGrid(searchTerm, qty, confidence);
    if (found) return;

    // 2. Fuzzy match (Croatian declension stem)
    found = _findFuzzyInGrid(searchTerm, qty, confidence);
    if (found) return;

    // 3. Fallback: search input
    var searchInput = document.getElementById('prodSearch');
    if (searchInput) {
      searchInput.value = searchTerm;
      searchInput.dispatchEvent(new Event('input', {bubbles: true}));
      _setVoice(null, 'Pretražujem: "' + searchTerm + '"', '');
      if (typeof fenixToast === 'function') fenixToast('🎤 Pretraga: "' + searchTerm + '"', 'info');
    } else {
      _setVoice(null, 'Artikl "' + searchTerm + '" nije pronađen', 'error');
    }
  }

  function _findInGrid(term, qty, confidence) {
    var prodButtons = document.querySelectorAll('#prodGrid .prod-btn');
    var bestMatch = null;
    var bestScore = 0;
    for (var i = 0; i < prodButtons.length; i++) {
      var btn = prodButtons[i];
      if (btn.style.display === 'none') continue;
      var name = (btn.dataset.name || btn.querySelector('.prod-name')?.textContent || '').toLowerCase();
      if (!name) continue;
      if (name === term) { bestMatch = btn; bestScore = 100; break; }
      if (name.includes(term)) {
        var score = 80 - Math.abs(name.length - term.length);
        if (score > bestScore) { bestMatch = btn; bestScore = score; }
      }
      if (term.includes(name)) {
        var score2 = 60;
        if (score2 > bestScore) { bestMatch = btn; bestScore = score2; }
      }
    }
    if (bestMatch && bestScore >= 50) {
      // Sprint 6: Low confidence fallback — ask for confirmation
      if (confidence < 0.5 && bestMatch) {
        var matchName = bestMatch.dataset.name || bestMatch.querySelector('.prod-name')?.textContent || '?';
        _showVoiceConfirm(matchName, qty, bestMatch);
        return true;
      }
      _clickProduct(bestMatch, qty);
      return true;
    }
    return false;
  }

  function _findFuzzyInGrid(term, qty, confidence) {
    var prodButtons = document.querySelectorAll('#prodGrid .prod-btn');
    var termWords = term.split(/\s+/);
    var bestMatch = null;
    var bestScore = 0;
    for (var i = 0; i < prodButtons.length; i++) {
      var btn = prodButtons[i];
      if (btn.style.display === 'none') continue;
      var name = (btn.dataset.name || btn.querySelector('.prod-name')?.textContent || '').toLowerCase();
      if (!name) continue;
      var score = 0;
      for (var j = 0; j < termWords.length; j++) {
        if (termWords[j].length < 2) continue;
        var stem = termWords[j].substring(0, Math.min(termWords[j].length, Math.max(3, termWords[j].length - 2)));
        if (name.includes(stem)) score += 30;
      }
      if (score > bestScore) { bestMatch = btn; bestScore = score; }
    }
    if (bestMatch && bestScore >= 25) {
      // Sprint 6: Low confidence fallback — ask for confirmation
      if (confidence < 0.5 && bestMatch) {
        var matchName = bestMatch.dataset.name || bestMatch.querySelector('.prod-name')?.textContent || '?';
        _showVoiceConfirm(matchName, qty, bestMatch);
        return true;
      }
      _clickProduct(bestMatch, qty);
      return true;
    }
    return false;
  }

  // ── Sprint 6: Voice Confirmation for low confidence ──────────
  function _showVoiceConfirm(name, qty, btn) {
    var textEl = document.getElementById('voiceText');
    if (textEl) textEl.innerHTML = 'Jeste li mislili:<br><strong style="color:#c9a84c;font-size:1.5rem">' + qty + '× ' + name + '</strong>?';
    var statusEl = document.getElementById('voiceStatus');
    if (statusEl) {
      statusEl.innerHTML = '<button onclick="_voiceConfirmYes()" style="background:#c9a84c;color:#000;border:none;padding:8px 24px;border-radius:8px;font-weight:700;margin-right:8px;font-size:1rem;cursor:pointer">DA ✓</button>' +
        '<button onclick="_voiceConfirmNo()" style="background:rgba(255,255,255,.1);color:#94a3b8;border:1px solid rgba(255,255,255,.2);padding:8px 24px;border-radius:8px;font-weight:600;font-size:1rem;cursor:pointer">NE ✕</button>';
      statusEl.className = 'voice-status';
    }
    window._voicePendingBtn = btn;
    window._voicePendingQty = qty;
    // Don't auto-close overlay — stop recognition but keep overlay visible
    if (_recognition) { try { _recognition.stop(); } catch(e){} }
  }

  window._voiceConfirmYes = function() {
    if (window._voicePendingBtn) {
      _clickProduct(window._voicePendingBtn, window._voicePendingQty || 1);
    }
    window._voicePendingBtn = null;
    window._voicePendingQty = null;
    stopVoice();
  };

  window._voiceConfirmNo = function() {
    window._voicePendingBtn = null;
    window._voicePendingQty = null;
    _setVoice('Pokušajte ponovo', 'Kliknite 🎤 za novi unos', '');
    setTimeout(stopVoice, 1500);
  };

  function _clickProduct(btn, qty) {
    var name = btn.dataset.name || btn.querySelector('.prod-name')?.textContent || '?';
    for (var j = 0; j < qty; j++) {
      if (typeof window.addProduct === 'function') {
        window.addProduct(btn, true);
      } else {
        btn.click();
      }
    }
    _setVoice(null, '✓ Dodano: ' + qty + '× ' + name, 'success');
    if (navigator.vibrate) navigator.vibrate([10, 50, 10]);
    if (typeof fenixToast === 'function') fenixToast('🎤 ' + qty + '× ' + name, 'success');
  }

})();
