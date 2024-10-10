# Style

## Commit Messages

The overarching point of these guidelines is to be considerate of the future reader. Remember that the code, comments, and commit messages are all read in the context of trying to solve problems. The commit message today becomes a historical detail tomorrow.

Please write clear and concise commit messages.
* Try to use a present tense, imperative verb describing the action the commit has on the codebase:
  * "Remove unused import."
  * **not** "Removing..." or "Removed..."
  * "Update project dependencies." is better than "Project dependencies."
* Use capitalization and punctuation:
  * "Add new feature."
  * **not** "add new feature"
* For changes to a single area of the codebase, prefix the commit with the submodule namespace. For long namespace paths, it is ok to omit all but the last two or three path components. For example:
  * ".web.browser: add support for HTTP/4."


## Code Formatting

* 2 spaces for indentation.
* 128 character line limit.
* No trailing whitespace.
* No trailing newlines.
* Two newlines between function definitions.
* For major class definitions with two newlines in between methods, put three newlines between the class definitions.
* __No spaces between__:
  * Function name and opening parenthesis: `def foo():`, not `def foo ():`.
  * Function parentheses and arguments: `def foo(x:int) -> None:`, not `def foo(x: int)->None:`.
  * parameter/variable declarations and type annotations: `x:int`, not `x: int`.
  * parameter names/types and default values: `x:int=0`, not `x: int = 0`.
  * inline list/tuple/dict literals and their opening/closing brackets/braces: `[1, 2, 3]`, not `[ 1, 2, 3 ]`.
* Prefer single quote over double quote for strings.
