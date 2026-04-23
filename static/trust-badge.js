/**
 * Limit-Connect Trust Badge v2.0
 * eIDAS Art. 41 | ZED HR NN 150/05 | ChainBlock-1.0 | Folija-POE
 *
 * Ugradnja:
 *   <script src="https://limit-connect.com/static/js/trust-badge.js"></script>
 *   <div data-folija-seal="NOLIMIT-GENESIS-0001"></div>
 *
 * Backward compat:
 *   <div data-lc-verify="SEAL_TOKEN"></div>
 *
 * Opcije:
 *   data-folija-seal="TOKEN"  — seal token (Folija/ChainBlock)
 *   data-lc-verify="TOKEN"   — legacy alias
 *   data-lc-lang="hr|en|de"  — jezik (default: hr)
 *   data-lc-compact          — kompaktni prikaz bez panela
 */
(function () {
  'use strict';

  var API_VERIFY = 'https://limit-connect.com/badge/api/';

  var LABELS = {
    hr: {
      loading: 'Verificiram...',
      ok: 'Verificirano',
      fail: 'Nije verificirano',
      error: 'Greška provjere',
      folija: 'Folija Seal',
      dok: 'Preuzmi .dok',
      block: 'ChainBlock',
      aktivan: 'AKTIVAN',
      neaktivan: 'NEAKTIVAN',
      docs: 'dok.',
      issued: 'Izdano'
    },
    en: {
      loading: 'Verifying...',
      ok: 'Verified',
      fail: 'Not verified',
      error: 'Verification error',
      folija: 'Folija Seal',
      dok: 'Download .dok',
      block: 'ChainBlock',
      aktivan: 'ACTIVE',
      neaktivan: 'INACTIVE',
      docs: 'docs',
      issued: 'Issued'
    },
    de: {
      loading: 'Verifiziere...',
      ok: 'Verifiziert',
      fail: 'Nicht verifiziert',
      error: 'Fehler',
      folija: 'Folija Siegel',
      dok: '.dok herunterladen',
      block: 'ChainBlock',
      aktivan: 'AKTIV',
      neaktivan: 'INAKTIV',
      docs: 'Dok.',
      issued: 'Ausgestellt'
    }
  };

  var CSS = [
    '@keyframes lc-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}',
    '@keyframes lc-chain-pulse{0%,100%{opacity:.4;transform:scale(.85)}50%{opacity:1;transform:scale(1)}}',
    '@keyframes lc-fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}',
    '.lc-badge-wrap{display:inline-block;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;line-height:1.4}',
    '.lc-badge{display:flex;align-items:center;gap:6px;padding:6px 10px 6px 8px;border-radius:6px;cursor:pointer;border:1.5px solid #2a7a2a;background:#f6fff6;color:#1a5c1a;user-select:none;transition:box-shadow .15s}',
    '.lc-badge:hover{box-shadow:0 2px 8px rgba(42,122,42,.18)}',
    '.lc-badge.lc-fail{border-color:#b22;background:#fff6f6;color:#800}',
    '.lc-badge.lc-loading{border-color:#888;background:#fafafa;color:#555}',
    '.lc-badge.lc-error{border-color:#c80;background:#fffbe6;color:#7a5700}',
    '.lc-icon{width:18px;height:18px;flex-shrink:0}',
    '.lc-spin{animation:lc-spin 1s linear infinite}',
    '.lc-nodes{display:flex;gap:3px;align-items:center}',
    '.lc-node{width:6px;height:6px;border-radius:50%;background:#2a7a2a;animation:lc-chain-pulse 1.4s ease-in-out infinite}',
    '.lc-node:nth-child(2){animation-delay:.2s}',
    '.lc-node:nth-child(3){animation-delay:.4s}',
    '.lc-node-live{background:#27ae60}',
    '.lc-text{font-weight:600;letter-spacing:.01em}',
    '.lc-panel{margin-top:4px;border:1px solid #d4e8d4;border-radius:6px;background:#fff;padding:10px 12px;animation:lc-fadeIn .18s ease}',
    '.lc-panel-row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px solid #eef5ee;font-size:12px;color:#333}',
    '.lc-panel-row:last-child{border-bottom:none}',
    '.lc-panel-label{color:#666;flex:0 0 auto;margin-right:8px}',
    '.lc-panel-value{font-weight:600;color:#1a5c1a;text-align:right;word-break:break-all}',
    '.lc-panel-value.lc-aktivan{color:#27ae60}',
    '.lc-panel-value.lc-neaktivan{color:#c0392b}',
    '.lc-dok-btn{display:inline-flex;align-items:center;gap:5px;margin-top:8px;padding:5px 10px;border-radius:4px;background:#1a5c1a;color:#fff;font-size:11px;font-weight:700;text-decoration:none;letter-spacing:.03em;transition:background .12s}',
    '.lc-dok-btn:hover{background:#2a7a2a}',
    '.lc-seal-token{font-family:monospace;font-size:10px;color:#555;word-break:break-all}'
  ].join('\n');

  function injectStyles() {
    if (document.getElementById('lc-badge-css')) return;
    var s = document.createElement('style');
    s.id = 'lc-badge-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function svgShield(color) {
    return '<svg class="lc-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
      + '<path d="M12 2L4 6v6c0 5.25 3.75 10.15 8 11 4.25-.85 8-5.75 8-11V6L12 2z" fill="' + color + '"/>'
      + '<path d="M9 12l2 2 4-4" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
      + '</svg>';
  }

  function svgSpinner() {
    return '<svg class="lc-icon lc-spin" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
      + '<circle cx="12" cy="12" r="9" stroke="#888" stroke-width="2.5" stroke-dasharray="28 56"/>'
      + '</svg>';
  }

  function chainNodes() {
    return '<div class="lc-nodes">'
      + '<div class="lc-node lc-node-live"></div>'
      + '<div class="lc-node lc-node-live"></div>'
      + '<div class="lc-node lc-node-live"></div>'
      + '</div>';
  }

  function renderBadge(wrap, state, data, lang, compact) {
    var L = LABELS[lang] || LABELS.hr;
    var badgeEl = document.createElement('div');

    if (state === 'loading') {
      badgeEl.className = 'lc-badge lc-loading';
      badgeEl.innerHTML = svgSpinner() + '<span class="lc-text">' + L.loading + '</span>';
      wrap.innerHTML = '';
      wrap.appendChild(badgeEl);
      return;
    }

    if (state === 'ok') {
      badgeEl.className = 'lc-badge';
      badgeEl.innerHTML = svgShield('#2a7a2a') + chainNodes() + '<span class="lc-text">' + L.ok + '</span>';
    } else if (state === 'fail') {
      badgeEl.className = 'lc-badge lc-fail';
      badgeEl.innerHTML = svgShield('#b22222') + '<span class="lc-text">' + L.fail + '</span>';
    } else {
      badgeEl.className = 'lc-badge lc-error';
      badgeEl.innerHTML = svgShield('#c8a000') + '<span class="lc-text">' + L.error + '</span>';
    }

    wrap.innerHTML = '';
    wrap.appendChild(badgeEl);

    if (compact || state !== 'ok' || !data) return;

    var panel = document.createElement('div');
    panel.className = 'lc-panel';

    function addRow(label, valueHtml) {
      var row = document.createElement('div');
      row.className = 'lc-panel-row';
      row.innerHTML = '<span class="lc-panel-label">' + label + '</span>' + valueHtml;
      panel.appendChild(row);
    }

    if (data.seal_token) {
      addRow(L.folija, '<span class="lc-seal-token">' + data.seal_token + '</span>');
    }

    var fStatus = data.folija_active !== false ? L.aktivan : L.neaktivan;
    var fClass = data.folija_active !== false ? 'lc-aktivan' : 'lc-neaktivan';
    addRow(L.folija + ' status', '<span class="lc-panel-value ' + fClass + '">' + fStatus + '</span>');

    if (data.block_number !== undefined && data.block_number !== null) {
      addRow(L.block, '<span class="lc-panel-value">#' + data.block_number + '</span>');
    }

    if (data.document_count !== undefined) {
      addRow(L.docs, '<span class="lc-panel-value">' + data.document_count + '</span>');
    }

    if (data.issued_at) {
      var d = new Date(data.issued_at);
      var dateStr = d.toLocaleDateString(lang === 'hr' ? 'hr-HR' : lang === 'de' ? 'de-DE' : 'en-GB');
      addRow(L.issued, '<span class="lc-panel-value">' + dateStr + '</span>');
    }

    if (data.dok_url) {
      var btn = document.createElement('a');
      btn.className = 'lc-dok-btn';
      btn.href = data.dok_url;
      btn.target = '_blank';
      btn.rel = 'noopener';
      btn.innerHTML = '&#128196; ' + L.dok;
      panel.appendChild(btn);
    }

    wrap.appendChild(panel);

    badgeEl.addEventListener('click', function () {
      panel.style.display = panel.style.display === 'none' ? '' : 'none';
    });
  }

  function initBadge(el) {
    var token = el.getAttribute('data-folija-seal') || el.getAttribute('data-lc-verify');
    if (!token) return;

    var lang = (el.getAttribute('data-lc-lang') || 'hr').toLowerCase();
    if (!LABELS[lang]) lang = 'hr';

    var compact = el.hasAttribute('data-lc-compact');

    var wrap = document.createElement('div');
    wrap.className = 'lc-badge-wrap';
    el.parentNode.insertBefore(wrap, el);
    el.parentNode.removeChild(el);

    renderBadge(wrap, 'loading', null, lang, compact);

    var url = API_VERIFY + '?token=' + encodeURIComponent(token);

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.verified) {
          renderBadge(wrap, 'ok', data, lang, compact);
        } else {
          renderBadge(wrap, 'fail', null, lang, compact);
        }
      })
      .catch(function () {
        renderBadge(wrap, 'error', null, lang, compact);
      });
  }

  function init() {
    injectStyles();
    var els = document.querySelectorAll('[data-folija-seal],[data-lc-verify]');
    for (var i = 0; i < els.length; i++) {
      initBadge(els[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
