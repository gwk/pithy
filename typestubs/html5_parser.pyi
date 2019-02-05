from typing import Any

def parse(
    html:str,
    transport_encoding:str=None,
    namespace_elements=False,
    treebuilder='lxml',
    fallback_encoding:str=None,
    keep_doctype=True,
    maybe_xhtml=False,
    return_root=True,
    line_number_attr:str=None,
    sanitize_names=True,
    stack_size:int=... ) -> Any: ...
