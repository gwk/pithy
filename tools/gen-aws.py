#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.
# type: ignore

import re
from argparse import ArgumentParser
from functools import singledispatch
from sys import stdin
from typing import *

import boto3
from botocore.docs.shape import ShapeDocumenter
from botocore.model import ListShape, MapShape, OperationModel, Shape, StringShape, StructureShape
from pithy.io import *


methods = { 'get_object', 'put_object', 'list_objects_v2' }


def main() -> None:
  arg_parser = ArgumentParser('Generate AWS API.')
  args = arg_parser.parse_args()

  services = ['s3']

  for service in services:
    generate_service(service)


def generate_service(service:str) -> None:
  outL(f'\n\nService: {service}')
  client = boto3.client(service)
  meta = client.meta
  service_model = meta.service_model
  for method, api in meta.method_to_api_mapping.items():
    if method not in methods: continue
    op_model = service_model.operation_model(api)
    generate_method(method, api, op_model)


def generate_method(method:str, api:str, op_model:OperationModel) -> None:
  outL(f'\ndef {method}(self, *,')

  in_sh = op_model.input_shape
  if in_sh is None: outL(' ) -> # Input shape is missing.')
  else:
    if in_sh.documentation: outL('  # ', in_sh.documentation)
    for k in Shape.METADATA_ATTRS:
      if k != 'required' and k in in_sh.metadata:
        outSL('   # metadata:', k, ':', in_sh.metadata[k])
    req = frozenset(in_sh.required_members)
    for name, shape in sorted(in_sh.members.items(), key=lambda p: (p[0] not in req, p)):
      handle_input(shape, name=name)
      r = 'Required.' if name in req else ''
      outL(f', # {r}')
    outL(' ) ->')

  out_sh = op_model.output_shape
  if out_sh is None:
    outZ('None')
  else:
    #outSL('  name:', out_sh.name)
    if out_sh.documentation: outL('  # ', out_sh.documentation)
    if isinstance(out_sh, StructureShape):
      outL(' {')
      req = frozenset(out_sh.required_members)
      for name, shape in sorted(out_sh.members.items(), key=lambda p: (p[0] not in req, p)):
        handle_output(shape, name=name)
        r = 'Required.' if name in req else ''
        outL(f', # {r}')
      outZ(' }')
    else:
      raise NotImplementedError(out_sh)
  outL(': ...')


@singledispatch
def handle_input(shape:Shape, name:str) -> None:
  t = shape_type_names_to_py_types[shape.type_name]
  outZ(f'  {name}:{t.__name__}')
  #if shape.metadata: outL(


@handle_input.register
def _(shape:StringShape, name:str) -> None:
  outZ(f'  {name}:str')
  enum = shape.enum
  if enum is not None:
    pass

@handle_input.register
def _(shape:StructureShape, name:str) -> None:
  outZ(f'  {name}:?')
  for name, shape in shape.members.items():
    handle_input(shape, name, depth+1)

@handle_input.register
def _(shape:MapShape, name:str) -> None:
  k = shape.key
  v = shape.value
  kt = shape_type_names_to_py_types[k.type_name]
  vt = shape_type_names_to_py_types[v.type_name]
  outZ(f'  {name}:Dict[{kt.__name__}, {vt.__name__}]')

@handle_input.register
def _(shape:ListShape, name:str) -> None:
  outZ(f'  {name}:list[{shape.member}]')


@singledispatch
def handle_output(shape:Shape, name:str) -> None:
  t = shape_type_names_to_py_types[shape.type_name]
  outZ(f'  {name!r}:{t.__name__}')

@handle_output.register
def _(shape:StringShape, name:str) -> None:
  outZ(f'  {name!r}:str')
  enum = shape.enum
  if enum is not None:
    pass

@handle_output.register
def _(shape:StructureShape, name:str) -> None:
  outZ(f'  {name!r}:?')
  for name, shape in shape.members.items():
    handle_output(shape, name, depth+1)

@handle_output.register
def _(shape:MapShape, name:str) -> None:
  k = shape.key
  v = shape.value
  kt = shape_type_names_to_py_types[k.type_name]
  vt = shape_type_names_to_py_types[v.type_name]
  outZ(f'  {name!r}:Dict[{kt.__name__}, {vt.__name__}]')

@handle_output.register
def _(shape:ListShape, name:str) -> None:
  outZ(f'  {name}:list[{shape.member}]')


shape_type_names_to_py_types = {
  'blob' : bytes,
  'boolean' : bool,
  'integer' : int,
  'string' : str,
  'timestamp': float,
  'long': int,
}


if __name__ == '__main__': main()
