"""Command-line entry point for reproducible local feature reuse."""
import argparse
import json
from pathlib import Path
import numpy as np
from featurecache import compute, features


def main(argv=None):
    parser = argparse.ArgumentParser(description='Reuse causal rolling features from a numeric CSV column.')
    parser.add_argument('csv', type=Path)
    parser.add_argument('--column', required=True)
    parser.add_argument('--windows', nargs='+', type=int, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--cache', type=Path, help='Directory for validated reuse')
    mode.add_argument('--no-cache', action='store_true', help='Recompute without reading or writing a cache')
    parser.add_argument('--output', type=Path, help='Optional new numeric NPZ file; existing files are never overwritten')
    args = parser.parse_args(argv)
    if len(set(args.windows)) != len(args.windows) or any(w < 2 for w in args.windows):
        parser.error('--windows must contain unique integers >=2')
    if args.output:
        target = args.output.resolve()
        if target == args.csv.resolve() or (args.cache and target.is_relative_to(args.cache.resolve())):
            parser.error('--output must be outside the cache and different from the input')
        if target.exists():
            parser.error('--output already exists; choose a new filename')
    if args.no_cache:
        values, columns = compute(args.csv.read_bytes(), args.column, args.windows)
        info = {'status': 'bypassed', 'computed': True}
    else:
        values, columns, info = features(args.csv, args.column, args.windows, args.cache)
    if args.output:
        # Exclusive creation also protects against a race after the existence check.
        with args.output.open('xb') as stream:
            np.savez(stream, values=values, columns=np.asarray(columns, dtype='U'))
    print(json.dumps({**info, 'rows': len(values), 'columns': columns,
                      'output': str(args.output) if args.output else None}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
