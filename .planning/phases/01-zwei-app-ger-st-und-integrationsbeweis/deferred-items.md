# Phase 1: Zurückgestellte Punkte

## Aus Plan 01-01

- ERLEDIGT in 01-10 (zwei Archive, zwei Pins, Backend-Pin wartet auf PR 1417): `.github/workflows/release.yml`, `.github/workflows/store-submit.yml` und `scripts/release/store-archive.sh` lesen noch `appinfo/`, `l10n/`, `img/` an der Repo-Wurzel und `APP_ID: audio_video_search` mit Image `ghcr.io/street1983nk/audio_video_search`. Nach dem Umbau auf `backend/` und `php/` sind sie bis zum Zwei-Archiv-Umbau nicht lauffähig. Zuständig: Plan 01-10 (laut files_modified dort).
- ERLEDIGT in 01-13: `CONTRIBUTING.md` nannte noch `src/audio_video_search/` und `--cov=src/audio_video_search`; `SECURITY.md` und die README-Badges nennen nur die PHP-App-ID. Zuständig: Doku-Plan 01-13.
- `php/tests/Unit/` ist leer (nur `.gitkeep`); `php.yml` (phpunit-Job, `failOnEmptyTestSuite`, `MINIMUM_TESTS: 1`) wird erst grün, wenn Plan 01-03 die ersten PHP-Tests und `SampleCommand`/`Search\Provider` liefert.

## Aus Plan 01-05

- ERLEDIGT in 01-09 (Commit 37f1ad0, Beweis im Container erst mit dem CI-Lauf in Plan 11): Das Image installierte das Debian-Paket `wngerman` noch nicht (Findling `Dockerfile` Z. 174 bis 211: `wngerman=20161207-15`, `test -s /usr/share/dict/ngerman`, Lizenztext GPL-2+ ins Image). Ohne die Liste zerlegt die deutsche Kette keine Komposita ("frist" findet "Kündigungsfrist" nicht), Stemming läuft. Die Analyzer-Marke trägt den Digest der Liste, also baut der Index nach dem Nachrüsten einmal aus SQLite neu. Zuständig: Plan, der das Dockerfile anfasst (Container-Build in CI, lokal kein Docker).
- `SearchIndex.reconcile` liest die Schlüssel des Index über eine Terms-Aggregation über alle Dokumente; für Phase 1 klein, bei großen Beständen in Phase 6 (TRANS-04, Lasttest) messen.
- Store und Index teilen sich eine SQLite-Verbindung; alle Routen und der Start-Abgleich laufen unter einer Sperre (`api.Services.lock`). Ein langer Neuaufbau beim Start blockiert die Suche bis zum Ende (PHP fällt nach 1,5 s still auf null). Phase 6 misst das.

## Aus Plan 01-09

- ERLEDIGT in 01-13 (README DE/EN/FR, Abschnitt Lizenz): THIRD-PARTY-/REUSE-Hinweis auf die Wortliste wngerman (GPL-2+, Lizenztext liegt im Image unter /usr/local/share/audio_video_search_backend/COPYING.wngerman) fehlt in der Repo-Doku. Zuständig: Doku-Plan 01-13.
- Playwright-Specs sind nur per `--list` geprüft (lokal kein TypeScript-Compiler, kein Browser, keine Instanz). Selektoren der Unified Search (Kernweg) und der Login-Weg über `/index.php/login` sind gegen keine echte Instanz gelaufen. Zuständig: Plan 01-11 (erster CI-Lauf).

## Aus Plan 01-10

- `BACKEND_CERT_PUBKEY_SHA256` in `release.yml` steht auf `pending-certificate`, bis app-certificate-requests PR 1417 gemergt ist. Danach: Pin aus dem Zertifikat eintragen (der öffentliche Schlüssel der lokalen CSR ergibt `326dcfa967425902b21160e1af447bbca769c9aa17d73395e29cfff686ba1d80`, gegen das ausgestellte Zertifikat gegenprüfen) und das Secret `BACKEND_PRIVATE_KEY` anlegen (Owner).
- Upgrade-Job, Drift-Schritte und `ci/admin-state.sh` sind nur per Gate und `bash -n`/shellcheck geprüft; der echte Lauf (HaRP, `app_api:app:update`, Volume, Playwright `@drift/@patch/@missing`) ist Plan 01-11. Fällt `app_api:app:update` dort wegen des Volumes rot (Annahme A5), auf unregister/register ohne Datenflag zurückfallen und als Befund festhalten.
