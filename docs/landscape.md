# Voice-changer landscape check

This is a dated log of what our setup has been compared against, so later checks only need to look for what is new or changed. Projects change quickly: a "no" here can flip when a project ships a release, fixes a bug or changes its license. That's why each row says what would change the verdict. Add a new `## Check YYYY-MM-DD` section at each re-check rather than editing old ones.

**Rules the stack must meet:** free or one-time purchase; no account, subscription or cloud; runs offline on Windows; no real-person voices. **Priority:** quality first, then latency.

## Current stack
- **Engine:** official RVC WebUI integrated package 2.3.260718 (2026-07-21, MIT), running `realtime_gui.py` with CUDA Graph and FP16, plus our add-on for hotkeys, presets, mute and save. As of 2026-09-27 the local realtime files are byte-identical to upstream main.
- **Voices:** `ex02` (default), a custom RVC v2 48 kHz model trained on ~4.5 h of Meta Expresso speaker ex02; since 2026-09-29 also `ears-p033` (female, low register) and `ears-p105` (male), each trained on ~1 h of one EARS speaker (TITAN-Medium 48k, 400 epochs, e200 picked). ex02 details: Base TITAN-Medium 48k, 200 epochs, rmvpe pitch, ContentVec embedder, HiFi-GAN-NSF vocoder, full faiss index (stored nprobe 4).
- **Audio chain:** headset mic -> RVC -> VB-CABLE -> Overwatch voice chat, on Windows 11 with an RTX 4080 SUPER, Ryzen 9 9950X and 64 GB RAM.
- **Settings:** block 0.75 s, fade 0.15, extra 4.0, WASAPI shared mode, as of this check. Since 2026-09-29 the default is block 0.25 (about 0.6 s estimated; the ~3 s figure here was the GUI's buffer-capacity formula, not a measurement). `ex02-reference` keeps 0.75.

## Check 2026-09-27

This check re-verified the 2026-09-24..26 comparisons and added new entries; rows marked "(prev.)" were already compared then. Sources were GitHub, Hugging Face, arXiv, AI Hub docs and vendor sites. Reddit was not checked. Latency figures are author claims or code-derived estimates unless marked measured.

| Candidate | Type | Latest seen | Verdict vs our stack | Re-check trigger |
|---|---|---|---|---|
| Official RVC WebUI realtime_gui (ours) | Engine | 2.3.260718 (2026-07-21; 7z re-upload 07-23; last commit 08-04) | Baseline; still the best-quality host | New tag/package on GitHub or HF lj1995 |
| Official RVC Realtime VST2/VST3 | Engine (plugin) | HF zip 2026-08-01; source 2026-08-03; not in our local install | Same sound, ~1.5-1.6 s est. at block 0.75. A/B bench only: bug #2859 (permanent backlog after GPU overload), context max 3 s, no hotkeys | #2859 fixed |
| Applio realtime (prev.) | Engine | 3.6.5 (2026-09-19); commits to 09-27; README says maintenance mode | Worse: no formant, no CUDA Graph, documented realtime bugs, repeats old audio when the GPU is late | 3.7 or realtime formant |
| vc-rs (shirohata) | Engine (Rust, ONNX/TensorRT) | v0.5.2 (2026-09-22) | No .index support, no formant; author measured ~0.47-0.58 s with underruns | Adds faiss .index support |
| rvc-realtime (Ramo-Inc) | Engine (Rust port) | v0.1.10-alpha (2026-09-21) | No .index, license undecided, alpha; 48k tested only with random weights | License + index + real 48k test |
| niel-blue RVC-Realtime-GUI | Engine (wrapper, MIT) | HF build 260914 (2026-09-14) | Same sound. Its ASIO-input route is truly decoupled (our mic would need FlexASIO); no output prefill. Useful A/B and reference code | Published latency numbers |
| VoxWeave | Engine (wrapper) | v0.2.0 (2026-08-13), push 09-21, AGPL-3.0 | Same algorithm; convenience only | Measured gain |
| Meloie (sstina) | Engine | Last commit 2026-06-15 | Abandoned; only its F0 quantile-mapping idea is worth borrowing | Activity with evidence |
| RvcStudio, RVC-Fabric, Phamu Ed., OpenVoiceChanger | Engine (wrappers) | Aug-Sep 2026 | Same engine, 0-25 stars | None expected |
| w-okada VCClient / deiteris / tg-develop (prev.) | Engine | 2.2.2-beta (~Aug 2025; only CLA-bot commits since, latest 2026-09-26) / b2332 (2024-12-07) / b2397 (2025-10-27) | Dormant | Any new release |
| Vonovox (prev.) | Engine (closed) | v1.6.9 (2025-09-07) | Closed source, Patreon extras | Open-sourced |
| Echo Live (Escalera Labs) | App (closed RVC) | Beta 2026-04-15, May 2026 update | Importing our own model needs the Pro plan; uses online account services | Free offline import |
| Beatrice v2 (prev.) | Engine + voices | VST 2.0.0-rc.3 (2025-08-24), trainer rc.0 (2025-08-31) | CPU ~50 ms but less realistic; JP voices | Trainer release, English voices |
| RVCv3 base | Model | Unreleased (README promise) | n/a | Release on GitHub/HF |
| Seed-VC + seed-vc-realtime fork (prev.) | Model + engine | Upstream archived 2025-11-21; fork active 2026, 1 star | Default model is zero-shot tiny at 22 kHz; no evidence against a trained RVC model | Fine-tuned 44.1k realtime evidence |
| StreamVoiceAnon / SVA+ (prev. tested) | Model | SVA+ arXiv 2603.06079 (2026-03-06) | Lost our ear test; SVA+ targets anonymization; no pitch control | Target-VC checkpoint + pitch |
| MeanVC 2 (prev.) | Model | arXiv 2606.09050 (Jun 2026) | 16 kHz | 24k+ variant |
| LLVC, StreamVC ports, Chatterbox VC (prev.) | Model | as of 2026-09-24 | 16 kHz or not better | Major new release |
| X-VC (SJTU) | Model | arXiv 2604.12456 v2 (2026-09-04), weights on HF | 16 kHz, zero-shot, speaker SIM ~0.62 | 24k+ or fine-tuning |
| Zero-VC (Amphion) | Model | arXiv 2606.20218 (2026-06-18) | Demo only, no code | Code/weights |
| Vevo2, Kanade, LinaCodec | Model | Vevo2 code 2026-03-25 (CC-BY-NC-ND); Kanade 2026-02; LinaCodec ~2026-01 (unverified) | Offline, not streamable | Streaming mode |
| SynthVC, RT-VC, TVTSyn, Conan, SDP-Codec, GenVC | Model (papers) | 2025-2026 | No usable weights, 16 kHz, or no realtime client | Weights + 24k+ |
| DDSP-SVC | Model | 5.0 (2025-02-08); 6.3 branch Jan 2025 | Stale, singing-focused | New release |
| SoulX-Singer-SVC, Phoenix TTS, OpenVoice V2, CosyVoice 3, IndexTTS-2.5 | Offline/TTS | 2024-2026 | Not realtime VC | n/a |
| TTS-as-training-data (Kokoro idea, MLX-RVC-Serena-E70) (prev.) | Data idea | Serena 2026-09-05 | Rejected: synthetic voice; Serena is Apple-only format | n/a |
| TITAN-Large | Base model | Never released (repo 2024-08-19) | Keep TITAN-Medium, which likely includes ex02's read speech (unverified) | A "large" folder appears |
| KLM9 / KLM-X-10 / KpopUniverse | Base model | KLM9 2026-03-08, X-10 2026-05-08 (32k only) | Singing-focused, 32k, unclear or NC licenses | 48k speech version |
| Ov2Super | Base model | 32k/40k only | No 48k | 48k release |
| Convbased-Studio pretrains | Base model | 2025-11-11 | No quality evidence; VCTK/Chinese data. The 48k variants confirmed are BigVGAN; sources disagree on a 48k HiFi-GAN variant (unverified) | Evidence + official-GUI-compatible 48k |
| Aurora v2, VocalCore, GuideVocalPretrain | Base model | Politrees mirror ~2026-09-22 | Undocumented origin and license | License + docs |
| Spin-v2 embedder | Embedder | Applio 3.6.5; dr87/spinv2_rvc 2025-12-05 | Sidegrade at best; needs an engine patch + full retrain; anecdotal evidence | 48k Spin-v2 HiFi-GAN base or blind A/B |
| RefineGAN vocoder | Vocoder | Applio 3.6.5 | 24k/32k only, Applio-only | 48k + official GUI support |
| MRF HiFi-GAN, BigVGAN, SiFiGAN, RingFormer | Vocoder | Forks only; codename-rvc-fork-4 returns 404 | No evidence; won't load in our engine | Official support |
| Multi-speaker training | Training | RVC git 2026-08-04; Applio 3.6.5 | Aimed at small datasets | n/a |
| More epochs (>200) | Training | n/a | Small gain at most; AI Hub warns more epochs can hurt robustness on mic input | Only if retraining anyway |
| SwiftF0 pitch | Pitch extractor | Added to Applio 2026-09-27 (swift-f0 0.3.0) | Paper: better than RMVPE on noisy speech, gap not significant overall; not in official engine | Official engine support |
| Antinode Shift (ex-Supertone) (prev.) | Commercial | v2.1; ownership moved in 2026 | Account required; the $149.99/voice perpetual licence is still account-tied | Works without sign-in |
| Vocoflex (prev.) | Commercial | 1.0.3, $199 | Government-ID check; singing-focused | ID check dropped |
| Voicemod (prev.) | Commercial | V3 (2026) | Login + always online; users report AI voices degraded Jul-Sep 2026 | Offline mode |
| Voice.ai (prev.) | Commercial | Pricing 2026-09-27 | Account + credit subscription | n/a |
| Paravo v3.0 | Commercial | 2026-06-30 | Google login (unverified for v3); JP anime-style voices | English adult voices, no login |
| Auto-Tune Metamorph v1.1 | Commercial plugin | 2026-08-03 | Singing DAW plugin; would run the same RVC models | n/a |
| SoundID VoiceAI, Voidol3, Altered, Dubbing AI | Commercial | 2024-2026 | Render-only, character voices, or subscription | n/a |
| Voice Changer AI Engine (OverStudio, Steam) | Commercial | "Coming soon" | Nothing verifiable | Release |
| Downloadable female RVC/Beatrice voices (prev.) | Voice models | HF uploads to 2026-09-27 | None both better and rights-clean in English | Rights-clean English adult female release |
| NVIDIA Broadcast | App | 2.2.1 | Has no voice conversion | n/a |
| FlexASIO / ASIO4ALL | Audio driver | FlexASIO 1.10b (2024-06-02) | No gain on its own; only useful as the input for the niel-blue route | n/a |

**Avoid:** look-alike "RVC-Desktop - Retrieval Voice Conversion 2026" repos (funnydaisy, Mikephyll6). They are README-only and link to external password-protected archives, a common malware-lure pattern.

## Improvements worth trying
- **Main win: decoupled audio I/O in the add-on.** Most of the ~3 s (roughly 60-65%) is PortAudio buffering, because the engine opens its stream with blocksize = the whole RVC block.
  - Wrap `sd.Stream` in `vcgui/hotkey_launcher.py` with no engine edits.
  - The real device stream uses a small buffer; a worker thread gathers block-sized chunks and calls the unchanged `audio_callback`.
  - Output goes through a pre-filled FIFO with a margin of about p99 inference time + 50 ms.
  - A bounded-age drop/reset is required, because the official VST's bug #2859 comes from lacking one.
  - Expected ~1.1-1.3 s at block 0.75 with identical sound (unverified).
  - Reference code: RVC `RVCRealtimeVST/src/WorkerClient.cpp` and niel-blue `tools/audio_fifo.py` (MIT).
  - If the audio glitches because of Python's GIL, move the worker to a subprocess.
- **Zero-code checks.**
  - WASAPI exclusive mode (`sg_wasapi_exclusive`, already covered in `docs/tuning.md`): est. 1.6-2.4 s.
  - To hear the decoupling gain before coding: niel-blue GUI with FlexASIO input, or the official VST in MicVST v1.1.1 (VST3, unsigned). Kushview Element 1.2.0 has no free Windows build, so use 1.1.1.
- **Re-test smaller blocks.** The old 0.25 s chop is not conclusive: commit 567c89b changed block, fade, extra and rms_mix at once, on the older VCTK voices.
  - Render block 0.25/0.35/0.5/0.75 with `tools/rt_render.py` + `artifact_scan.py`, holding fade 0.15 and rms_mix 0.75, then confirm by ear.
  - Keep fade at 0.15: in this engine it is the model's look-ahead (~110 ms). The actual crossfade is capped at 40 ms.
- **A/B extra 4.0 vs 2.5-2.7**, listening to the first words after 5-10 s of silence. RVC issue #1305 and the AI Hub guides report cut onsets above ~1.5-2.7 s. The HuBERT whole-window normalization is a plausible cause (untested).
- **GPU power (user action).** Set "Prefer maximum performance" for `engine\runtime\python.exe` in NVIDIA Control Panel. Optional: raise the GPU scheduling priority to HIGH via `D3DKMTSetProcessSchedulingPriorityClass` (unverified effect).
- **Minor:** A/B index nprobe 4 vs 8-16. Our index already uses 4, which mostly avoids issue #2864.
- **Optional, low confidence:**
  - F0 quantile mapping instead of a flat +12 semitones (idea from Meloie).
  - Spin-v2 retrain.
  - Going past 200 epochs, only if retraining anyway. Keep the logs until an epoch is picked, then delete them.

## Where to look next time
- RVC releases, commits and issues #2859/#2864: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/releases , /commits/main , /issues
- RVC packages and VST zip: https://huggingface.co/lj1995/VoiceConversionWebUI/tree/main
- Applio: https://github.com/IAHispano/Applio/releases
- New engines: https://github.com/shirohata/vc-rs/releases , https://github.com/Ramo-Inc/rvc-realtime , https://huggingface.co/niel-blue/RVC-Realtime-GUI
- New RVC repos: https://github.com/search?q=rvc+realtime&type=repositories&s=updated&o=desc
- Base models: https://huggingface.co/blaise-tk/TITAN , https://huggingface.co/Politrees/RVC_resources/tree/main/pretrained/v2/48k , https://huggingface.co/SeoulStreamingStation
- New HF uploads: https://huggingface.co/api/models?filter=rvc&sort=createdAt&direction=-1&limit=40 and https://huggingface.co/api/models?search=beatrice&sort=lastModified&direction=-1
- Community guides: https://docs.aihub.gg/ (realtime and training pages)
- Research: https://arxiv.org/search/?query=streaming+voice+conversion&searchtype=all&order=-announced_date_first (also try "real-time voice conversion")
- Commercial watch: https://antinodeaudio.com/shift , https://parakeet-inc.com/paravo , https://prj-beatrice.com/ , https://voicemod.canny.io , https://store.steampowered.com/app/3187240/
- Reddit (r/RVC, voice-changer threads): not checked on 2026-09-27; include next time.
