# Windows audio setup

One-time setup (plan Step 1) that you do yourself: the scripts never install drivers or change Windows sound settings. The RVC window plays your converted voice into VB-CABLE's **CABLE Input**, and games record from **CABLE Output** as if it were a mic (full signal chain in the [README](../README.md)).

| Device (as `launch.bat -ListDevices` prints it) | Sound dialog tab | Role |
|---|---|---|
| `Microphone (Chat-Audeze Maxwell)` | Recording | Your real mic. The RVC window records from it; games don't. |
| `Speakers (Game-Audeze Maxwell)` | Playback | Your headset. Default Device and Default Communication Device. |
| `Speakers (Chat-Audeze Maxwell)` | Playback | The headset's second (chat) channel. |
| `CABLE Input (VB-Audio Virtual Cable)` | Playback | The RVC window plays your converted voice here. **Never** a default device. |
| `CABLE In 16ch (VB-Audio Virtual Cable)` | Playback | An extra 16-channel endpoint. Leave it alone; the launcher's "CABLE Input" match doesn't pick it. |
| `CABLE Output (VB-Audio Virtual Cable)` | Recording | What games hear. The Default Device on the Recording tab. |

- Turn the Maxwell on and connect it first, or its devices won't show up. The Sound dialog shows each name on two lines, for example "Microphone" over "Chat-Audeze Maxwell".
- To open the classic Sound dialog, press Windows+R, type `mmsys.cpl` and press Enter. Its tabs are Playback, Recording, Sounds and Communications.

## 1. Install VB-CABLE

VB-CABLE is donationware from VB-Audio: free to download and use, with no account and no subscription. VB-Audio asks people who find it useful to pay what they want, and professional use needs a license.

1. Download `VBCABLE_Driver_Pack45.zip` (the Windows package, about 1.3 MB) from the official page, <https://vb-audio.com/Cable/>.
2. Extract the zip to a local folder. The setup doesn't work from inside the zip.
3. Right-click `VBCABLE_Setup_x64.exe` and choose **Run as administrator**. This is the only admin step of the normal setup.
4. Click **Install Driver** and wait for it to finish.
5. Open the Sound dialog: the Playback tab should now list CABLE Input and CABLE In 16ch, and the Recording tab CABLE Output. Restart the PC only if they don't appear.

To uninstall later, run the same setup as administrator (it offers to remove the driver), then restart.

### Right after installing: fix the default devices

The installer can make CABLE Input the default playback device (it did on the development PC). Then system sounds and the hotkey's cue sounds go into your mic, and you hear nothing. Fix it right away:

1. Press Windows+R, type `mmsys.cpl` and press Enter.
2. On the **Playback** tab, right-click `Speakers (Game-Audeze Maxwell)` and choose **Set as Default Device**.
3. Right-click it again and choose **Set as Default Communication Device**.
4. On the **Recording** tab, check that `CABLE Output` says "Default Device". If not, right-click it and choose **Set as Default Device**.

With another headset, use its playback device in steps 2 and 3. [Section 4](#4-set-the-default-devices) has the rules behind this.

## 2. Set every device in the chain to 48000 Hz

The RVC window opens the mic and CABLE Input as one stream, and in WASAPI shared mode it can't convert between two sample rates. If they differ, `launch.bat` stops with `ERROR: Sample rates differ: ...` instead of letting the window close on Start. 48000 Hz is also VB-CABLE's default internal rate, so nothing gets resampled.

Check these devices. The mic and both cable sides must match; on the development PC all of them were already at 48000 Hz, so you are usually only checking.

- Playback tab: `Speakers (Game-Audeze Maxwell)`, `Speakers (Chat-Audeze Maxwell)`, `CABLE Input`
- Recording tab: `Microphone (Chat-Audeze Maxwell)`, `CABLE Output`

1. In the Sound dialog, select the device and click **Properties**.
2. On the **Advanced** tab, under **Default Format**, pick an entry with 48000 Hz if it doesn't have one, for example "2 channel, 24 bit, 48000 Hz (Studio Quality)". Only the 48000 Hz part matters.
3. While you are there, untick **Enable audio enhancements** if it is shown ([section 3](#3-turn-off-enhancements-and-voice-clarity-set-communications-to-do-nothing)).
4. Click **OK**. If the RVC window was open, close it and run `launch.bat` again.

Only the WASAPI rate, the **Default Format** set here, counts. If a tool shows the same devices at 44100 Hz under MME or DirectSound, ignore it: the launcher uses only Windows WASAPI.

## 3. Turn off enhancements and Voice clarity; set Communications to "Do nothing"

Windows' own processing (noise suppression, echo cancellation, and Voice clarity, which applies to apps that use Windows' communications processing, including some games) changes the sound on the way. The model should hear your plain voice, and games should get the converted voice unchanged.

For `Microphone (Chat-Audeze Maxwell)` and `CABLE Output`:

1. Open **Start > Settings > System > Sound**.
2. Under **Input**, click the **>** arrow at the right of the device to open its properties page. Don't click the row itself: that makes the device the default input.
3. Set **Audio enhancements** to **Off**. This also turns off Voice clarity where your driver lists it there. Some devices don't show this setting; that's fine.
4. In the Sound dialog, open the same device's **Properties**. If it has an **Enhancements** tab, tick **Disable all enhancements** (or **Disable all sound effects**); otherwise untick **Enable audio enhancements** on the **Advanced** tab.

If `CABLE Input` shows **Audio enhancements**, set it to **Off** too. Open it with the **>** arrow under **Output**, never by clicking its row, which would make it the default playback device.

Then open the Sound dialog's **Communications** tab (one setting for the whole dialog), select **Do nothing** under "When Windows detects communications activity:" and click **OK**. Otherwise Windows may turn your game down whenever voice chat is active.

## 4. Set the default devices

| Tab | Device | Default Device | Default Communication Device |
|---|---|---|---|
| Playback | `Speakers (Game-Audeze Maxwell)` | Yes | Yes |
| Playback | `CABLE Input` | **Never** | **Never** |
| Recording | `CABLE Output` | Yes | Optional: needed only for Overwatch's Comms option ([overwatch.md](overwatch.md#voice-chat-devices)) |

The steps in [Right after installing](#right-after-installing-fix-the-default-devices) set this up. For the optional one, right-click **CABLE Output** on the **Recording** tab and choose **Set as Default Communication Device**. Re-check this table after installing any audio driver.

- **Why CABLE Input must never be a default:** everything that plays to the default device (game audio, music, browser, the cue sounds) would go into the cable, which is now your mic. Teammates would hear all of it and you would hear nothing. As the Default Communication Device it does the same with voice chat: other people's voices go back into your mic.
- **Other apps:** every app whose mic is the Windows default (Discord, browser calls, other games) now records from CABLE Output, which is silent while the voice changer isn't running. See [Back to your real mic](#back-to-your-real-mic).
- **The launcher ignores these defaults.** It picks its mic and cable by name from `config\audio.json` (`input_device_match`: "Audeze Maxwell" + "Chat"; `output_device_match`: "CABLE Input") and stops with an error if it can't find exactly one match ([Troubleshooting](#troubleshooting)).

## 5. Maxwell headset: FILTER A.I. low, sidetone off

Set these on the headset itself (from Audeze's Maxwell user guide; labels may differ with other models or firmware):

- **FILTER A.I. on low:** single-tap the A.I. noise suppression button to cycle through the modes. The headset announces "Noise suppression off", "low" or "high". Stop at low: some room-noise removal without the stronger processing of high.
- **Sidetone off:** double-click the game/chat wheel; the headset announces "Sidetone on" or "Sidetone off". Sidetone plays your raw voice into your ears, which gets in the way of hearing the converted one.

## 6. Hear yourself while tuning ("Listen to this device")

This plays exactly what games receive from CABLE Output into your headset.

1. In the Sound dialog, open the **Recording** tab, select **CABLE Output** and click **Properties**.
2. On the **Listen** tab, tick **Listen to this device**.
3. Under **Playback through this device:**, choose `Speakers (Game-Audeze Maxwell)` by name. Never choose CABLE Input, and don't choose **Default Playback Device** either: whenever CABLE Input is the default playback device, CABLE Output loops back into CABLE Input (feedback into your mic).
4. Click **Apply**.

You hear your converted voice slightly late; that is the voice changer's delay ([tuning.md](tuning.md#what-to-expect-from-the-300-ms-delay-target)). Untick **Listen to this device** before a match.

## 7. Check that the engine sees the devices

From the repo folder, run `launch.bat -ListDevices`. Under `== Windows WASAPI`, the `inputs:` list must contain `Microphone (Chat-Audeze Maxwell)` and the `outputs:` list `CABLE Input (VB-Audio Virtual Cable)`. Other host APIs appear too; under `== MME` the mic's name is cut short (`Microphone (Chat-Audeze Maxwell`), which doesn't matter.

A normal `launch.bat` then prints the devices it picked (for an `ERROR:` instead, see [Troubleshooting](#troubleshooting)):

```text
Input  : Microphone (Chat-Audeze Maxwell)
Output : CABLE Input (VB-Audio Virtual Cable)  (Windows WASAPI)
```

## Back to your real mic

- **Voice changer running:** press the hotkey (Ctrl+Alt+V by default) to switch to "Input voice monitor" (`im`). Games hear your raw voice, still through the engine and the cable. See [The hotkey](../README.md#the-hotkey).
- **Voice changer closed or crashed:** the cable is silent, so point Windows back at the real mic:
  1. On the Sound dialog's **Recording** tab, right-click `Microphone (Chat-Audeze Maxwell)` and choose **Set as Default Device**. (Or in **Settings > System > Sound**, under **Input**, click the mic's row, which makes it the default.)
  2. If Overwatch uses COMMS DEVICES, also right-click the mic and choose **Set as Default Communication Device**.
- **Before your next voice changer session:** on the **Recording** tab, right-click **CABLE Output** and choose **Set as Default Device**, and also **Set as Default Communication Device** if you changed that in step 2.

## Troubleshooting

| Symptom or message | Fix |
|---|---|
| You hear nothing, or teammates hear your PC sounds or the cue sounds | CABLE Input is the default playback device. Redo [Right after installing](#right-after-installing-fix-the-default-devices). |
| `No Windows WASAPI input device matches ['Audeze Maxwell', 'Chat']` | Connect and turn on the headset. If the mic is disabled, right-click in the Recording tab, choose **Show Disabled Devices**, then enable it. |
| `No Windows WASAPI output device matches ['CABLE Input']`, or no CABLE devices in the Sound dialog | VB-CABLE isn't installed ([section 1](#1-install-vb-cable)), or its devices haven't appeared yet: restart the PC. |
| `Sample rates differ: ...` | The message names both devices and their rates. Set the mic and both cable sides to 48000 Hz ([section 2](#2-set-every-device-in-the-chain-to-48000-hz)), then run `launch.bat` again. |
| `2 Windows WASAPI input devices match ...` (any count, input or output) | Add a more specific substring to `input_device_match` (or `output_device_match`) in `config\audio.json`. |
| Feedback while "Listen to this device" is on | "Playback through this device" must name the headset, not "Default Playback Device" or CABLE Input ([section 6](#6-hear-yourself-while-tuning-listen-to-this-device)). |
| Nobody hears you | Check that conversion is started and CABLE Output is the default recording device ([section 4](#4-set-the-default-devices)). |
| Crackles | See [Fallback: VAC Lite](#fallback-vac-lite-if-vb-cable-crackles). |

For a different mic, put substrings of its name, as `launch.bat -ListDevices` prints it under `== Windows WASAPI`, in `input_device_match` in `config\audio.json`. Every substring must match (case doesn't matter), and exactly one device may match.

## Fallback: VAC Lite if VB-CABLE crackles

First rule out the voice changer: the first fix for crackles is a larger "Sample length" ([tuning.md](tuning.md#the-tuning-loop)). If it still crackles with the hotkey on "Input voice monitor" (raw mic, no conversion), suspect the cable.

The fallback is Virtual Audio Cable Lite 4.71 by Eugene Muzychenko:

- **Download:** <https://vac.muzychenko.net/en/download.htm>, "Download VAC 4.71 Lite (ZIP archive)". Free, no account.
- **License:** the Lite version may only be used in a private home environment not associated with income generation. If you earn money from streaming, it doesn't fit.
- **Limits:** one cable, at most 48000 Hz, 16 bit, 2 channels. Each side takes one stream at a time, so if an app can't open the cable, close the other app using it (for example, turn off "Listen to this device").
- **Install:** it is a driver too, so its installer needs administrator rights, like VB-CABLE's.

After installing it, redo [Right after installing](#right-after-installing-fix-the-default-devices) and sections 2 to 6 with its devices in place of CABLE Input and CABLE Output. Then run `launch.bat -ListDevices` and put a substring of its playback device's name in `output_device_match` in `config\audio.json`. For `scripts\measure-delay.ps1`, pass its recording side with `-Cable`.

## Why not other voice changers' devices

Commercial voice-changer apps install their own virtual devices (e.g. Voice.ai, EaseUS, Voicemod). Don't use them in this chain:

- Each driver belongs to another app's installer and updater. An update or uninstall of that app could change or remove the device and silently break the voice changer.
- They come with commercial apps (Voicemod and Voice.ai sell subscription tiers). This project stays free and account-free.

If you have any, you don't need to uninstall them; just make sure none is a default device and quit their background apps before measuring performance ([perf-testing.md](perf-testing.md#1-prepare)).

## Sources

- VB-CABLE page and reference manual: <https://vb-audio.com/Cable/>
- VB-Audio licensing (donationware): <https://vb-audio.com/Services/licensing.htm>
- VAC Lite download and license: <https://vac.muzychenko.net/en/download.htm>
- Microsoft, fix sound problems (Default Format): <https://support.microsoft.com/en-us/windows/fix-sound-or-audio-problems-in-windows-73025246-b61c-40fb-671a-2535c7cd56c8>
- Microsoft, disable audio enhancements: <https://support.microsoft.com/en-us/topic/disable-audio-enhancements-0ec686c4-8d79-4588-b7e7-9287dd296f72>
- Microsoft, set up and test microphones (the ">" arrow to a device's properties): <https://support.microsoft.com/en-us/windows/how-to-set-up-and-test-microphones-in-windows-ba9a4aab-35d1-12ee-5835-cccac7ee87a4>
- Audeze Maxwell user guide: <https://www.audeze.com/pages/maxwell-user-guide>

Back to the [README](../README.md).
