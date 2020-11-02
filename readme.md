# Pithy: Python libraries and utilities

This repository contains the source code for the `pithy` library, as well as several other projects that depend on it. These dependent projects used to live in separate repositories but got merged together when versioning became too laborious. Each repository has its own readme.


## Pithy library

The code in the `pithy` library first started accumulating around 2010. It contains a variety of code, some of which has been used a lot, other parts that are still rather experimental, and probably a few parts that are or should be abandoned. A lot of it is rather idiosyncratic and pays little heed to various conventions in the Python community.


## Crafts
Crafts is an odd assortment of build tools.


## IOTest
`iotest` is a command line program for doing testing other command line programs. It is supposed to make it easy to test for expectations in text file outputs. In particular, it allows for parameterizing tests and shows diffs between expected and actual program output.


## Legs
Legs is a lexer generator. It is currently in an experimental state.


## Pithy Tools
`pithytools` This is a set of miscellaneous command line tools. They used to be part of Pithy but it seemed better that the core libary not come with a bunch of executables that potential users might not want.

## Tolkien
`tolkien` is a very small library that defines a Token type for writing parsers in Python. It was factored out of Legs so that I could use the same structure type in both Legs-based and in projects that do not depend on Legs.


## UTest
`utest` is a small, standalone library that provides basic unit testing. It can be used in conjunction with `iotest`.


## Writeup
A markup language similar to Markdown. This is currently in an experimental state. I have plans to rewrite it but it has been on the back burner for several years.
