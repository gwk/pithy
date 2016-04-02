# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
plus encoding is similar to url percent encoding, but uses '+' as the escape character.
it is used to create convenient file system paths out of urls.
just like url encoding, letters, digits, and the characters '_.-' are left unescaped.
additionally, percent characters are not escaped, to make prior url encoding more readable.
all other bytes are encoded as "+XX", where XX is the capitalized hexadecimal byte value.
'''


def _plus_encode_byte(b):
  '''
  ascii notes:
  0x25: '%'
  0x2d: '-'
  0x2e: '.'
  0x30-39: '0'-'9'
  0x41-5a: 'A'-'Z'
  0x5f: '_'
  0x61-7a: 'a'-'z'
  '''
  if \
    (0x30 <= b <= 0x39) or \
    (0x41 <= b <= 0x5a) or \
    (0x61 <= b <= 0x7a) or \
    b in (0x25, 0x2d, 0x2e, 0x5f):
    return chr(b)
  else:
    return '+{:2X}'.format(b)
 
_plus_encode_table = tuple(_plus_encode_byte(b) for b in range(0xff))

def plus_encode(string):
  utf8 = string.encode('utf-8')
  return ''.join(_plus_encode_table[b] for b in utf8)

