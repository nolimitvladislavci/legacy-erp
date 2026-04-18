/**
 * worktime-offline.js — Offline clock-in/out + TimeEntry cache.
 * IndexedDB za radne sate kad nema interneta.
 *
 * Usage:
 *   WorktimeOffline.clockIn()     — spremi clock-in lokalno
 *   WorktimeOffline.clockOut()    — spremi clock-out, izracunaj trajanje
 *   WorktimeOffline.sync()        — posalji sve na server
 *   WorktimeOffline.getStatus()   — trenutni status (clocked in/out)
 */
(function(){
  'use strict';

  var DB_NAME = 'worktime_offline';
  var DB_VERSION = 1;
  var db = null;

  function openDB(cb) {
    if (db) { cb(db); return; }
    var req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = function(e) {
      var d = e.target.result;
      if (!d.objectStoreNames.contains('entries')) {
        var store = d.createObjectStore('entries', { keyPath: 'id', autoIncrement: true });
        store.createIndex('synced', 'synced', { unique: false });
        store.createIndex('type', 'type', { unique: false });
      }
      if (!d.objectStoreNames.contains('status')) {
        d.createObjectStore('status', { keyPath: 'key' });
      }
    };
    req.onsuccess = function(e) { db = e.target.result; cb(db); };
    req.onerror = function() { console.error('WorktimeOffline DB error'); };
  }

  // ── Clock In ──────────────────────────────────────────────────
  function clockIn(data) {
    data = data || {};
    var entry = {
      type: 'clock_in',
      timestamp: new Date().toISOString(),
      lat: data.lat || null,
      lon: data.lon || null,
      note: data.note || '',
      synced: 0,
    };

    openDB(function(db) {
      var tx = db.transaction(['entries', 'status'], 'readwrite');
      tx.objectStore('entries').add(entry);
      tx.objectStore('status').put({ key: 'current', clocked_in: true, clock_in_time: entry.timestamp });
      tx.oncomplete = function() {
        if (window.showPosToast) showPosToast('Clock-in spremljen offline', 'info');
      };
    });

    // Try GPS
    if (navigator.geolocation && !data.lat) {
      navigator.geolocation.getCurrentPosition(function(pos) {
        entry.lat = pos.coords.latitude;
        entry.lon = pos.coords.longitude;
      }, function() {}, { timeout: 5000 });
    }

    return entry;
  }

  // ── Clock Out ─────────────────────────────────────────────────
  function clockOut(data) {
    data = data || {};
    var now = new Date();

    openDB(function(db) {
      var tx = db.transaction(['entries', 'status'], 'readwrite');

      // Get clock-in time for duration calc
      var statusStore = tx.objectStore('status');
      var getReq = statusStore.get('current');

      getReq.onsuccess = function() {
        var current = getReq.result || {};
        var clockInTime = current.clock_in_time ? new Date(current.clock_in_time) : null;
        var duration = clockInTime ? Math.round((now - clockInTime) / 1000 / 60) / 60 : 0; // hours

        var entry = {
          type: 'clock_out',
          timestamp: now.toISOString(),
          clock_in_time: current.clock_in_time || '',
          duration_hours: Math.round(duration * 100) / 100,
          lat: data.lat || null,
          lon: data.lon || null,
          note: data.note || '',
          synced: 0,
        };

        tx.objectStore('entries').add(entry);
        statusStore.put({ key: 'current', clocked_in: false, clock_in_time: null });

        if (window.showPosToast) {
          showPosToast('Clock-out: ' + entry.duration_hours.toFixed(1) + 'h spremljeno offline', 'info');
        }
      };
    });
  }

  // ── Get Status ────────────────────────────────────────────────
  function getStatus(cb) {
    openDB(function(db) {
      var tx = db.transaction('status', 'readonly');
      var req = tx.objectStore('status').get('current');
      req.onsuccess = function() {
        var s = req.result || { clocked_in: false };
        if (s.clocked_in && s.clock_in_time) {
          var mins = Math.round((new Date() - new Date(s.clock_in_time)) / 1000 / 60);
          s.elapsed_minutes = mins;
          s.elapsed_display = Math.floor(mins / 60) + 'h ' + (mins % 60) + 'min';
        }
        cb(s);
      };
    });
  }

  // ── Sync ──────────────────────────────────────────────────────
  function sync() {
    if (!navigator.onLine) {
      if (window.showPosToast) showPosToast('Nema veze — sync later', 'warning');
      return;
    }

    openDB(function(db) {
      var tx = db.transaction('entries', 'readonly');
      var unsynced = [];

      tx.objectStore('entries').index('synced').openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        var cursor = e.target.result;
        if (cursor) { unsynced.push(cursor.value); cursor.continue(); }
      };

      tx.oncomplete = function() {
        if (!unsynced.length) {
          if (window.showPosToast) showPosToast('Worktime: sve sinkronizirano', 'success');
          return;
        }

        var csrf = document.cookie.match('csrftoken=([^;]+)');
        csrf = csrf ? csrf[1] : '';

        fetch('/worktime/api/offline-sync/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({ entries: unsynced }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.ok) {
            // Mark all as synced
            var tx2 = db.transaction('entries', 'readwrite');
            unsynced.forEach(function(entry) {
              entry.synced = 1;
              tx2.objectStore('entries').put(entry);
            });
            if (window.showPosToast) showPosToast('Worktime: ' + unsynced.length + ' unosa sinkronizirano', 'success');
          }
        })
        .catch(function(err) {
          console.error('Worktime sync error:', err);
        });
      };
    });
  }

  // ── Get Pending Count ─────────────────────────────────────────
  function getPendingCount(cb) {
    openDB(function(db) {
      var tx = db.transaction('entries', 'readonly');
      var count = 0;
      tx.objectStore('entries').index('synced').openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        if (e.target.result) { count++; e.target.result.continue(); }
      };
      tx.oncomplete = function() { cb(count); };
    });
  }

  // ── Auto sync on reconnect ────────────────────────────────────
  window.addEventListener('online', function() {
    setTimeout(sync, 3000);
  });

  // ── Public API ────────────────────────────────────────────────
  window.WorktimeOffline = {
    clockIn: clockIn,
    clockOut: clockOut,
    getStatus: getStatus,
    sync: sync,
    getPendingCount: getPendingCount,
    version: '1.0.0',
  };

})();
