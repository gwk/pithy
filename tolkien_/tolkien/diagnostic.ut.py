# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from tolkien import Source, Token
from utest import utest


def token(pos:int, end:int) -> Token: return Token(pos=pos, end=end, mode='main', kind='word')


text = 'a © bc\nd\té f'

# Diagnostics for a bytes source match those of the equivalent str source: columns and underlines count characters, not bytes.
str_source = Source(name='test', text=text)
bytes_source = Source(name='test', text=text.encode())


def test_diagnostic(exp:str, sub:str) -> None:
  'Test the diagnostic for the first occurrence of `sub`, for both the str and bytes sources.'
  pos = text.index(sub)
  utest(exp, str_source.diagnostic, (token(pos, pos + len(sub)), 'MSG'))
  b_pos = text.encode().index(sub.encode())
  utest(exp, bytes_source.diagnostic, (token(b_pos, b_pos + len(sub.encode())), 'MSG'))


test_diagnostic('''\
test:1:1-2: MSG
| a © bc
  ~
''', 'a')

test_diagnostic('''\
test:1:3-4: MSG
| a © bc
    ~
''', '©')

test_diagnostic('''\
test:1:5-7: MSG
| a © bc
      ~~
''', 'bc')

# The newline is shown when the token includes it.
test_diagnostic('''\
test:1:5-8: MSG
| a © bc\u23ce
      ~~~
''', 'bc\n')

# Tabs are preserved in the underline indentation; the final line has no newline.
test_diagnostic('''\
test:2:3-4: MSG
| d\té f\u23ce\u0353
   \t~
''', 'é')

test_diagnostic('''\
test:2:5-6: MSG
| d\té f\u23ce\u0353
   \t  ~
''', 'f')

# A zero-length token gets a caret.
utest('''\
test:1:5: MSG
| a © bc
      ^
''', bytes_source.diagnostic, (token(5, 5), 'MSG'))

# A multiline token is reported as two diagnostics.
utest('''\
test:1:3-8: MSG
| a © bc\u23ce
    ~~~~~
test:2:1-4: ending here.
| d\té f\u23ce\u0353
  ~~~
''', bytes_source.diagnostic, (token(2, 12), 'MSG'))

# The prefix precedes the source name.
utest('''\
PRE: test:1:1: MSG
| a © bc
  ^
''', str_source.diagnostic, (token(0, 1).pos_token(), 'MSG'), prefix='PRE')


def test_ascii(exp:str, text:str, pos:int, end:int, msg:str='MSG', **source_kwargs:Any) -> None:
  'Test the diagnostic for an ASCII `text`, whose positions are the same for the str and bytes sources.'
  sources:list[Source] = [Source(text=text, **source_kwargs), Source(text=text.encode(), **source_kwargs)]
  for source in sources:
    utest(exp, source.diagnostic, (token(pos, end), msg), _utest_label=type(source.text).__name__)


# The end of text, as for `Source.eot_token`.
# Without a final newline the caret follows the last character.
test_ascii('''\
test:1:4: MSG
| a b⏎͓
     ^
''', 'a b', 3, 3, name='test')

# After a final newline the end belongs to the last line; the caret follows the newline symbol.
test_ascii('''\
test:2:3: MSG
| b⏎
    ^
''', 'a\nb\n', 4, 4, name='test')

# Empty text.
test_ascii('''\
test:1:1: MSG
| ⏎͓
  ^
''', '', 0, 0, name='test')

# A token consisting of the newline alone.
test_ascii('''\
test:1:2-3: MSG
| a⏎
   ~
''', 'a\n\nb\n', 1, 2, name='test')

# An empty line: the newline token, and a zero-length token before it.
test_ascii('''\
test:2:1-2: MSG
| ⏎
  ~
''', 'a\n\nb\n', 2, 3, name='test')

test_ascii('''\
test:2:1: MSG
| ⏎
  ^
''', 'a\n\nb\n', 2, 2, name='test')

# An empty message leaves no trailing space; a message starting with a newline is not preceded by a space.
test_ascii('''\
test:1:1-2:
| a b⏎͓
  ~
''', 'a b', 0, 1, msg='', name='test')

test_ascii('''\
test:1:1-2:
MSG
| a b⏎͓
  ~
''', 'a b', 0, 1, msg='\nMSG', name='test')

# Source options: the missing newline symbol can be disabled; the name can be empty; the line index can be offset.
test_ascii('''\
test:1:3-4: MSG
| a b
    ~
''', 'a b', 2, 3, name='test', show_missing_newline=False)

test_ascii('''\
1:3-4: MSG
| a b⏎͓
    ~
''', 'a b', 2, 3, name='')

test_ascii('''\
test:12:1-2: MSG
| b⏎͓
  ~
''', 'a\nb', 2, 3, name='test', line_idx_start=10)

# An empty source line gets a bare bar.
test_ascii('''\
test:1:1: MSG
|
  ^
''', '', 0, 0, name='test', show_missing_newline=False)

# Multiple syntax-message pairs are concatenated; None entries are skipped.
utest('''\
test:1:1-2: A
| a © bc
  ~
test:2:1-2: B
| d\té f⏎͓
  ~
''', str_source.diagnostic, (token(0, 1), 'A'), None, (token(7, 8), 'B'))

utest('', str_source.diagnostic)
utest('', str_source.diagnostic, None)
