#!/usr/bin/env bash
# Test media for the end-to-end tests, made in CI with ffmpeg, never checked in.
#
# A 90 s sine tone (440 Hz) on a grey picture: no speech, no licence question,
# a few hundred KB. WebM (VP9 + Opus) and Ogg (Opus) because the Playwright
# Chromium may lack H.264/AAC (01-RESEARCH.md, Pitfall 7).
#
# Phase 3 (plan 03-18): with AVS_SPEECH_DE and AVS_SPEECH_TR set (the WAV
# clips of ci/media/fetch_speech.py, FLEURS, CC-BY-4.0) the script also makes
# the media of the states of the playback page and of the search (UI-SPEC
# 03, S1 to S5 and P1 to P13). File names without umlauts:
#
#   stille-60s.ogg     60 s of silence, Opus                     A6 no speech
#   kaputt.mp3         random bytes under an audio name          A7 damaged
#   geschuetzt.m4a     the DE clip as AAC, CENC with a fixed     A8 protected
#                      test key (no secret: it only has to be
#                      encrypted, nobody ever decrypts it)
#   lang-12h01.flac    12 h 1 min of silence, FLAC (digital      A10 too long, plural
#                      silence packs to a few MB in seconds)     at the default 12 h,
#                                                                singular after the
#                                                                limit went down to 1
#   lang-40min.ogg     the DE clip looped to 40 min, Opus: four  A2 partial, A4 point
#                      pieces of 10 min with speech in each, a   not transcribed yet,
#                      copy of the clip also at about 25 min     A5 before piece 1
#   viele-stellen.ogg  the DE clip four times, 30 s apart        S1, S2: one file with
#                                                                four places
#   zwei-stellen.ogg   the DE clip twice, 30 s apart             S1: the second file
#   tuerkisch.wav      the TR clip (Parakeet does not know it)   A9 unsupported language
#   ohne-ton.mp4       a picture only, MPEG-4 part 2, no audio   A11 other reason
#                                                                (no_audio)
#
# usage: [AVS_SPEECH_DE=... AVS_SPEECH_TR=...] ci/make-testmedia.sh [target directory, default testdata]
set -euo pipefail

target="${1:-testdata}"
mkdir -p "${target}"

ff() {
	ffmpeg -hide_banner -loglevel error -y "$@"
}

ff -f lavfi -i sine=frequency=440:duration=90 \
	-f lavfi -i color=c=gray:s=320x180:d=90 \
	-map 1:v -map 0:a \
	-c:v libvpx-vp9 -b:v 0 -crf 40 -deadline realtime \
	-c:a libopus -b:a 48k \
	-shortest "${target}/tone-90s.webm"

ff -f lavfi -i sine=frequency=440:duration=90 \
	-c:a libopus -b:a 48k \
	"${target}/tone-90s.ogg"

sha256sum "${target}/tone-90s.webm" "${target}/tone-90s.ogg"

# -- phase 3 ----------------------------------------------------------------------

speech_de="${AVS_SPEECH_DE:-}"
speech_tr="${AVS_SPEECH_TR:-}"
if [ -z "${speech_de}" ] && [ -z "${speech_tr}" ]; then
	echo "AVS_SPEECH_DE and AVS_SPEECH_TR are not set: only the media of phase 1"
	exit 0
fi
# One clip without the other is a broken job, never a smaller set of media.
: "${speech_de:?AVS_SPEECH_DE is required next to AVS_SPEECH_TR}"
: "${speech_tr:?AVS_SPEECH_TR is required next to AVS_SPEECH_DE}"
test -s "${speech_de}"
test -s "${speech_tr}"

# Fixed test values for the encryption, not a secret.
CENC_KEY=00112233445566778899aabbccddeeff
CENC_KID=a0a1a2a3a4a5a6a7a8a9aaabacadaeaf
# 12 h 1 min, one minute above the default limit of 12 h (D-03-08).
LONG_SECONDS=43260
# 40 min: four pieces of 10 min (CHUNK_MS), so the file is partial for a while.
PARTIAL_SECONDS=2400
# The places of viele-stellen.ogg and zwei-stellen.ogg start 30 s apart.
PLACE_SECONDS=30

ff -f lavfi -i anullsrc=r=48000:cl=mono -t 60 -c:a libopus -b:a 24k "${target}/stille-60s.ogg"

head -c 8192 /dev/urandom > "${target}/kaputt.mp3"

ff -i "${speech_de}" -c:a aac -b:a 64k -f mp4 \
	-encryption_scheme cenc-aes-ctr -encryption_key "${CENC_KEY}" -encryption_kid "${CENC_KID}" \
	"${target}/geschuetzt.m4a"

ff -f lavfi -i anullsrc=r=8000:cl=mono -t "${LONG_SECONDS}" -c:a flac -sample_fmt s16 "${target}/lang-12h01.flac"

ff -stream_loop -1 -i "${speech_de}" -t "${PARTIAL_SECONDS}" -c:a libopus -b:a 24k "${target}/lang-40min.ogg"

place="$(mktemp --suffix=.wav)"
ff -i "${speech_de}" -af "apad=whole_dur=${PLACE_SECONDS}" "${place}"
ff -stream_loop 3 -i "${place}" -c:a libopus -b:a 24k "${target}/viele-stellen.ogg"
ff -stream_loop 1 -i "${place}" -c:a libopus -b:a 24k "${target}/zwei-stellen.ogg"
rm -f "${place}"

cp "${speech_tr}" "${target}/tuerkisch.wav"

ff -f lavfi -i color=c=gray:s=320x180:d=10 -c:v mpeg4 -an "${target}/ohne-ton.mp4"

for name in stille-60s.ogg kaputt.mp3 geschuetzt.m4a lang-12h01.flac lang-40min.ogg \
	viele-stellen.ogg zwei-stellen.ogg tuerkisch.wav ohne-ton.mp4; do
	test -s "${target}/${name}" || { echo "${name} was not made"; exit 1; }
done
# The protection boxes give a CENC file away (media/probe.py); without them the
# file would be plain AAC and A8 would never show.
grep -q schm "${target}/geschuetzt.m4a" || { echo "geschuetzt.m4a carries no protection box"; exit 1; }
sha256sum "${target}"/stille-60s.ogg "${target}"/geschuetzt.m4a "${target}"/lang-12h01.flac \
	"${target}"/lang-40min.ogg "${target}"/viele-stellen.ogg "${target}"/zwei-stellen.ogg \
	"${target}"/tuerkisch.wav "${target}"/ohne-ton.mp4
