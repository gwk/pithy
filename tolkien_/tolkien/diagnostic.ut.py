# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

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
