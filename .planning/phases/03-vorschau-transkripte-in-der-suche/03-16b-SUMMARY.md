---
phase: 03-vorschau-transkripte-in-der-suche
plan: 16b
subsystem: php-abspielseite
tags: [php, template, css, l10n, abspielseite, leck-regel]
requires: ["03-01", "03-16"]
provides:
  - "play.php: p.avs-excerpt__note (T2/T3) nach dem Ausschnitt, Hinweis-Sätze für A4 und A6 bis A13"
  - "play.css: .avs-excerpt__note nach UI-SPEC"
  - "php/l10n: T2 bis T12 in de, de_DE, en, fr, T9 als Plural-Schlüssel"
affects: ["03-18", "03-20", "03-21"]
tech-stack:
  added: []
  patterns: ["Feste Hinweis-Tabelle je Zustandsname, kein Wert aus dem Backend im HTML", "Plural-Schlüssel _Singular_::_Plural_ mit Formenzahl aus nplurals"]
key-files:
  created: []
  modified:
    - php/templates/play.php
    - php/css/play.css
    - php/l10n/de.json
    - php/l10n/de.js
    - php/l10n/de_DE.json
    - php/l10n/de_DE.js
    - php/l10n/en.json
    - php/l10n/en.js
    - php/l10n/fr.json
    - php/l10n/fr.js
    - backend/tests/test_ui_assets.py
    - backend/tests/test_trilingual.py
    - backend/tests/test_public_texts.py
decisions:
  - "FR-Plural mit drei Formen [Singular, Plural, Plural], weil der Katalog nplurals=3 trägt (Nextcloud-Regel mit Millionen-Form)"
  - "too_long ohne Stundenzahl (excerptHours < 1) zeigt im Template T11 statt eines Satzes ohne Zahl; der Controller liefert das schon als skipped_other, das Template bleibt für sich sicher"
  - "Hinweise über eine feste Tabelle $excerptHints mit den Zustandsnamen des Controllers; isset auf diese Tabelle, sonst Bestandszweig unavailable"
metrics:
  duration: "ca. 50 min"
  completed: 2026-11-14
---

# Phase 3 Plan 16b: Hinweise und Gründe auf der Abspielseite Summary

Die Abspielseite zeigt die in 03-16 abgeleiteten Zustände: Vorschau- bzw. Teil-Hinweis als gedämpfte Notiz unter dem Ausschnitt, für A4 und A6 bis A13 je einen festen Satz im grauen Ausschnitt-Block (überlang mit Stundenzahl im Plural und T10 im selben Absatz), alle Texte wörtlich aus 03-UI-SPEC.md in DE, EN und FR.

## Was gebaut wurde

- **play.php**: `excerptNote` (string, sonst '') und `excerptHours` (int, sonst 0) defensiv gelesen. Im ok-Zweig nach dem `blockquote`: `partial` ergibt T3, `preview` ergibt T2, sonst nichts (A3), nie beide. Neue Zweige über `$excerptHints` (pending_here T4, no_speech T5, skipped_damaged T6, skipped_protected T7, unsupported_language T8, too_long T9 per `$l->n` plus Leerzeichen plus T10, skipped_other T11, disk_full T12). Ausgabe nur mit `p()`; gedruckt wird der Wert der festen Tabelle, nie der Zustandsname. Zweig `none` (A5) und `unavailable` (A12) zeichengleich, `git diff` zeigt im Template keine einzige entfernte Zeile.
- **play.css**: `.avs-excerpt__note` mit genau den fünf Eigenschaften der UI-SPEC; `.avs-excerpt__hint` hatte `overflow-wrap: anywhere` schon.
- **Kataloge**: 11 neue Schlüssel je Sprache (T2 bis T8, T9 Plural, T10 bis T12), de und de_DE byte-gleich, `.js` mit `scripts/l10n_js.py` erzeugt (`--check` grün).
- **Tests**:
  - test_ui_assets.py: Regel `.avs-excerpt__note` exakt die fünf Deklarationen (Helfer `css_rule` mit Selbsttest), `overflow-wrap: anywhere` auf hint und note, beide note-Absätze nach dem `blockquote`, kein `p($excerptState)`, A5-Zeilen wörtlich.
  - test_trilingual.py: alle Kataloggates lesen jetzt auch Pluralformen (Listen-Werte); neue Prüfung `plural_findings` (Formenzahl = nplurals der Sprache, jede Form mit `%n`, Nicht-Plural-Schlüssel nur Text); `$l->n(...)`-Aufrufe in PHP werden als Schlüssel `_S_::_P_` gefunden und gegen die Kataloge geprüft; Stichproben T2, T9 (de, fr), T10 fr; Selbsttests für jede neue Regel.
  - test_public_texts.py: Umlaut-Gate liest Pluralformen mit (vorher TypeError), Selbsttest mit Ersatzschreibung in der zweiten Form.

## Verifikation

- Plan-Verify: `pytest test_ui_assets test_trilingual test_public_texts test_php_gates` 100 passed (nach Ergänzungen); Greps T2 de und fr gefunden; Gedankenstrich-Prüfung `[]`, rc 0; `grep -c avs-excerpt__note play.php` = 2.
- Gegenprobe gegen die Tabelle in 03-UI-SPEC.md (Skript parst die Zeilen `| T1 |` bis `| T12 |`, nicht den eigenen Code): 48 Werte (11 Schlüssel x 4 Kataloge + Plural x 4) gleich, 0 Fehler; alle EN-Texte T2 bis T12 stehen im Template. Positivkontrolle: ein entfernter Punkt in fr T3 ergibt 1 Fehler.
- Positivkontrollen der Gates (Mutation, Lauf, Originalbytes zurück, danach `git diff --stat` unverändert): Zusatzeigenschaft in der Notiz-Regel, Hexfarbe, Notiz vor dem blockquote, geänderte A5-Zeile, `p($excerptState)`, Template-Text ohne Katalog, Plural-Schlüssel ohne Katalog, FR mit nur zwei Pluralformen, Ersatzschreibung in einer DE-Pluralform: alle 9 rot.
- Umlaut-Audit: alle neuen DE-Werte mit echten Umlauten (Vorläufiges, spätere, enthält, beschädigt, unvollständig, geschützt, ungeschützte, unterstützt, Französisch, länger, später), keine ae/oe/ue-Ersatzschreibung, kein U+2013/U+2014, kein Ausrufezeichen, keine Emojis; FR-Werte ohne : ; ? ! (kein U+00A0 nötig).
- Python-Gates: ruff check grün, ruff format --check grün (107 Dateien), vulture rc 0, pyright (latest) auf den drei geänderten Testdateien 0 Fehler.
- Volle Suite: 1752 passed, 1 failed (`tests/test_engine_child.py::test_the_child_is_replaced_after_max_chunks`, Plan 03-10, paralleler Executor, nicht berührt).
- phpunit lokal nicht lauffähig (kein PHP); Template-Render und Byte-Vergleich A5 laufen in CI (03-20), Sichtabnahme in 03-21.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kataloggates scheiterten an Plural-Werten**
- **Found during:** Task 1
- **Issue:** test_trilingual (Strich/Emoji, FR-Abstand, Platzhalter, EN Schlüssel = Wert) und test_public_texts (Umlaut-Gate) setzten Textwerte voraus; der Plural-Schlüssel mit Listen-Wert ergab TypeError bzw. falsches Rot. Außerdem fand die Prüfung "jeder übersetzte Text steht im Katalog" `$l->n()` nicht.
- **Fix:** Helfer `forms()`/`catalogue_text()`, alle Regeln über jede Form; neue Regel `plural_findings`; `PHP_N_CALL` in `source_strings`; jeweils mit Selbsttest.
- **Files modified:** backend/tests/test_trilingual.py, backend/tests/test_public_texts.py (nicht in files_modified des Plans)
- **Commit:** c2c943d

**2. [Rule 2 - Robustheit] too_long ohne Stundenzahl**
- Das Template zeigt bei `too_long` mit `excerptHours < 1` T11 statt eines Satzes ohne Zahl. Der Controller liefert diesen Fall laut 03-16 schon als skipped_other; die Absicherung ändert am Normalfall nichts.

## Known Stubs

Keine. Der in 03-16 gemeldete Stub (neue Zustände fielen in den unavailable-Zweig, excerptNote ungenutzt) ist damit aufgelöst.

## Offene Punkte

- Kontrast `.avs-excerpt__note` (13 px, `--color-text-maxcontrast` auf `--color-background-hover`) wird erst im Playwright-Lauf gemessen (P1, 03-21); unter 4,5:1 wäre laut UI-SPEC `--color-main-text` der Fallback.
- pyright über das ganze Backend meldet 1 Fehler in `tests/engine_fakes.py:53` (`os.nice`), Datei aus Plan 03-10 (paralleler Executor), nicht berührt.

## Threat Flags

Keine neue Oberfläche. T-03-72: jeder Text über `$l->t`/`$l->n` und `p()`, excerptNote/excerptHours typgeprüft, gedruckt nur Werte der festen Tabelle. T-03-73: A5-Zweig zeichengleich (keine entfernte Zeile im Diff, Test hält die Zeilen wörtlich).

## Commits

- c2c943d feat(03-16): Hinweise und Gründe auf der Abspielseite in DE, EN und FR

## Self-Check: PASSED
