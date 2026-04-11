# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Render JSON-like data trees (dicts, lists, and leaf values) to human-readable indented strings.
'''

from typing import Any


def render_datatree(tree:Any, indent:int=0, mapping_symbol:str='*', sequence_symbol:str='') -> str:
  '''
  Recursively render a JSON-like data tree to a human-readable string.
  `indent` is the initial indent depth; uses two space indents.
  `mapping_symbol` is the line prefix for mapping key/value items; defaults to `*`.
  `sequence_symbol` is the line prefix for sequence items; if empty (the default), items are numbered and right-justified.
  '''
  out:list[str] = []
  _render(out, tree, indent, mapping_symbol, sequence_symbol)
  return ''.join(out)


def _render(out:list[str], tree:Any, indent:int, mapping_symbol:str, sequence_symbol:str) -> None:
  prefix = '  ' * indent
  if isinstance(tree, dict):
    for k, v in tree.items():
      key_str = k if (isinstance(k, str) and k.isidentifier()) else repr(k)
      out.append(f'{prefix}{mapping_symbol} {key_str}:')
      _render_value(out, v, indent, mapping_symbol, sequence_symbol)
  elif isinstance(tree, (list, tuple)):
    n = len(tree)
    if sequence_symbol:
      for item in tree:
        out.append(f'{prefix}{sequence_symbol}')
        _render_value(out, item, indent, mapping_symbol, sequence_symbol)
    else:
      width = len(str(n-1)) if n > 0 else 1
      for idx, item in enumerate(tree):
        out.append(f'{prefix}{idx:>{width}}.')
        _render_value(out, item, indent, mapping_symbol, sequence_symbol)
  else:
    out.append(f'{prefix}{tree!r}\n')


def _render_value(out:list[str], v:Any, indent:int, mapping_symbol:str, sequence_symbol:str) -> None:
  if isinstance(v, (dict, list, tuple)) and v:
    out.append('\n')
    _render(out, v, indent+1, mapping_symbol, sequence_symbol)
  else:
    out.append(f' {v!r}\n')
