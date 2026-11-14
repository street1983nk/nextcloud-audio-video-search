"""The fixed identity of every model file the preview needs.

Each file has exactly one identity: a URL pinned to a commit or a release asset,
a sha256 and a length. A file is accepted only when both match, no matter
whether the container fetched it or the admin placed it by hand (air gap).

Parakeet-TDT-0.6B-v3 int8 (CC-BY-4.0, attribution to NVIDIA) comes from the
sherpa-onnx export on Hugging Face at commit 2bda32ec; Silero VAD (MIT) from the
``asr-models`` release of k2-fsa/sherpa-onnx. The digests are the ones of the
Spike 3 gate; for the three LFS files Hugging Face announces the same values as
``X-Linked-ETag``, and tokens.txt and silero_vad.onnx were fetched and hashed
once on 14.11.2026 (plan 03-07).
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


PARAKEET_REPOSITORY: Final = "csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
PARAKEET_REVISION: Final = "2bda32ec70b097a55adaa07d9a7173915b43cc78"
_PARAKEET_BASE: Final = f"https://huggingface.co/{PARAKEET_REPOSITORY}/resolve/{PARAKEET_REVISION}"

PARAKEET_FILES: Final = (
    ModelFile(
        name="encoder.int8.onnx",
        url=f"{_PARAKEET_BASE}/encoder.int8.onnx",
        sha256="acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247",
        size=652_184_281,
    ),
    ModelFile(
        name="decoder.int8.onnx",
        url=f"{_PARAKEET_BASE}/decoder.int8.onnx",
        sha256="179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e",
        size=11_845_275,
    ),
    ModelFile(
        name="joiner.int8.onnx",
        url=f"{_PARAKEET_BASE}/joiner.int8.onnx",
        sha256="3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3",
        size=6_355_277,
    ),
    ModelFile(
        name="tokens.txt",
        url=f"{_PARAKEET_BASE}/tokens.txt",
        sha256="d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
        size=93_939,
    ),
)

SILERO_FILES: Final = (
    ModelFile(
        name="silero_vad.onnx",
        url="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
        sha256="9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
        size=643_854,
    ),
)

MODELS: Final = {"silero": SILERO_FILES, "parakeet": PARAKEET_FILES}

# Every host a download may touch, each one seen in a real redirect chain on
# 14.11.2026 (plan 03-07 SUMMARY): huggingface.co answers the three LFS files
# with 302 to us.aws.cdn.hf.co and tokens.txt with a relative 307 to itself;
# github.com answers the release asset with 302 to
# release-assets.githubusercontent.com. No pattern, no other host.
ASSET_HOSTS: Final = frozenset(
    {
        "huggingface.co",
        "us.aws.cdn.hf.co",
        "github.com",
        "release-assets.githubusercontent.com",
    }
)

# The identity of the whole set for the provenance of a transcript (TRANS-06):
# sha256 over the sorted file digests joined by commas. tests/test_models.py
# computes it again from the files above.
MODEL_SHA256: Final = "3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339"


def model_bytes(name: str) -> int:
    """The total length of all files of one model."""
    return sum(entry.size for entry in MODELS[name])
