# CC Task — Livestock V3: Karenca→POS, Offline PWA, JRDŽ osnova

## Pročitaj prvo — OBAVEZNO
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
cat /var/www/fina-connect/CC_TASK_FENIX_INTELLIGENCE.md       # V1 — što si napravio
cat /var/www/fina-connect/CC_TASK_FENIX_INTELLIGENCE_V2.md    # V2 — što radiš/si radio

# Ključni postojeći kod koji nasljeđujemo:
grep -n "karencija_do\|u_karenciji\|HealthRecord" /var/www/fina-connect/livestock/models.py | head -20
grep -n "def process_payment\|_deduct_inventory\|_attempt_fiscal" /var/www/fina-connect/pos/services.py | head -15
grep -n "^class InventoryItem\|is_active\|quantity\|min_quantity" /var/www/fina-connect/inventory/models.py | head -20
cat /var/www/fina-connect/static/js/worktime-offline.js       # pattern za offline
grep -n "def quick\|def analyze\|BarcodeDetector\|camera" /var/www/fina-connect/static/js/fenix-camera.js | head -20
```

## Kontekst — zašto ovaj task postoji

Tri "nagazne mine" koje ruše Livestock u produkciji:
1. Karenca goveda nije povezana s POS-om → mlijeko u karenciji može završiti na blagajni
2. Štale nemaju WiFi → farmer ne može unositi offline
3. Ušne markice se ne mogu skenirati → tipkanje 14 znamenki s prljavim rukama

Sve tri mine imamo alat da ih riješimo — samo trebamo spojiti što postoji.

---

## DIO A — Karenca → POS blokada (PRIORITET 1)

### A1: Provjeri stvarna polja InventoryItem PRIJE pisanja
```bash
grep -n "^    [a-z_]* = models\." /var/www/fina-connect/inventory/models.py | head -40
```
Traži postoji li `is_blocked`, `blocked_until`, `blocked_reason`. Ako ne postoji — dodaj.

### A2: Dodaj polja na InventoryItem
```python
# inventory/models.py — dodaj u klasu InventoryItem:

is_blocked = models.BooleanField(
    default=False,
    verbose_name='Blokiran za prodaju',
    help_text='Automatski postavlja Livestock modul za karenciju mlijeka/mesa'
)
blocked_until = models.DateField(
    null=True, blank=True,
    verbose_name='Blokiran do datuma',
)
blocked_reason = models.CharField(
    max_length=200, blank=True,
    verbose_name='Razlog blokade',
    help_text='npr. Karencija — antibiotik, do 2026-04-15'
)
```

### A3: Signal u livestock/models.py — automatska blokada

```python
# Na kraju livestock/models.py, NAKON klase HealthRecord:

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=HealthRecord)
def sync_karencija_with_inventory(sender, instance, created, **kwargs):
    """
    Kad se spremi HealthRecord s karencijom:
    - Pronađi InventoryItem 'mlijeko' firme (by name)
    - Postavi is_blocked=True, blocked_until, blocked_reason
    Kad karencija prođe (Celery task) — skine blokadu.
    """
    if not instance.karencija_do:
        return

    from django.utils import timezone
    today = timezone.now().date()

    try:
        from inventory.models import InventoryItem
        company = instance.animal.company

        # Pronađi mliječne i mesne artikle firme
        # Traži po kategoriji ili ključnoj riječi u nazivu
        milk_items = InventoryItem.objects.filter(
            company=company,
            is_active=True,
        ).filter(
            models.Q(name__icontains='mlijeko') |
            models.Q(name__icontains='milk') |
            models.Q(name__icontains='sir') |  # sir je od mlijeka u karenciji
            models.Q(category='dairy')
        )

        if instance.karencija_do >= today:
            # Blokada aktivna
            for item in milk_items:
                item.is_blocked = True
                item.blocked_until = instance.karencija_do
                item.blocked_reason = (
                    f'Karencija — {instance.lijek or "lijek"} '
                    f'(grlo {instance.animal.ear_tag}), '
                    f'do {instance.karencija_do}'
                )
                item.save(update_fields=['is_blocked', 'blocked_until', 'blocked_reason'])
        else:
            # Karencija prošla — provjeri ima li još aktivnih
            active_karencije = HealthRecord.objects.filter(
                animal__company=company,
                karencija_do__gte=today,
            ).exists()
            if not active_karencije:
                milk_items.update(
                    is_blocked=False,
                    blocked_until=None,
                    blocked_reason='',
                )
    except Exception as e:
        import logging
        logging.getLogger('livestock').error('karencija sync failed: %s', e)
```

### A4: POS blokada u CheckoutService

```python
# Pročitaj pos/services.py i pronađi gdje se dodaju stavke na račun.
# Traži: add_receipt_item() ili ekvivalent.
# Dodaj provjeru PRIJE nego se artikl doda:

# U pos/services.py, u funkciji add_receipt_item (ili process_payment):

def add_receipt_item(receipt, inventory_item, qty, price, ...):
    # NOVA PROVJERA — karencija blokada
    if getattr(inventory_item, 'is_blocked', False):
        from django.utils import timezone
        today = timezone.now().date()
        blocked_until = getattr(inventory_item, 'blocked_until', None)
        reason = getattr(inventory_item, 'blocked_reason', 'Karencija')

        if not blocked_until or blocked_until >= today:
            raise ValueError(
                f'BLOKADA: {inventory_item.name} nije za prodaju! '
                f'{reason}. '
                f'Dostupno od: {blocked_until or "nepoznato"}'
            )
        else:
            # Karencija prošla ali flag nije skinuti — skini automatski
            inventory_item.is_blocked = False
            inventory_item.save(update_fields=['is_blocked'])

    # ... nastavak originalne logike ...
```

### A5: Celery task — dnevna provjera karencija

```python
# Dodaj u livestock/tasks.py (kreiraj ako ne postoji):

from celery import shared_task
import logging
logger = logging.getLogger('livestock')

@shared_task(bind=True)
def lift_expired_karencije(self):
    """
    Pokreće se svako jutro u 06:00.
    Skida blokadu s InventoryItem kad je karencija prošla.
    Šalje notify Ivanu o promjenama.
    """
    from django.utils import timezone
    from livestock.models import HealthRecord
    from inventory.models import InventoryItem
    from core.notify import notify
    today = timezone.now().date()

    # Pronađi firme gdje su sve karencije završile
    lifted = 0
    still_blocked = 0

    blocked_items = InventoryItem.objects.filter(
        is_blocked=True,
        blocked_until__lt=today,
    ).select_related('company')

    for item in blocked_items:
        # Provjeri ima li još aktivnih karencija za tu firmu
        active = HealthRecord.objects.filter(
            animal__company=item.company,
            karencija_do__gte=today,
        ).exists()
        if not active:
            item.is_blocked = False
            item.blocked_until = None
            item.blocked_reason = ''
            item.save(update_fields=['is_blocked', 'blocked_until', 'blocked_reason'])
            lifted += 1
            notify('INFO', f'Karencija završila — {item.name} ({item.company.name}) ponovo dostupan za prodaju')
        else:
            still_blocked += 1

    logger.info('Karencije: %d skinuto, %d još aktivnih', lifted, still_blocked)
    return {'lifted': lifted, 'still_blocked': still_blocked}
```

```python
# U core/settings.py CELERY_BEAT_SCHEDULE dodaj:
'lift-expired-karencije': {
    'task': 'livestock.tasks.lift_expired_karencije',
    'schedule': crontab(hour=6, minute=0),
},
```

### A6: Migracije
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations inventory --name="add_blocked_fields"
venv/bin/python manage.py migrate inventory
venv/bin/python manage.py check
```

---

## DIO B — Livestock Offline PWA (PRIORITET 2)

### B1: Pročitaj worktime-offline.js kao template
```bash
cat /var/www/fina-connect/static/js/worktime-offline.js
```
Pattern: IndexedDB → queue → auto-sync on reconnect.
Kopiraj isti pattern za Livestock.

### B2: Kreiraj static/js/livestock-offline.js

```javascript
/**
 * livestock-offline.js — Offline unos za farmu.
 * IndexedDB čuva: teljenja, muzne zapise, zdravstvene događaje.
 * Auto-sync kad se veza vrati.
 *
 * API:
 *   LivestockOffline.saveMilkRecord(animalEarTag, jutarnja, vecernja)
 *   LivestockOffline.saveHealthEvent(animalEarTag, tip, opis, lijek, karencijaDo)
 *   LivestockOffline.saveCalving(motherEarTag, newEarTag, dateOfBirth)
 *   LivestockOffline.sync()
 *   LivestockOffline.getPendingCount()
 */
(function(window) {
  'use strict';

  var DB_NAME = 'livestock_offline';
  var DB_VERSION = 1;
  var STORE_MILK = 'milk_records';
  var STORE_HEALTH = 'health_events';
  var STORE_CALVING = 'calvings';

  var db = null;

  function openDB(callback) {
    if (db) { callback(db); return; }
    var req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = function(e) {
      var d = e.target.result;
      if (!d.objectStoreNames.contains(STORE_MILK)) {
        var ms = d.createObjectStore(STORE_MILK, { keyPath: 'id', autoIncrement: true });
        ms.createIndex('synced', 'synced', { unique: false });
        ms.createIndex('ear_tag', 'ear_tag', { unique: false });
      }
      if (!d.objectStoreNames.contains(STORE_HEALTH)) {
        var hs = d.createObjectStore(STORE_HEALTH, { keyPath: 'id', autoIncrement: true });
        hs.createIndex('synced', 'synced', { unique: false });
      }
      if (!d.objectStoreNames.contains(STORE_CALVING)) {
        var cs = d.createObjectStore(STORE_CALVING, { keyPath: 'id', autoIncrement: true });
        cs.createIndex('synced', 'synced', { unique: false });
      }
    };
    req.onsuccess = function(e) { db = e.target.result; callback(db); };
    req.onerror = function() { console.error('LivestockOffline: DB error'); };
  }

  function saveToStore(storeName, data, callback) {
    openDB(function(d) {
      var tx = d.transaction(storeName, 'readwrite');
      var store = tx.objectStore(storeName);
      data.synced = 0;
      data.created_at = new Date().toISOString();
      var req = store.add(data);
      req.onsuccess = function() {
        if (callback) callback(null, req.result);
        if (window.showPosToast) showPosToast('Spremljeno offline — sync na mreži', 'info');
      };
      req.onerror = function() { if (callback) callback('Greška pri spremanju'); };
    });
  }

  function syncStore(storeName, endpoint, callback) {
    openDB(function(d) {
      var tx = d.transaction(storeName, 'readwrite');
      var store = tx.objectStore(storeName);
      var index = store.index('synced');
      var unsynced = [];
      index.openCursor(IDBKeyRange.only(0)).onsuccess = function(e) {
        var cursor = e.target.result;
        if (cursor) { unsynced.push(cursor.value); cursor.continue(); }
        else {
          if (!unsynced.length) { if (callback) callback(0); return; }
          var sent = 0;
          unsynced.forEach(function(record) {
            fetch(endpoint, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.CSRF_TOKEN || ''
              },
              body: JSON.stringify(record)
            })
            .then(function(r) { return r.json(); })
            .then(function(resp) {
              if (resp.ok || resp.id) {
                var tx2 = d.transaction(storeName, 'readwrite');
                tx2.objectStore(storeName).delete(record.id);
                sent++;
                if (sent === unsynced.length && callback) callback(sent);
              }
            })
            .catch(function(err) { console.warn('Sync failed:', err); });
          });
        }
      };
    });
  }

  window.LivestockOffline = {
    saveMilkRecord: function(earTag, jutarnja, vecernja, notes) {
      saveToStore(STORE_MILK, {
        ear_tag: earTag,
        datum: new Date().toISOString().split('T')[0],
        jutarnja_l: parseFloat(jutarnja) || 0,
        vecernja_l: parseFloat(vecernja) || 0,
        notes: notes || '',
      });
    },
    saveHealthEvent: function(earTag, tip, opis, lijek, karencijaDo) {
      saveToStore(STORE_HEALTH, {
        ear_tag: earTag,
        datum: new Date().toISOString().split('T')[0],
        tip: tip,
        opis: opis,
        lijek: lijek || '',
        karencija_do: karencijaDo || null,
      });
    },
    saveCalving: function(motherEarTag, newEarTag, dateOfBirth) {
      saveToStore(STORE_CALVING, {
        mother_ear_tag: motherEarTag,
        new_ear_tag: newEarTag,
        date_of_birth: dateOfBirth || new Date().toISOString().split('T')[0],
      });
    },
    sync: function() {
      if (!navigator.onLine) return;
      syncStore(STORE_MILK,    '/livestock/api/milk-sync/',    function(n) { if (n) console.log('Milk synced:', n); });
      syncStore(STORE_HEALTH,  '/livestock/api/health-sync/',  function(n) { if (n) console.log('Health synced:', n); });
      syncStore(STORE_CALVING, '/livestock/api/calving-sync/', function(n) { if (n) console.log('Calving synced:', n); });
    },
    getPendingCount: function(callback) {
      var total = 0;
      var done = 0;
      [STORE_MILK, STORE_HEALTH, STORE_CALVING].forEach(function(store) {
        openDB(function(d) {
          var tx = d.transaction(store, 'readonly');
          tx.objectStore(store).index('synced').count(IDBKeyRange.only(0)).onsuccess = function(e) {
            total += e.target.result;
            done++;
            if (done === 3 && callback) callback(total);
          };
        });
      });
    }
  };

  // Auto-sync kad se mreža vrati
  window.addEventListener('online', function() {
    window.LivestockOffline.sync();
  });

})(window);
```

### B3: Sync API endpointi u livestock/views.py

```python
# Dodaj u livestock/views.py:

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

@login_required
@require_POST
def api_milk_sync(request):
    """Prima offline milk record i sprema u bazu."""
    from livestock.models import Livestock, MilkRecord
    from core.company_utils import get_user_company
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        animal = Livestock.objects.get(ear_tag=data['ear_tag'], company=company)
        record, created = MilkRecord.objects.get_or_create(
            animal=animal,
            datum=data['datum'],
            defaults={
                'jutarnja_l': data.get('jutarnja_l', 0),
                'večernja_l': data.get('vecernja_l', 0),
                'notes': data.get('notes', ''),
            }
        )
        return JsonResponse({'ok': True, 'id': record.pk, 'created': created})
    except Livestock.DoesNotExist:
        return JsonResponse({'error': 'Grlo nije pronađeno'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def api_health_sync(request):
    """Prima offline health event."""
    from livestock.models import Livestock, HealthRecord
    from core.company_utils import get_user_company
    import datetime
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        animal = Livestock.objects.get(ear_tag=data['ear_tag'], company=company)
        record = HealthRecord.objects.create(
            animal=animal,
            datum=data['datum'],
            tip=data.get('tip', 'pregled'),
            opis=data.get('opis', ''),
            lijek=data.get('lijek', ''),
            karencija_do=data.get('karencija_do') or None,
            created_by=request.user,
        )
        return JsonResponse({'ok': True, 'id': record.pk})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def api_calving_sync(request):
    """Prima offline teljenje — kreira novo tele."""
    from livestock.models import Livestock
    from core.company_utils import get_user_company
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
        mother = Livestock.objects.get(ear_tag=data['mother_ear_tag'], company=company)
        tele, created = Livestock.objects.get_or_create(
            company=company,
            ear_tag=data['new_ear_tag'],
            defaults={
                'vrsta': 'tele',
                'status': 'aktivno',
                'date_of_birth': data.get('date_of_birth'),
            }
        )
        # Ažuriraj majku
        mother.status = 'aktivno'
        mother.last_calving = data.get('date_of_birth')
        mother.expected_calving = None
        mother.save(update_fields=['status', 'last_calving', 'expected_calving'])
        return JsonResponse({'ok': True, 'tele_id': tele.pk, 'created': created})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
```

### B4: Dodaj URLove u livestock/urls.py
```python
path('api/milk-sync/', views.api_milk_sync, name='api_milk_sync'),
path('api/health-sync/', views.api_health_sync, name='api_health_sync'),
path('api/calving-sync/', views.api_calving_sync, name='api_calving_sync'),
```

### B5: Dodaj livestock-offline.js u SW cache i base template
```bash
# Provjeri koji template includea worktime-offline.js
grep -rn "worktime-offline\|fenix-camera" /var/www/fina-connect/templates/ | grep -v __pycache__ | head -10
```
Dodaj `livestock-offline.js` na isto mjesto.

---

## DIO C — FenixCamera barcode skeniranje ušnih markica (PRIORITET 3)

### C1: Provjeri BarcodeDetector podršku u fenix-camera.js
```bash
grep -n "BarcodeDetector\|barcode\|scan\|detect" /var/www/fina-connect/static/js/fenix-camera.js
```

### C2: Dodaj barcode scan metodu u fenix-camera.js

```javascript
// Dodaj u FenixCamera objekt (nakon postojećih metoda):

scanEarTag: function(callback) {
  /**
   * Skeniraj ušnu markicu goveda s kamerom.
   * Podržava: Code128, Code39, EAN13 (tipični barkodovi na ušnim markicama)
   * Fallback: manual unos ako BarcodeDetector nije dostupan
   *
   * Primjer:
   *   FenixCamera.scanEarTag(function(earTag) {
   *     document.getElementById('ear_tag').value = earTag;
   *   });
   */
  var self = this;

  if (!('BarcodeDetector' in window)) {
    // Fallback — prompt za ručni unos
    var tag = prompt('BarcodeDetector nije podržan u ovom browseru.\nRučno unesite broj ušne markice:');
    if (tag && callback) callback(tag.trim());
    return;
  }

  var detector = new BarcodeDetector({
    formats: ['code_128', 'code_39', 'ean_13', 'ean_8', 'data_matrix']
  });

  // Otvori kameru
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
  .then(function(stream) {
    var video = document.createElement('video');
    video.srcObject = stream;
    video.setAttribute('playsinline', true);
    video.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;object-fit:cover;background:#000';

    var overlay = document.createElement('div');
    overlay.innerHTML = '<div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);border:2px solid #0f0;width:60%;height:30%;z-index:10000;border-radius:8px;pointer-events:none"></div><button style="position:fixed;top:20px;right:20px;z-index:10001;background:#e00;color:#fff;border:none;padding:12px 20px;border-radius:8px;font-size:16px">Odustani</button>';
    overlay.querySelector('button').onclick = function() {
      stream.getTracks().forEach(function(t) { t.stop(); });
      document.body.removeChild(video);
      document.body.removeChild(overlay);
    };

    document.body.appendChild(video);
    document.body.appendChild(overlay);
    video.play();

    var scanning = true;
    function scan() {
      if (!scanning) return;
      detector.detect(video).then(function(codes) {
        if (codes.length > 0) {
          scanning = false;
          var raw = codes[0].rawValue;
          stream.getTracks().forEach(function(t) { t.stop(); });
          document.body.removeChild(video);
          document.body.removeChild(overlay);
          if (callback) callback(raw);
        } else {
          requestAnimationFrame(scan);
        }
      }).catch(function() { requestAnimationFrame(scan); });
    }
    video.addEventListener('playing', scan);
  })
  .catch(function(err) {
    console.warn('Kamera nije dostupna:', err);
    var tag = prompt('Unesite broj ušne markice:');
    if (tag && callback) callback(tag.trim());
  });
}
```

### C3: Koristi u livestock formama

```javascript
// U livestock animal form templateu:
// <button type="button" onclick="FenixCamera.scanEarTag(function(t){ document.getElementById('id_ear_tag').value = t; })">
//   📷 Skeniraj markicu
// </button>
```

---

## DIO D — JRDŽ osnova (zakonska obveza, V3 temelj)

### D1: Model za praćenje prijava

```python
# Dodaj u livestock/models.py:

class JRDZRegistration(models.Model):
    """
    Evidencija prijava u JRDŽ (HR) ili HI-Tier (DE).
    Pravni rok: 7 dana za telenje/uginuće, 3 dana za premještanje.
    """
    TIP_CHOICES = [
        ('teljenje', 'Teljenje (novo grlo)'),
        ('uginuce', 'Uginuće'),
        ('premjestaj', 'Premještaj'),
        ('klanje', 'Klanje'),
        ('uvoz', 'Uvoz'),
        ('izvoz', 'Izvoz'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Čeka prijavu'),
        ('submitted', 'Prijavljeno'),
        ('confirmed', 'Potvrđeno od JRDŽ'),
        ('overdue', 'Prekoračen rok!'),
        ('error', 'Greška pri prijavi'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='jrdz_registrations')
    animal = models.ForeignKey(Livestock, on_delete=models.CASCADE,
                                related_name='jrdz_records')
    tip = models.CharField(max_length=15, choices=TIP_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    datum_dogadjaja = models.DateField(verbose_name='Datum događaja')
    rok_prijave = models.DateField(verbose_name='Zakonski rok prijave',
                                    help_text='7 dana od događaja (HR)')
    datum_prijave = models.DateField(null=True, blank=True, verbose_name='Datum stvarne prijave')

    # Za export
    jrdz_referenca = models.CharField(max_length=50, blank=True,
                                       verbose_name='JRDŽ referenca/potvrda')
    napomena = models.TextField(blank=True)
    export_xml = models.TextField(blank=True, verbose_name='Generiran XML za upload')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'livestock_jrdz_registration'
        ordering = ['rok_prijave']
        verbose_name = 'JRDŽ prijava'
        verbose_name_plural = 'JRDŽ prijave'

    def __str__(self):
        return f'{self.animal.ear_tag} — {self.get_tip_display()} ({self.datum_dogadjaja})'

    @property
    def prekoraceno(self):
        from django.utils import timezone
        if self.status == 'submitted':
            return False
        return timezone.now().date() > self.rok_prijave

    @property
    def preostalo_dana(self):
        from django.utils import timezone
        return (self.rok_prijave - timezone.now().date()).days
```

### D2: Auto-kreira JRDZRegistration pri teljenju

```python
# U api_calving_sync (views.py), nakon kreiranja teleta:
from livestock.models import JRDZRegistration
import datetime

JRDZRegistration.objects.create(
    company=company,
    animal=tele,
    tip='teljenje',
    datum_dogadjaja=datetime.date.fromisoformat(data.get('date_of_birth', str(datetime.date.today()))),
    rok_prijave=datetime.date.fromisoformat(data.get('date_of_birth', str(datetime.date.today()))) + datetime.timedelta(days=7),
)
```

### D3: Celery upozorenje za JRDŽ rokove

```python
# U livestock/tasks.py dodaj:

@shared_task(bind=True)
def check_jrdz_deadlines(self):
    """Svako jutro u 07:00 — upozori za JRDŽ prijave koje uskoro ističu."""
    from django.utils import timezone
    from livestock.models import JRDZRegistration
    from core.whatsapp import send_text
    from accounts.models import UserProfile

    today = timezone.now().date()
    uskoro = JRDZRegistration.objects.filter(
        status='pending',
        rok_prijave__lte=today + timezone.timedelta(days=3),
    ).select_related('animal', 'company')

    prekoraceno = JRDZRegistration.objects.filter(
        status='pending',
        rok_prijave__lt=today,
    ).update(status='overdue')

    for reg in uskoro:
        admin = UserProfile.objects.filter(
            company=reg.company, role='company_admin'
        ).first()
        if admin:
            phone = getattr(admin.user, 'phone', '') or ''
            if phone:
                days = reg.preostalo_dana
                urgency = '🚨' if days <= 1 else '⚠️'
                send_text(phone,
                    f'{urgency} JRDŽ rok! '
                    f'Grlo {reg.animal.ear_tag} ({reg.get_tip_display()}) — '
                    f'rok prijave: {reg.rok_prijave} '
                    f'({days} dana)'
                )

    return {'upozorenja': uskoro.count(), 'prekoraceno': prekoraceno}
```

```python
# U core/settings.py CELERY_BEAT_SCHEDULE dodaj:
'check-jrdz-deadlines': {
    'task': 'livestock.tasks.check_jrdz_deadlines',
    'schedule': crontab(hour=7, minute=0),
},
```

---

## Finalne migracije i provjera

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations inventory --name="add_blocked_fields"
venv/bin/python manage.py makemigrations livestock --name="add_jrdz_model"
venv/bin/python manage.py migrate
venv/bin/python manage.py check

# Test karencija signal
venv/bin/python manage.py shell -c "
from livestock.models import Livestock, HealthRecord
from companies.models import Company
import datetime
company = Company.objects.get(name__icontains='Kruljac')
krava = Livestock.objects.filter(company=company, vrsta='krava').first()
print('Test krava:', krava)
if krava:
    hr = HealthRecord.objects.create(
        animal=krava, datum=datetime.date.today(),
        tip='tretman', opis='Test karencija',
        lijek='Amoksicilin', karencija_do=datetime.date.today() + datetime.timedelta(days=7),
    )
    print('HealthRecord kreiran, provjeravamo blokadu...')
    from inventory.models import InventoryItem
    blocked = InventoryItem.objects.filter(company=company, is_blocked=True)
    print('Blokirani artikli:', blocked.count())
    for b in blocked:
        print(f'  {b.name} — blokiran do {b.blocked_until}: {b.blocked_reason}')
" 2>&1 | grep -v Warning | grep -v Deprecat

systemctl restart celery-worker
```

---

## Ažuriraj FENIX_STATUS.md

```
### Livestock V3 (NOVO)
- Karenca → POS blokada (InventoryItem.is_blocked + signal + Celery) — DONE
- livestock-offline.js (IndexedDB: muža, zdravlje, teljenje) — DONE
- Sync API endpointi (/api/milk-sync/, /health-sync/, /calving-sync/) — DONE
- FenixCamera.scanEarTag() — BarcodeDetector + fallback — DONE
- JRDZRegistration model + auto-kreacija pri teljenju — DONE
- check_jrdz_deadlines Celery task (07:00) — DONE
```

## Definicija DONE
- [ ] InventoryItem.is_blocked polje i migracija
- [ ] post_save signal — HealthRecord → blokira mliječne artikle
- [ ] add_receipt_item provjera blokade (ValueError ako is_blocked)
- [ ] lift_expired_karencije Celery task
- [ ] livestock-offline.js (IndexedDB, 3 store-a, auto-sync)
- [ ] 3 sync API endpointa (milk, health, calving)
- [ ] FenixCamera.scanEarTag() metoda
- [ ] JRDZRegistration model + Celery upozorenje
- [ ] Test: HealthRecord → is_blocked=True na mliječnom artiklu
- [ ] django check: 0 grešaka
- [ ] /tmp/livestock_v3_done.txt
