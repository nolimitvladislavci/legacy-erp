# CC Task — Offline Engine: kompletna PWA podrška

## Misija
App mora raditi bez interneta. Minimalni zahtjev:
- Korisnik se može prijaviti (cached)
- Može upisati radno vrijeme (worktime clock-in/out)
- POS već radi offline — ne diraj
- Dozvole se traže pri prvom pokretanju (storage, notification, kamera)

## KORAK 0 — Pročitaj sve PRIJE pisanja koda
```bash
cat /var/www/fina-connect/static/sw.js
cat /var/www/fina-connect/static/js/core.js | grep -A30 "OFFLINE QUEUE"
cat /var/www/fina-connect/static/manifest.json
grep -n "offline\|navigator.onLine\|serviceWorker" /var/www/fina-connect/templates/base.html | head -20
grep -n "clock_in\|clock_out\|time_entry\|TimeEntry" /var/www/fina-connect/worktime/views.py | head -20
grep -n "clock_in\|clock_out" /var/www/fina-connect/worktime/urls.py | head -10
```

## KORAK 1 — fenix-permissions.js

Napiši `/var/www/fina-connect/static/js/fenix-permissions.js`

```javascript
/**
 * FenixPermissions — traženje dozvola pri prvom pokretanju.
 * Poziva se jednom: FenixPermissions.requestAll()
 * Prikazuje non-blocking UI panel s objašnjenjem.
 */
window.FenixPermissions = (function() {

  // 1. Storage persist — najvažnije, bez toga browser može obrisati IDB
  function requestStoragePersist() {
    if (!navigator.storage || !navigator.storage.persist) return Promise.resolve(false);
    return navigator.storage.persist().then(function(granted) {
      console.log('[Fenix] Storage persist:', granted ? 'granted' : 'denied');
      localStorage.setItem('fenix_storage_persist', granted ? '1' : '0');
      return granted;
    });
  }

  // 2. Notification dozvola — za offline sync obavijesti
  function requestNotification() {
    if (!('Notification' in window)) return Promise.resolve('unsupported');
    if (Notification.permission !== 'default') return Promise.resolve(Notification.permission);
    return Notification.requestPermission();
  }

  // 3. Kamera — pokušaj tiho (bez prompta ako nije potrebno)
  function checkCamera() {
    if (!navigator.mediaDevices) return Promise.resolve(false);
    return navigator.mediaDevices.enumerateDevices().then(function(devices) {
      return devices.some(function(d) { return d.kind === 'videoinput'; });
    }).catch(function() { return false; });
  }

  // 4. Prikaži onboarding panel (jednom, kad nije viđen)
  function showOnboardingIfNeeded() {
    if (localStorage.getItem('fenix_permissions_shown')) return;
    localStorage.setItem('fenix_permissions_shown', '1');

    var panel = document.createElement('div');
    panel.id = 'fenixPermPanel';
    panel.style.cssText = [
      'position:fixed;bottom:16px;left:50%;transform:translateX(-50%)',
      'background:var(--color-background-primary)',
      'border:1px solid var(--color-border-secondary)',
      'border-radius:12px;padding:16px 20px;max-width:340px;width:90%',
      'box-shadow:0 4px 20px rgba(0,0,0,.15);z-index:9999',
      'font-size:13px;color:var(--color-text-primary)'
    ].join(';');

    panel.innerHTML = [
      '<div style="font-weight:500;margin-bottom:6px">Dozvoli offline rad</div>',
      '<div style="color:var(--color-text-secondary);font-size:12px;margin-bottom:12px">',
      'LIMIT Connect treba pristup pohrani podataka za rad bez interneta.',
      '</div>',
      '<div style="display:flex;gap:8px">',
      '<button id="fenixPermAllow" style="flex:1;padding:8px;border:none;border-radius:8px;',
      'background:#1D9E75;color:#fff;font-size:13px;cursor:pointer">Dozvoli</button>',
      '<button id="fenixPermSkip" style="flex:1;padding:8px;border:1px solid var(--color-border-secondary);',
      'border-radius:8px;background:transparent;color:var(--color-text-secondary);font-size:13px;cursor:pointer">Preskoči</button>',
      '</div>'
    ].join('');

    document.body.appendChild(panel);

    document.getElementById('fenixPermAllow').onclick = function() {
      requestStoragePersist();
      requestNotification();
      panel.remove();
    };
    document.getElementById('fenixPermSkip').onclick = function() {
      panel.remove();
    };

    // Auto-dismiss nakon 10s
    setTimeout(function() { if (panel.parentNode) panel.remove(); }, 10000);
  }

  function requestAll() {
    requestStoragePersist();
    checkCamera();
    showOnboardingIfNeeded();
  }

  return { requestAll: requestAll, requestStoragePersist: requestStoragePersist };
})();
```

Dodaj poziv na kraj base.html (unutar DOMContentLoaded ili odmah):
```html
<script src="{% static 'js/fenix-permissions.js' %}"></script>
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() { FenixPermissions.requestAll(); });
  }
</script>
```

## KORAK 2 — worktime-offline.js

Napiši `/var/www/fina-connect/static/js/worktime-offline.js`

Pročitaj stvarne URL-ove za clock-in/clock-out iz worktime/urls.py PRIJE pisanja!

```javascript
/**
 * Worktime Offline Engine
 * Omogućuje clock-in/clock-out bez interneta.
 * Sync automatski kad se veza vrati.
 */
(function() {
  'use strict';

  var DB_NAME = 'worktime_offline_v1';
  var db = null;

  function openDB(cb) {
    if (db) { cb(db); return; }
    var req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = function(e) {
      var d = e.target.result;
      if (!d.objectStoreNames.contains('entries')) {
        var s = d.createObjectStore('entries', { keyPath: 'offline_id' });
        s.createIndex('synced', 'synced', { unique: false });
        s.createIndex('date', 'date', { unique: false });
      }
    };
    req.onsuccess = function(e) { db = e.target.result; cb(db); };
    req.onerror = function() { console.error('WorktimeOffline: IDB error'); };
  }

  // Spremi clock-in offline
  window.worktimeOfflineClockIn = function(data) {
    // data: { project_id, task, note, user_id, company_id }
    var entry = {
      offline_id: 'WT-' + Date.now(),
      type: 'clock_in',
      project_id: data.project_id || '',
      task: data.task || '',
      note: data.note || '',
      user_id: data.user_id || '',
      company_id: data.company_id || '',
      started_at: new Date().toISOString(),
      date: new Date().toISOString().slice(0, 10),
      synced: 0,
    };
    openDB(function(db) {
      db.transaction('entries', 'readwrite').objectStore('entries').put(entry);
      localStorage.setItem('wt_active_offline_entry', entry.offline_id);
      updateWorktimeBadge();
    });
    return entry;
  };

  // Spremi clock-out offline
  window.worktimeOfflineClockOut = function(note) {
    var activeId = localStorage.getItem('wt_active_offline_entry');
    if (!activeId) return null;
    openDB(function(db) {
      var tx = db.transaction('entries', 'readwrite');
      var store = tx.objectStore('entries');
      var req = store.get(activeId);
      req.onsuccess = function(e) {
        var entry = e.target.result;
        if (!entry) return;
        entry.type = 'time_entry';
        entry.ended_at = new Date().toISOString();
        entry.duration_minutes = Math.round(
          (new Date(entry.ended_at) - new Date(entry.started_at)) / 60000
        );
        entry.note = note || entry.note;
        store.put(entry);
        localStorage.removeItem('wt_active_offline_entry');
        updateWorktimeBadge();
      };
    });
  };

  // Sync sve nesihr. entrie
  window.worktimeOfflineSync = function() {
    if (!navigator.onLine) return;
    openDB(function(db) {
      var tx = db.transaction('entries', 'readonly');
      var unsynced = [];
      tx.objectStore('entries').index('synced').openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        var c = e.target.result;
        if (c) { unsynced.push(c.value); c.continue(); }
      };
      tx.oncomplete = function() {
        if (!unsynced.length) return;
        unsynced.forEach(function(entry) {
          if (entry.type !== 'time_entry') return; // samo završeni

          // Pročitaj pravi URL iz worktime/urls.py i koristi ga ovdje
          // Npr: /hr/worktime/time-entry/create/ ili /worktime/api/entry/
          var url = window.WORKTIME_ENTRY_URL || '/hr/worktime/ts/add/';
          var csrfToken = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';

          fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken,
              'X-Offline-Sync': '1',
            },
            body: JSON.stringify({
              project_id: entry.project_id,
              task: entry.task,
              note: (entry.note || '') + ' [OFFLINE ' + entry.offline_id + ']',
              started_at: entry.started_at,
              ended_at: entry.ended_at,
              duration_minutes: entry.duration_minutes,
              offline_id: entry.offline_id,
            })
          })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.ok || data.id) {
              var utx = db.transaction('entries', 'readwrite');
              entry.synced = 1;
              entry.server_id = data.id;
              utx.objectStore('entries').put(entry);
              updateWorktimeBadge();
            }
          })
          .catch(function(e) { console.warn('WT sync error:', e); });
        });
      };
    });
  };

  function updateWorktimeBadge() {
    openDB(function(db) {
      var count = 0;
      var tx = db.transaction('entries', 'readonly');
      tx.objectStore('entries').index('synced').openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        var c = e.target.result;
        if (c) { count++; c.continue(); }
      };
      tx.oncomplete = function() {
        var badge = document.getElementById('worktimeOfflineBadge');
        if (badge) {
          badge.textContent = count ? count + ' offline' : '';
          badge.style.display = count ? 'inline' : 'none';
        }
      };
    });
  }

  // Auto sync na reconnect
  window.addEventListener('online', function() {
    setTimeout(window.worktimeOfflineSync, 2000);
  });

  openDB(function() { updateWorktimeBadge(); });
  if (navigator.onLine) window.worktimeOfflineSync();

})();
```

## KORAK 3 — Proširi SW rute

U `/var/www/fina-connect/static/sw.js` dodaj u PAGE_CACHE rute:
```javascript
// Staro:
if (url.pathname.includes('/pos/') || url.pathname.includes('/field/') ...)

// Novo — dodaj:
url.pathname.includes('/worktime/') ||
url.pathname.includes('/fitness/') ||
url.pathname.includes('/udruge/') ||
url.pathname === '/hr/' ||
url.pathname.startsWith('/hr/worktime/') ||
```

Povećaj CACHE_VERSION na `fina-v6`.

## KORAK 4 — Offline login podrška

U sw.js, dodaj cachiranje login stranice i statičnog HTML-a:
```javascript
var PRECACHE_URLS = [
  '/offline.html',
  '/accounts/login/',   // cachej login formu
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/js/fenix-permissions.js',
  '/static/js/worktime-offline.js',
];
```

Za JWT/session cache: kad korisnik se uspješno prijavi, spremi u IDB:
```javascript
// U core.js ili base.html — nakon uspješnog logina:
if (window.cacheSessionForOffline) {
  window.cacheSessionForOffline({
    user_id: '{{ request.user.pk }}',
    username: '{{ request.user.username }}',
    company_id: '{{ company_id }}',
    cached_at: Date.now(),
  });
}
```

## KORAK 5 — Offline status panel u base.html

Provjeri postoji li offline bar u base.html:
```bash
grep -n "offlineBar\|offlineMsg\|offlineQueue" /var/www/fina-connect/templates/base.html | head -10
```

Ako postoji — proširi ga da prikazuje i worktime offline count:
```html
<!-- Dodaj u offline bar div: -->
<span id="worktimeOfflineBadge" style="display:none;background:#EF9F27;color:#fff;
  padding:2px 8px;border-radius:99px;font-size:11px;margin-left:8px"></span>
```

## KORAK 6 — Worktime view: prihvati offline sync request

Pročitaj `/var/www/fina-connect/worktime/views.py` pa provjeri koji view prima POST za time entry.
Dodaj header check u relevantni view:
```python
# Ako dolazi iz offline sync, označi ga
is_offline_sync = request.headers.get('X-Offline-Sync') == '1'
if is_offline_sync:
    # Provjeri duplicate po offline_id
    offline_id = data.get('offline_id', '')
    if offline_id and TimeEntry.objects.filter(notes__contains=offline_id).exists():
        return JsonResponse({'ok': True, 'duplicate': True})
```

## KORAK 7 — collectstatic i restart
```bash
cd /var/www/fina-connect
venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -5
systemctl reload nginx
```

## KORAK 8 — Test i provjera
```bash
# Fajlovi postoje?
ls -la /var/www/fina-connect/static/js/fenix-permissions.js
ls -la /var/www/fina-connect/static/js/worktime-offline.js

# Django check
venv/bin/python manage.py check 2>&1 | tail -3

# SW cache version promijenjen?
grep "CACHE_VERSION" /var/www/fina-connect/static/sw.js
```

## Definicija DONE
- [ ] fenix-permissions.js postoji, dodan u base.html
- [ ] worktime-offline.js postoji, IDB store se otvara bez greške
- [ ] SW PAGE_CACHE uključuje worktime/fitness/udruge rute
- [ ] CACHE_VERSION povećan na fina-v6
- [ ] collectstatic prošao
- [ ] Django check: 0 grešaka
- [ ] Napiši /tmp/offline_done.txt s "DONE"

## Napomena
NE diraj pos-offline.js — POS offline već radi.
NE diraj push notification logiku u core.js.
Worktime URL za sync — pročitaj worktime/urls.py, ne pretpostavljaj.
