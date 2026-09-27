"""Dev tool: render a WAV through the RVC realtime path offline, one block at a time.

Replicates start_vc(), prewarm_cuda_graph() and audio_callback() of engine\\realtime_gui.py
(2.3.260718) without audio devices or the GUI, so settings can be A/B-tested deterministically.
Run it with the engine's own Python (it needs torch, librosa and the engine's modules):

    engine\\runtime\\python.exe tools\\rt_render.py in.wav out.wav --preset vctk-p231 --set rms_mix_rate=1

Settings = config\\audio.json "settings" <- the preset's "settings" <- --set overrides (same keys as
the GUI's config.json). --no-cuda-graph sets RVC_CUDA_GRAPH=0, like launch.bat -NoCudaGraph.
Timing: like realtime_gui.py it pins OMP_NUM_THREADS=4. Use --realtime (one block per block_time)
for live-like inference times: back to back the GPU stays clocked up and blocks run ~5x faster than
live. Measured on the RTX 4080 SUPER: paced p50 ~110 ms, max ~155 ms per 0.25 s block, unchanged by
CPU thread count or background CPU load. The audio output doesn't depend on pacing.
Writes out.wav (mono, device rate) and out.json: settings, per-block inference seconds, SOLA
offsets and the gain the rms mix applied (max per block), plus a summary.
"""

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(REPO, "engine")
BOOL_KEYS = ("I_noise_reduce", "O_noise_reduce")


def load_settings(preset, overrides):
    with open(os.path.join(REPO, "config", "audio.json"), encoding="utf-8") as f:
        cfg = dict(json.load(f).get("settings", {}))
    with open(os.path.join(REPO, "config", "presets", preset + ".json"), encoding="utf-8") as f:
        cfg.update(json.load(f)["settings"])
    cfg.setdefault("I_noise_reduce", False)
    cfg.setdefault("O_noise_reduce", False)
    cfg.setdefault("formant", 0.0)
    for item in overrides:
        key, _, value = item.partition("=")
        if key in BOOL_KEYS:
            cfg[key] = value.lower() in ("1", "true", "yes")
        elif key in ("f0method", "pth_path", "index_path"):
            cfg[key] = value
        else:
            cfg[key] = float(value)
    for key in ("pth_path", "index_path"):
        if not os.path.isabs(cfg[key]):
            cfg[key] = os.path.normpath(os.path.join(REPO, cfg[key]))
    return cfg


class Renderer:
    """The GUI's realtime state and callback, minus the stream. Mirrors realtime_gui.py line for line."""

    def __init__(self, cfg, samplerate):
        import numpy as np
        import torch
        import torchaudio.transforms as tat
        from configs.config import Config
        from infer import rtrvc
        from tools.torchgate import TorchGate

        self.np, self.torch = np, torch
        self.cfg = cfg
        self.config = Config()
        self.rvc = rtrvc.RVC(cfg["pitch"], cfg["formant"], cfg["pth_path"], cfg["index_path"],
                             cfg["index_rate"], self.config, None)
        dev = self.config.device
        self.samplerate = samplerate
        self.zc = samplerate // 100
        zc = self.zc
        self.block_frame = int(np.round(cfg["block_time"] * samplerate / zc)) * zc
        self.block_frame_16k = 160 * self.block_frame // zc
        self.crossfade_frame = int(np.round(cfg["crossfade_length"] * samplerate / zc)) * zc
        self.sola_buffer_frame = min(self.crossfade_frame, 4 * zc)
        self.sola_search_frame = zc
        self.extra_frame = int(np.round(cfg["extra_time"] * samplerate / zc)) * zc
        self.input_wav = torch.zeros(self.extra_frame + self.crossfade_frame + self.sola_search_frame
                                     + self.block_frame, device=dev, dtype=torch.float32)
        self.input_wav_denoise = self.input_wav.clone()
        self.input_wav_res = torch.zeros(160 * self.input_wav.shape[0] // zc, device=dev, dtype=torch.float32)
        self.rms_buffer = np.zeros(4 * zc, dtype="float32")
        self.sola_buffer = torch.zeros(self.sola_buffer_frame, device=dev, dtype=torch.float32)
        self.sola_den_kernel = torch.ones(1, 1, self.sola_buffer_frame, device=dev, dtype=torch.float32)
        self.nr_buffer = self.sola_buffer.clone()
        self.output_buffer = self.input_wav.clone()
        self.skip_head = self.extra_frame // zc
        self.return_length = (self.block_frame + self.sola_buffer_frame + self.sola_search_frame) // zc
        self.fade_in_window = torch.sin(0.5 * np.pi * torch.linspace(
            0.0, 1.0, steps=self.sola_buffer_frame, device=dev, dtype=torch.float32)) ** 2
        self.fade_out_window = 1 - self.fade_in_window
        self.resampler = tat.Resample(orig_freq=samplerate, new_freq=16000, dtype=torch.float32).to(dev)
        if self.rvc.tgt_sr != samplerate:
            self.resampler2 = tat.Resample(orig_freq=self.rvc.tgt_sr, new_freq=samplerate,
                                           dtype=torch.float32).to(dev)
        else:
            self.resampler2 = None
        self.tg = TorchGate(sr=samplerate, n_fft=4 * zc, prop_decrease=0.9).to(dev)
        self.prewarm_cuda_graph()

    def prewarm_cuda_graph(self):
        from tools.cuda_graph import cuda_graph_enabled, run_cuda_graph
        torch, np, dev = self.torch, self.np, self.config.device
        if not cuda_graph_enabled(dev):
            return
        try:
            samples = self.input_wav_res.shape[0]
            phase = torch.arange(samples, device=dev, dtype=torch.float32)
            self.input_wav_res.copy_(0.05 * torch.sin(2 * np.pi * 220.0 * phase / 16000.0))
            if self.cfg["I_noise_reduce"]:
                short = self.input_wav[-self.sola_buffer_frame - self.block_frame:].unsqueeze(0)
                self.tg(short, self.input_wav.unsqueeze(0))
            resample_input = self.input_wav[-self.block_frame - 2 * self.zc:]
            run_cuda_graph(self.resampler, "realtime-input-resample", lambda a: self.resampler(a), resample_input)
            inferred = self.rvc.infer(self.input_wav_res, self.block_frame_16k, self.skip_head,
                                      self.return_length, self.cfg["f0method"])
            if self.resampler2 is not None:
                inferred = run_cuda_graph(self.resampler2, "realtime-output-resample",
                                          lambda a: self.resampler2(a), inferred)
            if self.cfg["O_noise_reduce"]:
                self.tg(inferred.unsqueeze(0), self.output_buffer.unsqueeze(0))
            torch.cuda.synchronize(dev)
        finally:
            for t in (self.input_wav, self.input_wav_denoise, self.input_wav_res, self.output_buffer,
                      self.sola_buffer, self.nr_buffer, self.rvc.cache_pitch, self.rvc.cache_pitchf):
                t.zero_()

    def process(self, indata):
        """audio_callback() for one mono block; returns (outdata, stats)."""
        import librosa
        import torch.nn.functional as F
        from tools.cuda_graph import run_cuda_graph
        torch, np, dev, zc, cfg = self.torch, self.np, self.config.device, self.zc, self.cfg
        start_time = time.perf_counter()
        stats = {}
        indata = np.asarray(indata, dtype=np.float32)
        if cfg["threhold"] > -60:
            indata = np.append(self.rms_buffer, indata)
            rms = librosa.feature.rms(y=indata, frame_length=4 * zc, hop_length=zc)[:, 2:]
            self.rms_buffer[:] = indata[-4 * zc:]
            indata = indata[2 * zc - zc // 2:]
            db_threhold = librosa.amplitude_to_db(rms, ref=1.0)[0] < cfg["threhold"]
            for i in range(db_threhold.shape[0]):
                if db_threhold[i]:
                    indata[i * zc:(i + 1) * zc] = 0
            indata = indata[zc // 2:]
        self.input_wav[: -self.block_frame] = self.input_wav[self.block_frame:].clone()
        self.input_wav[-indata.shape[0]:] = torch.from_numpy(indata).to(dev)
        self.input_wav_res[: -self.block_frame_16k] = self.input_wav_res[self.block_frame_16k:].clone()
        if cfg["I_noise_reduce"]:
            self.input_wav_denoise[: -self.block_frame] = self.input_wav_denoise[self.block_frame:].clone()
            input_wav = self.input_wav[-self.sola_buffer_frame - self.block_frame:]
            input_wav = self.tg(input_wav.unsqueeze(0), self.input_wav.unsqueeze(0)).squeeze(0)
            input_wav[: self.sola_buffer_frame] *= self.fade_in_window
            input_wav[: self.sola_buffer_frame] += self.nr_buffer * self.fade_out_window
            self.input_wav_denoise[-self.block_frame:] = input_wav[: self.block_frame]
            self.nr_buffer[:] = input_wav[self.block_frame:]
            resample_input = self.input_wav_denoise[-self.block_frame - 2 * zc:]
            self.input_wav_res[-self.block_frame_16k - 160:] = run_cuda_graph(
                self.resampler, "realtime-input-resample", lambda a: self.resampler(a), resample_input)[160:]
        else:
            resample_input = self.input_wav[-indata.shape[0] - 2 * zc:]
            self.input_wav_res[-160 * (indata.shape[0] // zc + 1):] = run_cuda_graph(
                self.resampler, "realtime-input-resample", lambda a: self.resampler(a), resample_input)[160:]
        infer_wav = self.rvc.infer(self.input_wav_res, self.block_frame_16k, self.skip_head,
                                   self.return_length, cfg["f0method"])
        if self.resampler2 is not None:
            infer_wav = run_cuda_graph(self.resampler2, "realtime-output-resample",
                                       lambda a: self.resampler2(a), infer_wav)
        if cfg["O_noise_reduce"]:
            self.output_buffer[: -self.block_frame] = self.output_buffer[self.block_frame:].clone()
            self.output_buffer[-self.block_frame:] = infer_wav[-self.block_frame:]
            infer_wav = self.tg(infer_wav.unsqueeze(0), self.output_buffer.unsqueeze(0)).squeeze(0)
        if cfg["rms_mix_rate"] < 1:
            input_wav = self.input_wav_denoise[self.extra_frame:] if cfg["I_noise_reduce"] else self.input_wav[self.extra_frame:]
            rms1 = librosa.feature.rms(y=input_wav[: infer_wav.shape[0]].cpu().numpy(),
                                       frame_length=4 * zc, hop_length=zc)
            rms1 = torch.from_numpy(rms1).to(dev)
            rms1 = F.interpolate(rms1.unsqueeze(0), size=infer_wav.shape[0] + 1, mode="linear",
                                 align_corners=True)[0, 0, :-1]
            rms2 = librosa.feature.rms(y=infer_wav[:].cpu().numpy(), frame_length=4 * zc, hop_length=zc)
            rms2 = torch.from_numpy(rms2).to(dev)
            rms2 = F.interpolate(rms2.unsqueeze(0), size=infer_wav.shape[0] + 1, mode="linear",
                                 align_corners=True)[0, 0, :-1]
            rms2 = torch.max(rms2, torch.zeros_like(rms2) + 1e-3)
            gain = torch.pow(rms1 / rms2, 1.0 - cfg["rms_mix_rate"])
            emitted = gain[: self.block_frame + self.sola_search_frame]  # the part that can reach the output
            stats["gain_max"] = float(emitted.max())
            stats["gain_over_4x"] = float((emitted > 4).float().mean())
            infer_wav *= gain
        conv_input = infer_wav[None, None, : self.sola_buffer_frame + self.sola_search_frame]
        cor_nom = F.conv1d(conv_input, self.sola_buffer[None, None, :])
        cor_den = torch.sqrt(F.conv1d(conv_input ** 2, self.sola_den_kernel) + 1e-8)
        sola_offset = torch.argmax(cor_nom[0, 0] / cor_den[0, 0])
        stats["sola_offset"] = int(sola_offset)
        infer_wav = infer_wav[sola_offset:]
        infer_wav[: self.sola_buffer_frame] *= self.fade_in_window
        infer_wav[: self.sola_buffer_frame] += self.sola_buffer * self.fade_out_window
        self.sola_buffer[:] = infer_wav[self.block_frame: self.block_frame + self.sola_buffer_frame]
        outdata = infer_wav[: self.block_frame].cpu().numpy()
        stats["seconds"] = time.perf_counter() - start_time
        return outdata, stats


def summarize(blocks, block_time):
    import numpy as np
    secs = np.array([b["seconds"] for b in blocks[1:]] or [0.0])  # block 0 includes one-off captures
    summary = {
        "blocks": len(blocks),
        "infer_ms_p50": round(float(np.percentile(secs, 50)) * 1000, 1),
        "infer_ms_p95": round(float(np.percentile(secs, 95)) * 1000, 1),
        "infer_ms_p99": round(float(np.percentile(secs, 99)) * 1000, 1),
        "infer_ms_max": round(float(secs.max()) * 1000, 1),
        "blocks_over_70pct": int((secs > 0.7 * block_time).sum()),
        "blocks_over_100pct": int((secs > block_time).sum()),
    }
    gains = [b["gain_max"] for b in blocks if "gain_max" in b]
    if gains:
        g = np.array(gains)
        summary.update(gain_max=round(float(g.max()), 1), gain_max_p95=round(float(np.percentile(g, 95)), 1),
                       blocks_gain_over_4x=int((g > 4).sum()),
                       samples_gain_over_4x=round(float(np.mean([b["gain_over_4x"] for b in blocks if "gain_over_4x" in b])), 4))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--preset", default="vctk-p231")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override a setting, e.g. rms_mix_rate=1 or f0method=fcpe")
    parser.add_argument("--samplerate", type=int, default=48000, help="device rate (sr_device)")
    parser.add_argument("--no-cuda-graph", action="store_true")
    parser.add_argument("--realtime", action="store_true",
                        help="pace blocks like the live stream (one per block_time) instead of back to back, "
                             "so GPU/CPU clocks idle between blocks as they do live")
    args = parser.parse_args(argv)
    cfg = load_settings(args.preset, args.set)
    inp, out = os.path.abspath(args.input), os.path.abspath(args.output)

    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # as realtime_gui.py, before torch loads
    os.environ["OMP_NUM_THREADS"] = "4"
    if args.no_cuda_graph:
        os.environ["RVC_CUDA_GRAPH"] = "0"
    os.chdir(ENGINE)
    sys.path.insert(0, ENGINE)
    sys.argv = [sys.argv[0]]  # configs/config.py parses sys.argv
    import librosa
    import numpy as np
    import soundfile as sf

    audio, _ = librosa.load(inp, sr=args.samplerate, mono=True)
    r = Renderer(cfg, args.samplerate)
    n = r.block_frame
    audio = np.concatenate([audio, np.zeros(-len(audio) % n + n, dtype=np.float32)])  # flush the tail
    chunks, blocks = [], []
    period = n / args.samplerate
    next_due = time.perf_counter()
    for i in range(0, len(audio), n):
        if args.realtime:
            next_due += period
        o, s = r.process(audio[i:i + n])
        chunks.append(o)
        blocks.append(s)
        if args.realtime:
            time.sleep(max(0.0, next_due - time.perf_counter()))
    sf.write(out, np.concatenate(chunks), args.samplerate, subtype="FLOAT")
    result = {"input": inp, "settings": {k: v for k, v in cfg.items() if k not in ("pth_path", "index_path")},
              "model": os.path.basename(cfg["pth_path"]), "cuda_graph": not args.no_cuda_graph,
              "realtime_pacing": args.realtime,
              "block_frame": n, "samplerate": args.samplerate,
              "summary": summarize(blocks, cfg["block_time"]), "blocks": blocks}
    with open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
