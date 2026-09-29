# Voices and licenses

Every voice this project uses is free, needs no account, and comes from sources that grant the right to use them. This page summarizes each voice's terms as checked in September 2026 and links the official pages. The linked terms are what apply, and they can change, so re-read them before you rely on a voice. The credits to keep are collected in [CREDITS.md](../CREDITS.md).

## Default voices

The default preset is `ex02`, a custom voice trained in this repo from the Expresso dataset ([custom-voice.md](custom-voice.md)). Two more custom voices, `ears-p033` (female, low register) and `ears-p105` (male), were trained the same way from the EARS dataset ([custom-voice.md](custom-voice.md#the-ears-voices-ears-p033-and-ears-p105)). None of the three can be downloaded, so [back them up](custom-voice.md#back-it-up).

`scripts\get-models.ps1` downloads seven English-speaking female VCTK speakers ("English" is the language, not an accent), about 1.5 GB. A blend of all of them, `vctk-all-f`, is opt-in because its index alone is 1.3 GB. Every preset starts with "Index Rate" 0.5 ([tuning.md](tuning.md#index-rate)). You pick one with `launch.bat -Preset <name>` or from the Voice list at the bottom of the window ([Switching voices](../README.md#switching-voices)).

| Preset | Files in `models\<preset>\` | Size |
|---|---|---|
| `ex02` (the default preset; not downloadable) | `ex02t48_e200_s133600.pth`, `added_IVF13764_Flat_nprobe_4_ex02t48full_v2.index` | 2.38 GB |
| `ears-p033` (not downloadable) | `ears-p033_e200_s27000.pth`, `added_IVF3463_Flat_nprobe_4_ears-p033full_v2.index` | 0.48 GB |
| `ears-p105` (not downloadable) | `ears-p105_e200_s25400.pth`, `added_IVF3085_Flat_nprobe_4_ears-p105full_v2.index` | 0.44 GB |
| `vctk-p231` | `Fp231rmvpe.pth`, `added_IVF1216_Flat_nprobe_1_Fp231rmvpe_v2.index` | 205 MB |
| `vctk-p238` | `Fp238rmvpe.pth`, `added_IVF1617_Flat_nprobe_1_Fp238rmvpe_v2.index` | 254 MB |
| `vctk-p249` | `Fp249rmvpe.pth`, `added_IVF1104_Flat_nprobe_1_Fp249rmvpe_v2.index` | 191 MB |
| `vctk-p262` | `Fp262rmvpe.pth`, `added_IVF1305_Flat_nprobe_1_Fp262rmvpe_v2.index` | 216 MB |
| `vctk-p280` | `Fp280rmvpe.pth`, `added_IVF1400_Flat_nprobe_1_Fp280rmvpe_v2.index` | 228 MB |
| `vctk-p323` | `Fp323rmvpe.pth`, `added_IVF1581_Flat_nprobe_1_Fp323rmvpe_v2.index` | 250 MB |
| `vctk-p340` | `Fp340rmvpe.pth`, `added_IVF1046_Flat_nprobe_1_Fp340rmvpe_v2.index` | 184 MB |
| `vctk-all-f` (opt-in: `get-models.ps1 -Voice vctk-all-f`) | `All_Frmvpe.pth`, `added_IVF10216_Flat_nprobe_1_All_Frmvpe_v2.index` | 1.34 GB |

```
powershell -ExecutionPolicy Bypass -File scripts\get-models.ps1
```

- `-List` prints the voices. `-Voice vctk-p238,vctk-all-f` fetches only those. `-IncludeBeatrice` also fetches each voice's optional Beatrice v2 zip (about 19 MB), which only the CPU-only fallback (Plan C in [PLAN.md](PLAN.md)) uses.
- Every file is pinned by revision, size and SHA256 in `config/models.json`.
- The VCTK models are RVC v2, trained by Nekochu for 250 epochs (the All_F blend 300) in 08/2023 with the Mangio fork of the RVC WebUI. The presets use the builds trained with `rmvpe` pitch extraction (each speaker's `rmvpe/` subfolder on Hugging Face), the same algorithm the GUI uses live (`"f0method": "rmvpe"`). That older RVC doesn't interpolate the pitch of unvoiced frames in training; the custom voices (ex02, ears-p033, ears-p105) were trained in the bundled engine, so their training and live inference match.

## License chain of the default voices

| Voice | Layer | What | License | Link |
|---|---|---|---|---|
| ex02 | Training data | Expresso dataset (Meta AI, 2023), speaker ex02 | CC BY-NC 4.0 | [Expresso](https://speechbot.github.io/expresso/), [dataset README](https://github.com/facebookresearch/textlesslib/tree/main/examples/expresso/dataset), [CC BY-NC 4.0 legal code](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) |
| ex02 | Pretrained base | TITAN-Medium 48k by blaise-tk, fine-tuned from the official RVC v2 pretrain on Expresso | Apache-2.0 | [Model card](https://huggingface.co/blaise-tk/TITAN) |
| ex02 | Voice model | Trained in this repo ([custom-voice.md](custom-voice.md#how-it-was-made)); not redistributed | Personal, non-commercial use (follows the data) | |
| ears-p033, ears-p105 | Training data | EARS dataset (Richter et al., Interspeech 2024), speakers p033 and p105 | CC BY-NC 4.0, attribution to the authors required | [EARS](https://sp-uhh.github.io/ears_dataset/), [dataset repo](https://github.com/facebookresearch/ears_dataset), [CC BY-NC 4.0 legal code](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) |
| ears-p033, ears-p105 | Pretrained base | TITAN-Medium 48k by blaise-tk (as ex02) | Apache-2.0 | [Model card](https://huggingface.co/blaise-tk/TITAN) |
| ears-p033, ears-p105 | Voice models | Trained in this repo ([custom-voice.md](custom-voice.md#the-ears-voices-ears-p033-and-ears-p105)); not redistributed | Personal, non-commercial use (follows the data) | |
| VCTK | Voice models | Nekochu/RVC-VCTK_Voice-sample (Hugging Face) | Apache-2.0 (model card) | [Model card](https://huggingface.co/Nekochu/RVC-VCTK_Voice-sample) |
| VCTK | Training data | CSTR VCTK Corpus 0.92, University of Edinburgh | CC BY 4.0 | [Edinburgh DataShare](https://datashare.ed.ac.uk/handle/10283/3443), [CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en) |

Expresso's and EARS's NC (non-commercial) terms carry over to ex02, ears-p033 and ears-p105: use them for yourself, not for anything that earns money. A monetized stream is a grey area. TITAN's weights are Apache-2.0, but TITAN was trained on Expresso too.

The Nekochu model card lists the VCTK dataset but says nothing about its license or attribution. This project credits the corpus anyway, because the models are built from its recordings.

### Attribution to keep

For the VCTK voices, the attribution line from `config/models.json`:

```
Voices: Nekochu/RVC-VCTK_Voice-sample (Apache-2.0), trained on CSTR VCTK Corpus (CC BY 4.0), University of Edinburgh.
```

For ex02 (this project's wording):

```
Voice: ex02, trained on the Expresso dataset (Meta AI, CC BY-NC 4.0) from the TITAN-Medium pretrain by blaise-tk (Apache-2.0).
```

For ears-p033 and ears-p105 (this project's wording):

```
Voices: ears-p033 and ears-p105, trained on the EARS dataset (Richter et al., Interspeech 2024; CC BY-NC 4.0) from the TITAN-Medium pretrain by blaise-tk (Apache-2.0).
```

Where they go:

1. [CREDITS.md](../CREDITS.md), with the full VCTK, Expresso and EARS citations.
2. The end of every `get-models.ps1` run, which prints the VCTK line.
3. Anything you publish that uses these voices (a video, a clip, a stream recording): put the line in the description. With ex02 and the EARS voices, only non-commercial ones.
4. If you pass the VCTK model files on to someone, include the line and the Apache-2.0 license with them. The custom voices are not passed on.

CC BY 4.0 and CC BY-NC 4.0 do not license publicity, privacy or similar personality rights (Section 2(b)(1) of both legal codes). The VCTK, Expresso and EARS speakers are real, anonymous people, so don't present a voice as a specific real person or claim to be one.

## Add another voice

Every female speaker in the VCTK model repo's `F/` folder is already set up. To train a voice yourself instead, follow how ex02 was made ([custom-voice.md](custom-voice.md#rebuild-it)). To add another voice from the same pinned repo (for example one of the male speakers under `M/`, for a different use):

1. Look up the size and SHA256 of its files. Open this URL in a browser, or fetch it with `curl.exe -s` (replace `<folder>`, for example `M/p226/rmvpe`):

   ```
   https://huggingface.co/api/models/Nekochu/RVC-VCTK_Voice-sample/tree/005c2f948ee9dafd7e3aa7f261b4c3a24beebeef/<folder>
   ```

   For each file, `size` is the size in bytes and `lfs.oid` is the SHA256. Use the `.pth` and `.index` in the speaker's `rmvpe/` subfolder, as the existing presets do.

2. Copy an existing entry in the `voices` list of `config/models.json` (keep the manifest's `revision`) and change `id`, `label`, `remote`, `local`, `size` and `sha256`. Delete the optional `beatrice` file unless you update it too. With `"default": false`, only `-Voice <id>` fetches it.
3. Make a preset for it as in [Switching voices](../README.md#switching-voices), with `"voice"`, `"pth_path"` and `"index_path"` pointing at the new files.
4. Download and verify with `get-models.ps1 -Voice <id>`. A file gets its final name only after its size and SHA256 match your entry. If your entry is wrong, the script stops with one of these:

   - `The download of <file> was corrupt (SHA256 is ..., expected ...) and has been deleted.` If the printed hash equals `lfs.oid` from step 1, fix the `sha256` in your entry; otherwise the download was damaged. Run the command again.
   - `...\<file>.part is ... bytes, expected ....` Fix the `size` in your entry, delete that `.part` file, and run the command again.
   - `curl.exe failed (exit 22)`: the server returned an error, for example HTTP 404 for a misspelled `remote`. Compare it with the listing from step 1.

5. Run `launch.bat -Preset <id>`, or pick it from the Voice list (the list is read at launch, so run `launch.bat` again after adding a preset). Tune it with [tuning.md](tuning.md) and press "Save settings" to keep the values in its preset ([Keep your changes](tuning.md#keep-your-changes)).

## Rules that apply to every voice

- The RVC package's license notice, `engine\MIT协议暨相关引用库协议` (also [on GitHub](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/MIT%E5%8D%8F%E8%AE%AE%E6%9A%A8%E7%9B%B8%E5%85%B3%E5%BC%95%E7%94%A8%E5%BA%93%E5%8D%8F%E8%AE%AE)), says the authors have no control over the software and that whoever uses it, or spreads audio made with it, bears full responsibility. If you don't accept that, it says you may not use the package. If `install-engine.ps1` unpacked the engine with Windows tar.exe instead of 7-Zip, this file is missing from `engine\` (tar skips non-ASCII file names); the MIT license itself is in `engine\LICENSE` either way.
- The game's rules still apply to what you say through any voice ([overwatch.md](overwatch.md#public-voice-chat)).
- Don't use any voice to pass yourself off as a specific real person.

## Optional anime-style extras (opt-in)

Two Japanese voice projects publish official, free RVC models. They are not in `config/models.json`, and the scripts never download them. Unlike the custom voices and the VCTK voices, which ask only for attribution (and, for the custom voices, non-commercial use), both come with content rules.

### Tsukuyomi-chan official RVC model (つくよみちゃん公式RVCモデル)

Links: [official page](https://tyc.rei-yumesaki.net/work/software/rvc/), [terms](https://tyc.rei-yumesaki.net/work/software/rvc/terms/), [how to use](https://tyc.rei-yumesaki.net/work/software/rvc/how-to-use/). Five variants (Normal 1 to 3, Strong, Weak), made with RVC-beta-v2-0528, version 1.0.0 released 2023-06-16. A free zip download from the official page, which mentions no account or registration.

Credit is required for every use and names both the source voice and the model. For your own voice the terms' example is `■声質変換：つくよみちゃん公式RVCモデル` with `■元の音声：自分の声` on the next line. When it is obviously you speaking, for example live on a stream, the shorter `■ボイスチェンジャー：つくよみちゃん公式RVCモデル` is allowed. Other wording is fine as long as the credit is clear, for example "Voice changer: Tsukuyomi-chan Official RVC Model (つくよみちゃん公式RVCモデル)". The terms give no exemption for places where text can't be shown, such as in-game voice chat; where you can, put the credit in your profile or stream description.

Content rules (paraphrased; see the terms):

- Not for activities that criticize or attack real people, organizations or products, or that urge support for or opposition to a political position, religion or ideology.
- Not under a name or account engaged in such activities (a separate name is allowed; the terms add that this doesn't apply below the level of an "activity").
- Don't infringe anyone else's rights.
- Don't publish what you make in a way that lets others reuse it as material (the terms list exceptions).

Otherwise the terms set no limit on commercial use and welcome use as a voice changer in videos and live streams. Take the model from the official page only: the Tsukuyomi-chan model that VC Client downloads may be used only on VC Client ([Tsukuyomi-chan VC Client page](https://tyc.rei-yumesaki.net/work/software/vc-client/)).

### Amitaro's RVC models (あみたろの声素材工房)

Links: [official page](https://amitaro.net/synth/rvc/), voice terms in [English](https://amitaro.net/voice/terms/) and [Japanese](https://amitaro.net/voice/voice_rule/). Four voices built from a speech corpus (hakihaki, runrun, yofukashi, sasayaki) and one livestream-talk voice (nonbiri). The free versions are zip downloads on the official page, with no account. Optional paid support versions of the same models exist; you don't need them.

Credit, exactly as the terms give it: `RVCモデル：あみたろの声素材工房（https://amitaro.net/）`, or in English "RVC Model: Amitaro's Voice Material Studio (https://amitaro.net/)". In a video, put it in the video and as text in the description. Where text credit is impossible (the terms name streams, VRChat and Discord), you may leave it out, but if someone asks about your voice you must make clear that you are using Amitaro's Voice Material Studio RVC model. If you publish a recording of such a chat, put the credit in its description.

Content rules (paraphrased; see the terms):

- Never pass it off as your natural voice.
- Nothing that hurts, discriminates against or deceives people; no political or religious activity, hate, fraud or impersonation.
- Nothing you couldn't show a child (sexual or gory content), no deepfakes of real people, no scam calls or robocalls, no NFT or crypto projects, no promotion of gambling, drugs or weapons.
- Don't use it while active under a name that resembles あみたろ, 小春音アミ or the studio.
- Don't resell or redistribute the models.

### Why they are opt-in

Competitive voice chat is where these rules bite:

- Trash talk aimed at an opponent or a teammate can fall under Tsukuyomi-chan's ban on criticizing or attacking real people, and under Amitaro's ban on hurting people.
- Amitaro's voice must never pass as your own, so in a lobby you have to say it's Amitaro's RVC model (not just "a voice changer") whenever someone asks.
- Tsukuyomi-chan requires a credit, and a voice chat lobby has no place to show it.

Use the custom voices or the VCTK presets for normal matches. Add an extra only if you can keep to its rules.

### Add an extra manually

1. Download the zip yourself from the official page. The scripts don't fetch these models and hold no pinned hash for them.
2. Extract it, create `models\<id>\` (for example `models\tsukuyomi-normal1\`) and copy the model's `.pth` and `.index` into it. Rename any file with Japanese characters to plain ASCII: the RVC GUI rejects non-ASCII paths.
3. Check that you have both files: the launcher needs `pth_path` and `index_path` to exist, and the GUI refuses an empty index field. The Tsukuyomi-chan how-to page only mentions the `.pth` files, so check whether your zip has an `.index`. A model without one can't be loaded by this launcher as is (not tested in this project).
4. Make a preset for it as in [Switching voices](../README.md#switching-voices), with `voice` set to the folder id, and tune it by ear ([tuning.md](tuning.md)).
5. Show the credit wherever the terms require it.
6. Run `launch.bat -Preset <id>`.

`get-models.ps1` doesn't know these voices: if the launcher reports missing voice files for such a preset, copy the files in again from the zip.

## Excluded

| Source | Why it is not used |
|---|---|
| AISO voices | Pitch-less models: the pitch slider does nothing, and they need about 2 s chunks, far over the 0.25 s `block_time` this setup starts with. |
| Real-person or character voices from unlicensed model-sharing sites | Nobody who owns the voice has granted a license to use it. |
| Sample models bundled with VCClient | Licensed for use in VC Client only (the Tsukuyomi-chan project states this for its model). This project runs the RVC realtime GUI, not VCClient. |
| Voices that need an account, a purchase or a subscription | Project rule: everything must be a free download with no account and must work offline. |
