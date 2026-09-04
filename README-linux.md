# EDAPGui on Linux (Proton)

A Linux port of [SumZer0-git/EDAPGui](https://github.com/SumZer0-git/EDAPGui).
Elite Dangerous runs under Proton; the autopilot runs natively.

Upstream is Windows-only. This fork replaces the Windows-specific layers —
input injection, screen capture, filesystem paths, global hotkeys — with
Linux equivalents, kept as a small commit series on top of upstream so it
stays rebaseable.

## Status

| Component | State |
|---|---|
| Key injection (uinput) | Working, flight-tested |
| Screen capture (XComposite) | Working on X11 and Plasma Wayland |
| Proton prefix paths (journal, binds, graphics/player settings) | Working |
| Global hotkeys (evdev) | Working, focus- and compositor-independent |
| OCR | Working; fixes an upstream thread-affinity bug |
| Headless daemon + control API | Working |
| In-game overlay | Stubbed (no-op on Linux) |
| Capture inside a gamescope session | **Not working** — see Known limits |

Flight-tested on Arch/CachyOS, Plasma Wayland, Ryzen 9 7945HX + RX 7600M XT:
15 consecutive FSD route-assist jumps followed by docking.

## Branches

- **`linux-port`** — the working port. Use this one.
- **`capture-pipewire`** — experimental PipeWire capture backend
  (`edap_capture.py`) intended for gamescope sessions. Untested and
  currently blocked; see Known limits.

## Requirements

- Elite Dangerous installed via Steam/Proton (appid 359320), run at least once
- Python 3.12 — 3.13+ has no wheels for the pinned dependency set
- Membership in the `input` group plus a udev rule for `/dev/uinput`
  (both handled by `setup-linux.sh`)
- An X11 session or Plasma Wayland; **not** a gamescope session

## Install (Arch / CachyOS)

```bash
git clone <this-fork-url> EDAPGui && cd EDAPGui
git checkout linux-port
./setup-linux.sh
```

Re-login (or `newgrp input`) so the group membership applies, then verify
with Elite Dangerous running:

```bash
ls -l /dev/uinput                     # crw-rw---- root input
.venv/bin/python edap_linux.py        # Proton paths, ED window rect, capture test
```

The final line should report a capture with a sane shape and a non-zero,
non-saturated mean. Then:

```bash
.venv/bin/python EDAPGui.py
```

### Manual environment notes

`setup-linux.sh` builds the venv with `uv` on Python 3.12 and with
`--system-site-packages`. If you build it by hand, note that `pyautogui`
depends on `python3-xlib`, a dead fork that installs into the same `Xlib/`
directory as `python-xlib` and overwrites it with a broken Composite
extension — which breaks screen capture. Evict it after installing:

```bash
uv pip uninstall python3-xlib
uv pip install --reinstall python-xlib==0.33
```

## Configuration

As upstream: `configs/`, plus the in-app settings and calibration. Elite
Dangerous itself must be set to **Borderless** at your native resolution,
with default HUD colours and Interface Brightness at maximum.

Note that upstream's templates were captured at 3440x1440, so the X/Y
scale values in your config matter; run the GUI's calibration for your
resolution.

Environment overrides:

| Variable | Effect |
|---|---|
| `EDAP_ED_PREFIX` | Path to the Proton prefix, if auto-discovery fails |
| `EDAP_CONTROL_PORT` | Daemon control API port (default 15580) |

On the `capture-pipewire` branch only, `EDAP_CAPTURE`
(`auto`/`xcomposite`/`pipewire`) and `EDAP_PIPEWIRE_NODE` select the
capture backend.

## Headless daemon

`edap_daemon.py` runs the engine without the GUI and exposes a
line-delimited JSON API on `127.0.0.1:15580`, alongside upstream's EDMesg
(zmq) server.

```bash
cp edap-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now edap-daemon

./edapctl status
./edapctl start fsd
./edapctl stop_all
```

Commands: `status`, `ping`, `start`/`stop` with an assist name
(`fsd`, `sc`, `waypoint`, `robigo`, `afk`, `dss`), `stop_all`, and
`load_waypoints <path>`.

The daemon waits for the ED window before constructing the engine, so it
can be enabled at login and left idle until the game starts. Calibration
still requires the GUI (it uses a Tk dialog); the daemon reads the same
config afterwards.

Do not run `edap_daemon.py` by hand while the service is active — the
second instance cannot bind the control port and systemd will restart it
in a loop.

## What changed, and why

**Input injection — `directinput.py`.** Windows `SendInput` is replaced
with an evdev/uinput virtual keyboard. DirectInput scancodes are AT set 1,
identical to Linux input keycodes across the whole main block
(`0x01`–`0x58`); only the `0xE0`-prefixed extended keys need an explicit
map. Injecting at the uinput layer means Wine/Proton translates events
back into exactly the scancodes the game expects — no XTEST, no
keyboard-layout dependency.

**Screen capture — `edap_linux.py`, `Screen.py`.** Under rootless Xwayland
the X root window has no grabbable contents: `XGetImage` on it fails with
`BadMatch`, so `mss` cannot be used. Instead the ED window is
composite-redirected and its backing pixmap is read via XComposite
`NameWindowPixmap` — the same mechanism as OBS's xcomposite capture.
Frames come back as BGRA arrays byte-identical in layout to what `mss`
produced, so nothing downstream changed.

**Window discovery — `edap_linux.py`.** KWin's Xwayland root does not carry
a usable `_NET_CLIENT_LIST`, so the EWMH lookup falls back to a full
`query_tree` walk. Which X display holds the game also varies by session,
so every display in `/tmp/.X11-unix` is searched and `DISPLAY` is exported
to match the one the game is on.

**Paths — `WindowsKnownPaths.py`, `EDKeys.py`, `EDJournal.py`,
`EDGraphicsSettings.py`, `EDPlayerSettings.py`, the parsers.** On Linux
`WindowsKnownPaths` becomes a shim resolving into the Proton prefix, found
by parsing `libraryfolders.vdf` across every Steam library. Journal,
`.binds`, and graphics/player option files all resolve from there.

**Global hotkeys — `edap_linux.py`.** The `keyboard` library requires root
on Linux, and pynput's X backend snoops via XRecord inside Xwayland, so on
Wayland it only sees keys routed to X clients — hotkeys miss depending on
focus. Reading `/dev/input/event*` directly through evdev is compositor-
and focus-independent. EDAP's own virtual keyboard is excluded from the
scan so injected keys cannot trigger its own hotkeys. Because hotkeys are
observed rather than consumed, keep EDAP's keys (Home/End/PageUp/Insert)
unbound in Elite Dangerous, or use modifier combos such as `ctrl+home`.

**OCR thread affinity — `OCR.py`.** Upstream calls PaddleOCR from both the
autopilot thread and the supercruise monitor thread. Paddle's predictor has
thread *affinity* (oneDNN state binds to the creating thread), not merely a
lack of thread safety, so cross-thread calls throw `std::exception` on
perfectly valid images — which upstream papers over by reinitializing the
whole predictor. Here a dedicated worker thread owns the predictor and
performs all construction, prediction and reinitialization; callers submit
jobs over a queue. A brightness gate additionally skips the expensive
predict when a region contains no bright pixels, which is most of the time
in the supercruise disengage poll loop.

This one is not Linux-specific — the same race exists on Windows, it just
fires less often.

**Star-import fallout — `ED_AP.py`.** `ctypes` and `datetime` reached
`ED_AP` only via `from directinput import *`. Moving the Windows-only
imports behind a platform guard broke that leak, so both are now imported
explicitly.

**Overlay — `Overlay.py`.** The win32 layered-window overlay has no Linux
equivalent here; a no-op class with the same public surface is selected on
non-Windows platforms.

## Known limits

- **Gamescope sessions**: gamescope composites and scans out client buffers
  itself, so the X backing pixmap is allocated but never painted —
  XComposite capture returns a blank (solid white) frame and the autopilot
  flies blind. The `capture-pipewire` branch adds a PipeWire backend for
  this case, but gamescope must publish a `Video/Source` node for it to
  read, and the build tested here exposes no flag to enable one. **Run
  EDAP from a normal desktop session.**
- **In-game overlay** is a no-op; use the GUI window, the daemon status
  API, or voice output instead.
- **Galaxy map text entry** still goes through `pyautogui`/XTEST and is
  keyboard-layout sensitive.
- **YOLO/torch** installs the CUDA build by default and runs on CPU here.
  For GPU inference on AMD: `uv pip install torch torchvision
  --index-url https://download.pytorch.org/whl/rocm6.2` (Navi 33 may need
  `HSA_OVERRIDE_GFX_VERSION=11.0.2`). PaddleOCR stays on CPU regardless.

## Credits

Upstream project and all autopilot logic: **SumZer0-git/EDAPGui** and its
contributors. This fork only ports the platform layers. Licensed under the
same terms as upstream.
