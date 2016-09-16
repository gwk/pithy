# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
generate a schema for an object tree.
'''

from collections import defaultdict, namedtuple
from sys import stdout, stderr
from .string_utils import iter_excluding_str


# A schema represents the aggregate of values occurring at a structural position in some data.
# atoms is a set of atom values.
# seqs is a defaultdict mapping all of the occurring element types to schemas.
# (this means that all sequence types are lumped together).
# dicts is a defaultdict mapping occurring keys to a defaultdict of occurring value types to schemas.
# (all dict classes are lumped together).
Schema = namedtuple('Schema', 'atoms seqs dicts')

def _mk_schema():
  return Schema(atoms=set(), seqs=defaultdict(_mk_schema), dicts=defaultdict(_dd_of_schemas))

def _dd_of_schemas():
  return defaultdict(_mk_schema)

def _compile_schema(node, schema):
  if isinstance(node, dict):
    # dict schemas have two layers: node key and node val type.
    for k, v in node.items():
      _compile_schema(v, schema.dicts[k][type(v)])
  else:
    try:
      it = iter_excluding_str(node) # will raise TypeError if str or not iterable.
    except TypeError: # n is an atom.
      schema.atoms.add(node)
    else: # n is iterable.
      # iterable schemas have one layer: the node element type.
      for el in it:
        _compile_schema(el, schema.seqs[type(el)])


def compile_schema(*nodes, schema=None):
  if schema is None:
    schema = _mk_schema()
  for node in nodes:
    _compile_schema(node, schema)
  return schema


def write_schema(f, schema, summary=False, depth=0):
  indent = '  ' * depth

  def put(*items, indent=indent, end='\n'):
    print(indent, *items, sep='', end=end, file=f)

  def put_types(label, symbol, types: dict):
    inline = (len(types) == 1)
    if label is not None:
      put(label, end=(' ' if inline else '\n'))
    elif inline: # need the indentation.
      put(end='')
    for t, v, in sorted(types.items(), key=lambda item: item[0].__name__):
      put(symbol, t.__name__, indent=('' if inline else indent))
      write_schema(f, v, summary=summary, depth=depth+1)

  if not any(schema): # should only happen for root; other schemas are created on demand.
    put('empty')
    return
  if schema.atoms and not summary:
    put(repr(schema.atoms))
  if schema.seqs:
    put_types(label=None, symbol='-', types=schema.seqs)
  if schema.dicts:
    for k, types in sorted(schema.dicts.items()):
      put_types(label=repr(k), symbol='+', types=types)

def out_schema(schema, summary=False):
  write_schema(stdout, schema, summary=summary)

def err_schema(schema, summary=False):
  write_schema(stderr, schema, summary=summary)
