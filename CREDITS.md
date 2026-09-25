# Credits

This repo holds only scripts, config and docs. The engine, the voices and the virtual cable below come from their official sources (downloaded by you or by the scripts) and are not redistributed here. For the voice terms in more detail, see [docs/voices-and-licenses.md](docs/voices-and-licenses.md).

## Software

| Component | Used for | License | Link |
|---|---|---|---|
| RVC-Project Retrieval-based-Voice-Conversion-WebUI, integrated package 2.3.260718 (`RVC20260718Nvidia.7z`) | Voice conversion engine and its realtime GUI | MIT, Copyright (c) 2023 liujing04, 源文雨, Ftps. The package also ships [`MIT协议暨相关引用库协议`](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/MIT%E5%8D%8F%E8%AE%AE%E6%9A%A8%E7%9B%B8%E5%85%B3%E5%BC%95%E7%94%A8%E5%BA%93%E5%8D%8F%E8%AE%AE), which lists the licenses of the libraries it bundles and says that whoever uses the software, or spreads audio made with it, is fully responsible for that use. | [GitHub](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI), [release 2.3.260718](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/releases/tag/2.3.260718) |
| FreeSimpleGUI 5.1.1 (bundled in the engine's `runtime`; the package metadata says 5.1.1, the module's own version string says 5.1.0) | The realtime GUI's window toolkit. The hotkey add-on patches `Window.read` in memory; no file is changed. | LGPL-3.0-or-later | [GitHub](https://github.com/spyoungtech/FreeSimpleGUI) |
| python-sounddevice 0.5.5 (bundled in the engine's `runtime`) | The realtime GUI's audio streams, and the device lists the launcher matches names against | MIT | [GitHub](https://github.com/spatialaudio/python-sounddevice) |
| VB-CABLE Virtual Audio Device (VB-Audio Software), `VBCABLE_Driver_Pack45.zip` | Virtual mic between the engine and the game | Donationware: free to download and use, no account. VB-Audio asks users who find it useful to pay what they want, and professional use needs a license. | [vb-audio.com/Cable](https://vb-audio.com/Cable/), [licensing](https://vb-audio.com/Services/licensing.htm) |
| Virtual Audio Cable Lite 4.71 (Eugene Muzychenko), optional fallback only | Virtual mic, if VB-CABLE crackles | Free; the Lite version may be used only in a private home environment not associated with income generation | [Download page](https://vac.muzychenko.net/en/download.htm) |
| FFmpeg (you install it, for example `winget install Gyan.FFmpeg`) | Performance testing only: `scripts\measure-delay.ps1` and the one-minute recording in [docs/perf-testing.md](docs/perf-testing.md) | LGPL 2.1 or later, or GPL when built with GPL parts. The gyan.dev full build reports GPL v3 or later; `ffmpeg -L` prints the license of your build. | [ffmpeg.org/legal.html](https://ffmpeg.org/legal.html), [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) |

## Voices

Attribution line (from `config/models.json`; `scripts\get-models.ps1` prints it after every run):

> Voices: Nekochu/RVC-VCTK_Voice-sample (Apache-2.0), trained on CSTR VCTK Corpus (CC BY 4.0), University of Edinburgh.

- **Voice models:** [Nekochu/RVC-VCTK_Voice-sample](https://huggingface.co/Nekochu/RVC-VCTK_Voice-sample) on Hugging Face, pinned to revision `005c2f948ee9dafd7e3aa7f261b4c3a24beebeef`. The model card license is [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). Speakers used by the presets: p231, p238, p249, p262, p280, p323 and p340 (English-speaking female VCTK speakers), plus `All_F`, a blend of them (preset `vctk-all-f`).
- **Training data:** CSTR VCTK Corpus, version 0.92, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Citation:

  Yamagishi, Junichi; Veaux, Christophe; MacDonald, Kirsten. (2019). CSTR VCTK Corpus: English Multi-speaker Corpus for CSTR Voice Cloning Toolkit (version 0.92), [sound]. University of Edinburgh. The Centre for Speech Technology Research (CSTR). https://doi.org/10.7488/ds/2645

- **Changes:** the model author trained RVC voice models on recordings from the corpus. This project downloads those models unchanged.

## Optional voices (only if you add them yourself)

The scripts never download these. If you add one, its terms require a credit:

| Voice | Credit the terms ask for | Terms |
|---|---|---|
| Tsukuyomi-chan official RVC model (つくよみちゃん公式RVCモデル) | `■声質変換：つくよみちゃん公式RVCモデル ■元の音声：<your source voice>`, or `■ボイスチェンジャー：つくよみちゃん公式RVCモデル` when it is obviously you speaking live | [Terms](https://tyc.rei-yumesaki.net/work/software/rvc/terms/) |
| Amitaro's RVC models (あみたろの声素材工房) | `RVCモデル：あみたろの声素材工房（https://amitaro.net/）` (English: "RVC Model: Amitaro's Voice Material Studio (https://amitaro.net/)") | [RVC page](https://amitaro.net/synth/rvc/), [terms (English)](https://amitaro.net/voice/terms/) |

## Sounds

The hotkey cue sounds, `C:\Windows\Media\Speech On.wav` and `C:\Windows\Media\Speech Off.wav`, are part of Windows (Microsoft). The add-on plays them from that folder; they are not copied into or shipped with this repo.
