# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BytesIO, StringIO

from tap_backblaze.progress import ProgressListener, ProgressReader
from utest import utest, utest_val


# ProgressReader reads through a BytesIO correctly and reports cumulative byte counts.

counts:list[int] = []
reader = ProgressReader(BytesIO(b'0123456789abcdef'), limit=10, on_bytes=counts.append)
utest_val(10, len(reader), 'reader length is the limit')
utest(b'0123', reader.read, 4)
utest(b'4567', reader.read, 4)
utest(b'89', reader.read, 4) # Truncated at the limit.
utest(b'', reader.read, 4) # Exhausted.
utest_val([4, 8, 10], counts, 'cumulative counts')

# An unbounded read stops at the limit.
reader = ProgressReader(BytesIO(b'0123456789abcdef'), limit=10)
utest(b'0123456789', reader.read)
utest(b'', reader.read)

# A short file yields what it has.
reader = ProgressReader(BytesIO(b'01'), limit=10)
utest(b'01', reader.read, 4)
utest(b'', reader.read, 4)


class FakeTty(StringIO):
  def isatty(self) -> bool: return True


class Clock:
  def __init__(self) -> None: self.time = 0.0
  def __call__(self) -> float: return self.time


# The listener throttles prints to one per 0.1s and formats percentages; an injected clock and stream make it deterministic.

stream = FakeTty()
clock = Clock()
with ProgressListener('Upload', stream=stream, now=clock) as listener:
  listener.set_total_bytes(1000)
  clock.time = 0.05
  listener.bytes_completed(100) # Too soon; throttled.
  utest_val('', stream.getvalue(), 'throttled')
  clock.time = 0.2
  listener.bytes_completed(200)
  utest_val('\rUpload: 20.0% of 1.000 kB…', stream.getvalue(), 'one progress line')
  clock.time = 0.25
  listener.bytes_completed(300) # Throttled again.
  utest_val('\rUpload: 20.0% of 1.000 kB…', stream.getvalue(), 'still one progress line')
utest_val('\rUpload: 20.0% of 1.000 kB…\rUpload: 100.0% of 1.000 kB.\n', stream.getvalue(), 'completion line on close')

# A failure prints a failed line.
stream = FakeTty()
clock = Clock()
try:
  with ProgressListener('Upload', stream=stream, now=clock) as listener:
    listener.set_total_bytes(1000)
    raise KeyboardInterrupt
except KeyboardInterrupt: pass
utest_val('\nUpload: failed.\n', stream.getvalue(), 'failure line on close')

# A non-tty stream prints nothing.
plain_stream = StringIO()
with ProgressListener('Upload', stream=plain_stream, now=Clock()) as listener:
  listener.set_total_bytes(1000)
  listener.bytes_completed(1000)
utest_val('', plain_stream.getvalue(), 'non-tty prints nothing')

# With no total bytes set, nothing is printed even on a tty.
stream = FakeTty()
with ProgressListener('Upload', stream=stream, now=Clock()) as listener:
  pass
utest_val('', stream.getvalue(), 'no total, no output')
