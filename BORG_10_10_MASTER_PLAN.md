# BORG 10/10 — ZATVOREN KRUG
## Datum: 2026-03-24 | Autor: Ivan + Sonnet
## Cilj: Trojstvo prima signale direktno od korisnika — bez Ivana u sredini

---

## FILOZOFIJA

```
SADA (7/10):    Korisnik → Ivan → Trojstvo → fix → Ivan → Korisnik
CILJ (10/10):   Korisnik → FENIX → Trojstvo → fix → Korisnik
```

Ivan ostaje VLASNIK i ARHITEKT.
Ivan NIJE bottleneck za svaki bug, anomaliju i pitanje.

---

## ARHITEKTURA — 4 SLOJA

```
┌─────────────────────────────────────────────────────────┐
│  SLOJ 1: SIGNAL ULAZ                                    │
│  WhatsApp (Šeki) · In-app gumb (Marija) · Auto-log     │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  SLOJ 2: FENIX SIGNAL ARHIVA                            │
│  FenixSignal model · screenshot · tekst · kontekst     │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  SLOJ 3: FENIX PATROL (Celery beat, svakih 15 min)     │
│  Haiku triage · auto-task kreacija · FENIX_STATUS.md   │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  SLOJ 4: ZATVORENA PETLJA                               │
│  Trojstvo fixa → korisnik dobiva potvrdu (WhatsApp)    │
└─────────────────────────────────────────────────────────┘
```

---

## SLOJ 1: SIGNAL KANALI

### Kanal A — WhatsApp (Šeki + svi klijenti s mobitelom)
- Šeki šalje sliku ili tekst na WAHA broj
- WAHA webhook → `/fenix/signal/whatsapp/`
- Automatski se kreira FenixSignal(source='whatsapp', company=Šekijeva firma)
- Šeki dobiva auto-odgovor: "Primljeno ✓ Fenix gleda"

### Kanal B — In-app gumb (Marija + svi logirani korisnici)
- Crveni gumb u navigaciji: 🔴 "Prijavi anomaliju"
- Modal: tekst + screenshot (drag&drop ili kamera)
- POST → `/fenix/signal/report/`
- FenixSignal(source='inapp', user=Marija, company=Konjik)

### Kanal C — Auto-signal iz sustava
- GracefulErrorMiddleware → svaka 500/neočekivana greška → FenixSignal(source='auto', severity='high')
- POS Pulse anomalije → FenixSignal(source='pos_pulse')
- Celery task failure → FenixSignal(source='celery')

---

## SLOJ 2: FENIX SIGNAL ARHIVA

```python
class FenixSignal(models.Model):
    # Izvor
    source = CharField(choices: whatsapp/inapp/auto/pos_pulse/celery/email)
    company = FK(Company)
    user = FK(User, null=True)  # null za auto-signale

    # Sadržaj
    title = CharField(200)
    body = TextField()
    screenshot = ImageField(null=True)  # WebP kompresija
    metadata = JSONField(default=dict)  # {path, user_agent, pos_terminal, ...}
    raw_payload = TextField()  # originalna poruka/log

    # Triage (Haiku popunjava)
    category = CharField(choices: bug/ux/data/feature/question/anomaly)
    severity = CharField(choices: critical/high/medium/low/info)
    ai_summary = TextField()
    ai_suggested_action = TextField()

    # Status
    status = CharField(choices: new/triaged/task_created/in_progress/resolved/ignored)
    task_file = CharField(null=True)  # npr. CC_TASK_BUG_20260325_001.md
    resolved_at = DateTimeField(null=True)
    resolution_note = TextField()

    # Feedback korisniku
    user_notified = BooleanField(default=False)
    notification_sent_at = DateTimeField(null=True)

    created_at = auto
    updated_at = auto
```

---

## SLOJ 3: FENIX PATROL

**Celery beat: svakih 15 minuta**

```
patrol():
  1. Dohvati sve FenixSignal(status='new')
  2. Za svaki signal → Haiku triage:
       - category (bug/ux/data/feature/question/anomaly)
       - severity (critical/high/medium/low)
       - ai_summary (1 rečenica)
       - suggested_action (što Trojstvo treba napraviti)
  3. severity == 'critical' → odmah kreira CC_TASK fajl + notify Ivan WhatsApp
  4. severity == 'high'     → kreira CC_TASK ili GEMINI_TASK
  5. severity == 'medium'   → dodaje u FENIX_STATUS.md backlog
  6. severity == 'low/info' → arhivira, bez taska
  7. Ažurira FENIX_STATUS.md — sekcija "Novi signali"
  8. signal.status = 'triaged' (ili 'task_created')
```

**Auto-task format:**
```
CC_TASK_SIGNAL_{datum}_{id}.md
  - izvor: {source} / {company}
  - poruka korisnika: {body}
  - screenshot: {url}
  - AI triage: {severity} / {category}
  - ai_suggested_action: {text}
  - OBAVEZNO: pročitaj relevantni models.py prije pisanja koda
```

---

## SLOJ 4: ZATVORENA PETLJA

Nakon što Trojstvo zatvori task (commit + test):
1. `signal.status = 'resolved'`
2. WhatsApp korisnika: "✅ {firma} — {ai_summary} je riješeno."
3. Za in-app: notifikacija u sučelju
4. Za auto-signale: log entry

---

## DASHBOARD (Superadmin)

`/superadmin/fenix-signals/`
- Tablica svih signala s filterima (source, severity, status, company)
- Statistika: prosječno vrijeme od signal → resolved
- Heatmap: koje firme, koje module, koji dan
- "Asimiliraj sve" gumb → pokreće patrol odmah

---

## DEFINICIJA 10/10

- [ ] Šeki šalje WhatsApp → FenixSignal kreiran za < 30 sekundi
- [ ] Marija klikne gumb → modal → FenixSignal kreiran
- [ ] Patrol triages za < 15 minuta
- [ ] Critical bug → CC_TASK kreiran automatski, Ivan dobiva WhatsApp
- [ ] Trojstvo zatvara task → Šeki/Marija dobivaju potvrdu
- [ ] Ivan nije potreban za cijeli krug osim za critical aproval

---

## TASKOVI

| Fajl | Agent | Što |
|------|-------|-----|
| CC_TASK_BORG_SIGNAL_FOUNDATION.md | CC Code | FenixSignal model + WhatsApp webhook + in-app gumb + API endpointi |
| GEMINI_TASK_BORG_PATROL.md | Gemini | Patrol Celery task + Haiku triage + auto-task kreacija |
| CC_TASK_BORG_DASHBOARD.md | CC Code | Superadmin dashboard /fenix-signals/ |

Redoslijed: Foundation → Patrol → Dashboard
