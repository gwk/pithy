# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from argparse import Namespace
from typing import *
from pithy.io import *
from pithy.json import write_json
from pithy.string import render_template
from .defs import ModeTransitions
from .rules import Rule


def output_vscode(path: str, patterns: Dict[str, Rule], mode_rule_names: Dict[str, List[str]], transitions: ModeTransitions,
  rule_descs: Dict[str, str], license: str, args: Namespace):

  if not args.syntax_name: exit('error: vscode output requires `-syntax-name` argument.')
  if not args.syntax_scope: exit('error: vscode output requires `-syntax-scope` argument.')
  if not args.syntax_exts: exit('error: vscode output requires `-syntax-exts` argument.')
  if args.test: exit('error: vscode output is not testable.')

  scope = args.syntax_scope
  repository: Dict[str, Any] = {}
  syntax_def = {
    "scopeName": "source." + scope,
    "fileTypes": args.syntax_exts,
    "name": args.syntax_name,
    "patterns": [{ "include" : "#main" }],
    "repository": repository,
  }

  gen_patterns = {name : rule.genRegex(flavor='vscode') for name, rule in patterns.items()}

  for mode, rule_names in mode_rule_names.items():
    mode_patterns: List[Any] = []
    for name in rule_names:
      rule = patterns[name]
      key = f'{name}.{scope}'
      if mode != 'main': key = f'{mode}.{key}'
      mode_patterns.append({
        "name": key,
        "match": rule.genRegex(flavor='vscode')})
    repository[mode] = {
      "patterns": mode_patterns,
    }

  #py_modes: List[str] = []
  #for mode, rule_names in sorted(mode_rule_names.items()):
  #  names_str = ''.join(f'\n      {n!r},' for n in rule_names)
  #  py_modes.append(f'\n    {mode}={{{names_str}}}')

  #py_transitions: List[str] = [f'\n    ({a}, {b}) : ({c}, {d})' for (a, b), (c, d) in transitions.items()]

  with open(path, 'w', encoding='utf8') as f:
    write_json(f, syntax_def)
