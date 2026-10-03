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


# Grammar Files

A grammar file consists of sections. A section header is a line that begins at column 0 with `# ` and the section name.
The sections can appear in any order and can be repeated. Text preceding the first header is treated as patterns.

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

* `License` text is copied into the generated code. It consists of the text following the colon and any following lines.
* `Patterns` entries have the form `name: pattern`. A bare `name` is a literal pattern matching the name itself.
* `Modes` entries have the form `mode: pattern_name ...`. If there are no modes then all patterns belong to the `main` mode.
* `Transitions` entries have the form `from_mode : open_kind :: push_mode : close_kind`.

Within a section, a line that begins at column 0 begins an entry.
An indented line continues the previous entry. In the patterns section a line beginning with `|` does too.
`//` begins a comment that extends to the end of the line.

The file is split into sections and entries by these line shapes before any pattern is parsed.
Therefore a mistake in one pattern, such as an unclosed `[`, is reported for that entry alone.
The consequence is that a pattern line cannot begin with `# ` at column 0; indent the line or write `\#`.

# Unicode Character Classes

Legs uses the `pithy.unicode` subpackage for up-to-date Unicode data.

See [Named Character Classes](character-classes.md) for the supported `$Name` references, aliases and set operations.


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

`legs -match` checks strings against the NFA and both DFAs of a mode, without generating code.

Tests that are too slow for the routine checks are in `legs_/test`; run them with `just test-full`.

Compilation and generated lexer runtime benchmarks are in [perf/](perf/readme.md).


# Incomplete Tokens and Commitment

An `invalid` token contains bytes that cannot start any pattern in the current mode.
An `incomplete` token contains a prefix that began matching but has no eligible complete match.
The failure location is the start of an invalid token or the end of an incomplete token.
Incomplete tokens can end before an offending character or at the end of the input range.

Normally the lexer remembers the longest complete match and falls back to it if a longer attempt fails.
A comma outside a character set is a zero-width **commitment barrier** that discards complete matches ending before it:

```text
number: $Dec+ | 0 [x X], $Hex+
```

For `0xG`, the barrier prevents fallback to decimal `0`.
The lexer emits `incomplete` for `0x`, leaves `G` unconsumed, and resumes lexing there.
For `0x` at EOF it emits the same incomplete prefix; `0x12` is a complete number.
Commitment does not consume input or change the mode stack.

Place another barrier after a separator that requires another digit:

```text
hex: 0 [x X], _? $Hex ($Hex | _, $Hex)*
```

Now `0x12_` cannot fall back to `0x12`.
Whitespace around a commitment comma is optional.
Use `\,` for a literal comma outside a character set; `[,]` and `[a,b]` contain literal commas.
Existing grammars with literal unescaped commas outside character sets must escape them.

A barrier applies across all competing patterns in the current token attempt.
It preserves complete matches at the barrier's position and permits later matches from any rule.
A later barrier discards those matches if they end before it.
Barriers in optional or repeated expressions apply whenever any active NFA path reaches them.
A barrier at the token's start has no earlier match to discard; a grammar that can match an empty token is still rejected.

Commitment is separate from token-boundary validation: `123abc` can still be a number followed by a name, and `0x12Z` can still be a hexadecimal number followed by a name.
No identifier-adjacency restriction is implied by a barrier.

The table-driven Python and Swift backends support commitment.
The experimental `python-re` backend rejects grammars containing barriers rather than silently changing their meaning.
The NFA property oracle checks commitment independently of DFA construction and minimization.


# Python Details

Generated Python lexer classes conform to `tolkien.LexerProtocol`, so they can be passed to `pithy.parse.Parser`.

A lexer can be given a range of the source text and a start mode. This allows a parser that frames the text by other means to lex each framed range in the appropriate mode; `legs.parse` does this for grammar files using `pithy.sectsyn`.


# Provided Lexers

The supplied grammars are in [grammars/](grammars/), with documentation beside each grammar:

* [ASCII](grammars/ascii.md): runs of ASCII characters grouped by category; useful for examples and benchmarks.
* [Unicode](grammars/unicode.md): runs of Unicode characters grouped by general category.
* [Legs](grammars/legs.md): pattern expressions, character sets and declarations within Legs grammar files.
* [Python](grammars/python.md): experimental Python 3.14 lexing with string and interpolation modes, individual escapes and diagnostic byte spans. A coordinator handles indentation and nested strings; an adapter supports comparison with stdlib `tokenize`.


# Column Pathology

Column numbers are a common feature of compiler error messages, and text editors. However in the modern world of Unicode columns are surprisingly ill-defined. Swift defines the Character type as an "extended grapheme literal", which is meant to represent a single visual character and can be composed of arbitarily many code points. Many modern languages like Python 3 count unicode scalars (code points), while older ones like JavaScript and Objective-C count 16 bit BMP code points. Further confounding the situation is the fact that some characters are rendered as double-width, so regardless of language the notion of character offset diverges from graphical offset within an editor or an console error message.

I hope that Legs will eventually provide a robust notion of textual distance. It seems that we will need to define several measures of distance: UTF-8/byte distance, UTF-16 distance, character distance, and visual distance. The latter two differ because there are code points that Swift treats as distinct characters but represent zero visual distance (e.g. Zero-width space), and some characters are rendered at double-width. Perhaps the more intelligible metric would be "cursor distance", roughly meaning number of arrow key presses, but this is likely to be application/OS dependent.
