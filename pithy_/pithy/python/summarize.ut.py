# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from pithy.python.summarize import DocsMode, ModuleSummary, SummarizeCmd
from utest import utest


def full_output(text:str, selectors:list[str]) -> str:
  summary = ModuleSummary('sample.py', text)
  with redirect_stdout(out := StringIO()):
    summary.print_full(selectors, public=False)
  return out.getvalue()


def summary_output(text:str, selectors:list[str], docs:DocsMode='none', locs:bool=False, members:bool=False) -> str:
  summary = ModuleSummary('sample.py', text, locs=locs)
  with redirect_stdout(out := StringIO()):
    summary.print_summary(selectors, docs=docs, public=False, assigns=True, members=members)
  return out.getvalue()


class_source = '''\
class Outer:
  value = 1
  def method(self): return self.value
  class Inner:
    def nested(self): pass
def other(): pass
'''

full_class = '''\
sample.py: sample, 6 lines.
1: class Outer:
2:   value = 1
3:   def method(self): return self.value
4:   class Inner:
5:     def nested(self): pass
'''

utest(full_class, full_output, class_source, ['Outer'])
utest(full_class, full_output, class_source, ['Outer', 'Outer.method', 'Outer.Inner.nested'])
utest(full_class + '6: def other(): pass\n', full_output, class_source, ['*'])
utest('''\
sample.py: sample, 6 lines.
1: class Outer:
4:   class Inner:
5:     def nested(self): pass
6: def other(): pass
''', full_output, class_source, ['Outer.Inner', 'other'])


decorated_source = '''\
@(
  decorator
)
class C:
  @property
  def first(self): return 1
  @(
    decorator
  )
  async def second(
    self, value:tuple[int,int]=(1,2),
  ) -> int:
    # A body comment is not part of the header.
    return value[0]
'''

selected_header = '''\
sample.py: sample, 14 lines.
 1: @(
 2:   decorator
 3: )
 4: class C:
 7:   @(
 8:     decorator
 9:   )
10:   async def second(
11:     self, value:tuple[int,int]=(1,2),
12:   ) -> int:
'''

utest(selected_header, summary_output, decorated_source, ['C.second'])
utest(selected_header + '''\
13:     # A body comment is not part of the header.
14:     return value[0]
''', full_output, decorated_source, ['C.second'])
utest('''\
sample.py: sample, 14 lines.
 1: @(
 2:   decorator
 3: )
 4: class C:
 5:   @property
 6:   def first(self): …
 7:   @(
 8:     decorator
 9:   )
10:   async def second(
11:     self, value:tuple[int,int]=(1,2),
12:   ) -> int:
''', summary_output, decorated_source, ['C'])

utest('''\
sample.py: sample, 8 lines.
1: @first
2: @(
3:   second
4: )
5: def f[T](value:dict[str,T], default=lambda: {'key': 1}):
''', summary_output, '''\
@first
@(
  second
)
def f[T](value:dict[str,T], default=lambda: {'key': 1}):

  # Body comment.
  return value
''', [])

utest('''\
sample.py: sample, 5 lines.
1: @(
2:   decorator
3: )
4: def f():
5:   return 1
''', full_output, '''\
@(
  decorator
)
def f():
  return 1
''', ['f'])


inline_doc_source = '''\
def f(): """First line.
Second line.
"""
'''

inline_doc_header = '''\
sample.py: sample, 3 lines.
1: def f(): """First line.
'''

utest(inline_doc_header + '2: Second line.\n3: """\n', summary_output, inline_doc_source, [], 'full')
utest(inline_doc_header, summary_output, inline_doc_source, [], 'first')
utest(inline_doc_header, summary_output, inline_doc_source, [], 'none')

utest('''\
sample.py: sample, 3 lines.
1: class C: """Class docs.
2: More docs.
3: """
''', summary_output, '''\
class C: """Class docs.
More docs.
"""
''', [], 'full')

utest('''\
sample.py: sample, 3 lines.
1: async def f(
2:   value:int,
3: ): 'Already printed.'
''', summary_output, '''\
async def f(
  value:int,
): 'Already printed.'
''', [], 'full')

utest('''\
sample.py: sample, 5 lines.
1: async def f(
2:   value:int,
3: ): """First line.
4: More docs.
5: """
''', summary_output, '''\
async def f(
  value:int,
): """First line.
More docs.
"""
''', [], 'full')

utest("sample.py: sample, 1 lines.\n1: def f(): 'Already printed.'\n", summary_output,
  "def f(): 'Already printed.'\n", [], 'full')


module_doc_source = '''\
"""

Module documentation.

More details.
"""
'''
utest('sample.py: sample, 6 lines.\n1: """\n2: \n3: Module documentation.\n4: \n5: More details.\n6: """\n',
  summary_output, module_doc_source, [], 'full')
utest("sample.py: sample, 6 lines.\n3: 'Module documentation.'…\n", summary_output, module_doc_source, [], 'first')
utest('sample.py: sample, 6 lines.\n', summary_output, module_doc_source, [], 'none')

# Escaped newlines stay on their actual source line.
utest('sample.py: sample, 1 lines.\n1: "One\\nTwo"\n', summary_output, '"One\\nTwo"\n', [], 'full')
utest("sample.py: sample, 1 lines.\n1: 'One\\nTwo'\n", summary_output, '"One\\nTwo"\n', [], 'first') # Too few source lines for a block.

concatenated_doc_source = '''\
def f():
  (
    ''
    r"First line."
    "More details."
  )
'''
utest('''\
sample.py: sample, 6 lines.
1: def f():
2:   (
3:     ''
4:     r"First line."
5:     "More details."
6:   )
''', summary_output, concatenated_doc_source, [], 'full')
utest('''\
sample.py: sample, 6 lines.
1: def f():
4:   'First line.More details.'
''', summary_output, concatenated_doc_source, [], 'first') # Adjacent literals concatenate without a newline.

utest('sample.py: sample, 1 lines.\n1: ""\n', summary_output, '""\n', [], 'full')
utest('sample.py: sample, 1 lines.\n', summary_output, '""\n', [], 'first')

# Unicode line separators in a string do not change Python source line numbers.
utest('sample.py: sample, 1 lines.\n1: "One\u2028Two"\n', summary_output, '"One\u2028Two"\n', [], 'full')


# -locs replaces the right-aligned line number with a `path:line: ` prefix.
utest('''\
sample.py: sample, 4 lines.
sample.py:1: class C:
sample.py:2:   'Docs.'
sample.py:4:   def m(self): pass
''', summary_output, "class C:\n  'Docs.'\n\n  def m(self): pass\n", [], 'full', True, True)


# Elisions are marked with the Unicode ellipsis, which is never a Python token.
# A header-line body that is just `...` or `pass` is complete, so it is kept verbatim.
elision_source = '''\
def one(): return 1
def stub(): ...
def commented():  # Trailing comment.
  return 1
def doc(): 'Header docstring.'
class C: pass
value = {
  'key': 1,
}
'''
utest('''\
sample.py: sample, 9 lines.
1: def one(): …
2: def stub(): ...
3: def commented():  # Trailing comment.
5: def doc(): 'Header docstring.'
6: class C: pass
7: value = { …
''', summary_output, elision_source, [], 'first')

# A complete one-line docstring has no ellipsis; its repr form is quoted consistently regardless of source quoting.
utest("sample.py: sample, 2 lines.\n1: def f():\n2:   'One line.'\n", summary_output, 'def f():\n  """One line."""\n', [], 'first')


# A docstring summary is the first block, up to the first blank line, which the author controls.
block_doc_source = """\
def f():
  '''
  Line one.
  Line two.

  More details.
  '''

def g():
  '''Line one.
  Line two.
  '''
"""
utest("""\
sample.py: sample, 12 lines.
 1: def f():
 3:   '''Line one.
 4:   Line two.'''…
 9: def g():
10:   '''Line one.
11:   Line two.'''
""", summary_output, block_doc_source, [], 'first')

# The default mode shows the module docstring in full and summarizes definitions.
utest("""\
sample.py: sample, 11 lines.
 1: '''
 2: Module intro.
 3: 
 4: Module details.
 5: '''
 6: def f():
 8:   'Summary.'…
""", summary_output, "'''\nModule intro.\n\nModule details.\n'''\ndef f():\n  '''\n  Summary.\n\n  Details.\n  '''\n", [], 'default')


# Without selectors or -members, a class shows a counts line for its direct members instead of listing them.
members_source = '''\
class Outer:
  value = 1
  other:int = 2
  def method(self): return self.value
  class Inner:
    def nested(self): pass
    def again(self): pass
class Empty: pass
'''
utest('''\
sample.py: sample, 8 lines.
1: class Outer:
     members: 1 method, 1 class, 2 attributes
8: class Empty: pass
''', summary_output, members_source, [])
utest('''\
sample.py: sample, 8 lines.
1: class Outer:
2:   value = 1
3:   other:int = 2
4:   def method(self): …
5:   class Inner:
6:     def nested(self): pass
7:     def again(self): pass
8: class Empty: pass
''', summary_output, members_source, [], 'none', False, True)
# Selecting a class implies its members; a nested class selected alone is shown under its context header.
utest('''\
sample.py: sample, 8 lines.
1: class Outer:
5:   class Inner:
6:     def nested(self): pass
7:     def again(self): pass
''', summary_output, members_source, ['Outer.Inner'])


# Interface summaries keep editable source paths and correct names, including selectors and dependency annotations.
with TemporaryDirectory() as tmp:
  package = Path(tmp) / 'example'
  package.mkdir()
  interface = package / '__init__.pyi'
  (package / 'helper.py').write_text('class Thing: pass\n')
  interface.write_text("'Interface module.'\nfrom pathlib import Path\nfrom .helper import Thing\n"
    "def f(path:Path, other:Thing) -> str:\n  \"\"\"Summary.\n\n  Details.\n  \"\"\"\n")
  source = package / '__init__.py'
  source.write_text("'Implementation module.'\n")
  for target in (str(package), str(interface)):
    with redirect_stdout(out := StringIO()):
      SummarizeCmd.parse([target + ':f', '-locs', '-docs', 'full', '-uses']).run()
    output = out.getvalue()
    utest(True, lambda: f'{interface}: example,' in output)
    utest(True, lambda: f'{interface}:4: def f(path:Path,' in output)
    utest(True, lambda: f'{interface}:7:   Details.' in output)
    utest(True, lambda: 'pathlib.Path' in output)
    utest(True, lambda: '.helper.Thing' in output)
    utest(False, lambda: 'Implementation module.' in output)
  with redirect_stdout(out := StringIO()):
    SummarizeCmd.parse([str(source)]).run()
  utest(True, lambda: 'Implementation module.' in out.getvalue())
  with redirect_stdout(out := StringIO()):
    SummarizeCmd.parse([str(package), '-full']).run()
  utest(True, lambda: 'Interface module.' in out.getvalue())
  utest(False, lambda: 'Implementation module.' in out.getvalue())
