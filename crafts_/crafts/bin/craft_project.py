# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-project` is a project configuration tool.
'''

from argparse import ArgumentParser

from .. import load_craft_config


def main() -> None:
  arg_parser = ArgumentParser(description='Craft project configuration tool.')
  _ = arg_parser.parse_args()

  _ = load_craft_config()


if __name__ == '__main__': main()
