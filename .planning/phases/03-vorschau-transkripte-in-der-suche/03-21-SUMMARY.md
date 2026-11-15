---
phase: 03-vorschau-transkripte-in-der-suche
plan: 21
subsystem: ui, abnahme
tags: [owner-abnahme, playwright, screenshots, kontrast, umlaut-audit]
requires: ["03-20"]
provides:
  - "Gemeinsame UI-Abnahme der Phase 3 durch den Owner am 15.11.2026 auf Basis der Playwright-Screenshots des gruenen Laufs 43673521607 (SHA 4c972ea): Suche S1 bis S5 und Abspielseite P1 bis P13 abgenommen"
  - "Kontrast-Gate >= 4,5:1 und Umlaut-Audit ohne Befund belegt"
affects: [verify-work-3]
key-files:
  created:
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-21-SUMMARY.md
  modified: []
decisions:
  - "Owner akzeptiert die vier dokumentierten Abweichungen (EN-Suchmatrix, Kontrastwerte nur als Gate, P12 als Discovery-HTML, P13 ohne CI-Bild)"
metrics:
  duration: "ca. 45 min (Artefakte, Pruefliste, Audit, Sichtung, Owner-Abnahme)"
  completed: 2026-11-15
  tasks: 2
  files: 1
---

# Phase 3 Plan 21: Gemeinsame UI-Abnahme Summary

Der Owner hat am 15.11.2026 die Phase-3-Oberfläche an den Playwright-Screenshots des grünen Laufs abgenommen ("Ich habe mir die Bilder angeschaut und es passt"): Suche S1 bis S5 und Abspielseite P1 bis P13 nach dem Prüfvertrag der 03-UI-SPEC, Kontrast-Gate und Umlaut-Audit ohne Befund. Vier Abweichungen wurden offen benannt und akzeptiert.

## Grundlage

- Bilder: Artefakte `playwright-stable33-ubuntu-24.04`, `playwright-stable34-ubuntu-24.04`, `playwright-stable35-ubuntu-24.04` des Deploy-through-HaRP-Laufs [43673521607](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43673521607) für SHA `4c972ea` (03-20), je Bein 190 Screenshots, Download in den Session-Scratchpad (`ui-abnahme-av/`), kein Docker, kein Browser.
- Vollmatrix NC 33 und 35, NC 34 als Stichprobe (Artefakt vollständig vorhanden); Sichtung der Kernpunkte an stable35, Owner-Durchsicht per Explorer über den ganzen Ordner.

## Prüfliste und Ergebnis (alle abgenommen)

| Punkt | Beleg | Ergebnis |
|---|---|---|
| S1 drei Stellen | `search-s1-*` 6 Bilder: genau 3 Zeilen viele-stellen.ogg (0:06/0:36/1:06), Reihenfolge Zeit · Kennzeichen · Ausschnitt, Trenner U+00B7 | PASS |
| S2 Mehr laden | `search-s2-w1280-*`: Seite 2 bringt die 4. Stelle 1:36, keine Dublette (resourceUrl-Vergleich im Test) | PASS |
| S3 langer Ausschnitt 375 px | `search-s3-w375-*`: Kennzeichen sichtbar, Kürzung nur am Ausschnitt | PASS |
| S4 Testtreffer | `search-s4-w1280-light`: "Test result" ohne Vorschau-Kennzeichen, nie zwei Kennzeichen; echter Treffer mit Kennzeichen über S1 | PASS |
| S5 Datei mit Grund | `search-s5-w1280-light`: stille Datei erscheint nicht (leeres Ergebnis für alice, Positivkontrolle im Test) | PASS |
| P1 Vorschau-Hinweis | `play-p1-*` 6 + Hochkontrast: Hinweis klein und gedämpft NACH dem Ausschnitt, kein Banner | PASS |
| P2 Teiltranskript | `play-p2-*` 6 Bilder, T3 statt T2 | PASS |
| P3/P4 | `play-p3-*`, `play-p4-*` je Matrix | PASS |
| P5 bis P8 | je Vertragsmatrix inkl. FR 375 bei P6/P7; P6 zeigt Format-Banner und Hinweis gleichzeitig (gewollt) | PASS |
| P9 überlang | `play-p9-*` + `play-p9-singular-*`: "12 hours" Plural, "1 hour" Singular, Admin-Satz im selben Absatz | PASS |
| P10 anderer Grund | `play-p10-w1280-light`, kein roher Code im DOM (Assertion) | PASS |
| P11 Leck-Probe | `play-p11-w1280-light` deckungsgleich `play-p4-w1280-light`; byte-Gleichheit als Test-Assertion; EXCERPT LEAK PROBE PASS auf allen 6 Beinen (0 `POST /excerpt` im Fenster des Ausgeschlossenen) | PASS |
| P12 Verweis nicht active | Discovery-Phase play-leak: p12a (Samba-Sperre) und p12b (Widerruf) mit HTML-Belegen, `PHASE PASS play-leak` auf allen 6 Beinen, Kontrolle zeigt den Unterschied | PASS (HTML statt PNG, Abweichung 3) |
| P13 zu wenig Speicherplatz | kein CI-Bild möglich (fixme); T12-Zuordnung über Unit-Tests aus 03-13/03-16b | PASS (Abweichung 4) |
| Kontrast | Assertion `ratio >= 4.5` auf jedem P1-Bild (hell, dunkel, Hochkontrast) grün, kalibrierter Selbsttest je Bein (21:1 PASS, #767676 knapp über, #999999 unter 4,5:1) | PASS |
| Umlaut-Audit | Skript `audit_0321.py` (Scratchpad) über `php/l10n/*.json`, `backend/l10n/*.json`, `docs/install*.md`, `README*.md`, `CHANGELOG.md`: Gedankenstriche, Emoji, ASCII-Ersatzumlaute (Wortliste), FR-U+00A0; OHNE BEFUND, Selbsttest 4/4 gefeuert | PASS |
| Gates | `uv run pytest tests/test_trilingual.py tests/test_ui_assets.py -x -q`: 49 passed | PASS |

## Abweichungen (dem Owner benannt, akzeptiert)

1. **Suchmatrix in EN:** Die S1-bis-S5-Screenshots liefen mit englischer Nutzersprache ("Preliminary"); der Prüfvertrag nennt DE. Die deutsche Fassung ("Vorläufig") ist über `search-hit-de-*` (375/1280) und die Katalog-Gates belegt.
2. **Kontrast-Zahlenwerte nicht erhalten:** playwright-report wird im Job von späteren Aufrufen überschrieben (bekannt aus 03-20); belegt ist das Gate (Assertion plus Selbsttest), nicht der Zahlenwert. Verbesserungskandidat bleibt offen.
3. **P12 ohne PNG:** per D-03-24/OC-1 als HTML-Probe in Discovery statt Playwright in deploy-harp (Container hält nur einen Verweis je Datei).
4. **P13 ohne Bild:** CI kann keine volle Platte stellen; Beleg sind die Unit-Tests der Zuordnung disk_full nach T12.

## Owner-Abnahme

- 15.11.2026, nach eigener Durchsicht des Screenshot-Ordners: "Ich habe mir die Bilder angeschaut und es passt." Keine Befunde, keine Korrekturschleife nötig.

## Deviations

Keine über die vier benannten, akzeptierten Abweichungen hinaus. Keine Repo-Dateien geändert außer diesem SUMMARY.
