# Task board

The orchestrator is the session "Real-time voice changer for gaming", and Worker-1 does the implementation. The approved plan is [docs/PLAN.md](docs/PLAN.md), and it is the source of truth. Ask the orchestrator before you deviate from it.

## Ground rules (Worker-1)
- **Worker-1 does not commit or push.** The orchestrator reviews each task and commits it on `feature/voice-changer-v1`, then pushes.
- **Downloads are limited to the two pinned manifests** (`config/engine.lock.json`, `config/models.json`), which are approved. Anything else needs the orchestrator's OK first.
- **Never** install drivers, change Windows audio or security settings, disable antivirus, or run anything as admin. VB-CABLE install and Windows sound settings are **user steps**: document them, don't perform them.
- Keep the code small and stdlib-only. We assemble existing tools; we do not re-implement them.
- When a task is done, update its status here and message the orchestrator with a short summary and anything that is still unverified.

## Pinned facts (already verified; don't re-research)
- **Engine**
  - Spec is in `config/engine.lock.json`: 7.8 GB `.7z` on Hugging Face, pinned to a revision, with the upstream LFS SHA256.
  - To extract, prefer `C:\Program Files\7-Zip\7z.exe` (installed). Fallback: Windows `tar.exe` (bsdtar 3.8.8, libarchive; reads 7z).
  - `curl.exe -L -C -` gives resumable downloads.
- **Voices**
  - `config/models.json`: pinned revision, per-file SHA256 and size, URL = `url_template`.
  - Beatrice zips are `optional` (Plan C only).
- **Engine launcher at tag 2.3.260718**
  - `go-realtime_gui.bat` does `cd` to the engine dir, prepends `runtime` to PATH, then runs `runtime\python.exe -I realtime_gui.py`.
- **Packaged engine (verified in T4)**
  - Runtime: Python 3.12.10, FreeSimpleGUI 5.1.0, sounddevice 0.5.5.
  - The packaged `realtime_gui.py` is 999 lines. Its only difference from the GitHub tag is that the TorchGate noise-reduction path calls `self.tg(...)` directly instead of `run_cuda_graph`. Everything the add-on uses, including handler lines 519/521, is identical.
  - Assets are bundled, so nothing is fetched at runtime:
    - HuBERT in `assets/hubert_base/` (transformers format, loaded with `local_files_only=True`),
    - `assets/rmvpe/rmvpe.pt`,
    - FCPE inside `torchfcpe`.
  - The shipped `configs/config.json` points at MME/VoiceMeeter devices; the launcher overrides every relevant key.
- **`realtime_gui.py` facts the add-on depends on** (from tag 2.3.260718; still true in the packaged copy)
  - Everything, including `class GUI`, lives inside `if __name__ == "__main__":`. You can't import it; run it with `runpy.run_path(path, run_name="__main__")`, and cwd plus `sys.path[0]` must be the engine dir.
  - The window is `sg.Window("RVC - GUI", ...)` stored as `self.window`. Radio keys `"im"` (raw passthrough) and `"vc"` (converted) are in the group `"function"`.
  - `event_handler` line 519: `elif event in ["vc", "im"]: self.function = event`. Line 521: `elif event == "stop_vc" or event != "start_vc": self.stop_stream()`.
    - So **any unknown event stops the stream**. The patched `Window.read` must translate the custom hotkey event into `"vc"`/`"im"` and update the radio on the GUI thread.
  - `sg.popup(...)` also calls `Window.read`. Only capture the window titled `"RVC - GUI"`.
  - `configs/config.py` calls `argparse.parse_args()` on `sys.argv` (`--port`, `--pycmd`, ...). **Reset `sys.argv = [realtime_gui_path]` before `runpy`**, or our `--preset` flag crashes it.
  - `-I` (isolated mode): the script dir is not on `sys.path`, and `PYTHON*` env vars are ignored. Non-PYTHON env vars such as `RVC_CUDA_GRAPH` still work.
  - `set_values` rejects an empty `index_path` and **non-ASCII paths**, so absolute repo paths must be ASCII.
  - `load()` reads `configs/config.json`. If `sg_hostapi` is not among sounddevice hostapi names, or the device names aren't *exact* members of that hostapi's device lists, it silently falls back to the Windows defaults.
    - That fallback is wrong for us: the default recording device will be CABLE Output. **Resolve exact names yourself** from `config/audio.json` substrings, using the engine's `sounddevice`, and fail loudly if there's no match.
  - Hostapi names in sounddevice: `"MME"`, `"Windows DirectSound"`, `"Windows WASAPI"`, `"Windows WDM-KS"`, `"ASIO"`.
  - When the user presses start, the GUI rewrites `configs/config.json` *without* `formant`. That's fine: our launcher re-merges the preset on every launch.
  - `sr_type` must be `"sr_device"` for WASAPI shared: 40k models + `sr_model` = sample-rate mismatch.
  - The threshold gate is only active when `threhold > -60`.
  - `load()` wraps everything in a bare `try/except`. A missing `sr_type`, `sg_hostapi`, `sg_input_device` or `sg_output_device` makes it silently rewrite `config.json` with defaults, which drops the preset. The launcher must guarantee these keys and fail loudly otherwise. (Found by Worker-1.)
  - The input and output noise-reduce checkboxes don't read `config.json` (no `default=`), so they're not configurable from our presets. Toggle them in the GUI if needed.
  - `RVC_CUDA_GRAPH=0` env var disables the CUDA Graph path; it is auto-enabled otherwise.
- **Cue sounds:** `C:\Windows\Media\Speech On.wav` / `Speech Off.wav` exist.
- **FFmpeg 9.0.2** is on PATH (winget).
  - `ffmpeg -list_devices true -f dshow -i dummy` lists capture devices.
  - The Maxwell is currently disconnected and VB-CABLE isn't installed yet, so real device tests wait for the user.
  - Pitfall: ffmpeg normalises each input's start time separately. Two dshow inputs in one run are NOT time-aligned by default. Use wallclock timestamps + `-copyts` into a pts-preserving container (e.g. `.mkv`), then run `silencedetect` with `-copyts` on each, or another method that keeps both inputs on one clock.
  - Use `-audio_buffer_size` of about 10–20 ms (the dshow default is ~500 ms).

## Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| T0 | Repo skeleton, pinned manifests (`config/*.json`), presets, this board, `docs/PLAN.md` | Orchestrator | done |
| T1 | `vcgui/hotkey_launcher.py` + stub-based tests | Worker-1 | done (47 stub tests pass; review fixes applied; real-engine smoke test passed) |
| T2 | PowerShell scripts: `install-engine.ps1`, `get-models.ps1`, `launch.ps1`, root `launch.bat`, `list-devices` (flag or script), `measure-delay.ps1` | Worker-1 | done (review fixes applied; tools/test_scripts.py 20 tests pass; real runs OK) |
| T3 | Docs: `README.md`, `CREDITS.md`, `docs/windows-audio.md`, `docs/overwatch.md`, `docs/tuning.md`, `docs/voices-and-licenses.md`, `docs/perf-testing.md` | Worker-1 | in progress |
| T4 | After the user approves downloads: run install + get-models, check the packaged `realtime_gui.py` against the facts above, smoke-test the launcher (list devices, GUI opens with the preset, hotkey flips vc/im) | Worker-1 | done (engine + 9 voice files SHA256-verified; anchors OK; smoke test passed on virtual devices, real Maxwell/CABLE in T5) |
| T5 | In-game acceptance (plan Step 5) with the user: VB-CABLE install, Maxwell connected, Overwatch settings, FrameView runs, delay measurement | User + Worker-1 | blocked (user) |

### T1 — `vcgui/hotkey_launcher.py` (acceptance)
- Runs with `engine\runtime\python.exe -I vcgui\hotkey_launcher.py --engine <dir> --preset <id>`.
- Uses the stdlib plus the engine's own `sounddevice` / `FreeSimpleGUI` only.
- Before starting the GUI:
  1. Merge the existing `engine/configs/config.json` (if valid), then `config/audio.json` `settings`, then `config/presets/<id>.json` `settings`.
  2. Make `pth_path`/`index_path` absolute (repo-relative) and check that they exist and are ASCII.
  3. Resolve the input/output device names within `hostapi`.
  4. Write `engine/configs/config.json`.
- `--list-devices` prints the input and output device names per hostapi and exits. `--list-presets` is optional.
- Hotkey:
  - Parse `"ctrl+alt+v"`-style combos (modifiers ctrl/alt/shift/win; keys a–z, 0–9, f1–f24, numpad0–9, plus a few named keys).
  - `RegisterHotKey(None, id, mods|MOD_NOREPEAT, vk)` + a `GetMessageW` loop on a daemon thread.
  - If registration fails, fall back to `poll` (`GetAsyncKeyState`, edge-triggered, `poll_interval_ms`) and print why.
  - The hotkey calls `window.write_event_value("__HOTKEY_TOGGLE__", None)`.
  - It never sends input to any other window.
- Patched `FreeSimpleGUI.Window.read`:
  - capture only the `"RVC - GUI"` window;
  - on the toggle event, flip the radio via `window[key].update(value=True)`, set `values["vc"]`/`values["im"]`, play the cue with `winsound.PlaySound(..., SND_FILENAME|SND_ASYNC|SND_NODEFAULT)`, print the state, and return `(key, values)`;
  - all other events pass through untouched.
- Then `os.chdir(engine)`, `sys.path.insert(0, engine)`, `sys.argv = [gui_path]`, `runpy.run_path(gui_path, run_name="__main__")`. **Do not modify any engine file.**
- Tests: `tools/test_hotkey_launcher.py` runs on system Python 3.13 with a **stub** `FreeSimpleGUI` + stub `realtime_gui.py` in a temp dir. It covers:
  - config merge + device resolution (with a fake sounddevice),
  - hotkey parsing,
  - the read-patch translating the toggle into `vc`/`im` and ignoring popups,
  - `sys.argv` reset.
- It does not need a real engine.

### T2 — scripts (acceptance)
- `install-engine.ps1`:
  - idempotent;
  - resumable `curl.exe` download to `downloads/`;
  - size + SHA256 check against `engine.lock.json` (refuse on mismatch);
  - extract to a temp dir, then move the folder that contains `go-realtime_gui.bat` to `engine/`;
  - verify `required_files`;
  - grep `realtime_gui.py` for the anchors the add-on needs (`key="im"`, `key="vc"`, `elif event in ["vc", "im"]`, `sg.Window("RVC - GUI"`) and warn loudly if any are missing.
  - `-SkipDownload` for an already-downloaded archive.
- `get-models.ps1`:
  - reads `models.json`; default = voices with `"default": true`, non-optional files;
  - `-Voice id,...`, `-IncludeBeatrice`;
  - resumable download, SHA256 verify, skip files already verified.
- `launch.ps1` (`-Preset`, default `vctk-p231`; `-NoCudaGraph`; `-ListDevices`):
  - set PATH to include `engine\runtime`;
  - run the engine's python `-I` on `hotkey_launcher.py`;
  - print friendly errors if the engine or models are missing.
- Root `launch.bat` forwards args to `launch.ps1` (`-ExecutionPolicy Bypass -NoProfile`) and does `chcp 65001`.
- `measure-delay.ps1`:
  - resolve dshow device names by substring (defaults "Audeze Maxwell"/"Chat" and "CABLE Output");
  - record ~12 s from both on one clock (see the pitfall above);
  - the user says a sharp "ta!" a few seconds in;
  - report onset(cable) − onset(mic) in ms;
  - save captures to `captures/` (git-ignored).
- All scripts: `Set-StrictMode`, `$ErrorActionPreference='Stop'`, repo-relative paths via `$PSScriptRoot`, and no admin.

### T3 — docs (acceptance)
Follow `docs/PLAN.md` Steps 0–6, Fallbacks and Verification.
- README: quick start (install engine → get voices → one-time Windows audio setup → Overwatch settings → `launch.bat -Preset vctk-p231`), daily use, hotkey, "back to real mic", switching voices, troubleshooting.
- `docs/windows-audio.md` = plan Step 1 (user steps, VB-CABLE Pack45, 48 kHz, defaults, "Listen to this device").
- `docs/overwatch.md` = Voice Chat Devices, Open Mic, FPS cap, Reflex, push-to-talk tail note.
- `docs/tuning.md` = starting values + the one-step tuning loop + pitch formula + technique.
- `docs/voices-and-licenses.md` + `CREDITS.md`:
  - VCTK attribution;
  - optional Tsukuyomi-chan / Amitaro with their content clauses;
  - excluded sources and why.
- `docs/perf-testing.md` = baseline/acceptance protocol (FrameView ×3, 1% lows ≥ 120 FPS, inference < ~70% of block_time, delay ≤ ~300 ms) plus a results table to fill in.
