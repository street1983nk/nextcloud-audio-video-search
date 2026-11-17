"""Phase-3-Research: Medienkorpus für "keine Sprache" / "Sprache nicht unterstützt" laden.

Nur öffentliche Quellen (FLEURS CC-BY-4.0, Wikimedia Commons PD/CC), Ablage nur im angegebenen Ordner.
python -I fetch_corpus.py [--ffmpeg PFAD] <corpus_dir>
ffmpeg kommt aus --ffmpeg, sonst aus der Umgebungsvariable AVS_FFMPEG, sonst aus PATH.
Ergebnis: <corpus_dir>/wav/<name>.wav (16 kHz mono s16), <corpus_dir>/sources.json
"""

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass, field

UA = {"User-Agent": "research-script/1.0"}

FLEURS = {
    # Instanz-Sprachen
    "de_de": 15,
    "en_us": 15,
    "fr_fr": 15,
    # von Parakeet v3 unterstützt, nicht Instanz
    "es_419": 10,
    "it_it": 10,
    "pl_pl": 10,
    "nl_nl": 10,
    "ru_ru": 10,
    "el_gr": 10,
    # von Parakeet v3 nicht unterstützt
    "tr_tr": 10,
    "ar_eg": 10,
    "cmn_hans_cn": 10,
    "ja_jp": 10,
    "hi_in": 10,
    "vi_vn": 10,
    "sw_ke": 10,
}

COMMONS = {
    "music_nocturne": "https://upload.wikimedia.org/wikipedia/commons/d/de/A_Midsummer_Night%27s_Dream%2C_Op._61_-_Nocturne.ogg",
    "music_scherzo": "https://upload.wikimedia.org/wikipedia/commons/7/71/A_Midsummer_Night%27s_Dream_Op._61_Scherzo_%28Mendelssohn%29_European_Archive.ogg",
    "music_band_rock": "https://upload.wikimedia.org/wikipedia/commons/4/4d/America_-_Blue_Aces_-_United_States_Air_Force_Heritage_of_America_Band.mp3",
    "sing_de_spohr_wiegenlied": "https://upload.wikimedia.org/wikipedia/commons/b/b0/Louis_Spohr_-_Wiegenlied.ogg",
    "sing_de_spohr_seistill": "https://upload.wikimedia.org/wikipedia/commons/d/d7/Louis_Spohr_-_Sei_Still_Mein_Herz.ogg",
    "sing_de_senfl_acap": "https://upload.wikimedia.org/wikipedia/commons/7/7f/Ludwig_Senfl_--_Ach_Elslein.opus",
    "sing_choir_mendelssohn": "https://upload.wikimedia.org/wikipedia/commons/2/2e/A_Midsummer_Night%27s_Dream_Op._61_Song_with_choir_%28Mendelssohn%29_European_Archive.ogg",
    "sing_en_bowlly_guilty": "https://upload.wikimedia.org/wikipedia/commons/9/99/Al_Bowly_-_Guilty.ogg",
    "sing_en_california": "https://upload.wikimedia.org/wikipedia/commons/8/89/%22I_Love_You%2C_California%22%2C_by_Knickerbocker_Quartet_and_Elizabeth_Spencer_%28cusb-cyl5053d%29.oga",
    "sing_fr_debussy": "https://upload.wikimedia.org/wikipedia/commons/e/e6/Claude_Debussy_-_Aupr%C3%A8s_de_cette_grotte_sombre.flac",
    "sing_fr_bruant_nini": "https://upload.wikimedia.org/wikipedia/commons/e/e8/Aristide_Bruant_Nini%2C_peau_d%27chien_1905.ogg",
    "sing_fr_choir_faure": "https://upload.wikimedia.org/wikipedia/commons/a/af/Petits_Chanteurs_de_Passy_-_Cantique_de_Racine_de_Gabriel_Faure.ogg",
}

FFMPEG_MISSING = "ffmpeg not found: pass --ffmpeg or set AVS_FFMPEG"


def ffmpeg_binary(argv_value: str | None) -> str:
    """ffmpeg in der Reihenfolge --ffmpeg, AVS_FFMPEG, PATH; fehlt es, Abbruch mit Exit 2."""
    chosen = argv_value or os.environ.get("AVS_FFMPEG") or "ffmpeg"
    found = shutil.which(chosen)
    if found is None:
        print(f"{FFMPEG_MISSING} (tried {chosen!r})", file=sys.stderr)
        raise SystemExit(2)
    return found


def split_ffmpeg(argv: list[str]) -> tuple[str | None, list[str]]:
    """Option --ffmpeg aus der Argumentliste lösen; die Positionsargumente bleiben in ihrer Reihenfolge."""
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--ffmpeg")
    known, rest = parser.parse_known_args(argv)
    return known.ffmpeg, rest


@dataclass
class Corpus:
    root: pathlib.Path
    ff: str
    sources: dict[str, dict] = field(default_factory=dict)

    @property
    def dl(self) -> pathlib.Path:
        return self.root / "dl"

    @property
    def wav(self) -> pathlib.Path:
        return self.root / "wav"


def open_corpus(argv: list[str]) -> Corpus:
    ff_value, rest = split_ffmpeg(argv)
    ff = ffmpeg_binary(ff_value)
    if len(rest) != 1:
        print("usage: python -I fetch_corpus.py [--ffmpeg PFAD] <corpus_dir>", file=sys.stderr)
        raise SystemExit(2)
    corpus = Corpus(pathlib.Path(rest[0]), ff)
    corpus.dl.mkdir(parents=True, exist_ok=True)
    corpus.wav.mkdir(parents=True, exist_ok=True)
    return corpus


def get(url: str) -> bytes:
    # feste https-Adressen aus diesem Skript
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:  # noqa: S310
        return r.read()


def to_wav(ff: str, src: pathlib.Path, dst: pathlib.Path) -> None:
    # Argumentliste ohne Shell, ffmpeg wählt der Aufrufer
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


def fleurs(corpus: Corpus, code: str, want: int) -> None:
    d = corpus.dl / f"fleurs_{code}"
    d.mkdir(exist_ok=True)
    base = f"https://huggingface.co/datasets/google/fleurs/resolve/main/data/{code}/"
    tsv = get(base + "test.tsv").decode("utf-8")
    rows = {}
    for line in tsv.splitlines():
        p = line.split("\t")
        rows[p[1]] = (p[0], p[2])
    seen, got = set(), []
    # feste https-Adresse aus diesem Skript
    resp = urllib.request.urlopen(urllib.request.Request(base + "audio/test.tar.gz", headers=UA), timeout=300)  # noqa: S310
    with tarfile.open(fileobj=resp, mode="r|gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            nm = pathlib.Path(m.name).name
            if nm not in rows or rows[nm][0] in seen:
                continue
            seen.add(rows[nm][0])
            raw = d / nm
            f = tf.extractfile(m)
            if f is None:
                raise RuntimeError(f"tar member without data: {nm}")
            raw.write_bytes(f.read())
            stem = f"fleurs_{code}_{len(got):02d}"
            to_wav(corpus.ff, raw, corpus.wav / f"{stem}.wav")
            corpus.sources[stem] = {
                "src": f"hf:google/fleurs data/{code}/audio/test.tar.gz",
                "file": nm,
                "ref": rows[nm][1],
                "license": "CC-BY-4.0",
            }
            got.append(stem)
            if len(got) >= want:
                break
    resp.close()
    print(code, len(got), flush=True)


def commons(corpus: Corpus, name: str, url: str) -> None:
    ext = url.rsplit(".", 1)[-1]
    raw = corpus.dl / f"{name}.{ext}"
    data = get(url)
    raw.write_bytes(data)
    to_wav(corpus.ff, raw, corpus.wav / f"{name}.wav")
    corpus.sources[name] = {
        "src": url,
        "sha256": hashlib.sha256(data).hexdigest(),
        "license": "siehe Commons-Seite",
    }
    print(name, flush=True)


if __name__ == "__main__":
    corpus = open_corpus(sys.argv[1:])
    for c, n in FLEURS.items():
        fleurs(corpus, c, n)
    for k, u in COMMONS.items():
        commons(corpus, k, u)
    (corpus.root / "sources.json").write_text(
        json.dumps(corpus.sources, ensure_ascii=False, indent=1), encoding="utf-8"
    )
