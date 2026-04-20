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

/* ═══════════════════════════════════════════════════════════════════════════
   FENIX CMD v2 — 4 nadogradnje
   ═══════════════════════════════════════════════════════════════════════════ */

/* ── 1. PREDICTIVE PREFETCHER ─────────────────────────────────────────────── */

var FenixSearchPrefetcher = (function () {
  var cache = new Map();          // prefiks → [{module,title,url,...}]
  var pendingPrefixes = new Set();
  var prefetchTimer = null;

  /**
   * Poziva se svaki put kad korisnik tipka.
   * Predviđa sljedeća 2-3 slova i batch-fetcha u pozadini.
   */
  function schedule(query) {
    clearTimeout(prefetchTimer);
    if (!query || query.length < 2) return;

    prefetchTimer = setTimeout(function () {
      var predictions = _predictNextChars(query);
      var toFetch = predictions.filter(function (p) {
        return !cache.has(p) && !pendingPrefixes.has(p);
      });
      if (toFetch.length === 0) return;

      toFetch.forEach(function (p) { pendingPrefixes.add(p); });

      fetch('/api/cmd/prefetch/?prefixes=' + toFetch.map(encodeURIComponent).join(','), {
        credentials: 'same-origin',
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var pf = data.prefetched || {};
          Object.keys(pf).forEach(function (k) {
            cache.set(k, pf[k]);
            pendingPrefixes.delete(k);
          });
        })
        .catch(function () {
          toFetch.forEach(function (p) { pendingPrefixes.delete(p); });
        });
    }, 150);  // 150ms — prije debounce searcha (280ms)
  }

  function get(query) {
    return cache.get(query) || null;
  }

  function _predictNextChars(q) {
    // Generiraj 3 varijante: q + česti nastavci
    var suffixes = ['a', 'e', 'i', ' ', 'n', 'r', 't'];
    var predictions = [q];
    suffixes.slice(0, 3).forEach(function (s) {
      predictions.push(q + s);
    });
    return predictions.filter(function (p) { return p.length >= 2 && p.length <= 30; });
  }

  return { schedule: schedule, get: get };
})();

/* Zakači prefetcher na input */
document.addEventListener('DOMContentLoaded', function () {
  var inp = document.getElementById('fcCmdInput');
  if (!inp) return;
  inp.addEventListener('input', function () {
    FenixSearchPrefetcher.schedule(inp.value.trim());
  });
});

/* Patch _doSearch da provjeri prefetch cache PRIJE API poziva */
(function () {
  var _originalDoSearch = window._fcDoSearch;
  if (!_originalDoSearch) return;  // ako nije eksponiran, patch je inline u closure
})();
// Prefetch integracija — exponiraj za inline patch u closure
window.FenixPrefetcher = FenixSearchPrefetcher;


/* ── 2. CROSS-MODULE INTELLIGENCE PANEL ──────────────────────────────────── */

var FenixCrossModule = (function () {
  var _panel = null;
  var _activeQuery = '';

  function init() {
    // Kreiraj panel ako ne postoji
    if (document.getElementById('fcCrossPanel')) return;
    var panel = document.createElement('div');
    panel.id = 'fcCrossPanel';
    panel.className = 'fc-cross-panel';
    panel.style.cssText = [
      'display:none',
      'position:absolute',
      'left:calc(100% + 8px)',
      'top:0',
      'width:280px',
      'background:var(--bg-card,#1e2a3a)',
      'border:1px solid var(--border,#334155)',
      'border-radius:12px',
      'padding:12px',
      'box-shadow:0 8px 30px rgba(0,0,0,.4)',
      'z-index:10001',
      'max-height:400px',
      'overflow-y:auto',
    ].join(';');
    var box = document.getElementById('fcCmdBox');
    if (box) {
      box.style.position = 'relative';
      box.appendChild(panel);
    }
    _panel = panel;
  }

  function show(entityType, entityId, query) {
    init();
    if (!_panel) return;
    _activeQuery = query;

    var url = '/api/cmd/cross/?entity_type=' + encodeURIComponent(entityType) +
              '&entity_id=' + encodeURIComponent(entityId) +
              '&q=' + encodeURIComponent(query);

    _panel.innerHTML = '<div style="font-size:.7rem;color:#64748b;padding:4px 0">Učitavam veze...</div>';
    _panel.style.display = 'block';

    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.related || !data.related.length) { hide(); return; }
        var html = '<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--gold,#c9a84c);margin-bottom:8px">' +
          '<i class="fas fa-project-diagram"></i> Povezani zapisi</div>';
        if (data.summary) {
          html += '<div style="font-size:.72rem;color:#94a3b8;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,.06)">' +
            data.summary + '</div>';
        }
        data.related.forEach(function (r) {
          html += '<a href="' + r.url + '" style="display:flex;align-items:center;gap:8px;padding:5px 0;text-decoration:none;color:var(--text,#e2e8f0);font-size:.78rem;border-bottom:1px solid rgba(255,255,255,.04)">' +
            '<i class="fas ' + (r.icon || 'fa-file') + '" style="color:var(--gold,#c9a84c);width:14px"></i>' +
            '<span>' + r.title + '</span>' +
            '<span style="margin-left:auto;font-size:.6rem;color:#64748b">' + r.type + '</span>' +
            '</a>';
        });
        _panel.innerHTML = html;
      })
      .catch(hide);
  }

  function hide() {
    if (_panel) _panel.style.display = 'none';
  }

  return { show: show, hide: hide };
})();

/* Zakači hover na rezultate za cross-module */
document.addEventListener('mouseover', function (e) {
  var item = e.target.closest('.fc-result-item');
  if (!item) return;
  var module = item.getAttribute('data-module') || '';
  var eid    = item.getAttribute('data-eid') || '';
  var q      = (document.getElementById('fcCmdInput') || {}).value || '';
  if (eid && module) FenixCrossModule.show(module, eid, q);
});
document.addEventListener('mouseout', function (e) {
  var panel = document.getElementById('fcCrossPanel');
  if (!panel) return;
  if (!e.relatedTarget || (!e.relatedTarget.closest('.fc-result-item') && !e.relatedTarget.closest('#fcCrossPanel'))) {
    FenixCrossModule.hide();
  }
});


/* ── 3. LIVE COLLABORATION ────────────────────────────────────────────────── */

var FenixLiveCollab = (function () {
  var _timer    = null;
  var _lastQ    = '';
  var _banner   = null;

  function init() {
    if (document.getElementById('fcLiveBanner')) return;
    var b = document.createElement('div');
    b.id = 'fcLiveBanner';
    b.style.cssText = [
      'display:none',
      'padding:6px 16px',
      'background:rgba(22,163,74,.08)',
      'border-bottom:1px solid rgba(22,163,74,.2)',
      'font-size:.72rem',
      'color:#4ade80',
      'flex-shrink:0',
    ].join(';');
    var body = document.getElementById('fcCmdBody');
    if (body) body.parentNode.insertBefore(b, body);
    _banner = b;
  }

  function start() {
    init();
    _poll();
    _timer = setInterval(_poll, 8000);  // poll svakih 8s
  }

  function stop() {
    clearInterval(_timer);
    if (_banner) _banner.style.display = 'none';
  }

  function onQuery(q) {
    _lastQ = q;
    // Odmah publish (ne čekaj interval)
    if (q && q.length >= 2) _publish(q);
  }

  function _publish(q) {
    fetch('/api/cmd/live/?q=' + encodeURIComponent(q), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(_render)
      .catch(function () {});
  }

  function _poll() {
    fetch('/api/cmd/live/', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(_render)
      .catch(function () {});
  }

  function _render(data) {
    init();
    if (!_banner) return;
    var active = data.active || [];
    if (!active.length) { _banner.style.display = 'none'; return; }
    var parts = active.slice(0, 3).map(function (a) {
      return '<strong>' + _escH(a.username) + '</strong> traži <em>"' + _escH(a.query) + '"</em>';
    });
    _banner.innerHTML = '<i class="fas fa-circle" style="font-size:.4rem;animation:fc-pulse 1s infinite"></i> ' +
      'Sada aktivno: ' + parts.join(' · ');
    _banner.style.display = 'block';
  }

  function _escH(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  return { start: start, stop: stop, onQuery: onQuery };
})();

/* Integracija Live Collab s CMD otvaranjem */
var _origOpen  = window.openCmdPalette;
var _origClose = window.closeCmdPalette;
window.openCmdPalette = function () { _origOpen && _origOpen(); FenixLiveCollab.start(); document.dispatchEvent(new CustomEvent('fcOpen')); };
window.closeCmdPalette = function () { _origClose && _origClose(); FenixLiveCollab.stop(); document.dispatchEvent(new CustomEvent('fcClose')); };

/* Prati input za publish */
document.addEventListener('DOMContentLoaded', function () {
  var inp = document.getElementById('fcCmdInput');
  if (!inp) return;
  inp.addEventListener('input', function () {
    FenixLiveCollab.onQuery(inp.value.trim());
  });
});


/* ── 4. ZERO-RESULT DEEPSEEK PANEL ───────────────────────────────────────── */

var FenixZeroResult = (function () {
  var _container = null;
  var _loading   = false;
  var _lastQ     = '';
  var _debounce  = null;

  function init() {
    _container = document.getElementById('fcAiSuggest');
  }

  /**
   * Poziva se kad search vrati 0 rezultata i q >= 3 znaka.
   * Prikazuje loading, zatim pravi DeepSeek odgovor.
   */
  function trigger(q) {
    if (!q || q.length < 3 || _loading) return;
    if (q === _lastQ) return;

    _lastQ = q;
    clearTimeout(_debounce);
    _debounce = setTimeout(function () { _fetch(q); }, 600);  // 600ms delay
  }

  function clear() {
    _lastQ   = '';
    _loading = false;
    clearTimeout(_debounce);
    _hide();
  }

  function _fetch(q) {
    if (!_container) init();
    if (!_container) return;

    _loading = true;
    _showLoading(q);

    fetch('/api/cmd/zero/?q=' + encodeURIComponent(q), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _loading = false;
        if (!data.answer && (!data.actions || !data.actions.length)) { _hide(); return; }
        _showResult(data);
      })
      .catch(function () {
        _loading = false;
        _hide();
      });
  }

  function _showLoading(q) {
    if (!_container) return;
    _container.innerHTML = '<i class="fas fa-robot" style="animation:fc-pulse 1s infinite"></i>' +
      '<span>DeepSeek analizira <em>"' + _escH(q) + '"</em>...</span>';
    _container.style.display = 'flex';
    _container.style.background = 'rgba(124,58,237,.08)';
  }

  function _showResult(data) {
    if (!_container) return;
    var html = '<div style="flex:1">' +
      '<div style="font-size:.78rem;line-height:1.5;margin-bottom:6px">' +
        '<i class="fas fa-robot" style="color:#7c3aed;margin-right:4px"></i>' +
        _escH(data.answer) +
      '</div>';

    if (data.actions && data.actions.length) {
      html += '<div style="display:flex;flex-wrap:wrap;gap:6px">';
      data.actions.forEach(function (a) {
        html += '<a href="' + _escH(a.url) + '" class="fc-suggest-btn">' +
          '<i class="fas ' + _escH(a.icon || 'fa-arrow-right') + '"></i> ' +
          _escH(a.label) + '</a>';
      });
      html += '</div>';
    }

    if (data.confidence) {
      var pct = Math.round(data.confidence * 100);
      html += '<div style="font-size:.6rem;color:#64748b;margin-top:6px">Pouzdanost: ' + pct + '%</div>';
    }

    html += '</div>';
    _container.innerHTML = html;
    _container.style.display = 'flex';
    _container.style.flexDirection = 'column';
  }

  function _hide() {
    if (_container) _container.style.display = 'none';
  }

  function _escH(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  return { trigger: trigger, clear: clear };
})();

/* Zakači Zero-Result na search rezultate */
(function () {
  var _origFetch = window._fcInternalDoSearch;
  // Monkey-patch fetch results → ako 0 rezultata, triggeramo DeepSeek
  var inp = null;
  document.addEventListener('DOMContentLoaded', function () {
    inp = document.getElementById('fcCmdInput');
  });

  // Preklopi globalni event listener na rezultate
  document.addEventListener('fcResultsRendered', function (e) {
    var detail = e.detail || {};
    if (detail.count === 0 && detail.query && detail.query.length >= 3) {
      FenixZeroResult.trigger(detail.query);
    } else {
      FenixZeroResult.clear();
    }
  });
})();

/* Emituj custom event nakon renderanja rezultata */
(function () {
  var _orig = window._fcRenderResults;
  // Wrap renderResults da emituje event
  document.addEventListener('DOMContentLoaded', function () {
    var inp    = document.getElementById('fcCmdInput');
    var resEl  = document.getElementById('fcCmdResults');
    if (!resEl || !inp) return;

    // MutationObserver na #fcCmdResults
    var obs = new MutationObserver(function () {
      var q    = inp.value.trim();
      var count = resEl.querySelectorAll('.fc-result-item').length;
      document.dispatchEvent(new CustomEvent('fcResultsRendered', {
        detail: { count: count, query: q }
      }));
    });
    obs.observe(resEl, { childList: true });
  });
})();

/* Eksponiranje za konzolu/debug */
window.FenixCmd = {
  prefetcher: FenixSearchPrefetcher,
  crossModule: FenixCrossModule,
  liveCollab: FenixLiveCollab,
  zeroResult: FenixZeroResult,
};

/* ═══════════════════════════════════════════════════════════════════════════
   FenixTemporalPredictor — ZAKON 24 DAN 1 KORAK 1.3
   Prikazuje chipove "Tipično u ovo doba:" kada je input prazan.
   Nestaje čim korisnik počne tipkati. Klik na chip = instant search.
   ═══════════════════════════════════════════════════════════════════════════ */
var FenixTemporalPredictor = (function () {
  'use strict';

  var _loaded   = false;
  var _data     = null;  /* { personal, team, confidence, window_label, has_data } */
  var _chipBar  = null;
  var _visible  = false;

  /* Dohvati predikciju iz API-ja (jednom, cache 5min na serveru) */
  function _load() {
    if (_loaded) return;
    _loaded = true;
    fetch('/api/cmd/predict/', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.has_data) return;
        _data = d;
        _buildBar();
      })
      .catch(function () { /* silent — feature degradable */ });
  }

  /* Kreiraj chip bar ispod inputa (jednom) */
  function _buildBar() {
    var box = document.getElementById('fcCmdBox');
    if (!box || !_data) return;

    var bar = document.createElement('div');
    bar.id = 'fcPredictBar';
    bar.style.cssText = [
      'display:none',
      'padding:6px 16px 10px',
      'animation:fcFadeIn 0.25s ease',
    ].join(';');

    /* Label */
    var lbl = document.createElement('span');
    lbl.style.cssText = 'font-size:11px;color:#8b949e;margin-right:6px;';
    lbl.textContent = '🔮 Tipično ' + _data.window_label + ':';
    bar.appendChild(lbl);

    /* Chipovi — osobni najprije, zatim timski */
    var queries = _mergeUnique(_data.personal, _data.team).slice(0, 4);
    queries.forEach(function (q) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.style.cssText = [
        'display:inline-flex',
        'align-items:center',
        'gap:4px',
        'padding:3px 10px',
        'margin:0 4px 4px 0',
        'background:rgba(56,139,253,0.12)',
        'border:1px solid rgba(56,139,253,0.3)',
        'border-radius:20px',
        'color:#58a6ff',
        'font-size:12px',
        'cursor:pointer',
        'transition:background 0.15s',
      ].join(';');
      chip.textContent = q.length > 30 ? q.slice(0, 28) + '…' : q;
      chip.title = q;

      /* Označi osobne chipove s drugom bojom */
      if (_data.personal && _data.personal.includes(q)) {
        chip.style.background = 'rgba(63,185,80,0.12)';
        chip.style.borderColor = 'rgba(63,185,80,0.3)';
        chip.style.color = '#3fb950';
        chip.title = '👤 Tvoj upit · ' + q;
      }

      chip.addEventListener('mouseenter', function () {
        chip.style.background = 'rgba(56,139,253,0.22)';
      });
      chip.addEventListener('mouseleave', function () {
        chip.style.background = _data.personal && _data.personal.includes(q)
          ? 'rgba(63,185,80,0.12)'
          : 'rgba(56,139,253,0.12)';
      });
      chip.addEventListener('click', function () {
        var inp = document.getElementById('fcCmdInput');
        if (!inp) return;
        inp.value = q;
        inp.dispatchEvent(new Event('input', { bubbles: true }));
        inp.focus();
        hide();
      });
      bar.appendChild(chip);
    });

    /* Confidence tooltip ako < 50% */
    if (_data.confidence < 0.5) {
      var hint = document.createElement('span');
      hint.style.cssText = 'font-size:10px;color:#6e7681;margin-left:4px;';
      hint.textContent = '(manje podataka)';
      bar.appendChild(hint);
    }

    _chipBar = bar;

    /* Ubaci bar ispod input reda unutar fcCmdBox */
    var inputRow = box.querySelector('#fcCmdInput');
    if (inputRow && inputRow.parentNode) {
      inputRow.parentNode.insertBefore(bar, inputRow.nextSibling);
    } else {
      box.prepend(bar);
    }
  }

  /* Merge bez duplikata — personal first */
  function _mergeUnique(a, b) {
    var seen = {};
    var out = [];
    (a || []).concat(b || []).forEach(function (q) {
      if (!seen[q]) { seen[q] = true; out.push(q); }
    });
    return out;
  }

  function show() {
    if (!_chipBar || _visible) return;
    _chipBar.style.display = 'block';
    _visible = true;
  }

  function hide() {
    if (!_chipBar || !_visible) return;
    _chipBar.style.display = 'none';
    _visible = false;
  }

  /* Inicijalizacija — veži se na input events */
  function init() {
    document.addEventListener('DOMContentLoaded', function () {
      var inp = document.getElementById('fcCmdInput');
      if (!inp) return;

      /* Učitaj predikciju unaprijed */
      _load();

      /* Prikaži kad je input prazan i CMD otvoren */
      document.addEventListener('fcOpen', function () {
        if (!inp.value.trim()) show();
      });

      inp.addEventListener('input', function () {
        if (inp.value.trim().length > 0) {
          hide();
        } else {
          show();
        }
      });

      /* Sakrij kad se CMD zatvori */
      document.addEventListener('fcClose', function () {
        hide();
      });
    });
  }

  init();

  return { show: show, hide: hide, reload: function () { _loaded = false; _data = null; _load(); } };
})();

/* Ažuriraj debug namespace */
window.FenixCmd.temporalPredictor = FenixTemporalPredictor;

/* ═══════════════════════════════════════════════════════════════════════════
   ZAKON 24 DAN 2 — WCAG 2.1 AA Accessibility Enhancement
   KORAK 2.2: Focus trap + keyboard nav
   KORAK 2.3: High contrast + font size toggle
   KORAK 2.4: Screen reader live region
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ── KORAK 2.4: Screen reader announcements ─────────────────────────── */
  function _announce(msg) {
    var el = document.getElementById('fcSrAnnounce');
    if (!el) return;
    el.textContent = '';
    setTimeout(function () { el.textContent = msg; }, 50);  // reset → set triggers SR
  }

  /* Hook na rezultate — announce count */
  document.addEventListener('fcResultsRendered', function (e) {
    var d = e.detail || {};
    if (d.query) {
      var msg = d.count > 0
        ? 'Pronađeno ' + d.count + ' rezultata za ' + d.query
        : 'Nema rezultata za ' + d.query;
      _announce(msg);
    }
  });

  /* Announce CMD open/close */
  document.addEventListener('fcOpen', function () {
    _announce('Command Center otvoren. Unesite pojam za pretragu ili pitajte AI asistenta.');
  });
  document.addEventListener('fcClose', function () {
    _announce('Command Center zatvoren.');
  });

  /* Announce voice/camera state */
  document.addEventListener('DOMContentLoaded', function () {
    var btnVoice  = document.getElementById('fcBtnVoice');
    var btnCamera = document.getElementById('fcBtnCamera');

    if (btnVoice) {
      btnVoice.addEventListener('click', function () {
        var isPressed = btnVoice.getAttribute('aria-pressed') === 'true';
        btnVoice.setAttribute('aria-pressed', isPressed ? 'false' : 'true');
        _announce(isPressed ? 'Glasovna pretraga deaktivirana.' : 'Glasovna pretraga aktivirana. Govorite...');
      });
    }
    if (btnCamera) {
      btnCamera.addEventListener('click', function () {
        var isPressed = btnCamera.getAttribute('aria-pressed') === 'true';
        btnCamera.setAttribute('aria-pressed', isPressed ? 'false' : 'true');
        _announce(isPressed ? 'Kamera deaktivirana.' : 'Kamera aktivirana. Snimite dokument.');
      });
    }

    /* Aria-expanded na input kad ima rezultata */
    var inp     = document.getElementById('fcCmdInput');
    var results = document.getElementById('fcCmdResults');
    if (inp && results) {
      var obs = new MutationObserver(function () {
        var hasResults = results.children.length > 0;
        inp.setAttribute('aria-expanded', hasResults ? 'true' : 'false');
      });
      obs.observe(results, { childList: true });
    }
  });

  /* ── KORAK 2.2: Focus trap unutar dijaloga ──────────────────────────── */
  document.addEventListener('keydown', function (e) {
    var overlay = document.getElementById('fcCmdOverlay');
    if (!overlay || !overlay.classList.contains('fc-open')) return;
    if (e.key !== 'Tab') return;

    /* Skupi sve focusable elemente unutar CMD boxa */
    var box = document.getElementById('fcCmdBox');
    if (!box) return;
    var focusable = Array.from(
      box.querySelectorAll(
        'a[href], button:not([disabled]), input, textarea, select, [tabindex]:not([tabindex="-1"])'
      )
    ).filter(function (el) {
      return !el.closest('[style*="display:none"]') && !el.closest('[hidden]') &&
             getComputedStyle(el).display !== 'none';
    });

    if (!focusable.length) return;

    var first = focusable[0];
    var last  = focusable[focusable.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });

  /* ── KORAK 2.3: High contrast + font size toggle ────────────────────── */
  var A11Y_KEY = 'fenix_a11y';  /* localStorage key */

  function _loadA11yState() {
    try {
      var saved = JSON.parse(localStorage.getItem(A11Y_KEY) || '{}');
      if (saved.hc) document.body.setAttribute('data-a11y',
        (document.body.getAttribute('data-a11y') || '') + ' hc');
      if (saved.lg) document.body.setAttribute('data-a11y',
        (document.body.getAttribute('data-a11y') || '') + ' lg');
    } catch (e) {}
  }

  function _toggleA11y(mode) {
    var current = (document.body.getAttribute('data-a11y') || '').split(/\s+/).filter(Boolean);
    var idx = current.indexOf(mode);
    if (idx > -1) { current.splice(idx, 1); }
    else { current.push(mode); }
    document.body.setAttribute('data-a11y', current.join(' '));

    /* Persist */
    try {
      var state = JSON.parse(localStorage.getItem(A11Y_KEY) || '{}');
      state[mode] = current.includes(mode);
      localStorage.setItem(A11Y_KEY, JSON.stringify(state));
    } catch (e) {}

    /* Update button pressed state */
    var btn = document.getElementById(mode === 'hc' ? 'fcA11yContrast' : 'fcA11yFont');
    if (btn) btn.setAttribute('aria-pressed', current.includes(mode) ? 'true' : 'false');

    /* Announce */
    if (mode === 'hc') {
      _announce(current.includes('hc') ? 'Visoki kontrast aktiviran.' : 'Visoki kontrast deaktiviran.');
    } else {
      _announce(current.includes('lg') ? 'Veći font aktiviran.' : 'Standardni font vraćen.');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    _loadA11yState();

    var btnFont     = document.getElementById('fcA11yFont');
    var btnContrast = document.getElementById('fcA11yContrast');

    if (btnFont) {
      /* Initial state */
      var initA11y = (document.body.getAttribute('data-a11y') || '').split(/\s+/);
      btnFont.setAttribute('aria-pressed', initA11y.includes('lg') ? 'true' : 'false');
      btnFont.addEventListener('click', function () { _toggleA11y('lg'); });
    }
    if (btnContrast) {
      var initA11y2 = (document.body.getAttribute('data-a11y') || '').split(/\s+/);
      btnContrast.setAttribute('aria-pressed', initA11y2.includes('hc') ? 'true' : 'false');
      btnContrast.addEventListener('click', function () { _toggleA11y('hc'); });
    }
  });

  /* Keyboard shortcut: Alt+C = high contrast, Alt+F = font toggle */
  document.addEventListener('keydown', function (e) {
    if (!e.altKey) return;
    if (e.key === 'c' || e.key === 'C') { e.preventDefault(); _toggleA11y('hc'); }
    if (e.key === 'f' || e.key === 'F') { e.preventDefault(); _toggleA11y('lg'); }
  });

})();

/* ═══════════════════════════════════════════════════════════════════════════
   FenixGoodMorning — ZAKON 25 DAN 1
   Proaktivni briefing: prikazuje hitne stavke kad je CMD prazan.
   Dismiss po stavci (localStorage, reset svaki dan).
   ═══════════════════════════════════════════════════════════════════════════ */
var FenixGoodMorning = (function () {
  'use strict';

  var _loaded   = false;
  var _data     = null;
  var _panel    = null;
  var _todayKey = 'gm_dismiss_' + new Date().toISOString().slice(0, 10);

  function _getDismissed() {
    try { return JSON.parse(localStorage.getItem(_todayKey) || '[]'); }
    catch (e) { return []; }
  }
  function _dismiss(key) {
    var list = _getDismissed();
    if (!list.includes(key)) { list.push(key); }
    try { localStorage.setItem(_todayKey, JSON.stringify(list)); }
    catch (e) {}
  }

  function _load() {
    if (_loaded) return;
    _loaded = true;
    fetch('/api/cmd/morning/', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.items || !d.items.length) return;
        _data = d;
        _buildPanel();
      })
      .catch(function () {});
  }

  function _buildPanel() {
    var body = document.getElementById('fcCmdBody');
    if (!body || !_data) return;

    var dismissed = _getDismissed();
    var visible = _data.items.filter(function (it) {
      return !dismissed.includes(it.dismiss_key);
    });
    if (!visible.length) return;

    var panel = document.createElement('div');
    panel.id = 'fcGoodMorning';
    panel.style.cssText = [
      'padding:12px 16px',
      'border-bottom:1px solid rgba(255,255,255,.06)',
      'animation:fcFadeIn .3s ease',
    ].join(';');

    /* Greeting header */
    var hdr = document.createElement('div');
    hdr.style.cssText = 'font-size:.8rem;font-weight:600;color:#94a3b8;margin-bottom:10px;display:flex;align-items:center;gap:6px';
    hdr.innerHTML = '<span>' + _escH(_data.greeting) + '</span>' +
      (_data.urgent > 0
        ? '<span style="background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3);border-radius:20px;padding:1px 8px;font-size:.65rem">' + _data.urgent + ' hitno</span>'
        : '');
    panel.appendChild(hdr);

    /* Items */
    visible.slice(0, 4).forEach(function (item) {
      var row = document.createElement('div');
      row.style.cssText = [
        'display:flex',
        'align-items:flex-start',
        'gap:10px',
        'padding:8px 10px',
        'margin-bottom:4px',
        'background:' + _priorityBg(item.priority),
        'border:1px solid ' + _priorityBorder(item.priority),
        'border-radius:8px',
        'position:relative',
      ].join(';');

      var textCol = document.createElement('div');
      textCol.style.cssText = 'flex:1;min-width:0';
      textCol.innerHTML =
        '<div style="font-size:.78rem;font-weight:600;color:#e2e8f0;display:flex;align-items:center;gap:6px">' +
          '<span>' + _escH(item.emoji) + '</span>' +
          '<span style="background:rgba(255,255,255,.06);border-radius:4px;padding:0 6px;font-size:.6rem;color:#94a3b8">' + _escH(item.label) + '</span>' +
          '<span>' + _escH(item.title) + '</span>' +
        '</div>' +
        (item.subtitle
          ? '<div style="font-size:.7rem;color:#64748b;margin-top:2px">' + _escH(item.subtitle) + '</div>'
          : '') +
        '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">' +
          (item.actions || []).slice(0, 2).map(function (a) {
            return '<a href="' + _escH(a.url) + '" style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;color:#94a3b8;font-size:.7rem;text-decoration:none;transition:.15s" onmouseover="this.style.color=\'#e2e8f0\'" onmouseout="this.style.color=\'#94a3b8\'">' +
              '<i class="fas ' + _escH(a.icon || 'fa-arrow-right') + '" style="font-size:.6rem"></i>' +
              _escH(a.label) + '</a>';
          }).join('') +
        '</div>';

      /* Dismiss X */
      var dimBtn = document.createElement('button');
      dimBtn.style.cssText = 'background:none;border:none;color:#64748b;cursor:pointer;font-size:.8rem;padding:0 0 0 4px;flex-shrink:0;line-height:1';
      dimBtn.innerHTML = '&times;';
      dimBtn.title = 'Zanemari danas';
      dimBtn.setAttribute('aria-label', 'Zanemari ovu stavku danas');
      dimBtn.addEventListener('click', function () {
        _dismiss(item.dismiss_key);
        row.style.transition = 'opacity .2s';
        row.style.opacity = '0';
        setTimeout(function () { row.remove(); _cleanIfEmpty(panel); }, 200);
      });

      row.appendChild(textCol);
      row.appendChild(dimBtn);
      panel.appendChild(row);
    });

    _panel = panel;

    /* Ubaci na vrh fcCmdBody, ispred svega */
    body.insertBefore(panel, body.firstChild);
  }

  function _cleanIfEmpty(panel) {
    if (!panel.querySelector('[style*="border-radius:8px"]')) {
      panel.style.transition = 'opacity .2s';
      panel.style.opacity = '0';
      setTimeout(function () { panel.remove(); }, 200);
    }
  }

  function _priorityBg(p) {
    if (p === 0) return 'rgba(239,68,68,.06)';
    if (p === 1) return 'rgba(234,179,8,.06)';
    return 'rgba(59,130,246,.06)';
  }
  function _priorityBorder(p) {
    if (p === 0) return 'rgba(239,68,68,.2)';
    if (p === 1) return 'rgba(234,179,8,.2)';
    return 'rgba(59,130,246,.2)';
  }
  function _escH(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function show() {
    if (!_panel) return;
    _panel.style.display = 'block';
  }
  function hide() {
    if (!_panel) return;
    _panel.style.display = 'none';
  }

  /* Inicijalizacija */
  document.addEventListener('fcOpen', function () {
    var inp = document.getElementById('fcCmdInput');
    if (!inp || inp.value.trim()) return;
    if (!_loaded) _load();
    else show();
  });
  document.addEventListener('fcClose', hide);

  /* Sakrij kad korisnik počne tipkati */
  document.addEventListener('DOMContentLoaded', function () {
    var inp = document.getElementById('fcCmdInput');
    if (!inp) return;
    inp.addEventListener('input', function () {
      if (inp.value.trim()) hide();
      else show();
    });
  });

  return { load: _load };
})();

window.FenixCmd.goodMorning = FenixGoodMorning;
