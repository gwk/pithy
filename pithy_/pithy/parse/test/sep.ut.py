# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.parse import Atom, atom_text, parse_skel, ParseError, Parser, ZeroOrMore
from pithy.python.lex import lexer
from tolkien import Source
from utest import utest, utest_seq, utest_seq_exc


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

# Ranges.
utest(['b', 'c'], comma_opt.parse, 'seq', Source('seq', 'a, b, c, d'), skeletonize=True, slc=slice(3, 7))


# parse_all.
name_parser = Parser(lexer, drop=('spaces',), rules=dict(
  name=Atom('name', transform=atom_text),
  names=ZeroOrMore('name')))

utest_seq(['a', 'bc', 'd'], name_parser.parse_all, 'name', Source('name', 'a bc d'))
utest_seq(['bc'], name_parser.parse_all, 'name', Source('name', 'a bc d'), slc=slice(2, 4))
utest_seq_exc(ParseError, name_parser.parse_all, 'names', Source('names', ', a'))
