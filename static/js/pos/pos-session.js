/* ═══ POS Session — Numpad, Detective Box, Shift Close ═══
 * Extracted from session.html
 * Reads config from #pos-config JSON block
 */
(function(){
  var cfg = {};
  try { cfg = JSON.parse(document.getElementById('pos-config').textContent); } catch(e){}

  var npExpected = parseFloat(cfg.expected_closing_cash) || 0;
  var npRaw = '';

  window.npPress = function(v) {
    if (v === 'C') {
      npRaw = npRaw.slice(0, -1) || '';
    } else if (v === '.') {
      if (npRaw.includes('.')) return;
      npRaw = (npRaw || '0') + '.';
    } else {
      var parts = npRaw.split('.');
      if (parts[1] !== undefined && parts[1].length >= 2) return;
      if (npRaw === '0' && v !== '.') { npRaw = v; }
      else { npRaw += v; }
    }
    npUpdate();
  };

  window.npAddCash = function(n) {
    var cur = parseFloat(npRaw) || 0;
    npRaw = (cur + n).toFixed(2);
    npUpdate();
  };

  window.npSetExact = function() {
    npRaw = npExpected.toFixed(2);
    npUpdate();
  };

  function npUpdate() {
    var display = document.getElementById('npDisplay');
    var input   = document.getElementById('closingCashInput');
    var diffEl  = document.getElementById('npDiff');
    var val = npRaw === '' ? 0 : parseFloat(npRaw) || 0;
    display.textContent = npRaw || '0';
    input.value = val.toFixed(2);
    if (!diffEl) return;
    var diff = val - npExpected;
    if (Math.abs(diff) < 0.01) {
      diffEl.textContent = 'Točno ✓';
      diffEl.style.color = 'var(--green)';
    } else if (diff > 0) {
      diffEl.textContent = '+€' + diff.toFixed(2) + ' (višak)';
      diffEl.style.color = 'var(--amber, #f59e0b)';
    } else {
      diffEl.textContent = '€' + diff.toFixed(2) + ' (manjak)';
      diffEl.style.color = 'var(--red)';
    }
  }

  document.addEventListener('keydown', function(e) {
    var tag = document.activeElement.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    if (e.key >= '0' && e.key <= '9') window.npPress(e.key);
    else if (e.key === '.' || e.key === ',') window.npPress('.');
    else if (e.key === 'Backspace') window.npPress('C');
  });

  npUpdate();

  window.guardNewReceipt = function(form) {
    var btn = document.getElementById('newReceiptBtn');
    if (!btn || btn.dataset.submitting === '1') return false;
    btn.dataset.submitting = '1';
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>&nbsp;Kreiranje...';
    return true;
  };

  window.checkBalance = function() {
    var actual   = parseFloat(document.getElementById("closingCashInput").value) || 0;
    var expected = npExpected;
    if (actual === 0 && expected > 0) {
      fenixToast('Molimo prebrojite gotovinu u blagajni i unesite iznos.', 'warning');
      return;
    }
    var diff = parseFloat((actual - expected).toFixed(2));
    if (Math.abs(diff) < 0.005) { submitClose(); return; }
    document.getElementById("closeSessionBtn").style.display = "none";
    var box = document.getElementById("detective-box");
    box.style.display = "block";
    var title = document.getElementById("debalans-title");
    var amt   = document.getElementById("debalans-amount");
    var hint  = document.getElementById("debalans-hint");
    if (diff < 0) {
      box.style.borderColor = "#ef4444"; box.style.background = "rgba(239,68,68,.1)";
      title.style.color = "#ef4444"; title.textContent = "Upozorenje: Manjak u blagajni!";
      amt.style.color = "#ef4444"; amt.textContent = diff.toFixed(2) + " EUR";
      hint.textContent = "Jesi li izdao artikl od oko " + Math.abs(diff).toFixed(2) + " EUR, a zaboravio ga kucati?";
    } else {
      box.style.borderColor = "#22c55e"; box.style.background = "rgba(34,197,94,.1)";
      title.style.color = "#22c55e"; title.textContent = "Upozorenje: Visak u blagajni!";
      amt.style.color = "#22c55e"; amt.textContent = "+" + diff.toFixed(2) + " EUR";
      hint.textContent = "Jesi li naplatio " + diff.toFixed(2) + " EUR, a zaboravio izdati racun?";
    }
  };

  window.resetDebalans = function() {
    document.getElementById("detective-box").style.display = "none";
    document.getElementById("closeSessionBtn").style.display = "";
  };

  window.forceClose = function() {
    var btn = document.getElementById("forceCloseBtn");
    if (btn.dataset.submitting === "1") return;
    if (!btn.dataset.confirmed) {
      btn.dataset.confirmed = "1";
      var secs = 3;
      btn.disabled = true;
      btn.style.opacity = "0.6";
      var iv = setInterval(function() {
        secs--;
        btn.textContent = "Potvrdi za " + secs + "s...";
        if (secs <= 0) {
          clearInterval(iv);
          btn.disabled = false;
          btn.style.opacity = "1";
          btn.textContent = "DA, zatvori s razlikom";
          btn.style.background = "#dc2626";
        }
      }, 1000);
      btn.textContent = "Potvrdi za 3s...";
      return;
    }
    btn.dataset.submitting = "1"; btn.disabled = true; btn.textContent = "Zatvaranje...";
    submitClose();
  };

  function submitClose() { document.getElementById("closeSessionForm").submit(); }

  window.addEventListener('pageshow', function() {
    ['newReceiptBtn', 'closeSessionBtn'].forEach(function(id) {
      var b = document.getElementById(id);
      if (b) { b.disabled = false; delete b.dataset.submitting; b.innerHTML = id === 'newReceiptBtn' ? '+ Novi bon' : 'Zatvori smjenu'; }
    });
  });
})();
