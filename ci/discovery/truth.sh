#!/usr/bin/env bash
# The independent truth of the discovery acceptance test (D-02-07), one file
# per phase: truth-<phase>.json in the working directory.
#
# Rule "never check with the pattern of the implementation": nothing here runs
# code of this app. The files come from the file systems themselves (find as
# the Unix user for the Samba views, find in the data directory for homes and
# the team folder, the S3 API for the bucket), the file ids from the database
# of Nextcloud (sqlite3 on data/owncloud.db: oc_mounts -> storage and root ->
# oc_filecache), the contents from sha256sum over bytes read by another way
# (smbclient as the user for Samba, cat for local files, the S3 API for S3).
#
# usage: truth.sh <phase>
#
# Output fields:
#   files         every file id the work stock has to hold for this phase,
#                 the unreadable ones included
#   unreadable    the file ids whose bytes their reader cannot get
#   N_active      |files| - |unreadable|
#   Y             number of distinct sha256 of the readable files
#   neverFetched  file ids excluded before the first run (eva, the group
#                 extern, the folder privat) and the ids that only the session
#                 mount M2 reaches
#   sessionShared file id -> users: ids of the session mount M2 that another
#                 mount of the same storage reaches, and the users of those
#                 mounts; only they may fetch such an id
#   sha           file id -> sha256 of the readable files (for ledger.sh)
#   unmapped      files on disk without a file id in oc_filecache (must be 0)
#
# The deductions per phase follow the interfaces of plan 02-04: exclusions,
# the session mount, vanished storages, deleted users, the trash.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=ci/discovery/common.sh
. "${SCRIPT_DIR}/common.sh"

PHASE="${1:-}"
is_phase "${PHASE}" || fail "usage: truth.sh <phase>, one of ${PHASES[*]}"
OUT="${PWD}/truth-${PHASE}.json"
ROWS="${WORK}/truth-${PHASE}.tsv"
NEVER="${WORK}/truth-${PHASE}.never"
: > "${ROWS}"
: > "${NEVER}"
SHARED="${WORK}/truth-${PHASE}.shared"
: > "${SHARED}"

# -- the rules of the test for this phase -----------------------------------------

EXCLUDED_USERS=(eva fritz)
EXCLUDED_FOLDERS=(privat)
reached "${PHASE}" exclude-user-after && EXCLUDED_USERS+=(ben)
reached "${PHASE}" exclude-after && EXCLUDED_FOLDERS+=(archiv-spaeter)

user_out() {
	local user
	for user in "${EXCLUDED_USERS[@]}"; do
		[ "${user}" = "$1" ] && return 0
	done
	if [ "$1" = dan ] && reached "${PHASE}" delete-user; then
		return 0
	fi
	if [ "$1" = cem ] && [ "$2" = smb ] && reached "${PHASE}" vanish; then
		return 0
	fi
	return 1
}

# folder_out REL: REL (relative to the root of its mount) lies in an excluded folder.
folder_out() {
	local folder
	for folder in "${EXCLUDED_FOLDERS[@]}"; do
		case "$1" in
			"${folder}" | "${folder}"/*) return 0 ;;
		esac
	done
	return 1
}

# -- file ids out of the database of Nextcloud ------------------------------------

sq() {
	printf '%s' "${1//\'/\'\'}"
}

# mount_of USER MOUNTPOINT: "storage|root path" of the mount, empty when the
# user has no such mount.
mount_of() {
	local row storage root rootpath
	row=$(sql "SELECT storage_id || '|' || root_id FROM oc_mounts WHERE user_id='$(sq "$1")' AND mount_point='$(sq "$2")' LIMIT 1")
	[ -n "${row}" ] || return 0
	storage=${row%%|*}
	root=${row##*|}
	rootpath=$(sql "SELECT path FROM oc_filecache WHERE fileid=${root}")
	printf '%s|%s' "${storage}" "${rootpath}"
}

# fid USER MOUNTPOINT REL: the file id of REL below the root of the mount.
fid() {
	local mount storage rootpath path
	mount=$(mount_of "$1" "$2")
	[ -n "${mount}" ] || return 0
	storage=${mount%%|*}
	rootpath=${mount#*|}
	path="${rootpath:+${rootpath}/}$3"
	sql "SELECT fileid FROM oc_filecache WHERE storage=${storage} AND path='$(sq "${path}")' LIMIT 1"
}

# media_ids_below USER MOUNTPOINT [PREFIX]: every media file id of the mount
# (below PREFIX), straight out of oc_filecache; for the ids that must never be
# fetched, which need no file on disk.
media_ids_below() {
	local mount storage rootpath base path id
	mount=$(mount_of "$1" "$2")
	[ -n "${mount}" ] || return 0
	storage=${mount%%|*}
	rootpath=${mount#*|}
	base="${rootpath:+${rootpath}/}${3:-}"
	while IFS='|' read -r id path; do
		[ -n "${id}" ] && is_media "${path}" && echo "${id}"
	done < <(sql "SELECT fileid || '|' || path FROM oc_filecache WHERE storage=${storage} AND path LIKE '$(sq "${base}")%' AND mimetype <> (SELECT id FROM oc_mimetypes WHERE mimetype='httpd/unix-directory')")
	return 0
}

UNMAPPED=0

# row ID SHA UNREADABLE SOURCE
row() {
	if [ -z "$1" ]; then
		UNMAPPED=$((UNMAPPED + 1))
		echo "truth: a file of ${4} has no file id in oc_filecache"
		return
	fi
	printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >> "${ROWS}"
}

# -- reading the bytes another way ------------------------------------------------

smb_sha() {
	local tmp="${WORK}/truth-get.bin" out
	rm -f "${tmp}"
	out=$(timeout 60 smbclient "${SMB_URL}" -A "$(smb_auth "$1")" -c "get \"$2\" \"${tmp}\"" 2>&1) || true
	if grep -q 'NT_STATUS_' <<< "${out}" || [ ! -s "${tmp}" ]; then
		return 0
	fi
	sha256sum "${tmp}" | cut -d ' ' -f 1
}

file_sha() {
	[ -r "$1" ] && sha256sum "$1" | cut -d ' ' -f 1
	return 0
}

s3() {
	curl -sfS --aws-sigv4 "aws:amz:us-east-1:s3" -u "${S3_ACCESS_KEY:?}:${S3_SECRET_KEY:?}" \
		"http://localhost:${S3_PORT:?}/${S3_BUCKET}$1"
}

# -- the views --------------------------------------------------------------------

# M1 /SMB: each user's own view of the share, as the Unix user sees it.
smb_views() {
	local user rel sha
	for user in ana ben cem; do
		user_out "${user}" smb && continue
		while IFS= read -r rel; do
			rel=${rel#"${SHARE_DIR}/"}
			is_media "${rel}" || continue
			folder_out "${rel}" && continue
			sha=$(smb_sha "${user}" "${rel}")
			row "$(fid "${user}" "/${user}/files/SMB/" "${rel}")" "${sha}" "$([ -n "${sha}" ] && echo 0 || echo 1)" "smb:${user}"
		done < <(sudo -u "${user}" find "${SHARE_DIR}" -type f 2> /dev/null | sort || true)
	done
	return 0
}

# M3 /SMB-Teil: the same share with the root gemeinsam, read by ana.
smb_part() {
	reached "${PHASE}" exclude-storage-after && return 0
	local rel sha
	while IFS= read -r rel; do
		rel=${rel#"${SHARE_DIR}/gemeinsam/"}
		is_media "${rel}" || continue
		folder_out "${rel}" && continue
		sha=$(smb_sha ana "gemeinsam/${rel}")
		row "$(fid ana /ana/files/SMB-Teil/ "${rel}")" "${sha}" "$([ -n "${sha}" ] && echo 0 || echo 1)" "smb-part:ana"
	done < <(sudo -u ana find "${SHARE_DIR}/gemeinsam" -type f 2> /dev/null | sort || true)
	return 0
}

# Homes in the data directory; files_trashbin and files_versions lie outside files/.
homes() {
	local user dir rel sha unreadable
	for user in ana ben cem dan eva fritz; do
		user_out "${user}" home && continue
		dir="${DATADIR}/${user}/files"
		[ -d "${dir}" ] || continue
		while IFS= read -r rel; do
			rel=${rel#"${dir}/"}
			is_media "${rel}" || continue
			folder_out "${rel}" && continue
			unreadable=0
			# Rule of the test, not of the file system: files_accesscontrol denies
			# every web access to sperre.webm from the phase access-control on.
			if [ "${user}" = ana ] && [ "${rel}" = sperre.webm ] && reached "${PHASE}" access-control; then
				unreadable=1
			fi
			sha=''
			[ "${unreadable}" = 0 ] && sha=$(file_sha "${dir}/${rel}")
			[ -n "${sha}" ] || unreadable=1
			row "$(fid "${user}" "/${user}/" "files/${rel}")" "${sha}" "${unreadable}" "home:${user}"
		done < <(find "${dir}" -type f | sort)
	done
	return 0
}

# The team folder: one file id per file for all members; old form
# __groupfolders/<id>, new form __groupfolders/<id>/files.
team() {
	local folder dir rel sha
	folder=$(need_id TEAM_FOLDER_ID)
	dir="${DATADIR}/__groupfolders/${folder}"
	[ -d "${dir}/files" ] && dir="${dir}/files"
	[ -d "${dir}" ] || fail "the team folder is not in the data directory"
	while IFS= read -r rel; do
		rel=${rel#"${dir}/"}
		is_media "${rel}" || continue
		folder_out "${rel}" && continue
		sha=$(file_sha "${dir}/${rel}")
		row "$(fid ana /ana/files/Team/ "${rel}")" "${sha}" "$([ -n "${sha}" ] && echo 0 || echo 1)" "team"
	done < <(find "${dir}" -type f | sort)
	return 0
}

# M4 /Lokal: one storage for ana and cem, so one file id per file.
local_mount() {
	local rel sha
	while IFS= read -r rel; do
		rel=${rel#"${LOCAL_DIR}/"}
		is_media "${rel}" || continue
		folder_out "${rel}" && continue
		sha=$(file_sha "${LOCAL_DIR}/${rel}")
		row "$(fid ana /ana/files/Lokal/ "${rel}")" "${sha}" "$([ -n "${sha}" ] && echo 0 || echo 1)" "local"
	done < <(find "${LOCAL_DIR}" -type f | sort)
	return 0
}

# M5 /S3: the keys and the bytes through the S3 API.
s3_mount() {
	local key sha tmp="${WORK}/truth-s3.bin"
	while IFS= read -r key; do
		[ -n "${key}" ] || continue
		is_media "${key}" || continue
		folder_out "${key}" && continue
		rm -f "${tmp}"
		sha=''
		if s3 "/${key}" > "${tmp}" 2> /dev/null && [ -s "${tmp}" ]; then
			sha=$(sha256sum "${tmp}" | cut -d ' ' -f 1)
		fi
		row "$(fid ana /ana/files/S3/ "${key}")" "${sha}" "$([ -n "${sha}" ] && echo 0 || echo 1)" "s3"
	done < <(s3 '?list-type=2' | grep -oE '<Key>[^<]*</Key>' | sed -e 's|<Key>||' -e 's|</Key>||' | sort)
	return 0
}

# session_mount USER MOUNTPOINT: the media file ids of a mount with session
# credentials (D-02-03: the mount is skipped, nothing is fetched through it).
# A storage has one file id per file, whichever mount leads to it. An id that
# another mount of the same storage reaches (M1 with stored credentials lies
# on the share of M2) is captured through that mount, so it cannot be "never
# fetched": it goes to sessionShared with the users of those other mounts, and
# compare.sh checks that nobody else fetched it. An id that only the session
# mount reaches stays in neverFetched. The access log names the user and the
# file id of a request, not the mount; that is the limit of this check.
session_mount() {
	local mount storage rootpath base ways="${WORK}/truth-${PHASE}.ways" user root id path readers
	mount=$(mount_of "$1" "$2")
	[ -n "${mount}" ] || return 0
	storage=${mount%%|*}
	rootpath=${mount#*|}
	base="${rootpath:+${rootpath}/}"
	: > "${ways}"
	while IFS='|' read -r user root; do
		[ -n "${user}" ] || continue
		user_out "${user}" smb && continue
		printf '%s|%s\n' "${user}" "${root}" >> "${ways}"
	done < <(sql "SELECT m.user_id || '|' || f.path FROM oc_mounts m JOIN oc_filecache f ON f.fileid = m.root_id WHERE m.storage_id=${storage} AND NOT (m.user_id='$(sq "$1")' AND m.mount_point='$(sq "$2")')")
	while IFS='|' read -r id path; do
		[ -n "${id}" ] || continue
		is_media "${path}" || continue
		readers=''
		while IFS='|' read -r user root; do
			if [ -z "${root}" ] || [ "${path#"${root}/"}" != "${path}" ]; then
				readers="${readers:+${readers},}${user}"
			fi
		done < "${ways}"
		if [ -n "${readers}" ]; then
			printf '%s\t%s\n' "${id}" "${readers}" >> "${SHARED}"
		else
			echo "${id}" >> "${NEVER}"
		fi
	done < <(sql "SELECT fileid || '|' || path FROM oc_filecache WHERE storage=${storage} AND path LIKE '$(sq "${base}")%' AND mimetype <> (SELECT id FROM oc_mimetypes WHERE mimetype='httpd/unix-directory')")
	return 0
}

never_fetched() {
	media_ids_below eva /eva/ files/ >> "${NEVER}"
	media_ids_below fritz /fritz/ files/ >> "${NEVER}"
	media_ids_below ana /ana/ files/privat/ >> "${NEVER}"
	session_mount ana /ana/files/SMB-Sitzung/
}

smb_views
smb_part
homes
team
local_mount
s3_mount
never_fetched

jq -Rn --arg phase "${PHASE}" --argjson unmapped "${UNMAPPED}" --rawfile never "${NEVER}" --rawfile shared "${SHARED}" '
	[inputs | select(length > 0) | split("\t")
		| {id: (.[0] | tonumber), sha: .[1], unreadable: (.[2] == "1"), source: .[3]}] as $rows
	| ($rows | group_by(.id) | map({id: .[0].id, unreadable: (map(.unreadable) | any), sha: (map(.sha) | max)})) as $files
	| ($files | map(select(.unreadable) | .id)) as $unreadable
	| {
		phase: $phase,
		files: ($files | map(.id)),
		unreadable: $unreadable,
		N_active: (($files | length) - ($unreadable | length)),
		Y: ($files | map(select(.unreadable | not) | .sha) | unique | length),
		neverFetched: ($never | split("\n") | map(select(length > 0) | tonumber) | unique),
		sessionShared: ($shared | split("\n") | map(select(length > 0) | split("\t")
			| {key: .[0], value: (.[1] | split(",") | unique)}) | from_entries),
		sha: ($files | map(select(.unreadable | not) | {key: (.id | tostring), value: .sha}) | from_entries),
		unmapped: $unmapped
	}' < "${ROWS}" > "${OUT}"

jq -c '{phase, files: (.files | length), unreadable, N_active, Y, neverFetched: (.neverFetched | length), sessionShared: (.sessionShared | length), unmapped}' "${OUT}"
