#!/usr/bin/env bash
# Shared pieces of truth.sh, ledger.sh, compare.sh and controls.sh: the order of
# the phases, the paths of the throwaway instance, ids.env and the passwords.
#
# Nothing in here runs code of this app: no occ command of audio_video_search,
# no container, no PHP class. truth.sh sources this file, so it has to stay
# that way (gate in backend/tests/test_discovery_workflow.py).
#
# Sourced, never run.

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
IDS_ENV="${IDS_ENV:-${SCRIPT_DIR}/ids.env}"
DATADIR="${DATADIR:-${PWD}/data}"
NC_DB="${DATADIR}/owncloud.db"
WORK="${RUNNER_TEMP:-/tmp}/avs-discovery"
ACCESS_LOG="${ACCESS_LOG:-${RUNNER_TEMP:-/tmp}/php-server.log}"
LEDGER="${LEDGER:-${WORK}/ledger.tsv}"
SHARE_DIR=/srv/avs-medien
SMB_URL=//127.0.0.1/Medien
LOCAL_DIR="${RUNNER_TEMP:-/tmp}/avs-lokal"
S3_BUCKET=avs-medien

# The phases of the acceptance test, in the order the workflow runs them. A
# later phase inherits every change of the earlier ones.
PHASES=(initial read-proof shares access-control upload overwrite copy rename tag move-cross trash
	restore exclude-user-after exclude-storage-after exclude-after reprove vanish delete-user reattach
	foreign-change)

# The media endings of MEDIA-01, in lower case.
MEDIA_ENDINGS='mp3|m4a|wav|ogg|oga|opus|flac|mp4|m4v|mov|mkv|webm|weba|mts|avi|wmv|3gp|mpeg'

mkdir -p "${WORK}"

fail() {
	echo "::error::$*"
	exit 1
}

# phase_index NAME: the place of NAME in PHASES, or nothing.
phase_index() {
	local i
	for i in "${!PHASES[@]}"; do
		if [ "${PHASES[$i]}" = "$1" ]; then
			echo "${i}"
			return
		fi
	done
}

# is_phase NAME: NAME is one of the phases.
is_phase() {
	[ -n "$(phase_index "$1")" ]
}

# reached CURRENT REF: CURRENT is REF or a later phase.
reached() {
	local current ref
	current=$(phase_index "$1")
	ref=$(phase_index "$2")
	[ -n "${current}" ] && [ -n "${ref}" ] && [ "${current}" -ge "${ref}" ]
}

# previous_phase NAME: the phase before NAME, empty for the first one.
previous_phase() {
	local i
	i=$(phase_index "$1")
	[ -n "${i}" ] && [ "${i}" -gt 0 ] && echo "${PHASES[$((i - 1))]}"
	return 0
}

is_media() {
	grep -qiE "\.(${MEDIA_ENDINGS})\$" <<< "$1"
}

password_of() {
	case "$1" in
		admin) printf '%s' "${ADMIN_PASS:?}" ;;
		ana) printf '%s' "${ANA_PASS:?}" ;;
		ben) printf '%s' "${BEN_PASS:?}" ;;
		cem) printf '%s' "${CEM_PASS:?}" ;;
		dan) printf '%s' "${DAN_PASS:?}" ;;
		eva) printf '%s' "${EVA_PASS:?}" ;;
		fritz) printf '%s' "${FRITZ_PASS:?}" ;;
		*) fail "no test password for $1" ;;
	esac
}

# The Samba authentication files topology.sh samba wrote (mode 0600).
smb_auth() {
	printf '%s/auth-%s' "${WORK}" "$1"
}

sql() {
	sqlite3 "${NC_DB}" "$1"
}

# get_id KEY: the newest value of KEY in ids.env, empty when missing.
get_id() {
	sed -n "s/^$1=//p" "${IDS_ENV}" 2> /dev/null | tail -n 1
}

need_id() {
	local value
	value=$(get_id "$1")
	[ -n "${value}" ] || fail "ids.env has no $1"
	printf '%s' "${value}"
}

# search_ids USER TERM: the file ids of the hits of USER, one per line, through
# the ordinary OCS route of the unified search (as deploy-harp.yml).
search_ids() {
	curl -sfS -u "$1:$(password_of "$1")" -H 'OCS-APIRequest: true' -H 'Accept: application/json' \
		"${NC_URL:?NC_URL is required}/ocs/v2.php/search/providers/audio_video_search/search?term=$2" \
		| jq -r '.ocs.data.entries[]?.attributes.fileId | tostring'
}

# gateway_lines LOG OFFSET ID [files|head|any]: lines of the access log of
# php -S after byte OFFSET that fetched ID through the gateway (files) or the
# read proof (head).
gateway_lines() {
	local log="$1" offset="$2" id="$3" kind="${4:-any}" pattern
	case "${kind}" in
		files) pattern="GET /ocs/v2\\.php/apps/audio_video_search/files/${id}([?[:space:]]|\$)" ;;
		head) pattern="GET /ocs/v2\\.php/apps/audio_video_search/files/${id}/head([?[:space:]]|\$)" ;;
		*) pattern="GET /ocs/v2\\.php/apps/audio_video_search/files/${id}(/head)?([?[:space:]]|\$)" ;;
	esac
	[ -f "${log}" ] || {
		echo 0
		return
	}
	tail -c "+$((offset + 1))" "${log}" | grep -cE "${pattern}" || true
}
