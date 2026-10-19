# Workload and reuse measurements

Warm local filesystem; synthetic single-column data; no energy/carbon measurements; break-even is estimated from measured medians, not an observed deployment.

| Rows | Feature columns | Warm speedup | Estimated break-even uses | Cache MiB |
|---:|---:|---:|---:|---:|
| 5,000 | 7 | 1.46x | 25 | 0.27 |
| 5,000 | 37 | 1.69x | 11 | 1.41 |
| 50,000 | 7 | 2.21x | 6 | 2.67 |
| 50,000 | 37 | 1.54x | 7 | 14.12 |
| 250,000 | 7 | 2.49x | 4 | 13.35 |
| 250,000 | 37 | 1.75x | 4 | 70.57 |

All arrays matched exactly, including NaN positions. Each workload built the matrix once across all cached accesses.
Both paths include CSV reads. Cache accesses additionally hash input/code and verify stored payloads.
Nine repeats alternate execution order; full wall and CPU timings are retained in the JSON.
For N uses, estimated cache time is cold population + (N-1) warm hits. Cheap workloads can remain slower with caching.
