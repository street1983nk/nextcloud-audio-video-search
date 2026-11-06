# syntax=docker/dockerfile:1
# Image of the External App. Multi-stage: the build tools and the frp download
# never reach the runtime layer, which carries the venv, three shell scripts,
# frpc, curl for the health check, and nothing else.
#
# Every base image is pinned by digest (tests/test_dockerfile.py). Dependabot
# (docker ecosystem) raises the digests; a tag alone can be moved by anyone who
# controls it. Same base and uv pins as Findling 1.6.x.

ARG BASE_IMAGE=python:3.13-slim-trixie@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

FROM ${BASE_IMAGE} AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so a code change does not invalidate the dependency layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-editable --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# frpc is the one binary that does not come from a package manager, so its
# supply chain is spelled out: fixed version, checksum per architecture, the
# build stops on any mismatch. Values taken over from Gameworld.
FROM ${BASE_IMAGE} AS frpc
ARG TARGETARCH
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# curl and ca-certificates stay unpinned on purpose: they only fetch and verify,
# and a pin would hold back security fixes of the base image. Packages whose
# version decides a result (an OCR engine, a model) get an exact pin instead.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    FRP_VERSION=0.71.1; \
    FRP_AMD64_SHA256=1d9875210972a5d1a62b2dc4c48df45ab0af05d3ca1b5e494a014428259df803; \
    FRP_ARM64_SHA256=8edf590b0c396fa42f9c147121a76af83cfc2002b08f5aef0ea1008c43482019; \
    case "${TARGETARCH:-amd64}" in \
        arm64) FRP_ARCH=arm64; FRP_SHA256="${FRP_ARM64_SHA256}" ;; \
        amd64) FRP_ARCH=amd64; FRP_SHA256="${FRP_AMD64_SHA256}" ;; \
        *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --proto '=https' --tlsv1.2 -o /tmp/frp.tar.gz \
        "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${FRP_ARCH}.tar.gz"; \
    echo "${FRP_SHA256}  /tmp/frp.tar.gz" | sha256sum -c -; \
    tar -C /tmp -xzf /tmp/frp.tar.gz "frp_${FRP_VERSION}_linux_${FRP_ARCH}/frpc"; \
    install -m 0755 "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}/frpc" /usr/local/bin/frpc; \
    /usr/local/bin/frpc --version

FROM ${BASE_IMAGE} AS runtime
LABEL org.opencontainers.image.source="https://github.com/street1983nk/nextcloud-audio-video-search" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.title="Audio & Video Search Backend"
# Unpinned for the reason given in the frpc stage.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
# The German word list for the compound splitter (index/wordlist.py), as in
# Findling on the same base digest: /usr/share/dict/ngerman, Architecture: all,
# so amd64 and arm64 split compounds byte for byte alike. Pinned, because the
# list decides how a compound falls apart, and its digest is part of the
# analyzer mark of the index. Without it "frist" never finds
# "Kündigungsfrist". GPL-2+: the copyright file travels with the image. Both
# tests fail closed, an image without the list must not be built.
RUN apt-get update \
    && apt-get install -y --no-install-recommends wngerman=20161207-15 \
    && rm -rf /var/lib/apt/lists/* \
    && test -s /usr/share/dict/ngerman \
    && test -s /usr/share/doc/wngerman/copyright \
    && install -D -m 0444 /usr/share/doc/wngerman/copyright \
        /usr/local/share/audio_video_search_backend/COPYING.wngerman
# A fixed uid without a root moment at run time. start.sh writes /frpc.toml, so
# that file and the two directories AppAPI and HaRP fill are prepared for it.
RUN groupadd --gid 10001 exapp \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /app --shell /usr/sbin/nologin exapp \
    && install -o 10001 -g 10001 -m 0600 /dev/null /frpc.toml \
    && install -d -o 10001 -g 10001 -m 0700 /nc_app_audio_video_search_backend_data \
    && install -d -o 10001 -g 10001 -m 0700 /certs
COPY docker/entrypoint.sh docker/start.sh docker/healthcheck.sh /
RUN chmod 0755 /entrypoint.sh /start.sh /healthcheck.sh
COPY --from=frpc /usr/local/bin/frpc /usr/local/bin/frpc
COPY --from=build /app/.venv /app/.venv
# nc_py_api serves js/, css/, img/ and l10n/ out of the working directory. The
# backend has no page of its own, so no icons ship; the PHP app carries them.
COPY appinfo /app/appinfo
COPY l10n /app/l10n
# The build context is backend/, so the licence text at the repository root
# stays out (as in Findling); the image names it in the licenses label above.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
USER 10001:10001
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 CMD ["/healthcheck.sh"]
ENTRYPOINT ["/entrypoint.sh", "/app/.venv/bin/python", "-m", "audio_video_search_backend.main"]
