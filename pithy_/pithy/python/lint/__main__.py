# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'A simple Python linter meant to work in conjunction with mypy.'

from ...argparser import ArgParser
from ...fs import walk_files
from . import lint_path, lint_text


def main() -> None:
  parser = ArgParser(description='Lint Python code.')
  parser.add_argument('paths', nargs='*', help='Paths to lint.')
  parser.add_argument('-c', '--code', help='Code snippet to lint provided as an argument string.')

  args = parser.parse_args()

  for path in walk_files(*args.paths, file_exts=['.py']):
      lint_path(path)

  if args.code:
    print(lint_text(args.code))
  elif not args.paths:
    print('No paths provided. Use -h for help.')
    exit(1)


if __name__ == '__main__': main()
