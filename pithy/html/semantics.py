# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
HTML semantics data.
'''

raw_text_tags = frozenset({ 'script', 'style' })
escapeable_raw_text_tags = frozenset({ 'textarea', 'title' })
ws_sensitive_tags = raw_text_tags | escapeable_raw_text_tags | frozenset({'pre'})

void_tags = frozenset({
  'area',
  'base',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'input',
  'link',
  'meta',
  'param',
  'source',
  'track',
  'wbr',
})

form_input_types = frozenset({
  'button', # Push button with no default behavior.
  'checkbox', # Check box allowing single values to be selected/deselected.
  'color', # Control for specifying a color. A color picker's UI has no required features other than accepting simple colors as text (more info).
  'date', # Control for entering a date (year, month, and day, with no time).
  'datetime-local', # Control for entering a date and time, with no time zone.
  'email', # Field for editing an e-mail address.
  'file', # Control that lets the user select a file. Use `accept` to define the types of files that the control can select.
  'hidden', # Control that is not displayed but whose value is submitted to the server.
  'image', # Graphical submit button. `src` specifies the image and `alt` specifies alternative text. Use the height and width attributes to define the size of the image in pixels.
  'month', # Control for entering a month and year, with no time zone.
  'number', # Control for entering a number.
  'password', # Single-line text field whose value is obscured. Use the maxlength and minlength attributes to specify the maximum length of the value that can be entered.
  'radio', # Radio button, allowing a single value to be selected out of multiple choices.
  'range', # Control for entering a number whose exact value is not important.
  'reset', # Button that resets the contents of the form to default values.
  'search', # Single-line text field for entering search strings. Line-breaks are automatically removed from the input value.
  'submit', # Button that submits the form.
  'tel', # Control for entering a telephone number.
  'text', # Single-line text field. Line-breaks are automatically removed from the input value.
  'time', # Control for entering a time value with no time zone.
  'url', # Field for entering a URL.
  'week', # Control for entering a date consisting of a week-year number and a week number with no time zone.
})


phrasing_tags = frozenset({
  'a',
  'abbr',
  'area',
  'audio',
  'b',
  'bdi',
  'bdo',
  'br',
  'button',
  'canvas',
  'cite',
  'code',
  'data',
  'datalist',
  'del',
  'dfn',
  'em',
  'embed',
  'i',
  'iframe',
  'img',
  'input',
  'ins',
  'kbd',
  'label',
  'link',
  'map',
  'mark',
  'meta',
  'meter',
  'noscript',
  'object',
  'output',
  'picture',
  'progress',
  'q',
  'ruby',
  's',
  'samp',
  'script',
  'select',
  'slot',
  'small',
  'span',
  'strong',
  'sub',
  'sup',
  'template',
  'textarea',
  'time',
  'u',
  'var',
  'video',
  'wbr',
})
