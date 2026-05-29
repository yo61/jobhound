#compdef jh
# Zsh completion for jh. Install: copy to a dir in $fpath as `_jh`,
# then `autoload -U compinit; compinit`. Default install location is
# ~/.zfunc/_jh (jh completion install will set this up).
# Generated and managed by `jh completion install`.

_jh() {
    local -a candidates
    # (@f) splits the command output on newlines only, preserving spaces
    # inside each line. The inner expansions MUST be quoted:
    #   - "${(@)words[1,$CURRENT-1]}" preserves each prior token as its own
    #     argument even when the token contains whitespace (e.g. a flag
    #     value like --body "long note"). The (@) flag preserves array
    #     element boundaries inside double quotes.
    #   - "${words[$CURRENT]}" ensures an empty current word is still
    #     passed as an empty positional. Unquoted, an empty value is
    #     elided entirely and the completer treats the previous word as
    #     the partial being typed — so `jh show <TAB>` would list
    #     top-level commands instead of opportunity slugs.
    candidates=("${(@f)$(jh __complete zsh "${(@)words[1,$CURRENT-1]}" "${words[$CURRENT]}" 2>/dev/null)}")

    # Directive: defer local-filesystem path completion to zsh's _files,
    # which handles tilde expansion, directory `/` suffixes and the
    # user's `zstyle` preferences.
    if [[ "${candidates[1]:-}" == "__JH_COMPLETE_FILES__" ]]; then
        _files
        return
    fi

    compadd -a candidates
}

_jh "$@"
