---
phase: 03-vorschau-transkripte-in-der-suche
plan: 12
subsystem: php-search
tags: [unified-search, paginierung, cursor, ueberabruf, rechtepruefung, vorlaeufig, l10n]
requires:
  - "03-08: POST /search mit offset, Antwort {hits[stage], nextOffset, hasMore}"
provides:
  - "ExAppService::search(uid, term, limit, offset = 0): ?array{hits, nextOffset, hasMore}"
  - "ExAppService::MAX_OFFSET = 1200, HIT_STAGES = [preview, final, sample]"
  - "Provider: getLimit (MAX_LIMIT 25), getCursor (MAX_CONTAINER_OFFSET 1200), MAX_ROUNDS 3, OVERFETCH 4, Prüf-Cache je fileId, SearchResult::paginated"
  - "l10n Preliminary: Vorläufig / Preliminary / Provisoire"
affects:
  - "03-20: phpunit in CI muss ProviderTest und ExAppServiceTest grün zeigen"
tech-stack:
  added: []
  patterns:
    - "Findling SearchService::run: Runden mit Überabruf, Offset-Decke vor dem Aufruf, leere Seite nur bei hasMore false das Ende"
    - "Cursor hinter dem letzten GELIEFERTEN Vorschlag"
key-files:
  created: []
  modified:
    - php/lib/Service/ExAppService.php
    - php/lib/Search/Provider.php
    - php/tests/Unit/ExAppServiceTest.php
    - php/tests/Unit/ProviderTest.php
    - php/l10n/de.json
    - php/l10n/de.js
    - php/l10n/de_DE.json
    - php/l10n/de_DE.js
    - php/l10n/en.json
    - php/l10n/en.js
    - php/l10n/fr.json
    - php/l10n/fr.js
decisions:
  - "Volle Seite mit dem allerletzten Vorschlag des Containers (Position am Seitenende und hasMore false) ist complete, nicht paginated: kein leerer Folgeabruf für Cursor-Clients"
  - "stage 'sample' ohne sample-Flag wird preview (Widerspruch des Containers, kein Testtreffer ohne Flag)"
  - "Rundenschleife bleibt in Provider::entries, damit die Gates Regel 14 (isExcludedFile vor ->entry() unverändert greifen"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 12
---

# Phase 3 Plan 12: PHP-Provider mit limit, Cursor, Auffüllen und "Vorläufig" Summary

Der Suchprovider liefert jetzt genau `limit` geprüfte Stellen (höchstens 25) aus bis zu drei Runden mit vierfachem Überabruf, prüft Ausschluss und Leserecht je fileId einmal pro Anfrage, antwortet `SearchResult::paginated` mit dem Container-Offset hinter dem letzten gelieferten Vorschlag und kennzeichnet Vorschau-Stellen mit "Vorläufig".

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | d3a0625 | feat(03-12): Container-Suche mit Offset und Stufe |
| 2 | 7c480c1 | feat(03-12): mehrere Stellen je Datei mit Mehr laden und Kennzeichen Vorläufig |

## Was gebaut wurde

- **ExAppService::search** sendet `{term, limit 1..50, offset 0..1200}`; die Antwort braucht `hits` (Liste), `nextOffset` (int >= 0) und `hasMore` (bool), sonst null. Leerer Begriff: `{hits: [], nextOffset: offset, hasMore: false}` ohne Aufruf.
- **filterHits** prüft zusätzlich `stage`: fehlend, null oder unbekannt wird `preview`; nicht-String verwirft den Treffer (gezählt im bestehenden Warn-Log ohne Inhalt); `sample: true` erzwingt `sample`.
- **Provider::search**: `reload`, Nutzer-Ausschluss und Drift-Prüfung unverändert vor jedem Containeraufruf; dann `entries($uid, $term, $limit, $offset)`.
- **Provider::entries**: Runden (MAX_ROUNDS 3, je `limit * OVERFETCH` Vorschläge, Budget 2,5 s, Offset-Decke vor dem Aufruf), Prüf-Cache `array<int, ?File>` (isExcludedFile, dann readableFile unter actAs, je fileId einmal), Ende bei genau `limit` Einträgen mit Cursor `offset + position + 1`; leere Seite nur bei `hasMore false` das Ende; null in einer späteren Runde ergibt complete mit dem Bisherigen.
- **Untertitel**: `Zeit · Preliminary · Ausschnitt` (preview, unbekannt), `Zeit · Test result · Ausschnitt` (Probe, nie beides), `Zeit · Ausschnitt` (final), ohne Trenner am Ende bei leerem Ausschnitt.
- **startOffset**: int > 0 oder Ziffern-String, sonst 0; gedeckelt auf 1200 (überlange Ziffernfolgen ohne int-Überlauf direkt auf die Decke).

## Tests

- phpunit (läuft erst in CI, Plan 03-20): ExAppServiceTest neu: gültige Seite, offset im Körper (inkl. Decke 1200 und negativ auf 0), 5 Fälle ohne gültiges Paging ergeben null, unbekannte/fehlende Stufe wird preview, Stufe int/Array verwirft. Bestehende Fälle auf die neue Rückgabeform umgestellt.
- ProviderTest neu (a bis h und mehr): limit 5 bei 12 Stellen (5 Einträge, Cursor 5, ein Aufruf mit 20), limit 10 präfixgleich, Auffüllen über zwei geschlossene Dateien (Cursor 7, Folgeseite beginnt mit der ersten nicht gezeigten), drei Stellen einer Datei: ein Lookup, eine Ausschlussfrage, geschlossene Datei mit drei Stellen ebenso, letzte Seite complete, volle Seite mit letztem Vorschlag complete, Probe ohne "Preliminary", preview vor dem Ausschnitt, final ohne Kennzeichen, leerer Ausschnitt "1:23 · Preliminary", Cursor "17"/17/"9999"/20 Ziffern/"abc"/"-3", limit 40 auf 25 und 0 auf 1, Störung in Runde 2, höchstens drei Runden. Der Container-Double schneidet eine feste Folge wie der Container (03-08).
- Lokal: test_php_gates + test_trilingual + test_public_texts 71 passed; volle Suite 1559 passed; ruff check, ruff format --check (100 Dateien), pyright 0 Fehler, vulture rc 0.
- Positivkontrollen (je auf Kopie zurückgesetzt): "Preliminary" aus fr.json entfernt: 3 rot (Katalog, js-Zwilling); isExcludedFile im Provider entfernt: 2 rot (Regel 14); unbekannter l10n-Schlüssel im Provider: 1 rot.
- Klammer-Bilanz der vier PHP-Dateien über `php_code` der Gates: 0/0/0 (kein PHP lokal, Syntax erst in CI).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Korrektheit] Volle Seite am Ende der Folge ist complete**
- **Found during:** Task 2
- **Issue:** Plan setzt bei `count === limit` immer hasMore true; liegt der letzte gelieferte Vorschlag am Ende der Folge (hasMore false), bekäme ein Cursor-Client eine leere Folgeseite.
- **Fix:** `$more = $position < $last || $page['hasMore']`; Test `testAFullPageWithTheVeryLastProposalIsComplete`. Web-Dialog unberührt (er zählt Einträge).
- **Commit:** 7c480c1

**2. [Rule 2 - Korrektheit] stage 'sample' ohne sample-Flag wird preview**
- **Found during:** Task 1
- **Issue:** Plan lässt 'sample' als Stufe stehen; ohne Flag würde ein Treffer an der Debug-Schranke vorbei als "Testtreffer" erscheinen.
- **Fix:** nur `sample: true` ergibt Stufe sample; Test in `testAMissingOrUnknownStageIsAPreview`.
- **Commit:** d3a0625

**3. [Rule 3 - Struktur] Rundenschleife in `entries` statt in `search`**
- **Issue:** Die Gates Regel 14 verlangen `isExcludedFile` vor `->entry(` in `Provider::entries`.
- **Fix:** `entries` enthält Runden, Cache und Prüfung; Gates unverändert und grün, Positivkontrolle rot bei entfernter Prüfung.

**4. Zusätzlich:** Schutz gegen Container ohne Fortschritt (`nextOffset <= offset` beendet die Runden); ExAppService deckelt offset selbst auf 0..1200.

## Threat Flags

Keine neue Angriffsfläche. T-03-39 bis T-03-42 umgesetzt (Cache nur je Anfrage; Decken 1200/3/2,5 s/25; Stufen-Positivliste; Ausschnitt weiter über plainText und shorten). Logs: nur round, checked, delivered, fileId (wie bisher); kein Begriff, kein Ausschnitt, kein Pfad.

## Offene Punkte

- phpunit-Lauf in CI (Plan 03-20) steht aus; lokal kein PHP.
- Playwright-Abnahme S2 ("Mehr laden", keine Dublette) gehört zur UI-Abnahme der Phase.

## Self-Check: PASSED

- d3a0625, 7c480c1 im Log vorhanden; alle 12 Dateien geändert und committet.
