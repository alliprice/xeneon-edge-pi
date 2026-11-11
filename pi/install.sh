#!/usr/bin/env bash
# Sets up a Raspberry Pi as the display computer. Run it on the Pi, as the
# user who will be logged in on the screen, from a checkout of this
# repository:
#
#     pi/install.sh --dry-run    # print each step, change nothing
#     pi/install.sh
#
# For Raspberry Pi OS Lite (64-bit). Safe to run again.
set -euo pipefail

DRY=0
case "${1:-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  *) echo "usage: pi/install.sh [--dry-run]" >&2; exit 2 ;;
esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$HOME/.config/xeneon-edge-pi"
SWAY_CONFIG="$HOME/.config/sway/config"
UNIT="$HOME/.config/systemd/user/xeneon-buttons.service"
PROFILE="$HOME/.bash_profile"
# shellcheck disable=SC2016  # the line is written to the profile unexpanded
START_LINE='[ "$(tty)" = /dev/tty1 ] && exec sway  # xeneon-edge-pi'

step() { printf '\n== %s\n' "$*"; }
run() {
  printf '   %s\n' "$*"
  if [ "$DRY" -eq 0 ]; then "$@"; fi
}
# write FILE: replaces FILE with stdin.
write() {
  printf '   write %s\n' "$1"
  if [ "$DRY" -eq 1 ]; then cat >/dev/null; return; fi
  mkdir -p "$(dirname "$1")"
  cat >"$1"
}
# copy_once SRC DEST MODE: copies only if DEST does not exist.
copy_once() {
  if [ -e "$2" ]; then
    printf '   keep %s\n' "$2"
  else
    run install -D -m "$3" "$1" "$2"
  fi
}

step "Packages"
run sudo apt-get update
if apt-cache show chromium >/dev/null 2>&1; then CHROMIUM=chromium; else CHROMIUM=chromium-browser; fi
run sudo apt-get install -y sway "$CHROMIUM" python3 fonts-quicksand

step "Log in on the console at boot"
if command -v raspi-config >/dev/null 2>&1; then
  run sudo raspi-config nonint do_boot_behaviour B2
else
  echo "   raspi-config not found: set console autologin for $USER yourself"
fi

step "Start sway on the first console"
if grep -qF "# xeneon-edge-pi" "$PROFILE" 2>/dev/null; then
  printf '   keep %s\n' "$PROFILE"
else
  printf '   append to %s\n' "$PROFILE"
  if [ "$DRY" -eq 0 ]; then printf '%s\n' "$START_LINE" >>"$PROFILE"; fi
fi

step "Configuration in $CONFIG"
copy_once "$REPO/kiosk/tiles.example.toml" "$CONFIG/tiles.toml" 644
copy_once "$REPO/buttons/buttons.example.toml" "$CONFIG/buttons.toml" 600

step "sway"
write "$SWAY_CONFIG" <<EOF
# Written by xeneon-edge-pi's pi/install.sh; it is replaced on each run.
include $REPO/kiosk/sway.config
exec python3 $REPO/kiosk/launch.py --config $CONFIG/tiles.toml
EOF

step "Buttons server"
write "$UNIT" <<EOF
[Unit]
Description=Home Assistant buttons page for the Xeneon Edge

[Service]
ExecStart=/usr/bin/python3 $REPO/buttons/server.py --config $CONFIG/buttons.toml
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
run systemctl --user daemon-reload
run systemctl --user enable xeneon-buttons.service
run systemctl --user restart xeneon-buttons.service

step "Done"
cat <<EOF
   Edit $CONFIG/tiles.toml and $CONFIG/buttons.toml,
   then reboot. Check the layout with:
     python3 $REPO/kiosk/launch.py --config $CONFIG/tiles.toml --check
EOF
