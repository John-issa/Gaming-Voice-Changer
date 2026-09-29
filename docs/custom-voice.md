# The custom voices (ex02, ears-p033, ears-p105)

Three voices were trained in this repo, so they can't be downloaded: `ex02`, the default preset (`launch.bat` with no `-Preset` starts it), and the two EARS voices `ears-p033` and `ears-p105` ([below](#the-ears-voices-ears-p033-and-ears-p105)). This page covers what they are, how to keep them safe, how they were made and how to build them again. Their license terms are in [voices-and-licenses.md](voices-and-licenses.md#license-chain-of-the-default-voices).

## What it is

- An RVC v2 voice model (48 kHz, with pitch guidance) trained on speaker ex02, a female voice actor from Meta AI's Expresso dataset. Her own voice sits around 253 Hz.
- Preset `config\presets\ex02.json`, label "Expresso ex02 - custom voice (e200, full index)": Pitch 12, Formant 0.0, Index Rate 0.5, loudness factor (`rms_mix_rate`) 0.75, pitch algorithm `rmvpe`. What these do: [tuning.md](tuning.md).
- It was trained in the bundled engine, so training and live inference handle pitch the same way (the VCTK voices come from an older RVC).
- Personal, non-commercial use only, because the Expresso data is CC BY-NC 4.0.

Its files, in `models\ex02\`:

| File | What | Size |
|---|---|---|
| `ex02t48_e200_s133600.pth` | The model, epoch 200 | 57.6 MB |
| `added_IVF13764_Flat_nprobe_4_ex02t48full_v2.index` | The full retrieval index | 2.32 GB |

The full index makes the engine hold about 4.5 GB more RAM and adds about 11 ms per block (a CPU faiss search) compared with the WebUI's usual small index.

If the files are missing, `launch.bat` stops with:

```
ERROR: The voice files for preset 'ex02' are missing (...).
  This voice can't be downloaded: restore models\ex02 from your backup, or rebuild it (docs\custom-voice.md).
  Or use a downloadable voice: launch.bat -Preset vctk-p231
```

Picking `ex02` in the window's Voice list shows "Can't load ex02" and beeps; nothing changes.

## Back it up

`models\ex02\` (2.38 GB), `models\ears-p033\` (0.48 GB) and `models\ears-p105\` (0.44 GB) exist only on this PC: `models\` is git-ignored and `get-models.ps1` can't fetch them. A rebuild takes a large download and hours of GPU time, so keep a copy on another drive. From the repo folder (replace `E:\Backup` with your backup folder):

```
robocopy models\ex02 E:\Backup\ex02
robocopy models\ears-p033 E:\Backup\ears-p033
robocopy models\ears-p105 E:\Backup\ears-p105
```

To restore, copy them back under the same file names, for example:

```
robocopy E:\Backup\ex02 models\ex02
```

The presets (`config\presets\ex02.json`, `ears-p033.json`, `ears-p105.json`) are in the repo, not in those folders. Values you keep with "Save settings" go there.

## How it was made

- **Engine:** the bundled RVC WebUI (package 2.3.260718), experiment `ex02t48`: RVC v2, 48 kHz, pitch guidance.
- **Base model:** TITAN-Medium 48k ([blaise-tk/TITAN](https://huggingface.co/blaise-tk/TITAN), Apache-2.0), itself fine-tuned from the official RVC v2 48k pretrain on about 11 hours of Expresso speech.
- **Training:** batch size 8, 200 epochs = 133,600 steps (668 per epoch), about 157 s per epoch on the RTX 4080 SUPER (about 9 hours). Epochs 30, 60, 100, 150 and 200 were auditioned by ear; e200 won.
- **Index:** the WebUI's own index step shrinks more than 200k feature vectors to 10,000 k-means centres (IVF256, 32 MB). ex02 ships a full index instead: all 740,100 vectors, IVF13764, nprobe 4, built with `tools\build_full_index.py`. It was picked by ear over the small one.
- **Data:** [Expresso](https://speechbot.github.io/expresso/) (Meta AI, 2023), speaker ex02, built by `tools\expresso_prep.py`:
  - Her own channel of the improvised dialogues, cut to her speech with the dataset's official VAD segments. The actors sat in separate booths; a check found no crosstalk.
  - Her read speech in the "default" style.
  - Minutes per style (clips include short pauses): default 41.6, awe 26.6, sarcastic 26.5, happy 25.6, fast 25.2, sympathetic 24.7, projected 24.2, calm 21.6, read default 29.0, laughing 20.4, nonverbal 4.5. Total 269.8 minutes in 2,189 clips (247.9 minutes after the WebUI's silence slicer).
  - Laughing and nonverbal are capped at 12% of the set; all of them fit (9.2%).
  - The official test split is held out.
  - Each source channel is levelled to -23 dBFS speech RMS, with peaks at most -1 dBFS. No denoising.
  - Left out: every other style, for example whisper, character voices, angry, fearful, disgusted, sad, sleepy, bored, desire, confused, enunciated and narration.

## The EARS voices (ears-p033 and ears-p105)

These two voices were trained the same way as `ex02`, each on a single speaker of the [EARS dataset](https://sp-uhh.github.io/ears_dataset/) (Richter et al., Interspeech 2024: anechoic 48 kHz recordings, about an hour per speaker). Personal, non-commercial use only, because EARS is CC BY-NC 4.0.

| Preset | Speaker | Pitch | Files in `models\<preset>\` | Size |
|---|---|---|---|---|
| `ears-p033` ("EARS p033 - custom female voice (low register)") | p033, female, her voice around 128 Hz | 7 | `ears-p033_e200_s27000.pth`, `added_IVF3463_Flat_nprobe_4_ears-p033full_v2.index` | 0.48 GB |
| `ears-p105` ("EARS p105 - custom male voice") | p105, male, around 86 Hz, close to the owner's own voice | 0 | `ears-p105_e200_s25400.pth`, `added_IVF3085_Flat_nprobe_4_ears-p105full_v2.index` | 0.44 GB |

Both presets use Formant 0.0, Index Rate 0.5, loudness factor 0.75 and `rmvpe`. Each index takes about 0.8 GB of RAM while that voice runs (about twice the file, as with `ex02`).

How they were made:

- **Data:** the speaker's zip from the [EARS release](https://github.com/facebookresearch/ears_dataset/releases/tag/dataset) (`p033.zip` 719 MB, `p105.zip` 690 MB), turned into a training folder by `tools\ears_prep.py` (`engine\runtime\python.exe -I tools\ears_prep.py p033 p105`). It keeps the freeform monologues, the emotions (freeform and read), the read styles (regular, slow, fast, loud, high and low pitch), interjections, laughter, cheering, yelling and the sung line, and leaves out whisper, the vegetative sounds, screaming and crying. Non-verbal material (the non-verbal sounds, interjections and the sung line) is capped at 12% of the set (both came to about 4%). EARS speech is recorded quietly (often -35 to -45 dBFS), near or under the WebUI slicer's -42 dBFS silence threshold, so each file is levelled to -23 dBFS speech RMS with peaks at most -1 dBFS. Result: 142 files per speaker, 57.2 minutes for p033 and 54.7 for p105 (1,085 and 1,025 clips after the WebUI's slicer).
- **Training:** the bundled WebUI's trainer with the same settings as `ex02` (48k, v2, pitch guidance, `rmvpe`, batch size 8, TITAN-Medium 48k pretrain), but 400 epochs with a save every 25 epochs, since each speaker has only about an hour. About 32 s per epoch (p033) and 30 s (p105) on the RTX 4080 SUPER, about 3.5 and 3.3 hours.
- **Pick:** epochs 100, 200, 300 and 400 of each voice were rendered through the realtime path (`tools\rt_render.py`) and compared; e200 was picked for both.
- **Index:** `tools\build_full_index.py ears-p033` (and `ears-p105`). Below 200k vectors the WebUI's own index already holds every vector (135,081 and 120,348 here), so the full index differs only in storing nprobe 4: each search looks in 4 clusters instead of 1, so it always finds its 8 neighbours. With nprobe 1 a search in a small cluster comes back short, and the engine then skips the index for that whole block.

To rebuild one, follow [Rebuild it](#rebuild-it) with these changes: download `pNNN.zip` into `downloads\ears\` instead of Expresso, build the folder with `tools\ears_prep.py pNNN` (it writes `downloads\ears\train-pNNN\`), name the experiment `ears-pNNN`, train 400 epochs with save frequency 25, and copy the e200 model and the full index into `models\ears-pNNN\`.

## Rebuild it

These steps rebuild `ex02`; for the EARS voices, apply the changes listed at the end of [The EARS voices](#the-ears-voices-ears-p033-and-ears-p105).

You need the installed engine (`scripts\install-engine.ps1`), about 50 GB of free disk space during the build and about 10 hours of GPU time. The GPU is busy the whole time, so no gaming. Run the commands in PowerShell from the repo folder.

1. Download Expresso (38,441,031,680 bytes). If it stops, run the `curl.exe` line again; it resumes.

   ```
   mkdir downloads\expresso
   curl.exe -L -C - -o downloads\expresso\expresso.tar https://dl.fbaipublicfiles.com/textless_nlp/expresso/data/expresso.tar
   certutil -hashfile downloads\expresso\expresso.tar MD5
   ```

   The MD5 must be `6bf580a4cd4392ae2473626147b5307c`.

2. Build the training folder:

   ```
   engine\runtime\python.exe -I tools\expresso_prep.py
   ```

   It extracts what it needs into `downloads\expresso\src` and writes `downloads\expresso\train-ex02\` (2,189 WAVs, 48 kHz mono 24-bit), plus `train-ex02.csv` (where each clip came from), `train-ex02.json` (minutes by style) and `spotcheck-ex02.wav` / `.txt` (a short listen).

3. Download the TITAN-Medium 48k pretrain into `downloads\titan\` and check both hashes:

   ```
   mkdir downloads\titan
   curl.exe -L -o downloads\titan\G-f048k-TITAN-Medium.pth https://huggingface.co/blaise-tk/TITAN/resolve/main/models/medium/48k/pretrained/G-f048k-TITAN-Medium.pth
   curl.exe -L -o downloads\titan\D-f048k-TITAN-Medium.pth https://huggingface.co/blaise-tk/TITAN/resolve/main/models/medium/48k/pretrained/D-f048k-TITAN-Medium.pth
   certutil -hashfile downloads\titan\G-f048k-TITAN-Medium.pth SHA256
   certutil -hashfile downloads\titan\D-f048k-TITAN-Medium.pth SHA256
   ```

   | File | Bytes | SHA256 |
   |---|---|---|
   | `G-f048k-TITAN-Medium.pth` | 452,338,845 | `51a6dc93687f7e1a6051be3dec958289958c9c738d5c520e4fa956e7886ee153` |
   | `D-f048k-TITAN-Medium.pth` | 857,126,469 | `4999a5b66aec0a9ab7e845063eeb242e47a611ab0e6260fb0b5ca44a7c5bbc44` |

   The full path of these files must not contain spaces: the WebUI passes it unquoted.

4. Train in the WebUI. Run `engine\go-webui.bat`; it opens in your browser (http://localhost:7897). On the "Train" tab:

   - Experiment name `ex02t48`; Target sample rate `48k`; pitch guidance: yes; Version `v2`; CPU processes: leave the default.
   - Training folder: the full path of `downloads\expresso\train-ex02`; speaker ID `0`. Click "Process data".
   - GPU `0`; pitch extraction algorithm `rmvpe`; rmvpe GPU field `0-0`. Click "Feature extraction".
   - Save frequency `10`; Total epochs `200`; Batch size `8`; Save only the latest ckpt: yes; Cache all training sets to GPU memory: no; Save a small final model at each save point: yes.
   - Pretrained G and D paths: the full paths of the two TITAN files. Paste them after setting sample rate, version and pitch guidance, because changing those resets the two fields.
   - Click "Train model". Each save writes `engine\assets\weights\ex02t48_e<N>_s<step>.pth`. If training stops, click "Train model" again; it resumes from the last save. The WebUI's "Train feature index" is optional (the small IVF256 index); the shipped voice uses step 5 instead.

5. Build the full index (about 4 minutes on the CPU):

   ```
   engine\runtime\python.exe -I tools\build_full_index.py ex02t48
   ```

   It writes `engine\logs\ex02t48\added_IVF<n>_Flat_nprobe_4_ex02t48full_v2.index`.

6. Copy the model and the index into `models\ex02\`:

   ```
   mkdir models\ex02
   copy engine\assets\weights\ex02t48_e200_s133600.pth models\ex02\
   copy engine\logs\ex02t48\added_IVF13764_Flat_nprobe_4_ex02t48full_v2.index models\ex02\
   ```

   `config\presets\ex02.json` points at these names. If your step count or IVF number differs, use your file names here and edit `pth_path` and `index_path` in the preset. Then `launch.bat` starts it.

7. Once you are happy with the voice, clean up and back up `models\ex02` ([Back it up](#back-it-up)):

   ```
   Remove-Item -Recurse engine\logs\ex02t48, engine\assets\weights\ex02t48_*, engine\assets\indices\ex02t48*, downloads\expresso, downloads\titan
   ```

## Dev tools

These scripts in `tools\` were used to build the custom voices and to track down clicks and chop in the live voice. Run them with the engine's Python; `--help` lists each tool's options.

| Tool | What it does | Example |
|---|---|---|
| `expresso_prep.py` | Builds the ex02 training folder from the Expresso tar ([Rebuild it](#rebuild-it), step 2). `--speaker ex01` to `ex04` picks another Expresso speaker (only ex02 was tried). | `engine\runtime\python.exe -I tools\expresso_prep.py` |
| `ears_prep.py` | Builds EARS training folders from the per-speaker zips in `downloads\ears\` ([The EARS voices](#the-ears-voices-ears-p033-and-ears-p105)). | `engine\runtime\python.exe -I tools\ears_prep.py p033 p105` |
| `build_full_index.py` | Builds the full retrieval index for a trained voice (step 5). It syncs the file to disk and reads it back before replacing an existing index. `--check` verifies an existing index against the features instead; `--nprobe` and `--seed` are optional. | `engine\runtime\python.exe -I tools\build_full_index.py ex02t48` |
| `rt_render.py` | Renders a WAV through the realtime engine path offline, for A/B tests of settings and voices. `--realtime` paces blocks like live use. It always writes `out.json` next to `out.wav` (settings, the model and index used, per-block timing). | `engine\runtime\python.exe tools\rt_render.py in.wav out.wav --preset ex02 --set rms_mix_rate=1` |
| `artifact_scan.py` | Counts clicks, spikes, dropouts, block-edge artifacts and (with `--pitch`) pitch wobble in a recording. Needs FFmpeg on PATH; add `--grid-offset 0` for `rt_render.py` output. | `engine\runtime\python.exe tools\artifact_scan.py out.wav --block-time 0.75` |
