# Legs

Legs is a lexer generator. It takes as input a `.legs` grammar file consisting of pattern definitions, and outputs lexer source code. The goal of this project is to produce correct Unicode-aware lexers that can be used in a variety of settings, including parsing, reformatting, and syntax coloring.

Legs is distinguished by the following features:
* Parses UTF-8 byte data directly; it does not require a preceding conversion to a unicode string datatype. Unicode errors show up as lexing errors with readable source positions.
* The lexer operates as a stream/iterator, and cannot fail. Instead, it emits tokens marked as invalid or incomplete when it encounters a lexing error and then resumes from the next starting character.
* The pattern definitions can specify multiple modes, and the resulting lexer maintains a stack of modes. This means that in theoretical terms it is not strictly a "deterministic finite automaton". The value of this is that we can parse one language embedded in another, e.g. string formatting syntax or escape tokens within string literals. The lexer still emits a flat stream of tokens, each tagged with both mode and kind, so in a sense the lexer is a hybrid between a traditional lexer and a context free parser.
* The legs syntax for pattern definitions is similar to traditional regular expression syntax, but with several alterations to accommodate the task of writing modern lexers:
  * Spaces and comments are ignored (equivalent to the "extended" mode of Python regular expression syntax).
  * Traditional backslash-escaped character classes are largely replaced by named character classes, denoting the complete set of Unicode classes and several convenience classes as well, (e.g. ASCII subsets, hex characters, etc).
  * Simple character set operations (union, intersection, difference, and symmetric difference).

The output languages currently supported are:
* `python`: a table-driven lexer. This is the reference implementation.
* `swift`: a lexer compiled to a switch statement.
* `python-re`: a lexer that uses compiled regular expressions. It is experimental and slower than the table-driven lexer.
* `dot`: Graphviz diagrams of the automata.


# Usage

Run these examples from the repository root with `legs` installed in your Python environment.

Generate a Python lexer from a grammar:

```sh
legs legs_/grammars/ascii.legs -output ascii_lexer.py -type-prefix Ascii
```

The generated module defines `AsciiLexer`. Without `-type-prefix`, the class is named `Lexer`.
Pass a `tolkien.Source` containing UTF-8 bytes to iterate over tokens:

```python
from ascii_lexer import AsciiLexer
from tolkien import Source

source = Source('example.txt', b'Hello 123\n')
for token in AsciiLexer(source):
  print(token.kind, token.pos, token.end, source.text[token.slc])
```

Target output languages are selected with `-langs`, separated by commas, or inferred from the extension of the `-output` path.
For multiple languages, `-output` supplies the shared output stem:

```sh
legs legs_/grammars/ascii.legs -langs python,swift -output ascii_lexer
```

This writes `ascii_lexer.py` and `ascii_lexer.swift`.
With `-langs` but no `-output`, files are written beside the input grammar.
With neither option, Legs validates and compiles the grammar without writing code.

Use `-stats` to report automaton sizes and compilation times, or `-describe` to print pattern descriptions.
For a quick pattern check without a file:

```sh
legs -patterns 'number: $Dec+' -match 123 -match abc
```

Repeat `-patterns` or `-match` for multiple values. Use `legs -help` for all options.

`-encoding` selects the encoding of the text that the lexer consumes; character sets are compiled to byte sequences in that encoding.
This is a work in progress: only the default `utf-8` is tested, and `legs-test` and the `python-re` output assume it.
The grammar file itself is read with Python's default encoding.


# Grammar Files

A grammar file consists of sections: `License`, `Patterns`, `Modes` and `Transitions`.
See the [Grammar Reference](grammar.md) for the file structure, the pattern syntax, modes, and commitment barriers.
See [Named Character Classes](character-classes.md) for the supported `$Name` references and aliases. The Unicode data comes from the `pithy.unicode` subpackage.

```
# License: Dedicated to the public domain under CC0.

# Patterns
spaces: \s+
word: $Ascii_Letter+
paren_o: \(
paren_c: \)
op:
  \+
| \*

# Modes
main: spaces word paren_o paren_c op

# Transitions
main : paren_o :: main : paren_c
```


# Testing

`legs-test` checks the lexers generated from a grammar against each other:
```
legs-test grammar.legs -mode main 'first input' 'second input'
```
Each input is lexed by a reference lexer built in-process, and the tokens are printed.
The Python and Swift lexers are then generated and run on the same inputs.
Any difference from the reference tokens is reported and causes a nonzero exit code.
Use `-langs` to choose the generated lexers, e.g. `-langs python,python-re`, and `-mode` for a grammar that has no `main` mode.

With `-props`, `legs-test` also checks the reference lexer against the NFA of each mode, using inputs generated from the grammar:
```
legs-test grammar.legs -props
```
The NFA is built directly from the patterns, so this tests DFA construction and minimization.
Each token must be the longest match at its position, and the tokens must cover the input exactly.
The inputs are strings generated from the patterns by [Hypothesis](https://hypothesis.readthedocs.io), and a traversal of every DFA transition.
See `legs.props` for details. The examples are the same on every run unless `-randomize` is given.

`legs -match` checks strings against the NFA, the unminimized DFA and the minimized DFA of a mode, without generating code.

Tests that are too slow for the routine checks are in `legs_/test`; run them with `just test-full`.

Compilation and generated lexer runtime benchmarks are in [perf/](perf/readme.md).


# Python Details

Generated Python lexer classes conform to `tolkien.LexerProtocol`, so they can be passed to `pithy.parse.Parser`.

A lexer can be given a range of the source text and a start mode. This allows a parser that frames the text by other means to lex each framed range in the appropriate mode; `legs.parse` does this for grammar files using `pithy.sectsyn`.


# Provided Lexers

The supplied grammars are in [grammars/](grammars/), with documentation beside each grammar:

* [ASCII](grammars/ascii.md): runs of ASCII characters grouped by category; useful for examples and benchmarks.
* [Unicode](grammars/unicode.md): runs of Unicode characters grouped by general category.
* [Legs](grammars/legs.md): pattern expressions, character sets and declarations within Legs grammar files.
* [Python](grammars/python.md): experimental Python 3.14 lexing with string and interpolation modes, individual escapes and diagnostic byte spans. A coordinator handles indentation and nested strings; an adapter supports comparison with stdlib `tokenize`.


# Column Numbers

Column numbers are a common feature of compiler error messages and text editors. However Unicode character counts are surprisingly ill-defined. Swift defines the `Character` type as an extended grapheme cluster, Python 3 counts Unicode scalars (code points), and older languages like JavaScript and Objective-C count UTF-16 code units. Characters can be zero-width or wide, and can be combining modifiers, and modern text renderers do not entirely agree on the specifics. For this reason Legs lexers do not produce column counts; tokens carry byte offsets only.
The `tolkien` Python library does however compute columns for diagnostics on a best effort basis: labels count code points, and underlines are aligned by estimated terminal width.
