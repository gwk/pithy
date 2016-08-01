# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
import json.decoder as _json_dec
import json.encoder as _json_enc

import pprint as _pp
import string as _string
import sys as _sys

from sys import stdout, stderr


def fmt_template(template, **substitutions):
  'Render a template using $ syntax.'
  t = _string.Template(template)
  return t.substitute(substitutions)


class JsonEncoder(_json.JSONEncoder):
  'More useful JSON encoder that handles all sequence types and treats named tuples as objects.'

  def default(self, obj):
    try:
      return obj._asdict()
    except AttributeError: pass
    return list(obj)

  def iterencode(self, o, _one_shot=False):
    '''
    Derived from Python/Lib/json/encoder.py.
    Custom iterencode always avoids using c_make_encoder,
    and passes hacked isinstance to _make_iterencode.'
    '''
    if self.check_circular:
      markers = {}
    else:
      markers = None
    if self.ensure_ascii:
      _encoder = _json_enc.encode_basestring_ascii
    else:
      _encoder = _json_enc.encode_basestring

    def floatstr(o, allow_nan=self.allow_nan,
      _repr=float.__repr__, _inf=_json_enc.INFINITY, _neginf=-_json_enc.INFINITY):
      if o != o:
        text = 'NaN'
      elif o == _inf:
        text = 'Infinity'
      elif o == _neginf:
        text = '-Infinity'
      else:
        return _repr(o)
      if not allow_nan:
        raise ValueError(
          "Out of range float values are not JSON compliant: " +
          repr(o))
      return text

    def isinstance_hacked(obj, type):
      'Prevent namedtuple types from being recognized as tuples, so that default is invoked.'
      return isinstance(obj, type) and not hasattr(obj, '_asdict')

    _iterencode = _json_enc._make_iterencode(
      markers, self.default, _encoder, self.indent, floatstr,
      self.key_separator, self.item_separator, self.sort_keys,
      self.skipkeys, _one_shot, isinstance=isinstance_hacked)
    return _iterencode(o, 0)


# basic printing.

def writeZ(file, *items, sep='', end='', flush=False):
  "Write `items` to file; default sep='', end=''."
  print(*items, sep=sep, end=end, file=file, flush=flush)

def writeS(file, *items, sep='', flush=False):
  "Write `items` to file; sep='', end=' '."
  print(*items, sep=sep, end=' ', file=file, flush=flush)

def writeSZ(file, *items, flush=False):
  "Write `items` to file; sep=' ', end=''."
  print(*items, sep=' ', end='', file=file, flush=flush)

def writeSS(file, *items, flush=False):
  "Write `items` to file; sep=' ', end=''."
  print(*items, sep=' ', end=' ', file=file, flush=flush)

def writeL(file, *items, sep='', flush=False):
  "Write `items` to file; sep='', end='\\n'."
  print(*items, sep=sep, end='\n', file=file, flush=flush)

def writeSL(file, *items, flush=False):
  "Write `items` to file; sep=' ', end='\\n'."
  print(*items, sep=' ', end='\n', file=file, flush=flush)

def writeLL(file, *items, flush=False):
  "Write `items` to file; sep='\\n', end='\\n'."
  print(*items, sep='\n', end='\n', file=file, flush=flush)

def writeLSSL(file, *items, flush=False):
  "Write `items` to file; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', end='\n', file=file, flush=flush)


# format printing.

def writeF(file, fmt, *items, flush=False, **keyed_items):
  "Write the formatted `items` to file; end=''."
  print(fmt.format(*items, **keyed_items), end='', file=file, flush=flush)

def writeFL(file, fmt, *items, flush=False, **keyed_items):
  "Write the formatted `items` to file; end='\\n'."
  print(fmt.format(*items, **keyed_items), end='\n', file=file, flush=flush)


# templated format printing.

def writeTF(file, template_fmt, *items, flush=False, **keyed_items):
  """
  Expand the format string with keyed_items, then format the string; end=''.
  Useful for constructing dynamic format strings.
  """
  fmt = fmt_template(template_fmt, **keyed_items)
  writeF(file, fmt, *items, flush=flush, **keyed_items)

def writeTFL(file, template_fmt, *items, flush=False, **keyed_items):
  """
  Expand the format string template with keyed_items, then format the string; end='\\n'
  Useful for constructing dynamic format strings.
  """
  fmt = fmt_template(template_fmt, **keyed_items)
  writeFL(file, fmt, *items, flush=flush, **keyed_items)


def writeP(file, *items, label=None, indent=2, **opts):
  'Pretty print to file.'
  if label is not None:
    file.write(label)
    file.write (': ')
  for item in items:
    _pp.pprint(item, stream=file, indent=indent, **opts)


def write_json(file, *items, indent=2, sort=True, end='\n', cls=JsonEncoder, flush=False):
  'Write `items` as json to file.'
  # TODO: remaining options with sensible defaults.
  for item in items:
    _json.dump(item, file, indent=indent, sort_keys=sort, cls=cls)
    if end:
      file.write(end, flush=flush)


# std out.

def outZ(*items, sep='', end='', flush=False):
  "Write `items` to std out; sep='', end=''."
  print(*items, sep=sep, end=end, flush=flush)

def outS(*items, sep='', flush=False):
  "Write `items` to std out; sep='', end=' '."
  print(*items, sep=sep, end=' ', flush=flush)

def outSZ(*items, flush=False):
  "Write `items` to std out; sep=' ', end=''."
  print(*items, sep=' ', end='', flush=flush)

def outSS(*items, flush=False):
  "Write `items` to std out; sep=' ', end=' '."
  print(*items, end=' ', flush=flush)

def outL(*items, sep='', flush=False):
  "Write `items` to std out; sep='', end='\\n'."
  print(*items, sep=sep, flush=flush)

def outSL(*items, flush=False):
  "Write `items` to std out; sep=' ', end='\\n'."
  print(*items, flush=flush)

def outLL(*items, flush=False):
  "Write `items` to std out; sep='\\n', end='\\n'."
  print(*items, sep='\n', flush=flush)

def outLSSL(*items, flush=False):
  "Write `items` to std out; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', flush=flush)

def outF(fmt, *items, flush=False, **keyed_items):
  "Write the formatted string to std out; end=''."
  writeF(stdout, fmt, *items, flush=flush, **keyed_items)

def outFL(fmt, *items, flush=False, **keyed_items):
  "Write the formatted string to std out; end='\\n'."
  writeFL(stdout, fmt, *items, flush=flush, **keyed_items)

def outP(*items, label=None, flush=False, **opts):
  'Pretty print to std out.'
  writeP(stdout, *items, label=label, **opts)

def out_json(*items, indent=2, sort=True, end='\n', cls=JsonEncoder, flush=False):
  write_json(stdout, *items, indent=indent, sort=sort, end=end, cls=cls, flush=flush)


# std err.

def errZ(*items, sep='', end='', flush=False):
  "Write items to std err; default sep='', end=''."
  print(*items, sep=sep, end=end, file=stderr, flush=flush)

def errS(*items, sep='', flush=False):
  "Write items to std err; sep='', end=' '."
  print(*items, sep=sep, end=' ', file=stderr, flush=flush)

def errSZ(*items, flush=False):
  "Write items to std err; sep=' ', end=''."
  print(*items, sep=' ', end='', file=stderr, flush=flush)

def errSS(*items, flush=False):
  "Write items to std err; sep=' ', end=''."
  print(*items, sep=' ', end=' ', file=stderr, flush=flush)

def errL(*items, sep='', flush=False):
  "Write items to std err; sep='', end='\\n'."
  print(*items, sep=sep, end='\n', file=stderr, flush=flush)

def errSL(*items, flush=False):
  "Write items to std err; sep=' ', end='\\n'."
  print(*items, sep=' ', end='\n', file=stderr, flush=flush)

def errLL(*items, flush=False):
  "Write items to std err; sep='\\n', end='\\n'."
  print(*items, sep='\n', end='\n', file=stderr, flush=flush)

def errLSSL(*items, flush=False):
  "Write items to std err; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', end='\n', file=stderr, flush=flush)

def errF(fmt, *items, flush=False, **keyed_items):
  "Write the formatted string to std err; end=''."
  writeF(stderr, fmt, *items, flush=flush, **keyed_items)

def errFL(fmt, *items, flush=False, **keyed_items):
  "Write the formatted string to std err; end='\\n'."
  writeFL(stderr, fmt, *items, flush=flush, **keyed_items)

def errP(*items, label=None, **opts):
  'Pretty print to std err.'
  writeP(stderr, *items, label=label, **opts)

def err_json(*items, indent=2, sort=True, end='\n', cls=JsonEncoder, flush=False):
  'Write items as json to std err.'
  write_json(stderr, *items, indent=indent, sort=sort, end=end, cls=cls, flush=flush)


def err_progress(iterator, label='progress', suffix='', frequency=0.1):
  '''
  For interactive terminals, return a generator that yields the elements of iterator
  and displays a progress indicator on std err.
  '''
  if not frequency or not stderr.isatty():
    return iterator

  from pithy.ansi import ERASE_LINE

  if label is None:
    label = str(iterator)
  pre = '◊ ' + label + ': '
  post = (suffix and ' ' + suffix) + '…\r'
  final = ' ' + suffix + '.' if suffix else '.'

  if isinstance(frequency, float):
    from time import time
    def err_progress_gen():
      prev_t = time()
      step = 1
      next_i = step
      for i, el in enumerate(iterator):
        if i == next_i:
          print(pre + str(i) + post, end='', file=stderr, flush=True)
          print(ERASE_LINE, end='', file=stderr, flush=False)
          t = time()
          d = t - prev_t
          step = max(1, int(step * frequency / d))
          prev_t = t
          next_i = i + step
        yield el
      print(pre + str(i) + final, file=stderr)


  else:
    def err_progress_gen():
      for i, el in enumerate(iterator):
        if i % frequency == 0:
          print(pre + str(i) + post, end='', file=stderr, flush=True)
          print(ERASE_LINE, end='', file=stderr, flush=False)
        yield el
      print(pre + str(i) + final, file=stderr)

  return err_progress_gen()


# errors.

def fail(*items, sep=''):
  'Write `items` to std err and exit.'
  errZ(*items, sep=sep, end='\n')
  _sys.exit(1)

def failS(*items): 
  "Write `items` to std err with sep =' ', and exit."
  fail(*items, sep=' ')

def failL(*items):
  "Write `items` to std err with sep ='\n', and exit."
  fail(*items, sep='\n')

def failF(fmt, *items, **keyed_items):
  'Writes `items` to std err with a formatted err, and exit.'
  fail(fmt.format(*items, **keyed_items))


def check(condition, *items, sep=''):
  'If `condition` is False, fail with `items`.'
  if not condition: fail(*items, sep=sep)

def checkS(condition, *items):
  "If `condition` is False, fail with `items` and a sep=' '."
  if not condition: failS(*items)

def checkF(condition, fmt, *items, **keyed_items):
  'If `condition` is False, fail with `items` with a formatted err.'
  if not condition: failF(fmt, *items, **keyed_items)


# exceptions.

def raiseS(*items, E=Exception):
  raise E(' '.join(items))

def raiseF(fmt, *items, E=Exception):
  raise E(fmt.format(*items))


# convenience read/write.

def read_from_path(path):
  'Read text that the file at `path` contains.'
  with open(path) as f:
    return f.read()


def write_to_path(path, string):
  'Writes `string` to file at `path`.'
  with open(path, 'w') as f:
    f.write(string)


# input.


def _mk_json_types_hook(types):
  '''
  Provide a hook function that creates custom objects from json.
  Types is a mapping from frozensets of json keys to type constructors.
  '''
  if not types: return None

  type_map = { frozenset(t._fields) : t for t in types }
  if len(type_map) < len(types):
    # TODO: find all offending pairs.
    raise ValueError('provided record types are ambiguous (identical field name sets).')

  def _read_json_object_hook(d):
    keys = frozenset(d.keys())
    try:
      record_type = type_map[keys]
    except KeyError: return d
    return record_type(**d)

  return _read_json_object_hook


def parse_json(string, types=()):
  '''
  Parse json from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  return _json.loads(string, object_hook=hook)


def parse_jsons(string, types=()):
  '''
  Parse multiple json objects from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  decoder = _json.JSONDecoder(object_hook=hook)
  ws_re = _json_dec.WHITESPACE

  # create generator as inner function,
  # so that the file read above gets executed before returning the iterator.
  # otherwise the file might get closed on closed prematurely by a context manager.
  def read_jsons_gen():
    idx = ws_re.match(string, 0).end()
    while idx < len(string):
      obj, end = decoder.raw_decode(string, idx)
      yield obj
      idx = ws_re.match(string, end).end()

  return read_jsons_gen()


def read_json(file, types=()):
  '''
  Read json from `file`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  return _json.load(file, object_hook=hook)


def read_jsons(file, types=()):
  return parse_jsons(file.read(), types=types)
