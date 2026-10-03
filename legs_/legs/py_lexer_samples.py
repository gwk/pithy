# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Valid Python 3.14 sources for differential tests and repeatable Unicode benchmarks.'


def python_samples() -> list[str]:
  'Cover the token kinds, string prefixes and interpolation forms of Python.'
  return [
    '', '\n', '  ', '# comment', 'x', 'x  ', 'x\n  ', '\t# comment\n',
    'if x:\n\tpass\n\n# out\ny = (\n  1 +\n  2\n)\n',
    'x = 1 + \\\n  2\n',
    'x = 0x_Ff + 0b_101 + 0o_17 + 1_234 + .5 + 1. + 1e-4 + 2.5e+6j + 1_0j\n',
    'x += 1; y **= 2; z //= 3; a <<= 2; b >>= 1; x := y; ...\n',
    "x = 'a\\n\\x41\\u03b1\\U0001f600\\N{LATIN SMALL LETTER A}\\123'\n",
    'x = "a\\\nb"\n',
    "x = r'\\n\\x'\ny = br'\\u1234'\nz = b'\\x41\\u1234'\n",
    "x = '''one\ntwo '' three ' four'''\n",
    'x = """one\ntwo "" three " four"""\n',
    'f"a{{b}}{x!r:>{w}}z"\n',
    'f"{x = } {x:} {x:{w}.{p}f}"\n',
    'f"{x:{{}}}"\n',
    'f"{x:=10} {(x := 3)} {x != 3}"\n',
    'if x:\n  \\\n  x\n',
    't"template {value!s:>{width}}"\n',
    'rf"raw \\n {x}"\n',
    'f"{ {\'x\': [1, 2]}[\'x\'] }"\n',
    'f"{f"{x}"}"\n',
    'f"{(lambda x: x)(1)}"\n',
    'f"{x # comment\n}"\n',
    'f"\\N{LATIN SMALL LETTER A}"\n',
    'rf"\\{x}"\n',
    "r'\\{' + '\\{'\n",
    'x = "a"\r\ny = 2\r\n',
    *unicode_samples(),
  ]


def unicode_samples() -> list[str]:
  'Exercise identifier continuation, normalization, UTF-8 boundaries and interpolated Unicode text.'
  names = ['α', '变量', 'é', 'e\u0301', 'K', '𝒙', '𐐀', 'a\u00b7b', 'a\u203fb']
  text = '\u007f\u0080\u07ff\u0800\ud7ff\ue000\uffff\U00010000\U0010ffff😀'
  return [f'{name} = "{text}"\nf"{{{name}=}} café {{{name}:>12}}"\n' for name in names] + [
    't"你好 {变量} 👩\u200d💻"\n',
    'résumé = """first\n  👩\u200d💻 e\u0301\nlast"""\n',
  ]
