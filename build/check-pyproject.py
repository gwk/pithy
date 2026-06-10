#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from os import chdir, listdir as list_dir
from os.path import dirname as dir_name, isdir as is_dir, splitext as split_ext
from sys import stderr
from tomllib import load as load_toml
from typing import Any


def main() -> None:
  arg_parser = ArgumentParser(description='Check the pyproject.toml files of packages hosted in this repository.')
  arg_parser.add_argument('names', nargs='+', help='Package names to check; defaults to all packages.')
  args = arg_parser.parse_args()

  proj_dir = dir_name(dir_name(__file__))
  chdir(proj_dir)

  with open('common.toml', 'rb') as f:
    common = load_toml(f)

  ok = True
  for name in args.names:
    ok &= check_package(name, common)
  if not ok: exit(1)


def check_package(name:str, common:dict[str,Any]) -> bool:
  pyproject_path = f'{name}_/pyproject.toml'
  try:
    with open(pyproject_path, 'rb') as f:
      pyproject = load_toml(f)
  except FileNotFoundError:
    print(f'{pyproject_path}: missing.', file=stderr)
    return False

  errors:list[str] = []
  check_common_keys(keys=(), common=common, actual=pyproject, errors=errors)

  project = pyproject.get('project', {})

  for key in ('name', 'description', 'requires-python'):
    if key not in project: errors.append(f'project.{key}: missing.')
  actual_name = project.get('name', name)
  if actual_name != name: errors.append(f'project.name: expected {name!r}; found {actual_name!r}.')

  doc_url = f'https://github.com/gwk/pithy/tree/main/{name}#readme'
  actual_doc_url = project.get('urls', {}).get('Documentation')
  if actual_doc_url != doc_url: errors.append(f'project.urls.Documentation: expected {doc_url!r}; found {actual_doc_url!r}.')

  check_scripts(name=name, actual=project.get('scripts', {}), errors=errors)

  for error in errors: print(f'{pyproject_path}: {error}', file=stderr)
  return not errors


def check_common_keys(keys:tuple[str,...], common:dict[str,Any], actual:dict[str,Any], errors:list[str]) -> None:
  'Recursively check that every key in common.toml is present in the pyproject with an equal value.'
  for key, common_val in common.items():
    key_path = keys + (key,)
    path = '.'.join(key_path)
    if key not in actual:
      errors.append(f'{path}: missing key specified in common.toml.')
      continue
    actual_val = actual[key]
    if isinstance(common_val, dict):
      if isinstance(actual_val, dict):
        check_common_keys(keys=key_path, common=common_val, actual=actual_val, errors=errors)
      else:
        errors.append(f'{path}: expected a table per common.toml; found {actual_val!r}.')
    elif actual_val != common_val:
      errors.append(f'{path}: value differs from common.toml: expected {common_val!r}; found {actual_val!r}.')


def check_scripts(name:str, actual:dict[str,Any], errors:list[str]) -> None:
  'Check that project.scripts exactly matches the entry points implied by the scripts in the package bin directory.'
  expected = bin_scripts(name)
  for script, entry_point in expected.items():
    if script not in actual: errors.append(f'project.scripts.{script}: missing; expected {entry_point!r}.')
    elif actual[script] != entry_point:
      errors.append(f'project.scripts.{script}: expected {entry_point!r}; found {actual[script]!r}.')
  for script in actual:
    if script not in expected: errors.append(f'project.scripts.{script}: unexpected; no matching script in {name}_/{name}/bin.')


def bin_scripts(name:str) -> dict[str,str]:
  scripts:dict[str,str] = {}
  bin_path = f'{name}_/{name}/bin'
  if not is_dir(bin_path): return scripts
  for entry in sorted(list_dir(bin_path)):
    stem, ext = split_ext(entry)
    if ext != '.py' or stem.startswith(('.', '_')) or stem.endswith('.ut'): continue
    scripts[stem.replace('_', '-')] = f'{name}.bin.{stem}:main'
  return scripts


if __name__ == '__main__': main()
