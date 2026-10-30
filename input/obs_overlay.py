"""Show a single static image source in OBS while the bot is talking.

This is the simple overlay path: one image source, visible only while the bot
speaks, hidden the rest of the time. It intentionally does NOT implement the
full PNGTuber state machine (talk frames, blinking, smug, thinking/listening).

Standalone: pass the connection and scene/source names to the constructor.
The module imports `obsws-python` lazily, so it can be imported even when the
package is not installed; `connect()` reports the problem instead.
"""
import contextlib
import threading
import time

from rich import print


class ObsStaticOverlay:
    """Toggle one scene item's visibility in OBS over obs-websocket v5.

    Typical use:

        overlay = ObsStaticOverlay(scene="Main", source="Bot Name")
        overlay.connect()              # connects and hides the image

        overlay.on_ai_speaking()       # show
        ...play speech...
        overlay.on_ai_done()           # hide

    or, safer against exceptions:

        with overlay.speaking():
            ...play speech...

    All methods are thread-safe. OBS failures never raise: they log, drop the
    connection, and retry on a later call. The host bot is never taken down by
    an OBS outage.
    """

    def __init__(self, host="localhost", port=4455, password="", scene="Main",
                 source="Bot Name", enabled=True, timeout_s=3.0,
                 hide_on_connect=True, retry_s=5.0, client_factory=None):
        self.host = host
        self.port = int(port)
        self.password = password or ""
        self.scene = scene
        self.source = source
        self.timeout_s = float(timeout_s)
        self.hide_on_connect = bool(hide_on_connect)
        self.retry_s = float(retry_s)

        self._client_factory = client_factory or self._default_client_factory
        self._lock = threading.RLock()
        self._enabled = bool(enabled)
        self._client = None
        self._item_id = None
        self._visible = None          # None = unknown/not applied
        self._last_error = ""
        self._connect_attempt_at = 0.0

    # ---------- connection ----------

    def _default_client_factory(self):
        from obsws_python import ReqClient
        return ReqClient(host=self.host, port=self.port,
                         password=self.password, timeout=self.timeout_s)

    def _resolve_item(self):
        resp = self._client.get_scene_item_id(self.scene, self.source)
        item_id = getattr(resp, "scene_item_id", None)
        if item_id is None and hasattr(resp, "datain"):
            item_id = resp.datain.get("sceneItemId")
        if item_id is None:
            raise RuntimeError(
                f"source '{self.source}' not found in scene '{self.scene}'")
        self._item_id = item_id

    def _apply(self, visible):
        if self._client is None:
            return False
        if self._item_id is None:
            self._resolve_item()
        self._client.set_scene_item_enabled(
            self.scene, self._item_id, bool(visible))
        self._visible = bool(visible)
        return True

    def _drop_client(self):
        client, self._client = self._client, None
        self._item_id = None
        self._visible = None
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass

    def connect(self):
        """Connect and (by default) hide the image. Returns True on success."""
        with self._lock:
            if not self._enabled:
                return False
            if self._client is not None:
                return True
            now = time.time()
            if self._last_error and (now - self._connect_attempt_at) < self.retry_s:
                return False
            self._connect_attempt_at = now
            try:
                self._client = self._client_factory()
                self._item_id = None
                self._visible = None
                self._resolve_item()
                if self.hide_on_connect:
                    self._apply(False)
                self._last_error = ""
                print(f"[green]OBS connected: scene '{self.scene}', "
                      f"source '{self.source}'"
                      + (" (hidden)" if self.hide_on_connect else ""))
                return True
            except Exception as e:
                self._last_error = f"{type(e).__name__}: {e}"
                print(f"[yellow]OBS overlay unavailable ({self._last_error}); "
                      "will retry on a later call")
                self._drop_client()
                return False

    def disconnect(self):
        """Hide the image (best effort) and close the connection."""
        with self._lock:
            try:
                if self._client is not None:
                    self._apply(False)
            except Exception:
                pass
            self._drop_client()
            self._last_error = ""

    def set_enabled(self, enabled):
        """Enable/disable OBS use. Disabling hides the image and disconnects."""
        enabled = bool(enabled)
        with self._lock:
            if enabled == self._enabled:
                return
            self._enabled = enabled
            if not enabled:
                try:
                    if self._client is not None:
                        self._apply(False)
                except Exception:
                    pass
                self._drop_client()
                self._last_error = ""
                print("[yellow]OBS overlay disabled (hidden, disconnected).")
            else:
                print("[cyan]OBS overlay enabled.")
                self.connect()

    # ---------- visibility ----------

    def set_visible(self, visible):
        """Show or hide the image. Returns True when OBS accepted the change."""
        with self._lock:
            if not self._enabled:
                return False
            if not self.connect():
                return False
            try:
                return self._apply(visible)
            except Exception as e:
                self._last_error = f"{type(e).__name__}: {e}"
                print(f"[yellow]OBS overlay update failed ({self._last_error}); "
                      "will reconnect on a later call")
                self._drop_client()
                return False

    def show(self):
        return self.set_visible(True)

    def hide(self):
        return self.set_visible(False)

    # Drop-in names matching the stream-tool contract used by the bot.
    def on_ai_speaking(self):
        return self.show()

    def on_ai_done(self):
        return self.hide()

    @contextlib.contextmanager
    def speaking(self):
        """`with overlay.speaking():` shows on enter and hides on exit, even
        when the body raises."""
        self.on_ai_speaking()
        try:
            yield self
        finally:
            self.on_ai_done()

    # ---------- info ----------

    @property
    def enabled(self):
        return self._enabled

    @property
    def connected(self):
        with self._lock:
            return self._client is not None

    @property
    def visible(self):
        with self._lock:
            return bool(self._visible)

    def status(self):
        with self._lock:
            return {
                "enabled": self._enabled,
                "connected": self._client is not None,
                "visible": bool(self._visible),
                "scene": self.scene,
                "source": self.source,
                "last_error": self._last_error,
            }

    # ---------- lifecycle helpers ----------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.disconnect()
        return False
