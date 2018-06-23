#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from argparse import ArgumentParser, FileType, Namespace
from collections import defaultdict
from os.path import isfile as is_file, exists as path_exists
from shutil import copyfile
from sys import stderr
from typing import DefaultDict, List, Set, NoReturn, Tuple, cast

from pithy.diff import calc_diff
from ..pat import *


__all__ = ['pat_dependency', 'main']


pat_version = '0'


def main() -> None:
  parser = ArgumentParser(prog='pat', description='create or apply a .pat patch file.')
  parser.epilog = "for help with a specific command, pass '-h' to that command."

  subs = parser.add_subparsers()
  subs.required = True
  subs.dest = 'command'


  sub_create = subs.add_parser('create',
    help='[original] [modified] [patch]: create an empty .pat file at [patch] referencing [original], and copy [original] to [modified].')

  sub_create.set_defaults(handler=main_create)

  sub_create.add_argument('original',
    help='source file to use as the original (left/minus) side of the patch.')

  sub_create.add_argument('modified',
    help='path at which to copy the modified (right/plus) side of the patch; must not exist.')

  sub_create.add_argument('patch',
    help='path at which to create the new empty .pat file; must not exist.')


  sub_diff = subs.add_parser('diff',
    help='[original] [modified] [out]?: create .pat style diff between [original] and [modified], writing it to [out] or stdout.')

  sub_diff.set_defaults(handler=main_diff)

  sub_diff.add_argument('original', type=FileType('r'),
    help='source file to use as the original (left/minus) side of the patch.')

  sub_diff.add_argument('modified', type=FileType('r'),
    help='source file to use as the modified (right/plus) side of the patch.')

  sub_diff.add_argument('out', nargs='?', type=FileType('w'), default='-',
    help='output path (defaults to stdout)')

  sub_diff.add_argument('-min-context', type=int, default=3,
    help='minimum number of lines of context to show before each hunk.')


  sub_apply = subs.add_parser('apply',
    help='[patch] [out]?: apply a [patch] to the source file specified in that patch, and write it to [out] or stdout.')

  sub_apply.set_defaults(handler=main_apply)

  sub_apply.add_argument('patch', type=FileType('r'),
    help='input .pat path to apply')

  sub_apply.add_argument('out', nargs='?', type=FileType('w'), default='-',
    help='output path (defaults to stdout)')

  args = parser.parse_args()
  args.handler(args)


def main_create(args: Namespace) -> None:
  'create command entry point.'
  original = args.original
  modified = args.modified
  patch = args.patch
  if not is_file(original): exit("pat create error: 'original' is not an existing file: " + original)
  if path_exists(modified): exit("pat create error: 'modified' file already exists: " + modified)
  if path_exists(patch):    exit("pat create error: 'patch' file already exists: " + patch)
  with open(patch, 'w') as f:
    f.write('pat v' + pat_version + '\n')
    f.write(original + '\n')
  copyfile(original, modified)


def main_diff(args) -> None:
  'diff command entry point.'
  original = args.original
  modified = args.modified
  f_out = args.out
  min_context = args.min_context

  if min_context < 1: failF('min-context value must be positive.')

  if original.name.find('..') != -1:
    failF("original path cannot contain '..': {!r}", original.name)

  o_lines = original.readlines()
  m_lines = modified.readlines()

  if o_lines and not o_lines[-1].endswith('\n'):
    failF('{}:{} original document is missing final newline (not yet supported).')
  if m_lines and not m_lines[-1].endswith('\n'):
    failF('{}:{} modified document is missing final newline (not yet supported).')

  write = f_out.write

  write('pat v' + pat_version + '\n')
  write(args.original.name + '\n')

  line_indices: DefaultDict[str, Set[int]] = defaultdict(set) # maps line contents to line numbers.
  for i, line in enumerate(o_lines):
    line_indices[line].add(i)

  diff = calc_diff(o_lines, m_lines) # List of (orig, mod) pairs of ranges.

  match_o = range(0, 0) # Previous match range on original side.
  em_end_o = 0 # End index of emitted original lines, either as 'match' or 'rem' chunks.

  has_start_symbol = False
  for r_o, r_m in diff:
    if r_o and r_m: # match range.
      match_o = r_o
      continue
    if not (r_o or r_m): # no-op.
      continue
    # Calculate how much context we need for this hunk to be unambiguous.
    # Work backwards from the end of either the current removed range or the previous match range.
    end_o = (r_o or match_o).stop
    last_o = end_o - 1
    matching_indices = line_indices[o_lines[last_o]] if (last_o >= 0) else set()
    # Iterate back through the first line of context.
    i = em_end_o
    for i in reversed(range(em_end_o, last_o)):
      decr_indices = [j-1 for j in matching_indices] # step all candidates backwards.
      curr_indices = line_indices[o_lines[i]]
      matching_indices = curr_indices.intersection(decr_indices)
      if len(matching_indices) == 1:
        break
    ctx_start_o = max(em_end_o, min(i, end_o - min_context))
    #errFL('* ci:{}', ci)
    if ctx_start_o == 0 and not has_start_symbol:
      has_start_symbol = True
      write('\n|^\n') # Add first separator line and start-of-file symbol line.
    elif em_end_o < ctx_start_o: # Not merged with previous hunk; separate with blank line.
      write('\n')
    # Output context and diff.
    for o in range(ctx_start_o, match_o.stop):
      write('| ' + o_lines[o]) # write context lines.
    for o in r_o:
      write('- ' + o_lines[o]) # remove lines from original.
    for m in r_m:
      write('+ ' + m_lines[m]) # add lines from modified.
    em_end_o = end_o


# version pattern is applied to the first line of documents;
# programs processing input strings may or may not check for a version as appropriate.
version_re = re.compile(r'pat v(\d+)\n')

def main_apply(args) -> None:
  'apply command entry point.'
  f_patch = args.patch
  f_out = args.out

  def patch_failF(line_num, fmt, *items) -> NoReturn:
    failF('{}:{}: ' + fmt, f_patch.name, line_num + 1, *items)

  version_line = f_patch.readline()
  orig_path_line = f_patch.readline()
  patch_lines = f_patch.readlines()

  m = version_re.fullmatch(version_line)
  if not m:
    patch_failF(0, 'first line should specify pat version matching pattern: {!r}\n  found: {!r}',
      version_re.pattern, version_line)
  version = m.group(1)
  if version != pat_version: patch_failF(0, 'unsupported version number: {}', version)

  if not orig_path_line:
    patch_failF(1, 'patch file does not specify an original path')
  orig_path = orig_path_line.rstrip()

  if orig_path.find('..') != -1:
    patch_failF(1, "original path cannot contain '..': {!r}", orig_path)

  try: f_orig = open(orig_path)
  except FileNotFoundError: patch_failF(1, 'could not open source path specified by patch: {!r}', orig_path)

  orig_lines = f_orig.readlines()

  orig_line_indices: DefaultDict[str, Set[int]] = defaultdict(set)
  for i, line in enumerate(orig_lines):
    orig_line_indices[line].add(i)

  len_orig = len(orig_lines)
  orig_index = 0
  def orig_line() -> str: return orig_lines[orig_index]

  for pi, patch_line in enumerate(patch_lines, 2): # advance two lines.
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


if __name__ == '__main__': main()
