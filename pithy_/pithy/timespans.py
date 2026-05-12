# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


_suffix_to_seconds:dict[str,float] = {
  'ns': 1e-9,
  'us': 1e-6,
  'ms': 1e-3,
  's':  1.0,
  'm':  60.0,
  'h':  3600.0,
  'd':  86400.0,
  'w':  604800.0,
  'mo': 2_592_000.0,  # Approximate: 30 days.
  'y':  31_536_000.0,  # Approximate: 365 days.
}

timespan_suffixes = list(_suffix_to_seconds)


def parse_timespan_as_seconds(timespan:str) -> float:
  '''
  Convert a timespan string consisting of a float followed by a unit suffix to seconds.
  Note that 'm' is minutes; months are not supported.
  '''
  for suffix in sorted(_suffix_to_seconds, key=len, reverse=True):
    if timespan.endswith(suffix):
      value_str = timespan[:-len(suffix)]
      try: value = float(value_str)
      except ValueError: raise ValueError(f'invalid timespan: {timespan!r}')
      return value * _suffix_to_seconds[suffix]
  raise ValueError(f'invalid timespan (unrecognized suffix): {timespan!r}')


def convert_timespan(timespan:str, *, to:str) -> str:
  '''
  Convert a timespan string to a different unit suffix.
  '''
  if to not in _suffix_to_seconds:
    raise ValueError(f'invalid timespan suffix: {to!r}')
  seconds = parse_timespan_as_seconds(timespan)
  value = seconds / _suffix_to_seconds[to]
  return f'{value:g}{to}'
