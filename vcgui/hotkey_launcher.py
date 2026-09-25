"""Start the stock RVC realtime GUI with a voice preset and a global vc/im toggle hotkey.

Run it with the engine's bundled Python (scripts/launch.ps1 does this for you):

    engine\\runtime\\python.exe -I vcgui\\hotkey_launcher.py --engine engine --preset vctk-p231

Stdlib only, plus the engine's own sounddevice and FreeSimpleGUI. No engine file is
modified: the launcher writes engine/configs/config.json (the file the GUI itself
saves), patches FreeSimpleGUI.Window.read in memory, and runs realtime_gui.py via runpy.
The hotkey only listens; it never sends input to any window.
"""

import argparse
import ctypes
import json
import os
import re
import runpy
import sys
import threading
from ctypes import wintypes

try:
    import winsound
except ImportError:  # only the cue sounds need it
    winsound = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_TITLE = "RVC - GUI"
TOGGLE_EVENT = "__HOTKEY_TOGGLE__"
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
    user32()
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


# ---------------------------------------------------------------- GUI patch


def play_cue(path):
    if not path or winsound is None:
        return
    try:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception as e:
        print(f"[hotkey] cue sound failed ({path}): {e}")


class Toggle:
    """Shared by the hotkey thread (fire) and the GUI thread (the patched Window.read)."""

    def __init__(self, cue_vc="", cue_im=""):
        self.window = None
        self.cues = {"vc": cue_vc, "im": cue_im}

    def fire(self):
        window = self.window
        if window is None:
            print("[hotkey] ignored: the RVC window is not open yet")
            return
        queue = getattr(window, "thread_queue", None)
        strvar = getattr(window, "thread_strvar", None)
        if queue is None or strvar is None:
            window.write_event_value(TOGGLE_EVENT, None)
            return
        # Window.write_event_value minus its tk.willdispatch(): forcing Tk's "dispatching" flag
        # from this thread can deadlock the GUI if the main thread is waiting for the audio
        # thread (stop_stream) at that moment. read() returns queued events first anyway.
        queue.put((TOGGLE_EVENT, None))
        try:
            strvar.set("new item")  # wakes a read() that is waiting in mainloop
        except RuntimeError:
            pass  # main thread busy outside mainloop; its next read() picks the event up


def patch_window_read(sg, toggle):
    """Turn TOGGLE_EVENT into the stock 'vc'/'im' radio event; everything else passes through.

    realtime_gui's handler stops the stream on any event it doesn't know, so the custom
    event must never reach it. Popups (sg.popup) also call read(); only the main window counts.
    """
    original = sg.Window.read

    def read(self, *args, **kwargs):
        is_gui = getattr(self, "Title", None) == GUI_TITLE
        if is_gui:
            toggle.window = self  # before blocking, so a hotkey during this read is delivered
        result = original(self, *args, **kwargs)
        if not is_gui:
            return result
        event, values = result
        if event is None:  # sg.WIN_CLOSED
            toggle.window = None
            return result
        if event != TOGGLE_EVENT:
            return result
        try:
            vc_on = bool(self["vc"].get())
        except Exception:
            vc_on = bool(values.get("vc"))
        key = "im" if vc_on else "vc"
        try:
            self[key].update(value=True)  # sets the tk variable; no extra event is generated
        except Exception as e:
            print(f"[hotkey] could not update the {key} radio: {e!r}")
        values.pop(TOGGLE_EVENT, None)
        values["vc"], values["im"] = key == "vc", key == "im"
        play_cue(toggle.cues[key])
        print("[hotkey] voice changer ON (vc)" if key == "vc" else "[hotkey] voice changer OFF (im: raw mic)")
        return key, values

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
        patch_window_read(sg, toggle)
        start_hotkey(hotkey, toggle.fire)
    except LaunchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
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
