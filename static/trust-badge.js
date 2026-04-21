/**
 * Limit-Connect Trust Badge v1.0
 * eIDAS Art. 41 | ZED HR NN 150/05 | ChainBlock-1.0
 *
 * Ugradnja:
 *   <script src="https://limit-connect.com/static/trust-badge.js"></script>
 *   <div data-lc-verify="TVOJ-SEAL-TOKEN"></div>
 *
 * Opcije:
 *   data-lc-verify="SEAL_TOKEN"   — obavezan, seal token dokumenta
 *   data-lc-lang="hr|en|de"       — jezik badge-a (default: hr)
 */
(function () {
  'use strict';

  var API = 'https://limit-connect.com/api/verify/';

  var LABELS = {
    hr: { loading: 'Verificiram...', ok: 'Verificirano · ChainBlock', fail: 'Nije verificirano', error: 'Greška' },
    en: { loading: 'Verifying...', ok: 'Verified · ChainBlock', fail: 'Not verified', error: 'Error' },
    de: { loading: 'Prüfe...', ok: 'Verifiziert · ChainBlock', fail: 'Nicht verifiziert', error: 'Fehler' },
  };

  var STYLE = [
    '.lc-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;',
    'border-radius:20px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;',
    'font-size:12px;font-weight:600;text-decoration:none;cursor:pointer;',
    'transition:opacity .2s;line-height:1}',
    '.lc-badge:hover{opacity:.85}',
    '.lc-badge-ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.4);color:#16a34a}',
    '.lc-badge-fail{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4);color:#dc2626}',
    '.lc-badge-loading{background:rgba(148,163,184,.1);border:1px solid rgba(148,163,184,.3);color:#64748b}',
    '.lc-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}',
    '.lc-dot-ok{background:#22c55e;animation:lc-pulse 2s ease-in-out infinite}',
    '.lc-dot-fail{background:#ef4444}',
    '.lc-dot-loading{background:#94a3b8;animation:lc-blink 1s step-end infinite}',
    '@keyframes lc-pulse{0%,100%{opacity:1}50%{opacity:.35}}',
    '@keyframes lc-blink{0%,100%{opacity:1}50%{opacity:0}}',
  ].join('');

  function injectStyle() {
    if (document.getElementById('lc-badge-style')) return;
    var s = document.createElement('style');
    s.id = 'lc-badge-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function renderLoading(el, lang) {
    var L = LABELS[lang] || LABELS.hr;
    el.innerHTML = '<span class="lc-badge lc-badge-loading"><span class="lc-dot lc-dot-loading"></span>' + L.loading + '</span>';
  }

  function renderOk(el, token, data, lang) {
    var L = LABELS[lang] || LABELS.hr;
    var ts = new Date(data.tsa_timestamp);
    var dateStr = ts.toLocaleDateString(lang === 'hr' ? 'hr-HR' : lang === 'de' ? 'de-DE' : 'en-GB');
    var title = L.ok + ' · ' + dateStr + ' · Block #' + data.block_number;
    el.innerHTML = '<a href="' + API + token + '/" target="_blank" rel="noopener" class="lc-badge lc-badge-ok" title="' + title + '">'
      + '<span class="lc-dot lc-dot-ok"></span>'
      + L.ok
      + '</a>';
  }

  function renderFail(el, lang) {
    var L = LABELS[lang] || LABELS.hr;
    el.innerHTML = '<span class="lc-badge lc-badge-fail"><span class="lc-dot lc-dot-fail"></span>' + L.fail + '</span>';
  }

  function processBadge(el) {
    var token = el.getAttribute('data-lc-verify');
    var lang = (el.getAttribute('data-lc-lang') || navigator.language || 'hr').slice(0, 2).toLowerCase();
    if (!token) return;

    renderLoading(el, lang);

    fetch(API + encodeURIComponent(token) + '/')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.verified && d.integrity === 'ok') {
          renderOk(el, token, d, lang);
        } else {
          renderFail(el, lang);
        }
      })
      .catch(function () {
        renderFail(el, lang);
      });
  }

  function init() {
    injectStyle();
    var badges = document.querySelectorAll('[data-lc-verify]');
    for (var i = 0; i < badges.length; i++) {
      processBadge(badges[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose za dinamički dodane elemente
  window.LCBadge = { verify: processBadge, init: init };
})();
