#!/usr/bin/env python3

from typing import Optional

from pithy.parse import Atom, Parser, ZeroOrMore, token_extract_text
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


def mk_comma_parser(sep_at_end:Optional[bool]) -> Parser:
  return Parser(lexer, dict(
      name=Atom('name', transform=token_extract_text),
      seq=ZeroOrMore('name', sep='comma', sep_at_end=sep_at_end)),
    drop=('spaces',))

comma_opt = mk_comma_parser(sep_at_end=None)
comma_req = mk_comma_parser(sep_at_end=True)
comma_rej = mk_comma_parser(sep_at_end=False)

utest(['a', 'b', 'c'], comma_opt.parse, 'seq', Source('', 'a, b, c'))
utest(['a', 'b', 'c'], comma_opt.parse, 'seq', Source('', 'a, b, c,'))
utest(['a', 'b', 'c'], comma_req.parse, 'seq', Source('', 'a, b, c,'))
utest(['a', 'b', 'c'], comma_rej.parse, 'seq', Source('', 'a, b, c'))
# TODO: test failure cases.
