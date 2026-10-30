"""
Standalone demo for the OBS static-image overlay.

Wires the real ObsStaticOverlay (input/obs_overlay.py) to a tiny console so you
can watch the image appear while the bot "speaks" and disappear afterwards.

    1. load .env (config.py)
    2. create ObsStaticOverlay(scene=..., source=...)
    3. connect()  -> the image is hidden immediately
    4. call on_ai_speaking() before speech and on_ai_done() after
       (or use `with overlay.speaking():`)

Replace the `say` helper with your real speech call and you are done.

Run:  python demo_main.py
"""
import sys
import time

import config
from input.obs_overlay import ObsStaticOverlay


def say(overlay, text):
    """Pretend to speak for a moment, showing the image only while talking."""
    seconds = max(1.0, min(10.0, len(text) / 12.0))
    print(f"[magenta]SPEAKING -> {text}")
    with overlay.speaking():
        time.sleep(seconds)
    print("[dim]done — image hidden")


def show_help():
    print("[cyan]Commands:")
    print("  say <text>   show the image, wait as if speaking, then hide it")
    print("  show         show the image now")
    print("  hide         hide the image now")
    print("  status       connection/visibility state")
    print("  on | off     enable/disable OBS use (off hides + disconnects)")
    print("  help         this list")
    print("  quit         exit")


def main():
    if not config.OBS_ENABLED:
        print("[yellow]OBS_ENABLED=0 in .env - overlay not started.")
        return 0

    overlay = ObsStaticOverlay(
        host=config.OBS_HOST,
        port=config.OBS_PORT,
        password=config.OBS_PASSWORD,
        scene=config.OBS_SCENE,
        source=config.OBS_SOURCE,
        enabled=True,
        timeout_s=config.OBS_TIMEOUT_S,
        hide_on_connect=config.OBS_HIDE_ON_CONNECT,
    )

    if not overlay.connect():
        print("[yellow]OBS is not reachable right now. The demo will retry on")
        print("[yellow]the next command (OBS must be running with WebSocket on).")

    print(f"[cyan]Watching scene '{config.OBS_SCENE}', source "
          f"'{config.OBS_SOURCE}'.")
    print("[cyan]The image starts hidden and only appears while speaking.")
    show_help()

    try:
        while True:
            try:
                line = input("obs> ").strip()
            except EOFError:
                break
            low = line.lower()

            if low in ("quit", "exit", "q"):
                break
            if not low:
                continue
            if low in ("help", "?"):
                show_help()
            elif low == "show":
                print("[green]shown" if overlay.show() else "[red]could not show")
            elif low == "hide":
                print("[green]hidden" if overlay.hide() else "[red]could not hide")
            elif low == "status":
                print(overlay.status())
            elif low == "on":
                overlay.set_enabled(True)
            elif low == "off":
                overlay.set_enabled(False)
            elif low.startswith("say "):
                text = line[4:].strip()
                if text:
                    say(overlay, text)
            else:
                print("[yellow]Unknown command. Type 'help'.")
    except KeyboardInterrupt:
        print()
    finally:
        overlay.disconnect()
        print("[red]Stopped (image hidden).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
