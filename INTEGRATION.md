# OBS Static Image Overlay — Integration Guide

A single static image source in OBS, visible only while the bot is talking and
hidden the rest of the time. This is deliberately the simple "static image"
option; the full PNGTuber state machine (talk frames, blink, smug,
thinking/listening) is not included.

The kit uses **obs-websocket v5** (OBS 28+) through `obsws-python`.

Contents:

- [How it works](#how-it-works)
- [OBS setup](#obs-setup)
- [Minimal wiring](#minimal-wiring)
- [Constructor](#constructor)
- [Methods](#methods)
- [Lifecycle and behaviour](#lifecycle-and-behaviour)
- [Threading and errors](#threading-and-errors)
- [Status](#status)
- [Layout and imports](#layout-and-imports)
- [How this differs from the full avatar](#how-this-differs-from-the-full-avatar)
- [Troubleshooting](#troubleshooting)

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

## OBS setup

1. OBS 28 or newer.
2. **Tools → WebSocket Server Settings → Enable WebSocket server.**
3. Note the port (default `4455`) and password.
4. Add an **Image** source (your static picture) directly to the scene you
   stream. Give it the exact name you will use for `OBS_SOURCE`.
5. Position and scale it in OBS.
6. Do not put it inside a group; the simple scene-item lookup expects the
   source directly in the scene.

## Minimal wiring

```python
from input.obs_overlay import ObsStaticOverlay

overlay = ObsStaticOverlay(
    host="localhost",
    port=4455,
    password="your OBS password",
    scene="Main",
    source="Bot Name",
)
overlay.connect()                    # connects + hides the image

def speak(text):
    overlay.on_ai_speaking()
    try:
        play_tts(text)               # your TTS/playback call
    finally:
        overlay.on_ai_done()         # hidden again, even on error

# Equivalent, exception-safe:
# with overlay.speaking():
#     play_tts(text)
```

At shutdown:

```python
overlay.disconnect()                 # hide (best effort) + close
```

## Constructor

```python
ObsStaticOverlay(
    host="localhost",
    port=4455,
    password="",
    scene="Main",
    source="Bot Name",
    enabled=True,
    timeout_s=3.0,
    hide_on_connect=True,
    retry_s=5.0,
    client_factory=None,
)
```

| Argument | Purpose |
|---|---|
| `host`, `port`, `password` | OBS WebSocket server settings. |
| `scene` | Scene containing the image. Case-sensitive. |
| `source` | Exact source name in that scene. Case-sensitive. |
| `enabled` | If False, every show/hide call is a no-op. |
| `timeout_s` | WebSocket connect timeout. Short so a stopped OBS cannot stall speech. |
| `hide_on_connect` | Hide the source when the connection is established. Keep True. |
| `retry_s` | After a failure, how long before another connection attempt. |
| `client_factory` | Injectable client for tests (defaults to `obsws_python.ReqClient`). |

## Methods

All methods are thread-safe and never raise.

| Method | Returns | What it does |
|---|---|---|
| `connect()` | `bool` | Connect, resolve the scene item, hide it (when `hide_on_connect`). |
| `disconnect()` | — | Hide (best effort), close the connection. |
| `set_enabled(bool)` | — | Off hides and disconnects; On connects. |
| `show()` | `bool` | Make the image visible. |
| `hide()` | `bool` | Hide the image. |
| `set_visible(bool)` | `bool` | Explicit form of show/hide. |
| `on_ai_speaking()` | `bool` | Alias for `show()` (stream-tool contract). |
| `on_ai_done()` | `bool` | Alias for `hide()` (stream-tool contract). |
| `speaking()` | context manager | Show on enter, hide on exit. |
| `status()` | `dict` | Snapshot for a dashboard/health check. |

Read-only properties: `enabled`, `connected`, `visible`.

## Lifecycle and behaviour

- Construction does not touch the network.
- `connect()` hides the image before returning, so an idle bot shows nothing.
- `show()`/`hide()` connect lazily if needed; you may skip the explicit
  `connect()` and just call `on_ai_speaking()`.
- If the source or scene is missing, `connect()` fails, logs the exact name,
  and returns False. The next call retries after `retry_s`.
- If OBS closes mid-session, the failing call logs, drops the client, and the
  next call reconnects. On reconnect the image is hidden again.
- `disconnect()` hides the image (best effort) so it does not linger.
- `enabled=False` makes all visibility calls return False without connecting.

"Hidden while not talking" is guaranteed by the host calling
`on_ai_done()`/`hide()` after speech. Use `try/finally` or
`with overlay.speaking():` so an exception cannot leave the image up.

## Threading and errors

- A single `threading.RLock` serialises connection and visibility changes.
- OBS calls are synchronous and bounded by `timeout_s`. They are cheap on
  localhost; do not call them from a latency-critical audio callback.
- Any OBS exception is caught: the kit logs, disconnects, and retries later.
  It never propagates into the host bot.
- `obsws-python` logs its own connection warnings through `logging`.

## Status

```python
{
    "enabled": True,
    "connected": True,
    "visible": False,
    "scene": "Main",
    "source": "Bot Name",
    "last_error": "",
}
```

`visible` is the last state the kit applied (`False` when unknown).

## Layout and imports

```
your_project/
  input/
    obs_overlay.py
  demo_main.py       # example only
  config.py          # example only
```

`demo_main.py` imports `input.obs_overlay`. The module itself has no layout
assumption; adjust that one import for your package name.

`obs_overlay.py` imports only the stdlib, `rich`, and (lazily)
`obsws_python`. It reads no config or environment variables.

## How this differs from the full avatar

| Full avatar (`AvatarDirector`) | This kit |
|---|---|
| Multi-state PNGTuber | One static image |
| A set of prefixed sources | One `source` name |
| Talk flap, blink, smug | None |
| Thinking/listening states | None |
| Continuous polling thread | Calls only on speech start/end |
| Depends on `audio_manager` | Host decides when speech happens |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ConnectionRefusedError` | OBS not running, WebSocket server off, or wrong host/port. |
| Auth failure | Wrong `OBS_PASSWORD`. |
| `source 'X' not found in scene 'Y'` | Wrong case/name, source not in that scene, or inside a group. |
| Image never appears | `enabled=False`, `on_ai_speaking()` never called, or the scene item is behind another layer. |
| Image stays up after speech | `on_ai_done()` not called/failed. Use `speaking()` or `finally`. |
| Image appears at startup | `hide_on_connect=False`. Set it True. |
| Calls block briefly | OBS host unreachable; lower `timeout_s`. |
