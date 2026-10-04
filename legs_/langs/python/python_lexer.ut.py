# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Differential token checks, detailed fragments and error recovery for the Python lexer.'

import io
import tokenize
from pathlib import Path

from legs.cache import cached_lexer_class
from legs.langs.python.py_lexer import PythonLexer
from legs.langs.python.py_lexer_samples import python_samples
from legs.langs.python.py_tokenize import python_tokens
from tolkien import Source, Token
from utest import utest_run, utest_val


root = Path(__file__).resolve().parents[3]
lexer_type = cached_lexer_class(root / 'legs_/langs/python/python.legs', root / '_build/langs/python.py')


def scan(text:str|bytes) -> tuple[PythonLexer,list[Token]]:
  source = Source('test', text.encode('utf-8') if isinstance(text, str) else text)
  scanner = PythonLexer(source, lexer_type)
  tokens = list(scanner)
  pos = 0
  for token in tokens:
    utest_val(pos, token.pos, 'contiguous byte coverage')
    pos = token.end
  utest_val(len(source.text), pos, 'complete byte coverage')
  return scanner, tokens


@utest_run
def differential() -> None:
  samples = python_samples()
  for prefix in ('', 'u', 'U', 'r', 'R', 'b', 'B', 'br', 'Rb', 'f', 'F', 'fr', 'Rf', 't', 'T', 'tr', 'Rt'):
    for quote in ("'", '"', "'''", '"""'):
      samples.append(f'{prefix}{quote}abc\\n\\\\{quote}\n')
  for text in samples:
    scanner, tokens = scan(text)
    utest_val([], scanner.issues, text)
    expected = list(tokenize.generate_tokens(io.StringIO(text).readline))
    actual = list(python_tokens(scanner.source, tokens))
    utest_val([(t[:4], t.exact_type) for t in expected], [(t[:4], t.exact_type) for t in actual], text)


@utest_run
def string_fragments() -> None:
  scanner, tokens = scan("x = 'α\\n\\x41'\n")
  utest_val([], scanner.issues)
  utest_val([
    ('main', 'name', b'x'), ('main', 'space', b' '), ('main', 'op', b'='), ('main', 'space', b' '),
    ('main', 'string_start', b"'"), ('str_s', 'text', 'α'.encode()), ('str_s', 'escape_simple', b'\\n'),
    ('str_s', 'escape_hex', b'\\x41'), ('str_s', 'string_end', b"'"), ('main', 'newline', b'\n'),
    ('main', 'endmarker', b''),
  ], [(t.mode, t.kind, scanner.source.text[t.slc]) for t in tokens])


@utest_run
def invalid_and_incomplete() -> None:
  cases:list[tuple[str|bytes,tuple[str,int,int]]] = [
    ('0x', ('incomplete', 2, 2)),
    ('0xG', ('invalid', 2, 3)),
    ('1e+', ('incomplete', 3, 3)),
    ('0x12_', ('incomplete', 5, 5)),
    ('1__2', ('invalid', 2, 3)),
    ("'\\xG1'", ('invalid', 3, 4)),
    ("'\\x4", ('incomplete', 4, 4)),
    ("'abc", ('incomplete', 4, 4)),
    ('"α\\u12Z4"', ('invalid', 7, 8)),
    ("b'α'", ('invalid', 2, 4)),
    ('x = $\ny=1\n', ('invalid', 4, 5)),
    ('(x', ('incomplete', 2, 2)),
    ('x)', ('invalid', 1, 2)),
    ('f"{x', ('incomplete', 4, 4)),
    ('f"a}b"', ('invalid', 3, 4)),
    (b"'\xff'", ('invalid', 1, 2)),
    (b"'\xc3", ('incomplete', 2, 2)),
    (b'\xc3', ('incomplete', 1, 1)),
    ('\\', ('incomplete', 1, 1)),
    ('\\x', ('invalid', 1, 2)),
  ]
  for text, expected in cases:
    scanner, tokens = scan(text)
    utest_val(expected, (scanner.issues[0].kind, scanner.issues[0].pos, scanner.issues[0].end), text)
    if expected[0] == 'incomplete':
      utest_val(True, any(t.kind == 'incomplete' for t in tokens) or text in ('(x', 'f"{x'))
  scanner, tokens = scan("'bad\nx = 1\n")
  utest_val(('invalid', 4, 5), (scanner.issues[0].kind, scanner.issues[0].pos, scanner.issues[0].end))
  utest_val(True, any(t.kind == 'name' and scanner.source.text[t.slc] == b'x' for t in tokens))
  utest_val(0, scanner.issues[0].opening)


@utest_run
def every_truncation_progresses() -> None:
  text = 'f"α{{x}}{name!r:>{width}}\\u1234"\n'.encode()
  for end in range(len(text) + 1):
    scan(text[:end])
