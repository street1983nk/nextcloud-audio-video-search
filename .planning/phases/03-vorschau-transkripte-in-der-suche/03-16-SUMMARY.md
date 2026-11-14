---
phase: 03-vorschau-transkripte-in-der-suche
plan: 16
subsystem: php-abspielseite
tags: [php, leck-regel, abspielseite, zustaende]
requires: ["03-12", "03-14"]
provides:
  - "ExAppService::excerpt mit stage, partial, pendingHere, reason, limitHours und Typprüfung"
  - "PageController: Zustände A1 bis A13, excerptNote, excerptHours, REASON_STATES"
affects: ["03-16b", "03-20"]
tech-stack:
  added: []
  patterns: ["Positivliste für Grundcodes", "Ausschluss vor Container-Frage", "Byte-Vergleich des Ausschnitt-Blocks"]
key-files:
  created: []
  modified:
    - php/lib/Service/ExAppService.php
    - php/lib/Controller/PageController.php
    - php/tests/Unit/ExAppServiceTest.php
    - php/tests/Unit/PlayControllerTest.php
decisions:
  - "partial und pendingHere: fehlend = false, null oder anderer Typ = ungültige Antwort (A12); limitHours fehlend oder null = keine Grenze, sonst int 1 bis 24"
  - "Unbekannter stage-Text wird null (Vorschau), wie bei Suchtreffern (HIT_STAGES); nur ein Nicht-Text macht die Antwort ungültig"
  - "Text vor Grund: disk_full mit Teiltext ergibt ok mit Teil-Hinweis (A2), A13 nur ohne Text"
  - "too_long ohne limitHours wird skipped_other (A11), weil T9 eine Zahl braucht"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-14
---

# Phase 3 Plan 16: Zustände der Abspielseite unter der Leck-Regel Summary

PageController leitet aus der geprüften `/excerpt`-Antwort genau einen Zustand A1 bis A13 ab (dazu `excerptNote` preview/partial und `excerptHours` für too_long), Gründe nur über die Positivliste `REASON_STATES`, Ausschluss weiter vor jeder Container-Frage.

## Was gebaut wurde

- **ExAppService::excerpt**: Rückgabe `{known, excerpt, stage, partial, pendingHere, reason, limitHours}`. `known: false` ergibt immer die feste Unbekannt-Form, alle mitgeschickten Felder werden verworfen. Mit `known: true` Typprüfung je Feld, ein Fehler ergibt null (A12).
- **PageController**: Konstanten `EXCERPT_PENDING_HERE`, `EXCERPT_NO_SPEECH`, `EXCERPT_SKIPPED_DAMAGED`, `EXCERPT_SKIPPED_PROTECTED`, `EXCERPT_UNSUPPORTED_LANGUAGE`, `EXCERPT_TOO_LONG`, `EXCERPT_DISK_FULL`, `EXCERPT_SKIPPED_OTHER`, `REASON_STATES`, `NOTE_NONE/PREVIEW/PARTIAL`. `excerpt()` liefert `array{state, text, note, hours}`; Reihenfolge: Ausschluss (Fehler = ausgeschlossen), searchAllowed, Container, null = unavailable, known false = none, Text = ok (partial vor preview, stage != final = preview), pendingHere, Grund über Positivliste, sonst none. Template-Parameter neu: `excerptNote`, `excerptHours` (auch auf der 404-Seite, leer/0).
- **Tests (phpunit, laufen in CI)**:
  - PlayControllerTest: Datenanbieter mit 22 Fällen über A1 bis A13 inkl. Kanten (sample = Vorschau, partial schlägt final, disk_full mit Teiltext, Leertext, engine_failed und xyz = A11, too_long ohne Grenze = A11, limitHours bei anderem Grund ignoriert, Singular 1 und Plural 12); Positivliste geschlossen und eindeutig; Leck-Fälle (ausgeschlossener Nutzer, ausgeschlossene Datei, scheiternde Ausschlussfrage) mit Grund-Datei `no_speech`, gleich der Antwort für eine unbekannte Datei, `expects(self::never())->method('excerpt')`; Byte-Vergleich des gerenderten Ausschnitt-Blocks (TemplateResponse mit RENDER_AS_BLANK, Abschnitt `section.avs-excerpt`) ausgeschlossen gegen unbekannt, mit Positivkontrolle (lesbarer Text ergibt anderen Block); unbekannter Grund "xyz" weder in den Parametern noch im HTML. Die drei bestehenden Ausschluss-Tests haben jetzt ebenfalls `never()`.
  - ExAppServiceTest: neue Form, known false verwirft alles, Standardwerte, stage geschlossene Liste, 19 Typfehler-Fälle je Feld mit Positivkontrolle, limitHours 1/12/24 bleiben.

## Verifikation

- `uv run pytest tests/test_php_gates.py`: 43 passed; Plan-Greps `EXCERPT_PENDING_HERE`, `REASON_STATES` gefunden; `grep -n "reason" php/templates/play.php`: keine Ausgabe.
- Positivkontrollen (Skript im Scratch-Ordner, Datei danach wiederhergestellt): `searchAllowed()` vor die Ausschlussfrage gesetzt = Gate rot; Gedankenstrich im Controller = Gate rot; Klammerbilanz-Prüfung der vier Dateien grün, gegen eine absichtlich entfernte Klammer rot. Keine U+2013/U+2014, keine Emojis, LF-Zeilenenden.
- Python volle Suite: 1713 passed; ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture rc 0.
- phpunit selbst ist lokal nicht lauffähig (kein PHP); läuft in CI (Plan 03-20).

## Deviations from Plan

None - plan executed exactly as written. Präzisierungen, wo der Plan offen war, stehen unter decisions (null bei partial/pendingHere, unbekannte stage, Text vor Grund).

## Known Stubs

- `php/templates/play.php` kennt die neuen Zustände noch nicht: `pending_here`, `no_speech`, `skipped_*`, `unsupported_language`, `too_long`, `disk_full` fallen bis Plan 03-16b in den else-Zweig ("Der Ausschnitt ist gerade nicht abrufbar"), `excerptNote` wird noch nicht gezeigt. Gewollt laut Plan (Template, CSS, Kataloge in 03-16b); 03-16b muss vor einem Release folgen. A5 (none) und die Leck-Gleichheit sind davon nicht betroffen.

## Offene Punkte

- Der Byte-Vergleich rendert über `TemplateResponse::render()` mit RENDER_AS_BLANK im installierten Server der CI; die l10n ist die des Servers (keine eigene Test-l10n injiziert), beide Seiten nutzen dieselbe. Lokal nicht ausführbar; erster echter Lauf in CI (03-20). Falls `\OCP\Util::addScript` im Unit-Kontext stört, dort nachziehen.

## Threat Flags

Keine neue Oberfläche. T-03-54 (Ausschluss zuerst, never(), Byte-Vergleich), T-03-55 (REASON_STATES, Rohcode nie im Template, Typprüfung), T-03-56 (nur limitHours der Instanz, 1 bis 24) umgesetzt.

## Commits

- f4ca711 feat(03-16): Zustände der Abspielseite mit Gründen unter der Leck-Regel

## Self-Check: PASSED
