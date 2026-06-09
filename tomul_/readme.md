# Tomul

Tomul is a small python library for reading and writing TOML files.

# Why?

Tomli-W is the mainstream way of writing TOML in Python. This module is derived from it, and I am grateful for the original.

I think that the rationale presented by Tomli-W for not defaulting to multiline strings is erroneous:
a '\r' character can just as easily be emitted by the multiline renderer.
This module does that, and simplifies some other aspects of the implementation.
It also changes the indent default to two spaces and the line wrap to 128 chars, which is unconventional but my preference.

Additionally, I am trying to minimize my third party dependencies given the rise in software supply chain attacks.
Since TOML output is a required part of the development process for this project it made sense to eliminate a dependency here.
