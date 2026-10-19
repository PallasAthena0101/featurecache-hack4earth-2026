"""Reproducible wall/CPU benchmark; makes no inferred energy or carbon claims."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import tempfile
import time
import numpy as np
import pandas as pd
from featurecache import compute,features


def run(output,rows=50000,repeats=7):
    rng=np.random.default_rng(20261019)
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/'synthetic_sensor.csv'
        pd.DataFrame({'value':100+np.cumsum(rng.normal(0,.1,rows))}).to_csv(source,index=False)
        raw=source.read_bytes();windows=[4,8,16,24,32,48,64,96,128,192,256,512]
        cache=Path(tmp)/'cache';base=compute(raw,'value',windows)[0]
        cold_wall=time.perf_counter();cold_cpu=time.process_time()
        cached,cols,initial=features(source,'value',windows,cache)
        cold_wall=time.perf_counter()-cold_wall;cold_cpu=time.process_time()-cold_cpu
        np.testing.assert_equal(base,cached)
        timings={'uncached':[],'cached':[]};computations=initial['computed']
        for i in range(repeats):
            # Alternate order to reduce thermal/cache/order bias.
            for mode in (['uncached','cached'] if i%2==0 else ['cached','uncached']):
                wall=time.perf_counter();cpu=time.process_time()
                if mode=='uncached':values=compute(source.read_bytes(),'value',windows)[0]
                else:
                    values,_,info=features(source,'value',windows,cache);computations+=info['computed']
                timings[mode].append({'wall_seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu})
                np.testing.assert_equal(base,values)
        med={k:{m:statistics.median(r[m] for r in v) for m in ['wall_seconds','cpu_seconds']} for k,v in timings.items()}
        result={'rows':rows,'feature_columns':len(cols),'repeats':repeats,'seed':20261019,'python':platform.python_version(),
                'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,
                'input_sha256':hashlib.sha256(raw).hexdigest(),'exact_equal_with_nan':True,
                'cold_cache_wall_seconds':cold_wall,'cold_cache_cpu_seconds':cold_cpu,
                'cached_branch_computations':computations,'raw_timings':timings,'median':med,
                'warm_wall_speedup':med['uncached']['wall_seconds']/med['cached']['wall_seconds'],
                'limitations':'Synthetic numeric CSV; uncompressed-cache reads and hashing included. Higher disk use than compressed storage. No electricity, carbon, or real-world fleet measurement.'}
        Path(output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='benchmark_results.json');args=p.parse_args();run(args.output)
