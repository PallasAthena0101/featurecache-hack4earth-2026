"""Preview or reclaim this cache's old payloads under its existing per-key locks.

Capacity is best effort: recent files, busy keys and unknown files are preserved.
Eviction order is oldest manifest first, not least recently accessed. Readers
already in flight may observe a miss and recompute; they cannot receive a wrong
array. Trusted local storage and the cache's existing locking assumptions apply.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from featurecache import writer_lock

MANIFEST=re.compile(r'([0-9a-f]{64})\.json')
PAYLOAD=re.compile(r'([0-9a-f]{64})\.[0-9a-f]{32}\.npz')

def _files(directory):
    result={}
    for path in directory.iterdir():
        try:
            if path.is_symlink() or not path.is_file():continue
            match=MANIFEST.fullmatch(path.name) or PAYLOAD.fullmatch(path.name)
            if match:
                stat=path.stat()
                result[path.name]={'key':match.group(1),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
        except FileNotFoundError:
            # Another locked cleaner may remove a directory entry mid-scan.
            continue
    return result

def _entry(directory,key):
    path=directory/f'{key}.json'
    if path.is_symlink() or not path.is_file():return None
    try:
        raw=path.read_bytes();entry=json.loads(raw);name=entry['payload']
        match=PAYLOAD.fullmatch(name)
        if not match or match.group(1)!=key or entry['provenance']['schema'] not in (1,2):return None
        return name,hashlib.sha256(raw).hexdigest()
    except (OSError,ValueError,KeyError,TypeError):return None

def prune_cache(cache_dir,max_bytes=None,min_age_seconds=3600,apply=False):
    if max_bytes is not None and (type(max_bytes)!=int or max_bytes<0):raise ValueError('max_bytes must be a nonnegative integer or None')
    if not isinstance(min_age_seconds,(int,float)) or isinstance(min_age_seconds,bool) or not 0<=min_age_seconds<float('inf'):raise ValueError('min_age_seconds must be finite and nonnegative')
    directory=Path(cache_dir).resolve()
    if not directory.exists():return {'applied':bool(apply),'bytes_before':0,'bytes_after':0,'removed':[],'planned':[],'skipped_keys':[],'target_met':True}
    if not directory.is_dir():raise NotADirectoryError(directory)
    now=time.time_ns();snapshot=_files(directory);before=sum(row['size'] for row in snapshot.values())
    keys=sorted({row['key'] for row in snapshot.values()});entries={key:_entry(directory,key) for key in keys}
    plans=[];skipped=set()
    def old(name):return (now-snapshot[name]['mtime_ns'])/1e9>=min_age_seconds
    for name,row in sorted(snapshot.items()):
        if not PAYLOAD.fullmatch(name) or not old(name):continue
        key=row['key']
        if (directory/f'{key}.lock').exists():skipped.add(key);continue
        entry=entries[key]
        if entry is None or entry[0]!=name:plans.append({'key':key,'kind':'orphan','files':[name]})
    projected=before-sum(snapshot[name]['size'] for plan in plans for name in plan['files'])
    ordered=sorted((key for key in keys if entries[key] and f'{key}.json' in snapshot),key=lambda key:(snapshot[f'{key}.json']['mtime_ns'],key))
    if max_bytes is not None:
        for key in ordered:
            if projected<=max_bytes:break
            manifest=f'{key}.json';payload=entries[key][0]
            if (directory/f'{key}.lock').exists():skipped.add(key);continue
            if payload not in snapshot or not old(manifest) or not old(payload):continue
            plans.append({'key':key,'kind':'entry','files':[manifest,payload],'manifest_sha256':entries[key][1]})
            projected-=snapshot[manifest]['size']+snapshot[payload]['size']
    removed=[]
    if apply:
        for plan in plans:
            key=plan['key']
            try:
                with writer_lock(directory,key,timeout=0):
                    current=_files(directory)
                    if any(current.get(name)!=snapshot[name] for name in plan['files']):skipped.add(key);continue
                    latest=_entry(directory,key)
                    if plan['kind']=='orphan':
                        if latest and latest[0]==plan['files'][0]:skipped.add(key);continue
                    elif latest is None or latest[1]!=plan['manifest_sha256']:skipped.add(key);continue
                    # Commit removal first. An unlocked reader safely falls back
                    # to the normal locked recomputation path on a concurrent miss.
                    for name in plan['files']:
                        (directory/name).unlink();removed.append(name)
            except (TimeoutError,OSError):skipped.add(key)
        after=sum(row['size'] for row in _files(directory).values())
    else:after=projected
    return {'applied':bool(apply),'bytes_before':before,'bytes_after':after,'bytes_after_is_projection':not apply,
            'removed':removed,'planned':plans,'skipped_keys':sorted(skipped),'target_met':max_bytes is None or after<=max_bytes,
            'max_bytes':max_bytes,'min_age_seconds':min_age_seconds,'order':'oldest_manifest_first','unknown_files_preserved':True}

def main(argv=None):
    parser=argparse.ArgumentParser(description='Preview old cache cleanup; recent files and busy entries are preserved.')
    parser.add_argument('cache',type=Path)
    parser.add_argument('--max-bytes',type=int,help='Best-effort capacity for recognized cache manifests and payloads')
    parser.add_argument('--min-age-seconds',type=float,default=3600,help='Protect files newer than this age (default:3600)')
    parser.add_argument('--apply',action='store_true',help='Perform the displayed cleanup; default only previews')
    args=parser.parse_args(argv)
    try:result=prune_cache(args.cache,args.max_bytes,args.min_age_seconds,args.apply)
    except ValueError as error:parser.error(str(error))
    print(json.dumps(result));return 0

if __name__=='__main__':raise SystemExit(main())
