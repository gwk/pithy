# Pithy Repository: Python libraries and utilities

This repository contains the source code for several Python packages:
* `pithy`: a utility library
* `pithytools`: command line utilities
* `crafts`: build tools
* `iotest`: an integration test harness
* `legs`: a lexer generator
* `tolkien`: a token datatype
* `utest`: a unit test library
* `wu`: the Writeup markup language

All code is dedicated to the public domain under CC0. Opinions vary, but this approach to licensing arguably creates the least burden for users who copy, modify, and intermix the code. Attribution is nonetheless appreciated!

# Packaging Status

Please note that the packages published to PyPI frequently lag behind the state of this repository. If you are interested in a using a package via PyPI, please get in touch.


# Packaging and Installation

## Quick Start
* Installation: `just install` for all packages; `sh/install.sh {package} ...` for specific packages. Invokes `pip install`.
* Development: `just develop` for all packages; `sh/develop.sh {package} ...` for specific packages. Invokes `pip install -e`.

For these commands, the justfile invokes the shell scripts with all package names.

## Details

For each project, pyproject.toml is generated using a short script, `build/gen-pyproject-toml.py`, which merges common values from `common.toml` with the `$PKG/$PKG.toml` to generate `$PKG/pyproject.toml`.


# Packages

These packages used to live in separate repositories but got merged together when versioning became too laborious.
More recently, we moved the package source directories into package subdirectories to be more conventional.
As a result the git history is somewhat unusual.

## Pithy

The code in the `pithy` library first started accumulating around 2010 under a different name. It contains a variety of modules, some of which has been used a lot, other parts that are still rather experimental, and some parts that are or should be abandoned.


## Crafts
Crafts is an odd assortment of build tools, most of which are experimental.


## IOTest
`iotest` is a command line program for doing testing other command line programs. It is designed to make it easy to test for expectations in text file outputs. In particular, it allows for parameterizing tests and shows diffs between expected and actual program output. It can also be used as a harness for running collections of unit tests written with the `utest` library (see below).


## Legs
Legs is a lexer generator. It is currently in an experimental state.


## Pithy Tools
`pithytools` This is a set of miscellaneous command line tools. They were split out from `pithy` so that the core libary no longer installs command line executables.


## Tolkien
`tolkien` is a very small library that defines a Token type for writing parsers in Python. It was factored out of Legs so that I could use the same structure type independently of the lexer generator.


## UTest
`utest` is a small, standalone library that provides basic unit testing. It can be used in conjunction with `iotest`. More recently it gained a standalone harness option: `python3 -m utest [paths...]` will search the given tests for `*.ut.py` and run those.


## Writeup
A markup language similar to Markdown. This is currently in an experimental state. I have plans to rewrite it but it has been on the back burner for years.


# Misc

## UnicodeData
`unicode-data` holds historical versions of the unicode character database.
