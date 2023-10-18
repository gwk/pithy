#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from pithy.fs import move_file, path_exists
from pithy.path import norm_path, path_join, path_name_stem
from pithy.xcproj.parse import parse_pbx
from pithy.xcproj.render import render_to_str


def main() -> None:
  parser = ArgumentParser(description='Rewrite Xcode projects to match directory contents.')
  parser.add_argument('project')
  parser.add_argument('-output',
    help='Destination for rewritten project. If not specified, then `project` will be moved aside to `.orig` and replaced.')
  parser.add_argument('-no-backup', action='store_true', help='Do not create `.orig` backup files.')

  args = parser.parse_args()

  xcodeproj_path = norm_path(args.project)
  if not xcodeproj_path.endswith('.xcodeproj'):
    exit(f"project path does not end with '.xcodeproj': {xcodeproj_path!r}")
  proj_name = path_name_stem(xcodeproj_path)
  assert proj_name, xcodeproj_path

  pbx_path = path_join(xcodeproj_path, 'project.pbxproj')
  try: proj_file = open(pbx_path)
  except FileNotFoundError: exit(f"project does not contain '.pbxproj' file: {pbx_path}")

  root = parse_pbx(path=pbx_path, text=proj_file.read())
  text = render_to_str(proj_name=proj_name, root=root)

  out_path = args.output or pbx_path
  if out_path == pbx_path and not args.no_backup:
    orig_path = pbx_path + '.orig'
    if path_exists(orig_path, follow=False):
      exit(f'previous backup already exists; please move it before rewriting: {orig_path}')
    move_file(pbx_path, orig_path)
  with open(out_path, 'w') as f:
    f.write(text)


if __name__ == '__main__': main()
