# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, cast

from tolkien import Source, Token

from ..lex import Lexer
from ..parse import (Alias, Atom, atom_text, Choice, choice_label, choice_labeled, choice_val, Infix, Left, OneOrMore, Opt,
  ParseError, Parser, Precedence, Quantity, Struct, uni_syn, uni_text, ZeroOrMore)
from .keywords import sqlite_keywords


def parse_sqlite(path:str, text:str) -> list[Any]: # Actual return type is list[parser.types.Stmt].
  '''
  Parse the SQLite source given in `text`.
  '''
  source = Source(name=path, text=text)
  try: stmts = parser.parse('stmts', source)
  except ParseError as e: e.fail()
  return cast(list, stmts)


lexer = Lexer(flags='mxi', # SQL is case-insensitive.
  patterns=dict(
    newline = r'\n',
    spaces  = r'\s+',
    comment = r'--[^\n]*',

    bitand = r'&',
    bitnot = r'~',
    comma = r',',
    dot = r'\.',
    eq = r'=',
    lp = r'\(',
    minus = r'-',
    ne = r'!=',
    plus = r'\+',
    rem = r'%',
    rp = r'\)',
    semi = r';',
    slash = r'/',
    star = r'\*',
    qmark = r'\?',

    le = r'<=',
    lshift = r'<<',
    lt = r'<',

    ge = r'>=',
    rshift = r'>>',
    gt = r'>',

    concat = r'\|\|',
    bitor = r'\|',

    **{k:rf'\b{k}\b' for k in sorted(sqlite_keywords, reverse=True)}, # Note: reverse to ensure that longer keywords are matched first.

    blob = r"x'[0-9a-fA-F]*'", # Must precede `name`.
    float = r'([0-9]+\.[0-9]* | \.[0-9]+) ([eE][+-]?[0-9]+)?', # Must precede `integer`.
    integer = r'[0-9]+ | 0x[0-9a-fA-F]+',
    string = r" ' ( [^'] | '' )* ' ",

    name = r''' # Note: in the SQLite grammar this is called "id" (identifier).
      [^\W\d]\w*
    | "  ( [^"]  | ""   )* "
    | `  ( [^`]  | ``   )* `  # MySQL style.
    | \[ ( [^\]] | \]\] )* \] # MS Access and SQL Server style.
    ''',

    variable = r'''
    # https://sqlite.org/lang_expr.html#parameters
    # Note that all three named parameter styles accept a digit as the first character, as well as unicode chars.
    # The TCL style allows interspersed "::" and trailing "(...)", "containing any text at all".
    # However this is underspecified. In particular, the parenthetical does not appear to accept spaces.
      \?   [0-9]*
    | [:@] \w+
    | \$ ( \w+ | :: )+ ( \([^)\s]*\) )?  # TCL style allows interspersed "::" and trailing "(...)".
    ''',
  ),
)


create_rules = dict(

  create_stmt = Struct('CREATE', Choice('create_index', 'create_table')),

  create_index = Struct(
    Opt('UNIQUE', field='is_unique'),
    'INDEX',
    Opt(Struct('IF', 'NOT', 'EXISTS'), field='if_not_exists', transform=lambda s, slc, f: True),
    Alias('schema_table_name', field='name'),
    'ON',
    Alias('schema_table_name', field='table'),
    'lp',
    'indexed_columns',
    'rp',
    Opt('where_clause', field='where'),
  ),

  create_table = Struct(
    Opt(Choice('TEMP', 'TEMPORARY', 'VIRTUAL', transform=choice_label), field='temp_or_virtual'),
    #^ Note: CREATE VIRTUAL TABLE is technically a separate rule. This hack requires post-parse validation to ensure that VIRTUAL has a matching USING choice below.
    'TABLE',
    Opt(Struct('IF', 'NOT', 'EXISTS'), field='if_not_exists'),
    Alias('schema_table_name', field='name'),
    Choice('table_def', 'as_select', 'virtual_using', field='def')
  ),

  table_def = Struct(
    'lp',
    OneOrMore('column_def', sep='comma', sep_at_end=False, field='column_defs'),
    ZeroOrMore(Struct('comma', 'table_constraint'), field='table_constraints'),
    'rp',
    ZeroOrMore('table_option', sep='comma', sep_at_end=False, field='table_options')),

  column_def = Struct(
    'name',
    Opt('name', field='type_name'),
    ZeroOrMore('column_constraint', field='constraints')),

  column_constraint = Struct(
    Opt(Struct('CONSTRAINT', 'name'), field='constraint_name'),
    Choice(
      Struct('PRIMARY', 'KEY', Opt('asc_desc'), 'on_conflict', Opt('AUTOINCREMENT'), field='primary_key'),
      Struct('NOT', 'NULL', 'on_conflict', field='not_null'),
      Struct('UNIQUE', 'on_conflict', field='unique'),
      Struct('CHECK', 'paren_expr', field='check'),
      Struct('DEFAULT', 'default_expr', field='default'),
      Struct('COLLATE', 'name', field='collate'),
      # TODO: foreign-key-clause.
      'generated_constraint',
      field='kind',
      transform=choice_labeled)),

  default_expr = Choice('paren_expr', 'literal_value', 'signed_number', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
    transform=choice_val),

  generated_constraint = Struct(
    Opt(Struct('GENERATED', 'ALWAYS'), field=None),
    'AS',
    Alias('paren_expr', transform=uni_syn, field='expr'),
    Opt(Choice('STORED', 'VIRTUAL'), field='stored_or_virtual', transform=uni_text)),

  asc_desc = Choice('ASC', 'DESC'),

  table_constraint = Struct(
    Opt(Struct('CONSTRAINT', 'name'), field='constraint_name'),
    Choice(
      Struct('PRIMARY', 'KEY', 'lp', 'indexed_columns', 'rp', 'on_conflict', field='primary_key'),
      Struct('UNIQUE', 'lp', 'indexed_columns', 'rp', 'on_conflict', field='unique'),
      Struct('CHECK', 'paren_expr', field='check'),
      Struct('FOREIGN', 'KEY', 'lp', OneOrMore('name', field='columns'), 'rp', 'foreign_key_clause', field='foreign_key'),
      field='kind',
      transform=choice_labeled)),

  table_option = Choice(
    Struct('WITHOUT', Atom('name', field='rowid'), transform=lambda s, slc, f: 'WITHOUT ROWID'), # TODO: the transform should raise ParseError if the name is not "ROWID".
    Atom('name', field='strict', transform=atom_text),
  ),

  as_select = Struct('AS', 'select_stmt'),

  virtual_using = Struct('USING', 'name', Opt(Struct('lp', ZeroOrMore('name', field='module_arguments'), 'rp'))),
)


expr_rules = dict(
  expr = Precedence(
    ( 'blob', 'float', 'integer', 'string', 'FALSE', 'TRUE', 'NULL', # The "literal-value" tokens.
      'signed_number',
      # bind-parameter
      'schema_table_column_name',
      'paren_expr',
      'cast_expr',
      'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
    ),
    Left(Infix('eq'), Infix('ne'), Infix('lt'), Infix('le'), Infix('gt'), Infix('ge')),
    Left(Infix('concat')),
    Left(Infix('plus'), Infix('minus')),
    Left(Infix('star'), Infix('slash'), Infix('rem')),
  ),

  # unary-operator expr
  # expr binary-operator expr
  # function-name ...
  # expr COLLATE collation-name
  # expr NOT LIKE|GLOB|REGEXP|MATCH expr
  # expr ISNULL, NOTNULL, NOT NULL
  # expr IS NOT DISTINCT FROM expr
  # expr NOT BETWEEEN expr AND expr
  # expr NOT IN (expr, expr, ...)
  # NOT EXISTS ( SELECT ... ) # Note: this will conflict with `( expr, ... )` above; refactor to separate NOT EXISTS and EXISTS, and ( SELECT ..).
  # CASE expr WHEN expr THEN expr ELSE expr END
  # raise-function

  signed_number = Struct(Choice('plus', 'minus', field='sign'), Choice('float', 'integer', field='number')),

  paren_expr = Struct('lp', 'expr', 'rp', field='expr'),
  cast_expr =  Struct('CAST', 'lp', 'expr', 'AS', 'name', 'rp'),

  exists_prefix = Opt(Choice('EXISTS', 'not_exists', transform=choice_label)),
  not_exists = Struct('NOT', 'EXISTS'),
)


select_rules = dict(

  select_stmt = Struct(
    'SELECT', # TODO.
  ),
)


parser = Parser(lexer,
  drop=('comment', 'spaces', 'newline'),
  literals=(
    'bitand', 'bitnot', 'comma', 'dot', 'eq', 'lp', 'minus', 'ne', 'plus', 'rem', 'rp', 'semi', 'slash', 'star', 'qmark',
    'le', 'lshift', 'lt', 'ge', 'rshift', 'gt', 'concat', 'bitor', *sqlite_keywords),

  rules=dict(

    stmts = ZeroOrMore('stmt', sep='semi', repeated_seps=True),

    stmt = Choice('create_stmt', 'select_stmt'),

    literal_value = Choice('blob', 'float', 'integer', 'string', 'FALSE', 'TRUE', 'NULL'),
    #^ NOTE: This is strict and does not allow entities as strings. See https://www.sqlite.org/lang_keywords.html.

    schema_table_name = Quantity('name', min=1, max=2, sep='dot', sep_at_end=False),
    table_column_name = Quantity('name', min=1, max=2, sep='dot', sep_at_end=False),
    schema_table_column_name = Quantity('name', min=1, max=3, sep='dot', sep_at_end=False),

    foreign_key_clause = Struct(
      'REFERENCES',
      'NULL'), # TODO.

    indexed_columns = OneOrMore('indexed_column', sep='comma', sep_at_end=False),

    indexed_column = Struct(
      'expr',
      Opt(Struct('COLLATE', 'name'), field='collate'),
      Opt('asc_desc')),

    on_conflict = Opt(Struct('ON', 'CONFLICT',
      Choice('ROLLBACK', 'ABORT', 'FAIL', 'IGNORE', 'REPLACE', transform=choice_label))),

    where_clause = Struct('WHERE', 'expr'),

    **create_rules,
    **expr_rules,
    **select_rules,
  ))


def test_lex(path:str, text:str) -> None:
  'Test the lexer.'
  source = Source(path, text)
  prev:Token|None = None
  for token in lexer.lex(source):
    if token.kind == 'invalid': source.fail(
      (prev, f'previous token: {prev.kind}') if prev else None,
      (token, f'invalid token: {source[token]!r}'))
    prev = token


def test_parse(path:str, text:str) -> None:
  'Test the parser.'
  ast = parse_sqlite(path, text=open(path).read())
  print(ast)


def main() -> None:
  from argparse import ArgumentParser

  argparser = ArgumentParser(description='Test the pithy sqlite parser.')
  argparser.add_argument('paths', nargs='+', help='paths to parse.')
  args = argparser.parse_args()

  for path in args.paths:
    test_parse(path, open(path).read())


if __name__ == '__main__': main()
