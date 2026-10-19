# FeatureCache: measured reuse for repeated feature engineering

Primary track: **EFFICIENT**

## Problem

Researchers and operators often rerun identical deterministic CSV feature transformations while experimenting with downstream models. Repeating unchanged feature jobs consumes time and compute. Caching can help, but stale entries and misleading benchmark comparisons can make reuse unreliable.

## Working solution

FeatureCache computes causal rolling features from a numeric CSV column and stores a numeric matrix. Its content-addressed key includes the exact input, feature parameters, implementation hash and dependency versions. Valid hits avoid recomputation. Writes use unique payloads, a per-key lock and an atomic manifest commit; reads verify hashes and reject pickle payloads and unsafe paths.

## Evidence

Seven automated tests pass, including input/parameter invalidation, concurrent writers and corruption/interruption recovery. A reproducible 50,000-row, 37-column synthetic benchmark produced exactly equal arrays. Across seven alternating-order repeats, warm lookup took a median 20.18 ms versus 29.88 ms for recomputation, approximately 1.48x faster. Initial population cost 99.53 ms and must be amortized. Full timings and environment versions are in `benchmark_results.json`.

Our first compressed implementation was slower: its cached lookup took 59.91 ms versus 32.00 ms for recomputation in that experiment. We retained that negative result and switched to uncompressed payloads. The improvement comes with additional disk use. We measured runtime and CPU time, not energy or carbon emissions, and do not claim measured carbon savings.

A follow-up six-workload matrix spans 5,000–250,000 rows and 7 or 37 features, with nine alternating-order repeats for each workload. Warm speedups were 1.46–2.49x with exact outputs; estimated break-even points were 4–25 total uses after counting cold population. Cache storage ranged from 0.27 to 70.57 MiB. All timings, source hashes and limitations are retained in `benchmark_suite_results.json` and its readable companion report.

## Reproduce and inspect

Install `requirements.txt`, run `python -m unittest -v`, then `python benchmark.py` and `python benchmark_suite.py`. The README gives an API example and documents workload, failure and security limits. Core license: MIT.

**Public source repository:** https://github.com/PallasAthena0101/featurecache-hack4earth-2026

This document is the submission draft. Publishing the source repository does not itself submit a Kaggle hackathon entry.

## Work completed during HACK4EARTH

The core implementation, test suite, initial failed compression experiment, corrected benchmark and documentation were created on 19 October 2026. Existing NumPy and pandas libraries perform the numerical work. AI assistance supported implementation and writing.

## Limits and next steps

This prototype assumes trusted local storage and local filesystem locking/atomicity. It needs garbage collection, storage quotas, a stale-lock operator workflow, broader repeated-workload trials and authenticated cache metadata for shared untrusted deployments. Cheap or rarely repeated transformations may not benefit. The project is a working prototype, without a deployed-user or first-place claim.
