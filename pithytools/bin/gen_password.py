# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from pithy.passwords import gen_password

def main() -> None:
  arg_parser = ArgumentParser('Generate a random password.')
  arg_parser.add_argument('-length', type=int, default=24, help='The length of the password to generate.')
  arg_parser.add_argument('-dash-every', type=int, default=6, help='Insert a dash every N characters.')

  args = arg_parser.parse_args()

  print(gen_password(length=args.length, dash_every=args.dash_every))


if __name__ == '__main__': main()
