#!/usr/bin/env python3
"""Stream a large NDJSON file into many gzip-compressed chunks for parallel COPY.

Snowflake COPY parallelises roughly one file per warehouse thread, so a single 13 GB
file loads on a single thread no matter how big the warehouse is. Splitting the input
into many ~150 MB gzip parts (default 500 MB uncompressed per part) lets a scaled
warehouse load them in parallel — the difference between minutes and hours.

Streams line by line, so memory stays flat and no full-size uncompressed copy is written
to disk. Handles plain / .gz input, or stdin ('-') for piping a .zst source:

  python split_ndjson.py full.ndjson         ./chunks
  python split_ndjson.py full.ndjson.gz      ./chunks --chunk-mb 500
  zstd -dc full.ndjson.zst | python split_ndjson.py - ./chunks
"""
from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path


def open_input(path: str):
    if path == "-":
        return sys.stdin.buffer
    if path.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def main() -> None:
    ap = argparse.ArgumentParser(description="Split NDJSON into gzip chunks for parallel COPY.")
    ap.add_argument("input", help="NDJSON path, .gz path, or '-' for stdin")
    ap.add_argument("out_dir", help="directory to write part_NNNNN.ndjson.gz into")
    ap.add_argument("--chunk-mb", type=int, default=500,
                    help="uncompressed MB per chunk (default 500 -> ~150 MB gzip)")
    ap.add_argument("--prefix", default="part_")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    limit = args.chunk_mb * 1024 * 1024
    src = open_input(args.input)

    idx = 0
    written = 0
    path = out / f"{args.prefix}{idx:05d}.ndjson.gz"
    gz = gzip.open(path, "wb")
    print(f"writing {path}", file=sys.stderr)

    for line in src:
        # roll to a new chunk before exceeding the limit (never split a JSON line)
        if written and written + len(line) > limit:
            gz.close()
            idx += 1
            written = 0
            path = out / f"{args.prefix}{idx:05d}.ndjson.gz"
            gz = gzip.open(path, "wb")
            print(f"writing {path}", file=sys.stderr)
        gz.write(line)
        written += len(line)

    gz.close()
    print(f"done: {idx + 1} chunk(s) in {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
