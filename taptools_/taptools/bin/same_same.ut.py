# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO

from pithy.ansi import strip_ctrl_seq
from taptools.bin.same_same import highlight_diff
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
