# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Summarize Python modules for fast orientation.

For each module the summary prints a header line naming the file, its dotted module name and its length,
then the module docstring, then one entry per definition in source order:
* The source lines of the definition header, including every decorator and multi-line signature, each prefixed with its line number.
* The docstring source, including quotes and indentation, with line numbers.
Module-level and class-level assignments are shown by their first source line.
Methods and nested classes are shown beneath their class; functions nested inside functions are not.

Numbered lines preserve source text and positions, with the Unicode ellipsis marking the tool's own elisions:
* A multi-line assignment shows its first line followed by ` …`.
* A body that begins on the header line is clipped after the colon, followed by ` …`.
  A header-line docstring is kept, as is a body that is just `...` or `pass`, since those lines are complete.
* `-docs=first` shows the first nonblank docstring line as a quoted literal, followed by `…` when more content follows.
Because `…` is not a Python token, these markers are never confused with a literal `...` in the source.
Generated module headers and dependency annotations are unnumbered.
`-locs` prefixes each numbered line with `path:line: ` instead of the bare line number,
so that locations survive filtering with grep and are recognized by editors.
`-docs=full` is the default; `first` shows the quoted first line of each docstring, and `none` omits docstrings.
Docstrings on definition header lines remain visible with any mode.

A target is a file, a directory, or a dotted module name, optionally followed by `:` and a comma-separated list of selectors.
Directory and package targets omit `.ut.py` unit test files unless `-include-utests` is given.
A selector is a definition name, a dotted qualified name such as `Class.method`, or a glob pattern over either.
Selecting a class includes its members; selecting a member also prints the enclosing class header for context.
When selectors are given for a directory or package, files in which nothing matches are omitted entirely.
A selector that matches nothing across all of a target's files is an error.

`-full` prints the complete source of the selected definitions, decorators included, instead of the summary.
Without selectors it prints the whole module with line numbers.

`-uses` appends a `uses:` line to each top-level definition, listing the modules and symbols that it references,
as analyzed by `pithy.python.deps`. Callers are not shown here; query them with `pithy.python.deps -dependents`.

Dotted targets resolve statically through the running Python environment; see `pithy.python.package.resolve_module_installed`.
'''

import ast
from fnmatch import fnmatchcase
from io import StringIO
from sys import exit, stderr
from tokenize import COMMENT, DEDENT, generate_tokens, INDENT, NEWLINE, NL, OP, STRING
from typing import Iterator, Literal, NamedTuple

from ..cmdparse import Cmd, flag, opt, pos
from ..fs import path_rel_to_current_or_abs
from .ast_utils import fmt_syntax_error
from .deps import DepGraph, DepsError, fmt_deps
from .package import module_name_for_path, resolve_spec_paths, safe_path_help, SpecResolutionError, target_resolution_help


_context_keywords_ = ['api', 'ast', 'decorators', 'definitions', 'docstring', 'inspect', 'line numbers', 'outline', 'overview',
  'signature', 'source']


type DocsMode = Literal['full','first','none']
type Def = ast.FunctionDef|ast.AsyncFunctionDef|ast.ClassDef
type Assign = ast.Assign|ast.AnnAssign|ast.TypeAlias
type Member = Def|Assign

ellipsis = '…' # The Unicode ellipsis marks elisions; unlike `...` it is never a Python token.


class HeaderRange(NamedTuple):
  'The inclusive line range of a definition header, and the column of the colon that ends its signature.'
  start:int
  end:int
  colon_col:int


class SummarizeCmd(Cmd):
  '''
  Summarize Python modules: the line-numbered header and docstring of every definition.
  A target is a file, directory or dotted module name, optionally followed by `:` and comma-separated selectors,
  e.g. `pithy.iterable:first_el,chunk*` or `pkg/mod.py:Cls.method`.
  Definition headers and docstrings are shown as line-numbered source.
  '''

  help_addenda = (target_resolution_help, safe_path_help)

  targets:list[str] = pos(doc='File paths, directories, or dotted module names, each with optional `:selectors`.')
  safe_path:bool = flag('-P', doc='Use safe-path target resolution.')
  full:bool = flag(doc='Print the complete source of the selected definitions, or the whole module, instead of a summary.')
  docs:DocsMode = opt(default='full',
    doc='Docstring source: full (default), first nonblank line as a quoted literal, or none. Header lines are always shown.')
  public:bool = flag(doc='Omit definitions whose names begin with an underscore.')
  assigns:bool = flag(default=True, doc='Show module and class level assignments; `-no-assigns` omits them.')
  locs:bool = flag(doc='Prefix numbered lines with `path:line: ` so that locations survive grep filtering.')
  include_utests:bool = flag(doc='Include `.ut.py` unit test files when walking directories and packages.')
  uses:bool = flag(doc='Append a `uses:` line to each top-level definition, listing the modules and symbols it references.')


  def run(self) -> None:
    ok = True
    for spec in self.targets:
      target, _, sel_text = spec.rpartition(':')
      if not target: target, sel_text = sel_text, ''
      selectors = [s for s in sel_text.split(',') if s]
      try: paths = resolve_spec_paths(target, safe_path=self.safe_path, include_utests=self.include_utests)
      except SpecResolutionError as e: exit(f'pithy.python.summarize error: {e}')
      unmatched_all = set(selectors) # Selectors that match in none of the files.
      for path in paths:
        try: summary = ModuleSummary.from_path(path, locs=self.locs)
        except SyntaxError as e:
          print(f'pithy.python.summarize error: {fmt_syntax_error(path, e)}', file=stderr)
          ok = False
          continue
        if selectors:
          unmatched = summary.check_selectors(selectors)
          unmatched_all.intersection_update(unmatched)
          if len(paths) > 1 and len(unmatched) == len(selectors): continue # Omit files where nothing matches.
        if self.full: summary.print_full(selectors, public=self.public)
        else:
          uses = None
          if self.uses:
            # Analyze each file independently: unrelated paths can have the same dotted module name.
            graph = DepGraph(safe_path=self.safe_path)
            graph.add_file(path)
            try: uses = {sym: fmt_deps(graph, summary.name, deps) for sym, deps in graph.symbol_deps(summary.name).items() if deps}
            except DepsError as e:
              print(f'pithy.python.summarize error: {e}', file=stderr)
              ok = False
          summary.print_summary(selectors, docs=self.docs, public=self.public, assigns=self.assigns, uses=uses)
      if unmatched_all:
        desc = paths[0] if len(paths) == 1 else f'{target} ({len(paths)} files)'
        print(f'pithy.python.summarize error: {desc}: no definition matches {[s for s in selectors if s in unmatched_all]!r}.',
          file=stderr)
        ok = False
    if not ok: exit(1)


def main() -> None: SummarizeCmd.main()


class ModuleSummary:
  '''
  A parsed module and its source lines, with methods to print summary and full views of its definitions.
  `locs` selects the `path:line: ` prefix for numbered lines instead of the bare right-aligned line number.
  '''

  def __init__(self, path:str, text:str, *, locs:bool=False) -> None:
    self.path = path_rel_to_current_or_abs(path)
    self.locs = locs
    self.name = module_name_for_path(path)[0]
    self.text = text
    self.lines = text.split('\n')
    if self.lines[-1] == '': self.lines.pop()
    self.tree = ast.parse(text, filename=path)
    self.width = len(str(len(self.lines)))
    self.header_ranges = definition_header_ranges(text)


  @classmethod
  def from_path(cls, path:str, *, locs:bool=False) -> 'ModuleSummary':
    with open(path) as f: text = f.read()
    return cls(path, text, locs=locs)


  def print_summary(self, selectors:list[str], *, docs:DocsMode, public:bool, assigns:bool, uses:dict[str,str]|None=None
   ) -> None:
    '''
    Print the summary of the selected definitions.
    `uses` optionally maps top-level symbol names to preformatted dependency text, printed after each docstring.
    '''
    print(f'{self.path}: {self.name}, {len(self.lines)} lines.')
    if not selectors: self.print_doc(self.tree, mode=docs)
    for member, qualname, selected in self.walk(self.tree.body, '', selectors, public=public, assigns=assigns):
      if selected:
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
          self.print_header(member)
          self.print_doc(member, mode=docs)
          if uses and (text := uses.get(qualname)):
            print(' ' * (len(self.prefix(member.lineno)) + member.col_offset + 2) + 'uses: ' + text)
        else:
          self.print_assign(member)
      elif isinstance(member, ast.ClassDef): # An unselected class containing selected members is shown for context.
        self.print_header(member)


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
    'The inclusive line range of a definition header: from its first decorator through the line that ends the signature.'
    r = self.header_ranges[node.lineno]
    return r.start, r.end


  def full_range(self, node:Member) -> tuple[int,int]:
    'The inclusive line range of a definition or assignment, including decorators.'
    start = node.lineno
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
      start = self.header_range(node)[0]
    return start, node.end_lineno or node.lineno


  def prefix(self, lineno:int) -> str:
    'The prefix of a numbered output line: `path:line: ` with `locs`, else the right-aligned line number.'
    if self.locs: return f'{self.path}:{lineno}: '
    return f'{lineno:>{self.width}}: '


  def print_lines(self, line_range:tuple[int,int]) -> None:
    'Print the inclusive 1-based range of source lines, each prefixed with its line number.'
    start, end = line_range
    for lineno in range(start, end + 1):
      print(f'{self.prefix(lineno)}{self.lines[lineno-1]}')


  def print_header(self, node:Def) -> None:
    '''
    Print the header lines of a definition.
    A body that begins on the signature line is clipped after the colon and marked with an ellipsis,
    unless the line is already complete: a docstring, which remains visible in every docs mode,
    or a stub body consisting of just `...` or `pass`. A trailing comment is kept.
    '''
    start, end, colon_col = self.header_ranges[node.lineno]
    self.print_lines((start, end - 1))
    line = self.lines[end-1]
    rest = line[colon_col+1:].strip()
    if rest and not rest.startswith('#') and not is_complete_header_body(node, end):
      line = f'{line[:colon_col+1]} {ellipsis}'
    print(f'{self.prefix(end)}{line}')


  def print_assign(self, node:Assign) -> None:
    'Print the first source line of an assignment, marking a multi-line statement with an ellipsis.'
    suffix = f' {ellipsis}' if node.end_lineno and node.end_lineno > node.lineno else ''
    print(f'{self.prefix(node.lineno)}{self.lines[node.lineno-1]}{suffix}')


  def print_doc(self, node:ast.Module|Def, *, mode:DocsMode) -> None:
    if mode == 'none': return
    doc = ast.get_docstring(node)
    if doc is None: return
    doc_node = node.body[0]
    start, end = doc_node.lineno, doc_node.end_lineno or doc_node.lineno
    header_end = self.header_range(node)[1] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else 0
    if mode == 'first':
      assert isinstance(doc_node, ast.Expr) and isinstance(doc_node.value, ast.Constant)
      content = [line for line in doc.split('\n') if line.strip()]
      lineno = self.first_doc_line(doc_node.value)
      if not content or lineno is None or lineno <= header_end: return
      text = repr(content[0]) + (ellipsis if len(content) > 1 else '')
      print(f'{self.prefix(lineno)}{" " * doc_node.col_offset}{text}')
      return
    self.print_lines((max(start, header_end + 1), end))


  def first_doc_line(self, value:ast.Constant) -> int|None:
    'Locate the source line of the first nonblank content line of a docstring literal, without decoding escapes.'
    source = ast.get_source_segment(self.text, value)
    assert source is not None
    # Parentheses allow adjacent literals on separate lines, including their original indentation.
    for token in generate_tokens(StringIO('(' + source + ')').readline):
      if token.type != STRING: continue
      literal = token.string.lstrip('rRuU')
      quote = literal[:3] if literal.startswith(('"""', "'''")) else literal[:1]
      for offset, line in enumerate(literal[len(quote):-len(quote)].split('\n')):
        if line.strip(): return value.lineno + token.start[0] - 1 + offset
    return None


def is_complete_header_body(node:Def, header_end:int) -> bool:
  'True if the body on the header line needs no elision: it is the docstring, or the whole body is a `...` or `pass` stub.'
  first = node.body[0]
  if first.lineno != header_end: return False
  if ast.get_docstring(node) is not None: return True
  if len(node.body) != 1: return False
  if isinstance(first, ast.Pass): return True
  return isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and first.value.value is ...


def definition_header_ranges(text:str) -> dict[int,HeaderRange]:
  'Map each definition line to its header range, including decorators and ending at the signature colon.'
  ranges:dict[int,HeaderRange] = {}
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
        ranges[lineno] = HeaderRange(start, token.start[0], token.start[1])
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
