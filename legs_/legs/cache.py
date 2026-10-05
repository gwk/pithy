# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Load generated Python lexers, compiling them only when they are stale.

`cached_lexer_class` runs `legs -if-stale`,
which skips compilation when the output file records the current hash of the grammar, the options and the legs sources.
'''

import sys
from importlib.util import module_from_spec, spec_from_file_location
from os import makedirs, PathLike
from os.path import basename, dirname
from subprocess import PIPE, run, STDOUT
from typing import cast

from . import DictLexerBase


_context_keywords_ = ['build cache', 'generated lexer', 'lexer']


def cached_lexer_class(grammar_path:str|PathLike[str], out_path:str|PathLike[str], type_prefix:str='') -> type[DictLexerBase]:
  '''
  Generate the table-driven Python lexer for the grammar at `out_path` if it is missing or stale, then load its lexer class.
  `out_path` must have the `.py` extension. Raise RuntimeError with the output of `legs` if generation fails.
  '''
  grammar_path = str(grammar_path)
  out_path = str(out_path)
  if not out_path.endswith('.py'):
    raise ValueError(f'expected a `.py` output path: {out_path!r}')
  makedirs(dirname(out_path) or '.', exist_ok=True)
  # Run the command as the console script does, so that it computes the same hash as `legs` run by hand.
  cmd = [sys.executable, '-c', 'from legs.bin.legs import main; main()', grammar_path, '-output', out_path, '-if-stale']
  if type_prefix: cmd += ['-type-prefix', type_prefix]
  result = run(cmd, stdout=PIPE, stderr=STDOUT, text=True)
  if result.returncode != 0: raise RuntimeError(f'legs failed for {grammar_path!r}:\n{result.stdout}')
  # Loading through the import machinery caches the bytecode of the tables beside the output.
  spec = spec_from_file_location('legs_cached_' + basename(out_path).removesuffix('.py'), out_path)
  assert spec and spec.loader
  module = module_from_spec(spec)
  spec.loader.exec_module(module)
  return cast(type[DictLexerBase], getattr(module, f'{type_prefix}Lexer'))
