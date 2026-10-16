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


def summary_output(text:str, selectors:list[str], docs:DocsMode='none', locs:bool=False, members:bool=False,
 public:bool=False, assigns:bool=True) -> str:
  summary = ModuleSummary('sample.py', text, locs=locs)
  with redirect_stdout(out := StringIO()):
    summary.print_summary(selectors, docs=docs, public=public, assigns=assigns, members=members)
  return out.getvalue()


# Definitions inside with blocks retain their docstrings.
utest("sample.py: sample, 5 lines.\n1: 'Module docs.'\n\n3:   def f():\n4:     'Function docs.'\n",
  summary_output, "'Module docs.'\nwith context():\n  def f():\n    'Function docs.'\n    pass\n", [], 'first')


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


# Consecutive assignments stay compact; omitted source and blank source lines separate items.
spacing_source = "a = 1\nb = (\n  2\n)\nc = 3\n\n@decorator\ndef f():\n\n  'Docs.'\n  return a\n"
spacing_expected = """\
sample.py: sample, 11 lines.
 1: a = 1
 2: b = ( …

 5: c = 3

 7: @decorator
 8: def f():
10:   'Docs.'
      uses: a
"""
with redirect_stdout(out := StringIO()):
  summary = ModuleSummary('sample.py', spacing_source)
  summary.print_summary([], docs='first', public=False, assigns=True, uses={'f': 'a'})
utest(spacing_expected, out.getvalue)

# File separators span target arguments, in both summary and full output, without leading or trailing blank lines.
with TemporaryDirectory() as tmp:
  first = Path(tmp) / 'first.py'
  second = Path(tmp) / 'second.py'
  first.write_text('a = 1\n')
  second.write_text('b = 2\n')
  for options in ([], ['-full']):
    with redirect_stdout(out := StringIO()):
      SummarizeCmd.parse([str(first), str(second), *options]).run()
    utest(f'{first}: first, 1 lines.\n1: a = 1\n\n{second}: second, 1 lines.\n1: b = 2\n', out.getvalue)


# Attribute docstrings apply to all assignment variants and share the existing docs modes.
for declaration in ('value = 30', 'value:int = 30', 'value:int', 'type value = int', 'value = other = 30',
 'value, other = (30, 40)'):
  assignment_source = declaration + '\n"""Timeout in seconds.\n\nApplies per attempt.\n"""\n'
  header = f'sample.py: sample, 5 lines.\n1: {declaration}\n'
  for mode in ('default', 'first'):
    utest(header + "2: 'Timeout in seconds.'…\n", summary_output, assignment_source, ['value'], mode)
  utest(header, summary_output, assignment_source, ['value'], 'none')
  complete = header + '2: """Timeout in seconds.\n3: \n4: Applies per attempt.\n5: """\n'
  utest(complete, summary_output, assignment_source, ['value'], 'full')
  utest(complete, full_output, assignment_source, ['value'])

# Multiline assignments and intervening comments preserve the docstring's source location.
assignment_source = "value = (\n  30\n)\n# Units.\n\n'Timeout in seconds.'\n"
utest("sample.py: sample, 6 lines.\nsample.py:1: value = ( …\nsample.py:6: 'Timeout in seconds.'\n",
  summary_output, assignment_source, ['value'], 'default', True)
utest("sample.py: sample, 6 lines.\n1: value = (\n2:   30\n3: )\n4: # Units.\n5: \n6: 'Timeout in seconds.'\n",
  full_output, assignment_source, ['value'])

# Class members and conditional declarations retain their own documentation.
assignment_source = "class C:\n  if enabled:\n    value:int\n    'Field docs.'\n"
utest("sample.py: sample, 4 lines.\n1: class C:\n\n3:     value:int\n4:     'Field docs.'\n",
  summary_output, assignment_source, ['C.value'], 'default')
utest("sample.py: sample, 4 lines.\n1: class C:\n     members: 1 attribute\n", summary_output, assignment_source, [], 'default')
utest("sample.py: sample, 4 lines.\n1: class C:\n2:   if enabled:\n3:     value:int\n4:     'Field docs.'\n",
  full_output, assignment_source, ['C', 'C.value'])

# Only the next literal string statement in the same block is attached.
for tail in ("pass\n'Unattached.'\n", "f'Not literal.'\n", "b'Not text.'\n", "42\n'Unattached.'\n"):
  assignment_source = 'value = 1\n' + tail
  utest(f'sample.py: sample, {len(assignment_source.splitlines())} lines.\n1: value = 1\n',
    summary_output, assignment_source, ['value'], 'full')
utest("sample.py: sample, 3 lines.\n2:   value = 1\n", summary_output,
  "if enabled:\n  value = 1\n'Outside block.'\n", ['value'], 'full')
utest("sample.py: sample, 3 lines.\n1: value = 1\n2: 'First.'\n3: 'Additional.'\n", full_output,
  "value = 1\n'First.'\n'Additional.'\n", ['value'])

# Filtering assignments also filters their documentation.
with redirect_stdout(out := StringIO()):
  ModuleSummary('sample.py', "value = 1\n'Hidden.'\n").print_summary([], docs='full', public=False, assigns=False)
utest('sample.py: sample, 2 lines.\n', out.getvalue)


# Separate string statements extend documentation as paragraphs without losing source locations.
for declaration in ('value = 1', 'value:int', 'type value = int', 'def value():', 'class value:'):
  indent = '  ' if declaration.endswith(':') else ''
  additional_source = declaration + '\n' + indent + "'Summary.'\n" + indent + "'Details.'\n"
  expected_header = f'sample.py: sample, 3 lines.\n1: {declaration}\n'
  for mode in ('first', 'default'):
    utest(expected_header + f"2: {indent}'Summary.'…\n", summary_output, additional_source, ['value'], mode)
  utest(expected_header + f"2: {indent}'Summary.'\n3: {indent}'Details.'\n",
    summary_output, additional_source, ['value'], 'full')
  utest(expected_header, summary_output, additional_source, ['value'], 'none')

utest("sample.py: sample, 2 lines.\n1: 'Summary.'…\n", summary_output,
  "'Summary.'\n'Details.'\n", [], 'first')
utest("sample.py: sample, 2 lines.\n1: 'Summary.'\n2: 'Details.'\n", summary_output,
  "'Summary.'\n'Details.'\n", [], 'default')

# Empty strings do not hide later content; intervening statements end the documentation.
utest("sample.py: sample, 5 lines.\n1: value = 1\n3: 'Details.'\n", summary_output,
  "value = 1\n''\n'Details.'\npass\n'Unattached.'\n", ['value'], 'first')
utest("sample.py: sample, 5 lines.\n1: value = 1\n2: 'Summary.'\n4: 'Details.'\n", summary_output,
  "value = 1\n'Summary.'\n# More documentation.\n'Details.'\npass\n", ['value'], 'full')


# Constructor attributes retain source order, repeated declarations, and their enclosing headers.
constructor_source = """\
class C:
  value:int
  def __init__(this, /):
    this.value = 1
    'First.'
    this.value:int = 2
    'Second.'
    this.hidden = 3
"""
constructor_header = 'sample.py: sample, 8 lines.\n1: class C:\n'
constructor_entries = ("3:   def __init__(this, /):\n4:     this.value = 1\n5:     'First.'\n"
  "6:     this.value:int = 2\n7:     'Second.'\n")
utest(constructor_header + '2:   value:int\n' + constructor_entries,
  summary_output, constructor_source, ['C'], 'default')
utest(constructor_header + '2:   value:int\n' + constructor_entries,
  summary_output, constructor_source, ['C.value'], 'default')
utest(constructor_header + '\n' + constructor_entries,
  summary_output, constructor_source, ['C.__init__'], 'default')
utest(constructor_header + '     members: 1 method, 3 attributes\n', summary_output, constructor_source, [])
utest(constructor_header + '     members: 3 attributes\n', summary_output, constructor_source, [], public=True)
utest(constructor_header + '2:   value:int\n' + constructor_entries,
  summary_output, constructor_source, [], 'default', members=True, public=True)
utest(constructor_header + '\n3:   def __init__(this, /):\n',
  summary_output, constructor_source, ['C'], 'full', assigns=False)
utest(constructor_header + '2:   value:int\n3:   def __init__(this, /):\n4:     this.value = 1\n\n6:     this.value:int = 2\n',
  summary_output, constructor_source, ['C'], 'none')
utest(constructor_header + '2:   value:int\n' + constructor_entries,
  full_output, constructor_source, ['C.value'])
utest(full_output(constructor_source, ['C']), full_output, constructor_source, ['C', 'C.value', 'C.__init__'])
utest([], ModuleSummary('sample.py', constructor_source).check_selectors, ['C.value', 'value', 'C.__init__'])
utest(['C.hidden'], ModuleSummary('sample.py', constructor_source).check_selectors, ['C.hidden'])

# Only documented direct receiver assignments qualify, including private attributes and additional strings.
constructor_scope_source = """\
class C:
  def __init__(self):
    self._private = 1
    'Private.'
    self.public = 2
    'Public.'
    'Details.'
    other.value = 3
    'Other receiver.'
    local = 4
    'Local.'
    if enabled:
      self.conditional = 5
      'Conditional.'
    def nested():
      self.nested = 6
      'Nested.'
  def method(self):
    self.later = 7
    'Other method.'
"""
utest(['C.value', 'C.local', 'C.conditional', 'C.nested', 'C.later'],
  ModuleSummary('sample.py', constructor_scope_source).check_selectors,
  ['C._private', 'C.public', 'C.value', 'C.local', 'C.conditional', 'C.nested', 'C.later'])
utest("sample.py: sample, 20 lines.\nsample.py:1: class C:\nsample.py:2:   def __init__(self):\n\n"
  "sample.py:5:     self.public = 2\nsample.py:6:     'Public.'…\n",
  summary_output, constructor_scope_source, ['C.public'], 'default', locs=True, public=True)
utest('sample.py: sample, 20 lines.\n',
  summary_output, constructor_scope_source, ['C._private'], 'default', public=True)
utest("sample.py: sample, 20 lines.\n 1: class C:\n 2:   def __init__(self):\n\n"
  " 5:     self.public = 2\n 6:     'Public.'\n 7:     'Details.'\n",
  full_output, constructor_scope_source, ['C.public'])
