# Tuning the voice

This page covers the settings in the "RVC - GUI" window: the starting values, what each control does, and how to tune one step at a time. Changes made in the window are not kept, so it also shows where to save the values you like.

Before you start:

1. Finish the [Quick start](../README.md#quick-start), run `launch.bat` and click "Start audio conversion".
2. To hear the result, turn on "Listen to this device" on CABLE Output ([windows-audio.md](windows-audio.md#6-hear-yourself-while-tuning-listen-to-this-device)). Turn it off before a match.
3. Use [the hotkey](../README.md#the-hotkey) (default Ctrl+Alt+V) to compare the converted voice with your raw mic.

Tune on the desktop first, then check the result in the game.

## Starting values

The launcher merges two files at every start: `config/audio.json` (timing, gate and audio mode, shared by every preset), then `config/presets/<id>.json` (one voice; a key there overrides `config/audio.json`).

| GUI label | Start | JSON key | File | A change applies |
|---|---|---|---|---|
| "Pitch settings" | +10 | `pitch` (`10`) | preset | live |
| "Gender factor / voice thickness" | 0.0 | `formant` | preset | live |
| "Index Rate" | 0.5 | `index_rate` | preset | live |
| "loudness factor" | 0.0 | `rms_mix_rate` | preset | live |
| "pitch detection algorithm" | rmvpe | `f0method` | preset | live |
| "Response threshold" | -60 (gate off) | `threhold` (the engine's spelling) | audio.json | live |
| "Sample length" | 0.25 | `block_time` | audio.json | restart |
| "Fade length" | 0.05 | `crossfade_length` | audio.json | restart |
| "Extra inference time" | 2.5 | `extra_time` | audio.json | restart |
| "Use device sample rate" | selected | `sr_type`: `"sr_device"` | audio.json | restart; leave it |
| "Exclusive WASAPI device" | unticked | `sg_wasapi_exclusive`: `false` | audio.json | restart; leave it |
| "Device type", "Input device", "Output device" | Windows WASAPI, Microphone (Chat-Audeze Maxwell), CABLE Input (VB-Audio Virtual Cable) | `hostapi`, `input_device_match`, `output_device_match` | audio.json | restart; leave them |
| "Input noise reduction", "Output noise reduction" | unticked | none (a preset can't set them) | - | live |
| "Input voice monitor", "Output converted voice" | "Output converted voice" | none | - | live (the hotkey flips these) |
| The `.pth` and `.index` fields ("Load model") | the preset's voice files | `pth_path`, `index_path` | preset | after Stop, then Start |

- **Live:** the next chunk of audio uses the new value while conversion keeps running.
- **Restart:** the window stops conversion as soon as you change the value (or click "Reload device list"). Click "Start audio conversion" again.
- **Model fields:** editing them, or clicking Start while conversion runs, does nothing. Click "Stop audio conversion", then "Start audio conversion". Relaunching with another preset is simpler ([Switching voices](../README.md#switching-voices)).

Keep "Use device sample rate" selected and "Exclusive WASAPI device" unticked. In WASAPI shared mode the stream runs at the mic's rate (48000 Hz); the default voices are 40 kHz models, so "Use model sample rate" would not match the devices, and the launcher prints a `WARNING` if `sr_type` isn't `"sr_device"`. If the mic and CABLE Input run at different rates, the launcher stops with `ERROR: Sample rates differ: ...` ([fix in windows-audio.md](windows-audio.md#2-set-every-device-in-the-chain-to-48000-hz)).

## What each control does

- **"Pitch settings"** (-16 to +16, whole semitones): the pitch of the converted voice. The main control for a male-to-female change.
- **"Gender factor / voice thickness"** (-2 to +2, steps of 0.05): moves the resonances that make a voice sound bigger or smaller, without changing its pitch.
- **"Index Rate"** (0 to 1): how much of the voice's `.index` file is mixed in. Higher pulls the timbre closer to the target speaker.
- **"loudness factor"** (0 to 1): at 0 the converted voice follows your loudness moment to moment; at 1 it keeps the model's own loudness.
- **"pitch detection algorithm"**: how the engine reads your pitch. The presets use `rmvpe`. `fcpe` is the alternative the tuning loop tries when the game needs headroom; the first switch loads its model, so expect a short pause. `pm` runs on the CPU and the presets don't use it.
- **"Response threshold"** (-60 to 0 dB): the noise gate ([below](#response-threshold-noise-gate)).
- **"Sample length"** (0.02 to 1.5 s): how much audio is converted at a time. Your voice is delayed by at least this much, so it is the main delay control.
- **"Fade length"** (0.01 to 0.15 s): the overlap that blends each chunk into the next so the joins don't click. Start at 0.05; 0.08-0.1 can sound less robotic, at the cost of that much more delay.
- **"Extra inference time"** (0.05 to 5 s): earlier audio processed again with each chunk, as context. It adds work to every chunk, not delay.
- **"Input noise reduction"**, **"Output noise reduction"**: GPU noise filtering on every chunk. Input noise reduction also adds up to 40 ms of delay. Leave both off unless you need them.
- **"Input voice monitor"**, **"Output converted voice"**: send your raw mic or the converted voice to the cable.

## Pitch

```
semitones = 12 * log2(target F0 / your F0)
```

F0 is the base pitch of your speaking voice, in Hz. Round to a whole number, because the slider moves in steps of 1. For example, 110 Hz to 220 Hz is 12 * log2(2.0) = +12 (one octave); 120 Hz to 200 Hz is 12 * log2(1.667) = 8.8, so +9.

If you don't know your F0, tune by ear:

1. Start at +10 (the preset value) and try +8 to +14, one step at a time.
2. Go down if the voice sounds squeaky or cartoonish; go up if it still sounds like a low voice.
3. If the pitch is right but the voice still sounds heavy or male, try the formant before adding more pitch.

## Formant

- Start at 0, then try +0.5 to +1.5. Positive values sound smaller and brighter, negative values thicker. Go back down if the voice turns thin or unnatural.
- Set it before a match, not during one. With CUDA Graph on (the default), the first chunk after each new formant value takes longer, so dragging the slider can cause short glitches.
- The window never saves the formant. Put it in the preset ([Keep your changes](#keep-your-changes)).

## Index Rate

- Every preset starts at 0.5. The index pulls the timbre toward the target speaker, so less of your own voice leaks through; at 0 the first live test sounded gender-neutral.
- Raise it to 0.75 if the voice still sounds too much like you ([below](#it-sounds-gender-neutral-or-too-much-like-you)).
- The index search runs on the CPU (faiss) for every chunk and adds to "Inference time (ms)". Watch the [70% rule](#reading-inference-time-ms-and-algorithmic-delaysms); if it doesn't hold under game load, step down to 0.3, then 0.
- When the index is in use, the console prints `Index search enabled` after Start.

## Response threshold (noise gate)

- The start value, -60, turns the gate off. The gate only works above -60.
- The gate checks the level in 10 ms slices and silences every slice below the threshold, with no hold or release. At -45 it chopped soft consonants and word endings on the Maxwell in the first live test, which is why it starts off.
- Raise it only if noise between words (breathing, keys, fan) gets converted into strange sounds, and only a little: about -55. If words start cutting in and out, lower it again.

## Technique

How you speak matters as much as the sliders.

- **Use a lighter "mixed" voice:** your normal voice, a little lighter and brighter. Not falsetto (the thin, breathy head voice); a mixed voice converts far better.
- **Use forward resonance:** aim the sound at the front of your face (lips and teeth), as if speaking with a slight smile, rather than from your chest.
- **Stay steady:** keep the same distance from the boom mic and a steady volume. The loudness factor, and the gate if you turn it on, follow your input level.
- **Recheck the pitch if you change your voice:** if you speak higher than usual, you may need less pitch on the slider.

## Reading "Inference time (ms)" and "Algorithmic delays(ms)"

**"Inference time (ms):"** is how long the engine took for the last chunk (gate, resampling, pitch detection and model). It must stay below the Sample length, or the audio crackles. During fights, when the game loads the GPU most, keep it under about 70% of the Sample length:

| "Sample length" | 70% limit for "Inference time (ms)" | "Algorithmic delays(ms)" at Fade length 0.05, before output latency |
|---|---|---|
| 0.15 s | 105 ms | 210 ms |
| 0.20 s | 140 ms | 260 ms |
| 0.25 s (start value) | 175 ms | 310 ms |
| 0.30 s | 210 ms | 360 ms |

At 0.25 s, a reading of 120 ms (48%) is fine; 190 ms (76%) is over the limit and close to crackling, so treat it as a stutter and use [the tuning loop](#the-tuning-loop).

The window shows only the latest value. The console prints a line such as `Inference time: 0.12 seconds` for every chunk, so you can scroll back after a fight. For the first 3 chunks and every 100th after that, it also prints `Elapsed time: features=...s, index=...s, pitch=...s, model=...s`, which shows which part costs the most.

**"Algorithmic delays(ms):"** is the window's own estimate, set when you click Start: output device latency + Sample length + Fade length + 10 ms, plus up to 40 ms with "Input noise reduction". It leaves out the mic's input latency. `scripts\measure-delay.ps1` measures the real end-to-end delay ([how to run it](perf-testing.md#4-measure-the-delay-measure-delayps1)).

### What to expect from the ~300 ms delay target

The acceptance target is a stable end-to-end delay of about 300 ms or less ([perf-testing.md](perf-testing.md#targets)). The starting values will probably miss it: at a Sample length of 0.25 s the window's estimate is already 250 + 50 + 10 = 310 ms plus the output latency, before the input latency. Expect your first measurement to print `Above the ~300 ms target.`

Reaching the target needs a lower Sample length. Each 0.05 s you take off lowers the estimate by 50 ms, but also lowers the 70% limit by 35 ms. Use the delay steps in [the tuning loop](#the-tuning-loop) to find the lowest Sample length that doesn't crackle. If even that is above the target, write the measured delay in the [results](perf-testing.md#results). If you use push-to-talk, this delay is also how long to keep holding the key after you stop speaking ([overwatch.md](overwatch.md#open-mic-and-the-push-to-talk-tail)).

## The tuning loop

1. Change one thing at a time.
2. Re-test the same way each time: sound quality through "Listen to this device", delay with `measure-delay.ps1`, game performance with the runs in [perf-testing.md](perf-testing.md).
3. Write down what you changed and what happened, and save the winning values ([Keep your changes](#keep-your-changes)).

**The audio stutters or crackles:** raise "Sample length" (`block_time`) by 0.05 s at a time.

**The delay is too high and there is no stutter:**

1. Lower "Sample length" (`block_time`) by 0.05 s. The window stops conversion; click "Start audio conversion" again. "Algorithmic delays(ms)" should read about 50 ms less.
2. Listen for a few minutes for crackling and check "Inference time (ms)" against the 70% limit for the new Sample length. Then run `measure-delay.ps1` 3 times.
3. Still above the target and clean: repeat from step 1. Crackling, or inference time over the limit: go back up 0.05 s.
4. Then lower "Extra inference time" (`extra_time`) one small step at a time and try the lower Sample length again. This doesn't shorten the delay by itself; it cuts the work per chunk, so a shorter Sample length can keep up. Listen after each step: below 2.5 the voice can turn robotic.
5. Confirm the final value under game load ([perf-testing.md](perf-testing.md)), then save it in `config/audio.json`.

**Game performance misses the target** ([perf-testing.md](perf-testing.md#targets)). Try these in order, one at a time:

1. Lower "Index Rate": 0.5, then 0.3, then 0 (less CPU per chunk, more of your own timbre).
2. Switch "pitch detection algorithm" to `fcpe` (`"f0method": "fcpe"` in the preset).
3. Lower the frame-rate cap ([overwatch.md](overwatch.md#frame-rate-cap-required)).
4. A/B test Windows "Hardware-accelerated GPU scheduling" (HAGS), under Settings > System > Display > Graphics (depending on your Windows build, behind "Advanced graphics settings" or "Change default graphics settings"). Restart the PC after each change, run the same test with it on and off, and keep the better result.
5. Run `launch.bat -NoCudaGraph` if the CUDA Graph path misbehaves ([next section](#cuda-graph-and--nocudagraph)).

**Words cut in and out:**

1. Check that "Response threshold" is at -60 (gate off; see [above](#response-threshold-noise-gate)).
2. Check that "Inference time (ms)" stays well below the Sample length (the 70% rule).
3. Set the Maxwell's FILTER A.I. to low, or off, and test again.

### It sounds gender-neutral or too much like you

Try these in order, one at a time:

1. Raise "Index Rate" from 0.5 to 0.75 (costs CPU; watch "Inference time (ms)").
2. Raise "Gender factor / voice thickness" to +0.5, then up to +1.5.
3. Raise "Pitch settings" to +11 or +12.
4. Technique: a lighter voice with more pitch movement, as in [Technique](#technique).
5. Try another voice ([Switching voices](../README.md#switching-voices)); `vctk-all-f` blends every female VCTK speaker.

### It sounds robotic

1. Raise "Fade length" (`crossfade_length`) to 0.08, then 0.1. It stops conversion (restart) and adds its difference to the delay.
2. Keep "Extra inference time" at 2.5 or more; lower values give the model less context.
3. Don't overshoot the pitch: go back down a step or two if the voice turned squeaky.
4. Compare `rmvpe` and `fcpe` ("pitch detection algorithm") by ear.

## CUDA Graph and -NoCudaGraph

The engine's CUDA Graph mode records the GPU work for a chunk once and then replays it. It lowers the inference time and uses about 20-30% less GPU, and it turns on automatically when your GPU passes a quick check at startup.

- **Is it on?** When the window opens, the console prints `RVC_CUDA_GRAPH=1` (on) or `RVC_CUDA_GRAPH=0` (off). With it on, clicking Start prints `Warming up CUDA Graph`, then `CUDA Graph warm-up complete`.
- **Turn it off for one run:** `launch.bat -NoCudaGraph` (or `launch.bat -Preset vctk-p238 -NoCudaGraph`). This sets `RVC_CUDA_GRAPH=0` for that run only; nothing is saved, so the next plain `launch.bat` turns it back on.
- **When to try it:** the console shows an error after `Warming up CUDA Graph`, or conversion glitches or crashes in a way the other steps don't fix. Without CUDA Graph, expect a higher "Inference time (ms)", so check the 70% rule again.

## Keep your changes

Changes made in the window don't carry over. When you click "Start audio conversion", the window saves its values at that moment to `engine\configs\config.json`, minus the formant, but `launch.bat` rebuilds that file from `config/audio.json` and the preset at every start.

To make a change stick:

1. Write down the values you like and close the window.
2. Put them in the right file with a text editor:
   - Voice values (`pitch`, `formant`, `index_rate`, `rms_mix_rate`, `f0method`) go in the preset's `"settings"`, for example `config/presets/vctk-p231.json`.
   - Timing and gate values (`block_time`, `crossfade_length`, `extra_time`, `threhold`) go in `config/audio.json`, for every preset. To override one for a single voice, add the key to that preset's `"settings"`.
3. Write plain JSON: `10`, not `+10`, and `0.5` with a dot. `f0method` must be `"rmvpe"`, `"fcpe"` or `"pm"`, in quotes.
4. Run `launch.bat -Preset <id>` again. The console shows the preset it loaded, for example `Preset : vctk-p231 - VCTK p231 - English female (default)`. Invalid JSON, a missing voice file or an unknown `f0method` gives an `ERROR:` line and a pause.

To keep the original preset and save your values as a new one, see [Switching voices](../README.md#switching-voices).

Back to the [README](../README.md).
