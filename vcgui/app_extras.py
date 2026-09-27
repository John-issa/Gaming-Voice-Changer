"""In-app extras for the stock RVC window: a Voice list, "Save settings" and "Mute cable".

Used by hotkey_launcher.py; like it, nothing under engine/ is modified. A row is added to the bottom
of the "RVC - GUI" window (FreeSimpleGUI Window.__init__ is wrapped for that title only), and the
launcher's patched read() hands the row's events to Extras.handle(); they never reach the stock
event handler, which would stop the stream on any event it doesn't know.

- Voice: switching validates the preset, sets the stock widgets (model, index, sliders, f0 radio)
  and, if conversion is running, restarts it through the stock stop/start.
- Save settings: the current widget values go back into the active preset (pitch, formant,
  index_rate, rms_mix_rate, f0method) and config/audio.json (threhold and the timing sliders,
  unless the preset overrides them). Written atomically, in the files' own layout.
- Mute: sounddevice.Stream is subclassed so the engine's callback runs as usual and its output is
  then zeroed: true silence on the cable in both vc and im mode, while the engine keeps running.

This module doesn't import hotkey_launcher (which runs as __main__); it gets load_json/model_path
and the cue player passed in.
"""

import json
import os
import re
import sys
import threading

try:
    import winsound
except ImportError:  # only the error beep needs it
    winsound = None

GUI_TITLE = "RVC - GUI"
PRESET_KEY, SAVE_KEY, MUTE_KEY, STATUS_KEY = "vcgui_preset", "vcgui_save", "vcgui_mute", "vcgui_status"
EVENTS = frozenset((PRESET_KEY, SAVE_KEY, MUTE_KEY))
F0_KEYS = ("pm", "rmvpe", "fcpe")
VOICE_KEYS = ("pitch", "formant", "index_rate", "rms_mix_rate")  # + f0method: saved to the preset
TIMING_KEYS = ("threhold", "block_time", "crossfade_length", "extra_time")  # saved to audio.json
INT_KEYS = ("pitch", "threhold")  # integer sliders (FreeSimpleGUI returns every slider as a float)


# ---------------------------------------------------------------- JSON files


def dump_json(obj, pad=""):
    """json.dumps(indent=2) but with lists kept on one line: the layout of the config/*.json files."""
    if isinstance(obj, dict) and obj:
        inner = pad + "  "
        items = ",\n".join(f"{inner}{json.dumps(k, ensure_ascii=False)}: {dump_json(v, inner)}"
                           for k, v in obj.items())
        return "{\n" + items + "\n" + pad + "}"
    return json.dumps(obj, ensure_ascii=False)


def write_json(path, data):
    """Replace path atomically; a failed write leaves the old file intact."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump_json(data) + "\n")
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def list_presets(repo, load_json):
    """[(id, label)] for config/presets/*.json, sorted; unreadable files are listed as such."""
    folder = os.path.join(repo, "config", "presets")
    presets = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            try:
                label = str(load_json(os.path.join(folder, name), name).get("label", ""))
            except Exception:
                label = "(unreadable)"
            presets.append((name[:-5], label))
    return presets


# ---------------------------------------------------------------- mute


class Mute:
    """The mute flag, shared by the GUI thread, the mute hotkey thread and the audio callback."""

    def __init__(self, cue_mute="", cue_unmute="", play=None):
        self.on = False  # a bool: reads and writes are atomic, the audio thread reads it lock-free
        self.sticky = False  # muted at some point since the audio callback last looked
        self.cues = {True: cue_mute, False: cue_unmute}
        self.play = play or (lambda path: None)
        self._lock = threading.Lock()

    def set(self, on):
        with self._lock:
            self.on = bool(on)
            if self.on:
                self.sticky = True
            self.play(self.cues[self.on])
        print("[mute] cable muted: silence on the output" if self.on else "[mute] cable unmuted")

    def toggle(self):  # the mute hotkey; any thread, no Tk
        self.set(not self.on)


FADE_FRAMES = 480  # ~10 ms: the first muted block fades out instead of cutting (a cut clicks)


def silence(buffer):
    """A zeroed copy of an audio buffer (the one PortAudio hands in may be read-only)."""
    quiet = buffer.copy()
    quiet.fill(0)
    return quiet


def fade_out(outdata):
    try:
        import numpy as np
        n = min(len(outdata), FADE_FRAMES)
        outdata[:n] *= np.linspace(1.0, 0.0, n, dtype=outdata.dtype).reshape((n,) + (1,) * (outdata.ndim - 1))
        outdata[n:] = 0
    except Exception:
        outdata.fill(0)


def wrap_stream(sd, mute):
    """Make every sd.Stream silent while muted, and the engine deaf to what was said meanwhile.

    The engine's callback still runs (its state keeps advancing, so unmuting is clean), but for
    every block captured while muted - including the block in which unmute lands - it gets silence
    as input, and its output is zeroed. Otherwise the ~0.2-0.75 s the engine holds in its buffers
    would put speech from the muted period on the cable right after unmute. Idempotent. Returns
    False if sd has no Stream."""
    base = getattr(sd, "Stream", None)
    if base is None:
        return False
    if getattr(base, "_vcgui_mute", None) is not None:
        return True

    class MutableStream(base):
        _vcgui_mute = mute

        def __init__(self, *args, callback=None, **kwargs):
            if callback is not None:
                inner = callback
                was_muted = [False]

                def callback(indata, outdata, frames, time, status):
                    deaf = mute.on or mute.sticky
                    mute.sticky = mute.on
                    inner(silence(indata) if deaf and indata is not None else indata, outdata, frames, time, status)
                    if mute.on:
                        if was_muted[0]:
                            outdata.fill(0)
                        else:
                            fade_out(outdata)
                    was_muted[0] = mute.on

            super().__init__(*args, callback=callback, **kwargs)

    sd.Stream = MutableStream
    return True


# ---------------------------------------------------------------- the window row


def engine_running(restart):
    """The engine's own flag_vc (realtime_gui runs as __main__ via runpy), else our best guess."""
    flag = getattr(sys.modules.get("__main__"), "flag_vc", None)
    return restart.running if flag is None else bool(flag)


def beep():
    if winsound is not None:
        try:
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass


class Extras:
    """The Voice / Save settings / Mute cable row and its event handling (GUI thread only)."""

    def __init__(self, repo, active, mute, load_json, model_path, f0_methods=F0_KEYS,
                 is_running=engine_running, alert=beep):
        self.repo, self.active, self.mute = repo, active, mute
        self.load_json, self.model_path, self.f0_methods = load_json, model_path, f0_methods
        self.is_running, self.alert = is_running, alert
        self.presets = list_presets(repo, load_json)
        self.labels = dict(self.presets)
        self.displays = [self.display(pid) for pid, _ in self.presets]
        self.ids = {self.display(pid): pid for pid, _ in self.presets}
        self.loading = None     # preset id whose model the stock start is (re)loading
        self.shown_mute = None  # what the checkbox shows, to catch hotkey changes

    def display(self, pid):
        label = self.labels.get(pid, "")
        return f"{pid} - {label}" if label else pid

    # -------- layout

    def row(self, sg):
        return [sg.Text("Voice"),
                sg.Combo(self.displays, default_value=self.display(self.active), key=PRESET_KEY,
                         readonly=True, enable_events=True, size=(44, 1)),
                sg.Button("Save settings", key=SAVE_KEY),
                sg.Checkbox("Mute cable", key=MUTE_KEY, default=self.mute.on, enable_events=True),
                sg.Text("", key=STATUS_KEY, size=(28, 1))]

    def attach(self, window):
        """After the window is built: don't let the mouse wheel over the Voice list switch voices."""
        combo = getattr(el(window, PRESET_KEY), "TKCombo", None)
        if combo is not None:
            try:
                combo.bind("<MouseWheel>", lambda e: "break")
            except Exception:
                pass

    # -------- events

    def handle(self, window, event, values, restart, now):
        """A row event. Returns an (event, values) for the stock handler, or None to keep polling."""
        values = dict(values or {})
        if event == MUTE_KEY:
            self.mute.set(values.get(MUTE_KEY))
            box = el(window, MUTE_KEY)
            if box is not None:
                box.update(value=self.mute.on)  # no event; keeps the box and the flag in step
            self.shown_mute = self.mute.on
            self.status(window, "Muted" if self.mute.on else "Unmuted")
            return None
        if event == SAVE_KEY:
            self.save(window, values)
            return None
        if event == PRESET_KEY:
            return self.switch(window, values, restart, now)
        return None

    def idle(self, window, values, restart):
        """Every poll timeout: follow mute hotkey presses and finished voice loads."""
        if self.mute.on != self.shown_mute:
            box = el(window, MUTE_KEY)
            if box is not None:
                box.update(value=self.mute.on)
            if self.shown_mute is not None:
                self.status(window, "Muted" if self.mute.on else "Unmuted")
            self.shown_mute = self.mute.on
        if self.loading and self.is_running(restart):
            self.status(window, f"{self.loading} ready")
            self.loading = None

    def on_flip(self):
        """After the vc/im hotkey: if the cable is muted, say so (the game has focus: sound only)."""
        if self.mute.on:
            self.mute.play(self.mute.cues[True])
            print("[mute] still muted: the cable stays silent")

    # -------- voice switch

    def load_target(self, pid):
        """The GUI values for preset pid (audio.json <- preset, as at launch), validated."""
        if not re.fullmatch(r"[A-Za-z0-9._-]+", pid or ""):
            raise ValueError(f"invalid preset name {pid!r}")
        audio = self.load_json(os.path.join(self.repo, "config", "audio.json"), "config/audio.json")
        preset = self.load_json(os.path.join(self.repo, "config", "presets", pid + ".json"), f"Preset {pid!r}")
        merged = dict(audio.get("settings") or {})
        merged.update(preset.get("settings") or {})
        target = {key: self.model_path(merged.get(key), key, self.repo) for key in ("pth_path", "index_path")}
        if merged.get("f0method") not in self.f0_methods:
            raise ValueError(f"f0method must be one of {tuple(self.f0_methods)}, got {merged.get('f0method')!r}")
        target["f0method"] = merged["f0method"]
        for key in VOICE_KEYS + TIMING_KEYS:
            if key in merged:
                value = merged[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"{key} must be a number, got {value!r}")
                target[key] = value
        return target

    def switch(self, window, values, restart, now):
        pid = self.ids.get(values.get(PRESET_KEY))
        if pid is None or pid == self.active:
            return None
        try:
            target = self.load_target(pid)
        except Exception as e:  # LaunchError from load_json/model_path, ValueError from here
            print(f"[voice] can't switch to {pid}: {e}")
            self.revert(window)
            self.status(window, f"Can't load {pid}")
            self.alert()
            return None
        for key, value in target.items():
            if key == "f0method":
                for m in F0_KEYS:
                    values[m] = m == value
                radio = el(window, value)
                if radio is not None:
                    radio.update(value=True)  # the radio group clears the others; no event
                continue
            values[key] = value
            element = el(window, key)
            if element is not None:
                element.update(value=value)  # sets the tk variable; no event
        self.active = pid
        print(f"[voice] {pid} - {self.labels.get(pid, '')}")
        if self.is_running(restart):
            self.loading = pid
            self.status(window, f"Loading {pid}...")
            restart.schedule(now)  # the next poll sends start_vc with these values
            return "stop_vc", values
        if restart.due is not None:  # already stopped, restart pending (slider, earlier pick)
            self.loading = pid       # the pending start_vc will read these widgets
            self.status(window, f"Loading {pid}...")
            return None
        self.loading = None
        self.status(window, f"{pid}: press Start")
        return None

    def revert(self, window):
        combo = el(window, PRESET_KEY)
        if combo is not None:
            combo.update(value=self.display(self.active))

    # -------- save

    def gui_settings(self, values):
        """The saveable widget values, rounded to what the sliders can show."""
        out = {}
        for key in VOICE_KEYS + TIMING_KEYS:
            value = values.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            out[key] = int(round(value)) if key in INT_KEYS else round(float(value), 2)
        methods = [m for m in F0_KEYS if values.get(m) is True]
        if len(methods) == 1:
            out["f0method"] = methods[0]
        return out

    def save(self, window, values):
        settings = self.gui_settings(values)
        preset_path = os.path.join(self.repo, "config", "presets", self.active + ".json")
        audio_path = os.path.join(self.repo, "config", "audio.json")
        try:
            preset = self.load_json(preset_path, f"Preset {self.active!r}")
            audio = self.load_json(audio_path, "config/audio.json")
            new_preset = json.loads(json.dumps(preset))
            new_audio = json.loads(json.dumps(audio))
            ps = new_preset.setdefault("settings", {})
            aus = new_audio.setdefault("settings", {})
            if not isinstance(ps, dict) or not isinstance(aus, dict):
                raise ValueError("'settings' must be a JSON object")
            for key, value in settings.items():
                target = aus if key in TIMING_KEYS and key not in ps else ps
                target[key] = value
        except Exception as e:
            print(f"[save] failed, nothing written: {e}")
            self.status(window, "Save failed")
            self.alert()
            return False
        written = []
        try:
            if new_preset != preset:
                write_json(preset_path, new_preset)
                written.append(f"{self.active}.json")
            if new_audio != audio:
                write_json(audio_path, new_audio)
                written.append("audio.json")
        except Exception as e:
            print(f"[save] failed{' after writing ' + ', '.join(written) if written else ', nothing written'}: {e}")
            self.status(window, "Save failed")
            self.alert()
            return False
        print(f"[save] {', '.join(written) if written else 'nothing changed'}: "
              + ", ".join(f"{k} {v}" for k, v in settings.items()))
        self.status(window, "Saved" if written else "No changes")
        return True

    # -------- helpers

    def status(self, window, text):
        label = el(window, STATUS_KEY)
        if label is not None:
            try:
                label.update(text)
            except Exception:
                pass


def el(window, key):
    """window[key] without FreeSimpleGUI's key-guessing: a missing key would open a modal popup."""
    return (getattr(window, "AllKeysDict", None) or {}).get(key)


def patch_layout(sg, extras):
    """Add the extras row to the bottom of the RVC window; other windows (popups) are untouched."""
    original = sg.Window.__init__

    def __init__(self, title=None, *args, **kwargs):
        ours = title == GUI_TITLE and isinstance(kwargs.get("layout"), list)
        if ours:
            try:
                kwargs["layout"] = kwargs["layout"] + [extras.row(sg)]
            except Exception as e:
                ours = False
                print(f"[extras] could not add the Voice/Save/Mute row: {e!r}")
        original(self, title, *args, **kwargs)
        if ours:
            extras.attach(self)

    sg.Window.__init__ = __init__
    return original
