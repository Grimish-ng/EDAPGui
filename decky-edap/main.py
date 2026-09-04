"""Decky backend for EDAP: thin stdlib-only JSON/TCP client.

Talks to edap_daemon.py's control API on 127.0.0.1:15580. No third-party
imports — Decky's Python environment doesn't carry the engine's deps, and
must not: the engine lives in its own systemd user service.
"""
import json
import socket

import decky  # provided by Decky Loader

HOST, PORT = "127.0.0.1", 15580
TIMEOUT = 5.0


def _rpc(obj: dict) -> dict:
    try:
        with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as s:
            s.sendall((json.dumps(obj) + "\n").encode())
            line = s.makefile().readline()
        return json.loads(line)
    except (OSError, ValueError) as ex:
        return {"ok": False, "error": f"daemon unreachable: {ex}"}


class Plugin:
    async def status(self) -> dict:
        return _rpc({"cmd": "status"})

    async def start_assist(self, assist: str) -> dict:
        decky.logger.info(f"start {assist}")
        return _rpc({"cmd": "start", "assist": assist})

    async def stop_assist(self, assist: str) -> dict:
        return _rpc({"cmd": "stop", "assist": assist})

    async def stop_all(self) -> dict:
        return _rpc({"cmd": "stop_all"})

    async def _main(self):
        decky.logger.info("decky-edap backend up")

    async def _unload(self):
        pass
