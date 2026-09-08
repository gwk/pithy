# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# The characters under test are spelled as escapes; they cannot be reviewed as literals.

from pithy.strings import normalize_newlines, strip_unsafe_chars
from utest import utest


utest('a\nb', normalize_newlines, 'a\r\nb')
utest('a\nb', normalize_newlines, 'a\rb')
utest('a\nb', normalize_newlines, 'a\u2028b')
utest('a\n\nb', normalize_newlines, 'a\u2029b')
utest('a\nb\nc', normalize_newlines, 'a\r\nb\rc')
utest('a\n\nb', normalize_newlines, 'a\r\n\r\nb')


utest('ab', strip_unsafe_chars, 'a\u200bb')
utest('ab', strip_unsafe_chars, 'a\u2028b')
utest('ab', strip_unsafe_chars, 'a\u2029b')
utest('ab', strip_unsafe_chars, 'a\u202db')
utest('ab', strip_unsafe_chars, 'a\u202eb')
utest('ab', strip_unsafe_chars, 'a\ufeffb')

# Normalizing first keeps the break that stripping alone would drop.
utest('a\nb', lambda s: strip_unsafe_chars(normalize_newlines(s)), 'a\u2028b')
