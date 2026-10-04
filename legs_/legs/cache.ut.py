# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'`cached_lexer_class` and the `legs -if-stale` hash line that it relies on.'

from os import stat, utime
from os.path import join
from tempfile import TemporaryDirectory

from legs.cache import cached_lexer_class
from tolkien import Source
from utest import utest, utest_exc, utest_val, utest_val_ne


def kinds(lexer_type:type, text:bytes) -> list[str]:
  return [t.kind for t in lexer_type(Source('test', text))]


with TemporaryDirectory() as tmp:
  grammar_path = join(tmp, 'g.legs')
  out_path = join(tmp, 'out/g.py')

  def write_grammar(text:str) -> None:
    with open(grammar_path, 'w') as f: f.write(text)

  def set_old_mtime() -> int:
    'Give the output a distinct old mtime, so that a rewrite is detectable.'
    utime(out_path, ns=(10**18, 10**18))
    return stat(out_path).st_mtime_ns

  write_grammar('word: $Ascii_Letter+\nspace: \\s+\n')
  utest(['word', 'space', 'word'], kinds, cached_lexer_class(grammar_path, out_path), b'ab cd')
  with open(out_path) as f: generated = f.read()
  utest_val(True, generated.splitlines()[-1].startswith('# legs-hash: '), 'hash is the last line')

  # A current output is not rewritten.
  old_mtime = set_old_mtime()
  utest(['word'], kinds, cached_lexer_class(grammar_path, out_path), b'ab')
  utest_val(old_mtime, stat(out_path).st_mtime_ns, 'current output is untouched')

  # A different option changes the hash.
  utest('XLexer', lambda: cached_lexer_class(grammar_path, out_path, type_prefix='X').__name__)
  utest_val_ne(old_mtime, stat(out_path).st_mtime_ns, 'changed option regenerates')

  # A changed grammar regenerates the output.
  cached_lexer_class(grammar_path, out_path)
  old_mtime = set_old_mtime()
  write_grammar('word: $Ascii_Letter+\nspace: \\s+\nnum: $Dec+\n')
  utest(['word', 'num'], kinds, cached_lexer_class(grammar_path, out_path), b'ab12')
  utest_val_ne(old_mtime, stat(out_path).st_mtime_ns, 'changed grammar regenerates')

  # An output without its final hash line is treated as incomplete.
  with open(out_path) as f: lines = f.readlines()
  with open(out_path, 'w') as f: f.writelines(lines[:-1])
  old_mtime = set_old_mtime()
  cached_lexer_class(grammar_path, out_path)
  utest_val_ne(old_mtime, stat(out_path).st_mtime_ns, 'truncated output regenerates')

  # Failures of `legs` and unsupported output paths are reported.
  write_grammar('word: [\n')
  utest_exc(RuntimeError, cached_lexer_class, grammar_path, out_path)
  utest_exc(ValueError("expected a `.py` output path: 'g.swift'"), cached_lexer_class, grammar_path, 'g.swift')
