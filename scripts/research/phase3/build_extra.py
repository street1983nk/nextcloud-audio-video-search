"""Phase-3-Research: verschlechterte Instanz-Sprache (darf von der Abfangregel nicht verworfen werden).

python -I build_extra.py <corpus_dir>  -> <corpus_dir>/extra/*.wav
Rauschen SNR 5 und 0 dB (rosa), Stimmengewirr SNR 5 dB (6 fremde FLEURS-Spuren), Telefonband 300-3400 Hz.
"""
import pathlib
import subprocess
import sys
import wave

import numpy as np

FF = r"C:/Users/Student/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffmpeg.exe"
SR = 16000
ROOT = pathlib.Path(sys.argv[1])
TEST = ROOT / "test"
OUT = ROOT / "extra"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(5)


def rd(p: pathlib.Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def wr(p: pathlib.Path, a: np.ndarray) -> None:
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def rms(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)


def pink(n: int) -> np.ndarray:
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    return np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(f), n).astype(np.float32)


def at_snr(speech: np.ndarray, noise: np.ndarray, snr: float) -> np.ndarray:
    active = speech[np.abs(speech) > 0.01]
    s = rms(active if len(active) else speech)
    return speech + noise / rms(noise) * s * 10 ** (-snr / 20)


babble_src = [rd(TEST / f"lang_{c}.wav") for c in ("es_419", "it_it", "pl_pl", "nl_nl", "ru_ru", "tr_tr")]
for code in ("de_de", "en_us", "fr_fr"):
    sp = rd(TEST / f"lang_{code}.wav")
    n = len(sp)
    wr(OUT / f"deg_pink5_{code}.wav", at_snr(sp, pink(n), 5))
    wr(OUT / f"deg_pink0_{code}.wav", at_snr(sp, pink(n), 0))
    bab = sum(np.resize(b, n) for b in babble_src)
    wr(OUT / f"deg_babble5_{code}.wav", at_snr(sp, bab, 5))
    subprocess.run([FF, "-nostdin", "-loglevel", "error", "-y", "-i", str(TEST / f"lang_{code}.wav"), "-af",
                    "highpass=f=300,lowpass=f=3400", "-ar", "8000", "-c:a", "pcm_mulaw", str(OUT / f"tmp_{code}.wav")],
                   check=True)
    subprocess.run([FF, "-nostdin", "-loglevel", "error", "-y", "-i", str(OUT / f"tmp_{code}.wav"), "-ar", "16000",
                    "-c:a", "pcm_s16le", str(OUT / f"deg_tel_{code}.wav")], check=True)
    (OUT / f"tmp_{code}.wav").unlink()
print(len(list(OUT.glob("*.wav"))))
