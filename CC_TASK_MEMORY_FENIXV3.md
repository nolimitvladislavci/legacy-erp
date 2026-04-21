# CC_TASK: Memory Sistem — Fenix V3 + Dual-System Fix

## STATUS: DONE ✅ (T-01→T-08 sve verificirano, log-session dual-system aktivan)

---

## CILJ

Proširiti 3-slojni memory sistem na Fenix V3.
Popraviti CLAUDE.md lutanje između sustava (sve putanje sad apsolutne).
log-session CLI postaje sustav-svjestan.

## KONTEKST

fina-connect memory sistem: DONE (commit 9c1656b7)
CLAUDE.md: AŽURIRAN — sada čita oba FENIX_STATUS.md s apsolutnim putanjama
Ovaj task: fenix-v3 strana + log-session upgrade

---

## ZADACI

### T-01 | STATUS: TODO
**Kreirati infrastrukturu u fenix-v3**

```bash
mkdir -p /var/www/fenix-v3/docs/decisions
```

### T-02 | STATUS: TODO
**Kopirati ADR template u fenix-v3**

```bash
cp /var/www/fina-connect/docs/decisions/ADR-000-template.md \
   /var/www/fenix-v3/docs/decisions/ADR-000-template.md
```

### T-03 | STATUS: TODO
**Kreirati IDEAS.md za fenix-v3**

Fajl: `/var/www/fenix-v3/IDEAS.md`

```markdown
# IDEAS — Append-Only Backlog (Fenix V3)

> Pravilo: nikad ne brišemo, samo dodajemo.
> Format: `[ID] [STATUS] Opis`
> Status: 💡 nova | 🔄 razmatrana | ✅ implementirana | ❌ odbačena

---

## Ideje

- [I-001] ✅ 3-slojni memory sistem — implementiran u fina-connect, migriran ovdje
- [I-002] 🔄 Weekly AI digest (cron + Claude API) — odgođeno, sprint +2
```

### T-04 | STATUS: TODO
**Dodati KONTEKST SESIJE sekciju u fenix-v3/FENIX_STATUS.md**

Dodati na kraj `/var/www/fenix-v3/FENIX_STATUS.md`:

```markdown
---

## KONTEKST SESIJE

> CC ažurira ovu sekciju na kraju svake sesije koja dira Fenix V3.
> Maksimalno 10 rečenica. Što je rađeno, koje odluke, open threads.

_Čeka prvu sesiju._
```

### T-05 | STATUS: TODO
**Kreirati pre-commit hook za fenix-v3**

Fajl: `/var/www/fenix-v3/.git/hooks/pre-commit`

```bash
#!/bin/bash
STAGED=$(git diff --cached --name-only | grep "FENIX_STATUS.md")

if [ -z "$STAGED" ]; then
    echo ""
    echo "⚠️  PODSJETNIK: FENIX_STATUS.md nije dio ovog commita."
    echo "   Jesi li ažurirao KONTEKST SESIJE i IDEAS.md?"
    echo ""
fi

exit 0
```

```bash
chmod +x /var/www/fenix-v3/.git/hooks/pre-commit
```

### T-06 | STATUS: TODO
**Upgrade log-session CLI — dual-system podrška**

Fajl: `/usr/local/bin/log-session` (zamijeni postojeći)

```python
#!/usr/bin/env python3
"""
Bilježi kontekst sesije u FENIX_STATUS.md odabranog sustava.

Korištenje:
  log-session 'Opis'              # pita koji sustav
  log-session --v3 'Opis'         # Fenix V3
  log-session --erp 'Opis'        # Stari ERP (fina-connect)
  log-session --both 'Opis'       # oba sustava
"""
import sys
import subprocess
import re

SYSTEMS = {
    'erp': {
        'status': '/var/www/fina-connect/FENIX_STATUS.md',
        'ideas':  '/var/www/fina-connect/IDEAS.md',
        'dir':    '/var/www/fina-connect',
        'label':  'Stari ERP (fina-connect)',
    },
    'v3': {
        'status': '/var/www/fenix-v3/FENIX_STATUS.md',
        'ideas':  '/var/www/fenix-v3/IDEAS.md',
        'dir':    '/var/www/fenix-v3',
        'label':  'Fenix V3 (limit-connect)',
    },
}

def git_info(directory):
    try:
        branch = subprocess.run(
            ['git', '-C', directory, 'branch', '--show-current'],
            capture_output=True, text=True).stdout.strip()
        commit = subprocess.run(
            ['git', '-C', directory, 'log', '-1', '--format=%s'],
            capture_output=True, text=True).stdout.strip()
        return branch, commit
    except Exception:
        return 'unknown', 'unknown'

def next_sid(content):
    ids = re.findall(r'\[S-(\d+)\]', content)
    return f"S-{(max(int(i) for i in ids) + 1):03d}" if ids else "S-001"

def log_to_system(system_key, message):
    cfg = SYSTEMS[system_key]
    with open(cfg['status'], 'r') as f:
        content = f.read()

    branch, commit = git_info(cfg['dir'])
    sid = next_sid(content)
    block = f"\n### [{sid}]\n**Branch:** {branch}\n**Zadnji commit:** {commit}\n**Kontekst:** {message}\n"

    marker = '## KONTEKST SESIJE'
    if marker in content:
        content = content.replace('_Čeka prvu sesiju._', '')
        pos = content.find(marker)
        end = content.find('\n\n', pos) + 2
        content = content[:end] + block + content[end:]
    else:
        content += f"\n---\n\n## KONTEKST SESIJE\n{block}"

    with open(cfg['status'], 'w') as f:
        f.write(content)

    print(f"✅ [{sid}] → {cfg['label']}")
    return sid

def pick_system():
    print("\nKoji sustav?")
    print("  1) Stari ERP (fina-connect)")
    print("  2) Fenix V3  (limit-connect)")
    print("  3) Oba")
    choice = input("Izbor [1/2/3]: ").strip()
    return {'1': ['erp'], '2': ['v3'], '3': ['erp', 'v3']}.get(choice, ['erp'])

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == '--v3':
        targets, message = ['v3'], ' '.join(args[1:])
    elif args[0] == '--erp':
        targets, message = ['erp'], ' '.join(args[1:])
    elif args[0] == '--both':
        targets, message = ['erp', 'v3'], ' '.join(args[1:])
    else:
        message = ' '.join(args)
        targets = pick_system()

    if not message:
        print("Greška: nedostaje poruka.")
        sys.exit(1)

    for t in targets:
        log_to_system(t, message)
```

```bash
chmod +x /usr/local/bin/log-session
```

**Primjeri:**
```bash
log-session --v3  'Test suite 96/96. Open: DATEV batch za sprint.'
log-session --erp 'Arhiva bugfix. Open: KumGift Stripe LIVE ključevi.'
log-session --both 'Redis prefiks audit završen. Nema kolizija.'
```

### T-07 | STATUS: TODO
**Verifikacija**

```bash
# fenix-v3 infrastruktura
ls /var/www/fenix-v3/docs/decisions/
cat /var/www/fenix-v3/IDEAS.md
grep "KONTEKST SESIJE" /var/www/fenix-v3/FENIX_STATUS.md
cat /var/www/fenix-v3/.git/hooks/pre-commit

# CLI test
log-session --v3 'Verifikacija dual-system log-session alata'
log-session --erp 'Verifikacija dual-system log-session alata'
grep "S-" /var/www/fenix-v3/FENIX_STATUS.md | tail -3
grep "S-" /var/www/fina-connect/FENIX_STATUS.md | tail -3
```

### T-08 | STATUS: TODO
**Commit (oba sustava)**

```bash
cd /var/www/fenix-v3
git add docs/ IDEAS.md FENIX_STATUS.md .git/hooks/pre-commit
git commit -m "docs(memory): mirror 3-layer session memory system from fina-connect"

cd /var/www/fina-connect
git add /usr/local/bin/log-session 2>/dev/null || true
# log-session je u /usr/local/bin, nije u git — commitaj samo ako je u repo
git commit -m "docs(memory): upgrade log-session CLI to dual-system support" --allow-empty
```

---

## REDOSLJED

T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08

---

## NAPOMENA ZA CC

Nakon ovog taska:
- `log-session --v3 'opis'`  → fenix-v3/FENIX_STATUS.md
- `log-session --erp 'opis'` → fina-connect/FENIX_STATUS.md
- CLAUDE.md KORAK 1 čita OBA sustava s apsolutnim putanjama
- Nema više lutanja između sustava
