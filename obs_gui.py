"""OBS WebSocket bridge GUI — tkinter (stdlib only, no extra pip install).

Starts demo_main.py as a subprocess and streams its log into a live
window. Lets you configure host, port, password, scene, source, and overlay
behaviour without touching .env by hand.
"""

import os
import subprocess
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# .env reading/writing is shared with the setup wizard, so both quote values
# the same way and keep your other lines and comments.
from setup_wizard import HEADER as ENV_HEADER, read_env, write_env

# ---------------------------------------------------------------------------
# Running the bridge without freezing the window
# (The same code is used in the OBS, Discord and Kick GUIs.)
# ---------------------------------------------------------------------------

class BridgeProcess:
    """Runs a bridge script and collects its output without ever blocking the
    window.

    Before, the GUI called stdout.readline() on the window's own thread, which
    waits until the bridge prints something - so the window froze ("Not
    Responding") whenever the bridge was quiet, and Stop couldn't be clicked.
    Now a background thread reads the output into a queue and the window only
    takes what's already there.

    Also:
    - the bridge's output is unbuffered UTF-8, so lines show up right away and
      emoji/accents in chat can't crash its printing;
    - Stop asks the bridge to shut down cleanly first (by closing its stdin;
      the bridge treats that like Ctrl+C and runs its own cleanup, e.g. hiding
      the OBS image) and only forces it if it hasn't exited after a grace
      period. Before, Stop killed it outright and the cleanup never ran.
    """

    def __init__(self, script, cwd):
        env = {**os.environ,
               "PYTHONUNBUFFERED": "1",        # print lines immediately
               "PYTHONIOENCODING": "utf-8",    # emoji/accents can't crash printing
               "BRIDGE_GUI_CHILD": "1"}        # "stdin closed" means "please stop"
        self.proc = subprocess.Popen(
            [sys.executable or "python", "-u", script],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        self.pid = self.proc.pid
        self.finished = False           # True once all output has been read
        self._lines = queue.Queue()
        self._stopping = False
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        try:
            for line in self.proc.stdout:
                self._lines.put(line.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        finally:
            self._lines.put(None)       # end of output

    def poll(self):
        return self.proc.poll()

    @property
    def returncode(self):
        return self.proc.returncode

    def drain(self, limit=500):
        """Lines printed since the last call. Never waits."""
        out = []
        for _ in range(limit):
            try:
                item = self._lines.get_nowait()
            except queue.Empty:
                break
            if item is None:
                self.finished = True
                break
            out.append(item)
        return out

    def request_stop(self, grace_s=8.0):
        """Ask for a clean stop, then force it after grace_s. Returns at once."""
        if self._stopping:
            return
        self._stopping = True
        threading.Thread(target=self._stop, args=(grace_s,), daemon=True).start()

    def _stop(self, grace_s):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=grace_s)
            return
        except subprocess.TimeoutExpired:
            pass
        self._lines.put(f"[bridge didn't stop within {grace_s:.0f}s - forcing it]")
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def stop_and_wait(self, timeout=12.0):
        """For closing the window: stop and wait (bounded)."""
        self.request_stop()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()


ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")

DEFAULT_ENV = {
    "OBS_ENABLED": "1",
    "OBS_HOST": "localhost",
    "OBS_PORT": "4455",
    "OBS_PASSWORD": "",
    "OBS_SCENE": "Main",
    "OBS_SOURCE": "Bot Name",
    "OBS_HIDE_ON_CONNECT": "1",
    "OBS_TIMEOUT_S": "3.0",
}


def load_env():
    """The settings in .env (with the defaults for any that are missing)."""
    env = dict(DEFAULT_ENV)
    try:
        env.update(read_env(ENV_PATH)[1])
    except (OSError, UnicodeError):
        pass
    return env


def save_env(env):
    """Save the window's settings into .env.

    Before, this rewrote .env from scratch with the values unquoted: any other
    lines or comments were lost, and a password containing " #" was cut short
    when the bridge read it back. Now it updates .env like the setup wizard
    does (quoting values that need it) and writes it in one step.
    """
    lines, _ = read_env(ENV_PATH)
    write_env(ENV_PATH, lines, env, ENV_HEADER)


class OBSBridgeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OBS WebSocket Bridge — Launcher")
        self.geometry("700x560")
        self.minsize(600, 420)

        self.process = None
        self.log_queue = []
        self.env = load_env()

        self._build_ui()
        self._load_env_into_fields()

        self.after(100, self._poll_process)
        self.after(500, self._poll_log_queue)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.status_var = tk.StringVar(value="Stopped")
        status = ttk.Label(
            self, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3),
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        self.tab_env = ttk.Frame(nb, padding=10)
        self.tab_log = ttk.Frame(nb, padding=10)
        self.tab_about = ttk.Frame(nb, padding=10)
        nb.add(self.tab_env, text="Configure")
        nb.add(self.tab_log, text="Live Log")
        nb.add(self.tab_about, text="About")

        self._build_env_tab()
        self._build_log_tab()
        self._build_about_tab()

    def _build_env_tab(self):
        f = self.tab_env
        canvas = tk.Canvas(f, highlightthickness=0)
        scrollbar = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.entries = {}

        def entry_row(parent, label, key, width=40, show=False, tip=None):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, width=26, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar()
            ent = ttk.Entry(row, textvariable=var, width=width, show="*" if show else "")
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = var
            if tip:
                ttk.Label(parent, text=tip, wraplength=300, foreground="#666666").pack(anchor=tk.W, pady=(0, 4))
            return row

        def check_row(parent, label, key, default="1", tip=None):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=4)
            var = tk.BooleanVar(value=default == "1")
            ttk.Checkbutton(row, text=label, variable=var).pack(side=tk.LEFT)
            self.entries[key] = var
            if tip:
                ttk.Label(parent, text=tip, wraplength=300, foreground="#666666").pack(anchor=tk.W, pady=(0, 4))
            return row

        obs = ttk.LabelFrame(scrollable, text="OBS WebSocket settings", padding=10)
        obs.pack(fill=tk.X, pady=(0, 8))

        check_row(obs, "Enable OBS overlay", "OBS_ENABLED", default=self.env.get("OBS_ENABLED", "1"),
                  tip="If off, all show/hide calls are no-ops.")
        entry_row(obs, "Host", "OBS_HOST",
                  tip="OBS WebSocket server host (usually localhost).")
        entry_row(obs, "Port", "OBS_PORT", width=10,
                  tip="OBS WebSocket port (default 4455).")
        entry_row(obs, "Password", "OBS_PASSWORD", width=40, show=True,
                  tip="OBS WebSocket server password.")
        entry_row(obs, "Scene", "OBS_SCENE",
                  tip="Scene containing the image source. Case-sensitive.")
        entry_row(obs, "Source name", "OBS_SOURCE",
                  tip="Exact name of the Image source in that scene. Case-sensitive.")
        check_row(obs, "Hide on connect", "OBS_HIDE_ON_CONNECT", default=self.env.get("OBS_HIDE_ON_CONNECT", "1"),
                  tip="Hide the image when the connection is established (keep on).")
        entry_row(obs, "Timeout (s)", "OBS_TIMEOUT_S", width=10,
                  tip="WebSocket connect timeout. Short so a stopped OBS cannot stall speech.")

        # --- Launch buttons ---
        btns = ttk.Frame(scrollable)
        btns.pack(fill=tk.X, pady=(16, 0))
        self.btn_start = ttk.Button(btns, text="Start bridge", command=self._start_bridge)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_stop = ttk.Button(btns, text="Stop bridge", command=self._stop_bridge, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Button(btns, text="Save .env", command=self._save_env).pack(side=tk.LEFT, padx=(10, 0))

    def _build_log_tab(self):
        f = self.tab_log
        self.log_text = scrolledtext.ScrolledText(f, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(f)
        btns.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns, text="Clear log", command=self._clear_log).pack(side=tk.LEFT)

    def _build_about_tab(self):
        f = self.tab_about
        text = (
            "OBS WebSocket Bridge\n\n"
            "Framework-agnostic OBS static-image overlay. Toggles a single\n"
            "image source on/off while the bot speaks.\n\n"
            "  • connect    — resolve scene item, hide image\n"
            "  • speaking   — show on enter, hide on exit (context manager)\n"
            "  • on_ai_*    — show/hide aliases for stream-tool contract\n\n"
            "Requires: Python 3, obsws-python\n"
            "OBS 28+ with WebSocket server enabled (Tools > WebSocket Server Settings)\n\n"
            "No credentials are hard-coded; everything lives in .env.\n"
        )
        ttk.Label(f, text=text, justify=tk.LEFT, wraplength=640).pack(anchor=tk.W, pady=10)

    # ------------------------------------------------------------------ env fields

    def _load_env_into_fields(self):
        for key, var in self.entries.items():
            if isinstance(var, tk.BooleanVar):
                var.set(str(self.env.get(key, "1")) == "1")
            else:
                var.set(str(self.env.get(key, "")))

    def _collect_env(self):
        env = {}
        for key, var in self.entries.items():
            if isinstance(var, tk.BooleanVar):
                env[key] = "1" if var.get() else "0"
            else:
                env[key] = var.get().strip()
        return env

    def _save_env(self):
        env = self._collect_env()
        try:
            save_env(env)
        except OSError as e:
            messagebox.showerror("Not saved", f"Could not write .env: {e}")
            return False
        self.env = env
        messagebox.showinfo("Saved", ".env written.")
        return True

    # ------------------------------------------------------------------ bridge process

    def _start_bridge(self):
        if self.process is not None and self.process.poll() is None:
            messagebox.showwarning("Already running", "The bridge is already running.")
            return

        env = self._collect_env()
        try:
            save_env(env)
        except OSError as e:
            messagebox.showerror("Start failed", f"Could not write .env: {e}")
            return
        self.env = env

        script = os.path.join(ROOT, "demo_main.py")
        try:
            self.process = BridgeProcess(script, ROOT)
        except Exception as e:
            messagebox.showerror("Start failed", str(e))
            return

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.status_var.set("Running")
        self._log_ui(f"Bridge started (PID {self.process.pid})")
        self._log_ui(f"OBS: {env.get('OBS_HOST')}:{env.get('OBS_PORT')} scene={env.get('OBS_SCENE')} source={env.get('OBS_SOURCE')}")

    def _stop_bridge(self):
        """Ask the bridge to stop cleanly. Returns at once; _poll_process
        notices when it has exited and resets the buttons."""
        if self.process is None:
            return
        self.process.request_stop()
        self.btn_stop.configure(state=tk.DISABLED)
        self.status_var.set("Stopping...")
        self._log_ui("Stopping the bridge (letting it clean up)...")

    def _set_stopped(self):
        self.process = None
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.status_var.set("Stopped")

    # ------------------------------------------------------------------ log plumbing

    def _poll_process(self):
        """Show whatever the bridge has printed so far. Never waits for
        output - the old readline() here froze the window."""
        proc = self.process
        if proc is not None:
            self.log_queue.extend(proc.drain())
            if proc.finished and proc.poll() is not None:
                self.log_queue.append(f"[process exited code {proc.returncode}]")
                self.log_queue.append("Bridge stopped.")
                self._set_stopped()
        self.after(100, self._poll_process)

    def _poll_log_queue(self):
        while self.log_queue:
            line = self.log_queue.pop(0)
            self._log_ui(line)
        self.after(500, self._poll_log_queue)

    def _log_ui(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def on_closing(self):
        if self.process is not None:
            self.status_var.set("Stopping...")
            self.update_idletasks()
            self.process.stop_and_wait()
        self.destroy()


if __name__ == "__main__":
    app = OBSBridgeGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
