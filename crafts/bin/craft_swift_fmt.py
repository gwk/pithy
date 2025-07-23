# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-swift-fmt` is a simple swift formatter.
'''

import re
from argparse import ArgumentParser, Namespace
from typing import NamedTuple

from pithy.fs import is_dir, is_file, list_dir_paths, path_name, walk_files
from pithy.io import outL, outM
from pithy.iterable import iter_interleave_sep
from pithy.task import runCO

from .. import CraftConfig, load_craft_config


def main() -> None:

  arg_parser = ArgumentParser(description='Simple swift formatter.')
  arg_parser.add_argument('paths', nargs='*', default=None, help='Paths to format.')
  arg_parser.add_argument('-dbg', action='store_true', help='Debug.')
  args = arg_parser.parse_args()

  paths = args.paths or [p for p in list_dir_paths('.') if default_path_filter(p)]
  conf = load_craft_config()

  git_status = get_git_status()
  if args.dbg: outM('git status', git_status)

  for path in walk_files(*paths, file_exts=['.swift']):
    if msg := check_git_status(git_status, path):
      outL(f'{path}: {msg}; skipping.')
      continue
    check_format_swift(args, conf, path)


def default_path_filter(path:str) -> bool:
  'By default, ignore any directories that begin with "." or "_".'
  if is_file(path, follow=True): return path.endswith('.swift')
  if not is_dir(path, follow=True): return False
  name = path_name(path)
  if not name or name[0] in ('.', '_'): return False
  return True


def get_git_status() -> dict[str,str]:
  'Return a dict of path to status.'
  gst, o = runCO(['git', 'status', '--porcelain=v1', '--untracked-files=all', '--no-renames', '-z'])
  if gst: exit('git status failed.')
  lines = o.split('\0')
  if lines and not lines[-1]: lines.pop() # Jettison trailing empty line.
  return dict(parse_git_status_line(l) for l in lines)


def parse_git_status_line(line:str) -> tuple[str,str]:
  'Return (path, status).'
  # Lines are of form 'XY path'; X is the status of the index (staged), Y is the status of the work tree (unstaged).
  # We only care about the work tree status, because those are changes that we do not want to overwrite.
  return line[3:], line[1]


def check_git_status(git_status:dict[str,str], path:str) -> str:
  'Returns an error message or the empty string for success.'
  try: s = git_status[path]
  except KeyError: return '' # Clean.
  match s:
    case ' ': return '' # Staged.
    case '?': return 'not tracked by git'
    case 'M': return 'modified in work tree'
  return f'git status: {s!r}'


class Ctx(NamedTuple):
  args:Namespace
  conf:CraftConfig
  path:str
  lines:list[str]
  clean_lines:list[str]
  dbg:bool

  def msg(self, line_idx:int, msg:str) -> None:
    outL(f'{self.path}:{line_idx+1}: {msg}')


def check_format_swift(args:Namespace, conf:CraftConfig, path:str) -> None:

  with open(path) as f:
    raw_lines = f.readlines()

  if not raw_lines: return

  lines = [l.rstrip() for l in raw_lines] # Remove all trailing whitespace.

  ctx = Ctx(args, conf, path, lines, clean_lines=[], dbg=args.dbg)

  format_swift(ctx)

  if ctx.lines == ctx.clean_lines: return

  outL(f'{ctx.path}: reformatted.')

  with open(path, 'w') as f:
    for line in ctx.clean_lines: f.write(line + '\n')
  if args.dbg:
    outM(ctx.lines)
    outM(ctx.clean_lines)
    exit(1)


def format_swift(ctx:Ctx) -> None:
  'Format lines of swift code.'
  lines = ctx.lines
  while lines and not lines[-1]: lines.pop() # Jettison empty lines at end of file.
  if not lines: return

  line_idx = check_shebang_and_copyright(ctx)
  for line_idx in range(line_idx, len(lines)):
    line = lines[line_idx]
    if not line:
      clean_line:str = line
    else:
      clean_line = format_line(ctx, line_idx, line)
    ctx.clean_lines.append(clean_line)


def check_shebang_and_copyright(ctx:Ctx) -> int:
  'Format copyright. Return end line index.'
  lines = ctx.lines
  idx = 0
  if lines[0].startswith('#!') or lines[0].startswith('// swift-tools-version:'):
    ctx.clean_lines.append(lines[0])
    idx = 1
    if len(lines) == 1: return 1 # Effectively empty.

  copyright_line = lines[idx]
  clean_copyright_line = f'// {ctx.conf.copyright}'
  if copyright_line != clean_copyright_line:
    ctx.msg(idx, 'copyright.')
    if ctx.dbg:
      outL(copyright_line)
      outL(clean_copyright_line)
  ctx.clean_lines.append(clean_copyright_line)

  return idx + 1



def format_line(ctx:Ctx, line_idx:int, line:str) -> str:
  'Format a single line of swift code.'
  words = [c for c in lexer_re.split(line) if c]
  indent_end = find_indent_end(words)

  decl_pos = find_decl(words, indent_end)
  if decl_pos is not None:
    format_decl(words, indent_end, decl_pos)

  return ''.join(words)


def find_indent_end(words:list[str]) -> int:
  'Return the index of the first word that is not whitespace.'
  for i, w in enumerate(words):
    if not w.isspace(): return i
  return len(words)


def find_decl(words:list[str], pos:int) -> int|None:
  '''
  Return the index of the first word that is a declaration keyword.
  '''
  for i in range(pos, len(words)):
    w = words[i]
    if w in decl_keywords: return i
  return None


def format_decl(words:list[str], indent_end:int, decl_pos:int) -> None:
  if decl_mods_indices := find_decl_modifiers(words, indent_end, decl_pos):
    reorder_decl_modifiers(words, *decl_mods_indices)


def find_decl_modifiers(words:list[str], indent_end:int, decl_pos:int) -> tuple[int,int]|None:
  # Find modifiers start and end.
  ms = indent_end
  while words[ms].isspace() or words[ms].startswith('@'): ms += 1
  me = ms
  while words[ms].isspace() or words[me] in modifier_keywords: me += 1
  # Because we are not really parsing, we need to be conservative.
  # If the last modifier has parenthesized arguments, we cannot easily sort it, so we back up.
  if words[me] == '(': me -= 1
  # Additionally, we have to be mindful of the trailing space.
  while ms < me and words[me-1].isspace(): me -= 1
  return (ms, me) if ms < me else None


def reorder_decl_modifiers(words:list[str], start:int, end:int) -> bool:
  assert not words[end] == '('
  mod_words = [w for w in words[start:end] if not w.isspace()] # `@` attributes and keywords.
  sorted_mod_words = sorted(mod_words, key=lmkw_order)
  if sorted_mod_words == mod_words: return False
  words[start:end] = iter_interleave_sep(sorted_mod_words, ' ')
  return True


def lmkw_order(w:str) -> int:
  '''
  Return the order of a modifier keyword.
  Words not in the dict are are `@` attributes and are ordered first.
  '''
  return modifer_keyword_orders.get(w, -1)


# Declarations keywords: https://docs.swift.org/swift-book/documentation/the-swift-programming-language/lexicalstructure/#Keywords-and-Punctuation
lexer_re = re.compile(r'''(?x)
( [\ ]+ # Spaces.
| \t+ # Tabs.
| @\w+ # At-words.
| \w+ # Words.
| \(
| \)
)''')


decl_keywords = {
  'associatedtype',
  'class',
  'deinit',
  'enum',
  'extension',
  'func',
  'import',
  'init',
  'let',
  'operator',
  'precedencegroup',
  'protocol',
  'struct',
  'subscript',
  'typealias',
  'inout',
  'var',
}


modifier_keywords_ordered = (

  'override',

  'open',
  'public',
  'internal',
  'private',
  'fileprivate',

  'final',

  'optional',
  'static',
  'dynamic', # Var.

  'convenience', # Init.
  'required', # Init.

  'indirect', # Enum.
  'lazy', # Var.
  'mutating', # Var.
  'nonmutating', # Var.
  'unowned', # Var.
  'weak', # Var.
)

modifer_keyword_orders = dict((k, i) for i, k in enumerate(modifier_keywords_ordered))

modifier_keywords = frozenset(modifier_keywords_ordered)


if __name__ == '__main__': main()
