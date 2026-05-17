# Fish completion for jh. Install: copy to
# ~/.config/fish/completions/jh.fish (auto-loaded by fish).
# Generated and managed by `jh completion install`.

function __jh_complete
    set -l tokens (commandline -opc) (commandline -ct)
    jh __complete fish $tokens 2>/dev/null
end

complete -c jh -f -a "(__jh_complete)"
