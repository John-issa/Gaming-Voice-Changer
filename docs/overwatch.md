# Overwatch settings

Settings for Overwatch (formerly Overwatch 2) with the voice changer (plan Step 5). Do the
[Windows audio setup](windows-audio.md) first, so that CABLE Output is the default recording device.
Blizzard Support ([Voice Chat](https://us.support.blizzard.com/en/article/31694),
[troubleshooting](https://us.support.blizzard.com/en/article/26042)) confirms only some labels: push
to talk is the default, its key is in the Controls menu, Group/Team Voice Chat can be turned off.
The other labels come from player reports and may differ by game version (the game shows capitals).

| Setting | Where | Value |
|---|---|---|
| VOICE CHAT DEVICES | Options > Sound (Voice Chat) | DEFAULT DEVICES |
| VOICE CHAT MODE | Options > Sound (Voice Chat) | OPEN MIC |
| GROUP / TEAM / MATCH VOICE CHAT | Options > Sound (Voice Chat) | On for the channels you use |
| FRAME RATE | Options > Video | CUSTOM, with a cap ([below](#frame-rate-cap-required)) |
| NVIDIA REFLEX | Options > Video | ENABLED |

## Voice chat devices

With **DEFAULT DEVICES**, Overwatch records from the default recording device (CABLE Output) and
plays voice chat on the default playback device (`Speakers (Game-Audeze Maxwell)`).

The alternative, **COMMS DEVICES**, uses the Windows Default *Communication* Devices instead. They
must be CABLE Output on the Recording tab and the Maxwell on the Playback tab (voice chat probably
plays there); never CABLE Input, or teammates' voices go straight back into your mic. Set them as
in [windows-audio.md](windows-audio.md#4-set-the-default-devices).

Use the headset's USB connection: Blizzard says voice chat does not work correctly over Bluetooth.

## Open Mic (and the push-to-talk tail)

1. Set **VOICE CHAT MODE** to **OPEN MIC**. The game's default is push to talk.
2. After the next game restart, check that it is still OPEN MIC; players report it switching back.

The RVC noise gate ("Response threshold") is off by default (-60 in `config\audio.json`): it has no
hold time, so higher values chop words. With Open Mic, rely on the Maxwell's FILTER A.I. on low
([windows-audio.md](windows-audio.md#5-maxwell-headset-filter-ai-low-sidetone-off)) and on Overwatch's own
voice activation instead. Only if breathing or room noise between words turns into odd sounds, raise the
gate to about -55 ([tuning.md](tuning.md#response-threshold-noise-gate)).

The hotkey is not a mute: in `im` teammates hear your real voice. To go silent, use Overwatch's own
voice chat controls, for example turn TEAM VOICE CHAT off.

**If you use push to talk anyway:** the converted voice reaches the cable later than you speak and
Overwatch has no release delay, so releasing the key on your last word cuts it off. Keep holding it
after you stop speaking for at least the delay `scripts\measure-delay.ps1` reports
([perf-testing.md](perf-testing.md#4-measure-the-delay-measure-delayps1)): about 0.4 s at the
starting values ([why](tuning.md#what-to-expect-from-the-300-ms-delay-target)). The binding is in
**Options > Controls** (it may be called VOICE CHAT: PUSH TO TALK).

## Frame-rate cap (required)

The voice model shares the GPU and must convert each "Sample length" (0.25 s by default) before the
next is due. Uncapped, the game keeps the GPU busy, "Inference time (ms)" jumps and your voice
stutters. A cap leaves spare GPU time. Choose it once, before the [perf-testing.md](perf-testing.md) baseline:

1. With the voice changer off, set **FRAME RATE** to **CUSTOM** at its highest value (NVIDIA says up
   to 600 FPS). Play your Practice Range route once with a capture running and note the Avg FPS.
2. Set the cap clearly below that and above 120 FPS (the target is 1% lows of at least 120 FPS).
   Use the same cap for the baseline and the conversion runs.
3. With the voice changer on, check "Inference time (ms)" during fights against the 70% rule in
   [tuning.md](tuning.md#reading-inference-time-ms-and-algorithmic-delaysms).
4. If it misses, follow the "Game performance misses the target" steps in
   [the tuning loop](tuning.md#the-tuning-loop). If you lower the cap there, redo the baseline.

## NVIDIA Reflex

Set **NVIDIA REFLEX** to **ENABLED**. [NVIDIA says](https://www.nvidia.com/en-us/geforce/news/overwatch-2-out-now-geforce-rtx-reflex-high-fps/)
**ENABLED + BOOST** keeps GPU clocks high at the cost of more power. Reflex lowers the game's own
input latency; it does not replace the cap. Keep the same Reflex setting for all test runs.

## Check your voice in the game

1. Before starting the game, run `launch.bat`, click **Start audio conversion**, and hear exactly
   what Overwatch records with [Listen to this device](windows-audio.md#6-hear-yourself-while-tuning-listen-to-this-device).
2. For the other side, form a group with a friend and join Group Voice Chat (Social menu, P by
   default > Channels > headphone icon). Press the hotkey so they can compare your real voice.

## Check the hotkey while the game has focus

A focused game can keep a registered hotkey from firing, so test both display modes. What the hotkey
does and how to change it: [README](../README.md#the-hotkey).

1. Run `launch.bat`, click **Start audio conversion**, and keep "Output converted voice" selected.
2. In Overwatch, set **Options > Video > DISPLAY MODE** to fullscreen; go to the Practice Range.
3. Press Ctrl+Alt+V: the `Speech Off.wav` cue (a short chime) plays for the raw mic. Press it again: the `Speech On.wav` cue plays for the converted voice.
4. Alt+Tab out. The console shows `[hotkey] voice changer OFF (im: raw mic)` and
   `[hotkey] voice changer ON (vc)`, the radio button moved each time, and conversion kept running.
5. Repeat steps 3 and 4 in borderless windowed mode.

If nothing happens while Overwatch has focus, close the RVC window, change `"method"` in
`config\hotkey.json` from `"registerhotkey"` to `"poll"`, and run `launch.bat` again. The console
then says `[hotkey] ctrl+alt+v toggles the voice changer (polling every 30 ms)`. Test again.
Polling doesn't reserve the combo, so Overwatch sees the keys too: make sure the game doesn't use it.

## Public voice chat

The voice changer doesn't change the rules: Blizzard can [record and transcribe](https://overwatch.blizzard.com/en-us/news/23857517/defense-matrix-activated-fortifying-gameplay-integrity-and-positivity-in-overwatch-2/)
a reported player's voice chat for review, converted voice or not. The voices' own terms also apply
([voices-and-licenses.md](voices-and-licenses.md#rules-that-apply-to-every-voice)).

Back to the [README](../README.md).
