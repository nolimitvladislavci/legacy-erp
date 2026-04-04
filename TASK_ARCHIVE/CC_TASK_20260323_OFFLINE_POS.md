# CC TASK: Offline POS mod — kompletan (zakonski 48h)
**Datum:** 23.03.2026
**Prioritet:** VISOK — zakonska obveza (Zakon o fiskalizaciji čl. 11)
**Procjena:** 4-6 sati

---

## ZAKONSKI OKVIR — OBVEZNO RAZUMJETI PRIJE PISANJA KODA

### Zakon o fiskalizaciji (NN 133/12, 115/16, 106/18), čl. 11:
- Ako CIS (FINA) nije dostupan → obveznik **smije izdavati račune** s lokalnim ZKI
- **Rok za dostavu JIR-a: 48 sati** od trenutka kada veza postane dostupna
- Računima bez JIR-a → na ispisku mora pisati "Veza s CIS-om nije ostvarena"
- Nakon uspostave veze → **automatski retry** svakih 15 min dok sve ne dobije JIR
- Nikad ne blokiraj prodaju zbog nedostupnosti FINE!

### Što već postoji (NE RADITI PONOVO):
- `POSReceipt.zki` — lokalno generiran ZKI (model postoji)
- `POSReceipt.jir` — JIR koji dolazi od FINE (null = još nije fiskaliziran)
- `POSReceipt.fiscal_retry_count` + `fiscal_last_error` — retry tracking
- `pos/tasks.py` → `retry_fiscalization()` — Celery task (postoji)
- `static/sw.js` v4 — ServiceWorker s IndexedDB offline queue (postoji)
- `pos/views_v2.py` — SW JS s background sync tagom 'pos-offline-sync'
- `pos/tests/test_b04_b08_b02.py` — B-04 testovi za retry (postoje)

### Što NEDOSTAJE (ovo gradimo):
1. **Frontend offline mod** — POS radi lokalno kad nema interneta
2. **IndexedDB → server sync** — kad se internet vrati, sve se sinkronizira
3. **UI indikatori** — korisnik uvijek zna je li online/offline
4. **Zakonski ispis** — "Veza s CIS-om nije ostvarena" kad nema JIR-a
5. **Backend offline receipt endpoint** — prima batch iz IndexedDB
6. **48h alarm** — upozorenje kad bon prijeti zakonskim rokom

---

## ARHITEKTURA — PREGLED

```
[POS Browser]
     │
     ├── Online → normalan flow → FINA CIS → JIR odmah
     │
     └── Offline → IndexedDB (lokalni storage)
                        │
                        └── Veza uspostavljena → Batch sync endpoint
                                                        │
                                                        └── retry_fiscalization() → JIR
```

---

## TASK 1: Backend — offline batch endpoint

**Fajl:** `pos/views_v2.py` (dodati novi view)

### Novi endpoint: `POST /pos/api/offline-sync/`

Prima JSON array lokalnih bonova iz IndexedDB, kreira ih u bazi ako ne postoje:

```python
@require_POST
@login_required
def offline_sync(request):
    """
    Prima batch offline bonova iz IndexedDB.
    Kreira POSReceipt za svaki, označava offline_created=True.
    Vraća: {synced: N, errors: [...]}
    """
    import json
    from pos.models import POSTerminal, POSSession, POSReceipt, POSReceiptItem
    from django.db import transaction

    try:
        data = json.loads(request.body)
        receipts = data.get('receipts', [])
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    company = get_user_company(request)
    synced = 0
    errors = []

    for r_data in receipts:
        offline_id = r_data.get('offline_id')
        # Provjeri duplikat po offline_id
        if POSReceipt.objects.filter(
            session__terminal__company=company,
            fiscal_last_error__contains=f'offline_id:{offline_id}'
        ).exists():
            continue

        try:
            with transaction.atomic():
                terminal = POSTerminal.objects.filter(
                    company=company,
                    id=r_data.get('terminal_id')
                ).first()
                if not terminal:
                    errors.append({'offline_id': offline_id, 'error': 'Terminal not found'})
                    continue

                session = POSSession.objects.filter(
                    terminal=terminal,
                    status__in=['open', 'closed']
                ).order_by('-opened_at').first()
                if not session:
                    errors.append({'offline_id': offline_id, 'error': 'No session'})
                    continue

                # Kreiraj receipt
                receipt = POSReceipt.objects.create(
                    session=session,
                    total=r_data.get('total', 0),
                    payment_method=r_data.get('payment_method', 'cash'),
                    status='paid',
                    note=r_data.get('note', '') + f' [offline_id:{offline_id}]',
                    paid_at=r_data.get('paid_at'),
                    # ZKI generiran offline — JIR dolazi kroz retry
                    zki=r_data.get('zki', ''),
                    jir='',  # prazan — retry će popuniti
                    fiscal_retry_count=0,
                )

                # Stavke
                for item in r_data.get('items', []):
                    POSReceiptItem.objects.create(
                        receipt=receipt,
                        inventory_item_id=item.get('product_id'),
                        description=item.get('name', ''),
                        quantity=item.get('quantity', 1),
                        unit_price=item.get('unit_price', 0),
                        total_price=item.get('total', 0),
                        tax_rate=item.get('tax_rate', 25),
                    )

                synced += 1

        except Exception as e:
            errors.append({'offline_id': offline_id, 'error': str(e)})

    # Odmah pokreni retry fiskalizacije
    from pos.tasks import retry_fiscalization
    retry_fiscalization.delay()

    return JsonResponse({'synced': synced, 'errors': errors})
```

**URL:** `pos/urls.py` → dodaj:
```python
path('api/offline-sync/', views_v2.offline_sync, name='offline_sync'),
```

---

## TASK 2: Frontend — offline mod u quick.html

**Fajl:** `templates/pos/quick.html`

### 2a. Offline status bar (dodati u header)

Nakon `.active-cashier-bar` div-a, dodati:
```html
<!-- Offline status bar -->
<div id="offlineBanner" style="display:none;background:#7c3aed;color:#fff;
     text-align:center;padding:6px 12px;font-size:.78rem;font-weight:600;
     border-bottom:1px solid rgba(255,255,255,.2)">
  <span id="offlineBannerText">OFFLINE MOD — bonovi se čuvaju lokalno</span>
  <span id="offlineQueueCount" style="margin-left:8px;background:rgba(255,255,255,.25);
        border-radius:10px;padding:2px 8px;font-size:.72rem"></span>
</div>

<!-- 48h upozorenje -->
<div id="fiscal48hBanner" style="display:none;background:#dc2626;color:#fff;
     text-align:center;padding:6px 12px;font-size:.78rem;font-weight:600">
  UPOZORENJE: Neki bonovi su stariji od 36h bez JIR-a! Uspostavi vezu odmah.
</div>
```

### 2b. Offline JS logika

Dodati u `<script>` blok quick.html (ili poseban fajl `static/pos/pos_offline.js`):

```javascript
// ═══ OFFLINE MOD ═══════════════════════════════════════════════════════

var _offlineDB = null;
var _isOffline = false;
var _offlineQueue = [];

// Init IndexedDB
function _initOfflineDB() {
  return new Promise(function(resolve, reject) {
    var req = indexedDB.open('limitconnect_pos_v1', 2);
    req.onupgradeneeded = function(e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains('receipts')) {
        var store = db.createObjectStore('receipts', {keyPath: 'offline_id'});
        store.createIndex('synced', 'synced', {unique: false});
        store.createIndex('created_at', 'created_at', {unique: false});
      }
    };
    req.onsuccess = function(e) { _offlineDB = e.target.result; resolve(); };
    req.onerror = function(e) { reject(e); };
  });
}

// Spremi bon lokalno
function _saveReceiptOffline(receiptData) {
  return new Promise(function(resolve, reject) {
    if (!_offlineDB) { reject('DB not ready'); return; }
    var tx = _offlineDB.transaction(['receipts'], 'readwrite');
    var store = tx.objectStore('receipts');
    receiptData.synced = false;
    receiptData.created_at = Date.now();
    store.put(receiptData);
    tx.oncomplete = function() { resolve(receiptData.offline_id); };
    tx.onerror = function(e) { reject(e); };
  });
}

// Dohvati nesinhronizirane bonove
function _getUnsynced() {
  return new Promise(function(resolve) {
    if (!_offlineDB) { resolve([]); return; }
    var tx = _offlineDB.transaction(['receipts'], 'readonly');
    var store = tx.objectStore('receipts');
    var idx = store.index('synced');
    var req = idx.getAll(false);
    req.onsuccess = function() { resolve(req.result || []); };
    req.onerror = function() { resolve([]); };
  });
}

// Označi kao sinhronizirano
function _markSynced(offline_id) {
  if (!_offlineDB) return;
  var tx = _offlineDB.transaction(['receipts'], 'readwrite');
  var store = tx.objectStore('receipts');
  var req = store.get(offline_id);
  req.onsuccess = function() {
    if (req.result) {
      req.result.synced = true;
      store.put(req.result);
    }
  };
}

// Sync s backendom
function _syncOfflineQueue() {
  _getUnsynced().then(function(receipts) {
    if (!receipts.length) return;
    fetch('/pos/api/offline-sync/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': _shGetCSRF ? _shGetCSRF() : getCsrfToken()
      },
      body: JSON.stringify({receipts: receipts})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.synced > 0) {
        receipts.slice(0, data.synced).forEach(function(r) {
          _markSynced(r.offline_id);
        });
        if (typeof fenixToast === 'function') {
          fenixToast(data.synced + ' bonova sinhronizirano', 'success');
        }
        _updateOfflineBanner();
      }
    })
    .catch(function(e) { console.warn('Offline sync failed:', e); });
  });
}

// Ažuriraj banner
function _updateOfflineBanner() {
  _getUnsynced().then(function(receipts) {
    var banner = document.getElementById('offlineBanner');
    var countEl = document.getElementById('offlineQueueCount');
    var alertBanner = document.getElementById('fiscal48hBanner');

    if (!banner) return;

    if (_isOffline || receipts.length > 0) {
      banner.style.display = 'block';
      if (countEl) {
        countEl.textContent = receipts.length > 0 ? receipts.length + ' u redu' : '';
      }
    } else {
      banner.style.display = 'none';
    }

    // 48h provjera — ZOR rok
    var now = Date.now();
    var critical = receipts.filter(function(r) {
      return (now - r.created_at) > 36 * 60 * 60 * 1000; // 36h warning
    });
    if (alertBanner) {
      alertBanner.style.display = critical.length > 0 ? 'block' : 'none';
    }
  });
}

// Online/offline event listeners
window.addEventListener('online', function() {
  _isOffline = false;
  _updateOfflineBanner();
  _syncOfflineQueue();
  console.log('POS: Online — sinkroniziram offline bonove');
});

window.addEventListener('offline', function() {
  _isOffline = true;
  _updateOfflineBanner();
  console.log('POS: Offline — bonovi idu u lokalnu bazu');
});

// Provjeri status na load
if (!navigator.onLine) {
  _isOffline = true;
}

// Init DB i banner
_initOfflineDB().then(function() {
  _updateOfflineBanner();
  // Ako smo online i ima nešto u queuu — sinhroniziraj
  if (!_isOffline) {
    _syncOfflineQueue();
  }
}).catch(function(e) {
  console.warn('Offline DB init failed:', e);
});

// Periodic sync svake 2 minute
setInterval(function() {
  if (!_isOffline) { _syncOfflineQueue(); }
  _updateOfflineBanner();
}, 2 * 60 * 1000);
```

### 2c. Modificiraj checkout flow

U funkciji koja šalje bon na server (traži `fetch('/pos/` ili `submitReceipt` ili `payBasket`):

```javascript
// Zamotaj postojeći fetch u offline-aware wrapper:
function _submitReceiptWithOfflineFallback(receiptData, onSuccess, onError) {
  if (!navigator.onLine) {
    // Offline → spremi lokalno
    var offlineId = 'off_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    receiptData.offline_id = offlineId;
    receiptData.terminal_id = POS_STATE.terminalId; // mora biti dostupan u POS_STATE
    _saveReceiptOffline(receiptData).then(function() {
      _updateOfflineBanner();
      // Generiraj lokalni ZKI (dummy, samo da bon može biti ispisan)
      var localZki = 'LOCAL-' + offlineId.slice(-8).toUpperCase();
      onSuccess({
        offline: true,
        offline_id: offlineId,
        zki: localZki,
        jir: null,
        receipt_number: 'OFFLINE-' + Date.now()
      });
    }).catch(onError);
  } else {
    // Online → normalan flow
    // ... postojeći kod ...
  }
}
```

---

## TASK 3: Ispis offline bona

**Fajl:** `templates/pos/receipt_print.html` ili inline u quick.html print funkcija

Kad bon nema JIR (`jir == null` ili prazan):
```html
{% if not receipt.jir %}
<div style="text-align:center;border:2px solid #000;padding:4px;margin:8px 0;font-size:.8rem;font-weight:bold">
  VEZA S CIS-om NIJE OSTVARENA<br>
  <small>Fiskalizacija u tijeku — ZKI: {{ receipt.zki }}</small>
</div>
{% endif %}
```

U JS print funkciji (quick.html):
```javascript
// U _buildReceiptHtml() ili gdje se gradi HTML za ispis:
var fiscalLine = '';
if (!receiptData.jir) {
  fiscalLine = '<div style="text-align:center;border:2px solid #000;padding:4px;' +
    'margin:8px 0;font-size:.8rem;font-weight:bold">' +
    'VEZA S CIS-om NIJE OSTVARENA<br>' +
    '<small>ZKI: ' + (receiptData.zki || 'LOKALNI') + '</small></div>';
}
```

---

## TASK 4: Backend — 48h Celery alarm

**Fajl:** `pos/tasks.py` — dodati u postojeći `retry_fiscalization()` ili novi task:

```python
@shared_task
def check_fiscal_deadline():
    """
    Upozorenje: bonovi koji su > 36h bez JIR-a (alarm 12h prije zakonskog roka).
    Šalje WhatsApp/email vlasniku tvrtke.
    """
    from datetime import timedelta
    from django.utils import timezone
    from pos.models import POSReceipt
    from companies.models import Company

    deadline_warning = timezone.now() - timedelta(hours=36)
    critical = POSReceipt.objects.filter(
        status='paid',
        jir__in=['', None],
        zki__isnull=False,
        paid_at__lt=deadline_warning,
    ).select_related('session__terminal__company')

    for receipt in critical:
        company = receipt.session.terminal.company
        hours_old = (timezone.now() - receipt.paid_at).total_seconds() / 3600
        # WhatsApp notify vlasniku
        try:
            from core.whatsapp import send_whatsapp_message
            admin = company.user_set.filter(is_staff=True).first()
            if admin and hasattr(admin, 'profile') and admin.profile.phone:
                msg = (
                    f"⚠️ FISKALIZACIJA ALARM\n"
                    f"Bon #{receipt.receipt_number} je {hours_old:.0f}h bez JIR-a.\n"
                    f"Zakonski rok: 48h od uspostave veze.\n"
                    f"Provjeri internet vezu odmah!"
                )
                send_whatsapp_message(admin.profile.phone, msg)
        except Exception as e:
            logger.warning('Fiscal deadline WhatsApp failed: %s', e)
```

**Celery beat schedule** (u `settings.py` ili `celery.py`):
```python
'check-fiscal-deadline': {
    'task': 'pos.tasks.check_fiscal_deadline',
    'schedule': crontab(minute='*/30'),  # svakih 30 min
},
```

---

## TASK 5: Ažurirati Service Worker

**Fajl:** `static/sw.js`

Dodati u background sync handler (tag: `pos-offline-sync`):
```javascript
// U sync event handleru — provjeri postoji li endpoint
self.addEventListener('sync', function(event) {
  if (event.tag === 'pos-offline-sync') {
    event.waitUntil(
      // Pošalji signal svim klijentima da pokrenu sync
      self.clients.matchAll().then(function(clients) {
        clients.forEach(function(client) {
          client.postMessage({type: 'TRIGGER_SYNC'});
        });
      })
    );
  }
});
```

U quick.html primati poruke od SW:
```javascript
navigator.serviceWorker.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'TRIGGER_SYNC') {
    _syncOfflineQueue();
  }
});
```

---

## TASK 6: Testovi

**Fajl:** `pos/tests/test_offline_pos.py` — NOVI

```python
"""
Offline POS testovi — zakonska obveza 48h fiskalizacije.
"""
class OfflineSyncTest(TestCase):
    def test_01_offline_sync_endpoint_creates_receipts(self):
        """Batch offline bonova se kreira u bazi."""

    def test_02_duplicate_offline_id_ignored(self):
        """Isti offline_id se ne kreira dvaput."""

    def test_03_receipts_without_jir_trigger_retry(self):
        """offline-sync automatski pokreće retry_fiscalization."""

    def test_04_48h_alarm_fires_at_36h(self):
        """check_fiscal_deadline() šalje alarm na 36h."""

    def test_05_receipt_print_shows_cis_warning(self):
        """Bon bez JIR-a ima 'VEZA S CIS-om NIJE OSTVARENA' u ispisku."""
```

---

## REDOSLIJED IZVRŠENJA

1. Task 4 (Celery alarm) — backend, nema frontend ovisnosti
2. Task 1 (offline-sync endpoint) — backend
3. Task 2a+2b (offline JS + banner) — frontend, neovisno
4. Task 3 (ispis) — frontend
5. Task 2c (checkout wrapper) — zadnje, ovisi o razumijevanju POS_STATE
6. Task 5 (SW ažuriranje)
7. Task 6 (testovi)

## PROVJERA MODELA PRIJE PISANJA
```bash
. venv/bin/activate
python manage.py shell -c "
from pos.models import POSReceipt, POSReceiptItem
print([f.name for f in POSReceipt._meta.get_fields() if not f.is_relation])
print([f.name for f in POSReceiptItem._meta.get_fields() if not f.is_relation])
"
# Provjeri i checkout view koji šalje bon — ime funkcije i URL
grep -n "def.*pay\|def.*checkout\|def.*submit.*receipt" pos/views_v2.py pos/views.py | head -10
```

## COMMIT FORMAT
```
Offline POS: 48h zakonski mod — IndexedDB queue, sync endpoint, fiscal alarm
```

## NAPOMENA ZA CC
- NE mijenjaj postojeći `retry_fiscalization()` — samo dodaj `check_fiscal_deadline()`
- Checkout flow wrapper (Task 2c) — OBAVEZNO pročitaj kako quick.html danas šalje bon
- `POS_STATE.terminalId` — provjeri postoji li to ili je drugi naziv
- Sve nove JS funkcije počinju s `_offline` prefiks da ne koliziraju s postojećim kodom
