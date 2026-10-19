"""Synthetic workload matrix and finite-reuse break-even evidence; no energy claims."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import tempfile
import time
import numpy as np
import pandas as pd
from featurecache import compute,features


def measure(call):
    wall=time.perf_counter();cpu=time.process_time();value=call()
    return value,{'wall_seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu}


def run(output,repeats=9):
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for rows in [5000,50000,250000]:
            rng=np.random.default_rng(20261019)
            source=root/f'sensor_{rows}.csv'
            pd.DataFrame({'value':100+np.cumsum(rng.normal(0,.1,rows))}).to_csv(source,index=False)
            for windows in [[24,168],[4,8,16,24,32,48,64,96,128,192,256,512]]:
                cache=root/f'cache_{rows}_{len(windows)}'
                expected,columns=compute(source.read_bytes(),'value',windows)
                (values,_,info),cold=measure(lambda:features(source,'value',windows,cache))
                np.testing.assert_equal(expected,values)
                timings={'uncached':[],'cached':[]};computations=int(info['computed'])
                for i in range(repeats):
                    for mode in (['uncached','cached'] if i%2==0 else ['cached','uncached']):
                        if mode=='uncached':
                            (values,_),timing=measure(lambda:compute(source.read_bytes(),'value',windows))
                        else:
                            (values,_,info),timing=measure(lambda:features(source,'value',windows,cache))
                            computations+=int(info['computed'])
                        np.testing.assert_equal(expected,values);timings[mode].append(timing)
                median={k:{metric:statistics.median(v[metric] for v in values)
                    for metric in ['wall_seconds','cpu_seconds']} for k,values in timings.items()}
                a=median['uncached']['wall_seconds'];b=median['cached']['wall_seconds'];c=cold['wall_seconds']
                # N ordinary computations versus one cold population and N-1 hits.
                # For a>b, N*(a-b) > c-b; strict inequality handles exact ties.
                breakeven=max(1,math.floor((c-b)/(a-b))+1) if a>b else (1 if c<a else None)
                result={'rows':rows,'windows':windows,'feature_columns':len(columns),'repeats':repeats,
                    'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                    'exact_equal_with_nan':True,'cached_branch_computations':computations,
                    'cold':cold,'median':median,'raw_timings':timings,
                    'cache_bytes':sum(p.stat().st_size for p in cache.iterdir()),
                    'warm_wall_speedup':a/b,'estimated_break_even_total_uses':breakeven,
                    'estimated_wall_for_total_uses':{str(n):{'recompute':n*a,'cache':c+(n-1)*b} for n in [1,2,5,10,20,50]}}
                results.append(result)
                print(rows,len(windows),'speedup',round(a/b,3),'break-even uses',breakeven,flush=True)
    record={'seed':20261019,'python':platform.python_version(),'platform':platform.platform(),
        'numpy':np.__version__,'pandas':pd.__version__,
        'implementation_sha256':hashlib.sha256(Path(__file__).with_name('featurecache.py').read_bytes()).hexdigest(),
        'benchmark_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations':'Warm local filesystem; synthetic single-column data; no energy/carbon measurements; break-even is estimated from measured medians, not an observed deployment.',
        'workloads':results}
    Path(output).write_text(json.dumps(record,indent=2),encoding='utf-8')
    lines=['# Workload and reuse measurements','',record['limitations'],'',
        '| Rows | Feature columns | Warm speedup | Estimated break-even uses | Cache MiB |',
        '|---:|---:|---:|---:|---:|']
    for r in results:
        n=r['estimated_break_even_total_uses']
        lines.append(f"| {r['rows']:,} | {r['feature_columns']} | {r['warm_wall_speedup']:.2f}x | {n if n is not None else 'No break-even'} | {r['cache_bytes']/2**20:.2f} |")
    lines+=['','All arrays matched exactly, including NaN positions. Each workload built the matrix once across all cached accesses.',
        'Both paths include CSV reads. Cache accesses additionally hash input/code and verify stored payloads.',
        'Nine repeats alternate execution order; full wall and CPU timings are retained in the JSON.',
        'For N uses, estimated cache time is cold population + (N-1) warm hits. Cheap workloads can remain slower with caching.']
    Path(output).with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='benchmark_suite_results.json')
    run(parser.parse_args().output)
