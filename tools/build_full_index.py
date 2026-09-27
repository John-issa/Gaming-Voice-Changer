"""Dev tool: build a retrieval index over ALL of an experiment's feature vectors.

    engine\\runtime\\python.exe -I tools\\build_full_index.py ex02t48

The WebUI's "Train feature index" step (engine\\train\\train_index.py) shrinks more than 200k
vectors to 10,000 k-means centres before indexing. This tool follows the same recipe without
that step: every engine\\logs\\<exp>\\3_feature768\\*.npy, one random permutation, RVC's own
list count min(16*sqrt(n), n//39), a faiss "IVF<n>,Flat" index. It sets nprobe 4 instead of 1:
with thousands of lists some hold fewer than 8 vectors, and the realtime engine skips index
retrieval for a whole block when a search comes back short (faiss stores nprobe in the file).

Writes engine\\logs\\<exp>\\added_IVF<n>_Flat_nprobe_<p>_<exp>full_v2.index. For ex02 (740k
vectors) that is 2.3 GB, built in about 4 minutes on the CPU; the realtime engine then holds
about twice the file size in RAM.
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build(engine, exp, nprobe=4, seed=None):
    import faiss
    import numpy as np

    feature_dir = os.path.join(engine, "logs", exp, "3_feature768")
    names = sorted(n for n in os.listdir(feature_dir) if n.endswith(".npy"))
    if not names:
        raise SystemExit(f"no features in {feature_dir}: run the WebUI's feature extraction first")
    t0 = time.time()
    big = np.concatenate([np.load(os.path.join(feature_dir, n)) for n in names], 0).astype(np.float32)
    big = big[np.random.default_rng(seed).permutation(big.shape[0])]
    n = big.shape[0]
    n_ivf = max(1, min(int(16 * np.sqrt(n)), n // 39))
    print(f"{len(names)} files, {n} vectors x {big.shape[1]}: IVF{n_ivf}, nprobe {nprobe}", flush=True)
    index = faiss.index_factory(big.shape[1], f"IVF{n_ivf},Flat")
    ivf = faiss.extract_index_ivf(index)
    index.train(big)
    for start in range(0, n, 8192):
        index.add(big[start:start + 8192])
    ivf.nprobe = nprobe
    path = os.path.join(engine, "logs", exp, f"added_IVF{n_ivf}_Flat_nprobe_{nprobe}_{exp}full_v2.index")
    faiss.write_index(index, path)
    sizes = np.array([ivf.invlists.list_size(i) for i in range(ivf.nlist)])
    print(f"wrote {path} ({os.path.getsize(path) / 1e9:.2f} GB) in {time.time() - t0:.0f} s; "
          f"lists with fewer than 8 vectors: {(sizes < 8).sum()} of {ivf.nlist}", flush=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("exp", help="experiment name (the folder under engine\\logs)")
    parser.add_argument("--engine", default=os.path.join(REPO, "engine"))
    parser.add_argument("--nprobe", type=int, default=4)
    parser.add_argument("--seed", type=int, help="fix the shuffle (the WebUI's is random)")
    args = parser.parse_args(argv)
    build(os.path.abspath(args.engine), args.exp, args.nprobe, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
