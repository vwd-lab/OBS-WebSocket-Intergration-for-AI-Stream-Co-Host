"""OBS WebSocket bridge GUI — tkinter (stdlib only, no extra pip install).

Starts demo_main.py as a subprocess and streams its log into a live
window. Lets you configure host, port, password, scene, source, and overlay
behaviour without touching .env by hand.
"""

import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
CONFIG_PATH = os.path.join(ROOT, "config.json")

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
    if os.path.exists(ENV_PATH):
        try:
            data = {}
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
            return data
        except Exception:
            pass
    return dict(DEFAULT_ENV)


def save_env(env):
    lines = ["# OBS WebSocket bridge configuration — written by setup_obs_gui.bat / obs_gui.py",
             "# Edit by hand or re-run setup_obs_gui.bat to change values.",
             ""]
    for k, v in env.items():
        lines.append(f"{k}={v}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


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
        save_env(env)
        self.env = env
        messagebox.showinfo("Saved", ".env written.")

    # ------------------------------------------------------------------ bridge process

    def _start_bridge(self):
        if self.process is not None and self.process.poll() is None:
            messagebox.showwarning("Already running", "The bridge is already running.")
            return

        env = self._collect_env()
        save_env(env)
        self.env = env

        script = os.path.join(ROOT, "demo_main.py")
        python = sys.executable or "python"
        try:
            self.process = subprocess.Popen(
                [python, script],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            messagebox.showerror("Start failed", str(e))
            return

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.status_var.set("Running")
        self._log_ui(f"Bridge started (PID {self.process.pid})")
        self._log_ui(f"OBS: {env.get('OBS_HOST')}:{env.get('OBS_PORT')} scene={env.get('OBS_SCENE')} source={env.get('OBS_SOURCE')}")

    def _stop_bridge(self):
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        self.process = None
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self._log_ui("Bridge stopped.")

    # ------------------------------------------------------------------ log plumbing

    def _poll_process(self):
        if self.process is None:
            self.after(200, self._poll_process)
            return
        line = self.process.stdout.readline()
        if line:
            self.log_queue.append(line.rstrip("\n"))
        if self.process.poll() is not None:
            remaining = self.process.stdout.read()
            if remaining:
                for ln in remaining.splitlines():
                    self.log_queue.append(ln)
            self._log_ui(f"[process exited code {self.process.returncode}]")
            self.process = None
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            self.status_var.set("Stopped")
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
        self._stop_bridge()
        self.destroy()


if __name__ == "__main__":
    app = OBSBridgeGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
