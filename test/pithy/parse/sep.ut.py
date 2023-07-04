#!/usr/bin/env python3

from pithy.parse import Atom, atom_text, Parser, ZeroOrMore
from pithy.py.lex import lexer
from tolkien import Source
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

utest(['a', 'b', 'c'], comma_opt.parse, 'seq', Source('', 'a, b, c'))
utest(['a', 'b', 'c'], comma_opt.parse, 'seq', Source('', 'a, b, c,'))
utest(['a', 'b', 'c'], comma_req.parse, 'seq', Source('', 'a, b, c,'))
utest(['a', 'b', 'c'], comma_rej.parse, 'seq', Source('', 'a, b, c'))
# TODO: test failure cases.
