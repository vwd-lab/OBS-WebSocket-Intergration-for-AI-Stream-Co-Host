# Changelog — sharing\OBS Websocket (MIT)

Canonical working copy at `C:\XXXXX\AI Projects\Project AI Logan\sharing\OBS Websocket`.

Framework-agnostic OBS static-image overlay. Transport-only: ships no brain,
persona, TTS, or voice. Connects to OBS via obs-websocket v5 (OBS 28+) and
toggles a single image source on/off around TTS speech events
(`on_ai_speaking()` / `on_ai_done()`, or the `overlay.speaking()` context manager).

This is not a git repository, so versions are tracked here by date instead of commit hash.

## 2026-10-28 — Initial release

- `obs_gui.py` — tkinter setup GUI (stdlib only) that configures host, port, password, scene, source, and overlay behaviour and writes them to `.env`; launches `demo_main.py` as a subprocess and streams its log.
- `setup_obs_gui.bat` / `start_obs_gui.bat` — interactive setup and launcher.
- `demo_main.py` — obs-websocket v5 client; connects, hides the image on connect, toggles scene-item `enabled` around speech events.
- `config.example.json` — example configuration.
- `LICENSE` — MIT (copyright-notice retention guarantees attribution downstream).
- `README.md` — setup sequence, `on_ai_speaking()` / `on_ai_done()` hook contract, Radeon AI Co-Host vs custom-framework plug-in instructions.

## 2026-11-21 — OBS fixes 24, 25, 29 (based on direct feedback)

- Fixed OBS closed/frozen holding up every reply (Fix 24): `on_ai_speaking()` /
  `on_ai_done()` / `speaking()` now return at once and a background thread
  (`obs-overlay`) makes OBS match the wished-for state. A closed or frozen OBS
  no longer adds seconds to every reply. Only the latest wish counts, retries
  every `retry_s` until OBS has it, and the "OBS unavailable" warning prints
  once (again only if it changes or once a minute). `show()` / `hide()` still
  wait and report success/failure. `disconnect()` stops the retrying.
- Fixed OBS image only showing for chat replies (Fix 25, Co-Host `main.py`):
  every line the bot speaks now switches the OBS image (and stream tool) on
  while it plays — raid alerts, watch-streak shout-outs, command answers — and
  always off afterwards, even if speaking fails. No flash when nothing is said
  (voice muted). A misbehaving stream tool can't stop the image or the speech.
- Fixed OBS small issues (Fix 29, both kits):
  - OBS password with `#` or quotes (e.g. `abc #1`) was cut short when read
    back; now values are written in quotes and read back exactly. Settings
    window Save no longer wipes other `.env` lines.
  - A typo in `OBS_PORT` / `OBS_TIMEOUT_S` crashed the demo; `OBS_ENABLED=yes`
    turned the overlay off; missing python-dotenv silently ignored `.env`. Now
    reports which setting is wrong and uses the default; `yes`/`true`/`on`
    count as on; warns about missing python-dotenv.
  - Missing package now says how to install it; overlay works without `rich`;
    OBS errors with `[/...]` no longer crash `connect()`.
  - Demo shows colours properly (no `[magenta]` in text).
  - Docs: sources inside a group work (put the group's name in `OBS_SCENE`);
    Co-Host OBS settings go in the Co-Host's own `.env`.
  - Co-Host dashboard OBS light now follows the real connection (on when OBS
    connects, off when it closes), not just the start-up state.

## Planned

- (none yet — log changes here as they land)
