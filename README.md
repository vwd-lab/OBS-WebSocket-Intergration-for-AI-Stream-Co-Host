# This is a Beta intergrations add-on
While this was designed for my AI Stream Co-Host framework, I tried to make it so this could be added to any AI Stream Co-Host framework. Feedback would be appricated to help improve it and make it better.

# OBS WebSocket Bridge

Framework-agnostic OBS static-image overlay. Toggle a single image source on
and off while the bot speaks — for any bot framework.

The kit is **transport-only**: it ships no brain, persona, TTS, or voice
support. It connects to OBS via obs-websocket v5 (OBS 28+) and shows/hides a
single image source tied to speech events.

## How it works

```
your bot                         OBS (obs-websocket v5)
   |                                    |
   | connect() ------------------------>|  resolve scene item, set hidden
   |                                    |
   | on_ai_speaking() ---------------->|  set_scene_item_enabled(True)
   |   ...TTS / playback...             |
   | on_ai_done() -------------------->|  set_scene_item_enabled(False)
```

The overlay only toggles the scene item's `enabled` flag. It does not move,
scale, crop, filter, or change scenes. Position the image in OBS once; the kit
turns it on and off.

The image is hidden as part of `connect()`, so it is never left on screen
before the first line.

## Universal integration point

Your bot calls `overlay.on_ai_speaking()` before speech and
`overlay.on_ai_done()` after speech. Or use the context manager:

```python
with overlay.speaking():
    play_tts(text)   # your TTS/playback call
```

That is the universal plug — works with Radeon AI Co-Host or any custom
framework that has a "bot is speaking" hook.

## Plugging in

### Option A: Radeon AI Co-Host

Already wired in: the Co-Host shows the image for every line it speaks. Put
this kit's folder next to the Co-Host's, then set `OBS_ENABLED=1` and the
`OBS_*` settings in **the Co-Host's own `.env`**. Inside the Co-Host, this
kit's `.env`, `config.py`, GUI and demo aren't used, only
`input/obs_overlay.py`. Install this kit's requirements into the Python that
runs the Co-Host (`python -m pip install -r requirements.txt`).

### Option B: Any custom framework

Use `demo_main.py` as the template — construct `ObsStaticOverlay`, call
`connect()`, then call `on_ai_speaking()` / `on_ai_done()` around your speech.

## OBS setup

1. **OBS 28 or newer.**
2. **Tools → WebSocket Server Settings → Enable WebSocket server.**
3. Note the port (default `4455`) and password.
4. Add an **Image** source (your static picture) directly to the scene you
   stream. Give it the exact name you will use for `OBS_SOURCE`.
5. Position and scale it in OBS.
6. Put it directly in the scene, or in a group: if it's inside a group, set
   `OBS_SCENE` to the **group's** name instead of the scene's (OBS looks a
   group's sources up like a small scene's).

## Setup you'll still need

### 1. Enable OBS WebSocket
See "OBS setup" above.

### 2. Configure `.env`
Copy `.env.example` to `.env` and fill in at minimum:

```
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=your-obs-password
OBS_SCENE=Main
OBS_SOURCE=Bot Name
```

The setup wizard and the GUI write these for you. If you edit `.env` by hand
and the password contains `#`, quotes or `\`, put it in single quotes:
`OBS_PASSWORD='abc #1'` (otherwise everything from ` #` on is dropped).

### 3. Launch

**First run (recommended):** double-click `setup_obs_gui.bat`. It prompts for
host, port, password, scene, source, and overlay behaviour, writes `.env`, then
opens `obs_gui.py` where you can start/stop the bridge.

**Subsequent runs:** double-click `start_obs_gui.bat` (reuses `.env`), or run
directly:

```bat
python demo_main.py
```

## Files

| File | Purpose |
|---|---|
| `demo_main.py` | Example harness (console commands to show/hide/speak) |
| `obs_gui.py` | tkinter GUI launcher (stdlib only) |
| `setup_obs_gui.bat` | Interactive setup: prompts, writes `.env`, launches GUI |
| `start_obs_gui.bat` | Double-click launcher (uses existing `.env`) |
| `config.example.json` | List of the settings and their defaults (for reference; the kit reads `.env`) |
| `.env` | Your runtime configuration (created at runtime, git-ignored) |
| `.env.example` | Config template |
| `input/obs_overlay.py` | OBS WebSocket static-image overlay |
| `requirements.txt` | Python dependencies |

## Requirements

- Python 3
- `python -m pip install -r requirements.txt` (obsws-python, python-dotenv, rich)
- OBS 28+ with WebSocket server enabled

The GUI (`obs_gui.py`) uses tkinter only, so no extra packages are needed
to launch.

## License

This kit is released under the [MIT License](LICENSE). You are free to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the software.

The one requirement is attribution: the copyright notice and license text must
be retained in all copies or substantial portions of the software, so the
original creator (the Radeon AI Co-Host authors) stays credited no matter how
far downstream the code is shared.
