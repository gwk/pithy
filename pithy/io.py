# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
import json.decoder as _json_dec
import json.encoder as _json_enc

import pprint as _pp
import string as _string
import sys as _sys

from sys import stdout, stderr


def fmt_template(template, **substitutions):
  'render a template using $ syntax.'
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
    custom iterencode always avoids using c_make_encoder,
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
      _repr=_json_enc.FLOAT_REPR, _inf=_json_enc.INFINITY, _neginf=-_json_enc.INFINITY):
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
      'prevent namedtuple types from being recognized as tuples, so that default is invoked.'
      return isinstance(obj, type) and not hasattr(obj, '_asdict')

    _iterencode = _json_enc._make_iterencode(
        markers, self.default, _encoder, self.indent, floatstr,
        self.key_separator, self.item_separator, self.sort_keys,
        self.skipkeys, _one_shot, isinstance=isinstance_hacked)
    return _iterencode(o, 0)


# basic printing.

def writeZ(file, *items, sep='', end=''):
  "write items to file; default sep='', end=''."
  print(*items, sep=sep, end=end, file=file)

def writeS(file, *items, sep=''):
  "write items to file; sep='', end=' '."
  print(*items, sep=sep, end=' ', file=file)

def writeSZ(file, *items):
  "write items to file; sep=' ', end=''."
  print(*items, sep=' ', end='', file=file)

def writeSS(file, *items):
  "write items to file; sep=' ', end=''."
  print(*items, sep=' ', end=' ', file=file)

def writeL(file, *items, sep=''):
  "write items to file; sep='', end='\\n'."
  print(*items, sep=sep, end='\n', file=file)

def writeSL(file, *items):
  "write items to file; sep=' ', end='\\n'."
  print(*items, sep=' ', end='\n', file=file)

def writeLL(file, *items):
  "write items to file; sep='\\n', end='\\n'."
  print(*items, sep='\n', end='\n', file=file)

def writeLSSL(file, *items):
  "write items to file; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', end='\n', file=file)


# format printing.

def writeF(file, fmt, *items, **keyed_items):
  "write the formatted string to file; end=''."
  print(fmt.format(*items, **keyed_items), end='', file=file)

def writeFL(file, fmt, *items, **keyed_items):
  "write the formatted string to file; end='\\n'."
  print(fmt.format(*items, **keyed_items), end='\n', file=file)


# templated format printing.

def writeTF(file, template_fmt, *items, **keyed_items):
  """
  expand the format string with keyed_items, then format the string; end=''.
  useful for constructing dynamic format strings.
  """
  fmt = fmt_template(template_fmt, **keyed_items)
  writeF(file, fmt, *items, **keyed_items)

def writeTFL(file, template_fmt, *items, **keyed_items):
  """
  expand the format string template with keyed_items, then format the string; end='\\n'
  useful for constructing dynamic format strings.
  """
  fmt = fmt_template(template_fmt, **keyed_items)
  writeFL(file, fmt, *items, **keyed_items)


def writeP(file, *items, label=None, indent=2, **opts):
  'pretty print to file.'
  if label is not None:
    file.write(label)
    file.write (': ')
  for item in items:
    _pp.pprint(item, stream=file, indent=indent, **opts)


def write_json(file, *items, indent=2, sort=True, end='\n', cls=JsonEncoder):
  # TODO: remaining options with sensible defaults.
  for item in items:
    _json.dump(item, file, indent=indent, sort_keys=sort, cls=cls)
    if end:
      stdout.write(end)


# std out.

def outZ(*items, sep='', end=''):
  "write items to std out; sep='', end=''."
  print(*items, sep=sep, end=end)

def outS(*items, sep=''):
  "write items to std out; sep='', end=' '."
  print(*items, sep=sep, end=' ')

def outSZ(*items):
  "write items to std out; sep=' ', end=''."
  print(*items, sep=' ', end='')

def outSS(*items):
  "write items to std out; sep=' ', end=' '."
  print(*items, end=' ')

def outL(*items, sep=''):
  "write items to std out; sep='', end='\\n'."
  print(*items, sep=sep)

def outSL(*items):
  "write items to std out; sep=' ', end='\\n'."
  print(*items)

def outLL(*items):
  "write items to std out; sep='\\n', end='\\n'."
  print(*items, sep='\n')

def outLSSL(*items):
  "write items to std out; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ')

def outF(fmt, *items, **keyed_items):
  "write the formatted string to std out; end=''."
  writeF(stdout, fmt, *items, **keyed_items)

def outFL(fmt, *items, **keyed_items):
  "write the formatted string to std out; end='\\n'."
  writeFL(stdout, fmt, *items, **keyed_items)

def outP(*items, label=None, **opts):
  'pretty print to std out.'
  writeP(stdout, *items, label=label, **opts)

def out_json(*items, indent=2, sort=True, end='\n', cls=JsonEncoder):
  write_json(stdout, *items, indent=indent, sort=sort, end=end, cls=cls)


# std err.

def errZ(*items, sep='', end=''):
  "write items to std err; default sep='', end=''."
  print(*items, sep=sep, end=end, file=stderr)

def errS(*items, sep=''):
  "write items to std err; sep='', end=' '."
  print(*items, sep=sep, end=' ', file=stderr)

def errSZ(*items):
  "write items to std err; sep=' ', end=''."
  print(*items, sep=' ', end='', file=stderr)

def errSS(*items):
  "write items to std err; sep=' ', end=''."
  print(*items, sep=' ', end=' ', file=stderr)

def errL(*items, sep=''):
  "write items to std err; sep='', end='\\n'."
  print(*items, sep=sep, end='\n', file=stderr)

def errSL(*items):
  "write items to std err; sep=' ', end='\\n'."
  print(*items, sep=' ', end='\n', file=stderr)

def errLL(*items):
  "write items to std err; sep='\\n', end='\\n'."
  print(*items, sep='\n', end='\n', file=stderr)

def errLSSL(*items):
  "write items to std err; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', end='\n', file=stderr)

def errF(fmt, *items, **keyed_items):
  "write the formatted string to std err; end=''."
  writeF(stderr, fmt, *items, **keyed_items)

def errFL(fmt, *items, **keyed_items):
  "write the formatted string to std err; end='\\n'."
  writeFL(stderr, fmt, *items, **keyed_items)

def errP(*items, label=None, **opts):
  'pretty print to std err.'
  writeP(stderr, *items, label=label, **opts)

def err_json(*items, indent=2, sort=True, end='\n', cls=JsonEncoder):
  write_json(stderr, *items, indent=indent, sort=sort, end=end, cls=cls)


def err_progress(iterator, label='progress', suffix='', frequency=0.1):
  if not frequency:
    return iterator

  if label is None:
    label = str(iterator)
  pre = '\r◊ ' + label + ': '
  post = (suffix and ' ' + suffix) + '…'
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
        yield el
      print(pre + str(i) + final, file=stderr)

  return err_progress_gen()


# errors.

def fail(*items, sep=''):
  errZ(*items, sep=sep, end='\n')
  _sys.exit(1)

def failS(*items): 
  fail(*items, sep=' ')

def failL(*items):
  fail(*items, sep='\n')

def failF(fmt, *items, **keyed_items):
  fail(fmt.format(*items, **keyed_items))


def check(condition, *items, sep=''):
  'if condition is False, fail with the provided message items.'
  if not condition: fail(*items, sep=sep)

def checkS(condition, *items):
  if not condition: failS(*items)

def checkF(condition, fmt, *items, **keyed_items):
  if not condition: failF(fmt, *items, **keyed_items)


# exceptions.

def raiseS(*items, E=Exception):
  raise E(' '.join(items))

def raiseF(fmt, *items, E=Exception):
  raise E(fmt.format(*items))


# input.


def _mk_json_types_hook(types):
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


def read_json(str_or_file, types=()):
  '''
  read json from either a string or file.
  if types is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  if isinstance(str_or_file, str):
    return _json.loads(str_or_file, object_hook=hook)
  else:
    return _json.load(str_or_file, object_hook=hook)


def read_jsons(str_or_file, types=()):
  hook = _mk_json_types_hook(types)
  if isinstance(str_or_file, str):
    string = str_or_file
  else:
    string = str_or_file.read()

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


