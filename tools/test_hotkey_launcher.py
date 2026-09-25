"""Stub-based tests for vcgui/hotkey_launcher.py. No engine, audio devices or real GUI needed.

    python tools\\test_hotkey_launcher.py

FreeSimpleGUI, sounddevice and realtime_gui.py are replaced by small stubs. The hotkey tests
register the unlikely combo ctrl+alt+shift+f24 for a moment and deliver WM_HOTKEY with
PostThreadMessageW, so no keyboard input is ever synthesized.
"""

import contextlib
import ctypes
import io
import json
import os
import queue
import runpy
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "vcgui"))
import hotkey_launcher as hl  # noqa: E402

TEST_COMBO = "ctrl+alt+shift+f24"
MAXWELL_IN = "Microphone (Chat-Audeze Maxwell)"  # real WASAPI name
CABLE_IN = "CABLE Input (VB-Audio Virtual Cable)"
DEVICES = {
    "MME": [
        ("Microsoft Sound Mapper - Input", 2, 0),
        ("Microphone (Chat-Audeze Maxwell", 1, 0),  # MME truncates names to 31 chars
        ("CABLE Input (VB-Audio Virtual C", 0, 2),
    ],
    "Windows WASAPI": [
        (MAXWELL_IN, 1, 0),
        ("Speakers (Chat-Audeze Maxwell)", 0, 2),
        ("Speakers (Game-Audeze Maxwell)", 0, 2),
        ("CABLE Output (VB-Audio Virtual Cable)", 2, 0),
        (CABLE_IN, 0, 2),
        ("Microphone (Voice.ai Audio Cable)", 2, 0),
    ],
}

FAKE_SOUNDDEVICE = '''
DEVICES = {devices!r}
_devices, _hostapis = [], []
for _api, _devs in DEVICES.items():
    _idx = []
    for _dev in _devs:
        _name, _ins, _outs = _dev[:3]
        _idx.append(len(_devices))
        _devices.append({{"name": _name, "index": len(_devices), "hostapi": len(_hostapis),
                          "max_input_channels": _ins, "max_output_channels": _outs,
                          "default_samplerate": _dev[3] if len(_dev) > 3 else 48000.0}})
    _hostapis.append({{"name": _api, "devices": _idx}})

def query_devices():
    return list(_devices)

def query_hostapis():
    return tuple(_hostapis)
'''


def fake_sd(devices=DEVICES):
    module = types.ModuleType("sounddevice")
    exec(FAKE_SOUNDDEVICE.format(devices=devices), module.__dict__)
    return module


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def make_repo(root, hotkey=None):
    """A throwaway repo: real config/ files, dummy voice files, and an engine/ with a configs/ dir."""
    shutil.copytree(os.path.join(REPO, "config"), os.path.join(root, "config"))
    for name in os.listdir(os.path.join(root, "config", "presets")):
        preset = read_json(os.path.join(root, "config", "presets", name))
        for key in ("pth_path", "index_path"):
            path = os.path.join(root, preset["settings"][key])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").close()
    if hotkey is not None:
        with open(os.path.join(root, "config", "hotkey.json"), "w", encoding="utf-8") as f:
            json.dump(hotkey, f)
    os.makedirs(os.path.join(root, "engine", "configs"))
    return os.path.join(root, "engine")


def upstream_load_accepts(data, sd):
    """The key accesses of realtime_gui.py GUI.load() (tag 2.3.260718), minus the GUI.

    Returns True if load() would keep our values, False if it would silently fall back.
    A KeyError here is what makes upstream rewrite config.json with its defaults.
    """
    data["sr_model"] = data["sr_type"] == "sr_model"
    data["sr_device"] = data["sr_type"] == "sr_device"
    if data.get("f0method") not in ("pm", "rmvpe", "fcpe"):
        data["f0method"] = "rmvpe"
    data["pm"] = data["f0method"] == "pm"
    apis = hl.devices_by_hostapi(sd)
    if data["sg_hostapi"] not in apis:
        return False
    inputs, outputs = apis[data["sg_hostapi"]]
    return data["sg_input_device"] in inputs and data["sg_output_device"] in outputs


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vcgui-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)


# ---------------------------------------------------------------- hotkey parsing


class ParseHotkeyTest(unittest.TestCase):
    def test_default_combo(self):
        self.assertEqual(hl.parse_hotkey("ctrl+alt+v"), (hl.MOD_CONTROL | hl.MOD_ALT, 0x56))

    def test_shipped_hotkey_json_parses(self):
        cfg = read_json(os.path.join(REPO, "config", "hotkey.json"))
        hl.parse_hotkey(cfg["toggle"])
        self.assertIn(cfg["method"], ("registerhotkey", "poll"))

    def test_case_spaces_and_aliases(self):
        self.assertEqual(hl.parse_hotkey(" Control + Shift + F13 "), (hl.MOD_CONTROL | hl.MOD_SHIFT, 0x7C))
        self.assertEqual(hl.parse_hotkey("win+alt+0"), (hl.MOD_WIN | hl.MOD_ALT, 0x30))

    def test_key_codes(self):
        cases = {"a": 0x41, "z": 0x5A, "0": 0x30, "9": 0x39, "f1": 0x70, "f12": 0x7B, "f24": 0x87,
                 "numpad0": 0x60, "numpad9": 0x69, "pause": 0x13, "grave": 0xC0, "space": 0x20,
                 "pageup": 0x21, "numpadadd": 0x6B}
        for name, vk in cases.items():
            with self.subTest(name=name):
                self.assertEqual(hl.parse_hotkey("alt+" + name), (hl.MOD_ALT, vk))

    def test_bare_function_key_allowed(self):
        self.assertEqual(hl.parse_hotkey("f13"), (0, 0x7C))

    def test_invalid(self):
        for combo in ("", "ctrl+alt", "ctrl+v+b", "ctrl+f25", "ctrl+f0", "ctrl+foo", "ctrl++v",
                      "v", "7", "space", "alt+ä", "ctrl+²",
                      # combos Windows never delivers as such
                      "ctrl+pause", "ctrl+alt+scrolllock", "shift+numpad5", "ctrl+shift+numpaddecimal"):
            with self.subTest(combo=combo), self.assertRaises(ValueError):
                hl.parse_hotkey(combo)


# ---------------------------------------------------------------- devices + config merge


class DeviceTest(unittest.TestCase):
    def setUp(self):
        self.sd = fake_sd()
        self.apis = hl.devices_by_hostapi(self.sd)

    def test_lists_per_hostapi(self):
        inputs, outputs = self.apis["Windows WASAPI"]
        self.assertIn(MAXWELL_IN, inputs)
        self.assertIn(CABLE_IN, outputs)
        self.assertNotIn(CABLE_IN, inputs)

    def test_resolves_exact_name_within_hostapi(self):
        inputs, outputs = self.apis["Windows WASAPI"]
        self.assertEqual(hl.match_device(inputs, ["audeze maxwell", "CHAT"], "input", "Windows WASAPI"), MAXWELL_IN)
        self.assertEqual(hl.match_device(outputs, ["CABLE Input"], "output", "Windows WASAPI"), CABLE_IN)
        mme_inputs = self.apis["MME"][0]
        self.assertEqual(hl.match_device(mme_inputs, ["Audeze Maxwell", "Chat"], "input", "MME"),
                         "Microphone (Chat-Audeze Maxwell")

    def test_no_match_lists_devices(self):
        inputs = self.apis["Windows WASAPI"][0]
        with self.assertRaises(hl.LaunchError) as cm:
            hl.match_device(inputs, ["Audeze Maxwell", "Boom"], "input", "Windows WASAPI")
        self.assertIn(MAXWELL_IN, str(cm.exception))
        self.assertIn("connected", str(cm.exception))

    def test_ambiguous_match_fails(self):
        outputs = self.apis["Windows WASAPI"][1]
        with self.assertRaises(hl.LaunchError) as cm:
            hl.match_device(outputs, ["Audeze Maxwell"], "output", "Windows WASAPI")
        self.assertIn("more specific", str(cm.exception))

    def test_empty_match_list_fails(self):
        for subs in ([], None, [""]):
            with self.subTest(subs=subs), self.assertRaises(hl.LaunchError):
                hl.match_device(["x"], subs, "input", "MME")


class BuildConfigTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.engine = make_repo(self.tmp)
        self.config_json = os.path.join(self.engine, "configs", "config.json")
        self.sd = fake_sd()

    def build(self, preset="vctk-p231"):
        return hl.build_config(self.engine, preset, self.sd, repo=self.tmp)

    def test_merge_order_paths_and_devices(self):
        write_json(self.config_json, {"pitch": 0, "threhold": -30, "sr_type": "sr_model",
                                      "sg_hostapi": "MME", "sg_input_device": "old", "keep_me": 7})
        cfg, preset = self.build()
        self.assertEqual(preset["voice"], "vctk-p231")
        self.assertEqual(cfg["pitch"], 10)                 # preset beats existing config
        self.assertEqual(cfg["formant"], 0.0)              # preset key the GUI never saves
        self.assertEqual(cfg["threhold"], -60)             # audio.json beats existing config
        self.assertEqual(cfg["sr_type"], "sr_device")
        self.assertEqual(cfg["keep_me"], 7)                # unrelated existing keys survive
        self.assertEqual(cfg["sg_hostapi"], "Windows WASAPI")
        self.assertEqual(cfg["sg_input_device"], MAXWELL_IN)
        self.assertEqual(cfg["sg_output_device"], CABLE_IN)
        for key in ("pth_path", "index_path"):
            self.assertTrue(os.path.isabs(cfg[key]) and os.path.isfile(cfg[key]), cfg[key])
        self.assertTrue(cfg["pth_path"].endswith(os.path.join("models", "vctk-p231", "Fp231rmvpe.pth")))

    def test_preset_overrides_audio_settings(self):
        preset_path = os.path.join(self.tmp, "config", "presets", "vctk-p238.json")
        preset = read_json(preset_path)
        preset["settings"]["block_time"] = 0.4
        write_json(preset_path, preset)
        cfg, _ = self.build("vctk-p238")
        self.assertEqual(cfg["block_time"], 0.4)
        self.assertIn("Fp238rmvpe.pth", cfg["pth_path"])

    def test_corrupt_existing_config_is_ignored(self):
        with open(self.config_json, "w") as f:
            f.write("{not json")
        cfg, _ = self.build()
        self.assertEqual(cfg["sg_input_device"], MAXWELL_IN)

    def test_written_config_is_accepted_by_upstream_load(self):
        cfg, _ = self.build()
        path = hl.write_engine_config(self.engine, cfg)
        self.assertEqual(path, self.config_json)
        data = read_json(path)
        self.assertEqual(data, cfg)
        self.assertTrue(upstream_load_accepts(data, self.sd))
        self.assertFalse(os.path.exists(path + ".tmp"))

    def test_missing_required_key_fails_loudly(self):
        # Fresh engine (no config.json) and an audio.json without sr_type: upstream load()
        # would hit KeyError and silently reset config.json, so the launcher must refuse.
        audio_path = os.path.join(self.tmp, "config", "audio.json")
        audio = read_json(audio_path)
        del audio["settings"]["sr_type"]
        write_json(audio_path, audio)
        with self.assertRaises(hl.LaunchError) as cm:
            self.build()
        self.assertIn("sr_type", str(cm.exception))
        # ...and the same config really would be rejected by upstream load().
        data = {"pth_path": "x", "index_path": "y", "sg_hostapi": "Windows WASAPI",
                "sg_input_device": MAXWELL_IN, "sg_output_device": CABLE_IN, "f0method": "rmvpe"}
        with self.assertRaises(KeyError):
            upstream_load_accepts(data, self.sd)

    def test_every_key_upstream_load_indexes_is_required(self):
        for key in ("sr_type", "f0method", "sg_hostapi", "sg_input_device", "sg_output_device",
                    "pth_path", "index_path"):
            self.assertIn(key, hl.REQUIRED_KEYS)

    def test_invalid_enum_values(self):
        for key, value in (("sr_type", "sr_foo"), ("f0method", "crepe")):
            preset_path = os.path.join(self.tmp, "config", "presets", "vctk-p249.json")
            preset = read_json(preset_path)
            preset["settings"][key] = value
            write_json(preset_path, preset)
            with self.subTest(key=key), self.assertRaises(hl.LaunchError):
                self.build("vctk-p249")
            del preset["settings"][key]
            write_json(preset_path, preset)

    def test_missing_model_file(self):
        os.remove(os.path.join(self.tmp, "models", "vctk-p231", "Fp231rmvpe.pth"))
        with self.assertRaises(hl.LaunchError) as cm:
            self.build()
        self.assertIn("get-models", str(cm.exception))

    def test_non_ascii_repo_path_rejected(self):
        repo = os.path.join(self.tmp, "Stimmen-\u00e9\u00e8")
        os.makedirs(repo)
        engine = make_repo(repo)
        with self.assertRaises(hl.LaunchError) as cm:
            hl.build_config(engine, "vctk-p231", self.sd, repo=repo)
        self.assertIn("ASCII", str(cm.exception))

    def test_unknown_or_unsafe_preset(self):
        for name in ("nope", "../audio", "", "a/b"):
            with self.subTest(name=name), self.assertRaises(hl.LaunchError):
                self.build(name)

    def test_missing_hostapi_or_device(self):
        with self.assertRaises(hl.LaunchError) as cm:
            hl.build_config(self.engine, "vctk-p231", fake_sd({"MME": DEVICES["MME"]}), repo=self.tmp)
        self.assertIn("Windows WASAPI", str(cm.exception))
        no_cable = {"Windows WASAPI": [d for d in DEVICES["Windows WASAPI"] if "CABLE" not in d[0]]}
        with self.assertRaises(hl.LaunchError) as cm:
            hl.build_config(self.engine, "vctk-p231", fake_sd(no_cable), repo=self.tmp)
        self.assertIn("VB-CABLE", str(cm.exception))

    def test_wasapi_shared_rate_mismatch_fails_loudly(self):
        devices = {"Windows WASAPI": [(MAXWELL_IN, 1, 0, 48000.0), (CABLE_IN, 0, 2, 44100.0)]}
        with self.assertRaises(hl.LaunchError) as cm:
            hl.build_config(self.engine, "vctk-p231", fake_sd(devices), repo=self.tmp)
        self.assertIn("44100", str(cm.exception))
        self.assertIn("48000", str(cm.exception))
        self.assertIn("windows-audio.md", str(cm.exception))

    def test_rate_check_skipped_in_exclusive_mode(self):
        audio_path = os.path.join(self.tmp, "config", "audio.json")
        audio = read_json(audio_path)
        audio["settings"]["sg_wasapi_exclusive"] = True
        write_json(audio_path, audio)
        devices = {"Windows WASAPI": [(MAXWELL_IN, 1, 0, 48000.0), (CABLE_IN, 0, 2, 44100.0)]}
        cfg, _ = hl.build_config(self.engine, "vctk-p231", fake_sd(devices), repo=self.tmp)
        self.assertEqual(cfg["sg_output_device"], CABLE_IN)


# ---------------------------------------------------------------- Window.read patch


TIMEOUT = "__TIMEOUT__"


def stub_sg():
    """A fresh FreeSimpleGUI stand-in. Window.read pops scripted events; when none are left, or
    for a scripted TIMEOUT, it behaves like a real read(timeout=...) that timed out."""

    class Radio:
        def __init__(self, window, key):
            self.window, self.key = window, key

        def get(self):
            return self.window.radio == self.key

        def update(self, value=None):
            self.window.updates.append((self.key, value))
            if value is True:
                self.window.radio = self.key

    class Text:
        def __init__(self):
            self.shown = []

        def update(self, value=None):
            self.shown.append(value)

    class Window:
        def __init__(self, title, events=()):
            self.Title = title
            self.events = list(events)
            self.radio = "vc"
            self.updates = []
            self.written = []
            self.timeouts = []
            self.texts = {}

        def read(self, timeout=None):
            self.timeouts.append(timeout)
            event = self.events.pop(0) if self.events else TIMEOUT
            if callable(event):
                event = event(self)
            if event is None:
                return None, None
            values = {"vc": self.radio == "vc", "im": self.radio == "im", "pitch": 10.0}
            if event == hl.TOGGLE_EVENT:
                values[event] = None
            return event, values

        def __getitem__(self, key):
            if key in ("vc", "im"):
                return Radio(self, key)
            return self.texts.setdefault(key, Text())

        def write_event_value(self, key, value):
            self.written.append((key, value))

    return types.SimpleNamespace(Window=Window, Text=Text, TIMEOUT_KEY=TIMEOUT)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.05  # every read(timeout=50) takes one poll interval
        return self.now


class ReadPatchTest(unittest.TestCase):
    def setUp(self):
        self.sg = stub_sg()
        self.toggle = hl.Toggle("C:\\cue\\on.wav", "C:\\cue\\off.wav")
        self.clock = FakeClock()
        hl.patch_window(self.sg, self.toggle, clock=self.clock, restart_delay=0.8)
        self.sound = mock.Mock(SND_FILENAME=0x20000, SND_ASYNC=0x1, SND_NODEFAULT=0x2)
        patcher = mock.patch.object(hl, "winsound", self.sound)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, window):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = window.read()
        return result, out.getvalue()

    def test_hotkey_flips_vc_im_and_plays_cue(self):
        window = self.sg.Window(hl.GUI_TITLE, ["pitch"])
        self.read(window)
        self.toggle.fire()
        (event, values), out = self.read(window)
        self.assertEqual(event, "im")
        self.assertEqual((values["vc"], values["im"]), (False, True))
        self.assertEqual(values["pitch"], 10.0)
        self.assertEqual(window.updates, [("im", True)])
        self.sound.PlaySound.assert_called_once_with("C:\\cue\\off.wav", 0x20000 | 0x1 | 0x2)
        self.assertIn("OFF", out)

        self.toggle.fire()
        (event, values), out = self.read(window)
        self.assertEqual(event, "vc")
        self.assertEqual((values["vc"], values["im"]), (True, False))
        self.assertEqual(window.updates[-1], ("vc", True))
        self.sound.PlaySound.assert_called_with("C:\\cue\\on.wav", 0x20000 | 0x1 | 0x2)
        self.assertIn("ON", out)

    def test_legacy_toggle_event_is_translated(self):
        window = self.sg.Window(hl.GUI_TITLE, [hl.TOGGLE_EVENT])
        (event, values), _ = self.read(window)
        self.assertEqual(event, "im")
        self.assertNotIn(hl.TOGGLE_EVENT, values)

    def test_hotkey_never_touches_the_window_from_its_thread(self):
        window = self.sg.Window(hl.GUI_TITLE, ["pitch"])
        self.read(window)
        worker = threading.Thread(target=self.toggle.fire)
        worker.start()
        worker.join()
        self.assertEqual((window.written, window.updates), ([], []))  # only the GUI thread acts on it
        (event, _), _ = self.read(window)
        self.assertEqual(event, "im")

    def test_timeouts_are_swallowed_other_events_pass_through(self):
        window = self.sg.Window(hl.GUI_TITLE, [TIMEOUT, "pitch", TIMEOUT, TIMEOUT, "start_vc"])
        for expected in ("pitch", "start_vc"):
            (event, values), _ = self.read(window)
            self.assertEqual(event, expected)
            self.assertEqual(values, {"vc": True, "im": False, "pitch": 10.0})
        self.assertEqual(window.updates, [])
        self.assertTrue(all(t == hl.POLL_MS for t in window.timeouts))
        self.sound.PlaySound.assert_not_called()

    def test_popups_and_explicit_timeouts_are_untouched(self):
        popup = self.sg.Window("", [hl.TOGGLE_EVENT])
        (event, values), _ = self.read(popup)
        self.assertEqual(event, hl.TOGGLE_EVENT)
        self.assertIn(hl.TOGGLE_EVENT, values)
        self.assertIsNone(self.toggle.window)
        window = self.sg.Window(hl.GUI_TITLE, [TIMEOUT])
        self.assertEqual(window.read(timeout=10)[0], TIMEOUT)  # a caller's own timeout is respected

    def test_window_captured_before_first_read_returns(self):
        seen = []
        window = self.sg.Window(hl.GUI_TITLE, [lambda w: seen.append(self.toggle.window) or "pitch"])
        self.read(window)
        self.assertEqual(seen, [window])

    def test_close_releases_window(self):
        window = self.sg.Window(hl.GUI_TITLE, ["pitch", None])
        self.read(window)
        self.assertIs(self.toggle.window, window)
        (event, values), _ = self.read(window)
        self.assertIsNone(event)
        self.assertIsNone(self.toggle.window)

    def test_fire_without_window_is_ignored(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.toggle.fire()
        self.assertIn("not open", out.getvalue())
        self.assertFalse(self.toggle.take())

    def test_text_updates_from_other_threads_are_applied_by_the_gui_thread(self):
        window = self.sg.Window(hl.GUI_TITLE, ["pitch", TIMEOUT, "stop_vc"])
        infer = window["infer_time"]
        infer.update(1)  # GUI thread: immediate
        self.assertEqual(infer.shown, [1])

        def audio_callback():
            for ms in (110, 120, 130):
                window["infer_time"].update(ms)

        worker = threading.Thread(target=audio_callback)
        worker.start()
        worker.join()
        self.assertEqual(infer.shown, [1])  # nothing touched Tk from the audio thread
        self.read(window)  # the GUI thread's read loop applies them; only the latest matters
        self.assertEqual(infer.shown, [1, 130])

    def test_auto_restart_after_timing_slider_settles(self):
        window = self.sg.Window(hl.GUI_TITLE, ["start_vc", "crossfade_length", "crossfade_length"])
        for expected in ("start_vc", "crossfade_length", "crossfade_length"):
            self.assertEqual(self.read(window)[0][0], expected)  # passed through: the stock GUI stops
        before = self.clock.now
        (event, values), out = self.read(window)  # nothing else happens: times out until due
        self.assertEqual(event, "start_vc")
        self.assertIn("pitch", values)
        self.assertGreaterEqual(self.clock.now - before, 0.8)
        self.assertIn("restarting conversion", out)
        window.events = ["pitch", "stop_vc"]  # and it doesn't repeat
        self.assertEqual([self.read(window)[0][0] for _ in range(2)], ["pitch", "stop_vc"])

    def test_no_auto_restart_unless_running_or_after_stop(self):
        for script in (["crossfade_length", "pitch"],                       # never started
                       ["start_vc", "block_time", "stop_vc", "pitch"],      # stopped meanwhile
                       ["start_vc", "block_time", "sg_input_device", "pitch"],  # device change: user decides
                       ["start_vc", "stop_vc", "extra_time", "pitch"]):     # slider after a stop
            window = self.sg.Window(hl.GUI_TITLE, list(script) + [TIMEOUT] * 40 + ["done"])
            seen = [self.read(window)[0][0] for _ in range(len(script) + 1)]
            with self.subTest(script=script):
                self.assertEqual(seen, script + ["done"])

    def test_empty_cue_is_silent(self):
        hl.play_cue("")
        self.sound.PlaySound.assert_not_called()


class AutoRestartTest(unittest.TestCase):
    def test_debounce_restarts_once(self):
        r = hl.AutoRestart(delay=1.0)
        r.observe("start_vc", 0.0)
        r.observe("block_time", 1.0)
        r.observe("block_time", 1.5)  # still dragging: pushes the restart out
        self.assertFalse(r.ready(2.4))
        self.assertTrue(r.ready(2.5))
        self.assertFalse(r.ready(10.0))
        r.observe("pitch", 11.0)  # live events don't change anything
        self.assertTrue(r.running)


class ConsoleWriterTest(unittest.TestCase):
    def test_writes_never_block_and_keep_order(self):
        release = threading.Event()

        class SlowConsole(io.StringIO):
            def write(self, text):
                release.wait(5)  # like a console frozen by QuickEdit selection
                return super().write(text)

        out, err = SlowConsole(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "run.log")
            writer = hl.ConsoleWriter(out, err, log)
            started = time.perf_counter()
            for i in range(200):
                writer.stdout.write(f"line {i}\n")
            writer.stderr.write("oops\n")
            self.assertLess(time.perf_counter() - started, 0.5)  # the caller never waited
            release.set()
            writer.close()
            with open(log, encoding="utf-8") as f:
                logged = f.read()
        self.assertEqual(out.getvalue(), "".join(f"line {i}\n" for i in range(200)))
        self.assertEqual(err.getvalue(), "oops\n")
        self.assertIn("line 199\n", logged)
        self.assertIn("oops\n", logged)
        self.assertEqual(writer.stdout.encoding if hasattr(out, "encoding") else None, out.encoding)


class QuickEditTest(unittest.TestCase):
    class FakeKernel32:
        def __init__(self, mode, is_console=True):
            self.mode, self.is_console, self.set_calls = mode, is_console, []

        def GetStdHandle(self, which):
            return 7

        def GetConsoleMode(self, handle, mode_ref):
            if not self.is_console:
                return 0
            mode_ref._obj.value = self.mode
            return 1

        def SetConsoleMode(self, handle, mode):
            self.set_calls.append(mode)
            return 1

    def test_clears_quick_edit_and_restores_at_exit(self):
        k = self.FakeKernel32(0x01F7)  # typical console input mode with QuickEdit (0x40) on
        with mock.patch.object(hl.atexit, "register") as register:
            self.assertEqual(hl.disable_quick_edit(k), 0x01F7)
        self.assertEqual(k.set_calls, [(0x01F7 | 0x80) & ~0x40])
        register.assert_called_once_with(k.SetConsoleMode, 7, 0x01F7)

    def test_no_console_or_already_off(self):
        for k in (self.FakeKernel32(0x01F7, is_console=False), self.FakeKernel32(0x01B7)):
            with mock.patch.object(hl.atexit, "register") as register:
                self.assertIsNone(hl.disable_quick_edit(k))
            self.assertEqual(k.set_calls, [])
            register.assert_not_called()


# ---------------------------------------------------------------- hotkey listeners


def post_thread_message(thread_id, msg, wparam):
    return hl.user32().PostThreadMessageW(thread_id, msg, wparam, 0)


class RegisteredHotkeyTest(unittest.TestCase):
    def start(self, combo=TEST_COMBO, callback=None):
        mods, vk = hl.parse_hotkey(combo)
        hl.user32()
        listener = hl.RegisteredHotkey(mods, vk, callback or (lambda: None))
        listener.start()
        self.assertTrue(listener.ready.wait(5))
        self.addCleanup(listener.join, 5)
        self.addCleanup(listener.stop)
        return listener

    def test_wm_hotkey_calls_back_and_other_ids_do_not(self):
        fired = threading.Event()
        calls = []
        listener = self.start(callback=lambda: (calls.append(1), fired.set()))
        if listener.error:
            self.skipTest(f"{TEST_COMBO} is taken on this machine: {listener.error}")
        self.assertTrue(post_thread_message(listener.thread_id, hl.WM_HOTKEY, hl.HOTKEY_ID + 1))
        self.assertTrue(post_thread_message(listener.thread_id, hl.WM_HOTKEY, hl.HOTKEY_ID))
        self.assertTrue(fired.wait(5))
        listener.stop()
        listener.join(5)
        self.assertFalse(listener.is_alive())
        self.assertEqual(calls, [1])

    def test_callback_errors_do_not_kill_the_listener(self):
        fired = threading.Event()
        state = {"n": 0}

        def callback():
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("window closed")
            fired.set()

        listener = self.start(callback=callback)
        if listener.error:
            self.skipTest(listener.error)
        with contextlib.redirect_stdout(io.StringIO()):
            post_thread_message(listener.thread_id, hl.WM_HOTKEY, hl.HOTKEY_ID)
            post_thread_message(listener.thread_id, hl.WM_HOTKEY, hl.HOTKEY_ID)
            self.assertTrue(fired.wait(5))

    def test_taken_hotkey_falls_back_to_poll(self):
        first = self.start()
        if first.error:
            self.skipTest(first.error)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            listener = hl.start_hotkey({"toggle": TEST_COMBO, "method": "registerhotkey",
                                        "poll_interval_ms": 20}, lambda: None)
        self.addCleanup(listener.stop)
        self.assertIsInstance(listener, hl.PolledHotkey)
        self.assertIn("RegisterHotKey(" + TEST_COMBO + ") failed", out.getvalue())
        self.assertIn("polling", out.getvalue())


class PolledHotkeyTest(unittest.TestCase):
    def setUp(self):
        self.down = set()
        self.calls = []
        mods, vk = hl.parse_hotkey("ctrl+alt+v")
        self.listener = hl.PolledHotkey(mods, vk, lambda: self.calls.append(1), 30,
                                        key_down=lambda v: v in self.down)

    def poll(self, *keys):
        self.down = set(keys)
        self.listener.poll_once()
        return len(self.calls)

    def test_edge_triggered(self):
        CTRL, ALT, V = 0x11, 0x12, 0x56
        self.assertEqual(self.poll(CTRL, ALT), 0)
        self.assertEqual(self.poll(CTRL, ALT, V), 1)   # press
        self.assertEqual(self.poll(CTRL, ALT, V), 1)   # held: no repeat
        self.assertEqual(self.poll(CTRL, V), 1)        # alt released
        self.assertEqual(self.poll(CTRL, ALT, V), 2)   # pressed again
        self.assertEqual(self.poll(), 2)

    def test_exact_modifiers_like_registerhotkey(self):
        self.assertEqual(self.poll(0x11, 0x12, 0x10, 0x56), 0)  # extra shift: no fire
        self.assertTrue(hl.combo_down(hl.MOD_WIN, 0x70, lambda v: v in (0x5C, 0x70)))  # right win

    def test_start_hotkey_poll_method(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            listener = hl.start_hotkey({"toggle": TEST_COMBO, "method": "poll", "poll_interval_ms": 20},
                                       lambda: None)
        listener.stop()
        listener.join(2)
        self.assertIsInstance(listener, hl.PolledHotkey)
        self.assertIn("polling every 20 ms", out.getvalue())

    def test_bad_hotkey_config(self):
        for cfg in ({"toggle": "ctrl+nope"}, {"toggle": "ctrl+alt+v", "method": "hook"}):
            with self.subTest(cfg=cfg), self.assertRaises(hl.LaunchError):
                hl.start_hotkey(cfg, lambda: None)


# ---------------------------------------------------------------- runpy launch


STUB_REALTIME_GUI_ARGS = '''
import argparse, json, os, sys
if __name__ == "__main__":
    # configs/config.py does this with sys.argv; unknown flags such as --preset exit(2).
    parser = argparse.ArgumentParser()
    for flag in ("--port", "--pycmd"):
        parser.add_argument(flag)
    for flag in ("--colab", "--noparallel", "--noautoopen", "--dml"):
        parser.add_argument(flag, action="store_true")
    parser.parse_args()
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ran.json"), "w") as f:
        json.dump({"argv": sys.argv, "cwd": os.getcwd(), "path0": sys.path[0],
                   "file": __file__, "name": __name__}, f)
'''


class RunGuiTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.engine = os.path.join(self.tmp, "engine")
        os.makedirs(self.engine)
        self.gui = os.path.join(self.engine, "realtime_gui.py")
        with open(self.gui, "w") as f:
            f.write(STUB_REALTIME_GUI_ARGS)
        cwd, argv, path = os.getcwd(), sys.argv[:], sys.path[:]

        def restore():
            os.chdir(cwd)
            sys.argv = argv
            sys.path[:] = path

        self.addCleanup(restore)

    def test_argv_reset_chdir_and_sys_path(self):
        sys.argv = ["hotkey_launcher.py", "--engine", self.engine, "--preset", "vctk-p231"]
        hl.run_gui(self.engine)
        ran = read_json(os.path.join(self.engine, "ran.json"))
        self.assertEqual(ran["argv"], [self.gui])
        self.assertEqual(os.path.normcase(ran["cwd"]), os.path.normcase(self.engine))
        self.assertEqual(ran["path0"], self.engine)
        self.assertEqual(ran["name"], "__main__")

    def test_control_without_argv_reset_the_stub_crashes(self):
        sys.argv = [self.gui, "--preset", "vctk-p231"]
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            runpy.run_path(self.gui, run_name="__main__")


# ---------------------------------------------------------------- end to end (subprocess)


STUB_FREESIMPLEGUI = '''
import queue
WIN_CLOSED = None
log = []

class Radio:
    def __init__(self, window, key):
        self.window, self.key = window, key
    def get(self):
        return self.window.radio == self.key
    def update(self, value=None):
        log.append(["update", self.key, value])
        if value is True:
            self.window.radio = self.key

TIMEOUT_KEY = "__TIMEOUT__"

class Text:
    def update(self, value=None):
        log.append(["text", value])

class StrVar:
    def set(self, value):
        log.append(["strvar", value])

class Window:
    def __init__(self, title, layout=None, finalize=False):
        self.Title = title
        self.radio = "vc"
        self.thread_queue = queue.Queue()
        self.thread_strvar = StrVar()
    def read(self, timeout=None):
        try:
            event, value = self.thread_queue.get(timeout=timeout / 1000 if timeout else 20)
        except queue.Empty:
            event, value = TIMEOUT_KEY, None
        if event is None:
            return None, None
        values = {"vc": self.radio == "vc", "im": self.radio == "im", "pitch": 10}
        if event == "__HOTKEY_TOGGLE__":
            values[event] = value
        return event, values
    def write_event_value(self, key, value):
        self.thread_queue.put((key, value))
    def __getitem__(self, key):
        return Radio(self, key)

def popup(*args, **kwargs):
    window = Window(kwargs.get("title", ""))
    window.write_event_value("__HOTKEY_TOGGLE__", None)
    return window.read()[0]
'''

STUB_CONFIG_PY = '''
import argparse

class Config:
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=7865)
        parser.add_argument("--pycmd", type=str, default="python")
        self.args = parser.parse_args()
'''

# Mirrors the parts of realtime_gui.py (2.3.260718) the add-on depends on: everything under
# __main__, FreeSimpleGUI window "RVC - GUI", load() device checks, the stock event_handler
# branches for vc/im and "any other event stops the stream".
STUB_REALTIME_GUI = '''
import ctypes, json, os, sys, threading, time
now_dir = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    import FreeSimpleGUI as sg
    import sounddevice as sd
    from configs.config import Config

    Config()
    with open(os.path.join(now_dir, "configs", "config.json"), encoding="utf8") as f:
        data = json.load(f)
    apis = {a["name"]: a["devices"] for a in sd.query_hostapis()}
    names = [d["name"] for d in sd.query_devices()]
    report = {"argv": sys.argv, "cwd": os.getcwd(), "config": data, "events": [], "stopped": 0,
              "devices_ok": data["sg_input_device"] in [names[i] for i in apis[data["sg_hostapi"]]]}
    function = "vc"
    window = sg.Window("RVC - GUI", layout=[], finalize=True)
    report["popup_event"] = sg.popup("pth missing")

    def press_hotkey():
        time.sleep(0.5)  # let the main loop enter window.read(), like a user pressing later
        listener = [t for t in threading.enumerate() if t.name == "hotkey-register"]
        if not listener:
            window.write_event_value("no-listener", None)
            window.write_event_value(None, None)
            return
        post = ctypes.WinDLL("user32").PostThreadMessageW
        post.argtypes = (ctypes.c_ulong, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        for _ in range(3):
            post(listener[0].thread_id, 0x0312, 1, 0)   # WM_HOTKEY, HOTKEY_ID
            time.sleep(0.2)
        window.write_event_value("start_vc", None)      # the user clicks Start...
        for _ in range(3):                              # ...then drags "Fade length"
            window.write_event_value("crossfade_length", None)
            time.sleep(0.1)
        time.sleep(2.0)                                 # the add-on restarts conversion once
        window.write_event_value(None, None)            # close the window

    threading.Thread(target=press_hotkey, daemon=True).start()
    while True:
        event, values = window.read()
        if event is None:
            break
        report["events"].append([event, values["vc"], values["im"], "__HOTKEY_TOGGLE__" in values])
        if event in ["vc", "im"]:
            function = event
        elif event == "start_vc":
            report["started"] = report.get("started", 0) + 1
        elif event == "stop_vc" or event != "start_vc":
            report["stopped"] += 1
    report["function"] = function
    report["radio_log"] = sg.log
    with open(os.path.join(now_dir, "report.json"), "w") as f:
        json.dump(report, f)
'''


class EndToEndTest(TempDirTest):
    """Runs the launcher as a real process against a stub engine and stub modules."""

    def setUp(self):
        super().setUp()
        self.engine = make_repo(self.tmp, hotkey={"toggle": TEST_COMBO, "method": "registerhotkey",
                                                  "poll_interval_ms": 30, "cue_vc": "", "cue_im": ""})
        os.makedirs(os.path.join(self.tmp, "vcgui"))
        shutil.copy(os.path.join(REPO, "vcgui", "hotkey_launcher.py"), os.path.join(self.tmp, "vcgui"))
        stubs = os.path.join(self.tmp, "stubs")
        os.makedirs(os.path.join(stubs, "FreeSimpleGUI"))
        files = {
            os.path.join(stubs, "FreeSimpleGUI", "__init__.py"): STUB_FREESIMPLEGUI,
            os.path.join(stubs, "sounddevice.py"): FAKE_SOUNDDEVICE.format(devices=DEVICES),
            os.path.join(self.engine, "configs", "__init__.py"): "",
            os.path.join(self.engine, "configs", "config.py"): STUB_CONFIG_PY,
            os.path.join(self.engine, "realtime_gui.py"): STUB_REALTIME_GUI,
        }
        for path, text in files.items():
            with open(path, "w", encoding="utf-8") as f:
                f.write(textwrap.dedent(text))
        self.env = dict(os.environ, PYTHONPATH=stubs, PYTHONIOENCODING="utf-8")

    def launch(self, *args):
        cmd = [sys.executable, os.path.join(self.tmp, "vcgui", "hotkey_launcher.py"), *args]
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True, encoding="utf-8",
                              timeout=60, cwd=self.tmp)

    def test_launch_hotkey_toggles_without_stopping_stream(self):
        proc = self.launch("--engine", self.engine, "--preset", "vctk-p238")
        report_path = os.path.join(self.engine, "report.json")
        report = read_json(report_path) if os.path.exists(report_path) else {"events": []}
        if report["events"] == [["no-listener", True, False, False]]:
            self.assertIn("Falling back", proc.stdout)
            self.skipTest(f"{TEST_COMBO} is taken on this machine; RegisterHotKey path not exercised")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual([os.path.normcase(a) for a in report["argv"]],
                         [os.path.normcase(os.path.join(self.engine, "realtime_gui.py"))])
        self.assertEqual(os.path.normcase(report["cwd"]), os.path.normcase(self.engine))
        self.assertTrue(report["devices_ok"])
        self.assertEqual(report["config"]["sg_input_device"], MAXWELL_IN)
        self.assertIn("Fp238rmvpe.pth", report["config"]["pth_path"])
        self.assertEqual(report["popup_event"], "__HOTKEY_TOGGLE__")   # popups untouched
        self.assertEqual(report["events"][:3], [["im", False, True, False],
                                                ["vc", True, False, False],
                                                ["im", False, True, False]])
        # Start, a 3-event slider drag (the stock GUI stops the stream on each), one auto restart.
        self.assertEqual([e[0] for e in report["events"][3:]],
                         ["start_vc", "crossfade_length", "crossfade_length", "crossfade_length", "start_vc"])
        self.assertEqual(report["started"], 2)
        self.assertEqual(report["stopped"], 3)  # only the slider events; the hotkey never stops it
        self.assertEqual(report["function"], "im")
        self.assertEqual([e for e in report["radio_log"] if e[0] == "update"],
                         [["update", "im", True], ["update", "vc", True], ["update", "im", True]])
        self.assertFalse([e for e in report["radio_log"] if e[0] == "strvar"])  # no Tk calls off-thread
        self.assertIn("restarting conversion", proc.stdout)
        self.assertIn("RegisterHotKey", proc.stdout)
        self.assertIn("voice changer OFF", proc.stdout)

    def test_list_devices(self):
        proc = self.launch("--list-devices")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("== Windows WASAPI", proc.stdout)
        self.assertIn(CABLE_IN, proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.engine, "configs", "config.json")))

    def test_list_devices_redirected_non_cp1252_name(self):
        # Under -I the child ignores PYTHONIOENCODING, so a pipe gets cp1252; emulate that here.
        extra = [("Headset (\u2605 Maxwell)", 1, 0)]
        devices = dict(DEVICES, **{"Windows WASAPI": DEVICES["Windows WASAPI"] + extra})
        with open(os.path.join(self.tmp, "stubs", "sounddevice.py"), "w", encoding="utf-8") as f:
            f.write(FAKE_SOUNDDEVICE.format(devices=devices))
        env = {k: v for k, v in self.env.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        cmd = [sys.executable, os.path.join(self.tmp, "vcgui", "hotkey_launcher.py"), "--list-devices"]
        proc = subprocess.run(cmd, env=env, capture_output=True, timeout=60, cwd=self.tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("cp1252", "replace"))
        self.assertIn(b"Headset (\\u2605 Maxwell)", proc.stdout)

    def test_list_presets(self):
        proc = self.launch("--list-presets")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ("vctk-p231", "vctk-p238", "vctk-p249"):
            self.assertIn(name, proc.stdout)

    def test_missing_voice_is_a_friendly_error(self):
        os.remove(os.path.join(self.tmp, "models", "vctk-p249", "Fp249rmvpe.pth"))
        proc = self.launch("--engine", self.engine, "--preset", "vctk-p249")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ERROR:", proc.stderr)
        self.assertIn("get-models", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.engine, "report.json")))

    def test_missing_engine(self):
        proc = self.launch("--engine", os.path.join(self.tmp, "no-engine"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("install-engine", proc.stderr)


if __name__ == "__main__":
    if sys.platform != "win32":
        sys.exit("These tests need Windows (ctypes user32, winsound).")
    unittest.main(verbosity=2)
