# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser
from itertools import groupby
from os import environ
from sys import stderr, stdout
from typing import Any, Dict, List, Match, Optional, Set, Tuple

from pithy.ansi import BG, cBOLD, FILL, RST, cRST_BOLD, cRST_TXT, TXT, gray26, rgb6, sanitize_for_console, sgr
from pithy.diff import calc_diff


'''
same-same is a git diff highlighter.

To use it, add the following configuration to your .gitconfig:
[core]
  pager = same-same | LESSANSIENDCHARS=mK less --RAW-CONTROL-CHARS
[interactive]
  diffFilter = same-same -interactive | LESSANSIENDCHARS=mK less --RAW-CONTROL-CHARS
[diff]
  noprefix = true
  wsErrorHighlight = none # Intraline coloring creates trouble for same-same.

To disable, set 'SAMESAME=0' in the shell environment.
To debug, set 'SAMESAME=2' in the shell environment.

For a description of LESSANSIENDCHARS, see: https://major.io/2013/05/21/handling-terminal-color-escape-sequences-in-less/
'''


class DiffLine:
  'A line of input from the traditional diff program, classfied.'

  def __init__(self, kind:str, match:Match):
    self.kind = kind # The name from `diff_pat` named capture groups.
    self.match = match
    self.old_num = 0 # 1-indexed.
    self.new_num = 0 # ".
    self.chunk_idx = 0 # Positive for rem/add.
    self.is_src = False # Is source code text; True for ctx/rem/add.
    self.text = '' # Final text for ctx/rem/add.

  @property
  def raw_text(self) -> str:
    return self.match.string # type: ignore[no-any-return]

  def set_text(self, key:str, clip:bool=False) -> None:
    text = self.match[key]
    if self.match['git_color'] or clip:
      text = clip_reset(text)
    self.text = text


def main() -> None:

  arg_parser = ArgumentParser(prog='same-same', description='Git diff filter.')
  arg_parser.add_argument('-interactive', action='store_true', help="Accommodate git's interactive mode.")
  args = arg_parser.parse_args()

  # Git can generate utf8-illegal sequences; ignore them.
  stdin = open(0, errors='replace')

  env_mode_str = environ.get('SAMESAME', '1')
  try: env_mode = int(env_mode_str)
  except ValueError:
    env_mode = 1
    errL(f'error: bad (non-integer) SAMESAME environment variable: {env_mode_str!r}')


  if env_mode == 0:
    for line in stdin:
      stdout.write(line)
    exit(0)

  dbg = (env_mode > 1)
  if dbg:
    errL("SAMESAME: DEBUG")

  # Break input into groups of lines starting with 'diff' lines.
  # Note that the first segment might begin with any kind of line.
  # As soon as a group is complete, call flush_buffer() to render them.
  buffer:List[DiffLine] = []

  def flush_buffer() -> None:
    nonlocal buffer
    if buffer:
      if dbg: errL(f'SAMESAME: FLUSH')
      handle_file_lines(buffer, interactive=args.interactive, dbg=dbg)
      buffer.clear()

  try:
    for line in stdin:
      raw_text = line.rstrip('\n')
      match = diff_pat.match(raw_text)
      assert match is not None
      kind = match.lastgroup
      assert kind is not None, match
      if dbg:
        errL(f'{kind}: {raw_text!r}')
      if kind in pass_kinds:
        flush_buffer()
        print(raw_text)
        continue
      if kind == 'diff':
        flush_buffer()
      buffer.append(DiffLine(kind, match))
  except BrokenPipeError:
    stderr.close() # Prevents warning message.
  finally:
    flush_buffer()


def handle_file_lines(lines:List[DiffLine], interactive:bool, dbg:bool) -> None:
  first = lines[0]
  kind = first.kind

  # If we are processing `git log --graph` then parsing will fail; detect and skip.
  if git_diff_graph_mode_pat.match(first.raw_text).end(): # type: ignore[union-attr]
    for line in lines: print(line.raw_text)
    return

  # Scan `lines` to build up diff structures.

  old_ctx_nums:Set[int] = set() # Line numbers of context lines.
  new_ctx_nums:Set[int] = set() # ".
  old_lines:Dict[int, DiffLine] = {} # Maps of line numbers to line structs.
  new_lines:Dict[int, DiffLine] = {} # ".
  old_uniques:Dict[str, Optional[int]] = {} # Maps unique line bodies to line numbers.
  new_uniques:Dict[str, Optional[int]] = {} # ".
  old_num = 0 # 1-indexed source line number.
  new_num = 0 # ".
  chunk_idx = 0 # Counter to differentiate chunks; becomes part of the groupby key.
  old_path = '<OLD_PATH>'
  new_path = '<NEW_PATH>'
  is_prev_add_rem = False
  is_loc_colored = False # Because git diff does not give ctx lines an sgr prefix, it seems more reliable to detect from the hunk.

  for line in lines:
    match = line.match
    kind = line.kind
    is_add_rem = (kind in ('rem', 'add'))
    # Determine if this is a new chunk.
    if not is_prev_add_rem and is_add_rem: chunk_idx += 1
    is_prev_add_rem = is_add_rem
    # Dispatch on kinds.
    if kind in ('ctx', 'rem', 'add'):
      line.is_src = True
      if kind == 'ctx':
        line.set_text(key='ctx_text', clip=is_loc_colored) # Clip is a hack; ctx lines do not have a leading color sequence.
      elif kind == 'rem':
        line.set_text(key='rem_text')
        line.chunk_idx = chunk_idx
        insert_unique_line(old_uniques, line.text, old_num)
      elif kind == 'add':
        line.set_text(key='add_text')
        line.chunk_idx = chunk_idx
        insert_unique_line(new_uniques, line.text, new_num)
      if kind in ('ctx', 'rem'):
        assert old_num not in old_lines
        assert old_num not in old_ctx_nums
        line.old_num = old_num
        old_lines[old_num] = line
        old_ctx_nums.add(old_num)
        old_num += 1
      if kind in ('ctx', 'add'):
        assert new_num not in new_lines
        assert new_num not in new_ctx_nums
        line.new_num = new_num
        new_lines[new_num] = line
        new_ctx_nums.add(new_num)
        new_num += 1
    elif kind == 'loc':
      is_loc_colored = bool(line.match['git_color'])
      o = int(match['old_num'])
      if o > 0:
        assert o > old_num, (o, old_num, match.string)
        old_num = o
      n = int(match['new_num'])
      if n > 0:
        assert n > new_num
        new_num = n
      line.set_text(key='loc')
    elif kind == 'diff': # Not the best way to parse paths, because paths with spaces are ambiguous.
      paths = clip_reset(match['diff_paths']).split(' ') # Split into words, then guess at old and new split as best we can.
      i = len(paths) // 2 # Assume that both sides have the same number of spaces between them.
      # Note: if this does not prove sufficient for file renames we could try to find a split that matches either head or tail.
      old_path = ' '.join(paths[:i])
      new_path = ' '.join(paths[i:])
    elif kind == 'old': old_path = vscode_path(clip_reset(match['old_path']).rstrip('\t'))
    elif kind == 'new': new_path = vscode_path(clip_reset(match['new_path']).rstrip('\t')) # Not sure why this trailing tab appears.
    #^ These lines are a better way to parse the paths, but are not always present (particularly when one side is /dev/null).
    #^ Since they come after the diff line, they will overwrite the previous guess.

  # Detect moved lines.

  def diff_lines_match(old_idx:int, new_idx:int) -> bool:
    if old_idx in old_ctx_nums or new_idx in new_ctx_nums: return False
    try: return old_lines[old_idx].text.strip() == new_lines[new_idx].text.strip()
    except KeyError: return False

  old_moved_nums:Set[int] = set()
  new_moved_nums:Set[int] = set()
  for body, new_idx in new_uniques.items():
    if new_idx is None: continue
    old_idx = old_uniques.get(body)
    if old_idx is None: continue
    p_o = old_idx
    p_n = new_idx
    while diff_lines_match(p_o-1, p_n-1):
      p_o -= 1
      p_n -= 1
    e_o = old_idx + 1
    e_n = new_idx + 1
    while diff_lines_match(e_o, e_n):
      e_o += 1
      e_n += 1
    old_moved_nums.update(range(p_o, e_o))
    new_moved_nums.update(range(p_n, e_n))

  # Break lines into rem/add chunks and print them.
  # While a "hunk" is a series of (possibly many) ctx/rem/add lines provided by git diff,
  # a "chunk" is either a contiguous block of rem/add lines, or else any other single line.
  # This approach simplifies the token diffing process so that it is a reasonably
  # straightforward comparison of a rem block to an add block.

  def chunk_key(line:DiffLine) -> Tuple[bool, int, bool]:
    return (line.is_src, line.chunk_idx, (line.old_num in old_moved_nums or line.new_num in new_moved_nums))

  for ((is_src, chunk_idx, is_moved), _chunk) in groupby(lines, key=chunk_key):
    chunk = list(_chunk) # We iterate over the sequence several times.
    if chunk_idx and not is_moved: # Chunk should be diffed by tokens.
      # We must ensure that the same number of lines is output, at least for `-interactive` mode.
      # Currently, we do not reorder lines at all, but that is an option for the future.
      rem_lines = [l for l in chunk if l.old_num]
      add_lines = [l for l in chunk if l.new_num]
      add_token_diffs(rem_lines, add_lines)
    elif is_src: # ctx or moved.
      for l in chunk:
        l.text = ''.join(sanitize_for_console(l.text))

    # Print lines.
    for line in chunk:
      kind = line.kind
      match = line.match
      text = line.text
      if kind == 'ctx':
        print(text)
      elif kind == 'rem':
        m = C_REM_MOVED if line.old_num in old_moved_nums else ''
        print(m, text, C_END, sep='')
      elif kind == 'add':
        m = C_ADD_MOVED if line.new_num in new_moved_nums else ''
        print(m, text, C_END, sep='')
      elif kind == 'loc':
        if interactive:
          print(text)
        else:
          new_num = match['new_num']
          snippet = clip_reset(match['parent_snippet'])
          s = ' ' + C_SNIPPET if snippet else ''
          print(C_LOC, new_path, ':', new_num, ':', s, snippet, C_END, sep='')
      elif kind == 'diff':
        msg = new_path if (old_path == new_path) else '{} -> {}'.format(old_path, new_path)
        print(C_FILE, msg, ':', C_END, sep='')
      elif kind == 'meta':
        print(C_MODE, new_path, ':', RST, ' ', line.text, sep='')
      elif kind in dropped_kinds:
        if interactive: # Cannot drop lines, because interactive mode slices the diff by line counts.
          print(C_DROPPED, line.text, RST, sep='')
      elif kind in pass_kinds:
        print(line.text)
      else:
        raise Exception('unhandled kind: {}\n{!r}'.format(kind, text))


dropped_kinds = {
  'idx', 'old', 'new'
}

pass_kinds = {
  'author', 'commit', 'date', 'empty', 'other'
}


def insert_unique_line(d:Dict[str,Optional[int]], line:str, line_num:int) -> None:
  'For the purpose of movement detection, lines are tested for uniqueness after stripping leading and trailing whitespace.'
  body = line.strip()
  if body in d: d[body] = None
  else: d[body] = line_num


def add_token_diffs(rem_lines:List[DiffLine], add_lines:List[DiffLine]) -> None:
  'Rewrite DiffLine.text values to include per-token diff highlighting.'
  r = HighlightState(lines=rem_lines, tokens=tokenize_difflines(rem_lines), hl_ctx=C_REM_CTX, hl_space=C_REM_SPACE, hl_token=C_REM_TOKEN)
  a = HighlightState(lines=add_lines, tokens=tokenize_difflines(add_lines), hl_ctx=C_ADD_CTX, hl_space=C_ADD_SPACE, hl_token=C_ADD_TOKEN)
  for r_r, r_a in calc_diff(r.tokens, a.tokens):
    if r_r and r_a: # Matching tokens; highlight as context.
      r.highlight_frags(r_r, is_ctx=True)
      a.highlight_frags(r_a, is_ctx=True)
    elif r_r: r.highlight_frags(r_r, is_ctx=False)
    elif r_a: a.highlight_frags(r_a, is_ctx=False)
  # Update the mutable lines lists.
  r.update_lines()
  a.update_lines()


H_START, H_CTX, H_SPACE, H_TOKEN = range(4)


class HighlightState:
  'HighlightState is a list of lines that have been tokenized for highlighting.'
  def __init__(self, lines:List[DiffLine], tokens:List[str], hl_ctx:str, hl_space:str, hl_token:str):
    self.lines = lines
    self.tokens = tokens
    self.hl_ctx = hl_ctx # Context highlight.
    self.hl_space = hl_space # Significant space highlight.
    self.hl_token = hl_token # Token highlighter.
    self.state = H_START
    self.line_idx = 0
    self.frags:List[List[str]] = [[] for _ in lines]

  def highlight_frags(self, rng:range, is_ctx:bool) -> None:
    for frag in self.tokens[rng.start:rng.stop]:
      line_frags = self.frags[self.line_idx]
      if frag == '\n':
        if self.state != H_CTX:
          line_frags.append(self.hl_ctx) # When combined with C_END, this highlights to end of line.
        self.state = H_START
        self.line_idx += 1
      else:
        if is_ctx:
          if self.state != H_CTX:
            self.state = H_CTX
            line_frags.append(self.hl_ctx)
        elif frag.isspace():
          if self.state == H_START: # Don't highlight spaces at the start of lines.
            self.state = H_TOKEN
            line_frags.append(self.hl_token)
          elif self.state == H_CTX:
            self.state = H_SPACE
            line_frags.append(self.hl_space)
        else:
          if self.state != H_TOKEN:
            self.state = H_TOKEN
            line_frags.append(self.hl_token)
        line_frags.extend(sanitize_for_console(frag))

  def update_lines(self) -> None:
    for line, line_frags in zip(self.lines, self.frags):
      line.text = ''.join(line_frags)


def tokenize_difflines(lines:List[DiffLine]) -> List[str]:
  'Convert the list of line texts into a single list of tokens, including newline tokens.'
  tokens:List[str] = []
  for line in lines:
    tokens.extend(m[0] for m in token_pat.finditer(line.text))
    tokens.append('\n')
  return tokens


def is_token_junk(token:str) -> bool:
  '''
  Treate newlines as tokens, but all other whitespace as junk.
  This forces the diff algorithm to respect line breaks but not get distracted aligning to whitespace.
  '''
  return token.isspace() and token != '\n'


git_diff_graph_mode_pat = re.compile(r'(?x) [ /\*\|\\]*') # space is treated as literal inside of brackets, even in extended mode.

diff_pat = re.compile(r'''(?x)
(?P<git_color> \x1b \[ \d* m)*
(?:
  (?P<empty>    $ )
| (?P<commit>   commit\ [0-9a-z]{40} )
| (?P<author>   Author: )
| (?P<date>     Date:   )
| (?P<diff>     diff\ --git\ (?P<diff_paths>.+) )
| (?P<idx>      index   )
| (?P<old>      ---     \ (?P<old_path>.+) )
| (?P<new>      \+\+\+  \ (?P<new_path>.+) )
| (?P<loc>      @@\ -(?P<old_num>\d+)(?P<old_len>,\d+)?\ \+(?P<new_num>\d+)(?P<new_len>,\d+)?\ @@
    (?:\x1b\[m)? \ ? (?:\x1b\[m)? (?P<parent_snippet>.*) ) # Note the RST SPACE RST sequence.
| (?P<ctx>      \  (?P<ctx_text>.*) )
| (?P<rem>      -  (?P<rem_text>.*) )
| (?P<add>      \+(?:\x1b\[m\x1b\[32m)? (?P<add_text>.*) ) # Hack to remove extra color sequences that git 2.19.2 shows for these lines only.
| (?P<meta>
  ( old\ mode
  | new\ mode
  | deleted\ file\ mode
  | new\ file\ mode
  | copy\ from
  | copy\ to
  | rename\ from
  | rename\ to
  | similarity\ index
  | dissimilarity\ index ) )
| (?P<other> .* )
)
''')


token_pat = re.compile(r'''(?x)
  (?:(?!_)\w)+ # Word characters, excluding underscores.
| \d+ # Numbers.
| \ + # Spaces; distinct from other whitespace.
| \t+ # Tabs; distinct from other whitespace.
| \s+ # Other whitespace.
| . # Any other single character; newlines are never present so DOTALL is irrelevant.
''')


# same-same colors.

C_FILE = sgr(BG, rgb6(1, 0, 1))
C_MODE = sgr(BG, rgb6(1, 0, 1))
C_LOC = sgr(BG, rgb6(0, 1, 2))
C_UNKNOWN = sgr(BG, rgb6(5, 0, 5))
C_SNIPPET = sgr(TXT, gray26(22))
C_DROPPED = sgr(TXT, gray26(10))

REM_BG = rgb6(1, 0, 0)
ADD_BG = rgb6(0, 1, 0)

C_REM_MOVED = sgr(BG, REM_BG, TXT, rgb6(4, 2, 0)) # Move detected.
C_ADD_MOVED = sgr(BG, ADD_BG, TXT, rgb6(2, 4, 0))

# Token highlighting.
C_REM_CTX = sgr(BG, REM_BG, cRST_TXT, cRST_BOLD)
C_ADD_CTX = sgr(BG, ADD_BG, cRST_TXT, cRST_BOLD)
C_REM_SPACE = sgr(BG, rgb6(3, 0, 0), cRST_TXT, cBOLD) # Change to space.
C_ADD_SPACE = sgr(BG, rgb6(0, 3, 0), cRST_TXT, cBOLD)
C_REM_TOKEN = sgr(BG, REM_BG, TXT, rgb6(5, 2, 3), cBOLD)
C_ADD_TOKEN = sgr(BG, ADD_BG, TXT, rgb6(2, 5, 3), cBOLD)

C_RST_TOKEN = sgr(cRST_TXT, cRST_BOLD)

C_END = FILL


def vscode_path(path:str) -> str:
  'VSCode will only recognize source locations if the path contains a slash; add "./" to plain file names.'
  if '/' in path or path.startswith('<') and path.endswith('>'): return path # Do not alter pseudo-names like <stdin>.
  return './' + path


def clip_reset(text:str) -> str:
  return text[:-len(reset_sgr)] if text.endswith(reset_sgr) else text

reset_sgr = '\x1b[m' # Git uses the short version with "0" code omitted.



def errL(*items:Any) -> None: print(*items, sep='', file=stderr)

def errSL(*items:Any) -> None: print(*items, file=stderr)


if __name__ == '__main__': main()
