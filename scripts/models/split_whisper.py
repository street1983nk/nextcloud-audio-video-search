"""Load the Whisper weights at a fixed commit and cut model.bin into release parts.

A developer step on a workstation, never part of the app: the app loads its
models from the project's own release only (D-03-21). A GitHub release asset
must stay under 2 GiB, so both ``model.bin`` are cut into parts of exactly
1 GiB (D-05-13). The identities go into a JSON file that the catalogue
(plan 05-08) and the upload (plan 05-10) read.

    uv run --project backend python -I scripts/models/split_whisper.py \
        --work DIR --out scripts/models/whisper-parts-2026-11.json [--skip-download]

``DIR`` lies outside the repository. Originals go to ``DIR/originals/<model>/``,
the release assets to ``DIR/assets/``. Order of work: load every file, check
length and sha256 of every whole file, and only then write parts. A mismatch
ends with exit 1 before any part exists (T-05-06). Output names hosts only,
never a redirect URL, because those carry a signature (T-03-77).
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urljoin, urlsplit

import httpx

PART_SIZE: Final = 1073741824  # 1 GiB, not 1 GB decimal
RELEASE_TAG: Final = "whisper-2026-11"
SOURCE_HOST: Final = "huggingface.co"
# Hugging Face answers a resolve URL with a redirect to a CDN host that changes
# with the region (measured us.aws.cdn.hf.co); all of them sit under hf.co.
CDN_SUFFIX: Final = ".hf.co"
MAX_REDIRECTS: Final = 5
REDIRECTS: Final = frozenset({301, 302, 303, 307, 308})
CHUNK: Final = 1024 * 1024
REPORT_EVERY: Final = 256 * 1024 * 1024
AGENT: Final = "model-split-script/1.0"


class FetchError(Exception):
    """The transfer failed: host, status, length or range."""


class DigestError(Exception):
    """Length or sha256 of a whole file is not the fixed value."""


@dataclass(frozen=True, slots=True)
class FileSpec:
    """One file at the commit: its name, its length, its sha256."""

    name: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class Model:
    """One model: the prefix of its asset names, where it comes from, its files."""

    prefix: str
    repo: str
    commit: str
    files: tuple[FileSpec, ...]


# Fixed values of plan 05-03 (05-RESEARCH.md pattern 5, checked at the commit on
# 18.11.2026). The sha256 of each model.bin is the LFS value of Hugging Face
# and the value of the Spike 3 gate.
MODELS: Final[Mapping[str, Model]] = {
    "whisper-turbo": Model(
        prefix="whisper-large-v3-turbo",
        repo="deepdml/faster-whisper-large-v3-turbo-ct2",
        commit="4df90f75321148c3a29a9e2351b7ddf8f5b115a8",
        files=(
            FileSpec("model.bin", 1617884929, "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da"),
            FileSpec("config.json", 2263, "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e"),
            FileSpec(
                "preprocessor_config.json", 340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"
            ),
            FileSpec("tokenizer.json", 2710337, "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd"),
            FileSpec("vocabulary.json", 1068114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
        ),
    ),
    "whisper-large-v3": Model(
        prefix="whisper-large-v3",
        repo="Systran/faster-whisper-large-v3",
        commit="edaa852ec7e145841d8ffdb056a99866b5f0a478",
        files=(
            FileSpec("model.bin", 3087284237, "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1"),
            FileSpec("config.json", 2394, "a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9"),
            FileSpec(
                "preprocessor_config.json", 340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"
            ),
            FileSpec("tokenizer.json", 2480617, "6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca"),
            FileSpec("vocabulary.json", 1068114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
        ),
    ),
}

# The one file of each model that is cut into parts.
SPLIT_NAME: Final = "model.bin"


def source_url(model: Model, name: str) -> str:
    return f"https://{SOURCE_HOST}/{model.repo}/resolve/{model.commit}/{name}"


def allowed_url(url: str) -> bool:
    """https to huggingface.co or to a host under hf.co, nothing else."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme != "https" or not host:
        return False
    return host == SOURCE_HOST or host.endswith(CDN_SUFFIX)


def host_of(url: str) -> str:
    try:
        return urlsplit(url).hostname or "?"
    except ValueError:
        return "?"


def file_digest(path: Path) -> tuple[int, str]:
    """Length and sha256 of a file, read in chunks."""
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            hasher.update(chunk)
            size += len(chunk)
    return size, hasher.hexdigest()


def check_whole(path: Path, size: int, sha256: str) -> None:
    """Raise DigestError unless ``path`` has exactly this length and sha256."""
    if not path.is_file():
        raise DigestError(f"{path.name}: missing")
    if path.stat().st_size != size:
        raise DigestError(f"{path.name}: length {path.stat().st_size}, expected {size}")
    _, found = file_digest(path)
    if found != sha256:
        raise DigestError(f"{path.name}: sha256 {found}, expected {sha256}")


def _open(client: httpx.Client, url: str, headers: dict[str, str]) -> httpx.Response:
    """Follow redirects by hand so that every hop is checked before it is asked."""
    for _ in range(MAX_REDIRECTS + 1):
        if not allowed_url(url):
            raise FetchError(f"host not allowed: {host_of(url)}")
        print(f"  GET {host_of(url)}", flush=True)
        response = client.send(client.build_request("GET", url, headers=headers), stream=True)
        if response.status_code not in REDIRECTS:
            return response
        location = response.headers.get("location")
        response.close()
        if not location:
            raise FetchError(f"redirect without a target from {host_of(url)}")
        url = urljoin(url, location)
    raise FetchError("too many redirects")


def download(client: httpx.Client, url: str, dest: Path, size: int, sha256: str) -> None:
    """Stream ``url`` into ``dest``; the file appears only with the fixed length and sha256.

    A present ``dest`` is checked and never replaced. A started ``dest.part`` goes
    on with a Range request; its bytes are hashed again, no stored verdict is
    trusted.
    """
    if dest.exists():
        check_whole(dest, size, sha256)
        print(f"  {dest.name}: present, sha256 ok", flush=True)
        return
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.is_file() else 0
    if have >= size:
        part.unlink()
        have = 0
    headers = {"User-Agent": AGENT, "Accept-Encoding": "identity"}
    if have:
        headers["Range"] = f"bytes={have}-"
    response = _open(client, url, headers)
    try:
        if response.status_code == 200:
            have = 0
        elif response.status_code == 206:
            if not response.headers.get("content-range", "").startswith(f"bytes {have}-"):
                raise FetchError(f"{dest.name}: range answer for another offset")
        else:
            raise FetchError(f"{dest.name}: HTTP {response.status_code} from {host_of(str(response.url))}")
        hasher = hashlib.sha256()
        if have:
            with part.open("rb") as old:
                while chunk := old.read(CHUNK):
                    hasher.update(chunk)
        done = have
        reported = done
        with part.open("ab" if have else "wb") as handle:
            for chunk in response.iter_raw(CHUNK):
                done += len(chunk)
                if done > size:
                    break
                hasher.update(chunk)
                handle.write(chunk)
                if done - reported >= REPORT_EVERY:
                    reported = done
                    print(f"  {dest.name}: {done // (1024 * 1024)} of {size // (1024 * 1024)} MiB", flush=True)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        response.close()
    if done > size:
        part.unlink()
        raise FetchError(f"{dest.name}: body longer than {size} bytes")
    if done < size:
        # the part stays, the next run goes on from here
        raise FetchError(f"{dest.name}: body too short, {done} of {size} bytes")
    if hasher.hexdigest() != sha256:
        part.unlink()
        raise DigestError(f"{dest.name}: sha256 {hasher.hexdigest()}, expected {sha256}")
    os.replace(part, dest)
    print(f"  {dest.name}: {size} bytes, sha256 ok", flush=True)


def split_file(path: Path, part_size: int, out_dir: Path, prefix: str) -> list[tuple[str, int, str]]:
    """Cut ``path`` into ``prefix.001``, ``prefix.002`` ... and return (name, size, sha256) in order."""
    if part_size < 1:
        raise ValueError("part_size must be at least 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    parts: list[tuple[str, int, str]] = []
    with path.open("rb") as source:
        number = 0
        while True:
            hasher = hashlib.sha256()
            written = 0
            number += 1
            name = f"{prefix}.{number:03d}"
            temporary = out_dir / f"{name}.tmp"
            with temporary.open("wb") as target:
                while written < part_size:
                    chunk = source.read(min(CHUNK, part_size - written))
                    if not chunk:
                        break
                    hasher.update(chunk)
                    target.write(chunk)
                    written += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            if written == 0:
                temporary.unlink()
                break
            os.replace(temporary, out_dir / name)
            parts.append((name, written, hasher.hexdigest()))
            if written < part_size:
                break
    return parts


def _originals(work: Path, key: str) -> Path:
    return work / "originals" / key


def _fetch_all(work: Path, models: Mapping[str, Model]) -> None:
    timeout = httpx.Timeout(30.0, read=120.0)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for key, model in models.items():
            folder = _originals(work, key)
            folder.mkdir(parents=True, exist_ok=True)
            for spec in model.files:
                print(f"{key}: {spec.name}", flush=True)
                download(client, source_url(model, spec.name), folder / spec.name, spec.size, spec.sha256)


def _entry(model: Model, spec: FileSpec, source: Path, assets: Path, part_size: int) -> dict[str, object]:
    asset = f"{model.prefix}.{spec.name}"
    if spec.name != SPLIT_NAME:
        assets.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, assets / asset)
        check_whole(assets / asset, spec.size, spec.sha256)
        return {"name": spec.name, "size": spec.size, "sha256": spec.sha256, "parts": None, "asset": asset}
    parts = split_file(source, part_size, assets, asset)
    if sum(size for _, size, _ in parts) != spec.size:
        raise DigestError(f"{spec.name}: the parts do not add up to {spec.size} bytes")
    return {
        "name": spec.name,
        "size": spec.size,
        "sha256": spec.sha256,
        "parts": [{"asset": name, "size": size, "sha256": sha256} for name, size, sha256 in parts],
        "asset": None,
    }


def run(
    work: Path,
    out: Path,
    *,
    models: Mapping[str, Model] = MODELS,
    part_size: int = PART_SIZE,
    skip_download: bool = False,
) -> int:
    """Load, check every whole file, write the assets, write the JSON. 0 on success, else 1."""
    try:
        if not skip_download:
            _fetch_all(work, models)
        # Every whole file first: no part is written while any file is in doubt.
        for key, model in models.items():
            for spec in model.files:
                check_whole(_originals(work, key) / spec.name, spec.size, spec.sha256)
        assets = work / "assets"
        document: dict[str, object] = {"tag": RELEASE_TAG, "models": {}}
        listed: dict[str, object] = {}
        for key, model in models.items():
            files = [
                _entry(model, spec, _originals(work, key) / spec.name, assets, part_size)
                for spec in sorted(model.files, key=lambda spec: spec.name)
            ]
            listed[key] = {"source": {"repo": model.repo, "commit": model.commit}, "files": files}
        document["models"] = listed
    except (FetchError, DigestError, httpx.HTTPError, OSError) as error:
        print(f"FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": the same bytes on every platform, the file is versioned
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out.name}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the Whisper weights and cut model.bin into release parts.")
    parser.add_argument("--work", type=Path, required=True, help="folder outside the repository")
    parser.add_argument("--out", type=Path, required=True, help="JSON with the identities")
    parser.add_argument("--skip-download", action="store_true", help="only split the files already present")
    args = parser.parse_args()
    return run(args.work, args.out, skip_download=args.skip_download)


if __name__ == "__main__":
    sys.exit(main())
