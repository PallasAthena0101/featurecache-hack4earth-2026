# Cold-to-finish cache lifecycle benchmark

Measured on the existing Ubuntu cloud server on 20 October 2026. This is a synthetic workload, not a deployment or energy measurement.

Each trace contains 36 requests for 25,000-row CSVs, each producing 37 features. Six trials start with fresh empty caches. Branch order alternates. Timings include input reads, cold population, validated hits, and applied maintenance after every cached request. Equality checks and input preparation are excluded equally. All 1,296 timed outputs matched their reference numeric digest, including canonical NaNs.

| Trace | Recompute median, s | Cache + cleanup median, s | Speedup (recompute/cache) | Computations with cache | Hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| repeat_one | 0.8747 | 1.1155 | 0.784x | 1/36 | 35/36 |
| mixed_hot_and_new | 0.8941 | 2.4602 | 0.363x | 24/36 | 12/36 |
| all_unique | 0.9141 | 3.1456 | 0.291x | 36/36 | 0/36 |

Every trace was slower with caching under this configuration, including 35 hits after one cold population. Avoided transformations do not automatically translate to lower total runtime or CPU use. Full CPU measurements and individual requests remain in `benchmark_lifecycle_results.json`; none of these results should be replaced by earlier warm-hit speedups.

The mixed trace repeats three hot inputs and introduces one new input per block. Oldest-manifest eviction is FIFO-like; hits do not renew an entry. A 32 MiB budget holds four entries. Independent simulation reproduced all hits, misses, and evictions. Mixed and unique traces ended at 28.24 MiB of recognized cache files; their temporary pre-cleanup peak was 35.30 MiB. Thus the best-effort post-operation target is not a strict transient disk quota.

This is one size, transformation family, storage system and maintenance frequency. It does not establish that all caching is slower. Running cleanup after every request is an explicit measured configuration; other schedules were not evaluated. Input generation, OS filesystem caches and other server activity can affect timings. Six trial totals describe variation on this server, not independent machines. No electricity or carbon was measured.

Use `--no-cache` when profiling does not support reuse. The bypass recomputes the same numeric features and exports the same numeric schema without cache reads or writes. It is explicit, not an automatic performance oracle. The unchanged core cache and maintenance implementations were used for the measured traces. Twenty API, CLI and maintenance tests pass on Windows and Linux, including bypass output equality and input protection.

Reproduce a new measurement without overwriting the recorded evidence:

```sh
python benchmark_lifecycle.py --freeze my_lifecycle_protocol.json
python benchmark_lifecycle.py --protocol my_lifecycle_protocol.json --output my_lifecycle_results.json
python featurecache_cli.py sensor.csv --column value --windows 4 24 168 --no-cache --output uncached_features.npz
```

The bundled protocol was frozen before the cloud run. `benchmark_lifecycle_verification.json` records source checks, independent regeneration of all 36 input hashes, FIFO simulation and timing-summary reconstruction. `lifecycle_cli_linux_verification.json` records the later CLI test replay; that CLI change did not alter the timed core or maintenance code.
