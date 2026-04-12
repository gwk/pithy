# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


type ResponseHeaderAtom = float | int | str
type ResponseHeaderVal = ResponseHeaderAtom | list[ResponseHeaderAtom]
type ResponseHeadersDict = dict[str,ResponseHeaderVal]



def add_header_item(headers:ResponseHeadersDict, key:str, val:ResponseHeaderAtom) -> None:
  if existing := headers.get(key):
    if isinstance(existing, list): existing.append(val)
    else: headers[key] = [existing, val]
  else:
    headers[key] = val
