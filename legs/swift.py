# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from collections import defaultdict
from pithy.strings import render_template


def output_swift(dfa, rules_path, path, test_path, license, stem):
  
  token_kinds = [name for node, name in sorted(dfa.matchNodeNames.items())]
  token_kind_case_defs = ['case {}'.format(kind) for kind in token_kinds]
  token_kind_case_descriptions = ['case .{}: return {}'.format(name, swift_repr(name)) for name in token_kinds]
  dfa_nodes = sorted(dfa.transitions.keys())

  def finish_case(node, name):
    template = 'case ${node}: tokenKind = .${name}'
    return render_template(template, name=name, node=node)
  
  finish_cases = [finish_case(node, name) for node, name in sorted(dfa.matchNodeNames.items())]
  
  def byte_case_ranges(chars):
    ranges = []
    for char in chars:
      if not ranges:
        ranges.append((char, char))
      else:
        low, prev = ranges[-1]
        if prev + 1 == char:
          ranges[-1] = (low, char)
        else:
          ranges.append((char, char))
    def fmt(l, h):
      if l == h: return hex(l)
      return hex(l) + (', ' if l + 1 == h else '...') + hex(h)
    return [fmt(*r) for r in ranges]

  def byte_case(chars, dst, suffix):
    template = 'case ${chars}: state = ${dst}${suffix}'
    return render_template(template,
      chars=', '.join(byte_case_ranges(chars)),
      dst=dst,
      suffix=suffix)
  
  def byte_cases(node, suffix, indent):
    dst_chars = defaultdict(list)
    for char, dst in sorted(dfa.transitions[node].items()):
      dst_chars[dst].append(char)
    dst_chars_sorted = sorted(dst_chars.items(), key=lambda p: p[1])
    cases = [byte_case(chars, dst, suffix) for dst, chars in dst_chars_sorted]
    return ('\n' + (' ' * indent)).join(cases)
  
  def transition_code(node):
    # TODO: condense cases into ranges and tuple patterns.
    d = dfa.transitions[node]
    if not d:
      return '      break'
    template = '''\
      switch byte {
      ${byte_cases}
      default: break top
      }'''
    return render_template(template, byte_cases=byte_cases(node, suffix='; return nil', indent=6))

  def state_case(node):
    kind = dfa.matchNodeNames.get(node)
    if kind:
      match_code = render_template('      tokenEnd = pos; tokenKind = .${kind}\n', kind=kind)
    else:
      match_code = ''
    template = '''\
    case ${node}:
${match_code}${transition_code}
'''
    return render_template(template,
      match_code=match_code,
      node=node,
      transition_code=transition_code(node),
    )
  
  start_byte_cases = [byte_cases(0, suffix='', indent=4)]
  state_cases = [state_case(node) for node in dfa_nodes[1:]]
  Name = stem.capitalize()

  src = render_template(template,
    finish_cases='\n'.join(finish_cases),
    license=license,
    Name=Name,
    path=path,
    rules_path=rules_path,
    start_byte_cases='\n'.join(start_byte_cases),
    state_cases='\n'.join(state_cases),
    token_kind_case_defs='\n'.join(token_kind_case_defs),
    token_kind_case_descriptions='\n'.join(token_kind_case_descriptions),
    )
  with open(path, 'w') as f:
    f.write(src)

  if test_path:
    src = render_template(test_template, Name=Name)
    with open(test_path, 'w') as f:
      f.write(src)


template = r'''// ${license}.
// This file was generated by legs from ${path}.

import Foundation


public enum ${Name}TokenKind: CustomStringConvertible {
  ${token_kind_case_defs}

  public var description: String {
    switch self {
    ${token_kind_case_descriptions}
    }
  }
}


public struct ${Name}Token: CustomStringConvertible {
  let pos: Int
  let end: Int
  let kind: ${Name}TokenKind

  public var description: String {
    return "\(kind):\(pos)-\(end)"
  }
}


public struct ${Name}Source {

  public let name: String
  public let data: Data
  public var lineIndexes: [Int]

  public init(name: String, data: Data, lineIndexes: [Int] = []) {
    self.name = name
    self.data = data
    self.lineIndexes = lineIndexes
  }
}


public struct ${Name}SourceLoc {
  public var pos: Int
  public var line: Int
  public var column: Int
}


public struct ${Name}Lexer: Sequence, IteratorProtocol {

  public typealias TokenKind = ${Name}TokenKind
  public typealias Token = ${Name}Token
  public typealias Source = ${Name}Source
  public typealias SourceLoc = ${Name}SourceLoc

  public typealias Element = Token
  public typealias Iterator = ${Name}Lexer
  public typealias Byte = UInt8

  public let source: Source

  private var isFinished = false
  private var state: UInt = 0
  private var pos: Int = 0
  private var tokenPos: Int = 0
  private var tokenEnd: Int = 0
  private var tokenKind: TokenKind? = nil

  public init(name: String, data: Data) {
    self.source = Source(name: name, data: data)
  }

  public mutating func next() -> Token? {
    if isFinished {
      return nil
    }
    while pos < source.data.count {
      let token = step(byte: source.data[pos])
      pos += 1
      if let token = token {
        return token
      }
    }
    // flush final token.
    isFinished = true
    if tokenPos < pos {
      tokenEnd = pos
      switch state {
      ${finish_cases}
      default: tokenKind = .invalid
      }
      return Token(pos: tokenPos, end: tokenEnd, kind: tokenKind!)
    } else {
      return nil
    }
  }

  @inline(__always)
  public mutating func step(byte: Byte) -> Token? {
    top: switch state {
    case 0: break
    ${state_cases}
    default: fatalError("lexer is in impossible state: \(state)")
    }
    // start.
    let token = flushToken()
    tokenPos = pos
    switch byte {
    ${start_byte_cases}
    default: state = 1 // transition to invalid.
    }
    return token
  }

  @inline(__always)
  private mutating func flushToken() -> Token? {
    if let tokenKind = self.tokenKind {
      assert(tokenPos < tokenEnd, "empty token; pos: \(tokenPos); kind: \(tokenKind).")
      self.tokenKind = nil
      return Token(pos: tokenPos, end: tokenEnd, kind: tokenKind)
    } else {
      return nil
    }
  }
}
'''

test_template = r'''
// test main.

import Foundation

func repr(_ string: String) -> String {
  var r = "\""
  for char in string.unicodeScalars {
    switch char {
    case UnicodeScalar(0x20)...UnicodeScalar(0x7E): r.append(char)
    case "\0": r.append("\\0")
    case "\\": r.append("\\\\")
    case "\t": r.append("\\t")
    case "\n": r.append("\\n")
    case "\r": r.append("\\r")
    case "\"": r.append("\\\"")
    default: r.append("\\{\(String(char.value, radix: 16, uppercase: false))}")
    }
  }
  r.append("\"")
  return r
}

func test(index: Int, arg: String) {
  print("\n", repr(arg), separator: "", terminator: ":\n")
  let data = Data(arg.utf8)
  let lexer = ${Name}Lexer(name: String(index), data: data)
  for token in lexer {
    print(token, separator: "")
  }
}

for (i, arg) in Process.arguments.enumerated() {
  if i == 0 { continue }
  test(index: i, arg: arg)
}
'''


swift_escapes = {
  '\0' : '\\0',
  '\\' : '\\\\',
  '\t' : '\\t',
  '\n' : '\\n',
  '\r' : '\\r',
  '"'  : '\\"',
}

def swift_escape_literal_char(c):
  try:
    return swift_escapes[c]
  except KeyError: pass
  if c.isprintable():
    return c
  return '\\u{{{:x}}}'.format(ord(c))

def swift_repr(string):
  return '"{}"'.format(''.join(swift_escape_literal_char(c) for c in string))

