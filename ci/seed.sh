#!/usr/bin/env bash
# The seed of the integration proof, on a throwaway Nextcloud in CI only.
#
# Users, a team folder, two shares and the test media, all over the real
# paths (occ, WebDAV, the sharing API), and then one test result per media
# file through occ audio_video_search:sample, which makes the container read
# the file through the content gateway like a real job does.
#
#   alice    owns the media files
#   bob      receives tone-90s.webm and locked.webm (download switched off)
#   carol    member of the group "team", reads the team folder "Team"
#   mallory  reads nothing of the above
#   dora     admin and member of "team", receives locked.webm and broken.webm,
#            high contrast theme, only for the screenshots of the high
#            contrast project
#   elke     like dora, language de_DE, for the German screenshots
#   fleur    like dora, language fr_FR, for the French screenshots
#
# The passwords come out of the job variables of the throwaway instance, never
# out of repository secrets. The file ids land in fileids.env for the later
# steps; this file is the only place that pairs an id with a test file.
#
# usage: NC_URL=... OCC=./occ MEDIA_DIR=... ALICE_PASS=... BOB_PASS=...
#        CAROL_PASS=... MALLORY_PASS=... DORA_PASS=... ELKE_PASS=...
#        FLEUR_PASS=... ci/seed.sh
set -euo pipefail

: "${NC_URL:?NC_URL is required}"
: "${OCC:?OCC is required}"
: "${MEDIA_DIR:?MEDIA_DIR is required (output of ci/make-testmedia.sh)}"
: "${ALICE_PASS:?}" "${BOB_PASS:?}" "${CAROL_PASS:?}" "${MALLORY_PASS:?}" "${DORA_PASS:?}"
: "${ELKE_PASS:?}" "${FLEUR_PASS:?}"
FILEIDS_ENV="${FILEIDS_ENV:-$(dirname "$0")/fileids.env}"
SERVER_VERSION="${SERVER_VERSION:-}"
AT_SECONDS=42
TEAM_FOLDER=Team
TEAM_GROUP=team

occ() {
	# shellcheck disable=SC2086 # OCC may carry arguments, for example "php occ".
	${OCC} "$@"
}

dav() {
	printf '%s/remote.php/dav/files/%s/%s' "${NC_URL}" "$1" "$2"
}

# -- users and the group ------------------------------------------------------

add_user() {
	OC_PASS="$2" occ user:add --password-from-env "$1"
}
add_user alice "${ALICE_PASS}"
add_user bob "${BOB_PASS}"
add_user carol "${CAROL_PASS}"
add_user mallory "${MALLORY_PASS}"
add_user dora "${DORA_PASS}"
add_user elke "${ELKE_PASS}"
add_user fleur "${FLEUR_PASS}"

occ group:add "${TEAM_GROUP}"
occ group:adduser "${TEAM_GROUP}" alice
occ group:adduser "${TEAM_GROUP}" carol
for reviewer in dora elke fleur; do
	occ group:adduser "${TEAM_GROUP}" "${reviewer}"
	occ group:adduser admin "${reviewer}"
done
occ user:setting dora theming enabled-themes '["light-highcontrast"]'
# Set before the first login: Nextcloud stores the browser language as the
# user language on the first request of a user who has none.
occ user:setting elke core lang de_DE
occ user:setting elke core locale de_DE
occ user:setting fleur core lang fr
occ user:setting fleur core locale fr_FR

# -- the team folder ------------------------------------------------------------

# The app store first; the tarball of the matching major line if the store
# does not deliver inside the job (the mapping as in Findling, read 2026-09-03).
if occ app:install groupfolders --force; then
	echo "groupfolders came from the app store"
else
	case "${SERVER_VERSION}" in
		stable33) tag='v21.0.15' ;;
		stable34) tag='v22.0.6' ;;
		*) tag='' ;;
	esac
	if [ -n "${tag}" ]; then
		curl -sfSL -o "${RUNNER_TEMP:-/tmp}/groupfolders.tar.gz" \
			"https://github.com/nextcloud-releases/groupfolders/releases/download/${tag}/groupfolders-${tag}.tar.gz"
		tar -xzf "${RUNNER_TEMP:-/tmp}/groupfolders.tar.gz" -C apps
		echo "groupfolders came from the tarball ${tag}"
	fi
fi
occ app:enable -f groupfolders

# groupfolders:create writes the id of the new folder and nothing else.
folder_id=$(occ groupfolders:create "${TEAM_FOLDER}")
occ groupfolders:group "${folder_id}" "${TEAM_GROUP}" read write share delete

# -- the media ------------------------------------------------------------------

upload() {
	local user="$1" pass="$2" source="$3" target="$4"
	curl -sfS -u "${user}:${pass}" -T "${source}" "$(dav "${user}" "${target}")"
}

broken="$(mktemp)"
head -c 512 /dev/urandom > "${broken}"

upload alice "${ALICE_PASS}" "${MEDIA_DIR}/tone-90s.webm" tone-90s.webm
upload alice "${ALICE_PASS}" "${MEDIA_DIR}/tone-90s.ogg" tone-90s.ogg
upload alice "${ALICE_PASS}" "${MEDIA_DIR}/tone-90s.webm" "${TEAM_FOLDER}/tone-90s.webm"
upload alice "${ALICE_PASS}" "${broken}" broken.webm
upload alice "${ALICE_PASS}" "${MEDIA_DIR}/tone-90s.webm" locked.webm
rm -f "${broken}"

# -- the shares -----------------------------------------------------------------

share() {
	curl -sfS -u "alice:${ALICE_PASS}" \
		-H 'OCS-APIRequest: true' -H 'Accept: application/json' \
		-X POST "${NC_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares" \
		"$@" > /dev/null
}

share --data-urlencode 'path=/tone-90s.webm' --data-urlencode 'shareWith=bob' \
	--data-urlencode 'shareType=0' --data-urlencode 'permissions=1'
share --data-urlencode 'path=/locked.webm' --data-urlencode 'shareWith=bob' \
	--data-urlencode 'shareType=0' --data-urlencode 'permissions=1' \
	--data-urlencode 'attributes=[{"scope":"permissions","key":"download","value":false}]'
# The review users reach every banner of the playback page: the same two
# shares as a recipient, next to the team folder.
for reviewer in dora elke fleur; do
	share --data-urlencode 'path=/locked.webm' --data-urlencode "shareWith=${reviewer}" 		--data-urlencode 'shareType=0' --data-urlencode 'permissions=1' 		--data-urlencode 'attributes=[{"scope":"permissions","key":"download","value":false}]'
	share --data-urlencode 'path=/broken.webm' --data-urlencode "shareWith=${reviewer}" 		--data-urlencode 'shareType=0' --data-urlencode 'permissions=1'
done
# Without this a share without download may still be viewed; with it the
# playback page shows the hint banner instead of the medium (01-RESEARCH.md,
# Pitfall 2).
occ config:app:set core shareapi_allow_view_without_download --value=no --type=boolean

# The mount of a recipient lands in the mount cache with a scan.
occ files:scan --all > /dev/null

# -- the file ids ---------------------------------------------------------------

file_id() {
	curl -sfS -u "alice:${ALICE_PASS}" -X PROPFIND -H 'Depth: 0' \
		--data '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>' \
		"$(dav alice "$1")" | sed -n 's|.*<oc:fileid>\([0-9]*\)</oc:fileid>.*|\1|p'
}

FILEID_WEBM=$(file_id tone-90s.webm)
FILEID_OGG=$(file_id tone-90s.ogg)
FILEID_TEAM=$(file_id "${TEAM_FOLDER}/tone-90s.webm")
FILEID_BROKEN=$(file_id broken.webm)
FILEID_LOCKED=$(file_id locked.webm)

for id in "${FILEID_WEBM}" "${FILEID_OGG}" "${FILEID_TEAM}" "${FILEID_BROKEN}" "${FILEID_LOCKED}"; do
	[[ "${id}" =~ ^[0-9]+$ ]] || { echo "a file id could not be read"; exit 1; }
done

{
	echo "FILEID_WEBM=${FILEID_WEBM}"
	echo "FILEID_OGG=${FILEID_OGG}"
	echo "FILEID_TEAM=${FILEID_TEAM}"
	echo "FILEID_BROKEN=${FILEID_BROKEN}"
	echo "FILEID_LOCKED=${FILEID_LOCKED}"
} > "${FILEIDS_ENV}"

# -- the test results -----------------------------------------------------------

# One test result per media file at 42 s, read by the container through the
# content gateway as alice. Debug mode must be on, the command refuses otherwise.
for id in "${FILEID_WEBM}" "${FILEID_OGG}" "${FILEID_TEAM}" "${FILEID_BROKEN}" "${FILEID_LOCKED}"; do
	occ audio_video_search:sample "${id}" --at="${AT_SECONDS}" --user=alice
done
# The search shows a test result only while the admin switch is on as well.
occ config:app:set audio_video_search sample_visible --value=true --type=boolean
