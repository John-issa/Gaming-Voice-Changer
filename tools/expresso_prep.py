"""Dev tool: build the RVC training folder for Expresso speaker ex02 from the official tar.

    engine\\runtime\\python.exe -I tools\\expresso_prep.py [--speaker ex02]

1. Extracts what the speaker needs from downloads\\expresso\\expresso.tar into
   downloads\\expresso\\src (files already there are skipped): her dialogues in the wanted styles,
   her read "default" style, and the metadata (VAD segments, splits, README, LICENSE).
2. Writes downloads\\expresso\\train-<speaker>\\, a flat folder of 48 kHz mono 24-bit WAVs (what the
   WebUI's "Process data" step reads), plus next to it train-<speaker>.csv (where every clip came
   from), train-<speaker>.json (minutes by style) and spotcheck-<speaker>.wav/.txt (a short listen).

What goes in:
  - Improvised dialogues, her own channel only (the actors sat in separate booths), cut to her
    speech with the official per-channel VAD: default, calm, happy, sarcastic, sympathetic,
    projected (loud), fast (quick callouts) and awe (excited reactions) in full; laughing and
    nonverbal capped so together they stay under ~12% of the set.
  - Read speech in the "default" style (base, emphasis, essentials, default longform) for
    phonetic coverage.
  - The official test split is left out.
Each source channel is scaled so its speech sits at -23 dBFS RMS with peaks <= -1 dBFS (the WebUI's
slicer drops anything under -42 dBFS). No denoising, gating or breath removal. (Checked: her channel
has no crosstalk from the other actor - zero correlation where only the other actor speaks; pauses
were already cut to digital silence at noise-floor level in the release.)

Expresso: CC BY-NC 4.0 (personal, non-commercial use; attribution).
"""

import argparse
import csv
import json
import os
import random
import shutil
import sys
import tarfile

import numpy as np
import soundfile as sf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(REPO, "downloads", "expresso")
TAR = os.path.join(BASE, "expresso.tar")
SRC = os.path.join(BASE, "src")
SR = 48000
# Improvised styles used; the rest (whisper, animal, child, angry, sad, sleepy, ...) stay out.
STYLES = ("default", "calm", "happy", "sarcastic", "sympathetic", "projected", "fast", "awe",
          "laughing", "nonverbal")
CAPPED = ("laughing", "nonverbal")
CAP_SHARE = 0.12       # laughing + nonverbal <= this share of the whole set
TARGET_DBFS = -23.0    # speech RMS per source channel
PEAK_DBFS = -1.0
MERGE_GAP = 0.8        # s: her VAD segments closer than this become one clip
PAD = 0.15             # s of context kept around each clip
MIN_CLIP = 1.0         # s: shorter clips are dropped
MAX_CLIP = 30.0        # s: longer runs are split at their widest internal gap


def db(x):
    return 20 * np.log10(max(float(x), 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0


def style_for(pair, style, speaker):
    """Folder style -> this speaker's style ("sad-sympathetic": left speaker sad, right sympathetic)."""
    styles = style.split("-")
    return style if len(styles) == 1 else styles[pair.index(speaker)]


def wanted_member(name, speaker):
    parts = name.split("/")
    if not name.endswith(".wav"):
        return len(parts) == 2 or (len(parts) >= 3 and parts[1] == "splits")  # metadata
    if len(parts) < 6 or parts[1] != "audio_48khz":
        return False
    if parts[2] == "read":
        return parts[3] == speaker and parts[4] == "default"
    if parts[2] == "conversational":
        pair = parts[3].split("-")
        return speaker in pair and style_for(pair, parts[4], speaker) in STYLES
    return False


def extract(speaker):
    if not os.path.isfile(TAR):
        sys.exit(f"{TAR} not found")
    count, total = 0, 0
    with tarfile.open(TAR, "r:") as tar:  # seekable: members we skip are never read
        for member in tar:
            if not (member.isfile() and wanted_member(member.name, speaker)):
                continue
            dest = os.path.join(SRC, *member.name.split("/"))
            if os.path.isfile(dest) and os.path.getsize(dest) == member.size:
                continue
            tar.extract(member, SRC, filter="data")
            count += 1
            total += member.size
    print(f"extracted {count} new files ({total / 1e9:.1f} GB) into {SRC}")


# ---------------------------------------------------------------- metadata


def load_vad(path):
    """VAD_segments.txt -> {"stem/channelN" (dialogues) or "stem" (longform): [(start, end), ...]}."""
    vad = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or "\t" not in line:
                continue
            key, segs = line.rstrip("\n").split("\t", 1)
            vad[key] = [tuple(float(v) for v in s.strip("() ").split(","))
                        for s in segs.split(") (") if s.strip("() ")]
    return vad


def load_test(path):
    """splits/test.txt -> ({read utterance stems}, {long file stem: (start, end) in s})."""
    names, ranges = set(), {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" not in line:
                names.add(line)
                continue
            stem, rng = line.split("\t")
            a, b = (v.strip().rstrip("s") for v in rng.strip("()").split(","))
            ranges[stem] = (float(a) if a else 0.0, float(b) if b else float("inf"))
    return names, ranges


# ---------------------------------------------------------------- clips


def subtract(segs, cut):
    """Segments minus one (start, end) range."""
    if cut is None:
        return list(segs)
    out = []
    for a, b in segs:
        if b <= cut[0] or a >= cut[1]:
            out.append((a, b))
            continue
        if a < cut[0]:
            out.append((a, cut[0]))
        if b > cut[1]:
            out.append((cut[1], b))
    return out


def split_long(run):
    """Speech pieces of one clip -> groups no longer than MAX_CLIP, split at the widest pause."""
    if len(run) == 1 or run[-1][1] - run[0][0] <= MAX_CLIP:
        return [run]
    gaps = [run[i + 1][0] - run[i][1] for i in range(len(run) - 1)]
    i = int(np.argmax(gaps))
    return split_long(run[:i + 1]) + split_long(run[i + 1:])


def clips_from(segs, length, cut=None):
    """VAD segments -> padded (start, end) clips, merged across short pauses, kept out of `cut`."""
    segs = sorted(s for s in subtract(segs, cut) if s[1] > s[0])
    runs, cur = [], []
    for s in segs:
        if cur and s[0] - cur[-1][1] >= MERGE_GAP:
            runs.append(cur)
            cur = []
        cur.append(s)
    if cur:
        runs.append(cur)
    out = []
    for run in runs:
        for piece in split_long(run):
            a, b = max(0.0, piece[0][0] - PAD), min(length, piece[-1][1] + PAD)
            if cut is not None and a < cut[1] <= piece[0][0]:
                a = cut[1]
            if cut is not None and piece[-1][1] <= cut[0] < b:
                b = cut[0]
            if b - a >= MIN_CLIP:
                out.append((a, b))
    return out


def mask(segs, n, widen=0.0):
    m = np.zeros(n, dtype=bool)
    for a, b in segs:
        m[max(0, int((a - widen) * SR)):max(0, int((b + widen) * SR))] = True
    return m


def gain_for(x, speech, clips):
    """dB gain: speech RMS to TARGET_DBFS, limited so no clip peaks above PEAK_DBFS."""
    level = rms(x[speech]) if speech.any() else rms(x)
    peak = max((float(np.max(np.abs(x[int(a * SR):int(b * SR)]))) for a, b in clips), default=0.0)
    return min(TARGET_DBFS - db(level), PEAK_DBFS - db(peak)), db(level)


# ---------------------------------------------------------------- build


def sources(speaker, root):
    """(style, stem, path, channel, VAD key or None for short read utterances) per source file."""
    conv = os.path.join(root, "audio_48khz", "conversational")
    for pair_dir in sorted(os.listdir(conv)):
        pair = pair_dir.split("-")
        if speaker not in pair:
            continue
        ch = pair.index(speaker)
        for style_dir in sorted(os.listdir(os.path.join(conv, pair_dir))):
            style = style_for(pair, style_dir, speaker)
            if style not in STYLES:
                continue
            for name in sorted(os.listdir(os.path.join(conv, pair_dir, style_dir))):
                stem = name[:-4]
                yield style, stem, os.path.join(conv, pair_dir, style_dir, name), ch, f"{stem}/channel{ch + 1}"
    read = os.path.join(root, "audio_48khz", "read", speaker, "default")
    for sub in ("base", "longform"):
        for name in sorted(os.listdir(os.path.join(read, sub))):
            stem = name[:-4]
            yield "read", stem, os.path.join(read, sub, name), 0, stem if sub == "longform" else None


def load_channel(path, ch):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != SR:
        sys.exit(f"{path}: {sr} Hz, expected {SR}")
    return x[:, ch]


def cut_source(src, vad, test_names, test_ranges):
    """One source file -> ([(start, end, gain_db)], info)."""
    style, stem, path, ch, key = src
    x = load_channel(path, ch)
    length = len(x) / SR
    info = {"style": style, "stem": stem, "path": path, "channel": ch, "seconds": round(length, 2)}
    if key is None:  # a short read utterance: kept whole unless it's in the test split
        if stem in test_names or length < MIN_CLIP:
            return [], info
        frame = SR // 100
        e = 10 * np.log10(np.mean(x[:len(x) // frame * frame].reshape(-1, frame) ** 2, axis=1) + 1e-12)
        speech = np.zeros(len(x), dtype=bool)
        speech[:len(e) * frame] = np.repeat(e > e.max() - 35, frame)
        clips = [(0.0, length)]
    else:
        cut = test_ranges.get(stem)
        segs = vad[key]
        clips = clips_from(segs, length, cut)
        speech = mask(subtract(segs, cut), len(x))
    gain, level = gain_for(x, speech, clips)
    info.update(speech_dbfs=round(level, 1), gain_db=round(gain, 1))
    return [(a, b, gain) for a, b in clips], info


def choose_capped(capped, budget_s, rng):
    """Clips of the capped styles, round-robin over their files, until the time budget is used."""
    by_file = {}
    for c in capped:
        by_file.setdefault(c["stem"], []).append(c)
    queues = [rng.sample(v, len(v)) for _, v in sorted(by_file.items())]
    rng.shuffle(queues)
    chosen, used = [], 0.0
    while any(queues):
        for q in queues:
            if not q:
                continue
            c = q.pop(0)
            if used + c["dur"] <= budget_s:
                chosen.append(c)
                used += c["dur"]
    return chosen


def build(speaker, seed=7):
    root = os.path.join(SRC, "expresso")
    vad = load_vad(os.path.join(root, "VAD_segments.txt"))
    test_names, test_ranges = load_test(os.path.join(root, "splits", "test.txt"))
    out = os.path.join(BASE, f"train-{speaker}")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    rng = random.Random(seed)
    clips, files = [], {}
    for src in sources(speaker, root):
        cuts, info = cut_source(src, vad, test_names, test_ranges)
        files[info["stem"]] = info
        for k, (a, b, g) in enumerate(cuts):
            clips.append({"style": info["style"], "stem": info["stem"], "k": k, "start": round(a, 3),
                          "end": round(b, 3), "dur": b - a, "gain_db": round(g, 2)})
    capped = [c for c in clips if c["style"] in CAPPED]
    kept = [c for c in clips if c["style"] not in CAPPED]
    budget = CAP_SHARE / (1 - CAP_SHARE) * sum(c["dur"] for c in kept)
    kept += choose_capped(capped, budget, rng)

    current = (None, None)
    for c in kept:
        info = files[c["stem"]]
        if current[0] != info["path"]:
            current = (info["path"], load_channel(info["path"], info["channel"]))
        y = current[1][int(c["start"] * SR):int(c["end"] * SR)] * 10 ** (c["gain_db"] / 20)
        c["file"] = f"{c['style']}_{c['stem']}_{c['k']:03d}.wav"
        sf.write(os.path.join(out, c["file"]), y, SR, subtype="PCM_24")

    minutes = {}
    for c in kept:
        minutes[c["style"]] = minutes.get(c["style"], 0.0) + c["dur"] / 60
    total = sum(minutes.values())
    summary = {"speaker": speaker, "clips": len(kept), "minutes_total": round(total, 1),
               "minutes_by_style": {k: round(v, 1) for k, v in sorted(minutes.items())},
               "capped_share": round(sum(minutes.get(s, 0.0) for s in CAPPED) / total, 3),
               "capped_available_min": round(sum(c["dur"] for c in capped) / 60, 1)}
    with open(os.path.join(BASE, f"train-{speaker}.json"), "w", encoding="utf-8") as f:
        json.dump(dict(summary, files=list(files.values())), f, indent=1)
    with open(os.path.join(BASE, f"train-{speaker}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "style", "source", "start_s", "end_s", "gain_db"])
        for c in kept:
            w.writerow([c["file"], c["style"], c["stem"], c["start"], c["end"], c["gain_db"]])
    spotcheck(speaker, kept, out, rng)
    print(json.dumps(summary, indent=1))


def spotcheck(speaker, kept, out, rng, per_style=3, seconds=6.0):
    """The first seconds of 3 random clips per style, as one WAV with a time index."""
    gap = np.zeros(int(0.6 * SR), dtype=np.float32)
    parts, lines, t = [], [], 0.0
    for style in sorted({c["style"] for c in kept}):
        pool = [c for c in kept if c["style"] == style]
        for c in rng.sample(pool, min(per_style, len(pool))):
            y, _ = sf.read(os.path.join(out, c["file"]), dtype="float32")
            y = y[:int(seconds * SR)]
            lines.append(f"{int(t // 60)}:{t % 60:04.1f}  {style:<12} {c['file']}")
            parts += [y, gap]
            t += (len(y) + len(gap)) / SR
    sf.write(os.path.join(BASE, f"spotcheck-{speaker}.wav"), np.concatenate(parts), SR, subtype="PCM_24")
    with open(os.path.join(BASE, f"spotcheck-{speaker}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--speaker", default="ex02", choices=("ex01", "ex02", "ex03", "ex04"))
    args = parser.parse_args()
    extract(args.speaker)
    build(args.speaker)


if __name__ == "__main__":
    main()
