"""Dev tool: build RVC training folders for EARS speakers from their downloaded zips.

    engine\\runtime\\python.exe -I tools\\ears_prep.py p033 p105

Reads downloads\\ears\\<speaker>.zip (the per-speaker zips from the EARS dataset release: 48 kHz
mono, anechoic, about 1 h per speaker) and writes downloads\\ears\\train-<speaker>\\, a flat folder
of 48 kHz mono 24-bit WAVs (what the WebUI's "Process data" step reads; its slicer does the
cutting), plus downloads\\ears\\train-<speaker>.json (minutes by category, what was left out).

What goes in: the freeform monologues, the emotions (freeform and read), the read styles (regular,
slow, fast, loud, high and low pitch), interjections, laughter, cheering, yelling and the sung
line. Left out: whisper (no pitch to learn), the vegetative sounds (eating, yawning, throat
clearing...) and screaming and crying (strained). Non-verbal material is capped at 12% of the set.
EARS files are recorded quietly (speech around -42 dBFS), under the WebUI slicer's -42 dBFS
silence threshold, so each file is scaled to -23 dBFS speech RMS with peaks <= -1 dBFS.

EARS: CC BY-NC 4.0 (personal, non-commercial use; attribution).
"""

import argparse
import json
import os
import shutil
import sys
import zipfile

import numpy as np
import soundfile as sf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(REPO, "downloads", "ears")
SR = 48000
TARGET_DBFS = -23.0
PEAK_DBFS = -1.0
NONVERBAL_CAP = 0.12
LEFT_OUT = ("whisper", "vegetative_", "nonverbal_screaming", "nonverbal_crying")
NONVERBAL = ("nonverbal_", "interjection_", "melodic_")


def category(base):
    if base.startswith("emo_"):
        return "emotion freeform" if base.endswith("_freeform") else "emotion read"
    if base.startswith("freeform_speech"):
        return "freeform"
    if base.startswith(("rainbow_", "sentences_")):
        return "read " + base.rsplit("_", 1)[-1]
    return base.split("_", 1)[0]  # interjection, nonverbal, melodic, vegetative


def level(x):
    """Gain in dB: speech RMS (10 ms frames within 35 dB of the loudest) to TARGET_DBFS, peaks <= PEAK_DBFS."""
    frame = SR // 100
    n = len(x) // frame
    e = 10 * np.log10(np.mean(x[:n * frame].reshape(n, frame).astype(np.float64) ** 2, axis=1) + 1e-12)
    speech = e > e.max() - 35
    rms_db = 10 * np.log10(np.mean(10 ** (e[speech] / 10)))
    peak_db = 20 * np.log10(max(float(np.max(np.abs(x))), 1e-9))
    return min(TARGET_DBFS - rms_db, PEAK_DBFS - peak_db)


def build(speaker):
    z = zipfile.ZipFile(os.path.join(BASE, f"{speaker}.zip"))
    out = os.path.join(BASE, f"train-{speaker}")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    keep, left_out = [], []
    for info in z.infolist():
        if not info.filename.endswith(".wav"):
            continue
        base = info.filename.split("/")[-1][:-4]
        meta = sf.info(z.open(info.filename))
        item = (base, info.filename, meta.frames / meta.samplerate)
        (left_out if any(tag in base for tag in LEFT_OUT) else keep).append(item)
    speech = [k for k in keep if not k[0].startswith(NONVERBAL)]
    nonverbal = sorted((k for k in keep if k[0].startswith(NONVERBAL)), key=lambda k: k[2])  # shortest first
    budget = NONVERBAL_CAP / (1 - NONVERBAL_CAP) * sum(k[2] for k in speech)
    chosen, used = [], 0.0
    for k in nonverbal:
        if used + k[2] <= budget:
            chosen.append(k)
            used += k[2]
        else:
            left_out.append(k)
    minutes = {}
    for base, name, seconds in speech + chosen:
        x, sr = sf.read(z.open(name), dtype="float32", always_2d=True)
        if sr != SR:
            sys.exit(f"{name}: {sr} Hz, expected {SR}")
        x = x.mean(axis=1)
        sf.write(os.path.join(out, base + ".wav"), x * 10 ** (level(x) / 20), SR, subtype="PCM_24")
        cat = category(base)
        minutes[cat] = minutes.get(cat, 0.0) + seconds / 60
    total = sum(minutes.values())
    summary = {"speaker": speaker, "files": len(speech) + len(chosen), "minutes_total": round(total, 1),
               "minutes_by_category": {k: round(v, 1) for k, v in sorted(minutes.items(), key=lambda kv: -kv[1])},
               "nonverbal_share": round(used / 60 / total, 3),
               "left_out": sorted(f"{b} ({s:.0f} s)" for b, _, s in left_out)}
    with open(os.path.join(BASE, f"train-{speaker}.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "left_out"}, indent=1))
    print(f"left out: {len(left_out)} files ({sum(s for _, _, s in left_out) / 60:.1f} min)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("speakers", nargs="+", help="EARS speaker ids, e.g. p033 p105")
    for speaker in parser.parse_args().speakers:
        build(speaker)


if __name__ == "__main__":
    main()
