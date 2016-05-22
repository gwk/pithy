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
  f_a = args.original
  f_b = args.modified
  f_out = args.destination
  lines = list(ndiff(f_a.readlines(), f_b.readlines()))

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
    start_max = hunk_start - args.min_context # always iterate at least to this index.
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
      f_out.write('\n$\n') # add first separator line and start-of-file symbol line.
    elif prev_end < i: # not merged with pervious hunk.
      f_out.write('\n')

    for j in range(i, hunk_end):
      line = lines[j]
      if line[0] == ' ':
        f_out.write('|')
        f_out.write(line[1:])
      else:
        f_out.write(line)
    prev_end = hunk_end


def main_apply(args):
  'apply command entry point.'
  f_patch = args.patch
  f_out = args.destination

  version_line = f_patch.readline()
  src_line = f_patch.readline().rstrip()
  patch_lines = f_patch.readlines()

  m = version_re.fullmatch(version_line)
  if not m:
    failF('first line should specify pat version matching pattern: {!r}\n  found: {!r}',
      version_re.pattern, version_line)
  version = int(m.group(1))
  if version != pat_version: failF('unsupported version number: {}', version)

  if not src_line:
    failF('patch file does not specify a source path')
  src_path = src_line.rstrip()

  try:
   f_src = open(src_path)
  except FileNotFoundError:
    failF('could not open source path specified by patch: {!r}', src_path)

  src_lines = f_src.readlines()
  apply_lines(patch_lines, src_lines, f_out)


def apply_lines(patch_lines, src_lines, f_out):
  src_line_indices = defaultdict(set)
  pass


def main():
  # cannot get argparse to do quite what i want, so using two parsers for now.
  parser = ArgumentParser(prog='pat', description='create or apply a .pat patch file.')
  parser.epilog = "for help with a specific command, pass '-h' to that command."

  subs = parser.add_subparsers()
  subs.required = True
  subs.dest = 'command'

  sub_diff = subs.add_parser('diff',
    help='create .pat style diff between two existing source files.')
  
  sub_diff.set_defaults(handler=main_diff)
  
  sub_diff.add_argument('original', type=FileType('r'),
    help='source file to use as the basis (left/minus side) of the patch.')

  sub_diff.add_argument('modified', type=FileType('r'),
    help='source file to use as the modification (right/plus side) from which to calculate the patch.')
  
  sub_diff.add_argument('destination', nargs='?', type=FileType('w'), default='-',
    help='output path (defaults to stdout)')
  
  sub_diff.add_argument('-min-context', type=int, default=1,
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


__all__ = ['main']


if __name__ == '__main__':
  main()
