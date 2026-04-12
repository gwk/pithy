# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Logic for dealing with VSCode "when" clauses.
'''

from typing import cast

from tolkien import Source

from ..lex import Lexer
from ..logic import And, Eq, Ge, Gt, In, Le, Logic, Lt, Match, Ne, Not, NotIn, Or
from ..parse import Choice, choice_text, Infix, Left, OneOrMore, Parser, Precedence, Prefix, quantity_text, Struct, syn_skeleton


def parse_when_text(*, name:str='<when-expr>', text:str, skeletonize:bool=False) -> Logic:
  'Parse a VSCode "when" expression into a Logic object.'
  source = Source(name, text)
  logic = cast(Logic, when_parser.parse('expr', source))
  if skeletonize: logic = syn_skeleton(logic, source=source)
  return logic


when_lexer = Lexer(flags='x', patterns=dict(
  spaces   = r'\ +',
  paren_o  = r'\(',
  paren_c  = r'\)',
  dot      = r'\.',
  or_      = r'\|\|',
  and_     = r'&&',
  eq_t     = r'===',
  eq       = r'==',
  match    = r'=~',
  ne_t     = r'!==',
  ne       = r'!=',
  not_     = r'!',
  le       = r'<=',
  lt       = r'<',
  ge       = r'>=',
  gt       = r'>',
  in_      = r'\bin\b',
  not_in   = r'\bnot\ +in\b',
  name     = r'[-:\w]+',
  str_d    = r'"([^"\\]|\\.)*"',
  str_s    = r"'([^'\\]|\\.)*'",
  regex    = r'/([^/\\]|\\.)*/',
))

when_parser = Parser(lexer=when_lexer,
  drop=('spaces',),
  literals=('paren_o', 'paren_c', 'dot', 'or_', 'and_', 'eq_t', 'eq', 'match', 'ne_t', 'ne', 'not_', 'le', 'lt', 'ge', 'gt',
   'in_', 'not_in'),
  rules=dict(
    string=Choice('str_s', 'str_d', transform=choice_text),
    path=OneOrMore('name', sep='dot', transform=quantity_text),
    paren_expr=Struct('paren_o', 'expr', 'paren_c'),
    expr=Precedence(
      ('path', 'string', 'paren_expr', 'regex'),
      Left(Infix('or_', transform=lambda s, slc, t, l, r: Or(slc=t.slc, l=l, r=r))),
      Left(Infix('and_', transform=lambda s, slc, t, l, r: And(slc=t.slc, l=l, r=r))),
      Left(
        Infix('eq_t', transform=lambda s, slc, t, l, r: Eq(slc=t.slc, l=l, r=r)),
        Infix('eq', transform=lambda s, slc, t, l, r: Eq(slc=t.slc, l=l, r=r)),
        Infix('match', transform=lambda s, slc, t, l, r: Match(slc=t.slc, l=l, r=r)),
        Infix('ne_t', transform=lambda s, slc, t, l, r: Ne(slc=t.slc, l=l, r=r)),
        Infix('ne', transform=lambda s, slc, t, l, r: Ne(slc=t.slc, l=l, r=r)),
        Infix('le', transform=lambda s, slc, t, l, r: Le(slc=t.slc, l=l, r=r)),
        Infix('lt', transform=lambda s, slc, t, l, r: Lt(slc=t.slc, l=l, r=r)),
        Infix('ge', transform=lambda s, slc, t, l, r: Ge(slc=t.slc, l=l, r=r)),
        Infix('gt', transform=lambda s, slc, t, l, r: Gt(slc=t.slc, l=l, r=r)),
        Infix('in_', transform=lambda s, slc, t, l, r: In(slc=t.slc, l=l, r=r)),
        Infix('not_in', transform=lambda s, slc, t, l, r: NotIn(slc=t.slc, l=l, r=r)),
      ),
      Left(
        Prefix('not_', transform=lambda s, slc, t, r: Not(slc=t.slc, sub=r))),
    )
  )
)
