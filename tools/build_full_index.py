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
about twice the file size in RAM. The index is written to a .tmp file, synced to disk (an index
still in the write cache came back 95% zeros after a crash), read back and checked (see
check_index), then renamed into place; if anything fails, any existing index is left alone and
the .tmp is removed.

    engine\\runtime\\python.exe -I tools\\build_full_index.py ex02t48 --check

checks an existing index against the features instead (e.g. after a crash) and exits 1 on problems.
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_features(engine, exp):
    import numpy as np

    feature_dir = os.path.join(engine, "logs", exp, "3_feature768")
    names = sorted(n for n in os.listdir(feature_dir) if n.endswith(".npy"))
    if not names:
        raise SystemExit(f"no features in {feature_dir}: run the WebUI's feature extraction first")
    return names, np.concatenate([np.load(os.path.join(feature_dir, n)) for n in names], 0).astype(np.float32)


def index_path(engine, exp, n_ivf, nprobe):
    return os.path.join(engine, "logs", exp, f"added_IVF{n_ivf}_Flat_nprobe_{nprobe}_{exp}full_v2.index")


def build(engine, exp, nprobe=4, seed=None):
    import faiss
    import numpy as np

    t0 = time.time()
    names, big = load_features(engine, exp)
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
    small = int(sum(ivf.invlists.list_size(i) < 8 for i in range(ivf.nlist)))
    path = index_path(engine, exp, n_ivf, nprobe)
    tmp = path + ".tmp"
    try:
        faiss.write_index(index, tmp)
        del index, ivf  # the check reads the file back; don't hold two copies
        sync_to_disk(tmp)
        problems = check_index(tmp, big, nprobe)
        if problems:
            raise SystemExit(f"the written index failed its read-back check, nothing replaced: {'; '.join(problems)}")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    print(f"wrote {path} ({os.path.getsize(path) / 1e9:.2f} GB) in {time.time() - t0:.0f} s; "
          f"lists with fewer than 8 vectors: {small} of {n_ivf}; read back OK", flush=True)
    return path


def check(engine, exp, nprobe=4):
    """--check: the existing full index of exp against its features. Returns the exit code."""
    import numpy as np

    _, big = load_features(engine, exp)
    n = big.shape[0]
    path = index_path(engine, exp, max(1, min(int(16 * np.sqrt(n)), n // 39)), nprobe)
    if not os.path.isfile(path):
        print(f"no index at {path}", flush=True)
        return 1
    problems = check_index(path, big, nprobe)
    print(f"{path}: {'; '.join(problems) if problems else f'OK, all {n} vectors'}", flush=True)
    return 1 if problems else 0


def sync_to_disk(path):
    """fsync: an index still in the write cache is lost to a crash (one came back 95% zeros)."""
    fd = os.open(path, os.O_RDWR | getattr(os, "O_BINARY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def check_index(path, vectors, nprobe):
    """Read an index file back against the feature vectors it should hold, in any order. Returns the
    problems found: unreadable, wrong count or nprobe, ids with no stored vector, all-zero vectors,
    or sampled features that don't come back as themselves (the same vector stored at the id found)."""
    import faiss
    import numpy as np

    try:
        index = faiss.read_index(path)
    except Exception as e:
        return [f"unreadable: {e}"]
    n = vectors.shape[0]
    problems = []
    if index.ntotal != n:
        problems.append(f"{index.ntotal} vectors stored, expected {n}")
    if faiss.extract_index_ivf(index).nprobe != nprobe:
        problems.append(f"nprobe {faiss.extract_index_ivf(index).nprobe}, expected {nprobe}")
    stored = np.full((index.ntotal, index.d), np.nan, dtype=np.float32)  # rows reconstruct_n skips stay NaN
    for start in range(0, index.ntotal, 65536):
        index.reconstruct_n(start, min(65536, index.ntotal - start), stored[start:start + 65536])
    missing = int(np.isnan(stored).any(axis=1).sum())
    if missing:
        problems.append(f"{missing} ids with no stored vector")
    zero = int((stored == 0).all(axis=1).sum())
    if zero:
        problems.append(f"{zero} all-zero vectors")
    sample = vectors[np.linspace(0, n - 1, min(n, 1000)).astype(int)]
    _, ids = index.search(sample, 1)
    ids = ids[:, 0]
    found = (ids >= 0) & (ids < index.ntotal)
    found[found] = (stored[ids[found]] == sample[found]).all(axis=1)
    if found.mean() < 0.99:
        problems.append(f"only {found.mean():.0%} of sampled vectors find themselves")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("exp", help="experiment name (the folder under engine\\logs)")
    parser.add_argument("--engine", default=os.path.join(REPO, "engine"))
    parser.add_argument("--nprobe", type=int, default=4)
    parser.add_argument("--seed", type=int, help="fix the shuffle (the WebUI's is random)")
    parser.add_argument("--check", action="store_true", help="check the existing index instead of building one")
    args = parser.parse_args(argv)
    if args.check:
        return check(os.path.abspath(args.engine), args.exp, args.nprobe)
    build(os.path.abspath(args.engine), args.exp, args.nprobe, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
