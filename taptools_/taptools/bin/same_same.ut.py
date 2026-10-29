# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from difflib import unified_diff
from io import StringIO

from pithy.ansi import strip_ctrl_seq
from taptools.bin.same_same import C_ADD_MOVED, C_ADD_TOKEN, C_END, C_REM_MOVED, C_REM_SPACE, C_REM_TOKEN, highlight_diff
from utest import utest, utest_val


def highlight(text:str, interactive:bool=False) -> str:
  output = StringIO()
  with redirect_stdout(output):
    highlight_diff(StringIO(text), interactive=interactive)
  return output.getvalue()


branches = '+ \x1b[36mdev1\x1b[m\n  topic\x1b[m\n* \x1b[32mmain\x1b[m\n  pool\x1b[m\n'
utest(branches, highlight, branches)

prose = '    Indented message.\n+ Added a feature.\n- Removed a feature.\ndiff  is a word.\n  No final newline.'
utest(prose, highlight, prose)

header = 'diff --git example.txt example.txt\nindex 1234567..abcdef0 100644\n--- example.txt\n+++ example.txt\n'
hunk = '@@ -1 +1 @@\n-old\n+new\n'
diff = header + hunk
rendered = highlight(diff)
utest_val(True, rendered.startswith('\x1b['), 'diff still receives highlighting')
utest_val(True, 'example.txt:1:' in rendered, 'hunk location is rendered')
utest_val(False, '\n-old\n' in rendered, 'diff prefixes are removed')

commit = 'commit ' + 'a' * 40 + '\nAuthor: Example\nDate: Today\n\n    Message.\n\n'
utest(commit + rendered + '\n' + commit + rendered, highlight, commit + diff + '\n' + commit + diff)
utest(rendered + rendered, highlight, diff + diff)
utest(rendered + '\n' + prose, highlight, diff + '\n' + prose)

graph = '* ' + commit + ''.join('| ' + line for line in diff.splitlines(keepends=True))
utest(graph, highlight, graph)

utest(hunk, highlight, hunk)
interactive = highlight(hunk, interactive=True)
utest_val(True, interactive.startswith('@@ -1 +1 @@\n'), 'interactive hunk header is retained')
utest_val(3, len(interactive.splitlines()), 'interactive line count is retained')
utest_val(False, interactive == hunk, 'interactive hunk is highlighted')

marker = '\\ No newline at end of file\n'
no_newline = header + '@@ -1 +1 @@\n-old\n' + marker + '+new\n' + marker
utest_val(2, highlight(no_newline).count(marker), 'missing-newline markers are retained')
utest_val(False, '+new\n' in highlight(no_newline), 'highlighting continues after a missing-newline marker')

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
      utest_val(len((comment_diff + diff).splitlines()), len(result.splitlines()), 'interactive comments retain line count')
      utest_val(True, '-- Old comment.\n-- Another old comment.\n++ New text.\n++ More new text.\n' in plain,
        'interactive comments retain source text')
    else:
      utest_val(True, plain.startswith(expected), 'comments do not overwrite renamed paths or disappear')
    utest_val(True, 'example.txt:1:' in plain if not interactive_mode else '+++ example.txt\n' in plain,
      'file header parsing resumes for the next diff')


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
      utest_val(len(patch.splitlines()), len(highlight(patch, interactive=True).splitlines()),
        'interactive unified diffs retain line counts')

# A unique moved line anchors repeated neighbors in both directions, including changed indentation.
moved = header + '@@ -1,4 +1,4 @@\n-repeat\n-anchor\n-repeat\n stay\n+  repeat\n+  anchor\n+  repeat\n'
moved_result = highlight(moved)
for text in ('repeat', 'anchor'):
  utest_val(True, C_REM_MOVED + text + C_END in moved_result, 'removed block is marked as moved')
  utest_val(True, C_ADD_MOVED + '  ' + text + C_END in moved_result, 'added block is marked as moved')
utest_val(False, C_REM_MOVED + 'stay' in moved_result, 'context is not marked as moved')

# Git color settings can include bold and multiple color parameters.
bold_diff = ''.join('\x1b[1;31m' + line + '\x1b[m\n' for line in diff.splitlines())
utest(strip_ctrl_seq(rendered), lambda: strip_ctrl_seq(highlight(bold_diff)))

colored_marker = '\x1b[31m' + marker.rstrip('\n') + '\x1b[m\n'
utest(strip_ctrl_seq(highlight(no_newline)), lambda: strip_ctrl_seq(highlight(no_newline.replace(marker, colored_marker))))

# Movement expansion stops at context, even when the neighboring text matches on both sides.
context_move = highlight(header + '@@ -1,3 +1,3 @@\n repeat\n-anchor\n-repeat\n+anchor\n+repeat\n')
utest_val(True, '\nrepeat\n' in context_move, 'context next to a moved block remains uncolored')
utest_val(1, context_move.count(C_REM_MOVED + 'repeat' + C_END), 'only the removed repeat is marked as moved')
utest_val(1, context_move.count(C_ADD_MOVED + 'repeat' + C_END), 'only the added repeat is marked as moved')

# Token highlighting distinguishes changed words and significant spaces while preserving source text.
tokens = highlight(header + '@@ -1 +1 @@\n-value = old_name\n+value = new_name\n')
utest_val(True, C_REM_TOKEN + 'old' in tokens, 'removed word is highlighted')
utest_val(True, C_ADD_TOKEN + 'new' in tokens, 'added word is highlighted')
spaces = highlight(header + '@@ -1 +1 @@\n-value  = 1\n+value = 1\n')
utest_val(True, C_REM_SPACE + '  ' in spaces, 'changed internal spaces are highlighted')
utest(['value  = 1', 'value = 1'], highlight_source, header + '@@ -1 +1 @@\n-value  = 1\n+value = 1\n')
utest(['', ''], highlight_source, header + '@@ -1 +1 @@\n-\n+\n')

# Metadata-only changes retain the information needed to understand the change.
for metadata in ('old mode 100644\nnew mode 100755\n',
 'similarity index 100%\ncopy from example.txt\ncopy to copied.txt\n',
 'dissimilarity index 100%\n'):
  metadata_diff = 'diff --git example.txt example.txt\n' + metadata
  plain_metadata = strip_ctrl_seq(highlight(metadata_diff))
  for line in metadata.splitlines():
    utest_val(True, 'example.txt: ' + line + '\n' in plain_metadata, 'metadata values are retained')
  utest_val(len(metadata_diff.splitlines()), len(highlight(metadata_diff, interactive=True).splitlines()),
    'interactive metadata retains line counts')

binary = 'diff --git example.txt example.txt\nindex 1234567..abcdef0 100644\nBinary files example.txt and example.txt differ\n'
utest_val(True, highlight(binary).endswith('Binary files example.txt and example.txt differ\n'), 'binary summary is retained')
utest('', highlight, '')
