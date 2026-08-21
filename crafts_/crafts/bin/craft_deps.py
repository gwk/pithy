# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os.path import abspath

from crafts.deps import (DepLocation, deps_local_config_name, deps_local_config_trust_problem, DepsConfigError,
  ensure_dep_symlinks, load_deps_config, load_deps_local_config, resolve_dep, ResolvedDep, suggest_dep_path,
  write_deps_local_config)


def main() -> None:
  '''
  `craft-deps` configures named symlinks to machine-local directories in a project's `deps/` directory.
  Targets may be Git checkouts or arbitrary source, documentation, and data directories.

  Declare and commit dependencies in `_deps.json`; ignore `deps/` and `_deps.local.json` in version control.
  `craft-deps` writes to those locations.

  The tool prompts for missing or invalid targets and records machine-specific paths plus a `writable` bool in `_deps.local.json`.
  `writable` defaults to false and is an advisory permission for other tools to enforce, not a property of the symlink.

  Example `_deps.json`:

    {"deps": ["pithy"]}

  Corresponding `_deps.local.json`:

    {"pithy": {"path": "../../pithy/main", "writable": true}}

  Note: Use `craft-deps` prior to invoking `uv` when the latter depends on `deps/` links for local workspaces.
  In such cases note that `craft-deps` must be available outside the uv virtual environment.
  '''

  parser = ArgumentParser(description=__doc__, formatter_class=RawDescriptionHelpFormatter)
  parser.add_argument('project', nargs='?', default='.', help='Project directory (default: current directory).')
  args = parser.parse_args()
  project_dir = abspath(args.project)

  try:
    names = load_deps_config(project_dir)
    locations = load_deps_local_config(project_dir)
    trust_problem = deps_local_config_trust_problem(project_dir)
    if trust_problem is not None:
      print(f'craft-deps: {trust_problem}')
      print('craft-deps: reconfirm every declared location before replacing the local config.')
    resolved:list[ResolvedDep] = []
    changed = trust_problem is not None
    for name in names:
      location = locations.get(name)
      if location is not None and trust_problem is None:
        try:
          dep = resolve_dep(project_dir, name, location)
          print(f'ok      dependency {name!r}: {dep.path}')
          resolved.append(dep)
          continue
        except DepsConfigError as e: print(f'craft-deps: {e}')
      location, dep = prompt_dep(project_dir, name, suggestion=location.path if location else None)
      locations[name] = location
      resolved.append(dep)
      changed = True
    extras = [name for name in locations if name not in names]
    if extras and trust_problem is None:
      print(f'craft-deps: note: leaving undeclared local entries: {", ".join(map(repr, extras))}')
    elif extras:
      for name in extras: del locations[name]
    if changed:
      write_deps_local_config(project_dir, locations)
      print(f'craft-deps: wrote {deps_local_config_name}.')
    ensure_dep_symlinks(project_dir, resolved)
  except DepsConfigError as e: exit(f'craft-deps: error: {e}')


def prompt_dep(project_dir:str, name:str, suggestion:str|None=None) -> tuple[DepLocation,ResolvedDep]:
  if suggestion is None: suggestion = suggest_dep_path(project_dir, name)
  hint = f' [{suggestion}]' if suggestion else ''
  while True:
    try: path = input(f'Enter the directory path for dependency {name!r}{hint}: ').strip() or suggestion
    except (EOFError, KeyboardInterrupt):
      print()
      exit(1)
    if not path:
      print('craft-deps: a directory path is required.')
      continue
    try: dep = resolve_dep(project_dir, name, DepLocation(path))
    except DepsConfigError as e:
      print(f'craft-deps: {e}')
      continue
    try: response = input(f'Allow consumers to modify dependency {name!r} at {dep.path}? [y/N] ').strip().lower()
    except (EOFError, KeyboardInterrupt):
      print()
      exit(1)
    location = DepLocation(path, writable=response == 'y')
    return location, resolve_dep(project_dir, name, location)


if __name__ == '__main__': main()
