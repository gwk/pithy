<!-- Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/. -->

# Legs Grammar Reference

A grammar file defines named patterns. It can also define modes, which are sets of patterns, and the transitions between modes.


# File Structure

A grammar file consists of sections. A section header is a line that begins at column 0 with `# ` and the section name.
The sections can appear in any order and can be repeated. Text preceding the first header is treated as patterns.
Within the `Modes` section, a line that begins at column 0 with `## ` and a name is a mode header.

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

## main
kinds: spaces word paren_o paren_c op

# Transitions
main : paren_o :: main : paren_c
```

* `License` text is copied into the generated code. It consists of the text following the colon and any following lines.
* `Patterns` entries have the form `name: pattern`. A bare `name` is a literal pattern matching the name itself.
* `Modes` holds one `## name` subsection per mode. The entries of a mode have the form `key: value ...`.
  The `kinds` entry is required; it lists the patterns that belong to the mode, by name.
  The other keys are described under [Line-Aware Modes](#line-aware-modes).
  If there are no modes then all patterns belong to the `main` mode.
* `Transitions` entries have the form `from_mode : open_kind :: push_mode : close_kind`.

Within a section, a line that begins at column 0 begins an entry.
An indented line continues the previous entry. In the patterns section a line beginning with `|` does too.
`//` begins a comment that extends to the end of the line.

The file is split into sections and entries by these line shapes before any pattern is parsed.
Therefore a mistake in one pattern, such as an unclosed `[`, is reported for that entry alone.
The consequence is that a pattern line cannot begin with `# ` or `## ` at column 0; indent the line or write `\#`.


# Patterns

A pattern is a regular expression over characters. Each pattern defines one token kind.
Spaces and newlines inside a pattern are ignored. `//` begins a comment that extends to the end of the line.

## Atoms

* A printable character matches itself, unless it is one of the operators listed here.
  For example `.`, `{`, `"`, `:`, `é` and `→` are ordinary characters.
* `\` escapes the next character:
  * `\n` is newline, `\r` carriage return, `\t` tab and `\s` a single space.
  * `\\ \# \| \$ \? \* \+ \( \) \[ \] \& \- \^ \: \/ \,` match the escaped character.
  * `\H/` matches the code point given by one to six hexadecimal digits `H`, closed by `/`. For example `\e9/`, `\200D/` and `\1F600/`.
    Surrogates and values above `10FFFF` are errors.
    There are no `\0` or `\f` escapes; write null as `\0/` and form feed as `\c/`.
  * Any other escape is an error.
* `$Name` matches one character of a named class, e.g. `$Dec` or `$Ascii_Letter`. See [Named Character Classes](character-classes.md).
* `[...]` is a character set; see below.
* `(...)` groups a pattern.
* `,` is a commitment barrier; see [Incomplete Tokens and Commitment](#incomplete-tokens-and-commitment).

Invisible characters, such as a no-break space or a zero width joiner, are errors. Write them as code point escapes.

## Operators

From tightest to loosest:

* `p?` matches `p` or nothing; `p*` matches zero or more; `p+` matches one or more.
* `p q` matches `p` followed by `q`.
* `p | q` matches `p` or `q`.

## Character Sets

A character set matches one character. Inside the brackets:

* A character, an escape or a `$Name` is a set. A nested `[...]` groups a set.
* A character set that contains no characters is an error.
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
The names `invalid`, `incomplete` and `end_of_text` are reserved for the token kinds that the lexer produces itself.


# Modes and Transitions

The lexer keeps a stack of modes. Only the patterns of the mode on top of the stack can match.
A transition `from_mode : open_kind :: push_mode : close_kind` has two effects:

* When the lexer is in `from_mode` and produces an `open_kind` token, it pushes `push_mode`.
* When it then produces a `close_kind` token in `push_mode`, it pops back to `from_mode`.

The `close_kind` pops only the mode that this transition pushed. The same kind in another context is an ordinary token.
Each token records the mode in which it was matched.


# Line-Aware Modes

A mode with a `line_break_kind` entry is line-aware. The entry names the kind that ends a line, typically a newline pattern.

```
## main
kinds: spaces newline word paren_o
line_break_kind: newline
```

In a line-aware mode the lexer emits an empty `end_of_line` token before the line break of each line that holds another token.
If the last line holds a token and has no line break, the token is emitted at the end of the text.
A line that holds only its line break produces nothing. A parser can therefore drop the line break tokens and use `end_of_line` as a terminator.

The rule applies only while the mode on top of the stack is line-aware. A pushed mode that is not suspends it:
a line that begins in the line-aware mode and continues through brackets or a string ends at the next line break in the line-aware mode.

`end_of_line` is a reserved kind, like `invalid`, `incomplete` and `end_of_text`. It is the only empty token apart from `end_of_text`.


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
The NFA property oracle checks commitment independently of DFA construction and minimization.
