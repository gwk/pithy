# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from tolkien import Diagnostic, Source, Token
from utest import utest, utest_val


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

# A multiline token is reported as two diagnostics. A tab within the token is copied into the marks.
utest('''\
test:1:3-8: MSG
| a © bc\u23ce
    ~~~~~
test:2:1-4: ending here.
| d\té f\u23ce\u0353
  ~\t~
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


# A bytes position inside a multibyte character is widened to the whole character.
split_source = Source(name='test', text='a \u00a9 \u20ac \U0001f600 b'.encode()) # Characters of 2, 3 and 4 bytes, at 2, 5 and 9.

def test_split(exp_cols:str, exp_under:str, pos:int, end:int) -> None:
  exp = f'test:1:{exp_cols}: MSG\n| a \u00a9 \u20ac \U0001f600 b\u23ce\u0353\n  {exp_under}\n'
  utest(exp, split_source.diagnostic, (token(pos, end), 'MSG'), _utest_label=f'{pos}:{end}')

test_split('3-4', '  ~', 3, 4) # The second byte alone.
test_split('3-4', '  ~', 2, 3) # The first byte alone.
test_split('3-5', '  ~~', 3, 5) # The start is widened backward.
test_split('1-4', '~~~', 0, 3) # The end is widened forward.
test_split('5-6', '    ~', 6, 7) # The middle byte of three.
test_split('7-8', '      ~~', 10, 12) # The middle bytes of four; the character is two columns wide.
test_split('3-8', '  ~~~~~~', 3, 10) # Both ends.
test_split('5', '    ^', 6, 6) # A zero-length token moves to the start of the character.

# Malformed text never raises; undecodable bytes are shown as replacement characters.
def test_malformed(exp:str, text:bytes, pos:int, end:int) -> None:
  utest(exp, Source(name='test', text=text, show_missing_newline=False).diagnostic, (token(pos, end), 'MSG'), _utest_label=repr(text))

test_malformed('test:1:2-3: MSG\n| a\ufffdb\n   ~\n', b'a\x80b', 1, 2) # A stray continuation byte.
test_malformed('test:1:3-4: MSG\n| a\ufffd\ufffdb\n    ~\n', b'a\x80\x80b', 2, 3) # No lead byte precedes the position.
test_malformed('test:1:3-4: MSG\n| a\u00a9\ufffdb\n    ~\n', b'a\xc2\xa9\x80b', 3, 4) # The preceding character is complete.
test_malformed('test:1:2-3: MSG\n| a\ufffdb\n   ~\n', b'a\xe2\x82b', 2, 3) # A truncated character is widened to its bytes.
test_malformed('test:1:2-3: MSG\n| a\ufffd\n   ~\n', b'a\xf0\x9f', 2, 3) # A character truncated by the end of text.
test_malformed('test:1:2-3: MSG\n| a\ufffdb\n   ~\n', b'a\xffb', 1, 2) # An invalid byte.


# An invalid position never raises: it is clamped to the text and noted in the message.
test_ascii('''\
test:1:3-4: MSG (invalid position 2:9; text length is 3)
| a b\u23ce\u0353
    ~
''', 'a b', 2, 9, name='test') # The end is past the text.

test_ascii('''\
test:1:4: MSG (invalid position 7:9; text length is 3)
| a b\u23ce\u0353
     ^
''', 'a b', 7, 9, name='test') # The whole token is past the text.

test_ascii('''\
test:1:1-2: MSG (invalid position -1:1; text length is 3)
| a b\u23ce\u0353
  ~
''', 'a b', -1, 1, name='test') # The start is negative.

test_ascii('''\
test:1:3: MSG (invalid position 2:1; text length is 3)
| a b\u23ce\u0353
    ^
''', 'a b', 2, 1, name='test') # The end precedes the start.

test_ascii('''\
test:1:3-4: (invalid position 2:9; text length is 3)
| a b\u23ce\u0353
    ~
''', 'a b', 2, 9, msg='', name='test') # An empty message.

# The note appears only on the first part of a multiline diagnostic.
test_ascii('''\
test:1:1-3: MSG (invalid position 0:9; text length is 3)
| a\u23ce
  ~~
test:2:1-2: ending here.
| b\u23ce\u0353
  ~
''', 'a\nb', 0, 9, name='test')


# The marks are aligned by terminal column: wide characters occupy two columns; combining marks and format characters none.
def test_width(exp_cols:str, exp_marks:str, text:str, sub:str) -> None:
  pos = text.index(sub)
  exp = f'test:1:{exp_cols}: MSG\n| {text}\n  {exp_marks}\n'
  utest(exp, Source(name='test', text=text, show_missing_newline=False).diagnostic, (token(pos, pos+len(sub)), 'MSG'),
    _utest_label=repr(text))

test_width('3-4', '    ~', '\u4e2d\u6587b', 'b') # CJK characters before the token.
test_width('2-4', ' ~~~~', 'a\u4e2d\u6587b', '\u4e2d\u6587') # CJK characters within the token.
test_width('4-5', '  ~', 'e\u0301 b', 'b') # A combining mark before the token.
test_width('1-3', '~', 'e\u0301 b', 'e\u0301') # A combining mark within the token.
test_width('2-3', ' ~', 'e\u0301 b', '\u0301') # A token of zero-width characters still gets a mark.
test_width('3-4', ' ~', 'a\u200db', 'b') # A zero-width joiner before the token.
test_width('2-3', '  ~', '\U0001f600b', 'b') # An emoji before the token.
test_width('1-4', '~\t~', 'a\tb', 'a\tb') # A tab within the token.

# The caller can supply the width function.
utest('test:1:3-4: MSG\n| \u4e2d\u6587b\u23ce\u0353\n    ~\n', Source(name='test', text='\u4e2d\u6587b').diagnostic,
  (token(2, 3), 'MSG'), char_width=lambda char: 1)


# The structured pieces.
utest_val([
  Diagnostic(prefix='PRE', name='test', line_idx=0, msg='MSG', before='a ', within='\u00a9 bc', after='',
    newline_symbol='\u23ce', is_newline_within=True),
  Diagnostic(prefix='PRE', name='test', line_idx=1, msg='ending here.', before='', within='d\t\u00e9', after=' f',
    newline_symbol='\u23ce\u0353', is_newline_within=False),
], bytes_source.diagnostics((token(2, 12), 'MSG'), None, prefix='PRE'))

d_range, d_end = bytes_source.diagnostics((token(2, 12), 'MSG'), prefix='PRE')
utest_val('PRE: test:1:3-8:', d_range.location)
utest_val((2, 7, False), (d_range.col, d_range.col_end, d_range.is_point))

d_point, = str_source.diagnostics((token(4, 4), 'MSG'))
utest_val(Diagnostic(prefix='', name='test', line_idx=0, msg='MSG', before='a \u00a9 ', within='', after='bc',
  newline_symbol='', is_newline_within=False), d_point)
utest_val('test:1:5:', d_point.location)
utest_val((4, 4, True), (d_point.col, d_point.col_end, d_point.is_point))
