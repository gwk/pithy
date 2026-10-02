# Legs

Legs is a lexer generator. It takes as input a `.legs` grammar file consisting of pattern definitions, and outputs lexer source code. The goal of the project is the correct generation of Unicode-aware lexers.

The output languages are selected with `-langs`, separated by commas, or by the extension of the `-output` path:
* `python`: a table-driven lexer. This is the reference implementation.
* `swift`: a lexer compiled to a switch statement.
* `python-re`: a lexer that uses compiled regular expressions. It is experimental and slower than the table-driven lexer.
* `dot`: Graphviz diagrams of the automata.

Generated Python lexer classes conform to `tolkien.LexerProtocol`, so they can be passed to `pithy.parse.Parser`.
A lexer can be given a range of the source text and a start mode. This allows a parser that frames the text by other means to lex each framed range in the appropriate mode; `legs.parse` does this for grammar files using `pithy.sectsyn`.

Legs is distinguished by the following features:
* Parses UTF-8 data directly; it does not require a preceding conversion to the String datatype.
* The lexer operates as a stream/iterator, and cannot fail. Instead, it will emit tokens marked as invalid or incomplete when it encounters a lexing error and then resumes from the next starting character.
* The pattern definitions can specify multiple modes, and the resulting lexer will maintain a stack during operation to track modes. This means that in theoretical terms it is not a "deterministic finite automata", but rather a "pushdown automaton". The value of this is that we can parse one language embedded in another, e.g. string formatting syntax within string literals. The emitted result is still a flat stream of tokens though, so the lexer is a hybrid between a traditional lexer and a context free parser.
* The legs syntax for pattern definitions is similar to traditional regular expression syntax, but with several alterations to accommodate the task of writing modern lexers:
  * Spaces and comments are ignored (equivalent to the "extended" mode of Python regular expression syntax).
  * Traditional backslash-escaped character classes are largely replaced by named character classes, denoting the complete set of Unicode classes and several convenience classes as well, (e.g. ASCII subsets, hex characters, etc).
  * Simple character set operations (union, intersection, difference, and symmetric difference).


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


# TODO

* Document the named character classes.
* Support UTF-16/UCS2 and UTF-32 representations as well.


# Incomplete Tokens
TODO.


# Column Pathology

Column numbers are a common feature of compiler error messages, and text editors. However in the modern world of Unicode columns are surprisingly ill-defined. Swift defines the Character type as an "extended grapheme literal", which is meant to represent a single visual character and can be composed of arbitarily many code points. Many modern languages like Python 3 count unicode scalars (code points), while older ones like JavaScript and Objective-C count 16 bit BMP code points. Further confounding the situation is the fact that some characters are rendered as double-width, so regardless of language the notion of character offset diverges from graphical offset within an editor or an console error message.

I hope that Legs will eventually provide a robust notion of textual distance. It seems that we will need to define several measures of distance: UTF-8/byte distance, UTF-16 distance, character distance, and visual distance. The latter two differ because there are code points that Swift treats as distinct characters but represent zero visual distance (e.g. Zero-width space), and some characters are rendered at double-width. Perhaps the more intelligible metric would be "cursor distance", roughly meaning number of arrow key presses, but this is likely to be application/OS dependent.
