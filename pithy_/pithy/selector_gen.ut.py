# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os

from pithy.exceptions import Timeout
from pithy.selector_gen import read_fds
from utest import utest, utest_run, utest_run_exc, utest_seq


utest_seq([], read_fds, [])
'Test with empty fds: generator should yield nothing.'



@utest_run
def _() -> None:
  'Basic test: two pipes, interleaved writes, read back in order.'

  r0, w0 = os.pipe()
  r1, w1 = os.pipe()
  try:
    it = read_fds([r0, r1])

    def next_chunk() -> tuple[int,bytes]: return next(it)

    os.write(w0, b'hello')
    utest((0, b'hello'), next_chunk)
    os.write(w1, b'world')
    utest((1, b'world'), next_chunk)

    os.close(w0)
    utest((0, b''), next_chunk)
    os.close(w1)
    utest((1, b''), next_chunk)
  finally:
    os.close(r0)
    os.close(r1)


@utest_run_exc(Timeout)
def _() -> None:
  'Test with timeout: no data available, should raise Timeout.'

  r0, w0 = os.pipe()
  try:
    gen = read_fds([r0], timeout=0.001)
    _idx, _chunk = next(gen)
  finally:
    os.close(r0)
    os.close(w0)
