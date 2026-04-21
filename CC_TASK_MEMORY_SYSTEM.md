# CC_TASK: 3-slojni Memory Sistem

## STATUS: DONE — commit 9c1656b7 (2026-04-21)

---

## CILJ

Implementirati trajni memory sistem koji CC automatski koristi na kraju svake sesije.
Bez ovog sistema — ideje, odluke i kontekst se gube između sesija.

---

## ZADACI

### T-01 | STATUS: TODO
**Kreirati direktorij za ADR-ove**
```bash
mkdir -p /var/www/fina-connect/docs/decisions
```

### T-02 | STATUS: TODO
**Kreirati ADR template**

Fajl: `/var/www/fina-connect/docs/decisions/ADR-000-template.md`

```markdown
# ADR-XXX: Naziv odluke

## Status
[ ] Predloženo | [ ] Prihvaćeno | [ ] Odbačeno | [ ] Zamijenjeno

## Kontekst
Što je bio problem / zašto je odluka trebala biti donesena.

## Odluka
Što smo odabrali.

## Razlozi
Zašto ovo, a ne alternative.

## Odbačene alternative
Što smo razmatrali i zašto odbacili.

## Posljedice
Što se mijenja, što treba pratiti.
```

### T-03 | STATUS: TODO
**Kreirati IDEAS.md**

Fajl: `/var/www/fina-connect/IDEAS.md`

```markdown
# IDEAS — Append-Only Backlog

> Pravilo: nikad ne brišemo, samo dodajemo.
> Format: `[ID] [STATUS] Opis`
> Status: 💡 nova | 🔄 razmatrana | ✅ implementirana | ❌ odbačena

---

## Ideje

- [I-001] 💡 3-slojni memory sistem (ADR + IDEAS + KONTEKST) — pokrenuto kao CC_TASK
- [I-002] 💡 Git hook upozorenje za FENIX_STATUS.md — T-08
- [I-003] 💡 CLI log-session alat za brzo bilježenje konteksta — T-09
- [I-004] 🔄 Weekly AI digest (cron + Claude API) — odgođeno, planirati za sprint +2
```

### T-04 | STATUS: TODO
**Ažurirati FENIX_STATUS.md — dodati sekciju KONTEKST SESIJE**

Dodati na kraj postojećeg FENIX_STATUS.md:

```markdown
---

## KONTEKST SESIJE

> CC ažurira ovu sekciju na kraju svake sesije.
> Maksimalno 10 rečenica. Što je razgovarano, koje su open threads.

_Čeka prvu sesiju._
```

### T-05 | STATUS: TODO
**Ažurirati CLAUDE.md — dodati Korak 5 (end-of-session)**

Dodati u CLAUDE.md nakon KORAK 4:

```markdown
## KORAK 5 — Kraj sesije (OBAVEZNO)

Prije završetka svake sesije izvrši:

1. Ažuriraj `FENIX_STATUS.md` → sekcija `## KONTEKST SESIJE`
   - 5-10 rečenica: što je rađeno, koje odluke, open threads

2. Ako je razmatrana arhitekturalna odluka → kreiraj ADR fajl:
   `docs/decisions/ADR-XXX-naziv.md`

3. Ako je iznesena ideja (neimplementirana) → dodaj u `IDEAS.md`:
   `[I-XXX] 💡 Opis ideje`

4. Commit svega:
   `docs(memory): update session context + ideas`
```

### T-06 | STATUS: TODO
**Kreirati pre-commit hook — upozorenje za FENIX_STATUS.md**

Fajl: `/var/www/fina-connect/.git/hooks/pre-commit`

```bash
#!/bin/bash
# Upozori ako FENIX_STATUS.md nije staged u ovom commitu
# Ne blokira (exit 0) — blokiranje vodi do --no-verify abuse

STAGED=$(git diff --cached --name-only | grep "FENIX_STATUS.md")

if [ -z "$STAGED" ]; then
    echo ""
    echo "⚠️  PODSJETNIK: FENIX_STATUS.md nije dio ovog commita."
    echo "   Jesi li ažurirao KONTEKST SESIJE i IDEAS.md?"
    echo "   (Nastavi s Enter, ili Ctrl+C da se vratiš)"
    echo ""
    # Ne blokiramo — samo podsjećamo
fi

exit 0
```

```bash
chmod +x /var/www/fina-connect/.git/hooks/pre-commit
```

**Zašto upozorenje umjesto blokiranja:**
- Blokiranje → frustracija → `git commit --no-verify` → hook je mrtav
- Upozorenje → svjesnost → navika → sustav živi

### T-07 | STATUS: TODO
**Kreirati CLI alat: log-session**

Fajl: `/usr/local/bin/log-session`

```python
#!/usr/bin/env python3
"""
Brzo bilježenje konteksta sesije u FENIX_STATUS.md i IDEAS.md.
Korištenje: log-session 'Što smo radili i koje su open threads'
"""
import sys
import subprocess
import re

FENIX_STATUS = '/var/www/fina-connect/FENIX_STATUS.md'
IDEAS_FILE   = '/var/www/fina-connect/IDEAS.md'

def git_info():
    try:
        branch = subprocess.run(['git', '-C', '/var/www/fina-connect',
                                 'branch', '--show-current'],
                                capture_output=True, text=True).stdout.strip()
        commit = subprocess.run(['git', '-C', '/var/www/fina-connect',
                                 'log', '-1', '--format=%s'],
                                capture_output=True, text=True).stdout.strip()
        return branch, commit
    except Exception:
        return 'unknown', 'unknown'

def next_session_id(content):
    ids = re.findall(r'\[S-(\d+)\]', content)
    return f"S-{(max(int(i) for i in ids) + 1):03d}" if ids else "S-001"

def update_fenix_status(message):
    with open(FENIX_STATUS, 'r') as f:
        content = f.read()

    branch, commit = git_info()
    sid = next_session_id(content)

    block = f"\n### [{sid}]\n**Branch:** {branch}\n**Zadnji commit:** {commit}\n**Kontekst:** {message}\n"

    marker = '## KONTEKST SESIJE'
    if marker in content:
        content = content.replace(
            '_Čeka prvu sesiju._', ''
        )
        # Ubaci iza markera i zaglavlja
        insert_after = content.find(marker)
        end_of_header = content.find('\n\n', insert_after) + 2
        content = content[:end_of_header] + block + content[end_of_header:]
    else:
        content += f"\n---\n\n## KONTEKST SESIJE\n{block}"

    with open(FENIX_STATUS, 'w') as f:
        f.write(content)

    return sid

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Korištenje: log-session 'Opis što je rađeno + open threads'")
        sys.exit(1)

    message = ' '.join(sys.argv[1:])
    sid = update_fenix_status(message)
    print(f"✅ Kontekst [{sid}] zapisan u FENIX_STATUS.md")
    print(f"   Dodaj ideje: echo '- [I-XXX] 💡 Opis' >> {IDEAS_FILE}")
```

```bash
chmod +x /usr/local/bin/log-session
```

**Korištenje:**
```bash
log-session 'Implementirali 3-slojni memory sistem. Open thread: weekly digest za sprint +2.'
```

### T-08 | STATUS: TODO
**Verifikacija svega**

```bash
# Struktura
ls /var/www/fina-connect/docs/decisions/
cat /var/www/fina-connect/IDEAS.md

# Hook
cat /var/www/fina-connect/.git/hooks/pre-commit

# CLI test
log-session 'Test poruka — verifikacija log-session alata'
grep "S-001" /var/www/fina-connect/FENIX_STATUS.md

# CLAUDE.md
grep -A 15 "KORAK 5" /var/www/fina-connect/CLAUDE.md
```

### T-09 | STATUS: TODO
**Commit**

```
docs(memory): implement 3-layer session memory system

- ADR template + docs/decisions/ dir
- IDEAS.md append-only backlog (I-001 do I-004)
- FENIX_STATUS.md KONTEKST SESIJE sekcija
- CLAUDE.md KORAK 5 end-of-session obaveza
- pre-commit hook (upozorenje, ne blokiranje)
- log-session CLI alat
```

---

## REDOSLJED IZVRŠAVANJA

T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08 → T-09

---

## NAPOMENA ZA CC

Ovo nije kod — ovo je infrastruktura tvog vlastitog pamćenja.
Nakon T-09, svaka buduća sesija automatski koristi ovaj sistem.
Weekly digest (I-004) ide u sljedeći sprint — ne sada.
