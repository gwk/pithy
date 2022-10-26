# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import Namespace
from importlib.util import find_spec as find_module_spec
from typing import Any, DefaultDict, Dict, List, Tuple, cast

from pithy.fs import path_dir, path_join
from pithy.iterable import closed_int_intervals
from pithy.string import render_template

from . import ModeTransitions
from .dfa import DFA


def output_swift(path:str, dfas:List[DFA], mode_transitions:ModeTransitions,
 pattern_descs:Dict[str,str], license:str, args:Namespace) -> None:
  'Generate and write a swift lexer to a file at `path`.'

  # Create safe mode names.
  modes = { dfa.name : swift_safe_sym(dfa.name) for dfa in dfas }
  mode_case_defs = [f'case {modes[dfa.name]} = {dfa.start_node}' for dfa in dfas]

  # Create safe token kind names.
  kind_syms = { kind : swift_safe_sym(kind) for kind in pattern_descs }
  kind_syms['incomplete'] = 'incomplete'
  assert len(kind_syms) == len(set(kind_syms.values()))
  token_kind_case_defs = [f'case {sym}' for sym in sorted(kind_syms.values())]

  # Token kind descriptions.
  def pattern_desc(kind:str) -> str: return swift_repr(pattern_descs[kind])
  token_kind_case_descs = [f'case .{sym}: return {pattern_desc(kind)}' for kind, sym in sorted(kind_syms.items())]

  # Mode transitions dictionary.

  def mode_trans_dict(d:Dict[str,Tuple[str,str]]) -> dict:
    return {SwiftEnum(parent_kind): (SwiftEnum(child_mode), SwiftEnum(child_kind))
      for parent_kind, (child_mode, child_kind) in d.items()}

  mode_transitions_dict = {SwiftEnum(modes[name]):mode_trans_dict(d) for name, d in mode_transitions.items()}

  # State cases.

  def byte_case_patterns(chars:List[int]) -> List[str]:
    def fmt(l:int, h:int) -> str:
      if l == h: return hex(l)
      return hex(l) + (', ' if l + 1 == h else '...') + hex(h)
    return [fmt(*r) for r in closed_int_intervals(chars)]

  def byte_case(dfa:DFA, chars:List[int], dst:int) -> str:
    pattern_kind = dfa.match_kind(dst)
    sym = None if pattern_kind is None else kind_syms.get(pattern_kind)
    return 'case {chars}: state = {dst}{suffix}'.format(
      chars=', '.join(byte_case_patterns(chars)),
      dst=dst,
      suffix=f'; last = pos; kind = .{sym}' if sym else '')

  def byte_cases(dfa:DFA, node:int) -> List[str]:
    dst_chars = DefaultDict[int, List[int]](list)
    for char, dst in sorted(dfa.transitions[node].items()):
      dst_chars[dst].append(char)
    dst_chars_sorted = sorted(dst_chars.items(), key=lambda p: p[1])
    return [byte_case(dfa, chars, dst) for dst, chars in dst_chars_sorted]

  def transition_code(dfa:DFA, node:int) -> str:
    d = dfa.transitions[node]
    if not d: return 'break loop' # no transitions.
    return render_template('''switch byte {
        ${byte_cases}
        default: break loop
        }''',
      byte_cases='\n        '.join(byte_cases(dfa, node)))

  def state_case(dfa:DFA, node:int) -> str:
    mode = dfa.name
    kind = dfa.match_kind(node)
    if kind:
      desc = kind
    elif node in dfa.pre_match_nodes:
      desc = f'{mode} pre-match'
    else:
      desc = f'{mode} post-match'
    return 'case {node}: // {desc}.\n        {transition_code}'.format(
      desc=desc,
      node=node,
      transition_code=transition_code(dfa, node))

  state_cases = [state_case(dfa, node) for dfa in dfas for node in sorted(dfa.transitions.keys())]

  with open(path, 'w', encoding='utf8') as f:
    src = render_template(template,
      Name=args.type_prefix,
      license=license,
      mode_case_defs='\n  '.join(mode_case_defs),
      mode_transitions_dict=swift_repr(mode_transitions_dict, indent=2),
      patterns_path=args.path,
      state_cases='\n      '.join(state_cases),
      token_kind_case_defs='\n  '.join(token_kind_case_defs),
      token_kind_case_descs='\n    '.join(token_kind_case_descs),
    )
    f.write(src)
    if args.test:
      # Append the base source because `swift` will only interpret a single file.
      spec = find_module_spec('legs')
      assert spec is not None
      pkg_dir_path = path_dir(cast(str, spec.origin))
      legs_base_path = path_join(pkg_dir_path, 'legs_base.swift')
      legs_base_contents = open(legs_base_path).read()
      f.write('\n\n')
      f.write(legs_base_contents)
      # Write the test main function.
      test_src = render_template(test_template, Name=args.type_prefix)
      f.write(test_src)


template = r'''// ${license}
// This file was generated by legs from ${patterns_path}.

import Foundation


public enum ${Name}LexMode: Int, Comparable {
  ${mode_case_defs}

  public var startState: Int { return rawValue }

  public static func < (l: ${Name}LexMode, r: ${Name}LexMode) -> Bool { return l.rawValue < r.rawValue }
}


public enum ${Name}TokenKind: Int, Comparable, CustomStringConvertible {
  ${token_kind_case_defs}

  public static func < (l: ${Name}TokenKind, r: ${Name}TokenKind) -> Bool { return l.rawValue < r.rawValue }

  public var description: String {
    switch self {
    ${token_kind_case_descs}
    }
  }
}


public struct ${Name}Lexer: Sequence, IteratorProtocol {

  public typealias Element = Token<${Name}TokenKind>
  public typealias Iterator = ${Name}Lexer

  public let source: Source

  private var stack: [(${Name}LexMode, ${Name}TokenKind?)] = [(.main, nil)]
  private var pos: Int = 0

  public init(source: Source) {
    self.source = source
  }

  public mutating func next() -> Token<${Name}TokenKind>? {

    if self.pos == source.text.count { // Done.
      return nil
    }

    let (mode, popKind) = self.stack.last!
    let linePos = (source.newlinePositions.last ?? -1) + 1
    let lineIdx = source.newlinePositions.count

    var pos = self.pos
    var state = mode.startState
    var last: Int = -1
    var kind: ${Name}TokenKind = .incomplete

    loop: while pos < source.text.count {
      let byte = source.text[pos]

      switch state {

      ${state_cases}

      default: fatalError("${Name}Lexer.next: impossible state: \(state)")
      }
      if byte == 0x0a {
        source.newlinePositions.append(pos)
      }
      pos += 1
    }

    let tokenPos = self.pos
    let tokenEnd:Int
    if (last == -1) {
      tokenEnd = pos
      assert(kind == .incomplete)
    } else {
      tokenEnd = last + 1
    }
    assert(tokenPos < tokenEnd, "tokenPos: \(tokenPos); tokenEnd: \(tokenEnd)")
    self.pos = tokenEnd
    if kind == popKind {
      stack.removeLast()
    } else {
      if let childPair = ${Name}Lexer.modeTransitions[mode]?[kind] {
        stack.append(childPair)
      }
    }
    return Token(pos: tokenPos, end: tokenEnd, linePos: linePos, lineIdx: lineIdx, kind: kind)
  }

  private static let modeTransitions: Dictionary<${Name}LexMode, Dictionary<TokenKind, (${Name}LexMode, TokenKind?)>> = ${mode_transitions_dict}
}
'''


test_template = r'''

// Legs test main.

func test(index: Int, arg: String) {
  let name = "arg\(index)"
  print("\n\(name): \(ployRepr(arg))")
  let text = Array(arg.utf8)
  let source = Source(name: name, text: text)
  for token in Lexer(source: source) {
    var from = 2 // "0_" prefix is the common case.
    let base: Int?
    switch token.kind.description {
    case "num":   base = 10; from = 0
    case "bin":   base = 2
    case "quat":  base = 4
    case "oct":   base = 8
    case "dec":   base = 10
    case "hex":   base = 16
    default:      base = nil
    }
    var msg: String = "error"
    if let base = base {
      do {
        let val = try source.parseDigits(token: token, from: from, base: base)
        msg = "\(token.kind): \(val)"
      } catch let e {
        msg = "error: \(e)"
      }
    } else {
      msg = token.kind.description
    }
    print(source.diagnostic(token: token, msg: msg, showMissingNewline: false), terminator: "")
  }
}

for (i, arg) in CommandLine.arguments.enumerated() {
  if i == 0 { continue }
  test(index: i, arg: arg)
}
'''


class SwiftEnum:
  def __init__(self, string:str):
    self.string = string

  @property
  def swift_repr(self) -> str: return '.' + self.string


swift_escapes:Dict[str, str] = {
  '\0' : '\\0',
  '\\' : '\\\\',
  '\t' : '\\t',
  '\n' : '\\n',
  '\r' : '\\r',
  '"'  : '\\"',
}

def swift_escape_literal_char(c:str) -> str:
  try:
    return swift_escapes[c]
  except KeyError: pass
  if c.isprintable():
    return c
  return '\\u{{{:x}}}'.format(ord(c))

def swift_esc_str(string:str) -> str:
  return ''.join(swift_escape_literal_char(c) for c in string)

def swift_repr(obj:Any, indent=0) -> str:
  if isinstance(obj, int): return repr(obj)
  if isinstance(obj, str): return f'"{swift_esc_str(obj)}"'
  if isinstance(obj, SwiftEnum): return obj.swift_repr
  if isinstance(obj, tuple): return f'({",".join(swift_repr(el) for el in obj)})'
  if isinstance(obj, dict):
    items = ''.join(swift_repr_kv(kv, indent=indent+2) for kv in obj.items())
    ind = ' ' * indent
    return f'[\n{items}{ind}]' if obj else '[:]'
  raise ValueError(obj)

def swift_repr_kv(kv:Tuple[Any, Any], indent:int) -> str:
  ind = ' ' * indent
  return f'{ind}{swift_repr(kv[0], indent=indent)}:{swift_repr(kv[1], indent=indent)},\n'


def swift_safe_sym(name:str) -> str:
  name = re.sub(r'[^\w]', '_', name)
  if name[0].isdigit():
    name = '_' + name
  if name in swift_reserved_syms:
    name += '_'
  return name

swift_reserved_syms = {
  # declarations.
  'associatedtype',
  'class',
  'deinit',
  'enum',
  'extension',
  'fileprivate',
  'func',
  'import',
  'init',
  'inout',
  'internal',
  'let',
  'open',
  'operator',
  'private',
  'protocol',
  'public',
  'static',
  'struct',
  'subscript',
  'typealias',
  'var',
  # statements.
  'case',
  'continue',
  'default',
  'defer',
  'do',
  'else',
  'fallthrough',
  'for',
  'guard',
  'if',
  'in',
  'repeat',
  'return',
  'switch',
  'where',
  'while',
  # expressions and types.
  'as',
  'Any',
  'catch',
  'false',
  'is',
  'nil',
  'rethrows',
  'super',
  'self',
  'Self',
  'throw',
  'throws',
  'true',
  'try',
  # patterns.
  '_',
}
