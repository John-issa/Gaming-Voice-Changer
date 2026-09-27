"""Dev tool: find clicks, spikes and dropouts in a voice recording and test if they sit on block edges.

    engine\\runtime\\python.exe tools\\artifact_scan.py out.wav [--track 1] [--block-time 0.25] [--json r.json]
    engine\\runtime\\python.exe tools\\artifact_scan.py --selftest

Any file FFmpeg can read works (--track picks the audio track of an .mkv). Needs numpy and FFmpeg
on PATH. Detectors, on 48 kHz mono float audio:
  click    a second-difference sample >16x the RMS of its +-2.5 ms neighbourhood (a discontinuity)
  spike    a 5 ms frame >12 dB louder than the 50 ms before it and >9 dB louder than the 20-50 ms
           after it (a short burst that dies away; a plosive is followed by its vowel)
  dropout  a near-silent 5 ms frame (< -70 dBFS) between loud frames (an underrun gap)
  clip     samples at full scale
Block alignment: for the events, a Rayleigh test on their phase modulo --block-time. R near 1 with
a small p means the events repeat at the block rate, i.e. they come from the chunked processing.
Edge score (with --block-time): spectral flux within +-5 ms of block boundaries vs mid-block, voiced
frames only; 1.0 = seamless joins. --grid-offset 0 for rt_render output, else the phase is searched.
Pitch (--pitch, slow): F0 jitter and "wobble" (F0 around its 150 ms average) in semitones via pyin;
compare an output against its input voice (on clean TTS the conversion adds none: ~0.41 st both).
"""

import argparse
import json
import math
import subprocess
import sys

import numpy as np

SR = 48000


def decode(path, track=0):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-map", f"0:a:{track}",
           "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def frames(x, size):
    n = len(x) // size
    return x[: n * size].reshape(n, size)


def local_median(v, radius):
    """Median of v over +-radius frames (edges clamped); O(n*radius), fine for minutes of audio."""
    padded = np.pad(v, radius, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * radius + 1)
    return np.median(windows, axis=1)


def db(v):
    return 20 * np.log10(np.maximum(v, 1e-9))


def scan(x, block_time=None, grid_offset=None):
    events = []
    hop = SR // 200  # 5 ms
    fr = frames(x, hop)
    rms_db = db(np.sqrt(np.mean(fr ** 2, axis=1)))

    # clicks: an isolated outlier of the second difference against its own +-2.5 ms neighbourhood
    # (a discontinuity is one sample; speech onsets rise over many samples)
    d2 = np.zeros_like(x)
    d2[1:-1] = x[2:] - 2 * x[1:-1] + x[:-2]
    energy = d2.astype(np.float64) ** 2
    win = 241
    csum = np.concatenate(([0.0], np.cumsum(energy)))
    half = win // 2
    idx = np.arange(len(x))
    lo, hi = np.clip(idx - half, 0, len(x)), np.clip(idx + half + 1, 0, len(x))
    neighbours = (csum[hi] - csum[lo] - energy) / np.maximum(hi - lo - 1, 1)
    ratio = np.abs(d2) / np.sqrt(np.maximum(neighbours, 1e-12))
    hits = np.nonzero((ratio > 16) & (np.abs(d2) > 0.02))[0]  # clean TTS speech peaks at ~15
    last = -SR
    for n in hits:
        if n - last > SR // 200:  # one event per 5 ms
            events.append(("click", n / SR, float(ratio[n])))
        last = n

    # spikes: a 5 ms frame far louder than the 50 ms before it AND the 20-50 ms after it
    # (a burst that dies away; a plosive is followed by its vowel)
    after_db = np.full_like(rms_db, -200.0)
    for k in range(4, 11):
        after_db[:-k] = np.maximum(after_db[:-k], rms_db[k:])
    before_db = local_median(rms_db, 10)
    before_db = np.concatenate((np.full(10, -200.0), before_db[:-10])) if len(before_db) > 10 else before_db
    for i in np.nonzero((rms_db > before_db + 12) & (rms_db > after_db + 9) & (rms_db > -40))[0]:
        events.append(("spike", i * hop / SR, float(rms_db[i] - before_db[i])))

    # dropouts: a near-silent frame with loud frames on both sides within 30 ms
    loud = rms_db > -40
    near = np.convolve(loud.astype(int), np.ones(7, dtype=int), mode="same")
    for i in np.nonzero((rms_db < -70) & (near >= 2))[0]:
        if loud[max(0, i - 6): i].any() and loud[i + 1: i + 7].any():
            events.append(("dropout", i * hop / SR, float(rms_db[i])))

    clips = int(np.sum(np.abs(x) >= 0.999))
    events.sort(key=lambda e: e[1])
    report = {
        "seconds": round(len(x) / SR, 2),
        "peak_dbfs": round(float(db(np.max(np.abs(x)) if len(x) else 0.0)), 1),
        "clipped_samples": clips,
        "counts": {k: sum(1 for e in events if e[0] == k) for k in ("click", "spike", "dropout")},
        "events": [{"kind": k, "t": round(t, 4), "value": round(v, 3)} for k, t, v in events],
    }
    report["per_minute"] = {k: round(v * 60 / max(report["seconds"], 1e-9), 1) for k, v in report["counts"].items()}
    if block_time and events:
        report["block_alignment"] = alignment([e[1] for e in events], block_time)
    if block_time:
        report["edges"] = edge_score(x, block_time, grid_offset)
    return report


def edge_score(x, block_time, offset=None):
    """How much rougher the audio is at block boundaries than mid-block (1.0 = seamless).

    Log-spectral flux per 2.5 ms hop; ratio of its mean within +-5 ms of each boundary to its mean
    elsewhere, over voiced frames only. offset: where the block grid starts (s); None searches for
    the phase with the highest ratio (for live recordings, whose grid is unknown).
    """
    n_fft, hop = 512, SR // 400
    if len(x) < n_fft * 4:
        return None
    win = np.hanning(n_fft).astype(np.float32)
    count = (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(count)[:, None]
    spec = np.log(np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-4)
    flux = np.sqrt(np.mean(np.diff(spec, axis=0) ** 2, axis=1))
    level = db(np.sqrt(np.mean(x[idx] ** 2, axis=1)))[1:]
    voiced = level > np.max(level) - 45
    t = (np.arange(len(flux)) * hop + n_fft / 2) / SR
    per = block_time

    def ratio(off):
        phase = ((t - off) / per) % 1.0
        near = np.minimum(phase, 1 - phase) * per <= 0.005
        a, b = flux[near & voiced], flux[~near & voiced]
        return float(a.mean() / b.mean()) if len(a) and len(b) else None

    if offset is not None:
        return {"edge_flux_ratio": round(ratio(offset), 3), "grid_offset_s": offset}
    best = max(((ratio(o), o) for o in np.arange(0, per, 0.0025)), key=lambda r: r[0] or 0)
    return {"edge_flux_ratio": round(best[0], 3), "grid_offset_s": round(float(best[1]), 4), "offset_searched": True}


def pitch_stability(x):
    """F0 steadiness over voiced frames (librosa pyin at 16 kHz, 10 ms hop), in semitones.

    jitter: median / p95 of the frame-to-frame F0 change. wobble: RMS of F0 around its own 150 ms
    moving average, i.e. the 3-12 Hz modulation heard as a warble. Compare against the input voice.
    """
    import librosa

    y = librosa.resample(x, orig_sr=SR, target_sr=16000)
    f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=1000, sr=16000, frame_length=1024, hop_length=160)
    st = 12 * np.log2(np.where(voiced & np.isfinite(f0), f0, np.nan) / 440.0)
    d = np.abs(np.diff(st))
    runs, cur = [], []
    for v in st:  # voiced runs of >= 150 ms
        if np.isfinite(v):
            cur.append(v)
        else:
            if len(cur) >= 15:
                runs.append(np.array(cur))
            cur = []
    if len(cur) >= 15:
        runs.append(np.array(cur))
    wob = [r - np.convolve(r, np.ones(15) / 15, mode="same") for r in runs]
    wob = np.concatenate([w[7:-7] for w in wob if len(w) > 14]) if wob else np.array([])
    d = d[np.isfinite(d)]
    return {"voiced_s": round(float(np.isfinite(st).sum()) * 0.01, 1),
            "median_f0_hz": round(float(np.nanmedian(f0[voiced])) if voiced.any() else 0.0, 1),
            "jitter_st_median": round(float(np.median(d)), 3) if len(d) else None,
            "jitter_st_p95": round(float(np.percentile(d, 95)), 3) if len(d) else None,
            "wobble_st_rms": round(float(np.sqrt(np.mean(wob ** 2))), 3) if len(wob) else None}


def alignment(times, block_time):
    phases = np.array([2 * math.pi * ((t / block_time) % 1.0) for t in times])
    z = np.exp(1j * phases).mean()
    r = float(abs(z))
    n = len(times)
    bins = max(1, int(round(block_time / 0.005)))  # 5 ms phase bins
    hist = np.bincount((phases / (2 * math.pi) * bins).astype(int) % bins, minlength=bins)
    peak = int(np.argmax(hist))
    return {"events": n, "R": round(r, 3), "p_uniform": float(f"{math.exp(-n * r * r):.2e}"),
            "peak_phase_s": round(peak * block_time / bins, 3),
            "share_in_peak_5ms_bin": round(float(hist[peak] / n), 3),
            "share_if_random": round(1.0 / bins, 3)}


def selftest():
    rng = np.random.default_rng(1)
    t = np.arange(SR * 10) / SR
    voice = 0.2 * np.sin(2 * np.pi * 150 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 1.5 * t))  # voiced, 10 s
    x = voice + 0.002 * rng.standard_normal(len(t))
    block = 0.25
    for k in range(4, 36):  # a discontinuity at every block edge 1..9 s
        n = int(k * block * SR)
        x[n:] += 0.12 * (1 if k % 2 else -1)
        x[n + 1:] -= 0.12 * (1 if k % 2 else -1)
    for s in (2.103, 5.517, 8.071):  # 3 ms bursts at +20 dB
        n = int(s * SR)
        x[n:n + 144] += 0.9 * rng.standard_normal(144)
    for s in (3.331, 6.662):  # 5-10 ms digital gaps
        n = int(s * SR)
        x[n:n + 480] = 0
    r = scan(x.astype(np.float32), block)
    c = r["counts"]
    ok = c["click"] >= 25 and c["spike"] >= 3 and c["dropout"] >= 2 and r["block_alignment"]["R"] > 0.5
    clean = scan((voice + 0.002 * rng.standard_normal(len(t))).astype(np.float32), block)
    ok = ok and sum(clean["counts"].values()) == 0
    print(json.dumps({"artifacts": c, "alignment": r["block_alignment"], "clean_signal_events": clean["counts"],
                      "selftest": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", nargs="?")
    p.add_argument("--track", type=int, default=0)
    p.add_argument("--block-time", type=float)
    p.add_argument("--start", type=float, default=0.0, help="skip this many seconds (e.g. warm-up)")
    p.add_argument("--grid-offset", type=float, help="block grid start in s (rt_render output: 0); "
                   "default: searched")
    p.add_argument("--json", help="write the full report (with every event) here")
    p.add_argument("--pitch", action="store_true", help="also measure F0 jitter/wobble (pyin, slow)")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args(argv)
    if a.selftest:
        return selftest()
    x = decode(a.input, a.track)[int(a.start * SR):]
    offset = None if a.grid_offset is None else (a.grid_offset - a.start) % (a.block_time or 1)
    r = scan(x, a.block_time, offset)
    if a.pitch:
        r["pitch"] = pitch_stability(x)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    short = {k: v for k, v in r.items() if k != "events"}
    print(json.dumps(short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
