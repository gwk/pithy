#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from os import chdir, listdir as list_dir
from os.path import dirname as dir_name, isdir as is_dir, splitext as split_ext
from tomllib import load as load_toml
from typing import Any

from tomli_w import dump as dump_toml


def main() -> None:
  arg_parser = ArgumentParser(description='Generate the pyproject.toml for a package hosted in this repository.')
  arg_parser.add_argument('name')
  arg_parser.add_argument('-dbg', action='store_true')

  args = arg_parser.parse_args()
  name = args.name

  proj_dir = dir_name(dir_name(__file__))
  chdir(proj_dir)

  pyproject_path = f'{name}_/pyproject.toml'

  print(f'\nGenerating {pyproject_path}.')

  with open(f'common.toml', 'rb') as f:
    common = load_toml(f)

  with open(f'{name}_/{name}.toml', 'rb') as f:
    project = load_toml(f)

  add_properties(name, common)

  merged = merge_toml((), common, project)

  with open(pyproject_path, 'wb') as f:
    dump_toml(merged, f, indent=2)


def add_properties(name:str, common:dict[str,Any]) -> None:
  project = common.setdefault('project', {})

  project_urls = project.setdefault('urls', {})
  project_urls['Documentation'] = f'https://github.com/gwk/pithy/tree/main/{name}#readme'

  project_scripts = project.setdefault('scripts', {})
  add_scripts(name, project_scripts)


def add_scripts(pkg_name:str, project_scripts:dict[str,Any]) -> None:
  bin_path = f'{pkg_name}_/{pkg_name}/bin'
  if not is_dir(bin_path): return
  for script_name in list_dir(bin_path):
    stem, ext = split_ext(script_name)
    if ext != '.py' or stem.startswith('.') or stem.startswith('_') or stem.endswith('.ut'): continue
    script_name = stem.replace('_', '-')
    project_scripts[script_name] = f'{pkg_name}.bin.{stem}:main'


def merge_toml(keys:tuple[str,...], base:dict[str,Any], project:dict[str,Any]) -> dict[str,Any]:
  result = dict(base)
  for key, proj_val in project.items():
    try: base_val = base[key]
    except KeyError:
      result[key] = proj_val
    else: # Merge the values.
      key_path = keys + (key,)
      print('Merging:', '.'.join(key_path))
      if isinstance(base_val, dict) and isinstance(proj_val, dict):
        result[key] = merge_toml(key_path, base_val, proj_val)
      else:
        result[key] = proj_val
  return result


if __name__ == '__main__': main()
