// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import Foundation


public struct Token<Kind>: CustomStringConvertible {

  public enum Err: Error {
    case overflow(token: Token<Kind>)
  }

  public let pos: Int
  public let end: Int
  public let linePos: Int
  public let lineIdx: Int
  public let kind: Kind

  public init(pos: Int, end: Int, linePos: Int, lineIdx: Int, kind: Kind) {
    assert(pos >= 0, "bad token pos: \(pos); kind: \(kind)")
    assert(pos < end, "bad token range: \(pos):\(end); kind: \(kind)")
    self.pos = pos
    self.end = end
    self.linePos = linePos
    self.lineIdx = lineIdx
    self.kind = kind
  }

  public var description: String {
    return "\(kind):\(pos)-\(end)"
  }

  public var colOff: Int { return pos - linePos }

  public var range: CountableRange<Int> {
    return pos..<end
  }

  public func subRange(from: Int, beforeEnd: Int = 0) -> CountableRange<Int> {
    assert(from >= 0)
    assert(beforeEnd >= 0)
    return (pos + from)..<(end - beforeEnd)
  }
}


public class Source: CustomStringConvertible {

  public let name: String
  public let text: [UInt8]
  public var newlinePositions: [Int] = []

  public init(name: String, text: [UInt8]) {
    self.name = name
    self.text = text
  }

  public var description: String {
    return "Source(\(name))"
  }

  public func getLineIndex(pos: Int) -> Int {
    // TODO: use binary search.
    for (index, newlinePos) in newlinePositions.enumerated() {
      if pos <= newlinePos { // newlines are considered to be the last character of a line.
        return index
      }
    }
    return newlinePositions.count
  }

  public func getLineStart(pos: Int) -> Int {
    var start = pos
    while start > 0 {
      let i = start - 1
      if text[i] == 0x0a { break }
      start = i
    }
    return start
  }

  public func getLineEnd(pos: Int) -> Int {
   // Include the terminating newline character if it is present.
    var end = pos
    while end < text.count {
      let i = end
      end += 1
      if text[i] == 0x0a { break }
    }
    return end
  }

  public func diagnostic<TokenKind>(token: Token<TokenKind>, msg: String = "", showMissingNewline: Bool = true) -> String {
    return diagnostic(pos: token.pos, end: token.end, linePos: token.linePos, lineIdx: token.lineIdx,
      msg: msg, showMissingNewline: showMissingNewline)
  }

  public func diagnosticAtEnd(msg: String = "", showMissingNewline: Bool = true) -> String {
    let lastPos = text.count - 1
    let linePos: Int
    let lineIdx: Int
    if let newlinePos = newlinePositions.last {
      if newlinePos == lastPos { // terminating newline.
        linePos = getLineStart(pos: newlinePos)
        lineIdx = newlinePositions.count - 1
      } else { // no terminating newline.
        linePos = newlinePos + 1
        lineIdx = newlinePositions.count
      }
    } else {
      linePos = 0
      lineIdx = 0
    }
    return diagnostic(pos: lastPos, linePos: linePos, lineIdx: lineIdx, msg: msg, showMissingNewline: showMissingNewline)
  }

  public func diagnostic(pos: Int, end: Int? = nil, linePos: Int, lineIdx: Int, msg: String = "", showMissingNewline: Bool = true) -> String {

    let end = end ?? pos
    let lineEnd = getLineEnd(pos: pos)
    if end <= lineEnd { // single line.
      return diagnostic(pos: pos, end: end, linePos: linePos, lineIdx: lineIdx, lineBytes: text[linePos..<lineEnd],
        msg: msg, showMissingNewline: showMissingNewline)
    } else { // multiline.
      let endLineIdx = getLineIndex(pos: end)
      let endLineRange = getLineStart(pos: end)..<getLineEnd(pos: end)
      return (
        diagnostic(pos: pos, end: lineEnd, linePos: linePos, lineIdx: lineIdx, lineBytes: text[linePos..<lineEnd],
          msg: msg, showMissingNewline: showMissingNewline) +
        diagnostic(pos: endLineRange.startIndex, end: end, linePos: endLineRange.startIndex, lineIdx: endLineIdx, lineBytes: text[endLineRange],
          msg: "ending here", showMissingNewline: showMissingNewline))
    }
  }

  public func diagnostic(pos: Int, end: Int, linePos: Int, lineIdx: Int, lineBytes: ArraySlice<UInt8>,
   msg: String, showMissingNewline: Bool = true) -> String {

    assert(pos >= 0)
    assert(pos <= end)
    assert(linePos <= pos)
    assert(end <= linePos + lineBytes.count)

    let tab = UInt8(0x09)
    let newline = UInt8(0x0a)
    let space = UInt8(0x20)
    let caret = UInt8(0x5E)
    let tilde = UInt8(0x7E)

    let lineEnd = linePos + lineBytes.count

    func decode(_ bytes: ArraySlice<UInt8>) -> String {
      return String(bytes: bytes, encoding: .utf8) ?? String(bytes: bytes, encoding: .ascii)!
    }

    let srcLine = { () -> String in
      if lineBytes.last == newline {
        let lastIndex = lineBytes.endIndex - 1
        let s = decode(lineBytes[lineBytes.startIndex..<lastIndex])
        if pos == lastIndex || end == lineEnd {
          return s + "\u{23CE}" // RETURN SYMBOL.
        } else {
          return s
        }
      } else if showMissingNewline {
        return decode(lineBytes) + "\u{23CE}\u{0353}" // RETURN SYMBOL, COMBINING X BELOW.
      } else {
        return decode(lineBytes)
      }
    }()

    let srcBar = srcLine.isEmpty ? "|" : "| "

    // Note: this relies on swift slices using indices of parent collections.
    // TODO: make this work for line-by-line lexing.

    // TODO: for each Character, decide appropriate single/wide/double/tab spacing.
    // Alternatively, just use ANSI underlining.
    var underBytes = [UInt8]()
    for byte in lineBytes[..<pos] {
      underBytes.append(byte == tab ? tab : space)
    }
    if pos >= end {
      underBytes.append(caret)
    } else {
      for _ in pos..<end {
        underBytes.append(tilde)
      }
    }
    let underline = String(bytes: underBytes, encoding: .utf8)!

    func colStr(_ pos: Int) -> String {
      if let s = String(bytes: lineBytes[..<pos], encoding: .utf8) {
        return String(s.count + 1)
      } else {
        return "?"
      }
    }

    let col = (pos < end) ? "\(colStr(pos))-\(colStr(end))" : colStr(pos)

    let msgSpace = (msg.isEmpty || msg.hasPrefix("\n")) ? "" : " "
    return "\(name):\(lineIdx+1):\(col):\(msgSpace)\(msg)\n\(srcBar)\(srcLine)\n  \(underline)\n"
  }

  public func stringFor<TokenKind>(token: Token<TokenKind>) -> String? {
    return String(bytes: text[token.range], encoding: .utf8)
  }

  public func parseSignedNumber<TokenKind>(token: Token<TokenKind>) throws -> Int64 {
    let negative: Bool
    let base: Int
    var offset: Int
    (negative, offset) = parseSign(token: token)
    (base, offset) = parseBasePrefix(token: token, offset: offset)
    return try parseSignedDigits(token: token, from: offset, base: base, negative: negative)
  }

  public func parseSign<TokenKind>(token: Token<TokenKind>) -> (negative: Bool, offset: Int) {
    switch text[token.pos] {
    case 0x2b: return (false, 1)  // '+'
    case 0x2d: return (true, 1)   // '-'
    default: return (false, 0)
    }
  }

  public func parseBasePrefix<TokenKind>(token: Token<TokenKind>, offset: Int) -> (base: Int, offset: Int) {
    let pos = token.pos + offset
    if text[pos] != 0x30 { // '0'
      return (base: 10, offset: offset)
    }
    let base: Int
    switch text[pos + 1] { // byte.
    case 0x62: base = 2 // 'b'
    case 0x64: base = 10 // 'd'
    case 0x6f: base = 8 // 'o'
    case 0x71: base = 4 // 'q'
    case 0x78: base = 16 // 'x'
    default: return (base: 10, offset: offset)
    }
    return (base: base, offset: offset + 2)
  }


  public func parseDigits<TokenKind>(token: Token<TokenKind>, from: Int, base: Int) throws -> UInt64 {
    let baseU64 = UInt64(base)
    var val: UInt64 = 0
    for i in token.subRange(from: from) {
      let byte = text[i]
      if let digit = valueForHexDigit(byte: byte) {
        let v = (val &* baseU64) &+ UInt64(digit)
        if v < val { throw Token.Err.overflow(token: token) }
        val = v
      } // else skip digit.
    }
    return val
  }

  public func parseSignedDigits<TokenKind>(token: Token<TokenKind>, from: Int, base: Int, negative: Bool) throws -> Int64 {
    let uns = try parseDigits(token: token, from: from, base: base)
    if negative {
      if uns <= UInt64(Int64.max) {
        return Int64(uns) * -1
      } else if uns == UInt64(Int64.max) + 1 {
        // Assuming that max + 1 == -min, we need this special case to avoid overflow during conversion.
        return Int64.min
      } else {
        throw Token.Err.overflow(token: token)
      }
    } else { // positive.
      if uns <= UInt64(Int64.max) {
        return Int64(uns)
      } else {
        throw Token.Err.overflow(token: token)
      }
    }
  }

  public func parseDouble<TokenKind>(token: Token<TokenKind>, from: Int, base: Double) -> Double {
    let bytes = text[token.subRange(from: from)]
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

  public func valueForHexDigit(byte: UInt8) -> UInt32? {
    let code = UInt32(byte)
    switch code {
      case ucv("0")...ucv("9"): return code      - ucv("0")
      case ucv("A")...ucv("F"): return code + 10 - ucv("A")
      case ucv("a")...ucv("f"): return code + 10 - ucv("a")
      default: return nil
    }
  }

  public func encodeToUtf8Fast(into array: inout [UInt8], code: UInt32) {
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

  @inline(__always)
  private func ucv(_ s: UnicodeScalar) -> UInt32 { return s.value }

  @inline(__always)
  private func ucb(_ s: UnicodeScalar) -> UInt8 { return UInt8(s.value) }
}


func ployRepr(_ string: String) -> String {
  var r = "'"
  for char in string.unicodeScalars {
    switch char {
    case "\\": r.append("\\\\")
    case "'": r.append("\\'")
    case UnicodeScalar(0x20)...UnicodeScalar(0x7E): r.append(String(char)) // must come after excluded chars above.
    case "\0": r.append("\\0")
    case "\t": r.append("\\t")
    case "\n": r.append("\\n")
    case "\r": r.append("\\r")
    default: r.append("\\\(String(char.value, radix: 16, uppercase: false));")
    }
  }
  r.append("'")
  return r
}
