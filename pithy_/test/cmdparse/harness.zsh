# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Exercise the zsh completion scripts with stubbed completion builtins.
# The real compadd/compset/_files exist only inside a completion widget, so stubs print their arguments instead.

# Ensure `python3 -m example` finds the linked module even when PYTHONSAFEPATH suppresses the automatic cwd entry.
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH}

compadd() {
  local dname suffix have_suffix jgroup heading
  local -a disp
  while (( $# )); do
    case $1 in
      -d) dname=$2; shift 2;;
      -S) suffix=$2; have_suffix=1; shift 2;;
      -J) jgroup=$2; shift 2;;
      -X) heading=$2; shift 2;;
      --) shift; break;;
      *) print -r -- "compadd: unexpected option: $1"; return 1;;
    esac
  done
  local out="compadd"
  if [[ -n $jgroup ]]; then out+=" tag=$jgroup heading=($heading)"; fi
  out+=" cands=(${(pj:|:)@})"
  if [[ -n $have_suffix ]]; then out+=" suffix=($suffix)"; fi
  if [[ -n $dname ]]; then
    disp=("${(@P)dname}")
    out+=" disp=(${(pj:|:)disp})"
  fi
  print -r -- "$out"
}

# The real _description consults the `descriptions` format zstyle; the stub passes the tag and heading through.
_description() {
  set -A $2 -J $1 -X $3
}

compset() { print -r -- "compset $*" }
_files() { print -r -- "_files" }
compdef() { : }
autoload() { : }
_pithy_cmdparse_stock_python() { print -r -- "stock-python" }

source ./pithy-cmdparse-completion.zsh
source ./pithy-cmdparse-module-completion.zsh

PITHY_CMDPARSE_MODE=print-zsh-completion ./example.py > _example.py.zsh
source ./_example.py.zsh

run() {
  print -r -- "== $*"
  words=("$@")
  CURRENT=$#words
  _example_py
}

run ./example.py --j
run ./example.py ''
run ./example.py --home ''
run ./example.py --home=src
run ./example.py -verbose ''
run ./example.py bu
run ./example.py build ''
run ./example.py build ap
run ./example.py build app -jobs ''
run ./example.py deploy ''

pithy_cmdparse_module_completion example

run_python() {
  print -r -- "== $*"
  words=("$@")
  CURRENT=$#words
  _pithy_cmdparse_complete_python
}

run_python python3 script.py ''
run_python python3 -m ex
run_python python3 -mex
run_python python3 -m example bu
run_python python3 -mexample --j
run_python python3 -m other ''

print -r -- '== emit-cmdparse-completion'
HOME=$PWD emit-cmdparse-completion ./example.py
ls .zfunc
