================================================================================
 BOT NAME OBS STATIC IMAGE OVERLAY - STANDALONE SHARE KIT
================================================================================

This folder is a bare-bones, plug-and-play OBS integration for a Bot Name
streamer bot. It does ONE thing:

    show a single static image in OBS while the bot is talking,
    and hide it while the bot is not talking.

That is the whole feature. It is the simple "static image" option - there are
no talk frames, blinking eyes, smug expressions or thinking/listening states.
If you want a multi-frame PNGTuber, this kit is deliberately not that.

For the full contract (constructor args, methods, threading, errors), see
INTEGRATION.md.

--------------------------------------------------------------------------------
 WHAT YOU GET
--------------------------------------------------------------------------------
  input/obs_overlay.py    ObsStaticOverlay (obs-websocket v5 client + state)
  demo_main.py            Console harness: type "say hello" and watch it work
  config.py               Trimmed config (only OBS settings)
  requirements.txt        Packages needed
  .env.example            Copy to .env and fill in your values
  COMMANDS.txt            Demo console + the API your bot calls
  INTEGRATION.md          Full integration contract

--------------------------------------------------------------------------------
 HOW IT BEHAVES
--------------------------------------------------------------------------------
  connect()            connects and HIDES the image immediately
  on_ai_speaking()     shows the image        (call before speech)
  on_ai_done()         hides the image        (call after speech)

So the image is only on screen while the bot is actually speaking. If the host
crashes mid-line without calling on_ai_done(), the image stays visible until
OBS is touched again - use `with overlay.speaking():` or a finally block to
make hiding unconditional.

The overlay reconnects by itself: if OBS was closed when the bot started, the
next show/hide call retries. A failed call never raises and never takes the
host bot down.

--------------------------------------------------------------------------------
 1) PREPARE OBS (2 minutes)
--------------------------------------------------------------------------------
  1. In OBS: Tools > WebSocket Server Settings.
  2. Tick "Enable WebSocket server".
  3. Note the port (default 4455) and password.
  4. In the scene you stream, add an Image source (the static picture you want
     to appear). Name it exactly what you will put in OBS_SOURCE below.
     Position/scale it in the scene; this kit only toggles visibility, it does
     not move or resize anything.
  5. Keep the image inside the scene itself. Putting it inside a group is not
     supported by the simple scene-item lookup.

OBS 28+ is required (obs-websocket v5). The old v4 protocol is not supported.

--------------------------------------------------------------------------------
 2) CONFIGURE .env
--------------------------------------------------------------------------------
  copy .env.example .env

Fill in:

      OBS_ENABLED=1
      OBS_HOST=localhost
      OBS_PORT=4455
      OBS_PASSWORD=the password from OBS
      OBS_SCENE=Main
      OBS_SOURCE=Bot Name

`OBS_SCENE` and `OBS_SOURCE` are case-sensitive. `OBS_SOURCE` is the source
name, not the image file path.

--------------------------------------------------------------------------------
 3) RUN THE DEMO
--------------------------------------------------------------------------------
      python demo_main.py

The image disappears as soon as it connects. Then:

      say hello there        -> image appears, waits, disappears
      show                   -> image appears and stays
      hide                   -> image disappears
      status                 -> { enabled, connected, visible, ... }
      on / off               -> enable/disable OBS use at runtime
      quit

This is the whole behaviour you need to copy into your bot.

--------------------------------------------------------------------------------
 4) WIRE IT INTO YOUR BOT
--------------------------------------------------------------------------------
Create one overlay at startup:

      from input.obs_overlay import ObsStaticOverlay

      overlay = ObsStaticOverlay(
          host=config.OBS_HOST,
          port=config.OBS_PORT,
          password=config.OBS_PASSWORD,
          scene=config.OBS_SCENE,
          source=config.OBS_SOURCE,
      )
      overlay.connect()

Then bracket speech:

      overlay.on_ai_speaking()
      try:
          play_the_tts()
      finally:
          overlay.on_ai_done()

or, equivalently:

      with overlay.speaking():
          play_the_tts()

The `finally` / `speaking()` form is what guarantees "hidden while not
talking" even when TTS or playback throws.

The method names match the stream-tool contract used by the bot, so you can
drop this in wherever on_ai_speaking()/on_ai_done() are already called.

--------------------------------------------------------------------------------
 API SUMMARY (all thread-safe)
--------------------------------------------------------------------------------
  connect()                 -> bool    connect + hide
  disconnect()              -> None    hide (best effort) + close
  set_enabled(bool)         -> None    off hides and disconnects
  show() / hide()           -> bool
  set_visible(bool)         -> bool
  on_ai_speaking()          -> bool    alias for show()
  on_ai_done()              -> bool    alias for hide()
  speaking()                -> context manager (show on enter, hide on exit)
  status()                  -> dict
  enabled / connected / visible       read-only properties

See INTEGRATION.md for the full tables.

--------------------------------------------------------------------------------
 TROUBLESHOOTING
--------------------------------------------------------------------------------
  "OBS overlay unavailable (ConnectionRefusedError ...)"
      OBS is not running, the WebSocket server is off, or host/port are wrong.

  "AuthenticationFailed" / auth error
      Wrong OBS_PASSWORD. Copy it from Tools > WebSocket Server Settings.

  "source 'X' not found in scene 'Y'"
      The source name or scene name is wrong (case-sensitive), the source is
      not an Image/Media source, or it is inside a group. Add it directly to
      the scene with the exact name.

  Image never appears
      OBS_ENABLED=0, the bot never called on_ai_speaking(), or the source is
      hidden behind another layer in the scene (this kit only toggles the
      scene item's own enabled flag).

  Image stays visible after speech
      on_ai_done() was not called, or it failed. Use `with overlay.speaking():`
      or a finally block. If OBS was closed, the image is frozen in its last
      state until OBS returns; the next connect() hides it.

  Image appears before the bot speaks
      OBS_HIDE_ON_CONNECT=0. Set it back to 1, or call hide() yourself after
      connect().

--------------------------------------------------------------------------------
 INTEGRATION NOTE
--------------------------------------------------------------------------------
input/obs_overlay.py imports only the stdlib, rich, and (lazily) obsws-python.
It reads no config and no environment variables. config.py and demo_main.py
exist to make the standalone demo run.

demo_main.py imports the overlay as "input.obs_overlay", so the kit expects an
input/ folder at your project root. If your project uses another package name,
adjust that one import; the module itself does not care where it lives.

This kit is transport/visibility only. It does not start or stop streaming,
change scenes, control audio, or drive a multi-frame avatar.
================================================================================
