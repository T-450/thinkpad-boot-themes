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

if [[ ! -f "$LIMINE_DIR/thinkpad-wallpaper.png" ]] || ! cmp -s "$WALLPAPER" "$LIMINE_DIR/thinkpad-wallpaper.png"; then
    cp "$WALLPAPER" "$LIMINE_DIR/thinkpad-wallpaper.png"
    echo "Wallpaper: $LIMINE_DIR/thinkpad-wallpaper.png"
else
    echo "Wallpaper already in place: $LIMINE_DIR/thinkpad-wallpaper.png"
fi

TMP="$(mktemp)"
LOG="$(mktemp)"
trap 'rm -f "$TMP" "$LOG"' EXIT

awk -v logf="$LOG" '
    function key(s,    k) {
        k = tolower(substr(s, 1, index(s, ":") - 1))
        sub(/_color/, "_colour", k)
        return k
    }
    FNR == 1 { pass++ }
    pass == 1 {
        if ($0 ~ /^[A-Za-z_]+:/) { k = key($0); order[++n] = k; want[k] = $0 }
        next
    }
    pass == 2 {
        if ($0 ~ /^[[:space:]]*\//) nextfile
        if ($0 ~ /^[A-Za-z_]+:/) have[key($0)] = 1
        next
    }
    {
        if (!globals_done && $0 ~ /^[[:space:]]*\//) globals_done = 1
        if (!globals_done && ($0 ~ /^# --- (end )?ThinkPad look/ || $0 ~ /^# \(kept existing [a-z_]+\)$/)) {
            print "removed old marker " $0 > logf
            next
        }
        if (!globals_done && $0 ~ /^[A-Za-z_]+:/) {
            k = key($0)
            if (k in want) {
                if (k in seen) { print "removed duplicate " $0 > logf; next }
                seen[k] = 1
                if ($0 != want[k]) print "updated " k > logf
                print want[k]
                next
            }
        }
        print
        if (!inserted && !globals_done && $0 ~ /^default_entry:/) {
            for (i = 1; i <= n; i++)
                if (!(order[i] in have)) { print want[order[i]]; print "added " order[i] > logf }
            inserted = 1
        }
    }
' "$SNIPPET" "$LIMINE_CONF" "$LIMINE_CONF" > "$TMP"

if cmp -s "$TMP" "$LIMINE_CONF"; then
    echo "Theme options already current: $LIMINE_CONF not modified."
else
    BACKUP="$LIMINE_CONF.bak-theme-$(date +%F-%H%M%S)"
    cp -a "$LIMINE_CONF" "$BACKUP"
    echo "Backup:    $BACKUP"
    cat "$TMP" > "$LIMINE_CONF"
    sed 's/^/Changed:   /' "$LOG"
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
