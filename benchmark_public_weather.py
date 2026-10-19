"""Reproduce a real public-weather workload without redistributing raw observations."""
import argparse
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import platform
import statistics
import tempfile
from urllib.request import urlopen
import numpy as np
import pandas as pd
from benchmark_suite import measure
from featurecache import compute,features

SOURCE='https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/2024/72295023174.csv'
METADATA='https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC00516'


def run(output,local_source=None):
    raw=Path(local_source).read_bytes() if local_source else urlopen(SOURCE,timeout=30).read()
    frame=pd.read_csv(BytesIO(raw)).sort_values('DATE').reset_index(drop=True)
    if frame.DATE.duplicated().any():raise ValueError('Duplicate daily observation')
    # NOAA GSOD TEMP uses Fahrenheit; 9999.9 is its missing-value sentinel.
    temperature=pd.to_numeric(frame.TEMP,errors='raise')
    if not np.isfinite(temperature).all() or temperature.eq(9999.9).any():
        raise ValueError('This benchmark requires complete observed temperatures')
    results=[]
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);source=root/'weather.csv'
        pd.DataFrame({'temperature_f':temperature}).to_csv(source,index=False)
        for windows in [[7,30],[2,3,4,5,7,10,14,21,28,30,60,90]]:
            cache=root/f'cache-{len(windows)}'
            expected,columns=compute(source.read_bytes(),'temperature_f',windows)
            (_,_,info),cold=measure(lambda:features(source,'temperature_f',windows,cache))
            timings={'uncached':[],'cached':[]};computations=int(info['computed'])
            for repeat in range(15):
                for branch in (['uncached','cached'] if repeat%2==0 else ['cached','uncached']):
                    if branch=='uncached':
                        (values,_),timing=measure(lambda:compute(source.read_bytes(),'temperature_f',windows))
                    else:
                        (values,_,info),timing=measure(lambda:features(source,'temperature_f',windows,cache))
                        computations+=int(info['computed'])
                    np.testing.assert_equal(values,expected);timings[branch].append(timing)
            median={branch:{metric:statistics.median(t[metric] for t in ts)
                for metric in ['wall_seconds','cpu_seconds']} for branch,ts in timings.items()}
            results.append({'rows':len(frame),'feature_columns':len(columns),'windows':windows,
                'repeats':15,'cold':cold,'median':median,'raw_timings':timings,
                'warm_wall_speedup':median['uncached']['wall_seconds']/median['cached']['wall_seconds'],
                'exact_equal_with_nan':True,'cached_branch_computations':computations,
                'cache_bytes':sum(p.stat().st_size for p in cache.iterdir())})
    record={'source_url':SOURCE,'dataset_metadata_url':METADATA,'station':str(frame.STATION.iloc[0]),
        'station_name':str(frame.NAME.iloc[0]),'date_min':str(frame.DATE.min()),'date_max':str(frame.DATE.max()),
        'source_sha256':hashlib.sha256(raw).hexdigest(),'measurement_utc':datetime.now(timezone.utc).isoformat(),
        'python':platform.python_version(),'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,
        'implementation_sha256':hashlib.sha256(Path(__file__).with_name('featurecache.py').read_bytes()).hexdigest(),
        'benchmark_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations':'One real historical station/year; no deployment, energy, carbon, or predictive-quality claim. Network download and one-time input preparation excluded from both timed branches. Each timed branch reads the same prepared CSV.',
        'workloads':results}
    Path(output).write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='workloads'},indent=2))
    for r in results:print('columns',r['feature_columns'],'warm speedup',r['warm_wall_speedup'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--local-source');parser.add_argument('--output',default='benchmark_public_weather_results.json')
    args=parser.parse_args();run(args.output,args.local_source)
