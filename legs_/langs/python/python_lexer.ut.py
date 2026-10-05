# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Differential token checks, detailed fragments and error recovery for the Python lexer.'

import io
import tokenize
from pathlib import Path
from typing import NamedTuple

from legs.cache import cached_lexer_class
from legs.langs.python.py_lexer import PythonLexer
from legs.langs.python.py_lexer_samples import python_samples
from legs.langs.python.py_preprocess import LexIssue, PythonPreprocessor
from legs.langs.python.py_tokenize import python_tokens
from tolkien import Source, Token
from utest import utest_run, utest_val


root = Path(__file__).resolve().parents[3]
lexer_type = cached_lexer_class(root / 'legs_/langs/python/python.legs', root / '_build/langs/python.py')

type IssueDesc = tuple[str,int,int,int|None] # (kind, pos, end, opening).
type TokenDesc = tuple[str,str,int,int] # (mode, kind, pos, end).


class Scan(NamedTuple):
  source:Source[bytes]
  issues:list[LexIssue]


def scan(text:str|bytes) -> tuple[Scan,list[Token]]:
  'Lex `text` and run the preprocessor over the tokens.'
  source = Source('test', text.encode('utf-8') if isinstance(text, str) else text)
  preprocessor = PythonPreprocessor()
  tokens = list(preprocessor(source, PythonLexer(source, lexer_type)))
  scanner = Scan(source, preprocessor.issues)
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
    ('str_s', 'escape_hex', b'\\x41'), ('str_s', 'string_end', b"'"), ('main', 'end_of_line', b''), ('main', 'newline', b'\n'),
  ], [(t.mode, t.kind, scanner.source.text[t.slc]) for t in tokens])


@utest_run
def line_structure() -> None:
  'Line structure is conveyed by the empty `end_of_line`, `indent` and `dedent` tokens; the tokens that cover text keep their kinds.'
  scanner, tokens = scan('if x:\n  # c\n  (a,\n b)\n\ny')
  utest_val([], scanner.issues)
  utest_val([
    ('name', b'if'), ('space', b' '), ('name', b'x'), ('op', b':'), ('end_of_line', b''), ('newline', b'\n'),
    ('space', b'  '), ('comment', b'# c'), ('newline', b'\n'), # A comment line has no indent and ends no logical line.
    ('indent', b''), ('space', b'  '), ('paren_o', b'('), ('name', b'a'), ('op', b','), ('newline', b'\n'), # Within brackets.
    ('space', b' '), ('name', b'b'), ('paren_c', b')'), ('end_of_line', b''), ('newline', b'\n'),
    ('newline', b'\n'), # A blank line.
    ('dedent', b''), ('name', b'y'), ('end_of_line', b''), # The last line has no line break.
  ], [(t.kind, scanner.source.text[t.slc]) for t in tokens])

  # The end of a format specification is visible from the mode of the closing token.
  scanner, tokens = scan("f'{a}{b:>3}'")
  utest_val([('main', b'}'), ('fmt_s', b'}')], [(t.mode, scanner.source.text[t.slc]) for t in tokens if t.kind == 'field_close'])


@utest_run
def invalid_and_incomplete() -> None:
  'Each case gives the text, every issue and every `invalid` or `incomplete` token.'
  cases:list[tuple[str|bytes,list[IssueDesc],list[TokenDesc]]] = [
    ('0x', [('incomplete', 2, 2, None)], [('main', 'incomplete', 0, 2)]),
    ('0xG', [('invalid', 2, 3, None)], [('main', 'incomplete', 0, 2)]),
    ('1e+', [('incomplete', 3, 3, None)], [('main', 'incomplete', 0, 3)]),
    ('0x12_', [('incomplete', 5, 5, None)], [('main', 'incomplete', 0, 5)]),
    ('1__2', [('invalid', 2, 3, None)], [('main', 'incomplete', 0, 2)]),
    ("'\\xG1'", [('invalid', 3, 4, 0)], [('str_s', 'incomplete', 1, 3)]),
    # A truncated escape and the unclosed string are reported separately, each with its own token.
    ("'\\x4", [('incomplete', 4, 4, 0), ('incomplete', 4, 4, 0)],
      [('str_s', 'incomplete', 1, 4), ('str_s', 'incomplete', 4, 4)]),
    ("'abc", [('incomplete', 4, 4, 0)], [('str_s', 'incomplete', 4, 4)]),
    ('"α\\u12Z4"', [('invalid', 7, 8, 0)], [('str_d', 'incomplete', 3, 7)]),
    # Issues that the coordinator detects in well-formed fragments have no `invalid` or `incomplete` token.
    ("b'α'", [('invalid', 2, 4, 0)], []),
    ('x = $\ny=1\n', [('invalid', 4, 5, None)], [('main', 'invalid', 4, 5)]),
    ('(x', [('incomplete', 2, 2, 0)], []),
    ('x)', [('invalid', 1, 2, None)], []),
    # The unclosed field and the unclosed string are both reported; the string yields the token.
    ('f"{x', [('incomplete', 4, 4, 2), ('incomplete', 4, 4, 0)], [('f_d', 'incomplete', 4, 4)]),
    ('f"a}b"', [('invalid', 3, 4, 0)], []),
    (b"'\xff'", [('invalid', 1, 2, 0)], [('str_s', 'invalid', 1, 2)]),
    (b"'\xc3", [('incomplete', 2, 2, 0), ('incomplete', 2, 2, 0)],
      [('str_s', 'incomplete', 1, 2), ('str_s', 'incomplete', 2, 2)]),
    (b'\xc3', [('incomplete', 1, 1, None)], [('main', 'incomplete', 0, 1)]),
    ('\\', [('incomplete', 1, 1, None)], [('main', 'incomplete', 0, 1)]),
    ('\\x', [('invalid', 1, 2, None)], [('main', 'incomplete', 0, 1)]),
    # An unescaped newline ends a single-quoted string; code lexing resumes at the newline.
    ("'bad\nx = 1\n", [('invalid', 4, 5, 0)], [('str_s', 'incomplete', 4, 4)]),
  ]
  for text, issues, error_tokens in cases:
    scanner, tokens = scan(text)
    utest_val(issues, [(i.kind, i.pos, i.end, i.opening) for i in scanner.issues], f'issues: {text!r}')
    utest_val(error_tokens, [(t.mode, t.kind, t.pos, t.end) for t in tokens if t.kind in ('invalid', 'incomplete')],
      f'error tokens: {text!r}')
  scanner, tokens = scan("'bad\nx = 1\n")
  utest_val(True, any(t.kind == 'name' and scanner.source.text[t.slc] == b'x' for t in tokens), 'recovery after newline')


@utest_run
def every_truncation_recovers() -> None:
  '''
  Truncate each sample at every byte position, including within UTF-8 sequences.
  `scan` checks that the tokens cover each prefix. The issues must be consistent with the tokens.
  '''
  texts = [*python_samples(), 'f"α{{x}}{name!r:>{width}}\\u1234"\n']
  for text in texts:
    data = text.encode()
    for end in range(len(data) + 1):
      prefix = data[:end]
      scanner, tokens = scan(prefix)
      issues = scanner.issues
      problems:list[str] = []
      if [i.pos for i in issues] != sorted(i.pos for i in issues): problems.append('The issues are not in source order.')
      for issue in issues:
        if not (0 <= issue.pos <= issue.end <= end): problems.append(f'Issue span is out of bounds: {issue}.')
        if issue.opening is not None and not (0 <= issue.opening <= issue.pos):
          problems.append(f'Issue opening is out of bounds: {issue}.')
      for token in tokens:
        if token.kind not in ('invalid', 'incomplete'): continue
        if not any(i.pos <= token.end and token.pos <= i.end for i in issues): problems.append(f'Token has no issue: {token}.')
      utest_val([], problems, f'truncation: {prefix!r}')
    utest_val([], scanner.issues, f'complete sample: {text!r}') # The last prefix is the whole sample.
