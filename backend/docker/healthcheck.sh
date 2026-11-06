#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Docker HEALTHCHECK of the ExApp container (T-02-25).
#
# Unchanged copy via nextcloud-mcp-connector and Gameworld. The app answers /heartbeat
# through nc_py_api (set_handlers), without authentication.
#
# AppAPI reads the container health before it sends the first heartbeat, and a container
# without a healthcheck counts as healthy, which hides a failed start until the fifteen
# minute deploy timeout expires. So the probe has to be honest about both transports.
#
# Behind HaRP the process listens on a unix socket and there is no TCP port at all;
# HP_SHARED_KEY is the switch, the very same one nc_py_api's run_app uses. A probe against
# 127.0.0.1:APP_PORT would be permanently red there, and AppAPI would sit out its timeout
# on a container that is in fact serving. Without HaRP the socket does not exist and the
# port is the only way in.
#
# The exit code of curl is the exit code of this script: exec, no wrapper, no retry. The
# retries belong to the HEALTHCHECK instruction, not here.
set -eu

# Is frpc still running? Only asked on the HaRP path, where it is the transport (WR-05).
# start.sh launches it as an unsupervised background child of PID 1 and configures
# `loginFailExit = false`, so a dead or never logged in frpc leaves uvicorn answering
# happily on the socket while HaRP has no backend at all: the container reports healthy and
# every request from outside is a 503. /proc instead of pgrep, because the image carries no
# procps and one probe is not worth a package.
frpc_is_running() {
    for entry in /proc/[0-9]*; do
        [ -r "${entry}/comm" ] || continue
        if [ "$(cat "${entry}/comm" 2>/dev/null)" = "frpc" ]; then
            return 0
        fi
    done
    return 1
}

if [ -n "${HP_SHARED_KEY:-}" ]; then
    if ! frpc_is_running; then
        echo "frpc is not running; HaRP has no backend for this container" >&2
        exit 1
    fi
    exec curl -fsS -o /dev/null \
        --unix-socket "${HP_EXAPP_SOCK:-/tmp/exapp.sock}" \
        http://localhost/heartbeat
fi

exec curl -fsS -o /dev/null "http://127.0.0.1:${APP_PORT}/heartbeat"
