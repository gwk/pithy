#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from typing import Iterator, Any, NamedTuple

from pithy.lex import Lexer, LexMode, LexTrans
from pithy.parse import Choice, OneOrMore, Opt, ParseError, Parser, Struct, ZeroOrMore, Atom, atom_text
from pithy.path import vscode_path
from tolkien import Source, Token
from pithy.ansi import BG_R, RST, TXT_G, TXT_Y, TXT_B, TXT_C, BG_C
from pithy.iterable import joinSCS, fan_items


def main() -> None:
  arg_parser = ArgumentParser()
  arg_parser.add_argument('input_path')
  args = arg_parser.parse_args()

  path = args.input_path
  with open(path) as f:
    source = Source(vscode_path(path), text=f.read())

  dbg_lexer = False
  if dbg_lexer:
    prev_kind = ''
    for token in lexer.lex(source, drop=['comment', 'c_syntax']):
      match token.kind:
        case 'invalid': bg, rst = (BG_R, RST)
        case 'sym': bg, rst = (TXT_Y, RST)
        case 'default_type'|'destructor'|'endif'|'extra_context'|'ifdef'|'ifndef'|'include'|'left'|'name'|'nonassoc'|'right'|'stack_overflow'|'syntax_error'|'token'|'token_class'|'token_prefix'|'token_type'|'type':
          bg, rst = (TXT_G, RST)
        #case 'spaces': bg, rst = (BG_C, RST)
        case _: bg, rst = ('', '')
      print(bg, source[token], rst, sep='', end='')
      if token.kind == 'invalid':
        print()
        exit(source.diagnostic_for_syntax(token, f'invalid token: {source[token]!r}'))
    print()

  try: grammar = parser.parse('grammar', source)
  except ParseError as e: e.fail()

  rules = fan_items(c for c in grammar if isinstance(c, parser.types.Rule))

  for name, choices in rules.items():
    print(f'\n{name}')
    for seq in choices:
      if seq: print('', *['|'.join(subchoices) for subchoices in seq], sep='  ')
      else: print('  .')



lexer = Lexer(flags='msx', # m: ^ and $ match every line; s: dot matches newline.
  patterns=dict(
    newline = r'\n',
    spaces  = r'\ +',
    comment = r'//[^\n]*|/\*.*?\*/',

    rule_op = r'::=',
    dot = r'\.',
    bang = r'\!',
    amp_amp = r'&&',
    pipe_pipe = r'\|\|',
    pipe = r'\|',

    paren_o = r'\(',
    paren_c = r'\)',
    brace_o = r'\{',
    brace_c = r'\}',
    brack_o = r'\[',
    brack_c = r'\]',

    # Directive symbols.
    default_type = r'%default_type\b',
    destructor = r'%destructor\b',
    else_ = r'%else\b',
    endif = r'%endif\b',
    extra_context = r'%extra_context\b',
    fallback = r'%fallback\b',
    if_ = r'%if\b',
    ifdef = r'%ifdef\b',
    ifndef = r'%ifndef\b',
    include = r'%include\b',
    left = r'%left\b',
    name = r'%name\b',
    nonassoc = r'%nonassoc\b',
    right = r'%right\b',
    stack_overflow = r'%stack_overflow\b',
    syntax_error = r'%syntax_error\b',
    token = r'%token\b',
    token_class = r'%token_class\b',
    token_prefix = r'%token_prefix\b',
    token_type = r'%token_type\b',
    type = r'%type\b',
    wildcard = r'%wildcard\b',

    sym = r'[A-Za-z_][0-9A-Za-z_]*', # Must come after directive symbols.

    #number = r'\d+',

    #str_dq=r'"([^\n\\"]|\\.)*"',
    #str_sq=r"'([^\n\\']|\\.)*'",

    c_syntax = r'[^{}]+?', #  Consume everything inside of braces.
  ),

  modes=[
    LexMode('main', kinds=[
      'newline', 'spaces', 'comment',
      'rule_op', 'dot', 'amp_amp', 'pipe_pipe', 'pipe', 'bang',
      'paren_o', 'paren_c', 'brace_o', 'brace_c', 'brack_o', 'brack_c',
      'default_type', 'destructor', 'else_', 'endif', 'extra_context', 'fallback', 'if_', 'ifdef', 'ifndef', 'include', 'left', 'name', 'nonassoc', 'right',
      'stack_overflow', 'syntax_error', 'token', 'token_class', 'token_prefix', 'token_type', 'type', 'wildcard',
      'sym',
    ]),
    LexMode('code', kinds=[
      #'newline', 'spaces', 'comment',
      'brace_o', 'brace_c', 'c_syntax']),
  ],
  transitions=[
    LexTrans(('main', 'code'), kind='brace_o', mode='code', pop='brace_c', consume=True),
  ]
)


def preprocess(source:Source, stream:Iterator[Token]) -> Iterator[Token]:

  cond_stack:list[tuple[Token,Token|None]] = [] # (if_token, cond_token)

  def expect_newline(preceding:Token) -> None:
    t = next(stream)
    if t.kind != 'newline':
      source.fail((t, f'preprocess error: expected newline after {source[preceding]}.'))

  for token in stream:
    kind = token.kind

    match kind:

      case 'ifdef'|'ifndef':
        if_token = token
        cond_token = next(stream)
        if cond_token.kind != 'sym': source.fail((cond_token, f'preprocess error: expected symbol after {source[token]}.'))
        cond_stack.append((if_token, cond_token))
        expect_newline(cond_token)

      case 'if_':
        if_token = token
        while t := next(stream): # Discard all conditional tokens up to the newline.
          if t.kind == 'newline': break
        cond_stack.append((if_token, None))

      case 'else_':
        if not cond_stack: source.fail((token, f'preprocess error: %else without preceding conditional.'))
        expect_newline(token)

      case 'endif':
        if not cond_stack: source.fail((token, f'preprocess error: %endif without preceding conditional.'))
        _, opt_cond_token = cond_stack[-1]
        end_cond_token = next(stream)
        if end_cond_token.kind == 'bang':
          end_cond_token = next(stream)
        if end_cond_token.kind != 'newline': # End condition is not always specified.
          if opt_cond_token and source[opt_cond_token] != source[end_cond_token]:
            source.fail((opt_cond_token, 'note: opening condition.'), (end_cond_token, f'preprocess error: mismatched %endif condition.'))
          expect_newline(end_cond_token)
        cond_stack.pop()

      case 'newline': continue # Discard newlines.
      case _: yield token


def transform_d_name(source:Source, slc:slice, label:str, obj:Any) -> str:
  'Omit the directive contents but return the name for debugging purposes.'
  return source[slc]


parser = Parser(
  lexer=lexer,
  preprocessor=preprocess,
  drop=('comment', 'spaces', 'c_syntax'),
  literals=(
    'rule_op', 'dot', 'amp_amp', 'pipe_pipe', 'pipe', 'bang',
    'paren_o', 'paren_c', 'brace_o', 'brace_c', 'brack_o', 'brack_c',
    'default_type', 'destructor', 'else_', 'endif', 'extra_context', 'fallback', 'if_', 'ifdef', 'ifndef', 'include', 'left', 'name', 'nonassoc', 'right',
    'stack_overflow', 'syntax_error', 'token', 'token_class', 'token_prefix', 'token_type', 'type', 'wildcard',
  ),

  rules=dict(

    grammar = ZeroOrMore('item'),
    item = Choice('rule', 'directive_sym', 'directive_code', 'directive_sym_code', 'directive_seq', 'directive_token_class'),

    directive_sym = Struct(
      Choice('name', 'ifdef', 'ifndef', 'endif', 'token_prefix', transform=transform_d_name),
      'sym'),

    directive_code = Struct(
      Choice('include', 'token_type', 'default_type', 'extra_context', 'syntax_error', 'stack_overflow', transform=transform_d_name),
      'braced_content'),

    directive_sym_code = Struct(
      Choice('type', 'destructor', transform=transform_d_name),
      'sym', 'braced_content'),

    directive_seq = Struct(
      Choice('fallback', 'token', 'wildcard', 'left', 'right', 'nonassoc', transform=transform_d_name),
      OneOrMore('sym'), 'dot'),

    directive_token_class = Struct('token_class', 'sym', 'sym', 'pipe', 'sym', 'dot'), # This is probably a misrepresentation of the actual grammar.

    rule = Struct(
      'sym',
      Opt('param', field=None),
      'rule_op',
      ZeroOrMore('rule_el', field='seq'),
      'dot',
      Opt('bracketed_content', field=None),
      Opt('braced_content', field=None)),

    rule_el =Struct(
      OneOrMore('sym', sep='pipe'),
      Opt('param', field=None)),

    param = Struct('paren_o', 'sym', 'paren_c'),

    sym = Atom('sym', transform=atom_text),

    bracketed_content = Struct('brack_o', ZeroOrMore('sym'), 'brack_c', transform=lambda s, t, fields: None),
    braced_content = Struct('brace_o', ZeroOrMore('braced_content'), 'brace_c', transform=lambda s, t, fields: None),
))


ignored_directives = {
  'default_type',
  'extra_context',
  'include',
  'token_prefix',
  'token_type',
  'syntax_error',
  'stack_overflow',
  'name',
  'type',
}

config_defs = {
  'SQLITE_OMIT_EXPLAIN': False,
  'SQLITE_OMIT_TEMPDB': False,
  'SQLITE_OMIT_COMPOUND_SELECT' : False,
  'SQLITE_OMIT_WINDOWFUNC' : False,
  'SQLITE_OMIT_GENERATED_COLUMNS' : False,
  'SQLITE_OMIT_VIEW' : False,
  'SQLITE_OMIT_CTE' : False,
  'SQLITE_OMIT_SUBQUERY' : False,
  'SQLITE_OMIT_CAST' : False,
  'SQLITE_OMIT_SUBQUERY' : False,
  'SQLITE_OMIT_SUBQUERY' : False,
  'SQLITE_OMIT_PRAGMA' : False,
  'SQLITE_OMIT_TRIGGER' : False,
  'SQLITE_OMIT_TRIGGER' : False,
  'SQLITE_OMIT_ATTACH' : False,
  'SQLITE_OMIT_REINDEX' : False,
  'SQLITE_OMIT_ANALYZE' : False,
  'SQLITE_OMIT_ALTERTABLE' : False,
  'SQLITE_OMIT_VIRTUALTABLE' : False,
  'SQLITE_OMIT_VIRTUALTABLE' : False,
}

if __name__ == '__main__': main()
