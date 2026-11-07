#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
app_dir="$data_home/lish"
bin_dir="${HOME}/.local/bin"
desktop_dir="$data_home/applications"
icon_dir="$data_home/icons/hicolor/scalable/apps"

uninstall() {
  # Only remove lish-open when it is our own link, never a user's command.
  [ "$(readlink -- "$bin_dir/lish-open" 2>/dev/null)" = "$app_dir/bin/lish-open" ] && rm -f -- "$bin_dir/lish-open"
  rm -f -- "$bin_dir/lish" "$desktop_dir/lish.desktop" \
    "$desktop_dir/org.littleshell.LittleShell.desktop" \
    "$icon_dir/lish.svg"
  rm -rf -- "$app_dir"
  command -v update-desktop-database >/dev/null && update-desktop-database "$desktop_dir" >/dev/null 2>&1 || true
  command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$data_home/icons/hicolor" >/dev/null 2>&1 || true
  printf '%s\n' "Little Shell removido da conta atual."
}

if [[ "${1:-}" == "--uninstall" ]]; then
  uninstall
  exit 0
fi

if [[ "${1:-}" == "--check" ]]; then
  exec "$project_dir/run.sh" --diagnose
fi

if [[ $# -gt 0 ]]; then
  printf 'Uso: %s [--check|--uninstall]\n' "$0" >&2
  exit 2
fi

for command in python3 install sed; do
  command -v "$command" >/dev/null || { printf 'Dependencia ausente: %s\n' "$command" >&2; exit 1; }
done

"$project_dir/run.sh" --diagnose

mkdir -p -- "$app_dir" "$bin_dir" "$desktop_dir" "$icon_dir"
install -m 755 "$project_dir/little_shell.py" "$app_dir/little_shell.py"
# Only the code folder is replaced (modules removed in a new version must
# not linger); sound packs and other data next to it stay untouched.
rm -rf -- "$app_dir/littleshell"
while IFS= read -r -d '' source; do
  install -D -m 644 "$project_dir/$source" "$app_dir/$source"
done < <(cd "$project_dir" && find littleshell -name '*.py' -not -path '*/__pycache__/*' -print0)
install -D -m 644 "$project_dir/littleshell/shell/zsh/.zshenv" "$app_dir/littleshell/shell/zsh/.zshenv"
install -D -m 644 "$project_dir/littleshell/shell/bash/integration.bash" "$app_dir/littleshell/shell/bash/integration.bash"
install -d "$app_dir/littleshell/themes"
for source in "$project_dir"/littleshell/themes/*.ini; do
  install -m 644 "$source" "$app_dir/littleshell/themes/$(basename "$source")"
done
while IFS= read -r -d '' source; do
  install -D -m 644 "$project_dir/$source" "$app_dir/$source"
done < <(cd "$project_dir" && find littleshell/soundpacks -type f -print0)
install -m 644 "$project_dir/assets/lish.svg" "$icon_dir/lish.svg"
launcher="$bin_dir/lish"
escaped_launcher="${launcher//\\/\\\\}"
escaped_launcher="${escaped_launcher//&/\\&}"
escaped_launcher="${escaped_launcher//|/\\|}"
sed "s|@EXEC@|\"$escaped_launcher\"|g" \
  "$project_dir/assets/org.littleshell.LittleShell.desktop" \
  > "$desktop_dir/org.littleshell.LittleShell.desktop"
chmod 644 "$desktop_dir/org.littleshell.LittleShell.desktop"
rm -f -- "$desktop_dir/lish.desktop"

install -d "$app_dir/bin"
install -m 755 "$project_dir/bin/lish-open" "$app_dir/bin/lish-open"
install -m 755 "$project_dir/bin/lish-askpass" "$app_dir/bin/lish-askpass"
install -m 755 "$project_dir/bin/lish-copy-key" "$app_dir/bin/lish-copy-key"
if [ -e "$bin_dir/lish-open" ] && [ "$(readlink -- "$bin_dir/lish-open")" != "$app_dir/bin/lish-open" ]; then
  printf '%s\n' "Aviso: $bin_dir/lish-open já existe e não foi alterado." >&2
else
  ln -sfn "$app_dir/bin/lish-open" "$bin_dir/lish-open"
fi

cat > "$bin_dir/lish" <<EOF
#!/bin/sh
exec python3 "$app_dir/little_shell.py" "\$@"
EOF
chmod 755 "$bin_dir/lish"

if command -v desktop-file-validate >/dev/null; then
  desktop-file-validate "$desktop_dir/org.littleshell.LittleShell.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$desktop_dir" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$data_home/icons/hicolor" >/dev/null 2>&1 || true

printf '%s\n' "Instalado para a conta atual. Abra pelo menu ou execute: lish"
