#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_dir"
# Never make noise while testing; the engine still runs through fakesink.
export LISH_AUDIO_SINK=fakesink
# Headless runners have no accessibility bus; its warning must not be fatal.
export NO_AT_BRIDGE=1

test_dir="$(mktemp -d)"
trap 'rm -rf -- "$test_dir"' EXIT
# CLI discovery and core tests must not load the user's themes or settings.
export XDG_CONFIG_HOME="$test_dir/config" XDG_DATA_HOME="$test_dir/data"
export XDG_STATE_HOME="$test_dir/state" XDG_CACHE_HOME="$test_dir/cache"

python3 -m compileall -q little_shell.py littleshell tests
python3 -m py_compile bin/lish-open
python3 -m py_compile bin/lish-askpass
sh -n bin/lish-copy-key
test -x bin/lish-askpass
test -x bin/lish-copy-key
zsh -n littleshell/shell/zsh/.zshenv 2>/dev/null || ! command -v zsh >/dev/null
bash -n littleshell/shell/bash/integration.bash
test -x bin/lish-open
bin/lish-open --help | grep -F "lish-open ARQUIVO" >/dev/null
bash -n run.sh install.sh tests/smoke.sh packaging/build-deb.sh
python3 little_shell.py --help >/dev/null
python3 little_shell.py --version | grep -F "0.22.0" >/dev/null
test "$(python3 little_shell.py --list-themes | grep -c "	interno$")" -eq 23
test "$(python3 little_shell.py --list-profiles | wc -l)" -eq 4
python3 -m unittest -v tests.test_core tests.test_regressions tests.test_speech

desktop_file="$test_dir/org.littleshell.LittleShell.desktop"
sed 's|@EXEC@|/usr/bin/lish|g' \
  assets/org.littleshell.LittleShell.desktop > "$desktop_file"
if command -v desktop-file-validate >/dev/null; then
  desktop-file-validate "$desktop_file"
fi
if command -v xmllint >/dev/null; then
  xmllint --noout assets/lish.svg \
    packaging/org.littleshell.LittleShell.metainfo.xml
fi
if command -v convert >/dev/null && command -v identify >/dev/null; then
  convert -background none assets/lish.svg -resize 256x256 "$test_dir/icon.png"
  identify "$test_dir/icon.png" | grep -F '256x256' >/dev/null
fi

if [[ "${LISH_GUI_TEST:-0}" == "1" || -n "${DISPLAY:-}" ]] \
    && command -v xvfb-run >/dev/null && command -v dbus-run-session >/dev/null; then
  python3 tests/run_isolated.py --gui tests/gui_smoke.py
  python3 tests/run_isolated.py --gui tests/shell_integration.py
  python3 tests/run_isolated.py --gui -- -m unittest -v tests.test_gui_regressions tests.test_speech_gui
else
  ./run.sh --diagnose
  printf '%s\n' "SKIP: smoke gráfico (use LISH_GUI_TEST=1 com xvfb-run)" >&2
fi
if [[ "${LISH_GUI_TEST:-0}" == "1" ]] && command -v dbus-run-session >/dev/null \
    && command -v xvfb-run >/dev/null && command -v xdotool >/dev/null; then
  # Private bus and display: never the user's running Little Shell.
  python3 tests/run_isolated.py --gui tests/single_instance.py
fi
if command -v dbus-run-session >/dev/null && command -v gnome-keyring-daemon >/dev/null; then
  python3 tests/run_isolated.py tests/ssh_access.py
fi

test_home="$test_dir/home with spaces"
test_data="$test_dir/data with spaces"
mkdir -p "$test_home"
HOME="$test_home" XDG_DATA_HOME="$test_data" ./install.sh
test -x "$test_home/.local/bin/lish"
HOME="$test_home" XDG_DATA_HOME="$test_data" "$test_home/.local/bin/lish" --version \
  | grep -F '0.22.0' >/dev/null
test -f "$test_data/lish/littleshell/themes/matrix-green.ini"
test -x "$test_home/.local/bin/lish-open"
test -x "$test_data/lish/bin/lish-askpass"
test -x "$test_data/lish/bin/lish-copy-key"
test -f "$test_data/lish/littleshell/shell/zsh/.zshenv"
test -f "$test_data/lish/littleshell/shell/bash/integration.bash"
"$test_home/.local/bin/lish-open" --help >/dev/null
test -f "$test_data/applications/org.littleshell.LittleShell.desktop"
test -f "$test_data/icons/hicolor/scalable/apps/lish.svg"
desktop-file-validate "$test_data/applications/org.littleshell.LittleShell.desktop"
HOME="$test_home" XDG_DATA_HOME="$test_data" ./install.sh --uninstall
test ! -e "$test_home/.local/bin/lish"
test ! -e "$test_home/.local/bin/lish-open"

if command -v dpkg-deb >/dev/null; then
  artifact="$(./packaging/build-deb.sh "$test_dir/packages")"
  dpkg-deb --info "$artifact" >/dev/null
  dpkg-deb --contents "$artifact" | grep -F './usr/bin/lish' >/dev/null
  dpkg-deb --contents "$artifact" | grep -F './usr/bin/lish-open -> ../lib/lish/bin/lish-open' >/dev/null
  dpkg-deb --contents "$artifact" | grep -F './usr/lib/lish/bin/lish-askpass' >/dev/null
  dpkg-deb --contents "$artifact" | grep -F './usr/lib/lish/bin/lish-copy-key' >/dev/null
  dpkg-deb --contents "$artifact" | grep -F './usr/lib/lish/littleshell/shell/zsh/.zshenv' >/dev/null
  dpkg-deb --contents "$artifact" | grep -F './usr/lib/lish/littleshell/shell/bash/integration.bash' >/dev/null
  dpkg-deb --contents "$artifact" \
    | grep -F './usr/lib/lish/littleshell/themes/matrix-green.ini' >/dev/null
  dpkg-deb --extract "$artifact" "$test_dir/package-root"
  python3 "$test_dir/package-root/usr/lib/lish/little_shell.py" --version \
    | grep -F '0.22.0' >/dev/null
  desktop-file-validate \
    "$test_dir/package-root/usr/share/applications/org.littleshell.LittleShell.desktop"
fi
