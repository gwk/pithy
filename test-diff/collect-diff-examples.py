#!/usr/bin/env python3

import re
from sys import argv
from typing import *

from pithy.fs import *
from pithy.io import *
from pithy.task import *


build_dir = '_build/test-diff'

def main() -> None:
  repo_paths = argv[1:]
  make_dirs(f'{build_dir}/pairs')
  for i in range(0x100):
    make_dirs(f'{build_dir}/objects/{i:02x}')
  for repo in repo_paths:
    name = path_name(repo.rstrip('/'))
    assert name not in ('', '.')
    outL()
    commits = runO('git --no-pager log --format=%H', cwd=repo).split('\n')
    outL(f'{name}: {len(commits)} commits.')
    objects:Set[str] = set()
    pairs:List[str] = []
    for commit in err_progress(commits, label='commit'):
      diff = runO(f'git --no-pager show --raw --abbrev=16 {commit}', cwd=repo) # only show modified files.
      for line in diff.split('\n'):
        m = mod_line_re.match(line)
        if not m:
          #outL('ignore: ', line)
          continue
        obj_l, obj_r, path = m.groups()
        pairs.append((obj_l, obj_r))
        save_obj(repo=repo, objects=objects, obj=obj_l)
        save_obj(repo=repo, objects=objects, obj=obj_r)
    with open(f'{build_dir}/pairs/{name}.txt', 'w') as f:
      for l, r in pairs: f.write(f'{l}_{r}\n')
    outL(f'{len(pairs)} pairs.')


def save_obj(repo:str, objects:Set[str], obj:str) -> None:
  if obj not in objects:
    objects.add(obj)
    path = f'{build_dir}/objects/{obj[:2]}/{obj}'
    run(f'git show {obj}', cwd=repo, out=open(path, 'w'))


mod_line_re = re.compile(r':\d{6} \d{6} (\w{16}) (\w{16}) M\t(.+)')

token_re = re.compile(r'''(?x)
  (?P<newline> \n ) # Preserve newlines.
| (?P<indent> ^ \s+ ) # Preserve leading space.
| (?P<other> .+) # Everything else gets reduced to a unique token.
''')


if __name__ == '__main__': main()
