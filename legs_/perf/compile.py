# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Benchmark the compilation stages of grammars. See `readme.md`.'

import gc
import os
import platform
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

import legs
from legs.build import build_dfa, build_nfa, mode_name_key
from legs.dfa import minimize_dfa
from legs.parse import parse_legs
from pithy.cmdparse import Cmd, opt, pos


def main() -> None: CompileBench.main()


class CompileBench(Cmd):
  'Measure grammar parsing, NFA construction, DFA construction, and minimization in the current Python process.'

  paths:list[str] = pos(default_factory=list, metavar='GRAMMAR', doc='Grammar paths; defaults to legs_/grammars/legs.legs.')
  runs:int = opt(default=3, doc='Number of measured runs per grammar.')
  warmups:int = opt(default=1, doc='Number of unmeasured runs per grammar.')


  def run(self) -> None:
    if self.runs < 1: exit('error: -runs must be positive.')
    if self.warmups < 0: exit('error: -warmups must be nonnegative.')
    root = Path(__file__).resolve().parents[2]
    legs_path = Path(legs.__file__).resolve()
    if legs_path.parent != root / 'legs_' / 'legs':
      exit(f'error: legs resolves to {legs_path}; select the Python environment for {root}.')
    print(f'Python: {sys.version.splitlines()[0]}')
    print(f'Executable: {sys.executable}')
    print(f'Legs: {legs_path}')
    print(f'Platform: {platform.platform()} ({platform.machine()})')
    print(f'PYTHONHASHSEED: {os.environ.get("PYTHONHASHSEED", "random")}')
    print(f'Runs: {self.runs}; warmups: {self.warmups}; times in seconds.', flush=True)
    for path_str in self.paths or [str(root / 'legs_' / 'grammars' / 'legs.legs')]:
      path = Path(path_str)
      text = path.read_text()
      samples:list[dict[str,float]] = []
      print(f'\nGrammar: {path}', flush=True)
      for run in range(self.warmups + self.runs):
        gc.collect() # Collect previous automata before timing; cyclic GC remains enabled during each run.
        times, sizes = compile_grammar(str(path), text)
        if run < self.warmups: continue
        samples.append(times)
        print(f'  Run {len(samples)}: total={times["total"]:.3g} minimize={times["minimize"]:.3g}', flush=True)
      print(f'  {"Stage":12} {"Median":>10} {"Min":>10} {"Max":>10}')
      for stage in samples[0]:
        values = [sample[stage] for sample in samples]
        print(f'  {stage:12} {median(values):10.3g} {min(values):10.3g} {max(values):10.3g}')
      for mode, nfa_nodes, dfa_nodes, min_nodes in sizes:
        print(f'  {mode}: NFA={nfa_nodes} DFA={dfa_nodes} minimized={min_nodes} nodes')


def compile_grammar(path:str, text:str) -> tuple[dict[str,float],list[tuple[str,int,int,int]]]:
  'Compile all modes in the same order as build_mode_automata, timing each stage without code generation.'
  start = perf_counter()
  grammar = parse_legs(path, text)
  times = dict(parse=perf_counter() - start, nfa=0.0, dfa=0.0, minimize=0.0)
  sizes = []
  start_node = 0
  for mode, kinds in sorted(grammar.modes.items(), key=lambda item: mode_name_key(item[0])):
    start = perf_counter()
    nfa = build_nfa(mode, sorted((kind, grammar.patterns[kind]) for kind in kinds), encoding='utf-8')
    msgs = nfa.validate()
    if msgs: exit('\n'.join(msgs))
    times['nfa'] += perf_counter() - start
    start = perf_counter()
    dfa = build_dfa(nfa)
    times['dfa'] += perf_counter() - start
    start = perf_counter()
    minimized = minimize_dfa(dfa, start_node=start_node)
    times['minimize'] += perf_counter() - start
    start_node = minimized.end_node
    sizes.append((mode, len(nfa.all_nodes), len(dfa.transitions), len(minimized.transitions)))
    del nfa, dfa, minimized # Release the previous mode outside the next mode's timing.
  times['total'] = sum(times.values())
  return times, sizes


if __name__ == '__main__': main()
