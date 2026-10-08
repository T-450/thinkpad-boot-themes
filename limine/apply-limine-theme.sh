#!/usr/bin/env bash
set -euo pipefail

LIMINE_CONF="${LIMINE_CONF:-/boot/limine.conf}"
LIMINE_DIR="${LIMINE_DIR:-/boot/limine}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WALLPAPER="$HERE/thinkpad-wallpaper.png"
SNIPPET="$HERE/limine-theme-snippet.conf"

for f in "$LIMINE_CONF" "$WALLPAPER" "$SNIPPET"; do
    [[ -f "$f" ]] || { echo "ERROR: missing $f" >&2; exit 1; }
done
[[ -d "$LIMINE_DIR" ]] || { echo "ERROR: missing directory $LIMINE_DIR" >&2; exit 1; }
grep -q '^default_entry:' "$LIMINE_CONF" || { echo "ERROR: no 'default_entry:' line in $LIMINE_CONF" >&2; exit 1; }

global_keys() {
    awk '/^[[:space:]]*\// { exit } /^[A-Za-z_]+:/ { print tolower(substr($0, 1, index($0, ":") - 1)) }' "$1"
}

mapfile -t HAVE < <(global_keys "$LIMINE_CONF")
mapfile -t WANT < <(global_keys "$SNIPPET")
MISSING=()
for k in "${WANT[@]}"; do
    [[ " ${HAVE[*]} " == *" $k "* ]] || MISSING+=("$k")
done

if [[ ! -f "$LIMINE_DIR/thinkpad-wallpaper.png" ]] || ! cmp -s "$WALLPAPER" "$LIMINE_DIR/thinkpad-wallpaper.png"; then
    cp "$WALLPAPER" "$LIMINE_DIR/thinkpad-wallpaper.png"
    echo "Wallpaper: $LIMINE_DIR/thinkpad-wallpaper.png"
else
    echo "Wallpaper already in place: $LIMINE_DIR/thinkpad-wallpaper.png"
fi

if (( ${#MISSING[@]} == 0 )); then
    echo "Theme options already present: $LIMINE_CONF not modified."
else
    BACKUP="$LIMINE_CONF.bak-theme-$(date +%F-%H%M%S)"
    cp -a "$LIMINE_CONF" "$BACKUP"
    echo "Backup:    $BACKUP"
    for k in "${WANT[@]}"; do
        [[ " ${MISSING[*]} " == *" $k "* ]] || echo "Kept existing: $k"
    done
    TMP="$(mktemp)"
    trap 'rm -f "$TMP"' EXIT
    awk -v snippet="$SNIPPET" -v missing=" ${MISSING[*]} " '
        {
            print
            if (!done && $0 ~ /^default_entry:/) {
                while ((getline s < snippet) > 0) {
                    if (s !~ /^[A-Za-z_]+:/) continue
                    k = tolower(substr(s, 1, index(s, ":") - 1))
                    if (index(missing, " " k " ")) print s
                }
                close(snippet)
                done = 1
            }
        }
    ' "$LIMINE_CONF" > "$TMP"
    cat "$TMP" > "$LIMINE_CONF"
    echo "Inserted after default_entry: ${MISSING[*]}"
fi

sync

if [[ "${SKIP_SYNC:-0}" != 1 ]] && command -v limine-snapper-sync >/dev/null 2>&1; then
    limine-snapper-sync
else
    echo "limine-snapper-sync skipped: not installed or SKIP_SYNC=1"
fi

echo
echo "===== theme keys in $LIMINE_CONF ====="
grep -nE '^(timeout|default_entry|interface_|wallpaper|backdrop|term_)' "$LIMINE_CONF" || echo "WARNING: no theme keys found"

if [[ -f "$LIMINE_DIR/limine.conf" && "$(realpath "$LIMINE_DIR/limine.conf")" != "$(realpath "$LIMINE_CONF")" ]]; then
    echo
    echo "WARNING: $LIMINE_DIR/limine.conf exists. Limine reads it BEFORE $LIMINE_CONF,"
    echo "         so the theme will not show at boot until it is moved aside, e.g.:"
    echo "         mv $LIMINE_DIR/limine.conf $LIMINE_DIR/limine.conf.old"
fi
