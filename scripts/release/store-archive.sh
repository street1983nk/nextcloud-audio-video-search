#!/bin/sh
# The one place that decides what ships in the two store archives (plan 01-10).
# Taken over from Findling's scripts/release/store-archive.sh.
#
# One repository, two apps, two archives:
#   audio_video_search          the PHP app out of php/, code signed inside
#   audio_video_search_backend  the External App, metadata only
#
# The signatures are not here. The code signature belongs INSIDE the PHP app
# archive and the release signature belongs OVER each tarball, so the order is
# stage, code sign, pack, release sign, and both signing steps stay in
# .github/workflows/release.yml next to the secrets they read. That is why
# stage and pack are separate subcommands.
#
# Usage, from the root of the repository:
#   store-archive.sh stage-companion <stage-dir>
#   store-archive.sh stage-backend   <stage-dir>
#   store-archive.sh pack            <stage-dir> <app-id> <archive>
#   store-archive.sh assert-contents <archive> <app-id> <wants-signature 0|1>
#
# POSIX sh, no bashisms. backend/tests/test_release_archives.py holds the
# include lists and runs both staging subcommands.
set -eu

COMPANION_ID=audio_video_search
BACKEND_ID=audio_video_search_backend

usage() {
	echo "usage: store-archive.sh stage-companion <stage-dir>"
	echo "       store-archive.sh stage-backend   <stage-dir>"
	echo "       store-archive.sh pack            <stage-dir> <app-id> <archive>"
	echo "       store-archive.sh assert-contents <archive> <app-id> <wants-signature 0|1>"
}

# An include list and not an exclude list: a new directory in php/ has to be
# named here before it ships, instead of shipping because nobody remembered
# to exclude it. Left out on purpose: tests and phpunit.xml (the unit suite),
# composer.json (no runtime dependency; it would invite a composer install on
# a production instance), .gitkeep (repository plumbing).
# LICENSE and CHANGELOG.md travel along: the store renders the changelog on the
# release listing.
stage_companion() {
	stage="$1"
	app="${stage}/audio_video_search"
	mkdir -p "${app}"
	for d in appinfo lib templates js css img l10n; do
		cp -R "php/${d}" "${app}/${d}"
	done
	cp LICENSE CHANGELOG.md "${app}/"
	find "${app}" -name '.gitkeep' -delete
	echo "staged tree:"
	find "${app}" -maxdepth 1 -mindepth 1 | sed "s|^${app}/|  |" | sort
}

# info.xml is copied byte for byte and never rewritten, and that is a hard
# requirement: the store transform (pre-info.xslt) drops the routes block, so
# the store database never sees the routes of the container. AppAPI reads
# them back out of this archive at installation time. A rewritten info.xml
# installs an app with an empty route table, and nothing anywhere says so.
# The image is not in the archive: info.xml names it, AppAPI pulls it from
# ghcr.io. LICENSE and CHANGELOG.md travel along as on the other side.
stage_backend() {
	stage="$1"
	app="${stage}/audio_video_search_backend"
	mkdir -p "${app}/appinfo"
	cp backend/appinfo/info.xml "${app}/appinfo/info.xml"
	cp LICENSE CHANGELOG.md "${app}/"
	cmp backend/appinfo/info.xml "${app}/appinfo/info.xml"
	echo "info.xml is byte identical to the working tree, so AppAPI reads the routes it expects"
}

# No carriage return in anything that ships as text. A checkout with
# core.autocrlf would hand one to every file .gitattributes does not pin, and
# the archive would be a different product from the one release.yml builds on
# its Linux runner under the same version. An allowlist of extensions: a
# binary is never looked at, a new kind of text file has to be named here.
assert_no_crlf() {
	stage="$1"
	app="$2"
	offenders=$(
		find "${stage}/${app}" -type f \
			\( -name '*.php' -o -name '*.xml' -o -name '*.js' -o -name '*.json' \
			-o -name '*.css' -o -name '*.md' -o -name '*.svg' -o -name 'LICENSE' \) \
			-exec sh -c '
				for file do
					tr -d "\r" < "${file}" | cmp -s - "${file}" ||
						printf "%s\n" "${file}"
				done
			' sh {} +
	)
	if [ -z "${offenders}" ]; then
		echo "no carriage return in any staged text file"
		return 0
	fi
	echo "these staged text files carry a carriage return, check out with LF and build again:"
	printf '%s\n' "${offenders}" | sed 's/^/  /'
	return 1
}

# Owner and group zero: the uid of a runner has no business in a public
# artefact. A tar.gz is not byte reproducible, so the archive that gets signed
# has to be the archive that gets uploaded; no later step may rebuild it.
pack() {
	stage="$1"
	app="$2"
	archive="$3"
	assert_no_crlf "${stage}" "${app}"
	mkdir -p "$(dirname "${archive}")"
	tar --numeric-owner --owner=0 --group=0 -czf "${archive}" -C "${stage}" "${app}"
	ls -l "${archive}"
}

# The listing is written once into a file and every check reads that file:
# "tar -tzf x | grep -q" lets grep leave early, tar takes SIGPIPE, and the
# answer then depends on the size of the archive (Findling rehearsal 05-18).
assert_contents() {
	archive="$1"
	app="$2"
	wants_signature="$3"
	listing="${archive}.listing"
	fail=0

	tar -tzf "${archive}" > "${listing}"
	echo "${archive}, $(wc -l < "${listing}") entries"
	cat "${listing}"

	tops=$(cut -d/ -f1 "${listing}" | sort -u)
	if [ "${tops}" != "${app}" ]; then
		echo "${archive}: the top level is '${tops}' and the store needs exactly one directory named ${app}"
		fail=1
	fi
	for wanted in appinfo/info.xml LICENSE CHANGELOG.md; do
		grep -qx "${app}/${wanted}" "${listing}" || { echo "${archive}: ${wanted} is missing"; fail=1; }
	done
	if [ "${app}" = "${COMPANION_ID}" ]; then
		for wanted in lib/AppInfo/Application.php l10n/de.json l10n/en.json l10n/fr.json; do
			grep -qx "${app}/${wanted}" "${listing}" || { echo "${archive}: ${wanted} is missing"; fail=1; }
		done
	fi
	if [ "${app}" = "${BACKEND_ID}" ] && [ "$(grep -c -v '/$' "${listing}")" != "3" ]; then
		echo "${archive}: the backend archive carries more than info.xml, LICENSE and CHANGELOG.md"
		fail=1
	fi

	if grep -qx "${app}/appinfo/signature.json" "${listing}"; then
		if [ "${wants_signature}" = "0" ]; then
			echo "${archive}: carries a code signature, and this half has no PHP for the integrity check to see"
			fail=1
		else
			echo "${archive}: carries appinfo/signature.json, as the integrity check of the instance requires"
		fi
	elif [ "${wants_signature}" = "1" ]; then
		echo "${archive}: has no appinfo/signature.json, so the integrity check would report the app as modified"
		fail=1
	else
		echo "${archive}: carries no code signature, which is correct for a container half"
	fi

	for forbidden in tests vendor phpunit.xml composer.json composer.lock src scripts docs .github; do
		if grep -q "^${app}/${forbidden}\(/\|$\)" "${listing}"; then
			echo "${archive}: contains ${forbidden}, which is development material and must not be released"
			fail=1
		fi
	done
	if grep -q '\.gitkeep$' "${listing}"; then
		echo "${archive}: contains a .gitkeep"
		fail=1
	fi
	if grep -Eq '\.(key|pem)$' "${listing}"; then
		echo "${archive}: contains a key file"
		fail=1
	fi
	return "${fail}"
}

command="${1:-}"
if [ "$#" -gt 0 ]; then
	shift
fi

case "${command}" in
	stage-companion)
		[ "$#" -eq 1 ] || { usage; exit 1; }
		stage_companion "$1"
		;;
	stage-backend)
		[ "$#" -eq 1 ] || { usage; exit 1; }
		stage_backend "$1"
		;;
	pack)
		[ "$#" -eq 3 ] || { usage; exit 1; }
		pack "$1" "$2" "$3"
		;;
	assert-contents)
		[ "$#" -eq 3 ] || { usage; exit 1; }
		assert_contents "$1" "$2" "$3"
		;;
	*)
		usage
		exit 1
		;;
esac
