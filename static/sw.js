// LIMIT Connect Service Worker – v4 (PWA + Offline)
'use strict';

var CACHE_VERSION = 'fina-v6';
var STATIC_CACHE  = CACHE_VERSION + '-static';
var PAGE_CACHE    = CACHE_VERSION + '-pages';

// Assets to precache on install
var PRECACHE_URLS = [
  '/offline.html',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
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
