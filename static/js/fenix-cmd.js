/**
 * fenix-cmd.js — Fenix Command Center
 *
 * Globalno sučelje: tekst + glas + kamera + chat + trending
 * Tri stvari iz budućnosti:
 *   1. AI intent → prijedlog kreiranja (backend DeepSeek)
 *   2. Audit security — svaki search logiran server-side
 *   3. Trending intelligence — shared company knowledge
 */
(function () {
  'use strict';

  /* ─── STATE ──────────────────────────────────────────────────────────── */
  var state = {
    open: false,
    mode: 'search',      // 'search' | 'chat'
    query: '',
    results: [],
    trending: [],
    chatHistory: [],     // [{role,content,results,actions}]
    sessionId: _genSession(),
    voiceActive: false,
    cameraActive: false,
    searchTimer: null,
    selectedIdx: -1,
  };

  function _genSession() {
    return 'cmd_' + Math.random().toString(36).substr(2, 16);
  }

  /* ─── DOM ────────────────────────────────────────────────────────────── */
  function $id(id) { return document.getElementById(id); }

  var OVERLAY, BOX, INPUT, RESULTS, TRENDING_WRAP, CHAT_WRAP,
      CHAT_MESSAGES, CHAT_INPUT, BTN_VOICE, BTN_CAMERA, BTN_CHAT,
      BTN_BACK, AI_SUGGEST;

  function _initDOM() {
    OVERLAY       = $id('fcCmdOverlay');
    BOX           = $id('fcCmdBox');
    INPUT         = $id('fcCmdInput');
    RESULTS       = $id('fcCmdResults');
    TRENDING_WRAP = $id('fcCmdTrending');
    CHAT_WRAP     = $id('fcCmdChatWrap');
    CHAT_MESSAGES = $id('fcChatMessages');
    CHAT_INPUT    = $id('fcChatInput');
    BTN_VOICE     = $id('fcBtnVoice');
    BTN_CAMERA    = $id('fcBtnCamera');
    BTN_CHAT      = $id('fcBtnChat');
    BTN_BACK      = $id('fcBtnBack');
    AI_SUGGEST    = $id('fcAiSuggest');

    if (!OVERLAY) return false;

    // Text input events
    INPUT.addEventListener('input', _onQueryInput);
    INPUT.addEventListener('keydown', _onInputKey);

    // Buttons
    BTN_VOICE.addEventListener('click', _toggleVoice);
    BTN_CAMERA.addEventListener('click', _toggleCamera);
    BTN_CHAT.addEventListener('click', _switchToChat);
    BTN_BACK.addEventListener('click', _switchToSearch);
    if (CHAT_INPUT) {
      CHAT_INPUT.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _sendChat(); }
      });
    }
    $id('fcChatSend').addEventListener('click', _sendChat);

    // Overlay click close
    OVERLAY.addEventListener('click', function (e) {
      if (e.target === OVERLAY) _close();
    });

    // Global keyboard
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        state.open ? _close() : _open();
      }
      if (e.key === 'Escape' && state.open) _close();
    });

    return true;
  }

  /* ─── OPEN / CLOSE ───────────────────────────────────────────────────── */
  function _open() {
    if (!OVERLAY) _initDOM();
    state.open = true;
    OVERLAY.classList.add('fc-open');
    setTimeout(function () { INPUT.focus(); }, 100);
    _loadTrending();
    state.selectedIdx = -1;
  }

  function _close() {
    state.open = false;
    OVERLAY.classList.remove('fc-open');
    _stopVoice();
    _stopCamera();
  }

  window.openCmdPalette = _open;
  window.closeCmdPalette = _close;

  /* ─── SEARCH ─────────────────────────────────────────────────────────── */
  function _onQueryInput() {
    var q = INPUT.value.trim();
    state.query = q;
    clearTimeout(state.searchTimer);

    if (!q) {
      _renderResults([]);
      _showTrending();
      _hideAiSuggest();
      return;
    }
    _hideTrending();
    state.searchTimer = setTimeout(function () {
      _doSearch(q, 'text');
    }, 280);
  }

  function _doSearch(q, src) {
    var url = '/api/cmd/search/?q=' + encodeURIComponent(q) + '&src=' + (src || 'text');
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.results  = data.results  || [];
        state.trending = data.trending || [];
        _renderResults(state.results);
        if (data.ai_suggestion) _showAiSuggest(data.ai_suggestion);
        else _hideAiSuggest();
      })
      .catch(function () { _renderResults([]); });
  }

  function _renderResults(results) {
    if (!results.length) {
      RESULTS.innerHTML = state.query
        ? '<div class="fc-empty">Nema rezultata za <strong>' + _esc(state.query) + '</strong></div>'
        : '';
      return;
    }
    var html = '';
    results.forEach(function (r, i) {
      html += '<a class="fc-result-item" href="' + _esc(r.url) + '" data-idx="' + i + '">' +
        '<span class="fc-result-icon"><i class="fas ' + _esc(r.icon || 'fa-file') + '"></i></span>' +
        '<span class="fc-result-body">' +
          '<span class="fc-result-title">' + _esc(r.title) + '</span>' +
          (r.subtitle ? '<span class="fc-result-sub">' + _esc(r.subtitle) + '</span>' : '') +
        '</span>' +
        '<span class="fc-result-type">' + _esc(r.type) + '</span>' +
        '</a>';
    });
    RESULTS.innerHTML = html;
    state.selectedIdx = -1;
  }

  /* ─── TRENDING (Budućnost 3 — Network Effect) ───────────────────────── */
  function _loadTrending() {
    fetch('/api/cmd/trending/', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.trending = data.trending || [];
        _renderTrending(state.trending);
      })
      .catch(function () {});
  }

  function _renderTrending(trending) {
    if (!trending || !trending.length) { TRENDING_WRAP.style.display = 'none'; return; }
    var chips = trending.map(function (t) {
      return '<button class="fc-trend-chip" onclick="window.fcSearchTrend(\'' + _esc(t) + '\')">' +
        '<i class="fas fa-fire-alt"></i> ' + _esc(t) + '</button>';
    }).join('');
    TRENDING_WRAP.innerHTML =
      '<div class="fc-trend-label"><i class="fas fa-users"></i> Ove sedmice vaši kolege traže:</div>' +
      '<div class="fc-trend-chips">' + chips + '</div>';
    TRENDING_WRAP.style.display = 'block';
  }

  window.fcSearchTrend = function (q) {
    INPUT.value = q;
    state.query = q;
    _hideTrending();
    _doSearch(q, 'text');
    INPUT.focus();
  };

  function _showTrending() {
    if (state.trending.length) TRENDING_WRAP.style.display = 'block';
  }
  function _hideTrending() { TRENDING_WRAP.style.display = 'none'; }

  /* ─── AI SUGGEST (Budućnost 1 — DeepSeek intent) ───────────────────── */
  function _showAiSuggest(sug) {
    AI_SUGGEST.innerHTML =
      '<i class="fas ' + _esc(sug.icon) + '"></i>' +
      '<span>AI prijedlog: <strong>' + _esc(sug.label) + '</strong></span>' +
      '<a class="fc-suggest-btn" href="' + _esc(sug.url) + '">Kreiraj →</a>';
    AI_SUGGEST.style.display = 'flex';
  }
  function _hideAiSuggest() { AI_SUGGEST.style.display = 'none'; }

  /* ─── KEYBOARD NAV ───────────────────────────────────────────────────── */
  function _onInputKey(e) {
    var items = RESULTS.querySelectorAll('.fc-result-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      state.selectedIdx = Math.min(state.selectedIdx + 1, items.length - 1);
      _highlightItem(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      state.selectedIdx = Math.max(state.selectedIdx - 1, -1);
      _highlightItem(items);
    } else if (e.key === 'Enter' && state.selectedIdx >= 0) {
      var sel = items[state.selectedIdx];
      if (sel) { window.location.href = sel.getAttribute('href'); }
    }
  }

  function _highlightItem(items) {
    items.forEach(function (el, i) {
      el.classList.toggle('fc-selected', i === state.selectedIdx);
    });
    if (items[state.selectedIdx])
      items[state.selectedIdx].scrollIntoView({ block: 'nearest' });
  }

  /* ─── VOICE (Glas → tekst → search) ─────────────────────────────────── */
  var _recognition = null;

  function _toggleVoice() {
    if (state.voiceActive) { _stopVoice(); return; }
    _startVoice();
  }

  function _startVoice() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { _showToast('Preglednik ne podržava prepoznavanje govora'); return; }

    _recognition = new SR();
    _recognition.continuous = false;
    _recognition.interimResults = true;
    _recognition.lang = document.documentElement.lang || 'hr-HR';

    _recognition.onstart = function () {
      state.voiceActive = true;
      BTN_VOICE.classList.add('fc-active');
      BTN_VOICE.innerHTML = '<i class="fas fa-stop"></i>';
      INPUT.placeholder = '🎤 Slušam...';
    };
    _recognition.onresult = function (e) {
      var transcript = '';
      for (var i = e.resultIndex; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript;
      }
      INPUT.value = transcript;
      state.query = transcript;
      if (e.results[e.resultIndex].isFinal) {
        _doSearch(transcript, 'voice');
        _stopVoice();
      }
    };
    _recognition.onerror = function (e) {
      _stopVoice();
      _showToast('Greška mikrofona: ' + e.error);
    };
    _recognition.onend = _stopVoice;
    _recognition.start();
  }

  function _stopVoice() {
    state.voiceActive = false;
    if (_recognition) { try { _recognition.stop(); } catch (e) {} _recognition = null; }
    BTN_VOICE.classList.remove('fc-active');
    BTN_VOICE.innerHTML = '<i class="fas fa-microphone"></i>';
    INPUT.placeholder = 'Pretraži ili pitaj AI...';
  }

  /* ─── CAMERA (Slika → OCR → search) ─────────────────────────────────── */
  var _stream = null, _videoEl = null;

  function _toggleCamera() {
    if (state.cameraActive) { _stopCamera(); return; }
    _startCamera();
  }

  function _startCamera() {
    var wrap = $id('fcCameraWrap');
    if (!wrap) return;

    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then(function (stream) {
        _stream = stream;
        state.cameraActive = true;
        BTN_CAMERA.classList.add('fc-active');

        _videoEl = document.createElement('video');
        _videoEl.srcObject = stream;
        _videoEl.autoplay = true;
        _videoEl.playsInline = true;
        _videoEl.style.cssText = 'width:100%;border-radius:8px;max-height:180px;object-fit:cover;';

        var captureBtn = document.createElement('button');
        captureBtn.className = 'fc-capture-btn';
        captureBtn.innerHTML = '<i class="fas fa-camera"></i> Snimi i pretraži';
        captureBtn.onclick = _captureAndOCR;

        wrap.innerHTML = '';
        wrap.appendChild(_videoEl);
        wrap.appendChild(captureBtn);
        wrap.style.display = 'block';
      })
      .catch(function (e) {
        _showToast('Kamera nedostupna: ' + e.message);
      });
  }

  function _captureAndOCR() {
    if (!_videoEl) return;
    var canvas = document.createElement('canvas');
    canvas.width  = _videoEl.videoWidth  || 640;
    canvas.height = _videoEl.videoHeight || 480;
    canvas.getContext('2d').drawImage(_videoEl, 0, 0);

    canvas.toBlob(function (blob) {
      var fd = new FormData();
      fd.append('file', blob, 'capture.jpg');
      fetch('/api/cmd/ocr/', {
        method: 'POST',
        body: fd,
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': _getCsrf() },
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.text) {
            INPUT.value = d.text;
            state.query = d.text;
            _doSearch(d.text, 'camera');
          }
          _stopCamera();
        })
        .catch(function () { _stopCamera(); });
    }, 'image/jpeg', 0.85);
  }

  function _stopCamera() {
    state.cameraActive = false;
    if (_stream) { _stream.getTracks().forEach(function (t) { t.stop(); }); _stream = null; }
    _videoEl = null;
    BTN_CAMERA.classList.remove('fc-active');
    var wrap = $id('fcCameraWrap');
    if (wrap) { wrap.innerHTML = ''; wrap.style.display = 'none'; }
  }

  /* ─── CHAT MODE ──────────────────────────────────────────────────────── */
  function _switchToChat() {
    state.mode = 'chat';
    BOX.classList.add('fc-chat-mode');
    BTN_CHAT.style.display = 'none';
    BTN_BACK.style.display = 'flex';
    RESULTS.style.display = 'none';
    TRENDING_WRAP.style.display = 'none';
    AI_SUGGEST.style.display = 'none';
    CHAT_WRAP.style.display = 'flex';
    if (state.chatHistory.length === 0) _addChatMsg('assistant', 'Zdravo! Kako vam mogu pomoći? Pitajte me o fakturama, dokumentima, partnerima ili tražite bilo što u sustavu.', [], []);
    setTimeout(function () { CHAT_INPUT.focus(); }, 100);
  }

  function _switchToSearch() {
    state.mode = 'search';
    BOX.classList.remove('fc-chat-mode');
    BTN_CHAT.style.display = 'flex';
    BTN_BACK.style.display = 'none';
    RESULTS.style.display = 'block';
    CHAT_WRAP.style.display = 'none';
    if (!state.query) _showTrending();
    setTimeout(function () { INPUT.focus(); }, 100);
  }

  function _sendChat() {
    var msg = CHAT_INPUT.value.trim();
    if (!msg) return;
    CHAT_INPUT.value = '';

    _addChatMsg('user', msg, [], []);

    var typingId = _addChatMsg('assistant', '...', [], []);
    var typingEl = document.querySelector('[data-msg-id="' + typingId + '"]');
    if (typingEl) typingEl.classList.add('fc-typing');

    fetch('/api/cmd/chat/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': _getCsrf(),
      },
      body: JSON.stringify({ message: msg, session_id: state.sessionId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (typingEl) typingEl.remove();
        _addChatMsg('assistant', data.reply, data.search_results || [], data.suggested_actions || []);
        if (data.session_id) state.sessionId = data.session_id;
      })
      .catch(function () {
        if (typingEl) typingEl.remove();
        _addChatMsg('assistant', 'Greška pri slanju. Pokušajte ponovo.', [], []);
      });
  }

  var _msgCounter = 0;
  function _addChatMsg(role, content, results, actions) {
    var id = 'fcmsg' + (++_msgCounter);
    state.chatHistory.push({ role: role, content: content });

    var html = '<div class="fc-chat-msg fc-msg-' + role + '" data-msg-id="' + id + '">' +
      '<div class="fc-msg-bubble">' + _esc(content).replace(/\n/g, '<br>') + '</div>';

    if (results && results.length) {
      html += '<div class="fc-msg-results">';
      results.forEach(function (r) {
        html += '<a class="fc-msg-result" href="' + _esc(r.url) + '">' +
          '<i class="fas ' + _esc(r.icon || 'fa-file') + '"></i> ' + _esc(r.title) + '</a>';
      });
      html += '</div>';
    }
    if (actions && actions.length) {
      html += '<div class="fc-msg-actions">';
      actions.forEach(function (a) {
        html += '<a class="fc-msg-action" href="' + _esc(a.url) + '">' +
          '<i class="fas ' + _esc(a.icon) + '"></i> ' + _esc(a.label) + '</a>';
      });
      html += '</div>';
    }
    html += '</div>';

    CHAT_MESSAGES.insertAdjacentHTML('beforeend', html);
    CHAT_MESSAGES.scrollTop = CHAT_MESSAGES.scrollHeight;
    return id;
  }

  /* ─── UTILS ──────────────────────────────────────────────────────────── */
  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function _getCsrf() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]') ||
             document.cookie.split(';').filter(function (c) { return c.includes('csrftoken'); });
    if (el && el.value) return el.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
  function _showToast(msg) {
    if (window.FenixToast) { window.FenixToast.show(msg, 'warning'); return; }
    alert(msg);
  }

  /* ─── BOOT ───────────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    _initDOM();
  });

})();
