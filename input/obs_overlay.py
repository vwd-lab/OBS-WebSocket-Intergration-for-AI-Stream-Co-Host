"""Show a single static image source in OBS while the bot is talking.

This is the simple overlay path: one image source, visible only while the bot
speaks, hidden the rest of the time. It intentionally does NOT implement the
full PNGTuber state machine (talk frames, blinking, smug, thinking/listening).

Standalone: pass the connection and scene/source names to the constructor.
The module imports `obsws-python` lazily, so it can be imported even when the
package is not installed; `connect()` reports the problem (and how to install
it) instead. `rich` is optional too: without it messages are printed plainly.
"""
import contextlib
import re
import threading
import time

try:
    from rich import print            # coloured console messages
except ImportError:                    # works without rich too, just no colour
    import builtins as _builtins

    _STYLE = re.compile(r"^\[(?:green|yellow|cyan|magenta|red|dim|bold)\]")

    def print(*args, **kwargs):
        """Plain print that drops the leading colour tag ("[green]...")."""
        _builtins.print(*(_STYLE.sub("", str(a), count=1) for a in args), **kwargs)

    def _plain(text):
        return str(text)
else:
    def _plain(text):
        """Show text exactly as written: a scene, source or error containing
        "[" would otherwise be read as a colour tag (and "[/x]" crashes it)."""
        return re.sub(r"(\\*)\[", lambda m: m.group(1) * 2 + "\\[", str(text))

# How to install the one package the overlay needs, shown when it's missing.
INSTALL_HINT = ("the obsws-python package isn't installed for this Python. "
                "In the OBS kit folder run:  python -m pip install -r requirements.txt  "
                "(with the same Python that runs the bot)")


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

    on_ai_speaking() / on_ai_done() / speaking() never wait for OBS: they note
    what should be on screen and a background thread makes OBS match - so a
    closed or frozen OBS can't hold up the bot's speech. Only the latest wish
    counts, and it's retried every `retry_s` until OBS has it. show() / hide()
    still wait (up to a few seconds) and report whether OBS took the change.
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
        self._last_warned = ("", 0.0)

        # Background worker: the wished-for state, and how far it has got.
        self._want_lock = threading.Lock()
        self._want = None             # True show / False hide / None nothing asked
        self._want_seq = 0            # bumps on every request
        self._done_seq = 0            # last request the worker finished
        self._done_ok = False
        self._done = threading.Condition(self._want_lock)
        self._wake = threading.Event()
        self._worker = None

    # ---------- background worker ----------

    def _request(self, visible):
        """Note that OBS should show/hide the image; return at once."""
        with self._want_lock:
            self._want = bool(visible)
            self._want_seq += 1
            seq = self._want_seq
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._work, daemon=True,
                                                name="obs-overlay")
                self._worker.start()
        self._wake.set()
        return seq

    def _work(self):
        pending = False
        while True:
            # Sleep until asked; while OBS hasn't taken the latest wish yet,
            # wake every retry_s to try again.
            self._wake.wait(timeout=self.retry_s if pending else None)
            self._wake.clear()
            with self._want_lock:
                want, seq = self._want, self._want_seq
            if want is None:
                pending = False
                continue
            ok = self.set_visible(want)
            with self._done:
                self._done_seq, self._done_ok = seq, ok
                self._done.notify_all()
            pending = not ok and self._enabled

    def _wait_for(self, seq, timeout):
        with self._done:
            self._done.wait_for(lambda: self._done_seq >= seq, timeout=timeout)
            return self._done_seq >= seq and self._done_ok

    def _warn(self, message):
        """Say a problem once, and again only if it changes or every minute -
        the worker retries quietly in between."""
        last, at = self._last_warned
        now = time.time()
        if message != last or now - at > 60:
            self._last_warned = (message, now)
            print(message)

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
                print(f"[green]OBS connected: scene '{_plain(self.scene)}', "
                      f"source '{_plain(self.source)}'"
                      + (" (hidden)" if self.hide_on_connect else ""))
                return True
            except ImportError as e:
                # obsws-python (or one of its own packages) isn't installed:
                # say how to fix it instead of a bare "No module named ...".
                self._last_error = f"{type(e).__name__}: {e}"
                self._warn(f"[yellow]OBS overlay unavailable ({_plain(e)}): "
                           + INSTALL_HINT)
                self._drop_client()
                return False
            except Exception as e:
                self._last_error = f"{type(e).__name__}: {e}"
                self._warn(f"[yellow]OBS overlay unavailable ({_plain(self._last_error)}); "
                           "will keep trying in the background")
                self._drop_client()
                return False

    def _forget_wish(self):
        with self._want_lock:
            self._want = None         # the worker stops trying

    def disconnect(self):
        """Hide the image (best effort) and close the connection."""
        self._forget_wish()
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
                self._forget_wish()
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
        """Show or hide the image now, waiting for OBS. Returns True when OBS
        accepted the change. (The background worker uses this too.)"""
        with self._lock:
            if not self._enabled:
                return False
            if not self.connect():
                return False
            try:
                return self._apply(visible)
            except Exception as e:
                self._last_error = f"{type(e).__name__}: {e}"
                self._warn(f"[yellow]OBS overlay update failed ({_plain(self._last_error)}); "
                           "will keep trying in the background")
                self._drop_client()
                return False

    def show(self, wait_s=None):
        """Show the image; waits for OBS (up to a few seconds) and returns
        True if it took the change. The background worker keeps trying."""
        return self._wait_for(self._request(True), self._wait_limit(wait_s))

    def hide(self, wait_s=None):
        """Hide the image; waits like show()."""
        return self._wait_for(self._request(False), self._wait_limit(wait_s))

    def _wait_limit(self, wait_s):
        return float(wait_s) if wait_s is not None else 2 * self.timeout_s + 1.0

    # Drop-in names matching the stream-tool contract used by the bot. These
    # never wait for OBS: a closed or frozen OBS used to hold up every reply
    # (a connection attempt or a timeout before speaking, and again after).
    def on_ai_speaking(self):
        self._request(True)
        return True

    def on_ai_done(self):
        self._request(False)
        return True

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
