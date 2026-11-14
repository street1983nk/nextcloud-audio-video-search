"""Phase-3-Research: Medienkorpus fuer "keine Sprache" / "Sprache nicht unterstuetzt" laden.

Nur oeffentliche Quellen (FLEURS CC-BY-4.0, Wikimedia Commons PD/CC), Ablage nur im Scratchpad.
python -I fetch_corpus.py <corpus_dir>
Ergebnis: <corpus_dir>/wav/<name>.wav (16 kHz mono s16), <corpus_dir>/sources.json
"""
import hashlib
import json
import pathlib
import subprocess
import sys
import tarfile
import urllib.request

FF = r"C:/Users/Student/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffmpeg.exe"
UA = {"User-Agent": "research-script/1.0"}
ROOT = pathlib.Path(sys.argv[1])
DL = ROOT / "dl"
WAV = ROOT / "wav"
DL.mkdir(parents=True, exist_ok=True)
WAV.mkdir(parents=True, exist_ok=True)
SOURCES: dict[str, dict] = {}

FLEURS = {
    # Instanz-Sprachen
    "de_de": 15, "en_us": 15, "fr_fr": 15,
    # von Parakeet v3 unterstuetzt, nicht Instanz
    "es_419": 10, "it_it": 10, "pl_pl": 10, "nl_nl": 10, "ru_ru": 10, "el_gr": 10,
    # von Parakeet v3 nicht unterstuetzt
    "tr_tr": 10, "ar_eg": 10, "cmn_hans_cn": 10, "ja_jp": 10, "hi_in": 10, "vi_vn": 10, "sw_ke": 10,
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


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def to_wav(src: pathlib.Path, dst: pathlib.Path) -> None:
    subprocess.run([FF, "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:a:0", "-ac", "1",
                    "-ar", "16000", "-c:a", "pcm_s16le", str(dst)], check=True)


def fleurs(code: str, want: int) -> None:
    d = DL / f"fleurs_{code}"
    d.mkdir(exist_ok=True)
    base = f"https://huggingface.co/datasets/google/fleurs/resolve/main/data/{code}/"
    tsv = get(base + "test.tsv").decode("utf-8")
    rows = {}
    for line in tsv.splitlines():
        p = line.split("\t")
        rows[p[1]] = (p[0], p[2])
    seen, got = set(), []
    resp = urllib.request.urlopen(urllib.request.Request(base + "audio/test.tar.gz", headers=UA), timeout=300)
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
            assert f is not None
            raw.write_bytes(f.read())
            stem = f"fleurs_{code}_{len(got):02d}"
            to_wav(raw, WAV / f"{stem}.wav")
            SOURCES[stem] = {"src": f"hf:google/fleurs data/{code}/audio/test.tar.gz", "file": nm,
                             "ref": rows[nm][1], "license": "CC-BY-4.0"}
            got.append(stem)
            if len(got) >= want:
                break
    resp.close()
    print(code, len(got), flush=True)


def commons(name: str, url: str) -> None:
    ext = url.rsplit(".", 1)[-1]
    raw = DL / f"{name}.{ext}"
    data = get(url)
    raw.write_bytes(data)
    to_wav(raw, WAV / f"{name}.wav")
    SOURCES[name] = {"src": url, "sha256": hashlib.sha256(data).hexdigest(), "license": "siehe Commons-Seite"}
    print(name, flush=True)


if __name__ == "__main__":
    for c, n in FLEURS.items():
        fleurs(c, n)
    for k, u in COMMONS.items():
        commons(k, u)
    (ROOT / "sources.json").write_text(json.dumps(SOURCES, ensure_ascii=False, indent=1), encoding="utf-8")
