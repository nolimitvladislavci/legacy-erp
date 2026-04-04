# CC_TASK: BORG Živući Sustav — Sprint 1
# Dodijelio: Sonnet | Datum: 2026-04-01 | Prioritet: 🔴 KRITIČNO
# Referenca: BORG_LIVING_SYSTEM.md
# PRAVILO: Čitaj models.py prije svakog koda. Nikad ne pretpostavljaj field names.

---

## TASK 1 — Morning Briefing (Celery task, Razina 3)

**Što:** Svako jutro u 08:00 svaka aktivna firma dobiva personalizirani WhatsApp briefing.

**Datoteka:** `limit_connect_ai/tasks.py` (dodaj novi task)

```python
@app.task(name='borg.morning_briefing')
def borg_morning_briefing():
    """
    Svako jutro 08:00 — personalizirani briefing za sve aktivne firme.
    Šalje na WhatsApp broj vlasnika (Company.phone ili UserProfile.phone).
    """
    from companies.models import Company
    from django.utils import timezone
    today = timezone.localdate()

    for company in Company.objects.filter(is_active=True, subscription__is_active=True):
        try:
            _send_company_briefing(company, today)
        except Exception as e:
            logger.error(f'Briefing fail {company.name}: {e}')
```

**_send_company_briefing logika:**
1. Provjeri modele koji postoje za tu firmu (provjeri has_module flags ili try/except)
2. Skupi podatke:
   - Neplaćeni računi (invoicing) — count + ukupan iznos
   - Termini danas (appointments) — lista ime+usluga+vrijeme
   - POS promet jučer (pos) — ukupan iznos
   - Tax deadlines ovaj tjedan (tax_wizard) — lista
   - Worktime prekoračenja (worktime) — count
3. Generiraj poruku s Haiku (anthropic API) — max 200 tokena, HR jezik, konkretan
4. Pošalji na Company.phone ili UserProfile.phone vlasnika

**System prompt za Haiku:**
```
Ti si poslovni asistent. Na temelju podataka kreiraj kratki jutarnji briefing (max 8 redaka).
Budi konkretan. Navedi samo akcije koje trebaju pažnju. Koristi emojije za preglednost.
Završi s: "LIMIT Connect | {datum}"
```

**Celery beat schedule** (dodaj u settings.py CELERY_BEAT_SCHEDULE):
```python
'borg-morning-briefing': {
    'task': 'borg.morning_briefing',
    'schedule': crontab(hour=8, minute=0),
},
```

---

## TASK 2 — Self-Heal V2 Watchdog (Razina 1)

**Što:** Proaktivni monitor koji hvata probleme PRIJE nego korisnici prijave.

**Nova datoteka:** `core/borg_watchdog.py`

```python
"""
BORG Watchdog — proaktivni monitor infrastrukture.
Pokreće se svakih 5 minuta via Celery beat.
Šalje alert na IVAN_PHONE ako nešto nije u redu.
"""
THRESHOLDS = {
    'response_time_ms': 2000,   # > 2s = problem
    'memory_pct': 85,           # > 85% RAM = problem
    'disk_pct': 80,             # > 80% disk = problem
    'celery_queue_depth': 100,  # > 100 task = problem
    'db_connections': 150,      # > 150 = PgBouncer stress
    'ssl_expiry_days': 30,      # < 30 dana = upozorenje
}
```

**Checks:**
1. `check_response_time()` — curl https://limit-connect.com/health/ i mjeri ms
2. `check_memory()` — psutil memory_percent()
3. `check_disk()` — psutil disk_usage('/') 
4. `check_celery_queue()` — Redis llen('celery')
5. `check_ssl_expiry()` — ssl.get_server_certificate expiry parse
6. `check_db_connections()` — SELECT count(*) FROM pg_stat_activity

Svaki failed check → WhatsApp Ivan + FenixSignal(signal_type='alert', severity='critical')

**Celery beat:**
```python
'borg-watchdog': {
    'task': 'core.tasks.borg_watchdog_check',
    'schedule': crontab(minute='*/5'),
},
```

---

## TASK 3 — Portal AI Widget (Razina 5 — UI)

**Što:** Floating AI widget na svakoj stranici portala — kontekst-svjesni prijedlozi.

**Implementacija:**
- `templates/partials/_borg_widget.html` — floating button + chat drawer
- `core/views.py` — `/api/borg/chat/` POST endpoint  
- Uključi u `templates/base.html` (samo za prijavljene korisnike)

**Widget HTML/CSS:**
```html
<!-- Floating button desno dolje -->
<div id="borgWidget" class="borg-widget-container">
  <button id="borgToggle" class="borg-fab">
    <span class="borg-icon">🤖</span>
    <span class="borg-badge" id="borgBadge" style="display:none">!</span>
  </button>
  <div id="borgDrawer" class="borg-drawer" style="display:none">
    <div class="borg-header">
      <span>🧠 BORG Asistent</span>
      <button onclick="closeBorg()">×</button>
    </div>
    <div id="borgMessages" class="borg-messages"></div>
    <div class="borg-input-row">
      <input id="borgInput" type="text" placeholder="Pitajte nešto...">
      <button onclick="sendBorgMessage()">↑</button>
    </div>
  </div>
</div>
```

**API endpoint `/api/borg/chat/`:**
```python
@login_required
@csrf_exempt  
def borg_chat(request):
    """Kontekst-svjesni AI chat za prijavljenog korisnika."""
    data = json.loads(request.body)
    question = data.get('question', '')
    page_context = data.get('page', '')  # trenutni URL/modul
    
    company = request.user.userprofile.company
    
    # Skupi kontekst firme (zadnjih 7 dana)
    context = _gather_company_context(company, page_context)
    
    # Pozovi Haiku (brz, jeftin)
    response = call_haiku(
        system="Ti si poslovni asistent za {company}. Odgovaraj kratko i konkretno na HR jeziku. Imaš pristup podacima te firme.",
        user=f"Kontekst firme:\n{context}\n\nPitanje: {question}",
        max_tokens=300
    )
    
    return JsonResponse({'answer': response, 'ok': True})
```

**Proaktivni prijedlog pri otvaranju:**
Kad korisnik otvori widget (bez pitanja) → AI automatski generira 2-3 prijedloga akcija bazirana na trenutnom stanju firme:
- "Imate 2 neplaćena računa. Poslati podsjetnik?"
- "Termin za 14:00 nije potvrđen. Potvrditi?"
- "PDV prijava za 3 dana. Pripremiti?"

Prijedlozi su klikabilni gumbi koji izvršavaju akciju direktno.

**CSS:** Dark theme (--dark, --gold), pozicija fixed bottom-right, z-index 9999, mobile-friendly.

---

## TASK 4 — Trend Radar (Razina 4)

**Nova datoteka:** `limit_connect_ai/trend_radar.py`

**RSS sources (samo HR za početak):**
```python
RADAR_SOURCES = [
    {'url': 'https://narodne-novine.nn.hr/', 'name': 'Narodne novine', 'category': 'legal'},
    {'url': 'https://www.fina.hr/novosti', 'name': 'FINA', 'category': 'financial'},
    {'url': 'https://www.porezna-uprava.hr/', 'name': 'Porezna uprava', 'category': 'tax'},
    {'url': 'https://www.hgk.hr/vijesti', 'name': 'HGK', 'category': 'business'},
    {'url': 'https://www.mingor.gov.hr/novosti', 'name': 'MINGOR', 'category': 'eu_funds'},
]
```

**Logika:**
1. Scrape naslova + lead paragrafa (BeautifulSoup, max 300 chars per item)
2. Haiku score (0-10): "Koliko je ova vijest relevantna za HRV malu firmu koja koristi ERP? Samo broj 0-10."
3. Score >= 7 → kreiraj FenixSignal + ComplianceWatchItem (ako pravni)
4. Score >= 9 → instant WhatsApp Ivan

**Celery beat:**
```python
'borg-trend-radar': {
    'task': 'limit_connect_ai.tasks.borg_trend_radar_scan',
    'schedule': crontab(hour='6,12,18', minute=0),  # 3x dnevno
},
```

---

## REDOSLJED IMPLEMENTACIJE

```
TASK 2 (Watchdog) → TASK 1 (Briefing) → TASK 3 (Widget) → TASK 4 (Radar)
```

Watchdog prvi jer štiti sve ostalo.

---

## TEHNIČKI ZAHTJEVI

- Provjeri postoji li `call_haiku()` helper ili `call_claude_haiku()` u codebaseu:
  `grep -rn "haiku\|claude-haiku\|Haiku" /var/www/fina-connect/core/ /var/www/fina-connect/limit_connect_ai/`
- Provjeri `CELERY_BEAT_SCHEDULE` u settings.py i dodaj nove taskove
- Provjeri `Company.phone` field postoji:
  `grep -n "phone" /var/www/fina-connect/companies/models.py`
- `psutil` je u venv? `venv/bin/pip show psutil`

---

## COMMITS (jedan per task)

```
feat(borg): Morning Briefing Celery task — 08:00 WhatsApp sve firme
feat(borg): Self-Heal V2 Watchdog — 5min infra monitor + alerts
feat(borg): Portal AI Widget — floating kontekst chat + proaktivni prijedlozi
feat(borg): Trend Radar — RSS scan + Haiku scoring + FenixSignal routing
```

## PO ZAVRŠETKU

Ažuriraj FENIX_STATUS.md + BORG_LIVING_SYSTEM.md (ažuriraj ocjene po razinama).
