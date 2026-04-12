# `pithy.html`

The `pithy.html` subpackage provides a DOM-like interface for building HTML object trees.
It is primarily used for constructing HTML documents.
It can also use `lxml` to parse HTML into a tree, and provides utilities for searching and manipulating trees.

The interface is designed to be convenient to write out complex HTML by hand as well-typed Python code.

Key points:
* `pithy.markup.Mu` is the base class that provides the document tree interface.
* `HtmlNode` is the base class for HTML nodes.
* Classes are provided for each HTML tag, e.g. `Html`, `Body`, `Div`, `Span`, etc.
* `HtmlNode.parse()` parses a string or bytes into a tree.
* `HtmlNode.parse_file()` parses a file into a tree.
* `HtmlNode.render()` renders a tree into an iterator of strings.
* `HtmlNode.render_str()` does the same but returns a single string.
* `cl` is used as a shorthand for the `class` attribute so that it does not conflict with the python `class` keyword.


Families of search methods are provided:
* `find_all()`: find all matching nodes in the subtree rooted at this node, returning an iterator of nodes.
* `find_opt()`: find the first matching node in the subtree rooted at this node, returning an optional node.
* `find()`: find the first matching node in the subtree rooted at this node, returning a single node.
* `pick_all()`: find all matching direct children of this node, returning an iterator of nodes.
* `pick_opt()`: find the first matching direct child of this node, returning an optional node.
* `pick()`: find the first matching direct child of this node, returning a single node.
