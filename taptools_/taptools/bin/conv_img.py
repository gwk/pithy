# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from base64 import b64encode


def main() -> None:
  arg_parser = ArgumentParser('Convert images.')
  arg_parser.add_argument('paths', nargs='+', help='paths to image files.')
  arg_parser.add_argument('-base64', action='store_true', help='output base64 encoding to stdout.')
  args = arg_parser.parse_args()

  for path in args.paths:
    conv_img(path, base64=args.base64)


def conv_img(path:str, base64:bool) -> None:
  b = open(path, 'rb').read()
  if base64:
    encoded = b64encode(b, altchars=None)
    print(f'{path}:\ndata:image/png;base64,{encoded.decode()}')
  else:
    exit('error: `-base64` is currently the only supported option.')

if __name__ == '__main__': main()
