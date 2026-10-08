#!/usr/bin/env bash
set -euo pipefail

THEME=thinkpad-limine
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/$THEME"
THEMES_DIR="${THEMES_DIR:-/usr/share/plymouth/themes}"
PLYMOUTH_CONF="${PLYMOUTH_CONF:-/etc/plymouth/plymouthd.conf}"
SET_THEME_CMD="${SET_THEME_CMD:-plymouth-set-default-theme}"
MKINITCPIO_CMD="${MKINITCPIO_CMD:-mkinitcpio}"
DEST="$THEMES_DIR/$THEME"

if [[ "${ALLOW_NON_ROOT:-0}" != 1 && $EUID -ne 0 ]]; then
    echo "ERROR: run with sudo: sudo bash $0" >&2; exit 1
fi
for f in "$THEME.plymouth" "$THEME.script" background.png seg.png seg-dim.png bullet.png; do
    [[ -f "$SRC/$f" ]] || { echo "ERROR: missing $SRC/$f" >&2; exit 1; }
done
command -v "$SET_THEME_CMD" >/dev/null || { echo "ERROR: $SET_THEME_CMD not found (is plymouth installed?)" >&2; exit 1; }
command -v "$MKINITCPIO_CMD" >/dev/null || { echo "ERROR: $MKINITCPIO_CMD not found" >&2; exit 1; }
[[ -d "$THEMES_DIR" ]] || { echo "ERROR: $THEMES_DIR does not exist" >&2; exit 1; }

if [[ -f "$PLYMOUTH_CONF" ]]; then
    BACKUP="$PLYMOUTH_CONF.bak-$(date +%F-%H%M%S)"
    cp -a "$PLYMOUTH_CONF" "$BACKUP"
    echo "Backup:  $BACKUP"
else
    echo "Note: $PLYMOUTH_CONF does not exist yet; $SET_THEME_CMD will create it."
fi

if [[ -d "$DEST" ]]; then
    rm -rf -- "$DEST"
    echo "Removed previous $DEST"
fi
install -d -m 755 "$DEST"
for f in "$SRC"/*; do
    [[ -f "$f" ]] && install -m 644 "$f" "$DEST/"
done
echo "Theme:   $DEST"
ls -l "$DEST"

"$SET_THEME_CMD" "$THEME"

"$MKINITCPIO_CMD" -P

echo
echo "Result:"
grep -E '^[[:space:]]*Theme[[:space:]]*=' "$PLYMOUTH_CONF" || echo "WARNING: no Theme= line in $PLYMOUTH_CONF"
echo "Default theme reported by $SET_THEME_CMD: $("$SET_THEME_CMD")"
