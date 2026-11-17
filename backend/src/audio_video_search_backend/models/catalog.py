"""The fixed identity of every model file the preview needs.

Each file has exactly one identity: a URL on the project's own model release,
a sha256 and a length. A file is accepted only when both match, no matter
whether the container fetched it or the admin placed it by hand (air gap).

Origin of the files, mirrored byte-identical (same sha256) into the release
``models-2026-11`` of street1983nk/nextcloud-audio-video-search (plan 03-07b):

- Parakeet-TDT-0.6B-v3 int8 by NVIDIA, CC-BY-4.0 (attribution to NVIDIA in the
  release text and the README): the sherpa-onnx export
  csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8 at commit
  2bda32ec70b097a55adaa07d9a7173915b43cc78.
- Silero VAD, MIT: the ``asr-models`` release of k2-fsa/sherpa-onnx.

Why an own release (D-03-21): Hugging Face redirects to a CDN host that changes
with the region (measured us.aws.cdn.hf.co), so a fixed allowlist would fail
elsewhere. The tag has no ``v`` prefix, so no workflow starts on it. The
digests are the ones of the Spike 3 gate, checked again with sha256sum and
certutil before the upload and against the API digest of every asset.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ModelFile:
    """One file of a model: its name on the volume, where it comes from, what it must be."""

    name: str
    url: str
    sha256: str
    size: int


MODEL_RELEASE_REPOSITORY: Final = "street1983nk/nextcloud-audio-video-search"
MODEL_RELEASE_TAG: Final = "models-2026-11"
_RELEASE_BASE: Final = f"https://github.com/{MODEL_RELEASE_REPOSITORY}/releases/download/{MODEL_RELEASE_TAG}"

PARAKEET_FILES: Final = (
    ModelFile(
        name="encoder.int8.onnx",
        url=f"{_RELEASE_BASE}/encoder.int8.onnx",
        sha256="acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247",
        size=652_184_281,
    ),
    ModelFile(
        name="decoder.int8.onnx",
        url=f"{_RELEASE_BASE}/decoder.int8.onnx",
        sha256="179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e",
        size=11_845_275,
    ),
    ModelFile(
        name="joiner.int8.onnx",
        url=f"{_RELEASE_BASE}/joiner.int8.onnx",
        sha256="3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3",
        size=6_355_277,
    ),
    ModelFile(
        name="tokens.txt",
        url=f"{_RELEASE_BASE}/tokens.txt",
        sha256="d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
        size=93_939,
    ),
)

SILERO_FILES: Final = (
    ModelFile(
        name="silero_vad.onnx",
        url=f"{_RELEASE_BASE}/silero_vad.onnx",
        sha256="9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
        size=643_854,
    ),
)

MODELS: Final = {"silero": SILERO_FILES, "parakeet": PARAKEET_FILES}

# Every host a download may touch, each one seen in the real redirect chain of
# every asset on 14.11.2026 (plan 03-07b SUMMARY): github.com answers
# "HTTP/1.1 302 Found" to release-assets.githubusercontent.com, which answers
# "HTTP/1.1 200 OK" with the fixed length. No pattern, no other host.
ASSET_HOSTS: Final = frozenset({"github.com", "release-assets.githubusercontent.com"})

# The identity of the whole set for the provenance of a transcript (TRANS-06):
# sha256 over the sorted file digests joined by commas. tests/test_models.py
# computes it again from the files above.
MODEL_SHA256: Final = "3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339"


def model_bytes(name: str) -> int:
    """The total length of all files of one model."""
    return sum(entry.size for entry in MODELS[name])
