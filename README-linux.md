# EDAPGui on Linux (Proton)

A Linux port of [SumZer0-git/EDAPGui](https://github.com/SumZer0-git/EDAPGui).
Elite Dangerous runs under Proton; the autopilot runs natively.

Upstream is Windows-only. This fork replaces the Windows-specific layers —
input injection, screen capture, filesystem paths, global hotkeys — with
Linux equivalents, and keeps the changes as a small commit series on top
of upstream so it stays rebaseable.

## Status

| Component | State |
|---|---|
| Key injection (uinput) | Working, flight-tested |
| Screen capture (XComposite) | Working on X11 and Plasma Wayland |
| Proton prefix paths (journal, binds, graphics settings) | Working |
| Global hotkeys (evdev) | Working, focus- and compositor-independent |
| OCR | Working, with an upstream thread-affinity bug fixed |
| Headless daemon + control API | Working |
| Decky Loader plugin | Working (start/stop/status) |
| In-game overlay | Stubbed (no-op on Linux) |
| Capture inside a gamescope session | **Not working** — see Known limits |

Flight-tested on Arch/CachyOS, Plasma Wayland, Ryzen 9 7945HX + RX 7600M XT:
15 consecutive FSD route-assist jumps and docking.

## Requirements

- Elite Dangerous installed via Steam/Proton (appid 359320), run at least once
- Python 3.12 (3.13+ lacks wheels for the pinned dependency set)
- Membership in the `input` group, and a udev rule granting access to `/dev/uinput`
- An X11 session, or Plasma Wayland (capture goes through the game's Xwayland window)

## Install (Arch / CachyOS)

```bash
git clone <this-fork> EDAPGui && cd EDAPGui
git checkout linux-port
./setup-linux.sh          # system packages, udev rule, input group, venv
```

Re-login (or `newgrp input`) so the group takes effect, then verify:

```bash
ls -l /dev/uinput                     # crw-rw---- root input
.venv/bin/python edap_linux.py        # prints Proton paths, ED window rect, capture test
```

With ED running, that self-test should end with a capture line showing a
sane shape and a non-zero mean. Then:

```bash
.venv/bin/python EDAPGui.py
```

`setup-linux.sh` builds the venv with `uv` on Python 3.12. If you build it
by hand, note that `pyautogui` pulls in `python3-xlib`, a dead fork that
overwrites `python-xlib`'s `Xlib/` package with a broken Composite
extension. Evict it:

```bash
uv pip uninstall python3-xlib
uv pip install --reinstall python-xlib==0.33
```

## Configuration

Same as upstream (`configs/`, in-app settings). ED itself must be set to
**Borderless** at your native resolution, with default HUD colours and
Interface Brightness at maximum.

Environment overrides:

| Variable | Effect |
|---|---|
| `EDAP_ED_PREFIX` | Path to the Proton prefix, if auto-discovery fails |
| `EDAP_CAPTURE` | `auto` (default), `xcomposite`, or `pipewire` |
| `EDAP_PIPEWIRE_NODE` | PipeWire node id, skipping discovery |
| `EDAP_CONTROL_PORT` | Daemon control API port (default 15580) |

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
(`fsd`, `sc`, `waypoint`, `robigo`, `afk`, `dss`), `stop_all`,
`load_waypoints`.

The daemon waits for the ED window before starting the engine, so it can
be enabled at login and left idle.

A Decky Loader plugin (`decky-edap`) is included; it is a thin client of
this API, so the daemon must be running for its buttons to work.

## What changed, and why

**Input injection — `directinput.py`.** Windows `SendInput` is replaced
with an evdev/uinput virtual keyboard. DirectInput scancodes are AT set 1,
identical to Linux input keycodes across the whole main block
(`0x01`–`0x58`); only the `0xE0`-prefixed extended keys need an explicit
map. Injecting at the uinput layer means Wine/Proton translates events
back into exactly the scancodes the game expects — no XTEST, and no
keyboard-layout dependency.

**Screen capture — `edap_linux.py`, `edap_capture.py`.** Under rootless
Xwayland the X root window has no grabbable contents; `XGetImage` on it
fails with `BadMatch`, so `mss` cannot be used. Instead the ED window is
composite-redirected and its backing pixmap read via XComposite
`NameWindowPixmap` — the same mechanism as OBS's xcomposite capture.
Frames come back as BGRA arrays byte-identical in layout to what `mss`
produced, so nothing downstream changed.

**Window discovery.** KWin's Xwayland root does not carry a usable
`_NET_CLIENT_LIST`, so the EWMH lookup falls back to a full `query_tree`
walk. Which X display holds the game also varies by session, so all
displays in `/tmp/.X11-unix` are searched and `DISPLAY` is exported to
match the one the game is on.

**Paths — `WindowsKnownPaths.py`, parsers.** On Linux this becomes a shim
that resolves into the Proton prefix, discovered by parsing
`libraryfolders.vdf` across every Steam library. Journal, `.binds`, and
graphics/player option files all resolve from there.

**Global hotkeys — `edap_linux.py`.** The `keyboard` library requires root
on Linux, and pynput's X backend snoops via XRecord inside Xwayland, so on
Wayland it only sees keys routed to X clients — hotkeys silently miss
depending on focus. Reading `/dev/input/event*` directly through evdev is
compositor- and focus-independent. EDAP's own virtual keyboard is excluded
from the scan so injected keys cannot trigger its own hotkeys.

**OCR thread affinity — `OCR.py`.** Upstream calls PaddleOCR from both the
autopilot thread and the supercruise monitor thread. Paddle's predictor
has thread *affinity* (oneDNN state binds to the creating thread), not
merely a lack of thread safety, so cross-thread calls throw
`std::exception` on perfectly valid images — which upstream papers over by
reinitializing the whole predictor. Here a dedicated worker thread owns the
predictor and performs all construction, prediction, and reinitialization;
callers submit jobs over a queue. A brightness gate also skips the
expensive predict when the region contains no bright pixels, which is most
of the time in the supercruise poll loop.

This one is not Linux-specific — the same race exists on Windows, it just
fires less often.

## Known limits

- **Gamescope sessions**: gamescope composites and scans out client buffers
  itself, so the X backing pixmap is allocated but never painted —
  XComposite capture returns a blank (solid white) frame and the autopilot
  flies blind. A PipeWire capture backend exists as a scaffold on the
  `capture-pipewire` branch, but gamescope must publish a `Video/Source`
  node for it to have anything to read, and the tested build exposes no
  such flag. **Run EDAP from a normal desktop session.**
- **In-game overlay** is a no-op; use the GUI window, the daemon status
  API, or voice output instead.
- **Galaxy map text entry** still goes through `pyautogui`/XTEST and is
  keyboard-layout sensitive.
- Calibration is done from the GUI (it uses a Tk dialog); the daemon reads
  the same config afterwards.

## Credits

Upstream project and all autopilot logic: **SumZer0-git/EDAPGui** and its
contributors. This fork only ports the platform layers. Licensed under the
same terms as upstream.
