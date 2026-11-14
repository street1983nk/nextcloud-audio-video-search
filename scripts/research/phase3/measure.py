"""Phase-3-Research: Parakeet-Vorschau (Spike-3-Standard, Schluck-Waechter 1,0) auf dem Korpus.

python -I measure.py <models_dir> <stop_dir> <out_dir> <wav> [<wav> ...]
Je Datei <out_dir>/<stem>.json mit VAD-Anteil, Woertern (Text, Start, Ende, Konfidenz) und Fenstern samt
Sprach-Merkmalen (Schrift, Stoppwort-Sprache, py3langid). Ein Prozess, ein Modell, 2 Threads.
"""
import json
import math
import pathlib
import sys
import time
import unicodedata
import wave

import numpy as np
import py3langid
import sherpa_onnx

SR = 16000
PAD = SR // 2
CTX = int(0.4 * SR)
WIN = 25.0
GUARD = 1.0
INSTANCE = ("de", "en", "fr")

MODELS = pathlib.Path(sys.argv[1])
STOP = pathlib.Path(sys.argv[2])
OUT = pathlib.Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

SNOWBALL = {"german": "de", "english": "en", "french": "fr", "spanish": "es", "italian": "it", "dutch": "nl",
            "portuguese": "pt", "russian": "ru", "swedish": "sv", "danish": "da", "norwegian": "no",
            "finnish": "fi", "hungarian": "hu"}
STOPWORDS: dict[str, set[str]] = {}
for name, code in SNOWBALL.items():
    words = set()
    for line in (STOP / f"{name}.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        w = line.split("|", 1)[0].strip().lower()
        if w:
            words.add(unicodedata.normalize("NFC", w))
    STOPWORDS[code] = words


def read_pcm(p: pathlib.Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def safe(s: np.ndarray) -> np.ndarray:
    return np.pad(s, (0, SR // 2 - len(s))) if len(s) < SR // 2 else s


def tokens_of(text: str) -> list[str]:
    out = []
    for raw in text.lower().split():
        w = "".join(ch for ch in unicodedata.normalize("NFC", raw) if ch.isalpha() or ch == "'")
        w = w.strip("'")
        if w:
            out.append(w)
    return out


def latin_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 1.0
    lat = sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, ""))
    return lat / len(letters)


def stop_lang(text: str) -> tuple[str | None, dict[str, float]]:
    toks = tokens_of(text)
    if not toks:
        return None, {}
    quotes = {code: sum(1 for t in toks if t in sw) / len(toks) for code, sw in STOPWORDS.items()}
    best = max(quotes, key=lambda c: quotes[c])
    return (best if quotes[best] > 0 else None), {k: round(v, 3) for k, v in quotes.items()}


LANGID = py3langid.langid.LanguageIdentifier.from_modelpath(py3langid.langid.MODEL_DIR / py3langid.langid.MODEL_FILE, norm_probs=True)


def lid(text: str) -> tuple[str, float]:
    if not text.strip():
        return "", 0.0
    lang, prob = LANGID.classify(text)
    return lang, round(float(prob), 3)


rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(MODELS / "parakeet" / "encoder.int8.onnx"), decoder=str(MODELS / "parakeet" / "decoder.int8.onnx"),
    joiner=str(MODELS / "parakeet" / "joiner.int8.onnx"), tokens=str(MODELS / "parakeet" / "tokens.txt"),
    num_threads=2, model_type="nemo_transducer", decoding_method="greedy_search")


def vad_segments(a: np.ndarray) -> list[tuple[int, int]]:
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(MODELS / "vad" / "silero_vad.onnx")
    cfg.silero_vad.min_silence_duration = 0.3
    cfg.silero_vad.min_speech_duration = 0.25
    cfg.silero_vad.max_speech_duration = 25
    cfg.silero_vad.threshold = 0.5
    cfg.sample_rate = SR
    cfg.num_threads = 1
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=60)
    ws = cfg.silero_vad.window_size
    segs = []
    for i in range(0, len(a), ws):
        vad.accept_waveform(a[i:i + ws])
        while not vad.empty():
            segs.append((vad.front.start, len(vad.front.samples)))
            vad.pop()
    vad.flush()
    while not vad.empty():
        segs.append((vad.front.start, len(vad.front.samples)))
        vad.pop()
    return segs


def dec_span(a: np.ndarray, ms: int, me: int) -> list[tuple[str, float, float, float]]:
    s0 = max(0, ms - CTX)
    s = np.pad(safe(a[s0:me + CTX]), (PAD, PAD))
    st = rec.create_stream()
    st.accept_waveform(SR, s)
    rec.decode_stream(st)
    r = st.result
    off = s0 / SR - PAD / SR
    lp = list(r.ys_log_probs) if len(r.ys_log_probs) == len(r.tokens) else [0.0] * len(r.tokens)
    ww: list[list] = []
    for tok, t, l in zip(r.tokens, r.timestamps, lp):
        if tok.startswith(" ") or not ww:
            ww.append([tok.strip(), t + off, t + off + 0.08, [l]])
        else:
            ww[-1][0] += tok
            ww[-1][2] = t + off + 0.08
            ww[-1][3].append(l)
    return [(w, round(s_, 3), round(e_, 3), round(math.exp(min(l_)), 4)) for w, s_, e_, l_ in ww if w]


def run(path: pathlib.Path) -> dict:
    a = read_pcm(path)
    t0 = time.perf_counter()
    segs = vad_segments(a)
    merged: list[tuple[int, int, list]] = []
    for st, n in segs:
        if merged and st - merged[-1][1] <= 2 * SR and st + n - merged[-1][0] <= WIN * SR:
            merged[-1] = (merged[-1][0], st + n, merged[-1][2] + [(st, n)])
            continue
        merged.append((st, st + n, [(st, n)]))
    words, wins = [], []
    for ms, me, sl in merged:
        ww = dec_span(a, ms, me)
        if len(sl) > 1:
            for st, n in sl:
                d_ = n / SR
                if d_ < 1.0:
                    continue
                inside = [w for w in ww if st / SR - 0.3 <= w[1] <= (st + n) / SR + 0.3]
                if len(inside) < GUARD * d_:
                    nw_ = dec_span(a, st, st + n)
                    if len(nw_) > len(inside):
                        ww = [w for w in ww if not (st / SR - 0.3 <= w[1] <= (st + n) / SR + 0.3)] + nw_
                        ww.sort(key=lambda w: w[1])
        text = " ".join(w[0] for w in ww)
        sl_lang, quotes = stop_lang(text)
        li, lp_ = lid(text)
        wins.append({"s": round(ms / SR, 3), "e": round(me / SR, 3), "speech_s": round(sum(n for _, n in sl) / SR, 3),
                     "nw": len(ww), "text": text, "conf_mean": round(float(np.mean([w[3] for w in ww])), 4) if ww else None,
                     "latin": round(latin_share(text), 3), "stop_lang": sl_lang,
                     "stop_inst": round(sum(quotes.get(c, 0) for c in INSTANCE), 3) if quotes else 0.0,
                     "stop_best": max(quotes.values()) if quotes else 0.0,
                     "lid": li, "lid_p": lp_})
        words += ww
    full = " ".join(w[0] for w in words)
    fl, fq = stop_lang(full)
    li, lp_ = lid(full)
    return {"file": path.stem, "dur_s": round(len(a) / SR, 2), "proc_s": round(time.perf_counter() - t0, 2),
            "speech_s": round(sum(n for _, n in segs) / SR, 2), "n_segs": len(segs), "n_words": len(words),
            "conf_mean": round(float(np.mean([w[3] for w in words])), 4) if words else None,
            "latin": round(latin_share(full), 3), "stop_lang": fl, "stop_quotes": fq, "lid": li, "lid_p": lp_,
            "text": full, "words": words, "windows": wins}


for arg in sys.argv[4:]:
    p = pathlib.Path(arg)
    res = run(p)
    (OUT / f"{p.stem}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(p.stem, res["dur_s"], res["speech_s"], res["n_words"], res["lid"], res["lid_p"], flush=True)
