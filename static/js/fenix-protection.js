/**
 * FENIX PROTECTION JS
 * Zaštita od kopiranja, printanja i detekcija screenshota
 *
 * REALNA OGRANIČENJA:
 *  - OS screenshot (PrtScr, cmd+shift+3, power+volume) → ne može se blokirati
 *  - Browser screenshot (extenzije) → ne može se blokirati
 *  - Što MOŽEMO: detektirati, logirati, watermark, odvratiti
 *
 * Strategija: Forenzički watermark + audit log → ako netko curri podatke,
 *             zna se TOČNO tko (user+IP+timestamp+URL)
 */

(function() {
  'use strict';

  // ── Konfiguracija ─────────────────────────────────────────────────────
  const CONFIG = {
    logEndpoint: '/api/security/log/',   // audit endpoint
    csrfToken: document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
    user: document.body.dataset.protectUser || 'anonymous',
    company: document.body.dataset.protectCompany || '',
    enabled: document.body.dataset.protectEnabled === 'true',
    level: document.body.dataset.protectLevel || 'standard', // standard | strict | off
  };

  if (!CONFIG.enabled || CONFIG.level === 'off') return;

  // ── Utils ─────────────────────────────────────────────────────────────
  function auditLog(event, detail = {}) {
    const payload = {
      event,
      user: CONFIG.user,
      company: CONFIG.company,
      url: window.location.pathname,
      ts: new Date().toISOString(),
      ua: navigator.userAgent.substring(0, 120),
      ...detail,
    };
    // Fire-and-forget — ne blokiraj korisnika
    if (navigator.sendBeacon && CONFIG.logEndpoint) {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(CONFIG.logEndpoint, blob);
    }
    console.warn('[FENIX PROTECT]', event, payload);
  }

  // ── 1. COPY zaštita ───────────────────────────────────────────────────
  document.addEventListener('copy', function(e) {
    const sel = window.getSelection()?.toString() || '';
    if (sel.length < 3) return; // ignore trivial selections

    // U strict modu — blokiraj
    if (CONFIG.level === 'strict') {
      e.preventDefault();
      showToast('⚠ Kopiranje sadržaja nije dopušteno u ovom modulu.', 'warning');
      auditLog('copy_blocked', { chars: sel.length, preview: sel.substring(0, 50) });
      return;
    }

    // Standard — dopusti ali logiraj + dodaj watermark u clipboard
    const watermark = `\n\n— ${CONFIG.user} @ FENIX LIMIT Connect (${new Date().toLocaleDateString('hr')}) —`;
    if (e.clipboardData) {
      e.clipboardData.setData('text/plain', sel + watermark);
      e.preventDefault(); // moramo preventDefault da postavimo custom data
    }
    auditLog('copy_watermarked', { chars: sel.length });
  });

  // ── 2. CUT zaštita ────────────────────────────────────────────────────
  document.addEventListener('cut', function(e) {
    if (CONFIG.level === 'strict') {
      e.preventDefault();
      auditLog('cut_blocked');
    }
  });

  // ── 3. PRINT zaštita ──────────────────────────────────────────────────
  // Ctrl+P / Cmd+P
  document.addEventListener('keydown', function(e) {
    const isCtrlP = (e.ctrlKey || e.metaKey) && e.key === 'p';
    const isCtrlS = (e.ctrlKey || e.metaKey) && e.key === 's';
    const isF12   = e.key === 'F12';
    const isCtrlU = (e.ctrlKey || e.metaKey) && e.key === 'u';
    const isCtrlShiftI = (e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'I';
    const isCtrlShiftJ = (e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'J';

    if (isCtrlP) {
      if (CONFIG.level === 'strict') {
        e.preventDefault();
        showToast('🖨 Printanje nije dopušteno. Koristite PDF export u aplikaciji.', 'warning');
        auditLog('print_blocked', { method: 'ctrl+p' });
      } else {
        auditLog('print_attempt', { method: 'ctrl+p' });
      }
      return;
    }

    // DevTools — samo logiraj, ne blokiraj (legitimni korisnici su i devs)
    if (isF12 || isCtrlShiftI || isCtrlShiftJ) {
      auditLog('devtools_opened');
    }
  });

  // window.print() override
  const _origPrint = window.print.bind(window);
  window.print = function() {
    auditLog('print_attempt', { method: 'window.print()' });
    if (CONFIG.level === 'strict') {
      showToast('🖨 Printanje nije dopušteno.', 'warning');
      return;
    }
    _origPrint();
  };

  // beforeprint event
  window.addEventListener('beforeprint', function() {
    auditLog('print_attempt', { method: 'beforeprint' });
    // Postavi print watermark s korisnikom
    document.body.setAttribute('data-print-user', CONFIG.user);
    document.body.setAttribute('data-print-ts', new Date().toLocaleString('hr'));
  });

  // ── 4. SCREENSHOT DETEKCIJA ───────────────────────────────────────────
  // Metoda 1: visibilitychange (tab switch = možda snimanje)
  // Metoda 2: window blur (snipping tool, cmd+shift+4 uzrokuje blur)
  // Metoda 3: Print Screen key detekcija (nepouzdano ali vrijedi)

  let lastBlur = 0;
  window.addEventListener('blur', function() {
    lastBlur = Date.now();
  });

  window.addEventListener('focus', function() {
    if (lastBlur && (Date.now() - lastBlur) < 800) {
      // Kratki blur/focus ciklus — moguće snimanje zaslona
      auditLog('screenshot_suspected', { blur_ms: Date.now() - lastBlur });
    }
    lastBlur = 0;
  });

  // PrintScreen key — ne možemo blokirati, ali možemo detektirati
  document.addEventListener('keyup', function(e) {
    if (e.key === 'PrintScreen') {
      auditLog('printscreen_key');
      if (CONFIG.level === 'strict') {
        // Prebriši clipboard s watermarkom
        navigator.clipboard?.writeText(
          `[FENIX LIMIT Connect — Snimka zaslona zabilježena: ${CONFIG.user}, ${new Date().toISOString()}]`
        ).catch(() => {});
        showToast('📸 Snimanje zaslona je zabilježeno i prijavljeno.', 'warning');
      }
    }
  });

  // ── 5. CONTEXT MENU (desni klik) ──────────────────────────────────────
  document.addEventListener('contextmenu', function(e) {
    const target = e.target.closest('[data-protected], .fx-protected-zone, .fx-protected-table');
    if (!target) return;

    if (CONFIG.level === 'strict') {
      e.preventDefault();
    }
    auditLog('contextmenu', { element: target.tagName });
  });

  // ── 6. DRAG zaštita na osjetljivim elementima ─────────────────────────
  document.addEventListener('dragstart', function(e) {
    const target = e.target.closest('[data-protected], .fx-protected-zone');
    if (!target) return;
    e.preventDefault();
    auditLog('drag_blocked');
  });

  // ── 7. DevTools detekcija (heuristička) ──────────────────────────────
  let devToolsOpen = false;
  const devToolsCheck = setInterval(function() {
    const threshold = 160;
    const widthDiff  = window.outerWidth  - window.innerWidth  > threshold;
    const heightDiff = window.outerHeight - window.innerHeight > threshold;
    const isOpen = widthDiff || heightDiff;

    if (isOpen && !devToolsOpen) {
      devToolsOpen = true;
      auditLog('devtools_detected');
    } else if (!isOpen && devToolsOpen) {
      devToolsOpen = false;
    }
  }, 3000);

  // ── Utils: Toast notifikacija ─────────────────────────────────────────
  function showToast(msg, type = 'info') {
    // Koristi postojeći FENIX toast sustav ako postoji
    if (window.fenixToast) {
      window.fenixToast(msg, type);
      return;
    }
    // Fallback — mini toast
    const t = document.createElement('div');
    t.style.cssText = [
      'position:fixed', 'bottom:80px', 'left:50%',
      'transform:translateX(-50%)', 'z-index:999999',
      'background:#1a1a2e', 'color:#f0a500',
      'padding:10px 20px', 'border-radius:8px',
      'font-size:0.9rem', 'box-shadow:0 4px 20px rgba(0,0,0,.4)',
      'pointer-events:none', 'max-width:90vw', 'text-align:center',
    ].join(';');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

})();
