"""User corrections survive a new machine version (decision 4 of the phase research).

A correction is anchored at audio time [start_ms, end_ms) of a media_id, never
at word indices. A machine word whose midpoint falls into the span is replaced.
"""

import json

from audio_video_search_backend.model.overlay import Correction, Word, effective_words


def _w(surface: str, start: int, end: int) -> Word:
    return Word(start_ms=start, end_ms=end, surface=surface, norm=surface.casefold(), conf=0.9, src="machine")


def _text(words: list[Word]) -> str:
    return " ".join(w.surface for w in words)


V1 = [_w("der", 0, 200), _w("haus", 250, 450), _w("halts", 460, 700), _w("plan", 710, 900), _w("wurde", 950, 1200)]
V2 = [
    _w("der", 0, 180),
    _w("Haushalts", 240, 640),
    _w("plan", 650, 880),
    _w("wurde", 1000, 1250),
    _w("beschlossen", 1260, 1900),
]


def _corr(
    start: int, end: int, body: str, *, kind: str = "text", words_json: str | None = None, cid: int = 1
) -> Correction:
    return Correction(
        correction_id=cid, media_id=7, start_ms=start, end_ms=end, kind=kind, body=body, words_json=words_json
    )


HAUSHALT = _corr(250, 900, "Haushaltsplan")


def test_correction_over_v1() -> None:
    assert _text(effective_words(V1, [HAUSHALT])) == "der Haushaltsplan wurde"


def test_correction_survives_replacement_by_v2() -> None:
    out = effective_words(V2, [HAUSHALT])
    assert _text(out) == "der Haushaltsplan wurde beschlossen"
    user = [w for w in out if w.src == "user"]
    assert len(user) == 1
    assert user[0].surface == "Haushaltsplan"
    assert user[0].norm == "haushaltsplan"
    assert user[0].conf == 1.0
    assert 250 <= user[0].start_ms <= user[0].end_ms <= 900
    assert all(w.surface != "Haushalts" for w in out)


def test_edge_1_no_machine_words_in_span() -> None:
    machine = [_w("der", 0, 200), _w("wurde", 950, 1200)]
    out = effective_words(machine, [HAUSHALT])
    assert _text(out) == "der Haushaltsplan wurde"
    assert [w.start_ms for w in out] == sorted(w.start_ms for w in out)


def test_edge_2_midpoint_on_end_stays_machine() -> None:
    # Midpoint (850 + 950) // 2 == 900 == end_ms: half-open interval, the word stays.
    machine = [_w("der", 0, 200), _w("haus", 300, 500), _w("grenze", 850, 950)]
    out = effective_words(machine, [HAUSHALT])
    assert _text(out) == "der Haushaltsplan grenze"
    assert out[-1].src == "machine"


def test_midpoint_on_start_is_replaced() -> None:
    # Midpoint (200 + 300) // 2 == 250 == start_ms: inside.
    machine = [_w("der", 0, 100), _w("rand", 200, 300)]
    assert _text(effective_words(machine, [HAUSHALT])) == "der Haushaltsplan"


def test_edge_3_speaker_and_sound_do_not_change_words() -> None:
    corrections = [
        _corr(250, 900, "Anna", kind="speaker", cid=2),
        _corr(950, 1200, "Applaus", kind="sound", cid=3),
    ]
    assert effective_words(V2, corrections) == V2


def test_no_corrections_returns_machine_unchanged() -> None:
    assert effective_words(V2, []) == V2


def test_multiword_spread_evenly_in_integer_ms() -> None:
    out = effective_words(V1, [_corr(250, 900, "der Haushalts plan")])
    user = [w for w in out if w.src == "user"]
    assert [w.surface for w in user] == ["der", "Haushalts", "plan"]
    for w in user:
        assert isinstance(w.start_ms, int)
        assert isinstance(w.end_ms, int)
        assert 250 <= w.start_ms <= w.end_ms <= 900
    starts = [w.start_ms for w in user]
    assert starts == sorted(starts)
    assert user[0].start_ms == 250
    assert user[-1].end_ms == 900


def test_words_json_times_are_taken() -> None:
    words_json = json.dumps(
        [{"start_ms": 260, "end_ms": 600, "surface": "Haushalts-"}, {"start_ms": 610, "end_ms": 880, "surface": "plan"}]
    )
    out = effective_words(V1, [_corr(250, 900, "Haushalts- plan", words_json=words_json)])
    user = [w for w in out if w.src == "user"]
    assert [(w.start_ms, w.end_ms, w.surface) for w in user] == [(260, 600, "Haushalts-"), (610, 880, "plan")]
    assert user[0].norm == "haushalts"


def test_norm_strips_edge_punctuation() -> None:
    out = effective_words(V1, [_corr(250, 900, "»Haushaltsplan«,")])
    user = [w for w in out if w.src == "user"]
    assert user[0].surface == "»Haushaltsplan«,"
    assert user[0].norm == "haushaltsplan"


def test_two_corrections_in_order() -> None:
    corrections = [_corr(950, 1300, "verabschiedet", cid=2), HAUSHALT]
    out = effective_words(V2, corrections)
    assert _text(out) == "der Haushaltsplan verabschiedet beschlossen"
