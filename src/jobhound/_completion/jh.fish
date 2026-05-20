# Fish completion for jh. Install: copy to
# ~/.config/fish/completions/jh.fish (auto-loaded by fish).
# Generated and managed by `jh completion install`.

function __jh_complete
    set -l tokens (commandline -opc) (commandline -ct)
    set -l result (jh __complete fish $tokens 2>/dev/null)
    # Directive: defer local-filesystem path completion to fish's
    # built-in path completer for the partial token under the cursor.
    if test (count $result) -gt 0; and test $result[1] = "__JH_COMPLETE_FILES__"
        __fish_complete_path (commandline -ct)
        return
    end
    for line in $result
        echo $line
    end
end

complete -c jh -f -a "(__jh_complete)"
