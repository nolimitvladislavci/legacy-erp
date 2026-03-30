/* ═══ POS Voice Input — Web Speech API ═══
 * Sprint 3: AI Voice Input for mobile POS
 * "Dodaj 3 bureka", "kava", "dva soka"
 */
(function(){
  var _recognition = null;
  var _voiceActive = false;

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
    _recognition.maxAlternatives = 1;
    _recognition.continuous = false;

    _recognition.onstart = function() {
      _voiceActive = true;
      var btn = document.getElementById('voiceBtn');
      if (btn) btn.classList.add('recording');
      var overlay = document.getElementById('voiceResult');
      if (overlay) overlay.classList.add('show');
      _setVoice('Slušam...', 'Recite npr: "3 bureka" ili "kava"', '');
      if (navigator.vibrate) navigator.vibrate(20);
    };

    _recognition.onresult = function(e) {
      var transcript = '';
      for (var i = e.resultIndex; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript;
      }
      var textEl = document.getElementById('voiceText');
      if (textEl) textEl.textContent = transcript;

      if (e.results[e.resultIndex].isFinal) {
        _processVoiceCommand(transcript.trim());
      }
    };

    _recognition.onerror = function(e) {
      var msg = 'Greška';
      if (e.error === 'no-speech') msg = 'Niste ništa rekli';
      else if (e.error === 'not-allowed') msg = 'Mikrofon nije dozvoljen';
      else if (e.error === 'network') msg = 'Nema mrežne veze';
      else msg = 'Greška: ' + e.error;
      _setVoice(null, msg, 'error');
      setTimeout(stopVoice, 2000);
    };

    _recognition.onend = function() { stopVoice(); };

    try {
      _recognition.start();
    } catch(e) {
      if (typeof fenixToast === 'function') fenixToast('Ne mogu pokrenuti mikrofon', 'error');
    }
  };

  function stopVoice() {
    _voiceActive = false;
    if (_recognition) { try { _recognition.stop(); } catch(e){} _recognition = null; }
    var btn = document.getElementById('voiceBtn');
    if (btn) btn.classList.remove('recording');
    setTimeout(function() {
      var overlay = document.getElementById('voiceResult');
      if (overlay) overlay.classList.remove('show');
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

  function _processVoiceCommand(text) {
    if (!text) { _setVoice('Ništa prepoznato', 'Pokušajte ponovo', 'error'); return; }

    // Parse: "3 bureka", "dva bureka", "kava", "burek sir"
    var words = text.toLowerCase().replace(/[.,!?]/g, '').split(/\s+/);
    var qty = 1;
    var searchTerm = text.toLowerCase().replace(/[.,!?]/g, '');

    // Croatian number words
    var numWords = {
      'jedan':1,'jedna':1,'jedno':1,
      'dva':2,'dvije':2,
      'tri':3,
      'četiri':4,'cetiri':4,
      'pet':5,
      'šest':6,'sest':6,
      'sedam':7,
      'osam':8,
      'devet':9,
      'deset':10,
      'jedanaest':11,'dvanaest':12,'trinaest':13,
      'dvadeset':20
    };

    // Extract quantity from start of phrase
    if (words.length > 1) {
      var firstWord = words[0];
      if (!isNaN(parseInt(firstWord)) && parseInt(firstWord) > 0 && parseInt(firstWord) <= 999) {
        qty = parseInt(firstWord);
        searchTerm = words.slice(1).join(' ');
      } else if (numWords[firstWord]) {
        qty = numWords[firstWord];
        searchTerm = words.slice(1).join(' ');
      }
    }

    // Also handle "dodaj X Y" pattern
    if (words[0] === 'dodaj' || words[0] === 'stavi') {
      words = words.slice(1);
      if (words.length > 1) {
        var w = words[0];
        if (!isNaN(parseInt(w)) && parseInt(w) > 0) {
          qty = parseInt(w);
          searchTerm = words.slice(1).join(' ');
        } else if (numWords[w]) {
          qty = numWords[w];
          searchTerm = words.slice(1).join(' ');
        } else {
          searchTerm = words.join(' ');
        }
      } else if (words.length === 1) {
        searchTerm = words[0];
      }
    }

    searchTerm = searchTerm.trim();
    if (!searchTerm) { _setVoice(null, 'Nisam razumio artikl', 'error'); return; }

    _setVoice(null, 'Tražim: "' + searchTerm + '" × ' + qty, '');

    // 1. Try exact match in visible product buttons
    var found = _findInGrid(searchTerm, qty);
    if (found) return;

    // 2. Try fuzzy match (partial words)
    found = _findFuzzyInGrid(searchTerm, qty);
    if (found) return;

    // 3. Fallback: put in search input and let user pick
    var searchInput = document.getElementById('prodSearch');
    if (searchInput) {
      searchInput.value = searchTerm;
      searchInput.dispatchEvent(new Event('input', {bubbles: true}));
      _setVoice(null, 'Pretražujem: "' + searchTerm + '"', '');
      if (typeof fenixToast === 'function') fenixToast('Glasovna pretraga: "' + searchTerm + '"', 'info');
    } else {
      _setVoice(null, 'Artikl "' + searchTerm + '" nije pronađen', 'error');
    }
  }

  function _findInGrid(term, qty) {
    var prodButtons = document.querySelectorAll('#prodGrid .prod-btn');
    var bestMatch = null;
    var bestScore = 0;

    for (var i = 0; i < prodButtons.length; i++) {
      var btn = prodButtons[i];
      if (btn.style.display === 'none') continue;
      var name = (btn.dataset.name || btn.querySelector('.prod-name')?.textContent || '').toLowerCase();
      if (!name) continue;

      // Exact match
      if (name === term) { bestMatch = btn; bestScore = 100; break; }
      // Name contains term
      if (name.includes(term)) {
        var score = 80 - Math.abs(name.length - term.length);
        if (score > bestScore) { bestMatch = btn; bestScore = score; }
      }
      // Term contains name
      if (term.includes(name)) {
        var score2 = 60;
        if (score2 > bestScore) { bestMatch = btn; bestScore = score2; }
      }
    }

    if (bestMatch && bestScore >= 50) {
      _clickProduct(bestMatch, qty);
      return true;
    }
    return false;
  }

  function _findFuzzyInGrid(term, qty) {
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
        // Check if first 3+ chars match (handles Croatian declension)
        var stem = termWords[j].substring(0, Math.min(termWords[j].length, Math.max(3, termWords[j].length - 2)));
        if (name.includes(stem)) score += 30;
      }
      if (score > bestScore) { bestMatch = btn; bestScore = score; }
    }

    if (bestMatch && bestScore >= 25) {
      _clickProduct(bestMatch, qty);
      return true;
    }
    return false;
  }

  function _clickProduct(btn, qty) {
    var name = btn.dataset.name || btn.querySelector('.prod-name')?.textContent || '?';
    for (var j = 0; j < qty; j++) {
      if (typeof window.addProduct === 'function') {
        window.addProduct(btn);
      } else {
        btn.click();
      }
    }
    _setVoice(null, '✓ Dodano: ' + qty + '× ' + name, 'success');
    if (navigator.vibrate) navigator.vibrate([10, 50, 10]);
    if (typeof fenixToast === 'function') fenixToast('🎤 ' + qty + '× ' + name, 'success');
  }

})();
