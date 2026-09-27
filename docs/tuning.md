# Tuning the voice

This page covers the settings in the "RVC - GUI" window: the starting values, what each control does, and how to tune one step at a time. Changes made in the window last only if you press "Save settings" ([Keep your changes](#keep-your-changes)).

Before you start:

1. Finish the [Quick start](../README.md#quick-start), run `launch.bat` and click "Start audio conversion".
2. To hear the result, turn on "Listen to this device" on CABLE Output ([windows-audio.md](windows-audio.md#6-hear-yourself-while-tuning-listen-to-this-device)). Turn it off before a match.
3. Use [the vc/im hotkey](../README.md#the-hotkeys) (default Ctrl+Alt+V) to compare the converted voice with your raw mic.

Tune on the desktop first, then check the result in the game.

## Starting values

The launcher merges two files at every start: `config/audio.json` (timing, gate and audio mode, shared by every preset), then `config/presets/<id>.json` (one voice; a key there overrides `config/audio.json`). Where the voices differ, the table shows ex02 (the default) first, then the VCTK presets.

| GUI label | Start | JSON key | File | A change applies |
|---|---|---|---|---|
| "Pitch settings" | +12 (ex02), +10 (VCTK) | `pitch` | preset | live |
| "Gender factor / voice thickness" | 0.0 | `formant` | preset | live |
| "Index Rate" | 0.5 | `index_rate` | preset | live |
| "loudness factor" | 0.75 (ex02), 0.5 (VCTK) | `rms_mix_rate` | preset | live |
| "pitch detection algorithm" | rmvpe | `f0method` | preset | live |
| "Response threshold" | -60 (gate off) | `threhold` (the engine's spelling) | audio.json | live |
| "Sample length" | 0.75 | `block_time` | audio.json | restart (automatic) |
| "Fade length" | 0.15 | `crossfade_length` | audio.json | restart (automatic) |
| "Extra inference time" | 4.0 | `extra_time` | audio.json | restart (automatic) |
| "Use device sample rate" | selected | `sr_type`: `"sr_device"` | audio.json | restart; leave it |
| "Exclusive WASAPI device" | unticked | `sg_wasapi_exclusive`: `false` | audio.json | restart ([trade-off](#what-to-expect-from-the-delay)) |
| "Device type", "Input device", "Output device" | Windows WASAPI, Microphone (Chat-Audeze Maxwell), CABLE Input (VB-Audio Virtual Cable) | `hostapi`, `input_device_match`, `output_device_match` | audio.json | restart; leave them |
| "Input noise reduction", "Output noise reduction" | unticked | none (a preset can't set them) | - | live |
| "Input voice monitor", "Output converted voice" | "Output converted voice" | none | - | live (the hotkey flips these) |
| The `.pth` and `.index` fields ("Load model") | the preset's voice files | `pth_path`, `index_path` | preset | use the "Voice" list |

- **Live:** the next chunk of audio uses the new value while conversion keeps running.
- **Restart (automatic):** the window stops conversion as soon as you move the slider. If it was running, it starts again by itself about a second after you let go (the console prints `[launcher] restarting conversion with the new setting...`).
- **Restart:** the window stops conversion (so does "Reload device list"). Click "Start audio conversion" again.
- **Model fields:** to change voice, pick one in the "Voice" list at the bottom of the window; it restarts conversion with the new model ([Switching voices](../README.md#switching-voices)). A path typed into the fields by hand is used only at the next Start after "Stop audio conversion".

Keep "Use device sample rate" selected. In WASAPI shared mode the stream runs at the mic's rate (48000 Hz); the VCTK voices are 40 kHz models, so "Use model sample rate" would not match the devices, and the launcher prints a `WARNING` if `sr_type` isn't `"sr_device"`. If the mic and CABLE Input run at different rates, the launcher stops with `ERROR: Sample rates differ: ...` ([fix in windows-audio.md](windows-audio.md#2-set-every-device-in-the-chain-to-48000-hz)). "Exclusive WASAPI device" cuts the delay but locks the mic ([below](#what-to-expect-from-the-delay)).

## What each control does

- **"Pitch settings"** (-16 to +16, whole semitones): the pitch of the converted voice. The main control for a male-to-female change.
- **"Gender factor / voice thickness"** (-2 to +2, steps of 0.05): moves the resonances that make a voice sound bigger or smaller, without changing its pitch.
- **"Index Rate"** (0 to 1): how much of the voice's `.index` file is mixed in. Higher pulls the timbre closer to the target speaker.
- **"loudness factor"** (0 to 1): at 1 the converted voice keeps the model's own loudness; at 0 it copies your loudness moment to moment. Near 0, quiet parts (breaths, noise between words) get boosted up to 15-20x and turn into spikes, so keep it at 0.5 or above.
- **"pitch detection algorithm"**: how the engine reads your pitch. The presets use `rmvpe`. `fcpe` is the alternative the tuning loop tries when the game needs headroom; the first switch loads its model, so expect a short pause. `pm` runs on the CPU and the presets don't use it.
- **"Response threshold"** (-60 to 0 dB): the noise gate ([below](#response-threshold-noise-gate)).
- **"Sample length"** (0.02 to 1.5 s): how much audio is converted at a time. The delay is several times this value ([why](#what-to-expect-from-the-delay)), so it is the main delay control. Longer chunks mean fewer joins: in live tests they chopped and popped less.
- **"Fade length"** (0.01 to 0.15 s): the overlap that blends each chunk into the next. The engine's actual crossfade is capped at 40 ms; above that, more Fade length mostly adds overlap and delay. Longer values also chopped and popped less in live tests, which is why it starts at the maximum.
- **"Extra inference time"** (0.05 to 5 s): earlier audio processed again with each chunk, as context. It adds work to every chunk, not delay.
- **"Input noise reduction"**, **"Output noise reduction"**: GPU noise filtering on every chunk. Input noise reduction also adds up to 40 ms of delay. Leave both off unless you need them.
- **"Input voice monitor"**, **"Output converted voice"**: send your raw mic or the converted voice to the cable. To go silent, use "Mute cable" (Ctrl+Alt+M) instead.

## Pitch

```
semitones = 12 * log2(target F0 / your F0)
```

F0 is the base pitch of your speaking voice, in Hz. Round to a whole number, because the slider moves in steps of 1. For example, a male voice with a median F0 around 86 Hz wants +12 to +14 (about 172-193 Hz); +10 lands near 150 Hz, which sounds low or androgynous. ex02's own voice sits around 253 Hz.

If you don't know your F0, tune by ear:

1. Start at the preset value (+12 for ex02, +10 for the VCTK voices) and try +10 to +14, one step at a time.
2. Go down if the voice sounds squeaky or cartoonish; go up if it still sounds like a low voice.
3. If the pitch is right but the voice still sounds heavy or male, try the formant before adding more pitch.

## Formant

- Start at 0, then try +0.5 to +1.5. Positive values sound smaller and brighter, negative values thicker. Go back down if the voice turns thin or unnatural.
- Set it before a match, not during one. With CUDA Graph on (the default), the first chunk after each new formant value takes longer, so dragging the slider can cause short glitches.

## Index Rate

- Every preset starts at 0.5. The index pulls the timbre toward the target speaker; lower values keep more of your own voice and sound more gender-neutral.
- Raise it to 0.75 if the voice still sounds too much like you ([below](#it-sounds-gender-neutral-or-too-much-like-you)).
- The index search runs on the CPU (faiss) for every chunk and adds to "Inference time (ms)". ex02's full index costs about 11 ms more per chunk and about 4.5 GB more RAM ([custom-voice.md](custom-voice.md#what-it-is)). Watch the [70% rule](#reading-inference-time-ms-and-algorithmic-delaysms); if it doesn't hold under game load, step down to 0.3, then 0.
- When the index is in use, the console prints `Index search enabled` after Start.

## Response threshold (noise gate)

- The start value, -60, turns the gate off. The gate only works above -60. Keep it there.
- The gate checks the level in 10 ms slices and silences every slice below the threshold, with no hold or release, so it chops soft consonants and word endings (at -45 it did on the Maxwell).
- Raise it only if noise between words (breathing, keys, fan) gets converted into strange sounds, and only a little: about -55. If words start cutting in and out, lower it again.

## Technique

How you speak matters as much as the sliders.

- **Use a lighter "mixed" voice:** your normal voice, a little lighter and brighter. Not falsetto (the thin, breathy head voice); a mixed voice converts far better.
- **Use forward resonance:** aim the sound at the front of your face (lips and teeth), as if speaking with a slight smile, rather than from your chest.
- **Stay steady:** keep the same distance from the boom mic and a steady volume. The loudness factor, and the gate if you turn it on, follow your input level.
- **Recheck the pitch if you change your voice:** if you speak higher than usual, you may need less pitch on the slider.

## Reading "Inference time (ms)" and "Algorithmic delays(ms)"

**"Inference time (ms):"** is how long the engine took for the last chunk (gate, resampling, pitch detection and model). It must stay below the Sample length, or the audio crackles. During fights, when the game loads the GPU most, keep it under about 70% of the Sample length:

| "Sample length" | 70% limit for "Inference time (ms)" | "Algorithmic delays(ms)" at Fade length 0.15, shared mode |
|---|---|---|
| 0.25 s | 175 ms | about 1.2 s |
| 0.50 s | 350 ms | about 2.2 s |
| 0.75 s (start value) | 525 ms | about 3.2 s |
| 1.00 s | 700 ms | about 4.2 s |

At 0.75 s, a reading of 250 ms (33%) is fine; 560 ms (75%) is over the limit and close to crackling, so treat it as a stutter and use [the tuning loop](#the-tuning-loop).

The window shows only the latest value. The console prints a line such as `Inference time: 0.30 seconds` for every chunk, so you can scroll back after a fight. For the first 3 chunks and every 100th after that, it also prints `Elapsed time: features=...s, index=...s, pitch=...s, model=...s`, which shows which part costs the most.

**"Algorithmic delays(ms):"** is the window's own estimate, set when you click Start: output device latency + Sample length + Fade length + 10 ms, plus up to 40 ms with "Input noise reduction". It leaves out the mic's input latency. `scripts\measure-delay.ps1` measures the real end-to-end delay ([how to run it](perf-testing.md#4-measure-the-delay-measure-delayps1)).

### What to expect from the delay

At the start values the window shows about 3.2 s, and the real end-to-end delay is in the same range. That is the price of quality-first settings: in live tests, shorter Sample lengths cut the delay but chopped and popped more.

The delay is several times the Sample length because in WASAPI shared mode PortAudio buffers about 2 blocks on input and 3 on output, whatever the latency setting. The window's estimate is therefore about 3 x 0.75 (output latency) + 0.75 + 0.15 + 0.01 = 3.2 s, and each 0.05 s you take off the Sample length lowers it by about 200 ms.

To get it lower:

- **A shorter Sample length:** use the delay steps in [the tuning loop](#the-tuning-loop), and accept more chop.
- **"Exclusive WASAPI device"** (`"sg_wasapi_exclusive": true` in `config/audio.json`; "Save settings" doesn't write it). PortAudio then buffers about 1 block (+10 ms) in and 2 blocks (+9 ms) out, roughly halving the delay. The trade-off: the engine takes the Maxwell mic and CABLE Input exclusively, so no other app can use that mic while conversion runs. Windows settings for it: [windows-audio.md](windows-audio.md#2-set-every-device-in-the-chain-to-48000-hz).

Push to talk in Overwatch: see [the push-to-talk tail](overwatch.md#open-mic-and-the-push-to-talk-tail).

## The tuning loop

1. Change one thing at a time.
2. Re-test the same way each time: sound quality through "Listen to this device", delay with `measure-delay.ps1`, game performance with the runs in [perf-testing.md](perf-testing.md).
3. Write down what you changed and what happened, and press "Save settings" to keep the winning values ([Keep your changes](#keep-your-changes)).

**The audio stutters or crackles:** raise "Sample length" (`block_time`) by 0.05 s at a time.

**Words chop, or the joins pop:** go back to a longer "Sample length" (0.75 or more) and "Fade length" 0.15. The cost is delay.

**Breaths or noise between words come out as loud spikes:** raise "loudness factor" (`rms_mix_rate`) to 0.5 or above. If strange sounds remain, see the [gate](#response-threshold-noise-gate).

**You want less delay and there is no stutter:**

1. Lower "Sample length" (`block_time`) by 0.05 s. Conversion restarts by itself; "Algorithmic delays(ms)" should read about 200 ms less.
2. Listen for a few minutes for chop, pops and crackling, and check "Inference time (ms)" against the 70% limit for the new Sample length. Then run `measure-delay.ps1` 3 times.
3. Clean, and you want less: repeat from step 1. Chop, pops, crackling, or inference time over the limit: go back up 0.05 s.
4. Then lower "Extra inference time" (`extra_time`) one small step at a time and try the lower Sample length again. This doesn't shorten the delay by itself; it cuts the work per chunk, so a shorter Sample length can keep up. Listen after each step: less context can make the voice robotic.
5. Confirm the final value under game load ([perf-testing.md](perf-testing.md)), then press "Save settings".

The other way down is exclusive mode ([What to expect from the delay](#what-to-expect-from-the-delay)).

**Game performance misses the target** ([perf-testing.md](perf-testing.md#targets)). Try these in order, one at a time:

1. Lower "Index Rate" from 0.5 to 0.3, then 0 (less CPU per chunk, more of your own timbre).
2. Switch "pitch detection algorithm" to `fcpe`.
3. Lower the frame-rate cap ([overwatch.md](overwatch.md#frame-rate-cap-required)).
4. A/B test Windows "Hardware-accelerated GPU scheduling" (HAGS), under Settings > System > Display > Graphics (depending on your Windows build, behind "Advanced graphics settings" or "Change default graphics settings"). Restart the PC after each change, run the same test with it on and off, and keep the better result.
5. Run `launch.bat -NoCudaGraph` if the CUDA Graph path misbehaves ([next section](#cuda-graph-and--nocudagraph)).

**Words cut in and out:**

1. Check that "Response threshold" is at -60 (gate off; see [above](#response-threshold-noise-gate)).
2. Check that "Inference time (ms)" stays well below the Sample length (the 70% rule).
3. Set the Maxwell's FILTER A.I. to low, or off, and test again.

### It sounds gender-neutral or too much like you

Pitch sets the register, formant the size of the vocal tract (positive = smaller, brighter), and Index Rate how strongly the trained voice's timbre replaces yours. More feminine: more pitch (+12 to +14), Index Rate 0.5-0.75, formant slightly positive. More gender-neutral: less pitch and a lower Index Rate.

Try these in order, one at a time:

1. Raise "Pitch settings" to +12, then up to +14 ([Pitch](#pitch)).
2. Raise "Index Rate" from 0.5 to 0.75 (costs CPU; watch "Inference time (ms)").
3. Raise "Gender factor / voice thickness" to +0.5, then up to +1.5.
4. Technique: a lighter voice with more pitch movement, as in [Technique](#technique).
5. Try another voice in the "Voice" list ([Switching voices](../README.md#switching-voices)); `vctk-all-f` blends every female VCTK speaker.

### It sounds robotic

1. Keep "Sample length" at 0.75 or more and "Fade length" at 0.15; shorter chunks chop more.
2. Keep "Extra inference time" at 4.0; less context can make the voice robotic.
3. Don't overshoot the pitch: go back down a step or two if the voice turned squeaky.
4. Compare `rmvpe` and `fcpe` ("pitch detection algorithm") by ear.

## CUDA Graph and -NoCudaGraph

The engine's CUDA Graph mode records the GPU work for a chunk once and then replays it. It lowers the inference time and uses about 20-30% less GPU. It is on by default: the engine checks the GPU when it starts and turns it on if the GPU supports it.

- **Is it on?** When the window opens, the console prints `RVC_CUDA_GRAPH=1` (on) or `RVC_CUDA_GRAPH=0` (off). With it on, clicking Start prints `Warming up CUDA Graph`, then `CUDA Graph warm-up complete`.
- **Turn it off for one run:** `launch.bat -NoCudaGraph` (or `launch.bat -Preset vctk-p238 -NoCudaGraph`). This sets `RVC_CUDA_GRAPH=0` for that run only; nothing is saved, so the next plain `launch.bat` turns it back on.
- **When to try it:** the console shows an error after `Warming up CUDA Graph`, or conversion glitches or crashes in a way the other steps don't fix. Without CUDA Graph, expect a higher "Inference time (ms)", so check the 70% rule again.

## Keep your changes

Every launch re-applies `config/audio.json` and the preset, so a change made in the window lasts only if you press "Save settings" (bottom row of the window) before you close it or pick another voice. "Save settings" writes:

- Pitch, formant, Index Rate, loudness factor and pitch detection algorithm to the active preset (the one shown in "Voice").
- Response threshold, Sample length, Fade length and Extra inference time to `config/audio.json`, for every voice. If the active preset has its own value for one of them, that value in the preset is updated instead.

It never writes model paths, devices or labels, and the files keep their layout. The status next to the button reads "Saved", "No changes" or "Save failed" (with a beep; the console says why).

Picking another voice in the "Voice" list replaces unsaved slider changes with that preset's saved values, as a relaunch would, so save first.

Editing the files by hand still works, and is the way to change `sg_wasapi_exclusive`, `sr_type` or the devices:

1. Close the window.
2. Put the values in the right file with a text editor:
   - Voice values (`pitch`, `formant`, `index_rate`, `rms_mix_rate`, `f0method`) go in the preset's `"settings"`, for example `config/presets/ex02.json`.
   - Timing and gate values (`block_time`, `crossfade_length`, `extra_time`, `threhold`) go in `config/audio.json`, for every preset. To override one for a single voice, add the key to that preset's `"settings"`.
3. Write plain JSON: `12`, not `+12`, and `0.5` with a dot. `f0method` must be `"rmvpe"`, `"fcpe"` or `"pm"`, in quotes.
4. Run `launch.bat` (or `launch.bat -Preset <id>`) again. The console shows the preset it loaded, for example `Preset : ex02 - Expresso ex02 - custom voice (e200, full index)`. Invalid JSON, a missing voice file or an unknown `f0method` gives an `ERROR:` line and a pause.

To keep the original preset and save your values as a new one, see [Switching voices](../README.md#switching-voices).

Back to the [README](../README.md).
