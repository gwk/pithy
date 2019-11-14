# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import Namespace
from pprint import pformat
from typing import Dict, FrozenSet, List, Optional, Tuple

from . import ModeTransitions
from pithy.fs import add_file_execute_permissions
from pithy.io import *
from pithy.optional import unwrap
from pithy.string import render_template

from .defs import MatchStateKinds, ModeData, ModeTransitions, StateTransitions
from .dfa import DFA
from .patterns import LegsPattern, regex_for_codes


def output_python(path:str, dfas:List[DFA], mode_transitions:ModeTransitions,
  pattern_descs:Dict[str, str], license:str, args:Namespace) -> None:

  mode_data:Dict[str,ModeData] = {}

  for dfa in dfas:
    mode = dfa.name
    match_node_kinds = { match_node : unwrap(dfa.match_kind(match_node)) for match_node in dfa.match_nodes }
    kinds = { kind : py_safe_sym(kind) for kind in dfa.pattern_kinds }
    kinds['incomplete'] = 'incomplete'
    assert len(kinds) == len(set(kinds.values()))
    mode_data[mode] = (dfa.start_node, dfa.transitions, match_node_kinds)

  with open(path, 'w', encoding='utf8') as f:
    src = render_template(template,
      Name=args.type_prefix,
      license=license,
      mode_data=fmt_obj(mode_data),
      mode_transitions=fmt_obj(mode_transitions),
      pattern_descs=fmt_obj(pattern_descs),
      patterns_path=args.path,
    )
    f.write(src)
    if args.test:
      test_src = render_template(test_template, Name=args.type_prefix)
      f.write(test_src)


template = '''# ${license}
# This file was generated by legs from ${patterns_path}.

from legs import DictLexerBase, ModeData, ModeTransitions
from typing import Dict, Iterator, Pattern, Tuple


class ${Name}Lexer(DictLexerBase):

  pattern_descs:Dict[str,str] = ${pattern_descs}

  mode_transitions:ModeTransitions = ${mode_transitions}

  mode_data:Dict[str,ModeData] = ${mode_data}

'''



def output_python_re(path:str, dfas:List[DFA], mode_transitions:ModeTransitions,
  patterns:Dict[str,LegsPattern], incomplete_patterns:Dict[str,Optional[LegsPattern]],
  pattern_descs:Dict[str, str], license:str, args:Namespace) -> None:

  flavor = 'py.re.bytes'

  mode_patterns_code:List[str] = []
  for dfa in dfas:
    mode = dfa.name
    regexes:List[str] = []
    incompletes:List[LegsPattern] = []

    for kind in dfa.backtracking_order:
      pattern = patterns[kind]
      regex = pattern.gen_regex(flavor=flavor)
      regexes.append(f'(?P<{kind}> {regex} )\n')

    invalid_regex = regex_for_codes(dfa.transitions[dfa.invalid_node], flavor) + '+'
    regexes.append(f'(?P<invalid> {invalid_regex} )\n')

    incomplete_pattern = incomplete_patterns[mode]
    if incomplete_pattern:
      incomplete_regex = incomplete_pattern.gen_regex(flavor=flavor)
      regexes.append(f'(?P<incomplete> {incomplete_regex} )\n')

    choices = '| '.join(regexes)
    re_text = f'(?x)\n  {choices}'
    code = f"    {mode!r} : _re_compile(br'''{re_text}''')"
    mode_patterns_code.append(code)

  mode_patterns_body = ",\n    ".join(mode_patterns_code)
  mode_patterns_repr = f'{{\n{mode_patterns_body}\n}}'

  with open(path, 'w', encoding='utf8') as f:
    src = render_template(re_template,
      Name=args.type_prefix,
      license=license,
      mode_patterns_repr=mode_patterns_repr,
      mode_transitions=fmt_obj(mode_transitions),
      pattern_descs=fmt_obj(pattern_descs),
      patterns_path=args.path,
    )
    f.write(src)
    if args.test:
      test_src = render_template(test_template, Name=args.type_prefix)
      f.write(test_src)


def fmt_obj(object:Any) -> str:
  return pformat(object, indent=2, width=128, compact=True)


re_template = '''# ${license}
# This file was generated by legs from ${patterns_path}.

from legs import RegexLexerBase, ModeData, ModeTransitions
from re import compile as _re_compile
from typing import Dict, Iterator, Pattern, Tuple

class ${Name}Lexer(RegexLexerBase):

  pattern_descs:Dict[str,str] = ${pattern_descs}

  mode_transitions:ModeTransitions = ${mode_transitions}

  mode_patterns:Dict[str,Pattern] = ${mode_patterns_repr}

'''


test_template = '''
from legs import test_main

if __name__ == '__main__': test_main(${Name}Lexer)
'''


def py_safe_sym(name:str) -> str:
  name = re.sub(r'[^\w]', '_', name)
  if name[0].isdigit():
    name = '_' + name
  if name in py_reserved_syms:
    name += '_'
  return name


py_reserved_syms = {
  'False',
  'class',
  'finally',
  'is',
  'return',
  'None',
  'continue',
  'for',
  'lambda',
  'try',
  'True',
  'def',
  'from',
  'nonlocal',
  'while',
  'and',
  'del',
  'global',
  'not',
  'with',
  'as',
  'elif',
  'if',
  'or',
  'yield',
  'assert',
  'else',
  'import',
  'pass',
  'break',
  'except',
  'in',
  'raise',
}
