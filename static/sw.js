// LIMIT Connect Service Worker – v4 (PWA + Offline)
'use strict';

var CACHE_VERSION = 'fina-v8';
var STATIC_CACHE  = CACHE_VERSION + '-static';
var PAGE_CACHE    = CACHE_VERSION + '-pages';

// Assets to precache on install
var PRECACHE_URLS = [
  '/offline.html',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/js/pos/pos-offline.js',
  '/static/js/pos/pos-quick.js',
  '/static/js/pos/pos-fiscal.js',
  '/static/js/pos/pos-scanner.js',
];

// ── Install: precache static assets ─────────────────────────────────────────
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function(cache) {
      return cache.addAll(PRECACHE_URLS);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

// ── Activate: clean old caches ───────────────────────────────────────────────
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) {
          return k !== STATIC_CACHE && k !== PAGE_CACHE;
        }).map(function(k) { return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// ── Fetch strategy ───────────────────────────────────────────────────────────
self.addEventListener('fetch', function(event) {
  var req = event.request;
  var url = new URL(req.url);

  // Skip non-GET, cross-origin, push/subscribe endpoints
  if (req.method !== 'GET') return;
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/push/')) return;
  if (url.pathname.startsWith('/admin/')) return;

  // Static assets → cache first
  if (url.pathname.startsWith('/static/') ||
      url.pathname === '/sw.js' ||
      url.pathname === '/manifest.json') {
    event.respondWith(
      caches.match(req).then(function(cached) {
        return cached || fetch(req).then(function(resp) {
          if (resp.ok) {
            var clone = resp.clone();
            caches.open(STATIC_CACHE).then(function(c) { c.put(req, clone); });
          }
          return resp;
        });
      })
    );
    return;
  }

  // Field/Tracking pages → network first, cache fallback, offline fallback
  if (url.pathname.includes('/field/') ||
      url.pathname.includes('/track/') ||
      url.pathname.includes('/pos/') ||
      url.pathname.includes('/helpdesk/') ||
      url.pathname.includes('/worktime/') ||
      url.pathname.includes('/fitness/') ||
      url.pathname.includes('/udruge/') ||
      url.pathname.includes('/hr/') ||
      url.pathname === '/') {
    event.respondWith(
      fetch(req).then(function(resp) {
        if (resp.ok) {
          var clone = resp.clone();
          caches.open(PAGE_CACHE).then(function(c) { c.put(req, clone); });
        }
        return resp;
      }).catch(function() {
        return caches.match(req).then(function(cached) {
          return cached || caches.match('/offline.html');
        });
      })
    );
    return;
  }

  // Default: network with offline fallback for navigation
  event.respondWith(
    fetch(req).catch(function() {
      if (req.mode === 'navigate') {
        return caches.match('/offline.html');
      }
    })
  );
});

// ── Background Sync: flush offline queue ────────────────────────────────────
self.addEventListener('sync', function(event) {
  if (event.tag === 'fina-offline-sync') {
    event.waitUntil(flushOfflineQueue());
  }
});

function flushOfflineQueue() {
  return self.clients.matchAll().then(function(clients) {
    clients.forEach(function(client) {
      client.postMessage({ type: 'FLUSH_QUEUE' });
    });
  });
}

// ── Push notifications ───────────────────────────────────────────────────────
self.addEventListener('push', function(event) {
  var data = {};
  try { data = event.data.json(); } catch(e) {}
  var title = data.title || 'LIMIT Connect';
  var options = {
    body:    data.body || '',
    icon:    data.icon || '/static/icons/icon-192.png',
    image:   data.image || undefined,
    badge:   '/static/icons/icon-192.png',
    tag:     data.tag || undefined,
    renotify: !!data.tag,
    data:    { url: data.url || '/' },
    actions: [
      { action: 'open',    title: 'Otvori' },
      { action: 'dismiss', title: 'Zatvori' }
    ],
    vibrate: [200, 100, 200]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.action === 'dismiss') return;
  var targetUrl = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clients) {
      for (var i = 0; i < clients.length; i++) {
        if (clients[i].url === targetUrl && 'focus' in clients[i]) {
          return clients[i].focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    })
  );
});

// ══════════════════════════════════════════════════════════════════════════════
// POS OFFLINE QUEUE — IndexedDB za bonove bez interneta
// ══════════════════════════════════════════════════════════════════════════════

var POS_DB_NAME = 'limit-pos-offline';
var POS_DB_VERSION = 1;
var POS_STORE = 'pending_receipts';

function openPosDB() {
  return new Promise(function(resolve, reject) {
    var req = indexedDB.open(POS_DB_NAME, POS_DB_VERSION);
    req.onupgradeneeded = function(e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains(POS_STORE)) {
        db.createObjectStore(POS_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = function(e) { resolve(e.target.result); };
    req.onerror = function(e) { reject(e.target.error); };
  });
}

function savePendingReceipt(data) {
  return openPosDB().then(function(db) {
    return new Promise(function(resolve, reject) {
      var tx = db.transaction(POS_STORE, 'readwrite');
      var store = tx.objectStore(POS_STORE);
      data.created_at = new Date().toISOString();
      data.synced = false;
      var req = store.add(data);
      req.onsuccess = function() { resolve(req.result); };
      req.onerror = function() { reject(req.error); };
    });
  });
}

function getPendingReceipts() {
  return openPosDB().then(function(db) {
    return new Promise(function(resolve, reject) {
      var tx = db.transaction(POS_STORE, 'readonly');
      var store = tx.objectStore(POS_STORE);
      var req = store.getAll();
      req.onsuccess = function() { resolve(req.result); };
      req.onerror = function() { reject(req.error); };
    });
  });
}

function deletePendingReceipt(id) {
  return openPosDB().then(function(db) {
    return new Promise(function(resolve, reject) {
      var tx = db.transaction(POS_STORE, 'readwrite');
      tx.objectStore(POS_STORE).delete(id);
      tx.oncomplete = function() { resolve(); };
      tx.onerror = function() { reject(tx.error); };
    });
  });
}

// ── Sync pending receipts when online ─────────────────────────────────────────
function syncPendingReceipts() {
  return getPendingReceipts().then(function(receipts) {
    if (!receipts || receipts.length === 0) return Promise.resolve(0);
    
    var synced = 0;
    var chain = Promise.resolve();
    
    receipts.forEach(function(receipt) {
      chain = chain.then(function() {
        return fetch('/hr/pos/api/quick-pay/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': receipt.csrf_token || '',
          },
          body: JSON.stringify(receipt.data),
          credentials: 'same-origin',
        }).then(function(response) {
          if (response.ok) {
            synced++;
            return deletePendingReceipt(receipt.id);
          }
        }).catch(function() {
          // Skip failed — will retry next sync
        });
      });
    });
    
    return chain.then(function() { return synced; });
  });
}

// ── Background sync registration ──────────────────────────────────────────────
self.addEventListener('sync', function(event) {
  if (event.tag === 'pos-sync-receipts') {
    event.waitUntil(
      syncPendingReceipts().then(function(count) {
        if (count > 0) {
          return self.registration.showNotification('POS Sync', {
            body: count + ' bon(ova) uspjesno sinkronizirano!',
            icon: '/static/icons/icon-192.png',
            badge: '/static/icons/icon-192.png',
          });
        }
      })
    );
  }
});

// ── Periodic sync (every 5 min when online) ──────────────────────────────────
self.addEventListener('periodicsync', function(event) {
  if (event.tag === 'pos-periodic-sync') {
    event.waitUntil(syncPendingReceipts());
  }
});

// ── Message handler for POS page ──────────────────────────────────────────────
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'POS_SAVE_OFFLINE') {
    savePendingReceipt(event.data.receipt).then(function(id) {
      event.ports[0].postMessage({ saved: true, id: id });
    }).catch(function(err) {
      event.ports[0].postMessage({ saved: false, error: err.message });
    });
  }
  if (event.data && event.data.type === 'POS_SYNC_NOW') {
    syncPendingReceipts().then(function(count) {
      event.ports[0].postMessage({ synced: count });
    });
  }
  if (event.data && event.data.type === 'POS_GET_PENDING') {
    getPendingReceipts().then(function(receipts) {
      event.ports[0].postMessage({ pending: receipts });
    });
  }
});

// ── Enhanced fetch: cache POS pages and API responses ─────────────────────────
var POS_CACHE = CACHE_VERSION + '-pos';
var POS_URLS = ['/hr/pos/', '/hr/pos/quick/', '/hr/pos/restaurant/'];

self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);
  
  // Cache POS pages with network-first strategy
  if (POS_URLS.some(function(p) { return url.pathname.startsWith(p); }) && event.request.method === 'GET') {
    event.respondWith(
      fetch(event.request).then(function(response) {
        if (response.ok) {
          var clone = response.clone();
          caches.open(POS_CACHE).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(function() {
        return caches.match(event.request).then(function(cached) {
          return cached || caches.match('/offline.html');
        });
      })
    );
    return;
  }
  
  // For POS API POST when offline — save to IndexedDB
  if (url.pathname.includes('/pos/api/quick-pay') && event.request.method === 'POST' && !navigator.onLine) {
    event.respondWith(
      event.request.json().then(function(data) {
        return savePendingReceipt({ data: data }).then(function(id) {
          return new Response(JSON.stringify({
            offline: true,
            pending_id: id,
            message: 'Bon spremljen lokalno. Sinkronizira se kad se vrati internet.'
          }), {
            status: 202,
            headers: { 'Content-Type': 'application/json' }
          });
        });
      }).catch(function() {
        return new Response(JSON.stringify({ error: 'Offline save failed' }), { status: 500 });
      })
    );
    return;
  }
});

// ═══ TRIGGER_SYNC — šalji signal klijentima da pokrenu sync ═══════════
self.addEventListener('sync', function(event) {
  if (event.tag === 'pos-offline-sync') {
    event.waitUntil(
      self.clients.matchAll().then(function(clients) {
        clients.forEach(function(client) {
          client.postMessage({type: 'TRIGGER_SYNC'});
        });
      })
    );
  }
});
