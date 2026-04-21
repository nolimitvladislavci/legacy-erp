/**
 * Fenix Heartbeat v1.0
 * Svakih 5 minuta šalje signal serveru da je korisnik aktivan.
 * Sentinel Live Monitor koristi ove podatke za detekciju stalih sesija.
 * WCAG: potpuno tiho, ne ometa UI, radi u pozadini.
 */
(function () {
  'use strict';

  var INTERVAL   = 5 * 60 * 1000;  // 5 minuta
  var ENDPOINT   = '/api/heartbeat/';
  var CLOSE_URL  = '/api/heartbeat/close/';
  var _timer     = null;
  var _csrfToken = null;

  function getCsrf() {
    if (_csrfToken) return _csrfToken;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    _csrfToken = m ? m[1] : '';
    return _csrfToken;
  }

  function send() {
    fetch(ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': getCsrf(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        page: window.location.pathname,
        ts:   Date.now(),
      }),
    }).catch(function () {
      // Silent fail — ne blokira UI
    });
  }

  function stop() {
    if (_timer) {
      clearInterval(_timer);
      _timer = null;
    }
    // Pokušaj poslati beacon (ne čeka response)
    if (navigator.sendBeacon) {
      var data = new FormData();
      data.append('csrfmiddlewaretoken', getCsrf());
      navigator.sendBeacon(CLOSE_URL, data);
    }
  }

  function start() {
    send();  // Odmah pošalji
    _timer = setInterval(send, INTERVAL);
    window.addEventListener('beforeunload', stop);
  }

  // Auto-start samo za prijavljene korisnike
  // base.html postavlja data-authenticated="true" na <body>
  function init() {
    var body = document.body;
    if (body && body.dataset.authenticated === 'true') {
      start();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Javni API (za debug / testove)
  window.FenixHeartbeat = { start: start, stop: stop, send: send };
})();
