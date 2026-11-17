# Phase 4: Suchqualität und Export - Pattern Map

**Mapped:** 2026-11-16
**Files analyzed:** 31 (neu und geändert, aus 04-CONTEXT.md, 04-RESEARCH.md, 04-UI-SPEC.md)
**Analogs found:** 29 / 31

Vorbemerkung für den Planer: Alle Muster unten stammen aus dem Bestand dieses Repos (Stand 0.3.0), ergänzt um zwei externe Muster: Findling (`C:/Users/Student/nextcloud-search`) für Filter und Analyzer-Tests, PII Redaction (`C:/Users/Student/nextcloud-pii-redaction`) für das Ablegen einer Datei neben dem Original. Die Gates in `backend/tests/test_php_gates.py` (Regeln 1 bis 18) und `test_trilingual.py`/`test_public_texts.py` gelten für jede neue Datei und sind unter "Shared Patterns" aufgeführt.

## File Classification

| Neue/geänderte Datei | Rolle | Datenfluss | Nächstes Analog | Qualität |
|---|---|---|---|---|
| `backend/src/audio_video_search_backend/index/numbers.py` (neu) | utility (Query-Erweiterung) | transform | `index/analyzer.py` (Konstanten-Tabellen, `Final`, kein Logging von Wörtern); Findling `query/rewrite.py:502-563` (Should/Must-Bau) | role-match |
| `backend/src/audio_video_search_backend/index/publish.py` (ändern: `search`, `first_match_ms`) | service | request-response | sich selbst, Zeilen 268-304 | exact |
| `backend/src/audio_video_search_backend/index/analyzer.py` / `schema.py` / `open.py` | config | , | Bestand; nur ändern, wenn F1 doch Index-seitig wird (D-04-14 sagt: nicht) | exact |
| `backend/src/audio_video_search_backend/subtitles/cues.py` (neu) | utility (reine Funktion) | transform | `index/publish.py:96-112` `segments_from_words` | role-match |
| `backend/src/audio_video_search_backend/subtitles/formats.py` (neu) | utility | transform | `index/publish.py:96-112` + `model/overlay.py` (Word) | partial |
| `backend/src/audio_video_search_backend/api/export.py` (neu) | controller (Container-Route) | request-response | `api/excerpt.py` (ganze Datei) | exact |
| `backend/src/audio_video_search_backend/api/__init__.py` (ändern) | config (Router) | , | Zeilen 61-73 | exact |
| `backend/appinfo/info.xml` (ändern: Route `^/export$`) | config | , | Zeilen 86-92 (`^/excerpt$`) | exact |
| `backend/src/audio_video_search_backend/worker/preview.py` (ändern: Mehrheitssprache, D-04-15) | service (Worker) | batch | Zeilen 114-115, 183-231 (`take`, Window `lid`/`lid_p`) | exact |
| `backend/src/audio_video_search_backend/store/repo.py` / `migrate.py` / `schema.sql` (ändern, falls Sprache je Datei Spalte/Update braucht) | model | CRUD | `store/migrate.py:152-179` (`migrate_v2_to_v3`), `repo.py:40` `SCHEMA_VERSION = 3` | exact |
| `php/lib/Controller/ExportController.php` (neu) | controller | request-response + file-I/O | `php/lib/Controller/PageController.php` | exact |
| `php/lib/Service/DownloadPolicy.php` (neu, herausgezogen) | service | request-response | `PageController::downloadAllowed` Zeilen 247-275 | exact |
| `php/lib/Service/SidecarWriter.php` oder Ablage im ExportController (neu) | service | file-I/O | PII `php/lib/Service/PublishService.php:95-136` | role-match (Achtung: Namensregel weicht ab) |
| `php/lib/Service/SearchFilters.php` (neu, AV) | service | CRUD (oc_share lesen) | Findling `php/lib/Service/SearchFilters.php` (Wertobjekt) + AV `php/lib/Db/QueueMapper.php:256` (`PARAM_INT_ARRAY`) | role-match |
| `php/lib/Search/Provider.php` (ändern: Filter) | provider | request-response | sich selbst + Findling `php/lib/Search/Provider.php:182-276` | exact |
| `php/lib/Controller/PageController.php` (ändern: `exportState`, Track, Sidecar-Daten) | controller | request-response | sich selbst, Zeilen 125-168, 313-371 | exact |
| `php/lib/Service/ExAppService.php` (ändern: `export()`, eigener Timeout) | service | request-response | Zeilen 233-324 (`excerpt()`), 979-1009 (`call`) | exact |
| `php/templates/play.php` (ändern: `section.avs-export`, `<track>`) | component (Template) | request-response | Zeilen 62-134 (Banner-Tabelle), 197-223 | exact |
| `php/templates/export_error.php` (neu, Fehlerseite D2) | component | request-response | `play.php` Banner-Schleife Zeilen 170-195 | role-match |
| `php/js/play.js` (ändern: Ablage-POST) | component (Browser-JS) | event-driven | `play.js:55-62` (Knopf sichtbar), `admin.js:35-54,97-110,166-182` (POST mit requesttoken, disabled/aria-busy, textContent) | exact |
| `php/css/play.css` (ändern) | config (Style) | , | Zeilen 77-119 (Banner), 154-157, 194-197, 240-246 | exact |
| `php/l10n/{de,de_DE,en,fr}.{json,js}` (ändern, T13 bis T35) | config (l10n) | , | `php/l10n/de.json` / `de.js` | exact |
| `backend/l10n/*` | config | , | nur falls Container-Texte neu (nicht vorgesehen) | , |
| `backend/tests/test_numbers.py` (neu) | test | , | Findling `backend/tests/test_analyzer.py:93-157` (Erwartungstabelle + parametrize) | exact |
| `backend/tests/test_search_numbers.py` (neu) | test | , | `backend/tests/test_index_publish.py:19-120` | exact |
| `backend/tests/test_subtitles.py` (neu) | test | , | `test_index_publish.py:224-245` (segments-Tests) | role-match |
| `backend/tests/test_api_export.py` (neu) | test | , | `backend/tests/test_excerpt_states.py` | exact |
| `backend/tests/test_trilingual.py`, `test_public_texts.py` (ändern) | test (Gate) | , | `test_trilingual.py:309-343`, `test_public_texts.py:126-129` | exact |
| `php/tests/Unit/ExportControllerTest.php`, `SidecarTest.php`, `SearchFiltersTest.php`; `ProviderTest.php` (erweitern) | test | , | `php/tests/Unit/PlayControllerTest.php` | exact |
| `ci/playwright/export.spec.ts` (neu), `helpers.ts` (erweitern) | test (E2E) | , | `ci/playwright/helpers.ts`, `play.spec.ts`, `preview.spec.ts` | exact |
| README (DE/EN/FR, NC-36-Hinweis D-04-18) | docs | , | bestehende READMEs + `test_trilingual.py:216` | exact |

## Pattern Assignments

### `backend/src/audio_video_search_backend/index/numbers.py` (utility, transform)

**Analog:** `index/analyzer.py` (Form) und Findling `query/rewrite.py` (Query-Bau)

**Modulkopf und Konstanten-Stil** (`analyzer.py` Zeilen 1-5, 41-64): Docstring erklärt das Warum, Tabellen als `Final`, kein Logging von Wörtern ("Nothing here logs a token or a word: this path sees user content.").
```python
from typing import Final
ANALYZER_VERSION: Final = 1
MAX_TOKEN_CHARS: Final = 48
FOLDED_STOPWORDS: Final[dict[str, tuple[str, ...]]] = { ... }
```

**Normalisierung beider Seiten** (`analyzer.py` Zeilen 103-110): jede Variante vor `parse_query` durch `normalize()` (NFC, Surrogate).

**Query-Bau Should-Gruppe / Must-Kette** (Findling `backend/src/findling/query/rewrite.py:502-507, 559-563`):
```python
terms = [Query.term_query(index.schema, FIELD_EXT, extension) for extension in extensions]
if len(terms) == 1:
    return terms[0]
return Query.boolean_query([(Occur.Should, term) for term in terms])
...
return Query.boolean_query([(Occur.Must, clause) for clause in clauses])
```
Für Zahlen: je Begriff `Query.boolean_query([(Occur.Should, index.parse_query(v, list(BODY_FIELDS))) for v in varianten])`, zwischen Begriffen `Occur.Must` (RESEARCH Pattern 1). Mehrteilige Varianten als Phrase (`'"soixante dix"'`). Jede Variante in `try/except ValueError` (siehe `publish.py:273-276`). Präfix F1 (D-04-14): `Query.regex_query(schema, FIELD_BODY_DE, re.escape(stamm) + ".*")` als weitere Should-Klausel, Mindestlänge, Metazeichen maskiert.

---

### `backend/src/audio_video_search_backend/index/publish.py` (service, request-response, ÄNDERN)

**Analog:** sich selbst. Einstieg Zeilen 268-291:
```python
def search(self, term: str, limit: int) -> list[IndexHit]:
    """Candidates for a term over the three body fields; a broken query is an empty list."""
    text = normalize(term[:MAX_TERM_CHARS]).strip()
    if not text or limit <= 0:
        return []
    try:
        query = self._index.parse_query(text, list(BODY_FIELDS), conjunction_by_default=True)
    except ValueError:
        return []
```
Hier ansetzen: Zahlenweg (und Präfix) baut die Query aus Einzelwörtern statt `parse_query(text)`; ohne Zahl bleibt der Bestandsweg byte-gleich (RESEARCH Pattern 1, Phase-3-Tests bleiben stehen). Nebenbefund "12:30" wirft heute `ValueError` und endet still leer (Zeile 274); der Einzelwort-Weg behebt das.

`first_match_ms` Zeilen 293-304 nutzt `self._chains` (de/en/fr) mit `chain.analyze`; die Varianten der Zahl müssen hier ebenfalls in `wanted` landen, sonst zeigt der Treffer die Segment-Startzeit statt der Wortzeit (`api/search.py:105-122`).

Analyzer/Schema/Open: unverändert lassen. Falls doch Index-Änderung, Marken-Mechanik `open.py:61-67` (`expected_marks`) und `publish.py:146-175` (`open_generation` baut neu) gelten; `ANALYZER_VERSION`/`SCHEMA_VERSION` erhöhen (Kommentar `schema.py:13-14`, `analyzer.py:37-39`).

---

### `backend/src/audio_video_search_backend/subtitles/cues.py` und `formats.py` (utility, transform)

**Analog:** `index/publish.py:74-112` (frozen dataclass + reine Schneidefunktion über `Sequence[Word]`)
```python
@dataclass(frozen=True, slots=True)
class Segment:
    """A run of words that becomes one index document; times in whole ms."""
    seg_idx: int
    start_ms: int
    end_ms: int
    text: str

def segments_from_words(words: Sequence[Word], *, max_gap_ms: int = 1500, max_words: int = 40) -> list[Segment]:
    segments: list[Segment] = []
    run: list[Word] = []
    def close() -> None:
        if run:
            text = " ".join(w.surface for w in run)
            segments.append(Segment(len(segments), int(run[0].start_ms), int(run[-1].end_ms), text))
            run.clear()
    for word in words:
        if run and (len(run) >= max_words or word.start_ms - run[-1].end_ms > max_gap_ms):
            close()
        run.append(word)
    close()
    return segments
```
Übernehmen: `Cue`-Dataclass (frozen, slots), Grenzen als `Final`-Konstanten (`MAX_LINE = 42`, `MAX_LINES = 2`, `MIN_MS = 1000`, `MAX_MS = 7000`, `MAX_CPS = 20`, `GAP_MS = 80`), Eingabe `store.effective_words(media_id)` (`repo.py:2105-2109`, Korrekturen schon überlagert), Text aus `w.surface` nie verändern (D-04-16). Writer ohne Bibliothek (CLAUDE.md "What NOT to Use"); webvtt-py/srt nur als dev-Prüfer im Test. Kein Kopf-/NOTE-Text im Container (Lokalisierung in PHP per IL10N, RESEARCH Responsibility Map).

---

### `backend/src/audio_video_search_backend/api/export.py` (controller, request-response)

**Analog:** `api/excerpt.py` (ganze Datei, 85 Zeilen)

**Imports/Request-Modell** (Zeilen 19-41):
```python
from typing import Annotated, Final
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from audio_video_search_backend.api import MAX_AT_MS, Services, run_locked, services

router = APIRouter()
_NOT_KNOWN: Final[dict[str, object]] = {"known": False}

class ExcerptRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fileId: Annotated[StrictInt, Field(gt=0)]  # the wire name of the contract
    atMs: Annotated[StrictInt, Field(ge=0, le=MAX_AT_MS)]
```
Für Export: `format: Literal["srt", "vtt", "txt"]` statt `atMs`.

**Leck-Regel und Teilstand** (Zeilen 52-80):
```python
view = store.preview_view(file_id)
media_id = store.media_for_file(file_id)
current = None if media_id is None else store.current(media_id)
if view is None and current is None:
    return dict(_NOT_KNOWN)
partial = view is not None and view.state in _IN_WORK and view.chunks_done > 0
```
Für X2 (D-04-17) zusätzlich `view.next_start_ms` als "Transkript bis" zurückgeben. Sprache: nur `de|en|fr`, nie `und` (D-04-15); Rückfall-Bestimmung für Altbestand hier.

**Route** (Zeilen 83-85):
```python
@router.post("/excerpt")
async def excerpt(body: ExcerptRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    return await run_locked(opened, lambda: _excerpt(opened, body.fileId, body.atMs))
```

**Registrierung** (`api/__init__.py:61-73`): `from audio_video_search_backend.api import ... export ...` und `router.include_router(export.router)`.

**info.xml** (`backend/appinfo/info.xml:86-92`), Block kopieren mit `<url>^/export$</url>`, `POST`, `USER`.

---

### `backend/src/audio_video_search_backend/worker/preview.py` + Store (Mehrheitssprache, D-04-15)

**Analog:** `worker/preview.py:114-115`
```python
# The language of a preview version: Parakeet names none.
PREVIEW_LANGUAGE: Final = "und"
```
Fenster tragen bereits `lid`/`lid_p` (`engine/parakeet.py:84-85, 252-266`); `take()` (Zeilen 183-231) iteriert die Fenster mit `verdict == KEEP` und ist die Stelle, wo wortgewichtete Sprachzählung je Chunk anfällt (gleiches Muster wie die Zähler `kept/script/language/conf`, `ChunkCounters` + `_add` Zeilen 173-180). Erlaubte Werte: `model/provenance.py:36` `LANGUAGES = frozenset({"de", "en", "fr", "und"})`, Prüfung `validate()` Zeile 101.

Falls Spalte/Zählerspalten nötig: Migration nach `store/migrate.py:167-179`:
```python
def migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    """Lift a v2 file to v3 in one transaction; on any error the file stays v2."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        for step in V2_TO_V3_STEPS:
            connection.execute(step, {"now": int(time.time())})
    except BaseException:
        connection.execute("ROLLBACK")
        _LOG.error("store migration failed, the file stays at version 2", extra={"from": 2, "to": 3})
        raise
    connection.execute("COMMIT")
```
plus `repo.py:40` `SCHEMA_VERSION` erhöhen und Testmuster `tests/test_store_migration_v3.py`.

---

### `php/lib/Controller/ExportController.php` (controller, request-response + file-I/O)

**Analog:** `php/lib/Controller/PageController.php`

**Imports/Konstruktor** (Zeilen 5-25, 100-113): gleiche DI-Liste (`IRootFolder`, `IUserSession`, `IURLGenerator`, `IAppConfig`, `IL10N`, `ExAppService`, `ReaderContext`, `LoggerInterface`, `ExclusionService`), neu `DownloadPolicy`.

**Route-Attribut** (Zeilen 122-125):
```php
#[\OCP\AppFramework\Http\Attribute\NoAdminRequired]
#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/play/{fileId}', requirements: ['fileId' => '\d+'])]
```
Export: `url: '/export/{fileId}/{format}', requirements: ['fileId' => '\d+', 'format' => 'srt|vtt|txt']`. Track-Variante gleich, ohne `attachment`. Sidecar: `verb: 'POST'`, **ohne** `NoCSRFRequired`, mit `#[\OCP\AppFramework\Http\Attribute\UserRateLimit(...)]` (RESEARCH Pattern 4). `routes.php` bleibt leer (Kommentar Zeilen 5-9).

**Rechte-Kern resolve** (Zeilen 223-245), 1:1 übernehmen bzw. in gemeinsamen Dienst ziehen:
```php
$uid = $this->userSession->getUser()?->getUID();
if (!is_string($uid) || $uid === '') { return null; }
try {
    return $this->readerContext->actAs($uid, function () use ($uid, $fileId): ?array {
        $userFolder = $this->rootFolder->getUserFolder($uid);
        $file = FileAccess::readableFile($userFolder, $fileId);
        return $file === null ? null : [$userFolder, $file, $uid];
    });
} catch (\Throwable $e) {
    $this->logger->warning('Audio & Video Search: a file for the playback page could not be resolved', [
        'fileId' => $fileId,
        'class' => $e::class,
    ]);
    return null;
}
```

**Ausschluss vor Container** (Zeilen 314-329):
```php
try {
    $this->exclusions->reload();
    $excluded = $this->exclusions->isExcludedUser($uid) || $this->exclusions->isExcludedFile($fileId);
} catch (\Throwable $e) {
    ...
    $excluded = true;
}
```
Reihenfolge laut UI-SPEC: resolve, Ausschluss, `DownloadPolicy::allowed($file)` (false = 403 ohne Container-Aufruf), `searchAllowed()`, dann `ExAppService::export()`.

**Fehlerseite** (Zeilen 382-417 `unavailable`/`render`): `TemplateResponse(Application::APP_ID, '<template>', $params, TemplateResponse::RENDER_AS_USER)` + `setStatus(Http::STATUS_NOT_FOUND)` bzw. 403/503; `'id-app-navigation' => null`.

**Download-Antwort** (RESEARCH Code Examples): `new DataDownloadResponse($body, $baseName . '.' . $lang . '.srt', 'application/x-subrip; charset=utf-8')`. Name nur aus dem Node (`$file->getName()`), letzte Endung ab, NFC.

**JSON-Antwort der Ablage** (Analog `SettingsController.php:77-108`):
```php
return new DataResponse(['error' => 'Debug mode is off.'], Http::STATUS_FORBIDDEN);
...
return new DataResponse(['visible' => $wish]);
```
Für Sidecar: `DataResponse(['name' => $name], Http::STATUS_CREATED)`, 409 mit `name`, 403/400/404/503 ohne weitere Felder (UI-SPEC E1 bis E7: `play.js` liest nur `name`).

---

### `php/lib/Service/DownloadPolicy.php` (service)

**Analog:** `PageController::downloadAllowed` + `viewWithoutDownload` (Zeilen 247-275), verschieben, nicht neu schreiben:
```php
private function downloadAllowed(File $file, int $fileId): bool {
    try {
        $storage = $file->getStorage();
        if (!$storage->instanceOfStorage(ISharedStorage::class)) {
            return true;
        }
        /** @var ISharedStorage $storage */
        return $storage->getShare()->getAttributes()?->getAttribute('permissions', 'download') !== false;
    } catch (\Throwable $e) {
        $this->logger->info('Audio & Video Search: the share rules of a file could not be read', [
            'fileId' => $fileId,
            'class' => $e::class,
        ]);
        return true;
    }
}
```
Achtung: Für Export/Ablage ist `return true` im catch-Zweig zu prüfen (Security: im Zweifel sperren? Für die Wiedergabe war `true` gewollt, weil WebDAV nachprüft; beim Export gibt es keine zweite Prüfung). `IShare::canDownload()` NICHT verwenden (Nebenbefund CONTEXT). PageController ruft danach den Dienst.

---

### Nebendatei ablegen (service, file-I/O)

**Analog:** PII `C:/Users/Student/nextcloud-pii-redaction/php/lib/Service/PublishService.php:95-136`
```php
$outcome = $this->readerContext->actAs($uid, function () use ($job, $original, $temp): array {
    ...
    if ($this->files->downloadBlocked($original)) {
        return [Reason::DownloadBlocked, false, null];
    }
    $folder = $original->getParent();
    if (!$folder->isCreatable()) {
        return [Reason::TargetNotWritable, false, null];
    }
    $name = $folder->getNonExistingName(...);
    try {
        $created = $folder->newFile($name, $temp);
    } catch (NotPermittedException) {
        return [Reason::TargetNotWritable, false, null];
    }
    return [null, true, $created];
});
```
Übernehmen: `actAs` als Nutzer, Sperrprüfung, `getParent()->isCreatable()`, `NotPermittedException` fangen. **Abweichen:** KEIN `getNonExistingName` (D-04-05: kein Alternativname); stattdessen unter eigener Sperre (`ILockingProvider::acquireLock`, Signatur vor Bau prüfen, RESEARCH A3) `if ($parent->nodeExists($name))` 409, sonst `newFile`. NFC wie `ExclusionService.php:809-817`:
```php
private static function composed(string $value): string {
    if (!class_exists(\Normalizer::class)) {
        return $value;
    }
    $composed = \Normalizer::normalize($value, \Normalizer::FORM_C);
    return is_string($composed) ? $composed : $value;
}
```
Bytelänge <= 255 prüfen (E5). PII hält Dateianlage per Gate-Regel 18 in einer Datei; für AV analog eine neue Gate-Regel "newFile nur in <Datei>" erwägen.

---

### `php/lib/Search/Provider.php` (provider, ÄNDERN) + `php/lib/Service/SearchFilters.php` (neu)

**Analog:** AV-Provider selbst; Findling-Provider für Filterlesen.

**Zu ersetzen** (AV `Provider.php:136-144`):
```php
/**
 * Only the term in phase 1. ...
 */
#[\Override]
public function getSupportedFilters(): array {
    return [IFilter::BUILTIN_TERM];
}
```
Neu: `[IFilter::BUILTIN_TERM, IFilter::BUILTIN_SINCE, IFilter::BUILTIN_UNTIL, IFilter::BUILTIN_PERSON]` (alle drei Pflicht, sonst "Partial matches", RESEARCH Pattern 2). `getCustomFilters()` bleibt `[]` (nur Kern-Namen; Findling `Provider.php:206-243` warnt: eigener Name ohne Definition bricht alle Provider).

**Filter lesen** (Findling `php/lib/Search/Provider.php:270-276`):
```php
$filters = new SearchFilters(
    $types,
    SearchFilters::SORT_DEFAULT,
    $this->epochWithin($this->epochOf($query, IFilter::BUILTIN_SINCE)),
    $this->epochWithin($this->epochOf($query, IFilter::BUILTIN_UNTIL)),
    $this->folderOf($query),
);
```
Wertobjekt-Form aus Findling `php/lib/Service/SearchFilters.php:133-152, 214-216` (readonly-Konstruktor, `none()`, `hasAny()`), für AV schlank: `since`, `until`, `person` (uid oder gid). Personen-Unterscheidung über `->get() instanceof IUser / IGroup`, nie über `OC\`-Klassen.

**Einhängen nach der Rechteprüfung** (AV `Provider.php:265-281`): nach `$file = $checked[$fileId]; if ($file === null) continue;` den Filter prüfen (`$file->getMTime()` inklusive Grenzen; Person über vorab je Runde geladene `file_source`-Menge). Cache je Datei wie `$checked`. Pitfall 4: `MAX_ROUNDS`/`OVERFETCH` (Zeilen 89-90) bei gesetzten Filtern ggf. erhöhen, `BUDGET_SECONDS = 2.5` bleibt.

**oc_share-Abfrage, eine je Runde** (Muster `php/lib/Db/QueueMapper.php:256` und RESEARCH Code Examples):
```php
->where($update->expr()->in('id', $update->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
```
mit Bedingung `uid_owner = uid OR (share_with = uid AND share_type = IShare::TYPE_USER)` bzw. Gruppe `share_with = gid AND share_type = IShare::TYPE_GROUP`. DB-Zugriff mit `IDBConnection`/`IQueryBuilder` ist im Projekt etabliert (QueueMapper, StorageService:219, StorageClassifier:389).

---

### `php/lib/Service/ExAppService.php` (service, ÄNDERN: `export()`)

**Analog:** `excerpt()` Zeilen 233-324 (Typprüfung jedes Feldes, ein falsches Feld = `null`, `known:false` verwirft alles):
```php
$answer = $this->call('/excerpt', $uid, ['fileId' => $fileId, 'atMs' => $startMs], self::REQUEST_TIMEOUT_SECONDS);
if ($answer === null || !is_bool($answer['known'] ?? null)) {
    return null;
}
...
if ($answer['known'] === false) {
    return $unknown;
}
```
Neu: eigene Konstante neben `REQUEST_TIMEOUT_SECONDS = 1.5` (Zeile 65), z. B. `EXPORT_TIMEOUT_SECONDS` (gemessen, RESEARCH A4). `MAX_BODY_BYTES = 1048576` (Zeile 155) gilt in `call()` (Zeilen 1009 ff.) und ist für 12-h-Dateien zu klein: eigene Obergrenze für die Export-Antwort messen. Sprache gegen `['de','en','fr']` prüfen, `und` = keine Antwort. Gate-Regel 3: Container nur aus `ExAppService` rufen.

---

### `php/lib/Controller/PageController.php` (controller, ÄNDERN)

**Analog:** sich selbst. Parameter-Übergabe Zeilen 154-167 (`render([...])`) um `exportState`, `exportUntilClock`, `exportUntilIso`, `exportUrls`, `sidecarAllowed`, `sidecarName`, `sidecarUrl`, `trackUrl`, `trackLang`, `trackLabel` erweitern; `unavailable()` (Zeilen 385-398) muss dieselben Schlüssel mit leeren Werten setzen (X4 byte-gleich). Zustandsableitung wie `excerpt()` Zeilen 313-371 (Konstanten `EXCERPT_*` als Vorbild für `EXPORT_AVAILABLE|PARTIAL|BLOCKED|NONE`). Zeiten über `Provider::clock()` (`Provider.php:349-358`) und `self::isoDuration()` (Zeilen 197-206). URLs über `$this->urlGenerator->linkToRoute('audio_video_search.export.<methode>', [...])`. Gate-Regel 14 (`test_php_gates.py:707-872`) prüft, dass die Abspielseite vor dem Ausschnitt die Ausschlüsse fragt; der Export-Zustand muss denselben Weg nehmen.

---

### `php/templates/play.php` (component, ÄNDERN) und Fehlerseite

**Analog:** `play.php`

**Defensives Lesen der Parameter** (Zeilen 35-50):
```php
$excerptState = is_string($_['excerptState'] ?? null) ? $_['excerptState'] : 'skipped';
$downloadAllowed = ($_['downloadAllowed'] ?? false) === true;
```

**Icons als Pfaddaten** (Zeilen 28-33) um `download` und `file-plus`, `check-circle-outline` ergänzen.

**Satz mit Element im Platzhalter** (Zeilen 59-60, 166), für T15 "Transkript bis %s" mit `<time class="avs-play__time">`:
```php
$marker = "\u{E000}";
$startParts = explode($marker, $l->t('Starts at %s', [$marker]), 2) + ['', ''];
...
<p class="avs-play__meta"><?php p($startParts[0]); ?><time class="avs-play__time" datetime="<?php p($startIso); ?>"><?php p($startClock); ?></time><?php p($startParts[1]); ?></p>
```

**Vorgerenderte, verborgene Banner** (Zeilen 170-195) als Vorlage für `#avs-sidecar-result` E1 bis E7 (`role="alert" tabindex="-1"` bei Fehler, `hidden`, `avs-banner--success` existiert schon in `play.css:92-95, 117-119`).

**Medium** (Zeile 198): `<track>` als Kind des `<video>` einfügen (statt selbstschließendem `</video>` direkt), nur bei `mediaTag === 'video'` und X1/X2. **Neuer Abschnitt** nach `section.avs-excerpt` (Zeilen 207-223), gleiche Form `aria-labelledby`.

**Knopf-hidden-Muster** (Zeile 202): `<button type="button" id="avs-jump" class="avs-play__jump" hidden>`; genauso `#avs-sidecar`. Gate-Regel 11 (`test_php_gates.py:388`): jede `hidden`-Regel muss gegen Server-CSS gewinnen, also ID tragen.

Fehlerseite `export_error.php`: Kopf mit `\OCP\Util::addStyle('audio_video_search', 'play')` (Zeilen 23-26), ein Banner `error` + Aktion als `<a class="avs-banner__action" href=...>` (Zeile 186).

---

### `php/js/play.js` (component, event-driven, ÄNDERN)

**Analog:** `play.js` (Stil, IIFE, kein Markup aus Strings) + `admin.js` (POST).

Knopf sichtbar schalten (`play.js:55-62`):
```js
const jump = document.getElementById('avs-jump')
if (jump !== null && serverStart > 0) {
  jump.hidden = false
  jump.addEventListener('click', function () { ... })
}
```
Banner zeigen mit Fokus (`play.js:71-82`, `show()`): `banner.hidden = false; banner.focus()`.

POST mit Token (`admin.js:35-54`):
```js
const response = await fetch(url(path), {
  ...
  headers: { requesttoken: document.head.dataset.requesttoken, ... }
})
```
Busy-Zustand (`admin.js:97-110, 166-182`): `button.disabled = on`, `stateArea.setAttribute('aria-busy', 'true')`, Texte nur über `textContent`. Antwortname nur übernehmen, wenn `^[^/\\]{1,255}$` (UI-SPEC E2), sonst E7. Die Abspielseite wird ohne `#avs-media` sofort verlassen (Zeile 21); Ablage-Code muss vor diesem `return` oder unabhängig davon laufen (Audio und Video haben `#avs-media`, aber X3 hat keine Ablage).

---

### `php/css/play.css` (ÄNDERN)

**Analog:** Zeilen 154-157 (`.avs-banner__action` mit `min-height: var(--default-clickable-area)`), 194-197 (`.avs-play__jump`), 240-246:
```css
@media (pointer: coarse) {
	.avs-play__jump,
	.avs-play__files,
	.avs-banner__action {
		min-height: calc(var(--default-grid-baseline) * 11);
	}
}
```
`.avs-export__download`, `.avs-export__save` in diese Liste aufnehmen; übrige Regeln exakt laut UI-SPEC-Tabelle "CSS (neu)". Gate `test_ui_assets.py` prüft Variablen-only.

---

### l10n-Kataloge `php/l10n/{de,de_DE,en,fr}.json` + `.js`

**Analog:** `php/l10n/de.json` / `de.js`:
```json
{
    "translations": {
        "Show in Files": "In Dateien anzeigen",
```
```js
OC.L10N.register(
    "audio_video_search",
    {
    "Show in Files": "In Dateien anzeigen",
```
Englischer Text = Schlüssel; `de` und `de_DE` inhaltsgleich; FR mit U+00A0 vor `: ; ? !`; `.js` exakt Zwilling der `.json` (`test_trilingual.py:235-306`). Hinweis: Katalog hat "In Dateien anzeigen", UI-SPEC-Tabelle schreibt "In Dateien zeigen"; der Bestandsschlüssel gilt (UI-SPEC Zeile 311). Stichproben für T13 bis T35 in `test_the_php_catalogue_holds_the_texts_of_the_ui_spec` (Zeilen 309-343) ergänzen. Backend-l10n (`backend/l10n/*`) nur bei neuen Container-Texten, nicht vorgesehen.

---

### Tests Backend

**`test_numbers.py`** nach Findling `backend/tests/test_analyzer.py:93-157`: handgeschriebene Erwartungstabelle als Modulkonstante + `@pytest.mark.parametrize(..., ids=[text for text, _ in TABLE])`, nicht aus dem Generator abgeleitet (Owner-Regel Gegenprobe). Dazu Findlings `COMPOUNDS` (Zeilen 93-122) und `UNSPLIT` (126-137) als Regressionsschutz übernehmen; die Zeile `("Haushaltssatzung", ["haushalt", "satzung"])` und die "nicht zerlegbar"-Fälle dokumentieren die F1-Grenze.

**`test_search_numbers.py`** nach `backend/tests/test_index_publish.py`: Fixture `search_index(tmp_path)` (Zeilen 19-26), Helfer `_segment`/`_words` (28-37), `CONSTITUENTS` aus `tests.test_index_open`; Fälle "zwölf/12/twelve/douze", "12:30" ohne Fehler (vgl. `test_an_empty_or_broken_query_is_an_empty_list` Zeile 102), "Häuser", "Haushalt" (Präfix).

**`test_subtitles.py`**: Form wie `test_segments_split_at_a_gap_and_after_forty_words` (`test_index_publish.py:224-245`) plus Eigenschaftstests über alle Cues; Parser webvtt-py/srt (dev) und `ffmpeg` per `subprocess` als Fremdprüfer.

**`test_api_export.py`** nach `backend/tests/test_excerpt_states.py` (TestClient + `signed_headers` aus `tests.conftest`, Zeilen 21-34; Leck-Fälle wie `test_an_unknown_file_gets_known_false_and_nothing_else` Zeile 438, `test_a_reference_without_a_hit_hides_text_stage_and_reason_byte_for_byte` Zeile 452, `test_an_excluded_file_with_a_reason_is_answered_like_one_never_seen` Zeile 474).

**`test_public_texts.py`** (Zeilen 126-129 lesen beide Kataloge) und Text-Gate EXP-04 ("BITV-konform"/"BITV compliant"/"conforme BITV" verboten, "Untertitel-Entwurf"/"Subtitle draft"/"Brouillon de sous-titres" Pflicht) als neue Testfunktion mit Selbsttest (Muster "every rule has to be able to fire", `test_trilingual.py:346 ff.`).

### Tests PHP

**Analog:** `php/tests/Unit/PlayControllerTest.php` (Kopf Zeilen 1-150): `#[CoversClass(...)]`, `final class ... extends TestCase`, Zustandsfelder in `setUp()` zurücksetzen, `controller()` baut Doubles für `IUserSession`, `Folder::getFirstNodeById`, `IRootFolder::getUserFolder`, `ISharedStorage` + `IAttributes` (Imports Zeilen 20, 31-32) für die Download-Sperre, `$containerNeverAsked` für "403 vor Container-Aufruf". Gate-Regel 10: kein Helfer, der eine finale TestCase-Methode überschattet (z. B. `status`).

### Playwright `ci/playwright/export.spec.ts` + `helpers.ts`

**Analog:** `ci/playwright/helpers.ts`: `APP_PATH` (Zeile 12), `users`/`fileIds` aus Env (34-62, neue IDs für Freigabe mit Download-Sperre und Nur-Lesen-Freigabe dort ergänzen, gesetzt von `ci/seed.sh`), `login` (106-109), `playPath` (94-96), `screenshot` (240), `reviewer`/`gridOnly` (75-92) für Raster DE/FR/Hochkontrast, `occ` (378-381), Kontrastmessung `excerptNoteContrast` (451-464) als Vorlage für `.avs-export__note`/`__hint`. Regel im Kopf (Zeilen 6-7): keine festen Wartezeiten, nur web-first Assertions und `waitForResponse`. Download-Prüfung über `page.waitForEvent('download')`, sha256 vor/nach für E2.

## Shared Patterns

### Rechteprüfung (alle PHP-Routen und der Provider)
**Source:** `php/lib/Service/FileAccess.php:59-72` + `ReaderContext::actAs`
```php
public static function readableFile(Folder $userFolder, int $fileId): ?File {
    return self::readableNode(self::nodeById($userFolder, $fileId));
}
```
Gate-Regel 4 (`test_php_gates.py:293`): Node-Lookup nach ID nur in `FileAccess.php`. Pfad nur über `FileAccess::relativePath` (Zeilen 166-168), nie geloggt.

### Ausschluss "Regeln von jetzt"
**Source:** `PageController.php:314-329`, `Provider.php:161-173, 268`. Jede neue Route ruft `reload()` und `isExcludedUser`/`isExcludedFile` vor dem Container; Fehler = ausgeschlossen. Gate-Regel 14.

### Logging ohne Inhalte
**Source:** `PageController.php:238-241`: nur `fileId` und `class`, keine Namen/Pfade/Begriffe (Gate-Regel 6, `test_php_gates.py:302`). Python: `publish.py:30` "Nothing here logs a word, a term or a path; only ids and counts."

### Container-Aufruf
**Source:** `ExAppService::call` (Zeilen 979-1009) über `proxyRequest` (929-943); nur aus `ExAppService` (Gate-Regel 3). Container-Routen in `backend/appinfo/info.xml` (Gate aus 02-09) und hinter `AppAPIAuthMiddleware`; alle Store-/Index-Arbeit über `run_locked` (`api/__init__.py:51-58`).

### Leck-Regel Container
**Source:** `api/excerpt.py:34, 56-60`: `{"known": False}` für nicht aktiv, ausgeschlossen, unbekannt; PHP verwirft bei `known:false` jedes weitere Feld (`ExAppService.php:266-277`).

### Texte DE/EN/FR
**Source:** `test_trilingual.py` (Kataloge, Platzhalter, Zwillinge, NBSP), `test_public_texts.py` (Umlaute, keine Gedankenstriche/Emojis), `test_php_gates.py:317` (Regel 8, keine Dash-Zeichen unter `php/`). Jeder sichtbare Text über `$l->t()`/`$l->n()`, Fremdwerte mit `p()`.

### Strikte PHP-Dateien
Gate-Regel 7: `declare(strict_types=1);` als erste Anweisung; Klassen `final`.

## No Analog Found

| Datei | Rolle | Datenfluss | Grund |
|---|---|---|---|
| Zahlwort-Generator in `index/numbers.py` (Tabellen DE/EN/FR, Ordinalia, Jahreszahlen) | utility | transform | Kein Zahlen-Code in AV oder Findling; nur Form-Analog. Inhalt nach RESEARCH Pattern 1 (Token-Tabelle) |
| Cue-Algorithmus in `subtitles/cues.py` (Umbruch, cps, Timing-Dehnung) | utility | transform | `segments_from_words` liefert nur die Schneide-Form; Algorithmus nach RESEARCH Pattern 5 |
| Sperrschlüssel `ILockingProvider` für Prüf-und-Schreib-Sequenz | service | file-I/O | Kein Lock-Code im Projekt (grep ohne Treffer); Signatur an `OCP\Lock\ILockingProvider` stable33 vor Bau prüfen (RESEARCH A3) |

## Metadata

**Analog search scope:** `php/lib/**`, `php/templates`, `php/js`, `php/css`, `php/l10n`, `php/tests/Unit`, `backend/src/audio_video_search_backend/{api,index,store,worker,engine,model}`, `backend/tests`, `backend/appinfo`, `ci/playwright`; extern Findling `php/lib/Search`, `php/lib/Service/SearchFilters.php`, `backend/src/findling/query/rewrite.py`, `backend/tests/test_analyzer.py`; PII `php/lib/Service/PublishService.php`
**Files scanned:** ca. 40
**Pattern extraction date:** 2026-11-16
