# Fish completion for jh. Install: copy to
# ~/.config/fish/completions/jh.fish (auto-loaded by fish).
# Generated and managed by `jh completion install`.

function __jh_complete
    # `commandline -ct` outputs nothing when the cursor sits right after
    # whitespace, which would contribute zero elements to a list. We
    # capture it into its own var and quote the expansion so an empty
    # current token still reaches the completer as an empty positional
    # argument — without it, `jh show <TAB>` would lose the trailing
    # empty arg and the completer would treat `show` as the partial
    # being typed, returning top-level commands instead of slugs.
    set -l prev (commandline -opc)
    set -l current (commandline -ct)
    set -l result (jh __complete fish $prev "$current" 2>/dev/null)
    # Directive: defer local-filesystem path completion to fish's
    # built-in path completer for the partial token under the cursor.
    if test (count $result) -gt 0; and test $result[1] = "__JH_COMPLETE_FILES__"
        __fish_complete_path "$current"
        return
    end
    for line in $result
        echo $line
    end
end

complete -c jh -f -a "(__jh_complete)"
