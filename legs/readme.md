# Legs

Legs is a lexer generator. It takes as input a `.legs` file consisting of pattern definitions, and outputs code. Currently it only outputs Swift code, but I would like to extend it to support other languages. The long-term goal of this project is to support correct generation of Unicode-aware lexers for a variety of targets (outputs), including various programming languages but also their regular expression engines and text editor syntax definitions. No more nightmare TextMate language definitions!

Legs is distinguished by the following features:
* Parses UTF-8 data directly; it does not require a preceding conversion to the String datatype.
* The lexer operates as a stream/iterator, and cannot fail. Instead, it will emit tokens marked as invalid or incomplete when it encounters a lexing error and then resumes from the next starting character.
* The pattern definitions can specify multiple modes, and the resulting lexer will maintain a stack during operation to track modes. This means that in theoretical terms it is not a "deterministic finite automata", but rather a "pushdown automaton". The value of this is that we can parse one language embedded in another, e.g. string formatting syntax within string literals. The emitted result is still a flat stream of tokens though, so the lexer is a hybrid between a traditional lexer and a context free parser.
* The legs syntax for pattern definitions is similar to traditional regular expression syntax, but with several alterations to accommodate the task of writing modern lexers:
  * Spaces and comments are ignored (equivalent to the "extended" mode of Pythno regular expression syntax).
  * Traditional backslash-escaped character classes are largely replaced by named character classes, denoting the complete set of Unicode classes and several convenience classes as well, (e.g. ASCII subsets, hex characters, etc).
  * Simple character set operatons (union, intersection, difference, and symmetric difference).


# TODO

* Better documentation.
* More testing.
* Support UTF-16/UCS2 and UTF-32 representations as well.
* Performance analysis of generated Swift code.


# Incomplete Tokens
TODO.


# Column Pathology

Column numbers are a common feature of compiler error messages, and text editors. However in the modern world of Unicode columns are surprisingly ill-defined. Swift defines the Character type as an "extended grapheme literal", which is meant to represent a single visual character and can be composed of arbitarily many code points. Many modern languages like Python 3 count unicode scalars (code points), while older ones like JavaScript and Objective-C count 16 bit BMP code points. Further confounding the situation is the fact that some characters are rendered as double-width, so regardless of language the notion of character offset diverges from graphical offset within an editor or an console error message.

I hope that Legs will eventually provide a robust notion of textual distance. It seems that we will need to define several measures of distance: UTF-8/byte distance, UTF-16 distance, character distance, and visual distance. The latter two differ because there are code points that Swift treats as distinct characters but represent zero visual distance (e.g. Zero-width space), and some characters are rendered at double-width. Perhaps the more intelligible metric would be "cursor distance", roughly meaning number of arrow key presses, but this is likely to be application/OS dependent.
