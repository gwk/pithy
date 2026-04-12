# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.parse import Atom, atom_text, parse_skel, Parser, ZeroOrMore
from pithy.py.lex import lexer
from utest import utest


def mk_comma_parser(sep_at_end:bool|None) -> Parser:
  return Parser(lexer,
    drop=('spaces',),
    rules=dict(
      name=Atom('name', transform=atom_text),
      seq=ZeroOrMore('name', sep='comma', sep_at_end=sep_at_end),
    ),
  )


comma_opt = mk_comma_parser(sep_at_end=None)
comma_req = mk_comma_parser(sep_at_end=True)
comma_rej = mk_comma_parser(sep_at_end=False)

utest(['a', 'b', 'c'], parse_skel, comma_opt, 'seq', 'a, b, c')
utest(['a', 'b', 'c'], parse_skel, comma_opt, 'seq', 'a, b, c,')
utest(['a', 'b', 'c'], parse_skel, comma_req, 'seq', 'a, b, c,')
utest(['a', 'b', 'c'], parse_skel, comma_rej, 'seq', 'a, b, c')
# TODO: test failure cases.
