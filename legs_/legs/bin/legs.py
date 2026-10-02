#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from time import perf_counter

from pithy.cmdparse import Cmd, flag, opt, pos
from pithy.io import errL, errLL, errSL, outL
from pithy.iterable import first_el
from pithy.path import path_ext, path_join, path_name, split_dir_name
from pithy.strings import pluralize

from ..build import build_dfa, build_nfa
from ..dfa import DFA, minimize_dfa
from ..dot import output_dot
from ..nfa import NFA
from ..parse import parse_legs
from ..patterns import gen_incomplete_pattern, LegsPattern
from ..python import output_python, output_python_re, OutputOpts
from ..swift import output_swift


def main() -> None: LegsCmd.main()



class LegsCmd(Cmd):
  '''
  Legs is a lexer generator: it takes as input a `.legs` grammar file,
  and outputs code that tokenizes text, converting a stream of characters into a stream of chunks of text called tokens.

  A grammar file defines the kinds of tokens and the patterns of text that they match.
  The patterns are similar to python regular expressions but with several important differences:
  * Character classes are specified using their Unicode names. (TODO: provide documentation)
  * The pattern language is limited to the semantics of formal regular languages.
  * Order does not matter. The pattern compilation process works in terms of sets of patterns,
    and detects ambiguities in overlapping patterns.

  There are two special token kinds:
  * `invalid` indicates a sequence of bytes for which the lexer could not start matching;
  * `incomplete` indicates a token that began to match but did not complete.
  This distinction is important for error reporting;
  lexical errors are found at the ends of `incomplete` tokens and the starts of `invalid` tokens.

  Options that accept multiple values are repeated, e.g. `-langs python -langs swift`.
  Use `legs-test` to run the generated lexers on test inputs and compare them.
  A value that begins with a dash must be written as `-option=VALUE`.
  '''

  cmd_name = 'legs'

  path:str|None = pos(default=None, doc='Path to the .legs file.')
  dbg:bool = flag(doc='Verbose debug printing.')
  describe:bool = flag(doc='Print pattern descriptions.')
  encoding:str = opt(default='utf-8', doc='Encoding of the input file.')
  langs:list[str] = opt(default_factory=list, metavar='LANG', doc='Target language for which to generate a lexer; repeatable.')
  match:list[str] = opt(default_factory=list, metavar='STRING', doc='Attempt to lex the argument string; repeatable.')
  mode:str|None = opt(default=None, doc='Mode with which to lex the arguments to `-match`; defaults to `main`.')
  output:str|None = opt(default=None, doc='Path to output generated source.')
  patterns:list[str] = opt(default_factory=list, metavar='PATTERN', doc='Specify a legs pattern for quick testing; repeatable.')
  stats:bool = flag(doc='Print statistics about the generated automata.')
  type_prefix:str = opt(default='', doc='Type names prefix for generated source code.')


  def run(self) -> None: run_legs(self)



def run_legs(args:LegsCmd) -> None:
  dbg = args.dbg

  if args.mode and not args.match:
    exit('`-mode` option only valid with `-match`.')
  start_mode = args.mode or 'main' # The mode in which `-match` starts lexing.

  if args.match and args.output: exit('`-match` and `-output` are mutually exclusive.')
  if args.match and args.langs: exit('`-match` and `-langs` are mutually exclusive.')

  langs:set[str] = determine_output_languages(args.langs, output_path=args.output)

  # Get the source string from either the command line or the source file.
  if (args.path is None) and args.patterns:
    path = '<patterns>'
    src = '\n'.join(args.patterns)
  elif (args.path is not None) and not args.patterns:
    path = args.path
    try: src = open(path).read()
    except FileNotFoundError:
      exit(f'legs error: no such pattern file: {path!r}')
  else:
    exit('`must specify either `path` or `-patterns`.')

  grammar = parse_legs(path, src)
  license = grammar.license
  patterns = grammar.patterns
  mode_pattern_kinds = grammar.modes
  mode_transitions = grammar.transitions

  if args.match and start_mode not in mode_pattern_kinds:
    hint = '' if args.mode else '; specify the start mode with `-mode`'
    exit(f'error: grammar has no mode named {start_mode!r}{hint}. modes: {", ".join(sorted(mode_pattern_kinds))}.')

  if dbg:
    errSL('\nPatterns:')
    for name, pattern in patterns.items():
      pattern.describe(name=name)
    errL()

  dfas:list[DFA] = []
  start_node = 0
  for mode, pattern_kinds in sorted(mode_pattern_kinds.items(), key=lambda p: mode_name_key(p[0])):
    if args.match and mode != start_mode: continue

    named_patterns = sorted((kind, patterns[kind]) for kind in pattern_kinds)
    nfa = build_nfa(name=mode, named_patterns=named_patterns, encoding=args.encoding)
    if dbg: nfa.describe('NFA')
    if dbg or args.stats: nfa.describe_stats('NFA Stats')
    msgs = nfa.validate()
    if msgs:
      errLL(*msgs)
      exit(1)

    fat_dfa = build_dfa(nfa)
    if dbg: fat_dfa.describe('Fat DFA')
    if dbg or args.stats: fat_dfa.describe_stats('Fat DFA Stats')

    start_time = perf_counter()
    min_dfa = minimize_dfa(fat_dfa, start_node=start_node)
    end_time = perf_counter()

    start_node = min_dfa.end_node
    if dbg: min_dfa.describe('Min DFA')
    if dbg or args.stats:
      min_dfa.describe_stats('Min DFA Stats')
      print(f'  time: {end_time-start_time:.3f} seconds')
    dfas.append(min_dfa)

    if dbg: errL('----')

    post_matches = len(min_dfa.post_match_nodes)
    if post_matches:
      errL(f'note: `{mode}`: minimized DFA contains ', pluralize(post_matches, "post-match node"), '.')

  # If we are testing patterns on the command line, then find the specified DFA, test each argument, and exit.
  if args.match:
    for dfa in dfas:
      if dfa.name != start_mode: continue
      for text in args.match:
        text_bytes = text.encode(args.encoding)
        match_bytes(nfa, fat_dfa, min_dfa, text, text_bytes)
      exit()
    exit(f'bad mode: {start_mode!r}')

  pattern_descs = { name : pattern.literal_desc or name for name, pattern in patterns.items() }
  pattern_descs.update((n, n) for n in ['invalid', 'incomplete'])

  incomplete_patterns:dict[str,LegsPattern|None] = {
    dfa.name : gen_incomplete_pattern(dfa.backtracking_order, patterns) for dfa in dfas }

  if args.describe:
    errL('Patterns:')
    for name, pattern in patterns.items():
      pattern.describe(name=name)
    for name, inc_pattern in incomplete_patterns.items():
      if inc_pattern:
        inc_pattern.describe(name=f'{name}.incomplete')

  if not langs: exit(0)

  out_path = args.output or args.path
  if not out_path: exit('`-path` or `-output` most be specified to determine output paths.')

  output_opts = OutputOpts(patterns_path=args.path, type_prefix=args.type_prefix)

  out_dir, out_name = split_dir_name(out_path)
  if not out_name:
    if not args.path: exit('could not determine output file name.')
    out_name = path_name(args.path)
    if not out_name: exit('could not determine output file name from `path`.')
  out_name_stem = out_name[:out_name.find('.')] if '.' in out_name else out_name # TODO: path_stem should be changed to do this.
  out_stem = path_join(out_dir, out_name_stem)

  if 'dot' in langs:
    output_dot(out_stem, dfas=dfas, pattern_descs=pattern_descs)

  if 'python' in langs:
    path = out_stem + '.py'
    output_python(path, dfas=dfas, mode_transitions=mode_transitions, pattern_descs=pattern_descs, license=license,
      **output_opts)

  if 'python-re' in langs:
    path = out_stem + '.re.py'
    output_python_re(path, dfas=dfas, mode_transitions=mode_transitions,
      patterns=patterns, incomplete_patterns=incomplete_patterns,
      pattern_descs=pattern_descs, license=license, **output_opts)

  if 'swift' in langs:
    path = out_stem + '.swift'
    output_swift(path, dfas=dfas, mode_transitions=mode_transitions, pattern_descs=pattern_descs, license=license,
      **output_opts)


def determine_output_languages(args_langs:list[str], output_path:str|None) -> set[str]:
  if args_langs:
    if 'all' in args_langs:
      langs = supported_langs
    else:
      for lang in args_langs:
        if lang not in supported_langs:
          exit(f'unknown language {lang!r}; supported languages are: {sorted(supported_langs)}.')
      langs = set(args_langs)
  elif output_path:
    ext = path_ext(output_path)
    try: langs = {ext_langs[ext]}
    except KeyError:
      exit(f'unsupported output language extension {ext!r}; supported extensions are: {sorted(ext_langs)}.')
  else:
    langs = set()
  return langs


def mode_name_key(name:str) -> str:
  'Always place main mode first.'
  return '' if name == 'main' else name


def match_bytes(nfa:NFA, fat_dfa:DFA, min_dfa:DFA, text:str, text_bytes:bytes) -> None:
  '''
  Test `nfa`, `fat_dfa`, and `min_dfa` against each other by attempting to match `string`.
  This is tricky because each is subtly different:
  * NFA does not have any transitions to `invalid`.
  * fat DFA does not disambiguate between multiple match states.
  Therefore the minimized DFA is most correct,
  but for now it seems worthwhile to keep the ability to check them against each other.
  '''
  nfa_matches = nfa.match(text_bytes)
  fat_dfa_matches = fat_dfa.match(text_bytes)
  if nfa_matches != fat_dfa_matches:
    if not (nfa_matches == frozenset() and fat_dfa_matches == frozenset({'invalid'})): # allow this special case.
      exit(f'match: {text!r}; inconsistent matches: NFA: {nfa_matches}; fat DFA: {fat_dfa_matches}.')
  min_dfa_matches = min_dfa.match(text_bytes)
  if not (fat_dfa_matches >= min_dfa_matches):
    exit(f'match: {text!r}; inconsistent matches: fat DFA: {fat_dfa_matches}; min DFA: {min_dfa_matches}.')
  assert len(min_dfa_matches) <= 1, min_dfa_matches
  if min_dfa_matches:
    outL(f'match: {text!r} -> {first_el(min_dfa_matches)}')
  else:
    outL(f'match: {text!r} -- <none>')


ext_langs = {
  '.dot' : 'dot',
  '.py' : 'python',
  '.re.py' : 'python-re',
  '.swift' : 'swift',
}

supported_langs = {'dot', 'python', 'python-re', 'swift'}


if __name__ == '__main__': main()
