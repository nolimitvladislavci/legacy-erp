/* ═══ POS Quick — Basket, Payment, Delivery, Cashier, Tips ═══
 * Extracted from quick.html main inline script
 * Reads config from #pos-config JSON block
 */
(function(){
  var cfg = {};
  try { cfg = JSON.parse(document.getElementById('pos-config').textContent); } catch(e){}

  var SESSION_ID = cfg.session_id || null;
  var CSRF = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  var LANG_PREFIX = (window.location.pathname.match(/^\/([a-z]{2})\//) || ['',''])[1];
  var API_BASE = LANG_PREFIX ? '/' + LANG_PREFIX : '';
  var defaultCashierName = cfg.default_cashier || '';

  var currentCat = '';
  var currentQ   = '';

  window.filterCat = function(el, cat) {
    currentCat = cat;
    document.querySelectorAll('.cat-tab').forEach(function(t){ t.classList.remove('active'); });
    el.classList.add('active');
    buildQuickKeys(cat);
    applyFilter();
  };

  window.filterProducts = function(q) {
    currentQ = q.toLowerCase();
    applyFilter();
  };

  function applyFilter() {
    document.querySelectorAll('.prod-btn').forEach(function(btn) {
      var name = btn.dataset.name.toLowerCase();
      var cat  = btn.dataset.cat;
      var matchCat = !currentCat || cat === currentCat;
      var matchQ   = !currentQ   || name.includes(currentQ);
      btn.style.display = (matchCat && matchQ) ? '' : 'none';
    });
  }

  var basket = {};
  var lastReceiptUrl = '';
  var lastReceiptId = null; window.lastReceiptId = null;
  var _weighBtn = null;

  window.addProduct = function(btn) {
    var rect = btn.getBoundingClientRect();
    var rip  = document.createElement('div');
    rip.className = 'ripple';
    rip.style.left = (event.clientX - rect.left) + 'px';
    rip.style.top  = (event.clientY - rect.top)  + 'px';
    btn.appendChild(rip);
    setTimeout(function(){ rip.remove(); }, 400);

    if (btn.dataset.weighable === '1') {
      _weighBtn = btn;
      document.getElementById('weightProductName').textContent = btn.dataset.name;
      document.getElementById('weightUnit').textContent = btn.dataset.unit || 'kg';
      var wi = document.getElementById('weightInput');
      wi.value = '';
      document.getElementById('weightModal').classList.add('show');
      setTimeout(function(){ wi.focus(); }, 80);
      return;
    }

    var id    = btn.dataset.id;
    var name  = btn.dataset.name;
    var price = parseFloat(btn.dataset.price);
    var tax   = parseFloat(btn.dataset.tax);

    if (basket[id]) { basket[id].qty += 1; }
    else { basket[id] = { name: name, price: price, tax: tax, qty: 1 }; }
    updateQtyBadge(id);
    renderBasket();
  };

  window.confirmWeight = function() {
    var qty = parseFloat(document.getElementById('weightInput').value);
    if (!qty || qty <= 0) { alert('Unesite ispravnu količinu'); return; }
    var btn = _weighBtn;
    var id = btn.dataset.id;
    var key = id + '_w' + Date.now();
    basket[key] = { name: btn.dataset.name, price: parseFloat(btn.dataset.price), tax: parseFloat(btn.dataset.tax), qty: parseFloat(qty.toFixed(3)), item_id: id };
    document.getElementById('weightModal').classList.remove('show');
    _weighBtn = null;
    renderBasket();
  };

  window.cancelWeight = function() {
    document.getElementById('weightModal').classList.remove('show');
    _weighBtn = null;
  };

  function updateQtyBadge(id) {
    var badge = document.getElementById('qb-' + id);
    if (!badge) return;
    var qty = basket[id] ? basket[id].qty : 0;
    badge.textContent = qty;
    badge.classList.toggle('show', qty > 0);
  }

  window.changeQty = function(id, delta) {
    if (!basket[id]) return;
    basket[id].qty += delta;
    if (basket[id].qty <= 0) delete basket[id];
    updateQtyBadge(id);
    updateQkBadge(id);
    renderBasket();
  };

  window.removeItem = function(id) {
    delete basket[id];
    updateQtyBadge(id);
    updateQkBadge(id);
    renderBasket();
  };

  function renderBasket() {
    var list = document.getElementById('basketList');
    var ids  = Object.keys(basket);
    if (!ids.length) {
      list.innerHTML = '<div class="basket-empty">Dodajte artiklе klikom ↑</div>';
      setTotals(0, 0, 0);
      setPayEnabled(false);
      return;
    }
    var subtotal = 0, tax = 0;
    list.innerHTML = ids.map(function(id) {
      var item = basket[id];
      var line = item.price * item.qty;
      var taxAmt = line * item.tax / 100;
      subtotal += line;
      tax += taxAmt;
      return '<div class="b-row">' +
        '<div class="b-name" title="' + item.name + '">' + item.name + '</div>' +
        '<div class="b-qty-ctrl">' +
        '<button class="bq-btn" onclick="changeQty(\'' + id + '\',-1)">−</button>' +
        '<span class="b-qty">' + item.qty + '</span>' +
        '<button class="bq-btn" onclick="changeQty(\'' + id + '\',1)">+</button>' +
        '</div>' +
        '<div class="b-price">€' + (item.price * item.qty).toFixed(2) + '</div>' +
        '<button class="b-del" onclick="removeItem(\'' + id + '\')">✕</button></div>';
    }).join('');
    setTotals(subtotal, tax, subtotal + tax);
    setPayEnabled(true);
    calcChange();
  }

  function setTotals(neto, pdv, total) {
    document.getElementById('tNeto').textContent  = '€' + neto.toFixed(2);
    document.getElementById('tPdv').textContent   = '€' + pdv.toFixed(2);
    document.getElementById('tTotal').textContent = '€' + total.toFixed(2);
    window._total = total;
  }

  function setPayEnabled(en) {
    document.getElementById('payCash').disabled = !en;
    document.getElementById('payCard').disabled = !en;
    try { document.getElementById('payRevolut').disabled = !en; } catch(e) {}
    document.getElementById('payBon').disabled = !en;
    try { document.getElementById('tipToggleBtn').disabled = !en; } catch(e){}
    try { document.getElementById('pfandBtn').disabled = !en; } catch(e){}
    var hint = document.getElementById('cashierHint');
    if (hint) hint.classList.remove('show');
  }

  window.clearBasket = function() {
    document.querySelectorAll('.prod-qty-badge').forEach(function(b){ b.textContent='0'; b.classList.remove('show'); });
    document.querySelectorAll('.qk-badge').forEach(function(b){ b.textContent='0'; b.classList.remove('show'); });
    basket = {};
    renderBasket();
  };

  window.setExact = function() { document.getElementById('cashAmt').value = (window._total || 0).toFixed(2); calcChange(); };
  window.addCash = function(n) { var cur = parseFloat(document.getElementById('cashAmt').value) || 0; document.getElementById('cashAmt').value = (cur + n).toFixed(2); calcChange(); };
  window.setCash = function(n) {
    if (n === 0) { document.getElementById('cashAmt').value = ''; calcChange(); document.getElementById('cashAmt').focus(); return; }
    document.getElementById('cashAmt').value = n.toFixed(2); calcChange();
  };
  window.calcChange = calcChange;
  function calcChange() {
    var paid = parseFloat(document.getElementById('cashAmt').value) || 0;
    var total = window._total || 0;
    var change = Math.max(0, paid - total);
    var row = document.getElementById('changeRow');
    document.getElementById('changeVal').textContent = '€' + change.toFixed(2);
    row.classList.toggle('show', paid > total + 0.001);
  }

  window.pay = function(method) {
    if (!SESSION_ID) { alert('Nema aktivne smjene!'); return; }
    var ids = Object.keys(basket);
    if (!ids.length) return;
    var btn = document.getElementById(method === 'CASH' ? 'payCash' : 'payCard');
    if (btn.dataset.submitting === '1') return;
    btn.dataset.submitting = '1'; btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    var amtPaid = method === 'CASH' ? (parseFloat(document.getElementById('cashAmt').value) || window._total) : window._total;
    var items = buildItemsPayload();
    var _ctrl = new AbortController();
    var _timeout = setTimeout(function(){ _ctrl.abort(); }, 15000); // 15s timeout
    fetch(API_BASE + '/pos/session/' + SESSION_ID + '/quick-pay/', {
      method: 'POST', credentials: 'same-origin', signal: _ctrl.signal,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      body: JSON.stringify({ items: items, method: method, amount_paid: amtPaid, tip_amount: window._tip || 0, cashier: window._currentCashier || '', cashier_id: window._currentCashierId || '' }),
    })
    .then(function(res){ return res.text().then(function(text){ return {res:res, text:text}; }); })
    .then(function(result) {
      var data;
      try { data = JSON.parse(result.text); } catch(e) {
        if (result.text.includes('login') || result.res.status === 302) { window.location.reload(); } else { alert('Greška servera (' + result.res.status + ').'); }
        return;
      }
      if (data.ok) {
        lastReceiptUrl = data.print_url || ''; lastReceiptId = data.receipt_id || null; window.lastReceiptId = lastReceiptId;
        window._publicUrl = data.public_url || null;
        var change = method === 'CASH' ? Math.max(0, amtPaid - parseFloat(data.total)) : 0;
        showSuccess(data.receipt_number, data.total, change);
        clearBasket();
      } else { alert('Greška: ' + (data.error || 'nepoznata')); }
    })
    .catch(function(e) {
      clearTimeout(_timeout);
      btn.disabled = false; btn.dataset.submitting = '0'; btn.textContent = _btnLabels[method] || 'Naplati';
      if (e.name === 'AbortError') {
        // Server timeout — offer offline mode
        if (window.showToast) showToast('Server ne odgovara (15s). Pokušajte ponovo ili koristite offline mode.');
        if (window.queueOfflineReceipt) {
          var offRec = window.queueOfflineReceipt({session_id:SESSION_ID,items:items,payment_method:method,amount_paid:amtPaid,tip_amount:window._tip||0,note:window._currentCashier||'',cashier_id:window._currentCashierId||''});
          if (offRec) { showSuccess('OFF-'+offRec.local_receipt_number,offRec.total,offRec.change); clearBasket(); }
        }
        return;
      }
      if (!navigator.onLine && window.queueOfflineReceipt) {
        var offRec = window.queueOfflineReceipt({
          session_id: SESSION_ID,
          items: items,
          payment_method: method,
          amount_paid: amtPaid,
          tip_amount: window._tip || 0,
          note: window._currentCashier || '',
          cashier_id: window._currentCashierId || '',
        });
        showSuccess('OFF-' + offRec.local_receipt_number, offRec.total.toFixed(2), offRec.change.toFixed(2));
        clearBasket();
        // Show printable offline receipt
        if (window.showOfflineReceipt) window.showOfflineReceipt(offRec);
      } else if (!navigator.onLine && window.queueOfflineSale) {
        window.queueOfflineSale({ _url: API_BASE + '/pos/session/' + SESSION_ID + '/quick-pay/', items: items, method: method, amount_paid: amtPaid, tip_amount: window._tip || 0, cashier: window._currentCashier || '', cashier_id: window._currentCashierId || '' });
        showSuccess('OFF', parseFloat(window._total).toFixed(2), 0);
        clearBasket();
      } else { alert('Nema veze. Pokusajte ponovo.'); }
    })
    .finally(function() { btn.dataset.submitting = ''; btn.disabled = false; btn.innerHTML = method === 'CASH' ? '💵 GOTOVINA' : '💳 KARTICA'; });
  };

  function showSuccess(num, total, change) {
    document.getElementById('sucTotal').textContent  = '€' + parseFloat(total).toFixed(2);
    document.getElementById('sucChange').textContent = change > 0.001 ? 'Kusur: €' + change.toFixed(2) : '';
    document.getElementById('sucNum').textContent    = 'Bon #' + num;
    document.getElementById('successOverlay').classList.add('show');
  }
  window.closeSuccess = function() {
    document.getElementById('successOverlay').classList.remove('show');
    document.getElementById('deliveryExtra').style.display = 'none';
    document.getElementById('cashAmt').value = '';
    document.getElementById('changeRow').classList.remove('show');
  };
  window.printLast = function() { if (lastReceiptUrl) window.open(lastReceiptUrl, '_blank'); };

  window.sendWhatsApp = function() {
    if (!lastReceiptId) return;
    var extra = document.getElementById('deliveryExtra');
    extra.style.display = 'block';
    extra.innerHTML = '<div style="text-align:center;margin-bottom:.75rem;color:var(--gold);font-weight:600">WhatsApp racun</div><input id="waPhone" type="tel" placeholder="+385 9x xxx xxxx" style="width:100%;padding:.6rem;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:1rem;text-align:center;margin-bottom:.5rem"><button onclick="doSendWhatsApp()" style="width:100%;padding:.6rem;background:#25d366;color:#fff;border:none;border-radius:8px;font-weight:700;cursor:pointer">Posalji na WhatsApp</button>';
    document.getElementById('waPhone').focus();
  };
  window.doSendWhatsApp = function() {
    var phone = document.getElementById('waPhone').value.trim();
    if (!phone || phone.length < 8) { showPosToast('Unesite ispravan broj', 'warning'); return; }
    event.target.disabled = true; event.target.textContent = 'Otvaram...';
    fetch(API_BASE + '/pos/receipt/' + lastReceiptId + '/whatsapp/', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': CSRF}, body: 'phone=' + encodeURIComponent(phone) })
    .then(function(r){ return r.json(); }).then(function(d) {
      if (d.wa_url) { window.open(d.wa_url, '_blank'); document.getElementById('deliveryExtra').innerHTML = '<div style="text-align:center;color:var(--green)">Poslano!</div>'; }
      else { document.getElementById('deliveryExtra').innerHTML = '<div style="text-align:center;color:#ef4444">' + (d.error || 'Greska') + '</div>'; }
    }).catch(function(e) { document.getElementById('deliveryExtra').innerHTML = '<div style="text-align:center;color:#ef4444">Greska: ' + e + '</div>'; });
  };
  window.sendEmail = function() {
    if (!lastReceiptId) return;
    var extra = document.getElementById('deliveryExtra');
    extra.style.display = 'block';
    extra.innerHTML = '<div style="text-align:center;margin-bottom:.75rem;color:var(--gold);font-weight:600">Email racun</div><input id="emailAddr" type="email" placeholder="gost@email.com" style="width:100%;padding:.6rem;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:1rem;text-align:center;margin-bottom:.5rem"><button onclick="doSendEmail()" style="width:100%;padding:.6rem;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-weight:700;cursor:pointer">Posalji PDF na email</button>';
    document.getElementById('emailAddr').focus();
  };
  window.doSendEmail = function() {
    var email = document.getElementById('emailAddr').value.trim();
    if (!email || email.indexOf('@') < 0) { showPosToast('Unesite ispravnu email adresu', 'warning'); return; }
    event.target.disabled = true; event.target.textContent = 'Saljem...';
    fetch(API_BASE + '/pos/receipt/' + lastReceiptId + '/email/', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': CSRF}, body: 'email=' + encodeURIComponent(email) })
    .then(function(r){ return r.json(); }).then(function(d) {
      if (d.ok) { document.getElementById('deliveryExtra').innerHTML = '<div style="text-align:center;color:var(--green)">Racun poslan na ' + d.sent_to + '!</div>'; showPosToast('Poslan na ' + d.sent_to, 'success'); }
      else { document.getElementById('deliveryExtra').innerHTML = '<div style="text-align:center;color:#ef4444">' + (d.error || 'Greska') + '</div>'; }
    }).catch(function(e) { document.getElementById('deliveryExtra').innerHTML = '<div style="text-align:center;color:#ef4444">Greska: ' + e + '</div>'; });
  };
  window.showQR = function() {
    if (!lastReceiptId) return;
    var extra = document.getElementById('deliveryExtra');
    var url = window.location.origin + (window._publicUrl || '/pos/r/' + lastReceiptId + '/');
    extra.style.display = 'block';
    extra.innerHTML = '<div style="text-align:center"><div style="color:var(--gold);font-weight:600;margin-bottom:.5rem">BEZ PAPIRA — Gost skenira</div><div style="background:#fff;display:inline-block;padding:12px;border-radius:12px"><img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=' + encodeURIComponent(url) + '" style="width:180px;height:180px"></div><div style="color:var(--muted);font-size:.75rem;margin-top:.5rem">Gost skenira QR → racun na mobitelu</div></div>';
  };

  window._tip = 0;
  window._currentCashier = '';
  window._currentCashierId = null;

  window.toggleTip = function() { var row = document.getElementById("tipRow"); var btn = document.getElementById("tipToggleBtn"); var hidden = row.classList.toggle("hidden"); btn.classList.toggle("active", !hidden); if (hidden) clearTip(); };
  window.setTipPct = function(pct) { document.querySelectorAll(".tip-pct-btn").forEach(function(b){ b.classList.remove("active"); }); if (event && event.target) event.target.classList.add("active"); document.getElementById("tipCustom").value = ""; window._tip = Math.round((window._total || 0) * pct / 100 * 100) / 100; updateTipDisplay(); };
  window.setTipCustom = function(val) { document.querySelectorAll(".tip-pct-btn").forEach(function(b){ b.classList.remove("active"); }); window._tip = Math.max(0, parseFloat(val) || 0); updateTipDisplay(); };
  function updateTipDisplay() { var el = document.getElementById("tipVal"); if (window._tip > 0) { el.textContent = "+ €" + window._tip.toFixed(2); } else { el.textContent = ""; } }
  function clearTip() { window._tip = 0; document.querySelectorAll(".tip-pct-btn").forEach(function(b){ b.classList.remove("active"); }); document.getElementById("tipCustom").value = ""; updateTipDisplay(); }

  window.addPfandReturn = function(id, name, price) {
    var key = "pfand_" + id;
    if (basket[key]) { basket[key].qty++; }
    else { basket[key] = { id: String(id), name: "↩ POVRAT: " + name, price: -Math.abs(parseFloat(price)), tax: 0, qty: 1, is_pfand_return: true }; }
    renderBasket();
    if (typeof closePfandModal === 'function') closePfandModal();
  };

  var _voucherData = null;
  window.openVoucherModal = function() {
    document.getElementById("voucherModal").classList.add("show");
    document.getElementById("voucherCodeInput").value = "";
    document.getElementById("voucherInfo").textContent = "";
    var splitEl = document.getElementById("voucherAmountInput"); if (splitEl) splitEl.value = "";
    document.getElementById("voucherPayBtn").style.display = "none";
    document.getElementById("voucherCheckBtn").style.display = "";
    document.getElementById("voucherSplitSection").style.display = "none";
    _voucherData = null;
    setTimeout(function(){ document.getElementById("voucherCodeInput").focus(); }, 100);
  };
  window.closeVoucherModal = function() { document.getElementById("voucherModal").classList.remove("show"); };
  window.checkVoucher = function() {
    var code = document.getElementById("voucherCodeInput").value.trim(); if (!code) return;
    var info = document.getElementById("voucherInfo"); info.textContent = "Provjera...";
    fetch(API_BASE + "/pos/api/voucher/check/?code=" + encodeURIComponent(code))
    .then(function(r){ return r.json(); }).then(function(data) {
      if (data.ok && data.is_usable) {
        var rem = parseFloat(data.remaining); var total = window._total || 0; _voucherData = data;
        info.style.color = "var(--green)"; info.textContent = "Vaucer " + data.code + ": " + rem.toFixed(2) + " € preostalo";
        document.getElementById("voucherPayBtn").style.display = ""; document.getElementById("voucherCheckBtn").style.display = "none";
        if (rem < total - 0.001) { document.getElementById("voucherSplitSection").style.display = ""; document.getElementById("voucherAmountInput").value = rem.toFixed(2); }
        else { document.getElementById("voucherSplitSection").style.display = "none"; }
      } else {
        _voucherData = null; info.style.color = "var(--red)";
        if (data.is_expired) info.textContent = "Vaucer je istekao.";
        else if (!data.is_active) info.textContent = "Vaucer je vec iskoristen.";
        else info.textContent = data.error || "Vaucer nije pronaden.";
      }
    }).catch(function() { info.style.color = "var(--red)"; info.textContent = "Greska veze."; });
  };

  function buildItemsPayload() {
    return Object.entries(basket).map(function(entry) {
      var id = entry[0], item = entry[1];
      var obj = { id: item.id || id, name: item.name, price: item.price, tax: item.tax, qty: item.qty };
      if (item.is_pfand_return) obj.is_pfand_return = true;
      return obj;
    });
  }

  window.payWithVoucher = function() {
    if (!_voucherData) return;
    var code = _voucherData.code; var rem = parseFloat(_voucherData.remaining); var total = window._total || 0;
    var splitSection = document.getElementById("voucherSplitSection"); var splitEl = document.getElementById("voucherAmountInput");
    var voucherAmt = (splitSection.style.display !== "none" && splitEl) ? (parseFloat(splitEl.value) || rem) : Math.min(rem, total);
    closeVoucherModal();
    var btn = document.getElementById("payBon"); if (btn.dataset.submitting === "1") return;
    btn.dataset.submitting = "1"; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
    fetch(API_BASE + "/pos/session/" + SESSION_ID + "/quick-pay/", {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
      body: JSON.stringify({ items: buildItemsPayload(), method: "VOUCHER", amount_paid: total, voucher_code: code, voucher_amount: voucherAmt, remainder_method: "CASH", tip_amount: window._tip || 0, cashier: window._currentCashier || "", cashier_id: window._currentCashierId || "" }),
    })
    .then(function(r){ return r.text(); }).then(function(vtxt) {
      var data; try { data = JSON.parse(vtxt); } catch(e) { window.location.reload(); return; }
      if (data.ok) { lastReceiptUrl = data.print_url || ""; lastReceiptId = data.receipt_id || null; window.lastReceiptId = lastReceiptId; window._publicUrl = data.public_url || null; showSuccess(data.receipt_number, data.total, 0); clearBasket(); clearTip(); }
      else { alert("Greska: " + (data.error || "nepoznata")); }
    }).catch(function() { alert("Greska veze."); })
    .finally(function() { btn.dataset.submitting = ""; btn.disabled = false; btn.innerHTML = "🎫 BON"; });
  };

  (function posClock(){
    var DAYS=['Ned','Pon','Uto','Sri','Čet','Pet','Sub'];
    var MONTHS=['Sij','Vel','Ožu','Tra','Svi','Lip','Srp','Kol','Ruj','Lis','Stu','Pro'];
    function tick(){
      var now=new Date(); var h=String(now.getHours()).padStart(2,'0'); var m=String(now.getMinutes()).padStart(2,'0'); var s=String(now.getSeconds()).padStart(2,'0');
      var el=document.getElementById('pos-clock'); if(el) el.textContent=h+':'+m+':'+s;
      var de=document.getElementById('pos-date'); if(de) de.textContent=DAYS[now.getDay()]+' '+now.getDate()+'. '+MONTHS[now.getMonth()]+'.';
    }
    tick(); setInterval(tick, 1000);
  })();

  (function(){
    var btns = document.querySelectorAll('.cashier-btn');
    if (btns.length === 1 && btns[0].dataset.hasPin !== '1') { selectCashier(btns[0], btns[0].dataset.name, btns[0].dataset.id); }
    if (btns.length === 0) { window._currentCashier = defaultCashierName; window._currentCashierId = 'user'; setPayEnabled(Object.keys(basket).length > 0); }
  })();

  var _pinTarget = null, _pinBuffer = '';
  window.onCashierClick = function(btn) {
    if (btn.dataset.hasPin === '1') { _pinTarget = btn; _pinBuffer = ''; document.getElementById('pinDots').textContent = ''; document.getElementById('pinModalTitle').textContent = '🔐 PIN — ' + btn.dataset.name; document.getElementById('pinModal').classList.add('show'); }
    else { selectCashier(btn, btn.dataset.name, btn.dataset.id); }
  };
  window.pinKey = function(k) {
    if (k === 'clear') { _pinBuffer = _pinBuffer.slice(0, -1); }
    else if (k === 'ok') { verifyPin(); return; }
    else { if (_pinBuffer.length >= 8) return; _pinBuffer += k; }
    document.getElementById('pinDots').textContent = '●'.repeat(_pinBuffer.length);
    if (_pinBuffer.length === 4) setTimeout(verifyPin, 150);
  };
  function verifyPin() {
    if (!_pinBuffer || !_pinTarget) return;
    fetch(API_BASE + '/pos/api/cashier/verify-pin/', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF }, body: JSON.stringify({ cashier_id: _pinTarget.dataset.id, pin: _pinBuffer }) })
    .then(function(r){ return r.json(); }).then(function(data) {
      if (data.ok) { selectCashier(_pinTarget, _pinTarget.dataset.name, _pinTarget.dataset.id); closePinModal(); }
      else { document.getElementById('pinDots').textContent = '❌ Pogrešan PIN'; _pinBuffer = ''; setTimeout(function(){ document.getElementById('pinDots').textContent = ''; }, 1200); }
    }).catch(function() { closePinModal(); });
  }
  window.closePinModal = function() { document.getElementById('pinModal').classList.remove('show'); _pinTarget = null; _pinBuffer = ''; };

  window.openShiftModal = function() { document.getElementById('shiftModal').classList.add('show'); loadShiftReport(); };
  window.closeShiftModal = function() { document.getElementById('shiftModal').classList.remove('show'); };
  function loadShiftReport() {
    var body = document.getElementById('shiftBody');
    body.innerHTML = '<div style="text-align:center;padding:1.5rem;color:var(--muted)">Učitavam...</div>';
    var url = window._currentCashierId ? API_BASE + '/pos/session/' + SESSION_ID + '/cashier/' + window._currentCashierId + '/report/' : API_BASE + '/pos/session/' + SESSION_ID + '/report/';
    fetch(url, { credentials:'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'} })
    .then(function(res) { if (res.redirected || res.status === 302) { body.innerHTML = '<div style="color:#ef4444;padding:1rem">Sesija istekla.</div>'; return Promise.reject('r'); } return res.json(); })
    .then(function(d) {
      var rHtml = d.receipts && d.receipts.length ? '<div class="shift-receipts">' + d.receipts.map(function(r){ return '<div class="shift-r-row"><span>' + r.vrijeme + ' — Račun #' + r.broj + '</span><strong>€' + parseFloat(r.ukupno).toFixed(2) + '</strong></div>'; }).join('') + '</div>' : '<p style="color:var(--muted);font-size:.8rem;margin-top:.5rem">Nema računa.</p>';
      body.innerHTML = [['Blagajnik',d.cashier,''],['Broj računa',d.racuna,''],['Rad',d.prvi+' — '+d.zadnji,''],['Gotovina','€'+parseFloat(d.gotovina).toFixed(2),'green'],['Kartica','€'+parseFloat(d.kartica).toFixed(2),''],['Vaučeri','€'+parseFloat(d.vavceri).toFixed(2),''],['<b>UKUPNO</b>','€'+parseFloat(d.ukupno).toFixed(2),'gold']].map(function(row){ return '<div class="shift-row"><span class="lbl">'+row[0]+'</span><span class="val '+row[2]+'">'+row[1]+'</span></div>'; }).join('') + rHtml;
    }).catch(function(e) { if (e !== 'r') body.innerHTML = '<div style="color:#ef4444;padding:1rem">Greška</div>'; });
  }
  window.printShiftReport = function() {
    var w = window.open('','_blank','width=380,height=550'); var b = document.getElementById('shiftBody');
    w.document.write('<html><head><title>Zaključak</title><style>body{font-family:monospace;padding:16px;font-size:12px} .shift-row{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #eee} .shift-receipts{margin-top:8px} .shift-r-row{display:flex;justify-content:space-between;font-size:11px;padding:2px 0}</style></head><body>');
    w.document.write('<h3 style="text-align:center">ZAKLJUČAK SMJENE</h3><p style="text-align:center;font-size:11px">' + new Date().toLocaleString('hr') + '</p><hr>');
    w.document.write(b.innerHTML + '</body></html>'); w.document.close(); setTimeout(function(){ w.print(); }, 300);
  };

  window.showToast = function(msg, duration) {
    var t = document.getElementById('posToast'); if (!t) return;
    t.textContent = msg; t.classList.add('show'); clearTimeout(window._toastTimer);
    window._toastTimer = setTimeout(function(){ t.classList.remove('show'); }, duration || 3000);
  };
  function updateCashierBar(name) {
    var bar = document.getElementById('activeCashierBar'); if (!bar) return;
    if (name) { bar.textContent = '👤 Aktivni blagajnik: ' + name; bar.classList.add('show'); } else { bar.classList.remove('show'); }
  }
  function selectCashier(el, name, id) {
    document.querySelectorAll('.cashier-btn').forEach(function(b){ b.classList.remove('active'); });
    if (el) el.classList.add('active');
    window._currentCashier = name || ''; window._currentCashierId = id || null;
    updateCashierBar(name);
    if (name) showToast('👤 ' + name + ' — prijavljen/a', 2500);
  }

  var _revolutPollTimer = null;
  window.payRevolut = function() {
    if (!SESSION_ID) { alert('Nema smjene!'); return; }
    if (!Object.keys(basket).length) return;
    var items = buildItemsPayload();
    fetch(API_BASE + '/pos/session/' + SESSION_ID + '/quick-pay/', { method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': CSRF}, body: JSON.stringify({items: items, method: 'REVOLUT', amount_paid: window._total, cashier: window._currentCashier || '', cashier_id: window._currentCashierId || ''}) })
    .then(function(r){ return r.json(); }).then(function(data) {
      if (!data.ok) { alert(data.error || 'Greška'); return; }
      var receiptId = data.receipt_id;
      document.getElementById('revolutAmount').textContent = '€' + parseFloat(data.total).toFixed(2);
      fetch(API_BASE + '/pos/revolut/pay/' + receiptId + '/', { method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': CSRF} })
      .then(function(r2){ return r2.json(); }).then(function(rev) {
        if (!rev.ok) { showSuccess(data.receipt_number, data.total, 0); clearBasket(); showToast('Naplata evidentirana (Revolut nije spojen)', 3000); return; }
        document.getElementById('revolutQR').innerHTML = '<img src="data:image/png;base64,' + (rev.qr_b64 || '') + '" style="width:200px;height:200px;image-rendering:pixelated"><br><a href="' + rev.checkout_url + '" target="_blank" style="color:#0075EB;font-size:.8rem">Otvori link</a>';
        document.getElementById('revolutModal').style.display = 'flex';
        document.getElementById('revolutStatus').textContent = 'Čekam plaćanje...';
        _revolutPollTimer = setInterval(function() {
          fetch(API_BASE + '/pos/revolut/status/' + receiptId + '/', {credentials: 'same-origin'}).then(function(s){ return s.json(); }).then(function(st) {
            if (st.status === 'completed') { clearInterval(_revolutPollTimer); document.getElementById('revolutStatus').innerHTML = '<span style="color:#22c55e;font-size:1.2rem">✓ PLAĆENO!</span>'; showSuccess(data.receipt_number, data.total, 0); clearBasket(); setTimeout(closeRevolutModal, 2000); }
            else if (st.status === 'failed') { clearInterval(_revolutPollTimer); document.getElementById('revolutStatus').innerHTML = '<span style="color:#ef4444">✗ Neuspješno</span>'; }
          });
        }, 2000);
      });
    }).catch(function(e) { alert('Greška: ' + e); });
  };
  window.closeRevolutModal = function() { document.getElementById('revolutModal').style.display = 'none'; if (_revolutPollTimer) { clearInterval(_revolutPollTimer); _revolutPollTimer = null; } };

  var ALL_PRODUCTS = [];
  (function(){
    document.querySelectorAll('.prod-btn').forEach(function(b){
      ALL_PRODUCTS.push({ id: b.dataset.id, name: b.dataset.name, price: b.dataset.price, tax: b.dataset.tax, cat: b.dataset.cat, weighable: b.dataset.weighable, unit: b.dataset.unit });
    });
    ALL_PRODUCTS.sort(function(a,b){ return a.name.localeCompare(b.name, 'hr'); });
  })();

  function buildQuickKeys(cat) {
    var grid = document.getElementById('qkGrid'); var label = document.getElementById('qkCatLabel');
    if (!grid) return;
    var filtered = cat ? ALL_PRODUCTS.filter(function(p){ return p.cat === cat; }) : ALL_PRODUCTS;
    var top12 = filtered.slice(0, 12);
    label.textContent = cat ? cat : 'Sve kategorije';
    if (!top12.length) { grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--muted);font-size:.78rem;padding:.5rem">Nema artikala</div>'; return; }
    grid.innerHTML = top12.map(function(p){
      return '<button class="qk-btn" id="qk-'+p.id+'" data-id="'+p.id+'" data-name="'+p.name.replace(/"/g,'&quot;')+'" data-price="'+p.price+'" data-tax="'+p.tax+'" data-cat="'+p.cat+'" data-weighable="'+p.weighable+'" data-unit="'+p.unit+'" onclick="qkAdd(this)"><div class="qk-name">'+p.name+'</div><div class="qk-price">€'+parseFloat(p.price).toFixed(2)+'</div><div class="qk-badge" id="qkb-'+p.id+'">0</div></button>';
    }).join('');
  }

  window.qkAdd = function(btn) {
    var rip = document.createElement('div'); rip.className = 'ripple'; rip.style.left = '50%'; rip.style.top = '50%'; btn.appendChild(rip); setTimeout(function(){ rip.remove(); }, 400);
    if (btn.dataset.weighable === '1') { var pb = document.getElementById('pb-'+btn.dataset.id); if (pb) { addProduct(pb); } else { _weighBtn = btn; document.getElementById('weightProductName').textContent = btn.dataset.name; document.getElementById('weightUnit').textContent = btn.dataset.unit||'kg'; var wi=document.getElementById('weightInput'); wi.value=''; document.getElementById('weightModal').classList.add('show'); setTimeout(function(){wi.focus();},80); } return; }
    var id = btn.dataset.id, name = btn.dataset.name;
    var price = parseFloat(btn.dataset.price), tax = parseFloat(btn.dataset.tax);
    if (basket[id]) { basket[id].qty += 1; } else { basket[id] = { name: name, price: price, tax: tax, qty: 1 }; }
    updateQtyBadge(id); updateQkBadge(id); renderBasket();
  };

  function updateQkBadge(id) { var b = document.getElementById('qkb-'+id); if (!b) return; var qty = basket[id] ? basket[id].qty : 0; b.textContent = qty; b.classList.toggle('show', qty > 0); }

  if (document.readyState !== 'loading') { buildQuickKeys(''); }
  else { document.addEventListener('DOMContentLoaded', function(){ buildQuickKeys(''); }); }

  (function(){
    var btns = document.querySelectorAll('.prod-btn'); var items = [];
    btns.forEach(function(b){ items.push({ id: b.dataset.id, name: b.dataset.name, price: b.dataset.price, tax: b.dataset.tax, cat: b.dataset.cat, weighable: b.dataset.weighable, unit: b.dataset.unit }); });
    if(items.length && window.cacheArticlesForOffline){ window.cacheArticlesForOffline(items); }
  })();
})();

  // ── Shift close 2-step flow ────────────────────────────────────────────────
  var _shiftExpectedCash = 0;

  window.openShiftModal = function() {
    document.getElementById('shiftModal').classList.add('show');
    document.getElementById('shiftStep1').style.display = '';
    document.getElementById('shiftStep2').style.display = 'none';
    loadShiftReport();
    // Load expected cash
    fetch(API_BASE + '/pos/session/' + SESSION_ID + '/report/', {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(function(r){return r.json()})
      .then(function(d){
        _shiftExpectedCash = parseFloat(d.gotovina || 0);
        var inp = document.getElementById('shiftCashInput');
        if (inp) inp.placeholder = _shiftExpectedCash.toFixed(2);
      }).catch(function(){});
    // Live diff
    var inp = document.getElementById('shiftCashInput');
    if (inp) inp.addEventListener('input', function() {
      var v = parseFloat(this.value) || 0;
      var diff = v - _shiftExpectedCash;
      var el = document.getElementById('shiftCashDiff');
      if (Math.abs(diff) < 0.01) { el.innerHTML = '<span style="color:#22c55e">✓ Točno</span>'; }
      else if (diff > 0) { el.innerHTML = '<span style="color:#f59e0b">Višak: +' + diff.toFixed(2) + ' €</span>'; }
      else { el.innerHTML = '<span style="color:#ef4444">Manjak: ' + diff.toFixed(2) + ' €</span>'; }
    });
  };

  window.shiftSkipCash = function() { document.getElementById('shiftCashInput').value = ''; shiftGoStep2(); };

  window.shiftGoStep2 = function() {
    var cash = document.getElementById('shiftCashInput').value || '0';
    // POST close session
    fetch(API_BASE + '/pos/session/' + SESSION_ID + '/close/', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type':'application/x-www-form-urlencoded', 'X-CSRFToken': CSRF},
      body: 'closing_cash=' + encodeURIComponent(cash)
    })
    .then(function(r) {
      // Close might redirect (302) — that's ok
      document.getElementById('shiftStep1').style.display = 'none';
      document.getElementById('shiftStep2').style.display = '';
      var diff = (parseFloat(cash) || 0) - _shiftExpectedCash;
      var diffText = Math.abs(diff) < 0.01 ? 'Gotovina OK' : (diff > 0 ? 'Višak: +' + diff.toFixed(2) + ' €' : 'Manjak: ' + diff.toFixed(2) + ' €');
      document.getElementById('shiftCloseSummary').textContent = 'Ukupno: €' + _shiftExpectedCash.toFixed(2) + ' | ' + diffText;
    })
    .catch(function() {
      document.getElementById('shiftStep1').style.display = 'none';
      document.getElementById('shiftStep2').style.display = '';
      document.getElementById('shiftCloseSummary').textContent = 'Smjena zatvorena';
    });
  };

  window.shiftZReport = function() {
    window.open(API_BASE + '/pos/session/' + SESSION_ID + '/zreport/', '_blank');
  };

  window.shiftShare = function() {
    openShare({type:'zreport', id: SESSION_ID, title: 'Z-izvještaj smjene'});
  };

  window.shiftFinish = function() {
    window.location.href = API_BASE + '/pos/';
  };
