"""Minimal config loader for the OBS sharing demo.

Loads `.env` from THIS folder (not the current working directory) and exposes
only the OBS settings the static-image overlay needs.

The overlay itself (input/obs_overlay.py) reads no config; everything is passed
to its constructor. This file exists for demo_main.py.

Inside the Radeon AI Stream Co-Host this file is NOT used: the Co-Host reads
the same OBS_* settings from its own .env.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE = os.path.join(_HERE, ".env")

try:
    from dotenv import load_dotenv
    # interpolate=False: read values literally. Otherwise python-dotenv
    # replaces "${...}" in a value (even in quotes), which would change a
    # password that happens to contain it.
    load_dotenv(dotenv_path=_ENV_FILE, interpolate=False)
except ImportError:
    # Without python-dotenv the .env file can't be read. Say so, instead of
    # quietly running with the defaults (wrong password, wrong scene...).
    if os.path.exists(_ENV_FILE):
        print("Warning: python-dotenv isn't installed, so the settings in .env are "
              "being IGNORED (defaults are used). In this folder run:  "
              "python -m pip install -r requirements.txt")


def _flag(name, default):
    """1/0, yes/no, true/false, on/off. Anything else: the default."""
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "yes", "y", "true", "on"):
        return True
    if raw in ("0", "no", "n", "false", "off"):
        return False
    if raw:
        print(f"Warning: {name}={raw!r} in .env isn't yes/no; using "
              f"{'1' if default else '0'}.")
    return default


def _number(name, default, kind, low, high=None):
    """A number from .env. A typo is reported and the default used, instead
    of a crash before anything starts."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = kind(raw)
        if value >= low and (high is None or value <= high):
            return value
    except ValueError:
        pass
    print(f"Warning: {name}={raw!r} in .env isn't a valid number; using {default}.")
    return default


# --- OBS WebSocket (v5, OBS 28+) ---
OBS_ENABLED = _flag("OBS_ENABLED", True)
OBS_HOST = os.getenv("OBS_HOST", "localhost").strip() or "localhost"
OBS_PORT = _number("OBS_PORT", 4455, int, 1, 65535)
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

# --- The single static image source ---
# Scene that contains the image source. If the image is inside a group, put
# the GROUP's name here instead (OBS treats a group like a small scene).
OBS_SCENE = os.getenv("OBS_SCENE", "Main").strip() or "Main"
# Exact name of the Image/Media source in that scene (case-sensitive).
OBS_SOURCE = os.getenv("OBS_SOURCE", "Bot Name").strip() or "Bot Name"

# Hide the image as soon as the overlay connects, so it never sits on screen
# before the bot's first line. Keep this on for "hide while not talking".
OBS_HIDE_ON_CONNECT = _flag("OBS_HIDE_ON_CONNECT", True)

# Connection timeout for the WebSocket request (seconds). Short so a down OBS
# cannot stall the host bot's speech loop.
OBS_TIMEOUT_S = _number("OBS_TIMEOUT_S", 3.0, float, 0.1)
