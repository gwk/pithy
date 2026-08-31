#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Literal

from pithy.cmdparse import Cmd, flag, opt, Path, pos, sub


class Build(Cmd):
  'Build the project.'
  target:Literal['app','lib'] = pos(doc='The build target.')
  jobs:int = opt(default=1, doc='Number of parallel jobs.')
  verbose:bool = flag(doc='Print more.')

  def run(self) -> None: print(f'build {self.target} jobs={self.jobs} verbose={self.verbose}')


class Deploy(Cmd):
  'Deploy the build.'
  dest:Path = pos(doc='The destination path.')

  def run(self) -> None: print(f'deploy {self.dest}')


class Example(Cmd):
  'Example command for completion tests.'
  home:Path = opt(default='', doc='The home path.')
  cmd:Build|Deploy = sub(doc='The command to run.')


if __name__ == '__main__': Example.main()
