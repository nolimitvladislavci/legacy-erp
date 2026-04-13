# PLAN: Brisanje table — 13.04.2026
# Autor: Opus | Sesija: 13.04. nastavak

## PRIORITET 1 — Prije 15.04. (DANAS)

### P1.1 Cookie Banner [GDPR bloker]
- base.html: cookie consent banner za SVE stranice
- memio-pet statički: /var/www/memio-pet/index.html
- memio-world landing
- localStorage persistencija (ne kolačić za kolačić)
- Categorije: necessary, analytics, marketing
- Accept/Reject/Settings
- COMMIT + DEPLOY

### P1.2 Compliance Autofix [pokreni engine]
- Pokreni validation_engine na sve Company
- Zapiši nalaze kao ImprovementSuggestion
- Provjeri 8 radnika bez OIB-a
- COMMIT rezultata

### P1.3 Archive Readonly [zakonska obaveza]
- Middleware: ako je subscription plan='archive_readonly' → read-only
- View guard: blokira POST/PUT/DELETE, dopušta GET
- Template banner: "Vaša pretplata je istekla — arhiva dostupna read-only"
- COMMIT + DEPLOY

### P1.4 Stolarija AI [dovrši]
- ai_agent.py: email draft agent
- Admin registracija modela (Stavka 5)
- manage.py check
- COMMIT

### P1.5 Dead tasks → TASK_ARCHIVE
- Premjesti sve DONE taskove u TASK_ARCHIVE/
- Ažuriraj aktivne taskove sa stvarnim statusom

## PRIORITET 2 — Može nakon 15.04.

- CC_TASK_EMPLOYEE_10_10 Faze 4-5
- CC_TASK_POS_WORKSPACE
- CC_TASK_BOOKING_SIGNATURE (wire preostale akcije)
- GEMINI_TASK_AUDIT_TRAIL_PARTITION
- GEMINI_TASK_SERVICE_AI_STOLARIJA
- Shell Migration Faze 2-3
- Inline style purge (4,634 → <1,000)
