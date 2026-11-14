"""The Parakeet preview: VAD, windows, decoding, swallow guard and catch rule (plan 03-10).

TRANS-01: the pipeline is ``scripts/research/phase3/measure.py`` 1:1 (itself
Spike 3 ``bench3.py``), with the measured values of engine/constants.py; only
names differ, and times are whole milliseconds of media time instead of rounded
seconds of the file. TRANS-02: the VAD is always on; the second pass of D-03-16
only lowers its threshold and its minimum speech. TRANS-08: every word time is
the offset of the chunk in the medium plus the token time in the decoded span.
TRANS-03: each merged window gets the catch rule (engine/catch.window_verdict);
a window that is not kept carries no word out of the child, only its counts.

sherpa_onnx and py3langid are imported when an Engine is built, never at module
level: the main process imports this module for Window and EngineWord, and the
native runtime belongs to the child only (engine/child.py).
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from audio_video_search_backend.engine.catch import KEEP, latin_share, window_verdict
from audio_video_search_backend.engine.constants import (
    CONTEXT_S,
    DECODING_METHOD,
    GUARD_MIN_S,
    GUARD_SLACK_S,
    GUARD_WORDS_PER_S,
    MERGE_GAP_S,
    MIN_DECODE_S,
    MODEL_TYPE,
    PAD_S,
    RECOGNIZER_THREADS,
    SAMPLE_RATE,
    SECOND_PASS_MIN_SPEECH_S,
    SECOND_PASS_THRESHOLD,
    TOKEN_S,
    VAD_BUFFER_S,
    VAD_MAX_SPEECH_S,
    VAD_MIN_SILENCE_S,
    VAD_MIN_SPEECH_S,
    VAD_THREADS,
    VAD_THRESHOLD,
    WINDOW_MAX_S,
)
from audio_video_search_backend.models.procure import model_dir

_PAD = int(PAD_S * SAMPLE_RATE)
_CONTEXT = int(CONTEXT_S * SAMPLE_RATE)
_MIN_DECODE = int(MIN_DECODE_S * SAMPLE_RATE)
_MERGE_GAP = int(MERGE_GAP_S * SAMPLE_RATE)
_WINDOW_MAX = int(WINDOW_MAX_S * SAMPLE_RATE)


@dataclass(frozen=True, slots=True)
class EngineWord:
    """One recognised word with its media time in milliseconds and its confidence."""

    text: str
    start_ms: int
    end_ms: int
    conf: float


@dataclass(frozen=True, slots=True)
class Window:
    """One merged VAD window: media time, VAD speech, word count and verdict.

    ``words`` is empty unless the verdict is KEEP. The language features are the
    ones the verdict was made from (latin share, text language and its
    probability, mean word confidence).
    """

    start_ms: int
    end_ms: int
    speech_ms: int
    n_words: int
    verdict: str
    words: tuple[EngineWord, ...]
    latin: float = 1.0
    lid: str = ""
    lid_p: float = 0.0
    conf_mean: float = 0.0


def _ms(samples: int) -> int:
    return samples * 1000 // SAMPLE_RATE


def vad_values(*, second_pass: bool) -> tuple[float, float]:
    """The Silero threshold and minimum speech of a pass (D-03-16: the VAD stays on)."""
    if second_pass:
        return SECOND_PASS_THRESHOLD, SECOND_PASS_MIN_SPEECH_S
    return VAD_THRESHOLD, VAD_MIN_SPEECH_S


def merge_segments(segments: list[tuple[int, int]]) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """VAD segments (start, samples) as windows (start, end, parts): gap up to 2 s, window up to 25 s."""
    merged: list[tuple[int, int, list[tuple[int, int]]]] = []
    for start, count in segments:
        if merged and start - merged[-1][1] <= _MERGE_GAP and start + count - merged[-1][0] <= _WINDOW_MAX:
            merged[-1] = (merged[-1][0], start + count, [*merged[-1][2], (start, count)])
            continue
        merged.append((start, start + count, [(start, count)]))
    return merged


def words_from_tokens(
    tokens: list[str], timestamps: list[float], log_probs: list[float], *, span_offset_s: float, offset_ms: int
) -> list[EngineWord]:
    """Tokens of one decoded span as words in media time.

    A token with a leading space starts a word. The time of a word is the token
    time plus the place of the span in the chunk (context and padding included)
    plus the offset of the chunk; its end is the last token plus one token
    length; its confidence is exp of the lowest token log probability. Without
    one log probability per token every token counts as certain.
    """
    probs = list(log_probs) if len(log_probs) == len(tokens) else [0.0] * len(tokens)
    parts: list[tuple[str, float, float, list[float]]] = []
    for token, time, log_prob in zip(tokens, timestamps, probs, strict=False):
        at = time + span_offset_s
        if token.startswith(" ") or not parts:
            parts.append((token.strip(), at, at + TOKEN_S, [log_prob]))
        else:
            text, start, _, logs = parts[-1]
            parts[-1] = (text + token, start, at + TOKEN_S, [*logs, log_prob])
    return [
        EngineWord(
            text=text,
            start_ms=offset_ms + round(start * 1000),
            end_ms=offset_ms + round(end * 1000),
            conf=round(math.exp(min(logs)), 4),
        )
        for text, start, end, logs in parts
        if text
    ]


def language_identifier() -> Any:
    """The py3langid identifier of measure.py, with normalised probabilities.

    Only the langid module of py3langid is loaded, never its HTTP server module (plan 03-01).
    """
    from py3langid import langid  # loaded in the child only

    return langid.LanguageIdentifier.from_modelpath(langid.MODEL_DIR / langid.MODEL_FILE, norm_probs=True)


class Engine:
    """Parakeet-TDT-0.6B-v3 int8 with Silero VAD, built once per child."""

    def __init__(self, models_root: Path) -> None:
        import sherpa_onnx  # the native runtime is loaded in the child only

        self._sherpa = sherpa_onnx
        parakeet = model_dir(models_root, "parakeet")
        self._vad_model = str(model_dir(models_root, "silero") / "silero_vad.onnx")
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(parakeet / "encoder.int8.onnx"),
            decoder=str(parakeet / "decoder.int8.onnx"),
            joiner=str(parakeet / "joiner.int8.onnx"),
            tokens=str(parakeet / "tokens.txt"),
            num_threads=RECOGNIZER_THREADS,
            model_type=MODEL_TYPE,
            decoding_method=DECODING_METHOD,
        )
        self._identifier = language_identifier()

    def _segments(self, pcm: np.ndarray, *, second_pass: bool) -> list[tuple[int, int]]:
        """The Silero speech segments (start sample, sample count) of the PCM."""
        threshold, min_speech = vad_values(second_pass=second_pass)
        config = self._sherpa.VadModelConfig()
        config.silero_vad.model = self._vad_model
        config.silero_vad.min_silence_duration = VAD_MIN_SILENCE_S
        config.silero_vad.min_speech_duration = min_speech
        config.silero_vad.max_speech_duration = VAD_MAX_SPEECH_S
        config.silero_vad.threshold = threshold
        config.sample_rate = SAMPLE_RATE
        config.num_threads = VAD_THREADS
        vad = self._sherpa.VoiceActivityDetector(config, buffer_size_in_seconds=VAD_BUFFER_S)
        step = config.silero_vad.window_size
        segments: list[tuple[int, int]] = []
        for index in range(0, len(pcm), step):
            vad.accept_waveform(pcm[index : index + step])
            while not vad.empty():
                segments.append((vad.front.start, len(vad.front.samples)))
                vad.pop()
        vad.flush()
        while not vad.empty():
            segments.append((vad.front.start, len(vad.front.samples)))
            vad.pop()
        return segments

    def _decode(self, samples: np.ndarray) -> tuple[list[str], list[float], list[float]]:
        """Tokens, token times in seconds and token log probabilities of one padded span."""
        stream = self._recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        self._recognizer.decode_stream(stream)
        result = stream.result
        return list(result.tokens), list(result.timestamps), list(result.ys_log_probs)

    def _language(self, text: str) -> tuple[str, float]:
        if not text.strip():
            return "", 0.0
        language, probability = self._identifier.classify(text)
        return language, round(float(probability), 3)

    def _decode_span(self, pcm: np.ndarray, start: int, end: int, offset_ms: int) -> list[EngineWord]:
        """measure.dec_span: context on both sides, at least 0.5 s, padded with silence."""
        first = max(0, start - _CONTEXT)
        span = pcm[first : end + _CONTEXT]
        if len(span) < _MIN_DECODE:
            span = np.pad(span, (0, _MIN_DECODE - len(span)))
        tokens, times, log_probs = self._decode(np.pad(span, (_PAD, _PAD)))
        return words_from_tokens(
            tokens, times, log_probs, span_offset_s=first / SAMPLE_RATE - _PAD / SAMPLE_RATE, offset_ms=offset_ms
        )

    def _guard(
        self, pcm: np.ndarray, words: list[EngineWord], parts: list[tuple[int, int]], offset_ms: int
    ) -> list[EngineWord]:
        """measure.run: a part of a merged window with too few words is decoded again on its own."""
        if len(parts) <= 1:
            return words
        for start, count in parts:
            seconds = count / SAMPLE_RATE
            if seconds < GUARD_MIN_S:
                continue
            low = (start / SAMPLE_RATE - GUARD_SLACK_S) * 1000
            high = ((start + count) / SAMPLE_RATE + GUARD_SLACK_S) * 1000

            def inside(word: EngineWord, low: float = low, high: float = high) -> bool:
                return low <= word.start_ms - offset_ms <= high

            within = [word for word in words if inside(word)]
            if len(within) < GUARD_WORDS_PER_S * seconds:
                again = self._decode_span(pcm, start, start + count, offset_ms)
                if len(again) > len(within):
                    words = sorted([word for word in words if not inside(word)] + again, key=lambda w: w.start_ms)
        return words

    def transcribe(self, pcm: np.ndarray, offset_ms: int, *, second_pass: bool) -> list[Window]:
        """The windows of one chunk of 16 kHz mono float PCM that starts at ``offset_ms`` in the medium."""
        windows: list[Window] = []
        for start, end, parts in merge_segments(self._segments(pcm, second_pass=second_pass)):
            words = self._guard(pcm, self._decode_span(pcm, start, end, offset_ms), parts, offset_ms)
            text = " ".join(word.text for word in words)
            lid, lid_p = self._language(text)
            latin = round(latin_share(text), 3)
            conf_mean = round(float(np.mean([word.conf for word in words])), 4) if words else 0.0
            verdict = window_verdict(latin, lid, lid_p, len(words), conf_mean)
            windows.append(
                Window(
                    start_ms=offset_ms + _ms(start),
                    end_ms=offset_ms + _ms(end),
                    speech_ms=_ms(sum(count for _, count in parts)),
                    n_words=len(words),
                    verdict=verdict,
                    words=tuple(words) if verdict == KEEP else (),
                    latin=latin,
                    lid=lid,
                    lid_p=lid_p,
                    conf_mean=conf_mean,
                )
            )
        return windows
