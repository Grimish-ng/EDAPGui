"""
edap_linux.py

Linux (Proton/Steam) compatibility layer for EDAPGui.

Provides:
  - Proton prefix path resolution for ED (appid 359320):
      saved_games_dir(), bindings_dir(), graphics_options_dir(), player_options_dir()
  - WindowsKnownPaths-compatible shim: get_path(FOLDERID.SavedGames, UserHandle.current)
  - X11 window utilities (python-xlib): find_elite_window_rect(), activate_elite_window(),
    elite_window_exists()
  - Global hotkey shim (pynput) exposing keyboard-lib-compatible
    add_hotkey()/remove_all_hotkeys()

Requires X11 (native X session, or run inside gamescope's XWayland with
DISPLAY pointed at it). Pure-Wayland capture/injection is not supported here.
"""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache

ED_APPID = "359320"
ELITE_WINDOW_TITLE = "Elite - Dangerous (CLIENT)"

IS_LINUX = sys.platform.startswith("linux")


# ---------------------------------------------------------------------------
# Steam / Proton path resolution
# ---------------------------------------------------------------------------

def _steam_roots() -> list[str]:
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local/share/Steam"),
        os.path.join(home, ".steam/steam"),
        os.path.join(home, ".steam/root"),
        os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/Steam"),  # flatpak
    ]
    seen, roots = set(), []
    for c in candidates:
        r = os.path.realpath(c)
        if r not in seen and os.path.isdir(r):
            seen.add(r)
            roots.append(r)
    return roots


def _library_paths() -> list[str]:
    """All steam library roots, parsed from libraryfolders.vdf."""
    libs = []
    for root in _steam_roots():
        libs.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if not os.path.isfile(vdf):
            continue
        try:
            with open(vdf, "r", encoding="utf-8", errors="replace") as f:
                for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                    p = m.group(1).replace("\\\\", "\\").replace("\\", "/")
                    if os.path.isdir(p):
                        libs.append(p)
        except OSError:
            pass
    # dedupe, preserve order
    seen, out = set(), []
    for p in libs:
        r = os.path.realpath(p)
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


@lru_cache(maxsize=1)
def proton_prefix() -> str:
    """Path to .../steamapps/compatdata/359320/pfx for Elite Dangerous."""
    override = os.environ.get("EDAP_ED_PREFIX")
    if override:
        if os.path.isdir(override):
            return override
        raise FileNotFoundError(f"EDAP_ED_PREFIX set but not a directory: {override}")

    for lib in _library_paths():
        pfx = os.path.join(lib, "steamapps", "compatdata", ED_APPID, "pfx")
        if os.path.isdir(pfx):
            return pfx
    raise FileNotFoundError(
        "Elite Dangerous Proton prefix (compatdata/359320/pfx) not found in any "
        "Steam library. Run ED once via Proton, or set EDAP_ED_PREFIX."
    )


def _pfx_user() -> str:
    return os.path.join(proton_prefix(), "drive_c", "users", "steamuser")


def saved_games_dir() -> str:
    """.../Saved Games (parent of 'Frontier Developments/Elite Dangerous')."""
    return os.path.join(_pfx_user(), "Saved Games")


def journal_dir() -> str:
    return os.path.join(saved_games_dir(), "Frontier Developments", "Elite Dangerous")


def _local_appdata() -> str:
    return os.path.join(_pfx_user(), "AppData", "Local")


def bindings_dir() -> str:
    return os.path.join(_local_appdata(), "Frontier Developments",
                        "Elite Dangerous", "Options", "Bindings")


def graphics_options_dir() -> str:
    return os.path.join(_local_appdata(), "Frontier Developments",
                        "Elite Dangerous", "Options", "Graphics")


def player_options_dir() -> str:
    return os.path.join(_local_appdata(), "Frontier Developments",
                        "Elite Dangerous", "Options", "Player")


# ---------------------------------------------------------------------------
# WindowsKnownPaths shim (signature-compatible)
# ---------------------------------------------------------------------------

class FOLDERID:
    SavedGames = "SavedGames"
    LocalAppData = "LocalAppData"


class UserHandle:
    current = 0
    common = 1


def get_path(folderid, user_handle=UserHandle.current) -> str:
    if folderid == FOLDERID.SavedGames:
        return saved_games_dir()
    if folderid == FOLDERID.LocalAppData:
        return _local_appdata()
    raise NotImplementedError(f"edap_linux.get_path: unmapped FOLDERID {folderid!r}")


# ---------------------------------------------------------------------------
# X11 window utilities (python-xlib)
# ---------------------------------------------------------------------------

_display_name = None   # display that was last seen holding the ED window


def _candidate_displays():
    """$DISPLAY first, then every X socket on the machine."""
    import glob
    names = []
    env = os.environ.get("DISPLAY")
    if env:
        names.append(env)
    for p in sorted(glob.glob("/tmp/.X11-unix/X*")):
        n = ":" + p.rsplit("X", 1)[1]
        if n not in names:
            names.append(n)
    return names


def _display(name=None):
    from Xlib import display  # lazy: only needed at runtime on X11
    return display.Display(name or _display_name)


def _iter_client_windows(d):
    from Xlib import X, Xatom
    root = d.screen().root
    net_client_list = d.intern_atom("_NET_CLIENT_LIST")
    prop = root.get_full_property(net_client_list, Xatom.WINDOW)
    if prop is None:
        return
    for wid in prop.value:
        try:
            yield d.create_resource_object("window", wid)
        except Exception:
            continue


def _window_title(d, win) -> str:
    try:
        net_name = d.intern_atom("_NET_WM_NAME")
        utf8 = d.intern_atom("UTF8_STRING")
        prop = win.get_full_property(net_name, utf8)
        if prop and prop.value:
            v = prop.value
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
        name = win.get_wm_name()
        return name or ""
    except Exception:
        return ""


def _walk_windows(w):
    yield w
    try:
        for c in w.query_tree().children:
            yield from _walk_windows(c)
    except Exception:
        return


def _search_display(d):
    # Preferred: EWMH client list (real X window managers)
    for win in _iter_client_windows(d):
        if _window_title(d, win) == ELITE_WINDOW_TITLE:
            return win
    # Fallback: full tree walk. Required on KWin Wayland and gamescope,
    # whose Xwayland roots lack a usable _NET_CLIENT_LIST.
    for win in _walk_windows(d.screen().root):
        if _window_title(d, win) == ELITE_WINDOW_TITLE:
            return win
    return None


def _find_elite_window():
    """Search the cached display, then every display on the machine.
    On a hit, cache and export DISPLAY so capture/injection/automation
    downstream bind to the same X server the game is on."""
    global _display_name
    order = []
    if _display_name:
        order.append(_display_name)
    order += [n for n in _candidate_displays() if n not in order]
    for name in order:
        try:
            d = _display(name)
        except Exception:
            continue
        try:
            win = _search_display(d)
        except Exception:
            win = None
        if win is not None:
            if _display_name != name:
                _display_name = name
                os.environ["DISPLAY"] = name
            return d, win
        d.close()
    return None, None


def elite_window_exists() -> bool:
    d, win = _find_elite_window()
    if d:
        d.close()
    return win is not None


def find_elite_window_rect():
    """Returns (left, top, right, bottom) in root coordinates, or None."""
    d, win = _find_elite_window()
    if win is None:
        return None
    try:
        geom = win.get_geometry()
        # translate window origin to root coordinates
        coords = win.translate_coords(d.screen().root, 0, 0)
        # translate_coords(dst, x, y) gives coords of (x,y) in dst's space
        # from win's space when called as win.translate_coords(root,...).
        # Xlib returns negatives of what we want in some impls; use the
        # robust query: root-relative via query_tree walk instead.
        x, y = _root_position(d, win)
        return (x, y, x + geom.width, y + geom.height)
    finally:
        d.close()


def _root_position(d, win):
    root = d.screen().root
    x = y = 0
    w = win
    while True:
        geom = w.get_geometry()
        x += geom.x
        y += geom.y
        parent = w.query_tree().parent
        if parent == root or parent == 0:
            break
        w = parent
    return x, y


def activate_elite_window() -> bool:
    """Raise + focus the ED window via _NET_ACTIVE_WINDOW. Returns success."""
    from Xlib import X
    from Xlib.protocol import event as xevent

    d, win = _find_elite_window()
    if win is None:
        return False
    try:
        root = d.screen().root
        net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
        ev = xevent.ClientMessage(
            window=win,
            client_type=net_active,
            data=(32, [1, X.CurrentTime, 0, 0, 0]),
        )
        root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        d.flush()
        return True
    except Exception:
        return False
    finally:
        d.close()


def foreground_is_elite() -> bool:
    try:
        from Xlib import Xatom
        d = _display()
        try:
            root = d.screen().root
            net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
            prop = root.get_full_property(net_active, Xatom.WINDOW)
            if not prop or not prop.value:
                return False
            win = d.create_resource_object("window", prop.value[0])
            return _window_title(d, win) == ELITE_WINDOW_TITLE
        finally:
            d.close()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Global hotkeys via evdev
#
# pynput's Linux backend snoops keys through XRecord inside Xwayland, so on
# a Wayland desktop it only sees keystrokes that happen to be routed to X
# clients — hotkeys silently miss whenever focus is elsewhere. Reading
# /dev/input/event* directly is compositor-independent: works on Wayland,
# X11, and inside gamescope, regardless of window focus.
#
# Requires membership in the 'input' group (already required for uinput
# injection). EDAP's own virtual keyboard is excluded so injected keys can
# never trigger our own hotkeys.
#
# API surface is keyboard-lib compatible: add_hotkey(combo, cb, args=()),
# remove_all_hotkeys(). Combos use keyboard-lib syntax: 'home', 'pgup',
# 'ctrl+shift+x', ' ' (space).
# ---------------------------------------------------------------------------

class _EvdevHotkeys:
    _OWN_DEVICE = "edap-virtual-kbd"
    _RESCAN_S = 3.0

    # combo token -> acceptable keycode names (modifiers accept either side)
    _MODS = {
        "ctrl":  ("KEY_LEFTCTRL", "KEY_RIGHTCTRL"),
        "control": ("KEY_LEFTCTRL", "KEY_RIGHTCTRL"),
        "shift": ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"),
        "alt":   ("KEY_LEFTALT", "KEY_RIGHTALT"),
        "win":   ("KEY_LEFTMETA", "KEY_RIGHTMETA"),
        "windows": ("KEY_LEFTMETA", "KEY_RIGHTMETA"),
        "cmd":   ("KEY_LEFTMETA", "KEY_RIGHTMETA"),
        "super": ("KEY_LEFTMETA", "KEY_RIGHTMETA"),
    }
    _NAMES = {
        " ": "KEY_SPACE", "space": "KEY_SPACE",
        "pgup": "KEY_PAGEUP", "pageup": "KEY_PAGEUP", "page up": "KEY_PAGEUP",
        "pgdn": "KEY_PAGEDOWN", "pagedown": "KEY_PAGEDOWN", "page down": "KEY_PAGEDOWN",
        "ins": "KEY_INSERT", "insert": "KEY_INSERT",
        "del": "KEY_DELETE", "delete": "KEY_DELETE",
        "esc": "KEY_ESC", "escape": "KEY_ESC",
        "return": "KEY_ENTER", "enter": "KEY_ENTER",
        "up": "KEY_UP", "down": "KEY_DOWN", "left": "KEY_LEFT", "right": "KEY_RIGHT",
        "home": "KEY_HOME", "end": "KEY_END", "tab": "KEY_TAB",
        "backspace": "KEY_BACKSPACE",
    }

    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._hotkeys = []          # list of (mod_groups, keycode, callback)
        self._down = set()          # currently held keycodes, all devices
        self._thread = None
        self._stop = threading.Event()

    # -- combo parsing -------------------------------------------------------

    @classmethod
    def _resolve_key(cls, token: str) -> int:
        from evdev import ecodes
        t = token.strip().lower()
        name = cls._NAMES.get(t)
        if name is None:
            cand = f"KEY_{t.upper()}"
            if cand in ecodes.ecodes:
                name = cand
        if name is None:
            raise ValueError(f"Unknown hotkey token: {token!r}")
        return ecodes.ecodes[name]

    @classmethod
    def _parse(cls, combo: str):
        """'ctrl+shift+x' -> ([(LCTRL,RCTRL),(LSHIFT,RSHIFT)], KEY_X).
        A lone ' ' means space (split('+') would destroy it)."""
        from evdev import ecodes
        if combo.strip() == "" and " " in combo:
            return [], ecodes.ecodes["KEY_SPACE"]
        parts = [p for p in combo.split("+") if p.strip()]
        if not parts:
            raise ValueError(f"Empty hotkey combo: {combo!r}")
        mods = []
        for p in parts[:-1]:
            names = cls._MODS.get(p.strip().lower())
            if names is None:
                raise ValueError(f"Unknown modifier: {p!r}")
            mods.append(tuple(ecodes.ecodes[n] for n in names))
        return mods, cls._resolve_key(parts[-1])

    # -- public API (keyboard-lib compatible) --------------------------------

    def add_hotkey(self, combo, callback, args=()):
        mods, key = self._parse(combo)
        a = tuple(args)
        with self._lock:
            self._hotkeys.append((mods, key, (lambda cb=callback, aa=a: cb(*aa))))
        self._ensure_thread()

    def remove_all_hotkeys(self):
        with self._lock:
            self._hotkeys.clear()

    # -- event handling (separated for testability) --------------------------

    def _handle_key(self, code: int, value: int):
        from EDlogger import logger
        if value == 0:
            self._down.discard(code)
            return
        if value != 1:              # 2 = autorepeat; fire on initial press only
            return
        self._down.add(code)
        with self._lock:
            hks = list(self._hotkeys)
        for mods, key, cb in hks:
            if code != key:
                continue
            if all(any(m in self._down for m in group) for group in mods):
                try:
                    cb()
                except Exception as ex:
                    logger.error(f"hotkey callback failed: {ex}")

    # -- device management ----------------------------------------------------

    @classmethod
    def _is_keyboard(cls, dev) -> bool:
        from evdev import ecodes
        if dev.name == cls._OWN_DEVICE:
            return False
        keys = dev.capabilities().get(ecodes.EV_KEY)
        # heuristic: a real keyboard exposes the main letter block
        return bool(keys) and ecodes.KEY_A in keys and ecodes.KEY_Z in keys

    def _scan(self, sel, registered):
        import evdev
        for path in evdev.list_devices():
            if path in registered:
                continue
            try:
                dev = evdev.InputDevice(path)
                if self._is_keyboard(dev):
                    sel.register(dev, 1)
                    registered[path] = dev
                else:
                    dev.close()
            except (OSError, PermissionError):
                continue

    def _loop(self):
        import selectors
        import time as _time
        from evdev import ecodes
        from EDlogger import logger
        sel = selectors.DefaultSelector()
        registered = {}
        self._scan(sel, registered)
        if not registered:
            logger.warning("evdev hotkeys: no keyboard devices readable — "
                           "check 'input' group membership.")
        last_scan = _time.monotonic()
        while not self._stop.is_set():
            for skey, _ in sel.select(timeout=1.0):
                dev = skey.fileobj
                try:
                    for ev in dev.read():
                        if ev.type == ecodes.EV_KEY:
                            self._handle_key(ev.code, ev.value)
                except OSError:            # device unplugged
                    sel.unregister(dev)
                    registered.pop(dev.path, None)
                    try:
                        dev.close()
                    except OSError:
                        pass
            if _time.monotonic() - last_scan > self._RESCAN_S:
                self._scan(sel, registered)
                last_scan = _time.monotonic()

    def _ensure_thread(self):
        import threading
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop,
                                            name="evdev-hotkeys", daemon=True)
            self._thread.start()


hotkeys = _EvdevHotkeys()
add_hotkey = hotkeys.add_hotkey
remove_all_hotkeys = hotkeys.remove_all_hotkeys



# ---------------------------------------------------------------------------
# XComposite window capture
#
# Under rootless Xwayland (Plasma Wayland session) the X root window has no
# grabbable contents: XGetImage on the root fails with BadMatch, so mss
# cannot capture. The ED window itself, however, is composited and has a
# backing pixmap. XComposite NameWindowPixmap gives us that pixmap and
# XGetImage on it works — same mechanism as OBS xcomposite capture.
# ---------------------------------------------------------------------------

class EliteWindowGrabber:
    """Grabs regions of the ED window via XComposite. Coordinates passed to
    grab() are ROOT (screen) coordinates, matching what Screen.py computes
    from mss monitor geometry; they are translated to window-relative."""

    def __init__(self):
        self.d = None
        self.win = None
        self.pixmap = None
        self.win_x = 0
        self.win_y = 0
        self._acquire()

    def _acquire(self):
        self.close()
        from Xlib.ext import composite
        d, win = _find_elite_window()
        if win is None:
            raise RuntimeError(f"'{ELITE_WINDOW_TITLE}' window not found")
        if not d.has_extension('Composite'):
            raise RuntimeError("X server lacks the Composite extension")
        d.composite_query_version()
        win.composite_redirect_window(composite.RedirectAutomatic)
        d.sync()
        self.d = d
        self.win = win
        self.pixmap = win.composite_name_window_pixmap()
        self.win_x, self.win_y = _root_position(d, win)
        g = win.get_geometry()
        self.win_w, self.win_h = g.width, g.height

    def close(self):
        if self.pixmap is not None:
            try:
                self.pixmap.free()
            except Exception:
                pass
            self.pixmap = None
        if self.d is not None:
            try:
                self.d.close()
            except Exception:
                pass
            self.d = None

    def grab(self, left, top, width, height):
        """Returns a (h, w, 4) uint8 BGRA numpy array (mss-compatible),
        for the region given in root coordinates."""
        import numpy as np
        from Xlib import X

        for attempt in (0, 1):
            try:
                x = int(left) - self.win_x
                y = int(top) - self.win_y
                w, h = int(width), int(height)
                # clamp to window bounds; GetImage outside them is BadMatch
                x = max(0, min(x, self.win_w - 1))
                y = max(0, min(y, self.win_h - 1))
                w = max(1, min(w, self.win_w - x))
                h = max(1, min(h, self.win_h - y))
                img = self.pixmap.get_image(x, y, w, h, X.ZPixmap, 0xffffffff)
                buf = img.data
                if isinstance(buf, str):
                    buf = buf.encode('latin-1')
                arr = np.frombuffer(buf, dtype=np.uint8)
                return arr.reshape(h, w, 4).copy()
            except Exception:
                if attempt == 1:
                    raise
                # pixmap invalidated (window resized/remapped) — re-acquire once
                self._acquire()


_grabber = None

def grab_region(left, top, width, height):
    """Module-level convenience wrapper with lazy singleton grabber."""
    global _grabber
    if _grabber is None:
        _grabber = EliteWindowGrabber()
    return _grabber.grab(left, top, width, height)


if __name__ == "__main__":
    print("proton prefix :", proton_prefix())
    print("journal dir   :", journal_dir())
    print("bindings dir  :", bindings_dir())
    print("graphics dir  :", graphics_options_dir())
    print("ED window     :", find_elite_window_rect())
    try:
        img = grab_region(*(lambda r: (r[0], r[1], r[2]-r[0], r[3]-r[1]))(find_elite_window_rect()))
        print(f"capture       : shape={img.shape} mean={img.mean():.1f} max={img.max()}")
    except Exception as ex:
        print("capture       : FAILED -", ex)
