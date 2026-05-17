#compdef jh
# Zsh completion for jh. Install: copy to a dir in $fpath as `_jh`,
# then `autoload -U compinit; compinit`. Default install location is
# ~/.zfunc/_jh (jh completion install will set this up).
# Generated and managed by `jh completion install`.

_jh() {
    local -a candidates
    # (@f) splits on newlines only, preserving spaces inside each line.
    candidates=("${(@f)$(jh __complete zsh ${words[1,$CURRENT-1]} ${words[$CURRENT]} 2>/dev/null)}")
    compadd -a candidates
}

_jh "$@"
