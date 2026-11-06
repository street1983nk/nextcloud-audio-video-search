#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Entrypoint of the image: two guards, then the unchanged HaRP start.sh.
# Taken over from Gameworld (template: nextcloud-mcp-connector/entrypoint.sh).
#
# Guard 1: without the three files in /certs/frp, start.sh falls back to
# transport.tls.enable = false and sends HP_SHARED_KEY in plain text. HaRP copies
# the certificate into the running container, so it is waited for; if it does not
# arrive the container does not start (unless ALLOW_PLAINTEXT_FRP=1 on a trusted
# local network).
#
# Guard 2: the container runs as uid 10001 without a root moment and without
# chown. A fresh volume takes over owner and mode of the directory prepared in the
# image. If it belongs to root after all, the start aborts here with a clear
# message instead of failing later on the first write.
set -eu

FRP_CERT_DIR="/certs/frp"
FRP_CERT_WAIT_SECONDS="${FRP_CERT_WAIT_SECONDS:-60}"
STORAGE_DIR="${APP_PERSISTENT_STORAGE:-/nc_app_audio_video_search_backend_data}"

storage_writable() {
    if [ ! -d "${STORAGE_DIR}" ]; then
        mkdir -p "${STORAGE_DIR}" 2>/dev/null || return 1
    fi
    probe="${STORAGE_DIR}/.write-probe.$$"
    if ( : > "${probe}" ) 2>/dev/null; then
        rm -f "${probe}"
        return 0
    fi
    return 1
}

if ! storage_writable; then
    echo "ERROR: APP_PERSISTENT_STORAGE ${STORAGE_DIR} is not writable for uid $(id -u)." >&2
    echo "ERROR: Let AppAPI create the volume again (reinstall the app) or chown it to 10001:10001." >&2
    exit 1
fi

# HaRP creates the directory with mkdir -p before it copies the three files, so
# the files themselves are waited for, not the directory.
frp_certs_present() {
    [ -f "${FRP_CERT_DIR}/client.crt" ] &&
        [ -f "${FRP_CERT_DIR}/client.key" ] &&
        [ -f "${FRP_CERT_DIR}/ca.crt" ]
}

if [ -n "${HP_SHARED_KEY:-}" ]; then
    waited=0
    while ! frp_certs_present && [ "${waited}" -lt "${FRP_CERT_WAIT_SECONDS}" ]; do
        if [ "${waited}" -eq 0 ]; then
            echo "waiting for HaRP to install the FRP client certificate in ${FRP_CERT_DIR}"
        fi
        sleep 1
        waited=$((waited + 1))
    done

    if ! frp_certs_present; then
        if [ "${ALLOW_PLAINTEXT_FRP:-0}" = "1" ]; then
            echo "WARNING: ${FRP_CERT_DIR} is still incomplete after ${FRP_CERT_WAIT_SECONDS}s." >&2
            echo "WARNING: ALLOW_PLAINTEXT_FRP=1 is set, so frpc sends HP_SHARED_KEY unencrypted." >&2
            echo "WARNING: Only ever do this on a trusted local network." >&2
        else
            echo "ERROR: ${FRP_CERT_DIR} is still missing client.crt, client.key or ca.crt after ${FRP_CERT_WAIT_SECONDS}s." >&2
            echo "ERROR: frpc would send HP_SHARED_KEY in the clear. Refusing to start." >&2
            echo "ERROR: The usual cause is a /certs that is not writable for uid 10001." >&2
            echo "ERROR: Set ALLOW_PLAINTEXT_FRP=1 on a trusted local network, or raise FRP_CERT_WAIT_SECONDS." >&2
            exit 1
        fi
    fi
fi

exec /start.sh "$@"
