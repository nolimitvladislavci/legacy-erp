/* ═══════════════════════════════════════════════════════════════
   LIMIT CONNECT — Globalni UX Hint Sustav
   Verzija: 1.0 | 2026-03-15
   
   Automatski inicijalizira:
   1. Bootstrap 5 Tooltips (sva [title] i [data-lc-tip] polja)
   2. Field hints (info ikonica uz labele s [data-lc-help])
   3. Process status poruke (data-lc-status)
   4. Smart form validation feedback (vizualni, ne alert())
   5. Button loading state (data-lc-loading)
═══════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── 1. BOOTSTRAP TOOLTIP INICIJALIZACIJA ──────────────────── */
  function initTooltips() {
    if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return;

    // Svi elementi s [title] koji nisu linkovi, nav, ili already-initialized
    const selectors = [
      '[data-lc-tip]',       // naš custom atribut
      'button[title]',
      'input[title]',
      'select[title]',
      'textarea[title]',
      '[data-lc-action][title]',
      '.btn[title]',
      'td[title]',
      'th[title]',
      '.badge[title]',
      '.status-badge[title]',
    ];

    document.querySelectorAll(selectors.join(',')).forEach(function (el) {
      // Preskoči ako već ima tooltip
      if (bootstrap.Tooltip.getInstance(el)) return;

      // data-lc-tip ima prednost nad title
      const content = el.dataset.lcTip || el.title;
      if (!content || content.trim() === '') return;

      new bootstrap.Tooltip(el, {
        title: content,
        placement: el.dataset.lcPlacement || 'top',
        trigger: 'hover focus',
        html: el.dataset.lcHtml === 'true',
        delay: { show: 300, hide: 100 },
        customClass: 'lc-tooltip',
      });

      // Makni title da browser ne prikazuje native tooltip
      if (el.dataset.lcTip) {
        el.removeAttribute('title');
      }
    });
  }

  /* ── 2. FIELD HELP IKONICE ─────────────────────────────────── */
  // Upotreba: <label data-lc-help="OIB je 11-znamenkasti porezni broj.">
  function initFieldHelp() {
    document.querySelectorAll('[data-lc-help]').forEach(function (label) {
      if (label.dataset.lcHelpDone) return;
      label.dataset.lcHelpDone = '1';

      const icon = document.createElement('span');
      icon.className = 'lc-help-icon';
      icon.innerHTML = '<i class="fas fa-circle-question"></i>';
      icon.setAttribute('tabindex', '0');
      icon.setAttribute('role', 'tooltip');
      icon.setAttribute('aria-label', label.dataset.lcHelp);

      // Dodaj tooltip na ikonu
      label.appendChild(icon);

      if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        new bootstrap.Tooltip(icon, {
          title: label.dataset.lcHelp,
          placement: 'right',
          trigger: 'hover focus',
          html: true,
          customClass: 'lc-tooltip lc-tooltip-help',
        });
      }
    });
  }

  /* ── 3. PROCESS STATUS PORUKE ──────────────────────────────── */
  // Upotreba: <div data-lc-status="pending|active|done|error" data-lc-label="Fiskalizacija">
  function initStatusBadges() {
    const statusConfig = {
      pending:  { icon: 'fa-clock',         color: '#f59e0b', label: 'Na čekanju' },
      active:   { icon: 'fa-circle-dot',    color: '#3b82f6', label: 'Aktivno',   pulse: true },
      done:     { icon: 'fa-circle-check',  color: '#10b981', label: 'Završeno' },
      error:    { icon: 'fa-circle-xmark',  color: '#ef4444', label: 'Greška' },
      locked:   { icon: 'fa-lock',          color: '#6366f1', label: 'Zaključano' },
      draft:    { icon: 'fa-pen-to-square', color: '#94a3b8', label: 'Nacrt' },
      fiscalized: { icon: 'fa-shield-check', color: '#10b981', label: 'Fiskalizirano' },
    };

    document.querySelectorAll('[data-lc-status]').forEach(function (el) {
      if (el.dataset.lcStatusDone) return;
      el.dataset.lcStatusDone = '1';

      const status = el.dataset.lcStatus;
      const cfg = statusConfig[status];
      if (!cfg) return;

      const customLabel = el.dataset.lcLabel || cfg.label;
      const badge = document.createElement('span');
      badge.className = 'lc-status-badge lc-status-' + status;
      badge.style.cssText = 'display:inline-flex;align-items:center;gap:5px;' +
        'padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;' +
        'letter-spacing:0.5px;color:' + cfg.color + ';' +
        'background:' + cfg.color + '18;border:1px solid ' + cfg.color + '44;';

      const dot = cfg.pulse
        ? '<span style="width:7px;height:7px;border-radius:50%;background:' + cfg.color +
          ';display:inline-block;animation:lc-pulse 1.5s infinite"></span>'
        : '<i class="fas ' + cfg.icon + '"></i>';

      badge.innerHTML = dot + customLabel;
      el.replaceWith(badge);
    });
  }

  /* ── 4. SMART VALIDATION FEEDBACK ─────────────────────────── */
  // Vizualna povratna informacija bez alert() — prikazuje se ispod polja
  window.lcShowFieldError = function (fieldId, message) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    field.classList.add('lc-field-error');
    let hint = field.parentElement.querySelector('.lc-field-hint');
    if (!hint) {
      hint = document.createElement('div');
      hint.className = 'lc-field-hint';
      field.parentElement.appendChild(hint);
    }
    hint.innerHTML = '<i class="fas fa-triangle-exclamation"></i> ' + message;
    hint.style.color = '#ef4444';
    hint.style.display = 'block';
    field.focus();
  };

  window.lcShowFieldSuccess = function (fieldId, message) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    field.classList.remove('lc-field-error');
    field.classList.add('lc-field-success');
    let hint = field.parentElement.querySelector('.lc-field-hint');
    if (!hint) {
      hint = document.createElement('div');
      hint.className = 'lc-field-hint';
      field.parentElement.appendChild(hint);
    }
    hint.innerHTML = '<i class="fas fa-circle-check"></i> ' + message;
    hint.style.color = '#10b981';
    hint.style.display = 'block';
    setTimeout(function () {
      hint.style.display = 'none';
      field.classList.remove('lc-field-success');
    }, 3000);
  };

  window.lcClearFieldHint = function (fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    field.classList.remove('lc-field-error', 'lc-field-success');
    const hint = field.parentElement.querySelector('.lc-field-hint');
    if (hint) hint.style.display = 'none';
  };

  /* ── 5. BUTTON LOADING STATE ───────────────────────────────── */
  // Upotreba: <button data-lc-loading="Sprema se..."> ili JS: lcButtonLoading(btn, true)
  window.lcButtonLoading = function (btn, loading, loadingText) {
    if (!btn) return;
    if (loading) {
      btn.dataset.lcOriginalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="lc-spinner"></span>' +
        (loadingText || btn.dataset.lcLoading || 'Učitavanje...');
    } else {
      btn.disabled = false;
      btn.innerHTML = btn.dataset.lcOriginalText || btn.innerHTML;
    }
  };

  // Auto-loading za forme s data-lc-form
  document.querySelectorAll('[data-lc-form]').forEach(function (form) {
    form.addEventListener('submit', function () {
      const btn = form.querySelector('[type="submit"]');
      if (btn) lcButtonLoading(btn, true);
    });
  });

  /* ── 6. OIB LIVE VALIDACIJA ────────────────────────────────── */
  function validateOib(oib) {
    if (!/^\d{11}$/.test(oib)) return false;
    let a = 10;
    for (let i = 0; i < 10; i++) {
      a = (a + parseInt(oib[i])) % 10;
      if (a === 0) a = 10;
      a = (a * 2) % 11;
    }
    const k = 11 - a;
    return (k % 10) === parseInt(oib[10]);
  }

  document.querySelectorAll('input[name*="oib"], input[id*="oib"], input[id*="Oib"]').forEach(function (inp) {
    inp.addEventListener('input', function () {
      const val = this.value.replace(/\s/g, '');
      if (val.length === 0) {
        lcClearFieldHint(this.id || this.name);
        return;
      }
      if (val.length === 11) {
        if (validateOib(val)) {
          lcShowFieldSuccess(this.id, 'OIB validan ✓');
        } else {
          lcShowFieldError(this.id, 'OIB nije ispravan — provjerite broj');
        }
      } else if (val.length > 11) {
        lcShowFieldError(this.id, 'OIB ima točno 11 znamenki');
      } else {
        lcClearFieldHint(this.id);
      }
    });
  });

  /* ── 7. IBAN LIVE FORMAT ───────────────────────────────────── */
  document.querySelectorAll('input[name*="iban"], input[id*="iban"], input[id*="Iban"]').forEach(function (inp) {
    inp.addEventListener('input', function () {
      // Auto-format: HR12 1001 0051 8630 0016 0
      let val = this.value.replace(/\s/g, '').toUpperCase();
      if (val.startsWith('HR') && val.length > 2) {
        val = val.replace(/(.{4})/g, '$1 ').trim();
        this.value = val;
      }
    });
  });

  /* ── 8. GLOBALNI PROCESS HINT BAR ──────────────────────────── */
  // Za stranice s data-lc-process atributom na body elementu
  window.lcShowProcessHint = function (message, type) {
    type = type || 'info';
    let bar = document.getElementById('lc-process-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'lc-process-bar';
      bar.style.cssText = 'position:fixed;top:56px;left:0;right:0;z-index:9990;' +
        'padding:8px 16px;font-size:0.82rem;font-weight:500;' +
        'display:flex;align-items:center;gap:8px;' +
        'transition:transform 0.3s ease;transform:translateY(-100%)';
      document.body.appendChild(bar);
    }
    const colors = {
      info:    { bg: '#1e3a5f', border: '#3b82f6', color: '#93c5fd', icon: 'fa-circle-info' },
      success: { bg: '#14532d', border: '#10b981', color: '#86efac', icon: 'fa-circle-check' },
      warning: { bg: '#431407', border: '#f59e0b', color: '#fcd34d', icon: 'fa-triangle-exclamation' },
      error:   { bg: '#450a0a', border: '#ef4444', color: '#fca5a5', icon: 'fa-circle-xmark' },
    };
    const c = colors[type] || colors.info;
    bar.style.background = c.bg;
    bar.style.borderBottom = '1px solid ' + c.border;
    bar.style.color = c.color;
    bar.innerHTML = '<i class="fas ' + c.icon + '"></i><span>' + message + '</span>' +
      '<span onclick="lcHideProcessHint()" style="margin-left:auto;cursor:pointer;opacity:0.6">✕</span>';
    bar.style.transform = 'translateY(0)';

    if (type === 'success') {
      setTimeout(lcHideProcessHint, 4000);
    }
  };

  window.lcHideProcessHint = function () {
    const bar = document.getElementById('lc-process-bar');
    if (bar) bar.style.transform = 'translateY(-100%)';
  };

  /* ── CSS INJEKCIJA ─────────────────────────────────────────── */
  const css = `
    /* Bootstrap tooltip overrides */
    .lc-tooltip .tooltip-inner {
      background: #1a1a2e;
      color: #e2e8f0;
      border: 1px solid rgba(201,168,76,0.3);
      font-size: 0.8rem;
      max-width: 260px;
      text-align: left;
      padding: 8px 12px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    .lc-tooltip.bs-tooltip-top .tooltip-arrow::before,
    .lc-tooltip.bs-tooltip-auto[data-popper-placement^=top] .tooltip-arrow::before {
      border-top-color: rgba(201,168,76,0.4);
    }
    .lc-tooltip-help .tooltip-inner {
      background: #0f1a2e;
      border-color: rgba(59,130,246,0.4);
    }

    /* Help ikonica */
    .lc-help-icon {
      display: inline-flex;
      align-items: center;
      margin-left: 5px;
      color: #4a5060;
      font-size: 0.75rem;
      cursor: help;
      transition: color 0.2s;
    }
    .lc-help-icon:hover { color: #c9a84c; }

    /* Field validation */
    .lc-field-error {
      border-color: #ef4444 !important;
      box-shadow: 0 0 0 2px rgba(239,68,68,0.15) !important;
    }
    .lc-field-success {
      border-color: #10b981 !important;
      box-shadow: 0 0 0 2px rgba(16,185,129,0.15) !important;
    }
    .lc-field-hint {
      display: none;
      font-size: 0.75rem;
      margin-top: 4px;
      padding: 3px 6px;
    }
    .lc-field-hint i { margin-right: 4px; }

    /* Button spinner */
    .lc-spinner {
      display: inline-block;
      width: 13px; height: 13px;
      border: 2px solid rgba(255,255,255,0.3);
      border-radius: 50%;
      border-top-color: currentColor;
      animation: lc-spin 0.8s linear infinite;
      margin-right: 7px;
      vertical-align: middle;
    }
    @keyframes lc-spin { to { transform: rotate(360deg); } }
    @keyframes lc-pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.85); }
    }
  `;

  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  /* ── INIT ──────────────────────────────────────────────────── */
  function initAll() {
    initTooltips();
    initFieldHelp();
    initStatusBadges();
  }

  // Inicijaliziraj kad DOM bude spreman
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Re-init za dinamički dodane elemente (HTMX, AJAX)
  window.lcReinit = function (root) {
    root = root || document;
    root.querySelectorAll('[data-lc-tip],[title][data-lc-reinit]').forEach(function (el) {
      const existing = bootstrap.Tooltip && bootstrap.Tooltip.getInstance(el);
      if (existing) existing.dispose();
    });
    initTooltips();
    initFieldHelp();
    initStatusBadges();
  };

  // Eksponiranog globalnog API-ja
  window.lcUX = {
    reinit: window.lcReinit,
    showFieldError: window.lcShowFieldError,
    showFieldSuccess: window.lcShowFieldSuccess,
    clearFieldHint: window.lcClearFieldHint,
    buttonLoading: window.lcButtonLoading,
    showProcessHint: window.lcShowProcessHint,
    hideProcessHint: window.lcHideProcessHint,
    validateOib: validateOib,
  };

})();
