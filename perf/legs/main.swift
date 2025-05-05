// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import Foundation


var counts:[TokenKind:Int] = [:]

func parse(path: String) {
  let string = try! String(contentsOfFile: path, encoding: .utf8)
  let text = Array(string.utf8)
  let source = Source(name: path, text: text)
  for token in Lexer(source: source) {
    counts[token.kind] = (counts[token.kind] ?? 0) + 1
  }
}

for (i, arg) in CommandLine.arguments.enumerated() {
  if i == 0 { continue }
  parse(path: arg)
}

let pairs = counts.sorted { $0.0 < $1.0 }
for (kind, count) in pairs {
  print("\(kind): \(count)")
}
