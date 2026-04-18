/* ═══ POS Receipt Detail — Autocomplete, Payment, Storno ═══
 * Extracted from receipt.html
 * Reads config from #pos-config JSON block
 */
(function(){
  var cfg = {};
  try { cfg = JSON.parse(document.getElementById('pos-config').textContent); } catch(e){}

  var INV = cfg.inventory || [];
  var recTotal = parseFloat(cfg.receipt_total) || 0;

  window.quickAdd = function(itemId) {
    var item = INV.find(function(i){ return String(i.id) === String(itemId); });
    if (!item) {
      fetch('/hr/pos/api/item/' + itemId + '/').then(function(r){ return r.json(); }).then(function(d){
        if(d.id) { INV.push({id:d.id, name:d.name, price:d.price, tax:d.tax, bc:d.bc||'', sku:d.sku||'', unit:''}); quickAdd(itemId); }
        else { showToast('Artikl nije pronađen', 'error'); }
      }).catch(function(){ showToast('Greška', 'error'); });
      return;
    }
    var btn = event && event.target ? event.target.closest('.qk-btn') : null;
    if (btn) { btn.style.opacity='0.5'; btn.style.pointerEvents='none'; }
    var form = new FormData();
    form.append('inventory_item_id', item.id); form.append('description', item.name);
    form.append('quantity', '1'); form.append('unit_price', item.price);
    form.append('tax_rate', item.tax); form.append('barcode', item.bc || '');
    form.append('csrfmiddlewaretoken', getCsrf());
    var formEl = document.getElementById('aiForm');
    if (!formEl) { showToast('Bon je zatvoren', 'warn'); return; }
    fetch(formEl.action, {method:'POST', body:form, credentials:'same-origin', redirect:'follow'})
      .then(function(r){ if(r.ok||r.redirected) location.reload(); else { showToast('Greška: '+r.status, 'error'); if(btn){btn.style.opacity='1';btn.style.pointerEvents='auto';} } })
      .catch(function(e){ showToast('Greška: '+e.message, 'error'); if(btn){btn.style.opacity='1';btn.style.pointerEvents='auto';} });
  };

  var camStream = null;
  window.openCamScanner = function() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { showToast('Kamera nije dostupna', 'warn'); return; }
    var ov = document.getElementById('camOverlay');
    if (ov) { ov.style.display='flex'; startCam(); return; }
    ov = document.createElement('div'); ov.id='camOverlay';
    ov.style.cssText='position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.95);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px';
    ov.innerHTML = '<div style="color:#fff;font-size:1rem;margin-bottom:12px;font-weight:600">Skeniraj barkod kamerom</div><video id="camVideo" autoplay playsinline style="width:90%;max-width:400px;border-radius:10px;border:2px solid var(--gold,#c9a84c)"></video><canvas id="camCanvas" style="display:none"></canvas><div id="camStatus" style="color:var(--gold,#c9a84c);margin-top:10px;font-size:.85rem">Cekam dozvolu kamere...</div><div style="margin-top:12px;display:flex;gap:10px"><button onclick="closeCamScanner()" style="padding:10px 28px;border-radius:8px;border:1px solid #555;background:#222;color:#fff;cursor:pointer">Zatvori</button><button onclick="manualBarcodeInput()" style="padding:10px 28px;border-radius:8px;border:1px solid var(--gold,#c9a84c);background:#1a1a0a;color:var(--gold,#c9a84c);cursor:pointer">Rucni unos</button></div>';
    document.body.appendChild(ov); startCam();
  };
  window.closeCamScanner = function() { var ov=document.getElementById('camOverlay'); if(ov) ov.style.display='none'; if(camStream){camStream.getTracks().forEach(function(t){t.stop();});camStream=null;} };
  window.manualBarcodeInput = function() { closeCamScanner(); var el=document.getElementById('bcIn'); if(el){el.focus();el.select();} };
  function startCam() {
    var video=document.getElementById('camVideo'), status=document.getElementById('camStatus');
    navigator.mediaDevices.getUserMedia({video:{facingMode:'environment',width:{ideal:1280},height:{ideal:720}}})
      .then(function(stream){camStream=stream;video.srcObject=stream;status.textContent='Kamera aktivna';scanFrame();})
      .catch(function(e){ var m='Kamera nedostupna.'; if(e.name==='NotAllowedError') m='Dozvola za kameru je odbijena.'; status.textContent=m; status.style.color='#ef4444'; });
  }
  function scanFrame() {
    if(!camStream)return; var v=document.getElementById('camVideo'),c=document.getElementById('camCanvas');
    if(!v||v.readyState<2){setTimeout(scanFrame,200);return;}
    c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);
    if('BarcodeDetector' in window){ new BarcodeDetector({formats:['ean_13','ean_8','code_128','qr_code','code_39']}).detect(c).then(function(bc){if(bc.length>0){closeCamScanner();document.getElementById('bcIn').value=bc[0].rawValue;lookupBC();return;}setTimeout(scanFrame,150);}).catch(function(){setTimeout(scanFrame,300);}); }
    else { document.getElementById('camStatus').innerHTML='Preglednik ne podrzava skeniranje.<br>Koristite Chrome ili unesite rucno.'; document.getElementById('camStatus').style.color='#f59e0b'; }
  }

  var acInput = document.getElementById('acInput'), acDropdown = document.getElementById('acDropdown'), acClear = document.getElementById('acClear'), acIdx = -1;
  if (acInput) {
    acInput.addEventListener('input', function() {
      acClear.style.display = this.value ? 'block' : 'none';
      var ql = this.value.toLowerCase();
      var matches = ql.length < 1 ? [] : INV.filter(function(i){ return i.name.toLowerCase().includes(ql) || i.sku.toLowerCase().includes(ql); }).slice(0, 30);
      if (!matches.length) { acDropdown.style.display = 'none'; return; }
      acDropdown.innerHTML = matches.map(function(m, i) { return '<div class="ac-item" data-idx="'+i+'" onclick="selectAC('+INV.indexOf(m)+')"><span class="ac-item-name">'+m.name+' <span class="ac-item-meta">'+m.sku+'</span></span><span class="ac-item-price">&euro;'+parseFloat(m.price).toFixed(2)+'</span></div>'; }).join('');
      acDropdown.style.display = 'block'; acIdx = -1;
    });
    acInput.addEventListener('keydown', function(e) {
      var items = acDropdown.querySelectorAll('.ac-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); acIdx = Math.min(acIdx+1, items.length-1); items.forEach(function(el,i){ el.classList.toggle('highlighted',i===acIdx); }); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); acIdx = Math.max(acIdx-1, 0); items.forEach(function(el,i){ el.classList.toggle('highlighted',i===acIdx); }); }
      else if (e.key === 'Enter' && acIdx >= 0) { e.preventDefault(); if(items[acIdx]) items[acIdx].click(); }
      else if (e.key === 'Escape') { acDropdown.style.display='none'; }
    });
    document.addEventListener('click', function(e) { if (!e.target.closest('#acInput') && !e.target.closest('#acDropdown')) acDropdown.style.display='none'; });
  }
  window.selectAC = function(i) {
    var m = INV[i]; if (!m) return;
    document.getElementById('inv_id').value = m.id; document.getElementById('desc_f').value = m.name;
    document.getElementById('price_f').value = m.price; document.getElementById('tax_f').value = m.tax;
    document.getElementById('bc_field').value = m.bc; acInput.value = m.name;
    acClear.style.display = 'block'; acDropdown.style.display = 'none';
    document.getElementById('qty_f').focus(); document.getElementById('qty_f').select();
  };
  window.clearAC = function() { acInput.value = ''; acClear.style.display = 'none'; acDropdown.style.display = 'none'; document.getElementById('inv_id').value = ''; document.getElementById('bc_field').value = ''; };

  window.lookupBC = function() {
    var bc = document.getElementById('bcIn').value.trim(); if (!bc) return;
    fetch('/pos/api/barcode/?barcode=' + encodeURIComponent(bc)).then(function(r){ return r.json(); }).then(function(d) {
      if (d.found) { document.getElementById('inv_id').value=d.id; document.getElementById('desc_f').value=d.name; document.getElementById('price_f').value=d.price; document.getElementById('tax_f').value=d.tax_rate; document.getElementById('bc_field').value=bc; document.getElementById('bcIn').value=''; document.getElementById('qty_f').focus(); }
      else { showToast('Artikl nije pronađen: ' + bc, 'error'); }
    });
  };
  var bcIn = document.getElementById('bcIn');
  if (bcIn) bcIn.addEventListener('keydown', function(e) { if (e.key === 'Enter') { e.preventDefault(); lookupBC(); } });

  window.setM = function(v, el) { document.getElementById('payMethod').value = v; document.querySelectorAll('.mtab').forEach(function(t){ t.classList.remove('active'); }); el.classList.add('active'); };
  window.calcChg = function() { var p = parseFloat(document.getElementById('amtPaid').value) || 0; var c = Math.max(0, p - recTotal); document.getElementById('chgVal').textContent = '€' + c.toFixed(2); document.getElementById('chgBox').classList.toggle('show', p > recTotal + 0.001); };
  window.setExact = function() { document.getElementById('amtPaid').value = recTotal.toFixed(2); calcChg(); };
  window.addCash = function(n) { var cur = parseFloat(document.getElementById('amtPaid').value) || 0; document.getElementById('amtPaid').value = (cur + n).toFixed(2); calcChg(); };

  window.openStornoModal = function() { document.getElementById('stornoModal').style.display = 'flex'; };
  window.closeStornoModal = function() { document.getElementById('stornoModal').style.display = 'none'; };
  window.onReasonChange = function(val) { document.getElementById('stornoReasonOther').style.display = val === 'Ostalo' ? 'block' : 'none'; };
  window.submitStorno = function() { var sel = document.getElementById('stornoReasonSelect').value; var other = document.getElementById('stornoReasonOther').value.trim(); document.getElementById('cancelReasonHidden').value = sel === 'Ostalo' ? (other || 'Ostalo') : sel; document.getElementById('cancelForm').submit(); };

  window.guardSubmit = function(form, loadingText, isPayment) {
    var btn = isPayment ? document.getElementById('payBtn') : document.getElementById('addBtn');
    if (!btn || btn.dataset.submitting === '1') return false;
    btn.dataset.submitting = '1'; btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>&nbsp;' + loadingText; return true;
  };
  window.addEventListener('pageshow', function() { ['payBtn','addBtn'].forEach(function(id) { var b = document.getElementById(id); if (b) { b.disabled = false; delete b.dataset.submitting; } }); });

  window.addPfandReturn = function(id, name, price) {
    var form = document.getElementById('aiForm'); if (!form) return;
    var csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch(form.action, { method:'POST', headers:{'X-CSRFToken':csrf}, body:new URLSearchParams({csrfmiddlewaretoken:csrf, inventory_item:id, quantity:1, is_pfand_return:'true'}) }).then(function(r){if(r.ok)location.reload()});
    if(typeof closePfandModal==='function') closePfandModal();
  };

  window.showToast = function(msg, type) {
    var t = document.getElementById("posToast"); if(!t) return;
    t.textContent = msg; t.style.borderLeftColor = type==="error" ? "#ef4444" : type==="warn" ? "#f59e0b" : "var(--gold,#c9a84c)";
    t.style.display = "block"; clearTimeout(window._toastTimer);
    window._toastTimer = setTimeout(function(){ t.style.display="none"; }, 3000);
  };
})();
