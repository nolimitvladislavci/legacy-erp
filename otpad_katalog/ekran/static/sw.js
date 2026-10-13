/* Servisni worker: aplikacija se otvara i bez mreže (dvorište bez signala). Samo ljuska (HTML/JS/CSS), nikad /api/.
   Mreža ima prednost (nove verzije stižu odmah), a bez mreže se služi zadnja spremljena ljuska. */
var VERZIJA = 'otpad-ljuska-v1';
// Putanje relativno prema sw.js: radi i na korijenu i pod prefiksom (/otpad/ iza nginxa).
var BAZA = new URL('./', self.location).pathname;
var LJUSKA = ['./', 'app.css', 'app.js', 'tamno.js', 'favicon.svg'].map(function (x) { return new URL(x, self.location).href; });

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERZIJA).then(function (c) { return c.addAll(LJUSKA); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (imena) {
    return Promise.all(imena.filter(function (i) { return i !== VERZIJA; }).map(function (i) { return caches.delete(i); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== self.location.origin || u.pathname.indexOf(BAZA + 'api/') === 0) return;   // API nikad iz cachea
  e.respondWith(fetch(r).then(function (odg) {
    if (odg && odg.ok) { var kopija = odg.clone(); caches.open(VERZIJA).then(function (c) { c.put(r, kopija); }); }
    return odg;
  }).catch(function () {
    return caches.match(r).then(function (c) { return c || caches.match(LJUSKA[0]); });
  }));
});
