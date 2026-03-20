/* ═══ POS Offline Engine v2 — Kompletna smjena bez interneta ═══
 *
 * Nadogradnja pos-core.js offline sustava.
 * Koristi IndexedDB umjesto localStorage (nema 5MB limita).
 *
 * Mogucnosti:
 * 1. Offline otvaranje smjene (cached session)
 * 2. Offline prodaja s local receipt brojevima
 * 3. Offline racun prikaz (ne PDF, ali HTML)
 * 4. Offline polog/podizanje gotovine
 * 5. Offline zatvaranje smjene (lokalni Z-report)
 * 6. Bulk sync kad se vrati internet
 * 7. IndexedDB storage (neogranicen prostor)
 */
(function(){
  'use strict';

  var DB_NAME = 'pos_offline_v2';
  var DB_VERSION = 1;
  var db = null;

  // ── IndexedDB Setup ────────────────────────────────────────────────
  function openDB(callback) {
    if (db) { callback(db); return; }
    var req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = function(e) {
      var d = e.target.result;
      if (!d.objectStoreNames.contains('receipts')) {
        var store = d.createObjectStore('receipts', { keyPath: 'offline_id' });
        store.createIndex('synced', 'synced', { unique: false });
        store.createIndex('session_id', 'session_id', { unique: false });
      }
      if (!d.objectStoreNames.contains('sessions')) {
        d.createObjectStore('sessions', { keyPath: 'offline_session_id' });
      }
      if (!d.objectStoreNames.contains('cash_ops')) {
        d.createObjectStore('cash_ops', { keyPath: 'offline_id' });
      }
    };
    req.onsuccess = function(e) { db = e.target.result; callback(db); };
    req.onerror = function(e) { console.error('IndexedDB error:', e); };
  }

  // ── 1. Offline Session Management ─────────────────────────────────
  // Cache session info kad je online, koristi kad je offline
  window.cacheSessionForOffline = function(sessionData) {
    openDB(function(db) {
      var tx = db.transaction('sessions', 'readwrite');
      tx.objectStore('sessions').put(sessionData);
    });
    // Also cache in localStorage as fast fallback
    try {
      localStorage.setItem('pos_active_session', JSON.stringify(sessionData));
    } catch(e) {}
  };

  window.getOfflineSession = function() {
    try {
      return JSON.parse(localStorage.getItem('pos_active_session') || 'null');
    } catch(e) { return null; }
  };

  // ── 2. Offline Receipt Queue (IndexedDB) ──────────────────────────
  window.queueOfflineReceipt = function(receiptData) {
    var offlineId = 'OFF-' + Date.now() + '-' + Math.random().toString(36).substr(2,6);
    var session = window.getOfflineSession();

    var record = {
      offline_id: offlineId,
      session_id: receiptData.session_id || (session ? session.id : null),
      terminal_id: receiptData.terminal_id || (session ? session.terminal_id : null),
      items: receiptData.items || [],
      payment_method: receiptData.payment_method || 'CASH',
      amount_paid: receiptData.amount_paid || 0,
      tip_amount: receiptData.tip_amount || 0,
      note: receiptData.note || '',
      created_at: new Date().toISOString(),
      synced: 0,
      sync_error: '',
      // Local receipt number
      local_receipt_number: getNextLocalReceiptNumber(),
      // Izracunati lokalni total
      total: calculateTotal(receiptData.items || []),
      change: 0,
    };

    record.change = Math.max(0, (record.amount_paid || record.total) - record.total);

    openDB(function(db) {
      var tx = db.transaction('receipts', 'readwrite');
      tx.objectStore('receipts').put(record);
      tx.oncomplete = function() {
        updateOfflineBadge();
        showPosToast('Bon #' + record.local_receipt_number + ' spremljen offline', 'info');
      };
    });

    return record;
  };

  function getNextLocalReceiptNumber() {
    var last = parseInt(localStorage.getItem('pos_offline_receipt_counter') || '0');
    last++;
    localStorage.setItem('pos_offline_receipt_counter', String(last));
    return last;
  }

  function calculateTotal(items) {
    var total = 0;
    items.forEach(function(it) {
      var price = parseFloat(it.unit_price || it.price || 0);
      var qty = parseFloat(it.quantity || it.qty || 1);
      var tax = parseFloat(it.tax_rate || it.tax || 25);
      total += price * qty * (1 + tax / 100);
    });
    return Math.round(total * 100) / 100;
  }

  // ── 3. Offline Receipt Display ────────────────────────────────────
  window.showOfflineReceipt = function(record) {
    var session = window.getOfflineSession();
    var companyName = session ? session.company_name : 'LIMIT Connect';
    var terminalName = session ? session.terminal_name : 'POS';

    var html = '<div style="font-family:monospace;max-width:300px;margin:auto;padding:20px;background:#fff;color:#000">';
    html += '<div style="text-align:center;font-weight:bold;font-size:14px">' + companyName + '</div>';
    html += '<div style="text-align:center;font-size:11px">' + terminalName + '</div>';
    html += '<div style="text-align:center;font-size:10px;color:#888">OFFLINE BON</div>';
    html += '<hr style="border:none;border-top:1px dashed #000">';
    html += '<div style="font-size:11px">Bon #: OFF-' + record.local_receipt_number + '</div>';
    html += '<div style="font-size:11px">Datum: ' + new Date(record.created_at).toLocaleString('hr') + '</div>';
    html += '<hr style="border:none;border-top:1px dashed #000">';

    (record.items || []).forEach(function(it) {
      var name = it.name || it.description || 'Artikl';
      var qty = it.quantity || it.qty || 1;
      var price = parseFloat(it.unit_price || it.price || 0);
      html += '<div style="display:flex;justify-content:space-between;font-size:11px">';
      html += '<span>' + qty + 'x ' + name + '</span>';
      html += '<span>' + (qty * price).toFixed(2) + '</span>';
      html += '</div>';
    });

    html += '<hr style="border:none;border-top:1px dashed #000">';
    html += '<div style="display:flex;justify-content:space-between;font-weight:bold">';
    html += '<span>UKUPNO:</span><span>' + record.total.toFixed(2) + ' EUR</span></div>';

    if (record.change > 0) {
      html += '<div style="display:flex;justify-content:space-between;font-size:11px">';
      html += '<span>Placeno:</span><span>' + record.amount_paid.toFixed(2) + ' EUR</span></div>';
      html += '<div style="display:flex;justify-content:space-between;font-size:11px">';
      html += '<span>Povrat:</span><span>' + record.change.toFixed(2) + ' EUR</span></div>';
    }

    html += '<div style="font-size:10px;color:#888;text-align:center;margin-top:10px">';
    html += record.payment_method + ' | ' + record.offline_id;
    // Country-aware offline clause
    var session = window.getOfflineSession();
    var isDE = session && (session.country === 'DE' || session.fiscal_system === 'de_gobd');
    if (isDE) {
      html += '<br><br><strong style="border:2px solid #000;padding:4px;display:block;text-align:center">*** TSE AUSGEFALLEN ***<br>Nacherfassung erfolgt automatisch<br>gem. KassenSichV §146a AO</strong>';
    } else {
      html += '<br>* Fiskalizacija ce biti izvrsena naknadno *';
    }
    html += '</div>';
    html += '</div>';

    // Open in new window for printing
    var w = window.open('', '_blank', 'width=350,height=500');
    if (w) {
      w.document.write('<html><body>' + html + '<script>setTimeout(function(){window.print()},300)<\/script></body></html>');
    }
  };

  // ── 4. Offline Cash Operations ────────────────────────────────────
  window.queueOfflineCashOp = function(type, amount, note) {
    var session = window.getOfflineSession();
    var record = {
      offline_id: 'CASH-' + Date.now(),
      session_id: session ? session.id : null,
      type: type, // 'deposit' or 'withdrawal'
      amount: parseFloat(amount),
      note: note || '',
      created_at: new Date().toISOString(),
    };

    openDB(function(db) {
      var tx = db.transaction('cash_ops', 'readwrite');
      tx.objectStore('cash_ops').put(record);
      tx.oncomplete = function() {
        showPosToast(
          (type === 'deposit' ? 'Polog' : 'Podizanje') + ' ' + amount + ' EUR spremljen offline',
          'info'
        );
      };
    });
    return record;
  };

  // ── 5. Offline Shift Summary ──────────────────────────────────────
  window.getOfflineShiftSummary = function(callback) {
    openDB(function(db) {
      var session = window.getOfflineSession();
      if (!session) { callback(null); return; }

      var tx = db.transaction(['receipts', 'cash_ops'], 'readonly');
      var receipts = [];
      var cashOps = [];

      tx.objectStore('receipts').openCursor().onsuccess = function(e) {
        var cursor = e.target.result;
        if (cursor) {
          if (cursor.value.session_id == session.id) {
            receipts.push(cursor.value);
          }
          cursor.continue();
        }
      };

      tx.objectStore('cash_ops').openCursor().onsuccess = function(e) {
        var cursor = e.target.result;
        if (cursor) {
          if (cursor.value.session_id == session.id) {
            cashOps.push(cursor.value);
          }
          cursor.continue();
        }
      };

      tx.oncomplete = function() {
        var totalSales = 0;
        var cashSales = 0;
        var cardSales = 0;
        var receiptCount = 0;

        receipts.forEach(function(r) {
          totalSales += r.total || 0;
          receiptCount++;
          if (r.payment_method === 'CASH') cashSales += r.total || 0;
          else cardSales += r.total || 0;
        });

        var deposits = 0, withdrawals = 0;
        cashOps.forEach(function(op) {
          if (op.type === 'deposit') deposits += op.amount;
          else withdrawals += op.amount;
        });

        callback({
          session_id: session.id,
          terminal_name: session.terminal_name,
          receipt_count: receiptCount,
          total_sales: totalSales,
          cash_sales: cashSales,
          card_sales: cardSales,
          deposits: deposits,
          withdrawals: withdrawals,
          opening_cash: session.opening_cash || 0,
          expected_cash: (session.opening_cash || 0) + cashSales + deposits - withdrawals,
          unsynced: receipts.filter(function(r) { return !r.synced; }).length,
        });
      };
    });
  };

  // ── 6. Bulk Sync ──────────────────────────────────────────────────
  window.syncOfflineData = function() {
    if (!navigator.onLine) {
      showPosToast('Nema veze — pokusajte kasnije', 'warning');
      return;
    }

    openDB(function(db) {
      var tx = db.transaction('receipts', 'readonly');
      var unsynced = [];

      tx.objectStore('receipts').index('synced').openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        var cursor = e.target.result;
        if (cursor) {
          unsynced.push(cursor.value);
          cursor.continue();
        }
      };

      tx.oncomplete = function() {
        if (!unsynced.length) {
          showPosToast('Sve je sinkronizirano!', 'success');
          return;
        }

        showPosToast('Sinkroniziram ' + unsynced.length + ' bonova...', 'info');
        var done = 0;
        var errors = 0;

        unsynced.forEach(function(receipt) {
          var url = '/pos/session/' + receipt.session_id + '/quick-pay/';

          fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({
              session_id: receipt.session_id,
              items: receipt.items,
              payment_method: receipt.payment_method,
              amount_paid: receipt.amount_paid,
              tip_amount: receipt.tip_amount,
              note: (receipt.note || '') + ' [OFFLINE:' + receipt.offline_id + ']',
              client_ip: '',
              client_ua: 'OFFLINE-SYNC',
            })
          })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.ok) {
              // Mark as synced in IndexedDB
              var utx = db.transaction('receipts', 'readwrite');
              var rec = receipt;
              rec.synced = 1;
              rec.server_receipt_id = data.receipt_id;
              rec.server_receipt_number = data.receipt_number;
              utx.objectStore('receipts').put(rec);
              done++;
            } else {
              errors++;
              // Store error
              var etx = db.transaction('receipts', 'readwrite');
              receipt.sync_error = data.error || 'Unknown';
              etx.objectStore('receipts').put(receipt);
            }

            if (done + errors >= unsynced.length) {
              updateOfflineBadge();
              if (errors) {
                showPosToast('Sinkronizirano ' + done + '/' + unsynced.length + ' (' + errors + ' gresaka)', 'warning');
              } else {
                showPosToast('Sinkronizirano ' + done + ' bonova!', 'success');
              }
            }
          })
          .catch(function(err) {
            errors++;
            console.error('Sync error:', receipt.offline_id, err);
          });
        });

        // Sync cash operations too
        var cashTx = db.transaction('cash_ops', 'readonly');
        var cashOps = [];
        cashTx.objectStore('cash_ops').openCursor().onsuccess = function(e) {
          var c = e.target.result;
          if (c) { cashOps.push(c.value); c.continue(); }
        };
        cashTx.oncomplete = function() {
          cashOps.forEach(function(op) {
            fetch('/pos/session/' + op.session_id + '/cash-deposit/', {
              method: 'POST',
              headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': getCsrf() },
              body: 'amount=' + op.amount + '&deposit_type=' + op.type + '&note=' + encodeURIComponent(op.note + ' [OFFLINE]'),
            }).catch(function(err) { console.error('Cash sync error:', err); });
          });
        };
      };
    });
  };

  // ── 7. Offline Badge ──────────────────────────────────────────────
  function updateOfflineBadge() {
    openDB(function(db) {
      var tx = db.transaction('receipts', 'readonly');
      var count = 0;
      tx.objectStore('receipts').index('synced').openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        var cursor = e.target.result;
        if (cursor) { count++; cursor.continue(); }
      };
      tx.oncomplete = function() {
        var badge = document.getElementById('offlineSyncBadge');
        if (badge) {
          badge.textContent = count ? count + ' offline' : '';
          badge.style.display = count ? 'inline-block' : 'none';
        }
        // Also update old badge
        var oldBadge = document.getElementById('offlineQueue');
        if (oldBadge) {
          oldBadge.textContent = count ? count + ' ceka sync' : '';
        }
      };
    });
  }

  // ── Auto-sync on reconnect ────────────────────────────────────────
  window.addEventListener('online', function() {
    setTimeout(function() { window.syncOfflineData(); }, 3000);
  });

  // Init
  openDB(function() { updateOfflineBadge(); });

})();
