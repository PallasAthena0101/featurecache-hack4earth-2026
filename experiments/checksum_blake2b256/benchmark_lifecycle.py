"""Cold-to-finish traces, including storage maintenance; no inferred energy claims."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,platform,statistics,tempfile,time
import numpy as np
import pandas as pd
from featurecache import compute,features
from baseline_featurecache import features as baseline_features
from cache_maintenance import prune_cache

ROWS=25000
WINDOWS=[4,8,16,24,32,48,64,96,128,192,256,512]
TRIALS=6
CAPACITY=32*1024*1024
TRACES={'repeat_one':[0]*36,'mixed_hot_and_new':[v for j in range(9) for v in [0,1,2,3+j]],'all_unique':list(range(36))}
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def protocol():
    root=Path(__file__).resolve().parent
    return dict(rows=ROWS,windows=WINDOWS,trials=TRIALS,capacity_bytes=CAPACITY,traces=TRACES,
        seed=20261020,source_sha256={n:sha((root/n).read_bytes()) for n in ['featurecache.py','baseline_featurecache.py','cache_maintenance.py','benchmark_lifecycle.py']},
        sampling='Six complete fresh-cache trials per trace, three-branch cyclic order balanced twice. No warmup request or primed entry. Same fixed files in both branches.',
        timing='Sum per-request wall and process CPU time for CSV read and compute or validated features plus applied cleanup after every request. Equality checks excluded equally; input generation/reference construction excluded.',
        storage='32MiB best-effort recognized-byte budget, oldest manifest eviction; explicit min_age_seconds=0 only inside disposable benchmark directories. Record temporary pre-cleanup disk peak separately.',
        inference='Synthetic workload on one existing cloud server. No extrapolated energy, carbon, fleet savings or OS effect. Report slowdowns and all traces; no selection of a winning workload.')

def numeric_digest(values,columns):
    assert values.dtype==np.float64
    # Canonicalize NaN bit patterns while retaining exact equality of finite values.
    a=np.asarray(values,dtype='<f8').copy();a[np.isnan(a)]=np.nan
    return sha(a.tobytes()+json.dumps(columns,separators=(',',':')).encode())

def run(expected,out):
    assert protocol()==json.loads(Path(expected).read_text()),'Frozen benchmark source or configuration changed'
    result=dict(utc=datetime.now(timezone.utc).isoformat(),protocol=protocol(),environment=dict(python=platform.python_version(),platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__),trials=[],automatic_publication=False)
    with tempfile.TemporaryDirectory(prefix='featurecache-lifecycle-') as tmp:
        root=Path(tmp);inputs=root/'inputs';inputs.mkdir();refs={};hashes={}
        for k in range(36):
            rng=np.random.default_rng(20261020+k)
            path=inputs/f'{k}.csv';pd.DataFrame({'value':100+np.cumsum(rng.normal(0,.1,ROWS))}).to_csv(path,index=False)
            raw=path.read_bytes();values,columns=compute(raw,'value',WINDOWS)
            refs[k]=numeric_digest(values,columns);hashes[str(k)]=sha(raw)
        result['inputs_sha256']=hashes
        for name,trace in TRACES.items():
            for trial in range(TRIALS):
                for mode in (['uncached','sha256','blake2b256'][trial%3:]+['uncached','sha256','blake2b256'][:trial%3]):
                    cache=root/f'{name}-{trial}-{mode}';wall=cpu=0.;computed=hits=removed=peak=after=0;requests=[]
                    for k in trace:
                        path=inputs/f'{k}.csv';w=time.perf_counter();c=time.process_time()
                        if mode=='uncached':
                            values,columns=compute(path.read_bytes(),'value',WINDOWS);miss=True
                        else:
                            values,columns,info=(baseline_features if mode=='sha256' else features)(path,'value',WINDOWS,cache);miss=info['computed']
                            clean=prune_cache(cache,max_bytes=CAPACITY,min_age_seconds=0,apply=True)
                        elapsed_cpu=time.process_time()-c;elapsed_wall=time.perf_counter()-w
                        wall+=elapsed_wall;cpu+=elapsed_cpu;computed+=int(miss);hits+=int(not miss)
                        assert numeric_digest(values,columns)==refs[k]
                        if mode!='uncached':
                            assert clean['target_met'] and clean['bytes_after']<=CAPACITY and not clean['skipped_keys']
                            peak=max(peak,clean['bytes_before']);after=clean['bytes_after'];removed+=len(clean['removed'])
                        requests.append(dict(input=k,computed=bool(miss),wall_seconds=elapsed_wall,cpu_seconds=elapsed_cpu))
                    result['trials'].append(dict(trace=name,trial=trial,mode=mode,wall_seconds=wall,cpu_seconds=cpu,computations=computed,hits=hits,requests=requests,removed_files=removed,peak_recognized_bytes_before_cleanup=peak,final_recognized_bytes=after))
    summary={}
    for name in TRACES:
        by_mode={m:[r for r in result['trials'] if r['trace']==name and r['mode']==m] for m in ['uncached','sha256','blake2b256']}
        row={m:{metric:statistics.median(r[metric] for r in records) for metric in ['wall_seconds','cpu_seconds','computations','hits','peak_recognized_bytes_before_cleanup','final_recognized_bytes']} for m,records in by_mode.items()}
        row['blake2_wall_vs_recompute']=row['uncached']['wall_seconds']/row['blake2b256']['wall_seconds']
        row['blake2_wall_vs_sha256']=row['sha256']['wall_seconds']/row['blake2b256']['wall_seconds']
        row['blake2_cpu_vs_recompute']=row['uncached']['cpu_seconds']/row['blake2b256']['cpu_seconds']
        row['blake2_cpu_vs_sha256']=row['sha256']['cpu_seconds']/row['blake2b256']['cpu_seconds']
        summary[name]=row
    result.update(summary=summary,exact_numeric_equality_all_requests=True,completed=True,energy_measured=False)
    Path(out).write_text(json.dumps(result,indent=2));print(json.dumps(result['summary']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze');p.add_argument('--protocol');p.add_argument('--output',default='benchmark_lifecycle_results.json');a=p.parse_args()
    if a.freeze:
        with Path(a.freeze).open('x') as f:json.dump(protocol(),f,indent=2)
    else:
        assert a.protocol;run(a.protocol,a.output)
