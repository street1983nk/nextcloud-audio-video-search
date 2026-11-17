#!/usr/bin/env bash
# The leak probe P12 on the real play page (plan 03-18b, D-03-24): a reference
# that is not active for the person who opens the page shows the excerpt block
# of a file without a transcript (A5), byte for byte, and nothing of the
# transcript, the reason or the stage (03-UI-SPEC, area 2 and the test contract
# P12 "excerpt block equal to P4"; D-02-15c, D-02-16, D-03-13).
#
# Two cases:
#   p12a never active: ana opens SMB/rede-gesperrt.wav (Samba denies her the
#        bytes, set before Nextcloud saw the file, so the read proof never
#        succeeded). The same clip is readable for her in rede-geteilt.wav, an
#        active reference: the positive control at the same time mark.
#   p12b revoked: cem opens SMB/widerruf.webm. Before revoke_cem his reference
#        is active (positive control), after revoke_cem and reconcile --reprove
#        it is unreadable (probe). It runs in the phase reprove, before vanish
#        takes his SMB mount away.
# The reference for A5 is ana's privat/p.webm (the folder privat is excluded
# before the first run, so the page shows A5 without asking the container).
#
# Two independent patterns judge every probe:
#   1. same_bytes: the bytes of the block against the bytes of the reference;
#   2. is_a5: the structure against the literal texts of the UI-SPEC table
#      (label, A5 hint, no blockquote, no note, no clip word, no T5).
# The state of the reference comes from two sources: occ
# audio_video_search:files and a copy of state.db read with sqlite3 of the
# runner. A probe on a page that is not ready, on a reference that is active,
# unknown or reported differently by the two sources, or with a control that
# shows no difference, is INVALID, and INVALID never passes.
#
# usage: playpage.sh --self-test     offline, no instance, no network
#        playpage.sh before-revoke   phase reprove, before the operation
#        playpage.sh after-revoke    phase reprove, after compare.sh
#        playpage.sh check           phase play-leak: self test, then the verdict
#
# Output: only ids, the short names of the test persons and codes. "PHASE PASS
# play-leak" only when the self test, both control lines and both probes passed.
# This script reads only: no occ command that changes anything, state.db only as
# a copy.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SELF_TEST_DIR=''
if [ "${1:-}" = --self-test ]; then
	# The self test keeps every file in a folder of its own, WORK included.
	SELF_TEST_DIR=$(mktemp -d)
	trap 'rm -rf "${SELF_TEST_DIR}"' EXIT
	export RUNNER_TEMP="${SELF_TEST_DIR}"
	export IDS_ENV="${SELF_TEST_DIR}/ids.env"
fi
# shellcheck source=ci/discovery/common.sh
. "${SCRIPT_DIR}/common.sh"

export LC_ALL=C
PHASE=play-leak
MAX_PAGES="${MAX_PAGES:-40}"
PLAY_DIR="${WORK}/play"
P12B_STATE="${WORK}/play-p12b.state"
FAILED=0

# UI-SPEC table, not the catalogues (the probes ask with Accept-Language: en).
LABEL_TEXT='Excerpt at this point'
A5_TEXT='There is no transcript for this file yet.'
T5_TEXT='No speech was found in this file, for example because it only contains music, silence or noise.'

mkdir -p "${PLAY_DIR}"

# -- the two patterns (no network) ----------------------------------------------------

# block PAGE: the bytes from the line with the opening section of the excerpt
# to the first closing section; nothing when the page has no block.
block() {
	[ -f "$1" ] || return 0
	awk '/<section class="avs-excerpt"/ { on = 1 } on { print } on && /<\/section>/ { exit }' "$1"
}

# ready PAGE: the page is in the state ready, it has the medium and the block.
ready() {
	[ -f "$1" ] && grep -q 'id="avs-media"' "$1" && [ -n "$(block "$1")" ]
}

# same_bytes A B: pattern 1, the blocks of two pages are the same bytes.
same_bytes() {
	[ -n "$(block "$1")" ] && cmp -s <(block "$1") <(block "$2")
}

# text_of BLOCK CLASS: the text of the elements with CLASS, one per line.
text_of() {
	sed -n "s/.*class=\"$2\"[^>]*>\\([^<]*\\)<.*/\\1/p" <<< "$1"
}

# is_a5 PAGE: pattern 2, independent of the bytes: exactly one label with the
# label text, exactly one hint with the A5 text, no excerpt, no note, neither
# the clip word nor T5.
is_a5() {
	local b word="${AVS_SPEECH_WORD:-}"
	b=$(block "$1")
	[ -n "${b}" ] || return 1
	[ "$(grep -c 'class="avs-excerpt__label"' <<< "${b}")" = 1 ] || return 1
	[ "$(text_of "${b}" avs-excerpt__label)" = "${LABEL_TEXT}" ] || return 1
	[ "$(grep -c 'class="avs-excerpt__hint"' <<< "${b}")" = 1 ] || return 1
	[ "$(text_of "${b}" avs-excerpt__hint)" = "${A5_TEXT}" ] || return 1
	grep -q 'avs-excerpt__text' <<< "${b}" && return 1
	grep -q 'avs-excerpt__note' <<< "${b}" && return 1
	[ -n "${word}" ] && grep -qiF -- "${word}" <<< "${b}" && return 1
	grep -qF -- "${T5_TEXT}" <<< "${b}" && return 1
	return 0
}

# states_say OCC DB: "ok" when both sources name the same state and it is not
# active, else the reason of the INVALID. Empty or "-" is a source without a
# row: an unknown file, not the case P12.
states_say() {
	if [ -z "$1" ] || [ -z "$2" ] || [ "$1" = - ] || [ "$2" = - ]; then
		echo "ref_unknown occ=${1:--} db=${2:--}"
	elif [ "$1" != "$2" ]; then
		echo "sources_differ occ=$1 db=$2"
	elif [ "$1" = active ]; then
		echo "ref_active"
	else
		echo ok
	fi
}

# judge_probe REF PROBE OCC DB: "PASS|FAIL|INVALID grund=..." for one probe.
judge_probe() {
	local ref="$1" probe="$2" said reasons=''
	if ! ready "${ref}" || ! is_a5 "${ref}"; then
		echo "INVALID grund=reference_not_a5"
		return
	fi
	if ! ready "${probe}"; then
		echo "INVALID grund=probe_not_ready"
		return
	fi
	said=$(states_say "$3" "$4")
	if [ "${said}" != ok ]; then
		echo "INVALID grund=${said// /,}"
		return
	fi
	same_bytes "${ref}" "${probe}" || reasons="${reasons},bytes_differ"
	is_a5 "${probe}" || reasons="${reasons},not_a5"
	if [ -n "${reasons}" ]; then
		echo "FAIL grund=${reasons#,}"
	else
		echo "PASS grund=a5_byte_equal"
	fi
}

# judge_control REF CONTROL OCC DB [WORD]: "SHOWED" when the control of the
# same person differs from the reference in both patterns, else INVALID.
judge_control() {
	local ref="$1" control="$2" word="${5:-}" quote
	if ! ready "${control}"; then
		echo "INVALID grund=control_not_ready"
		return
	fi
	if [ -z "$3" ] || [ "$3" != "$4" ] || [ "$3" != active ]; then
		echo "INVALID grund=control_not_active,occ=${3:--},db=${4:--}"
		return
	fi
	if same_bytes "${ref}" "${control}" || is_a5 "${control}"; then
		echo "INVALID grund=control_equals_reference"
		return
	fi
	if [ -n "${word}" ]; then
		quote=$(text_of "$(block "${control}")" avs-excerpt__text)
		if ! grep -qiF -- "${word}" <<< "${quote}"; then
			echo "INVALID grund=control_without_the_clip_word"
			return
		fi
	fi
	echo "SHOWED grund=control_differs"
}

# -- the self test (offline) ---------------------------------------------------------

# synthetic OUT MEDIUM INNER: a page in the markup of play.php; MEDIUM 0 leaves
# the medium out, INNER replaces the lines between label and closing section;
# INNER "none" gives a page without the block.
synthetic() {
	local out="$1" medium="$2" inner="$3"
	{
		printf '<!DOCTYPE html>\n<html lang="en">\n<body>\n<div id="app-content" class="avs-play">\n'
		[ "${medium}" = 1 ] && printf '\t\t<audio id="avs-media" class="avs-media avs-media--audio" controls preload="metadata" playsinline src="/x" data-start="0"></audio>\n'
		if [ "${inner}" != none ]; then
			printf '\t\t<section class="avs-excerpt" aria-labelledby="avs-excerpt-label">\n'
			printf '\t\t\t<p id="avs-excerpt-label" class="avs-excerpt__label">%s</p>\n' "${LABEL_TEXT}"
			printf '%s\n' "${inner}"
			printf '\t\t</section>\n'
		fi
		printf '</div>\n</body>\n</html>\n'
	} > "${out}"
}

# expect NAME EXPECTED SEEN: one line per case; 1 when they differ.
expect() {
	echo "self-test $1: erwartet=$2 gesehen=$3"
	[ "$2" = "$3" ]
}

yes_no() {
	if "$@"; then echo yes; else echo no; fi
}

self_test() {
	local d="${PLAY_DIR}/self" result=0 hint quote
	mkdir -p "${d}"
	AVS_SPEECH_WORD=haushalt
	hint=$(printf '\t\t\t\t<p class="avs-excerpt__hint">%s</p>' "${A5_TEXT}")
	quote=$(printf '\t\t\t\t<blockquote class="avs-excerpt__text">der haushalt der stadt</blockquote>')
	synthetic "${d}/ref.html" 1 "${hint}"
	synthetic "${d}/same.html" 1 "${hint}"
	synthetic "${d}/quote.html" 1 "${quote}"
	synthetic "${d}/t5.html" 1 "$(printf '\t\t\t\t<p class="avs-excerpt__hint">%s</p>' "${T5_TEXT}")"
	synthetic "${d}/space.html" 1 "${hint} "
	synthetic "${d}/text.html" 1 "$(printf '\t\t\t\t<p class="avs-excerpt__hint">%s</p>' 'There is no transcript for this file.')"
	synthetic "${d}/404.html" 0 none
	local v
	# 1. the probe equals the reference
	v=$(judge_probe "${d}/ref.html" "${d}/same.html" unreadable unreadable)
	expect equal PASS "${v%% *}" || result=1
	# 2. the probe carries an excerpt
	v=$(judge_probe "${d}/ref.html" "${d}/quote.html" unreadable unreadable)
	expect blockquote "FAIL bytes=no a5=no" "${v%% *} bytes=$(yes_no same_bytes "${d}/ref.html" "${d}/quote.html") a5=$(yes_no is_a5 "${d}/quote.html")" || result=1
	# 3. the probe says T5 instead of A5
	v=$(judge_probe "${d}/ref.html" "${d}/t5.html" unreadable unreadable)
	expect t5 "FAIL bytes=no a5=no" "${v%% *} bytes=$(yes_no same_bytes "${d}/ref.html" "${d}/t5.html") a5=$(yes_no is_a5 "${d}/t5.html")" || result=1
	# 4. one more space: the bytes see it, the structure alone does not
	v=$(judge_probe "${d}/ref.html" "${d}/space.html" unreadable unreadable)
	expect space "FAIL bytes=no a5=yes" "${v%% *} bytes=$(yes_no same_bytes "${d}/ref.html" "${d}/space.html") a5=$(yes_no is_a5 "${d}/space.html")" || result=1
	# 5. another A5 text in the same structure: both patterns see it
	v=$(judge_probe "${d}/ref.html" "${d}/text.html" unreadable unreadable)
	expect a5-text "FAIL bytes=no a5=no" "${v%% *} bytes=$(yes_no same_bytes "${d}/ref.html" "${d}/text.html") a5=$(yes_no is_a5 "${d}/text.html")" || result=1
	# 6. a page without the block (404)
	v=$(judge_probe "${d}/ref.html" "${d}/404.html" unreadable unreadable)
	expect no-block INVALID "${v%% *}" || result=1
	# 7. the control equals the reference
	v=$(judge_control "${d}/ref.html" "${d}/same.html" active active)
	expect control-equal INVALID "${v%% *}" || result=1
	# 8. the reference is active
	v=$(judge_probe "${d}/ref.html" "${d}/same.html" active active)
	expect ref-active INVALID "${v%% *}" || result=1
	# 9. the two sources of the state disagree
	v=$(judge_probe "${d}/ref.html" "${d}/same.html" unreadable vanished)
	expect sources-differ INVALID "${v%% *}" || result=1
	# A source without a row is the case "unknown", not P12.
	v=$(judge_probe "${d}/ref.html" "${d}/same.html" - -)
	expect ref-unknown INVALID "${v%% *}" || result=1
	# The control that differs has to be seen as such, or no control could pass.
	v=$(judge_control "${d}/ref.html" "${d}/quote.html" active active haushalt)
	expect control-differs SHOWED "${v%% *}" || result=1
	if [ "${result}" != 0 ]; then
		echo "PLAY SELF-TEST FAILED"
		return 1
	fi
	echo "PLAY SELF-TEST PASSED"
}

# -- the instance (network) ----------------------------------------------------------

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	timeout 300 ${OCC:?OCC is required} "$@"
}

# occ_files OUT: every reference of the work stock as one JSON array (as compare.sh).
occ_files() {
	occ audio_video_search:files --json --all > "$1.raw" || return 1
	jq '(if type == "object" then .files else . end) // [] | if type == "array" then . else [] end' "$1.raw" > "$1"
}

# state_db SQL: the query against a copy of state.db of the container (as compare.sh).
state_db() {
	local dir="${WORK}/statedb-play" db suffix
	: "${EXAPP_CONTAINER:?EXAPP_CONTAINER is required}"
	rm -rf "${dir}"
	mkdir -p "${dir}"
	db=$(docker exec "${EXAPP_CONTAINER}" sh -c 'printf %s "${APP_PERSISTENT_STORAGE}/state.db"')
	for suffix in '' -wal -shm; do
		docker cp "${EXAPP_CONTAINER}:${db}${suffix}" "${dir}/state.db${suffix}" > /dev/null 2>&1 || true
	done
	sqlite3 "${dir}/state.db" "$1"
}

# ref_state FILEID: "OCC DB", the state of the reference out of both sources;
# "-" for a source without a row. The container keeps one reference per file id.
ref_state() {
	local id="$1" files="${PLAY_DIR}/files-$1.json" occ_state db_state
	[[ "${id}" =~ ^[0-9]+$ ]] || {
		echo "- -"
		return
	}
	occ_state=''
	occ_files "${files}" && occ_state=$(jq -r --arg id "${id}" \
		'[.[] | select((.fileId | tostring) == $id)][0].state // "" | tostring' "${files}")
	db_state=$(state_db "SELECT state FROM file_ref WHERE file_id = ${id}" 2> /dev/null | head -n 1)
	echo "${occ_state:--} ${db_state:--}"
}

# page USER FILEID SECONDS OUT: the play page as USER; basic auth first, a
# session when that does not give a page.
page() {
	local user="$1" id="$2" t="$3" out="$4" url http jar token
	url="${NC_URL:?NC_URL is required}/index.php/apps/audio_video_search/play/${id}?t=${t}"
	http=$(curl -sS -m 60 -u "${user}:$(password_of "${user}")" -H 'Accept-Language: en' \
		-o "${out}" -w '%{http_code}' "${url}" 2> /dev/null)
	if [ "${http}" = 200 ] && grep -qi '<html' "${out}"; then
		echo "page ${user} ${id} t=${t} http=${http} via=basic"
		return 0
	fi
	echo "NOTE basic auth refused (http=${http:-none}), signing in with a session"
	jar="${WORK}/play-cookies-${user}"
	rm -f "${jar}"
	token=$(curl -sS -m 60 -c "${jar}" -b "${jar}" -H 'Accept-Language: en' "${NC_URL}/index.php/login" 2> /dev/null \
		| sed -n 's/.*data-requesttoken="\([^"]*\)".*/\1/p' | head -n 1)
	curl -sS -m 60 -c "${jar}" -b "${jar}" -o /dev/null -H 'Accept-Language: en' \
		--data-urlencode "user=${user}" --data-urlencode "password=$(password_of "${user}")" \
		--data-urlencode 'timezone=UTC' --data-urlencode 'timezone_offset=0' \
		--data-urlencode "requesttoken=${token}" "${NC_URL}/index.php/login" 2> /dev/null
	http=$(curl -sS -m 60 -c "${jar}" -b "${jar}" -H 'Accept-Language: en' \
		-o "${out}" -w '%{http_code}' "${url}" 2> /dev/null)
	echo "page ${user} ${id} t=${t} http=${http:-none} via=session"
}

# hit_seconds USER FILEID: the time mark of the first hit of FILEID in the
# search for the clip word (the form of parity.sh product_of); 1 without a hit.
hit_seconds() {
	local user="$1" id="$2" cursor='' result pages=0 t count next
	local -a more
	while [ "${pages}" -lt "${MAX_PAGES}" ]; do
		pages=$((pages + 1))
		more=()
		[ -n "${cursor}" ] && more=(--data-urlencode "cursor=${cursor}")
		result=$(curl -sfS -m 60 -G -u "${user}:$(password_of "${user}")" -H 'OCS-APIRequest: true' \
			-H 'Accept: application/json' --data-urlencode "term=${AVS_SPEECH_WORD:?AVS_SPEECH_WORD is required}" \
			--data-urlencode 'limit=25' "${more[@]}" \
			"${NC_URL:?NC_URL is required}/ocs/v2.php/search/providers/audio_video_search/search") || return 1
		t=$(jq -r --arg id "${id}" \
			'[.ocs.data.entries[]? | select((.attributes.fileId | tostring) == $id) | .resourceUrl][0] // ""' \
			<<< "${result}" | sed -nE 's/.*[?&]t=([0-9]+(\.[0-9]+)?).*/\1/p')
		if [ -n "${t}" ]; then
			printf '%s' "${t}"
			return 0
		fi
		count=$(jq -r '.ocs.data.entries | length' <<< "${result}")
		next=$(jq -r 'if .ocs.data.isPaginated then (.ocs.data.cursor // "" | tostring) else "" end' <<< "${result}")
		if [ "${count}" = 0 ] || [ -z "${next}" ] || [ "${next}" = "${cursor}" ]; then
			return 1
		fi
		cursor="${next}"
	done
	return 1
}

# keep NAME: the saved page as a copy in the working folder (Collect the logs).
keep() {
	cp "${WORK}/$1" "./$1" 2> /dev/null || true
}

# -- the phase reprove ---------------------------------------------------------------

cmd_before_revoke() {
	local ref control id states
	ref=$(need_id ID_ANA_PRIVAT_P_WEBM)
	id=$(need_id ID_CEM_SMB_WIDERRUF_WEBM)
	page ana "${ref}" 0 "${WORK}/play-p12b-reference.html"
	page cem "${id}" 0 "${WORK}/play-p12b-control.html"
	states=$(ref_state "${id}")
	keep play-p12b-reference.html
	keep play-p12b-control.html
	{
		echo "control_occ=${states%% *}"
		echo "control_db=${states##* }"
	} > "${P12B_STATE}"
	echo "p12b before-revoke reference=${ref} control=${id} state=${states// /,}"
	echo "p12b control $(judge_control "${WORK}/play-p12b-reference.html" "${WORK}/play-p12b-control.html" \
		"${states%% *}" "${states##* }")"
}

cmd_after_revoke() {
	local id states
	id=$(need_id ID_CEM_SMB_WIDERRUF_WEBM)
	page cem "${id}" 0 "${WORK}/play-p12b-probe.html"
	states=$(ref_state "${id}")
	keep play-p12b-probe.html
	{
		echo "probe_occ=${states%% *}"
		echo "probe_db=${states##* }"
	} >> "${P12B_STATE}"
	echo "p12b after-revoke probe=${id} state=${states// /,}"
	echo "p12b probe $(judge_probe "${WORK}/play-p12b-reference.html" "${WORK}/play-p12b-probe.html" \
		"${states%% *}" "${states##* }")"
}

# -- the phase play-leak -------------------------------------------------------------

saved() {
	sed -n "s/^$1=//p" "${P12B_STATE}" 2> /dev/null | tail -n 1
}

# result NAME VERDICT-LINE: the line of a probe; FAILED for anything but PASS.
result() {
	echo "P12 $1 $2"
	[ "${2%% *}" = PASS ] || FAILED=1
}

control_line() {
	if [ "${2%% *}" = SHOWED ]; then
		echo "PLAY CONTROL SHOWED THE DIFF $1"
	else
		echo "P12 $1-control $2"
		FAILED=1
	fi
}

cmd_check() {
	local tested ref p12a shared t states found
	tested=$(bash "${SCRIPT_DIR}/playpage.sh" --self-test)
	echo "${tested}"
	if ! grep -qx 'PLAY SELF-TEST PASSED' <<< "${tested}"; then
		echo "PLAY SELF-TEST FAILED"
		echo "PHASE FAIL ${PHASE}"
		return 1
	fi

	# p12a: never active.
	ref=$(need_id ID_ANA_PRIVAT_P_WEBM)
	p12a=$(need_id ID_ANA_SMB_REDE_GESPERRT_WAV)
	shared=$(need_id ID_ANA_REDE_GETEILT_WAV)
	page ana "${ref}" 0 "${WORK}/play-p12a-reference.html"
	keep play-p12a-reference.html
	if [ ! -f "${WORK}/play-p12b-reference.html" ]; then
		result p12a-reference "INVALID grund=no_reference_of_the_phase_reprove"
	elif same_bytes "${WORK}/play-p12b-reference.html" "${WORK}/play-p12a-reference.html"; then
		echo "PASS ${PHASE}:reference_stable"
	else
		result p12a-reference "FAIL grund=reference_changed_since_reprove"
	fi
	if t=$(hit_seconds ana "${shared}"); then
		echo "p12a time mark of the shared copy t=${t}"
		page ana "${shared}" "${t}" "${WORK}/play-p12a-control.html"
		keep play-p12a-control.html
		states=$(ref_state "${shared}")
		control_line p12a "$(judge_control "${WORK}/play-p12a-reference.html" "${WORK}/play-p12a-control.html" \
			"${states%% *}" "${states##* }" "${AVS_SPEECH_WORD:?AVS_SPEECH_WORD is required}")"
		page ana "${p12a}" "${t}" "${WORK}/play-p12a-probe.html"
		keep play-p12a-probe.html
		states=$(ref_state "${p12a}")
		echo "p12a probe=${p12a} state=${states// /,}"
		found=$(search_ids ana "${AVS_SPEECH_WORD}" | grep -x "${p12a}" || true)
		if [ -n "${found}" ]; then
			result p12a "FAIL grund=probe_is_a_hit_of_the_search"
		else
			result p12a "$(judge_probe "${WORK}/play-p12a-reference.html" "${WORK}/play-p12a-probe.html" \
				"${states%% *}" "${states##* }")"
		fi
	else
		control_line p12a "INVALID grund=no_hit_of_the_shared_copy"
		result p12a "INVALID grund=no_time_mark"
	fi

	# p12b: revoked, out of the files of the phase reprove.
	if [ ! -f "${P12B_STATE}" ] || [ ! -f "${WORK}/play-p12b-probe.html" ]; then
		control_line p12b "INVALID grund=phase_reprove_left_no_pages"
		result p12b "INVALID grund=phase_reprove_left_no_pages"
	else
		control_line p12b "$(judge_control "${WORK}/play-p12b-reference.html" "${WORK}/play-p12b-control.html" \
			"$(saved control_occ)" "$(saved control_db)")"
		result p12b "$(judge_probe "${WORK}/play-p12b-reference.html" "${WORK}/play-p12b-probe.html" \
			"$(saved probe_occ)" "$(saved probe_db)")"
	fi

	if [ "${FAILED}" = 0 ]; then
		echo "PHASE PASS ${PHASE}"
		return 0
	fi
	echo "PHASE FAIL ${PHASE}"
	return 1
}

case "${1:-}" in
	--self-test) self_test ;;
	before-revoke) cmd_before_revoke ;;
	after-revoke) cmd_after_revoke ;;
	check) cmd_check ;;
	*) fail "usage: playpage.sh --self-test|before-revoke|after-revoke|check" ;;
esac
