# FeatureCache: avoid repeating identical time-series feature jobs

HACK4EARTH 2.0, primary track **EFFICIENT**. A working Python prototype created during October 2026 for repeated local research and sensor-data jobs.

When the input CSV, selected column, window parameters, implementation and dependency versions are unchanged, this tool reuses an already computed numeric feature matrix. It checks content hashes before reuse. Changing those inputs invalidates the entry automatically.

## Reproduce

Python 3.12 recommended. Install dependencies from `requirements.txt`, then:

```sh
python -m unittest -v
python benchmark.py
python benchmark_suite.py
```

```python
from featurecache import features
values, columns, info = features('sensor.csv', 'value', [4, 24, 168], '.feature-cache')
print(info)  # computed=True on miss; computed=False on validated hit
```

The input must have a finite numeric column, and its rows must already be in the desired time order. The tool preserves row order. Rolling means, standard deviations and lagged differences use the current or earlier rows; they never use future rows. It does not validate timestamps, infer sampling frequency or establish a safe target-label validation gap.

## Measurement

Full raw measurements are in `benchmark_results.json`; the original compressed-payload experiment remains in `benchmark_compressed_v0.json`.

The benchmark generates 50,000 synthetic sensor readings with a fixed seed and computes 37 numeric feature columns. Both branches include reading the same CSV; the cached branch additionally verifies input/code/dependency identity and payload checksum. Seven alternating-order repeats compare warm-cache lookup against recomputation. Arrays match exactly, including NaN positions.

On the recorded Windows/Python 3.12 environment:

| Implementation | Median wall time | Result |
|---|---:|---|
| Recompute | 29.88 ms | Reference matrix |
| Uncompressed validated cache | 20.18 ms | Exactly equal matrix |
| Compressed cache, earlier experiment | 59.91 ms | Slower than recomputation in its comparison |

The current warm lookup is approximately 1.48x faster. Initial cache construction cost 99.53 ms, so caching requires enough repeated uses to recover its startup cost. It trades additional disk space and hashing/IO work for avoided feature computation. Results vary with data size, storage, hardware and workload; caching cheap computations may be slower.

The follow-up [workload matrix](benchmark_suite_results.md) measures six workloads: 5,000, 50,000 and 250,000 rows, each with 7 or 37 feature columns. Nine alternating-order repeats per workload produced exact arrays, warm wall speedups of 1.46–2.49x, and estimated break-even points of 4–25 total uses. These estimates compare one cold population plus subsequent hits with repeated recomputation; they are not measured deployment outcomes. Raw CPU/wall timings, disk sizes and source hashes are in `benchmark_suite_results.json`.

No electricity or carbon measurements were taken. This project makes **no quantified energy, carbon or deployment-wide savings claim**. The evidence supports a runtime improvement for this workload and reuse of one computed matrix across the measured cache accesses.

## Reliability and trust boundaries

- Input bytes are read once and hashed; computation uses those same bytes.
- Keys include parameters, implementation SHA-256, Python, NumPy and pandas versions.
- A unique payload is flushed before an atomic manifest replacement commits the entry.
- An exclusive per-key writer lock prevents concurrent local writers from repeating the job.
- Readers verify the payload checksum and numeric schema, reject path traversal, and use `allow_pickle=False`.
- Corrupt or interrupted entries are recomputed. A crashed writer may leave an abandoned lock; timeout raises an explicit error rather than silently breaking another writer's lock.

The cache directory is trusted local storage. Checksums detect accidental corruption; they do not authenticate a maliciously replaced manifest and payload. A shared untrusted cache needs authentication and stronger isolation. Local filesystem rename/locking guarantees are assumed; this is not yet a distributed or network-filesystem cache. Old replaced payloads and interrupted orphan payloads are retained; production deployments need garbage collection and storage quotas. Files are flushed, but directory-entry durability across power loss depends on the filesystem.

Seven tests cover reuse, parameter/input invalidation, corruption recovery, interrupted manifests, path traversal, concurrent writers and independence of earlier features from later input changes. These are prototype checks, not a security certification.

## Scope and provenance

All core code, tests, benchmark and documentation in this directory were created on 19 October 2026. NumPy and pandas are existing dependencies, not our inventions. No competition-protected data or credentials are included. Benchmark input is synthetic and reproducible. AI assistance was used to implement and document the prototype.

License: MIT. See `LICENSE`. Public source: https://github.com/PallasAthena0101/featurecache-hack4earth-2026. The local `SUBMISSION.md` is the hackathon write-up draft; repository publication is separate from Kaggle competition submission.
