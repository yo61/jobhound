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

    COMPREPLY=()
    local cand
    for cand in "${response_lines[@]}"; do
        [[ -z "$cand" ]] && continue
        # %q escapes whitespace and shell metacharacters so bash treats
        # the candidate as a single token when inserted.
        COMPREPLY+=("$(printf '%q' "$cand")")
    done

    # Don't append a trailing space — keeps completion sticky on partials.
    compopt -o nospace 2>/dev/null || true
}

complete -F _jh_complete jh
