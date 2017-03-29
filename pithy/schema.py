# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Generate and print informative schemas from sets of example object trees.
'''

from collections import Counter, defaultdict, namedtuple
from typing import Any, Hashable, NamedTuple, TextIO, TypeVar
from .string_utils import iter_excluding_str

K = TypeVar('K')

# TODO: mypy does not yet support NamedTuple docstrings.
'''
A schema represents the aggregate of values occurring at a structural position in some data.
atoms: counts atom values.
seqs: maps all of the occurring element types to schemas.
dicts: maps occurring keys to a defaultdict of occurring value types to schemas.
All sequence types are lumped together.
All dict classes are lumped together.
'''
class Schema(NamedTuple):
  atoms: Counter
  seqs: defaultdict
  dicts: defaultdict


def _mk_schema() -> Schema:
  return Schema(atoms=Counter(), seqs=defaultdict(_mk_schema), dicts=defaultdict(_dd_of_schemas))

def _dd_of_schemas() -> defaultdict:
  return defaultdict(_mk_schema)


def _compile_schema(node: Any, schema: Schema):
  if isinstance(node, dict):
    # dict schemas have two layers: node key and node val type.
    for k, v in node.items():
      _compile_schema(v, schema.dicts[k][type(v)])
  else:
    try:
      it = iter_excluding_str(node) # will raise TypeError if str or not iterable.
    except TypeError: # n is an atom.
      schema.atoms[node] += 1
    else: # n is iterable.
      # iterable schemas have one layer: the node element type.
      for el in it:
        _compile_schema(el, schema.seqs[type(el)])


def compile_schema(*nodes: Any, schema: Schema=None) -> Schema:
  '''
  Generate or update a `Schema` from one or more example objects.
  Each object (JSON or similar generic collections) is explored
  and type information about constituent dictionary, sequence, and atom values is saved.

  Each node of the schema represents a level of the aggregate structure.
  `Schema` objects consist of:
  * atoms: a Counter of all atoms (non-Dict, non-sequence) "leaf" values.
  * seqs: a mapping from types to element schemas.
  * dicts: a two-level mapping from keys to types to value schemas.
  '''
  if schema is None:
    schema = _mk_schema()
  for node in nodes:
    _compile_schema(node, schema)
  return schema


def _unique_el(counter: Counter) -> Any:
  'Return the first element of the counter whose count is 1.'
  for k, c in counter.items():
    if c == 1: return k
  raise ValueError(counter)


def _write_schema(f: TextIO, schema: Schema, count_atoms: bool, inline: bool, indent: str, root: bool) -> None:
  '''
  Note: _write_schema expects its caller to not have emitted a trailing newline.
  This allows it to decide whether or not to inline monomorphic type information.
  '''

  def put(*items: Any):
    print(*items, sep='', end='', file=f)

  def put_types(prefix: str, symbol: str, subindent: str, types: dict):
    for t, subschema, in sorted(types.items(), key=lambda item: item[0].__name__):
      put(prefix, symbol, t.__name__)
      _write_schema(f, subschema, count_atoms=count_atoms, inline=inline, indent=subindent, root=False)

  if not any(schema): # should only happen for root; other schemas are created on demand.
    put(indent, 'empty')
    return
  if count_atoms and schema.atoms:
    repeated_atoms = sorted(((c, v) for v, c in schema.atoms.items() if c > 1), reverse=True)
    unique_count = len(schema.atoms) - len(repeated_atoms)
    for c, v in repeated_atoms:
      put(indent, '#', c, ' ', repr(v))
    if unique_count > 1:
      put(indent, '+', unique_count)
    elif unique_count == 1: # find the unique element.
      put(indent, '#1 ', _unique_el(schema.atoms))
  if schema.seqs:
    if inline and len(schema.seqs) == 1 and not schema.atoms and not schema.dicts:
      prefix = ('' if root else ' ')
    else:
      prefix = indent
    put_types(prefix=prefix, symbol='* ', subindent=(indent + '| '), types=schema.seqs)
  if schema.dicts:
    for k, types in sorted(schema.dicts.items()):
      put(indent, repr(k))
      # Inlining for dictionaries is simpler, because we can always inline after the key we just emitted.
      prefix = ' ' if (inline and len(types) == 1) else indent
      put_types(prefix=prefix, symbol=': ', subindent=(indent + '. '), types=types)


def write_schema(f: TextIO, schema: Schema, count_atoms=False, inline=True, indent='', end='\n') -> None:
  '''
  Write `schema` to file `f`.
  If `count_atoms` is true, then histograms of atom values are emitted.
  If `inline` is false, then monomorphic type names are never inlined,
  resulting in longer but more regular output.
  '''
  _write_schema(f, schema=schema, count_atoms=count_atoms, inline=inline, indent='\n' + indent, root=True)
  f.write(end)

