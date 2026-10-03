<!-- Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/. -->

# Legs Grammar Reference

A grammar file defines named patterns. It can also define modes, which are sets of patterns, and the transitions between modes.
The [readme](readme.md#grammar-files) describes the file structure.


# Patterns

A pattern is a regular expression over characters. Each pattern defines one token kind.
Spaces and newlines inside a pattern are ignored. `//` begins a comment that extends to the end of the line.

## Atoms

* A printable ASCII character matches itself, unless it is one of the operators listed here.
  For example `.`, `{`, `"` and `:` are ordinary characters.
* `\` escapes the next character:
  * `\0` is null, `\f` form feed, `\n` newline, `\r` carriage return, `\t` tab and `\s` a single space.
  * `\\ \# \| \$ \? \* \+ \( \) \[ \] \& \- \^ \: \/ \,` match the escaped character.
  * Any other escape is an error.
* `$Name` matches one character of a named class, e.g. `$Dec` or `$Ascii_Letter`. See [Named Character Classes](character-classes.md).
* `[...]` is a character set; see below.
* `(...)` groups a pattern.
* `,` is a commitment barrier; see [Incomplete Tokens and Commitment](readme.md#incomplete-tokens-and-commitment).

Non-ASCII characters cannot be written in a pattern, and there are no code point escapes. Use a named class to match them.

## Operators

From tightest to loosest:

* `p?` matches `p` or nothing; `p*` matches zero or more; `p+` matches one or more.
* `p q` matches `p` followed by `q`.
* `p | q` matches `p` or `q`.

## Character Sets

A character set matches one character. Inside the brackets:

* A character, an escape or a `$Name` is a set. A nested `[...]` groups a set.
* Sets written next to each other form a union: `[$Ascii_Letter $Dec _]`.
* `a & b` is the intersection, `a - b` the difference and `a ^ b` the symmetric difference.
  These three have equal precedence and apply from left to right. Union binds tighter.
  For example `[$Letter $Number - $Ascii]` is the letters and numbers outside of ASCII.

The only special characters inside the brackets are `[ ] & - ^ $ \` and space. For example `|`, `(` and `,` are ordinary characters.

## Differences from Common Regular Expression Syntax

* `.` is an ordinary character. There is no wildcard; use a class such as `$Readable`.
* `-` in a character set is the difference operator. There are no ranges: `[a-z]` is `a` without `z`, which is just `a`.
* `^` is an infix operator. There is no negated set; subtract from a class instead, e.g. `[$Ascii - \n]`.
* There are no counted repetitions such as `x{2}`, no anchors and no lookahead.
* `\s` is a single space, not a whitespace class.


# Overlapping Patterns

The order of the patterns does not matter. The lexer always takes the longest match in the current mode.
When two patterns in a mode match the same text, Legs resolves the choice as follows:

* If one pattern matches only texts that the other also matches, then the narrower pattern wins.
  The usual case is a keyword such as `if` and a general `name` pattern: `if` lexes as the keyword and `iff` as a name.
* Otherwise the grammar is rejected with the error `Rules are ambiguous`.

A pattern that matches the empty string is also rejected.


# Modes and Transitions

The lexer keeps a stack of modes. Only the patterns of the mode on top of the stack can match.
A transition `from_mode : open_kind :: push_mode : close_kind` has two effects:

* When the lexer is in `from_mode` and produces an `open_kind` token, it pushes `push_mode`.
* When it then produces a `close_kind` token in `push_mode`, it pops back to `from_mode`.

The `close_kind` pops only the mode that this transition pushed. The same kind in another context is an ordinary token.
Each token records the mode in which it was matched.
