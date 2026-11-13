#!/usr/bin/env bash
# The verdict of the discovery acceptance test (D-02-07): the work stock and
# the numbers of the app against the independent truth of truth.sh, the ledger
# of ledger.sh and the access log of php -S.
#
# usage: compare.sh wait               until crawl, queue and due work are empty
#        compare.sh --self-test        the checks have to be able to fail
#        compare.sh prepare <phase>    test results and controls before the operation
#        compare.sh mark <phase>       snapshot before the operation (log offset,
#                                      work stock, status)
#        compare.sh appear <fileId> <since> <limit>
#                                      wait until the file is in the work stock,
#                                      note the seconds since <since>
#        compare.sh <phase>            compare after the operation
#
# Every check prints "PASS <phase>:<check>" or "FAIL <phase>:<check>
# erwartet=<..> gefunden=<..>", only ids and numbers; "PHASE PASS <phase>"
# only when every check of the phase passed. The exit code is not 0 after a
# FAIL. App data come only out of the occ commands under test
# (audio_video_search:files --json --all, :status --json) and, for the
# statements about state.db, out of a copy of state.db read with sqlite3 of the
# runner.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=ci/discovery/common.sh
. "${SCRIPT_DIR}/common.sh"

WAIT_LIMIT="${WAIT_LIMIT:-900}"
WAIT_EVERY="${WAIT_EVERY:-15}"
# Every reason a read can fail with: Samba may deny, let the download hang, or
# answer with 422 or 500 (Findling A6). The security statements stay strict.
READ_REASONS='read_denied not_found read_timeout gateway_failed size_mismatch storage_paused'
FAILED=0

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	timeout 300 ${OCC:?OCC is required} "$@"
}

# occ_files OUT: every reference of the work stock as one JSON array.
occ_files() {
	occ audio_video_search:files --json --all > "$1.raw" || return 1
	jq '(if type == "object" then .files else . end) // [] | if type == "array" then . else [] end' "$1.raw" > "$1"
}

occ_status() {
	occ audio_video_search:status --json > "$1"
}

check() {
	if [ "$2" = "$3" ]; then
		echo "PASS ${PHASE}:$1"
	else
		echo "FAIL ${PHASE}:$1 erwartet=$2 gefunden=$3${4:+ $4}"
		FAILED=1
	fi
}

# check_true NAME CONDITION-TEXT: a statement without numbers.
check_true() {
	if [ "$2" = true ]; then
		echo "PASS ${PHASE}:$1"
	else
		echo "FAIL ${PHASE}:$1 erwartet=true gefunden=$2${3:+ $3}"
		FAILED=1
	fi
}

# set_check NAME EXPECTED FOUND: two comma lists of ids.
set_check() {
	local missing extra
	if [ "$2" = "$3" ]; then
		echo "PASS ${PHASE}:$1"
		return
	fi
	missing=$(comm -23 <(tr ',' '\n' <<< "$2" | sort) <(tr ',' '\n' <<< "$3" | sort) | paste -sd, -)
	extra=$(comm -13 <(tr ',' '\n' <<< "$2" | sort) <(tr ',' '\n' <<< "$3" | sort) | paste -sd, -)
	echo "FAIL ${PHASE}:$1 erwartet=$(tr ',' '\n' <<< "$2" | grep -c .) gefunden=$(tr ',' '\n' <<< "$3" | grep -c .) fehlt=${missing:-} zuviel=${extra:-}"
	FAILED=1
}

ids_of_state() {
	jq -r --arg state "$2" '[.[] | select(.state == $state) | .fileId] | map(tostring) | sort | join(",")' "$1"
}

field_of() {
	jq -r --arg id "$2" --arg field "$3" '[.[] | select((.fileId | tostring) == $id)][0][$field] // "" | tostring' "$1"
}

state_of() {
	field_of "$1" "$2" state
}

media_of() {
	field_of "$1" "$2" mediaId
}

in_list() {
	tr ',' '\n' <<< "$2" | grep -qx "$1"
}

# state_db SQL: the query against a copy of state.db of the container.
state_db() {
	local dir="${WORK}/statedb" db suffix
	: "${EXAPP_CONTAINER:?EXAPP_CONTAINER is required}"
	rm -rf "${dir}"
	mkdir -p "${dir}"
	db=$(docker exec "${EXAPP_CONTAINER}" sh -c 'printf %s "${APP_PERSISTENT_STORAGE}/state.db"')
	for suffix in '' -wal -shm; do
		docker cp "${EXAPP_CONTAINER}:${db}${suffix}" "${dir}/state.db${suffix}" > /dev/null 2>&1 || true
	done
	sqlite3 "${dir}/state.db" "$1"
}

log_offset() {
	if [ -f "${ACCESS_LOG}" ]; then
		stat -c %s "${ACCESS_LOG}"
	else
		echo 0
	fi
}

# -- core checks of every phase -------------------------------------------------------

# core_checks TRUTH FILES STATUS EXPECTED_TRANSCRIBED LOG
core_checks() {
	local truth="$1" files="$2" status="$3" expected="$4" log="$5" id never found count
	check unmapped 0 "$(jq -r '.unmapped' "${truth}")"
	set_check active_set "$(jq -r '(.files - .unreadable) | map(tostring) | sort | join(",")' "${truth}")" \
		"$(ids_of_state "${files}" active)"
	set_check unreadable_set "$(jq -r '.unreadable | map(tostring) | sort | join(",")' "${truth}")" \
		"$(ids_of_state "${files}" unreadable)"
	check files_count "$(jq -r '.N_active' "${truth}")" "$(jq -r '.files' "${status}")"
	check unreadable_count "$(jq -r '.unreadable | length' "${truth}")" "$(jq -r '.byState.unreadable // 0' "${status}")"
	check contents "$(jq -r '.Y' "${truth}")" "$(jq -r '.contents' "${status}")"
	check transcribed "${expected}" "$(jq -r '.transcribed' "${status}")"
	never=$(jq -r '.neverFetched | map(tostring) | join(",")' "${truth}")
	found=$(jq -r --arg never "${never}" '($never | split(",")) as $n | [.[] | (.fileId | tostring) | select(. as $i | $n | index($i) != null)] | join(",")' "${files}")
	check never_in_stock '' "${found}"
	found=''
	for id in $(tr ',' ' ' <<< "${never}"); do
		count=$(gateway_lines "${log}" 0 "${id}" any)
		[ "${count}" = 0 ] || found="${found:+${found},}${id}"
	done
	check never_in_log '' "${found}"
	# Ids of the session mount that a mount with stored credentials reaches
	# too are fetched, but only as a user of such a mount (truth.sh).
	local readers user
	found=''
	while IFS=$'\t' read -r id readers; do
		[ -n "${id}" ] || continue
		for user in $(gateway_users "${log}" "${id}"); do
			in_list "${user}" "${readers}" || found="${found:+${found},}${id}:${user}"
		done
	done < <(jq -r '(.sessionShared // {}) | to_entries[] | "\(.key)\t\(.value | join(","))"' "${truth}")
	check session_shared_readers '' "${found}"
}

unreadable_reasons() {
	local truth="$1" files="$2" sperre id reason
	sperre=$(get_id ID_ANA_SPERRE_WEBM)
	for id in $(jq -r '.unreadable[]' "${truth}"); do
		[ "$(state_of "${files}" "${id}")" = unreadable ] || continue
		reason=$(field_of "${files}" "${id}" reason)
		if [ "${id}" = "${sperre}" ]; then
			check "reason_${id}" access_control "${reason}"
		elif in_list "${reason}" "$(tr ' ' ',' <<< "${READ_REASONS}")"; then
			echo "PASS ${PHASE}:reason_${id}"
		else
			check "reason_${id}" "one-of(${READ_REASONS// /|})" "${reason}"
		fi
	done
}

# -- before a phase ------------------------------------------------------------------

before() {
	printf '%s/before-%s.%s' "${WORK}" "$1" "$2"
}

cmd_mark() {
	is_phase "$1" || fail "unknown phase $1"
	log_offset > "$(before "$1" offset)"
	occ_files "$(before "$1" files.json)" || fail "occ audio_video_search:files failed"
	occ_status "$(before "$1" status.json)" || fail "occ audio_video_search:status failed"
}

previous_truth() {
	local previous
	previous=$(previous_phase "$1")
	[ -n "${previous}" ] || fail "the phase $1 has no previous truth"
	printf '%s/truth-%s.json' "${PWD}" "${previous}"
}

ledger() {
	bash "${SCRIPT_DIR}/ledger.sh" "$@" || fail "ledger.sh $1 failed"
}

cmd_prepare() {
	PHASE="$1"
	local truth files="${WORK}/prepare-$1.files.json"
	case "$1" in
		read-proof)
			ledger sample "$(need_id ID_ANA_SMB_GESPERRT_WEBM)" ana "$(previous_truth "$1")"
			;;
		shares)
			truth=$(previous_truth "$1")
			ledger sample "$(need_id ID_ANA_TEILEN_WEBM)" ana "${truth}"
			ledger sample "$(need_id ID_ANA_SMB_GEMEINSAM_G1_WEBM)" ana "${truth}"
			;;
		exclude-after)
			# x lives only in archiv-spaeter/, z also in gemeinsam/; z gets a
			# correction by hand that has to survive (D-02-04).
			truth=$(previous_truth "$1")
			ledger sample "$(need_id ID_ANA_SMB_ARCHIV_SPAETER_X_WEBM)" ana "${truth}"
			ledger sample "$(need_id ID_ANA_SMB_ARCHIV_SPAETER_Z_WEBM)" ana "${truth}"
			occ_files "${files}" || fail "occ audio_video_search:files failed"
			media_of "${files}" "$(need_id ID_ANA_SMB_ARCHIV_SPAETER_X_WEBM)" > "${WORK}/media-x"
			media_of "${files}" "$(need_id ID_ANA_SMB_ARCHIV_SPAETER_Z_WEBM)" > "${WORK}/media-z"
			[[ "$(cat "${WORK}/media-z")" =~ ^[0-9]+$ ]] || fail "z has no media id before the exclusion"
			docker exec -i "${EXAPP_CONTAINER:?}" python3 - "$(cat "${WORK}/media-z")" << 'PY' || fail "the correction on z could not be written"
import os
import sqlite3
import sys
import time

path = os.path.join(os.environ["APP_PERSISTENT_STORAGE"], "state.db")
connection = sqlite3.connect(path, timeout=30)
with connection:
    connection.execute(
        "INSERT INTO correction (media_id, start_ms, end_ms, kind, body, author_uid, created_at)"
        " VALUES (?, 0, 1000, 'text', 'Korrektur der Abnahme', 'ana', ?)",
        (int(sys.argv[1]), int(time.time() * 1000)),
    )
PY
			;;
		reprove)
			# Positive control: cem finds widerruf.webm before Samba denies it to him.
			ledger sample "$(need_id ID_ANA_SMB_WIDERRUF_WEBM)" ana "$(previous_truth "$1")"
			check_true cem_finds_before "$(search_ids cem Testtreffer | grep -qx "$(need_id ID_CEM_SMB_WIDERRUF_WEBM)" && echo true || echo false)"
			;;
		vanish)
			ledger sample "$(need_id ID_CEM_SMB_NUR_CEM_C1_WEBM)" cem "$(previous_truth "$1")"
			;;
		delete-user)
			ledger sample "$(need_id ID_DAN_DAN_WEBM)" dan "$(previous_truth "$1")"
			occ_files "${files}" || fail "occ audio_video_search:files failed"
			media_of "${files}" "$(need_id ID_DAN_DAN_WEBM)" > "${WORK}/media-dan"
			[[ "$(cat "${WORK}/media-dan")" =~ ^[0-9]+$ ]] || fail "dan.webm has no media id before the deletion"
			;;
		*) ;;
	esac
	return "${FAILED}"
}

cmd_appear() {
	local id="${1:?}" since="${2:?}" limit="${3:?}" files="${WORK}/appear.files.json" now
	while true; do
		now=$(date +%s)
		if occ_files "${files}" 2> /dev/null && [ -n "$(state_of "${files}" "${id}")" ]; then
			echo "$((now - since))" > "${WORK}/appear-${id}"
			echo "file ${id} is in the work stock after $((now - since)) s"
			return 0
		fi
		if [ "$((now - since))" -gt "${limit}" ]; then
			echo "-1" > "${WORK}/appear-${id}"
			echo "file ${id} is not in the work stock after ${limit} s"
			return 1
		fi
		sleep 5
	done
}

# A stock without any first crawl is not complete: the scheduler plans the
# first crawls up to five minutes after the backend is ready (run 43359737879
# judged four phases before that).
cmd_wait() {
	local start now status="${WORK}/wait-status.json"
	start=$(date +%s)
	while true; do
		if occ_status "${status}" 2> /dev/null && jq -e '
			(.crawl.open == 0)
			and ((.crawl.finished + .crawl.open) > 0)
			and ([.queue.open // {} | .[]] | all(. == 0))
			and (.queue.ok != false)
			and (.dueWork == 0)' "${status}" > /dev/null; then
			echo "work stock complete after $(($(date +%s) - start)) s"
			return 0
		fi
		now=$(date +%s)
		if [ "$((now - start))" -ge "${WAIT_LIMIT}" ]; then
			echo "FAIL wait: not complete after ${WAIT_LIMIT} s $(jq -c '{crawl, queue, dueWork}' "${status}" 2> /dev/null || echo 'status unreadable')"
			return 1
		fi
		sleep "${WAIT_EVERY}"
	done
}

# -- one phase ----------------------------------------------------------------------

search_has() {
	search_ids "$1" Testtreffer | grep -qx "$2" && echo true || echo false
}

lines_since() {
	gateway_lines "${ACCESS_LOG}" "$(cat "$(before "${PHASE}" offset)" 2> /dev/null || echo 0)" "$1" "$2"
}

phase_checks() {
	local files="$1" status="$2" before_files before_status id old new count
	before_files=$(before "${PHASE}" files.json)
	before_status=$(before "${PHASE}" status.json)
	case "${PHASE}" in
		initial)
			check_true skipped_session_mount "$(jq --arg m "$(need_id M2_ID)" '
				[.skippedStorages[]? | select(([.[]? | tostring] | index($m) != null) and .reason == "session_credentials")]
				| length >= 1' "${status}")"
			id=$(need_id ID_ANA_TEILEN_WEBM)
			check shared_once_ben "${id}" "$(need_id ID_BEN_TEILEN_WEBM)"
			check shared_once_cem "${id}" "$(need_id ID_CEM_TEILEN_WEBM)"
			check shared_once_dan "$(need_id ID_ANA_SMB_GEMEINSAM_G1_WEBM)" "$(need_id ID_DAN_GEMEINSAM_G1_WEBM)"
			check local_captured active "$(state_of "${files}" "$(need_id ID_ANA_LOKAL_L1_WEBM)")"
			check s3_captured active "$(state_of "${files}" "$(need_id ID_ANA_S3_S1_WEBM)")"
			;;
		read-proof)
			check_true ana_finds_her_copy "$(search_has ana "$(need_id ID_ANA_SMB_GESPERRT_WEBM)")"
			check ben_finds_no_denied_copy false "$(search_has ben "$(need_id ID_BEN_SMB_GESPERRT_WEBM)")"
			;;
		shares)
			id=$(need_id ID_ANA_TEILEN_WEBM)
			check_true ben_finds_share "$(search_has ben "${id}")"
			check_true cem_finds_reshare "$(search_has cem "${id}")"
			check_true dan_finds_smb_share "$(search_has dan "$(need_id ID_DAN_GEMEINSAM_G1_WEBM)")"
			check eva_finds_nothing 0 "$(search_ids eva Testtreffer | grep -c . || true)"
			;;
		access-control)
			check sperre_reason access_control "$(field_of "${files}" "$(need_id ID_ANA_SPERRE_WEBM)" reason)"
			;;
		upload)
			id=$(need_id UPLOAD_ID)
			count=$(cat "${WORK}/appear-${id}" 2> /dev/null || echo -1)
			check_true upload_within_300s "$([ "${count}" -ge 0 ] && [ "${count}" -le 300 ] && echo true || echo false)" "seconds=${count}"
			check upload_active active "$(state_of "${files}" "${id}")"
			;;
		overwrite)
			id=$(need_id ID_ANA_UEBERSCHREIBEN_WEBM)
			old=$(media_of "${before_files}" "${id}")
			new=$(media_of "${files}" "${id}")
			check overwrite_active active "$(state_of "${files}" "${id}")"
			check_true overwrite_new_media "$([ -n "${new}" ] && [ "${new}" != "${old}" ] && echo true || echo false)" "alt=${old} neu=${new}"
			check_true overwrite_downloaded "$([ "$(lines_since "${id}" files)" -ge 1 ] && echo true || echo false)"
			check_true old_media_orphaned "$([[ "${old}" =~ ^[0-9]+$ ]] && [ -n "$(state_db "SELECT orphaned_at FROM media WHERE media_id=${old} AND orphaned_at IS NOT NULL")" ] && echo true || echo false)"
			;;
		copy)
			id=$(need_id ID_ANA_KOPIE_WEBM)
			check copy_active active "$(state_of "${files}" "${id}")"
			check copy_same_media "$(media_of "${files}" "$(need_id ID_ANA_KOPIEREN_WEBM)")" "$(media_of "${files}" "${id}")"
			check_true copy_at_most_one_download "$([ "$(lines_since "${id}" files)" -le 1 ] && echo true || echo false)"
			;;
		rename)
			id=$(need_id ID_ANA_UMBENANNT_WEBM)
			check rename_same_file_id "$(need_id ID_ANA_UMBENENNEN_WEBM)" "${id}"
			check rename_same_media "$(media_of "${before_files}" "${id}")" "$(media_of "${files}" "${id}")"
			check rename_no_gateway_line 0 "$(lines_since "${id}" any)"
			;;
		tag)
			id=$(need_id ID_ANA_TAGGEN_WEBM)
			check tag_same_media "$(media_of "${before_files}" "${id}")" "$(media_of "${files}" "${id}")"
			check tag_no_gateway_line 0 "$(lines_since "${id}" any)"
			;;
		move-cross)
			id=$(need_id ID_ANA_TEAM_WANDERN_WEBM)
			check move_same_media "$(media_of "${before_files}" "$(need_id ID_ANA_WANDERN_WEBM)")" "$(media_of "${files}" "${id}")"
			check_true move_at_most_one_download "$([ "$(lines_since "${id}" files)" -le 1 ] && echo true || echo false)"
			;;
		trash)
			id=$(need_id ID_ANA_PAPIERKORB_WEBM)
			check_true trashed_not_active "$([ "$(state_of "${files}" "${id}")" != active ] && echo true || echo false)"
			;;
		restore)
			id=$(need_id ID_ANA_PAPIERKORB_WEBM)
			old=$(media_of "$(before trash files.json)" "${id}")
			check restore_active active "$(state_of "${files}" "${id}")"
			check restore_same_media "${old}" "$(media_of "${files}" "${id}")"
			check restore_no_download 0 "$(lines_since "${id}" files)"
			;;
		exclude-user-after)
			check ben_storage_refs 0 "$(jq --arg s "$(need_id STORAGE_SMB_BEN)" '[.[] | select((.storageId | tostring) == $s)] | length' "${files}")"
			check_true ana_storage_refs_stay "$(jq --arg s "$(need_id STORAGE_SMB_ANA)" '[.[] | select((.storageId | tostring) == $s and .state == "active")] | length > 0' "${files}")"
			check ben_finds_nothing 0 "$(search_ids ben Testtreffer | grep -c . || true)"
			;;
		exclude-storage-after)
			check m3_refs 0 "$(jq --arg s "$(need_id STORAGE_SMB_TEIL_ANA)" '[.[] | select((.storageId | tostring) == $s)] | length' "${files}")"
			check contents_unchanged "$(jq -r '.contents' "${before_status}")" "$(jq -r '.contents' "${status}")"
			check_true files_fewer "$(jq -n --slurpfile b "${before_status}" --slurpfile a "${status}" '$a[0].files < $b[0].files')"
			;;
		exclude-after)
			old=$(cat "${WORK}/media-x" 2> /dev/null)
			new=$(cat "${WORK}/media-z" 2> /dev/null)
			check x_forgotten 0 "$(state_db "SELECT (SELECT COUNT(*) FROM media WHERE media_id=${old:-0}) + (SELECT COUNT(*) FROM transcript WHERE media_id=${old:-0}) + (SELECT COUNT(*) FROM current WHERE media_id=${old:-0})")"
			check z_kept 1 "$(state_db "SELECT COUNT(*) FROM media WHERE media_id=${new:-0}")"
			check_true z_correction_kept "$([ "$(state_db "SELECT COUNT(*) FROM correction WHERE media_id=${new:-0}")" -ge 1 ] && echo true || echo false)"
			;;
		reprove)
			id=$(need_id ID_CEM_SMB_WIDERRUF_WEBM)
			check reprove_unreadable unreadable "$(state_of "${files}" "${id}")"
			check cem_finds_no_revoked_copy false "$(search_has cem "${id}")"
			;;
		vanish)
			count=$(jq --arg s "$(need_id STORAGE_SMB_CEM)" '[.[] | select((.storageId | tostring) == $s)] | length' "${files}")
			check_true cem_refs_vanished "$(jq --arg s "$(need_id STORAGE_SMB_CEM)" '[.[] | select((.storageId | tostring) == $s) | .state] | length > 0 and all(. == "vanished")' "${files}")" "refs=${count}"
			check transcribed_minus_one "$(($(jq -r '.transcribed' "${before_status}") - 1))" "$(jq -r '.transcribed' "${status}")"
			;;
		delete-user)
			id=$(need_id ID_DAN_DAN_WEBM)
			old=$(cat "${WORK}/media-dan" 2> /dev/null)
			check_true dan_ref_gone "$([ "$(state_of "${files}" "${id}")" != active ] && echo true || echo false)"
			check_true dan_media_orphaned "$([ -n "$(state_db "SELECT orphaned_at FROM media WHERE media_id=${old:-0} AND orphaned_at IS NOT NULL")" ] && echo true || echo false)"
			check transcribed_minus_one "$(($(jq -r '.transcribed' "${before_status}") - 1))" "$(jq -r '.transcribed' "${status}")"
			;;
		reattach)
			id=$(need_id ID_ANA_DAN_KOPIE_WEBM)
			old=$(cat "${WORK}/media-dan" 2> /dev/null)
			check reattach_active active "$(state_of "${files}" "${id}")"
			check reattach_same_media "${old}" "$(media_of "${files}" "${id}")"
			check reattach_not_orphaned 1 "$(state_db "SELECT COUNT(*) FROM media WHERE media_id=${old:-0} AND orphaned_at IS NULL")"
			check reattach_transcript_kept 1 "$(state_db "SELECT COUNT(*) FROM current WHERE media_id=${old:-0}")"
			check transcribed_plus_one "$(($(jq -r '.transcribed' "${before_status}") + 1))" "$(jq -r '.transcribed' "${status}")"
			check_true reattach_downloaded "$([ "$(lines_since "${id}" files)" -ge 1 ] && echo true || echo false)"
			;;
		foreign-change)
			id=$(need_id ID_ANA_SMB_GEMEINSAM_FREMD_WEBM)
			old=$(media_of "${before_files}" "${id}")
			new=$(media_of "${files}" "${id}")
			check_true foreign_new_hash "$([ -n "${new}" ] && [ "${new}" != "${old}" ] && echo true || echo false)" "alt=${old} neu=${new}"
			;;
	esac
}

cmd_phase() {
	PHASE="$1"
	local truth="${PWD}/truth-${PHASE}.json" files="${PWD}/occ-files-${PHASE}.json" status="${PWD}/occ-status-${PHASE}.json"
	[ -f "${truth}" ] || fail "truth.sh ${PHASE} has not run"
	occ_files "${files}" || fail "occ audio_video_search:files failed"
	occ_status "${status}" || fail "occ audio_video_search:status failed"
	case "${PHASE}" in
		exclude-user-after | exclude-storage-after | exclude-after) ledger drop-where-gone "${truth}" ;;
	esac
	core_checks "${truth}" "${files}" "${status}" "$(bash "${SCRIPT_DIR}/ledger.sh" expected "${truth}")" "${ACCESS_LOG}"
	unreadable_reasons "${truth}" "${files}"
	phase_checks "${files}" "${status}"
	if [ "${FAILED}" = 0 ]; then
		echo "PHASE PASS ${PHASE}"
		return 0
	fi
	echo "PHASE FAIL ${PHASE}"
	return 1
}

# -- the checks have to be able to fail ---------------------------------------------

# failures OUTPUT: the names of the failed checks, one per line.
failures() {
	sed -n 's/^FAIL [^:]*:\([^ ]*\).*/\1/p' <<< "$1" | sort
}

cmd_self_test() {
	PHASE=self-test
	local files="${WORK}/self.files.json" status="${WORK}/self.status.json" truth="${WORK}/self.truth.json"
	local shifted="${WORK}/self.shifted.json" log="${WORK}/self.access.log" base out never id
	# An id shared with the session mount that no request names, read by ana.
	local shared=999999998 foreign="${WORK}/self.foreign.log"
	occ_files "${files}" || fail "occ audio_video_search:files failed"
	occ_status "${status}" || fail "occ audio_video_search:status failed"
	bash "${SCRIPT_DIR}/truth.sh" initial > /dev/null || fail "truth.sh initial failed"
	# A never fetched id that is not yet in the log, so the baseline passes it.
	never=999999999
	for id in $(jq -r '.neverFetched[]' "${PWD}/truth-initial.json"); do
		if [ "$(gateway_lines "${ACCESS_LOG}" 0 "${id}" any)" = 0 ]; then
			never="${id}"
			break
		fi
	done
	# The expectation is the real output itself: the baseline passes the
	# shifted checks by construction, a shift has to make exactly them fail.
	jq --slurpfile s "${status}" --argjson never "${never}" --arg shared "${shared}" '{
		files: [.[] | select(.state == "active" or .state == "unreadable") | .fileId],
		unreadable: [.[] | select(.state == "unreadable") | .fileId],
		N_active: $s[0].files, Y: $s[0].contents, neverFetched: [$never],
		sessionShared: {($shared): ["ana"]}, sha: {}, unmapped: 0
	}' "${files}" > "${truth}"
	local transcribed
	transcribed=$(jq -r '.transcribed' "${status}")
	base=$(failures "$(FAILED=0 core_checks "${truth}" "${files}" "${status}" "${transcribed}" "${ACCESS_LOG}")")

	shift_one() {
		local name="$1" expected_fail="$2" output
		output=$(FAILED=0 core_checks "${@:3}")
		echo "${output}" | grep '^FAIL' || true
		if [ "$(comm -13 <(echo "${base}") <(failures "${output}") | paste -sd, -)" != "${expected_fail}" ] \
			|| grep -qx "${expected_fail}" <<< "${base}"; then
			echo "compare self-test did not fail (${name})"
			return 1
		fi
		echo "self-test ${name}: the shifted check ${expected_fail} failed"
	}

	local result=0
	jq '.N_active += 1' "${truth}" > "${shifted}"
	shift_one N_active+1 files_count "${shifted}" "${files}" "${status}" "${transcribed}" "${ACCESS_LOG}" || result=1
	jq '.Y += 1' "${truth}" > "${shifted}"
	shift_one Y+1 contents "${shifted}" "${files}" "${status}" "${transcribed}" "${ACCESS_LOG}" || result=1
	shift_one transcribed+1 transcribed "${truth}" "${files}" "${status}" "$((transcribed + 1))" "${ACCESS_LOG}" || result=1
	cp "${ACCESS_LOG}" "${log}" 2> /dev/null || : > "${log}"
	echo "[Sat Nov  7 00:00:00 2026] 127.0.0.1:1 [200]: GET /ocs/v2.php/apps/audio_video_search/files/${never}?userId=x" >> "${log}"
	shift_one access-log never_in_log "${truth}" "${files}" "${status}" "${transcribed}" "${log}" || result=1
	cp "${ACCESS_LOG}" "${foreign}" 2> /dev/null || : > "${foreign}"
	echo "[Sat Nov  7 00:00:00 2026] 127.0.0.1:1 [200]: GET /ocs/v2.php/apps/audio_video_search/files/${shared}?userId=x" >> "${foreign}"
	shift_one foreign-reader session_shared_readers "${truth}" "${files}" "${status}" "${transcribed}" "${foreign}" || result=1
	[ "${result}" = 0 ] || fail "compare self-test did not fail"
	echo "compare self-test passed: every shifted check failed on its own"
}

case "${1:-}" in
	wait) cmd_wait ;;
	--self-test) cmd_self_test ;;
	prepare) cmd_prepare "${2:?phase}" ;;
	mark) cmd_mark "${2:?phase}" ;;
	appear) cmd_appear "${2:-}" "${3:-}" "${4:-}" ;;
	*)
		is_phase "${1:-}" || fail "usage: compare.sh wait|--self-test|prepare <phase>|mark <phase>|appear <id> <since> <limit>|<phase>"
		cmd_phase "$1"
		;;
esac
