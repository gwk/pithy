# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Compare detailed Legs Python lexing with stdlib over repository sources and Unicode examples.'

import gc
import io
import os
import platform
import sys
import tokenize
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from statistics import median
from subprocess import check_output
from time import perf_counter
from typing import cast

import legs
from legs import DictLexerBase
from legs.build import build_lexer_class
from legs.parse import parse_legs
from legs.py_lexer import PythonLexer
from legs.py_lexer_samples import python_samples, unicode_samples
from legs.py_tokenize import python_tokens
from pithy.cmdparse import Cmd, opt, pos
from tolkien import Source


def main() -> None: PythonBench.main()


class PythonBench(Cmd):
  paths:list[str] = pos(default_factory=list, doc='Python files; defaults to repository .py and .pyi files.')
  runs:int = opt(default=3, doc='Measured runs; zero performs only differential checks.')
  lexer:str = opt(default='', doc='Optional generated Python lexer module, for repeated development checks.')


  def run(self) -> None:
    if self.runs < 0: exit('error: -runs must be nonnegative.')
    root = Path(__file__).resolve().parents[2]
    start = perf_counter()
    if self.lexer:
      spec = spec_from_file_location('generated_python_lexer', self.lexer)
      assert spec and spec.loader
      module = module_from_spec(spec)
      spec.loader.exec_module(module)
      lexer_type = cast(type[DictLexerBase], module.PythonLexer)
    else:
      path = root / 'legs_/grammars/python.legs'
      lexer_type = build_lexer_class('PythonLexer', parse_legs(str(path), path.read_text()))
    print(f'Python: {sys.version.splitlines()[0]}\nExecutable: {sys.executable}\nLegs: {legs.__file__}\n'
      f'Platform: {platform.platform()}\nPYTHONHASHSEED: {os.environ.get("PYTHONHASHSEED", "random")}\n'
      f'Lexer preparation: {perf_counter() - start:.3f}s', flush=True)
    paths = self.paths or check_output(
      ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '*.py', '*.pyi'], cwd=root
    ).decode().split('\0')[:-1]
    sources:list[Source[bytes]] = []
    rejected:list[tuple[str,str]] = []
    failures = 0
    for path_str in paths:
      path = Path(path_str) if self.paths else root / path_str
      try:
        with tokenize.open(path) as f: text = f.read()
        expected = list(tokenize.generate_tokens(io.StringIO(text).readline))
      except (SyntaxError, tokenize.TokenError, UnicodeError) as exc:
        rejected.append((path_str, str(exc)))
        continue
      source = Source(path_str, text.encode('utf-8'))
      sources.append(source)
      failures += compare(source, lexer_type, expected)
    for idx, text in enumerate(python_samples()):
      source = Source(f'<sample {idx}>', text.encode('utf-8'))
      expected = list(tokenize.generate_tokens(io.StringIO(text).readline))
      failures += compare(source, lexer_type, expected)
    for rejected_path, reason in rejected: print(f'Stdlib rejected: {rejected_path}: {reason}')
    print(f'Compared {len(sources)} files and {len(python_samples())} samples; '
      f'{len(rejected)} stdlib rejections; {failures} failures.', flush=True)
    if failures: exit(1)
    if not self.runs: return
    unicode_source = Source('<unicode benchmark>', ''.join(unicode_samples() * 100).encode('utf-8'))
    for name, corpus in [('repository', sources), ('unicode', [unicode_source])]:
      decoded = [source.text.decode('utf-8') for source in corpus]
      count_bytes = sum(len(source.text) for source in corpus)
      print(f'{name}: {len(corpus)} sources; {count_bytes:,} UTF-8 bytes; one warmup; {self.runs} measured runs.', flush=True)
      for label in ('detailed', 'adapted', 'stdlib'):
        times = []
        counts = []
        for run in range(self.runs + 1):
          gc.collect()
          start = perf_counter()
          count = 0
          if label == 'stdlib':
            for text in decoded: count += sum(1 for _ in tokenize.generate_tokens(io.StringIO(text).readline))
          else:
            for source in corpus:
              scanner = PythonLexer(source, lexer_type)
              tokens = iter(scanner) if label == 'detailed' else python_tokens(source, scanner)
              count += sum(1 for _ in tokens)
          elapsed = perf_counter() - start
          if run:
            times.append(elapsed)
            counts.append(count)
        print(f'  {label}: median={median(times):.3f}s min={min(times):.3f}s max={max(times):.3f}s; '
          f'{counts[0]:,} tokens', flush=True)


def compare(source:Source[bytes], lexer_type:type[DictLexerBase], expected:list[tokenize.TokenInfo]) -> int:
  scanner = PythonLexer(source, lexer_type)
  detailed = list(scanner)
  actual = list(python_tokens(source, detailed))
  pos = 0
  for token in detailed:
    if token.pos != pos:
      print(f'{source.name}: coverage gap/overlap at {pos}: {token}')
      return 1
    pos = token.end
  if pos != len(source.text):
    print(f'{source.name}: missing source suffix at {pos}')
    return 1
  if scanner.issues:
    print(f'{source.name}: {scanner.issues[:3]}')
    return 1
  for idx in range(max(len(expected), len(actual))):
    exp = expected[idx] if idx < len(expected) else None
    act = actual[idx] if idx < len(actual) else None
    if exp is None or act is None or exp[:4] != act[:4] or exp.exact_type != act.exact_type:
      print(f'{source.name}: token {idx}:\n  stdlib: {exp}\n  legs:   {act}')
      return 1
  return 0


if __name__ == '__main__': main()
