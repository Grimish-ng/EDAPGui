# decky-edap

Decky Loader frontend for the EDAP autopilot daemon.

Architecture: this plugin is a thin client. The engine (capture, OCR,
input injection) runs as a systemd user service (`edap-daemon.service`)
and exposes a JSON/TCP control API on 127.0.0.1:15580. The plugin backend
(main.py, stdlib only) forwards Quick-Access-Menu button presses to it.

## Prerequisites
- EDAPGui linux-port checkout with a working .venv
- `edap_daemon.py` present in the repo root
- daemon unit installed and running (see repo README / unit file)
- Decky Loader installed

## Dev build + sideload
    pnpm i
    pnpm run build
    # deploy: copy this folder (with dist/) to the target:
    #   ~/homebrew/plugins/decky-edap
    # then restart Decky (or use `decky-cli plugin deploy`)

## Notes
- Buttons: start/stop FSD, Supercruise, Waypoint assists; STOP ALL.
- Status line polls every 2 s (engine state, AP statusline, jump count).
- The daemon waits for the ED window; buttons return an error until the
  game is running.
