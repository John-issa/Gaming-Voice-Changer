"""Start the stock RVC realtime GUI with a voice preset and a global vc/im toggle hotkey.

Run it with the engine's bundled Python (scripts/launch.ps1 does this for you):

    engine\\runtime\\python.exe -I vcgui\\hotkey_launcher.py --engine engine --preset vctk-p231

Stdlib only, plus the engine's own sounddevice and FreeSimpleGUI. No engine file is
modified: the launcher writes engine/configs/config.json (the file the GUI itself
saves), patches FreeSimpleGUI.Window.read in memory, and runs realtime_gui.py via runpy.
The hotkey only listens; it never sends input to any window.
"""

import argparse
import atexit
import ctypes
import json
import os
import queue
import re
import runpy
import sys
import threading
import time
from ctypes import wintypes

try:
    import winsound
except ImportError:  # only the cue sounds need it
    winsound = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_TITLE = "RVC - GUI"
TOGGLE_EVENT = "__HOTKEY_TOGGLE__"
POLL_MS = 50  # the GUI's read() wakes this often to apply queued work (hotkey, audio-thread updates)
RESTART_DELAY = 0.8  # s of quiet after a timing-slider change before conversion restarts
# Events realtime_gui's handler applies live; every other event (except start_vc) stops the stream.
LIVE_EVENTS = frozenset(("vc", "im", "threhold", "pitch", "formant", "index_rate", "rms_mix_rate",
                         "pm", "rmvpe", "fcpe", "I_noise_reduce", "O_noise_reduce"))
# Sliders that stop the stream; conversion restarts by itself once they settle, if it was running.
RESTART_EVENTS = frozenset(("block_time", "crossfade_length", "extra_time"))
DEFAULT_PRESET = "vctk-p231"

# realtime_gui.py load() indexes these with data[...] inside a bare try/except; a missing
# one makes it silently overwrite config.json with defaults and drop the preset.
REQUIRED_KEYS = ("pth_path", "index_path", "sg_hostapi", "sg_input_device",
                 "sg_output_device", "sr_type", "f0method")
SR_TYPES = ("sr_model", "sr_device")
F0_METHODS = ("pm", "rmvpe", "fcpe")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
MODIFIERS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
             "shift": MOD_SHIFT, "win": MOD_WIN}
MODIFIER_VKS = {MOD_CONTROL: (0x11,), MOD_ALT: (0x12,), MOD_SHIFT: (0x10,),
                MOD_WIN: (0x5B, 0x5C)}
NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "left": 0x25, "up": 0x26, "right": 0x27,
    "down": 0x28, "pause": 0x13, "scrolllock": 0x91, "grave": 0xC0, "minus": 0xBD,
    "equals": 0xBB, "lbracket": 0xDB, "rbracket": 0xDD, "backslash": 0xDC,
    "semicolon": 0xBA, "quote": 0xDE, "comma": 0xBC, "period": 0xBE, "slash": 0xBF,
    "numpadadd": 0x6B, "numpadsubtract": 0x6D, "numpadmultiply": 0x6A,
    "numpaddivide": 0x6F, "numpaddecimal": 0x6E,
}
NUMPAD_DIGITS = tuple(range(0x60, 0x6A)) + (0x6E,)  # numpad0-9 + decimal: only with NumLock on
VK_NUMLOCK = 0x90
WM_QUIT, WM_HOTKEY, PM_NOREMOVE = 0x0012, 0x0312, 0x0000
HOTKEY_ID = 1


class LaunchError(Exception):
    """A setup problem the user has to fix; printed without a traceback."""


# ---------------------------------------------------------------- config.json


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise LaunchError(f"{what} not found: {path}")
    except ValueError as e:
        raise LaunchError(f"{what} is not valid JSON ({path}): {e}")
    if not isinstance(data, dict):
        raise LaunchError(f"{what} must be a JSON object: {path}")
    return data


def read_engine_config(path):
    """The GUI's current config.json, or {} if it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def devices_by_hostapi(sd):
    """{hostapi name: (input names, output names)}, built the way realtime_gui.update_devices does."""
    devices = sd.query_devices()
    result = {}
    for api in sd.query_hostapis():
        inputs = [devices[i]["name"] for i in api["devices"] if devices[i]["max_input_channels"] > 0]
        outputs = [devices[i]["name"] for i in api["devices"] if devices[i]["max_output_channels"] > 0]
        result[api["name"]] = (inputs, outputs)
    return result


def default_samplerate(sd, hostapi, name, kind):
    """default_samplerate (the shared-mode mix rate for WASAPI) of an input/output device, or None."""
    devices = sd.query_devices()
    for api in sd.query_hostapis():
        if api["name"] == hostapi:
            for i in api["devices"]:
                if devices[i]["name"] == name and devices[i][f"max_{kind}_channels"] > 0:
                    return devices[i].get("default_samplerate")
    return None


def match_device(names, substrings, kind, hostapi):
    """Exact device name whose name contains every substring (case-insensitive)."""
    if isinstance(substrings, str):
        substrings = [substrings]
    wanted = [s.lower() for s in substrings or [] if s]
    if not wanted:
        raise LaunchError(f"config/audio.json: {kind}_device_match is empty")
    matches = []
    for name in names:
        if all(s in name.lower() for s in wanted) and name not in matches:
            matches.append(name)
    if len(matches) == 1:
        return matches[0]
    listing = "\n".join(f"    {n}" for n in names) or "    (none)"
    if not matches:
        hint = {"input": "Is the headset connected and its mic enabled?",
                "output": "Is VB-CABLE installed (see docs/windows-audio.md)?"}[kind]
        raise LaunchError(f"No {hostapi} {kind} device matches {substrings}. {hint}\n"
                          f"  {kind.capitalize()} devices in {hostapi}:\n{listing}")
    raise LaunchError(f"{len(matches)} {hostapi} {kind} devices match {substrings}: {matches}. "
                      f"Add a more specific substring to {kind}_device_match in config/audio.json.")


def model_path(value, key, repo):
    """Absolute, existing, ASCII-only path for pth_path/index_path (the GUI rejects non-ASCII)."""
    if not isinstance(value, str) or not value.strip():
        raise LaunchError(f"The preset has no {key}.")
    path = os.path.normpath(value if os.path.isabs(value) else os.path.join(repo, value))
    if not os.path.isfile(path):
        raise LaunchError(f"{key} not found: {path}\n  Download the voice with scripts\\get-models.ps1.")
    if not path.isascii():
        raise LaunchError(f"{key} has non-ASCII characters, which the RVC GUI rejects: {path}\n"
                          "  Move the repo to a folder whose path is plain ASCII.")
    return path


def build_config(engine, preset_id, sd, repo=REPO):
    """Merge engine config.json <- audio.json settings <- preset settings, then fix paths and devices."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", preset_id or ""):
        raise LaunchError(f"Invalid preset name: {preset_id!r}")
    audio = load_json(os.path.join(repo, "config", "audio.json"), "config/audio.json")
    preset = load_json(os.path.join(repo, "config", "presets", preset_id + ".json"),
                       f"Preset {preset_id!r}")

    cfg = read_engine_config(os.path.join(engine, "configs", "config.json"))
    cfg.update(audio.get("settings", {}))
    cfg.update(preset.get("settings", {}))
    for key in ("pth_path", "index_path"):
        cfg[key] = model_path(cfg.get(key), key, repo)

    hostapi = audio.get("hostapi")
    apis = devices_by_hostapi(sd)
    if hostapi not in apis:
        raise LaunchError(f"config/audio.json hostapi {hostapi!r} not found. Available: {list(apis)}")
    inputs, outputs = apis[hostapi]
    cfg["sg_hostapi"] = hostapi
    cfg["sg_input_device"] = match_device(inputs, audio.get("input_device_match"), "input", hostapi)
    cfg["sg_output_device"] = match_device(outputs, audio.get("output_device_match"), "output", hostapi)

    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise LaunchError(f"Missing config keys {missing}: set them in config/audio.json or the preset. "
                          "Without them the GUI silently resets config.json to its defaults.")
    if cfg["sr_type"] not in SR_TYPES:
        raise LaunchError(f"sr_type must be one of {SR_TYPES}, got {cfg['sr_type']!r}")
    if cfg["f0method"] not in F0_METHODS:
        raise LaunchError(f"f0method must be one of {F0_METHODS}, got {cfg['f0method']!r}")
    if "WASAPI" in hostapi and not cfg.get("sg_wasapi_exclusive"):
        # The GUI opens one duplex stream at the input's rate without WASAPI auto-convert, so a
        # rate mismatch raises PortAudioError on Start and the window just disappears.
        rate_in = default_samplerate(sd, hostapi, cfg["sg_input_device"], "input")
        rate_out = default_samplerate(sd, hostapi, cfg["sg_output_device"], "output")
        if rate_in and rate_out and rate_in != rate_out:
            raise LaunchError(f"Sample rates differ: '{cfg['sg_input_device']}' runs at {rate_in:g} Hz but "
                              f"'{cfg['sg_output_device']}' at {rate_out:g} Hz, and the RVC GUI can't convert "
                              "between them in WASAPI shared mode.\n  Set both (and both sides of the cable) "
                              "to 48000 Hz in the Sound control panel; see docs/windows-audio.md.")
        if cfg["sr_type"] != "sr_device":
            print("WARNING: WASAPI shared mode needs sr_type 'sr_device'; 'sr_model' will mismatch the device rate.")
    return cfg, preset


def write_engine_config(engine, cfg):
    path = os.path.join(engine, "configs", "config.json")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        raise LaunchError(f"Could not write {path}: {e}")
    return path


def print_devices(sd):
    for api, (inputs, outputs) in devices_by_hostapi(sd).items():
        print(f"== {api}")
        print("  inputs:")
        for name in inputs:
            print(f"    {name}")
        print("  outputs:")
        for name in outputs:
            print(f"    {name}")


def print_presets(repo=REPO):
    folder = os.path.join(repo, "config", "presets")
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            label = load_json(os.path.join(folder, name), name).get("label", "")
            print(f"{name[:-5]:<16} {label}")


# ---------------------------------------------------------------- hotkey


def key_code(name):
    if len(name) == 1 and ("a" <= name <= "z" or "0" <= name <= "9"):
        return ord(name.upper())
    m = re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", name)
    if m:
        return 0x6F + int(m.group(1))  # VK_F1 = 0x70
    m = re.fullmatch(r"numpad([0-9])", name)
    if m:
        return 0x60 + int(m.group(1))  # VK_NUMPAD0 = 0x60
    return NAMED_KEYS.get(name)


def parse_hotkey(combo):
    """'ctrl+alt+v' -> (MOD_* flags, virtual-key code). Raises ValueError."""
    mods, vk = 0, None
    for part in str(combo).lower().replace(" ", "").split("+"):
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
            continue
        if vk is not None:
            raise ValueError(f"hotkey {combo!r} has more than one non-modifier key")
        vk = key_code(part)
        if vk is None:
            raise ValueError(f"hotkey {combo!r}: unknown key {part!r}")
    if vk is None:
        raise ValueError(f"hotkey {combo!r} has no key, e.g. 'ctrl+alt+v'")
    if not mods and (0x30 <= vk <= 0x5A or vk == 0x20):
        raise ValueError(f"hotkey {combo!r} needs a modifier; a bare letter, digit or space "
                         "would be swallowed in every app")
    if mods & MOD_CONTROL and vk in (0x13, 0x91):
        raise ValueError(f"hotkey {combo!r} can't work: Windows reports Ctrl+Pause/ScrollLock as Break")
    if mods & MOD_SHIFT and vk in NUMPAD_DIGITS:
        raise ValueError(f"hotkey {combo!r} can't work: Windows turns Shift+numpad keys into navigation keys")
    return mods, vk


_USER32 = None


def user32():
    """A private user32 handle, so these argtypes don't leak into other ctypes users."""
    global _USER32
    if _USER32 is None:
        u = ctypes.WinDLL("user32", use_last_error=True)
        lpmsg = ctypes.POINTER(wintypes.MSG)
        u.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        u.RegisterHotKey.restype = wintypes.BOOL
        u.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        u.UnregisterHotKey.restype = wintypes.BOOL
        u.GetMessageW.argtypes = (lpmsg, wintypes.HWND, wintypes.UINT, wintypes.UINT)
        u.GetMessageW.restype = wintypes.BOOL
        u.PeekMessageW.argtypes = (lpmsg, wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT)
        u.PeekMessageW.restype = wintypes.BOOL
        u.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.PostThreadMessageW.restype = wintypes.BOOL
        u.GetAsyncKeyState.argtypes = (ctypes.c_int,)
        u.GetAsyncKeyState.restype = ctypes.c_short
        u.GetKeyState.argtypes = (ctypes.c_int,)
        u.GetKeyState.restype = ctypes.c_short
        _USER32 = u
    return _USER32


def safe_call(callback):
    try:
        callback()
    except Exception as e:  # keep the listener alive whatever the GUI does
        print(f"[hotkey] toggle failed: {e!r}")


class RegisteredHotkey(threading.Thread):
    """RegisterHotKey(NULL, ...) + GetMessageW loop; WM_HOTKEY arrives on this thread's queue."""

    def __init__(self, mods, vk, callback):
        super().__init__(name="hotkey-register", daemon=True)
        self.mods, self.vk, self.callback = mods, vk, callback
        self.ready = threading.Event()
        self.error = None
        self.thread_id = None

    def run(self):
        u = user32()
        msg = wintypes.MSG()
        u.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)  # create the message queue
        self.thread_id = threading.get_native_id()
        if not u.RegisterHotKey(None, HOTKEY_ID, self.mods | MOD_NOREPEAT, self.vk):
            self.error = ctypes.FormatError(ctypes.get_last_error()).strip()
            self.ready.set()
            return
        self.ready.set()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    safe_call(self.callback)
        finally:
            u.UnregisterHotKey(None, HOTKEY_ID)

    def stop(self):
        if self.thread_id:
            user32().PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


def combo_down(mods, vk, key_down):
    """True if vk is down with exactly the requested modifiers (RegisterHotKey semantics)."""
    if not key_down(vk):
        return False
    return all(bool(mods & flag) == any(key_down(v) for v in vks)
               for flag, vks in MODIFIER_VKS.items())


class PolledHotkey(threading.Thread):
    """Fallback: poll GetAsyncKeyState and fire once per press (edge-triggered)."""

    def __init__(self, mods, vk, callback, interval_ms=30, key_down=None):
        super().__init__(name="hotkey-poll", daemon=True)
        self.mods, self.vk, self.callback = mods, vk, callback
        self.interval = max(5, int(interval_ms)) / 1000.0
        self.key_down = key_down or (lambda v: bool(user32().GetAsyncKeyState(v) & 0x8000))
        self._stop_event = threading.Event()
        self._was_down = False

    def run(self):
        while not self._stop_event.wait(self.interval):
            self.poll_once()

    def poll_once(self):
        down = combo_down(self.mods, self.vk, self.key_down)
        if down and not self._was_down:
            safe_call(self.callback)
        self._was_down = down

    def stop(self):
        self._stop_event.set()


def start_hotkey(cfg, callback):
    combo = cfg.get("toggle", "ctrl+alt+v")
    method = cfg.get("method", "registerhotkey")
    interval = cfg.get("poll_interval_ms", 30)
    try:
        mods, vk = parse_hotkey(combo)
    except ValueError as e:
        raise LaunchError(f"config/hotkey.json: {e}")
    if method not in ("registerhotkey", "poll"):
        raise LaunchError(f"config/hotkey.json: method must be 'registerhotkey' or 'poll', got {method!r}")
    if vk in NUMPAD_DIGITS and not user32().GetKeyState(VK_NUMLOCK) & 1:
        print(f"[hotkey] NumLock is off: {combo} only works while NumLock is on.")
    if method == "registerhotkey":
        listener = RegisteredHotkey(mods, vk, callback)
        listener.start()
        if not listener.ready.wait(5):
            listener.error = "no answer from the hotkey thread"
        if listener.error is None:
            print(f"[hotkey] {combo} toggles the voice changer (RegisterHotKey)")
            return listener
        print(f"[hotkey] RegisterHotKey({combo}) failed: {listener.error}\n"
              f"[hotkey] Falling back to polling the keyboard every {interval} ms.")
    listener = PolledHotkey(mods, vk, callback, interval)
    listener.start()
    print(f"[hotkey] {combo} toggles the voice changer (polling every {interval} ms)")
    return listener


# ---------------------------------------------------------------- console


class ConsoleWriter:
    """stdout/stderr that never block the caller: a daemon thread does the actual writing.

    The engine prints two lines per audio block from the PortAudio callback. A console write can
    block (QuickEdit selection, Pause, a slow console), which would stall the audio thread; here
    only the writer thread waits. Optionally tees everything into a log file.
    """

    def __init__(self, stdout, stderr, log_path=None, maxsize=20000):
        self.queue = queue.Queue(maxsize)
        self.dropped = 0
        self.log = open(log_path, "a", encoding="utf-8", errors="backslashreplace") if log_path else None
        self.stdout = _QueuedStream(self, stdout)
        self.stderr = _QueuedStream(self, stderr)
        self.thread = threading.Thread(target=self._run, name="console-writer", daemon=True)
        self.thread.start()

    def put(self, target, text):
        try:
            self.queue.put_nowait((target, text))
        except queue.Full:
            self.dropped += 1

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                return
            target, text = item
            for out in (target, self.log):
                if out is not None:
                    try:
                        out.write(text)
                        if self.queue.empty():
                            out.flush()
                    except Exception:
                        pass

    def close(self, timeout=2.0):
        """Write what is queued (at exit), then stop the thread."""
        try:
            self.queue.put(None, timeout=timeout)
        except queue.Full:
            return
        self.thread.join(timeout)
        if self.log:
            self.log.close()


class _QueuedStream:
    def __init__(self, writer, target):
        self._writer, self._target = writer, target

    def write(self, text):
        self._writer.put(self._target, text)
        return len(text)

    def flush(self):
        pass

    def __getattr__(self, name):  # encoding, isatty, fileno, ...
        return getattr(self._target, name)


def install_console_writer(log_path=None):
    writer = ConsoleWriter(sys.stdout, sys.stderr, log_path)
    sys.stdout, sys.stderr = writer.stdout, writer.stderr
    atexit.register(writer.close)
    return writer


ENABLE_QUICK_EDIT_MODE, ENABLE_EXTENDED_FLAGS = 0x0040, 0x0080


def disable_quick_edit(kernel32=None):
    """Clear QuickEdit on this console (restored at exit): a click into it can't freeze output.

    Returns the original mode, or None when there is no console or nothing to change.
    """
    if kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetConsoleMode.restype = wintypes.BOOL
        kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.SetConsoleMode.restype = wintypes.BOOL
    handle = kernel32.GetStdHandle(wintypes.DWORD(-10 & 0xFFFFFFFF))  # STD_INPUT_HANDLE
    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return None  # input isn't a console
    if not mode.value & ENABLE_QUICK_EDIT_MODE:
        return None
    new = (mode.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE
    if not kernel32.SetConsoleMode(handle, new):
        return None
    atexit.register(kernel32.SetConsoleMode, handle, mode.value)
    return mode.value


# ---------------------------------------------------------------- GUI patch


def play_cue(path):
    if not path or winsound is None:
        return
    try:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception as e:
        print(f"[hotkey] cue sound failed ({path}): {e}")


class Toggle:
    """Hotkey presses, handed from the hotkey thread to the GUI thread without touching Tk."""

    def __init__(self, cue_vc="", cue_im=""):
        self.window = None
        self.cues = {"vc": cue_vc, "im": cue_im}
        self._pending = 0
        self._lock = threading.Lock()

    def fire(self):  # hotkey thread
        if self.window is None:
            print("[hotkey] ignored: the RVC window is not open yet")
            return
        with self._lock:
            self._pending += 1

    def take(self):  # GUI thread
        with self._lock:
            if not self._pending:
                return False
            self._pending -= 1
            return True


class DeferredUpdates:
    """Element updates made off the GUI thread are queued and applied by the GUI thread.

    realtime_gui's audio callback updates "Inference time (ms)" every block from the PortAudio
    thread. A cross-thread Tk call waits for the GUI thread, so a busy GUI (slider drags, event
    handling) stalls the audio, and stop_stream() - which waits for the callback - can hang ~1 s.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pending = {}

    def wrap(self, cls):
        original = cls.update
        deferred = self

        def update(element, *args, **kwargs):
            if threading.current_thread() is threading.main_thread():
                return original(element, *args, **kwargs)
            with deferred._lock:
                deferred._pending[id(element)] = (original, element, args, kwargs)  # latest wins

        cls.update = update

    def apply(self):
        with self._lock:
            items, self._pending = list(self._pending.values()), {}
        for original, element, args, kwargs in items:
            try:
                original(element, *args, **kwargs)
            except Exception:
                pass


class AutoRestart:
    """Restart conversion after a timing slider (which stops the stream) settles, if it was running."""

    def __init__(self, delay=RESTART_DELAY):
        self.delay = delay
        self.running = False
        self.due = None

    def observe(self, event, now):
        if event == "start_vc":
            self.running, self.due = True, None
        elif event in LIVE_EVENTS:
            pass
        elif event in RESTART_EVENTS:
            if self.running or self.due is not None:
                self.due = now + self.delay  # every further slider event pushes it out
            self.running = False
        else:  # stop_vc, devices, sample-rate option, ...: the user decides
            self.running, self.due = False, None

    def ready(self, now):
        if self.due is not None and now >= self.due:
            self.running, self.due = True, None
            return True
        return False


def flip(window, values, toggle):
    """Select the other vc/im radio and return the stock radio event for it."""
    try:
        vc_on = bool(window["vc"].get())
    except Exception:
        vc_on = bool(values.get("vc"))
    key = "im" if vc_on else "vc"
    try:
        window[key].update(value=True)  # sets the tk variable; no extra event is generated
    except Exception as e:
        print(f"[hotkey] could not update the {key} radio: {e!r}")
    values = dict(values or {})
    values.pop(TOGGLE_EVENT, None)
    values["vc"], values["im"] = key == "vc", key == "im"
    play_cue(toggle.cues[key])
    print("[hotkey] voice changer ON (vc)" if key == "vc" else "[hotkey] voice changer OFF (im: raw mic)")
    return key, values


def patch_window(sg, toggle, clock=time.monotonic, poll_ms=POLL_MS, restart_delay=RESTART_DELAY):
    """Patch FreeSimpleGUI so the stock GUI gets the hotkey, never blocks audio, and restarts itself.

    For the "RVC - GUI" window, read() (called by realtime_gui without a timeout) becomes a loop of
    short reads: in between it applies deferred element updates, turns hotkey presses into the stock
    "vc"/"im" radio events, and after a timing-slider change sends "start_vc" once the slider has
    settled. Timeouts never reach the stock handler, which would stop the stream on unknown events.
    Popups (sg.popup) also call read(); only the main window is affected.
    """
    original = sg.Window.read
    timeout_key = getattr(sg, "TIMEOUT_KEY", "__TIMEOUT__")
    deferred = DeferredUpdates()
    deferred.wrap(sg.Text)
    restart = AutoRestart(restart_delay)

    def read(self, *args, **kwargs):
        if getattr(self, "Title", None) != GUI_TITLE:
            return original(self, *args, **kwargs)
        toggle.window = self
        if args or kwargs.get("timeout") is not None:
            return original(self, *args, **kwargs)
        while True:
            event, values = original(self, timeout=poll_ms)
            deferred.apply()
            if event is None:  # sg.WIN_CLOSED
                toggle.window = None
                return event, values
            if event == TOGGLE_EVENT:  # posted with write_event_value by older callers
                return flip(self, values, toggle)
            if event == timeout_key:
                if toggle.take():
                    return flip(self, values, toggle)
                if restart.ready(clock()):
                    print("[launcher] restarting conversion with the new setting...")
                    return "start_vc", values
                continue
            restart.observe(event, clock())
            return event, values

    sg.Window.read = read
    return original


def run_gui(engine):
    gui_path = os.path.join(engine, "realtime_gui.py")
    os.chdir(engine)
    sys.path.insert(0, engine)
    sys.argv = [gui_path]  # configs/config.py parses sys.argv; our flags would crash it
    runpy.run_path(gui_path, run_name="__main__")


# ---------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", default=os.path.join(REPO, "engine"), help="RVC package folder")
    parser.add_argument("--preset", default=DEFAULT_PRESET, help="config/presets/<name>.json")
    parser.add_argument("--list-devices", action="store_true", help="print audio devices per host API")
    parser.add_argument("--list-presets", action="store_true", help="print the available presets")
    parser.add_argument("--log", help="also append all console output (incl. per-block timings) to this file")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # under -I, redirected output is cp1252 whatever the env says
            stream.reconfigure(errors="backslashreplace")
    engine = os.path.abspath(args.engine)
    try:
        if args.list_presets:
            print_presets()
            return 0
        import sounddevice as sd
        if args.list_devices:
            print_devices(sd)
            return 0
        if not os.path.isfile(os.path.join(engine, "realtime_gui.py")):
            raise LaunchError(f"realtime_gui.py not found in {engine}. Run scripts\\install-engine.ps1.")
        cfg, preset = build_config(engine, args.preset, sd)
        path = write_engine_config(engine, cfg)
        hotkey = load_json(os.path.join(REPO, "config", "hotkey.json"), "config/hotkey.json")
        import FreeSimpleGUI as sg
        toggle = Toggle(hotkey.get("cue_vc", ""), hotkey.get("cue_im", ""))
        patch_window(sg, toggle)
        start_hotkey(hotkey, toggle.fire)
    except LaunchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    install_console_writer(os.path.abspath(args.log) if args.log else None)
    disable_quick_edit()
    print(f"Preset : {args.preset} - {preset.get('label', '')}")
    print(f"Model  : {cfg['pth_path']}")
    print(f"Input  : {cfg['sg_input_device']}")
    print(f"Output : {cfg['sg_output_device']}  ({cfg['sg_hostapi']})")
    print(f"Wrote  : {path}")
    print("Click 'Start audio conversion' in the RVC window to begin.")
    run_gui(engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
