# Phase 1: Zwei-App-Gerüst und Integrationsbeweis - Research

**Researched:** 2026-11-06
**Domain:** Nextcloud-Zwei-App-Integration (PHP-App + AppAPI-ExApp), Unified Search, HTML5-Abspielansicht über WebDAV, Datenmodell (Inhalts-Schlüssel, Provenienz, Korrektur-Schicht)
**Confidence:** HIGH für Plattformfakten (Quelltext NC 33/35, AppAPI, Mobil-Apps gelesen), MEDIUM für Datenmodell-Entscheide (begründet, lokal teilweise geprüft, noch nicht im Container gemessen)

<user_constraints>
## User Constraints

Es gibt für Phase 1 keine CONTEXT.md. Die folgenden Owner-Entscheide stammen aus dem Auftrag, aus STATE.md und SUMMARY.md und sind gesetzt.

### Locked Decisions
- Zwei Apps: PHP-App `audio_video_search` (Zertifikat aus PR #1409, gemergt 05.11.2026) und ExApp `audio_video_search_backend` (Zertifikat-PR #1417, offen seit 06.11.2026).
- Minimale eigene Abspielansicht mit `#t=` (der Viewer kann keine Startzeit), keine Medienübersicht.
- Export SRT/VTT/TXT kommt später (nicht Phase 1).
- Freigaben mit Download-Sperre: Suche ja, Export nein.
- BITV-Weg in v1: Korrekturen als eigene Schicht über den Maschinen-Stufen (Schema in Phase 1, Editor in Phase 10).
- Fehlerstatus ohne Dateinamen (auch in Logs keine Pfade).
- Datenschutz: nichts verlässt den Server (kein Audio, kein Text, keine Telemetrie).
- Qualität vor Speed; Entwicklungsaufwand ist kein Grund, die bessere Lösung wegzulassen.
- Alle nutzersichtbaren Texte DE/EN/FR, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis.
- Vor jedem Push, Merge oder Kommentar den Owner fragen; Commits nur als street1983nk <k.cherif@outlook.de>, ohne "closes #N".
- UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel).

### Claude's Discretion
- Wahl der Suchmaschine (Tantivy oder FTS5), Inhalts-Schlüssel, Verankerung der Korrekturen, Ordnung der Provenienz, Form der Lockstep-Prüfung, Form des Dummy-Treffers: in diesem Dokument je mit Empfehlung.

### Deferred Ideas (OUT OF SCOPE)
- Medienübersicht/eigene Medienseite (v2), Korrektur-Editor (Phase 10), Export (Phase 4), echte Transkription (Phase 3), Discovery/Crawl (Phase 2), cgroup-Wächter (Phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAT-01 | Zwei Apps aus dem Store, Lockstep (gleiche Version, Upgrade-Beweis in CI) | Abschnitt "Entscheid 6", Muster Findling `test_lockstep_versions.py`, `occ app_api:app:update --info-xml` (Quelltext geprüft), synthetische Vorversion für den Upgrade-Test |
| PLAT-02 | Klare Meldung bei fehlender, nicht erreichbarer oder anders versionierter Gegen-App | `PublicFunctions::getExApp()` in AppAPI stable33 bis 35 (geprüft) liefert Registrierung, Version, enabled ohne Netzaufruf; `/status` für Erreichbarkeit; Handshake-Route für die Gegenrichtung |
| PLAT-03 | NC 33, 34, 35, AppAPI/HaRP, amd64 + arm64, nur CPU | Skeleton-`deploy-harp.yml` hat 33/34/35, Findling-Matrix mit `ubuntu-24.04-arm`; tantivy 0.26.2 hat cp313-Wheels für x86_64 und aarch64 (PyPI geprüft) |
| PLAY-01 | Klick öffnet Abspielansicht an der Zeitstelle mit Transkript-Ausschnitt | Entscheid 1 und 7: eigene Route, `SearchResultEntry.resourceUrl`, Web-Client nutzt nur `href` (Quelltext geprüft) |
| PLAY-02 | Seek über WebDAV auf NC 33 bis 35, hell/dunkel, drei Breiten | Entscheid 1: GET/HEAD ohne CSRF-Prüfung (Auth.php stable33/35), Sabre liefert 206 + `Accept-Ranges`, CSP `media-src 'self'` Standard |
| TRANS-06 | Herkunft je Transkript, veraltetes Ergebnis überschreibt nie ein neueres | Entscheid 5: Ordnungsschlüssel `(epoch, level, config_version)` mit bedingtem UPSERT, lokal gegen SQLite 3.45.3 geprüft |
</phase_requirements>

## Summary

Phase 1 ist ein Walking Skeleton mit zwei Zielen: (a) der ganze Integrationsweg PHP-App -> AppAPI -> Container -> Unified Search -> Abspielansicht läuft auf NC 33/34/35 und amd64/arm64 echt durch, und (b) die Datenentscheide, deren Korrektur später am teuersten wäre (Inhalts-Schlüssel, Provenienz, Korrektur-Schicht, Index als abgeleitete Größe), stehen im Schema und sind durch Tests belegt. Fast alles für (a) existiert schon gehärtet in Findling (`C:/Users/Student/nextcloud-search`); neu sind nur die Abspielroute und die Zeitmarke im Treffer.

Die sieben Pflichtfragen sind geklärt. Der Viewer bekommt keine Startzeit: nextcloud/viewer#2176 und #3226 sind am 25.10.2026 als `NOT_PLANNED` geschlossen, und in der Nachfolge-Bibliothek `nextcloud-libraries/nextcloud-viewer` gibt es weder Issue noch PR dazu. Eine eigene Seite mit `<video>` auf die WebDAV-Adresse funktioniert mit dem Sitzungs-Cookie, weil Nextcloud GET/HEAD von der CSRF-Prüfung ausnimmt und Sabre Range-Anfragen mit 206 beantwortet. Ein eigener Stream-Controller wäre ein Nachbau dessen, was Sabre schon richtig macht. Beim Suchindex löst sich der Widerspruch so auf: SQLite ist die Wahrheit, der Suchindex ist abgeleitet und jederzeit neu baubar. Damit ist die Motorwahl umkehrbar. Empfohlen ist trotzdem Tantivy ab Phase 1, weil FTS5 kein deutsches Stemming und keine Kompositazerlegung hat und Python keine eigenen FTS5-Tokenizer registrieren kann. Den Atomaritätsvorteil von FTS5 holt ein Versionsfilter (`index_rev`) ein.

Beim Inhalts-Schlüssel spricht der Beleg gegen den PCM-Fingerabdruck als Primärschlüssel: FFmpeg prüft seine eigenen Fließkomma-Decoder (MP3, Opus, Vorbis, AAC) in FATE nur mit Toleranz (`CMP = oneoff/stddev`, `FUZZ`), also nicht bitgenau. Ein sha256 über dekodiertes PCM ist darum über ffmpeg-Versionen und CPU-Architekturen nicht stabil. Empfehlung: sha256 der Dateibytes als Schlüssel, im Download-Strom berechnet, mit `(file_id, etag, size)` als Vorfilter. Dazu eine Indirektionstabelle `media_key(kind, value) -> media_id`, damit später ein zweiter Schlüssel (Hash der Audio-Pakete gegen den ID3-Fall) ohne Migration dazukommt. Korrekturen hängen an Audiozeit in Millisekunden, nicht an Wortindizes. Sie gehören zum Inhalt (`media_id`), nicht zu einer Maschinen-Version, und werden beim Lesen per Mittelpunktregel über die jeweils aktuelle Maschinen-Version gelegt.

**Primary recommendation:** Repo auf `php/` + `backend/` umbauen (ExApp-ID `audio_video_search_backend`). Findling-Bausteine übernehmen: Application, Provider, ExAppService mit Lockstep, Gateway, ReaderContext, CI-Gates. Die Abspielansicht als PHP-Template mit `<video>` auf die WebDAV-Adresse bauen. Das SQLite-Schema mit `media`/`media_key`/`file_ref`/`transcript`/`word`/`current`/`correction` und bedingtem UPSERT gleich in Phase 1 anlegen, Tantivy als abgeleiteten Index mit Versionsfilter.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Unified-Search-Provider, Treffer mit Zeitmarke | PHP-App (API/Backend) | Container (Kandidaten) | Nur PHP kann `registerSearchProvider`; Container liefert nur file_id + Zeit + Text |
| Rechteprüfung je Treffer und je Abspielaufruf | PHP-App | - | Index kennt nie Rechte; `getUserFolder()->getFirstNodeById()` + `isReadable()` zur Abfragezeit |
| Abspielansicht (Seite, `<video>`, Ausschnitt) | Browser | PHP-App (Template, Recheck, DAV-Adresse) | Seek macht der Browser per Range direkt gegen WebDAV |
| Byte-Auslieferung inkl. Range | Nextcloud-WebDAV (Sabre) | - | Vorhanden, getestet, ViewOnly-Regeln eingebaut |
| Lockstep- und Gegen-App-Prüfung | PHP-App | Container (`/status`, Handshake) | Admin-Meldung erscheint auf der PHP-Admin-Seite |
| Transkript-Wahrheit, Provenienz, Korrekturen | Container (SQLite WAL) | - | Einziger SQL-Schreiber, Findling-Muster `store/repo.py` |
| Suchindex | Container (Tantivy) | SQLite (Neuaufbau) | Abgeleitet, jederzeit aus SQLite neu baubar |
| Inhalts-Schlüssel (sha256) | Container | PHP-Gateway (liefert Bytes) | Hash im Download-Strom, kein zweites Lesen |

## Die sieben Pflichtfragen: Befund und Empfehlung

### Entscheid 1: Abspielansicht, Range über WebDAV, Shares, CSP, Mobil

**Stand Viewer [VERIFIED: gh API, 06.11.2026]:**
- `nextcloud/viewer#2176` ("Navigate to specific timestamps in video urls"): CLOSED, `NOT_PLANNED`, 25.10.2026 13:43. `#3226` ("Starting an audio at a specific timestamp"): CLOSED, `NOT_PLANNED`, 25.10.2026 13:42. Begründung susnux: Viewer wird nur noch als Bibliothek `nextcloud-libraries/nextcloud-viewer` entwickelt, Feature-Wünsche dort neu stellen.
- In `nextcloud-libraries/nextcloud-viewer` (letzter Push 05.11.2026) findet die Suche nach "timestamp", "start time", "seek", "currentTime" weder Issue noch PR. Die Bibliothek wechselt auf Video.js (PR #128) und zeigt Untertitel-Nebendateien (PR #184, #186), hat aber keine Startzeit.
- **Folge:** eigene Route. Ein Feature-Wunsch in der Bibliothek darf gestellt werden (Owner-Frage, Kommentar-Regel), ändert Phase 1 aber nicht.

**Range mit Sitzungs-Cookie aus `<video>` [VERIFIED: nextcloud/server stable33 + stable35, `apps/dav/lib/Connector/Sabre/Auth.php`]:**
```php
private function requiresCSRFCheck(): bool {
    $methodsWithoutCsrf = ['GET', 'HEAD', 'OPTIONS'];
    if (in_array($this->request->getMethod(), $methodsWithoutCsrf, true)) {
        return false;
    }
```
GET und HEAD brauchen kein `requesttoken`. Ein `<video src="/remote.php/dav/files/{uid}/{pfad}">` auf derselben Origin schickt das Sitzungs-Cookie mit und wird angenommen. Genau so spielt der Viewer heute Videos ab.

**Range-Verhalten [VERIFIED: sabre-io/dav `lib/DAV/CorePlugin.php`, NC 33 nutzt `sabre/dav ^4.7.0`]:** `getHTTPRange()`, `If-Range` mit ETag oder Datum, Antwort `206` mit `Content-Range`, immer `Accept-Ranges: bytes`, `416` bei ungültigem Start. Ist der Speicher-Stream nicht seekbar, liest Sabre bis zum Startpunkt vor (Zeilen 172 bis 179). Auf externen Speichern ohne Seek (SMB/S3 je nach Treiber) kann ein Sprung in Minute 50 einer großen Datei deshalb langsam sein. [MEDIUM: Treiberverhalten nicht gemessen]

**Eigener Stream-Controller mit `StreamResponse`:** nicht bauen. `OCP\AppFramework\Http\StreamResponse` kann kein Range. Man müsste 206/416, `If-Range`, Mehrfachbereiche, ETag, ViewOnly-Regeln und Verschlüsselungs-Streams nachbauen. Findlings Gateway ist bewusst nur für den Container da (`#[ExAppRequired]`, Prüfung von `EX-APP-ID`) und bleibt so.

**Pfad statt fileId:** WebDAV adressiert über den Pfad. Die PHP-Route bekommt die fileId und rechnet serverseitig um: `getUserFolder($uid)->getFirstNodeById($fileId)`, `isReadable()`, `getRelativePath()`. Dann wird jedes Segment mit `rawurlencode` kodiert, die UID ebenfalls (LDAP-UIDs, Leerzeichen, `@`). Gruppenordner erscheinen als Mount im Nutzerordner (`/Gruppenname/...`), empfangene Freigaben unter ihrem Zielnamen. Beides hat einen gültigen DAV-Pfad aus Sicht des Nutzers. Wird die Datei zwischen Seitenaufbau und Abspielen umbenannt, gibt es 404. Dann zeigt die Seite einen klaren Hinweis und einen Link zum Neuladen. [VERIFIED: Findling `SearchService::readableFile`; DAV-Pfadschema ASSUMED aus Viewer-Verhalten]

**Download-Sperre [VERIFIED: `apps/dav/lib/DAV/ViewOnlyPlugin.php` stable33/35, `Share20/Share.php::canSeeContent`, `Share20/Manager.php::allowViewWithoutDownload`]:** Bei GET auf eine empfangene Freigabe mit gesperrtem Download liefert Nextcloud den Inhalt trotzdem, solange `core/shareapi_allow_view_without_download` an ist (Standard `true`). Hat der Admin das abgeschaltet, antwortet WebDAV mit 403. Die Abspielansicht muss diesen Fall als eigene Meldung zeigen ("Abspielen ist für diese Freigabe gesperrt"), nicht als Fehler. Die Suche zeigt den Treffer weiter (Owner: Suche ja).

**CSP [VERIFIED: `lib/public/AppFramework/Http/ContentSecurityPolicy.php` stable33]:** `allowedMediaDomains = ["'self'"]`. Die WebDAV-Adresse liegt auf derselben Origin, also braucht es keine CSP-Änderung. Kein `blob:` verwenden, keine Inline-Skripte (Nonce-Pflicht der Seite), Skript als Datei über `Util::addScript`.

**Mobil-Apps [VERIFIED: Quelltext nextcloud/android `UnifiedSearchViewModel.kt`, android-library `SearchResultEntry.kt`, nextcloud/ios `NCCollectionViewCommon+Search.swift`]:**
- Android: `isFile = attributes["fileId"] != null || (resourceUrl enthält dir und scrollto)`. Ist es eine Datei, öffnet die App sie nativ über `attributes["path"]` (sonst wird der Pfad aus `dir`/`scrollto` der URL geparst). Sonst öffnet sie `resourceUrl` im Browser.
- iOS (Standard-Zweig für fremde Provider): mit `fileId` oder Pfad wird die Datei als Datei-Metadatum geöffnet, sonst als URL-Eintrag.
- **Folge:** Einen Zeitsprung gibt es in den Mobil-Apps in keinem Fall. Sie öffnen entweder die Datei nativ ab 0:00 oder die Webseite im Browser, wo erst eine Web-Anmeldung nötig ist. Achtung: Wer nur `fileId` ohne `path` setzt, bekommt auf Android einen kaputten Pfad ("null/null"), weil die Play-URL kein `dir`/`scrollto` hat. Empfehlung siehe Offene Frage 1.

**Zeitparameter und Anmeldung [ASSUMED, Browserstandard]:** Das Fragment `#t=` geht nicht an den Server. Ist die Sitzung abgelaufen, leitet Nextcloud auf die Anmeldung um, und die `redirect_url` wird serverseitig ohne Fragment gebaut, also ist die Zeit nach der Anmeldung weg. Außerdem kann die Seite den Ausschnitt um die Zeitstelle nur serverseitig holen, wenn sie die Zeit kennt. **Empfehlung:** `resourceUrl = /apps/audio_video_search/play/{fileId}?t=754.2`. Die Seite setzt dann `<video>` per Media Fragment `#t=754.2` und zusätzlich `currentTime`. Die Seite akzeptiert auch `#t=` (Owner-Entscheid bleibt im Kern erhalten: Media Fragment am Medium). Owner bestätigen lassen.

### Entscheid 2: Suchindex Tantivy oder SQLite FTS5

**Was Phase 1 wirklich braucht:** ein Dummy-Treffer über den echten Weg. Das könnte jeder Motor.

**Was schwer umkehrbar ist:** nicht der Motor, sondern (a) SQLite als einzige Wahrheit für Wörter, Zeiten, Versionen, Provenienz und Korrekturen und (b) die Regel, dass der Index nur abgeleitet ist und nie etwas enthält, das nicht aus SQLite neu entstehen kann. Gelten (a) und (b), ist ein Motorwechsel nur ein Neuaufbau. Transkripte sind klein (60 min Sprache sind ca. 9.000 Wörter, ARCHITECTURE.md).

**Belege:**
- FTS5 hat genau vier eingebaute Tokenizer: `unicode61`, `ascii`, `porter` ("designed for use with English language terms only") und `trigram` (Teilstrings ab 3 Zeichen, kein Stemming). Eigene Tokenizer gehen nur über die C-API (`fts5_api`, `sqlite3_bind_pointer`). [CITED: sqlite.org/fts5.html] Das Python-Modul `sqlite3` bietet dafür keine Schnittstelle. [ASSUMED: stdlib-Doku nicht im Detail geprüft]
- Findling hat für Tantivy 0.26.2 deutsche, englische und französische Snowball-Ketten, Kompositazerlegung, Schema-/Analyzer-Versionsmarken, Neuaufbau und Verzeichnistausch bereits gebaut und gemessen (`backend/src/findling/index/analyzer.py`, `open.py`, `rebuild.py`, `writer.py`). [VERIFIED: Codebasis]
- tantivy 0.26.2 hat Wheels `cp313-manylinux_2_17_x86_64` und `cp313-manylinux_2_17_aarch64` (Upload 17.09.2026). 0.27.0 ist aktuell. [VERIFIED: PyPI JSON]
- Der Atomaritätsvorteil von FTS5 (Tausch in einer SQLite-Transaktion) lässt sich mit Tantivy über einen Versionsfilter nachbilden (Muster 3 unten). Findlings Zweiphasen-Ärger kommt vom Tausch ganzer Verzeichnisse beim Analyzer-Wechsel (Windows-mmap, Writer-Handles, `rebuild.py` Zeilen 26 bis 75). Der Tausch eines einzelnen Inhalts in einem Commit ist dagegen einfach.

**Empfehlung (prescriptive):**
1. In Phase 1 SQLite als Wahrheit festschreiben, mit `meta.schema_version` und `meta.index_generation`.
2. Tantivy 0.26.2 als einzigen Suchmotor ab Phase 1, hinter einer schmalen Schnittstelle `SearchIndex` (`publish(media_id, index_rev, segments)`, `retire(media_id, keep_rev)`, `search(term, limit) -> [(media_id, index_rev, seg_idx, start_ms, score)]`, `rebuild_from_store()`). Der Dummy-Treffer läuft schon durch Tantivy. So ist die arm64-Lauffähigkeit, die Analyzer-Registrierung beim Öffnen und der RAM-Bedarf (deutscher Automat ca. 23 MB, Findling-Messung) von Anfang an im CI.
3. Analyzer-Code aus Findling kopieren (nicht importieren), nur DE/EN/FR. Index-Felder je Sprache; welche Sprache ein Segment hat, entscheidet Phase 3 (in Phase 1 alle Felder befüllen oder nur `body_de` + `body_en`, Planer-Ermessen).
4. FTS5 nicht zusätzlich bauen.

### Entscheid 3: Inhalts-Schlüssel

| Kriterium | sha256 der Datei | sha256 über dekodiertes 16-kHz-PCM | Hash der Audio-Pakete (`-c copy`) |
|---|---|---|---|
| Kosten | im Download-Strom, ca. 0 zusätzlich (Download ist ohnehin nötig, MP4 mit moov am Ende braucht die ganze Datei) | voller Decode + Resampling (schnell, aber für jede Datei, auch für reine Dedup-Fragen) | Demux ohne Decode, billig |
| Stabil bei ID3/MP4-Tag-Änderung | nein | ja | ja [ASSUMED] |
| Stabil bei Remux (MP4 -> MKV) | nein | ja | eher nein (Paketrahmen wie ADTS unterscheiden sich) [ASSUMED] |
| Deterministisch über ffmpeg-Versionen/CPU | ja | **nein**: FFmpeg prüft MP3 (`CMP = oneoff`, `FUZZ = 18`), Opus (`CMP = stddev`), Vorbis (`oneoff`), AAC (`stddev`) in FATE nur mit Toleranz [VERIFIED: FFmpeg `tests/fate/*.mak`]; SIMD-Pfade wählt ffmpeg zur Laufzeit je CPU | ja, kein Fließkomma [ASSUMED] |
| Kollisions-/Fehlerrisiko | keins | Wechsel des ffmpeg-Builds (Monatsend-Autobuild, Dependabot) macht alle Schlüssel neu: Neuberechnungs-Sturm | gering |

**Empfehlung:**
- **Primärschlüssel ist `file_sha256`** (Dateibytes), im Download-Strom berechnet (Findling-Muster `nc/client.py:363 fetch_file_stream`).
- **Vorfilter** `(file_id, etag, size)`: Ist beides unverändert, wird nicht neu geladen. Den ETag vergibt Nextcloud je Schreibvorgang, er ist kein Inhaltshash und taugt nur als Änderungsmerker.
- **Indirektion im Schema:** Transkripte hängen an einem Ersatzschlüssel `media_id`. `media_key(kind, value) -> media_id` ist eindeutig je `(kind, value)`. Phase 1 schreibt nur `kind='file_sha256'`. Ein späterer Zweitschlüssel (`audio_pkt_sha256` gegen den ID3-Fall, erst nach Messung) kommt ohne Migration dazu, indem er auf eine vorhandene `media_id` zeigt.
- **PCM-Fingerabdruck nicht als Schlüssel verwenden,** auch nicht optional. Wenn überhaupt, dann nur mit der Decoder-Kennung im `kind` (z. B. `pcm_sha256@ffmpeg-n8.1-amd64`), und das bringt wenig.
- **In Phase 1 ins Schema:** `media`, `media_key`, `file_ref(file_id PK, media_id NULL, storage_id, etag, size, mtime, state, reason, updated_at)`. Rechte bleiben je file_id (nie über den Schlüssel vererben, PITFALLS 4/6).

### Entscheid 4: Verankerung von Nutzerkorrekturen

**Befund:** Wortindizes ändern sich bei jeder neuen Maschinen-Version (andere Wortzahl, ROVER fügt ein und verwirft). Als Anker taugen sie nicht. Die Audiozeit desselben Inhalts (gleiche `media_id`) ist dagegen invariant. Die Engines weichen nur um Dutzende bis wenige Hundert Millisekunden ab (PITFALLS 15, Spike 2: Parakeet-Zeiten präziser).

**Empfehlung, Schema:**
```sql
CREATE TABLE correction (
    correction_id   INTEGER PRIMARY KEY,
    media_id        INTEGER NOT NULL REFERENCES media(media_id),
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL CHECK (end_ms > start_ms),
    kind            TEXT    NOT NULL CHECK (kind IN ('text','speaker','sound')),
    body            TEXT    NOT NULL,            -- Ersatztext, Sprechername oder Geräuschmarke
    words_json      TEXT,                        -- optional: eigene Wortzeiten aus dem Editor (Phase 10)
    base_version_id INTEGER,                     -- Maschinen-Version, die der Nutzer sah
    base_text       TEXT,                        -- Maschinentext der Spanne zum Zeitpunkt der Korrektur
    author_uid      TEXT    NOT NULL,            -- BITV-04: wer und wann; DSGVO-Löschpfad in Phase 8
    created_at      INTEGER NOT NULL,
    superseded_by   INTEGER REFERENCES correction(correction_id),
    reviewed_at     INTEGER                      -- Phase 10 "geprüft"
);
CREATE INDEX correction_media ON correction (media_id, start_ms) WHERE superseded_by IS NULL;
```
- Anker = `[start_ms, end_ms)` in ganzen Millisekunden der Audiozeit, gebunden an `media_id` (nicht an `version_id`).
- **Überlagerung beim Lesen (reine Funktion):** Ein Maschinenwort fällt in eine Text-Korrektur, wenn sein Mittelpunkt `(start+end)/2` in `[start_ms, end_ms)` liegt. Diese Wörter werden durch die Korrekturwörter ersetzt. Sie tragen `words_json` oder werden gleichmäßig über die Spanne verteilt und bekommen `src='user'`. Alles außerhalb kommt aus der jeweils aktuellen Maschinen-Version.
- Invariante beim Schreiben: aktive Text-Korrekturen einer `media_id` überlappen nicht. Eine neue Korrektur über eine alte setzt `superseded_by` (Historie bleibt, BITV-04).
- Ändert sich die Datei (neuer Inhalt, neue `media_id`), gelten alte Korrekturen nicht automatisch weiter. "Korrekturen übernehmen" wäre ein Phase-10-Thema.
- Index und Export lesen immer `effective_words(machine_current, corrections_active)`. Jede Korrektur erhöht `current.index_rev`, damit der Index neu veröffentlicht wird.
- `base_text` dient nur der Konfliktanzeige in Phase 10 ("die Maschine hört hier inzwischen etwas anderes"). Die Korrektur gewinnt immer.

**Testfall (Phase 1, Erfolgskriterium 5):**
- Maschine v1 (Level 100): `der`(0-200) `haus`(250-450) `halts`(460-700) `plan`(710-900) `wurde`(950-1200).
- Korrektur `kind='text'`, `[250, 900)`, `body='Haushaltsplan'`.
- Maschine v2 (Level 200, neue Wortzahl, Zeiten um bis zu 120 ms verschoben): `der`(0-180) `Haushalts`(240-640) `plan`(650-880) `wurde`(1000-1250) `beschlossen`(1260-1900).
- Erwartet nach dem Ersatz: `der Haushaltsplan wurde beschlossen`. Genau ein `Haushaltsplan`, kein `Haushalts`, `beschlossen` aus v2 bleibt, Korrektur-Wortzeit innerhalb `[250, 900)`.
- Randfälle als eigene Tests: (1) v2 hat in der Spanne keine Wörter, die Korrektur wird trotzdem eingesetzt. (2) Ein Wort mit Mittelpunkt genau auf `end_ms` bleibt Maschine (halboffenes Intervall). (3) Eine Korrektur einer anderen `media_id` wird nicht angewendet. (4) Eine Korrektur übersteht auch die Abweisung eines veralteten Ergebnisses (Entscheid 5). (5) Die Suche nach "Haushaltsplan" findet die Datei nach dem Ersatz über den Index.

### Entscheid 5: Provenienz und bedingtes Schreiben

**Pflichtfelder je Transkript-Version:** `engine` (`sample`, `parakeet`, `whisper-turbo`, `whisper-large-v3`, `rover`), `model_sha256` (bei ROVER die sortierte Liste beider), `config_version` (ganze Zahl, Konstante im Code, steigt bei jeder Änderung der Spike-3-Parameter, ROVER-Schwellen oder Normalisierung), `profile` (`fast`/`balanced`/`quality`, nur zur Information), `level` (Ordnung), `epoch`, `language`, `created_at`, dazu `media_id` und `input_file_sha256`.

**Ordnung:** lexikografisch `(epoch, level, config_version)`.
- `level`: Stufen mit Abstand, damit später etwas dazwischen passt: `sample=1`, `preview=100` (Parakeet + Schluck-Wächter), `selective=150` (Parakeet + selektives turbo), `refined=200` (turbo + ROVER), `refined_l3=300` (large-v3 + ROVER, DE).
- Höhere Stufe gewinnt immer. Bei gleicher Stufe gewinnt die höhere `config_version` (Modell-Update rechnet gezielt nach, Owner-Entscheid je Release). Gleichstand gilt als veraltet und wird abgewiesen (idempotent, keine Doppelarbeit).
- `epoch` je `media_id` (Standard 0) erhöht nur der Admin mit "neu rechnen" oder ein Rückruf eines fehlerhaften Modells. Damit kann eine niedrigere Stufe bewusst gewinnen. Ohne `epoch` gäbe es keinen Weg zurück.
- Profil-Herabstufung (Qualität -> Schnell) lässt vorhandene bessere Transkripte stehen. Das ist gewollt.
- Ein Ergebnis für alten Dateiinhalt landet strukturell bei der alten `media_id` und kann die neue nie überschreiben. Zusätzlich prüft der Schreiber `input_file_sha256` gegen `media_key`.

**Bedingtes Schreiben [VERIFIED: lokal gegen SQLite 3.45.3, Python 3.13.1; Zeilenwert-Vergleich ab 3.15, UPSERT-WHERE ab 3.24]:**
```sql
INSERT INTO current (media_id, version_id, epoch, level, config_version, index_rev)
VALUES (:m, :v, :e, :l, :c, 1)
ON CONFLICT (media_id) DO UPDATE SET
    version_id = excluded.version_id, epoch = excluded.epoch,
    level = excluded.level, config_version = excluded.config_version,
    index_rev = current.index_rev + 1
WHERE (excluded.epoch, excluded.level, excluded.config_version)
    > (current.epoch, current.level, current.config_version);
-- changes() = 0  ->  ROLLBACK, Ergebnis "stale_rejected" zählen und verwerfen
```
Gemessen: Einfügen 1, bessere Stufe 1, ältere Stufe mit höherer config 0, Gleichstand 0, Epoch-Erhöhung 1. Alles in `BEGIN IMMEDIATE`, damit Versionszeilen und Zeiger gemeinsam stehen oder fallen.

### Entscheid 6: Zwei-App-Lockstep, Meldungen, CI-Upgrade, Store

**Findling-Muster [VERIFIED: Codebasis]:**
- Drei Werte, eine Zahl: `php/appinfo/info.xml <version>`, `backend/appinfo/info.xml <version>` und `<image-tag>`, dazu `pyproject.toml` und Git-Tag `v<version>`. `backend/tests/test_lockstep_versions.py` vergleicht sie bei jedem Lauf, `docker.yml` vergleicht sie beim Tag gegen den Git-Tag, ein zweiter Test vergleicht das Serverfenster (`min/max-version`) beider Hälften mit der CI-Matrix.
- Laufzeit: Der Container meldet `appVersion` aus `APP_VERSION` (setzt AppAPI) in `GET /status`. PHP liest die eigene Version über `IAppManager::getAppVersion()` und vergleicht Major.Minor (`ExAppService::lockstep()`, `driftOnRecord()`). Bei Drift liefert die Suche nichts statt Geratenem.
- `info.xml` kennt keine App-zu-App-Abhängigkeit. Die Bindung an `app_api` und an die Gegen-App prüft deshalb der Code zur Laufzeit.

**Verbesserung für PLAT-02 (Findling unterscheidet nur erreichbar/nicht erreichbar):** `OCA\AppAPI\PublicFunctions::getExApp(string $appId): ?array` liefert `appid`, `version`, `name`, `enabled` aus der AppAPI-Datenbank, ohne Netzaufruf. [VERIFIED: app_api stable33, stable34, stable35, main] Daraus folgen fünf Zustände für die Admin-Seite. Jeder hat einen eigenen übersetzten Text und keinen Dateinamen:

| Zustand | Erkennung | Meldung (Sinn) | Suche |
|---|---|---|---|
| `no_app_api` | `isEnabledForUser('app_api')` falsch oder `PublicFunctions` nicht auflösbar | AppAPI fehlt | leer |
| `backend_missing` | `getExApp(...) === null` | Backend-App installieren (Link auf External Apps) | leer |
| `backend_disabled` | `enabled` falsch | Backend-App aktivieren | leer |
| `backend_unreachable` | registriert und aktiv, `/status` scheitert | Backend antwortet nicht (Deploy-Daemon/HaRP prüfen) | leer |
| `version_drift` | Major.Minor ungleich (aus `getExApp().version` oder `/status.appVersion`) | Beide Apps auf dieselbe Version bringen, beide Versionen nennen | leer |
| `version_patch_differs` | nur Patch ungleich | Hinweis, kein Fehler | normal |

**Gegenrichtung (Backend ohne PHP-App):** Der Container ruft beim Start und periodisch eine eigene OCS-Route der PHP-App auf (`GET /ocs/v2.php/apps/audio_video_search/api/v1/handshake`, `#[ExAppRequired]`, Prüfung von `EX-APP-ID`). Die Antwort liefert die Companion-Version. Bei 404 oder Fehler: `/status.companion = "missing"`, eine Logzeile (Findling: "the queue has not answered for ..."), und der Container arbeitet nicht. Die Beschreibung der ExApp-Einstellungsseite nennt statisch die Pflicht der PHP-App. Ob zusätzlich eine Admin-Benachrichtigung geht (nc_py_api `notifications.create` braucht einen Nutzer), ist offen. [ASSUMED]

**CI-Upgrade-Beweis ohne Vorversion:** Es gibt noch kein Release (keine Git-Tags). Empfehlung:
1. Im Job beide Hälften aus demselben Commit zweimal bauen: einmal mit synthetischer Vorversion (Versionen in beiden `info.xml` und im Image-Tag auf `0.0.1` umgeschrieben), einmal unverändert (`0.1.0`).
2. `0.0.1` installieren, Dummy-Transkript säen, Suche prüfen.
3. PHP-Hälfte: Dateien ersetzen und `occ upgrade` aufrufen (Exit 0 oder 3 wie Findling). ExApp: `occ app_api:app:update audio_video_search_backend --info-xml <neu> --wait-finish` (Option in AppAPI stable33 vorhanden [VERIFIED: `lib/Command/ExApp/Update.php`]). Das ist derselbe Weg wie ein Store-Update. Findling nutzt unregister/register. Der Update-Befehl ist näher am echten Store-Ablauf, muss aber am Harness zeigen, dass das Volume bleibt.
4. Danach prüfen: `state.db` und Dummy-Treffer sind noch da, `schema_version` stimmt, Lockstep `match`.
5. Drift-Schritte wie Findling ("Drift 1/2/3"): Container mit anderer Major.Minor registrieren, Admin-Zustand `version_drift` und leere Suche prüfen, dann zurück.
6. Sobald `v0.1.0` getaggt ist, die synthetische Vorversion durch die echte Vorversion aus den Release-Assets ersetzen (Findling "Store upgrade 1").

**Store-Ablauf mit zwei Apps [VERIFIED: gh, Findling `store-submit.yml`, `release.yml`]:** Zertifikat `audio_video_search` gemergt (PR #1409, 05.11.2026), `audio_video_search_backend` offen (PR #1417, 06.11.2026). Erfolgskriterium 1 verlangt nur den gestellten Antrag, das ist erfüllt. Zwei Archive, zwei Signaturen, Secrets `APP_PRIVATE_KEY` (PHP-App, vorhanden) und `BACKEND_PRIVATE_KEY` (neu, nach Merge von #1417). In `release.yml` braucht es eine zweite Zertifikats-Pin (`CERT_PUBKEY_SHA256` gilt jetzt für die PHP-App). Der erste Store-Upload ist kein Thema von Phase 1.

### Entscheid 7: Unified-Search-Provider mit Zeitmarke

**API-Stand [VERIFIED: nextcloud/server stable33 und stable35, `lib/public/Search/`]:** dieselben Dateien (`IFilteringProvider`, `SearchResultEntry`, `FilterDefinition`, ...), `SearchResultEntry::__construct` und `addAttribute` seit 20.0.0 unverändert. Ein Provider deckt 33 bis 35 ab.

**Web-Client [VERIFIED: `core/src/components/UnifiedSearch/SearchResult.vue`, `UnifiedSearchModal.vue` stable33]:** Der Treffer ist ein `<a :href="resourceUrl" target="_self">`, Attribute nutzt der Web-Client nicht. Bei aktiven Inhaltsfiltern werden Provider ohne `supportsActiveFilters` ausgeblendet und deren Einträge über `resourceUrl` dedupliziert. Gibt es mehrere Stellen je Datei (Phase 3), hat jede eine eigene URL (eigenes `t`) und wird nicht weggefiltert.

**Empfehlung für den Eintrag:**
- `title` = Dateiname (`$node->getName()`).
- `subline` = `"12:34 · <Ausschnitt>"` (über 1 h `1:02:03`, Trennzeichen Mittelpunkt, kein Gedankenstrich). Der Ausschnitt ist reiner Text, Vue maskiert ihn. Keine HTML-Hervorhebung in Phase 1.
- `resourceUrl` = `linkToRouteAbsolute('audio_video_search.page.play', ['fileId' => $id, 't' => '754.2'])` (siehe Entscheid 1).
- `thumbnailUrl` = Mime-Symbol (`IMimeTypeDetector::mimeTypeIcon`) oder leer. Vorschaubilder von Videos erst später.
- Attribute `fileId` und `path` nur nach Owner-Entscheid (Offene Frage 1).
- Provider-ID `audio_video_search`, Name "Audio und Video" (l10n), `getOrder` wie Findling, Zeitbudget 2,5 s (Findling `Provider::BUDGET_SECONDS`), zweistufig (Kandidaten -> Recheck -> Ausschnitt). Filter in Phase 1 nur `BUILTIN_TERM`. `since/until/title-only` kommen mit Phase 3, sonst blendet die Suche die Gruppe bei aktiven Filtern aus.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Nextcloud OCP (PHP) | NC 33 bis 35, PHP >= 8.2 (35: 8.3 in CI) | Search Provider, Controller, TemplateResponse, IAppConfig | Einziger Weg in die Unified Search [VERIFIED: Findling] |
| AppAPI `PublicFunctions` | app_api stable33 bis 35 | `exAppRequest`, `getExApp` | Signierter Pfad PHP -> Container, Registrierungsabfrage [VERIFIED] |
| nc-py-api[app] | 0.30.3 | AppAPI-Vertrag im Container | Skeleton-Pin, nur Async-API [VERIFIED: pyproject] |
| FastAPI | 0.162.0 | Container-HTTP | Skeleton-Pin [VERIFIED] |
| Python sqlite3 (WAL) | Python 3.13, SQLite der trixie-Basis (3.46.x) [ASSUMED: Debian-Version] | Wahrheit | Findling-Muster `store/repo.py` |
| tantivy | 0.26.2 | Abgeleiteter Suchindex DE/EN/FR | Findling-Code 1:1, cp313-Wheels x86_64/aarch64 [VERIFIED: PyPI] |
| Sabre DAV (in Nextcloud) | `sabre/dav ^4.7.0` | Range-Auslieferung | Bestandteil von Nextcloud [VERIFIED: 3rdparty composer.json] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| phpunit | 11.5.x (Findling `php/composer.json`) | PHP-Tests | nur CI (lokal kein PHP) |
| pytest / ruff / pyright / vulture | 9.2.0 / 0.17.3 / 1.1.414 basic / 2.16 | Python-Gates | Owner-Regel, Skeleton |
| @playwright/test | 1.65.0 (npm, 06.11.2026) | Abspielansicht in CI (206, currentTime, 3 Breiten, hell/dunkel) | CI-Job; zusätzlich Owner-Abnahme gemeinsam |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WebDAV-Quelle | eigener Range-Stream-Controller | Nachbau von 206/416/If-Range/ViewOnly; kein Gewinn |
| Tantivy | FTS5 im `state.db` | Atomarer Tausch trivial, aber kein deutsches Stemming/Kompositum; Python kann keinen Tokenizer registrieren |
| `file_sha256` | PCM-sha256 | Stabil bei ID3, aber nicht deterministisch über ffmpeg-Builds/CPU (FATE-Toleranzen) |
| `app_api:app:update` im Upgrade-Test | unregister + register (Findling) | Findling-Weg ist erprobt; Update-Befehl entspricht dem Store-Weg |

**Installation (Container, Ergänzung zum Skeleton):**
```bash
uv add "tantivy==0.26.2"
```

## Package Legitimacy Audit

slopcheck ließ sich in dieser Sitzung nicht installieren (Ausführung fremden Codes vom Klassifizierer abgelehnt). Alle neuen Pakete sind deshalb `[ASSUMED]`. Die Registerprüfung lief.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| tantivy 0.26.2 | PyPI | seit Jahren (0.27.0 aktuell) | nicht erhoben | github.com/quickwit-oss/tantivy-py (PyPI-Metadaten) | nicht gelaufen | Approved per Findling-Einsatz (seit 1.x im Store), trotzdem [ASSUMED] |
| @playwright/test 1.65.0 | npm | seit Jahren | nicht erhoben | github.com/microsoft/playwright | nicht gelaufen | Approved, nur CI, `postinstall` leer [VERIFIED: npm view] |
| phpunit 11.5 | Packagist | seit Jahren | nicht erhoben | github.com/sebastianbergmann/phpunit | nicht gelaufen | Approved per Findling-Lock |

**Packages removed due to slopcheck [SLOP] verdict:** keine
**Packages flagged as suspicious [SUS]:** keine (slopcheck nicht gelaufen; der Planer setzt für tantivy keinen Checkpoint, weil Findling dieselbe Version produktiv nutzt, Owner-Entscheid)

## Architecture Patterns

### System Architecture Diagram

```
Nutzer tippt Suchwort
   │
   ▼
Unified Search (NC-Web)  ──GET /ocs/v2.php/search/providers/audio_video_search/search──▶ PHP Provider
                                                                                         │
            ┌────────────────────────────────────────────────────────────────────────────┤
            │ Vorab: getExApp() + Lockstep (aus Cache/AppConfig) ── Drift/fehlt ──▶ leere Gruppe
            ▼
   exAppRequest(audio_video_search_backend, /search, uid)  (signiert, HaRP)
            │
            ▼
   Container /search ──▶ Tantivy (Kandidaten: media_id, index_rev, start_ms, seg)
            │                 │
            │                 ▼
            │           SQLite: index_rev == current.index_rev ? sonst verwerfen
            │                 │
            │                 ▼
            │           file_ref: media_id -> [file_id ...]
            ▼
   PHP Recheck je file_id: getUserFolder(uid)->getFirstNodeById + isReadable
            │ (nicht lesbar: weg)
            ▼
   SearchResultEntry(title=Name, subline="12:34 · Ausschnitt", resourceUrl=/apps/audio_video_search/play/{fileId}?t=754.2)
            │
            ▼  Klick
   PHP PageController::play(fileId, t)
            │  Recheck, DAV-Pfad bauen, Ausschnitt um t vom Container holen
            ▼
   Template: <video|audio src="/remote.php/dav/files/{uid}/{pfad}#t=754.2"> + Ausschnitt
            │
            ▼  Browser (Sitzungs-Cookie, GET ohne CSRF)
   WebDAV (Sabre) ──Range: bytes=...──▶ 206 Partial Content ──▶ Wiedergabe ab t

Gegenrichtung:  Container ──GET /ocs/.../api/v1/handshake (ExAppRequired)──▶ PHP (Companion-Version)
Dummy-Saat:     occ audio_video_search:dev:sample <fileId> ─▶ PHP ─▶ Container /admin/sample
                ─▶ Container holt Bytes über Gateway (sha256 im Strom) ─▶ media/media_key/transcript(level=1)
                ─▶ current (bedingt) ─▶ Tantivy publish(index_rev)
```

### Recommended Project Structure
```
php/                                  # App audio_video_search (Findling-Layout)
├── appinfo/info.xml, routes.php      # routes.php leer, Routen per Attribut
├── lib/AppInfo/Application.php       # registerSearchProvider, APP_ID, BACKEND_APP_ID
├── lib/Search/Provider.php           # Zeitmarke, Ausschnitt, play-URL
├── lib/Service/ExAppService.php      # exAppRequest, getExApp, lockstep, Zustände
├── lib/Service/ReaderContext.php     # Findling-Kopie
├── lib/Controller/PageController.php # play/{fileId}
├── lib/Controller/GatewayController.php   # Findling-Kopie (ExAppRequired)
├── lib/Controller/HandshakeController.php # Companion-Version für den Container
├── lib/Settings/Admin.php, Section.php    # Zustandsanzeige PLAT-02
├── lib/Command/SampleCommand.php     # occ-Saat des Dummy-Treffers (nur mit Debug-Schalter)
├── templates/play.php, admin.php
├── js/play.js, css/play.css          # reines Browser-JS, kein Bundler (Findling-Muster)
├── l10n/ (de, de_DE, en, fr)
└── tests/                            # phpunit
backend/                              # ExApp audio_video_search_backend (aus dem Skeleton verschoben)
├── appinfo/info.xml                  # id, image audio_video_search_backend, routes ^/<name>$
├── Dockerfile, pyproject.toml, uv.lock
├── src/audio_video_search_backend/
│   ├── main.py, config.py, logs.py, settings.py, nc.py   # Skeleton
│   ├── api/status.py, api/search.py, api/sample.py
│   ├── store/schema.sql, store/repo.py                    # einziger SQL-Ort
│   ├── model/provenance.py, model/overlay.py              # reine Funktionen
│   └── index/analyzer.py, schema.py, open.py, publish.py  # Tantivy (Findling-Kopie, DE/EN/FR)
└── tests/
.github/workflows/                    # python.yml, php.yml, docker.yml, deploy-harp.yml (Matrix 6 Beine), release.yml (2 Archive)
```

### Pattern 1: Lockstep- und Gegen-App-Zustand (PHP)
```php
// Quelle: Findling ExAppService::lockstep + AppAPI PublicFunctions::getExApp (stable33)
public function backendState(string $uid): array {
    $api = $this->publicFunctions($uid);                 // prüft app_api enabled
    if ($api === null) { return ['state' => 'no_app_api']; }
    $info = $api->getExApp(Application::BACKEND_APP_ID);
    if ($info === null) { return ['state' => 'backend_missing']; }
    if (!$info['enabled']) { return ['state' => 'backend_disabled']; }
    $own = $this->appManager->getAppVersion(Application::APP_ID);
    if ($this->majorMinor($own) !== $this->majorMinor((string)$info['version'])) {
        return ['state' => 'version_drift', 'own' => $own, 'backend' => (string)$info['version']];
    }
    $status = $this->call('/status', $uid, []);          // 1,5 s Timeout wie Findling
    if ($status === null) { return ['state' => 'backend_unreachable']; }
    return ['state' => $own === $info['version'] ? 'ok' : 'version_patch_differs'];
}
```

### Pattern 2: Bedingtes Veröffentlichen mit Provenienz (Python)
```python
# Quelle: eigener Entwurf, SQL lokal gegen SQLite 3.45.3 geprüft
def publish_version(conn, media_id, prov, words) -> bool:
    with conn:  # isolation_level=None + explizites BEGIN IMMEDIATE in repo.py
        conn.execute("BEGIN IMMEDIATE")
        vid = conn.execute(INSERT_TRANSCRIPT, prov.as_row(media_id)).lastrowid
        conn.executemany(INSERT_WORD, ((vid, i, w.start_ms, w.end_ms, w.surface, w.norm, w.conf, w.src)
                                       for i, w in enumerate(words)))
        conn.execute(UPSERT_CURRENT, {"m": media_id, "v": vid, "e": prov.epoch,
                                      "l": prov.level, "c": prov.config_version})
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            conn.execute("ROLLBACK")
            return False  # stale_rejected
        conn.execute("COMMIT")
    return True
```

### Pattern 3: Tantivy als abgeleiteter Index mit Versionsfilter
Reihenfolge, damit nie null und nie doppelte Treffer entstehen:
1. SQLite: neue Version schreiben und `current` bedingt umsetzen (Pattern 2), `index_rev` steigt.
2. Tantivy: Dokumente mit `(media_id, index_rev_neu)` hinzufügen, `commit`, `reload`.
3. Tantivy: Dokumente mit `media_id` und `index_rev != neu` löschen (`delete_documents_by_query`, Findling `writer.py:330`), `commit`.
4. Suche: Kandidaten aus Tantivy nur übernehmen, wenn `index_rev == current.index_rev` (ein Primärschlüssel-Lookup). Zwischen Schritt 1 und 2 fehlen die neuen Dokumente kurz. Darum vor Schritt 1 die Dokumente hinzufügen, wenn die Ablehnung unwahrscheinlich ist, oder ein Filter, der `index_rev in (alt, neu)` bis zum Commit akzeptiert. Der Planer legt das in einer Aufgabe fest. Der Lasttest "Suche in Schleife während des Tauschs" gehört zu Phase 6 (TRANS-04).
5. Anlauf-Abgleich: Tantivy-Dokumente ohne passenden `current.index_rev` löschen, fehlende aus SQLite nachtragen (Tabelle `index_outbox(media_id, index_rev)`).
6. `meta.index_generation` + Analyzer-/Schema-Marken wie Findling `open.py`. Eine Abweichung baut den Index aus SQLite neu (hier billig, weil SQLite den Text hält).

### Pattern 4: Abspielseite (Template + reines JS)
```js
// play.js, kein Bundler, keine Inline-Skripte (CSP-Nonce), Findling-Muster
'use strict'
;(function () {
  const media = document.getElementById('avs-media')
  if (!media) return
  const start = Number(media.dataset.start || '0')       // serverseitig aus ?t= validiert
  const fromHash = /^#t=(\d{1,6}(?:\.\d{1,3})?)$/.exec(window.location.hash)
  const t = fromHash ? Number(fromHash[1]) : start
  const seek = () => { if (t > 0 && Number.isFinite(t)) media.currentTime = t }
  if (media.readyState >= 1) seek(); else media.addEventListener('loadedmetadata', seek, { once: true })
  media.addEventListener('error', () => { document.getElementById('avs-error').hidden = false })
})()
```
Die Seite rendert `src` schon mit `#t=` (Media Fragment, wirkt auch ohne JS). `currentTime` ist die Absicherung für Browser, die das Fragment nach dem Laden ignorieren. Fehlerzustände (403 Download-Sperre, 404 umbenannt) erscheinen als Textblock mit Rolle `alert`.

### Anti-Patterns to Avoid
- **Eigener Range-Controller:** siehe oben, Nachbau von Sabre.
- **Wortindex als Korrekturanker:** bricht beim ersten Ersatz.
- **Rechte im Container oder über den Inhalts-Schlüssel vererben:** Recheck je file_id in PHP.
- **Dateinamen oder Pfade in Logs/Status:** Owner-Regel; nur file_id und Fehlerklasse.
- **Nur `fileId`-Attribut ohne `path`:** Android baut daraus einen kaputten Pfad.
- **H.264/AAC-Testmedium mit dem gebündelten Chromium:** Codecs evtl. nicht vorhanden; WebM (VP9/Opus) und Ogg/Opus als Testmedien nehmen, MP4 nur mit `canPlayType`-Prüfung.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Range/206/If-Range | Stream-Controller | WebDAV `/remote.php/dav/files/...` | Sabre + ViewOnlyPlugin + Verschlüsselungs-Streams |
| Player | Eigene Steuerelemente | natives `<video controls>`/`<audio controls>` | Tastatur/Screenreader eingebaut, Mobilbrowser |
| Deutsches Stemming/Komposita | Python-Vorstemming für FTS5 | Findling-Analyzer in Tantivy | gemessen, versioniert |
| Signierter Aufruf PHP -> Container | eigener HTTP-Client | `PublicFunctions::exAppRequest` | HaRP, Signatur, Timeout |
| Registrierungsprüfung | DB-Abfrage `oc_ex_apps` | `PublicFunctions::getExApp` | öffentliche Schnittstelle |
| Lockstep-Gates, Store-Archiv, Signatur | neue Skripte | Findling `test_lockstep_versions.py`, `store-archive.sh`, `release.yml` | erprobt im Store |
| Rechte-Recheck mit Gruppenordner-ACL | eigene ACL-Logik | `ReaderContext::actAs` + `readableFile` (Findling #14) | bekannte Falle |

**Key insight:** Neu in Phase 1 sind nur die Abspielseite, die Zeitmarke und das Datenmodell. Alles andere ist kopierter, gehärteter Findling-Code. Jede Eigenentwicklung dort wäre ein Rückschritt.

## Runtime State Inventory

Phase 1 benennt die bestehende ExApp-ID `audio_video_search` in `audio_video_search_backend` um und verschiebt das Repo in `backend/` + `php/`.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Keine Installation mit Daten bekannt; CI-Instanzen sind Wegwerf. Ob auf budachst oder lokal eine Testinstallation der ExApp `audio_video_search` läuft, ist nicht geprüft [ASSUMED: nein] | Owner fragen; falls ja: `occ app_api:app:unregister audio_video_search --rm-data` vor der ersten PHP-App-Installation (gleiche ID!) |
| Live service config | App-Store: Zertifikat `audio_video_search` (PR #1409) gilt jetzt für die PHP-App. Ob die ID im Store schon als App registriert ist, ist offen. `audio_video_search_backend`: PR #1417 offen | Store-Registrierung beider IDs in Phase 11; nichts in Phase 1 |
| OS-registered state | Keine (keine Tasks, Dienste) [VERIFIED: nichts im Repo] | keine |
| Secrets/env vars | GitHub-Secrets `APP_PRIVATE_KEY` (Schlüssel `audio_video_search` = jetzt PHP-App), `APPSTORE_TOKEN`; lokaler Schlüssel `~/.nextcloud/certificates/audio_video_search_backend.key` vorhanden; `release.yml` pinnt `CERT_PUBKEY_SHA256` des PHP-Zertifikats; Umgebungsvariablen-Präfix `AUDIO_VIDEO_SEARCH_` im Skeleton | Secret `BACKEND_PRIVATE_KEY` nach Merge #1417 (Owner), zweite Pin in `release.yml`; Präfix für den Container auf `AVS_` oder `AUDIO_VIDEO_SEARCH_BACKEND_` festlegen (Planer) |
| Build artifacts | `docker.yml` pusht bei jedem main-Lauf nach Digest nach `ghcr.io/street1983nk/audio_video_search` inkl. `buildcache-*`-Tags; lokales `.venv` mit Paket `audio_video_search`, `__pycache__` | Neues Image `audio_video_search_backend`; altes ghcr-Paket später löschen oder privat stellen (Owner, braucht `read:packages`/`delete:packages`); `uv sync` nach Umbenennung |

## Common Pitfalls

### Pitfall 1: Zeitmarke geht nach der Anmeldung verloren
**What goes wrong:** Ein Link mit `#t=` führt bei abgelaufener Sitzung über die Anmeldung, danach startet die Datei bei 0:00.
**Why it happens:** Fragmente gehen nie an den Server, `redirect_url` hat keins.
**How to avoid:** `?t=` in der resourceUrl, Fragment nur am Medium.
**Warning signs:** Playwright-Test "abgemeldet öffnen" landet bei 0.

### Pitfall 2: Download-Sperre mit abgeschaltetem "view without download"
**What goes wrong:** Die Suche zeigt einen Treffer, das Abspielen gibt 403.
**How to avoid:** Eigener Zustand auf der Seite, CI-Fall mit `occ config:app:set core shareapi_allow_view_without_download --value=no --type=boolean`.

### Pitfall 3: Langsamer Seek auf nicht seekbaren Speichern
**What goes wrong:** Sabre liest bis zum Startbyte vor.
**How to avoid:** In Phase 1 dokumentieren, in Phase 2 (externe Speicher) messen. Kein eigener Workaround.

### Pitfall 4: Analyzer nicht registriert beim Öffnen des Index
**What goes wrong:** `The tokenizer 'de' ... is unknown`, sieht aus wie ein kaputter Index.
**How to avoid:** Findling-Regel: nur `open_index()` öffnet, ein Test durchsucht das Paket nach `Index(`/`Index.open(` (Findling `test_index_open.py`).

### Pitfall 5: ExApp-Routenblock falsch
**What goes wrong:** `<url>search</url>` passt nie, weil HaRP `re.match(url, "/search")` nutzt.
**How to avoid:** Form `^/<name>$` (Skeleton-Kommentar, Findling 06.1-19). Signierte Aufrufe prüft HaRP nicht, der Block schützt nur unsignierte.

### Pitfall 6: Gleiche ID für PHP-App und alte ExApp auf einer Instanz
**What goes wrong:** Eine noch registrierte ExApp `audio_video_search` kollidiert mit der PHP-App gleicher ID.
**How to avoid:** Runtime State Inventory, Stored data.

### Pitfall 7: Testmedium spielt im CI-Browser nicht
**What goes wrong:** Der Playwright-Chromium ist ohne H.264/AAC gebaut (laut Playwright-Doku historisch so; ab 1.57 angeblich Chrome for Testing) [LOW].
**How to avoid:** Testmedien als WebM (VP9 + Opus) und Ogg/Opus erzeugen und einchecken (Sinuston, wenige KB, keine Lizenzfrage). Im Test `canPlayType` loggen.

### Pitfall 8: Zeiten als Fließkomma
**What goes wrong:** Rundungsdrift bei Vergleichen in Korrektur-Überlagerung und Index.
**How to avoid:** Überall ganze Millisekunden (`INTEGER`). Sekunden mit einer Nachkommastelle nur in URL und Anzeige.

## Code Examples

### Treffer-Eintrag
```php
// Quelle: Findling Provider::toEntries, erweitert um Zeitmarke
$t = intdiv($hit->startMs, 100) / 10;                   // 754.2
$entry = new SearchResultEntry(
    thumbnailUrl: $this->mimeIcon($hit->mime),
    title: $hit->title,
    subline: $this->clock($hit->startMs) . ' · ' . $hit->excerpt,  // "12:34 · ..."
    resourceUrl: $this->urlGenerator->linkToRouteAbsolute(
        'audio_video_search.page.play', ['fileId' => $hit->fileId, 't' => sprintf('%.1f', $t)]),
    icon: '',
);
```

### DAV-Adresse aus fileId
```php
// Quelle: Findling SearchService::readableFile; DAV-Pfadschema wie Viewer
$userFolder = $this->rootFolder->getUserFolder($uid);
$file = SearchService::readableFile($userFolder, $fileId);      // null -> 404-Seite ohne Namen
$rel = $userFolder->getRelativePath($file->getPath());          // "/Team/Sitzung.webm"
$segments = array_map('rawurlencode', explode('/', ltrim((string)$rel, '/')));
$src = $this->urlGenerator->getWebroot() . '/remote.php/dav/files/'
    . rawurlencode($uid) . '/' . implode('/', $segments);
```

### Korrektur-Überlagerung
```python
# Quelle: eigener Entwurf zu Entscheid 4
def effective_words(machine: Sequence[Word], corrections: Sequence[Correction]) -> list[Word]:
    spans = sorted((c for c in corrections if c.kind == "text"), key=lambda c: c.start_ms)
    out: list[Word] = []
    i = 0
    for c in spans:
        while i < len(machine) and _mid(machine[i]) < c.start_ms:
            out.append(machine[i]); i += 1
        while i < len(machine) and _mid(machine[i]) < c.end_ms:
            i += 1                                   # Maschinenwort ersetzt
        out.extend(_correction_words(c))             # words_json oder gleichmäßig verteilt, src="user"
    out.extend(machine[i:])
    return out

def _mid(w: Word) -> int:
    return (w.start_ms + w.end_ms) // 2
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Viewer-App `nextcloud/viewer` | Bibliothek `nextcloud-libraries/nextcloud-viewer` (2.0.0-beta, Video.js) | Okt. 2026 | Feature-Wünsche alter Repos geschlossen; Startzeit nirgends geplant |
| plyr im Viewer | Video.js (PR #128, 07.10.2026) | Okt. 2026 | ohne Bedeutung für die eigene Seite |
| Untertitel-Nebendateien unbelegt | Viewer-Bibliothek zeigt `<Name>.<Sprache>.vtt` (PR #184) und eingebettete MKV/WebM-Untertitel (PR #186) | Nov. 2026 | stützt den Owner-Entscheid "Nebendatei" für später (Phase 4), betrifft Phase 1 nicht |

**Deprecated/outdated:**
- AppAPI-Event-Listener für Dateiereignisse: ab stable32 entfernt (SUMMARY.md), deshalb PHP-Companion.
- nc_py_api-Sync-API: fällt in 0.31.0, nur Async nutzen.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python-`sqlite3` kann keine FTS5-Tokenizer registrieren | Entscheid 2 | gering, Empfehlung Tantivy steht auch ohne diesen Punkt |
| A2 | Hash der Audio-Pakete ist ID3-stabil und deterministisch | Entscheid 3 | nur Zukunftsoption, Phase 1 schreibt ihn nicht |
| A3 | Login-Umleitung verliert das Fragment `#t=` | Entscheid 1 | Falls doch erhalten: `?t=` bleibt trotzdem nötig für den Ausschnitt |
| A4 | Keine Testinstallation der alten ExApp-ID auf budachst/lokal | Runtime State | ID-Kollision bei der PHP-Installation |
| A5 | `app_api:app:update --info-xml` behält das Volume | Entscheid 6 | Upgrade-Test fällt rot; Rückfall auf Findling-Weg unregister/register |
| A6 | Playwright-Chromium ohne H.264/AAC | Pitfall 7 | gering, WebM-Testmedien umgehen es |
| A7 | trixie liefert SQLite >= 3.24 (Debian 3.46.x) | Standard Stack | UPSERT-WHERE fehlte; sehr unwahrscheinlich |
| A8 | Admin-Benachrichtigung aus dem Container ohne Nutzerkontext nicht möglich | Entscheid 6 | Wenn möglich: zusätzliche Meldung, keine Planänderung |
| A9 | iOS liest den Pfad aus einem Attribut (`filePath`); Schlüsselname nicht geprüft | Entscheid 1 | Native Öffnung auf iOS geht evtl. nur über `fileId` |

## Open Questions

1. **Mobil: nativ öffnen oder Browser mit Zeitsprung?**
   - What we know: Mit `fileId` + `path` öffnen Android und iOS die Datei in der App ab 0:00. Ohne diese Attribute öffnen sie die Play-URL im Browser, wo eine Web-Anmeldung nötig ist. Den Web-Client betrifft keins von beidem.
   - Recommendation: `fileId` + `path` setzen (kein Anmeldebruch, gewohnte Wiedergabe) und die fehlende Zeitmarke in der Doku nennen. Owner entscheidet.
2. **`?t=` statt nur `#t=` in der resourceUrl?** Empfehlung ja (Anmeldung, serverseitiger Ausschnitt). Owner bestätigt, weil der Entscheid `#t=` nannte.
3. **Dummy-Saat:** Empfehlung: echter Weg über `occ`-Befehl + Gateway + sha256, damit Schema und Schlüssel schon in Phase 1 echt laufen. Alternative ohne Gateway: fester Pseudo-Schlüssel. Der Befehl bleibt hinter einem Debug-Schalter, sonst könnte ein Admin Pseudo-Transkripte erzeugen.
4. **Feature-Wunsch in `nextcloud-libraries/nextcloud-viewer`?** Kommentar- und Issue-Regel: nur nach Owner-Freigabe.
5. **Laufzeit-Lockstep exakt oder Major.Minor?** Empfehlung: Build-Gate exakt, Laufzeit Major.Minor (Fehler) plus Patch (Hinweis), wie in der Zustandstabelle.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Python-Gates | ✓ | 0.11.7 | - |
| Python | Backend-Tests | ✓ | 3.13.1 | - |
| SQLite (Python) | Schema-Tests | ✓ | 3.45.3 | - |
| Node/npx | Playwright lokal (Owner-Abnahme) | ✓ | 22.21.0 / 11.14.1 | - |
| gh | CI-Läufe, Zertifikat-PR | ✓ | 2.92.0 | - |
| Docker | Container-Build | ✓ | 29.5.2 | lokal nicht starten (RAM ca. 6 GB frei); Builds in CI |
| PHP / Composer | phpunit | ✗ | - | nur in CI (`php.yml`), wie Findling |
| ffmpeg | Testmedien erzeugen | ✗ (nicht gefunden) | - | Testmedien einmalig in CI erzeugen und als Artefakt prüfen oder fertig einchecken |
| Nextcloud-Testinstanz | Integration | ✗ lokal | - | CI `deploy-harp.yml` (33/34/35, amd64 + arm64) |

**Missing dependencies with no fallback:** keine (alles PHP-/Integrationsseitige läuft in CI).
**Missing dependencies with fallback:** PHP, ffmpeg, Nextcloud lokal: über CI.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 (backend), phpunit 11.5 (php, CI), Playwright 1.65 (CI-Job, Abspielseite), GitHub-Actions-Integration mit HaRP |
| Config file | `backend/pyproject.toml` (aus Skeleton verschoben), `php/phpunit.xml` (Wave 0) |
| Quick run command | `cd backend && uv run pytest -q -x` |
| Full suite command | `cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q`; PHP und Integration in CI |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAT-01 | drei Versionswerte + pyproject + Matrix stimmen | unit | `uv run pytest tests/test_lockstep_versions.py -x` | ❌ Wave 0 (Findling-Kopie) |
| PLAT-01 | Upgrade 0.0.1 -> 0.1.0 beider Hälften, Daten bleiben | integration | `deploy-harp.yml` Schritt "Upgrade" | ❌ Wave 0 |
| PLAT-02 | fünf Zustände + Patch-Hinweis | unit (php) | `composer run test -- --filter BackendStateTest` | ❌ Wave 0 |
| PLAT-02 | Drift beide Richtungen, Suche leer | integration | `deploy-harp.yml` "Drift 1/2/3" | ❌ Wave 0 |
| PLAT-02 | Container meldet `companion: missing` | unit + integration | `uv run pytest tests/test_handshake.py -x` | ❌ Wave 0 |
| PLAT-03 | Matrix deckt 33/34/35 x amd64/arm64 | unit | `uv run pytest tests/test_workflows.py -x` (erweitern) | ✅ vorhanden, erweitern |
| PLAT-03 | Installation + Suche auf 6 Beinen | integration | `deploy-harp.yml` | ✅ teilweise (3 Beine, nur ExApp) |
| PLAY-01 | Eintrag mit Titel, `mm:ss · Ausschnitt`, play-URL mit `t` | unit (php) | `--filter ProviderTest` | ❌ Wave 0 |
| PLAY-01 | Klick öffnet Seite, Ausschnitt sichtbar | e2e | Playwright `play.spec.ts` | ❌ Wave 0 |
| PLAY-02 | 206-Antwort, `currentTime` ca. t, Home + Gruppenordner + Freigabe | e2e | Playwright `play.spec.ts` | ❌ Wave 0 |
| PLAY-02 | hell/dunkel, 3 Breiten (z. B. 375, 768, 1280) | e2e + Owner-Abnahme | Playwright Screenshots | ❌ Wave 0 |
| PLAY-02 | 403 bei Download-Sperre + view_without_download aus | e2e | Playwright | ❌ Wave 0 |
| TRANS-06 | Provenienz-Pflichtfelder, ältere/gleiche Herkunft abgewiesen, epoch gewinnt | unit | `uv run pytest tests/test_provenance.py -x` | ❌ Wave 0 |
| TRANS-06 | Korrektur übersteht Ersatz (Testfall Entscheid 4 + Randfälle) | unit | `uv run pytest tests/test_corrections.py -x` | ❌ Wave 0 |
| TRANS-06 | Schema-Version, `media_key`-Indirektion, Zeiten als INTEGER | unit | `uv run pytest tests/test_store_schema.py -x` | ❌ Wave 0 |
| (Index) | Versionsfilter, Anlauf-Abgleich, Analyzer beim Öffnen | unit | `uv run pytest tests/test_index_publish.py tests/test_index_open.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest -q -x`
- **Per wave merge:** volle Python-Gates lokal + CI (`python.yml`, `php.yml`, `deploy-harp.yml`)
- **Phase gate:** alles grün auf 6 Matrix-Beinen, dann gemeinsame Playwright-Abnahme mit dem Owner, dann `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Repo-Umbau `backend/` + `php/`, Pfade in allen Workflows und Tests
- [ ] `php/composer.json`, `php/phpunit.xml`, `php/tests/bootstrap.php` (Findling-Kopie)
- [ ] `backend/tests/test_lockstep_versions.py` (Findling, angepasst auf zwei IDs)
- [ ] Testmedien `testdata/tone-90s.webm`, `testdata/tone-90s.ogg` (generiert, Lizenz frei)
- [ ] Playwright-Gerüst im CI-Job (`npm ci` in einem eigenen Ordner `ci/playwright/`, nur CI)
- [ ] Matrix 33/34/35 x amd64/arm64 in `deploy-harp.yml`, PHP-App-Installation im Setup

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | ja (indirekt) | Nextcloud-Sitzung; Seite ohne `#[PublicPage]`; Container nur über signiertes AppAPI |
| V3 Session Management | ja | Nextcloud; GET-Seite mit `#[NoCSRFRequired]` ist rein lesend |
| V4 Access Control | ja | Recheck je fileId in Provider und PageController; `#[ExAppRequired]` + `EX-APP-ID`-Prüfung auf Gateway und Handshake; Admin-Zustand nur für Admins |
| V5 Input Validation | ja | `fileId` per Routen-Requirement `\d+`; `t` als Zahl 0 bis 86400 mit höchstens 3 Nachkommastellen, sonst 0; Suchbegriff gekürzt; Versionen per Muster (Findling `VERSION_PATTERN`) |
| V6 Cryptography | ja (Hash) | `hashlib.sha256` im Strom, keine Eigenentwicklung |
| V7 Error Handling and Logging | ja | keine Dateinamen/Pfade in Logs, Status und Fehlermeldungen (Owner) |
| V14 Configuration | ja | CSP Standard unverändert, keine Inline-Skripte |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR über `play/{fileId}` | Information Disclosure | `getFirstNodeById` im Nutzerordner + `isReadable`; 404 ohne Namen |
| Treffer aus nicht mehr lesbarer Datei | Information Disclosure | Recheck zur Abfragezeit, Index kennt keine Rechte |
| Fremde ExApp liest über das Gateway | Elevation of Privilege | `#[ExAppRequired]` + `EX-APP-ID == audio_video_search_backend` (Findling `rejectForeignCaller`) |
| XSS über Ausschnitt oder Dateiname | Tampering | Vue maskiert `subline`; im Template `p()`; Ausschnitt nur als Text |
| Pfadinjektion in die DAV-Adresse | Tampering | Pfad nur serverseitig aus dem Node, `rawurlencode` je Segment |
| Gefälschte `appVersion` eines Containers | Spoofing | Lockstep ist keine Authentisierung (Findling T-05-25); Schutz über signierten Pfad |
| Debug-Saat in Produktion | Tampering | `occ`-Befehl nur mit Debug-Schalter, Level `sample=1` wird von jeder echten Stufe verdrängt |

## Project Constraints (from CLAUDE.md)

- Kein Audio, Text oder Telemetrie nach außen; einzige ausgehende Verbindung ist später der Modell-Download.
- Qualität vor Speed, Qualitätsentscheide mit WER belegen (betrifft Phase 1 nur beim Index: Stemming).
- Python-ExApp aus dem Skeleton (FastAPI, nc_py_api 0.30.3, Async-API).
- NC 33 bis 35, AppAPI mit HaRP, amd64 + arm64, nur CPU.
- Texte DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis; Umlaute nur in Prosa, nie in Code/URLs/YAML-Schlüsseln.
- Gates: ruff-Vollsatz, pyright basic (`PYRIGHT_PYTHON_FORCE_VERSION=latest`), vulture lokal grün; ruff-format-Gate.
- Commits nur als street1983nk <k.cherif@outlook.de>, keine Claude-Session-Zeilen (Owner-Regel geht vor), kein "closes #N".
- Vor jedem Push, Merge oder Kommentar den Owner fragen.
- UI-Abnahme gemeinsam per Playwright, 3 Breiten, hell/dunkel; UI-Ablauf gegen Slop (DESIGN.md, nextcloud-ui).
- Ressourcen dieser Maschine: keine Docker-Stacks lokal, keine großen Downloads.

## Sources

### Primary (HIGH confidence)
- gh API: nextcloud/viewer#2176, #3226 (Status, Abschlusskommentar), nextcloud-libraries/nextcloud-viewer (Issues/PRs, Push 05.11.2026)
- nextcloud/server stable33/stable35: `apps/dav/lib/Connector/Sabre/Auth.php`, `apps/dav/lib/DAV/ViewOnlyPlugin.php`, `lib/private/Share20/Share.php`, `lib/private/Share20/Manager.php`, `lib/public/AppFramework/Http/ContentSecurityPolicy.php`, `lib/public/Search/*`, `core/src/components/UnifiedSearch/SearchResult.vue`, `UnifiedSearchModal.vue`
- sabre-io/dav `lib/DAV/CorePlugin.php`; nextcloud/3rdparty stable33 `composer.json`
- nextcloud/app_api stable33/34/35/main `lib/PublicFunctions.php`, stable33 `lib/Command/ExApp/Update.php`
- nextcloud/android `UnifiedSearchViewModel.kt`, nextcloud/android-library `SearchResultEntry.kt`, nextcloud/ios `NCCollectionViewCommon+Search.swift`
- FFmpeg `tests/fate/aac.mak`, `mp3.mak`, `opus.mak`, `vorbis.mak`
- https://www.sqlite.org/fts5.html (Tokenizer, porter nur Englisch, trigram, C-API)
- PyPI JSON tantivy 0.26.2/0.27.0; npm @playwright/test 1.65.0
- Findling-Codebasis `C:/Users/Student/nextcloud-search` (php/lib, backend/src/findling/index und store, .github/workflows/deploy-harp.yml, backend/tests/test_lockstep_versions.py)
- Skeleton und Projektrepo (info.xml, release.yml, docker.yml), gh: app-certificate-requests PR #1409 (gemergt), #1417 (offen)
- Lokale Prüfung: SQLite 3.45.3 bedingter UPSERT mit Zeilenwert-Vergleich

### Secondary (MEDIUM confidence)
- https://ffmpeg.org/ffmpeg-formats.html (hash/streamhash: Standard s16-Konvertierung, SHA-256; `-c copy` nicht beschrieben)
- Projekt-Recherche `.planning/research/*.md`, SPIKE3-REPORT.md

### Tertiary (LOW confidence)
- [Playwright-Codecs, Diskussion](https://ray.run/discord-forum/threads/39515-video-codecs-in-browsers), [Wiki "chromium is not chrome"](https://github.com/feder-cr/invisible_playwright/wiki/chromium-is-not-chrome), [Chromium audio-video](https://chromium.org/audio-video)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (Findling-Pins, Registerprüfung, Wheels geprüft)
- Architecture: HIGH für Integrationsweg (Quelltext), MEDIUM für Index-Protokoll und Korrektur-Überlagerung (Entwurf, Tests in Phase 1 belegen ihn)
- Pitfalls: HIGH für CSRF/ViewOnly/CSP/Mobil (Quelltext), MEDIUM für Seek auf externen Speichern und Playwright-Codecs

**Research date:** 2026-11-06
**Valid until:** 2026-12-06 (Plattform stabil; Viewer-Bibliothek bewegt sich schnell, vor Phase 4 erneut prüfen)
