# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Summarize Python modules for fast orientation.

For each module the summary prints a header line naming the file, its dotted module name and its length,
then the module docstring, then one entry per definition in source order:
* The source lines of the definition header, including every decorator and multi-line signature, each prefixed with its line number.
* The docstring, indented beneath the header without line numbers.
Module-level and class-level assignments are shown by their first source line.
Methods and nested classes are shown beneath their class; functions nested inside functions are not.

Line numbers are the gutter: every numbered line is verbatim source, so `path:line` references and `sed -n` ranges
taken from the summary are exact. Unnumbered lines are docstring text.

A target is a file, a directory, or a dotted module name, optionally followed by `:` and a comma-separated list of selectors.
A selector is a definition name, a dotted qualified name such as `Class.method`, or a glob pattern over either.
Selecting a class includes its members; selecting a member also prints the enclosing class header for context.

`-full` prints the complete source of the selected definitions, decorators included, instead of the summary.
Without selectors it prints the whole module with line numbers.

Dotted targets resolve statically through the running Python environment; see `pithy.python.package.resolve_module_installed`.
'''

import ast
from fnmatch import fnmatchcase
from io import StringIO
from sys import exit, stderr
from tokenize import COMMENT, DEDENT, generate_tokens, INDENT, NEWLINE, NL, OP
from typing import Iterator, Literal

from ..cmdparse import Cmd, flag, opt, pos
from ..fs import path_rel_to_current_or_abs
from .ast_utils import fmt_syntax_error
from .package import module_name_for_path, resolve_spec_paths, safe_path_help, SpecResolutionError, target_resolution_help


_context_keywords_ = ['api', 'ast', 'decorators', 'definitions', 'docstring', 'inspect', 'line numbers', 'outline', 'overview',
  'signature', 'source']


type DocsMode = Literal['full','first','none']
type Def = ast.FunctionDef|ast.AsyncFunctionDef|ast.ClassDef
type Assign = ast.Assign|ast.AnnAssign|ast.TypeAlias
type Member = Def|Assign


class SummarizeCmd(Cmd):
  '''
  Summarize Python modules: the line-numbered header and docstring of every definition.
  A target is a file, directory or dotted module name, optionally followed by `:` and comma-separated selectors,
  e.g. `pithy.iterable:first_el,chunk*` or `pkg/mod.py:Cls.method`.
  Numbered lines are verbatim source; unnumbered lines are docstrings.
  '''

  help_addenda = (target_resolution_help, safe_path_help)

  targets:list[str] = pos(doc='File paths, directories, or dotted module names, each with optional `:selectors`.')
  safe_path:bool = flag('-P', doc='Use safe-path target resolution.')
  full:bool = flag(doc='Print the complete source of the selected definitions, or the whole module, instead of a summary.')
  docs:DocsMode = opt(default='full', doc='How much of each docstring to show: all lines, the first line only, or none.')
  public:bool = flag(doc='Omit definitions whose names begin with an underscore.')
  assigns:bool = flag(default=True, doc='Show module and class level assignments; `-no-assigns` omits them.')


  def run(self) -> None:
    ok = True
    for spec in self.targets:
      target, _, sel_text = spec.rpartition(':')
      if not target: target, sel_text = sel_text, ''
      selectors = [s for s in sel_text.split(',') if s]
      try: paths = resolve_spec_paths(target, safe_path=self.safe_path)
      except SpecResolutionError as e: exit(f'pithy.python.summarize error: {e}')
      for path in paths:
        try: summary = ModuleSummary.from_path(path)
        except SyntaxError as e:
          print(f'pithy.python.summarize error: {fmt_syntax_error(path, e)}', file=stderr)
          ok = False
          continue
        if selectors and len(paths) == 1:
          unmatched = summary.check_selectors(selectors)
          if unmatched:
            print(f'pithy.python.summarize error: {path}: no definition matches {unmatched!r}.', file=stderr)
            ok = False
        if self.full: summary.print_full(selectors, public=self.public)
        else: summary.print_summary(selectors, docs=self.docs, public=self.public, assigns=self.assigns)
    if not ok: exit(1)


def main() -> None: SummarizeCmd.main()


class ModuleSummary:
  'A parsed module and its source lines, with methods to print summary and full views of its definitions.'

  def __init__(self, path:str, text:str) -> None:
    self.path = path_rel_to_current_or_abs(path)
    self.name = module_name_for_path(path)[0]
    self.lines = text.splitlines()
    self.tree = ast.parse(text, filename=path)
    self.width = len(str(len(self.lines)))
    self.header_ranges = definition_header_ranges(text)


  @classmethod
  def from_path(cls, path:str) -> 'ModuleSummary':
    with open(path) as f: text = f.read()
    return cls(path, text)


  def print_summary(self, selectors:list[str], *, docs:DocsMode, public:bool, assigns:bool) -> None:
    print(f'{self.path}: {self.name}, {len(self.lines)} lines.')
    if not selectors: self.print_doc(self.tree, indent=2, mode=docs)
    for member, qualname, selected in self.walk(self.tree.body, '', selectors, public=public, assigns=assigns):
      if selected:
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
          self.print_lines(self.header_range(member))
          self.print_doc(member, indent=member.col_offset+2, mode=docs)
        else:
          self.print_assign(member)
      elif isinstance(member, ast.ClassDef): # An unselected class containing selected members is shown for context.
        self.print_lines(self.header_range(member))


  def print_full(self, selectors:list[str], *, public:bool) -> None:
    print(f'{self.path}: {self.name}, {len(self.lines)} lines.')
    if not selectors:
      self.print_lines((1, len(self.lines)))
      return
    printed_through = 0
    for member, qualname, selected in self.walk(self.tree.body, '', selectors, public=public, assigns=True):
      if selected: start, end = self.full_range(member)
      elif isinstance(member, ast.ClassDef): start, end = self.header_range(member)
      else: continue
      # A selected class already includes its descendants; overlapping selectors must not repeat source lines.
      self.print_lines((max(start, printed_through + 1), end))
      printed_through = max(printed_through, end)


  def walk(self, body:list[ast.stmt], prefix:str, selectors:list[str], *, public:bool, assigns:bool
   ) -> Iterator[tuple[Member,str,bool]]:
    '''
    Yield (member, qualname, selected) for each definition and assignment, in source order.
    A selected class is yielded, and all of its members are yielded as selected.
    An unselected class is yielded as unselected only if it contains selected members, and only those members follow.
    '''
    for stmt in body:
      if isinstance(stmt, (ast.If, ast.Try, ast.TryStar, ast.With)): # Conditional definitions are summarized in place.
        for sub_body in sub_bodies(stmt):
          yield from self.walk(sub_body, prefix, selectors, public=public, assigns=assigns)
        continue
      names = member_names(stmt)
      if not names: continue
      if public and all(n.startswith('_') for n in names): continue
      if isinstance(stmt, ast.ClassDef):
        qualname = prefix + stmt.name
        if is_selected(qualname, stmt.name, selectors):
          yield stmt, qualname, True
          yield from self.walk(stmt.body, qualname + '.', [], public=public, assigns=assigns)
        else:
          members = list(self.walk(stmt.body, qualname + '.', selectors, public=public, assigns=assigns))
          if members:
            yield stmt, qualname, False
            yield from members
        continue
      if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if not assigns: continue
      assert isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign, ast.AnnAssign, ast.TypeAlias))
      if any(is_selected(prefix + n, n, selectors) for n in names):
        yield stmt, prefix + names[0], True


  def check_selectors(self, selectors:list[str]) -> list[str]:
    'Return the selectors that match no definition in the module.'
    qualnames:set[tuple[str,str]] = set()
    def collect(body:list[ast.stmt], prefix:str) -> None:
      for stmt in body:
        if isinstance(stmt, (ast.If, ast.Try, ast.TryStar, ast.With)):
          for sub_body in sub_bodies(stmt): collect(sub_body, prefix)
          continue
        for n in member_names(stmt): qualnames.add((prefix + n, n))
        if isinstance(stmt, ast.ClassDef): collect(stmt.body, prefix + stmt.name + '.')
    collect(self.tree.body, '')
    return [s for s in selectors if not any(is_selected(q, n, [s]) for q, n in qualnames)]


  def header_range(self, node:Def) -> tuple[int,int]:
    '''
    The inclusive line range of a definition header: from its first decorator through the line that ends the signature.
    If the body begins on the signature line, that whole line is included.
    '''
    return self.header_ranges[node.lineno]


  def full_range(self, node:Member) -> tuple[int,int]:
    'The inclusive line range of a definition or assignment, including decorators.'
    start = node.lineno
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
      start = self.header_range(node)[0]
    return start, node.end_lineno or node.lineno


  def print_lines(self, line_range:tuple[int,int]) -> None:
    'Print the inclusive 1-based range of source lines, each prefixed with its line number.'
    start, end = line_range
    for lineno in range(start, end + 1):
      print(f'{lineno:>{self.width}}: {self.lines[lineno-1]}')


  def print_assign(self, node:Assign) -> None:
    'Print the first source line of an assignment, marking truncation of multi-line statements.'
    suffix = ' ...' if node.end_lineno and node.end_lineno > node.lineno else ''
    print(f'{node.lineno:>{self.width}}: {self.lines[node.lineno-1]}{suffix}')


  def print_doc(self, node:ast.Module|Def, *, indent:int, mode:DocsMode) -> None:
    if mode == 'none': return
    doc = ast.get_docstring(node, clean=True)
    if not doc: return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
      doc_node = node.body[0]
      # Suppress only docstrings that were printed in full as part of the header.
      if doc_node.end_lineno is not None and doc_node.end_lineno <= self.header_range(node)[1]: return
    lines = doc.splitlines()
    if mode == 'first': lines = lines[:1]
    pad = ' ' * (self.width + 2 + indent)
    for line in lines:
      print(pad + line if line else '')


def definition_header_ranges(text:str) -> dict[int,tuple[int,int]]:
  'Map each definition line to its header range, including decorators and ending at the signature colon.'
  ranges:dict[int,tuple[int,int]] = {}
  tokens = generate_tokens(StringIO(text).readline)
  statement_start = True
  decorator_start = 0
  for token in tokens:
    if token.type in (COMMENT, NL, INDENT, DEDENT): continue
    if token.type == NEWLINE:
      statement_start = True
      continue
    if not statement_start: continue
    statement_start = False
    if token.string == '@':
      if not decorator_start: decorator_start = token.start[0]
      continue
    lineno = token.start[0]
    start = decorator_start or lineno
    decorator_start = 0
    if token.string == 'async': token = next(tokens)
    if token.string not in ('def', 'class'): continue
    depth = 0
    for token in tokens:
      if token.type != OP: continue
      if token.string in ('(', '[', '{'): depth += 1
      elif token.string in (')', ']', '}'): depth -= 1
      elif token.string == ':' and depth == 0:
        ranges[lineno] = start, token.start[0]
        break
  return ranges


def sub_bodies(stmt:ast.If|ast.Try|ast.TryStar|ast.With) -> list[list[ast.stmt]]:
  if isinstance(stmt, ast.If): return [stmt.body, stmt.orelse]
  if isinstance(stmt, ast.With): return [stmt.body]
  return [stmt.body, *(h.body for h in stmt.handlers), stmt.orelse, stmt.finalbody]


def member_names(stmt:ast.stmt) -> list[str]:
  'The names bound by a definition or a simple assignment statement; empty for other statements.'
  if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): return [stmt.name]
  if isinstance(stmt, ast.TypeAlias): return [stmt.name.id]
  if isinstance(stmt, ast.AnnAssign): return [stmt.target.id] if isinstance(stmt.target, ast.Name) else []
  if isinstance(stmt, ast.Assign):
    names:list[str] = []
    for target in stmt.targets:
      els = target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]
      names.extend(el.id for el in els if isinstance(el, ast.Name))
    return names
  return []


def is_selected(qualname:str, name:str, selectors:list[str]) -> bool:
  'Whether a definition matches any selector; an empty selector list selects everything.'
  if not selectors: return True
  return any(fnmatchcase(qualname, s) or fnmatchcase(name, s) for s in selectors)


if __name__ == '__main__': main()
