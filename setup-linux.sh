#!/usr/bin/env bash
# EDAPGui Linux (Arch / CachyOS) setup
#
# Builds the environment that is actually known to work:
#   - venv on Python 3.12 (3.13+ has no wheels for the pinned deps;
#     a source build of numpy/paddle fails)
#   - system site-packages visible, so python-gobject (gi) can be used
#     by the optional PipeWire capture backend
#   - python3-xlib evicted after install (see note below)
#   - /dev/uinput access for the virtual keyboard used to drive the game
set -euo pipefail

cd "$(dirname "$0")"

# --- system packages ---------------------------------------------------------
sudo pacman -S --needed --noconfirm \
    uv tk espeak-ng xdotool base-devel

# --- uinput access (virtual keyboard for key injection into Proton) ----------
# /dev/uinput is root:root 0600 by default. Grant the 'input' group access;
# do NOT run EDAP as root.
sudo tee /etc/udev/rules.d/99-edap-uinput.rules >/dev/null <<'EOF'
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
EOF
echo uinput | sudo tee /etc/modules-load.d/edap-uinput.conf >/dev/null
sudo modprobe uinput
sudo udevadm control --reload && sudo udevadm trigger /dev/uinput || true
sudo usermod -aG input "$USER"

# --- python environment -------------------------------------------------------
rm -rf .venv
uv venv --python 3.12 --system-site-packages .venv
uv pip install --python .venv/bin/python -r requirements-linux.txt

# pyautogui depends on python3-xlib, a dead fork that installs into the same
# Xlib/ package directory as python-xlib and overwrites it with a version
# whose Composite extension is broken (breaks screen capture). Remove it and
# restore python-xlib. Order matters: uninstalling deletes shared files.
uv pip uninstall --python .venv/bin/python python3-xlib || true
uv pip install --python .venv/bin/python --reinstall python-xlib==0.33

cat <<'MSG'

Done. NEXT STEPS:
  1. Re-login (or run `newgrp input`) so the 'input' group takes effect.
  2. Verify:   ls -l /dev/uinput      -> crw-rw---- root input
  3. Run Elite Dangerous once via Steam/Proton so the prefix exists
     (steamapps/compatdata/359320/pfx).
  4. With ED running, check paths, window detection and capture:
        .venv/bin/python edap_linux.py
     The last line should report a capture with a non-zero mean.
  5. Launch:   .venv/bin/python EDAPGui.py

  Run from a normal desktop session (X11 or Plasma Wayland).
  Capture does not work inside a gamescope session - see README-linux.md.
MSG
