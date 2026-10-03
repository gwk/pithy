<!-- Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/. -->

# Legs grammar

[legs.legs](legs.legs) lexes the contents of grammar entries. It does not lex an entire grammar file in one pass.
The parser first splits the file into sections and entries by line shape using `pithy.sectsyn`.

Start each framed range in the mode appropriate to its syntax:

* `pattern`: a pattern expression after the entry name and colon.
* `charset`: the contents of a character set; bracket transitions enter and leave this mode automatically.
* `decl`: a modes or transitions entry.

There is no `main` mode. For example, from the repository root:

```sh
legs-test legs_/grammars/legs.legs -mode pattern '[$Ascii_Letter _]+'
```

The handwritten lexer in `legs.parse` implements the same token interface so the compiler can bootstrap without generated code.
