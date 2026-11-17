#!/usr/bin/env bash
# Register the backend again at a version of choice, on the volume it had.
#
# The drift steps of .github/workflows/deploy-harp.yml need a container that
# reports a version other than the one of the PHP app. The image stays the
# image of this commit: AppAPI hands <version> of the info.xml to the
# container as APP_VERSION, and that value is all the lockstep check compares
# (config.app_version). The same image is pushed once more with the version
# as its tag, so the registration names an image tag that fits what it claims.
#
# The registration that is there goes first, through app_api:app:unregister
# without the data flag. AppAPI then asks HaRP to remove the container and to
# keep the volume nc_app_<id>_data (app_api lib/Command/ExApp/Unregister.php,
# stable33 to stable35; HaRP haproxy_agent.py deletes the volume only on
# remove_data and reuses an existing one at create), so state.db and the index
# come back with the new container. Without a registration (after the step
# that unregistered the backend on purpose) the script only registers.
#
# At the end the script fails on its own if the container does not run the
# version it was asked for, both in its environment and in GET /status.
#
# usage: INFO_XML=<info.xml pointed at the local registry> ADMIN_PASS=...
#        [OCC=./occ, a path without arguments] ci/redeploy.sh <major.minor.patch>
set -euo pipefail

version="${1:-}"
: "${INFO_XML:?INFO_XML is required (the info.xml pointed at the local registry)}"
: "${ADMIN_PASS:?ADMIN_PASS is required}"
OCC="${OCC:-./occ}"
BACKEND_APP_ID="${BACKEND_APP_ID:-audio_video_search_backend}"
LOCAL_REGISTRY="${LOCAL_REGISTRY:-localhost:5000}"
LOCAL_IMAGE_TAG="${LOCAL_IMAGE_TAG:-citest}"
DAEMON="${DAEMON:-harp_proxy_host}"
EXAPPS_URL="${EXAPPS_URL:-http://localhost:8090}"
WORK_DIR="${RUNNER_TEMP:-/tmp}"

if [[ ! "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
	echo "usage: ci/redeploy.sh <major.minor.patch>, got '${version}'"
	exit 1
fi

image="${LOCAL_REGISTRY}/${BACKEND_APP_ID}"
docker tag "${image}:${LOCAL_IMAGE_TAG}" "${image}:${version}"
docker push "${image}:${version}" > /dev/null

info="${WORK_DIR}/info-${version}.xml"
sed -e "s|<version>[^<]*</version>|<version>${version}</version>|" \
	-e "s|<image-tag>[^<]*</image-tag>|<image-tag>${version}</image-tag>|" \
	"${INFO_XML}" > "${info}"
# Exactly one version element and one image tag, both rewritten; anything
# else means the sed hit a line it was not aimed at.
if [ "$(grep -c '<version>[^<]*</version>' "${info}")" != "1" ] \
	|| [ "$(grep -c "<version>${version}</version>" "${info}")" != "1" ] \
	|| [ "$(grep -c "<image-tag>${version}</image-tag>" "${info}")" != "1" ]; then
	echo "${info} does not carry exactly one version and one image tag ${version}"
	exit 1
fi

# The list goes into a variable first: grep -q on a pipe ends the pipe early,
# and with pipefail that reads as a failure of occ.
registered=$(timeout 30 "${OCC}" app_api:app:list)
if grep -q "${BACKEND_APP_ID}" <<<"${registered}"; then
	timeout 300 "${OCC}" app_api:app:unregister "${BACKEND_APP_ID}"
else
	echo "${BACKEND_APP_ID} is not registered, registering only"
fi
timeout 600 "${OCC}" app_api:app:register "${BACKEND_APP_ID}" "${DAEMON}" \
	--info-xml "${info}" --wait-finish

container=$(docker ps --filter "name=nc_app_${BACKEND_APP_ID}" --format '{{.Names}}' | head -n 1)
if [ -z "${container}" ]; then
	echo "the registration at ${version} left no running container"
	docker ps -a
	exit 1
fi
running=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${container}" \
	| sed -n 's/^APP_VERSION=//p' | head -n 1)
if [ "${running}" != "${version}" ]; then
	echo "the container runs APP_VERSION '${running}' while the registration asked for '${version}'"
	exit 1
fi

status_file="${WORK_DIR}/redeploy-status.json"
for _ in $(seq 1 30); do
	code=$(curl -s -o "${status_file}" -w '%{http_code}' -u "admin:${ADMIN_PASS}" \
		"${EXAPPS_URL}/exapps/${BACKEND_APP_ID}/status" || true)
	if [ "${code}" = "200" ] && jq -e --arg v "${version}" '.appVersion == $v' "${status_file}" > /dev/null; then
		echo "${container} redeployed, APP_VERSION and /status say ${version}"
		exit 0
	fi
	sleep 2
done
echo "GET /status did not report appVersion ${version} within 60 s (last HTTP ${code})"
cat "${status_file}" 2>/dev/null || true
exit 1
