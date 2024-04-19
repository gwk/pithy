# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Audit dependencies for various package managers.'

from pithy.argparse import CommandParser
from pithytools.deps_audit.brew import main_brew
from pithytools.deps_audit.pip import main_pip


def main() -> None:
  parser = CommandParser(description='Audit dependencies for various package managers.')

  command_brew = parser.add_command(main_brew, help='Audit homebrew dependencies.')
  command_brew = parser.add_command(main_pip, help='Audit pip dependencies.')

  args = parser.parse_args()
  args.main(args)


if __name__ == '__main__': main()
