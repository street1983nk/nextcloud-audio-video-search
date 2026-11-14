# Phase 3: Vorschau-Transkripte in der Suche - Pattern Map

**Mapped:** 2026-11-14
**Files analyzed:** 38 (neu oder geändert, aus 03-CONTEXT.md, 03-RESEARCH.md "Recommended Project Structure" und "Wave 0 Gaps", 03-UI-SPEC.md)
**Analogs found:** 34 / 38 (Rest: keine Entsprechung im Repo, Muster aus RESEARCH bzw. Spike 3)

Grundregel aus CLAUDE.md: Findling-Muster kopieren, nicht importieren. Alle Pfade unten relativ zu `C:/Users/Student/nextcloud-audio-video-search/`, Findling-Pfade mit vollem Präfix `C:/Users/Student/nextcloud-search/`.

## File Classification

| Neue/geänderte Datei | Rolle | Datenfluss | Nächstes Analog | Qualität |
|---|---|---|---|---|
| `backend/src/audio_video_search_backend/worker/preview.py` (NEU) | worker | batch, event-driven (Claim) | `backend/src/audio_video_search_backend/worker/capture.py` | exact |
| `backend/src/audio_video_search_backend/media/probe.py` (NEU) | utility | file-I/O (Unterprozess) | `C:/Users/Student/nextcloud-search/backend/src/findling/extract/sandbox.py` (`_run_probe`, Popen) + `nc.py` (geschlossene Fehlercodes) | partial |
| `backend/src/audio_video_search_backend/media/decode.py` (NEU) | utility | streaming (PCM aus Pipe) | wie probe.py; Kommando aus RESEARCH Pattern 1 | partial |
| `backend/src/audio_video_search_backend/engine/child.py` (NEU) | service (Kindprozess) | request-response über Pipe | `C:/Users/Student/nextcloud-search/backend/src/findling/extract/sandbox.py` `_child_main` + `ExtractionWorker` | role-match |
| `backend/src/audio_video_search_backend/engine/parakeet.py` (NEU) | service | transform | keine im Repo; Spike 3 `spike3/scripts/bench3.py` Zeilen 44 bis 132 | no analog |
| `backend/src/audio_video_search_backend/engine/catch.py` (NEU) | utility (reine Regel) | transform | `worker/capture.py` `retry_at` + Konstantenstil; Regel aus RESEARCH Pattern 5 | role-match |
| `backend/src/audio_video_search_backend/models/` (NEU, Downloader) | service | file-I/O, Download | `C:/Users/Student/nextcloud-search/backend/src/findling/embed/weights.py` | exact |
| `backend/src/audio_video_search_backend/memory_guard.py` (NEU, Kopie) | utility | file-I/O (cgroup) | `C:/Users/Student/nextcloud-search/backend/src/findling/memory_guard.py` | exact (Kopie) |
| `backend/src/audio_video_search_backend/store/schema.sql` (v3) | migration/model | CRUD | sich selbst (`file_ref`, `index_outbox`) | exact |
| `backend/src/audio_video_search_backend/store/migrate.py` (v2 nach v3) | migration | batch | sich selbst, `migrate_v1_to_v2` | exact |
| `backend/src/audio_video_search_backend/store/repo.py` (preview_job-Methoden) | store | CRUD | sich selbst: `next_capture`/`_CLAIM_CAPTURE`, `publish_version`, `add_correction` | exact |
| `backend/src/audio_video_search_backend/store/coverage.py` (Gründe zählen) | store | CRUD (Zählung) | sich selbst, `_BY_STAGE` + `_grouped` | exact |
| `backend/src/audio_video_search_backend/api/search.py` | controller | request-response | sich selbst + Findling Offset-Vertrag | exact |
| `backend/src/audio_video_search_backend/api/excerpt.py` | controller | request-response | sich selbst | exact |
| `backend/src/audio_video_search_backend/settings.py` | config | request-response | sich selbst (`MAX_FILE_SIZE_MB`) | exact |
| `backend/src/audio_video_search_backend/main.py` | config (Lifespan) | event-driven | sich selbst, `start_background(capture...)` | exact |
| `backend/src/audio_video_search_backend/nc_queue.py` + `worker/intake.py` (origin) | contract | request-response | sich selbst, `ClaimItem` | exact |
| `backend/Dockerfile` (ffmpeg-Stage) | config | build | sich selbst, Stage `frpc` | exact |
| `backend/pyproject.toml` + `uv.lock` | config | build | Bestand | exact |
| `php/lib/Search/Provider.php` | controller (Suchprovider) | request-response, Paginierung | sich selbst + `C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php` + `.../Service/SearchService.php::run` | exact |
| `php/lib/Service/ExAppService.php` (`search(offset)`, `excerpt` mit Stufe/Grund) | service | request-response | sich selbst, `search`/`excerpt`/`filterHits` | exact |
| `php/lib/Controller/PageController.php` | controller | request-response | sich selbst, `excerpt()` | exact |
| `php/templates/play.php` | component (Template) | request-response | sich selbst, Abschnitt `section.avs-excerpt` | exact |
| `php/css/play.css` (`.avs-excerpt__note`) | config (CSS) | - | sich selbst, `.avs-excerpt__hint` | exact |
| `php/l10n/{de,de_DE,en,fr}.{json,js}` | config (l10n) | - | Bestand + `scripts/l10n_js.py` | exact |
| `php/lib/Db/QueueMapper.php` + neue Migration `Version000300Date2026111...php` | model/migration | CRUD | `php/lib/Migration/Version000200Date20261107000000.php`, `QueueMapper::enqueue` | exact |
| `php/lib/Listener/FileEventListener.php`, `BackgroundJobs/StorageCrawlJob.php`, `Service/QueueService.php` (origin setzen/ausgeben) | middleware/service | event-driven | Bestand | exact |
| `php/lib/Command/StatusCommand.php` | controller (occ) | request-response | sich selbst | exact |
| `backend/tests/test_preview_worker.py` | test | - | `backend/tests/test_capture.py` | exact |
| `backend/tests/test_vad_gate.py` | test (Quelltext-Gate) | - | `backend/tests/test_read_proof_gate.py` | exact |
| `backend/tests/test_store_migration_v3.py` | test | - | `backend/tests/test_store_migration_v2.py` | exact |
| `backend/tests/test_search_tiers.py`, Erweiterung `test_excerpt_states.py` | test | - | `backend/tests/test_excerpt_states.py` | exact |
| `backend/tests/test_catch_rule.py`, `test_engine_constants.py` | test | - | `test_capture.py` (`retry_at`-Tests), `test_provenance.py` | role-match |
| `backend/tests/media_fixtures.py`, `test_media_decode.py`, `test_media_timeline.py`, `test_media_hardening.py` | test | file-I/O | keine (erstes ffmpeg im Repo) | no analog |
| `backend/tests/test_engine_model.py` (Modelltest, markiert) | test | - | keine | no analog |
| `php/tests/Unit/ProviderTest.php`, `PlayControllerTest.php` | test | - | sich selbst | exact |
| `backend/tests/test_trilingual.py` (neue Schlüssel) | test | - | sich selbst | exact |
| `scripts/research/phase3/` (Messskripte ohne Daten) | utility | batch | `scripts/research/` (Bestand) | role-match |

## Pattern Assignments

### `backend/src/audio_video_search_backend/worker/preview.py` (worker, batch)

**Analog:** `backend/src/audio_video_search_backend/worker/capture.py`

**Modulkopf und Imports** (Zeilen 58 bis 96): Docstring beschreibt die Zustandsmaschine vollständig, Konstanten als `Final`, Abhängigkeiten als injizierbare Callables.
```python
import asyncio
import enum
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from audio_video_search_backend import companion, config, nc
from audio_video_search_backend.api import Services, run_locked

LOGGER = logging.getLogger(__name__)

IDLE_SECONDS: Final = 15.0
TMP_DIRNAME: Final = "tmp"

type Fetch = Callable[[int, str, Path, int, int], Awaitable[nc.FetchResult]]
```

**Ergebnis-Typ** (Zeilen 99 bis 119): geschlossenes `StrEnum` plus frozen Dataclass; für preview: `IDLE, CHUNK_DONE, COMPLETE, SKIPPED, YIELDED (Unterbrechen), DEFERRED, STALE`.
```python
class CaptureOutcome(enum.StrEnum):
    IDLE = "idle"
    KEYED = "keyed"
    ...

@dataclass(frozen=True, slots=True)
class CaptureStep:
    outcome: CaptureOutcome
    file_id: int | None = None
    reason: str | None = None
    media_id: int | None = None
```

**Klasse mit Injektion, seriellem Lock, prepare/run_once** (Zeilen 156 bis 198): Konstruktor nimmt `services`, `directory`, `fetch`, `clock`; `prepare()` räumt `.part`-Reste und setzt Claims zurück (für preview: `reset_running` setzt `running` auf `queued`, TRANS-07).
```python
class Capture:
    def __init__(self, services: Services, *, directory: Path | None = None,
                 fetch: Fetch = _default_fetch, clock: Callable[[], float] = time.time, ...) -> None:
        ...
        self._serial = asyncio.Lock()

    async def prepare(self) -> None:
        directory = self._directory
        def tidy() -> int:
            directory.mkdir(parents=True, exist_ok=True)
            return nc.remove_stale_parts(directory)
        removed = await asyncio.to_thread(tidy)
        reset = await run_locked(self._services, store.reset_fetching)

    async def run_once(self) -> CaptureStep:
        async with self._serial:
            return await self._step()
```

**Claim und Store-Zugriff nur über `run_locked`** (Zeilen 200 bis 216):
```python
ref = await run_locked(self._services, lambda: store.next_capture(now))
if ref is None:
    return _IDLE
```

**Download und Validierung** (Zeilen 144 bis 153, 301 bis 318): Für preview zweiter Download über denselben `nc.fetch_to_tempfile`-Weg, aber die Temp-Datei muss für ffmpeg bleiben. Achtung: `fetch_to_tempfile` (nc.py Zeilen 502 bis 554) löscht die Datei im `finally`. Der Planer braucht eine Variante, die einen Pfad an einen Callback übergibt oder die Datei behält und der Aufrufer löscht (gleiche Regeln: Name `secrets.token_hex(16)`, ohne sprechende Endung, Löschen auf jedem Weg). sha256 gegen `media_key` prüfen wie `_validated`:
```python
def _validated(ref: FileRef, result: nc.FetchResult) -> tuple[str, str] | str:
    if result.error is not None:
        return result.error if result.error in nc.FETCH_ERRORS else nc.GATEWAY_FAILED
    if result.size != ref.size:
        return nc.SIZE_MISMATCH
    ...
```

**Plattenplatz (D-03-17)** aus nc.py Zeilen 529 bis 536: `free_bytes` ist per Test ersetzbar (`monkeypatch.setattr(nc, "free_bytes", ...)` in test_capture.py Zeile 82). Neuer Grund "zu wenig Speicherplatz" wie `DISK_FULL` mit Wiederholung (`DISK_FULL_RETRY_SECONDS = 300`, capture.py Zeile 83), nie als Endurteil.
```python
if expected_size > max_bytes:
    return _refused(file_id, TOO_LARGE, None)
free = await asyncio.to_thread(free_bytes, tmp_dir)
if free < expected_size + DISK_RESERVE_BYTES:
    return _refused(file_id, DISK_FULL, None)
```

**Fehlerbewertung in einer Methode** (Zeilen 331 bis 359, `_judge`): je Grund eine Store-Methode, `False` vom Store heißt STALE.

**Endlosschleife** (Zeilen 361 bis 390): nur bei `companion.current().state == companion.OK`, jede Ausnahme geloggt mit `error_type`, nie mit Inhalt.
```python
async def run_forever(self, *, idle: float = IDLE_SECONDS,
                      sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                      rounds: int | None = None) -> None:
    await self.prepare()
    ...
        if companion.current().state == companion.OK:
            try:
                step = await self.run_once()
            except Exception as exc:  # the loop must outlive any single step
                LOGGER.exception("capture step failed", extra={"error_type": type(exc).__name__})

async def run_forever(services: Services) -> None:
    await Capture(services).run_forever()
```

**Unterbrechen an der Stückgrenze (D-03-06):** nach jedem Stück-Commit eine Store-Abfrage `EXISTS(queued AND origin='event')`; wenn ja und laufender Job `crawl`: Job auf `queued`, Temp-Datei löschen, Outcome `YIELDED`.

---

### `backend/src/audio_video_search_backend/engine/child.py` (Kindprozess, request-response über Pipe)

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/extract/sandbox.py`

**Spawn-Kontext und Job-Kennungen** (Zeilen 73 bis 102):
```python
SPAWN_CONTEXT: Final = mp.get_context("spawn")
_JOB_EXTRACT: Final = "extract"
_JOB_STOP: Final = "stop"
SANDBOX_NICE: Final = 10
_JOIN_GRACE_SECONDS: Final = 5.0
```

**Kind-Hauptschleife** (Zeilen 339 bis 427): eigene Session (`os.setsid`), `nice`, Thread-Pools pinnen VOR dem Import der schweren Bibliothek, Import erst im Kind, `MemoryError` als Antwort statt Absturz, `EOFError`/`BrokenPipeError` beendet still.
```python
def _child_main(pipe: PipeEnd, address_space_bytes: int) -> None:
    if sys.platform != "win32":
        os.setsid()
        os.nice(SANDBOX_NICE)
    _shed_secrets()
    _pin_native_thread_pools()

    from findling.extract.dispatch import Route, extract   # im Kind: sherpa_onnx erst hier

    while True:
        try:
            job = pipe.recv()
        except EOFError:
            return
        kind = job[0]
        if kind == _JOB_STOP:
            return
        try:
            answer = ...
        except MemoryError:
            answer = ExtractionOutcome.failed(Reason.OUT_OF_MEMORY)
        except Exception as error:
            answer = ExtractionOutcome.from_exception(error)
        try:
            pipe.send(answer)
        except (BrokenPipeError, OSError):
            return
```
Abweichung für Phase 3: RESEARCH nennt `RLIMIT_AS` ausdrücklich als ungeeignet für ORT ("What NOT to Use" in CLAUDE.md), also `_limit_address_space` NICHT übernehmen. Stattdessen vor dem Start `memory_guard.admits(memory_guard.headroom_bytes(), need=1,7 GB + Reserve)`, Wandzeit je Stück über `ExtractionWorker._ask`-Muster (Zeilen 563 ff., Deadline, Kill des Kinds via `_kill_child_tree` Zeilen 156 ff.). RESEARCH Pattern 6 erlaubt alternativ `python -m audio_video_search_backend.engine.child` mit JSON-Zeilen; das Findling-Muster (multiprocessing spawn + Pipe) ist bereits gehärtet und vorzuziehen.

**Worker-Hülle** (Zeilen 430 bis 438): eine Klasse hält genau ein Kind und die Regeln zum Ersetzen (`max_files` entspricht "N Stücke je Job-Block").

---

### `backend/src/audio_video_search_backend/memory_guard.py` (Kopie)

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/memory_guard.py` Zeilen 35 bis 94 vollständig kopieren; die Leser `meminfo_bytes`, `memory_limit`, `CGROUP_ROOT`, `MEMINFO` aus `findling/hardware.py` mitkopieren (nicht importieren).
```python
def headroom_bytes(*, cgroup_root: Path = CGROUP_ROOT, meminfo: Path = MEMINFO) -> int | None:
    available = meminfo_bytes(meminfo, "MemAvailable")
    limit = memory_limit(cgroup_root)
    if limit is None:
        return available
    anon = anon_bytes(cgroup_root)
    if anon is None:
        return available
    within_limit = max(0, limit - anon)
    return within_limit if available is None else min(within_limit, available)

def admits(headroom: int | None, *, need: int) -> bool:
    return headroom is not None and headroom >= need
```

---

### `backend/src/audio_video_search_backend/models/` (Downloader, file-I/O)

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/embed/weights.py`

**Feste Identität als Konstanten** (Zeilen 49 bis 70): sha256 und Länge je Datei, feste URL mit Commit, geschlossene Ergebnisliste.
```python
FP32_SHA256: Final = "ca456c06..."
FP32_BYTES: Final = 470_268_510
FP32_ASSET_URL: Final = f"https://github.com/.../releases/download/{FP32_RELEASE_TAG}/{FP32_ASSET_NAME}"
PART_SUFFIX: Final = ".part"
PROCURED: Final = "procured"
UNAVAILABLE: Final = "unavailable"
WRONG_DIGEST: Final = "wrong_digest"
NO_ROOM: Final = "no_room"
PROCURE_OUTCOMES: Final = frozenset({PROCURED, UNAVAILABLE, WRONG_DIGEST, NO_ROOM})
FetchAsset = Callable[..., Awaitable[None]]
_HASH_CHUNK: Final = 1024 * 1024
```
Drei Regeln aus dem Docstring (Zeilen 18 bis 30) übernehmen: Schreiben nach `.part`, Hash und Länge beim Streamen, `fsync` dann `os.replace`; jeder Fehler ist ein Wert, nie eine Ausnahme; eine vom Admin abgelegte Datei wird gegen denselben Digest geprüft (Air-Gap-Weg), Urteil gecacht nach Größe und mtime. Logs nur Typnamen. Werte für Phase 3: Parakeet-Dateien und Silero aus 03-RESEARCH.md "Standard Stack" (Commit `2bda32ec...`, vier sha256; Silero `9e2449e1...`). Der HTTP-Teil gehört nach `nc.py` (das einzige Modul mit Client, `tests/test_boundary.py`), wie Findling `nc/client.py fetch_release_asset` mit Host-Allowlist.

---

### `backend/src/audio_video_search_backend/media/probe.py` und `media/decode.py` (utility, Unterprozess)

**Analog (Unterprozess-Aufruf):** `C:/Users/Student/nextcloud-search/backend/src/findling/extract/sandbox.py` Zeilen 192 bis 199: `subprocess.Popen` mit Argumentliste, nie Shell, Kommentar `# noqa: S603 - an argument list, never a shell`.

**Analog (geschlossene Fehlercodes, Logs ohne Inhalt):** `backend/src/audio_video_search_backend/nc.py` Zeilen 431 bis 434 und 437 bis 453:
```python
def _refused(file_id: int, error: str, status: int | None) -> FetchResult:
    # A code, the file id and a status; never the user, a name, a path or the body.
    LOGGER.info("capture read refused", extra={"file_id": file_id, "reason": error, "status": status})
    return FetchResult(sha256=None, size=0, error=error, status=status)
```
Für media: Gründe als `Final`-Konstanten plus `frozenset` (`too_long`, `no_audio`, `damaged`, `protected`, `format_unsupported`), stderr von ffmpeg nie loggen (kann Pfade enthalten), nur Exit-Code und Grund.

**Kernmuster:** wörtlich aus 03-RESEARCH.md Pattern 1 (ffmpeg-Kommando mit `-protocol_whitelist file`, `-format_whitelist DEMUXERS`, `-ss`/`-t` vor `-i`, `-map 0:<index>`, `-af aresample=async=1:first_pts=0`, `-fs`, `subprocess.run(..., timeout=WALL_LIMIT_S)`) und "Code Examples" `pick_audio_stream`. DRM-Erkennung über Box-Kennungen `enca/sinf/schm/tenc` (M-5). Pfad der Binärdateien als Konstante `/usr/local/bin/ffmpeg` mit Parameter für Tests (Owner-Regel: lokale Pfade vor Push durch Parameter ersetzen).

---

### `backend/src/audio_video_search_backend/engine/catch.py` (reine Regel, transform)

**Analog (Stil reiner Entscheidungsfunktionen):** `worker/capture.py` Zeilen 77 bis 94 und 122 bis 128:
```python
MAX_ATTEMPTS: Final = 5
RETRY_BASE_SECONDS: Final = 60

def retry_at(now: int, attempts_before: int, reason: str) -> int | None:
    """The time of the next try after a read failure, None after the last attempt."""
    if attempts_before + 1 >= MAX_ATTEMPTS:
        return None
    ...
```
**Regel:** wörtlich 03-RESEARCH.md Pattern 5 (`INSTANCE`, `MIN_LATIN = 0.5`, `LID_P = 0.9`, `LID_MIN_WORDS = 3`, `CONF = 0.6`, `CONF_INSTANCE = 0.5`, `window_verdict`, Dateiurteil). D-03-16: zweite VAD-Schwelle 0,3 / 0,1 s nur bis 60 s und nur bei 0 behaltenen Wörtern als weitere `Final`-Konstanten. Keine Einstellung, kein Env (Gate siehe test_vad_gate.py).

---

### `backend/src/audio_video_search_backend/engine/parakeet.py` (keine Entsprechung)

Konstanten aus SPIKE3 Abschnitt 11 bzw. `spike3/scripts/bench3.py` Zeilen 44 bis 132 (Silero 0,5 / Mindeststille 0,3 s / Mindestsprache 0,25 s / max. 25 s, Fenster bis 25 s mit Zusammenfassung bei Lücke bis 2 s, 0,4 s Kontext, 0,5 s Polster, Schluck-Wächter 1,0 Wort/s ab 1 s, `greedy_search`, 2 Threads). Konstantenstil wie `model/provenance.py` Zeilen 24 bis 42 (`IntEnum`, `Final`-frozensets). Provenance für die Vorschau: `engine="parakeet"`, `level=Level.PREVIEW` (=100), `language="und"`, `profile` aus `PROFILES`.

---

### `backend/src/audio_video_search_backend/store/schema.sql` (v3)

**Analog:** sich selbst. Kopfkommentar fortschreiben ("Schema version 3 (phase 3) ..."), jede Anweisung `IF NOT EXISTS`, Zeiten in INTEGER ms, Codes aus geschlossenen Listen in repo.py, ausführlicher Kommentar je Tabelle (Muster `file_ref` Zeilen 52 bis 91). Neue Tabelle `preview_job` wörtlich aus RESEARCH Pattern 3; `file_ref` bekommt `origin TEXT NOT NULL DEFAULT 'crawl'` (Pitfall 6).

### `backend/src/audio_video_search_backend/store/migrate.py` (v2 nach v3)

**Analog:** sich selbst, Zeilen 26 bis 109.
```python
V1_TO_V2_STEPS: tuple[str, ...] = (
    FILE_REF_V2,
    ...
    "ALTER TABLE media ADD COLUMN head_sha256 TEXT",
    "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
)

def migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        for step in V1_TO_V2_STEPS:
            connection.execute(step)
    except BaseException:
        connection.execute("ROLLBACK")
        _LOG.error("store migration failed, the file stays at version 1", extra={"from": 1, "to": 2})
        raise
    connection.execute("COMMIT")
```
Für v3: `V2_TO_V3_STEPS` (Tabelle `preview_job` als Konstante, die identisch zu schema.sql bleiben muss, Index `preview_job_order`, `ALTER TABLE file_ref ADD COLUMN origin ...`, Befüllen von `preview_job` für vorhandene `keyed`+`active`-Referenzen mit `origin='crawl'`, `sort_mtime` aus `file_ref.mtime`, `meta` auf `'3'`). Konstante `SCHEMA_VERSION` in repo.py auf 3.

### `backend/src/audio_video_search_backend/store/repo.py` (preview_job, Stück-Commit)

**Claim-Muster** (Zeilen 229 bis 244, 1031 bis 1044): ein `UPDATE ... WHERE id = (SELECT ... ORDER BY ... LIMIT 1) RETURNING ...` in einer Transaktion, Reset beim Start.
```python
_CLAIM_CAPTURE: Final = """
UPDATE file_ref SET stage = 'fetching', updated_at = :now
WHERE file_id = (
    SELECT file_id FROM file_ref
    WHERE state IN ('active', 'unreadable') AND (...)
    ORDER BY CASE WHEN ... THEN 0 ELSE 1 END, COALESCE(next_try_at, 0), file_id
    LIMIT 1)
RETURNING file_id, media_id, ...
"""
_RESET_FETCHING: Final = "UPDATE file_ref SET stage = 'pending', updated_at = :now WHERE stage = 'fetching'"

def next_capture(self, now: int | None = None) -> FileRef | None:
    moment = _now() if now is None else now
    with self._transaction():
        row = self._conn.execute(_CLAIM_CAPTURE, {"now": moment}).fetchone()
    return None if row is None else FileRef(*row)
```
Für preview: `ORDER BY CASE origin WHEN 'event' THEN 0 ELSE 1 END, sort_mtime DESC, media_id` (D-03-05), nur Jobs mit mindestens einem `active`-Verweis mit Leser.

**Stück 1: Version anlegen** (Zeilen 1530 bis 1585, `publish_version`): `_INSERT_TRANSCRIPT`, `executemany(_INSERT_WORD, ...)`, `_UPSERT_CURRENT`, `SELECT changes()` gleich 0 heißt stale, `_INSERT_OUTBOX` in derselben Transaktion. In derselben Transaktion zusätzlich `preview_job.next_start_ms`, `chunks_done`, `version_id`, Zähler.

**Folgestücke: Wörter anhängen und Revision erhöhen** (Zeilen 1630 bis 1656, `add_correction`): genau dieses Muster.
```python
with self._transaction():
    ...
    row = self._conn.execute(_BUMP_INDEX_REV, (media_id,)).fetchone()
    if row is not None:
        self._conn.execute(_INSERT_OUTBOX, (media_id, int(row[0])))
```
`_INSERT_WORD` (Zeilen 447 bis 450) mit fortlaufendem `idx` ab `MAX(idx)+1`. Keine neue Version je Stück (RESEARCH Anti-Pattern: UPSERT verwirft Gleichstand).

**Feldprüfung** (Zeilen 1101 bis 1106): `ValueError("invalid file_ref field: reason")` nennt das Feld, nie den Wert; neue Liste `PREVIEW_REASONS: Final = frozenset({...})` neben `STATE_REASONS` (Zeile 57).

**Rechte für Excerpt-Gründe:** `media_for_file` (Zeilen 1483 bis 1496) liefert nur bei `state = 'active'`; Grund/Stufe/`partial` nur über genau diesen Weg auslesen (Leck-Regel UI-SPEC).

### `backend/src/audio_video_search_backend/store/coverage.py` (Gründe für occ)

**Analog:** sich selbst, Zeilen 56 bis 57 und 95 ff.:
```python
_BY_STAGE: Final = "SELECT stage, COUNT(*) FROM file_ref GROUP BY stage"
...
by_stage=_grouped(conn, _BY_STAGE, STAGES),
```
Neu: `_BY_PREVIEW = "SELECT COALESCE(reason, state), COUNT(*) FROM preview_job GROUP BY 1"` gegen eine geschlossene Namensliste, Feld `byPreview` in `to_json` (Zeilen 85 bis 87). Keine Dateinamen (D-03-13).

---

### `backend/src/audio_video_search_backend/api/search.py` (controller, request-response)

**Analog:** sich selbst (ganze Datei, 96 Zeilen) plus Findling-Offset-Vertrag.

**Request-Modell** (Zeilen 39 bis 43): strikt, `extra="ignore"`, Grenzen per `Field`.
```python
class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    term: Annotated[StrictStr, Field(max_length=MAX_TERM_INPUT)]
    limit: Annotated[StrictInt, Field(ge=1, le=50)]
```
Neu: `offset: Annotated[StrictInt, Field(ge=0, le=MAX_OFFSET)] = 0` (Obergrenze wie Findling `MAX_CONTAINER_OFFSET = 1200`, `SearchService.php` Zeile 87).

**Zulässige Revision** (Zeilen 46 bis 56, `admissible`): bleibt, aber nicht mehr "ein Treffer je Medium", sondern alle Segmente der höchsten zulässigen Revision je Medium (eine Stelle = ein Segment, RESEARCH Pattern 4 Punkt 6).

**Zeit der Stelle** (Zeilen 70 bis 78): erstes passendes Wort, sonst Segmentanfang; unverändert übernehmen.

**Stufen-Folge:** Funktion `tiered` wörtlich aus 03-RESEARCH.md "Code Examples"; Schnitt `[offset, offset+limit)`, Antwort `{"appVersion", "hits", "nextOffset", "hasMore"}`. Jeder Treffer trägt `stage` (`preview`/`final`/`sample`, UI-SPEC Datenvertrag) zusätzlich zu `sample`.

**Antwort und Log** (Zeilen 91 bis 96): nur Zähler im Log, nie Term.
```python
@router.post("/search")
async def search(body: SearchRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    term = body.term[:MAX_TERM_CHARS].strip()
    hits = await run_locked(opened, lambda: _search(opened, term, body.limit)) if term else []
    _LOG.debug("search answered", extra={"hits": len(hits), "limit": body.limit})
    return {"appVersion": config.app_version(), "hits": hits}
```

### `backend/src/audio_video_search_backend/api/excerpt.py`

**Analog:** sich selbst (47 Zeilen). Antwort erweitern auf `{"known", "excerpt", "stage", "partial", "reason", "pendingHere"}`; `known: false` ohne weitere Felder für jeden nicht aktiven Verweis (Zeilen 35 bis 41 bleiben die Pforte):
```python
def _excerpt(opened: Services, file_id: int, at_ms: int) -> str | None:
    store = opened.store
    media_id = store.media_for_file(file_id)
    if media_id is None or store.current(media_id) is None:
        return None
```
Für Gründe: Datei ohne `current`, aber mit `preview_job.state='skipped'` und aktivem Verweis liefert `known: true, excerpt: null, reason: <code>`. `pendingHere` (A4): `at_ms >= next_start_ms` bei laufendem Job.

### `backend/src/audio_video_search_backend/settings.py`

**Analog:** sich selbst, Zeilen 24 bis 62.
```python
PROCESSING_ENABLED: Final = "processing_enabled"
MAX_FILE_SIZE_MB: Final = "max_file_size_mb"
DEFAULTS: Final[dict[str, str]] = {PROCESSING_ENABLED: "1", MAX_FILE_SIZE_MB: "100"}
...
SettingsField(
    id=MAX_FILE_SIZE_MB,
    title="Largest file in MB",
    description="Larger files are skipped and listed as skipped.",
    type=SettingsFieldType.NUMBER,
    default=int(DEFAULTS[MAX_FILE_SIZE_MB]),
    placeholder="100",
),
```
Neu: `MAX_DURATION_HOURS = "max_duration_hours"` Standard `"12"`. `MAX_FILE_SIZE_MB` entfällt nach D-03-17 (Feld-ID-Regel Zeilen 24 bis 25 beachten: entfernte ID verwirft gespeicherten Wert; capture.py `MAX_CAPTURE_BYTES = 64 GiB` Zeile 85 bleibt als Schutz gegen Ausreißer). Jeder neue Text englisch hier, DE/FR in `l10n/` des Backends, `tests/test_trilingual.py` hält sie zusammen (Docstring Zeilen 8 bis 10). Erhöhung der Grenze: `too_long`-Jobs mit `duration_ms <= neue Grenze` zurück auf `queued` (D-03-09).

### `backend/src/audio_video_search_backend/main.py`

**Analog:** sich selbst, Zeilen 136 bis 153: neuer Task neben `capture_task`, gleich abgebrochen im `finally`.
```python
capture_task = start_background(capture.run_forever(services), "capture")
...
finally:
    capture_task.cancel()
```

### `backend/src/audio_video_search_backend/nc_queue.py` (origin im Claim-Vertrag)

**Analog:** sich selbst, Zeilen 43 bis 77. `ClaimItem` ist `extra="forbid", strict=True`: ein neues Feld `origin: Literal["event", "crawl"]` muss gleichzeitig in PHP `QueueService::describe` erscheinen, sonst verwirft der Container das ganze Band (T-02-17). Lockstep der Versionen (`php/appinfo/info.xml` Zeile 7 ff.) und `tests/test_lockstep_versions.py` beachten. `to_intake` und `IntakeItem` um `origin` erweitern.

### `backend/Dockerfile` (ffmpeg-Stage)

**Analog:** Stage `frpc`, Zeilen 24 bis 51.
```dockerfile
FROM ${BASE_IMAGE} AS frpc
ARG TARGETARCH
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN set -eux; \
    FRP_VERSION=0.71.1; \
    FRP_AMD64_SHA256=1d98...; \
    FRP_ARM64_SHA256=8edf...; \
    case "${TARGETARCH:-amd64}" in \
        arm64) FRP_ARCH=arm64; FRP_SHA256="${FRP_ARM64_SHA256}" ;; \
        amd64) FRP_ARCH=amd64; FRP_SHA256="${FRP_AMD64_SHA256}" ;; \
        *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --proto '=https' --tlsv1.2 -o /tmp/frp.tar.gz "https://github.com/..."; \
    echo "${FRP_SHA256}  /tmp/frp.tar.gz" | sha256sum -c -; \
    tar -C /tmp -xzf ...; \
    install -m 0755 ... /usr/local/bin/frpc; \
    /usr/local/bin/frpc --version
```
Für ffmpeg: Tag `autobuild-2026-10-31-12-59`, Asset `ffmpeg-n8.1.3-27-g8dca1586f4-linux64-lgpl-8.1.tar.xz` (sha256 `a64f3171...f1f3`) bzw. `linuxarm64` (`2ea30086...0809`), nur `ffmpeg` und `ffprobe` installieren, `COPY --from=ffmpeg` in runtime wie Zeile 85. `tests/test_dockerfile.py` und `tests/test_workflow_pins.py` prüfen Pins.

---

### `php/lib/Search/Provider.php` (controller, Paginierung)

**Analog A (Bestand, bleibt):** sich selbst. Ausschluss vor dem Container (Zeilen 131 bis 148), Prüfung je Treffer (Zeilen 177 bis 212), `entry()` (Zeilen 220 bis 245), `clock()`/`shorten()` (Zeilen 252 bis 285) unverändert.

Untertitel-Aufbau (Zeilen 221 bis 228), erweitert um Kennzeichen vor dem Ausschnitt (UI-SPEC Fläche 1):
```php
$parts = [self::clock($hit['startMs'])];
if ($hit['sample']) {
    $parts[] = $this->l10n->t('Test result');
}
// NEU: elseif ($hit['stage'] !== 'final') { $parts[] = $this->l10n->t('Preliminary'); }
$excerpt = self::shorten($hit['excerpt']);
if ($excerpt !== '') {
    $parts[] = $excerpt;
}
```

**Analog B (Cursor, Runden, paginated):** `C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php`

Offset aus Cursor (Zeilen 511 bis 522):
```php
private function startOffset(ISearchQuery $query): int {
    $cursor = $query->getCursor();
    if (is_int($cursor) && $cursor > 0) {
        return $cursor;
    }
    if (is_string($cursor) && ctype_digit($cursor)) {
        return (int)$cursor;
    }
    return 0;
}
```
Limit vom Dialog statt `SEARCH_LIMIT` (Zeile 283): `max(1, $query->getLimit())`. Ergebnisform (Zeilen 333 bis 335):
```php
return $outcome->hasMore
    ? SearchResult::paginated($this->getName(), $entries, $outcome->nextCursor)
    : SearchResult::complete($this->getName(), $entries);
```
NICHT übernehmen: den zusätzlichen "entryPoint"-Eintrag (Zeilen 324 bis 326), er ersetzt den "Mehr laden"-Knopf; Phase 3 braucht genau diesen Knopf (D-03-15).

**Analog C (Runden mit Überabruf):** `C:/Users/Student/nextcloud-search/php/lib/Service/SearchService.php::run`, Zeilen 263 bis 363: Schleife über `maxRounds`, Abbruch bei `count($approved) >= $pageSize`, Prüfbudget oder Deadline; Offset-Decke vor dem Aufruf (Zeilen 293 bis 302); leere Seite ist nur Ende, wenn `hasMore` falsch ist (Zeilen 350 bis 363):
```php
for ($round = 0; $round < $maxRounds; $round++) {
    if (count($approved) >= $pageSize || $rechecks >= $recheckBudget || ($this->clock)() >= $deadline) {
        break;
    }
    if ($offset > self::MAX_CONTAINER_OFFSET) {
        $ceilingReached = true;
        $exhausted = true;
        break;
    }
    $fetchLimit = min($pageSize * $caps->overfetch, $recheckBudget - $rechecks + $pageSize);
    $page = $this->exApp->searchCandidates($uid, $term, $fetchLimit, $offset, ...);
    if ($page === null) { $silent = true; break; }
    $candidates = $page['candidates'];
    if ($candidates === []) {
        $exhausted = !$page['hasMore'];
        if ($exhausted) { break; }
        $offset = $page['nextOffset'];
        continue;
    }
    ...
}
```
Für AVS in den Provider selbst einbauen (kein eigener SearchService nötig) mit `MAX_ROUNDS = 3`, `OVERFETCH = 4` (Findling Provider Zeilen 72 bis 73), `BUDGET_SECONDS = 2.5`. Wichtig für Präfix-Stabilität: der `nextCursor` ist der Container-Offset nach dem letzten ausgelieferten Eintrag, nicht nach dem letzten geholten (sonst Lücken). Prüf-Cache `array<int, ?File>` je Anfrage für `isExcludedFile` und `readableFile` (Pitfall 9).

### `php/lib/Service/ExAppService.php`

**Analog:** sich selbst. `search()` Zeilen 177 bis 199 bekommt `int $offset` und gibt `{hits, nextOffset, hasMore}` zurück; `filterHits()` Zeilen 941 bis 976 prüft zusätzlich `stage` gegen Positivliste (unbekannt wird `preview`, UI-SPEC: "im Zweifel ehrlich vorläufig"), `nextOffset` als `int >= 0`, `hasMore` als `bool`.
```php
if (!is_int($fileId) || $fileId <= 0
    || !is_int($startMs) || $startMs < 0
    || !is_string($excerpt) || !is_bool($sample)) {
    $dropped++;
    continue;
}
```
`excerpt()` Zeilen 206 bis 227: Muster "falscher Typ macht die ganze Antwort ungültig (null)" übernehmen für `reason` (string|null), `stage`, `partial` (bool), `pendingHere` (bool). Positivliste der Gründe NICHT hier, sondern im PageController (UI-SPEC: unbekannter String wird A11).

### `php/lib/Controller/PageController.php`

**Analog:** sich selbst, `excerpt()` Zeilen 273 bis 303 und Zustandskonstanten Zeilen 64 bis 68.
```php
public const EXCERPT_OK = 'ok';
public const EXCERPT_NONE = 'none';
public const EXCERPT_UNAVAILABLE = 'unavailable';
...
if ($excluded) {
    return [self::EXCERPT_NONE, ''];
}
if (!$this->exAppService->searchAllowed()) {
    return [self::EXCERPT_UNAVAILABLE, ''];
}
$answer = $this->exAppService->excerpt($uid, $fileId, $startMs);
if ($answer === null) {
    return [self::EXCERPT_UNAVAILABLE, ''];
}
```
Neu: Konstanten `EXCERPT_PENDING_HERE`, `EXCERPT_NO_SPEECH`, `EXCERPT_SKIPPED_DAMAGED`, `EXCERPT_SKIPPED_PROTECTED`, `EXCERPT_UNSUPPORTED_LANGUAGE`, `EXCERPT_TOO_LONG`, `EXCERPT_SKIPPED_OTHER` (Tabelle A1 bis A12 in 03-UI-SPEC.md); Rückgabe erweitert um `note` (`preview`/`partial`/leer) und `maxHours` für A10. Ausschlussprüfung bleibt zuerst (Leck-Regel). Höchstdauer für A10 liest PHP aus appconfig_ex der ExApp oder bekommt sie vom Container in der Antwort; nie die echte Dauer der Datei.

### `php/templates/play.php`

**Analog:** sich selbst, Zeilen 45 bis 46 (defensives Lesen) und 181 bis 190 (Ausschnitt-Block).
```php
<section class="avs-excerpt" aria-labelledby="avs-excerpt-label">
    <p id="avs-excerpt-label" class="avs-excerpt__label"><?php p($l->t('Excerpt at this point')); ?></p>
    <?php if ($excerptState === 'ok' && $excerpt !== '') { ?>
        <blockquote class="avs-excerpt__text"><?php p($excerpt); ?></blockquote>
    <?php } elseif ($excerptState === 'none') { ?>
        <p class="avs-excerpt__hint"><?php p($l->t('There is no transcript for this file yet.')); ?></p>
    <?php } else { ?>
        <p class="avs-excerpt__hint"><?php p($l->t('The excerpt cannot be loaded right now. Playback works regardless.')); ?></p>
    <?php } ?>
</section>
```
Neu: nach `blockquote` ein `p.avs-excerpt__note` (T2 oder T3), weitere `elseif`-Zweige für A4, A6 bis A11; A10 als `$l->n('This file is longer than %n hour ...', '... %n hours ...', $maxHours)` plus Leerzeichen plus T10 in EINEM `p`. Der A5-Zweig bleibt byte-gleich (Leck-Regel). Kein JS, kein `aria-live`.

### `php/css/play.css`

**Analog:** bestehende Regel `.avs-excerpt__hint` in derselben Datei; neue Regel exakt laut UI-SPEC: `margin: calc(var(--default-grid-baseline) * 2) 0 0; color: var(--color-text-maxcontrast); font-size: var(--font-size-small); line-height: var(--default-line-height); overflow-wrap: anywhere;`. `tests/test_ui_assets.py` prüft die CSS-Regeln (kein Hex, kein `!important`).

### `php/l10n/*.json` und `*.js`

**Analog:** `php/l10n/de.json` Zeilen 1 bis 12: englischer Text ist Schlüssel.
```json
{
    "translations": {
        "Test result": "Testtreffer",
        "There is no transcript for this file yet.": "Für diese Datei gibt es noch kein Transkript.",
```
Plural als Schlüssel `_Singular_::_Plural_` mit Array-Wert (UI-SPEC Copywriting). `.js` aus `.json` mit `scripts/l10n_js.py` erzeugen. `de` und `de_DE` inhaltsgleich. Neuer Text für "zu wenig Speicherplatz" (D-03-17) ist noch nicht freigegeben: dem Owner zeigen, in 03-UI-SPEC.md nachtragen, dann bauen.

### `php/lib/Db/QueueMapper.php` + neue Migration

**Analog Migration:** `php/lib/Migration/Version000200Date20261107000000.php` Zeilen 35 bis 107: `hasTable`/`hasColumn`-Wächter, Klassenname gleich Dateiname, `$changed ? $schema : null`.
```php
if (!$schema->hasTable('avs_queue')) { ... }
$table->addColumn('kind', Types::STRING, ['notnull' => true, 'length' => 16]);
...
return $changed ? $schema : null;
```
Neu: `$table = $schema->getTable('avs_queue'); if (!$table->hasColumn('origin')) { $table->addColumn('origin', Types::STRING, ['notnull' => true, 'length' => 8, 'default' => 'crawl']); }`.

**Analog enqueue:** Zeilen 98 bis 128: Signatur erweitern `enqueue(string $kind, ?int $fileId, int $storageId, string $origin = 'crawl')`, Positivliste `ORIGINS = ['event', 'crawl']` wie `KINDS` (Zeile 49) mit `InvalidArgumentException('unknown queue origin')`. Konflikt (`insertIgnoreConflict` liefert 0): ein `event` hebt eine vorhandene `crawl`-Zeile auf `event`, nie umgekehrt (RESEARCH Pattern 3 "ein Ereignis gewinnt"). Aufrufer: `FileEventListener` übergibt `'event'`, `StorageCrawlJob`/`RescanService` `'crawl'`; `QueueService::describe` gibt `origin` aus.

### `php/lib/Command/StatusCommand.php`

**Analog:** sich selbst, Zeilen 74 bis 82 und 108 bis 116:
```php
$output->writeln('By stage: ' . self::listed($coverage['byStage']));
...
private static function listed(array $counts): string { ... }
```
Neu: Zeile `Preview: ` mit `self::listed($coverage['byPreview'])`; `--json` übernimmt das Feld automatisch über `$coverage +`. Nur Codes und Zahlen (T-02-44).

---

### `backend/tests/test_preview_worker.py`

**Analog:** `backend/tests/test_capture.py` Zeilen 1 bis 90: Docstring nennt die zwei Teile, gefälschtes `fetch` gegen echte state.db, `tmp_dir`-Fixture, `plenty_of_space` per `monkeypatch.setattr(nc, "free_bytes", ...)`, `HIDDEN_PATH` zum Nachweis, dass nichts in Logs landet. Engine als Fälschung (Fenster mit Wörtern), Fälle aus RESEARCH Test-Map TRANS-07/08: Abbruch nach Commit k, Fortsetzen bei k+1, Unterbrechen durch `event`-Job, Wortzeit + Stückversatz.

### `backend/tests/test_vad_gate.py`

**Analog:** `backend/tests/test_read_proof_gate.py` Zeilen 1 bis 80: `scan(root)` als Funktion eines Baums, Regex für Schalterwörter (`SWITCH = re.compile(r"(?i)skip|disabl|bypass|unsafe")`), verbotene Muster `("os.environ", "getenv", "settings.", ...)` in den Engine-Modulen, Gegentests auf einer veränderten Kopie, die das Gate scheitern lassen. Für TRANS-02: VAD- und Abfangkonstanten nur in `engine/`, kein Einstellungs-, Env- oder Routenweg.

### `backend/tests/test_store_migration_v3.py`

**Analog:** `backend/tests/test_store_migration_v2.py` Zeilen 1 bis 50: eingefrorene Kopie des v2-Schemas als String (`V2_SCHEMA`), Migration darauf, spaltenweiser Vergleich mit einer frischen Datei, Fehler zwischen Schritten einschieben (Modulkonstante `V2_TO_V3_STEPS`) und Rollback prüfen.

### `backend/tests/test_search_tiers.py` und `test_excerpt_states.py`

**Analog:** `backend/tests/test_excerpt_states.py` Zeilen 40 bis 70: `TestClient(main.APP)`, `_store(client)`, `_transcribed` über `publish_version` mit `Level.PREVIEW`, `_reference` über `upsert_file_ref`, `signed_headers` aus conftest; Parametrisierung über `NOT_ACTIVE = sorted((state, stage) for state in repo.STATES - {"active"} ...)` für die Leck-Regel (Grund nur bei active). Für Stufen: Präfix-Test `limit` 5/10/15, Offset ohne Dubletten und Lücken.

### `php/tests/Unit/ProviderTest.php`, `PlayControllerTest.php`

**Analog:** sich selbst; ProviderTest Zeilen 82 bis 120: Doubles für `IL10N` (`willReturnArgument(0)`), `IURLGenerator` sammelt Links, `ExAppService`-Mock mit Zählern. Neu: Mock von `search()` mit `offset`, Cursor-Doppel `ISearchQuery::getCursor/getLimit`, Assertions auf `SearchResult::paginated` und genau `limit` Einträge, Prüf-Cache (readableFile je fileId einmal). PlayControllerTest: byte-gleicher A5-Block für ausgeschlossen gegen unbekannt (UI-SPEC P11).

## Shared Patterns

### Store-Zugriff nur unter dem Services-Lock
**Source:** `backend/src/audio_video_search_backend/api/__init__.py` Zeilen 51 bis 58
**Apply to:** worker/preview.py, api/search.py, api/excerpt.py
```python
async def run_locked[T](opened: Services, work: Callable[[], T]) -> T:
    def locked() -> T:
        with opened.lock:
            return work()
    return await asyncio.to_thread(locked)
```
Lange Arbeit (Download, ffmpeg, Engine) NIE unter dem Lock, nur der Commit je Stück.

### Rechte und Ausschluss in PHP, Container schlägt nur vor
**Source:** `php/lib/Search/Provider.php` Zeilen 137 bis 148 und 192 bis 209; `php/lib/Controller/PageController.php` Zeilen 273 bis 286
**Apply to:** Provider, PageController
```php
$this->exclusions->reload();
if ($this->exclusions->isExcludedUser($uid)) { return SearchResult::complete($this->getName(), []); }
...
if ($this->exclusions->isExcludedFile($fileId)) { continue; }
$file = $this->readerContext->actAs($uid, static fn (): ?File => FileAccess::readableFile($userFolder, $fileId));
```

### Nur active-Verweise geben Text, Grund oder Treffer
**Source:** `backend/src/audio_video_search_backend/store/repo.py` Zeilen 124 bis 132 (`_FILE_IDS_FOR_MEDIA`) und 1483 bis 1496 (`media_for_file`)
**Apply to:** api/search.py, api/excerpt.py, jede neue Abfrage auf `preview_job`

### Geschlossene Code-Listen und Logs ohne Inhalt
**Source:** `repo.py` Zeilen 54 bis 73 (`STATES`, `STAGES`, `STATE_REASONS`), `nc.py` Zeilen 431 bis 434, `capture.py` Zeilen 382 bis 385
**Apply to:** alle neuen Python-Module
```python
LOGGER.info("capture step", extra={"file_id": step.file_id, "outcome": step.outcome.value, "reason": step.reason})
```
Nur ids, Codes, Zähler; nie Wörter, Begriffe, Pfade, ffmpeg-stderr.

### Eine Transaktion je Zustandswechsel, Outbox in derselben Transaktion
**Source:** `repo.py` Zeilen 1530 bis 1574 (`publish_version`) und 1630 bis 1656 (`add_correction`)
**Apply to:** Stück-Commit, Dateiurteil, Rückstellen bei Unterbrechung

### Strikte Verträge zwischen den Hälften
**Source:** `backend/src/audio_video_search_backend/nc_queue.py` Zeilen 43 bis 64 (pydantic `extra="forbid", strict=True`), `php/lib/Service/ExAppService.php` Zeilen 941 bis 990 (`filterHits`, `plainText`)
**Apply to:** `/search`-Antwort (neue Felder `stage`, `nextOffset`, `hasMore`), `/excerpt`-Antwort (`reason`, `partial`, `pendingHere`), Claim-Feld `origin`

### Lieferkette mit festem sha256
**Source:** `backend/Dockerfile` Zeilen 37 bis 51 (frpc), `C:/Users/Student/nextcloud-search/backend/src/findling/embed/weights.py` Zeilen 49 bis 70
**Apply to:** ffmpeg-Stage, Modell-Downloader, CI-Modell-Cache, FLEURS-Clip für e2e

### Dreisprachige Texte
**Source:** `backend/src/audio_video_search_backend/settings.py` Zeilen 8 bis 10, `php/l10n/de.json`, `backend/tests/test_trilingual.py`, `backend/tests/test_public_texts.py`
**Apply to:** T1 bis T11, neues Einstellungsfeld Höchstdauer, Text "zu wenig Speicherplatz"

## No Analog Found

| Datei | Rolle | Datenfluss | Grund |
|---|---|---|---|
| `backend/src/audio_video_search_backend/engine/parakeet.py` | service | transform | Erste echte Erkennung im Repo; Vorlage ist Spike 3 `bench3.py` Zeilen 44 bis 132 und RESEARCH Pattern 6 |
| `backend/src/audio_video_search_backend/media/decode.py` (Kommando selbst) | utility | streaming | Erstes ffmpeg im Repo; Kommando wörtlich aus RESEARCH Pattern 1 (gemessen M-1 bis M-5) |
| `backend/tests/media_fixtures.py` + `test_media_*.py` | test | file-I/O | Keine Medienerzeugung bisher; Beep-Dateien per ffmpeg zur Laufzeit, Skip mit Grund ohne ffmpeg (RESEARCH Wave 0) |
| `backend/tests/test_engine_model.py` | test | - | Modelltest mit CI-Cache (actions/cache, Schlüssel = sha256), markiert |

## Metadata

**Analog search scope:** `backend/src/audio_video_search_backend/**`, `backend/tests/**`, `backend/Dockerfile`, `php/lib/**`, `php/templates/`, `php/l10n/`, `php/tests/Unit/`; Findling `C:/Users/Student/nextcloud-search/backend/src/findling/{memory_guard.py,extract/sandbox.py,embed/weights.py}`, `C:/Users/Student/nextcloud-search/php/lib/{Search/Provider.php,Service/SearchService.php}`
**Files scanned:** ca. 30 gelesen bzw. gezielt durchsucht
**Pattern extraction date:** 2026-11-14
