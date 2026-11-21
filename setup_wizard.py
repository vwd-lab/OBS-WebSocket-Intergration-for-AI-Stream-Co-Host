"""Interactive setup for the OBS WebSocket kit: asks a few questions, writes .env.

Run by setup_obs_gui.bat, or directly:  python setup_wizard.py
- Other lines already in .env (your own settings, comments) are kept.
- Uses only the Python standard library, so it works before `pip install`.
- Press Enter to keep the value shown in [brackets]. Type - to clear a value.
- Secrets (passwords, tokens) are not shown while you type them.
- Exits with code 1 and writes nothing if setup is cancelled or fails, so the
  .bat file knows not to launch the GUI.

Replaces the multi-line `python -c "..."` the .bat used before: cmd.exe can't
pass a multi-line string, so the settings were never actually written.
"""
import getpass
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
HEADER = ["# OBS WebSocket bridge configuration - written by setup_obs_gui.bat / obs_gui.py",
          "# Edit by hand or re-run setup_obs_gui.bat to change values.",
          ""]

# (key, question, default, kind[, options])
QUESTIONS = [
    ("OBS_ENABLED", "Enable OBS overlay?", "1", "yesno"),
    ("OBS_HOST", "OBS WebSocket host", "localhost", "text"),
    ("OBS_PORT", "OBS WebSocket port", "4455", "port"),
    ("OBS_PASSWORD", "OBS WebSocket password (Tools > WebSocket Server Settings)", "", "secret"),
    ("OBS_SCENE", "Scene name containing the image source", "Main", "text"),
    ("OBS_SOURCE", "Exact Image source name in that scene", "Bot Name", "text"),
    ("OBS_HIDE_ON_CONNECT", "Hide the image when the bot connects?", "1", "yesno"),
    ("OBS_TIMEOUT_S", "Connection timeout in seconds", "3.0", "seconds"),
]

# ---------------------------------------------------------------- shared helpers
# (The same helper code is used in the OBS, Discord and Kick kits.)
class Cancelled(Exception):
    pass


def read_line(prompt, secret=False):
    try:
        if secret and sys.stdin.isatty():
            return getpass.getpass(prompt)
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        raise Cancelled()


def ask(question, current, kind, options=None):
    """Ask until the answer is valid. Returns the value as a string.

    kind: text | secret | yesno | port | count | seconds | id | idlist | choice
    """
    while True:
        if kind == "yesno":
            shown = "yes" if current == "1" else "no"
            raw = read_line(f"{question} [yes/no] [{shown}]: ").strip().lower()
            if not raw:
                return current
            if raw in ("y", "yes", "1", "true", "on"):
                return "1"
            if raw in ("n", "no", "0", "false", "off"):
                return "0"
            print("  Please answer yes or no.")
            continue
        if kind == "secret":
            shown = "keep current" if current else "none"
            raw = read_line(f"{question} [{shown}]: ", secret=True).strip()
        elif kind == "choice":
            raw = read_line(f"{question} [{'/'.join(options)}] [{current}]: ").strip().lower()
        else:
            raw = read_line(f"{question} [{current}]: ").strip()
        if not raw:
            return current
        if raw == "-" and kind not in ("port", "count", "seconds", "choice"):
            return ""
        if "\n" in raw or "\r" in raw:
            print("  That can't contain a line break.")
            continue
        if kind == "port":
            if raw.isdigit() and 0 < int(raw) < 65536:
                return raw
            print("  Please enter a port number between 1 and 65535.")
        elif kind == "count":
            if raw.isdigit() and int(raw) > 0:
                return raw
            print("  Please enter a whole number of 1 or more.")
        elif kind == "seconds":
            try:
                if float(raw) > 0:
                    return raw
            except ValueError:
                pass
            print("  Please enter a number of seconds, e.g. 3.0.")
        elif kind == "id":
            if raw.isdigit():
                return raw
            print("  Please enter the ID as digits only (right-click > Copy ID in Discord).")
        elif kind == "idlist":
            ids = [p.strip() for p in raw.split(",") if p.strip()]
            if ids and all(p.isdigit() for p in ids):
                return ",".join(ids)
            print("  Please enter digits only, separated by commas, e.g. 123456789012345678.")
        elif kind == "choice":
            if raw in options:
                return raw
            print(f"  Please choose one of: {', '.join(options)}.")
        else:
            return raw


def ask_all(questions, current):
    answers = {}
    for key, question, default, kind, *rest in questions:
        options = rest[0] if rest else None
        answers[key] = ask(question, current.get(key, default), kind, options)
    return answers


def save_atomically(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# Characters that change a value's meaning when it's written bare (KEY=value):
# " #" starts a comment, quotes are removed, "${X}" is replaced, and spaces at
# either end are dropped. A value with any of them is written in quotes.
_NEEDS_QUOTES = set("#'\"\\$")


def env_quote(value):
    """Write a value so python-dotenv reads back exactly the same text.

    Simple values stay bare (OBS_PORT=4455). Anything else goes in single
    quotes; inside those only \\\\ and \\' are special, so those two are
    escaped. (The kit's config.py reads .env with "${...}" replacement off.)
    """
    value = str(value)
    if value == value.strip() and not (_NEEDS_QUOTES & set(value)):
        return value
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


_DOUBLE_QUOTE_ESCAPES = {"\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b",
                         "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}


def env_unquote(raw):
    """Read a value the way python-dotenv does: quoted values lose their quotes
    (and escapes), and a bare value ends at " #" (a comment)."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        quote, out, i = raw[0], [], 1
        while i < len(raw):
            c = raw[i]
            if c == "\\" and i + 1 < len(raw):
                nxt = raw[i + 1]
                if quote == "'" and nxt in "\\'":
                    out.append(nxt)
                    i += 2
                    continue
                if quote == '"' and nxt in _DOUBLE_QUOTE_ESCAPES:
                    out.append(_DOUBLE_QUOTE_ESCAPES[nxt])
                    i += 2
                    continue
            if c == quote:
                return "".join(out)
            out.append(c)
            i += 1
        return raw            # no closing quote: dotenv keeps it as typed
    for i, c in enumerate(raw):
        if c == "#" and i > 0 and raw[i - 1] in " \t":
            return raw[:i].strip()
    return raw


def _env_key(stripped_line):
    k = stripped_line.split("=", 1)[0].strip()
    if k.startswith("export "):
        k = k[len("export "):].strip()
    return k


def read_env(path):
    """Return (lines, values) from an existing .env, or ([], {})."""
    if not os.path.exists(path):
        return [], {}
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    values = {}
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            values[_env_key(s)] = env_unquote(s.split("=", 1)[1])
    return lines, values


def write_env(path, lines, answers, header):
    """Update answered keys in place, append new ones, keep everything else.

    Values that need it are quoted (see env_quote), so a password like
    "abc #1" isn't cut short to "abc" when the bridge reads .env. The kit's
    GUI saves through this same function.
    """
    out, done = [], set()
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = _env_key(s)
            if k in answers:
                if k not in done:
                    out.append(f"{k}={env_quote(answers[k])}")
                    done.add(k)
                continue
        out.append(line)
    if not lines:
        out = list(header)
    for k, v in answers.items():
        if k not in done:
            out.append(f"{k}={env_quote(v)}")
    save_atomically(path, "\n".join(out) + "\n")


def intro():
    print()
    print("Press Enter to keep the value in [brackets]. Type - to clear a value.")
    print()


# ---------------------------------------------------------------- main
def main():
    intro()
    lines, current = read_env(ENV_PATH)
    try:
        answers = ask_all(QUESTIONS, current)
    except Cancelled:
        print("\nSetup cancelled - nothing was written.")
        return 1
    try:
        write_env(ENV_PATH, lines, answers, HEADER)
    except OSError as e:
        print(f"\nCould not write {ENV_PATH}: {e}")
        return 1
    print(f"\nSaved {ENV_PATH}")
    if not answers["OBS_PASSWORD"]:
        print("Note: no OBS password set. OBS listens on your whole network, so anyone on it")
        print("could control OBS. Set one in OBS (Tools > WebSocket Server Settings) and here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
