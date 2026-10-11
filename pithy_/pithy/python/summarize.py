# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A simple Python analysis tool that outputs information about package contents.

Dotted targets resolve statically through the running Python environment; see `pithy.python.package.resolve_module_installed`.
'''

import ast
from ast import parse as parse_ast

from ..cmdparse import Cmd, flag, pos
from .package import resolve_spec_paths, SpecResolutionError


class SummarizeCmd(Cmd):
  'Summarize Python package contents.'

  targets:list[str] = pos(doc='File paths, directories, and/or dotted module names to summarize.')
  safe_path:bool = flag('-P', doc='Omit the implicit Python search directory; also enabled by PYTHONSAFEPATH.')


  def run(self) -> None:
    try: paths = [path for spec in self.targets for path in resolve_spec_paths(spec, safe_path=self.safe_path)]
    except SpecResolutionError as e: exit(f'pithy.python.summarize error: {e}')
    for path in paths:
      summarize_path(path)


def main() -> None: SummarizeCmd.main()


def summarize_path(path:str) -> None:

  try:
    with open(path) as f: text = f.read()

    tree = parse_ast(text, filename=path)

    for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef):
        _print_function_info(node)
      elif isinstance(node, ast.ClassDef):
        _print_class_info(node)

  except Exception as e:
    print(f'Error processing {path}: {e}')


def _print_function_info(node: ast.FunctionDef) -> None:
  'Print information about a function definition.'

  print(f'\nFunction: {node.name}')

  # Print annotations
  if node.args.args or node.returns:
    annotations = []
    for arg in node.args.args:
      if arg.annotation:
        annotations.append(f'{arg.arg}: {ast.unparse(arg.annotation)}')
      else:
        annotations.append(arg.arg)

    return_annotation = ''
    if node.returns:
      return_annotation = f' -> {ast.unparse(node.returns)}'

    print(f'  Signature: {node.name}({", ".join(annotations)}){return_annotation}')

  # Print docstring
  docstring = ast.get_docstring(node)
  if docstring:
    print(f'  Docstring: {docstring}')


def _print_class_info(node: ast.ClassDef) -> None:
  '''Print information about a class definition.'''
  print(f'\nClass: {node.name}')

  # Print base classes
  if node.bases:
    bases = [ast.unparse(base) for base in node.bases]
    print(f'  Bases: {', '.join(bases)}')

  # Print docstring
  docstring = ast.get_docstring(node)
  if docstring:
    print(f'  Docstring: {docstring}')

  # Print methods
  for item in node.body:
    if isinstance(item, ast.FunctionDef):
      print(f'  Method: {item.name}')
      method_docstring = ast.get_docstring(item)
      if method_docstring:
        print(f'    Docstring: {method_docstring}')




if __name__ == '__main__': main()
