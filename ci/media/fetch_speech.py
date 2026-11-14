"""Gepinnte Sprachclips für CI, Modelltests und Abnahme laden (plan 03-02).

python -I ci/media/fetch_speech.py OUTDIR [--ffmpeg PFAD]
ffmpeg kommt aus --ffmpeg, sonst aus der Umgebungsvariable AVS_FFMPEG, sonst aus PATH.

Quelle und Lizenz: FLEURS, Google, CC-BY-4.0 (Hugging Face google/fleurs, feste Revision unten).
Je Clip wird das Test-Archiv der Sprache als Strom gelesen, nur das eine benannte Mitglied
angenommen (nie extractall, kein Pfadteil des Archivs wird übernommen), sein sha256 gegen den
festen Wert geprüft und erst dann per ffmpeg nach OUTDIR/<name> als 16 kHz mono s16 WAV gewandelt.
Der sha256 des Archivmitglieds ist der verbindliche Pin. Weicht nur der sha256 der WAV-Ausgabe ab
(andere ffmpeg-Version), gibt es eine Warnung mit beiden Werten und trotzdem Exit 0.
Exit 2: Aufruf falsch oder ffmpeg fehlt. Exit 3: Mitglied fehlt oder sha256 weicht ab, keine Datei.
Audiodaten gehören nie ins Repo; OUTDIR liegt außerhalb.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import IO

DATASET = "google/fleurs"
REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
# Alle Mitglieder der FLEURS-Testarchive liegen unter diesem Ordner.
TAR_MEMBER_DIR = "test/"
ATTRIBUTION = "FLEURS, Google, CC-BY-4.0"
FFMPEG_MISSING = "ffmpeg not found: pass --ffmpeg or set AVS_FFMPEG"
# Hugging Face leitet LFS/Xet-Dateien auf CDN-Hosts unter hf.co weiter.
ALLOWED_HOSTS = ("huggingface.co",)
ALLOWED_HOST_SUFFIXES = (".hf.co", ".huggingface.co")
EXIT_USAGE = 2
EXIT_PIN = 3


@dataclass(frozen=True)
class Clip:
    name: str
    tar_path: str
    member: str
    member_sha256: str
    wav_sha256: str
    duration_s: float
    expected_word: str | None = None
    expected_text: str | None = None


SPEECH_DE = Clip(
    name="speech_de.wav",
    tar_path="data/de_de/audio/test.tar.gz",
    member="10009182821551087671.wav",
    member_sha256="90d0470adf728783e98cc8dddd51e2c2cbf0d6bf360da65f7d2ac5c3e65876aa",
    wav_sha256="97d77a9d323b903dcc10c608521fa07fb78766d4b65d016ba620caae442dece9",
    duration_s=11.16,
    expected_word="dinosaurier",
    expected_text=(
        "Er griff auch alles an, was ins Wasser kam; selbst ein großer Dinosaurier wie der T. Rex war ihm nicht "
        "gewachsen."
    ),
)
# Türkisch: von Parakeet v3 nicht unterstützt, für den Grund "Sprache nicht unterstützt".
SPEECH_TR = Clip(
    name="speech_tr.wav",
    tar_path="data/tr_tr/audio/test.tar.gz",
    member="10000377651956138413.wav",
    member_sha256="e2efd9f3ce2fcc9e191126dcded8e674233a9ce83a9c2132541700e8f1bd57c3",
    wav_sha256="bee83b904f9c506159b0d026b66e7372839b63bc76591341c62ea73601d3dd31",
    duration_s=14.16,
)
CLIPS = (SPEECH_DE, SPEECH_TR)
EXPECTED_WORD = SPEECH_DE.expected_word
EXPECTED_TEXT = SPEECH_DE.expected_text


class PinError(Exception):
    """The archive does not hold the pinned member with the pinned sha256."""


def ffmpeg_binary(argv_value: str | None) -> str:
    """ffmpeg in der Reihenfolge --ffmpeg, AVS_FFMPEG, PATH; fehlt es, Abbruch mit Exit 2."""
    chosen = argv_value or os.environ.get("AVS_FFMPEG") or "ffmpeg"
    found = shutil.which(chosen)
    if found is None:
        print(f"{FFMPEG_MISSING} (tried {chosen!r})", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
    return found


def clip_url(clip: Clip) -> str:
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{clip.tar_path}"


def host_allowed(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host in ALLOWED_HOSTS or host.endswith(ALLOWED_HOST_SUFFIXES))


def pick_member(tar_stream: IO[bytes], name: str, sha256: str) -> bytes:
    """Bytes genau des Mitglieds TAR_MEMBER_DIR + name mit diesem sha256; schreibt nichts auf die Platte."""
    if "/" in name or "\\" in name or ".." in name or not name:
        raise ValueError(f"member name must be a plain file name: {name!r}")
    wanted = TAR_MEMBER_DIR + name
    with tarfile.open(fileobj=tar_stream, mode="r|gz") as archive:
        for member in archive:
            if member.name != wanted:
                continue
            if not member.isfile():
                raise PinError(f"{wanted} is not a regular file")
            handle = archive.extractfile(member)
            if handle is None:
                raise PinError(f"{wanted} has no data")
            data = handle.read()
            actual = hashlib.sha256(data).hexdigest()
            if actual != sha256:
                raise PinError(f"{wanted}: sha256 {actual}, expected {sha256}")
            return data
    raise PinError(f"{wanted} not in archive")


def to_wav(ff: str, src: Path, dst: Path) -> None:
    # Argumentliste ohne Shell; bitexact und ohne Metadaten, damit die Ausgabe nicht von der ffmpeg-Version abhängt.
    subprocess.run(  # noqa: S603
        [
            ff,
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src),
            "-map",
            "0:a:0",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ],
        check=True,
    )


def fetch(clip: Clip, out_dir: Path, ff: str) -> bool:
    """Clip laden und wandeln; True, wenn auch der WAV-sha256 stimmt."""
    url = clip_url(clip)
    if not host_allowed(url):
        raise PinError(f"host outside the allowlist: {urllib.parse.urlsplit(url).hostname}")
    # Schema und Host oben geprüft (nur https, Allowlist)
    request = urllib.request.Request(url, headers={"User-Agent": "audio-video-search-ci/1.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        final_host = urllib.parse.urlsplit(response.geturl()).hostname
        if not host_allowed(response.geturl()):
            raise PinError(f"redirect to a host outside the allowlist: {final_host}")
        data = pick_member(response, clip.member, clip.member_sha256)
    dst = out_dir / clip.name
    with tempfile.TemporaryDirectory(dir=out_dir) as scratch:
        raw = Path(scratch) / "member.wav"
        raw.write_bytes(data)
        to_wav(ff, raw, dst)
    wav_sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    print(f"{clip.name}: member {clip.member} sha256 {clip.member_sha256} ok, wav sha256 {wav_sha}", flush=True)
    if wav_sha != clip.wav_sha256:
        print(
            f"warning: {clip.name} wav sha256 {wav_sha} differs from {clip.wav_sha256} (other ffmpeg version?)",
            file=sys.stderr,
        )
        return False
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fetch the pinned FLEURS speech clips (" + ATTRIBUTION + ").")
    parser.add_argument("outdir")
    parser.add_argument("--ffmpeg")
    args = parser.parse_args(argv)
    ff = ffmpeg_binary(args.ffmpeg)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for clip in CLIPS:
        try:
            fetch(clip, out_dir, ff)
        except PinError as error:
            (out_dir / clip.name).unlink(missing_ok=True)
            print(f"error: {error}", file=sys.stderr)
            return EXIT_PIN
    print(f"source: {ATTRIBUTION}, {DATASET}@{REVISION}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
