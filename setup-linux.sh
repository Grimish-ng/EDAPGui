#!/usr/bin/env bash
# EDAPGui Linux (Arch/CachyOS) setup
set -euo pipefail

# --- system packages ---------------------------------------------------------
sudo pacman -S --needed --noconfirm \
    python python-pip tk espeak-ng ux xdotool base-devel

# --- uinput access (virtual keyboard for key injection into Proton) ----------
# Root cause: /dev/uinput is root:root 0600 by default. Grant the 'input'
# group rw access; do NOT run EDAP as root.
sudo tee /etc/udev/rules.d/99-edap-uinput.rules >/dev/null <<'EOF'
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
EOF
echo uinput | sudo tee /etc/modules-load.d/edap-uinput.conf >/dev/null
sudo modprobe uinput
sudo udevadm control --reload && sudo udevadm trigger /dev/uinput || true
sudo usermod -aG input "$USER"

# --- python venv --------------------------------------------------------------
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements-linux.txt

cat <<'MSG'

Done. NOTES:
  1. Re-login (or `newgrp input`) for the input group to take effect.
  2. Verify:   ls -l /dev/uinput      -> crw-rw---- root input
  3. Run ED once via Steam/Proton so compatdata/359320/pfx exists.
  4. Sanity check paths + window detection (with ED running):
        .venv/bin/python edap_linux.py
  5. Launch:   .venv/bin/python EDAPGui.py
     Must run inside an X11 session (or with DISPLAY pointing at
     gamescope's XWayland) — mss capture does not work on pure Wayland.
MSG
