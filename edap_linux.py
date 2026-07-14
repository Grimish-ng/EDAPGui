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

def _display():
    from Xlib import display  # lazy: only needed at runtime on X11
    return display.Display()


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


def _find_elite_window():
    d = _display()
    # Preferred: EWMH client list (real X window managers)
    for win in _iter_client_windows(d):
        if _window_title(d, win) == ELITE_WINDOW_TITLE:
            return d, win
    # Fallback: full tree walk. Required on KWin/Plasma Wayland, where the
    # rootless Xwayland root does not carry a usable _NET_CLIENT_LIST.
    for win in _walk_windows(d.screen().root):
        if _window_title(d, win) == ELITE_WINDOW_TITLE:
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
# Global hotkey shim: keyboard-lib-compatible surface backed by pynput
# ---------------------------------------------------------------------------

class _Hotkeys:
    """Drop-in for the subset of the `keyboard` module EDAPGui uses:
       add_hotkey(combo, fn, args=()) / remove_all_hotkeys().
       Combo strings use keyboard-lib syntax ('end', 'home', 'pgup',
       'ctrl+shift+x'); converted to pynput ('<end>', '<ctrl>+<shift>+x')."""

    _NAME_MAP = {
        "pgup": "page_up", "pageup": "page_up", "page up": "page_up",
        "pgdn": "page_down", "pagedown": "page_down", "page down": "page_down",
        "ins": "insert", "del": "delete", "esc": "esc",
        "return": "enter", "windows": "cmd", "win": "cmd",
    }

    def __init__(self):
        self._listener = None
        self._map = {}

    @classmethod
    def _to_pynput(cls, combo: str) -> str:
        parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
        out = []
        for p in parts:
            p = cls._NAME_MAP.get(p, p)
            out.append(p if len(p) == 1 else f"<{p}>")
        return "+".join(out)

    def add_hotkey(self, combo, callback, args=()):
        key = self._to_pynput(combo)
        self._map[key] = (lambda cb=callback, a=tuple(args): cb(*a))
        self._restart()

    def remove_all_hotkeys(self):
        self._map.clear()
        self._restart()

    def _restart(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if not self._map:
            return
        from pynput import keyboard as pk
        self._listener = pk.GlobalHotKeys(dict(self._map))
        self._listener.daemon = True
        self._listener.start()


hotkeys = _Hotkeys()
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
