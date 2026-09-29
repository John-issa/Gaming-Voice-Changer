# Gaming Voice Changer

A real-time voice changer for gaming on Windows. It converts your headset mic into another voice (by default `ex02`, a natural English female voice trained for this project) and hands the result to games as an ordinary microphone. It is set up for Overwatch (formerly Overwatch 2) voice chat, and it works with any app that records from the default Windows mic. Nothing is re-implemented: it assembles free tools (the official RVC realtime GUI, RVC voice models and the VB-CABLE virtual audio cable) and adds one small add-on for voice presets, two hotkeys and a Voice / Save settings / Mute cable row in the window. The signal chain, with the Windows WASAPI device names from the development PC (as `launch.bat -ListDevices` prints them):

```text
Headset mic: Microphone (Chat-Audeze Maxwell), 48 kHz
  -> RVC realtime GUI (WASAPI shared mode, CUDA)       converts the voice
  -> CABLE Input (VB-Audio Virtual Cable)              VB-CABLE playback side
  -> CABLE Output (VB-Audio Virtual Cable)             VB-CABLE recording side = Windows default recording device
  -> Overwatch voice chat (Open Mic), or any app that uses the default mic

Game sound and cue sounds: Speakers (Game-Audeze Maxwell) = Windows default playback device
Add-on (inside the GUI process): presets, voice switching, Save settings, converted voice <-> raw mic, cable mute, cue sounds
```

## Requirements

| Item | Details |
|---|---|
| Windows 11 | Developed on Windows 11 Pro. The scripts use the built-in Windows PowerShell, `curl.exe` and `tar.exe`. 7-Zip is optional: it unpacks faster, and without it `tar.exe` skips a few files with non-ASCII names that the engine doesn't need. |
| NVIDIA GPU | The pinned engine is the NVIDIA build for cards older than the RTX 50 series. Developed on an RTX 4080 SUPER (16 GB). |
| Disk space | About 25 GB free during setup: the 7.8 GB archive, about 15 GB of unpacked engine and 1.5 GB of VCTK voices (1.3 GB more for the optional `vctk-all-f`). You can delete the archive afterwards. The default voice `ex02` takes 2.4 GB more and is not downloaded: it comes from your backup, or a rebuild that needs about 50 GB free while it runs ([docs/custom-voice.md](docs/custom-voice.md)). |
| RAM | `ex02` loads a 2.3 GB voice index, which takes about 4.5 GB of RAM while the voice changer runs. The VCTK voices need far less. |
| Headset mic | The defaults match the Audeze Maxwell boom mic. Another mic needs one edit in `config/audio.json` (see [Troubleshooting](#troubleshooting)). |
| VB-CABLE | Free virtual audio cable (donationware, no account). You install it in Quick start step 3. |
| ASCII-only folder | The RVC GUI rejects model paths with non-ASCII characters, so keep this repo in a folder whose full path is plain ASCII. |
| FFmpeg (optional) | Only for performance testing ([docs/perf-testing.md](docs/perf-testing.md)): `winget install Gyan.FFmpeg`. |

## Recommended setup (copy this)

The setup the project owner uses and currently prefers (last updated 2026-09-29). To skip the tuning, copy it exactly. Everything is adjustable later ([docs/tuning.md](docs/tuning.md)).

| Where | Setting | Value |
|---|---|---|
| Voice | Preset | `ex02` (the default; `launch.bat` with no options) |
| RVC window | Pitch settings | 12 (anything from +12 to +18 also sounds good; the slider goes from -24 to +24) |
| | Gender factor / voice thickness | 0 |
| | Index Rate | 0.5 |
| | loudness factor | 0.75 |
| | pitch detection algorithm | rmvpe |
| | Response threshold | -60 (gate off) |
| | Sample length / Fade length / Extra inference time | 0.25 / 0.15 / 4.0 (about 1.4 s delay) |
| | Input / Output noise reduction | off |
| | Device type / sample rate | Windows WASAPI (not exclusive) / Use device sample rate |
| | Input → Output device | Microphone (Chat-Audeze Maxwell) → CABLE Input (VB-Audio Virtual Cable) |
| Windows sound | Default recording / playback device | CABLE Output / Speakers (Game-Audeze Maxwell); every device at 48000 Hz |
| Overwatch | Voice chat devices / mode | Default Devices / Open Mic; cap the frame rate below the refresh rate |
| NVIDIA Control Panel | Power management mode for `engine\runtime\python.exe` | Prefer maximum performance |

The presets already hold all the RVC-window values: `launch.bat` applies them, so there's nothing to set by hand in that window. **Reference point:** `ex02-reference` (in the Voice list, or `launch.bat -Preset ex02-reference`) keeps the original tuned setup unchanged, with Sample length 0.75 and about 3 s of delay, so you can always compare against it. It's locked: **Save settings** never writes to it (the status shows `Reference is locked`).

`ex02` isn't downloadable. Without a backup of `models\ex02`, use `vctk-p231` with the same RVC-window values, or rebuild `ex02` ([docs/custom-voice.md](docs/custom-voice.md)).

## Quick start

Run the commands from the repo folder in a normal (not administrator) terminal. `-ExecutionPolicy Bypass` applies only to that one command. In PowerShell, type `.\launch.bat` instead of `launch.bat`.

1. **Install the engine** (downloads about 7.8 GB). If the download stops, run it again and it resumes. It checks the size and SHA256 against `config/engine.lock.json`, refuses a mismatch, and unpacks the engine into `engine\`. If `downloads\RVC20260718Nvidia.7z` is already there, add `-SkipDownload`.

   ```text
   powershell -ExecutionPolicy Bypass -File scripts\install-engine.ps1
   ```

2. **Get the voices** (about 1.5 GB). This downloads and verifies seven female VCTK voices (`vctk-p231`, `p238`, `p249`, `p262`, `p280`, `p323`, `p340`) into `models\`. The blend `vctk-all-f` is opt-in: `get-models.ps1 -Voice vctk-all-f`. Details: [docs/voices-and-licenses.md](docs/voices-and-licenses.md#default-voices).

   ```text
   powershell -ExecutionPolicy Bypass -File scripts\get-models.ps1
   ```

   The default voice `ex02` can't be downloaded: restore `models\ex02` from your backup, or rebuild it ([docs/custom-voice.md](docs/custom-voice.md#rebuild-it)). Until then, start a VCTK voice with `launch.bat -Preset vctk-p231`.

3. **Set up Windows audio** once with [docs/windows-audio.md](docs/windows-audio.md): install VB-CABLE (the only admin step), set 48000 Hz, set the default devices, and check them with `launch.bat -ListDevices`. The VB-CABLE installer may make CABLE Input the default playback device; fix that right away with [Right after installing](docs/windows-audio.md#right-after-installing-fix-the-default-devices).
4. **Set up Overwatch** with [docs/overwatch.md](docs/overwatch.md).
5. **Start:** run `launch.bat`. The console prints the preset, model and devices, then the "RVC - GUI" window opens (the first start can take about 20 seconds). Click **Start audio conversion**. To hear what the game gets, see [Hear yourself](docs/windows-audio.md#6-hear-yourself-while-tuning-listen-to-this-device).
6. **Tune** the voice with [docs/tuning.md](docs/tuning.md), then check game performance and delay with [docs/perf-testing.md](docs/perf-testing.md).

## Daily use

1. Double-click `launch.bat` (the same as `launch.bat -Preset ex02`).
2. Click **Start audio conversion** in the RVC window.
3. Keep the console window open: it shows hotkey messages and errors, and closing it closes the voice changer. If a start fails, it stays open so you can read the error.
4. To stop, click **Stop audio conversion** or close the window.

The add-on puts a row at the bottom of the RVC window:

- **Voice:** switches to another preset ([Switching voices](#switching-voices)).
- **Save settings:** writes the current Pitch, Formant, Index Rate, loudness factor and pitch algorithm to the active preset, and Response threshold, Sample length, Fade length and Extra inference time to `config/audio.json` (or to the preset, if it sets that key). It never writes model paths, devices or labels, and keeps the files' layout. A locked preset (`"locked": true`, like `ex02-reference`) is never written, not even the timing in `config/audio.json`.
- **Mute cable:** silence on the cable, also on Ctrl+Alt+M ([The hotkeys](#the-hotkeys)).
- **Status text:** what the last action did, for example `Saved`, `No changes`, `Save failed` (with a beep), `Reference is locked`, `Muted` or `ex02 ready`.

Changes made in the window last only if you click **Save settings**; otherwise every launch re-applies `config/audio.json` and the preset ([Keep your changes](docs/tuning.md#keep-your-changes)). Some controls apply live and others restart the stream ([docs/tuning.md](docs/tuning.md#starting-values)). At the defaults (Sample length 0.25) the game hears you about 1.4 seconds after you speak; `ex02-reference` keeps the original 0.75 (about 3 s) for comparison ([why, and how to shorten it](docs/tuning.md#what-to-expect-from-the-delay)).

Other `launch.bat` options: `-ListPresets`, `-ListDevices`, `-NoCudaGraph` (turns CUDA Graph off for one run; [docs/tuning.md](docs/tuning.md#cuda-graph-and--nocudagraph)) and `-Log <file>` (also appends the console output to that file).

## The hotkeys

Two global hotkeys work while the voice changer runs. Neither restarts anything.

- **Ctrl+Alt+V** switches between the two options next to the Start and Stop buttons, like clicking them.
- **Ctrl+Alt+M** ticks or unticks **Mute cable**.

| Option in the window | Mode | What the game hears | Cue sound | Console message |
|---|---|---|---|---|
| Output converted voice (selected at start) | `vc` | Your converted voice | `Speech On.wav` | `[hotkey] voice changer ON (vc)` |
| Input voice monitor | `im` | Your raw mic, still passed through the engine and the cable. It is not a mute. | `Speech Off.wav` | `[hotkey] voice changer OFF (im: raw mic)` |

**Mute cable** puts true silence on the cable in either mode while the engine keeps running. Nothing you say after pressing it reaches the game, not even right after you unmute (in exchange, up to one Sample length just after unmuting can be lost). Speech from a few seconds before you press it can still come out: the converted voice is about 1.4 s late anyway (about 3 s with `ex02-reference`) ([delay](docs/tuning.md#what-to-expect-from-the-delay)). The cues are `Speech Sleep.wav` (muted) and `Windows Notify System Generic.wav` (unmuted), and the console prints `[mute] cable muted: silence on the output` or `[mute] cable unmuted`. Pressing Ctrl+Alt+V while muted replays the mute cue as a reminder. Every launch starts unmuted.

- The cue sounds (from `C:\Windows\Media\`) play on the default playback device, your headset. Teammates don't hear them unless CABLE Input has become the default playback device.
- The hotkeys only listen and never send keys to the game. With the default method, Windows reserves the combos while the voice changer runs, so the game and other apps don't see them.
- At launch the console prints `[hotkey] ctrl+alt+v toggles the voice changer (RegisterHotKey)` and `[hotkey] ctrl+alt+m mutes/unmutes the cable (RegisterHotKey)`. A Ctrl+Alt+V press before the window is open prints `[hotkey] ignored: the RVC window is not open yet`.

To change them, edit `config/hotkey.json` and relaunch:

| Key | Default | Meaning |
|---|---|---|
| `toggle` | `"ctrl+alt+v"` | The vc/im combo (syntax below). |
| `method` | `"registerhotkey"` | `"registerhotkey"` or `"poll"`, for both hotkeys. |
| `poll_interval_ms` | `30` | How often `poll` checks the keyboard, in milliseconds. |
| `cue_vc` | `"C:\\Windows\\Media\\Speech On.wav"` | Played when the converted voice turns on. `""` means no sound. |
| `cue_im` | `"C:\\Windows\\Media\\Speech Off.wav"` | Played when the raw mic turns on. `""` means no sound. |
| `mute` | `"ctrl+alt+m"` | The Mute cable combo. `""` means no mute hotkey (the box still works). The launcher refuses the same combo as `toggle`. |
| `cue_mute` | `"C:\\Windows\\Media\\Speech Sleep.wav"` | Played when the cable is muted, and on Ctrl+Alt+V while muted. `""` means no sound. |
| `cue_unmute` | `"C:\\Windows\\Media\\Windows Notify System Generic.wav"` | Played when the cable is unmuted. `""` means no sound. |

- Combo syntax: the modifiers `ctrl`, `alt`, `shift` and `win`, joined with `+`, plus one key, for example `"ctrl+alt+f9"`.
- Keys: `a`-`z`, `0`-`9`, `f1`-`f24`, `numpad0`-`numpad9`, and the named keys `space`, `enter`, `tab`, `esc`, `backspace`, `insert`, `delete`, `home`, `end`, `pageup`, `pagedown`, `left`, `up`, `right`, `down`, `pause`, `scrolllock`, `grave`, `minus`, `equals`, `lbracket`, `rbracket`, `backslash`, `semicolon`, `quote`, `comma`, `period`, `slash`, `numpadadd`, `numpadsubtract`, `numpadmultiply`, `numpaddivide` and `numpaddecimal`.
- A letter, digit or `space` needs at least one modifier.
- Windows can't deliver Ctrl+Pause, Ctrl+ScrollLock, or Shift with a numpad digit or `numpaddecimal`, so the launcher rejects those combos. Numpad digits and `numpaddecimal` only work while NumLock is on.

If registering a combo fails (for example, because another app owns it), the console shows `[hotkey] RegisterHotKey(...) failed: ...` and the launcher polls for that combo instead. If a hotkey doesn't fire while the game has focus ([in-game check](docs/overwatch.md#check-the-hotkey-while-the-game-has-focus)), set `"method": "poll"`. Polling doesn't reserve the combos, so the game also gets those keys: pick combos the game doesn't use.

## Back to the real mic

- **Voice changer running:** press Ctrl+Alt+V to switch to `im`. To go silent instead, press Ctrl+Alt+M (Mute cable).
- **Voice changer closed or crashed:** the cable is silent. Make your headset mic the Windows default recording device, and also the Default Communication Device if Overwatch uses Comms Devices. Before your next voice changer session, set CABLE Output back as the Default Device and, if you changed it, the Default Communication Device. Steps: [docs/windows-audio.md](docs/windows-audio.md#back-to-your-real-mic).

## Switching voices

Pick a voice in the **Voice** list at the bottom of the RVC window:

- While converting, it stops and restarts conversion with the new model (about 3-4 seconds; the status shows `Loading <id>...`, then `<id> ready`). While stopped, it only sets the controls (`<id>: press Start`).
- The new preset's saved values replace unsaved changes in the window, as a relaunch would. Click **Save settings** first to keep them.
- A preset with missing files or bad values is refused (`Can't load <id>` and a beep) and nothing changes.
- The pick isn't saved: the next plain `launch.bat` starts `ex02` again.

Or start with a preset: `launch.bat -Preset vctk-p238`. `launch.bat -ListPresets` lists all nine: `ex02` (default), `vctk-p231`, `vctk-p238`, `vctk-p249`, `vctk-p262`, `vctk-p280`, `vctk-p323`, `vctk-p340` and `vctk-all-f`.

For more voices and their licenses, see [docs/voices-and-licenses.md](docs/voices-and-licenses.md).

To make your own preset:

1. Copy a preset to a new name, for example `config\presets\ex02.json` to `config\presets\ex02-high.json`. Use only letters, digits, `.`, `_` and `-` in the name.
2. In the copy, change `label` (shown in the Voice list, by `-ListPresets` and in the console). Keep `voice`, `pth_path` and `index_path`.
3. Run `launch.bat -Preset ex02-high` (new presets appear in the Voice list at the next launch), tune it in the window and click **Save settings**. Or edit the values under `settings` by hand: `pitch`, `formant`, `index_rate`, `rms_mix_rate` and `f0method`, in the RVC GUI's own keys, which override `config/audio.json`. What they do and which values to try: [docs/tuning.md](docs/tuning.md).

## Config files

| File | Holds | Edit it? |
|---|---|---|
| `config/audio.json` | The host API (`Windows WASAPI`) and the substrings that pick your mic (`input_device_match`) and the cable (`output_device_match`). Also the settings every preset shares: `sg_wasapi_exclusive` ("Exclusive WASAPI device"), `sr_type`, `threhold` (noise gate), `block_time`, `crossfade_length` and `extra_time`. | Yes: devices by hand; **Save settings** writes the gate and timing values. |
| `config/hotkey.json` | The two hotkey combos, method, poll interval and cue sounds ([The hotkeys](#the-hotkeys)). | Yes. |
| `config/presets/*.json` | One file per voice: `label`, `voice`, optionally `"locked": true` (Save settings leaves it alone) and `settings` (model paths, pitch, formant, index rate, loudness factor and pitch algorithm). | Yes, or with **Save settings**. Copy one to make a new preset. |
| `config/engine.lock.json` | The pinned engine download: URL, Hugging Face revision, size, SHA256 and required files. | No. |
| `config/models.json` | The pinned VCTK voice downloads: revision, per-file size and SHA256, license and attribution line. `ex02` isn't in it. | Only to add voices ([how](docs/voices-and-licenses.md#add-another-voice)). |

The launcher rewrites `engine\configs\config.json` at every start: the engine's config first, then the `config/audio.json` settings, then the preset's settings. Don't edit that file by hand.

## Troubleshooting

- **You hear nothing, or teammates hear your PC sounds or the cue sounds:** CABLE Input has become the default playback device (the VB-CABLE installer can do this). Make your headset the default playback and communication device again ([docs/windows-audio.md](docs/windows-audio.md#right-after-installing-fix-the-default-devices)).
- **Nobody hears you:** read the console for errors, check that you clicked **Start audio conversion**, that **Mute cable** is off and that CABLE Output is the default recording device, then check the [Overwatch voice chat settings](docs/overwatch.md#voice-chat-devices).
- **`No Windows WASAPI input device matches ...`, `... output device matches ...` or `2 Windows WASAPI ... devices match ...`:** connect the headset or install VB-CABLE; for another mic or cable, put a substring of its name from `launch.bat -ListDevices` in `input_device_match` or `output_device_match` in `config/audio.json` ([docs/windows-audio.md](docs/windows-audio.md#troubleshooting)).
- **`Sample rates differ: ...`:** set the mic and both sides of the cable to 48000 Hz, then relaunch ([docs/windows-audio.md](docs/windows-audio.md#2-set-every-device-in-the-chain-to-48000-hz)).
- **`The RVC engine is not installed`:** run `scripts\install-engine.ps1`. If it says `engine exists but is incomplete`, rename or delete `engine\`, then run it again.
- **`The voice files for preset '...' are missing`:** for a VCTK voice, run the `get-models.ps1 -Voice ...` command the message shows. For `ex02`, restore `models\ex02` from your backup or rebuild it ([docs/custom-voice.md](docs/custom-voice.md#rebuild-it)), or use `launch.bat -Preset vctk-p231`.
- **`Can't load <id>` or `Save failed` in the window:** the console line starting with `[voice]` or `[save]` says why.
- **A download stopped or failed:** run the same script again; it resumes and skips files that already verify. If the error says to delete a file (a full-size file whose SHA256 doesn't match), delete it first. If it says to run without `-SkipDownload`, drop that switch.
- **`pth_path has non-ASCII characters, which the RVC GUI rejects`:** move the repo to a folder whose full path is plain ASCII, for example `C:\Tools\Gaming-Voice-Changer`. A non-ASCII Windows user name causes this too if the repo is in your user folder.
- **A hotkey doesn't fire in game:** set `"method": "poll"` in `config/hotkey.json` and relaunch ([The hotkeys](#the-hotkeys)).
- **Crackles, stutter or choppy voice:** raise "Sample length" one step ([docs/tuning.md](docs/tuning.md#the-tuning-loop)). If it also crackles in `im` (no conversion), try the [VAC Lite fallback](docs/windows-audio.md#fallback-vac-lite-if-vb-cable-crackles).
- **Words cut in and out:** check that "Response threshold" is at -60 (gate off), then that "Inference time (ms)" stays well below the Sample length ([docs/tuning.md](docs/tuning.md#the-tuning-loop)).
- **The voice sounds gender-neutral, too much like you, or robotic:** [docs/tuning.md](docs/tuning.md#it-sounds-gender-neutral-or-too-much-like-you) has a step list for each.
- **Conversion errors out or sounds broken:** try `launch.bat -NoCudaGraph` once ([docs/tuning.md](docs/tuning.md#cuda-graph-and--nocudagraph)).
- **Your antivirus flags a file:** keep protection on and never run the engine as administrator. `install-engine.ps1` only unpacks an archive whose SHA256 matches the pinned upstream file; handle that one file in the antivirus's own quarantine screen.

## Docs

| Doc | Covers |
|---|---|
| [docs/windows-audio.md](docs/windows-audio.md) | VB-CABLE install, 48 kHz, default devices, hearing yourself, back to the real mic, audio-device errors. |
| [docs/overwatch.md](docs/overwatch.md) | Voice chat devices, Open Mic, the push-to-talk tail, frame-rate cap, Reflex, the in-game hotkey check. |
| [docs/tuning.md](docs/tuning.md) | Starting values, what each control does, the delay, the pitch formula, voice technique, the tuning loop, keeping changes. |
| [docs/voices-and-licenses.md](docs/voices-and-licenses.md) | The voices and their licenses, adding voices, optional anime-style extras and their rules, excluded sources. |
| [docs/custom-voice.md](docs/custom-voice.md) | The default voice `ex02`: what it is, backing it up, how it was made, how to rebuild it, the dev tools. |
| [docs/perf-testing.md](docs/perf-testing.md) | Baseline and acceptance runs, delay measurement with `scripts\measure-delay.ps1`, offline test, results tables. |
| [docs/landscape.md](docs/landscape.md) | Dated log of alternatives checked against this stack, and what would change each verdict. Re-check periodically. |
| [docs/PLAN.md](docs/PLAN.md) | Design decisions and the fallbacks (VCClient, CPU-only Beatrice v2). |
| [CREDITS.md](CREDITS.md) | Attribution for the engine, the voices, the `ex02` training data and pretrain, and the tools. |

If you share recordings made with the voices, keep the attribution line from [CREDITS.md](CREDITS.md). `ex02` is for personal, non-commercial use only, because its training data (Expresso) is CC BY-NC 4.0. The rules for every voice, including game moderation, are in [docs/voices-and-licenses.md](docs/voices-and-licenses.md#rules-that-apply-to-every-voice).

## Layout

```text
launch.bat                     starts the voice changer (runs scripts\launch.ps1)
config/                        your settings and the pinned download manifests (table above)
scripts/                       install-engine.ps1, get-models.ps1, launch.ps1, measure-delay.ps1 (FFmpeg delay test), common.ps1 (shared helpers)
vcgui/hotkey_launcher.py       the add-on: preset merge, device matching, hotkeys
vcgui/app_extras.py            the add-on's Voice / Save settings / Mute cable row
tools/test_hotkey_launcher.py  tests for vcgui\ (run with python; stubs, no engine, devices or internet)
tools/test_scripts.py          tests for scripts\ (run with python; local fixtures, 7-Zip and FFmpeg tests skip if missing)
tools/rt_render.py             renders a WAV through the realtime engine path offline, for A/B tests of settings and voices
tools/artifact_scan.py         counts clicks, spikes, dropouts, block-edge artifacts and pitch wobble in a recording
tools/expresso_prep.py         builds the ex02 training folder from the Expresso tar
tools/build_full_index.py      builds the full retrieval index for a trained voice
docs/                          setup, tuning, licenses, the custom voice, performance testing, plan
CREDITS.md                     attribution
engine/ models/ downloads/ captures/   downloaded or generated, git-ignored (back up models\ex02)
```

## Offline and free

- No accounts, no subscriptions, nothing to buy.
- The only downloads are one-time: the engine from the public Hugging Face repo `lj1995/VoiceConversionWebUI` and the VCTK voices from `Nekochu/RVC-VCTK_Voice-sample` (both pinned by revision and SHA256), and VB-CABLE from vb-audio.com. Only a rebuild of `ex02` also downloads, once, the Expresso dataset and the TITAN pretrain ([docs/custom-voice.md](docs/custom-voice.md#rebuild-it)).
- VB-CABLE is donationware: free to use, with no account ([license details](docs/windows-audio.md#1-install-vb-cable)).
- After setup, nothing is fetched at runtime: HuBERT, rmvpe and fcpe all ship inside the engine package ([offline test](docs/perf-testing.md#6-offline-test)).
- Commercial voice-changer apps and their virtual devices are not used ([why](docs/windows-audio.md#why-not-other-voice-changers-devices)).
