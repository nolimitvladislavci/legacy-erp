/**
 * LIMIT Connect — core.js
 * Sav globalni JS izvučen iz base.html inline <script> blokova.
 * Čita konfiguraciju iz window.FC (postavlja se u base.html).
 */
(function(){
'use strict';

// ═══ HELPERS ═══════════════════════════════════════════════════════════════
function getCsrf(){
  var m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}
function escHtml(s){
  return s.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
function _escH(s){
  if(!s) return '';
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ═══ OFFLINE BAR ═══════════════════════════════════════════════════════════
function updateOfflineBar(){
  var bar = document.getElementById('offlineBar');
  var msg = document.getElementById('offlineMsg');
  var qBadge = document.getElementById('offlineQueue');
  // Also check WorktimeOffline pending
  if (window.WorktimeOffline) {
    WorktimeOffline.getPendingCount(function(c) {
      if (c > 0 && qBadge) {
        var existing = qBadge.textContent || '';
        qBadge.textContent = existing + (existing ? ' + ' : '') + c + ' worktime';
      }
    });
  }
  if(!bar) return;
  if(!navigator.onLine){
    bar.style.display = 'block';
    document.body.style.paddingTop = '36px';
    msg.textContent = 'Nema internetske veze — podaci se spremaju lokalno';
    var q = JSON.parse(localStorage.getItem('fina_offline_queue')||'[]');
    var posQ = JSON.parse(localStorage.getItem('pos_offline_sales')||'[]');
    var total = q.length + posQ.length;
    qBadge.textContent = total > 0 ? total+' u redu čekanja' : '';
  } else {
    bar.style.display = 'none';
    document.body.style.paddingTop = '';
  }
}
window.addEventListener('online', function(){
  updateOfflineBar();
  var bar = document.getElementById('offlineBar');
  if(!bar) return;
  bar.style.background = '#22c55e';
  document.getElementById('offlineMsg').textContent = 'Veza uspostavljena — sinkronizacija...';
  bar.style.display = 'block';
  setTimeout(function(){ bar.style.display='none'; document.body.style.paddingTop=''; }, 3000);
});
window.addEventListener('offline', updateOfflineBar);
updateOfflineBar();

// ═══ OFFLINE QUEUE ════════════════════════════════════════════════════════
(function(){
  var QUEUE_KEY = 'fina_offline_queue';
  function getQueue(){ try{ return JSON.parse(localStorage.getItem(QUEUE_KEY)||'[]'); }catch(e){ return []; } }
  function saveQueue(q){ localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); }

  window.finaQueueRequest = function(url, method, body){
    var q = getQueue();
    q.push({ url: url, method: method || 'POST', body: body, ts: Date.now() });
    saveQueue(q);
    var qBadge = document.getElementById('offlineQueue');
    if(qBadge) qBadge.textContent = q.length + ' u redu čekanja';
  };

  function flushQueue(){
    var q = getQueue();
    if(!q.length) return;
    var remaining = [];
    var done = Promise.resolve();
    q.forEach(function(item){
      done = done.then(function(){
        return fetch(item.url, {
          method: item.method,
          headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
          body: typeof item.body === 'string' ? item.body : JSON.stringify(item.body)
        }).then(function(r){
          if(!r.ok) remaining.push(item);
        }).catch(function(){ remaining.push(item); });
      });
    });
    done.then(function(){
      saveQueue(remaining);
    });
  }

  window.addEventListener('online', function(){
    flushQueue();
    if('serviceWorker' in navigator && navigator.serviceWorker.controller){
      navigator.serviceWorker.ready.then(function(reg){
        if('sync' in reg) reg.sync.register('fina-offline-sync');
      });
    }
  });

  if('serviceWorker' in navigator){
    navigator.serviceWorker.addEventListener('message', function(e){
      if(e.data && e.data.type === 'FLUSH_QUEUE') flushQueue();
    });
  }

  if(navigator.onLine) flushQueue();
})();

// ═══ TOAST AUTO-DISMISS ══════════════════════════════════════════════════
function initToasts(){
  document.querySelectorAll('.toast-msg').forEach(function(el){
    var delay = 8000; // default for error
    if(el.classList.contains('alert-success')) delay = 4000;
    else if(el.classList.contains('alert-info')) delay = 5000;
    else if(el.classList.contains('alert-warning')) delay = 6000;
    setTimeout(function(){
      el.style.transition = 'all 0.5s';
      el.style.opacity = '0';
      el.style.transform = 'translateX(20px)';
      setTimeout(function(){ el.remove(); }, 500);
    }, delay);
  });
}

// ═══ SIDEBAR ═════════════════════════════════════════════════════════════
window.openSidebar = function(){
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
};
window.closeSidebar = function(){
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
  document.body.style.overflow = '';
};
window.toggleGroup = function(btn){
  var links = btn.nextElementSibling;
  if(links.classList.contains('collapsed')){
    links.classList.remove('collapsed');
    links.style.maxHeight = links.scrollHeight + 'px';
    btn.classList.remove('collapsed');
  } else {
    links.classList.add('collapsed');
    links.style.maxHeight = '0';
    btn.classList.add('collapsed');
  }
};

function initSidebarGroups(){
  var path = window.location.pathname;
  document.querySelectorAll('.sidebar-group').forEach(function(g){
    var links = g.querySelector('.sidebar-group-links');
    var btn = g.querySelector('.sidebar-group-toggle');
    var hasActive = false;
    links.querySelectorAll('a').forEach(function(a){
      var href = a.getAttribute('href');
      if(href && path.startsWith(href) && href !== '/'){
        a.classList.add('active');
        hasActive = true;
      }
    });
    if(hasActive){
      links.classList.remove('collapsed');
      links.style.maxHeight = links.scrollHeight + 'px';
      btn.classList.remove('collapsed');
    } else if(!links.classList.contains('collapsed')){
      links.style.maxHeight = links.scrollHeight + 'px';
    } else {
      links.style.maxHeight = '0';
      btn.classList.add('collapsed');
    }
  });
}

// Swipe to open/close sidebar
var touchStartX = 0;
document.addEventListener('touchstart', function(e){ touchStartX = e.touches[0].clientX; });
document.addEventListener('touchend', function(e){
  var diff = e.changedTouches[0].clientX - touchStartX;
  if(touchStartX < 30 && diff > 60) window.openSidebar();
  if(diff < -60 && document.getElementById('sidebar').classList.contains('open')) window.closeSidebar();
});

// ═══ SLIM SIDEBAR ════════════════════════════════════════════════════════
window.toggleSlimSidebar = function(){
  var sidebar = document.getElementById('sidebar');
  var main = document.querySelector('.main');
  var isSlim = sidebar.classList.toggle('slim');
  main.classList.toggle('slim-main', isSlim);
  main.style.marginLeft = isSlim ? '60px' : '260px';
  localStorage.setItem('fc_sidebar_slim', isSlim ? '1' : '0');
};

function restoreSlimSidebar(){
  if(localStorage.getItem('fc_sidebar_slim') === '1'){
    var sidebar = document.getElementById('sidebar');
    var main = document.querySelector('.main');
    if(sidebar && main && window.innerWidth > 768){
      sidebar.classList.add('slim');
      main.classList.add('slim-main');
      main.style.marginLeft = '60px';
    }
  }
}

function wrapSidebarLinkText(){
  var selectors = ['.sidebar a', '.sidebar-footer a'];
  selectors.forEach(function(sel){
    document.querySelectorAll(sel).forEach(function(a){
      var nodes = a.childNodes;
      for(var i = 0; i < nodes.length; i++){
        if(nodes[i].nodeType === 3 && nodes[i].textContent.trim()){
          var span = document.createElement('span');
          span.textContent = nodes[i].textContent;
          a.replaceChild(span, nodes[i]);
        }
      }
    });
  });
}

// ═══ VAPID WEB PUSH ═════════════════════════════════════════════════════
(function(){
  if(!('serviceWorker' in navigator) || !('PushManager' in window)) return;

  var VAPID_KEY = null;

  fetch('/push/vapid-public-key/')
    .then(function(r){ return r.json(); })
    .then(function(d){
      VAPID_KEY = d.public_key;
      return navigator.serviceWorker.register('/sw.js');
    })
    .then(function(reg){
      return reg.pushManager.getSubscription().then(function(sub){
        if(sub) syncSubscription(sub);
      });
    })
    .catch(function(){});

  window.requestPushPermission = function(callback){
    if(!VAPID_KEY){ if(callback) callback(false); return; }
    Notification.requestPermission().then(function(perm){
      if(perm !== 'granted'){ if(callback) callback(false); return; }
      navigator.serviceWorker.ready.then(function(reg){
        var appKey = urlBase64ToUint8(VAPID_KEY);
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: appKey
        });
      }).then(function(sub){
        syncSubscription(sub);
        if(callback) callback(true);
      }).catch(function(){ if(callback) callback(false); });
    });
  };

  function syncSubscription(sub){
    fetch('/push/subscribe/', {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify(sub.toJSON())
    }).catch(function(){});
  }

  function urlBase64ToUint8(base64String){
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g,'+').replace(/_/g,'/');
    var raw = atob(base64);
    var output = new Uint8Array(raw.length);
    for(var i = 0; i < raw.length; ++i) output[i] = raw.charCodeAt(i);
    return output;
  }
})();

// Push opt-in check
(function(){
  if('Notification' in window && Notification.permission === 'default'){
    var el = document.getElementById('push-opt-in');
    if(el) el.style.display = 'block';
  }
})();

// ═══ PASSWORD TOGGLE ════════════════════════════════════════════════════
(function(){
  var EO='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:block"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EC='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:block"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
  function addToggle(inp){
    if(inp._pwDone) return; inp._pwDone = true;
    var w = document.createElement('div');
    w.style.cssText = 'position:relative;display:block;';
    inp.parentNode.insertBefore(w, inp); w.appendChild(inp);
    inp.style.paddingRight = '40px';
    var b = document.createElement('button');
    b.type = 'button'; b.tabIndex = -1; b.title = 'Prikaži/sakrij lozinku';
    b.style.cssText = 'position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;color:#888;line-height:0;z-index:2;';
    b.innerHTML = EO;
    b.onclick = function(e){ e.preventDefault(); if(inp.type==='password'){inp.type='text';b.innerHTML=EC;}else{inp.type='password';b.innerHTML=EO;} };
    w.appendChild(b);
  }
  function init(){ document.querySelectorAll('input[type="password"]').forEach(addToggle); }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

// ═══ NOTIFICATIONS ══════════════════════════════════════════════════════
window.toggleNotifDropdown = function(){
  var dd = document.getElementById('notif-dropdown');
  if(!dd) return;
  dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
};

document.addEventListener('click', function(e){
  var w = document.getElementById('notif-bell-wrap');
  if(w && !w.contains(e.target)){
    var dd = document.getElementById('notif-dropdown');
    if(dd) dd.style.display = 'none';
  }
});

window.markNotifRead = function(id, url){
  var FC = window.FC || {};
  var base = FC.notifMarkReadUrl || '';
  if(!base) return false;
  fetch(base.replace('99999', id), {
    method: 'POST',
    headers: {'X-Requested-With':'XMLHttpRequest', 'X-CSRFToken': getCsrf()},
  }).finally(function(){ if(url) window.location.href = url; });
  return false;
};

window.markAllNotifsRead = function(){
  var FC = window.FC || {};
  fetch(FC.notifMarkAllUrl || '', {
    method: 'POST',
    headers: {'X-Requested-With':'XMLHttpRequest', 'X-CSRFToken': getCsrf()},
  }).then(function(){ fetchNotifs(); });
};

function fetchNotifs(){
  var FC = window.FC || {};
  if(!FC.notifApiUrl) return;
  fetch(FC.notifApiUrl, {headers:{'X-Requested-With':'XMLHttpRequest'}})
  .then(function(r){ if(!r.ok) return null; return r.json(); })
  .then(function(d){
    if(!d) return;
    var badge = document.getElementById('notif-badge');
    if(badge){
      if(d.unread_count > 0){ badge.textContent = d.unread_count; badge.style.display = 'inline'; }
      else { badge.style.display = 'none'; }
    }
    var markAllBtn = document.getElementById('notif-mark-all');
    if(markAllBtn) markAllBtn.style.display = d.unread_count > 0 ? 'inline' : 'none';
    var list = document.getElementById('notif-list');
    if(list){
      if(!d.recent || d.recent.length === 0){
        list.innerHTML = '<div class="text-center text-muted py-3" style="font-size:.8rem">Nema obavijesti</div>';
      } else {
        var h = '';
        for(var i = 0; i < d.recent.length; i++){
          var n = d.recent[i];
          var bg = n.is_read ? '' : 'background:#f0f7ff;';
          var u = _escH(n.url || '/notifications/');
          h += '<a href="#" onclick="return markNotifRead('+n.id+',&quot;'+u+'&quot;)" style="display:block;padding:8px 12px;border-bottom:1px solid #f1f1f1;text-decoration:none;color:#333;'+bg+'">';
          h += '<div style="font-weight:600;font-size:.8rem">'+_escH(n.title)+'</div>';
          h += '<div style="font-size:.75rem;color:#666">'+_escH((n.message||'').substring(0,80))+'</div></a>';
        }
        list.innerHTML = h;
      }
    }
  }).catch(function(){});
}
window.fetchNotifs = fetchNotifs;

// ═══ COMMAND PALETTE ════════════════════════════════════════════════════
var menuItems = [];
var selectedIdx = -1;

function initMenuItems(){
  document.querySelectorAll('.sidebar a[href]').forEach(function(a){
    var icon = a.querySelector('i');
    var group = a.closest('.sidebar-group');
    var groupName = '';
    if(group){
      var toggle = group.querySelector('.sidebar-group-toggle span');
      if(toggle) groupName = toggle.textContent.trim();
    }
    var label = a.textContent.trim();
    if(!label || label === 'Odjava' || label === '✕') return;
    menuItems.push({
      label: label,
      href: a.getAttribute('href'),
      icon: icon ? icon.className : 'fas fa-circle',
      group: groupName
    });
  });
}

window.openCmdPalette = function(){
  document.getElementById('cmdOverlay').classList.add('open');
  var input = document.getElementById('cmdInput');
  input.value = '';
  setTimeout(function(){ input.focus(); input.click(); }, 150);
  renderCmdResults('');
};
window.closeCmdPalette = function(){
  document.getElementById('cmdOverlay').classList.remove('open');
};

document.addEventListener('keydown', function(e){
  if((e.ctrlKey || e.metaKey) && e.key === 'k'){
    e.preventDefault();
    window.openCmdPalette();
  }
  if(e.key === 'Escape') window.closeCmdPalette();
});

document.addEventListener('keydown', function(e){
  if(!document.getElementById('cmdOverlay').classList.contains('open')) return;
  var items = document.querySelectorAll('.cmd-item');
  if(e.key === 'ArrowDown'){
    e.preventDefault();
    selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
    items.forEach(function(el,i){ el.classList.toggle('selected', i === selectedIdx); });
    if(items[selectedIdx]) items[selectedIdx].scrollIntoView({block:'nearest'});
  } else if(e.key === 'ArrowUp'){
    e.preventDefault();
    selectedIdx = Math.max(selectedIdx - 1, 0);
    items.forEach(function(el,i){ el.classList.toggle('selected', i === selectedIdx); });
    if(items[selectedIdx]) items[selectedIdx].scrollIntoView({block:'nearest'});
  } else if(e.key === 'Enter'){
    if(items[selectedIdx]){
      var href = items[selectedIdx].getAttribute('data-href');
      if(href) window.location.href = href;
    }
  }
});

function renderCmdResults(query){
  var container = document.getElementById('cmdResults');
  var favs = getFavorites();
  var q = query.toLowerCase().trim();

  var filtered = menuItems.filter(function(item){
    if(!q) return true;
    return item.label.toLowerCase().indexOf(q) > -1 ||
           item.group.toLowerCase().indexOf(q) > -1 ||
           item.href.toLowerCase().indexOf(q) > -1;
  });

  filtered.sort(function(a, b){
    var aFav = favs.indexOf(a.href) > -1 ? 0 : 1;
    var bFav = favs.indexOf(b.href) > -1 ? 0 : 1;
    if(aFav !== bFav) return aFav - bFav;
    return a.group.localeCompare(b.group);
  });

  var html = '';
  if(!q && favs.length){
    html += '<div style="padding:4px 14px;font-size:.6rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--gold,#c9a84c);">★ Favoriti</div>';
    filtered.filter(function(i){ return favs.indexOf(i.href) > -1; }).forEach(function(item){
      html += cmdItemHtml(item, true);
    });
    html += '<div style="padding:4px 14px;font-size:.6rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#94a3b8;margin-top:6px;">Sve stranice</div>';
  }

  filtered.forEach(function(item){
    if(!q && favs.indexOf(item.href) > -1) return;
    html += cmdItemHtml(item, favs.indexOf(item.href) > -1);
  });

  container.innerHTML = html;
}

function cmdItemHtml(item, isPinned){
  return '<a class="cmd-item" href="' + item.href + '" data-href="' + item.href + '">' +
    '<i class="' + item.icon + '"></i>' +
    '<span class="cmd-label">' + item.label + '</span>' +
    '<span class="cmd-group">' + item.group + '</span>' +
    '<span class="cmd-fav ' + (isPinned ? 'pinned' : '') + '" onclick="event.preventDefault();event.stopPropagation();toggleFav(\'' + item.href + '\',\'' + escHtml(item.label) + '\',\'' + item.icon + '\')" title="' + (isPinned ? 'Ukloni iz favorita' : 'Dodaj u favorite') + '"><i class="fas fa-star"></i></span>' +
    '</a>';
}

// ═══ FAVORITES ══════════════════════════════════════════════════════════
function getFavorites(){
  try { return JSON.parse(localStorage.getItem('fc_favs') || '[]'); } catch(e){ return []; }
}
function getFavData(){
  try { return JSON.parse(localStorage.getItem('fc_favs_data') || '{}'); } catch(e){ return {}; }
}
window.toggleFav = function(href, label, icon){
  var favs = getFavorites();
  var data = getFavData();
  var idx = favs.indexOf(href);
  if(idx > -1){
    favs.splice(idx, 1);
    delete data[href];
  } else {
    favs.push(href);
    data[href] = {label: label, icon: icon};
  }
  localStorage.setItem('fc_favs', JSON.stringify(favs));
  localStorage.setItem('fc_favs_data', JSON.stringify(data));
  renderFavBar();
  renderCmdResults(document.getElementById('cmdInput').value);
};

function renderFavBar(){
  var bar = document.getElementById('favBar');
  if(!bar) return;
  var favs = getFavorites();
  var data = getFavData();
  if(!favs.length){ bar.innerHTML = ''; return; }
  var html = '';
  favs.forEach(function(href){
    var d = data[href] || {};
    html += '<a class="fav-chip" href="' + href + '">' +
      '<i class="' + (d.icon || 'fas fa-circle') + '"></i> ' +
      (d.label || href) +
      '<span class="fav-remove" onclick="event.preventDefault();event.stopPropagation();toggleFav(\'' + href + '\',\'\',\'\')">✕</span>' +
      '</a>';
  });
  bar.innerHTML = html;
}

// ═══ THEME TOGGLE ═══════════════════════════════════════════════════════
window.toggleTheme = function(){
  var current = document.documentElement.getAttribute('data-theme');
  var next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('fina-theme', next);
  updateThemeIcon(next);
};
function updateThemeIcon(theme){
  var icon = document.getElementById('theme-icon');
  if(!icon) return;
  icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}
// Apply saved theme icon
(function(){
  var saved = localStorage.getItem('fina-theme') || 'dark';
  updateThemeIcon(saved);
})();

// ═══ AI WIDGET ══════════════════════════════════════════════════════════
window.toggleAiWidget = function(){
  var p = document.getElementById('ai-widget-panel');
  if(!p) return;
  if(p.style.display === 'none'){
    p.style.display = 'block';
    loadAiContext();
  } else {
    p.style.display = 'none';
  }
};

function loadAiContext(){
  var mod = '';
  var path = window.location.pathname;
  var map = {'/invoicing/':'invoicing','/inventory/':'inventory','/partners/':'partners',
             '/pos/':'pos','/worktime/':'worktime','/rental/':'rental',
             '/finance/':'finance','/projects/':'projects'};
  for(var k in map){ if(path.startsWith(k)){ mod = map[k]; break; } }
  fetch('/ai/api/context-widget/?module=' + mod)
    .then(function(r){ return r.json(); })
    .then(function(d){
      document.getElementById('ai-widget-title').textContent = d.title || 'Connect';
      document.getElementById('ai-widget-icon').className = 'fas ' + (d.icon||'fa-robot') + ' me-2';
      var tips = '';
      (d.tips||[]).forEach(function(t){
        tips += '<div style="padding:6px 0;color:#ccc;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.05)"><i class="fas fa-lightbulb me-2" style="color:var(--gold,#c9a84c)"></i>' + t + '</div>';
      });
      document.getElementById('ai-widget-tips').innerHTML = tips;
      var acts = '';
      (d.quick_actions||[]).forEach(function(a){
        acts += '<a href="' + a.url + '" class="btn btn-sm btn-outline-warning me-1 mb-1"><i class="fas ' + a.icon + ' me-1"></i>' + a.label + '</a>';
      });
      document.getElementById('ai-widget-actions').innerHTML = acts;
    }).catch(function(){});
}

// ═══ FAB DRAG ═══════════════════════════════════════════════════════════
var dragEl = null, dragOX = 0, dragOY = 0;
window.startDrag = function(e){
  dragEl = document.getElementById('ai-context-fab');
  if(!dragEl) return;
  dragEl.style.cursor = 'grabbing';
  var t = e.touches ? e.touches[0] : e;
  var r = dragEl.getBoundingClientRect();
  dragOX = t.clientX - r.left;
  dragOY = t.clientY - r.top;
  dragEl.style.transform = 'none';
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', endDrag);
  document.addEventListener('touchmove', onDrag, {passive:false});
  document.addEventListener('touchend', endDrag);
  e.preventDefault();
};
function onDrag(e){
  if(!dragEl) return;
  var t = e.touches ? e.touches[0] : e;
  dragEl.style.left = (t.clientX - dragOX) + 'px';
  dragEl.style.top = (t.clientY - dragOY) + 'px';
  e.preventDefault();
}
function endDrag(){
  if(dragEl) dragEl.style.cursor = 'grab';
  dragEl = null;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', endDrag);
  document.removeEventListener('touchmove', onDrag);
  document.removeEventListener('touchend', endDrag);
}

// ═══ IMPERSONATION TIMER ════════════════════════════════════════════════
function initImpersonationTimer(){
  var FC = window.FC || {};
  if(!FC.impersonationStart) return;
  var start = FC.impersonationStart * 1000;
  function tick(){
    var secs = Math.floor((Date.now() - start) / 1000);
    var h = Math.floor(secs/3600), m = Math.floor((secs%3600)/60), s = secs%60;
    var el = document.getElementById('imp-timer');
    if(el) el.textContent = String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  }
  tick();
  setInterval(tick, 1000);
}

// ═══ DOM READY — INIT ALL ═══════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function(){
  initToasts();
  initSidebarGroups();
  restoreSlimSidebar();
  wrapSidebarLinkText();
  initMenuItems();
  renderFavBar();
  initImpersonationTimer();

  // Notification polling
  if(document.getElementById('notif-bell-wrap')){
    fetchNotifs();
    setInterval(fetchNotifs, 60000);
  }

  // Cmd palette input
  var cmdInput = document.getElementById('cmdInput');
  if(cmdInput){
    cmdInput.addEventListener('input', function(){
      selectedIdx = -1;
      renderCmdResults(this.value);
    });
  }
});

})();

// === PULL-TO-REFRESH (mobile only) ===
(function(){
  if(window.innerWidth > 768) return;
  var ptr = document.createElement("div");
  ptr.className = "ptr-indicator";
  ptr.innerHTML = '<i class="fas fa-arrow-down"></i>';
  document.body.appendChild(ptr);
  var startY = 0, pulling = false;
  document.addEventListener("touchstart", function(e){
    if(window.scrollY === 0) { startY = e.touches[0].clientY; pulling = true; }
  }, {passive:true});
  document.addEventListener("touchmove", function(e){
    if(!pulling) return;
    var dy = e.touches[0].clientY - startY;
    if(dy > 60 && window.scrollY === 0){
      ptr.classList.add("visible");
      ptr.innerHTML = '<i class="fas fa-sync-alt"></i>';
    }
  }, {passive:true});
  document.addEventListener("touchend", function(){
    if(ptr.classList.contains("visible")){
      ptr.classList.add("loading");
      setTimeout(function(){ location.reload(); }, 300);
    }
    pulling = false;
    if(!ptr.classList.contains("loading")) ptr.classList.remove("visible");
  });
})();

