# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import Alias, Choice, OneOrMore, Opt, Parser, Struct, ZeroOrMore
from tolkien import Source, Token

from ..parse import ParseError
from .lex import lexer
from .syntax import eon_syntax_token, EonBinding, EonList, EonNode, EonStr, EonSyntax, render_eon_syntax, section_rank_leaf


class ConversionError(ParseError):
  error_prefix = 'conversion'


def _build_eon_parser() -> Parser:
  return Parser(lexer,
    drop=('comment', 'spaces'),

    literals=('indent', 'dedent', 'newline', 'newlines',
      'brace_o', 'brace_c', 'brack_o', 'brack_c', 'paren_o', 'paren_c',
      'dq', 'sq'),

    rules=dict(
      body=ZeroOrMore('section_or_tree', transform=transform_body),

      section_or_tree=Choice('section_tree', 'tree'),

      section_tree=Struct('section', 'trees', transform=transform_section_tree),

      trees=ZeroOrMore('tree', transform=transform_trees),

      tree=Struct('inline_els', Opt('spaced_eq_tail'), 'newlines', Opt('subtree'), transform=transform_tree),

      inline_els=OneOrMore('inline_el'),

      spaced_eq_tail=Struct('spaced_eq', ZeroOrMore('inline_el')),

      subtree=Struct('indent', 'trees', 'dedent'),

      inline_el=Struct('atom', Opt(Struct('eq', 'val')), transform=transform_inline_el),

      val=Alias('atom'),

      atom=Choice('flt', 'int', 'str_dq', 'str_sq', 'sym'),

      #pair=Struct('atom', 'eq', 'atom'),

      str_dq=Struct('dq', ZeroOrMore(Choice('esc_char', 'chars_dq')), 'dq', transform=lambda s, slc, fields: EonStr(slc, fields[1])),
      str_sq=Struct('sq', ZeroOrMore(Choice('esc_char', 'chars_sq')), 'sq', transform=lambda s, slc, fields: EonStr(slc, fields[1])),

      newlines=OneOrMore('newline'),
    ))

# Parser transformers.

def transform_body(source:Source, start:Token, nodes:list[EonList]) -> list[EonList]:
  # Restructure top level by section rank.
  top_nodes:list[EonList] = []
  section_stack:list[EonList] = []
  for node in nodes:
    rank = node.section_rank if isinstance(node, EonNode) else section_rank_leaf
    while section_stack and section_stack[-1].section_rank >= rank:
      section_stack.pop()
    if not section_stack: # No parent section.
      top_nodes.append(node)
      if rank != section_rank_leaf:
        section_stack.append(node)
    else: # We have a parent section; any peers have already been popped.
      section_stack[-1].els.append(node)
      if rank:
        section_stack.append(node)

  return top_nodes


def transform_section_tree(source:Source, start:Token, fields:list[Any]) -> EonList:
  section_token, tree = fields
  assert isinstance(section_token, Token)
  assert isinstance(tree, EonList)
  tree.token = section_token
  return tree


def transform_trees(source:Source, start:Token, els:list[EonSyntax]) -> EonList:
  return EonList(start, els)


def transform_tree(source:Source, start:Token, fields:list[Any]) -> EonSyntax:
  inline_els, opt_spaced_eq_tail, newlines, opt_subtree = fields
  assert isinstance(inline_els, list)
  assert inline_els
  if opt_spaced_eq_tail:
    if len(inline_els) == 1:
      key = inline_els[0]
    else:
      key = EonList(eon_syntax_token(inline_els[0]), inline_els)
    spaced_eq_token, tail_els = opt_spaced_eq_tail
    if opt_subtree:
      tail_els += opt_subtree
    if len(tail_els) == 1:
      val = tail_els[0]
    else:
      val = EonList(eon_syntax_token(tail_els[0]), tail_els)
    return EonBinding(token=spaced_eq_token, key=key, val=val)
  else: # No spaced_eq.
    if opt_subtree:
      return EonList(start, inline_els + opt_subtree.els)
    elif len(inline_els) == 1:
      single_el = inline_els[0]
      assert isinstance(single_el, (Token, EonNode))
      return single_el
    else:
      return EonList(start, inline_els)


def transform_inline_el(source:Source, start:Token, fields:list[Any]) -> EonSyntax:
  key, eq_val = fields
  assert isinstance(key, (Token, EonNode))
  if eq_val:
    eq, val = eq_val
    return EonBinding(token=eq, key=key, val=val)
  else:
    return key


eon_parser = _build_eon_parser()


def main() -> None:
  '''
  Parse specified files (or stdin) as EON and print each result.'
  '''
  from sys import argv

  from ..io import outD

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    with open(path) as f: text = f.read()
    source = Source(name=path, text=text)
    try: body = eon_parser.parse('body', source)
    except ParseError as e: e.fail()
    print(f'{path}:')
    for el in body:
      print(*render_eon_syntax(el, source), sep='', end='')


if __name__ == '__main__': main()
