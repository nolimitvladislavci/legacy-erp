# CC_TASK_CLEANUP_PRINT_LOGS — Code cleanup: print() → logger, tools_archive
## Agent: CC Code | Prioritet: NIZAK | Datum: 2026-03-25

---

## ZADATAK 1 — synesis/bulk_import.py: print() → logger

```bash
cd /var/www/fina-connect
# Dodaj import ako ne postoji
grep -q "^import logging" synesis/bulk_import.py || \
  sed -i '1s/^/import logging\nlogger = logging.getLogger(__name__)\n\n/' synesis/bulk_import.py

# Zamijeni sve print( s logger.info(
sed -i 's/^\(\s*\)print(\(.*\))/\1logger.info(\2)/' synesis/bulk_import.py

# Verifikacija
grep -c "print(" synesis/bulk_import.py  # mora biti 0
```

---

## ZADATAK 2 — tools_archive → van projekta

```bash
# Premjesti na root home (izvan web roota)
mv /var/www/fina-connect/tools_archive /root/limit_connect_archive_$(date +%Y%m%d)

# Verifikacija — ne smije postojati više
ls /var/www/fina-connect/tools_archive 2>/dev/null && echo "GREŠKA" || echo "OK"
```

---

## ZADATAK 3 — backups → van web roota (OPREZ: provjeri da ne koriste cron)

```bash
# Provjeri cron referira li /var/www/fina-connect/backups
crontab -l | grep backup
grep -r "fina-connect/backups" /etc/cron* 2>/dev/null

# Ako ništa ne referira → premjesti
mkdir -p /root/limit_connect_backups
mv /var/www/fina-connect/backups /root/limit_connect_backups/$(date +%Y%m%d)

# Ako cron referira → ne premještaj, samo javi Ivanu
```

---

## ZADATAK 4 — Wildcard imports u production kodu

```bash
# Nađi wildcard importe izvan test fajlova i venv-a
grep -rn "from .* import \*" /var/www/fina-connect \
  --include="*.py" \
  --exclude-dir=venv \
  --exclude-dir=backups \
  --exclude-dir=migrations | grep -v "test_\|_test\|tools_archive" | head -20
```

Za svaki wildcard import u production kodu: zamijeni s eksplicitnim importima.

---

## DONE kriterij

- [ ] synesis/bulk_import.py: 0 print() izjava
- [ ] tools_archive premještena iz web roota
- [ ] backups premještena ili flagana (ovisno o cron statusu)
- [ ] Commit: "chore: cleanup print→logger, archive tools_archive"
