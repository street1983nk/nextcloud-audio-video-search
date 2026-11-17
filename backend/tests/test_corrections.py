"""User corrections survive a new machine version (decision 4 of the phase research).

A correction is anchored at audio time [start_ms, end_ms) of a media_id, never
at word indices. A machine word whose midpoint falls into the span is replaced.
"""

import itertools
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from audio_video_search_backend.model.overlay import Correction, Word, effective_words
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import Store


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


# Store level: the correction layer survives replacement and stale results.

SHA = "a" * 64
MODEL = "d" * 64


def _prov(level: Level, config_version: int = 1) -> Provenance:
    return Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=config_version,
        profile="balanced",
        level=level,
        epoch=0,
        language="de",
        input_file_sha256=SHA,
    )


def _store_text(store: Store, media_id: int) -> str:
    return _text(store.effective_words(media_id))


def _correct(store: Store, media_id: int, start: int, end: int, body: str, *, kind: str = "text") -> int:
    return store.add_correction(
        media_id, start, end, kind, body, author_uid="alice", base_version_id=None, base_text=None
    )


def test_store_correction_survives_v2(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    v1 = store.publish_version(media_id, _prov(Level.PREVIEW), V1)
    store.add_correction(
        media_id,
        250,
        900,
        "text",
        "Haushaltsplan",
        author_uid="alice",
        base_version_id=v1.version_id,
        base_text="haus halts plan",
    )
    assert _store_text(store, media_id) == "der Haushaltsplan wurde"
    assert store.publish_version(media_id, _prov(Level.REFINED), V2).published
    assert _store_text(store, media_id) == "der Haushaltsplan wurde beschlossen"


def test_edge_4_correction_survives_a_stale_rejection(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    store.publish_version(media_id, _prov(Level.REFINED), V2)
    _correct(store, media_id, 250, 900, "Haushaltsplan")
    assert store.publish_version(media_id, _prov(Level.PREVIEW, 9), V1).reason == "stale_rejected"
    assert _store_text(store, media_id) == "der Haushaltsplan wurde beschlossen"


def test_store_edge_3_other_media_is_not_corrected(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    other = store.media_for_file_sha256("b" * 64)
    store.publish_version(media_id, _prov(Level.REFINED), V2)
    _correct(store, other, 250, 900, "Haushaltsplan")
    assert _store_text(store, media_id) == "der Haushalts plan wurde beschlossen"
    assert store.active_corrections(media_id) == []


def test_without_current_only_correction_words(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    _correct(store, media_id, 250, 900, "Haushaltsplan")
    assert _store_text(store, media_id) == "Haushaltsplan"


def test_overlapping_correction_supersedes(store: Store, tmp_path: Path) -> None:
    media_id = store.media_for_file_sha256(SHA)
    store.publish_version(media_id, _prov(Level.REFINED), V2)
    old = _correct(store, media_id, 250, 900, "Haushaltsplan")
    speaker = _correct(store, media_id, 0, 2000, "Anna", kind="speaker")
    new = _correct(store, media_id, 600, 1300, "plan verabschiedet")
    with closing(sqlite3.connect(tmp_path / "state.db")) as conn:
        superseded = conn.execute("SELECT superseded_by FROM correction WHERE correction_id = ?", (old,)).fetchone()[0]
    assert superseded == new
    active = store.active_corrections(media_id)
    assert {c.correction_id for c in active} == {speaker, new}
    texts = sorted((c.start_ms, c.end_ms) for c in active if c.kind == "text")
    assert all(a[1] <= b[0] for a, b in itertools.pairwise(texts))
    assert _store_text(store, media_id) == "der Haushalts plan verabschiedet beschlossen"


def test_adjacent_corrections_do_not_supersede(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    _correct(store, media_id, 0, 250, "Der")
    _correct(store, media_id, 250, 900, "Haushaltsplan")
    assert len(store.active_corrections(media_id)) == 2


def test_each_correction_raises_index_rev(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    store.publish_version(media_id, _prov(Level.REFINED), V2)
    store.mark_indexed(media_id, 1)
    _correct(store, media_id, 250, 900, "Haushaltsplan")
    current = store.current(media_id)
    assert current is not None
    assert current.index_rev == 2
    assert store.pending_index_work() == [(media_id, 2)]
    _correct(store, media_id, 950, 1300, "verabschiedet")
    assert store.pending_index_work() == [(media_id, 2), (media_id, 3)]


@pytest.mark.parametrize(
    ("start", "end", "kind", "field"),
    [
        (900, 900, "text", "end_ms"),
        (900, 250, "text", "end_ms"),
        (-1, 250, "text", "start_ms"),
        (0, 250, "note", "kind"),
    ],
)
def test_invalid_corrections_are_refused(store: Store, start: int, end: int, kind: str, field: str) -> None:
    media_id = store.media_for_file_sha256(SHA)
    with pytest.raises(ValueError, match=field):
        _correct(store, media_id, start, end, "x", kind=kind)
    assert store.active_corrections(media_id) == []


def test_words_json_outside_span_is_refused(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA)
    bad = json.dumps([{"start_ms": 100, "end_ms": 300, "surface": "Haushaltsplan"}])
    with pytest.raises(ValueError, match="words_json"):
        store.add_correction(
            media_id,
            250,
            900,
            "text",
            "Haushaltsplan",
            author_uid="alice",
            base_version_id=None,
            base_text=None,
            words_json=bad,
        )
