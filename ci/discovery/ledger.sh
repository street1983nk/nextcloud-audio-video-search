#!/usr/bin/env bash
# The ledger of the test results the acceptance test seeds itself (D-02-07).
#
# status.transcribed of the app has to equal a number the test knows without
# asking the app: every test result is seeded through this script, which notes
# the sha256 of the sampled content as the truth (truth.sh) or the Samba server
# gives it. The expected number of transcribed contents is the number of
# distinct sampled sha256 that still lie behind an active, readable file of the
# current truth.
#
# usage: ledger.sh add <fileId> <sha256>
#        ledger.sh sample <fileId> <user> <truth.json|sha256>
#                                     occ audio_video_search:sample as <user>, then add
#        ledger.sh drop-where-gone <truth.json>
#                                     forget the sampled contents the truth no longer
#                                     holds (after an exclusion, D-02-04: the
#                                     transcript is gone and does not come back)
#        ledger.sh expected <truth.json>
#
# A deleted user or a trashed file only orphans its content (D-02-09, D-02-13):
# the ledger keeps it, so a copy that turns up again counts once more.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=ci/discovery/common.sh
. "${SCRIPT_DIR}/common.sh"

touch "${LEDGER}"

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	timeout 300 ${OCC:?OCC is required} "$@"
}

is_sha() {
	[[ "$1" =~ ^[0-9a-f]{64}$ ]]
}

cmd_add() {
	[[ "${1:-}" =~ ^[0-9]+$ ]] || fail "ledger add takes a numeric file id"
	is_sha "${2:-}" || fail "ledger add takes a sha256"
	printf '%s\t%s\n' "$1" "$2" >> "${LEDGER}"
	echo "ledger: test result on file ${1}"
}

cmd_sample() {
	local id="${1:-}" user="${2:-}" source="${3:-}" sha
	[[ "${id}" =~ ^[0-9]+$ ]] || fail "ledger sample takes a numeric file id"
	[ -n "${user}" ] || fail "ledger sample takes a user"
	if is_sha "${source}"; then
		sha="${source}"
	else
		[ -f "${source}" ] || fail "ledger sample takes a truth file or a sha256"
		sha=$(jq -r --arg id "${id}" '.sha[$id] // empty' "${source}")
		is_sha "${sha}" || fail "the truth has no readable content for file ${id}"
	fi
	occ audio_video_search:sample "${id}" --user="${user}"
	cmd_add "${id}" "${sha}"
}

cmd_drop_where_gone() {
	local truth="${1:-}" kept="${LEDGER}.kept"
	[ -f "${truth}" ] || fail "ledger drop-where-gone takes a truth file"
	: > "${kept}"
	local id sha
	while IFS=$'\t' read -r id sha; do
		[ -n "${sha}" ] || continue
		if jq -e --arg sha "${sha}" '[.sha[]] | index($sha) != null' "${truth}" > /dev/null; then
			printf '%s\t%s\n' "${id}" "${sha}" >> "${kept}"
		else
			echo "ledger: the content sampled on file ${id} is gone"
		fi
	done < "${LEDGER}"
	mv "${kept}" "${LEDGER}"
}

cmd_expected() {
	local truth="${1:-}"
	[ -f "${truth}" ] || fail "ledger expected takes a truth file"
	cut -f 2 "${LEDGER}" | sort -u | jq -Rn --slurpfile truth "${truth}" '
		[inputs | select(length > 0)] as $sampled
		| ([$truth[0].sha[]] | unique) as $present
		| [$sampled[] | select(. as $s | $present | index($s) != null)] | length'
}

case "${1:-}" in
	add) cmd_add "${2:-}" "${3:-}" ;;
	sample) cmd_sample "${2:-}" "${3:-}" "${4:-}" ;;
	drop-where-gone) cmd_drop_where_gone "${2:-}" ;;
	expected) cmd_expected "${2:-}" ;;
	*) fail "usage: ledger.sh add|sample|drop-where-gone|expected" ;;
esac
