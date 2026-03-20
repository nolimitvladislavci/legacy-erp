/* ═══ POS Core — Theme, Offline, Toast ═══
 * Extracted from base_pos.html inline scripts
 * Loaded on ALL POS pages via base_pos.html
 */

// ── Theme Toggle ──────────────────────────────────────────────────────────────
function togglePosTheme(){
  var html=document.documentElement;
  var current=html.getAttribute('data-theme');
  var next=current==='light'?null:'light';
  if(next){html.setAttribute('data-theme','light');localStorage.setItem('fina-theme','light');}
  else{html.removeAttribute('data-theme');localStorage.setItem('fina-theme','dark');}
  updatePosThemeBtn();
}
function updatePosThemeBtn(){
  var btn=document.getElementById('pos-theme-btn');
  if(!btn)return;
  var isLight=document.documentElement.getAttribute('data-theme')==='light';
  btn.innerHTML=isLight?'&#9728;':'&#9790;';
}
updatePosThemeBtn();

// ── POS Offline Support ──────────────────────────────────────────────────────
(function(){
  var OFFLINE_KEY = 'pos_offline_sales';
  var ITEMS_KEY = 'pos_cached_items';

  window.posIsOnline = navigator.onLine;
  window.addEventListener('online', function(){
    window.posIsOnline = true;
    document.body.classList.remove('pos-offline');
    flushOfflineSales();
    showPosToast('Povezano! Sinkroniziram podatke...', 'success');
  });
  window.addEventListener('offline', function(){
    window.posIsOnline = false;
    document.body.classList.add('pos-offline');
    showPosToast('Offline mod — prodaja nastavlja lokalno', 'warning');
  });

  window.cacheArticlesForOffline = function(items){
    try { localStorage.setItem(ITEMS_KEY, JSON.stringify(items)); }
    catch(e) { console.warn('Cache full:', e); }
  };

  window.getOfflineArticles = function(){
    try { return JSON.parse(localStorage.getItem(ITEMS_KEY) || '[]'); }
    catch(e) { return []; }
  };

  window.queueOfflineSale = function(saleData){
    var q = JSON.parse(localStorage.getItem(OFFLINE_KEY) || '[]');
    saleData._offline_ts = Date.now();
    saleData._offline_id = 'OFF-' + Date.now() + '-' + Math.random().toString(36).substr(2,5);
    q.push(saleData);
    localStorage.setItem(OFFLINE_KEY, JSON.stringify(q));
    showPosToast('Prodaja spremljena offline (#' + q.length + ')', 'info');
    return saleData._offline_id;
  };

  function flushOfflineSales(){
    var q = JSON.parse(localStorage.getItem(OFFLINE_KEY) || '[]');
    if(!q.length) return;
    var total = q.length;
    var sent = 0;
    q.forEach(function(sale){
      fetch(sale._url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
        body: JSON.stringify(sale)
      }).then(function(){
        sent++;
        if(sent >= total){
          localStorage.setItem(OFFLINE_KEY, '[]');
          showPosToast('Sinkronizirano ' + total + ' offline prodaja!', 'success');
        }
      }).catch(function(e){
        console.error('Flush failed:', e);
      });
    });
  }

  window.showPosToast = function(msg, type){
    var el = document.createElement('div');
    el.className = 'pos-toast pos-toast-' + (type||'info');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function(){ el.classList.add('show'); }, 10);
    setTimeout(function(){ el.remove(); }, 4000);
  };

  if(!navigator.onLine) document.body.classList.add('pos-offline');
  if(navigator.onLine) setTimeout(flushOfflineSales, 2000);
})();

// ── CSRF Helper (global) ─────────────────────────────────────────────────────
function getCsrf() {
  var v = document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}


// ── B-02: Upozorenje pri odjavi s otvorenim bonovima ─────────────────────────
(function(){
  window.addEventListener('beforeunload', function(e){
    // Check if there are items in the receipt area
    var receiptItems = document.querySelectorAll('.bon-row, .receipt-item, .b-row');
    var hasItems = false;
    receiptItems.forEach(function(el){
      if(el.offsetParent !== null) hasItems = true; // visible items
    });
    if(hasItems){
      e.preventDefault();
      e.returnValue = 'Imate otvoren bon s artiklima. Jeste li sigurni da zelite napustiti stranicu?';
      return e.returnValue;
    }
  });
})();
