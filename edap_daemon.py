#!/usr/bin/env python3
"""
edap_daemon.py — headless EDAP engine for Linux.

Runs EDAutopilot without the tkinter GUI and exposes a control surface:
  1. The upstream EDMesg server (zmq, ports from config) — starts
     automatically inside EDAutopilot; EDCoPilot-compatible.
  2. A dependency-free JSON-over-TCP control API on 127.0.0.1:15580 for
     thin clients that cannot ship pyzmq/pydantic (e.g. a Decky Loader
     plugin backend, curl, netcat).

Protocol (one JSON object per line, one reply per line):
  {"cmd": "status"}
  {"cmd": "start", "assist": "fsd" | "sc" | "waypoint" | "robigo" | "afk" | "dss"}
  {"cmd": "stop",  "assist": ...}                     # same names
  {"cmd": "stop_all"}
  {"cmd": "load_waypoints", "path": "/abs/path.json"}
  {"cmd": "ping"}
Reply: {"ok": true, ...} or {"ok": false, "error": "..."}

Waits for the ED window before constructing the engine, so it can be
started at login and idle until the game is up.
"""
from __future__ import annotations

import json
import os
import signal
import socketserver
import sys
import threading
import time

from EDlogger import logger

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = int(os.environ.get("EDAP_CONTROL_PORT", "15580"))

ASSIST_SETTERS = {
    "fsd": "set_fsd_assist",
    "sc": "set_sc_assist",
    "waypoint": "set_waypoint_assist",
    "robigo": "set_robigo_assist",
    "afk": "set_afk_combat_assist",
    "dss": "set_dss_assist",
}

# callback msgs that mean "this assist ended itself" -> keep state truthful
STOP_MSGS = {
    "fsd_stop": "fsd", "sc_stop": "sc", "waypoint_stop": "waypoint",
    "robigo_stop": "robigo", "afk_stop": "afk", "dss_stop": "dss",
    "single_waypoint_stop": "single_waypoint",
}
START_MSGS = {
    "fsd_start": "fsd", "sc_start": "sc", "waypoint_start": "waypoint",
}


class Daemon:
    def __init__(self):
        self.ap = None
        self.state = {
            "active": {},          # assist name -> bool
            "statusline": "",
            "jumpcount": "",
            "last_log": "",
            "engine": "waiting-for-game",
        }
        self._state_lock = threading.Lock()
        self._shutdown = threading.Event()

    # ---- EDAutopilot callback (replaces the tkinter GUI callback) ----------

    def callback(self, msg, body=None):
        with self._state_lock:
            if msg in ("log", "log+vce"):
                self.state["last_log"] = str(body)
                logger.info(f"[AP] {body}")
                if msg == "log+vce" and self.ap is not None:
                    try:
                        self.ap.vce.say(body)
                    except Exception:
                        pass
            elif msg == "statusline":
                self.state["statusline"] = str(body)
            elif msg == "jumpcount":
                self.state["jumpcount"] = str(body)
            elif msg in STOP_MSGS:
                self.state["active"][STOP_MSGS[msg]] = False
                logger.info(f"[AP] assist stopped: {STOP_MSGS[msg]}")
            elif msg in START_MSGS:
                self.state["active"][START_MSGS[msg]] = True
            # update_ship_cfg / load_waypoints etc.: GUI-refresh only, ignore

    # ---- engine lifecycle ----------------------------------------------------

    def wait_for_game(self):
        import edap_linux
        logger.info("Waiting for Elite Dangerous window...")
        while not self._shutdown.is_set():
            try:
                if edap_linux.elite_window_exists():
                    return True
            except Exception as ex:
                logger.warning(f"window probe failed: {ex}")
            time.sleep(5)
        return False

    def start_engine(self):
        from ED_AP import EDAutopilot
        self.ap = EDAutopilot(cb=self.callback)
        with self._state_lock:
            self.state["engine"] = "running"
        logger.info("EDAutopilot engine up (EDMesg server on configured ports).")

    # ---- control API -----------------------------------------------------------

    def handle(self, req: dict) -> dict:
        cmd = req.get("cmd")
        if cmd == "ping":
            return {"ok": True, "pong": True}
        if cmd == "status":
            with self._state_lock:
                return {"ok": True, "state": json.loads(json.dumps(self.state))}
        if self.ap is None:
            return {"ok": False, "error": "engine not running (game not detected yet)"}
        if cmd in ("start", "stop"):
            assist = req.get("assist")
            setter = ASSIST_SETTERS.get(assist)
            if setter is None:
                return {"ok": False, "error": f"unknown assist {assist!r}"}
            getattr(self.ap, setter)(cmd == "start")
            with self._state_lock:
                self.state["active"][assist] = (cmd == "start")
            return {"ok": True, "assist": assist, "active": cmd == "start"}
        if cmd == "stop_all":
            for name, setter in ASSIST_SETTERS.items():
                try:
                    getattr(self.ap, setter)(False)
                except Exception as ex:
                    logger.warning(f"stop_all: {name}: {ex}")
                with self._state_lock:
                    self.state["active"][name] = False
            return {"ok": True}
        if cmd == "load_waypoints":
            path = req.get("path", "")
            if not os.path.isfile(path):
                return {"ok": False, "error": f"no such file: {path}"}
            try:
                self.ap.waypoint.load_waypoint_file(path)
                return {"ok": True, "path": path}
            except Exception as ex:
                return {"ok": False, "error": str(ex)}
        return {"ok": False, "error": f"unknown cmd {cmd!r}"}


def make_control_server(daemon: Daemon):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            for line in self.rfile:
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line)
                    resp = daemon.handle(req)
                except Exception as ex:
                    resp = {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
                self.wfile.write((json.dumps(resp) + "\n").encode())
                self.wfile.flush()

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    return Server((CONTROL_HOST, CONTROL_PORT), Handler)


def main():
    daemon = Daemon()

    server = make_control_server(daemon)
    threading.Thread(target=server.serve_forever, name="control-api",
                     daemon=True).start()
    logger.info(f"Control API on {CONTROL_HOST}:{CONTROL_PORT}")

    def _term(signum, frame):
        logger.info("SIGTERM/SIGINT: shutting down.")
        daemon._shutdown.set()
        try:
            if daemon.ap is not None:
                daemon.handle({"cmd": "stop_all"})
                daemon.ap.quit()
        finally:
            server.shutdown()
            os._exit(0)

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)

    if not daemon.wait_for_game():
        return 0
    daemon.start_engine()

    while not daemon._shutdown.is_set():
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
