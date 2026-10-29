# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from difflib import unified_diff
from io import StringIO

from pithy.ansi import strip_ctrl_seq
from taptools.bin.same_same import C_ADD_MOVED, C_ADD_TOKEN, C_END, C_REM_MOVED, C_REM_SPACE, C_REM_TOKEN, highlight_diff
from utest import utest, utest_val_ne


def highlight(text:str, interactive:bool=False) -> str:
  output = StringIO()
  with redirect_stdout(output):
    highlight_diff(StringIO(text), interactive=interactive)
  return output.getvalue()


def highlight_plain(text:str, interactive:bool=False) -> str:
  'Return highlighted output with terminal control sequences removed.'
  return strip_ctrl_seq(highlight(text, interactive=interactive))


def highlight_line_count(text:str, interactive:bool=False) -> int:
  'Return the number of output lines for a diff.'
  return len(highlight(text, interactive=interactive).splitlines())


branches = '+ \x1b[36mdev1\x1b[m\n  topic\x1b[m\n* \x1b[32mmain\x1b[m\n  pool\x1b[m\n'
utest(branches, highlight, branches)

prose = '    Indented message.\n+ Added a feature.\n- Removed a feature.\ndiff  is a word.\n  No final newline.'
utest(prose, highlight, prose)

header = 'diff --git example.txt example.txt\nindex 1234567..abcdef0 100644\n--- example.txt\n+++ example.txt\n'
hunk = '@@ -1 +1 @@\n-old\n+new\n'
diff = header + hunk
rendered = highlight(diff)
utest(True, str.startswith, rendered, '\x1b[', _utest_label='diff still receives highlighting')
utest(True, str.__contains__, rendered, 'example.txt:1:', _utest_label='hunk location is rendered')
utest(False, str.__contains__, rendered, '\n-old\n', _utest_label='diff prefixes are removed')

commit = 'commit ' + 'a' * 40 + '\nAuthor: Example\nDate: Today\n\n    Message.\n\n'
utest(commit + rendered + '\n' + commit + rendered, highlight, commit + diff + '\n' + commit + diff)
utest(rendered + rendered, highlight, diff + diff)
utest(rendered + '\n' + prose, highlight, diff + '\n' + prose)

graph = '* ' + commit + ''.join('| ' + line for line in diff.splitlines(keepends=True))
utest(graph, highlight, graph)

utest(hunk, highlight, hunk)
interactive = highlight(hunk, interactive=True)
utest(True, str.startswith, interactive, '@@ -1 +1 @@\n', _utest_label='interactive hunk header is retained')
utest(3, highlight_line_count, hunk, interactive=True, _utest_label='interactive line count is retained')
utest_val_ne(hunk, interactive, 'interactive hunk is highlighted')

marker = '\\ No newline at end of file\n'
no_newline = header + '@@ -1 +1 @@\n-old\n' + marker + '+new\n' + marker
utest(2, str.count, highlight(no_newline), marker, _utest_label='missing-newline markers are retained')
utest(False, str.__contains__, highlight(no_newline), '+new\n',
  _utest_label='highlighting continues after a missing-newline marker')

# Hunk source text can look exactly like file headers on either side of a change.
rename_header = ('diff --git old.sql new.sql\nsimilarity index 75%\nrename from old.sql\nrename to new.sql\n'
  'index 1234567..abcdef0 100644\n--- old.sql\n+++ new.sql\n')
comments = '@@ -1,2 +1,2 @@\n--- Old comment.\n--- Another old comment.\n+++ New text.\n+++ More new text.\n'
expected = ('./old.sql -> ./new.sql:\n./new.sql: similarity index 75%\n./new.sql: rename from old.sql\n'
  './new.sql: rename to new.sql\n./new.sql:1:\n-- Old comment.\n-- Another old comment.\n++ New text.\n++ More new text.\n')
for colored in (False, True):
  comment_diff = rename_header + comments
  if colored:
    comment_diff = ''.join('\x1b[31m' + line + '\x1b[m\n' for line in comment_diff.splitlines())
  for interactive_mode in (False, True):
    result = highlight(comment_diff + diff, interactive=interactive_mode)
    plain = strip_ctrl_seq(result)
    if interactive_mode:
      utest(len((comment_diff + diff).splitlines()), highlight_line_count, comment_diff + diff, interactive=True,
        _utest_label='interactive comments retain line count')
      utest(True, str.__contains__, plain, '-- Old comment.\n-- Another old comment.\n++ New text.\n++ More new text.\n',
        _utest_label='interactive comments retain source text')
    else:
      utest(expected + strip_ctrl_seq(rendered), highlight_plain, comment_diff + diff,
        _utest_label='comments do not overwrite renamed paths or disappear')
    utest(True, str.__contains__, plain, '+++ example.txt\n' if interactive_mode else 'example.txt:1:',
      _utest_label='file header parsing resumes for the next diff')


def highlight_source(text:str) -> list[str]:
  'Return source lines from a highlighted diff of example.txt.'
  return [line for line in strip_ctrl_seq(highlight(text)).splitlines() if not line.startswith('./example.txt:')]


# Exercise real unified diffs, including empty ranges and adjacent hunks with no context.
versions = [[], ['a'], ['a', 'b'], ['a', 'b', 'c'], ['b', 'a', 'c'], ['a', 'a', 'b'],
  ['a', '', 'b', '', 'c'], ['a', 'b', 'x', 'c', 'd', 'y'], ['x', 'b', 'c', 'y']]
for old in versions:
  for new in versions:
    for context in (0, 1, 3):
      patch_lines = list(unified_diff([line + '\n' for line in old], [line + '\n' for line in new],
        fromfile='example.txt', tofile='example.txt', n=context))
      if not patch_lines: continue
      patch = 'diff --git example.txt example.txt\n' + ''.join(patch_lines)
      expected_source = [line[1:-1] for line in patch_lines[2:] if not line.startswith('@@')]
      utest(expected_source, highlight_source, patch, _utest_label=f'context={context}')
      utest(len(patch.splitlines()), highlight_line_count, patch, interactive=True,
        _utest_label=f'interactive unified diff, context={context}')

# A unique moved line anchors repeated neighbors in both directions, including changed indentation.
moved = header + '@@ -1,4 +1,4 @@\n-repeat\n-anchor\n-repeat\n stay\n+  repeat\n+  anchor\n+  repeat\n'
moved_result = highlight(moved)
for text in ('repeat', 'anchor'):
  utest(True, str.__contains__, moved_result, C_REM_MOVED + text + C_END, _utest_label='removed block is marked as moved')
  utest(True, str.__contains__, moved_result, C_ADD_MOVED + '  ' + text + C_END, _utest_label='added block is marked as moved')
utest(False, str.__contains__, moved_result, C_REM_MOVED + 'stay', _utest_label='context is not marked as moved')

# Git color settings can include bold and multiple color parameters.
bold_diff = ''.join('\x1b[1;31m' + line + '\x1b[m\n' for line in diff.splitlines())
utest(strip_ctrl_seq(rendered), highlight_plain, bold_diff)

colored_marker = '\x1b[31m' + marker.rstrip('\n') + '\x1b[m\n'
utest(highlight_plain(no_newline), highlight_plain, no_newline.replace(marker, colored_marker))

# Movement expansion stops at context, even when the neighboring text matches on both sides.
context_move = highlight(header + '@@ -1,3 +1,3 @@\n repeat\n-anchor\n-repeat\n+anchor\n+repeat\n')
utest(True, str.__contains__, context_move, '\nrepeat\n', _utest_label='context next to a moved block remains uncolored')
utest(1, str.count, context_move, C_REM_MOVED + 'repeat' + C_END, _utest_label='only the removed repeat is marked as moved')
utest(1, str.count, context_move, C_ADD_MOVED + 'repeat' + C_END, _utest_label='only the added repeat is marked as moved')

# Token highlighting distinguishes changed words and significant spaces while preserving source text.
tokens = highlight(header + '@@ -1 +1 @@\n-value = old_name\n+value = new_name\n')
utest(True, str.__contains__, tokens, C_REM_TOKEN + 'old', _utest_label='removed word is highlighted')
utest(True, str.__contains__, tokens, C_ADD_TOKEN + 'new', _utest_label='added word is highlighted')
spaces = highlight(header + '@@ -1 +1 @@\n-value  = 1\n+value = 1\n')
utest(True, str.__contains__, spaces, C_REM_SPACE + '  ', _utest_label='changed internal spaces are highlighted')
utest(['value  = 1', 'value = 1'], highlight_source, header + '@@ -1 +1 @@\n-value  = 1\n+value = 1\n')
utest(['', ''], highlight_source, header + '@@ -1 +1 @@\n-\n+\n')

# Metadata-only changes retain the information needed to understand the change.
for metadata in ('old mode 100644\nnew mode 100755\n',
 'similarity index 100%\ncopy from example.txt\ncopy to copied.txt\n',
 'dissimilarity index 100%\n'):
  metadata_diff = 'diff --git example.txt example.txt\n' + metadata
  plain_metadata = strip_ctrl_seq(highlight(metadata_diff))
  for line in metadata.splitlines():
    utest(True, str.__contains__, plain_metadata, 'example.txt: ' + line + '\n', _utest_label='metadata values are retained')
  utest(len(metadata_diff.splitlines()), highlight_line_count, metadata_diff, interactive=True,
    _utest_label='interactive metadata retains line counts')

binary = 'diff --git example.txt example.txt\nindex 1234567..abcdef0 100644\nBinary files example.txt and example.txt differ\n'
utest(True, str.endswith, highlight(binary), 'Binary files example.txt and example.txt differ\n',
  _utest_label='binary summary is retained')
utest('', highlight, '')
