# Gaming Voice Changer — Plan (rev 2)

## Context
The user wants a real-time voice changer to use while playing Overwatch. The example is male → girl's voice, but neither the voice nor the game is hard-coded, and the voice must be adjustable. It has to be light enough not to ruin gameplay. The job is to assemble existing tools, not build them from scratch. A minimal UI with basic toggles is enough.

The repo `Gaming-Voice-Changer` is empty (no commits). It will hold setup scripts, pinned download manifests, voice presets, one small hotkey add-on, and docs. Engines and models stay out of git.

**Constraints / answers from user**
- Mic: Audeze Maxwell boom mic ("Chat" endpoint). It currently shows as disconnected ("Unknown"), so it must be connected for tuning.
- Destination: Overwatch voice chat. The virtual mic will work in other apps too.
- Voices: try several, so we use presets.
- Hotkey: voice changer on/off.
- **HARD: no paid subscriptions and no accounts.** After the one-time free downloads, it must run fully offline.

**Machine (verified):** RTX 4080 SUPER 16 GB, Ryzen 9 9950X, 61.6 GB RAM, Win 11 Pro 26200, FFmpeg 9.0.2 installed (winget). Existing Voicemod, Voice.ai and EaseUS virtual devices will not be used. VB-CABLE is not installed.

## Engine decision: official RVC real-time GUI (primary), VCClient (benchmark fallback)
Research (2026-09-24, adversarially verified) led to the official **RVC-Project integrated package `2.3.260718`** (2026-07-21, MIT, `go-realtime_gui.bat`) over VCClient:
- **Maintained.** VCClient is dormant.
  - Its last RVC-capable builds are 2.0.78-beta (May 2025) and 2.1.4-alpha (Jun 2025).
  - v2 is closed source, and 2026 issues get no replies.
  - There is an open report of in-game choppiness on an RTX 4080 SUPER.
- **Lighter while gaming.** CUDA Graph acceleration gives lower latency and about 20–30% less GPU use. FP16 is used automatically.
- **Controls we need already exist:**
  - pitch
  - **formant** (VCClient RVC has none)
  - index rate
  - noise-gate threshold
  - f0 method (rmvpe/fcpe)
  - block/crossfade/extra time
  - noise reduction
  - WASAPI device picker
  - live inference-time readout
  - built-in **`vc` / `im` switch** (converted vs raw mic, changeable live)
- **The hotkey requirement is achievable.** VCClient has no global hotkey either, so both engines would need a small add-on. This engine's toggle can be driven in-process without modifying its files (Step 4).
- The same package can train voices later if ever wanted.

Signal chain:
```
Maxwell boom mic (48 kHz) ─► RVC realtime GUI (WASAPI shared, CUDA) ─► CABLE Input (VB-CABLE)
   ─► CABLE Output = Windows default recording device ─► Overwatch voice chat (Open Mic)
hotkey add-on (in the GUI process) flips vc ⇄ im + plays a Windows cue sound on the headset
```

## Repo layout (authored; everything large is downloaded and git-ignored)
```
README.md                  quick start, daily use, "back to real mic", troubleshooting
.gitignore                 engine/, models/, downloads/, captures/, *.pth, *.index, *.7z
config/engine.lock.json    pinned URL + size + SHA256 of RVC20260718Nvidia.7z
config/models.json         each voice: URL, SHA256, license, attribution line
config/presets/*.json      one per voice: RVC GUI config keys (pth_path, index_path, pitch, formant,
                           index_rate, f0method, threhold, block_time, crossfade_length, extra_time,
                           sg_hostapi, sg_input_device, sg_output_device, ...)
config/hotkey.json         combo, method (registerhotkey | poll), cue sounds
scripts/install-engine.ps1 resumable download → SHA256 check → extract → engine/
scripts/get-models.ps1     download the manifest's voices → SHA256 check → models/ → CREDITS.md
scripts/launch.ps1 + launch.bat -Preset <name>: merge preset into engine/configs/config.json,
                           run engine\runtime\python.exe vcgui\hotkey_launcher.py
scripts/measure-delay.ps1  FFmpeg dshow capture of mic + CABLE Output → silencedetect onset diff
vcgui/hotkey_launcher.py   the only real code (~100 lines, stdlib only)
docs/                      windows-audio.md, overwatch.md, tuning.md, voices-and-licenses.md, perf-testing.md
```

## Steps

### 0. Baseline
- Quit the Voicemod, Voice.ai and EaseUS background apps.
- In the Overwatch Practice Range, run the same route 3 times with fixed graphics settings. Capture with **NVIDIA FrameView** (free), or PresentMon 2.6 as the alternative.
- Record avg FPS, **1% lows** and stutter.

### 1. Audio plumbing (manual, `docs/windows-audio.md`)
- Install **VB-CABLE Pack45** (donationware; admin install plus reboot).
  - Fallback if it crackles: VAC Lite 4.71 (free for home use).
  - We deliberately don't reuse the Voice.ai cable: its driver is owned by another app's installer and updater, so an update or uninstall would silently break the chain.
- Set **48 kHz** on:
  - the Maxwell Chat mic,
  - the Maxwell playback endpoints,
  - both sides of the cable.
- On the mic and the cable, turn off enhancements and Voice clarity. Set Communications ducking to "Do nothing".
- Windows defaults:
  - **CABLE Output = Default recording device.**
  - The Maxwell Game endpoint stays the default playback device.
  - **Never make CABLE Input the default playback device.**
  - Re-check the defaults after the driver install.
- Maxwell: FILTER A.I. on low, sidetone off.
- To hear yourself while tuning, use "Listen to this device" on CABLE Output. Turn it off for matches.
- **Back to real mic, quickly:**
  - Hotkey → `im` (raw passthrough through the engine).
  - If the engine is closed or has crashed: Settings → System → Sound → Input → Maxwell. Document this in the README.

### 2. Engine install (`install-engine.ps1`)
- Download `RVC20260718Nvidia.7z` (~7.8 GB). Record SHA256 on first download, then verify on every reinstall. Extract to `engine/`.
- Confirm the packaged `realtime_gui.py` matches what the add-on relies on:
  - `GUI` and `self.window`,
  - the `vc`/`im` radio keys,
  - the handler at line 519.
  - Also note that line 521 stops the stream on *any* unknown event, which is why the add-on must translate its event into `vc` or `im`.
- Confirm the bundled `assets/` include hubert and rmvpe, so nothing is fetched at runtime.
- Never disable antivirus. Never run the engine as admin.

### 3. Voices (`get-models.ps1`, `docs/voices-and-licenses.md`)
**Default set: English, natural female, rights-cleared**
- Source: **Nekochu/RVC-VCTK_Voice-sample** (Hugging Face).
  - Model card: Apache-2.0. The underlying VCTK corpus is CC BY 4.0, so attribution goes in `CREDITS.md`.
  - These are RVC v2 models: 250 epochs, rmvpe, pitch-aware (55 MB .pth plus an `added_*_v2.index`).
- Presets:
  - **p231** (default): `F/p231/Fp231.pth` plus `added_IVF1216_Flat_nprobe_1_Fp231_v2.index`
  - **p238**
  - **p249**
  - More female speakers exist under `F/` and can be added the same way.
- Each speaker folder also ships a **Beatrice v2** model (`*_beatrice-v2_*step.zip`), which gives the same voice for the CPU-only Plan C.

**Optional anime-style extras**
- Official **Tsukuyomi-chan RVC** (free, credit required; terms ban attacking or criticizing people).
- **Amitaro** official models (credit required; must never be passed off as your real voice; no sensitive statements).
- Both clauses matter for competitive banter, so these are opt-in.

**Excluded**
- AISO: pitch-less models, so the pitch slider does nothing and they need a ~2 s chunk.
- Real-person or character voices from unlicensed sites.
- VCClient-bundled samples: licensed for VCClient only.

**Starting preset**
- pitch **+10**. Tune by ear: +8…+14, or 12·log2(target F0 / your F0).
- formant **0** (try +0.5…+1.5).
- f0 **rmvpe**.
- **index_rate 0** to start. Later test 0.3 for less male-timbre leakage if GPU/CPU headroom allows.
- threshold ≈ **-45 dB** (gate).
- block_time **0.25**, crossfade **0.05**, extra_time **2.5**.
- Noise reduction off.
- WASAPI shared, output = CABLE Input.

Technique: a lighter "mixed" voice with forward resonance converts far better than falsetto.

### 4. Hotkey add-on (`vcgui/hotkey_launcher.py`, the only real code)
- Runs on the engine's bundled Python. Uses only the stdlib: `ctypes`, `threading`, `winsound`, `runpy`, `json`.
- Launch sequence:
  - `chdir` to `engine/` and insert it into `sys.path`.
  - Monkeypatch `FreeSimpleGUI.Window.read` so the custom `"__HOTKEY_TOGGLE__"` event:
    - flips the `vc`/`im` radio on the GUI thread,
    - plays `C:\Windows\Media\Speech On.wav` / `Speech Off.wav`,
    - returns `("vc"|"im", values)` to the stock handler.
  - Then `runpy.run_path("realtime_gui.py", run_name="__main__")`. The upstream file is not modified.
- Hotkey thread:
  - `RegisterHotKey` with `MOD_NOREPEAT` (default Ctrl+Alt+V, configurable) plus a `GetMessage` loop.
  - It posts `window.write_event_value(...)`.
  - It is **listen-only**: it never sends input to the game, and there is no AutoHotkey.
  - `"method": "poll"` fallback: a 30 ms `GetAsyncKeyState` poll, for the case where Overwatch's raw input suppresses registered hotkeys.
- Pitch, formant and devices stay in the stock GUI window. Switching voices = relaunch with `-Preset`; the GUI needs a stream restart for a model change anyway.

### 5. Overwatch setup, tuning loop, acceptance
- **Overwatch settings:**
  - Voice Chat Devices = Default Devices (alternative: Comms, with CABLE Output as the default communication device).
  - **Open Mic.** With push-to-talk, hold the key about 0.3 s past the end of speech, because there is no release delay and the converted tail would be clipped.
  - **Frame-rate cap** (required for RVC while gaming).
  - Reflex on.
- **Tuning loop, one step at a time:**
  - audio stutters/crackles → raise block_time;
  - delay too high with no stutter → lower block_time, then extra_time;
  - game performance misses the target → keep index 0, then f0 → fcpe, then lower the FPS cap, then A/B test HAGS, then `RVC_CUDA_GRAPH=0` if the CUDA Graph path misbehaves.
- **Acceptance**, on 3 matched FrameView runs with conversion on vs the Step 0 baseline (same graphics and cap):
  - **1% lows ≥ 120 FPS**
  - no recurring stutter
  - GUI inference time under ~70% of block_time during fights
  - stable end-to-end voice delay **≤ ~300 ms**, measured with `measure-delay.ps1`: FFmpeg records the raw mic and CABLE Output together, you clap, and `silencedetect` onset times give the offset

### Fallbacks (only if Step 5 acceptance fails)
- **B: VCClient**, benchmarked with the same voice and the same Step 5 tests. Adopt it only if it passes.
  - Use v1.5.3.18a (open source). The add-on switches to its REST API: `POST http://127.0.0.1:18888/update_settings`, `key=passThrough`, `val=true|false`.
  - Block inbound port 18888 in the firewall.
  - Alternatives:
    - **deiteris fork b2332**: same API; adds `formantShift`; binds 127.0.0.1; stale since Dec 2024; reported split-zip extraction issue.
    - v2 `vcclient_win_cuda_2.0.78-beta`: its API is undocumented; you would read it from `:18000/docs`.
- **C: zero GPU.** Beatrice v2 official VST rc.3 in a free VST host, loading the **same VCTK voices' Beatrice zips**. Whether these Jan-2025 models load in rc.3 needs verifying. CPU only, ~50 ms, less realistic.

## Verification (end to end)
1. `install-engine.ps1` and `get-models.ps1` verify every SHA256. The stock `go-realtime_gui.bat` opens.
2. `launch.bat -Preset p231` opens the GUI with the preset loaded. Start conversion and confirm the voice via "Listen to this device".
3. **Record 1 minute from CABLE Output** with FFmpeg. Check for clipping, dropouts, echo, and gate chatter.
4. Hotkey on the desktop and then with Overwatch focused (fullscreen and borderless): the radio flips vc⇄im, the cue plays, and there is no stream restart. If it doesn't fire in-game, switch to `"poll"` and re-test.
5. Switch presets (p238, p249) and confirm the voices change.
6. **Offline test:** disable networking, reboot, then launch and convert. This proves there are no online, account or subscription dependencies.
7. Run the Step 5 acceptance: 3 FrameView runs plus `measure-delay.ps1`. Record results in `docs/perf-testing.md`.
