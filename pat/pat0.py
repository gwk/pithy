#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
import sys

from argparse import ArgumentParser, FileType
from collections import defaultdict
from difflib import ndiff


pat_version = '0'

# version pattern is applied to the first line of documents;
# programs processing input strings may or may not check for a version as appropriate.
version_re = re.compile(r'pat v(\d+)\n')

def errF(fmt, *items):
  print(fmt.format(*items), end='', file=sys.stderr)

def errFL(fmt, *items):
  print(fmt.format(*items), file=sys.stderr)

def failF(fmt, *items):
  errFL('pat error: ' + fmt, *items)
  sys.exit(1)


def main_diff(args):
  'diff command entry point.'
  original = args.original
  modified = args.modified
  f_out = args.destination
  min_context = args.min_context

  if min_context < 1: failF('min-context value must be positive.')

  if original.name.find('..') != -1:
    failF("original path cannot contain '..': {!r}", original.name)

  o_lines = original.readlines()
  m_lines = modified.readlines()
  lines = list(ndiff(o_lines, m_lines))

  if o_lines and not o_lines[-1].endswith('\n'):
    failF('{}:{} original document is missing final newline (not yet supported).')
  if m_lines and not m_lines[-1].endswith('\n'):
    failF('{}:{} modified document is missing final newline (not yet supported).')

  # first, find hunk ranges and identical lines.
  bare_line_indices = defaultdict(set)
  hunk_ranges = []
  in_hunk = False
  hunk_start = -1
  for i, line in enumerate(lines):
    prefix = line[0]
    if line[0] in (' ', '-'): # the line is in the original document.
      bare_line = line[2:] # strip off the diff prefix character and space.
      bare_line_indices[bare_line].add(i)
    if in_hunk:
      if prefix == ' ':
        in_hunk = False
        hunk_ranges.append((hunk_start, i))
    else:
      if prefix != ' ':
        in_hunk = True
        hunk_start = i
  if in_hunk:
    hunk_ranges.append((hunk_start, len(lines)))
  
  f_out.write('pat v' + pat_version + '\n')
  f_out.write(args.original.name + '\n')

  # emit hunks with enough context lines to disambiguate identical lines.
  prev_end = 0
  for hunk_start, hunk_end in hunk_ranges:
    assert hunk_start < hunk_end
    #print('HUNK', hunk_start, hunk_end, file=sys.stderr)
    # walk back through the hunk and continue until the sequence of lines is unique.
    # algorithm begins with the set of indices for instances of start line.
    # we walk backwards, gathering lines of context, until hunk is unambiguous.
    i = hunk_end - 1 # start with last line.
    start_max = hunk_start - min_context # always iterate at least to this index.
    matching_indices = set() # track all locations that match thus far.
    last_line = lines[i]
    has_context = False
    if last_line[0] == '-':
      has_context = True
      matching_indices = bare_line_indices[last_line[2:]]
    while i > prev_end and (len(matching_indices) != 1 or i > start_max):
      # once we hit the previous end, the hunks simply merge.
      # otherwise, if we have multiple indices,
      # then the match is ambiguous and we need more context.
      i -= 1
      line = lines[i]
      prefix = line[0]
      if prefix in (' ', '-'): # line is in source document.
        line_indices = bare_line_indices[line[2:]]
        if has_context: # matching has already begun.
          # find all instances of line that precede the indices in the matching set.
          prevs = { max(0, j - 1) for j in matching_indices }
          matching_indices = line_indices.union(prevs)
        else:
          has_context = True
          matching_indices = line_indices

    assert (i == 0) or (has_context and (i in matching_indices))

    if i == 0:
      f_out.write('\n|^\n') # add first separator line and start-of-file symbol line.
    elif prev_end < i: # not merged with previous hunk; separate with blank line.
      f_out.write('\n')

    for j in range(i, hunk_end):
      line = lines[j]
      assert line.endswith('\n') # TODO: deal with final missing newline in original and modified.
      if line[0] == ' ':
        f_out.write('|')
        f_out.write(line[1:])
      else:
        f_out.write(line)
    prev_end = hunk_end


def open_orig_path(path):
  try:
   return open(path)
  except FileNotFoundError:
    pass
  if not path.startswith('/') and not path.startswith('_build/'):
    build_path = '_build/' + path
    try:
      return open(build_path)
    except FileNotFoundError:
      patch_failF(1, 'could not open source path specified by patch: {!r}\n'
        '  also could not open corresponding build path: {!r}', path, build_path)
  else:
    patch_failF(1, 'could not open source path specified by patch: {!r}', path)


def main_apply(args):
  'apply command entry point.'
  f_patch = args.patch
  f_out = args.destination

  def patch_failF(line_num, fmt, *items):
    failF('{}:{}: ' + fmt, f_patch.name, line_num + 1, *items)

  version_line = f_patch.readline()
  orig_line = f_patch.readline()
  patch_lines = f_patch.readlines()

  m = version_re.fullmatch(version_line)
  if not m:
    patch_failF(0, 'first line should specify pat version matching pattern: {!r}\n  found: {!r}',
      version_re.pattern, version_line)
  version = m.group(1)
  if version != pat_version: patch_failF(0, 'unsupported version number: {}', version)

  if not orig_line:
    patch_failF(1, 'patch file does not specify an original path')
  orig_path = orig_line.rstrip()

  if orig_path.find('..') != -1:
    failF("original path cannot contain '..': {!r}", orig_path)

  f_orig = open_orig_path(orig_path)

  orig_lines = f_orig.readlines()

  orig_line_indices = defaultdict(set)
  for i, orig_line in enumerate(orig_lines):
    orig_line_indices[orig_line].add(i)

  len_orig = len(orig_lines)
  orig_index = 0
  def orig_line(): return orig_lines[orig_index]

  for pi, patch_line in enumerate(patch_lines):
    if patch_line == '\n':
      continue
    if patch_line == '|^\n':
      if orig_index != 0:
        patch_failF(pi, 'patch start-of-file symbol `|^` may only occur at beginning of patch.')
      continue
    prefix = patch_line[0]
    line = patch_line[2:]
    if prefix == '#':
      pass
    elif prefix in '|-':
      orig_index_start = orig_index
      while orig_index < len_orig and orig_line() != line:
        f_out.write(orig_line())
        orig_index += 1
      if orig_index == len_orig:
        patch_failF(pi, 'patch context line does not match in source line range: {}-{}\n{}',
          orig_index_start + 1, orig_index + 1, patch_line)
      if prefix == '|':
        f_out.write(orig_line())
      orig_index += 1
    elif prefix == '+':
      f_out.write(line)
    else:
      patch_failF(pi, 'bad patch line prefix: {!r}',  prefix)

  while orig_index < len_orig:
    f_out.write(orig_line())
    orig_index += 1


def pat_dependencies(src_path, src_file, dir_names):
  version_line = src_file.readline()
  orig_line = src_file.readline()
  orig_path = orig_line.strip()
  return [orig_path]


def main():
  # cannot get argparse to do quite what i want, so using two parsers for now.
  parser = ArgumentParser(prog='pat', description='create or apply a .pat patch file.')
  parser.epilog = "for help with a specific command, pass '-h' to that command."

  subs = parser.add_subparsers()
  subs.required = True # unofficial workaround.
  subs.dest = 'command' # this is necessary to make `required` above work.

  sub_diff = subs.add_parser('diff',
    help='create .pat style diff between two existing source files.')
  
  sub_diff.set_defaults(handler=main_diff)
  
  sub_diff.add_argument('original', type=FileType('r'),
    help='source file to use as the basis (left/minus side) of the patch.')

  sub_diff.add_argument('modified', type=FileType('r'),
    help='source file to use as the modification (right/plus side) from which to calculate the patch.')
  
  sub_diff.add_argument('destination', nargs='?', type=FileType('w'), default='-',
    help='output path (defaults to stdout)')
  
  sub_diff.add_argument('-min-context', type=int, default=3,
    help='minimum number of lines of context to show before each hunk.')

  sub_apply = subs.add_parser('apply',
    help='apply a .pat patch file to an existing, matching source file.')
  
  sub_apply.set_defaults(handler=main_apply)
  
  sub_apply.add_argument('patch', type=FileType('r'),
    help='input .pat path to apply')
  
  sub_apply.add_argument('destination', nargs='?', type=FileType('w'), default='-',
    help='output path (defaults to stdout)')

  args = parser.parse_args()
  args.handler(args)


__all__ = ['pat_dependencies', 'main']


if __name__ == '__main__':
  main()
