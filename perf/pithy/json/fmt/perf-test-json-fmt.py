#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Performance test for pithy.json.fmt.fmt_json_bytes.

Data files are fetched by build/update-json-data.bash.
By default this runs the standard nativejson-benchmark trio.
Arguments are glob patterns relative to the data directory, e.g. `sajson/*.json` or `nativejson-benchmark/canada.json`.

Each file is timed in batches: the batch repetition count is calibrated from a single warm run to hit `target_batch_time`,
and the best (minimum) batch is reported. The minimum is the standard choice for detecting changes of a few percent,
because timing noise is strictly additive.
'''

from pathlib import Path
from sys import argv
from time import perf_counter

from pithy.json.fmt import fmt_json_bytes


data_dir = Path(__file__).resolve().parent / 'data'

target_batch_time = 0.3 # Seconds. Long enough to judge changes of a few percent, short enough for quick iteration.
num_batches = 3


def main() -> None:
  patterns = argv[1:] or ['nativejson-benchmark/*.json']
  paths = sorted({path for pattern in patterns for path in data_dir.glob(pattern)})
  if not paths: exit(f'error: no data files match {patterns!r} in {data_dir}; run build/update-json-data.bash first.')
  for path in paths:
    time_file(path)


def time_file(path:Path) -> None:
  data = path.read_bytes()
  size = len(data)
  fmt(data) # Warm up.
  start = perf_counter()
  fmt(data)
  single_time = perf_counter() - start
  reps = max(1, round(target_batch_time / single_time))
  best = min(time_batch(data, reps) for _ in range(num_batches))
  per_run = best / reps
  mb_per_sec = size / per_run / 1e6
  name = str(path.relative_to(data_dir))
  print(f'{name:40} {size/1e6:6.3f} MB  x{reps:<5} {per_run*1e3:8.2f} ms/run  {mb_per_sec:6.1f} MB/s')


def time_batch(data:bytes, reps:int) -> float:
  start = perf_counter()
  for _ in range(reps):
    fmt(data)
  return perf_counter() - start


def fmt(data:bytes) -> int:
  'Format `data` and return the total output size, discarding the output.'
  total = 0
  for chunk in fmt_json_bytes(data, fix=False):
    total += len(chunk)
  return total


if __name__ == '__main__': main()
