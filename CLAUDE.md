# LIMIT Connect — Upute za AI agente

## Server
```
root@37.27.248.86 | /var/www/fina-connect
. venv/bin/activate
systemctl restart gunicorn-fina celery-worker celery-beat
```

## Pravila

1. **Tema:** crna-zlatna (`--black:#0a0a0a`, `--gold:#c9a84c`), fontovi Cormorant Garamond + Barlow
2. **Branding:** "LIMIT Connect" (NE "Fina Connect", NE "ERP")
3. **Slogan:** "Fiskalizacija u džepu"
4. **HTML forme:** native `<label><input type="radio">` — NIKAD JavaScript onclick za selekciju. Mora raditi na mobitelu.
5. **Tenant isolation:** SVAKI query mora imati `company=` filter. Ako model nema `company`, koristi `session__terminal__company` (POS) ili `parent_company` (Branch).

## Task fajlovi
- **Naming:** `CC_TASK_YYYYMMDD_OPIS.md` (datum obavezan)
- **Jednokratni:** napiši → agent odradi → obriši
- **Nikad > 10 aktivnih** — ako ima više, prioritiziraj i obriši stare
- **Trajni kontekst** ide u memoriju (Opus), ne u task fajlove
