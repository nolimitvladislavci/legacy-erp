# CC_TASK_POS_UNIFIED_FENIX.md
# Za: CC Code
# Datum: 2026-03-31
# Rok: 07.04.2026.
# Prioritet: P0 — prezentacija Mariji, produkcija
# Procjena: 3-4 dana
#
# CILJ: Jedan POS (Joker) koji:
#   1. Ima ikone za sve module (navigacija bez napuštanja POS-a)
#   2. Pri pokretanju traži prijavu blagajnika (OIB obavezan)
#   3. Provjerava poslovni prostor — ako nema, nudi formu
#   4. AI sukladnost u pozadini — provjera zakonskih propisa s gumbima za rješavanje
#   5. AI asistent spreman odmah pri otvaranju smjene
#
# ŠTO POSTOJI:
#   - templates/pos/joker.html — master template (sve sprint značajke tu)
#   - pos/models.py: POSCashier (oib, pin_hash), POSTerminal (business_location)
#   - pos/views.py: cashier_pin_verify, pos_joker
#   - eracun/models.py: ERacunConfig (oznaka_prostora, oznaka_uredjaja)
#   - pos/services/checkout.py: HR fiskalizacija, AI barcode
#   - static/js/pos/pos-voice.js: glasovni unos
#
# ZAKONSKI PROPISI KOJE AI PROVJERAVA:
#   HR Zakon o fiskalizaciji (NN 133/12):
#     - Čl. 9: OIB operatera obavezan na svakom bonu
#     - Čl. 14: Fiskalizacija unutar 48h (offline bon)
#     - Čl. 17: JIR na bonu obavezan
#     - Čl. 10: Oznaka poslovnog prostora obavezna
#   Zakon o PDV-u:
#     - Svaki bon mora imati razradu PDV-a
#   Zakon o blagajničkom poslovanju:
#     - Gotovinski maksimum 10.000 kn (1.327 EUR) dnevno u blagajni
#   Zakon o radu:
#     - Max smjena: 8h (redovni rad), iznimno 10h
#     - Obvezni odmor 30 min pri radu > 6h

---

## ARHITEKTURA RJEŠENJA

```
/hr/pos/joker/<terminal_id>/
        │
        ├── [NOVO] Ako nema session → CASHIER GATE screen
        │         OIB + PIN blagajnika + početna gotovina
        │         Provjera poslovnog prostora
        │         Ako nema oznake → mini-forma za upis
        │
        ├── [NOVO] Po otvaranju → AI COMPLIANCE SCAN (3 sekunde)
        │         Async background check
        │         Provjera: OIB, fiskalizacija, PDV, gotovina, smjena
        │         Banner s upozorenjem + gumbi za rješavanje
        │
        ├── [NOVO] Top navigation ikone za module
        │         Fakture, Arhiva, Partneri, Inventar, Izvještaji,
        │         Gastro, Knjiga boljitaka, Radni sati, Obavijesti
        │
        └── [POSTOJI] Naplata + AI glasovni unos (sprint 1-6)
```

---

## KORAK 1 — Cashier Gate Screen (modal pri pokretanju)

### 1a. Backend: novi endpoint `pos_start_session`

Dodati u `pos/views.py`:

```python
@login_required
def pos_start_session(request, terminal_id):
    """
    POST /pos/start/<terminal_id>/
    Otvara smjenu s blagajnikom i provjerom poslovnog prostora.
    Zamjenjuje stari open_session flow.
    """
    from decimal import Decimal
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    company, err = _check_tenant(request, terminal)
    if err: return JsonResponse({'error': str(err)}, status=403)

    if request.method == 'GET':
        # Vrati podatke potrebne za gate formu
        cashiers = list(POSCashier.objects.filter(
            company=company, is_active=True
        ).values('id', 'name', 'oib', 'can_void', 'can_discount'))

        # Provjeri business location
        bl = terminal.business_location
        has_location = bool(bl and getattr(bl, 'oznaka_prostora', None))

        # Provjeri postoji li otvorena smjena
        existing = POSSession.objects.filter(
            terminal=terminal, status='open'
        ).first()

        return JsonResponse({
            'cashiers': cashiers,
            'has_location': has_location,
            'location_label': bl.oznaka_prostora if bl else '',
            'terminal_name': terminal.name if hasattr(terminal, 'name') else f'Terminal {terminal.id}',
            'existing_session': existing.id if existing else None,
        })

    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        cashier_id = data.get('cashier_id')
        pin = data.get('pin', '')
        opening_cash = Decimal(str(data.get('opening_cash', '0') or '0'))
        oib_manual = data.get('oib_manual', '').strip()
        oznaka_prostora = data.get('oznaka_prostora', '').strip()
        oznaka_uredjaja = data.get('oznaka_uredjaja', '1').strip()

        # Validacija blagajnika
        if cashier_id:
            try:
                cashier = POSCashier.objects.get(id=cashier_id, company=company, is_active=True)
                if not cashier.check_pin(pin):
                    return JsonResponse({'error': 'Pogrešan PIN.'}, status=400)
                if not cashier.oib:
                    if not oib_manual:
                        return JsonResponse({
                            'error': 'OIB blagajnika je obavezan (čl. 9. Zakona o fiskalizaciji).',
                            'need_oib': True,
                        }, status=400)
                    # Spremi OIB
                    cashier.oib = oib_manual
                    cashier.save(update_fields=['oib'])
            except POSCashier.DoesNotExist:
                return JsonResponse({'error': 'Blagajnik nije pronađen.'}, status=400)
        else:
            cashier = None

        # Validacija poslovnog prostora
        bl = terminal.business_location
        if not bl or not getattr(bl, 'oznaka_prostora', None):
            if not oznaka_prostora:
                return JsonResponse({
                    'error': 'Oznaka poslovnog prostora je obavezna (čl. 10. Zakona o fiskalizaciji).',
                    'need_location': True,
                }, status=400)
            # Postavi oznaku ako je upisana
            if bl:
                bl.oznaka_prostora = oznaka_prostora
                bl.oznaka_uredjaja = oznaka_uredjaja or '1'
                bl.save(update_fields=['oznaka_prostora', 'oznaka_uredjaja'])
            else:
                # Kreiraj BusinessLocation inline
                from invoicing.models import BusinessLocation
                bl_new = BusinessLocation.objects.create(
                    company=company,
                    name=oznaka_prostora,
                    oznaka_prostora=oznaka_prostora,
                    oznaka_uredjaja=oznaka_uredjaja or '1',
                )
                terminal.business_location = bl_new
                terminal.save(update_fields=['business_location'])

        # Provjeri postoji li otvorena smjena
        existing = POSSession.objects.filter(terminal=terminal, status='open').first()
        if existing:
            return JsonResponse({'ok': True, 'session_id': existing.id, 'existing': True})

        # Otvori smjenu
        last = terminal.sessions.order_by('-session_number').first()
        next_num = (last.session_number + 1) if last else 1
        session = POSSession.objects.create(
            terminal=terminal,
            operator=request.user,
            session_number=next_num,
            opening_cash=opening_cash,
            status='open',
        )

        # Clock-in blagajnika
        if cashier:
            from django.utils import timezone
            cashier.clock_in_at = timezone.now()
            cashier.save(update_fields=['clock_in_at'])
            session.notes = f'Blagajnik: {cashier.name} (OIB: {cashier.oib})'
            session.save(update_fields=['notes'])

        return JsonResponse({
            'ok': True,
            'session_id': session.id,
            'cashier_name': cashier.name if cashier else '',
            'opening_cash': float(opening_cash),
        })
```

Dodati u `pos/urls.py`:
```python
path('start/<int:terminal_id>/', views.pos_start_session, name='pos_start_session'),
```

---

### 1b. Frontend: Cashier Gate modal u joker.html

Dodati odmah nakon `<body>` otvaranja, PRIJE svega:

```html
<!-- ══════════════════════════════════════════════════════
     CASHIER GATE — Prijava blagajnika pri otvaranju
     ════════════════════════════════════════════════════ -->
<div id="cashier-gate" style="
  display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);
  z-index:9999;display:flex;align-items:center;justify-content:center;
  font-family:'Space Grotesk',system-ui,sans-serif;">
  
  <div style="background:#111827;border:1px solid rgba(201,168,76,.3);border-radius:20px;
    padding:32px;width:min(420px,95vw);box-shadow:0 0 60px rgba(201,168,76,.1)">
    
    <!-- Logo + naziv -->
    <div style="text-align:center;margin-bottom:24px">
      <div style="font-size:2rem;margin-bottom:4px">🏛️</div>
      <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9" id="gate-terminal-name">LIMIT Connect POS</div>
      <div style="font-size:.78rem;color:#64748b;margin-top:2px" id="gate-location-info">Poslovni prostor</div>
    </div>

    <!-- Korak 1: Odabir blagajnika -->
    <div id="gate-step-cashier">
      <div style="font-size:.8rem;color:#94a3b8;margin-bottom:10px;font-weight:600;
        text-transform:uppercase;letter-spacing:.06em">Odaberi blagajnika</div>
      <div id="gate-cashiers-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px">
        <!-- Dinamički punjeno -->
      </div>
      <a href="/hr/pos/settings/#cashiers" id="gate-add-cashier-link"
        style="display:none;font-size:.75rem;color:#c9a84c;text-align:center;
        display:block;padding:8px;border:1px dashed rgba(201,168,76,.3);border-radius:8px;
        text-decoration:none;margin-bottom:16px">
        + Dodaj blagajnika
      </a>
    </div>

    <!-- Korak 2: PIN unos -->
    <div id="gate-step-pin" style="display:none">
      <div style="text-align:center;margin-bottom:12px">
        <div style="font-size:.85rem;color:#94a3b8">Unesi PIN za</div>
        <div id="gate-selected-cashier-name" style="font-size:1.1rem;font-weight:700;color:#c9a84c"></div>
      </div>
      
      <!-- OIB warning ako nema -->
      <div id="gate-oib-warning" style="display:none;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);
        border-radius:10px;padding:12px;margin-bottom:12px;font-size:.78rem;color:#fca5a5">
        ⚠️ OIB blagajnika nije upisan — obavezan po čl. 9. Zakona o fiskalizaciji.<br>
        <input id="gate-oib-input" type="text" maxlength="11" placeholder="Unesite OIB (11 znamenki)"
          style="width:100%;margin-top:8px;padding:8px;border-radius:8px;border:1px solid rgba(239,68,68,.4);
          background:rgba(0,0,0,.3);color:#f1f5f9;font-size:.9rem;text-align:center;letter-spacing:.1em">
      </div>

      <!-- PIN numpad -->
      <div id="gate-pin-display" style="text-align:center;font-size:1.8rem;
        letter-spacing:.5rem;color:#c9a84c;margin-bottom:16px;min-height:2.5rem">
        &bull;&bull;&bull;&bull;
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-width:240px;margin:0 auto 16px">
        {% for d in "123456789" %}
        <button class="gate-pin-btn" data-d="{{ d }}" style="padding:14px;border-radius:10px;
          background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
          color:#f1f5f9;font-size:1.2rem;font-weight:600;cursor:pointer">{{ d }}</button>
        {% endfor %}
        <button class="gate-pin-btn gate-pin-clear" style="padding:14px;border-radius:10px;
          background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);
          color:#f87171;font-size:.8rem;cursor:pointer">⌫</button>
        <button class="gate-pin-btn" data-d="0" style="padding:14px;border-radius:10px;
          background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
          color:#f1f5f9;font-size:1.2rem;font-weight:600;cursor:pointer">0</button>
        <button id="gate-pin-confirm" style="padding:14px;border-radius:10px;
          background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);
          color:#c9a84c;font-size:.8rem;cursor:pointer;font-weight:700">OK ✓</button>
      </div>
      <button id="gate-back-btn" style="width:100%;padding:8px;background:none;
        border:none;color:#64748b;font-size:.78rem;cursor:pointer">← Nazad</button>
    </div>

    <!-- Korak 3: Poslovni prostor (ako nema) -->
    <div id="gate-step-location" style="display:none">
      <div style="background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);
        border-radius:10px;padding:14px;margin-bottom:16px">
        <div style="font-size:.8rem;font-weight:700;color:#fbbf24;margin-bottom:6px">
          ⚠️ Poslovni prostor nije postavljen
        </div>
        <div style="font-size:.75rem;color:#d97706">
          Zakon o fiskalizaciji čl. 10 zahtijeva oznaku poslovnog prostora na svakom bonu.
        </div>
      </div>
      <div style="margin-bottom:12px">
        <label style="font-size:.75rem;color:#94a3b8;display:block;margin-bottom:4px">
          Oznaka poslovnog prostora *
        </label>
        <input id="gate-location-input" type="text" placeholder="P1"
          style="width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,.15);
          background:rgba(255,255,255,.05);color:#f1f5f9;font-size:1rem;box-sizing:border-box">
        <div style="font-size:.65rem;color:#64748b;margin-top:4px">
          Npr: P1, PRODAVAONICA1 (registrirano kod Porezne uprave)
        </div>
      </div>
      <div style="margin-bottom:16px">
        <label style="font-size:.75rem;color:#94a3b8;display:block;margin-bottom:4px">
          Oznaka naplatnog uređaja
        </label>
        <input id="gate-device-input" type="text" placeholder="1" value="1"
          style="width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,.15);
          background:rgba(255,255,255,.05);color:#f1f5f9;font-size:1rem;box-sizing:border-box">
      </div>
      <!-- AI asistent hint -->
      <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);
        border-radius:8px;padding:10px;margin-bottom:16px;font-size:.73rem;color:#93c5fd;
        display:flex;align-items:flex-start;gap:8px">
        🤖 <span>AI asistent može pomoći s registracijom poslovnog prostora. Nakon što upišete oznaku, 
        provjerimo automatski odgovara li formatu Porezne uprave.</span>
      </div>
    </div>

    <!-- Korak 4: Početna gotovina -->
    <div id="gate-step-cash" style="display:none">
      <div style="font-size:.8rem;color:#94a3b8;margin-bottom:8px;font-weight:600;
        text-transform:uppercase;letter-spacing:.06em">Početno stanje blagajne</div>
      <div style="position:relative;margin-bottom:8px">
        <input id="gate-cash-input" type="number" step="0.01" min="0" placeholder="0.00"
          style="width:100%;padding:12px 40px 12px 12px;border-radius:10px;
          border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.05);
          color:#f1f5f9;font-size:1.4rem;text-align:right;box-sizing:border-box">
        <span style="position:absolute;right:12px;top:50%;transform:translateY(-50%);
          color:#64748b;font-size:1rem">EUR</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:16px">
        {% for amt in "20 50 100 200 500" %}
        <button class="gate-cash-preset" data-amount="{{ amt }}" style="padding:8px 4px;
          border-radius:8px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
          color:#94a3b8;font-size:.78rem;cursor:pointer">{{ amt }} €</button>
        {% endfor %}
      </div>
    </div>

    <!-- Error poruka -->
    <div id="gate-error" style="display:none;background:rgba(239,68,68,.1);
      border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:10px;
      font-size:.78rem;color:#fca5a5;margin-bottom:12px;text-align:center"></div>

    <!-- CTA gumb -->
    <button id="gate-submit-btn" style="display:none;width:100%;padding:14px;
      border-radius:12px;background:linear-gradient(135deg,#c9a84c,#a07830);
      border:none;color:#0a0a0c;font-size:1rem;font-weight:700;cursor:pointer;
      transition:opacity .2s">
      🔓 Otvori smjenu
    </button>

  </div>
</div>
```

### 1c. JavaScript za Cashier Gate

Dodati u `<script>` sekciju joker.html, PRVI script blok:

```javascript
/* ══════════════════════════════════════════
   CASHIER GATE — Init & Logic
   ══════════════════════════════════════════ */
(function(){
  const TERMINAL_ID = {{ terminal.id }};
  const HAS_SESSION = {{ session.id | default:"null" }};
  
  let selectedCashier = null;
  let enteredPin = '';
  let gateData = {};

  // Inicijaliziraj gate
  async function initGate() {
    // Ako već ima otvorena smjena, ne prikazuj gate
    if (HAS_SESSION) {
      runComplianceCheck(); // Provjeri sukladnost u pozadini
      return;
    }
    
    // Prikaži gate
    document.getElementById('cashier-gate').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    // Dohvati podatke
    try {
      const r = await fetch(`/hr/pos/start/${TERMINAL_ID}/`);
      gateData = await r.json();
      
      // Popuni naziv terminala
      document.getElementById('gate-terminal-name').textContent = 
        gateData.terminal_name || 'POS Terminal';
      document.getElementById('gate-location-info').textContent = 
        gateData.location_label ? `Poslovni prostor: ${gateData.location_label}` : 
        '⚠️ Poslovni prostor nije postavljen';
      
      // Ako postoji otvorena smjena
      if (gateData.existing_session) {
        closeGate();
        runComplianceCheck();
        return;
      }
      
      // Popuni blagajnike
      renderCashiers(gateData.cashiers || []);
      
    } catch(e) {
      showError('Greška pri učitavanju podataka: ' + e.message);
    }
  }

  function renderCashiers(cashiers) {
    const grid = document.getElementById('gate-cashiers-grid');
    if (!cashiers.length) {
      grid.innerHTML = '';
      document.getElementById('gate-add-cashier-link').style.display = 'block';
      document.getElementById('gate-step-pin').style.display = 'none';
      showError('Nema blagajnika. Dodajte blagajnika u postavkama.');
      return;
    }
    grid.innerHTML = cashiers.map(c => `
      <button class="gate-cashier-item" data-id="${c.id}" data-name="${c.name}" 
        data-oib="${c.oib}" onclick="selectCashier(${c.id},'${c.name}','${c.oib}')"
        style="padding:14px 10px;border-radius:12px;background:rgba(255,255,255,.05);
        border:1px solid rgba(255,255,255,.1);color:#f1f5f9;font-size:.85rem;
        font-weight:600;cursor:pointer;text-align:center;transition:all .15s">
        <div style="font-size:1.4rem;margin-bottom:4px">👤</div>
        <div>${c.name}</div>
        ${!c.oib ? '<div style="font-size:.65rem;color:#f87171;margin-top:2px">bez OIB-a</div>' : ''}
      </button>
    `).join('');
  }

  window.selectCashier = function(id, name, oib) {
    selectedCashier = {id, name, oib};
    enteredPin = '';
    
    document.getElementById('gate-step-cashier').style.display = 'none';
    document.getElementById('gate-step-pin').style.display = 'block';
    document.getElementById('gate-selected-cashier-name').textContent = name;
    updatePinDisplay();
    
    // Pokaži OIB warning ako nema
    if (!oib) {
      document.getElementById('gate-oib-warning').style.display = 'block';
    }
  };

  function updatePinDisplay() {
    const d = document.getElementById('gate-pin-display');
    d.textContent = '•'.repeat(enteredPin.length) || '····';
  }

  // PIN gumbi
  document.querySelectorAll('.gate-pin-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('gate-pin-clear')) {
        enteredPin = enteredPin.slice(0, -1);
      } else {
        const d = btn.dataset.d;
        if (d && enteredPin.length < 6) enteredPin += d;
      }
      updatePinDisplay();
    });
  });

  // PIN potvrda
  document.getElementById('gate-pin-confirm').addEventListener('click', async () => {
    if (!enteredPin) { showError('Unesite PIN.'); return; }
    
    // Provjeri je li potreban poslovni prostor
    if (!gateData.has_location) {
      showLocationStep();
      return;
    }
    
    showCashStep();
  });

  document.getElementById('gate-back-btn').addEventListener('click', () => {
    document.getElementById('gate-step-pin').style.display = 'none';
    document.getElementById('gate-step-cashier').style.display = 'block';
    selectedCashier = null;
    enteredPin = '';
  });

  function showLocationStep() {
    document.getElementById('gate-step-pin').style.display = 'none';
    document.getElementById('gate-step-location').style.display = 'block';
    document.getElementById('gate-submit-btn').style.display = 'block';
    document.getElementById('gate-submit-btn').textContent = 'Dalje →';
    document.getElementById('gate-submit-btn').onclick = () => {
      const loc = document.getElementById('gate-location-input').value.trim();
      if (!loc) { showError('Oznaka poslovnog prostora je obavezna.'); return; }
      document.getElementById('gate-step-location').style.display = 'none';
      showCashStep();
    };
    
    // AI asistencija za poslovni prostor
    setTimeout(() => aiAssistLocation(), 1000);
  }

  function showCashStep() {
    document.getElementById('gate-step-pin') && 
      (document.getElementById('gate-step-pin').style.display = 'none');
    document.getElementById('gate-step-location').style.display = 'none';
    document.getElementById('gate-step-cash').style.display = 'block';
    document.getElementById('gate-submit-btn').style.display = 'block';
    document.getElementById('gate-submit-btn').textContent = '🔓 Otvori smjenu';
    document.getElementById('gate-submit-btn').onclick = submitGate;
  }

  // Preset gumbi za gotovinu
  document.querySelectorAll('.gate-cash-preset').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('gate-cash-input').value = btn.dataset.amount;
    });
  });

  async function submitGate() {
    const btn = document.getElementById('gate-submit-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Otvara se...';
    
    const oibInput = document.getElementById('gate-oib-input');
    const locInput = document.getElementById('gate-location-input');
    const devInput = document.getElementById('gate-device-input');
    const cashInput = document.getElementById('gate-cash-input');

    try {
      const r = await fetch(`/hr/pos/start/${TERMINAL_ID}/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
        body: JSON.stringify({
          cashier_id: selectedCashier?.id,
          pin: enteredPin,
          oib_manual: oibInput ? oibInput.value : '',
          oznaka_prostora: locInput ? locInput.value : '',
          oznaka_uredjaja: devInput ? devInput.value : '1',
          opening_cash: cashInput ? parseFloat(cashInput.value || 0) : 0,
        }),
      });
      const data = await r.json();
      
      if (data.ok) {
        closeGate();
        // Refresh stranice da učita session
        window.location.reload();
      } else {
        if (data.need_oib) {
          document.getElementById('gate-oib-warning').style.display = 'block';
          document.getElementById('gate-oib-input').focus();
        }
        if (data.need_location) {
          showLocationStep();
        }
        showError(data.error || 'Greška pri otvaranju smjene.');
        btn.disabled = false;
        btn.textContent = '🔓 Otvori smjenu';
      }
    } catch(e) {
      showError('Greška: ' + e.message);
      btn.disabled = false;
      btn.textContent = '🔓 Otvori smjenu';
    }
  }

  function closeGate() {
    document.getElementById('cashier-gate').style.display = 'none';
    document.body.style.overflow = '';
  }

  function showError(msg) {
    const el = document.getElementById('gate-error');
    el.style.display = 'block';
    el.textContent = msg;
    setTimeout(() => el.style.display = 'none', 5000);
  }

  function getCsrf() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  }

  // AI asistencija za poslovni prostor
  async function aiAssistLocation() {
    const hint = document.querySelector('#gate-step-location [style*="93c5fd"]');
    if (!hint) return;
    hint.innerHTML = `🤖 Uobičajene oznake prostora: <strong>P1</strong> (prodavaonica 1), 
      <strong>T1</strong> (tržnica 1), <strong>M1</strong> (magacin 1). 
      Oznaka mora biti registrirana kod Porezne uprave na oibr ${window.COMPANY_OIB || 'tvrtke'}.`;
  }

  // Pokretanje
  document.addEventListener('DOMContentLoaded', initGate);

})(); // Cashier Gate
```

---

## KORAK 2 — Module Navigation Bar

### 2a. Gornja navigacijska traka s ikonama modula

Dodati u joker.html, direktno nakon `<header>` / top bara POS-a:

```html
<!-- ══ MODULE NAV BAR ════════════════════════════════════════════════ -->
<div id="pos-module-nav" style="
  background:rgba(0,0,0,.4);border-bottom:1px solid rgba(255,255,255,.06);
  padding:0 8px;display:flex;align-items:center;gap:2px;overflow-x:auto;
  scrollbar-width:none;flex-shrink:0;height:38px">
  
  {% load i18n %}
  <!-- Fakturiranje -->
  <a href="{% url 'invoicing:index' %}" title="Fakture" target="_blank" class="mod-nav-btn">
    <i class="fas fa-file-invoice-dollar"></i><span>Fakture</span>
  </a>
  <!-- Arhiva -->
  <a href="{% url 'documents:arhiva_list' %}" title="Arhiva dokumenti" target="_blank" class="mod-nav-btn">
    <i class="fas fa-archive"></i><span>Arhiva</span>
  </a>
  <!-- Partneri -->
  <a href="{% url 'partners:list' %}" title="Partneri / kupci" target="_blank" class="mod-nav-btn">
    <i class="fas fa-users"></i><span>Partneri</span>
  </a>
  <!-- Inventar -->
  <a href="{% url 'inventory:list' %}" title="Skladište" target="_blank" class="mod-nav-btn">
    <i class="fas fa-boxes"></i><span>Inventar</span>
  </a>
  <!-- Radni sati -->
  <a href="{% url 'worktime:dashboard' %}" title="Radni sati" target="_blank" class="mod-nav-btn">
    <i class="fas fa-clock"></i><span>Sati</span>
  </a>
  <!-- Izvještaji -->
  <a href="{% url 'pos:cashier_full_report' session.id %}" title="Izvještaj smjene" 
    class="mod-nav-btn" {% if not session %}style="opacity:.4;pointer-events:none"{% endif %}>
    <i class="fas fa-chart-bar"></i><span>Izvještaj</span>
  </a>
  <!-- Gastro (ako je terminal gastro) -->
  {% if is_gastro %}
  <a href="{% url 'pos:gastro_dashboard' %}" title="Gastro stolovi" class="mod-nav-btn mod-nav-active">
    <i class="fas fa-utensils"></i><span>Stolovi</span>
  </a>
  {% endif %}
  <!-- Knjiga boljitaka -->
  <a href="{% url 'pos:prigovori' %}" title="Knjiga boljitaka" target="_blank" class="mod-nav-btn">
    <i class="fas fa-book-open"></i><span>Boljitci</span>
  </a>
  <!-- Postavke -->
  <a href="{% url 'pos:pos_settings' %}" title="POS postavke" target="_blank" class="mod-nav-btn">
    <i class="fas fa-cog"></i><span>Postavke</span>
  </a>
  
  <!-- Compliance indikator (desno) -->
  <div style="margin-left:auto;flex-shrink:0">
    <div id="compliance-dot" title="Provjera sukladnosti" style="
      width:10px;height:10px;border-radius:50%;background:#22c55e;
      box-shadow:0 0 6px #22c55e;cursor:pointer" onclick="showCompliancePanel()">
    </div>
  </div>
</div>

<style>
.mod-nav-btn{
  display:inline-flex;align-items:center;gap:4px;padding:0 8px;height:38px;
  white-space:nowrap;color:#94a3b8;font-size:.7rem;text-decoration:none;
  border-radius:6px;transition:all .15s;flex-shrink:0
}
.mod-nav-btn:hover,.mod-nav-active{color:#c9a84c;background:rgba(201,168,76,.08)}
.mod-nav-btn i{font-size:.8rem}
.mod-nav-btn span{display:none}
@media(min-width:600px){.mod-nav-btn span{display:inline}}
</style>
```

---

## KORAK 3 — AI Compliance Monitor

### 3a. Backend: compliance check API

Dodati u `pos/views.py`:

```python
@login_required
def pos_compliance_check(request, terminal_id):
    """
    GET /pos/compliance/<terminal_id>/
    AI provjera zakonske sukladnosti POS terminala.
    Vraća listu upozorenja s gumbima za rješavanje.
    """
    from django.utils import timezone
    from decimal import Decimal
    
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    company = terminal.company
    session = POSSession.objects.filter(terminal=terminal, status='open').first()
    
    warnings = []  # Lista: {code, severity, title, message, actions[{label, url}]}
    
    # ── PROVJERA 1: Poslovni prostor ─────────────────────────────────────
    bl = terminal.business_location
    if not bl or not getattr(bl, 'oznaka_prostora', None):
        warnings.append({
            'code': 'NO_BUSINESS_LOCATION',
            'severity': 'critical',
            'title': 'Nema oznake poslovnog prostora',
            'message': 'Zakon o fiskalizaciji čl. 10 — svaki bon mora imati oznaku poslovnog prostora registriranu kod PU.',
            'actions': [
                {'label': '⚙️ Postavi sada', 'url': f'/hr/pos/settings/', 'style': 'gold'},
            ]
        })
    
    # ── PROVJERA 2: Blagajnici bez OIB-a ─────────────────────────────────
    cashiers_no_oib = POSCashier.objects.filter(
        company=company, is_active=True
    ).filter(oib='')
    if cashiers_no_oib.exists():
        names = ', '.join(c.name for c in cashiers_no_oib[:3])
        warnings.append({
            'code': 'CASHIER_NO_OIB',
            'severity': 'critical',
            'title': f'Blagajnik bez OIB-a: {names}',
            'message': 'Zakon o fiskalizaciji čl. 9 — OIB operatera je zakonski obavezan na svakom bonu.',
            'actions': [
                {'label': '⚙️ Uredi blagajnike', 'url': f'/hr/pos/settings/#cashiers', 'style': 'gold'},
            ]
        })
    
    # ── PROVJERA 3: Fiskalizacija neaktivna ──────────────────────────────
    try:
        settings = POSSettings.objects.get(company=company)
        if not settings.fiscal_active:
            warnings.append({
                'code': 'FISCAL_INACTIVE',
                'severity': 'critical',
                'title': 'Fiskalizacija nije aktivna',
                'message': 'Bez FINA certifikata svaki bon je fiskalno nevažeći. Kazna: 5.000–500.000 HRK.',
                'actions': [
                    {'label': '🔐 Postavi certifikat', 'url': '/hr/pos/settings/#fiscal', 'style': 'gold'},
                    {'label': '📖 Upute za fiskalizaciju', 'url': 'https://www.porezna-uprava.hr', 'style': 'ghost', 'external': True},
                ]
            })
    except POSSettings.DoesNotExist:
        warnings.append({
            'code': 'NO_POS_SETTINGS',
            'severity': 'warning',
            'title': 'POS postavke nisu konfigurirane',
            'message': 'Preporučujemo postavljanje fiskalnih podataka prije prve naplate.',
            'actions': [
                {'label': '⚙️ Otvori postavke', 'url': '/hr/pos/settings/', 'style': 'gold'},
            ]
        })
    
    # ── PROVJERA 4: Offline boni koji čekaju fiskalizaciju ────────────────
    if session:
        pending_fiscal = session.receipts.filter(
            status='paid',
            jir__isnull=True,
        ).exclude(jir='').count()
        if pending_fiscal > 0:
            from datetime import timedelta
            oldest_pending = session.receipts.filter(
                status='paid', jir__isnull=True
            ).order_by('paid_at').first()
            hours_pending = 0
            if oldest_pending and oldest_pending.paid_at:
                hours_pending = (timezone.now() - oldest_pending.paid_at).total_seconds() / 3600
            
            severity = 'critical' if hours_pending > 47 else 'warning'
            warnings.append({
                'code': 'PENDING_FISCAL',
                'severity': severity,
                'title': f'{pending_fiscal} bon(a) čeka fiskalizaciju',
                'message': (
                    f'Zakon o fiskalizaciji čl. 14 — offline bonovi moraju biti fiskalizirani unutar 48h. '
                    f'Najstariji čeka {hours_pending:.0f}h.'
                ),
                'actions': [
                    {'label': '🔄 Pokušaj sinkronizaciju', 'url': '#', 'style': 'gold', 
                     'onclick': 'retryFiscalization()'},
                ]
            })
    
    # ── PROVJERA 5: Duljina smjene ────────────────────────────────────────
    if session and session.opened_at:
        hours_open = (timezone.now() - session.opened_at).total_seconds() / 3600
        if hours_open > 10:
            warnings.append({
                'code': 'SHIFT_TOO_LONG',
                'severity': 'warning',
                'title': f'Smjena otvorena {hours_open:.0f}h',
                'message': 'Zakon o radu — redovna smjena max 8h, iznimno 10h. Zatvorite smjenu i napravite Z-izvješće.',
                'actions': [
                    {'label': '📊 Zatvori smjenu', 'url': f'/hr/pos/session/{session.id}/close/', 'style': 'gold'},
                ]
            })
    
    # ── PROVJERA 6: Gotovinski maksimum ─────────────────────────────────
    if session:
        try:
            from pos.models import POSPaymentLine
            cash_total = sum(
                r.total or 0 
                for r in session.receipts.filter(status='paid')
                if r.payment_method in ('CASH', 'gotovina', None)
            )
            # Blagajnički maksimum: zakon ne propisuje HR limit, ali preporučena praksa
            if cash_total > 5000:
                warnings.append({
                    'code': 'HIGH_CASH',
                    'severity': 'info',
                    'title': f'Visok gotovinski promet: {cash_total:.2f} EUR',
                    'message': 'Preporučujemo polisajzno polaganje viška gotovine radi sigurnosti i SOX/internih pravila.',
                    'actions': [
                        {'label': '💰 Zabilježi polaganje', 'url': f'/hr/pos/session/{session.id}/deposit/', 'style': 'ghost'},
                    ]
                })
        except Exception:
            pass
    
    # ── PROVJERA 7: Artikli s cijenama 0 ────────────────────────────────
    from inventory.models import InventoryItem
    zero_price = InventoryItem.objects.filter(
        company=company, is_active=True, price__lte=0
    ).count()
    if zero_price > 0:
        warnings.append({
            'code': 'ZERO_PRICE_ITEMS',
            'severity': 'info',
            'title': f'{zero_price} artikl(a) s cijenom 0,00 EUR',
            'message': 'Artikli s nultom cijenom mogu uzrokovati pogrešne blagajničke izvještaje.',
            'actions': [
                {'label': '📦 Uredi artikle', 'url': '/hr/inventory/', 'style': 'ghost'},
            ]
        })
    
    # Odredi ukupni status
    criticals = [w for w in warnings if w['severity'] == 'critical']
    status = 'critical' if criticals else ('warning' if warnings else 'ok')
    
    return JsonResponse({
        'status': status,
        'warnings': warnings,
        'checked_at': timezone.now().isoformat(),
    })
```

Dodati u `pos/urls.py`:
```python
path('compliance/<int:terminal_id>/', views.pos_compliance_check, name='pos_compliance_check'),
```

### 3b. Frontend: Compliance Panel u joker.html

```html
<!-- ══ COMPLIANCE PANEL ════════════════════════════════════════════ -->
<div id="compliance-panel" style="
  display:none;position:fixed;top:0;right:0;bottom:0;width:min(360px,100vw);
  background:#111827;border-left:1px solid rgba(255,255,255,.1);z-index:8888;
  overflow-y:auto;box-shadow:-20px 0 60px rgba(0,0,0,.5)">
  
  <div style="padding:20px;border-bottom:1px solid rgba(255,255,255,.08);
    display:flex;align-items:center;justify-content:space-between">
    <div>
      <div style="font-size:1rem;font-weight:700;color:#f1f5f9">🤖 AI Sukladnost</div>
      <div id="compliance-status-text" style="font-size:.72rem;color:#64748b"></div>
    </div>
    <button onclick="hideCompliancePanel()" style="background:none;border:none;
      color:#64748b;font-size:1.2rem;cursor:pointer">✕</button>
  </div>
  
  <div id="compliance-items" style="padding:16px;display:flex;flex-direction:column;gap:12px">
    <div style="text-align:center;padding:24px;color:#64748b;font-size:.85rem">
      ⏳ Provjera u tijeku...
    </div>
  </div>
  
  <div style="padding:16px;border-top:1px solid rgba(255,255,255,.08);font-size:.7rem;color:#374151;text-align:center">
    Provjera zakonske sukladnosti za HR tržište.<br>
    Zakon o fiskalizaciji · Zakon o PDV-u · Zakon o radu
  </div>
</div>

<!-- Overlay za compliance panel -->
<div id="compliance-overlay" onclick="hideCompliancePanel()" style="
  display:none;position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:8887"></div>
```

```javascript
/* ══ AI COMPLIANCE MONITOR ════════════════════════════════════════ */
const TERMINAL_ID_COMPLIANCE = {{ terminal.id }};

async function runComplianceCheck() {
  try {
    const r = await fetch(`/hr/pos/compliance/${TERMINAL_ID_COMPLIANCE}/`);
    const data = await r.json();
    
    // Ažuriraj dot indikator
    const dot = document.getElementById('compliance-dot');
    if (dot) {
      const colors = { ok: '#22c55e', warning: '#f59e0b', critical: '#ef4444' };
      const glows  = { ok: '#22c55e', warning: '#f59e0b', critical: '#ef4444' };
      dot.style.background = colors[data.status] || '#22c55e';
      dot.style.boxShadow  = `0 0 8px ${glows[data.status] || '#22c55e'}`;
    }
    
    // Ako ima kritičnih — automatski prikaži panel
    if (data.warnings?.some(w => w.severity === 'critical')) {
      renderCompliancePanel(data);
      // Umjesto automatskog otvaranja, blink dot
      if (dot) {
        dot.style.animation = 'blinkDot 1s infinite';
      }
    }
    
    // Pohrani za kasniji prikaz
    window._complianceData = data;
    
  } catch(e) {
    console.warn('Compliance check failed:', e);
  }
}

function renderCompliancePanel(data) {
  const items = document.getElementById('compliance-items');
  const statusText = document.getElementById('compliance-status-text');
  
  if (!items) return;
  
  const criticals = data.warnings.filter(w => w.severity === 'critical').length;
  const warnings  = data.warnings.filter(w => w.severity === 'warning').length;
  
  statusText.textContent = criticals > 0 
    ? `${criticals} kritičnih upozorenja` 
    : warnings > 0 ? `${warnings} upozorenja` : 'Sve je u redu';
  
  if (!data.warnings.length) {
    items.innerHTML = `
      <div style="text-align:center;padding:32px">
        <div style="font-size:3rem;margin-bottom:12px">✅</div>
        <div style="color:#4ade80;font-weight:700">Sve je sukladno</div>
        <div style="font-size:.75rem;color:#64748b;margin-top:6px">
          Provjera: ${new Date(data.checked_at).toLocaleTimeString('hr-HR')}
        </div>
      </div>`;
    return;
  }
  
  const severityIcon = { critical: '🔴', warning: '🟡', info: '🔵' };
  const severityBorder = { 
    critical: 'rgba(239,68,68,.3)', 
    warning: 'rgba(251,191,36,.3)', 
    info: 'rgba(59,130,246,.2)' 
  };
  const severityBg = { 
    critical: 'rgba(239,68,68,.06)', 
    warning: 'rgba(251,191,36,.06)', 
    info: 'rgba(59,130,246,.04)' 
  };
  
  items.innerHTML = data.warnings.map(w => `
    <div style="background:${severityBg[w.severity]};border:1px solid ${severityBorder[w.severity]};
      border-radius:12px;padding:14px">
      <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px">
        <span style="flex-shrink:0">${severityIcon[w.severity] || '⚪'}</span>
        <div style="font-size:.85rem;font-weight:700;color:#f1f5f9">${w.title}</div>
      </div>
      <div style="font-size:.75rem;color:#94a3b8;margin-bottom:12px;line-height:1.5">
        ${w.message}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${(w.actions||[]).map(a => `
          <a href="${a.url}" 
            ${a.external ? 'target="_blank"' : ''}
            ${a.onclick ? `onclick="${a.onclick};return false"` : ''}
            style="padding:6px 12px;border-radius:8px;font-size:.72rem;font-weight:700;
            text-decoration:none;transition:opacity .15s;
            ${a.style === 'gold' 
              ? 'background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);color:#c9a84c' 
              : 'background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#94a3b8'}">
            ${a.label}
          </a>
        `).join('')}
      </div>
    </div>
  `).join('');
}

function showCompliancePanel() {
  document.getElementById('compliance-panel').style.display = 'block';
  document.getElementById('compliance-overlay').style.display = 'block';
  if (window._complianceData) {
    renderCompliancePanel(window._complianceData);
  } else {
    runComplianceCheck().then(() => {
      if (window._complianceData) renderCompliancePanel(window._complianceData);
    });
  }
}

function hideCompliancePanel() {
  document.getElementById('compliance-panel').style.display = 'none';
  document.getElementById('compliance-overlay').style.display = 'none';
}

// CSS za dot blink
const _compStyle = document.createElement('style');
_compStyle.textContent = `
  @keyframes blinkDot {
    0%,100%{opacity:1} 50%{opacity:.2}
  }
`;
document.head.appendChild(_compStyle);

// Pokretanje provjere: odmah i svakih 5 minuta
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(runComplianceCheck, 2000); // 2s nakon učitavanja
  setInterval(runComplianceCheck, 5 * 60 * 1000); // Svakih 5 min
});
```

---

## KORAK 4 — Modificirani joker view

Dodati u `pos/views.py` u `pos_joker()`:

```python
def pos_joker(request, terminal_id):
    # ... (postojeći kod ostaje) ...
    
    # NOVO: Ako nema session → gate će se otvoriti na frontendu
    # Ne redirectamo više na terminal_detail
    # Samo proslijedimo podatke
    
    cashiers = list(POSCashier.objects.filter(
        company=company, is_active=True
    ).order_by('name'))
    
    # Provjeri business location
    bl = terminal.business_location
    has_location = bool(bl and getattr(bl, 'oznaka_prostora', None))
    
    ctx = {
        'terminal': terminal,
        'session': session,
        'cashiers': cashiers,
        'has_location': has_location,
        'is_gastro': is_gastro,
        # ... ostali kontekst ...
    }
    
    return render(request, 'pos/joker.html', ctx)
```

**Ukloni redirect na terminal_detail:**
```python
# STARO (ukloniti):
if not session and request.user.is_authenticated:
    return redirect('pos:terminal_detail', terminal_id=terminal.pk)

# NOVO: ne redirectamo — gate se otvara na JS
```

---

## KORAK 5 — Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py check

# Test compliance API
venv/bin/python manage.py shell -c "
from django.test import Client
from django.contrib.auth.models import User

c = Client()
ivan = User.objects.get(username='ivan_brtan')
c.force_login(ivan)

# Compliance check
r = c.get('/hr/pos/compliance/51/')
import json
data = json.loads(r.content)
print('Compliance status:', data['status'])
for w in data['warnings']:
    print(f'  [{w[\"severity\"]}] {w[\"title\"]}')
"

# Test start session GET
venv/bin/python manage.py shell -c "
from django.test import Client
from django.contrib.auth.models import User

c = Client()
ivan = User.objects.get(username='ivan_brtan')
c.force_login(ivan)
r = c.get('/hr/pos/start/51/')
import json
print(json.loads(r.content))
"

# Live URLs
curl -s -k -o /dev/null -w '%{http_code}' https://limit-connect.com/hr/pos/joker/51/
```

---

## COMMIT

```bash
git add pos/ templates/pos/
git commit -m "feat(pos): Unified Fenix POS — Cashier Gate + Module Nav + AI Compliance

Cashier Gate (modal pri startu):
  - Odabir blagajnika + PIN unos (numpad 0-9)
  - OIB validacija (obavezan po čl. 9 Zakona o fiskalizaciji)
  - Poslovni prostor check — ako nema, inline forma za upis
  - Početna gotovina s preset gumbima (20/50/100/200/500 EUR)
  - AI hint za oznaku poslovnog prostora
  - /hr/pos/start/<terminal_id>/ API (GET: podaci, POST: otvori smjenu)

Module Navigation Bar:
  - Fakture, Arhiva, Partneri, Inventar, Sati, Izvještaj
  - Gastro stolovi (samo gastro terminali)
  - Knjiga boljitaka, Postavke
  - Compliance dot indikator (zeleno/žuto/crveno)

AI Compliance Monitor:
  - /hr/pos/compliance/<terminal_id>/ endpoint
  - 7 provjera: poslovni prostor, OIB blagajnika, fiskalizacija,
    offline boni (48h rok), trajanje smjene (>10h), gotovina, 0€ artikli
  - Severity: critical/warning/info
  - Svaka provjera ima akcijski gumb za rješavanje
  - Auto-check: 2s po učitavanju + svakih 5 minuta
  - Dot blink za kritična upozorenja

Zakonski propisi (HR):
  Zakon o fiskalizaciji NN 133/12: čl. 9, 10, 14, 17
  Zakon o PDV-u: razrada PDV-a na bonu
  Zakon o radu: max smjena 8/10h"
```

---

## NAPOMENE ZA CC

1. **Joker.html je jedini POS template** — sve ostalo su backup ili zastarjelo.
   Ne modificirati `quick.html`, `restaurant.html`, `field_start.html`.

2. **Gate JS varijable** — `{{ terminal.id }}` i `{{ session.id|default:"null" }}"` 
   moraju biti ispravno escapeani za Django template.

3. **CSRF token** — `getCsrf()` funkcija čita iz cookija. Provjeri radi li
   s Django-ovim `{% csrf_token %}` u formi.

4. **`oznaka_prostora` na BusinessLocation** — provjeri field name:
   ```bash
   grep -n "oznaka_prostora\|class BusinessLocation" invoicing/models.py | head -5
   ```
   Ako ne postoji — dodati field i migraciju.

5. **Redirect uklanjanje** — u `pos_joker()` view, linija ~1108 trenutno ima:
   ```python
   if not session and request.user.is_authenticated:
       return redirect('pos:terminal_detail', terminal_id=terminal.pk)
   ```
   Ovo treba ukloniti — gate se sad otvara na JS strani.

6. **Module Nav URLs** — neke URL ime mogu biti drugačije. Provjeri:
   ```bash
   grep -n "app_name\|name=" invoicing/urls.py partners/urls.py inventory/urls.py | head -10
   ```

7. **Javi Sonnet** po završetku s:
   - Compliance API vraća JSON (testom kao gore)
   - Gate se otvara za terminal bez sesije
   - Module nav ikone linkaju ispravno
