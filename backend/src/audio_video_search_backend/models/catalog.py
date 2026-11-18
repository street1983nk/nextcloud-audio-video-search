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

The Whisper models (plan 05-08, D-05-05, D-05-13) come from a second release
of the same repository, ``whisper-2026-11``, so ``models-2026-11`` stays as it
is. Origin, named for provenance only and never asked by the app:

- Whisper large-v3-turbo in CTranslate2 format, MIT: the Hugging Face
  repository deepdml/faster-whisper-large-v3-turbo-ct2 at commit
  4df90f75321148c3a29a9e2351b7ddf8f5b115a8.
- Whisper large-v3 in CTranslate2 format: the Hugging Face repository
  Systran/faster-whisper-large-v3 at commit
  edaa852ec7e145841d8ffdb056a99866b5f0a478. The weights are by OpenAI, Apache-2.0
  according to the model card; the CTranslate2 conversion is by Systran, MIT
  (D-05-15).

A release asset must stay under 2 GiB, so both ``model.bin`` are stored in
parts of exactly 1 GiB (:class:`PartedFile`). Each part has its own sha256 and
length, and the whole file has the sha256 of the origin (the LFS value), so an
admin may place the whole file from either source and gets the same verdict.
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


@dataclass(frozen=True, slots=True)
class Part:
    """One release asset of a file that is stored in parts: where it comes from, what it must be."""

    url: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class PartedFile:
    """One file of a model that the release holds in parts, in the order they are joined.

    ``sha256`` and ``size`` are the ones of the whole file. Every part has its
    own pair, so a wrong part is found before the next one is asked for; the
    whole is the last verdict and the only one for a file an admin placed.
    """

    name: str
    sha256: str
    size: int
    parts: tuple[Part, ...]


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

# The Whisper models of the refinement (plan 05-08): an own release tag, so the
# preview release above stays untouched. The values are the measured ones of
# scripts/models/whisper-parts-2026-11.json (plan 05-03); tests/test_models.py
# compares every one of them with that file. model.bin comes last, so the small
# files fail first when the release cannot be reached.
WHISPER_RELEASE_TAG: Final = "whisper-2026-11"
_WHISPER_BASE: Final = f"https://github.com/{MODEL_RELEASE_REPOSITORY}/releases/download/{WHISPER_RELEASE_TAG}"

WHISPER_TURBO_FILES: Final = (
    ModelFile(
        name="config.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3-turbo.config.json",
        sha256="b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e",
        size=2_263,
    ),
    ModelFile(
        name="preprocessor_config.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3-turbo.preprocessor_config.json",
        sha256="7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
        size=340,
    ),
    ModelFile(
        name="tokenizer.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3-turbo.tokenizer.json",
        sha256="297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd",
        size=2_710_337,
    ),
    ModelFile(
        name="vocabulary.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3-turbo.vocabulary.json",
        sha256="c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
        size=1_068_114,
    ),
    PartedFile(
        name="model.bin",
        sha256="e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da",
        size=1_617_884_929,
        parts=(
            Part(
                url=f"{_WHISPER_BASE}/whisper-large-v3-turbo.model.bin.001",
                sha256="229405133905b758bbdef3a8104ab31939bf8994125d1547ed950799af20d555",
                size=1_073_741_824,
            ),
            Part(
                url=f"{_WHISPER_BASE}/whisper-large-v3-turbo.model.bin.002",
                sha256="bfa3916ab9fc48c3af1d994331aadc6df5cfe40776b0d33b4081f5503203dcb4",
                size=544_143_105,
            ),
        ),
    ),
)

WHISPER_LARGE_V3_FILES: Final = (
    ModelFile(
        name="config.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3.config.json",
        sha256="a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9",
        size=2_394,
    ),
    ModelFile(
        name="preprocessor_config.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3.preprocessor_config.json",
        sha256="7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
        size=340,
    ),
    ModelFile(
        name="tokenizer.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3.tokenizer.json",
        sha256="6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca",
        size=2_480_617,
    ),
    ModelFile(
        name="vocabulary.json",
        url=f"{_WHISPER_BASE}/whisper-large-v3.vocabulary.json",
        sha256="c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
        size=1_068_114,
    ),
    PartedFile(
        name="model.bin",
        sha256="69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1",
        size=3_087_284_237,
        parts=(
            Part(
                url=f"{_WHISPER_BASE}/whisper-large-v3.model.bin.001",
                sha256="ffb5a6cd5d53b9188fc30dfc8c9e59d596fdbc2b2fb61368c0564b407be46591",
                size=1_073_741_824,
            ),
            Part(
                url=f"{_WHISPER_BASE}/whisper-large-v3.model.bin.002",
                sha256="c14e94cdd7837754a73f63b3b197925addda5fd0f39cb92bcdfb9e146a0e71d5",
                size=1_073_741_824,
            ),
            Part(
                url=f"{_WHISPER_BASE}/whisper-large-v3.model.bin.003",
                sha256="4daea110817f4be7bfe5c0cfb82d01f12adc2684ab3bd548bd43634f658d5380",
                size=939_800_589,
            ),
        ),
    ),
)

WHISPER_MODELS: Final = ("whisper-turbo", "whisper-large-v3")
# Where the bytes were taken from: repository and commit. Provenance only; the
# app never builds a URL from these and never asks that host.
WHISPER_SOURCES: Final = {
    "whisper-turbo": ("deepdml/faster-whisper-large-v3-turbo-ct2", "4df90f75321148c3a29a9e2351b7ddf8f5b115a8"),
    "whisper-large-v3": ("Systran/faster-whisper-large-v3", "edaa852ec7e145841d8ffdb056a99866b5f0a478"),
}

MODELS: Final[dict[str, tuple[ModelFile | PartedFile, ...]]] = {
    "silero": SILERO_FILES,
    "parakeet": PARAKEET_FILES,
    "whisper-turbo": WHISPER_TURBO_FILES,
    "whisper-large-v3": WHISPER_LARGE_V3_FILES,
}

# Every host a download may touch, each one seen in the real redirect chain of
# every asset on 14.11.2026 (plan 03-07b SUMMARY): github.com answers
# "HTTP/1.1 302 Found" to release-assets.githubusercontent.com, which answers
# "HTTP/1.1 200 OK" with the fixed length. No pattern, no other host.
ASSET_HOSTS: Final = frozenset({"github.com", "release-assets.githubusercontent.com"})

# The identity of the preview set (Parakeet and Silero) for the provenance of a
# transcript (TRANS-06): sha256 over the sorted file digests joined by commas.
# tests/test_models.py computes it again from those files. The Whisper models
# are not part of it, so it did not move when they joined the catalog.
MODEL_SHA256: Final = "3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339"


def model_bytes(name: str) -> int:
    """The total length of all files of one model; a file in parts counts once, as the whole."""
    return sum(entry.size for entry in MODELS[name])
