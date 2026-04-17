from sys import argv

from pithy.argparse import CommandParser, Namespace
from utest import utest_val


parser = CommandParser()

def main_cmdB(ns:Namespace) -> None:
  assert 0 # Not called.

cmdA_parser = parser.add_parent_command('cmdA')
cmdA_parser.add_argument('-a_arg', help='An argument.')

cmdB_parser = parser.add_parent_command('cmdB')
cmdB_parser.add_argument('-b_arg', help='A second argument.')

def main_cmdAA(ns:Namespace) -> None:
  utest_val(ns.a_arg, 'arg1')
  utest_val(ns.aa_arg, 'arg2')

def main_cmdBB(ns:Namespace) -> None:
  assert 0 # Not called.

cmdAA_parser = cmdA_parser.add_command(main_cmdAA)
cmdAA_parser.add_argument('-aa_arg', help='A subcommand argument.')

cmdBB_parser = cmdB_parser.add_command(main_cmdBB)
cmdBB_parser.add_argument('-bb_arg', help='A second subcommand argument.')

parser.parse_and_run_command(['cmdA', '-a_arg', 'arg1', 'cmdAA', '-aa_arg', 'arg2'])
