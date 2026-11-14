"""Phase-3-Research: zweiter Durchgang für Dateien ohne Wörter.

Varianten je Datei (nur erste 30 s):
  vad03  Silero-Schwelle 0,3, Mindestsprache 0,1 s (VAD bleibt an)
  vad02  Silero-Schwelle 0,2, Mindestsprache 0,1 s
  novad  ganze 30 s ohne VAD an Parakeet (nur zum Vergleich, nicht als Produktweg)
python -I shortpass.py <models_dir> <out_json> <wav> [<wav> ...]
"""
import json
import math
import pathlib
import sys
import wave

import numpy as np
import sherpa_onnx

SR = 16000
PAD = SR // 2
MODELS = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])

rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(MODELS / "parakeet" / "encoder.int8.onnx"), decoder=str(MODELS / "parakeet" / "decoder.int8.onnx"),
    joiner=str(MODELS / "parakeet" / "joiner.int8.onnx"), tokens=str(MODELS / "parakeet" / "tokens.txt"),
    num_threads=2, model_type="nemo_transducer", decoding_method="greedy_search")


def rd(p: pathlib.Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def decode(a: np.ndarray) -> list[tuple[str, float]]:
    s = np.pad(a, (PAD, PAD))
    st = rec.create_stream()
    st.accept_waveform(SR, s)
    rec.decode_stream(st)
    r = st.result
    lp = list(r.ys_log_probs) if len(r.ys_log_probs) == len(r.tokens) else [0.0] * len(r.tokens)
    ww: list[list] = []
    for tok, l in zip(r.tokens, lp):
        if tok.startswith(" ") or not ww:
            ww.append([tok.strip(), [l]])
        else:
            ww[-1][0] += tok
            ww[-1][1].append(l)
    return [(w, round(math.exp(min(l_)), 3)) for w, l_ in ww if w]


def vad(a: np.ndarray, thr: float) -> list[tuple[int, int]]:
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(MODELS / "vad" / "silero_vad.onnx")
    cfg.silero_vad.min_silence_duration = 0.3
    cfg.silero_vad.min_speech_duration = 0.1
    cfg.silero_vad.max_speech_duration = 25
    cfg.silero_vad.threshold = thr
    cfg.sample_rate = SR
    cfg.num_threads = 1
    v = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=60)
    ws = cfg.silero_vad.window_size
    segs = []
    for i in range(0, len(a), ws):
        v.accept_waveform(a[i:i + ws])
        while not v.empty():
            segs.append((v.front.start, len(v.front.samples)))
            v.pop()
    v.flush()
    while not v.empty():
        segs.append((v.front.start, len(v.front.samples)))
        v.pop()
    return segs


res = {}
for arg in sys.argv[3:]:
    p = pathlib.Path(arg)
    a = rd(p)[: 30 * SR]
    out = {}
    for name, thr in (("vad03", 0.3), ("vad02", 0.2)):
        segs = vad(a, thr)
        words = []
        for st, n in segs:
            s0 = max(0, st - int(0.4 * SR))
            words += decode(a[s0: st + n + int(0.4 * SR)])
        out[name] = {"speech_s": round(sum(n for _, n in segs) / SR, 2), "words": words}
    out["novad"] = {"words": decode(a)}
    res[p.stem] = out
    print(p.stem, {k: len(v["words"]) for k, v in out.items()}, flush=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
