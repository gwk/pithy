# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..html import HtmlNode


def configure_htmx_event_replaced_attrs() -> None:
  '''
  Update `HtmlNode.replaced_attrs` with single-hyphen versions of all hx-on--{event} attributes.
  e.g. 'hx-on-click' -> 'hx-on--click'.
  Note that the canonical form is 'hx-on:htmx:before-request'.
  This can be simplified to 'hx-on::before-request'.
  Furthermore, hyphens can replace colons, leading to 'hx-on--before-request'.
  See:
  * https://htmx.org/attributes/hx-on/
  * https://htmx.org/reference/#events
  '''
  HtmlNode.replaced_attrs.update({f'hx-on-{ke}' : f'hx-on--{ke}' for ke in htmx_kebab_events })


htmx_events = [
  'abort', # Send this event to an element to abort a request.
  'afterOnLoad', # Triggered after an AJAX request has completed processing a successful response.
  'afterProcessNode', # Triggered after htmx has initialized a node.
  'afterRequest', # Triggered after an AJAX request has completed.
  'afterSettle', # Triggered after the DOM has settled.
  'afterSwap', # Triggered after new content has been swapped in.
  'beforeCleanupElement', # Triggered before htmx disables an element or removes it from the DOM.
  'beforeOnLoad', # Triggered before any response processing occurs.
  'beforeProcessNode', # Triggered before htmx initializes a node.
  'beforeRequest', # Triggered before an AJAX request is made.
  'beforeSwap', # Triggered before a swap is done, allows you to configure the swap.
  'beforeSend', # Triggered just before an ajax request is sent.
  'beforeTransition', # Triggered before the View Transition wrapped swap occurs.
  'configRequest', # Triggered before the request, allows you to customize parameters, headers.
  'confirm', # Triggered after a trigger occurs on an element, allows you to cancel (or delay) issuing the AJAX request.
  'historyCacheError', # Triggered on an error during cache writing.
  'historyCacheMiss', # Triggered on a cache miss in the history subsystem.
  'historyCacheMissError', # Triggered on a unsuccessful remote retrieval.
  'historyCacheMissLoad', # Triggered on a successful remote retrieval.
  'historyRestore', # Triggered when htmx handles a history restoration action.
  'beforeHistorySave', # Triggered before content is saved to the history cache.
  'load', # Triggered when new content is added to the DOM.
  'noSSESourceError', # Triggered when an element refers to a SSE event in its trigger, but no parent SSE source has been defined.
  'onLoadError', # Triggered when an exception occurs during the onLoad handling in htmx.
  'oobAfterSwap', # Triggered after an out of band element as been swapped in.
  'oobBeforeSwap', # Triggered before an out of band element swap is done, allows you to configure the swap.
  'oobErrorNoTarget', # Triggered when an out of band element does not have a matching ID in the current DOM.
  'prompt', # Triggered after a prompt is shown.
  'pushedIntoHistory', # Triggered after an url is pushed into history.
  'responseError', # Triggered when an HTTP response error (non-200 or 300 response code) occurs.
  'sendError', # Triggered when a network error prevents an HTTP request from happening.
  'sseError', # Triggered when an error occurs with a SSE source.
  'sseOpen', # Triggered when a SSE source is opened.
  'swapError', # Triggered when an error occurs during the swap phase.
  'targetError', # Triggered when an invalid target is specified.
  'timeout', # Triggered when a request timeout occurs.
  'validation:validate', # Triggered before an element is validated.
  'validation:failed', # Triggered when an element fails validation.
  'validation:halted', # Triggered when a request is halted due to validation errors.
  'xhr:abort', # Triggered when an ajax request aborts.
  'xhr:loadend', # Triggered when an ajax request ends.
  'xhr:loadstart', # Triggered when an ajax request starts.
  'xhr:progress', # Triggered periodically during an ajax request that supports progress events.
]

htmx_kebab_events = [
  'abort',
  'after-on-load',
  'after-process-node',
  'after-request',
  'after-settle',
  'after-swap',
  'before-cleanup-element',
  'before-on-load',
  'before-process-node',
  'before-request',
  'before-swap',
  'before-send',
  'before-transition',
  'config-request',
  'confirm',
  'history-cache-error',
  'history-cache-miss',
  'history-cache-miss-error',
  'history-cache-miss-load',
  'history-restore',
  'before-history-save',
  'load',
  'no-sse-source-error',
  'on-load-error',
  'oob-after-swap',
  'oob-before-swap',
  'oob-error-no-target',
  'prompt',
  'pushed-into-history',
  'response-error',
  'send-error',
  'sse-error',
  'sse-open',
  'swap-error',
  'target-error',
  'timeout',
  'validation-validate',
  'validation-failed',
  'validation-halted',
  'xhr-abort',
  'xhr-loadend',
  'xhr-loadstart',
  'xhr-progress',
]
