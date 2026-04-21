/**
 * Limit-Connect Trust Badge v1.0
 * Korištenje: <div data-lc-verify="SEAL_TOKEN"></div>
 * Embed:      <script src="https://limit-connect.com/static/trust-badge.js"></script>
 *
 * Svaki element s data-lc-verify atributom automatski se verificira
 * i prikazuje badge s live statusom iz ChainBlock lanca.
 *
 * eIDAS Art. 41 | ZED HR NN 150/05
 */
(function () {
  'use strict';

  var API = 'https://limit-connect.com/api/verify/';

  var STYLE = [
    '.lc-badge{display:inline-flex;align-items:center;gap:6px;',
    'padding:6px 14px;border-radius:20px;font-family:-apple-system,BlinkMacSystemFont,',
    '"Segoe UI",sans-serif;font-size:12px;font-weight:600;text-decoration:none;',
    'cursor:pointer;transition:opacity .2s}',
    '.lc-badge:hover{opacity:.85}',
    '.lc-badge-ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.4);color:#22c55e}',
    '.lc-badge-err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.4);color:#ef4444}',
    '.lc-badge-loading{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.4)}',
    '.lc-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}',
    '.lc-dot-ok{background:#22c55e;animation:lc-pulse 2s infinite}',
    '.lc-dot-err{background:#ef4444}',
    '@keyframes lc-pulse{0%,100%{opacity:1}50%{opacity:.35}}'
  ].join('');

  function injectStyle() {
    if (document.getElementById('lc-badge-style')) return;
    var s = document.createElement('style');
    s.id = 'lc-badge-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function renderLoading(el) {
    el.innerHTML = '<span class="lc-badge lc-badge-loading">Verificiram...</span>';
  }

  function renderOk(el, token) {
    el.innerHTML = '<a href="' + API + token + '/" target="_blank" rel="noopener" class="lc-badge lc-badge-ok">'
      + '<span class="lc-dot lc-dot-ok"></span>Verificirano \u00b7 ChainBlock</a>';
  }

  function renderErr(el) {
    el.innerHTML = '<span class="lc-badge lc-badge-err">'
      + '<span class="lc-dot lc-dot-err"></span>\u26a0 Nije verificirano</span>';
  }

  function verifyEl(el) {
    var token = el.getAttribute('data-lc-verify');
    if (!token) return;
    renderLoading(el);
    fetch(API + encodeURIComponent(token) + '/')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.verified) { renderOk(el, token); } else { renderErr(el); }
      })
      .catch(function () { renderErr(el); });
  }

  function init() {
    injectStyle();
    var els = document.querySelectorAll('[data-lc-verify]');
    for (var i = 0; i < els.length; i++) { verifyEl(els[i]); }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
