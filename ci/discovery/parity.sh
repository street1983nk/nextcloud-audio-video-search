#!/usr/bin/env bash
# The rights parity of the search in the HTTP path (plan 03-17, SRCH-03): the
# hits of the ordinary unified search route against a truth that never runs
# code of this app.
#
# Truth per person: every file the person reaches through WebDAV (PROPFIND,
# one folder after the other, oc:fileid and oc:owner-id), every .wav fetched
# with GET as that person and compared by sha256sum with the speech clip
# (AVS_SPEECH_DE). Readable and the same bytes is an expected hit, unless the
# rules of this test exclude it: a person excluded by the test (eva and fritz
# before the first run, ben in exclude-user-after), a copy owned by such a
# person, a folder or a storage the test excluded. Those rules are the ledger
# of the test (topology.sh, truth.sh), not an answer of the app.
#
# Product per person: GET /ocs/v2.php/search/providers/audio_video_search/search
# with term=AVS_SPEECH_WORD and limit=25 as that person, following the cursor to
# the last page; the set of attributes.fileId.
#
# usage: parity.sh baseline     note the completed preview jobs before the clip lands
#        parity.sh wait         until the preview of the clip is done and ana sees a hit
#        parity.sh before       positive controls before the revocation (cem finds the
#                               shared copy, ana the copy that goes into the trash)
#        parity.sh settle       let the preview of the test media come to rest
#                               (bounded, never a verdict)
#        parity.sh --self-test  the comparison has to see an extra and a missing id
#        parity.sh check        self test, then the verdict of the phase
#
# Output: only ids, the short names of the test persons and numbers; "PHASE PASS
# search-parity" only when every check passed. occ audio_video_search:status
# serves the waiting only and never the truth.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=ci/discovery/common.sh
. "${SCRIPT_DIR}/common.sh"

export LC_ALL=C
PHASE=search-parity
WAIT_LIMIT="${WAIT_LIMIT:-900}"
WAIT_EVERY="${WAIT_EVERY:-15}"
SETTLE_LIMIT="${SETTLE_LIMIT:-600}"
MAX_FOLDERS="${MAX_FOLDERS:-400}"
MAX_PAGES="${MAX_PAGES:-40}"
PARITY_DIR="${WORK}/parity"
BASELINE="${PARITY_DIR}/baseline"
FAILED=0

# The persons who can still log in after the phases of phase 2 (dan is deleted).
PERSONS=(ana ben cem eva fritz)
# The rules of the test: who and what it excluded.
EXCLUDED_PERSONS=(eva fritz ben)
EXCLUDED_FOLDERS=(privat archiv-spaeter)
# ana's mount of the storage excluded in exclude-storage-after (M3).
EXCLUDED_MOUNTS=(ana:SMB-Teil)
# Persons who read at least one copy: without a hit for them, "no hit for
# anybody" would pass as parity.
READING_PERSONS=(ana cem)
PRELIMINARY='Vorläufig|Preliminary|Provisoire'
NO_SUCH_ID=999999999

mkdir -p "${PARITY_DIR}"

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	timeout 300 ${OCC:?OCC is required} "$@"
}

occ_status() {
	occ audio_video_search:status --json > "$1"
}

pass() {
	echo "PASS ${PHASE}:$1"
}

failed() {
	echo "FAIL ${PHASE}:$1 $2"
	FAILED=1
}

in_list() {
	local item
	for item in "${@:2}"; do
		[ "${item}" = "$1" ] && return 0
	done
	return 1
}

# ids FILE: the sorted, unique ids of a list, one per line in FILE, comma separated.
ids() {
	grep -E '^[0-9]+$' "$1" 2> /dev/null | sort -u | paste -sd, -
}

minus() {
	comm -23 <(tr ',' '\n' <<< "$1" | grep . | sort -u) <(tr ',' '\n' <<< "$2" | grep . | sort -u) | paste -sd, -
}

# -- the truth: WebDAV only -----------------------------------------------------------

PROPFIND_BODY='<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><d:resourcetype/><oc:fileid/><oc:owner-id/></d:prop></d:propfind>'

dav_base() {
	printf '/remote.php/dav/files/%s/' "$1"
}

# dav_list USER REL: kind, file id, owner and href of every entry of the folder
# REL (Depth 1), one line each, separated by | (a tab would merge an empty
# owner with its neighbour; | is percent encoded in an href). The folder
# itself is included.
dav_list() {
	curl -sS -m 60 -u "$1:$(password_of "$1")" -X PROPFIND -H 'Depth: 1' --data "${PROPFIND_BODY}" \
		"${NC_URL:?NC_URL is required}$(dav_base "$1")$2" 2> /dev/null \
		| tr -d '\r\n' | sed 's|</d:response>|&\n|g' \
		| while IFS= read -r response; do
			local href id owner kind=file
			href=$(sed -n 's|.*<d:href>\([^<]*\)</d:href>.*|\1|p' <<< "${response}")
			[ -n "${href}" ] || continue
			id=$(sed -n 's|.*<oc:fileid>\([0-9]*\)</oc:fileid>.*|\1|p' <<< "${response}")
			owner=$(sed -n 's|.*<oc:owner-id>\([^<]*\)</oc:owner-id>.*|\1|p' <<< "${response}")
			grep -q '<d:collection */>' <<< "${response}" && kind=dir
			printf '%s|%s|%s|%s\n' "${kind}" "${id}" "${owner}" "${href}"
		done
}

# excluded_place USER REL: REL lies in a folder or a mount the test excluded.
excluded_place() {
	local folder mount
	for folder in "${EXCLUDED_FOLDERS[@]}"; do
		case "/$2" in
			*/"${folder}"/*) return 0 ;;
		esac
	done
	for mount in "${EXCLUDED_MOUNTS[@]}"; do
		[ "${mount%%:*}" = "$1" ] || continue
		case "$2" in
			"${mount#*:}"/*) return 0 ;;
		esac
	done
	return 1
}

# truth_of USER: one line per .wav the person reaches: id, owner, readable
# (GET answered with bytes), same (sha256 of the clip), expected; into
# PARITY_DIR/truth-USER.tsv. The relative paths stay in that file.
truth_of() {
	local user="$1" out="${PARITY_DIR}/truth-$1.tsv" base clip queue=('') folders=0 dir kind id owner href rel
	local tmp="${PARITY_DIR}/get.bin" readable same expected
	base=$(dav_base "${user}")
	clip=$(sha256sum "${AVS_SPEECH_DE:?AVS_SPEECH_DE is required}" | cut -d ' ' -f 1)
	: > "${out}"
	while [ "${#queue[@]}" -gt 0 ]; do
		dir="${queue[0]}"
		queue=("${queue[@]:1}")
		folders=$((folders + 1))
		if [ "${folders}" -gt "${MAX_FOLDERS}" ]; then
			echo "truth ${user}: more than ${MAX_FOLDERS} folders"
			return 1
		fi
		while IFS='|' read -r kind id owner href; do
			rel=${href#"${base}"}
			[ "${rel}" = "${href}" ] && continue
			[ "${rel}" = "${dir}" ] && continue
			if [ "${kind}" = dir ]; then
				queue+=("${rel}")
				continue
			fi
			grep -qiE '\.wav$' <<< "${rel}" || continue
			[[ "${id}" =~ ^[0-9]+$ ]] || continue
			rm -f "${tmp}"
			readable=0
			same=0
			if curl -sf -m 60 -o "${tmp}" -u "${user}:$(password_of "${user}")" "${NC_URL}${href}" 2> /dev/null \
				&& [ -s "${tmp}" ]; then
				readable=1
				[ "$(sha256sum "${tmp}" | cut -d ' ' -f 1)" = "${clip}" ] && same=1
			fi
			expected=0
			if [ "${same}" = 1 ] && ! in_list "${user}" "${EXCLUDED_PERSONS[@]}" \
				&& ! in_list "${owner}" "${EXCLUDED_PERSONS[@]}" && ! excluded_place "${user}" "${rel}"; then
				expected=1
			fi
			printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${id}" "${owner}" "${readable}" "${same}" "${expected}" "${rel}" >> "${out}"
		done < <(dav_list "${user}" "${dir}")
	done
	rm -f "${tmp}"
	awk -F '\t' '$5 == 1 { print $1 }' "${out}" > "${PARITY_DIR}/expected-${user}.ids"
	echo "truth ${user}: folders=${folders} wav=$(wc -l < "${out}") lesbar=$(awk -F '\t' '$3 == 1' "${out}" | wc -l) gleich=$(awk -F '\t' '$4 == 1' "${out}" | wc -l) erwartet=$(ids "${PARITY_DIR}/expected-${user}.ids" | tr ',' '\n' | grep -c .)"
}

# -- the product: the OCS route of the unified search ---------------------------------

# product_of USER OUT: {fileId, subline} of every entry of every page, one JSON per line.
product_of() {
	local user="$1" out="$2" cursor='' page next count pages=0
	local -a more
	: > "${out}"
	while true; do
		pages=$((pages + 1))
		if [ "${pages}" -gt "${MAX_PAGES}" ]; then
			echo "search ${user}: more than ${MAX_PAGES} pages"
			return 1
		fi
		more=()
		[ -n "${cursor}" ] && more=(--data-urlencode "cursor=${cursor}")
		page=$(curl -sfS -m 60 -G -u "${user}:$(password_of "${user}")" -H 'OCS-APIRequest: true' \
			-H 'Accept: application/json' --data-urlencode "term=${AVS_SPEECH_WORD:?AVS_SPEECH_WORD is required}" \
			--data-urlencode 'limit=25' "${more[@]}" \
			"${NC_URL:?NC_URL is required}/ocs/v2.php/search/providers/audio_video_search/search") || return 1
		jq -c '.ocs.data.entries[]? | {fileId: (.attributes.fileId | tostring), subline: (.subline // "")}' \
			<<< "${page}" >> "${out}" || return 1
		count=$(jq -r '.ocs.data.entries | length' <<< "${page}")
		next=$(jq -r 'if .ocs.data.isPaginated then (.ocs.data.cursor // "" | tostring) else "" end' <<< "${page}")
		if [ "${count}" = 0 ] || [ -z "${next}" ] || [ "${next}" = "${cursor}" ]; then
			return 0
		fi
		cursor="${next}"
	done
}

found_ids() {
	jq -r '.fileId' "$1" | grep -E '^[0-9]+$' | sort -u | paste -sd, -
}

# -- the comparison -------------------------------------------------------------------

# judge PERSON EXPECTED ENTRIES: the parity line and three checks; 1 after a FAIL.
judge() {
	local person="$1" expected="$2" entries="$3" found dup bad before="${FAILED}"
	FAILED=0
	found=$(found_ids "${entries}")
	echo "parity ${person} erwartet=${expected:--} gefunden=${found:--}"
	if [ "${expected}" = "${found}" ]; then
		pass "set_${person}"
	else
		failed "set_${person}" "fehlt=$(minus "${expected}" "${found}") zuviel=$(minus "${found}" "${expected}")"
	fi
	dup=$(jq -r '.fileId' "${entries}" | sort | uniq -d | paste -sd, -)
	if [ -z "${dup}" ]; then
		pass "unique_${person}"
	else
		failed "unique_${person}" "doppelt=${dup}"
	fi
	bad=$(jq -r --arg p "${PRELIMINARY}" 'select(.subline | test($p) | not) | .fileId' "${entries}" | sort -u | paste -sd, -)
	if [ -z "${bad}" ]; then
		pass "preliminary_${person}"
	else
		failed "preliminary_${person}" "ohne=${bad}"
	fi
	local result="${FAILED}"
	[ "${before}" = 1 ] && FAILED=1
	return "${result}"
}

collect() {
	local person
	for person in "${PERSONS[@]}"; do
		truth_of "${person}" || failed "truth_${person}" "abgebrochen"
		product_of "${person}" "${PARITY_DIR}/found-${person}.jsonl" || failed "search_${person}" "abgebrochen"
	done
}

# shifted NAME CHECK PERSON EXPECTED ENTRIES: the shift has to make CHECK fail.
shifted() {
	local output
	output=$(FAILED=0 judge "$3" "$4" "$5")
	if grep -q "^FAIL ${PHASE}:$2_$3 " <<< "${output}"; then
		echo "self-test $1: ${2}_$3 failed"
		return 0
	fi
	echo "self-test $1: ${2}_$3 did not fail"
	return 1
}

# The expectation is the real answer itself, so the base passes by
# construction; each shift on its own has to fail. Without a single hit no
# missing id can be shown, and the self test fails: "no hit for anybody"
# cannot pass.
self_test() {
	local person found entries output extra="${PARITY_DIR}/self.extra.jsonl" result=0 chosen=''
	for person in "${PERSONS[@]}"; do
		if [ -n "$(found_ids "${PARITY_DIR}/found-${person}.jsonl" 2> /dev/null)" ]; then
			chosen="${person}"
			break
		fi
	done
	if [ -z "${chosen}" ]; then
		echo "self-test: nobody has a hit, a missing id cannot be shown"
		echo "PARITY SELF-TEST FAILED"
		return 1
	fi
	entries="${PARITY_DIR}/found-${chosen}.jsonl"
	found=$(found_ids "${entries}")
	# Into a variable first: grep -q in a pipe ends judge early, and pipefail
	# would read that as a failure.
	output=$(FAILED=0 judge "${chosen}" "${found}" "${entries}")
	if ! grep -q "^PASS ${PHASE}:set_${chosen}$" <<< "${output}"; then
		echo "self-test base: the answer does not equal itself"
		result=1
	fi
	shifted extra-id set "${chosen}" "$(printf '%s\n%s\n' "${found//,/$'\n'}" "${NO_SUCH_ID}" | sort -u | paste -sd, -)" "${entries}" || result=1
	shifted missing-id set "${chosen}" "$(tr ',' '\n' <<< "${found}" | tail -n +2 | paste -sd, -)" "${entries}" || result=1
	{
		cat "${entries}"
		head -n 1 "${entries}"
	} > "${extra}"
	shifted duplicate unique "${chosen}" "${found}" "${extra}" || result=1
	{
		cat "${entries}"
		jq -cn --arg id "${found%%,*}" '{fileId: $id, subline: "00:06"}'
	} > "${extra}"
	shifted subline preliminary "${chosen}" "${found}" "${extra}" || result=1
	if [ "${result}" != 0 ]; then
		echo "PARITY SELF-TEST FAILED"
		return 1
	fi
	echo "PARITY CONTROL SHOWED THE DIFF"
}

# The truth has to be able to say no: ana sees the Samba and the
# files_accesscontrol copy in her listing, and neither is readable for her.
truth_control() {
	local id row ok=true
	for id in "$(get_id ID_ANA_SMB_REDE_GESPERRT_WAV)" "$(get_id ID_ANA_REDE_SPERRE_WAV)"; do
		row=$(awk -F '\t' -v id="${id}" '$1 == id { print $3 }' "${PARITY_DIR}/truth-ana.tsv" | sort -u | paste -sd, -)
		if [ -z "${id}" ] || [ "${row}" != 0 ]; then
			ok=false
		fi
	done
	if [ "${ok}" = true ]; then
		pass truth_says_no
	else
		failed truth_says_no "erwartet=gesehen-und-nicht-lesbar"
	fi
}

cmd_check() {
	local person expected
	collect
	self_test || exit 1
	truth_control
	for person in "${PERSONS[@]}"; do
		expected=$(ids "${PARITY_DIR}/expected-${person}.ids")
		judge "${person}" "${expected}" "${PARITY_DIR}/found-${person}.jsonl" || true
	done
	for person in "${READING_PERSONS[@]}"; do
		expected=$(ids "${PARITY_DIR}/expected-${person}.ids")
		if [ -n "${expected}" ] && [ -n "$(found_ids "${PARITY_DIR}/found-${person}.jsonl")" ]; then
			pass "at_least_one_hit_${person}"
		else
			failed "at_least_one_hit_${person}" "at least one hit per reading person"
		fi
	done
	if [ "${FAILED}" = 0 ]; then
		echo "PHASE PASS search-parity"
		return 0
	fi
	echo "PHASE FAIL search-parity"
	return 1
}

cmd_self_test() {
	collect
	self_test
}

# -- waiting ------------------------------------------------------------------------

cmd_baseline() {
	local status="${PARITY_DIR}/baseline.status.json"
	occ_status "${status}" || fail "occ status failed"
	jq -r '.byPreview.complete // 0' "${status}" > "${BASELINE}"
	echo "preview jobs complete before the clip: $(cat "${BASELINE}")"
}

cmd_wait() {
	local base start status="${PARITY_DIR}/wait.status.json" hits="${PARITY_DIR}/wait.jsonl"
	base=$(cat "${BASELINE}" 2> /dev/null || echo 0)
	start=$(date +%s)
	until occ_status "${status}" 2> /dev/null && jq -e --argjson b "${base}" \
		'(.byPreview.complete // 0) > $b and (.byPreview.running // 0) == 0' "${status}" > /dev/null; do
		if [ "$(($(date +%s) - start))" -ge "${WAIT_LIMIT}" ]; then
			echo "FAIL ${PHASE}:wait_preview not done after ${WAIT_LIMIT} s $(jq -c '.byPreview' "${status}" 2> /dev/null)"
			return 1
		fi
		sleep "${WAIT_EVERY}"
	done
	echo "preview of the clip done after $(($(date +%s) - start)) s $(jq -c '.byPreview' "${status}")"
	# The index publishes after the preview: wait until ana, who reads copies, sees one.
	until product_of ana "${hits}" && [ -n "$(found_ids "${hits}")" ]; do
		if [ "$(($(date +%s) - start))" -ge "${WAIT_LIMIT}" ]; then
			echo "FAIL ${PHASE}:wait_index ana has no hit after ${WAIT_LIMIT} s"
			return 1
		fi
		sleep "${WAIT_EVERY}"
	done
	echo "first hit for ana after $(($(date +%s) - start)) s"
}

# Positive controls: what parity_revoke takes away is found before it.
cmd_before() {
	local found="${PARITY_DIR}/before.jsonl" id
	id=$(need_id ID_ANA_REDE_GETEILT_WAV)
	if product_of cem "${found}" && jq -r '.fileId' "${found}" | grep -x "${id}" > /dev/null; then
		pass before_cem_finds_the_share
	else
		failed before_cem_finds_the_share "id=${id}"
	fi
	id=$(need_id ID_ANA_REDE_PAPIERKORB_WAV)
	if product_of ana "${found}" && jq -r '.fileId' "${found}" | grep -x "${id}" > /dev/null; then
		pass before_ana_finds_the_trash_copy
	else
		failed before_ana_finds_the_trash_copy "id=${id}"
	fi
	return "${FAILED}"
}

# Once the models lie in the volume, the preview fetches every test medium
# through the gateway. A preview download in the window of a later phase would
# be a gateway line that phase did not cause, so the phases start only after
# the preview came to rest: nothing running and the counts unchanged over
# three looks. Bounded, and never a verdict.
cmd_settle() {
	local start status="${PARITY_DIR}/settle.status.json" last='' now same=0
	start=$(date +%s)
	while [ "$(($(date +%s) - start))" -lt "${SETTLE_LIMIT}" ]; do
		if occ_status "${status}" 2> /dev/null; then
			now=$(jq -c '.byPreview // {}' "${status}")
			if [ "${now}" = "${last}" ] && [ "$(jq -r '.byPreview.running // 0' "${status}")" = 0 ]; then
				same=$((same + 1))
			else
				same=0
			fi
			last="${now}"
			if [ "${same}" -ge 2 ]; then
				echo "preview at rest after $(($(date +%s) - start)) s ${now}"
				return 0
			fi
		fi
		sleep "${WAIT_EVERY}"
	done
	echo "::warning::preview not at rest after ${SETTLE_LIMIT} s ${last}"
	return 0
}

case "${1:-}" in
	baseline) cmd_baseline ;;
	wait) cmd_wait ;;
	before) cmd_before ;;
	settle) cmd_settle ;;
	--self-test) cmd_self_test ;;
	check) cmd_check ;;
	*) fail "usage: parity.sh baseline|wait|before|settle|--self-test|check" ;;
esac
