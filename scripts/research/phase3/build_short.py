"""Phase-3-Research: echte Kurzmemos (1 bis 4 Wörter) an Wortgrenzen geschnitten, mit 0,5 s Stille davor und danach.

Schnittpunkte aus den Parakeet-Wortzeiten der vollen Clips (results/memo_*.json): Ende des k-ten Worts + 0,25 s.
python -I build_short.py <corpus_dir> <results_dir>  -> <corpus_dir>/short/*.wav
"""

import json
import pathlib
import sys
import wave

import numpy as np

SR = 16000
ROOT = pathlib.Path(sys.argv[1])
RES = pathlib.Path(sys.argv[2])
OUT = ROOT / "short"
OUT.mkdir(exist_ok=True)


def rd(p: pathlib.Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def wr(p: pathlib.Path, a: np.ndarray) -> None:
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(a.astype(np.int16).tobytes())


n = 0
for code in ("de_de", "en_us", "fr_fr"):
    for i in range(15):
        res = json.loads((RES / f"memo_{code}_{i:02d}.json").read_text(encoding="utf-8"))
        words = res["words"]
        if len(words) < 5:
            continue
        a = rd(ROOT / "test" / f"memo_{code}_{i:02d}.wav")
        for k in (1, 2, 4):
            if i % 3 != k % 3:
                continue  # je Clip nur eine Länge, damit es verschiedene Sprecher sind
            start = max(0.0, words[0][1] - 0.3)
            end = words[k - 1][2] + 0.25
            nxt = words[k][1]
            end = min(end, nxt - 0.02)
            piece = a[int(start * SR) : int(end * SR)]
            pad = np.zeros(SR // 2, dtype=np.int16)
            wr(OUT / f"short{k}w_{code}_{i:02d}.wav", np.concatenate([pad, piece, pad]))
            n += 1
print(n)
