#!/usr/bin/env bash
# The state of the other half, as the admin section reads it.
#
# GET /apps/audio_video_search/admin/state is the route behind "Check again":
# it determines the state anew under the signed in admin and stores it, so the
# search of the next minute follows it. The route requires an administrator
# and passes the CSRF check only with the request token or with the header
# OCS-APIRequest (Findling, deploy-harp overview probe, measured on stable33
# to stable35). Two ways in, as there:
#   1. an app password of the admin, from the OCS route core/getapppassword,
#      used as basic auth together with OCS-APIRequest,
#   2. the login form with a session, as the fallback and as the diagnosis
#      when way one dies.
#
# usage: ADMIN_PASS=... [NC_URL=http://localhost:8080] ci/admin-state.sh <out.json>
set -euo pipefail

out="${1:?usage: ci/admin-state.sh <out.json>}"
: "${ADMIN_PASS:?ADMIN_PASS is required}"
NC_URL="${NC_URL:-http://localhost:8080}"
WORK_DIR="${RUNNER_TEMP:-/tmp}"
ROUTE="${NC_URL}/index.php/apps/audio_video_search/admin/state"

has_state() {
	jq -e '.state | type == "string"' "${out}" > /dev/null 2>&1
}

report() {
	echo "admin state: $(jq -c '{state, own, backend, companion, sampleCount}' "${out}")"
}

apppw=$(curl -s -u "admin:${ADMIN_PASS}" -H 'OCS-APIRequest: true' -H 'Accept: application/json' \
	"${NC_URL}/ocs/v2.php/core/getapppassword" | jq -r '.ocs.data.apppassword // empty' 2>/dev/null || true)
if [ -n "${apppw}" ]; then
	# Masked in the log of a GitHub run; harmless elsewhere.
	echo "::add-mask::${apppw}"
	code=$(curl -s -o "${out}" -w '%{http_code}' -u "admin:${apppw}" \
		-H 'OCS-APIRequest: true' -H 'Accept: application/json' "${ROUTE}")
	echo "state via app password: HTTP ${code}"
	if [ "${code}" = "200" ] && has_state; then
		report
		exit 0
	fi
else
	echo "app password: not available, trying the login form"
fi

jar="${WORK_DIR}/avs-admin-cookies.txt"
rm -f "${jar}"
curl -s -c "${jar}" -o "${WORK_DIR}/avs-login.html" "${NC_URL}/index.php/login"
token=$(grep -o 'data-requesttoken="[^"]*"' "${WORK_DIR}/avs-login.html" | head -n 1 | cut -d'"' -f2 || true)
curl -s -b "${jar}" -c "${jar}" -o /dev/null \
	--data-urlencode "user=admin" --data-urlencode "password=${ADMIN_PASS}" \
	--data-urlencode "requesttoken=${token}" "${NC_URL}/index.php/login"
curl -s -b "${jar}" -c "${jar}" -o "${WORK_DIR}/avs-settings.html" "${NC_URL}/index.php/settings/admin"
token=$(grep -o 'data-requesttoken="[^"]*"' "${WORK_DIR}/avs-settings.html" | head -n 1 | cut -d'"' -f2 || true)
code=$(curl -s -b "${jar}" -c "${jar}" -o "${out}" -w '%{http_code}' \
	-H "requesttoken: ${token}" -H 'OCS-APIRequest: true' -H 'Accept: application/json' "${ROUTE}")
echo "state via session: HTTP ${code}, token length ${#token}"
if [ "${code}" = "200" ] && has_state; then
	report
	exit 0
fi
echo "the admin state could not be read; answer head:"
head -c 400 "${out}" || true
echo
exit 1
