# shellcheck shell=sh
# Installed as /etc/profile.d/nara.sh. Debian's /etc/profile resets PATH for
# every login shell (`bash -l`, `docker exec <c> bash -l`, ssh, the terminal
# tool's background `bash -lic`), dropping the image's ENV PATH dirs, so bare
# `nara` exits 127 there. Put them back in the ENV PATH order; dirs a login
# PATH already lists keep their position.
for __nara_p in /opt/data/.local/bin /opt/nara/.venv/bin /opt/nara/bin; do
    case ":$PATH:" in
        *":$__nara_p:"*) ;;
        *) PATH="$__nara_p:$PATH" ;;
    esac
done
unset __nara_p
export PATH
