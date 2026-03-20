/**
 * fenix-permissions.js — PWA permissions request pri instalaciji.
 * Traži: persistent storage, notifications, camera — u jednom koraku.
 * Dodaje se u base.html, pokreće se jednom (localStorage flag).
 */
(function(){
  'use strict';

  var KEY = 'fenix_permissions_granted';
  if (localStorage.getItem(KEY)) return;

  // Čekaj da se stranica učita
  window.addEventListener('load', function() {
    setTimeout(requestPermissions, 3000); // 3s delay da ne ometa UX
  });

  function requestPermissions() {
    var granted = [];

    // 1. Persistent Storage (IndexedDB ne briše browser)
    if (navigator.storage && navigator.storage.persist) {
      navigator.storage.persist().then(function(ok) {
        if (ok) granted.push('storage');
      });
    }

    // 2. Notifications
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then(function(p) {
        if (p === 'granted') granted.push('notifications');
      });
    } else if (Notification.permission === 'granted') {
      granted.push('notifications');
    }

    // 3. Camera permission se traži tek kad korisnik klikne FenixCamera
    // Ne tražimo unaprijed — samo bilježimo da smo pokrenuli flow

    // Mark as done
    setTimeout(function() {
      localStorage.setItem(KEY, JSON.stringify({
        granted: granted,
        timestamp: new Date().toISOString(),
      }));
    }, 2000);
  }
})();
