---
phase: 04-suchqualit-t-und-export
plan: 02
subsystem: php/search
tags: [SRCH-06, SRCH-04, filter, unified-search, oc_share]
requires: []
provides:
  - "Service/SearchFilters.php: Wertobjekt since/until/personUid/groupId, fromQuery(ISearchQuery), hasAny(), hasPerson(), matchesTime(File), sharedSubset(list<int>) mit einer share-Abfrage je Aufruf (Chunk 1000, PARAM_INT_ARRAY)"
  - "Search/Provider.php: getSupportedFilters = term, since, until, person; Filteranwendung in entries() nach Ausschluss- und Rechteprüfung; MAX_ROUNDS_FILTERED = 6"
affects: [04-14]
tech-stack:
  added: []
  patterns: ["Filter nur nach readableFile, nie davor: Antwort kann nur verwerfen, nie hinzufügen", "Zwei Durchgänge je Runde: bestätigen, eine Freigabe-Abfrage für neue Kandidaten, Einträge in Container-Reihenfolge"]
key-files:
  created:
    - php/lib/Service/SearchFilters.php
    - php/tests/Unit/SearchFiltersTest.php
  modified:
    - php/lib/Search/Provider.php
    - php/tests/Unit/ProviderTest.php
decisions:
  - "Die Freigabe-Antwort wird wie der Recheck je Datei und Suche gemerkt: eine zweite Runde fragt nur noch Dateien, die die erste Abfrage nicht beantwortet hat (höchstens eine Abfrage je Runde, PATTERNS 'Cache je Datei')"
  - "sharedSubset ohne Personenfilter stellt nichts in Frage: alle übergebenen ids gelten als bestanden, ohne Abfrage (defensiv, der Provider ruft es dann gar nicht)"
  - "DB-Fehler in sharedSubset ist fail-closed: leere Menge, der Filter verwirft alle Kandidaten der Runde statt einen ungeprüften zu zeigen (T-04-04)"
  - "Der SearchFilters-Konstruktor trägt zusätzlich den LoggerInterface, weil die geforderte Warnung bei DB-Fehlern sonst nicht möglich wäre (Plan nannte nur IDBConnection)"
metrics:
  duration: "ca. 30 min"
  completed: 2026-11-16
  tasks: 2
  files: 4
---

# Phase 4 Plan 02: Datums- und Personenfilter mit Files-Semantik Summary

Der Unified-Search-Provider meldet since, until und person; der Web-Client von NC 33 bis 35 lässt die Gruppe damit bei gesetztem Filter im Hauptteil (SRCH-06), und die Treffer sind nach mtime (beide Grenzen inklusiv, D-04-09) und nach der exakten Freigabe-Semantik der Files-Suche (uid_owner oder share_with bei share_type USER, Gruppe bei GROUP, D-04-10) gefiltert, immer erst NACH Ausschluss- und Rechteprüfung.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | SearchFilters-Dienst mit Files-Semantik | 8ffd8cf (RED), ac59404 (GREEN) | Service/SearchFilters.php, tests/Unit/SearchFiltersTest.php |
| 2 | Provider meldet und wendet die Filter nach der Rechteprüfung an | 9d9fab1 (RED), 450123a (GREEN) | Search/Provider.php, tests/Unit/ProviderTest.php |

## Ergebnis

- `SearchFilters::fromQuery` liest since/until nur als `\DateTimeImmutable` und die Person über `instanceof IUser` bzw. `instanceof IGroup` (nie über private Server-Klassen); ein Wert anderen Typs ist kein Filter.
- `matchesTime` vergleicht `getMTime() >= since` und `<= until`, Grenzsekunden-Test genau auf der Sekunde (999/1000/2000/2001).
- `sharedSubset` stellt je Aufruf genau eine Abfrage auf die Tabelle `share` (`file_source IN` als `PARAM_INT_ARRAY`, Chunk 1000, Dubletten dedupliziert), Bedingung wie `FilesSearchProvider`/`QuerySearchHelper::equipQueryForShares` (stable33 bis 35 identisch): `uid_owner = uid OR (share_with = uid AND share_type = 0)`, Gruppe `share_with = gid AND share_type = 1`. Folgen a bis c von D-04-10 im Docblock und im Test (Link-Freigabe zählt für den Eigentümer, nie geteilte Datei fällt heraus).
- Der Provider wendet die Filter in `entries()` in zwei Durchgängen je Runde an: erst die bestehende Bestätigung (Ausschluss, readableFile, dann matchesTime), dann eine Freigabe-Abfrage für die noch unbeantworteten bestätigten Kandidaten, dann die Einträge in Container-Reihenfolge. Cursor-Semantik (`$offset + $position + 1` hinter dem letzten GELIEFERTEN Vorschlag) unverändert.
- Eine ausgeschlossene oder nicht lesbare Datei erreicht SearchFilters nie (Test: nur die lesbare, nicht ausgeschlossene id steht in der Abfrage).
- Mit gesetztem Filter gelten bis zu `MAX_ROUNDS_FILTERED = 6` Runden (Test: Offsets 0 bis 100), `BUDGET_SECONDS = 2.5` bleibt die harte Grenze (Pitfall 4, T-04-06).
- SRCH-04 als Test festgehalten: eine Datei in einer Freigabe mit Attribut download=false (ISharedStorage-Double) liefert weiterhin einen Treffer; der Provider fragt die Storage nie nach der Sperre.
- Ohne Filter ist das Verhalten byte-gleich zu vorher: gleiche Container-Aufrufe, gleiche Cursor, keine share-Abfrage; alle bestehenden ProviderTest-Fälle unverändert gültig.
- SearchFiltersTest wertet die gebaute Bedingung unabhängig aus: der IQueryBuilder-Double gibt lesbare Bedingungen heraus, executeQuery löst die gebundenen Parameter auf und wendet sie auf eine eigene share-Tabelle an (Gegenprobe mit unabhängigem Muster, kein Spiegel der Implementierung); zusätzlich werden Abfragen gezählt und die Parameter (uid, share_type 0 bzw. 1, genau ein PARAM_INT_ARRAY) geprüft.
- Gates lokal: test_php_gates.py, test_trilingual.py, test_public_texts.py zusammen 91 bestanden; Plan-Greps (PARAM_INT_ARRAY, TYPE_GROUP, instanceof IGroup, BUILTIN_SINCE/UNTIL/PERSON, MAX_ROUNDS_FILTERED, kein "Only the term in phase 1", kein privates OC-Namespace-Präfix) alle erfüllt.
- PHPUnit läuft erst in CI (lokal kein PHP): Lauf beim nächsten Owner-freigegebenen Push, wie im Plan vorgesehen.

## Bekannte Grenzen

1. **Sichtbarkeits-Beweis im echten Client:** Dass die Gruppe bei gesetztem Filter im Hauptteil bleibt, belegt erst der Playwright-Lauf S6 in Plan 04-14; hier ist die Voraussetzung (vier gemeldete Filter) gebaut und getestet.
2. **Dünne Seiten trotz sechs Runden:** Ein sehr strenger Filter kann eine Seite weiter unterfüllen; das Zeitbudget bleibt bewusst bei 2,5 s (Pitfall 4, dokumentiertes Verhalten).
3. **Gruppenfilter zählt nur GROUP-Zeilen:** Wie bei Files zählt für eine Gruppe nur share_with = gid bei share_type GROUP, nicht der Eigentümer (D-04-10 wörtlich).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Fehlende kritische Funktionalität] Logger im SearchFilters-Konstruktor**
- **Found during:** Task 1
- **Issue:** Der Plan verlangt bei DB-Fehlern `logger->warning` nur mit `class`, nennt in der Konstruktor-Signatur aber nur `IDBConnection`.
- **Fix:** `LoggerInterface` als weiterer readonly-Parameter; `fromQuery` reicht ihn durch.
- **Files modified:** php/lib/Service/SearchFilters.php
- **Commit:** ac59404

Sonst keine Abweichungen: der Zwei-Durchgänge-Umbau je Runde, MAX_ROUNDS_FILTERED = 6 und die unveränderte Cursor-Berechnung folgen wörtlich dem Plan.

## TDD Gate Compliance

RED 8ffd8cf und 9d9fab1, danach GREEN ac59404 und 450123a. Ein REFACTOR-Commit war nicht nötig. Die RED-Läufe konnten lokal nicht ausgeführt werden (kein PHP auf der Maschine, PHPUnit läuft in CI); die Tests wurden vor der Implementierung geschrieben und committet.

## Requirements

SRCH-06 und SRCH-04 bleiben in REQUIREMENTS.md offen: SRCH-06 braucht noch den Sichtbarkeits-Beleg im echten Web-Client (Plan 04-14, S6), SRCH-04 noch die Export-Seite ("Export nein" entsteht erst mit den Export-Routen späterer Pläne).

## Threat Flags

Keine neue Angriffsfläche über das Threat Model des Plans hinaus.
- T-04-04: sharedSubset sieht nur fileIds nach readableFile und Ausschluss; die Antwort wirkt nur als Ausschluss, DB-Fehler fail-closed (Tests: Ausschluss/Unlesbar nie in der Abfrage, Fehler = leere Menge).
- T-04-05: nur IQueryBuilder mit createNamedParameter und PARAM_INT_ARRAY, keine String-Verkettung (Test prüft die Parameterbindung).
- T-04-06: MAX_ROUNDS_FILTERED = 6, BUDGET_SECONDS 2,5 bleibt, eine Abfrage je Runde, Chunk 1000.
- T-04-07: kein uid, gid oder Datum in Logs; die eine Warnung trägt nur `class` (Test: Log ohne Namen).

## Self-Check: PASSED

- FOUND: php/lib/Service/SearchFilters.php
- FOUND: php/tests/Unit/SearchFiltersTest.php
- FOUND: php/lib/Search/Provider.php (geändert)
- FOUND: php/tests/Unit/ProviderTest.php (geändert)
- FOUND: Commits 8ffd8cf, ac59404, 9d9fab1, 450123a
