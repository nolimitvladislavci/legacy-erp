/**
 * GolubarOffline — Offline podrska za Golubar modul.
 * IndexedDB queue + sync za golub_create i golubinjak_create forme.
 *
 * Koristi: limit-golubar-offline DB, dva store-a.
 * Integrira se sa FenixCamera za fotografije.
 */
(function() {
  'use strict';

  var DB_NAME = 'limit-golubar-offline';
  var DB_VERSION = 1;
  var STORE_GOLUBOVI = 'pending_golubovi';
  var STORE_GOLUBINJACI = 'pending_golubinjaci';

  // ── IndexedDB open ──────────────────────────────────────────────
  function openDB() {
    return new Promise(function(resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function(e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_GOLUBOVI)) {
          db.createObjectStore(STORE_GOLUBOVI, { keyPath: 'id', autoIncrement: true });
        }
        if (!db.objectStoreNames.contains(STORE_GOLUBINJACI)) {
          db.createObjectStore(STORE_GOLUBINJACI, { keyPath: 'id', autoIncrement: true });
        }
      };
      req.onsuccess = function(e) { resolve(e.target.result); };
      req.onerror = function(e) { reject(e.target.error); };
    });
  }

  // ── CSRF token iz cookie ────────────────────────────────────────
  function getCSRF() {
    var match = document.cookie.match('csrftoken=([^;]+)');
    return match ? match[1] : '';
  }

  // ── File input → base64 ─────────────────────────────────────────
  function fileToBase64(file) {
    return new Promise(function(resolve, reject) {
      if (!file || file.size === 0) { resolve(null); return; }
      var reader = new FileReader();
      reader.onload = function() {
        resolve({
          b64: reader.result.split(',')[1],
          filename: file.name || 'photo.jpg',
          type: file.type || 'image/jpeg',
          size: file.size
        });
      };
      reader.onerror = function() { reject(reader.error); };
      reader.readAsDataURL(file);
    });
  }

  // ── Serialize form → plain object (skip files) ──────────────────
  function serializeForm(form) {
    var data = {};
    var fd = new FormData(form);
    var entries = fd.entries ? fd.entries() : [];
    var entry = entries.next ? entries.next() : { done: true };
    while (!entry.done) {
      var key = entry.value[0];
      var val = entry.value[1];
      // Skip file inputs — handled separately
      if (val instanceof File) {
        entry = entries.next();
        continue;
      }
      data[key] = val;
      entry = entries.next();
    }
    return data;
  }

  // ── Collect photos from form file inputs ────────────────────────
  function collectPhotos(form) {
    var fileInputs = form.querySelectorAll('input[type="file"]');
    var promises = [];
    for (var i = 0; i < fileInputs.length; i++) {
      var input = fileInputs[i];
      if (input.files && input.files.length > 0) {
        for (var j = 0; j < input.files.length; j++) {
          promises.push(fileToBase64(input.files[j]).then(function(result) {
            if (result) result.field_name = input.name;
            return result;
          }));
        }
      }
    }
    // Also check for FenixCamera captured photos stored in window._golubarPhotos
    if (window._golubarPhotos && window._golubarPhotos.length > 0) {
      window._golubarPhotos.forEach(function(p) {
        promises.push(Promise.resolve(p));
      });
    }
    return Promise.all(promises).then(function(results) {
      return results.filter(function(r) { return r !== null; });
    });
  }

  // ── Save to store ───────────────────────────────────────────────
  function saveToStore(storeName, entry) {
    return openDB().then(function(db) {
      return new Promise(function(resolve, reject) {
        var tx = db.transaction(storeName, 'readwrite');
        var store = tx.objectStore(storeName);
        entry.created_at = new Date().toISOString();
        entry.synced = false;
        var req = store.add(entry);
        req.onsuccess = function() { resolve(req.result); };
        req.onerror = function() { reject(req.error); };
      });
    });
  }

  // ── Get all from store ──────────────────────────────────────────
  function getAll(storeName) {
    return openDB().then(function(db) {
      return new Promise(function(resolve, reject) {
        var tx = db.transaction(storeName, 'readonly');
        var req = tx.objectStore(storeName).getAll();
        req.onsuccess = function() { resolve(req.result || []); };
        req.onerror = function() { reject(req.error); };
      });
    });
  }

  // ── Delete from store ───────────────────────────────────────────
  function deleteFromStore(storeName, id) {
    return openDB().then(function(db) {
      return new Promise(function(resolve, reject) {
        var tx = db.transaction(storeName, 'readwrite');
        tx.objectStore(storeName).delete(id);
        tx.oncomplete = function() { resolve(); };
        tx.onerror = function() { reject(tx.error); };
      });
    });
  }

  // ── Base64 → Blob ───────────────────────────────────────────────
  function b64toBlob(b64, type) {
    type = type || 'image/jpeg';
    var byteString = atob(b64);
    var ab = new ArrayBuffer(byteString.length);
    var ia = new Uint8Array(ab);
    for (var i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: type });
  }

  // ── Reconstruct FormData from saved entry ───────────────────────
  function reconstructFormData(entry) {
    var fd = new FormData();
    var data = entry.form_data || {};
    for (var key in data) {
      if (data.hasOwnProperty(key)) {
        fd.append(key, data[key]);
      }
    }
    // Re-attach photos as File objects
    var photos = entry.photos || [];
    for (var i = 0; i < photos.length; i++) {
      var p = photos[i];
      var blob = b64toBlob(p.b64, p.type || 'image/jpeg');
      var file = new File([blob], p.filename || 'photo.jpg', { type: p.type || 'image/jpeg' });
      fd.append(p.field_name || 'fotografija', file);
    }
    return fd;
  }

  // ══════════════════════════════════════════════════════════════════
  // PUBLIC API
  // ══════════════════════════════════════════════════════════════════

  // ── Save golub form offline ─────────────────────────────────────
  function saveGolub(form) {
    var formData = serializeForm(form);
    formData._csrf = getCSRF();
    return collectPhotos(form).then(function(photos) {
      return saveToStore(STORE_GOLUBOVI, {
        form_data: formData,
        photos: photos,
        url: form.action || window.location.href
      });
    });
  }

  // ── Save golubinjak form offline ────────────────────────────────
  function saveGolubinjak(form) {
    var formData = serializeForm(form);
    formData._csrf = getCSRF();
    return saveToStore(STORE_GOLUBINJACI, {
      form_data: formData,
      photos: [],
      url: form.action || window.location.href
    });
  }

  // ── Get pending count ───────────────────────────────────────────
  function getPendingCount() {
    return Promise.all([
      getAll(STORE_GOLUBOVI),
      getAll(STORE_GOLUBINJACI)
    ]).then(function(results) {
      var golubovi = results[0].filter(function(e) { return !e.synced; });
      var golubinjaci = results[1].filter(function(e) { return !e.synced; });
      return golubovi.length + golubinjaci.length;
    });
  }

  // ── Sync one entry ──────────────────────────────────────────────
  function syncEntry(storeName, entry) {
    var fd = reconstructFormData(entry);
    // Use stored CSRF or current one
    var csrf = entry.form_data._csrf || getCSRF();
    // Remove internal _csrf from FormData (server uses header)
    fd.delete('_csrf');

    return fetch(entry.url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf
      },
      body: fd,
      credentials: 'same-origin',
      redirect: 'follow'
    }).then(function(response) {
      // Django form POST returns 302 on success, 200 on validation error
      if (response.ok || response.redirected || response.status === 302) {
        return deleteFromStore(storeName, entry.id).then(function() {
          return true;
        });
      }
      // If 403 (CSRF expired), try with current CSRF
      if (response.status === 403) {
        var newCsrf = getCSRF();
        if (newCsrf && newCsrf !== csrf) {
          fd.set('csrfmiddlewaretoken', newCsrf);
          return fetch(entry.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': newCsrf },
            body: fd,
            credentials: 'same-origin',
            redirect: 'follow'
          }).then(function(r2) {
            if (r2.ok || r2.redirected || r2.status === 302) {
              return deleteFromStore(storeName, entry.id).then(function() {
                return true;
              });
            }
            return false;
          });
        }
      }
      return false;
    }).catch(function() {
      return false;
    });
  }

  // ── Sync all pending ────────────────────────────────────────────
  function syncNow() {
    var totalSynced = 0;
    return getAll(STORE_GOLUBOVI).then(function(golubovi) {
      var pending = golubovi.filter(function(e) { return !e.synced; });
      var chain = Promise.resolve();
      pending.forEach(function(entry) {
        chain = chain.then(function() {
          return syncEntry(STORE_GOLUBOVI, entry).then(function(ok) {
            if (ok) totalSynced++;
          });
        });
      });
      return chain;
    }).then(function() {
      return getAll(STORE_GOLUBINJACI);
    }).then(function(golubinjaci) {
      var pending = golubinjaci.filter(function(e) { return !e.synced; });
      var chain = Promise.resolve();
      pending.forEach(function(entry) {
        chain = chain.then(function() {
          return syncEntry(STORE_GOLUBINJACI, entry).then(function(ok) {
            if (ok) totalSynced++;
          });
        });
      });
      return chain;
    }).then(function() {
      if (totalSynced > 0) {
        showToast(totalSynced + ' zapis(a) sinkronizirano!', 'success');
        updatePendingBadge();
        // Try to register background sync for future
        if ('serviceWorker' in navigator && navigator.serviceWorker.ready) {
          navigator.serviceWorker.ready.then(function(reg) {
            if (reg.sync) reg.sync.register('golubar-sync');
          });
        }
      }
      return totalSynced;
    });
  }

  // ── Toast helper ────────────────────────────────────────────────
  function showToast(message, type) {
    type = type || 'info';
    // Try offlineBar first
    var bar = document.getElementById('offlineBar');
    var msg = document.getElementById('offlineMsg');
    if (bar && msg) {
      bar.style.display = 'block';
      if (type === 'success') {
        bar.style.background = 'linear-gradient(135deg, #166534, #14532d)';
        bar.style.borderColor = '#22c55e';
      } else {
        bar.style.background = 'linear-gradient(135deg, #78350f, #451a03)';
        bar.style.borderColor = '#c9a84c';
      }
      msg.textContent = message;
      if (type === 'success') {
        setTimeout(function() { bar.style.display = 'none'; }, 4000);
      }
      return;
    }
    // Fallback: create floating toast
    var toast = document.createElement('div');
    toast.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
      'padding:14px 24px;border-radius:12px;font-size:.88rem;font-weight:600;z-index:99999;' +
      'box-shadow:0 8px 32px rgba(0,0,0,.3);transition:opacity .3s;max-width:90vw;text-align:center;';
    if (type === 'success') {
      toast.style.background = 'linear-gradient(135deg, #166534, #14532d)';
      toast.style.color = '#22c55e';
      toast.style.border = '1px solid rgba(34,197,94,.3)';
    } else {
      toast.style.background = 'linear-gradient(135deg, #78350f, #451a03)';
      toast.style.color = '#c9a84c';
      toast.style.border = '1px solid rgba(201,168,76,.3)';
    }
    toast.innerHTML = (type === 'success' ? '<i class="fas fa-check-circle me-1"></i>' : '<i class="fas fa-cloud me-1"></i>') + message;
    document.body.appendChild(toast);
    setTimeout(function() {
      toast.style.opacity = '0';
      setTimeout(function() { toast.remove(); }, 300);
    }, 4000);
  }

  // ── Update pending badge on dashboard ───────────────────────────
  function updatePendingBadge() {
    var el = document.getElementById('offline-pending');
    var countEl = document.getElementById('pending-count');
    if (!el || !countEl) return;
    getPendingCount().then(function(c) {
      if (c > 0) {
        el.style.display = 'block';
        countEl.textContent = c;
      } else {
        el.style.display = 'none';
      }
    });
  }

  // ── Listen for online event → auto sync ─────────────────────────
  window.addEventListener('online', function() {
    setTimeout(function() {
      syncNow();
    }, 2000); // Wait 2s for stable connection
  });

  // ── Listen for SW message (GOLUBAR_SYNC) ────────────────────────
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function(event) {
      if (event.data && event.data.type === 'GOLUBAR_SYNC') {
        syncNow();
      }
    });
  }

  // ── Gallery enhancement via FenixCamera ─────────────────────────
  // Store captured photos for offline save
  window._golubarPhotos = [];

  function enhanceGalleryButton() {
    // Find gallery buttons in golub form and enhance with FenixCamera multi-pick
    var galleryLabels = document.querySelectorAll('.gf-cam-gallery');
    galleryLabels.forEach(function(label) {
      var input = label.querySelector('input[type="file"]');
      if (!input) return;
      // Allow multiple files
      input.setAttribute('multiple', 'multiple');
    });
  }

  function addPhotoToOfflineQueue(result, fieldName) {
    window._golubarPhotos.push({
      b64: result.b64,
      filename: result.filename,
      type: 'image/jpeg',
      field_name: fieldName || 'fotografija'
    });
  }

  // ── Init: enhance gallery on page load ──────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceGalleryButton);
  } else {
    enhanceGalleryButton();
  }

  // ══════════════════════════════════════════════════════════════════
  // EXPOSE PUBLIC API
  // ══════════════════════════════════════════════════════════════════
  window.GolubarOffline = {
    saveGolub: saveGolub,
    saveGolubinjak: saveGolubinjak,
    getPendingCount: getPendingCount,
    syncNow: syncNow,
    showToast: showToast,
    updatePendingBadge: updatePendingBadge,
    addPhotoToOfflineQueue: addPhotoToOfflineQueue,
    version: '1.0.0'
  };

})();
