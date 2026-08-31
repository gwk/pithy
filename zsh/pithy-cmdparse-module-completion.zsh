# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Zsh completion for `python -m module` invocations of cmdparse-based commands.
# This wraps the stock `_python` completion, so it must be sourced at startup; it cannot be an fpath file.
# Source pithy-cmdparse-completion.zsh and then this file in ~/.zshrc after `compinit`,
# then call `pithy_cmdparse_module_completion mod ...`.

typeset -gA _pithy_cmdparse_modules


_pithy_cmdparse_complete_python() {
  local idx module module_idx invocation_end args_start attached
  for (( idx = 2; idx <= CURRENT; idx++ )); do
    if [[ $words[$idx] == -m ]]; then
      module_idx=$(( idx + 1 ))
      invocation_end=$module_idx
      args_start=$(( module_idx + 1 ))
      module=$words[$module_idx]
      break
    elif [[ $words[$idx] == -m?* ]]; then
      module_idx=$idx
      invocation_end=$idx
      args_start=$(( idx + 1 ))
      module=${words[$idx]#-m}
      attached=1
      break
    elif [[ $words[$idx] == -c || $words[$idx] == -c?* || $words[$idx] == -- || $words[$idx] != -* ]]; then
      break
    elif [[ $words[$idx] == -W || $words[$idx] == -X || $words[$idx] == --check-hash-based-pycs ]]; then
      (( idx++ ))
    fi
  done

  if [[ -z $module_idx ]]; then
    _pithy_cmdparse_stock_python "$@"
    return
  fi

  if (( CURRENT == module_idx )); then
    _pithy_cmdparse_stock_python "$@"
    local stock_status=$?
    if [[ -n $attached ]]; then
      compset -p 2 # Strip the attached `-m` prefix.
    fi
    compadd -- "${(@k)_pithy_cmdparse_modules}"
    local module_status=$?
    (( !stock_status || !module_status ))
    return
  fi

  if (( CURRENT > module_idx )) && [[ -n ${_pithy_cmdparse_modules[$module]} ]]; then
    local -a cmdparse_invocation=("${(@)words[1,$invocation_end]}")
    local -a cmdparse_args=("${(@)words[$args_start,$CURRENT]}")
    _pithy_cmdparse_complete_request
    return
  fi

  _pithy_cmdparse_stock_python "$@"
}


_pithy_cmdparse_install_python_completion() {
  if (( ! $+functions[_pithy_cmdparse_stock_python] )); then
    autoload -Uz +X _python
    functions -c _python _pithy_cmdparse_stock_python
    functions -c _pithy_cmdparse_complete_python _python
  fi
}


# Register Python modules whose `python -m` entry points use cmdparse. Repeated calls register additional modules.
pithy_cmdparse_module_completion() {
  local module
  for module in "$@"; do
    _pithy_cmdparse_modules[$module]=1
  done
  _pithy_cmdparse_install_python_completion
}
