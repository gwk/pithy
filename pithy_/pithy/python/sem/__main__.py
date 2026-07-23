# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tolkien import Source

from ...argparser import ArgParser
from ...fs import walk_files
from ..ast_utils import fmt_syntax_error
from . import sem_for_source
from .scopes import build_scope_info


def main() -> None:

  parser = ArgParser(description='Analyze Python code.')
  parser.add_argument('paths', nargs='*', help='Paths to analyze.')
  parser.add_argument('-code', help='Code snippet to analyze provided as an argument string.')
  parser.add_argument('-tree', action='store_true', help='Print the sem tree.')
  parser.add_argument('-scopes', action='store_true', help='Print scope info.')

  args = parser.parse_args()

  actions = dict(
    print_tree=args.tree,
    print_scopes=args.scopes)

  if not any(actions.values()):
    actions = { k: True for k in actions }

  for path in walk_files(*args.paths, file_exts=['.py']):
    with open(path) as f:
      parse_and_render(name=path, text=f.read(), actions=actions)

  if args.code:
    parse_and_render(name='code', text=args.code, actions=actions)

  elif not args.paths:
    print('No paths provided. Use -h for help.')
    exit(1)


def parse_and_render(name:str, text:str, actions:dict[str,bool]) -> None:
  source = Source(name=name, text=text)

  try:
    sem = sem_for_source(source=source)
    print()

    if actions['print_tree']:
      print()
      for line in sem.render(source=source):
        print(line)

    if actions['print_scopes']:
      scope_info = build_scope_info(sem, source=source)
      print()
      for line in scope_info.render(source):
        print(line)

  except SyntaxError as e:
    exit(fmt_syntax_error(source.name, e))


if __name__ == '__main__': main()
