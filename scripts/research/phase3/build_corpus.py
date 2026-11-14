# pyright: reportMissingImports=false
# numpy, sherpa_onnx und py3langid gehören zur Messumgebung, nicht zur Umgebung des Backends.
"""Phase-3-Research: abgeleitete Testdateien aus dem geladenen Korpus bauen (alles 16 kHz mono s16).

python -I build_corpus.py <corpus_dir>   -> <corpus_dir>/test/<name>.wav
"""

import pathlib
import sys
import wave

import numpy as np

SR = 16000
ROOT = pathlib.Path(sys.argv[1])
WAV = ROOT / "wav"
OUT = ROOT / "test"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(3)


def rd(p: pathlib.Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def wr(name: str, a: np.ndarray) -> None:
    a = np.clip(a, -1, 1)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def sil(s: float) -> np.ndarray:
    return np.zeros(int(s * SR), dtype=np.float32)


def rms(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)


def dbfs(a: np.ndarray, level: float) -> np.ndarray:
    return a / rms(a) * 10 ** (level / 20)


def colored(n: int, kind: str) -> np.ndarray:
    white = rng.standard_normal(n)
    if kind == "white":
        return white.astype(np.float32)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    spec = np.fft.rfft(white) / (np.sqrt(f) if kind == "pink" else f)
    return np.fft.irfft(spec, n).astype(np.float32)


def clips(code: str) -> list[np.ndarray]:
    return [rd(p) for p in sorted(WAV.glob(f"fleurs_{code}_*.wav"))]


def cat(parts: list[np.ndarray], gap: float = 0.6) -> np.ndarray:
    out = []
    for p in parts:
        out += [p, sil(gap)]
    return np.concatenate(out)


langs = sorted({p.stem.split("_", 1)[1].rsplit("_", 1)[0] for p in WAV.glob("fleurs_*.wav")})
for code in langs:
    wr(f"lang_{code}", cat(clips(code)))

# kurze Sprachmemos: Einzelclips DE/EN/FR (je 15) und 3-s-Anschnitte (je 5)
for code in ("de_de", "en_us", "fr_fr"):
    for i, c in enumerate(clips(code)):
        wr(f"memo_{code}_{i:02d}", c)
    for i, c in enumerate(clips(code)[:5]):
        wr(f"memo3s_{code}_{i:02d}", c[: 3 * SR])

de, en, fr = clips("de_de"), clips("en_us"), clips("fr_fr")
# Memo in langer Stille / Rauschen / Musik
wr("memo_de_in_5min_silence", np.concatenate([sil(20), de[0], sil(280)]))
noise = dbfs(colored(300 * SR, "pink"), -40)
wr("memo_de_in_5min_pink40", noise + np.concatenate([sil(20), de[1], sil(300 - 20 - len(de[1]) / SR)])[: len(noise)])
music = rd(WAV / "music_nocturne.wav")[: 300 * SR]
speech = np.concatenate([sil(60), de[2], sil(len(music) / SR - 60 - len(de[2]) / SR)])[: len(music)]
wr("memo_de_over_music_snr10", dbfs(music, -30) + speech / rms(de[2]) * 10 ** (-20 / 20))
wr("memo_de_over_music_snr0", dbfs(music, -20) + speech / rms(de[2]) * 10 ** (-20 / 20))
wr("podcast_music3min_then_de", np.concatenate([music[: 180 * SR] * 0.5, cat(de[3:8])]))

# Nicht-Sprache synthetisch
wr("ns_silence_5min", sil(300))
wr("ns_white45_5min", dbfs(colored(300 * SR, "white"), -45))
wr("ns_pink25_5min", dbfs(colored(300 * SR, "pink"), -25))
wr("ns_brown20_5min", dbfs(colored(300 * SR, "brown"), -20))
t = np.arange(120 * SR) / SR
wr("ns_sine440_2min", (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))
wr("ns_hum50_2min", (0.2 * np.sin(2 * np.pi * 50 * t) + 0.05 * np.sin(2 * np.pi * 150 * t)).astype(np.float32))

# Musik und Gesang unverändert
for p in sorted(WAV.glob("music_*.wav")) + sorted(WAV.glob("sing_*.wav")):
    wr(p.stem, rd(p))

# Gemischte Dateien
es, tr, ar = clips("es_419"), clips("tr_tr"), clips("ar_eg")
wr("mix_de50_es50", cat([x for pair in zip(de[:8], es[:8], strict=False) for x in pair]))
wr("mix_de20_tr80", cat(de[:2] + tr[:8]))
wr("mix_de10_ar90", cat(de[:1] + ar[:9]))
wr("mix_fr30_ja70", cat(fr[:3] + clips("ja_jp")[:7]))
print(len(list(OUT.glob("*.wav"))), "Testdateien")
