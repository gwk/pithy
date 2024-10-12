# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

dom_category_events = {
  'mouse': ['mousedown', 'mouseup', 'click', 'dblclick', 'mousemove', 'mouseover', 'mousewheel', 'mouseout', 'contextmenu'],
  'touch': ['touchstart', 'touchmove', 'touchend', 'touchcancel'],
  'keyboard': ['keydown', 'keypress', 'keyup'],
  'form': ['focus', 'blur', 'change', 'submit'],
  'window': ['scroll', 'resize', 'hashchange', 'load', 'unload']
}

all_dom_events = [e for events in dom_category_events.values() for e in events]
