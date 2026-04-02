# CC_TASK: DRON #3 — CSS Kirurgija (NE diraj template)
# Datum: 02.04.2026 | Prioritet: 🟡 Go-live readiness, ali sigurno
# Odgovorni: CC Code
# Kontekst: Sonnet analiza — 175 hardcoded hex vrijednosti u CSS, global_themes.css već ima :root

---

## PRAVILO #1 (APSOLUTNO)

**NE DIRAJ HTML PREDLOŠKE. NE DIRAJ KLASE. NE PREPIŠI NIŠTA.**
1.025 templatea je zaštićena zona do 01.05.2026.
Sve se radi isključivo u CSS datotekama.

---

## MAPIRANJE — Poznate hardkodirane vrijednosti → CSS varijable

global_themes.css VEĆ ima :root s ovim varijablama:
```
--gold: #c9a84c          --gold2: #e8c96a          --gold-dim: rgba(201,168,76,0.12)
--gold-border: rgba(201,168,76,0.28)
--black: #0a0a0a         --white: #f0ede8           --dark: #111214
--surface: #181a1d       --surface2: #1e293b        --surface3: #22222c
--border: #252830        --border-light: rgba(255,255,255,0.08)
--text: #e2e8f0          --text-dim: #94a3b8        --muted: #4a5060
--green: #10b981         --red: #ef4444             --amber: #f59e0b  --blue: #3b82f6
```

Hardkodirani hex-ovi koji se ponavljaju u CSS datotekama (iz analize):
```
#c9a84c  → var(--gold)
#e8c96a  → var(--gold2)
#1e293b  → var(--surface2)
#0a0a0a  → var(--black)
#0f172a  → var(--black)  [alternativna varijanta]
#111214  → var(--dark)
#181a1d  → var(--surface)
#22222c  → var(--surface3)
#252830  → var(--border)
#334155  → var(--border)  [close match — provjeri vizualno]
#e2e8f0  → var(--text)
#94a3b8  → var(--text-dim)
#64748b  → var(--muted)   [ili dodaj --muted2: #64748b u :root]
#4a5060  → var(--muted)
#10b981  → var(--green)
#ef4444  → var(--red)
#f59e0b  → var(--amber)
#3b82f6  → var(--blue)
```

---

## ZADATAK A — Dodaj alias varijable u global_themes.css

U :root blok dodaj varijable koje nedostaju:
```css
:root {
    /* ... postojeće ... */
    --muted2: #64748b;           /* Dodati — u konto.css */
    --border2: #334155;          /* Dodati — alternativni border */
    --surface-deep: #0f172a;     /* Dodati — najdublji dark layer */
    --text-muted3: #4a5060;      /* Alias za --muted */
}
```

---

## ZADATAK B — Script za automatsku zamjenu u CSS datotekama

SAMO .css datoteke, NIKAD .html, .py, .js:

```bash
#!/bin/bash
# run: cd /var/www/fina-connect && bash scripts/css_token_fix.sh
# SIGURNO: radi samo na CSS, ne dira HTML

CSS_DIR="/var/www/fina-connect/static/css"

# Backup prvo
cp -r "$CSS_DIR" "/tmp/css_backup_$(date +%Y%m%d_%H%M%S)"
echo "Backup napravljen u /tmp/"

# Zamijeni hardkodirane hex s CSS varijablama
# SAMO u CSS datotekama

declare -A REPLACEMENTS=(
    ["#c9a84c"]="var(--gold)"
    ["#e8c96a"]="var(--gold2)"
    ["#1e293b"]="var(--surface2)"
    ["#0f172a"]="var(--surface-deep)"
    ["#111214"]="var(--dark)"
    ["#181a1d"]="var(--surface)"
    ["#22222c"]="var(--surface3)"
    ["#252830"]="var(--border)"
    ["#334155"]="var(--border2)"
    ["#e2e8f0"]="var(--text)"
    ["#94a3b8"]="var(--text-dim)"
    ["#64748b"]="var(--muted2)"
    ["#10b981"]="var(--green)"
    ["#ef4444"]="var(--red)"
    ["#f59e0b"]="var(--amber)"
    ["#3b82f6"]="var(--blue)"
)

for HEX in "${!REPLACEMENTS[@]}"; do
    VAR="${REPLACEMENTS[$HEX]}"
    # Zamijeni u svim CSS datotekama, case-insensitive hex
    find "$CSS_DIR" -name "*.css" -exec sed -i "s/${HEX}/${VAR}/gI" {} \;
    HEX_UPPER=$(echo "$HEX" | tr '[:lower:]' '[:upper:]')
    find "$CSS_DIR" -name "*.css" -exec sed -i "s/${HEX_UPPER}/${VAR}/gI" {} \;
done

echo "Zamjena završena. Provjeri vizualno:"
echo "  curl -s https://limit-connect.com/static/css/fenix-ui.css | grep -c 'var(--'"
```

---

## ZADATAK C — Vizualna provjera PRIJE commita

```bash
# Provjeri da nema zaostalih hardkodiranih boja (osim rgba s transparentnošću — te su OK)
grep -r ":\s*#[0-9a-fA-F]\{3,6\}" /var/www/fina-connect/static/css/ \
  --include="*.css" \
  | grep -v "global_themes\|/\*\|rgba\|linear-gradient\|box-shadow" \
  | wc -l
# Cilj: 0 (ili blizu 0 — rgba su dozvoljeni)

# Vizualni test — otvori 3 stranice i provjeri:
# 1. /hr/dashboard/ — zlatni akcenti mora biti isti
# 2. /hr/pos/joker/1/ — POS terminali
# 3. /hr/invoicing/ — fakture
```

---

## ŠTO NE RADITI

- NE raditi `sed` zamjene u .html datotekama
- NE brisati klase iz CSS datoteka
- NE prepisivati selektore
- NE dirai static/css/apps/ datoteke dok nema vizualne provjere
- NE commitati bez diff provjere: `git diff --stat static/css/`

---

## DELIVERABLE

1. global_themes.css s 4 nove alias varijable
2. scripts/css_token_fix.sh kreiran i pokrenut
3. `grep -c '#[0-9a-fA-F]' static/css/**/*.css` → ispod 20 (samo rgba ostaci)
4. Vizualna provjera 3 stranice → screenshot u FENIX_STATUS.md

Rok: **12.04.2026** (3 dana prije go-live — dovoljno za rollback ako treba)

