#!/bin/bash
# Riavvia ssc-viewer nella sessione grafica della sala (labwc/wayfire), con il comando
# del file di autostart. L'ambiente grafico viene preso dal viewer in esecuzione
# oppure, se non c'è, dal compositor.
set -euo pipefail

DESKTOP="$HOME/.config/autostart/smartstation.desktop"
PATTERN="ssc_viewer/start.py"
uid=$(id -u)

cmd=$(sed -n 's/^Exec=//p' "$DESKTOP" | head -n1)
if [ -z "$cmd" ]; then
    echo "Exec non trovato in $DESKTOP" >&2
    exit 1
fi

src=$(pgrep -u "$uid" -f "$PATTERN" | head -n1 || true)
[ -n "$src" ] || src=$(pgrep -u "$uid" -x labwc | head -n1 || true)
[ -n "$src" ] || src=$(pgrep -u "$uid" -x wayfire | head -n1 || true)
if [ -z "$src" ]; then
    echo "Nessuna sessione grafica attiva per $(id -un)" >&2
    exit 1
fi

session_env=()
while IFS= read -r -d '' kv; do
    case "$kv" in
        WAYLAND_DISPLAY=*|DISPLAY=*|XAUTHORITY=*|XDG_RUNTIME_DIR=*|XDG_SESSION_TYPE=*|\
        XDG_CURRENT_DESKTOP=*|DBUS_SESSION_BUS_ADDRESS=*|QT_*=*|LANG=*|PATH=*|HOME=*|USER=*|LOGNAME=*)
            session_env+=("$kv") ;;
    esac
done < "/proc/$src/environ"

pkill -u "$uid" -f "$PATTERN" || true
for _ in $(seq 10); do
    pgrep -u "$uid" -f "$PATTERN" >/dev/null || break
    sleep 1
done
pkill -9 -u "$uid" -f "$PATTERN" || true

cd "$HOME"
# shellcheck disable=SC2086 # Exec è una riga di comando da dividere in parole
env -i "${session_env[@]}" setsid $cmd </dev/null >/dev/null 2>&1 &

sleep 5
if pid=$(pgrep -u "$uid" -f "$PATTERN" | head -n1); then
    echo "ssc-viewer avviato, pid $pid"
else
    echo "ssc-viewer non è partito: controllare src/ssc_viewer/log/app.log" >&2
    exit 1
fi
