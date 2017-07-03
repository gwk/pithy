// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import Foundation


func main() {
  for (i, arg) in CommandLine.arguments.enumerated() {
    if i == 0 { continue }
    test(index: i, arg: arg)
  }
}


func test(index: Int, arg: String) {
  let name = "arg\(index)"
  print("\n\(name): \(arg.repr)")
  let data = Data(arg.utf8)
  let source = Source(name: name, data: data)
  for token in source.lex() {
    let base: Int
    var from = 2 // "0_" prefix is the common case.
    switch token.kind {
      case .space: continue
      case .incomplete, .invalid: base = 0
      case .num:  base = 10; from = 0
      case .bin:  base = 2
      case .quat: base = 4
      case .oct:  base = 8
      case .dec:  base = 10
      case .hex:  base = 16
    }
    var msg: String
    do {
      let val = try source.parseDigits(token: token, from: from, base: base)
      msg = "\(token.kind): \(val)"
    } catch let e {
      msg = "error: \(e)"
    }
    let d = source.diagnostic(token: token, prefix: "token", msg: msg, showMissingFinalNewline: false)
    print(d, terminator: "")
  }
}


extension String {
  var repr: String {
    var r = "\""
    for char in unicodeScalars {
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
}
