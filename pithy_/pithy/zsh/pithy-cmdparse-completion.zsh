# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Core zsh completion support for cmdparse-based commands.
# Source this file in ~/.zshrc; the completion scripts printed by `PITHY_CMDPARSE_MODE=print-zsh-completion`
# call `_pithy_cmdparse_complete_request`. See the pithy.cmdparse module docs.
# For completion of `python -m module` invocations, also source pithy-cmdparse-module-completion.zsh.
#
# Candidates are added in named groups (tags: commands, options, values), so the standard zstyles apply.
# Group headings render through the `descriptions` format style; the heading text is 'Subcommands', 'Options' or 'Values'.
# For example, add to ~/.zshrc:
#   zstyle ':completion:*:descriptions' format '%F{cyan}%d:%f'
#   zstyle ':completion:*' group-name ''
# The second line makes zsh list each group separately instead of merging them.
# Reorder or hide groups per command with e.g.:
#   zstyle ':completion:*:complete:<name>:*' tag-order 'commands options'
#
# Listing colors are controlled by the complist module's `list-colors` zstyle, which matches display strings.
# For example, to dim the description following each candidate, add to ~/.zshrc:
#   zstyle ':completion:*' list-colors '=(#b)*( : *)=0=2'
# The `(#b)` activates backreferences; the first `=0` styles the whole match and `=2` (faint) styles the group.
# Scope the style to one command with ':completion:*:*:<name>:*', or to one tag with ':completion:*:<tag>'.


# Generate the completion script for a cmdparse-based command and install it as `_<name>` in ~/.zfunc.
emit-cmdparse-completion() {
  if (( $# != 1 )); then
    print -ru2 -- 'usage: emit-cmdparse-completion <command-name>'
    return 2
  fi
  local prog=$1 name=${1:t} script
  script=$(PITHY_CMDPARSE_MODE=print-zsh-completion "$prog") || {
    print -ru2 -- "emit-cmdparse-completion: failed to run: $prog"
    return 1
  }
  mkdir -p ~/.zfunc || return 1
  print -r -- "$script" > ~/.zfunc/_$name
  print -r -- "wrote ~/.zfunc/_$name"
}


# Invoke `$cmdparse_invocation` in complete mode with `$cmdparse_args` and add the resulting completions.
# Candidates arrive tagged with a display group; each group is added through `_description`,
# so the standard zstyles (`descriptions` format, `group-name`, `tag-order`, tag-scoped `list-colors`) apply.
_pithy_cmdparse_complete_request() {
  local line kind group value doc disp path_prefix has_path
  local -a lines fields expl
  local -a cmd_cands cmd_disps opt_cands opt_disps opt_eq_cands opt_eq_disps val_cands val_disps
  lines=("${(@f)$(PITHY_CMDPARSE_MODE=complete "$cmdparse_invocation[@]" "$cmdparse_args[@]" 2>/dev/null)}")
  for line in $lines; do
    fields=("${(@ps:\t:)line}")
    kind=$fields[1]
    if [[ $kind == candidate ]]; then
      group=$fields[2]
      value=$fields[3]
      doc=$fields[4]
      disp=$value
      if [[ -n $doc ]]; then disp="$value : $doc"; fi
      case $group in
        commands)
          cmd_cands+=("$value")
          cmd_disps+=("$disp");;
        options)
          if [[ $value == *= ]]; then
            opt_eq_cands+=("$value")
            opt_eq_disps+=("$disp")
          else
            opt_cands+=("$value")
            opt_disps+=("$disp")
          fi;;
        *)
          val_cands+=("$value")
          val_disps+=("$disp");;
      esac
    elif [[ $kind == path ]]; then
      has_path=1
      path_prefix=$fields[2]
    fi
  done

  if (( $#cmd_cands )); then
    _description commands expl 'Subcommands'
    compadd "$expl[@]" -d cmd_disps -- "$cmd_cands[@]"
  fi
  if (( $#opt_cands || $#opt_eq_cands )); then
    _description options expl 'Options'
    if (( $#opt_cands )); then compadd "$expl[@]" -d opt_disps -- "$opt_cands[@]"; fi
    if (( $#opt_eq_cands )); then compadd "$expl[@]" -S '' -d opt_eq_disps -- "$opt_eq_cands[@]"; fi
  fi
  if (( $#val_cands )); then
    _description values expl 'Values'
    compadd "$expl[@]" -d val_disps -- "$val_cands[@]"
  fi
  if (( has_path )); then
    if [[ -n $path_prefix ]]; then compset -P "$path_prefix"; fi
    _files
  fi
}
