#!/usr/bin/env bash
# The topology of the discovery acceptance test (D-02-07), on a throwaway
# Nextcloud in CI only, and every operation the phases of the test run on it.
#
# Findling #25 passed three times because only the single parts were tested.
# This builds the shape of a real instance in one place: a Samba share that
# every user sees differently, a file Samba denies one user (Findling A6), a
# mount with session credentials, two configurations of the same share, a
# local and an S3 mount, a team folder with ACL, shares and a reshare, a share
# out of the SMB mount, an access control rule and exclusions set before the
# backend exists.
#
# usage: topology.sh samba                  Samba server, accounts and share content
#        topology.sh part-a                 Nextcloud side, before the ExApp is registered
#        topology.sh part-b                 after the registration: scan, ids
#        topology.sh control                the small topology of the leak-control leg
#        topology.sh <operation>            one operation of a phase (list below)
#
# Operations: upload_new overwrite copy_in_home rename_in_home tag_file
#   move_home_to_team trash_file restore_file access_control exclude_user_after
#   exclude_storage_after exclude_after revoke_cem vanish_cem delete_dan
#   foreign_change reattach parity_place parity_revoke
#
# Test persons: ana, ben, cem (Samba and Nextcloud), dan (own home medium, is
# deleted), eva (excluded before the first run), fritz (member of the group
# extern, which is excluded before the first run).
#
# Environment: NC_URL, OCC, MEDIA_DIR (output of ci/make-testmedia.sh),
# ADMIN_PASS, ANA_PASS, BEN_PASS, CEM_PASS, DAN_PASS, EVA_PASS, FRITZ_PASS,
# S3_ACCESS_KEY, S3_SECRET_KEY, S3_PORT; optional IDS_ENV, DATADIR,
# SERVER_VERSION. The passwords are job variables of the throwaway instance,
# never repository secrets, and are never printed: Samba gets them on stdin,
# smbclient through authentication files with mode 0600.
#
# ci/discovery/ids.env is the only place that pairs a test file with its file
# id; logs of the app must never carry a name (owner rule).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IDS_ENV="${IDS_ENV:-${SCRIPT_DIR}/ids.env}"
DATADIR="${DATADIR:-${PWD}/data}"
NC_DB="${DATADIR}/owncloud.db"
WORK="${RUNNER_TEMP:-/tmp}/avs-discovery"
SHARE_DIR=/srv/avs-medien
NETBIOS=AVSSMB
SMB_URL=//127.0.0.1/Medien
LOCAL_DIR="${RUNNER_TEMP:-/tmp}/avs-lokal"
S3_BUCKET=avs-medien
SAMBA_USERS=(ana ben cem)
NC_USERS=(ana ben cem dan eva fritz)

umask 077
mkdir -p "${WORK}"

fail() {
	echo "::error::$*"
	exit 1
}

step() {
	echo "--- $* ---"
}

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	timeout 300 ${OCC:?OCC is required} "$@"
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

sql() {
	sqlite3 "${NC_DB}" "$1"
}

# set_id KEY VALUE: one line per key in ids.env, the newest value wins.
set_id() {
	touch "${IDS_ENV}"
	sed -i "/^$1=/d" "${IDS_ENV}"
	echo "$1=$2" >> "${IDS_ENV}"
}

get_id() {
	local value
	value=$(sed -n "s/^$1=//p" "${IDS_ENV}" 2> /dev/null | tail -n 1)
	[ -n "${value}" ] || fail "ids.env has no $1"
	printf '%s' "${value}"
}

# id_key USER PATH: ID_ANA_SMB_GESPERRT_WEBM for ana and SMB/gesperrt.webm.
id_key() {
	printf 'ID_%s_%s' "$1" "$2" | tr '[:lower:]' '[:upper:]' | tr -c 'A-Z0-9_\n' '_'
}

# media TAG TARGET: the test tone with its own bytes, the tag lands in the
# comment of the container, so no two tags give the same sha256.
media() {
	ffmpeg -hide_banner -loglevel error -y -i "${MEDIA_DIR:?MEDIA_DIR is required}/tone-90s.webm" \
		-c copy -metadata comment="avs-$1" "$2"
}

# -- WebDAV and OCS -------------------------------------------------------------

dav_url() {
	printf '%s/remote.php/dav/files/%s/%s' "${NC_URL:?NC_URL is required}" "$1" "$2"
}

dav_put() {
	curl -sfS -u "$1:$(password_of "$1")" -T "$3" "$(dav_url "$1" "$2")"
}

dav_mkcol() {
	curl -sfS -u "$1:$(password_of "$1")" -X MKCOL "$(dav_url "$1" "$2")"
}

dav_login() {
	# The first request of a user is the login "save in database" stores the
	# credentials from; a missing folder still logs in.
	curl -s -o /dev/null -w '%{http_code}' -u "$1:$(password_of "$1")" -X PROPFIND -H 'Depth: 1' \
		"$(dav_url "$1" "${2:-}")" || true
}

file_id() {
	curl -sfS -u "$1:$(password_of "$1")" -X PROPFIND -H 'Depth: 0' \
		--data '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>' \
		"$(dav_url "$1" "$2")" | sed -n 's|.*<oc:fileid>\([0-9]*\)</oc:fileid>.*|\1|p'
}

# record USER PATH: the file id of PATH as USER sees it, into ids.env.
record() {
	local id
	id=$(file_id "$1" "$2" || true)
	[[ "${id}" =~ ^[0-9]+$ ]] || fail "no file id for a test file of $1"
	set_id "$(id_key "$1" "$2")" "${id}"
}

# record_soft USER PATH: like record, but a missing id is a line in the log.
record_soft() {
	local id
	id=$(file_id "$1" "$2" || true)
	if [[ "${id}" =~ ^[0-9]+$ ]]; then
		set_id "$(id_key "$1" "$2")" "${id}"
	else
		echo "no file id for $(id_key "$1" "$2") (expected for a mount without stored credentials)"
	fi
}

ocs() {
	local user="$1"
	shift
	curl -sfS -u "${user}:$(password_of "${user}")" -H 'OCS-APIRequest: true' -H 'Accept: application/json' "$@"
}

share() {
	local user="$1" path="$2" with="$3" permissions="$4"
	ocs "${user}" -X POST "${NC_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares" \
		--data-urlencode "path=${path}" --data-urlencode "shareWith=${with}" \
		--data-urlencode 'shareType=0' --data-urlencode "permissions=${permissions}" > /dev/null
}

# system_tag NAME: creates a visible, assignable system tag, prints its id.
system_tag() {
	local headers="${WORK}/tag-$1.headers"
	curl -sfS -o /dev/null -D "${headers}" -u "admin:$(password_of admin)" \
		-H 'Content-Type: application/json' \
		--data "{\"name\":\"$1\",\"userVisible\":true,\"userAssignable\":true,\"canAssign\":true}" \
		"${NC_URL}/remote.php/dav/systemtags/"
	tr -d '\r' < "${headers}" | sed -n 's|^[Cc]ontent-[Ll]ocation: .*/systemtags/\([0-9]*\)$|\1|p'
}

assign_tag() {
	curl -sfS -u "$1:$(password_of "$1")" -X PUT \
		"${NC_URL}/remote.php/dav/systemtags-relations/files/$2/$3"
}

# exclude ARG...: occ audio_video_search:exclude (plan 16), and before that
# exists the same values in the app config, so a run of this test before
# plan 16 still describes the intended exclusion.
has_command() {
	occ list audio_video_search 2> /dev/null | grep -q "audio_video_search:$1"
}

exclude() {
	if has_command exclude; then
		occ audio_video_search:exclude "$@"
		return
	fi
	echo "occ audio_video_search:exclude is missing, writing the app config instead"
	local option key value current
	for option in "$@"; do
		case "${option}" in
			--user=*) key=excluded_users ;;
			--group=*) key=excluded_groups ;;
			--folder=*) key=excluded_folders ;;
			--storage=*) key=excluded_storages ;;
			*) fail "unknown exclusion ${option}" ;;
		esac
		value="${option#*=}"
		current=$(occ config:app:get audio_video_search "${key}" 2> /dev/null || echo '[]')
		occ config:app:set audio_video_search "${key}" \
			--value="$(jq -cn --argjson list "${current:-[]}" --arg v "${value}" '$list + [$v] | unique')"
	done
}

# -- Samba ------------------------------------------------------------------------

smb_auth() {
	printf '%s/auth-%s' "${WORK}" "$1"
}

# put_share SOURCE TARGET OWNER MODE: a file into the share, the way an NAS
# admin puts it there, not through Nextcloud.
put_share() {
	sudo install -D -o "$3" -g "$3" -m "$4" "$1" "${SHARE_DIR}/$2"
}

deny_read() {
	# The DENY ACE is set by ana as owner of the file (WRITE_DAC).
	smbcacls "${SMB_URL}" "$1" -A "$(smb_auth ana)" --add "ACL:${NETBIOS}\\$2:DENIED/0x0/READ" \
		|| fail "smbcacls could not add the DENY ACE for $2"
}

cmd_samba() {
	step "Samba server and accounts"
	sudo mkdir -p "${SHARE_DIR}"
	sudo chmod 0755 "${SHARE_DIR}"
	# acl_xattr keeps the NT ACL in an extended attribute, and with "ignore
	# system acls" that stored ACL decides inside Samba; smbd still opens every
	# file as the Unix user, so the Unix modes of nur-ana/ and nur-cem/ give
	# each user a different view. Same settings as Findling's A6 measurement.
	sudo tee /etc/samba/smb.conf > /dev/null << EOF
[global]
   netbios name = ${NETBIOS}
   workgroup = WORKGROUP
   server role = standalone server
   security = user
   map to guest = never
   smb ports = 445
   interfaces = lo
   bind interfaces only = yes
   disable netbios = yes
   log level = 1

[Medien]
   path = ${SHARE_DIR}
   read only = no
   browseable = yes
   create mask = 0644
   directory mask = 0755
   vfs objects = acl_xattr
   acl_xattr:ignore system acls = yes
   store dos attributes = yes
EOF
	testparm -s > /dev/null 2>&1 || fail "testparm rejected the generated smb.conf"
	local user pass
	for user in "${SAMBA_USERS[@]}"; do
		id "${user}" > /dev/null 2>&1 || sudo useradd -M -s /usr/sbin/nologin "${user}"
		pass=$(password_of "${user}")
		printf '%s\n%s\n' "${pass}" "${pass}" | sudo smbpasswd -a -s "${user}" > /dev/null
		printf 'username = %s\npassword = %s\ndomain = %s\n' "${user}" "${pass}" "${NETBIOS}" > "$(smb_auth "${user}")"
	done
	sudo systemctl restart smbd

	step "share content"
	local m="${WORK}/media"
	mkdir -p "${m}"
	media smb-g1 "${m}/g1.webm"
	media smb-z "${m}/z.webm"
	media smb-fremd "${m}/fremd.webm"
	media smb-a1 "${m}/a1.webm"
	media smb-c1 "${m}/c1.webm"
	media smb-doppelt "${m}/doppelt.webm"
	media smb-gesperrt "${m}/gesperrt.webm"
	media smb-x "${m}/x.webm"
	media smb-widerruf "${m}/widerruf.webm"
	# A file below the 64 KiB of the read proof.
	ffmpeg -hide_banner -loglevel error -y -f lavfi -i sine=frequency=330:duration=1 \
		-c:a libopus -b:a 16k -metadata comment=avs-smb-klein "${m}/klein.ogg"
	[ "$(stat -c %s "${m}/klein.ogg")" -lt 65536 ] || fail "klein.ogg is not below 64 KiB"

	put_share "${m}/g1.webm" gemeinsam/g1.webm root 0644
	put_share "${m}/z.webm" gemeinsam/z.webm root 0644
	put_share "${m}/fremd.webm" gemeinsam/fremd.webm root 0644
	put_share "${m}/klein.ogg" gemeinsam/klein.ogg root 0644
	put_share "${m}/a1.webm" nur-ana/a1.webm ana 0600
	sudo chown ana:ana "${SHARE_DIR}/nur-ana"
	sudo chmod 0700 "${SHARE_DIR}/nur-ana"
	# One medium only cem reads: the counter control of the vanish phase.
	put_share "${m}/c1.webm" nur-cem/c1.webm cem 0600
	sudo chown cem:cem "${SHARE_DIR}/nur-cem"
	sudo chmod 0700 "${SHARE_DIR}/nur-cem"
	put_share "${m}/doppelt.webm" doppelt/a.webm root 0644
	put_share "${m}/doppelt.webm" doppelt/b.webm root 0644
	put_share "${m}/gesperrt.webm" gesperrt.webm ana 0644
	# x lives only in archiv-spaeter/, z also in gemeinsam/ (D-02-04).
	put_share "${m}/x.webm" archiv-spaeter/x.webm root 0644
	put_share "${m}/z.webm" archiv-spaeter/z.webm root 0644
	# Readable for everyone until revoke_cem (D-02-12).
	put_share "${m}/widerruf.webm" widerruf.webm ana 0644
	sudo find "${SHARE_DIR}" -mindepth 1 -maxdepth 1 -type d ! -name 'nur-*' -exec chmod 0755 {} +

	local up=0
	for _ in $(seq 1 30); do
		if smbclient -L //127.0.0.1 -A "$(smb_auth ana)" > /dev/null 2>&1; then
			up=1
			break
		fi
		sleep 1
	done
	[ "${up}" = 1 ] || fail "smbd did not answer on 127.0.0.1:445"
	# The A6 case: ben sees gesperrt.webm, Samba refuses to give him its bytes.
	deny_read gesperrt.webm ben
	smbcacls "${SMB_URL}" gesperrt.webm -A "$(smb_auth ana)" > /dev/null || fail "smbcacls could not read the ACL back"
}

# -- Nextcloud ------------------------------------------------------------------

add_users() {
	local user
	for user in "$@"; do
		OC_PASS="$(password_of "${user}")" occ user:add --password-from-env "${user}" > /dev/null
	done
}

mount_id_of() {
	# files_external:create answers "Storage created with id N".
	grep -oE '[0-9]+' <<< "$1" | tail -n 1
}

smb_options=(-c host=127.0.0.1 -c share=Medien -c domain="${NETBIOS}" -c timeout=20)

# create_m1 USER...: the share with "Log-in credentials, save in database" for
# all given users. If the credentials store stays empty after the first login
# of each user, one personal mount per user with fixed credentials replaces it
# (same share, same view), and the log says so.
create_m1() {
	local created id user stored
	created=$(occ files_external:create /SMB smb password::logincredentials -c root= "${smb_options[@]}")
	id=$(mount_id_of "${created}")
	[ -n "${id}" ] || fail "files_external:create returned no mount id for /SMB"
	for user in "$@"; do
		occ files_external:applicable "${id}" --add-user "${user}" > /dev/null
	done
	occ files_external:option "${id}" enable_sharing true > /dev/null
	for user in "$@"; do
		echo "first login of ${user}: HTTP $(dav_login "${user}")"
		dav_login "${user}" SMB > /dev/null
	done
	stored=$(sql "SELECT COUNT(*) FROM oc_storages_credentials WHERE identifier='password::logincredentials/credentials'")
	if [ "${stored}" = "$#" ]; then
		set_id M1_MODE logincredentials
		set_id M1_ID "${id}"
		return
	fi
	echo "NOTE: ${stored} of $# login credentials stored, falling back to one personal mount per user (password::password)"
	occ files_external:delete --yes "${id}" > /dev/null
	occ config:app:set files_external allow_user_mounting --value=yes > /dev/null
	set_id M1_MODE personal
	local ids=""
	for user in "$@"; do
		created=$(occ files_external:create --user="${user}" /SMB smb password::password -c root= \
			"${smb_options[@]}" -c user="${user}" -c password="$(password_of "${user}")")
		id=$(mount_id_of "${created}")
		[ -n "${id}" ] || fail "files_external:create returned no personal mount id"
		occ files_external:option "${id}" enable_sharing true > /dev/null
		set_id "M1_ID_$(tr '[:lower:]' '[:upper:]' <<< "${user}")" "${id}"
		ids="${ids:+${ids} }${id}"
		dav_login "${user}" SMB > /dev/null
	done
	set_id M1_ID "${ids}"
}

install_groupfolders() {
	if occ app:install groupfolders --force; then
		echo "groupfolders came from the app store"
	else
		local tag=''
		case "${SERVER_VERSION:-}" in
			stable33) tag='v21.0.15' ;;
			stable34) tag='v22.0.6' ;;
		esac
		if [ -n "${tag}" ]; then
			curl -sfSL -o "${WORK}/groupfolders.tar.gz" \
				"https://github.com/nextcloud-releases/groupfolders/releases/download/${tag}/groupfolders-${tag}.tar.gz"
			tar -xzf "${WORK}/groupfolders.tar.gz" -C apps
			echo "groupfolders came from the tarball ${tag}"
		fi
	fi
	occ app:enable -f groupfolders
}

storage_of() {
	# storage_of USER MOUNTPOINT: numeric storage id out of the mount cache.
	sql "SELECT storage_id FROM oc_mounts WHERE user_id='$1' AND mount_point='/$1/files/$2/'" | head -n 1
}

record_ids() {
	step "file ids"
	local user path
	for user in ana ben cem; do
		for path in SMB/gemeinsam/g1.webm SMB/gemeinsam/z.webm SMB/gemeinsam/fremd.webm SMB/gemeinsam/klein.ogg \
			SMB/doppelt/a.webm SMB/doppelt/b.webm SMB/gesperrt.webm SMB/archiv-spaeter/x.webm \
			SMB/archiv-spaeter/z.webm SMB/widerruf.webm; do
			record "${user}" "${path}"
		done
		set_id "STORAGE_SMB_$(tr '[:lower:]' '[:upper:]' <<< "${user}")" "$(storage_of "${user}" SMB)"
	done
	record ana SMB/nur-ana/a1.webm
	record cem SMB/nur-cem/c1.webm
	# The session mount: in the background there are no credentials, so the
	# file ids may exist only from a request of ana (neverFetched in plan 04).
	record_soft ana SMB-Sitzung/gemeinsam/g1.webm
	record_soft ana SMB-Sitzung/gesperrt.webm
	for path in SMB-Teil/g1.webm SMB-Teil/z.webm SMB-Teil/fremd.webm SMB-Teil/klein.ogg \
		Lokal/l1.webm Lokal/l2.webm S3/s1.webm S3/s2.webm \
		teilen.webm papierkorb.webm ueberschreiben.webm sperre.webm umbenennen.webm kopieren.webm \
		wandern.webm taggen.webm privat/p.webm Team/t.webm Team/frei/f.webm Team/intern/i.webm; do
		record ana "${path}"
	done
	set_id STORAGE_SMB_TEIL_ANA "$(storage_of ana SMB-Teil)"
	record cem Lokal/l1.webm
	record ben teilen.webm
	record cem teilen.webm
	record eva teilen.webm
	record dan gemeinsam/g1.webm
	record dan dan.webm
	record eva eva.webm
	record fritz fritz.webm
	record ben Team/t.webm
	record ben Team/frei/f.webm
}

cmd_part_a() {
	: "${NC_URL:?NC_URL is required}" "${S3_ACCESS_KEY:?}" "${S3_SECRET_KEY:?}" "${S3_PORT:?}"
	: > "${IDS_ENV}"

	step "users and groups"
	add_users "${NC_USERS[@]}"
	occ group:add team > /dev/null
	occ group:adduser team ana
	occ group:adduser team ben
	occ group:add extern > /dev/null
	occ group:adduser extern fritz

	step "M1 /SMB, log-in credentials saved in the database"
	create_m1 ana ben cem

	step "M2 /SMB-Sitzung, log-in credentials saved in the session"
	local created
	created=$(occ files_external:create /SMB-Sitzung smb password::sessioncredentials -c root= "${smb_options[@]}")
	set_id M2_ID "$(mount_id_of "${created}")"
	occ files_external:applicable "$(get_id M2_ID)" --add-user ana > /dev/null
	echo "ana opens the session mount: HTTP $(dav_login ana SMB-Sitzung)"

	step "M3 /SMB-Teil, the same share with the root gemeinsam"
	created=$(occ files_external:create /SMB-Teil smb password::password -c root=gemeinsam "${smb_options[@]}" \
		-c user=ana -c password="$(password_of ana)")
	set_id M3_ID "$(mount_id_of "${created}")"
	occ files_external:applicable "$(get_id M3_ID)" --add-user ana > /dev/null

	step "M4 /Lokal, a local external storage"
	occ config:system:set files_external_allow_create_new_local --value=true --type=boolean > /dev/null
	mkdir -p "${LOCAL_DIR}"
	chmod 0755 "${LOCAL_DIR}"
	media lokal-1 "${LOCAL_DIR}/l1.webm"
	media lokal-2 "${LOCAL_DIR}/l2.webm"
	chmod 0644 "${LOCAL_DIR}"/*.webm
	created=$(occ files_external:create /Lokal local null::null -c datadir="${LOCAL_DIR}")
	set_id M4_ID "$(mount_id_of "${created}")"
	occ files_external:applicable "$(get_id M4_ID)" --add-user ana --add-user cem > /dev/null

	step "M5 /S3, an S3 bucket"
	created=$(occ files_external:create /S3 amazons3 amazons3::accesskey -c bucket="${S3_BUCKET}" \
		-c hostname=localhost -c port="${S3_PORT}" -c use_ssl=false -c use_path_style=true \
		-c region=us-east-1 -c key="${S3_ACCESS_KEY}" -c secret="${S3_SECRET_KEY}")
	set_id M5_ID "$(mount_id_of "${created}")"
	occ files_external:applicable "$(get_id M5_ID)" --add-user ana > /dev/null
	local mount
	for mount in M3_ID M4_ID M5_ID; do
		occ files_external:verify "$(get_id "${mount}")" | tee "${WORK}/verify-${mount}.txt"
		grep -q 'status: ok' "${WORK}/verify-${mount}.txt" || fail "the mount ${mount} is not available"
	done
	local m="${WORK}/media"
	mkdir -p "${m}"
	media s3-1 "${m}/s1.webm"
	media s3-2 "${m}/s2.webm"
	dav_put ana S3/s1.webm "${m}/s1.webm"
	dav_put ana S3/s2.webm "${m}/s2.webm"

	step "homes"
	for name in teilen papierkorb ueberschreiben sperre umbenennen kopieren wandern taggen; do
		media "home-${name}" "${m}/${name}.webm"
		dav_put ana "${name}.webm" "${m}/${name}.webm"
	done
	dav_mkcol ana privat
	media home-privat "${m}/p.webm"
	dav_put ana privat/p.webm "${m}/p.webm"
	# dan's own content; reattach puts the same bytes into ana's home (D-02-13).
	media home-dan "${WORK}/dan.webm"
	dav_put dan dan.webm "${WORK}/dan.webm"
	media home-eva "${m}/eva.webm"
	dav_put eva eva.webm "${m}/eva.webm"
	media home-fritz "${m}/fritz.webm"
	dav_put fritz fritz.webm "${m}/fritz.webm"

	step "team folder with ACL"
	install_groupfolders
	local folder
	folder=$(occ groupfolders:create Team)
	[[ "${folder}" =~ ^[0-9]+$ ]] || fail "groupfolders:create returned no folder id"
	set_id TEAM_FOLDER_ID "${folder}"
	occ groupfolders:group "${folder}" team read write share delete
	occ groupfolders:permissions "${folder}" --enable
	dav_mkcol ana Team/frei
	dav_mkcol ana Team/intern
	media team-t "${m}/t.webm"
	media team-f "${m}/f.webm"
	media team-i "${m}/i.webm"
	dav_put ana Team/t.webm "${m}/t.webm"
	dav_put ana Team/frei/f.webm "${m}/f.webm"
	dav_put ana Team/intern/i.webm "${m}/i.webm"
	occ groupfolders:permissions "${folder}" --user ben frei -- +read -share
	occ groupfolders:permissions "${folder}" --user ben intern -- -read

	step "shares"
	share ana /teilen.webm ben 17
	share ben /teilen.webm cem 1
	share ana /SMB/gemeinsam dan 1
	share ana /teilen.webm eva 1

	step "files_accesscontrol rule on the tag avs-sperre"
	local sperre harmless
	sperre=$(system_tag avs-sperre)
	harmless=$(system_tag avs-harmlos)
	[[ "${sperre}" =~ ^[0-9]+$ && "${harmless}" =~ ^[0-9]+$ ]] || fail "a system tag could not be created"
	set_id TAG_SPERRE "${sperre}"
	set_id TAG_HARMLOS "${harmless}"
	jq -n --arg tag "${sperre}" '{
		class: "OCA\\FilesAccessControl\\Operation", name: "", operation: "deny",
		entity: "OCA\\WorkflowEngine\\Entity\\File", events: [],
		checks: [{class: "OCA\\WorkflowEngine\\Check\\FileSystemTags", operator: "is", value: $tag}]
	}' > "${WORK}/rule.json"
	ocs admin -H 'Content-Type: application/json' --data @"${WORK}/rule.json" \
		-X POST "${NC_URL}/ocs/v2.php/apps/workflowengine/api/v1/workflows/global" > /dev/null

	step "exclusions before the first run (D-02-05)"
	exclude --user=eva
	exclude --group=extern
	exclude --folder=privat

	step "scan"
	occ files:scan --all > /dev/null
	record_ids
}

cmd_part_b() {
	step "scan after the registration"
	occ files:scan --all > /dev/null
	record_ids
	if has_command exclude; then
		occ audio_video_search:exclude --list | tee occ-exclusions.txt
	else
		echo "occ audio_video_search:exclude is missing" | tee occ-exclusions.txt
	fi
}

cmd_control() {
	: > "${IDS_ENV}"
	step "control topology"
	add_users ana ben
	create_m1 ana ben
	occ files:scan --all > /dev/null
	record ana SMB/gesperrt.webm
	record ben SMB/gesperrt.webm
	set_id STORAGE_SMB_ANA "$(storage_of ana SMB)"
	set_id STORAGE_SMB_BEN "$(storage_of ben SMB)"
}

# -- operations of the phases ---------------------------------------------------

upload_new() {
	local stamp
	stamp=$(date +%s)
	media "neu-${stamp}" "${WORK}/neu.webm"
	set_id UPLOAD_AT "${stamp}"
	dav_put ana "neu-${stamp}.webm" "${WORK}/neu.webm"
	record ana "neu-${stamp}.webm"
	set_id UPLOAD_ID "$(get_id "$(id_key ana "neu-${stamp}.webm")")"
}

overwrite() {
	media "ueberschreiben-$(date +%s)" "${WORK}/ueberschreiben.webm"
	set_id OVERWRITE_AT "$(date +%s)"
	dav_put ana ueberschreiben.webm "${WORK}/ueberschreiben.webm"
}

copy_in_home() {
	curl -sfS -u "ana:$(password_of ana)" -X COPY -H "Destination: $(dav_url ana kopie.webm)" \
		"$(dav_url ana kopieren.webm)"
	record ana kopie.webm
}

rename_in_home() {
	curl -sfS -u "ana:$(password_of ana)" -X MOVE -H "Destination: $(dav_url ana umbenannt.webm)" \
		"$(dav_url ana umbenennen.webm)"
	record ana umbenannt.webm
}

tag_file() {
	assign_tag ana "$(get_id ID_ANA_TAGGEN_WEBM)" "$(get_id TAG_HARMLOS)"
}

move_home_to_team() {
	curl -sfS -u "ana:$(password_of ana)" -X MOVE -H "Destination: $(dav_url ana Team/wandern.webm)" \
		"$(dav_url ana wandern.webm)"
	record ana Team/wandern.webm
}

trash_file() {
	curl -sfS -u "ana:$(password_of ana)" -X DELETE "$(dav_url ana papierkorb.webm)"
}

restore_file() {
	local listing href
	listing=$(curl -sfS -u "ana:$(password_of ana)" -X PROPFIND -H 'Depth: 1' \
		"${NC_URL}/remote.php/dav/trashbin/ana/trash/")
	href=$(grep -oE '<d:href>[^<]*papierkorb\.webm\.d[0-9]+</d:href>' <<< "${listing}" | head -n 1 \
		| sed -e 's|<d:href>||' -e 's|</d:href>||')
	[ -n "${href}" ] || fail "papierkorb.webm is not in the trash bin"
	curl -sfS -u "ana:$(password_of ana)" -X MOVE \
		-H "Destination: ${NC_URL}/remote.php/dav/trashbin/ana/restore/papierkorb.webm" "${NC_URL}${href}"
	record ana papierkorb.webm
}

# The rule denies every web access to a file with the tag, writes through
# WebDAV as well. So the change comes from the command line: new bytes into
# the data directory and a scan of that one file, which raises the cache event
# the discovery reacts to.
access_control() {
	assign_tag ana "$(get_id ID_ANA_SPERRE_WEBM)" "$(get_id TAG_SPERRE)"
	media "sperre-$(date +%s)" "${WORK}/sperre.webm"
	cp "${WORK}/sperre.webm" "${DATADIR}/ana/files/sperre.webm"
	occ files:scan --path=ana/files/sperre.webm > /dev/null
}

exclude_user_after() {
	exclude --user=ben
}

exclude_storage_after() {
	exclude --storage="$(get_id M3_ID)"
}

exclude_after() {
	exclude --folder=archiv-spaeter
}

revoke_cem() {
	deny_read widerruf.webm cem
}

vanish_cem() {
	if [ "$(get_id M1_MODE)" = personal ]; then
		occ files_external:delete --yes "$(get_id M1_ID_CEM)" > /dev/null
	else
		occ files_external:applicable "$(get_id M1_ID)" --remove-user cem > /dev/null
	fi
}

delete_dan() {
	occ user:delete dan
}

# Replaced on the NAS itself, Nextcloud is not told (RESEARCH Befund 5).
foreign_change() {
	media "fremd-$(date +%s)" "${WORK}/fremd.webm"
	set_id FOREIGN_AT "$(date +%s)"
	put_share "${WORK}/fremd.webm" gemeinsam/fremd.webm root 0644
}

reattach() {
	dav_put ana dan-kopie.webm "${WORK}/dan.webm"
	record ana dan-kopie.webm
}

# -- phase search-parity (plan 03-17) ---------------------------------------------
#
# The speech clip (AVS_SPEECH_DE) at the places where the right to read differs;
# parity.sh judges the hits against WebDAV. After the phases of phase 2 ben is
# excluded (exclude-user-after), cem has no SMB mount any more (vanish), dan is
# deleted, eva and fritz were excluded before the first run. So Samba refuses
# the bytes to ana herself, and cem joins the team for the ACL of the team
# folder: +read -share on one subfolder, -read on the other.
#
# parity_place puts every copy in place; parity_revoke later takes away what
# was readable before (the share to cem, the second copy of ana into the
# trash), after parity.sh before showed both as hits.

parity_place() {
	local clip="${AVS_SPEECH_DE:?AVS_SPEECH_DE is required}" dir="${WORK}/parity" folder share
	[ -s "${clip}" ] || fail "the speech clip is missing"
	mkdir -p "${dir}"
	folder=$(get_id TEAM_FOLDER_ID)

	step "ana home, shared with cem (revoked later)"
	dav_put ana rede-geteilt.wav "${clip}"
	record ana rede-geteilt.wav
	share=$(ocs ana -X POST "${NC_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares" \
		--data-urlencode 'path=/rede-geteilt.wav' --data-urlencode 'shareWith=cem' \
		--data-urlencode 'shareType=0' --data-urlencode 'permissions=1' | jq -r '.ocs.data.id // empty')
	[[ "${share}" =~ ^[0-9]+$ ]] || fail "the share of the shared copy has no id"
	set_id PARITY_SHARE_ID "${share}"

	step "ana home, a second copy (into the trash later)"
	dav_put ana rede-papierkorb.wav "${clip}"
	record ana rede-papierkorb.wav

	step "team folder: cem with +read -share on one subfolder, -read on the other"
	occ group:adduser team cem
	dav_mkcol ana Team/rede-frei
	dav_mkcol ana Team/rede-intern
	dav_put ana Team/rede-frei/rede.wav "${clip}"
	dav_put ana Team/rede-intern/rede.wav "${clip}"
	record ana Team/rede-frei/rede.wav
	record ana Team/rede-intern/rede.wav
	occ groupfolders:permissions "${folder}" --user cem rede-frei -- +read -share
	occ groupfolders:permissions "${folder}" --user cem rede-intern -- -read

	step "SMB: Samba refuses the bytes to ana, set before Nextcloud ever sees the file"
	put_share "${clip}" rede-gesperrt.wav ana 0644
	deny_read rede-gesperrt.wav ana
	record ana SMB/rede-gesperrt.wav

	# As in access_control: the rule denies every web access to a tagged file,
	# so a tone goes in first, then the tag, then the clip from the command line.
	step "files_accesscontrol: a tone, the tag avs-sperre, then the clip"
	ffmpeg -hide_banner -loglevel error -y -f lavfi -i sine=frequency=550:duration=5 \
		-metadata comment=avs-rede-sperre "${dir}/ton.wav"
	dav_put ana rede-sperre.wav "${dir}/ton.wav"
	record ana rede-sperre.wav
	assign_tag ana "$(get_id ID_ANA_REDE_SPERRE_WAV)" "$(get_id TAG_SPERRE)"
	cp "${clip}" "${DATADIR}/ana/files/rede-sperre.wav"
	occ files:scan --path=ana/files/rede-sperre.wav > /dev/null

	step "eva (excluded before the first run): own copy, shared with cem"
	dav_put eva rede-eva.wav "${clip}"
	record eva rede-eva.wav
	share eva /rede-eva.wav cem 1
}

parity_revoke() {
	ocs ana -X DELETE "${NC_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares/$(get_id PARITY_SHARE_ID)" > /dev/null
	curl -sfS -u "ana:$(password_of ana)" -X DELETE "$(dav_url ana rede-papierkorb.wav)"
}

OPERATIONS=(upload_new overwrite copy_in_home rename_in_home tag_file move_home_to_team trash_file
	restore_file access_control exclude_user_after exclude_storage_after exclude_after revoke_cem
	vanish_cem delete_dan foreign_change reattach parity_place parity_revoke)

main() {
	local command="${1:-}"
	case "${command}" in
		samba) cmd_samba ;;
		part-a) cmd_part_a ;;
		part-b) cmd_part_b ;;
		control) cmd_control ;;
		*)
			local operation
			for operation in "${OPERATIONS[@]}"; do
				if [ "${operation}" = "${command}" ]; then
					step "operation ${operation}"
					"${operation}"
					return
				fi
			done
			fail "usage: topology.sh samba|part-a|part-b|control|<operation>"
			;;
	esac
}

main "$@"
