# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Helpers for generating htmx attributes and responses.
pithy targets htmx 4; see https://four.htmx.org.
'''

from typing import Any, Iterable

from ..html import HtmlNode


def configure_htmx_event_replaced_attrs() -> None:
  '''
  Update `HtmlNode.replaced_attrs` so that `hx-on--{event}` attributes render as `hx-on::{event}` for all htmx events.
  e.g. `hx_on__before_request` -> `hx-on--before-request` -> `hx-on::before:request`.
  This is necessary because htmx event names contain colons, which cannot appear in Python keyword arguments.
  Note that the canonical form is `hx-on:htmx:before:request`, which can be shortened to `hx-on::before:request`.
  See:
  * https://four.htmx.org/reference/attributes/hx-on
  * https://four.htmx.org/reference/events
  '''
  HtmlNode.replaced_attrs.update({ f'hx-on--{e.replace(":", "-")}' : f'hx-on::{e}' for e in htmx_events })


def hx_inherited(**attrs:Any) -> dict[str,Any]:
  '''
  Convert `hx_*` keyword attributes to their `hx-*:inherited` forms, e.g. `hx_target` -> `hx-target:inherited`.
  Use this to specify a set of attributes on a node that should be inherited by its children.
  See: https://four.htmx.org/docs/#attribute-inheritance.
  '''
  return { k.replace('_', '-') + ':inherited' : v for k, v in attrs.items() }


def hx_trigger_on(*events:str, from_body:str|Iterable[str]) -> str:
  '''
  Compose an `hx-trigger` value from local trigger clauses and event names to listen for on `body`.
  `events` are passed through verbatim and may carry modifiers, e.g. `'load'`, `'every 30s'`, `'toggle[this.open]'`.
  `from_body` names one or more events that will be suffixed with `from:body`,
  so that the element refreshes whenever the event is dispatched anywhere in the document.
  Servers dispatch such events with the `HX-Trigger` response header; see `HtmxResponse.hx_trigger`.
  See: https://four.htmx.org/reference/attributes/hx-trigger.
  '''
  if isinstance(from_body, str): from_body = (from_body,)
  clauses = [*events, *(f'{e} from:body' for e in from_body)]
  if not clauses: raise ValueError('hx_trigger_on: no trigger clauses.')
  return ', '.join(clauses)


htmx_events = [
  # Event names without the `htmx:` prefix. See https://four.htmx.org/reference/events.
  'abort', # Send this event to an element to abort a request.
  'after:cleanup', # Triggered after htmx removes its state from an element.
  'after:history:push', # Triggered after a URL is pushed into history.
  'after:history:replace', # Triggered after the history URL is replaced.
  'after:history:update', # Triggered after a history push or replace.
  'after:implicitInheritance', # Triggered after implicit attribute inheritance is computed.
  'after:init', # Triggered after htmx has initialized an element.
  'after:process', # Triggered after htmx has processed an element and its descendants.
  'after:request', # Triggered after a request completes and the response text is available.
  'after:settle', # Triggered after the DOM has settled.
  'after:swap', # Triggered after new content has been swapped in.
  'after:viewTransition', # Triggered after a view transition completes.
  'before:cleanup', # Triggered before htmx removes its state from an element.
  'before:history:restore', # Triggered before history restoration.
  'before:history:update', # Triggered before a history push or replace.
  'before:init', # Triggered before htmx initializes an element.
  'before:morph:attr', # Triggered before a morph swap updates an attribute.
  'before:morph:node', # Triggered before a morph swap updates a node.
  'before:on:init', # Triggered before htmx binds hx-on handlers.
  'before:process', # Triggered before htmx processes an element and its descendants.
  'before:request', # Triggered before a request is sent.
  'before:response', # Triggered after the response headers arrive, before the body is read.
  'before:settle', # Triggered before the DOM settles.
  'before:swap', # Triggered before a swap is done; preventDefault cancels the swap.
  'before:viewTransition', # Triggered before a view transition starts.
  'config:request', # Triggered before the request, allows customizing parameters and headers.
  'confirm', # Triggered before a request that has hx-confirm; allows cancelling or delaying it.
  'error', # Triggered when an internal error occurs.
  'finally:request', # Triggered after a request finishes, whether or not it succeeded.
  'finally:swap', # Triggered after a swap finishes, whether or not it succeeded.
  'response:error', # Triggered when the response status is 400 or greater.
]
