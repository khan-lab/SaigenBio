# Loaded only by the shell launched through saigen start.
# Shell history would otherwise persist unredacted command text.
unset HISTFILE
SAVEHIST=0
unsetopt SHARE_HISTORY INC_APPEND_HISTORY INC_APPEND_HISTORY_TIME 2>/dev/null

function saigen() { "$SAIGEN_PYTHON" -m saigen "$@"; }
function _saigen_record() {
  "$SAIGEN_PYTHON" -m saigen _shell-event "$@" ||
    print -u2 -- "SaigenBio: recording failed; this activity may be missing."
}
function _saigen_before() {
  print -rn -- "$1" | _saigen_record begin --cwd "$PWD"
}
function _saigen_after() {
  _saigen_record end --exit-code "$1" --pipeline "${@:2}"
}

# Observe status before prompt plugins change it.
if (( $+functions[preexec] )); then
  functions[_saigen_user_preexec]=$functions[preexec]
fi
if (( $+functions[precmd] )); then
  functions[_saigen_user_precmd]=$functions[precmd]
fi
function preexec() {
  _saigen_before "$1"
  if (( $+functions[_saigen_user_preexec] )); then
    _saigen_user_preexec "$@"
  fi
  return 0
}
function precmd() {
  local -a _saigen_codes=( "$?" "${pipestatus[@]}" )
  _saigen_after "${_saigen_codes[@]}"
  if (( $+functions[_saigen_user_precmd] )); then
    _saigen_user_precmd
  fi
  return 0
}
print -- "SaigenBio recording active. Use saigen save for a state; saigen pause/resume controls capture; exit ends this session."
