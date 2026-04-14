# CC TASK — KORAK 9: Security Hardening
**Executor: CC Code | Koordinator: Opus**

---

## CILJ
Nema poznatih ranjivosti pri ulasku klijenata. OWASP Top 10 čist.

## PRAVILA
- Čitaj CLAUDE.md i FENIX_STATUS.md prije rada
- Commitaj svaki logički blok zasebno
- manage.py check --deploy mora proći bez upozorenja na kraju
- NE diraj gunicorn (nemoj systemctl) — nemoj restartati servis

---

## ZADACI

### 9.1 — Django Deploy Check
```bash
cd /var/www/fina-connect
source venv/bin/activate
python manage.py check --deploy 2>&1
```
- Svako upozorenje = fix odmah
- SECURE_HSTS_SECONDS, SECURE_CONTENT_TYPE_NOSNIFF, SECURE_BROWSER_XSS_FILTER, X_FRAME_OPTIONS
- SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE
- Ako nešto od ovoga fali u settings.py → dodaj

### 9.2 — Rate Limiting
- Instaliraj django-ratelimit ako nije instalirano
- Login view: max 5 pokušaja/minuti po IP
- AI endpoint (/api/advisor/*, /api/deepseek/*): max 10/min po korisniku
- PDF generacija: max 20/min po korisniku
- API generalno: max 60/min po korisniku
- Koristi @ratelimit decorator ili middleware

### 9.3 — GDPR Audit Log
- Company switch mora logirati: user_id, from_company, to_company, timestamp, IP
- Provjeri da AuditLog model postoji (core/audit.py)
- Ako ne postoji, kreiraj minimalan model + signal
- Login/logout već ima signal? Provjeri i dodaj ako fali

### 9.4 — OWASP Top 10 Checklist
Provjeri i popravi:
1. **Injection** — raw SQL? ORM svugdje? Provjeri queryset.extra() i RawSQL
2. **Broken Auth** — session timeout? Password policy?
3. **Sensitive Data** — .env sigurnost, DEBUG=False u produkciji
4. **XXE** — XML parsiranje sigurno?
5. **Broken Access Control** — RouteRegistry pokriva sve? (KORAK 3 done)
6. **Security Misconfiguration** — manage.py check --deploy = 0
7. **XSS** — autoescape=True default? |safe filter audit
8. **Insecure Deserialization** — pickle? yaml.load? Provjeri
9. **Known Vulnerabilities** — pip audit
10. **Insufficient Logging** — Sentry LIVE, audit log

### 9.5 — pip audit
```bash
pip install pip-audit
pip-audit 2>&1
```
- Svaka CRITICAL/HIGH ranjivost = upgrade odmah
- MEDIUM = dokumentiraj, planiraj

### 9.6 — Commit i izvještaj
- Commitaj sve promjene (grupno po logičkom bloku)
- Na kraju ispiši tablicu:
  | Provjera | Status | Detalj |
  |----------|--------|--------|
  | deploy check | ✅/❌ | ... |
  | rate limiting | ✅/❌ | ... |
  | GDPR audit log | ✅/❌ | ... |
  | OWASP 1-10 | ✅/❌ | ... |
  | pip audit | ✅/❌ | ... |

---

## ZAVRŠETAK
Kad sve bude ✅, ispiši: **KORAK 9 — SECURITY HARDENING ✅ GOTOV**
