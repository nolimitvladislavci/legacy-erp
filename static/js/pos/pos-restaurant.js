/* ═══ POS Restaurant — Tables, Receipts, Payment ═══
 * Extracted from restaurant.html
 * Reads config from #pos-config JSON block
 */
(function(){
  var cfg = {};
  try { cfg = JSON.parse(document.getElementById('pos-config').textContent); } catch(e){}

  var SESSION_ID = cfg.session_id || null;
  var CSRF       = cfg.csrf || getCsrf();
  var INV        = cfg.inventory || [];

  var activeRid = null, activeTotal = 0, payMethod = 'CASH', selItem = null, tipAmount = 0;

  window.selectTable = function(el) {
    document.querySelectorAll('.tbl-card').forEach(function(c){ c.classList.remove('tbl-selected'); });
    el.classList.add('tbl-selected');
    var rid = el.dataset.rid, tNum = el.dataset.table;
    document.getElementById('panelTitle').textContent = tNum ? 'Stol ' + tNum : el.querySelector('.tbl-num').textContent;
    if (rid) { loadReceipt(parseInt(rid)); } else { openNewBonModal(tNum || null); }
  };

  function loadReceipt(rid) {
    fetch('/pos/receipt/' + rid + '/json/').then(function(r){ return r.json(); }).then(function(data) {
      if (!data.ok) { alert(data.error||'Greška'); return; }
      activeRid = rid; activeTotal = parseFloat(data.total||0);
      renderItems(data.items||[]); updateTotals(data.subtotal||data.total||0, data.tax_amount||0, data.total||0);
      document.getElementById('emptyHint').style.display = 'none';
      document.getElementById('itemsZone').style.display = '';
      document.getElementById('sideFooter').style.display = '';
    });
  }

  function renderItems(items) {
    document.getElementById('itemsList').innerHTML = items.map(function(it){
      return '<div class="r-item"><div class="r-item-name">' + it.description + '</div><div class="r-item-qty">&times;' + parseFloat(it.quantity) + '</div><div class="r-item-price">&euro;' + parseFloat(it.line_total||0).toFixed(2) + '</div></div>';
    }).join('');
  }

  function updateTotals(net, tax, total) {
    document.getElementById('fNeto').textContent = '€'+parseFloat(net).toFixed(2);
    document.getElementById('fPdv').textContent = '€'+parseFloat(tax).toFixed(2);
    document.getElementById('fTotal').textContent = '€'+parseFloat(total).toFixed(2);
    activeTotal = parseFloat(total);
  }

  window.closePanel = function() {
    activeRid = null;
    document.querySelectorAll('.tbl-card').forEach(function(c){ c.classList.remove('tbl-selected'); });
    document.getElementById('panelTitle').textContent = 'Odaberite stol';
    document.getElementById('emptyHint').style.display = '';
    document.getElementById('itemsZone').style.display = 'none';
    document.getElementById('sideFooter').style.display = 'none';
  };

  var acInput = document.getElementById('acInput'), acList = document.getElementById('acList');
  if (acInput) {
    acInput.addEventListener('input', function(){
      var q = acInput.value.toLowerCase(); if (!q){ acList.classList.remove('open'); return; }
      var hits = INV.filter(function(i){ return i.name.toLowerCase().includes(q); }).slice(0,30);
      acList.innerHTML = hits.map(function(i){ return '<div class="ac-item" onclick="pickItem(' + i.id + ')"><span>' + i.name + '</span><span class="ac-price">&euro;' + parseFloat(i.price).toFixed(2) + '</span></div>'; }).join('') || '<div class="ac-item" style="color:var(--muted)">Nema rezultata</div>';
      acList.classList.add('open');
    });
    document.addEventListener('click', function(e){ if (!acInput.contains(e.target) && !acList.contains(e.target)) acList.classList.remove('open'); });
  }
  window.pickItem = function(id) { selItem = INV.find(function(i){ return i.id === id; }); if (!selItem) return; acInput.value = selItem.name; acList.classList.remove('open'); document.getElementById('acQty').focus(); };

  window.addItemToReceipt = function() {
    if (!activeRid){ alert('Odaberite stol/bon'); return; } if (!selItem){ alert('Odaberite artikal'); return; }
    var qty = parseFloat(document.getElementById('acQty').value)||1;
    fetch('/pos/receipt/' + activeRid + '/add-item/', { method:'POST', headers:{'X-CSRFToken':CSRF,'Content-Type':'application/json'}, body:JSON.stringify({inventory_item_id:selItem.id,description:selItem.name,quantity:qty,unit_price:selItem.price,tax_rate:selItem.tax}) })
    .then(function(r){ return r.json(); }).then(function(data) {
      if (data.ok){ renderItems(data.items||[]); updateTotals(data.subtotal||data.total||0, data.tax_amount||0, data.total||0); acInput.value=''; acList.classList.remove('open'); document.getElementById('acQty').value='1'; selItem=null;
        var card = document.querySelector('.tbl-card[data-rid="' + activeRid + '"]'); if (card){ var t=card.querySelector('.tbl-total'); if(t) t.textContent='€'+parseFloat(data.total).toFixed(2); }
      } else { alert(data.error||'Greška'); }
    });
  };

  window.openPay = function(method){
    if (!activeRid){ alert('Odaberite bon'); return; } payMethod = method; tipAmount = 0;
    var tc = document.getElementById('tipCustom'); if(tc) tc.value = '';
    var td = document.getElementById('tipDisplay'); if(td) td.textContent = '';
    document.querySelectorAll('#tipSection .qc').forEach(function(b){ b.style.background = ''; });
    var tb0 = document.getElementById('tipBtn0'); if(tb0) tb0.style.background = 'rgba(201,168,76,.2)';
    var ts = document.getElementById('tipSection'); if(ts) ts.style.display = 'block';
    document.getElementById('payTitle').textContent = method==='CASH'?'Naplata – gotovina':'Naplata – kartica';
    document.getElementById('payTtl').textContent = '€'+activeTotal.toFixed(2);
    document.getElementById('cashInput').value = ''; document.getElementById('chgLbl').textContent = '';
    if (method==='CARD'){ document.getElementById('cashInput').value = activeTotal.toFixed(2); document.getElementById('cashInput').disabled = true; }
    else { document.getElementById('cashInput').disabled = false; setTimeout(function(){ document.getElementById('cashInput').focus(); },80); }
    document.getElementById('payOverlay').classList.add('open');
  };
  window.closePay = function(){ document.getElementById('payOverlay').classList.remove('open'); };
  window.setExact = function(){ document.getElementById('cashInput').value=activeTotal.toFixed(2); calcChg(); };
  window.addCash = function(n){ var c=parseFloat(document.getElementById('cashInput').value)||0; document.getElementById('cashInput').value=(c+n).toFixed(2); calcChg(); };
  window.calcChg = function(){ if(payMethod==='CARD'){ document.getElementById('chgLbl').textContent=''; return; } var paid=parseFloat(document.getElementById('cashInput').value)||0; var chg=paid-activeTotal; document.getElementById('chgLbl').textContent = chg>=0?'Kusur: €'+chg.toFixed(2):'Nedostaje: €'+Math.abs(chg).toFixed(2); };

  window.setTip = function(amount) { tipAmount = amount; document.querySelectorAll('#tipSection .qc').forEach(function(b){ b.style.background = ''; }); if (event && event.target) event.target.style.background = 'rgba(201,168,76,.2)'; var tc = document.getElementById('tipCustom'); if(tc) tc.value = ''; var td = document.getElementById('tipDisplay'); if(td) td.textContent = amount > 0 ? 'Napojnica: +€' + amount.toFixed(2) : ''; };
  window.setCustomTip = function() { var val = parseFloat(document.getElementById('tipCustom').value) || 0; tipAmount = Math.max(0, val); document.querySelectorAll('#tipSection .qc').forEach(function(b){ b.style.background = ''; }); var td = document.getElementById('tipDisplay'); if(td) td.textContent = tipAmount > 0 ? 'Napojnica: +€' + tipAmount.toFixed(2) : ''; };

  var paying = false;
  window.confirmPay = function(){
    if(paying) return; var paid=parseFloat(document.getElementById('cashInput').value)||0;
    if(payMethod==='CASH'&&paid<activeTotal){ alert('Primljeni iznos je manji od ukupnog!'); return; }
    paying=true; document.getElementById('payConfirmBtn').textContent='…';
    var tipPromise = tipAmount > 0 ? fetch('/pos/receipt/' + activeRid + '/add-item/', { method:'POST', headers:{'X-CSRFToken':CSRF,'Content-Type':'application/json'}, body: JSON.stringify({ description: 'Napojnica (Trinkgeld)', quantity: '1', unit_price: tipAmount.toFixed(2), tax_rate: '0', is_tip: true }) }).catch(function(e){ console.warn('Tip fail:', e); }) : Promise.resolve();
    tipPromise.then(function(){ return fetch('/pos/receipt/' + activeRid + '/pay/', { method:'POST', headers:{'X-CSRFToken':CSRF,'Content-Type':'application/json'}, body:JSON.stringify({method:payMethod,amount_paid:(paid+tipAmount).toFixed(2)}) }); })
    .then(function(r){ return r.json(); }).then(function(data){
      paying=false; document.getElementById('payConfirmBtn').textContent='Naplati';
      if(data.ok){ closePay(); document.getElementById('okNum').textContent = 'Bon #' + data.receipt_number; document.getElementById('okTotal').textContent = '€' + parseFloat(data.total).toFixed(2); document.getElementById('okChg').textContent = parseFloat(data.change)>0?'Kusur: €'+parseFloat(data.change).toFixed(2):''; document.getElementById('okPrint').href = data.print_url||'#'; document.getElementById('okOverlay').classList.add('open'); setTimeout(closeOk, 5000); }
      else { alert(data.error||'Greška pri naplati'); }
    }).catch(function(){ paying=false; document.getElementById('payConfirmBtn').textContent='Naplati'; });
  };
  window.closeOk = function(){ document.getElementById('okOverlay').classList.remove('open'); location.reload(); };

  window.openNewBonModal = function(tableNum){ document.getElementById('newBonTable').value = tableNum||''; document.getElementById('newBonOverlay').classList.add('open'); };
  window.closeNewBon = function(){ document.getElementById('newBonOverlay').classList.remove('open'); };
  var creating = false;
  window.createBon = function(){
    if(creating||!SESSION_ID){ alert('Nema aktivne smjene'); return; } creating=true;
    var tableNum = document.getElementById('newBonTable').value.trim()||null;
    fetch('/pos/session/' + SESSION_ID + '/new-receipt/', { method:'POST', headers:{'X-CSRFToken':CSRF,'Content-Type':'application/json'}, body:JSON.stringify({table_number:tableNum?parseInt(tableNum):null}) })
    .then(function(r){ return r.json(); }).then(function(data){ creating=false; if(data.ok){ closeNewBon(); location.reload(); } else { alert(data.error||'Greška'); } });
  };

  // Pfand for restaurant
  window.addPfandReturn = function(id, name, price) {
    if(!activeRid) return;
    fetch('/pos/receipt/'+activeRid+'/add-item/',{ method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CSRF}, body:JSON.stringify({inventory_item_id:id,quantity:1,unit_price:price,description:name,is_pfand_return:true}) })
    .then(function(){ if(typeof closePfandModal==='function') closePfandModal(); loadReceipt(activeRid); });
  };
})();
