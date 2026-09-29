# Credits

This repo holds only scripts, config and docs. The engine, the voices and the virtual cable below come from their official sources (downloaded by you or by the scripts) and are not redistributed here. The custom voices (ex02 from the Expresso dataset, ears-p033 and ears-p105 from the EARS dataset) are trained on your PC and are not redistributed either. For the voice terms in more detail, see [docs/voices-and-licenses.md](docs/voices-and-licenses.md).

## Software

| Component | Used for | License | Link |
|---|---|---|---|
| RVC-Project Retrieval-based-Voice-Conversion-WebUI, integrated package 2.3.260718 (`RVC20260718Nvidia.7z`) | Voice conversion engine, its realtime GUI, and the WebUI that trained the custom voices | MIT, Copyright (c) 2023 liujing04, 源文雨, Ftps. The package also ships [`MIT协议暨相关引用库协议`](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/MIT%E5%8D%8F%E8%AE%AE%E6%9A%A8%E7%9B%B8%E5%85%B3%E5%BC%95%E7%94%A8%E5%BA%93%E5%8D%8F%E8%AE%AE), which lists the licenses of the libraries it bundles and says that whoever uses the software, or spreads audio made with it, is fully responsible for that use. | [GitHub](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI), [release 2.3.260718](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/releases/tag/2.3.260718) |
| FreeSimpleGUI 5.1.1 (bundled in the engine's `runtime`; the package metadata says 5.1.1, the module's own version string says 5.1.0) | The realtime GUI's window toolkit. The add-on patches `Window.__init__` (to add the Voice / Save settings / Mute cable row), `Window.read` and `Text.update` (so audio-thread updates run on the GUI thread) in memory; no file is changed. | LGPL-3.0-or-later | [GitHub](https://github.com/spyoungtech/FreeSimpleGUI) |
| python-sounddevice 0.5.5 (bundled in the engine's `runtime`) | The realtime GUI's audio streams, the add-on's cable mute, and the device lists the launcher matches names against | MIT | [GitHub](https://github.com/spatialaudio/python-sounddevice) |
| VB-CABLE Virtual Audio Device (VB-Audio Software), `VBCABLE_Driver_Pack45.zip` | Virtual mic between the engine and the game | Donationware: free to download and use, no account. VB-Audio asks users who find it useful to pay what they want, and professional use needs a license. | [vb-audio.com/Cable](https://vb-audio.com/Cable/), [licensing](https://vb-audio.com/Services/licensing.htm) |
| Virtual Audio Cable Lite 4.71 (Eugene Muzychenko), optional fallback only | Virtual mic, if VB-CABLE crackles | Free; the Lite version may be used only in a private home environment not associated with income generation | [Download page](https://vac.muzychenko.net/en/download.htm) |
| FFmpeg (you install it, for example `winget install Gyan.FFmpeg`) | Testing only: `scripts\measure-delay.ps1`, the one-minute recording in [docs/perf-testing.md](docs/perf-testing.md), and `tools\artifact_scan.py` | LGPL 2.1 or later, or GPL when built with GPL parts. The gyan.dev full build reports GPL v3 or later; `ffmpeg -L` prints the license of your build. | [ffmpeg.org/legal.html](https://ffmpeg.org/legal.html), [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) |

## Voices

### VCTK voices

Attribution line (from `config/models.json`; `scripts\get-models.ps1` prints it after every run):

> Voices: Nekochu/RVC-VCTK_Voice-sample (Apache-2.0), trained on CSTR VCTK Corpus (CC BY 4.0), University of Edinburgh.

- **Voice models:** [Nekochu/RVC-VCTK_Voice-sample](https://huggingface.co/Nekochu/RVC-VCTK_Voice-sample) on Hugging Face, pinned to revision `005c2f948ee9dafd7e3aa7f261b4c3a24beebeef`. The model card license is [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). Speakers used by the presets: p231, p238, p249, p262, p280, p323 and p340 (English-speaking female VCTK speakers), plus `All_F`, a blend of them (preset `vctk-all-f`). The presets use the builds trained with `rmvpe` pitch extraction (each speaker's `rmvpe/` subfolder).
- **Training data:** CSTR VCTK Corpus, version 0.92, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Citation:

  Yamagishi, Junichi; Veaux, Christophe; MacDonald, Kirsten. (2019). CSTR VCTK Corpus: English Multi-speaker Corpus for CSTR Voice Cloning Toolkit (version 0.92), [sound]. University of Edinburgh. The Centre for Speech Technology Research (CSTR). https://doi.org/10.7488/ds/2645

- **Changes:** the model author trained RVC voice models on recordings from the corpus. This project downloads those models unchanged.

### Custom voice ex02

Attribution line (this project's wording; personal, non-commercial use only):

> Voice: ex02, trained on the Expresso dataset (Meta AI, CC BY-NC 4.0) from the TITAN-Medium pretrain by blaise-tk (Apache-2.0).

- **Training data:** the Expresso dataset (Meta AI), licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). [Project page](https://speechbot.github.io/expresso/), [dataset](https://github.com/facebookresearch/textlesslib/tree/main/examples/expresso/dataset). Citation:

  Tu Anh Nguyen, Wei-Ning Hsu, Antony D'Avirro, Bowen Shi, et al. (2023). EXPRESSO: A Benchmark and Analysis of Discrete Expressive Speech Resynthesis. Interspeech 2023. arXiv:2308.05725. Meta AI.

- **Pretrained base model:** TITAN-Medium 48k by blaise-tk, [huggingface.co/blaise-tk/TITAN](https://huggingface.co/blaise-tk/TITAN), licensed under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). It is fine-tuned from the official RVC v2 pretrain on Expresso.
- **Changes:** speaker ex02's speech was selected, cut and levelled for training (`tools\expresso_prep.py`) and used to train the ex02 voice model, which is not redistributed. How: [docs/custom-voice.md](docs/custom-voice.md#how-it-was-made).

### Custom voices ears-p033 and ears-p105

Attribution line (this project's wording; personal, non-commercial use only):

> Voices: ears-p033 and ears-p105, trained on the EARS dataset (Richter et al., Interspeech 2024; CC BY-NC 4.0) from the TITAN-Medium pretrain by blaise-tk (Apache-2.0).

- **Training data:** the EARS dataset (anechoic 48 kHz speech), speakers p033 and p105, released under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) with attribution to the original authors required. [Project page](https://sp-uhh.github.io/ears_dataset/), [dataset](https://github.com/facebookresearch/ears_dataset). Citation:

  Julius Richter, Yi-Chiao Wu, Steven Krenn, Simon Welker, Bunlong Lay, Shinji Watanabe, Alexander Richard, Timo Gerkmann. (2024). EARS: An Anechoic Fullband Speech Dataset Benchmarked for Speech Enhancement and Dereverberation. Interspeech 2024.

- **Pretrained base model:** TITAN-Medium 48k by blaise-tk (as for ex02 above), [huggingface.co/blaise-tk/TITAN](https://huggingface.co/blaise-tk/TITAN), [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
- **Changes:** each speaker's recordings were selected and levelled for training (`tools\ears_prep.py`) and used to train one voice model per speaker, which is not redistributed. How: [docs/custom-voice.md](docs/custom-voice.md#the-ears-voices-ears-p033-and-ears-p105).

## Optional voices (only if you add them yourself)

The scripts never download these. If you add one, its terms require a credit:

| Voice | Credit the terms ask for | Terms |
|---|---|---|
| Tsukuyomi-chan official RVC model (つくよみちゃん公式RVCモデル) | `■声質変換：つくよみちゃん公式RVCモデル ■元の音声：<your source voice>`, or `■ボイスチェンジャー：つくよみちゃん公式RVCモデル` when it is obviously you speaking live | [Terms](https://tyc.rei-yumesaki.net/work/software/rvc/terms/) |
| Amitaro's RVC models (あみたろの声素材工房) | `RVCモデル：あみたろの声素材工房（https://amitaro.net/）` (English: "RVC Model: Amitaro's Voice Material Studio (https://amitaro.net/)") | [RVC page](https://amitaro.net/synth/rvc/), [terms (English)](https://amitaro.net/voice/terms/) |

## Sounds

The cue sounds are part of Windows (Microsoft), in `C:\Windows\Media`: `Speech On.wav` and `Speech Off.wav` for the vc/im hotkey, and `Speech Sleep.wav` and `Windows Notify System Generic.wav` for mute and unmute. The add-on plays them from that folder; they are not copied into or shipped with this repo.
