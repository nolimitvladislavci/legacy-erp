#!/usr/bin/env bash
# css_token_fix.sh — zamjena hardkodiranih hex vrijednosti s CSS varijablama
# Kirurgija: radi SAMO na .css datotekama, NE dira HTML predloške.
# Preskače linije s definicijama varijabli (--var: #hex).
# Backup: cp -r static/css /tmp/css_backup_$(date) PRIJE pokretanja!

set -e
CSS_DIR="$(dirname "$0")/../static/css"

echo "=== CSS Token Fix — $(date) ==="
echo "Direktorij: $CSS_DIR"
echo ""

# Mapiranje: hex → var() — SAMO jednoznačne veze
declare -A MAP=(
    ["#c9a84c"]="var(--gold)"
    ["#C9A84C"]="var(--gold)"
    ["#e8c96a"]="var(--gold2)"
    ["#E8C96A"]="var(--gold2)"
    ["#0a0a0a"]="var(--black)"
    ["#0A0A0A"]="var(--black)"
    ["#111214"]="var(--dark)"
    ["#181a1d"]="var(--surface)"
    ["#181A1D"]="var(--surface)"
    ["#1e293b"]="var(--surface2)"
    ["#1E293B"]="var(--surface2)"
    ["#22222c"]="var(--surface3)"
    ["#22222C"]="var(--surface3)"
    ["#252830"]="var(--border)"
    ["#1e2130"]="var(--border2)"
    ["#1E2130"]="var(--border2)"
    ["#e2e8f0"]="var(--text)"
    ["#E2E8F0"]="var(--text)"
    ["#94a3b8"]="var(--text-dim)"
    ["#94A3B8"]="var(--text-dim)"
    ["#64748b"]="var(--text-muted3)"
    ["#64748B"]="var(--text-muted3)"
    ["#4a5060"]="var(--muted)"
    ["#334155"]="var(--muted2)"
    ["#10b981"]="var(--green)"
    ["#10B981"]="var(--green)"
    ["#ef4444"]="var(--red)"
    ["#EF4444"]="var(--red)"
    ["#dc2626"]="var(--red)"
    ["#DC2626"]="var(--red)"
    ["#f59e0b"]="var(--amber)"
    ["#F59E0B"]="var(--amber)"
    ["#3b82f6"]="var(--blue)"
    ["#3B82F6"]="var(--blue)"
)

changed=0
skipped=0

for CSS_FILE in "$CSS_DIR"/*.css; do
    FILENAME=$(basename "$CSS_FILE")

    # global_themes.css — preskači (to su definicije, ne upotrebe)
    if [ "$FILENAME" = "global_themes.css" ]; then
        echo "  SKIP (definicije): $FILENAME"
        continue
    fi

    file_changed=0

    for HEX in "${!MAP[@]}"; do
        VAR="${MAP[$HEX]}"
        HEX_LOWER=$(echo "$HEX" | tr '[:upper:]' '[:lower:]')

        # Zamijeni HEX → var() SAMO na linijama koje NISU definicije varijabli
        # Definicija varijable: linija oblika "  --nešto: #hex"
        # sed: ako linija počinje s opcionalnim whitespace + "--", preskoči
        BEFORE=$(grep -cE "(^|[^-a-z])${HEX_LOWER}" "$CSS_FILE" 2>/dev/null || true)
        if [ "$BEFORE" -gt 0 ]; then
            # Zamjena: samo na linijama koje ne matchaju definiciju varijable
            sed -i "/^\s*--[a-z]/! s|${HEX}|${VAR}|gI" "$CSS_FILE"
            AFTER=$(grep -cE "(^|[^-a-z])${HEX_LOWER}" "$CSS_FILE" 2>/dev/null || true)
            REPLACED=$((BEFORE - AFTER))
            if [ "$REPLACED" -gt 0 ]; then
                echo "    $FILENAME: $HEX → $VAR ($REPLACED zamjena)"
                file_changed=$((file_changed + REPLACED))
                changed=$((changed + REPLACED))
            fi
        fi
    done

    if [ "$file_changed" -gt 0 ]; then
        echo "  [OK] $FILENAME — $file_changed zamjena"
    fi
done

echo ""
echo "=== Završeno ==="
echo "Ukupno zamjena: $changed"
echo ""
echo "Preostali hex (provjera):"
grep -rn "#[0-9a-fA-F]\{6\}\b\|#[0-9a-fA-F]\{3\}\b" "$CSS_DIR"/*.css \
    | grep -v "global_themes.css" \
    | grep -v "^\s*--[a-z]" \
    | grep -oE "#[0-9a-fA-F]{3,6}" \
    | tr '[:upper:]' '[:lower:]' | sort | uniq -c | sort -rn | head -20
