# Changelog — sharing\OBS Websocket (MIT)

Canonical working copy at `C:\Users/bbsti\AI Projects\Project AI Logan\sharing\OBS Websocket`.

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

## Planned

- (none yet — log changes here as they land)
