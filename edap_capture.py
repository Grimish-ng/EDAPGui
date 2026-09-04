"""
edap_capture.py — pluggable screen-capture backends for EDAP on Linux.

Backends
--------
xcomposite : reads the ED window's composited backing pixmap via XComposite.
             Correct under KWin/Plasma (X11 or Wayland). Fails under
             gamescope, which is its own compositor and scans client
             buffers out directly — NameWindowPixmap yields an allocated
             but unpainted pixmap (observed: solid white, mean=255).

pipewire   : consumes gamescope's composited output as a PipeWire video
             stream via GStreamer (pipewiresrc -> videoconvert -> appsink,
             BGRA). This is the same mechanism OBS uses to record a
             gamescope session, so it sees real frames.

Selection
---------
EDAP_CAPTURE=auto (default) : try xcomposite; if its frames fail the
                              blank-frame check, fall back to pipewire.
EDAP_CAPTURE=xcomposite     : force XComposite (previous behaviour).
EDAP_CAPTURE=pipewire       : force PipeWire.
EDAP_PIPEWIRE_NODE=<id>     : skip node discovery, use this PipeWire node.

Every backend returns the same thing the old code did: a (h, w, 4) uint8
BGRA numpy array for the requested region in root coordinates.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time

import numpy as np

try:
    from EDlogger import logger
except Exception:                                    # standalone use
    import logging
    logger = logging.getLogger("edap_capture")


# ---------------------------------------------------------------------------
# Frame sanity
# ---------------------------------------------------------------------------

def looks_blank(img) -> bool:
    """True if a frame carries no usable image content.

    Catches the gamescope XComposite failure (uniform white) and the
    unmapped-window case (uniform black). Uses spread rather than mean:
    a real ED frame — even a dark starfield or a bright station — always
    has structure, so its std is far above this floor.
    """
    if img is None or img.size == 0:
        return True
    sample = img[..., :3]
    if sample.shape[0] > 64:                         # cheap subsample
        sample = sample[::max(1, sample.shape[0] // 64)]
    return float(sample.std()) < 2.0


# ---------------------------------------------------------------------------
# XComposite backend (existing behaviour, unchanged semantics)
# ---------------------------------------------------------------------------

class XCompositeBackend:
    name = "xcomposite"

    def __init__(self):
        import edap_linux
        self._grabber = edap_linux.EliteWindowGrabber()

    def grab(self, left, top, width, height):
        return self._grabber.grab(left, top, width, height)

    def close(self):
        try:
            self._grabber.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# PipeWire backend
# ---------------------------------------------------------------------------

def discover_pipewire_node():
    """Find gamescope's video output node id via pw-dump.

    Returns an int node id, or None. Honours EDAP_PIPEWIRE_NODE.
    """
    env = os.environ.get("EDAP_PIPEWIRE_NODE")
    if env:
        return int(env)
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True,
                             timeout=10).stdout
        objs = json.loads(out)
    except Exception as ex:
        logger.warning(f"pw-dump failed: {ex}")
        return None

    best = None
    for o in objs:
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        props = (o.get("info") or {}).get("props") or {}
        media_class = str(props.get("media.class", ""))
        if "Video/Source" not in media_class:
            continue
        blob = " ".join(str(props.get(k, "")) for k in
                        ("node.name", "node.description", "application.name",
                         "media.name")).lower()
        score = 0
        if "gamescope" in blob:
            score = 2
        elif "screen" in blob or "desktop" in blob:
            score = 1
        if score and (best is None or score > best[0]):
            best = (score, o.get("id"))
    if best:
        logger.info(f"PipeWire video node selected: {best[1]}")
        return best[1]
    logger.warning("No PipeWire Video/Source node found. Is gamescope "
                   "running with PipeWire output enabled?")
    return None


class PipeWireBackend:
    """GStreamer pipewiresrc -> appsink. Keeps only the newest frame;
    grab() crops from it, so region grabs cost a memcpy, not a round trip."""

    name = "pipewire"

    def __init__(self, node_id=None, timeout=10.0):
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        self._Gst = Gst
        if not Gst.is_initialized():
            Gst.init(None)

        self._frame = None
        self._frame_lock = threading.Lock()
        self._have_frame = threading.Event()

        node_id = node_id if node_id is not None else discover_pipewire_node()
        src = "pipewiresrc" + (f" path={node_id}" if node_id is not None else "")
        desc = (f"{src} ! videoconvert ! video/x-raw,format=BGRA ! "
                f"appsink name=sink emit-signals=true max-buffers=1 drop=true "
                f"sync=false")
        self._pipeline = Gst.parse_launch(desc)
        sink = self._pipeline.get_by_name("sink")
        sink.connect("new-sample", self._on_sample)
        self._pipeline.set_state(Gst.State.PLAYING)

        if not self._have_frame.wait(timeout):
            self.close()
            raise RuntimeError(
                f"No PipeWire frame within {timeout}s (node={node_id}). "
                f"Check that a Video/Source node exists (pw-dump) and that "
                f"GStreamer's pipewire plugin is installed.")

    def _on_sample(self, sink):
        Gst = self._Gst
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK
        buf = sample.get_buffer()
        caps = sample.get_caps().get_structure(0)
        w, h = caps.get_value("width"), caps.get_value("height")
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if ok:
            try:
                arr = np.frombuffer(mapinfo.data, dtype=np.uint8)
                # stride may exceed w*4; trim per row if so
                if arr.size >= h * w * 4:
                    stride = arr.size // h
                    arr = arr[:h * stride].reshape(h, stride)[:, :w * 4]
                    frame = arr.reshape(h, w, 4).copy()
                    with self._frame_lock:
                        self._frame = frame
                    self._have_frame.set()
            finally:
                buf.unmap(mapinfo)
        return Gst.FlowReturn.OK

    def grab(self, left, top, width, height):
        with self._frame_lock:
            frame = self._frame
        if frame is None:
            raise RuntimeError("PipeWire backend has no frame yet")
        h, w = frame.shape[:2]
        x = max(0, min(int(left), w - 1))
        y = max(0, min(int(top), h - 1))
        cw = max(1, min(int(width), w - x))
        ch = max(1, min(int(height), h - y))
        return frame[y:y + ch, x:x + cw].copy()

    def close(self):
        try:
            self._pipeline.set_state(self._Gst.State.NULL)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

_backend = None
_backend_lock = threading.Lock()


def _probe(backend) -> bool:
    """Grab a small region and check it isn't a blank/uniform frame."""
    try:
        import edap_linux
        rect = edap_linux.find_elite_window_rect()
        if rect is None:
            return False
        l, t, r, b = rect
        img = backend.grab(l, t, min(400, r - l), min(400, b - t))
        return not looks_blank(img)
    except Exception as ex:
        logger.warning(f"{backend.name} probe failed: {ex}")
        return False


def _build(kind):
    if kind == "xcomposite":
        return XCompositeBackend()
    if kind == "pipewire":
        return PipeWireBackend()
    raise ValueError(f"unknown capture backend: {kind!r}")


def get_backend(force_new=False):
    """Returns the active capture backend, selecting one on first use."""
    global _backend
    with _backend_lock:
        if _backend is not None and not force_new:
            return _backend
        if _backend is not None:
            _backend.close()
            _backend = None

        choice = os.environ.get("EDAP_CAPTURE", "auto").strip().lower()
        if choice in ("xcomposite", "pipewire"):
            _backend = _build(choice)
            logger.info(f"Capture backend: {_backend.name} (forced)")
            return _backend

        errors = []
        for kind in ("xcomposite", "pipewire"):
            try:
                cand = _build(kind)
            except Exception as ex:
                errors.append(f"{kind}: {ex}")
                continue
            if _probe(cand):
                _backend = cand
                logger.info(f"Capture backend: {kind} (auto-selected)")
                return _backend
            cand.close()
            errors.append(f"{kind}: produced blank frames")
        raise RuntimeError("No usable capture backend. Tried: " +
                           "; ".join(errors))


def grab_region(left, top, width, height):
    """Module-level capture entry point used by Screen.py."""
    backend = get_backend()
    try:
        return backend.grab(left, top, width, height)
    except Exception:
        # backend went stale (window resized, stream died) — rebuild once
        return get_backend(force_new=True).grab(left, top, width, height)


if __name__ == "__main__":
    import sys
    import edap_linux
    rect = edap_linux.find_elite_window_rect()
    print("ED window   :", rect)
    if rect is None:
        sys.exit("Elite Dangerous window not found.")
    l, t, r, b = rect
    img = grab_region(l, t, r - l, b - t)
    print(f"backend     : {get_backend().name}")
    print(f"capture     : shape={img.shape} mean={img.mean():.1f} "
          f"std={img[..., :3].std():.1f} blank={looks_blank(img)}")
    try:
        import cv2
        out = os.path.expanduser("~/edap-logs/capture-probe.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cv2.imwrite(out, img)
        print("wrote       :", out)
    except Exception as ex:
        print("(no png written:", ex, ")")
