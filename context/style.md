# Style

## Prose Style

Use succinct language. Avoid overly complex sentences.
* If a sentence contains more than one parenthetical, colon, semicolon, em-dashes, or relativizer (which/where/when/that etc)
  then it may be difficult to read and should be reconsidered.

Adjectives like "genuine" and "honest" are not be necessary; the entire discourse should have those qualities.

Do not use excessive jargon, industry speak, flattery, signposting, performative cognition, affective framing, folksy idioms,
filler, or marketing/casual/feel-good language.

## Code Style
* 2-space indentation (not 4-space).
* Line length: 128 characters; wrap long function declarations past that length, not per parameter.
* Do not wrap at shorter lengths; 128 is our page width.
* Double newlines between functions.
* Double newlines between methods, except for very compact classes where no methods have blank lines.
* Triple newlines between classes that have double-newline method separation.
* Use descriptive, concise variable names.
  * `el` for elements
  * `idx` for indices when passed as an argument (not just `i`).
* Prefer single quotes for strings.
* Use lowercase for constants and global vars, not all caps.
* Always ask before adding external dependencies.
* Use proper capitalization and periods in comments, docstrings and commit messages.
* Do not put non-ascii characters like em-dashes, arrows or fancy quotes in code comments or docstrings
  unless there is is a specific reason, for example if you were describing a unicode character.
* Add standard license text as a comment to all files that support comments:
  * For pithy and other CC0 projects:
    `Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.`
  * For proprietary projects, write the proper owner into this standard copyright notice:
    `# © {OWNER}. All Rights Reserved.`

### Python Style
* Python 3.14+, strict typing with mypy.
* Do not import `__future__` annotations or use strings for types; 3.14 supports deferred annotations.
* Type hints required.
* Use the modern `type` keyword and forward references wherever appropriate.
* Type declarations omit spaces after colons and inside of types, e.g `def f(x:dict[str,int]) -> None: ...`.
* Use `just isort` to normalize imports.
* No bare `# type: ignore`; always add error codes.
* Error handling: early returns, custom exceptions where they clarify intent or need to be caught, explicit error messages.
* Docstrings: single quotes for brief docs, triple single-quotes for multi-line. Use markdown syntax, not rst.
* `if __name__ == '__main__': main()` should always be inlined, not two lines.
* If you encounter circular import problems:
  * Factor out interdependent code from `__init__` into leaf submodules. This reduces the most common circularity problems.
  * Consider reorganizing packages/modules so that they are less circular. This usually deserves some discussion and approval.
  * Use lazy imports within functions as a last resort; doing so delays imports and can therefore hide problems.

## Markdown Style
When authoring markdown:
* Use `#` only, never the underline syntax.
* Use `*`, not `-` for lists.
* For prose text:
  * Unlike source code, do not hard-wrap lines at a fixed column; you can rely on soft wrap.
  * You can however use line breaks after sentences.
  * Especially do not hard-wrap blockquote text, because then the `>` characters are interleaved at random points in the text.
  * Code blocks should preserve the wrapping of the embedded code.
* Wrap source code at 128 characters like we do everywhere else.
* Do not use excessive emphasis bold/italics. Only use the asterisk syntax for emphasis, never underscores.
* Never use tab characters for code blocks.
