# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pprint as _pp
import string as _string
import sys as _sys

from sys import stdout, stderr


def fmt_template(template, **substitutions):
  'render a template using $ syntax.'
  t = _string.Template(template)
  return t.substitute(substitutions)


# basic printing.

def writeZ(file, *items, sep='', end=''):
  "write items to file; default sep='', end=''."
  print(*items, sep=sep, end=end, file=file)

def writeS(file, *items):
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
    #file.write('\n')


# std out.

def outZ(*items, sep='', end=''):
  "write items to std out; sep='', end=''."
  print(*items, sep=sep, end=end)

def outS(*items):
  "write items to std out; sep=' ', end=''."
  print(*items, end='')

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


# std err.

def errZ(*items, sep='', end=''):
  "write items to std err; default sep='', end=''."
  print(*items, sep=sep, end=end, file=stderr)

def errS(*items):
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
