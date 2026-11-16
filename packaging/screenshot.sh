#!/usr/bin/env bash
# Capture a clean Little Shell screenshot on a real X display.
#
# It runs the app from source against a throwaway HOME so the prompt is the
# neutral "user@lab" and no real history, theme or settings leak into the
# image. Headless Xvfb does not render VTE faithfully, so run this on your
# actual desktop (X11; a compositor is fine).
#
#   packaging/screenshot.sh <theme-id> <out.png> [extra lish args...]
#   packaging/screenshot.sh mac-dark docs/screenshots/hero.png
#   packaging/screenshot.sh nord      docs/screenshots/nord.png --no-panel
#
# Needs: xdotool and ImageMagick (import). Wayland: run under XWayland or use
# your desktop's own screenshot tool on the window instead.
set -euo pipefail

theme="${1:?usage: screenshot.sh <theme-id> <out.png> [lish args...]}"
out="${2:?usage: screenshot.sh <theme-id> <out.png> [lish args...]}"
shift 2 || true
root="$(cd "$(dirname "$0")/.." && pwd)"

home="$(mktemp -d)"
trap 'rm -rf "$home"' EXIT
printf 'export PS1="\\[\\e[38;5;75m\\]user@lab\\[\\e[0m\\]:~\\$ "\nclear\n' > "$home/.bashrc"
work="$home/lab"
mkdir -p "$work/bin" "$work/docs"
echo "scope: 10.10.13.0/24 (autorizado)" > "$work/scope.txt"
: > "$work/bin/run.sh"
: > "$work/docs/notas.md"

HOME="$home" SHELL=/bin/bash LISH_AUDIO_SINK=fakesink \
    python3 "$root/little_shell.py" --separate --no-sound \
    --theme "$theme" --font-size 14 --working-directory "$work" "$@" &
app=$!
sleep 4

wid="$(xdotool search --pid "$app" 2>/dev/null | tail -1 || true)"
[ -z "$wid" ] && wid="$(xdotool getactivewindow)"
xdotool windowactivate "$wid" 2>/dev/null || true
sleep 0.4
for command in "ls" "cat scope.txt" "echo porta 22/tcp aberta no 10.10.13.37"; do
    xdotool type --window "$wid" --delay 22 "$command"
    xdotool key --window "$wid" Return
    sleep 0.6
done
sleep 1.2
import -window "$wid" "$out"
kill "$app" 2>/dev/null || true
echo "saved $out ($theme)"
