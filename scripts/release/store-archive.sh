#!/bin/sh
# Build the store archive of the External App. Taken over from Findling's
# scripts/release/store-archive.sh, reduced to the ExApp half.
#
#   store-archive.sh stage           <stage-dir>
#   store-archive.sh pack            <stage-dir> <archive>
#   store-archive.sh assert-contents <archive>
#
# What the archive carries and why:
#   appinfo/info.xml  byte identical to the working tree, because AppAPI reads the
#                     routes block out of the archive and the store database never
#                     sees it (cmp below)
#   l10n/             AppAPI copies this directory into the apps path at install
#                     time (ExAppArchiveFetcher::installTranslations)
#   img/              the app icon
#   LICENSE, CHANGELOG.md
# No code signature: an ExApp archive has no PHP for the integrity check to see,
# and a signature.json in it is reported as a defect below.
set -eu

APP_ID=$(sed -n 's:.*<id>\(.*\)</id>.*:\1:p' appinfo/info.xml | head -n 1)

usage() {
	echo "usage: store-archive.sh stage           <stage-dir>"
	echo "       store-archive.sh pack            <stage-dir> <archive>"
	echo "       store-archive.sh assert-contents <archive>"
}

stage() {
	app="$1/${APP_ID}"
	mkdir -p "${app}/appinfo"
	cp appinfo/info.xml "${app}/appinfo/info.xml"
	cp -R l10n "${app}/l10n"
	cp -R img "${app}/img"
	cp LICENSE CHANGELOG.md "${app}/"
	cmp appinfo/info.xml "${app}/appinfo/info.xml"
	echo "info.xml is byte identical to the working tree, so AppAPI reads the routes it expects"
	find "${app}" -type f | sort | sed 's/^/  /'
}

assert_no_crlf() {
	offenders=$(find "$1" -type f \( -name '*.xml' -o -name '*.json' -o -name '*.js' -o -name '*.md' -o -name '*.svg' -o -name 'LICENSE' \) \
		-exec sh -c 'for f do tr -d "\r" < "$f" | cmp -s - "$f" || printf "%s\n" "$f"; done' sh {} +)
	if [ -n "${offenders}" ]; then
		echo "these staged files carry a carriage return, check out with LF and build again:"
		printf '%s\n' "${offenders}" | sed 's/^/  /'
		return 1
	fi
	echo "no carriage return in any staged text file"
}

pack() {
	assert_no_crlf "$1/${APP_ID}"
	mkdir -p "$(dirname "$2")"
	tar --numeric-owner --owner=0 --group=0 -czf "$2" -C "$1" "${APP_ID}"
	ls -l "$2"
}

assert_contents() {
	listing="$1.listing"
	fail=0
	tar -tzf "$1" > "${listing}"
	cat "${listing}"
	tops=$(cut -d/ -f1 "${listing}" | sort -u)
	if [ "${tops}" != "${APP_ID}" ]; then
		echo "the top level is '${tops}' and the store needs exactly one directory named ${APP_ID}"
		fail=1
	fi
	for wanted in appinfo/info.xml l10n/de.json l10n/de.js l10n/en.json l10n/en.js l10n/fr.json l10n/fr.js LICENSE; do
		grep -qx "${APP_ID}/${wanted}" "${listing}" || { echo "${wanted} is missing"; fail=1; }
	done
	if grep -qx "${APP_ID}/appinfo/signature.json" "${listing}"; then
		echo "carries a code signature, and an ExApp archive has no PHP for it to cover"
		fail=1
	fi
	for forbidden in tests src scripts .github docs; do
		if grep -q "^${APP_ID}/${forbidden}\(/\|$\)" "${listing}"; then
			echo "contains ${forbidden}, which is development material and must not be released"
			fail=1
		fi
	done
	if grep -Eq '\.(key|pem)$' "${listing}"; then
		echo "contains a key file"
		fail=1
	fi
	return "${fail}"
}

command="${1:-}"
[ "$#" -gt 0 ] && shift
case "${command}" in
	stage) [ "$#" -eq 1 ] || { usage; exit 1; }; stage "$1" ;;
	pack) [ "$#" -eq 2 ] || { usage; exit 1; }; pack "$1" "$2" ;;
	assert-contents) [ "$#" -eq 1 ] || { usage; exit 1; }; assert_contents "$1" ;;
	*) usage; exit 1 ;;
esac
