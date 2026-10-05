# Detailed Python lexing

[python.legs](python.legs) and `legs.langs.python.py_lexer.PythonLexer` provide an experimental Python 3.14 lexer.
The grammar is also a compilation benchmark with realistic modes and Unicode character sets.

The primary output is a detailed, lossless stream of `tolkien.Token` objects with UTF-8 byte spans.
Spaces and comments remain in the stream. Indentation and end markers are included; structural tokens can have empty spans.
Ordinary strings retain opening delimiters, text runs, individual escapes and closing delimiters.
For example, `'α\n\x41'` produces `string_start`, `text`, `escape_simple`, `escape_hex` and `string_end`.
The interior tokens carry mode `str_s`, so a consumer can interpret their context without reconstructing it from the spelling.

# Grammar and coordination

The grammar recognizes names, numbers, operators, trivia, string openers and string fragments.
There are separate single and triple quote modes for ordinary, raw, bytes and interpolated strings, plus format specifications.
Template strings use the same interior DFAs as f-strings while retaining distinct opening and closing token kinds.
Raw bytes use raw string modes with additional ASCII validation.

The Python coordinator selects the DFA mode for each fragment.
It handles indentation, nested delimiters, replacement expressions, conversions and format specifications.
This is why the grammar has no static `Transitions` section: quote reuse and replacement-field colons require context from the coordinator.
Running the grammar's generated lexer alone in `main` mode does not tokenize complete Python strings.

Non-ASCII name candidates are checked with Python's `str.isidentifier`, using the running interpreter's Unicode database.
The spelling is preserved, including combining characters and identifiers whose NFKC normalization differs.
String contents support Unicode scalar values, including unassigned and private-use characters.

```python
from pathlib import Path

from legs.cache import cached_lexer_class
from legs.langs.python.py_lexer import PythonLexer
from tolkien import Source

fragments = cached_lexer_class(Path('legs_/langs/python/python.legs'), Path('_build/langs/python.py'))
source = Source('example.py', b"name = 'hello\\n'\n")
scanner = PythonLexer(source, fragments)
for token in scanner:
  print(token.mode, token.kind, source.text[token.slc])
for issue in scanner.issues:
  print(issue.kind, issue.pos, issue.end, issue.message)
```

`cached_lexer_class` compiles it only when the generated file is stale.
Load the fragment lexer once and reuse it across sources. `PythonLexer` instances are single-use.
The grammar is a repository resource; callers supply its path when building a lexer.

# Diagnostics and recovery

The scanner retains Legs' `invalid` and `incomplete` fragment tokens.
It also accumulates `LexIssue` diagnostics with byte spans and, where applicable, the opening delimiter's position.
For a malformed escape such as `'\xG1'`, the incomplete prefix is retained and the diagnostic points at `G`.
For a truncated escape such as `'\x4`, the incomplete fragment is retained and the diagnostic points at EOF.
An unclosed string also emits an empty `incomplete` token at EOF.
An unescaped newline in a single-quoted string ends that string and resumes code lexing at the newline.

Additional checks identify non-ASCII bytes-literal characters, invalid identifier characters, unmatched delimiters, inconsistent dedents, unknown Unicode character names and out-of-range Unicode escapes.
Unknown escapes remain distinct tokens; this lexer does not reproduce Python's warning machinery.

This is lexical analysis, not Python syntax validation. It does not validate expressions, conversion names or format-specifier semantics.
Its error messages and recovery behavior are deliberately independent of CPython's.
Numeric prefixes, exponents and digit separators use comma commitment barriers to retain malformed or truncated prefixes.
Token-boundary restrictions such as `123abc`, and ambiguous tab/space indentation checks, remain future work.

# Stdlib comparison

`legs.langs.python.py_tokenize.python_tokens` adapts the detailed stream to Python 3.14 `tokenize.TokenInfo` objects.
Only this adapter aggregates ordinary string fragments into `STRING` tokens.
It preserves the f-string and template-string token structure, including CPython's doubled-brace middle-token boundaries.
It does not call the stdlib tokenizer for recognition.

The compatibility contract is token type, spelling, start/end code-point positions and `exact_type` on lexically valid input.
`TokenInfo.line` contains the starting physical line; CPython sometimes supplies a larger internal buffer, so this field is not compared.
The adapter accepts decoded source re-encoded as UTF-8, with LF or CRLF line endings.
Decode encoding cookies and normalize standalone CR before calling it; the corpus command uses `tokenize.open` for this boundary step.
There is no `ENCODING` token, matching `tokenize.generate_tokens` rather than the bytes-oriented `tokenize.tokenize` API.

```sh
# Compile the grammar if it is stale, compare the repository and synthetic sources, then benchmark.
just perf-legs-python

# Differential checks only, or selected files.
just perf-legs-python -runs 0
just perf-legs-python legs_/legs/langs/python/py_lexer.py -runs 3

# Detailed fragment and malformed-input tests; compiles the grammar if it is stale.
just test-legs-langs python

# Compilation stages alone.
just perf-legs-compile legs_/langs/python/python.legs -runs 3 -warmups 1
```

The repository corpus includes tracked and non-ignored untracked `.py` and `.pyi` files.
Every file accepted by stdlib is compared; stdlib rejections are listed and counted rather than silently dropped.
The harness also checks exact byte coverage and requires no Legs diagnostics for the accepted corpus.
Synthetic cases cover combining identifiers, normalization-sensitive names, supplementary-plane identifiers, UTF-8 boundaries, nested interpolation, raw strings and template strings.
The unit tests exercise every prefix/quote combination and truncate an interpolated Unicode source at every byte position.

The tests and the corpus command share the generated lexer at `_build/langs/python.py`.
`just build-legs-langs python` generates it; each of them also regenerates it when it is stale.

The reference specifications are [Python 3.14 lexical analysis](https://docs.python.org/3.14/reference/lexical_analysis.html) and the [`tokenize` API](https://docs.python.org/3.14/library/tokenize.html).
