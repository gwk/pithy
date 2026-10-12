# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO

from pithy.python.summarize import DocsMode, ModuleSummary
from utest import utest


def full_output(text:str, selectors:list[str]) -> str:
  summary = ModuleSummary('sample.py', text)
  with redirect_stdout(out := StringIO()):
    summary.print_full(selectors, public=False)
  return out.getvalue()


def summary_output(text:str, selectors:list[str], docs:DocsMode='none', locs:bool=False) -> str:
  summary = ModuleSummary('sample.py', text, locs=locs)
  with redirect_stdout(out := StringIO()):
    summary.print_summary(selectors, docs=docs, public=False, assigns=True)
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
 6:   def first(self): return 1
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
utest('sample.py: sample, 6 lines.\n3: Module documentation.\n', summary_output, module_doc_source, [], 'first')
utest('sample.py: sample, 6 lines.\n', summary_output, module_doc_source, [], 'none')

# Escaped newlines stay on their actual source line.
utest('sample.py: sample, 1 lines.\n1: "One\\nTwo"\n', summary_output, '"One\\nTwo"\n', [], 'full')
utest('sample.py: sample, 1 lines.\n1: One\\nTwo\n', summary_output, '"One\\nTwo"\n', [], 'first')

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
4:     First line.
''', summary_output, concatenated_doc_source, [], 'first')

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
''', summary_output, "class C:\n  'Docs.'\n\n  def m(self): pass\n", [], 'full', True)
