# Bash completion for jh. Install: copy to
# ~/.local/share/bash-completion/completions/jh
# Generated and managed by `jh completion install`.

_jh_complete() {
    local cur prev words cword
    _init_completion -n : || return

    local response_raw
    local -a response_lines

    # Pass everything typed so far, including the partial last word.
    # COMP_WORDS includes the program name; we pass it through.
    response_raw="$(jh __complete bash "${COMP_WORDS[@]:0:$COMP_CWORD}" "${COMP_WORDS[$COMP_CWORD]}" 2>/dev/null)"

    # Newline-split into an array; preserves spaces inside each line.
    mapfile -t response_lines <<< "$response_raw"

    # Directive: when the completer can't enumerate candidates itself
    # (e.g. local filesystem paths), it emits a sentinel. Hand back to
    # readline's default completion so tilde expansion, directory `/`
    # suffixes and friends work as users expect.
    if [[ "${response_lines[0]:-}" == "__JH_COMPLETE_FILES__" ]]; then
        COMPREPLY=()
        compopt -o default 2>/dev/null || true
        compopt -o filenames 2>/dev/null || true
        return
    fi

    # Bash does NOT auto-filter COMPREPLY by the current word when we
    # populate it directly (it would if we used `compgen -W`, but that
    # word-splits on whitespace and breaks filenames with spaces). So
    # we apply the prefix filter manually here.
    local current="${COMP_WORDS[$COMP_CWORD]}"
    COMPREPLY=()
    local cand
    for cand in "${response_lines[@]}"; do
        [[ -z "$cand" ]] && continue
        [[ "$cand" == "$current"* ]] || continue
        # %q escapes whitespace and shell metacharacters so bash treats
        # the candidate as a single token when inserted.
        COMPREPLY+=("$(printf '%q' "$cand")")
    done

    # Don't append a trailing space — keeps completion sticky on partials.
    compopt -o nospace 2>/dev/null || true
}

complete -F _jh_complete jh
