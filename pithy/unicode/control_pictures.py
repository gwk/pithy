# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# For the unicode control pictures block, see: https://www.unicode.org/charts/PDF/U2400.pdf.

c0_to_pictures:dict[str,str] = {
  '\x00' : '␀', # SYMBOL FOR NULL
  '\x01' : '␁', # SYMBOL FOR START OF HEADING
  '\x02' : '␂', # SYMBOL FOR START OF TEXT
  '\x03' : '␃', # SYMBOL FOR END OF TEXT
  '\x04' : '␄', # SYMBOL FOR END OF TRANSMISSION
  '\x05' : '␅', # SYMBOL FOR ENQUIRY
  '\x06' : '␆', # SYMBOL FOR ACKNOWLEDGE
  '\x07' : '␇', # SYMBOL FOR BELL
  '\x08' : '␈', # SYMBOL FOR BACKSPACE
  '\x09' : '␉', # SYMBOL FOR HORIZONTAL TABULATION
  '\x0A' : '␊', # SYMBOL FOR LINE FEED
  '\x0B' : '␋', # SYMBOL FOR VERTICAL TABULATION
  '\x0C' : '␌', # SYMBOL FOR FORM FEED
  '\x0D' : '␍', # SYMBOL FOR CARRIAGE RETURN
  '\x0E' : '␎', # SYMBOL FOR SHIFT OUT
  '\x0F' : '␏', # SYMBOL FOR SHIFT IN
  '\x10' : '␐', # SYMBOL FOR DATA LINK ESCAPE
  '\x11' : '␑', # SYMBOL FOR DEVICE CONTROL ONE
  '\x12' : '␒', # SYMBOL FOR DEVICE CONTROL TWO
  '\x13' : '␓', # SYMBOL FOR DEVICE CONTROL THREE
  '\x14' : '␔', # SYMBOL FOR DEVICE CONTROL FOUR
  '\x15' : '␕', # SYMBOL FOR NEGATIVE ACKNOWLEDGE
  '\x16' : '␖', # SYMBOL FOR SYNCHRONOUS IDLE
  '\x17' : '␗', # SYMBOL FOR END OF TRANSMISSION BLOCK
  '\x18' : '␘', # SYMBOL FOR CANCEL
  '\x19' : '␙', # SYMBOL FOR END OF MEDIUM
  '\x1A' : '␚', # SYMBOL FOR SUBSTITUTE
  '\x1B' : '␛', # SYMBOL FOR ESCAPE
  '\x1C' : '␜', # SYMBOL FOR FILE SEPARATOR
  '\x1D' : '␝', # SYMBOL FOR GROUP SEPARATOR
  '\x1E' : '␞', # SYMBOL FOR RECORD SEPARATOR
  '\x1F' : '␟', # SYMBOL FOR UNIT SEPARATOR
  '\x7F' : '␡', # SYMBOL FOR DELETE
}

c0_del_to_pictures:dict[str,str] = {
  '\x21' : '␡', # SYMBOL FOR DELETE
  **c0_to_pictures
}

c0_sp_del_to_pictures:dict[str,str] = {
  '\x20' : '␠', # SYMBOL FOR SPACE
  **c0_del_to_pictures
}
