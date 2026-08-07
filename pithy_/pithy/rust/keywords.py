# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Rust keywords, per https://doc.rust-lang.org/reference/keywords.html.
Keywords that were added in a later edition are included unconditionally, because a name that is only valid in an old
edition is not worth generating.
'''


# Strict keywords can only be used in their syntactic positions. `async`, `await` and `dyn` were added in the 2018 edition.
rust_strict_keywords = frozenset({
  'as', 'async', 'await', 'break', 'const', 'continue', 'crate', 'dyn', 'else', 'enum', 'extern', 'false', 'fn', 'for', 'if',
  'impl', 'in', 'let', 'loop', 'match', 'mod', 'move', 'mut', 'pub', 'ref', 'return', 'self', 'Self', 'static', 'struct',
  'super', 'trait', 'true', 'type', 'unsafe', 'use', 'where', 'while',
})


# Reserved keywords are not yet used, but have the same restrictions as strict keywords.
# `try` was reserved in the 2018 edition, and `gen` in the 2024 edition.
rust_reserved_keywords = frozenset({
  'abstract', 'become', 'box', 'do', 'final', 'gen', 'macro', 'override', 'priv', 'try', 'typeof', 'unsized', 'virtual',
  'yield',
})


# The names that cannot be used as ordinary identifiers.
rust_keywords = rust_strict_keywords | rust_reserved_keywords


# Most keywords can be used as identifiers when written as raw identifiers, e.g. `r#type`. These cannot.
rust_non_raw_keywords = frozenset({'crate', 'self', 'Self', 'super'})
assert rust_non_raw_keywords <= rust_strict_keywords


# Weak keywords have special meaning only in certain contexts, and are valid identifiers elsewhere.
# `'static` is also a weak keyword, but it is a lifetime rather than an identifier.
rust_weak_keywords = frozenset({'macro_rules', 'raw', 'safe', 'union'})
assert rust_weak_keywords.isdisjoint(rust_keywords)
