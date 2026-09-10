# OverType 2.4.2

Bundled editor from `overtype.urls`, with its MIT license.

## HTMX integration

Settings changes send the current Markdown to Python. HTMX applies the returned editor attributes.
The editor and settings controls are locked during the request to prevent lost edits.
The toolbar controls editing and preview modes.

## Known limitations

Changing toolbar visibility, statistics, or auto-resize rebuilds the editor:

* Undo history and selection may reset.
* Literal `\r`, `\n`, and `\t` sequences become control characters, altering the Markdown.
