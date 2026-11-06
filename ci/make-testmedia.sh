#!/usr/bin/env bash
# Test media for the end-to-end tests, made in CI with ffmpeg, never checked in.
#
# A 90 s sine tone (440 Hz) on a grey picture: no speech, no licence question,
# a few hundred KB. WebM (VP9 + Opus) and Ogg (Opus) because the Playwright
# Chromium may lack H.264/AAC (01-RESEARCH.md, Pitfall 7).
#
# usage: ci/make-testmedia.sh [target directory, default testdata]
set -euo pipefail

target="${1:-testdata}"
mkdir -p "${target}"

ffmpeg -hide_banner -loglevel error -y \
	-f lavfi -i sine=frequency=440:duration=90 \
	-f lavfi -i color=c=gray:s=320x180:d=90 \
	-map 1:v -map 0:a \
	-c:v libvpx-vp9 -b:v 0 -crf 40 -deadline realtime \
	-c:a libopus -b:a 48k \
	-shortest "${target}/tone-90s.webm"

ffmpeg -hide_banner -loglevel error -y \
	-f lavfi -i sine=frequency=440:duration=90 \
	-c:a libopus -b:a 48k \
	"${target}/tone-90s.ogg"

sha256sum "${target}/tone-90s.webm" "${target}/tone-90s.ogg"
