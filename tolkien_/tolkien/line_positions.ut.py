# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tolkien import Source
from utest import utest, utest_exc


def test_line_indices(text:str, line_indices:list[int]) -> None:
  'Test the line index of every position including the end, for both the str and bytes sources.'
  sources:list[Source] = [Source(name='str', text=text), Source(name='bytes', text=text.encode())]
  for source in sources:
    label = f'{source.name} {text!r}'
    for pos, line_idx in enumerate(line_indices):
      utest(line_idx, source.get_line_index, pos, _utest_label=label)
    utest_exc(IndexError(len(text)+1), source.get_line_index, len(text)+1, _utest_label=label)
    # The results must not depend on how far the newline positions have already been scanned.
    for pos, line_idx in enumerate(line_indices):
      utest(line_idx, source.get_line_index, pos, _utest_label=label + ' after complete scan')


test_line_indices('', [0])
test_line_indices('a', [0, 0])
test_line_indices('\n', [0, 0]) # The end position after a final newline is a special case: it belongs to the last line.
test_line_indices('a\nb', [0, 0, 1, 1])
test_line_indices('a\nb\nc\n', [0, 0, 1, 1, 2, 2, 2])
test_line_indices('\n\n', [0, 1, 1])
