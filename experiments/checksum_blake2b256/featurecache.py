"""MIT-licensed, content-addressed cache for causal CSV feature computation."""
from contextlib import contextmanager
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import uuid
import numpy as np
import pandas as pd

SCHEMA=2


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def compute(raw,column,windows):
    frame=pd.read_csv(BytesIO(raw),usecols=[column])
    p=pd.to_numeric(frame[column],errors='raise')
    if not np.isfinite(p).all():raise ValueError('Expected finite numeric input')
    result={'value':p}
    for w in windows:
        roll=p.rolling(w,min_periods=w)
        result[f'mean_{w}']=roll.mean()
        result[f'std_{w}']=roll.std()
        result[f'change_{w}']=p.diff(w)
    features=pd.DataFrame(result)
    return features.to_numpy(dtype=np.float64),features.columns.tolist()


@contextmanager
def writer_lock(directory,key,timeout=30):
    lock=directory/f'{key}.lock';start=time.monotonic()
    while True:
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(fd);break
        except FileExistsError:
            if time.monotonic()-start>timeout:raise TimeoutError('Cache writer lock timed out; inspect abandoned lock manually')
            time.sleep(.02)
    try:yield
    finally:lock.unlink(missing_ok=True)


def read_entry(directory,key,provenance):
    manifest=directory/f'{key}.json'
    if not manifest.exists():return None,'miss'
    try:
        entry=json.loads(manifest.read_text())
        if entry['provenance']!=provenance:raise ValueError('Provenance mismatch')
        name=entry['payload']
        # A manifest cannot direct a reader outside this cache directory.
        if Path(name).name!=name or not name.startswith(key+'.') or not name.endswith('.npz'):
            raise ValueError('Invalid payload path')
        payload=(directory/name).read_bytes()
        if entry['payload_digest_algorithm']!='blake2b-256':raise ValueError('Unsupported payload digest')
        if hashlib.blake2b(payload,digest_size=32).hexdigest()!=entry['payload_digest']:raise ValueError('Payload checksum mismatch')
        with np.load(BytesIO(payload),allow_pickle=False) as data:
            values=data['values'];columns=data['columns'].tolist()
        if list(values.shape)!=entry['shape'] or values.dtype!=np.float64 or len(columns)!=values.shape[1]:
            raise ValueError('Payload schema mismatch')
        return (values,columns),'hit'
    except (OSError,ValueError,KeyError,TypeError,EOFError):return None,'invalid'


def features(path,column,windows,cache_dir):
    windows=list(windows)
    if not windows or any(type(w)!=int or w<2 for w in windows) or len(set(windows))!=len(windows):
        raise ValueError('Windows must be unique integers >=2')
    raw=Path(path).read_bytes()
    provenance={'schema':SCHEMA,'input_sha256':digest(raw),'column':column,'windows':windows,
                'implementation_sha256':digest(Path(__file__).read_bytes()),
                'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}
    key=digest(canonical(provenance));directory=Path(cache_dir);directory.mkdir(parents=True,exist_ok=True)
    found,status=read_entry(directory,key,provenance)
    if found is not None:return *found,{'status':status,'key':key,'computed':False}
    with writer_lock(directory,key):
        found,rechecked=read_entry(directory,key,provenance)
        if found is not None:return *found,{'status':rechecked,'key':key,'computed':False}
        values,columns=compute(raw,column,windows)
        payload_name=f'{key}.{uuid.uuid4().hex}.npz'
        payload_path=directory/payload_name
        # Unique, fully flushed payload first; atomic manifest replacement is commit.
        with payload_path.open('xb') as stream:
            # Uncompressed numeric payload: benchmark showed decompression costs
            # exceeded recomputation for this workload. Disk space is the tradeoff.
            np.savez(stream,values=values,columns=np.asarray(columns,dtype='U'))
            stream.flush();os.fsync(stream.fileno())
        entry={'provenance':provenance,'payload':payload_name,'payload_digest_algorithm':'blake2b-256','payload_digest':hashlib.blake2b(payload_path.read_bytes(),digest_size=32).hexdigest(),'shape':list(values.shape)}
        temp=directory/f'{key}.{uuid.uuid4().hex}.tmp'
        try:
            with temp.open('xb') as stream:
                stream.write(canonical(entry));stream.flush();os.fsync(stream.fileno())
            os.replace(temp,directory/f'{key}.json')
        finally:temp.unlink(missing_ok=True)
        return values,columns,{'status':status,'key':key,'computed':True}
