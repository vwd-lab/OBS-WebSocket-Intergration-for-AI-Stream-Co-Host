"""Minimal config loader for the OBS sharing demo.

Loads `.env` from THIS folder (not the current working directory) and exposes
only the OBS settings the static-image overlay needs.

The overlay itself (input/obs_overlay.py) reads no config; everything is passed
to its constructor. This file exists for demo_main.py.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(_HERE, ".env"))
except ImportError:
    pass  # .env optional; env vars read from the OS directly

# --- OBS WebSocket (v5, OBS 28+) ---
OBS_ENABLED = os.getenv("OBS_ENABLED", "1") == "1"
OBS_HOST = os.getenv("OBS_HOST", "localhost").strip() or "localhost"
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

# --- The single static image source ---
# Scene that contains the image source.
OBS_SCENE = os.getenv("OBS_SCENE", "Main").strip() or "Main"
# Exact name of the Image/Media source in that scene (case-sensitive).
OBS_SOURCE = os.getenv("OBS_SOURCE", "Bot Name").strip() or "Bot Name"

# Hide the image as soon as the overlay connects, so it never sits on screen
# before the bot's first line. Keep this on for "hide while not talking".
OBS_HIDE_ON_CONNECT = os.getenv("OBS_HIDE_ON_CONNECT", "1") == "1"

# Connection timeout for the WebSocket request (seconds). Short so a down OBS
# cannot stall the host bot's speech loop.
OBS_TIMEOUT_S = float(os.getenv("OBS_TIMEOUT_S", "3.0"))
