#!/usr/bin/env bash
# The positive controls of the discovery acceptance test (D-02-07). Each one
# shows that a statement of the test can see what it claims to see; without
# them a green run proves nothing.
#
# usage: controls.sh samba        at the Samba server: ana reads gesperrt.webm,
#                                 ben is refused with NT_STATUS_ACCESS_DENIED
#        controls.sh access-log   after the phase initial: a file the backend
#                                 certainly fetched has a line in the access log
#        controls.sh leak         only in the job leak-control, with the image
#                                 without the read proof: ben finds a file Samba
#                                 denies him (D-02-01a, D-02-10)
#
# Environment: as topology.sh; leak also needs OCC, MEDIA_DIR and NC_URL.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=ci/discovery/common.sh
. "${SCRIPT_DIR}/common.sh"

NETBIOS=AVSSMB

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	timeout 300 ${OCC:?OCC is required} "$@"
}

# smb_get USER PATH: the smbclient output of a get into a temporary file.
smb_get() {
	rm -f "${WORK}/control-get.bin"
	timeout 60 smbclient "${SMB_URL}" -A "$(smb_auth "$1")" -c "get \"$2\" \"${WORK}/control-get.bin\"" 2>&1 || true
}

cmd_samba() {
	local out
	out=$(smb_get ana gesperrt.webm)
	if grep -q 'NT_STATUS_' <<< "${out}" || [ ! -s "${WORK}/control-get.bin" ]; then
		fail "samba positive control failed, run invalid (ana cannot read gesperrt.webm)"
	fi
	out=$(smb_get ben gesperrt.webm)
	if ! grep -q 'NT_STATUS_ACCESS_DENIED' <<< "${out}" || [ -s "${WORK}/control-get.bin" ]; then
		fail "samba positive control failed, run invalid (ben was not refused gesperrt.webm)"
	fi
	echo "samba positive control: ana reads gesperrt.webm, ben gets NT_STATUS_ACCESS_DENIED"
}

cmd_access_log() {
	local id count
	# A home file of ana: no prefilter, so the backend has to fetch it in full.
	id=$(need_id ID_ANA_TEILEN_WEBM)
	count=$(gateway_lines "${ACCESS_LOG}" 0 "${id}" files)
	if [ "${count}" -lt 1 ]; then
		fail "access log positive control failed, run invalid (no gateway line for file ${id})"
	fi
	echo "access log positive control: ${count} gateway line(s) for file ${id}"
}

file_id() {
	curl -sfS -u "$1:$(password_of "$1")" -X PROPFIND -H 'Depth: 0' \
		--data '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>' \
		"${NC_URL:?NC_URL is required}/remote.php/dav/files/$1/$2" | sed -n 's|.*<oc:fileid>\([0-9]*\)</oc:fileid>.*|\1|p'
}

cmd_leak() {
	local tone="${WORK}/kontrolle.webm" ana_id ben_id sha out
	ffmpeg -hide_banner -loglevel error -y -i "${MEDIA_DIR:?MEDIA_DIR is required}/tone-90s.webm" \
		-c copy -metadata comment=avs-kontrolle "${tone}"
	sudo install -D -o ana -g ana -m 0644 "${tone}" "${SHARE_DIR}/kontrolle.webm"
	smbcacls "${SMB_URL}" kontrolle.webm -A "$(smb_auth ana)" --add "ACL:${NETBIOS}\\ben:DENIED/0x0/READ" \
		|| fail "smbcacls could not add the DENY ACE for kontrolle.webm"
	out=$(smb_get ben kontrolle.webm)
	grep -q 'NT_STATUS_ACCESS_DENIED' <<< "${out}" || fail "Samba does not deny kontrolle.webm to ben, the control is invalid"
	smb_get ana kontrolle.webm > /dev/null
	[ -s "${WORK}/control-get.bin" ] || fail "ana cannot read kontrolle.webm, the control is invalid"
	sha=$(sha256sum "${WORK}/control-get.bin" | cut -d ' ' -f 1)

	occ files:scan ana ben > /dev/null
	ana_id=$(file_id ana SMB/kontrolle.webm)
	ben_id=$(file_id ben SMB/kontrolle.webm)
	[[ "${ana_id}" =~ ^[0-9]+$ && "${ben_id}" =~ ^[0-9]+$ ]] || fail "kontrolle.webm has no file id for ana or ben"
	bash "${SCRIPT_DIR}/compare.sh" wait || fail "the work stock of the control leg did not complete"
	occ config:app:set audio_video_search sample_visible --value=true --type=boolean > /dev/null
	bash "${SCRIPT_DIR}/ledger.sh" sample "${ana_id}" ana "${sha}"
	bash "${SCRIPT_DIR}/compare.sh" wait || fail "the work stock of the control leg did not complete"
	if search_ids ben Testtreffer | grep -qx "${ben_id}"; then
		echo "LEAK CONTROL SHOWED THE LEAK"
		return 0
	fi
	fail "leak control did not show the leak, the test cannot see it"
}

case "${1:-}" in
	samba) cmd_samba ;;
	access-log) cmd_access_log ;;
	leak) cmd_leak ;;
	*) fail "usage: controls.sh samba|access-log|leak" ;;
esac
