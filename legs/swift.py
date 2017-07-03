# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from collections import defaultdict
from itertools import chain
from pithy.fs import add_file_execute_permissions
from pithy.string_utils import render_template
from pithy.iterable import closed_int_intervals


def output_swift(dfa, modes, node_modes, mode_transitions, license, args):
  path = args.output
  type_prefix = args.type_prefix
  has_modes = len(modes) > 1
  modes_by_name = { mode.name : mode for mode in modes }
  pop_names = { name for mode, name in mode_transitions.values() }
  parent_names_to_transition_pairs = { kv[0][1] : kv for kv in mode_transitions.items() }
  preMatchNodes = dfa.preMatchNodes
  kinds = { name : swift_safe_sym(name) for name in chain(dfa.ruleNames, (mode.incomplete_name for mode in modes)) }
  assert len(kinds) == len(set(kinds.values()))
  token_kind_case_defs = ['case {}'.format(kind) for kind in sorted(kinds.values())]
  start_nodes = { mode.start for mode in modes }

  def rule_desc(name):
    try:
      literal = dfa.literalRules[name]
      if all((c.isprintable() and not c.isspace()) for c in literal):
        return '"`{}`"'.format(swift_esc_str(literal))
    except KeyError: pass
    return swift_repr(kinds[name])

  if has_modes:
    mode_stack_decl = render_template('  private var stack: [(childKind: ${Name}TokenKind, parentState: UInt)] = []',
      Name=type_prefix)
  else:
    mode_stack_decl = ''

  token_kind_case_descs = ['case .{}: return {}'.format(kind, rule_desc(name)) for name, kind in sorted(kinds.items())]

  dfa_nodes = sorted(dfa.transitions.keys())

  def byte_case_patterns(chars):
    def fmt(l, h):
      if l == h: return hex(l)
      return hex(l) + (', ' if l + 1 == h else '...') + hex(h)
    return [fmt(*r) for r in closed_int_intervals(chars)]

  def byte_case(chars, dst, returns):
    return 'case {chars}: state = {dst}{suffix}'.format(
      chars=', '.join(byte_case_patterns(chars)),
      dst=dst,
      suffix='; return nil' if returns else '')

  def byte_cases(node, returns):
    dst_chars = defaultdict(list)
    for char, dst in sorted(dfa.transitions[node].items()):
      dst_chars[dst].append(char)
    dst_chars_sorted = sorted(dst_chars.items(), key=lambda p: p[1])
    return [byte_case(chars, dst, returns) for dst, chars in dst_chars_sorted]

  def mode_pop_clause(kind, else_code):
    return render_template('''\
if let last = stack.last, last.childKind == .${kind} {
  _ = stack.popLast()
  restart(state: last.parentState)
} else {
  ${else_code}
}''',
      kind=kind,
      else_code=else_code)

  def mode_push_clause(parent_pair, child_pair):
    parent_mode_name, parent_name = parent_pair
    child_mode_name, child_name = child_pair
    return render_template('''\
stack.append((childKind: .${child_kind}, parentState: ${parent_state}))
start_${child_mode_name}()''',
      child_kind=kinds[child_name],
      parent_state=modes_by_name[parent_mode_name].start,
      child_mode_name=child_mode_name)

  def transition_code(node):
    mode = node_modes[node]
    rule_name = dfa.matchNodeNames.get(node, mode.incomplete_name)
    kind = kinds[rule_name]
    restart_code = 'start_{mode}()'.format(mode=node_modes[node].name)
    if has_modes:
      # if this a transition push node, replace restart code.
      try: pairs = parent_names_to_transition_pairs[rule_name]
      except KeyError: pass
      else: restart_code = mode_push_clause(*pairs)
      # if this is a pop node, pop code comes first.
      # we currently allow a node to be both pop and push but this is questionable.
      if rule_name in pop_names:
        restart_code = mode_pop_clause(kind, else_code=restart_code)
    default = '''\
{restart_code}
return flushToken(kind: .{kind})'''.format(
      restart_code=restart_code,
      kind=kind)
    d = dfa.transitions[node]
    if not d: # no transitions; omit the switch and unconditionally take the default action.
      return default.replace('\n', '\n      ')
    # has transitions; need an inner switch.
    # TODO: condense cases into ranges and tuple patterns.
    return render_template('''switch byte {
      ${byte_cases}
      default:
        ${default}
      }''',
      byte_cases='\n      '.join(byte_cases(node, returns=True)),
      default=default.replace('\n', '\n        '))

  def state_case(node):
    mode = node_modes[node]
    if node in start_nodes:
      return 'case {node}: start_{mode.name}(); return nil'.format(mode=mode, node=node)
    name = dfa.matchNodeNames.get(node)
    if name:
      desc = name
    elif node in preMatchNodes:
      desc = mode.name + ' pre-match'
    else:
      desc = mode.name + ' post-match'
    return '''case {node}: // {desc}.
      {transition_code}'''.format(
      desc=desc,
      node=node,
      transition_code=transition_code(node))

  state_cases = [state_case(node) for node in dfa_nodes]

  def start_fn(mode):
    return render_template('''func start_${name}() {
      switch byte {
      ${cases}
      default: state = ${invalid}
      }
    }''',
    name=mode.name,
    cases='\n      '.join(byte_cases(mode.start, returns=False)),
    invalid=mode.invalid)

  start_fns = [start_fn(mode) for mode in modes]

  def restart_case(mode):
    return 'case {mode.start}: start_{mode.name}()'.format(mode=mode)

  if has_modes:
    restart_cases = [restart_case(mode) for mode in modes]
    start_fns.append(render_template('''func restart(state: UInt) {
      switch state {
      ${restart_cases}
      default: fatalError("step.restart: invalid state: \(state)")
      }
    }''',
      restart_cases='\n      '.join(restart_cases) if has_modes else ''))


  with open(path, 'w', encoding='utf8') as f:
    if args.test:
      f.write('#!/usr/bin/env swift\n')
    src = render_template(template,
      license=license,
      mode_stack_decl=mode_stack_decl,
      Name=type_prefix,
      path=path,
      rules_path=args.rules_path,
      start_fns='\n    '.join(start_fns),
      state_cases='\n    '.join(state_cases),
      token_kind_case_defs='\n  '.join(token_kind_case_defs),
      token_kind_case_descs='\n    '.join(token_kind_case_descs),
    )
    f.write(src)
    if args.test:
      test_src = render_template(test_template, Name=type_prefix)
      f.write(test_src)
      add_file_execute_permissions(f.fileno())


template = r'''// ${license}
// This file was generated by legs from ${rules_path}.

import Foundation


public enum ${Name}TokenKind: CustomStringConvertible {
  ${token_kind_case_defs}

  public var description: String {
    switch self {
    ${token_kind_case_descs}
    }
  }
}


public struct ${Name}Token: CustomStringConvertible {
  public let pos: Int
  public let end: Int
  public let kind: ${Name}TokenKind

  public init(pos: Int, end: Int, kind: ${Name}TokenKind) {
    assert(pos >= 0, "bad token pos: \(pos); kind: \(kind)")
    assert(pos < end, "bad token range: \(pos):\(end); kind: \(kind)")
    self.pos = pos
    self.end = end
    self.kind = kind
  }

  public var description: String {
    return "\(kind):\(pos)-\(end)"
  }

  public var range: CountableRange<Int> {
    return pos..<end
  }

  public func subRange(from: Int, beforeEnd: Int = 0) -> CountableRange<Int> {
    assert(from >= 0)
    assert(beforeEnd >= 0)
    return (pos + from)..<(end - beforeEnd)
  }
}


public class ${Name}Source: CustomStringConvertible {

  enum Err: Error {
    case TokenKind(token: ${Name}Token, msg: String)
    case Overflow(token: ${Name}Token)
    case Negative(token: ${Name}Token)
  }

  public let name: String
  public let data: Data
  public fileprivate(set) var newlinePositions: [Int] = []

  public init(name: String, data: Data) {
    self.name = name
    self.data = data
  }

  public var description: String {
    return "${Name}Source(name: \(name), data: \(data))"
  }

  public func lex() -> ${Name}Lexer {
    return ${Name}Lexer(source: self)
  }

  public var tokens: [${Name}Token] {
    return Array(lex())
  }

  public func lineIndex(pos: Int) -> Int {
    // TODO: use binary search.
    for (index, newlinePos) in newlinePositions.enumerated() {
      if pos <= newlinePos { // newlines are considered to be the last character of a line.
        return index
      }
    }
    return newlinePositions.count
  }

  public func lineRange(pos: Int) -> CountableRange<Int> {
   // returns the range in `data` for the line containing `pos`,
   // including the terminating newline character if it is present.
    var start = pos
    while start > 0 {
      let i = start - 1
      if data[i] == 0x0a { break }
      start = i
    }
    var end = pos
    while end < data.count {
      let i = end
      end += 1
      if data[i] == 0x0a { break }
    }
    return start..<end
  }

  public func getColumn(line: String, lineStart: Int, pos: Int) -> Int {
    let utf8 = line.utf8
    let utf8Index = utf8.index(utf8.startIndex, offsetBy: pos - lineStart)
    if let charIndex = String.Index(utf8Index, within: line) {
        return line.distance(from: line.startIndex, to: charIndex)
    } else {
      return -1
    }
  }

  public func getLineAndColumn(range: CountableRange<Int>, pos: Int) -> (Bool, String, Int) {
    if let line = String(bytes: data[range], encoding: .utf8) {
      return (true, line, getColumn(line: line, lineStart: range.startIndex, pos: pos))
    } else {
      // TODO: this should return a best-effort representation if unicode decoding fails.
      return (false, "?", -1)
    }
  }

  public func underline(col: Int, endCol: Int = -1) -> String {
    if col < 0 { return "" }
    let indent = String(repeating: " ", count: col)
    if col < endCol {
      return indent + String(repeating: "~", count: endCol - col)
    } else {
      return indent + "^"
    }
  }

  public func underlines(col: Int, lineLength: Int, endCol: Int) -> (String, String) {
    // for two distinct lines, return start and end underlines.
    let startLine, endLine: String
    if col < 0 {
      startLine = ""
    } else {
      let spaces = String(repeating: " ", count: col)
      let squigs = String(repeating: "~", count: lineLength - col)
      startLine = spaces + squigs
    }
    if endCol < 0 {
      endLine = ""
    } else {
      endLine = String(repeating: "~", count: endCol)
    }
    return (startLine, endLine)
  }

  private func colString(_ col: Int) -> String {
    return (col >= 0) ? String(col + 1) : "?"
  }

  public func diagnostic(token: ${Name}Token, prefix: String, msg: String = "", showMissingFinalNewline: Bool = true)
   -> String {
    return diagnostic(pos: token.pos, end: token.end, prefix: prefix, msg: msg, showMissingFinalNewline: showMissingFinalNewline)
  }

  public func diagnostic(pos: Int, end: Int? = nil, prefix: String, msg: String = "", showMissingFinalNewline: Bool = true)
   -> String {

    func diagLine(_ line: String, _ returnSymbol: Bool) -> String {
      if line.hasSuffix("\n") {
        if returnSymbol {
          var s = line
          s.remove(at: s.index(before: s.endIndex))
          return s + "\u{23CE}\n"
        } else {
          return line
        }
      } else if showMissingFinalNewline {
        return line + "\u{23CE}\u{0353}\n"
      } else {
        return line + "\n"
      }
    }

    let msgSpace = (msg.isEmpty || msg.hasPrefix("\n")) ? "" : " "
    let lineNum = lineIndex(pos: pos) + 1
    let range = lineRange(pos: pos)
    let (_, line, col) = getLineAndColumn(range: range, pos: pos)
    let common = "\(prefix): \(name):\(lineNum):\(colString(col))"
    if let end = end {
      if end <= range.endIndex { // single line.
        if pos < end { // multiple columns.
          let endCol = getColumn(line: line, lineStart: range.startIndex, pos: end)
          let under = underline(col: col, endCol: endCol)
          let retSym = (end == range.endIndex)
          return "\(common)-\(colString(endCol)):\(msgSpace)\(msg)\n  \(diagLine(line, retSym))  \(under)\n"
        } // else: single line, single column case below.
      } else { // multiline.
        let endLineNum = lineIndex(pos: end) + 1
        let endLineRange = lineRange(pos: end)
        let (_, endLine, endCol) = getLineAndColumn(range: endLineRange, pos: end)
        let endRetSym = (end == endLineRange.endIndex)
        let (under, endUnder) = underlines(col: col, lineLength: line.characters.count, endCol: endCol)
        let a = "\(common)--\(endLineNum):\(colString(endCol)):\(msgSpace)\(msg)\n"
        let b = "  \(diagLine(line, true))  \(under)…\n"
        let c = "  \(diagLine(endLine, endRetSym)) …\(endUnder)\n"
        return "\(a)\(b)\(c)"
      }
    }
    // single line, single column.
    let retSym = (pos == range.endIndex - 1)
    return "\(common):\(msgSpace)\(msg)\n  \(diagLine(line, retSym))  \(underline(col: col))\n"
  }

  func stringFor(token: ${Name}Token) -> String {
    return String(bytes: data[token.range], encoding: .utf8)!
  }

  func parseDigits(token: ${Name}Token, from: Int, base: UInt64) throws -> UInt64 {
    var val: UInt64 = 0
    for byte in data[token.subRange(from: from)] {
      let digit = UInt64(valueForHexDigit(byte: byte)!)
      let v = (val &* base) &+ digit
      if v < val { throw Err.Overflow(token: token) }
      val = v
    }
    return val
  }

  func parseSignedDigits(token: ${Name}Token, from: Int, base: UInt64, negative: Bool) throws -> Int64 {
    let uns = try parseDigits(token: token, from: from, base: base)
    if negative {
      if uns <= UInt64(Int64.max) {
        return Int64(uns) * -1
      } else if uns == UInt64(Int64.max) + 1 {
        // Assuming that max + 1 == -min, we need this special case to avoid overflow during conversion.
        return Int64.min
      } else {
        throw Err.Overflow(token: token)
      }
    } else { // positive.
      if uns <= UInt64(Int64.max) {
        return Int64(uns)
      } else {
        throw Err.Overflow(token: token)
      }
    }
  }

  func parseDouble(token: ${Name}Token, from: Int, base: Double) -> Double {
    let bytes = data[token.subRange(from: from)]
    var sign: Double = 1
    var digitsOffset = from
    if bytes[0] == ucb("-") {
      digitsOffset += 1
      sign = -1
    } else if bytes[0] == ucb("+") {
      digitsOffset += 1
    }
    var val: Double = 0
    var fraction: Double = 0
    for byte in bytes.suffix(digitsOffset) {
      if byte == ucb(".") {
        assert(fraction == 0) // expect only one dot in token.
        fraction = 1
      } else {
        let digit = Double(valueForHexDigit(byte: byte)!)
        if fraction == 0 {
          val = (val * base) + digit
        } else {
          fraction /= Double(base)
          val += digit * fraction
        }
      }
    }
    return sign * val
  }

  func encodeToUtf8Fast(into array: inout [UInt8], code: UInt32) {
    let end: UInt32 = 0x110000
    let surrogates = UInt32(0xD800)...UInt32(0xE000)
    //let replacementBytes = [0xef, 0xbf, 0xbd] // U+FFD.
    if code < 0x80 {
      array.append(UInt8(code))
    } else if code < 0x800 {
      array.append(UInt8(0b110_00000 | ((code >> 6))))
      array.append(UInt8(0b10_000000 | ((code >> 0)  & 0b111111)))
    } else if code < 0x10000 {
      assert(!surrogates.contains(code))
      array.append(UInt8(0b1110_0000 | ((code >> 12))))
      array.append(UInt8(0b10_000000 | ((code >>  6) & 0b111111)))
      array.append(UInt8(0b10_000000 | ((code >>  0) & 0b111111)))
    } else {
      assert(code < end)
      array.append(UInt8(0b11110_000 | ((code >> 18))))
      array.append(UInt8(0b10_000000 | ((code >> 12) & 0b111111)))
      array.append(UInt8(0b10_000000 | ((code >>  6) & 0b111111)))
      array.append(UInt8(0b10_000000 | ((code >>  0) & 0b111111)))
    }
  }

  func valueForHexDigit(byte: UInt8) -> UInt32? {
    let code = UInt32(byte)
    switch code {
      case ucv("0")..<ucv("9"): return code      - ucv("0")
      case ucv("A")..<ucv("F"): return code + 10 - ucv("A")
      case ucv("a")..<ucv("f"): return code + 10 - ucv("a")
      default: return nil
    }
  }

  @inline(__always)
  func ucv(_ s: UnicodeScalar) -> UInt32 { return s.value }

  @inline(__always)
  func ucb(_ s: UnicodeScalar) -> UInt8 { return UInt8(s.value) }
}


public struct ${Name}Lexer: Sequence, IteratorProtocol {

  public typealias Element = ${Name}Token
  public typealias Iterator = ${Name}Lexer

  public private(set) var source: ${Name}Source

  private var isFinished = false
  private var state: UInt = 0
${mode_stack_decl}
  private var pos: Int = 0
  private var tokenPos: Int = 0

  public init(source: ${Name}Source) {
    self.source = source
  }

  public mutating func next() -> ${Name}Token? {
    while pos < source.data.count {
      let byte = source.data[pos]
      if byte == 0x0a {
        source.newlinePositions.append(pos)
      }
      let token = step(byte: UInt16(byte))
      pos += 1
      if token != nil {
        return token
      }
    }
    // text exhausted.
    if tokenPos < pos { // one or more tokens need to be flushed.
      return step(byte: 0x100) // pass a 'byte' value that always defaults; may backtrack.
    }
    return nil
  }

  @inline(__always)
  private mutating func step(byte: UInt16) -> ${Name}Token? {

    ${start_fns}

    func flushToken(kind: ${Name}TokenKind) -> ${Name}Token {
      let token = ${Name}Token(pos: self.tokenPos, end: pos, kind: kind)
      self.tokenPos = pos
      return token
    }

    switch state {

    ${state_cases}

    default: fatalError("step: lexer is in impossible state: \(state)")
    }
  }
}
'''

test_template = r'''
// test main.

func repr(_ string: String) -> String {
  var r = "\""
  for char in string.unicodeScalars {
    switch char {
    case "\\": r.append("\\\\")
    case "\"": r.append("\\\"")
    case UnicodeScalar(0x20)...UnicodeScalar(0x7E): r.append(String(char))
    case "\0": r.append("\\0")
    case "\t": r.append("\\t")
    case "\n": r.append("\\n")
    case "\r": r.append("\\r")
    default: r.append("\\{\(String(char.value, radix: 16, uppercase: false))}")
    }
  }
  r.append("\"")
  return r
}

func test(index: Int, arg: String) {
  let name = "arg\(index)"
  print("\n\(name): \(repr(arg))")
  let data = Data(arg.utf8)
  let source = ${Name}Source(name: name, data: data)
  for token in source.lex() {
    let d = source.diagnostic(token: token, prefix: "token", msg: token.kind.description,
      showMissingFinalNewline: false)
    print(d, terminator: "")
  }
}

for (i, arg) in CommandLine.arguments.enumerated() {
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

def swift_esc_str(string):
  return ''.join(swift_escape_literal_char(c) for c in string)

def swift_repr(string):
  return '"{}"'.format(swift_esc_str(string))


swift_reserved_syms = {
  '#column',
  '#file',
  '#function',
  '#line',
  'Self',
  '_',
  'as',
  'associatedtype',
  'break',
  'case',
  'catch',
  'class',
  'continue',
  'default',
  'defer',
  'deinit',
  'do',
  'dynamicType',
  'else',
  'enum',
  'extension',
  'fallthrough',
  'false',
  'false',
  'for',
  'func',
  'guard',
  'if',
  'import',
  'in',
  'in',
  'init',
  'inout',
  'internal',
  'is',
  'let',
  'nil',
  'operator',
  'private',
  'protocol',
  'public',
  'repeat',
  'rethrows',
  'return',
  'self',
  'static',
  'struct',
  'subscript',
  'super',
  'switch',
  'throw',
  'throws',
  'true',
  'try',
  'typealias',
  'var',
  'where',
  'while',
}

def swift_safe_sym(name):
  name = re.sub(r'[^\w]', '_', name)
  if name[0].isdigit():
    name = '_' + name
  if name in swift_reserved_syms:
    name += '_'
  return name
