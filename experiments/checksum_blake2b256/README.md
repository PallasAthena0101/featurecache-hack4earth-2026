# Paired checksum experiment: retain SHA-256 default

One frozen implementation change: BLAKE2b-256 payload digest with all payload bytes still checked. Same 20 original tests pass on both hosts. Per host: 54 trials, 1944 requests, three branches (uncached, SHA-256, BLAKE2b-256), six balanced trials for each trace/branch. Independent verification rebuilt inputs, output equality, FIFO/storage accounting and raw timing statistics.

| Trace | Cloud BLAKE2 speedup vs SHA256 | Windows BLAKE2 speedup vs SHA256 |
|---|---:|---:|
| repeat_one | 1.209002 | 0.743616 |
| mixed_hot_and_new | 1.097985 | 0.961466 |
| all_unique | 1.049999 | 0.981551 |

Values above 1 mean BLAKE2 is faster. Cloud results improve over SHA256, but Windows results regress in every trace. BLAKE2 remains slower than uncached recomputation in every measured trace on both hosts. Reject replacing the public default. Keep the no-cache option and all negative observations. These are wall-time/CPU measurements, not energy or carbon estimates. Host inputs differ only by native CSV newline convention; within-host branches share identical inputs. Do not infer an OS-specific causal mechanism. Windows CPU-time granularity permits zero for short requests; wall-time measurements remain positive.


## Reproduce the rejected variant

This folder is an isolated snapshot; the main package keeps SHA-256 and its existing schema. The experimental `featurecache.py` uses BLAKE2b-256 for the complete payload digest, with a schema bump and the corresponding maintenance compatibility change. It still reads and verifies every payload byte. `baseline_featurecache.py` is the unchanged public SHA-256 implementation at commit `2c3d3bc7c53e4ac3f4138d4e3dc867c029b14d2d`.

From this directory, with NumPy and pandas installed:

```sh
python run.py
```

The command runs the original 20 tests, then runs all 54 balanced trials and writes a new `results.json`. It does not overwrite the archived `cloud_results.json` or `windows_results.json`. Input CSVs and cache directories are generated in disposable temporary directories. No external dataset, network access or cloud credentials are required. The fixed protocol records source hashes, data generation, timing boundaries and capacity policy.

`cloud_results.json` and `windows_results.json` retain every trial and request timing, exact-array equality, input hashes, environment versions and cleanup/storage accounting. The companion verification receipts record independent reconstruction of generated input hashes, FIFO accounting, medians and ratios. Original verification scripts remain in the research workspace; these receipts are evidence, not a substitute for replaying the benchmark. This repository addition does not claim a new benchmark run.

The frozen protocol's original inference text describes the initial cloud trial; the paired report above incorporates the subsequent Windows replication. Native CSV newline conventions differ between hosts, and each host uses identical inputs across all its branches. This is not a controlled operating-system comparison. No timing-to-energy or carbon conversion is made.
