# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import Namespace
from typing import Dict, FrozenSet, List, Optional

from pithy.io import *
from pithy.json import write_json
from pithy.string import render_template

from .defs import ModeTransitions
from .dfa import DFA
from .patterns import LegsPattern


def output_vscode(path:str, dfas:List[DFA], mode_transitions:ModeTransitions,
  patterns:Dict[str,LegsPattern], incomplete_patterns:Dict[str,Optional[LegsPattern]],
  pattern_descs:Dict[str, str], license:str, args:Namespace) -> None:

  if not args.syntax_name: exit('error: vscode output requires `-syntax-name` argument.')
  if not args.syntax_scope: exit('error: vscode output requires `-syntax-scope` argument.')
  if not args.syntax_exts: exit('error: vscode output requires `-syntax-exts` argument.')
  if args.test: exit('error: vscode output is not testable.')

  lang_scope = args.syntax_scope
  repository:Dict[str,Any] = {}
  syntax_def = {
    "scopeName": "source." + lang_scope,
    "fileTypes": args.syntax_exts,
    "name": args.syntax_name,
    "patterns": [{ "include" : "#main" }],
    "repository": repository,
  }

  for name, pattern in patterns.items():
    key = f'{name}.{lang_scope}'
    repository[name] = {
      "name": key,
      "match": pattern.gen_regex(flavor='vscode')}

  for dfa in dfas:
    mode = dfa.name
    mode_patterns:List[Any] = []
    includes = [{"include" : f'#{name}'} for name in dfa.backtracking_order]
    repository[mode] = dict(patterns=includes)

  with open(path, 'w', encoding='utf8') as f:
    write_json(f, syntax_def)
