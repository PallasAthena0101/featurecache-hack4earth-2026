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

The command-line interface can also reuse features and export a numeric NPZ file:

```sh
python featurecache_cli.py sensor.csv --column value --windows 4 24 168 --cache .feature-cache --output features.npz
python featurecache_cli.py sensor.csv --column value --windows 4 24 168 --cache .feature-cache
```

The second command reports a validated cache hit. Export is optional, never overwrites an existing file, and must point outside the cache directory. Load exports with `numpy.load('features.npz', allow_pickle=False)`; `values` contains the matrix and `columns` its column names.

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

An additional [real public-weather benchmark](benchmark_public_weather_results.json) uses NOAA GSOD daily temperatures from Los Angeles International Airport during 2024 (366 observations). Fifteen alternating-order repeats found a **0.93x** warm speedup for 7 columns (a slowdown), and **1.68x** for 37 columns. Both outputs matched exactly. This small observed workload demonstrates that cache overhead can outweigh inexpensive transformations. Network download and one-time preparation are excluded from both branches; each timed branch reads the same prepared CSV. Reproduce with `python benchmark_public_weather.py`. The script records the download URL, input checksum, date coverage and full timings; raw observations are not bundled. Dataset description: [NOAA GSOD](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC00516).


### Independent Linux reproduction

The same NOAA input SHA-256 and unchanged implementation/benchmark scripts were replayed on an existing 4-vCPU Tencent Cloud Ubuntu server (Python 3.12.3, NumPy 2.4.0, pandas 2.3.3). The seven core API tests passed there. Fifteen alternating-order repeats per workload produced exact arrays, including NaNs:

| Environment | 7 columns | 37 columns |
|---|---:|---:|
| Windows development machine | 0.93x (slower) | 1.68x |
| Linux cloud server | 2.48x | 4.96x |

These are separate measurements with different hardware, operating systems and dependencies, not a controlled operating-system comparison. They do not establish that Linux causes the difference or that these speedups generalize. The Windows slowdown remains part of the evidence. Full Linux raw timings, environment versions, input/script hashes and equality checks are in [benchmark_linux_weather_results.json](benchmark_linux_weather_results.json). The three CLI-specific tests were verified on Windows, not rerun in this Linux check. No energy or carbon measurement was added.

## Complete lifecycle and opting out

The [cold-to-finish lifecycle benchmark](benchmark_lifecycle_results.md) includes first population, input changes and capacity cleanup, rather than timing only an existing warm entry. On the existing Linux server, all three 25,000-row/37-feature traces were slower with caching: recompute/cache wall ratios were **0.784x** (one input repeated 36 times), **0.363x** (mixed hot/new inputs) and **0.291x** (all unique). Six fresh-cache trials per trace retained every slowdown; all 1,296 outputs matched. Cleanup ran after every cached request with a 32 MiB best-effort budget. These results describe that configuration, not every workload; they do not imply energy or carbon savings.

The CLI now accepts an explicit bypass for work that does not benefit from caching:

```sh
python featurecache_cli.py sensor.csv --column value --windows 4 24 168 --no-cache --output uncached_features.npz
```

Choose either `--cache DIR` or `--no-cache`. Bypass preserves input validation and safe numeric export without reading or writing cache entries. It does not automatically predict whether caching will help. Twenty tests pass on Windows and Linux; the additional checks compare bypass/cached outputs and protect the input file. Earlier benchmark and maintenance evidence remains intact.

## Cache storage maintenance

`cache_maintenance.py` previews cleanup by default. It removes old unreferenced payloads, and can evict committed entries in oldest-manifest order toward a best-effort size limit:

```sh
python cache_maintenance.py .feature-cache --max-bytes 104857600
python cache_maintenance.py .feature-cache --max-bytes 104857600 --apply
```

The default minimum age is one hour. Recent files, busy writer keys, symlinks and unknown files are preserved. Applying a plan acquires the existing per-key lock and rechecks file metadata and the committed manifest; a payload that became current after preview is preserved. An evicted entry is recomputed on its next use. Readers already in flight may encounter a cache miss and recompute. This is oldest-manifest eviction, not LRU, and not a strict quota: inspect `target_met` and `skipped_keys`. Only recognized manifest/payload bytes count toward the target. Abandoned locks and temporary files still require an operator workflow.

All 18 API, CLI and maintenance tests pass on Windows and the existing Linux cloud server, with no skipped tests. Eight maintenance tests cover preview-only behavior, orphan cleanup, capacity eviction and exact recomputation, active writers, recent entries, path protection, manifest changes under lock, symlinks and invalid limits. Source hashes and Linux verification are retained in `maintenance_linux_verification.json`. The core cache implementation is unchanged; previous benchmark timings were not rerun for this addition. No new runtime, energy or carbon saving is claimed.

## Reliability and trust boundaries

- Input bytes are read once and hashed; computation uses those same bytes.
- Keys include parameters, implementation SHA-256, Python, NumPy and pandas versions.
- A unique payload is flushed before an atomic manifest replacement commits the entry.
- An exclusive per-key writer lock prevents concurrent local writers from repeating the job.
- Readers verify the payload checksum and numeric schema, reject path traversal, and use `allow_pickle=False`.
- Corrupt or interrupted entries are recomputed. A crashed writer may leave an abandoned lock; timeout raises an explicit error rather than silently breaking another writer's lock.

The cache directory is trusted local storage. Checksums detect accidental corruption; they do not authenticate a maliciously replaced manifest and payload. A shared untrusted cache needs authentication and stronger isolation. Local filesystem rename/locking guarantees are assumed; this is not yet a distributed or network-filesystem cache. The optional maintenance command reclaims old payloads and evicts entries toward a best-effort capacity; strict quotas, stale-lock recovery and temporary-file cleanup remain outside this prototype. Files are flushed, but directory-entry durability across power loss depends on the filesystem.

Twenty tests cover reuse, parameter/input invalidation, corruption recovery, interrupted manifests, path traversal, concurrent writers, independence of earlier features from later input changes, CLI exports and overwrite protection. These are prototype checks, not a security certification.

## Scope and provenance

The original core and benchmarks were created on 19 October 2026; lifecycle measurements and the CLI bypass were added on 20 October 2026. NumPy and pandas are existing dependencies, not our inventions. No competition-protected data or credentials are included. Benchmark input is synthetic and reproducible. AI assistance was used to implement and document the prototype.

License: MIT. See `LICENSE`. Public source: https://github.com/PallasAthena0101/featurecache-hack4earth-2026. The local `SUBMISSION.md` is the hackathon write-up draft; repository publication is separate from Kaggle competition submission.
