---
phase: 04-suchqualit-t-und-export
plan: 13
subsystem: docs
tags: [readme, security, changelog, exp-04, exp-03, srch-05, srch-06, d-04-18]
requires:
  - "04-02 (Datums- und Personenfilter, Files-Semantik)"
  - "04-06 (Komposita-Präfix, voller Zahlenraum)"
  - "04-09, 04-10 (Export, Download-Sperre fail closed)"
  - "04-11 (Abspielseite: Abschnitt Untertitel-Entwurf, Spur, Ablage-Knopf)"
  - "04-12 (Nebendatei nie überschreiben, T-04-42)"
provides:
  - "README.md/.en/.fr: Unterabschnitte Suche, Untertitel-Entwurf, Grenzen im Gleichstand; NC-36-Hinweis zum Viewer"
  - "SECURITY.md Scope: Versprechen für Export, Spur, Ablage und Filter; Restrisiko T-04-42"
  - "CHANGELOG.md: Abschnitt Unreleased als englische Faktenliste"
affects: [04-15, 04-16, 04-17]
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified:
    - README.md
    - README.en.md
    - README.fr.md
    - SECURITY.md
    - CHANGELOG.md
decisions:
  - "Status-Absatz sagt ausdrücklich, dass Suche und Untertitel-Entwurf gebaut, aber in keiner veröffentlichten Version sind (kein Versprechen zur nächsten Version)"
  - "Der Punkt 'Verändert nie Ihre Dateien' bleibt, ergänzt um: eine neue Datei entsteht nur bei der Ablage eines Untertitel-Entwurfs"
  - "T-04-42 als Restrisiko in die öffentliche SECURITY.md (Auftrag und 04-12-Plan), mit der ehrlichen Folge: die Datei des fremden Clients kann überschrieben werden"
  - "CHANGELOG-Abschnitt heißt 'Unreleased'; die Versionsnummer setzt das Release"
metrics:
  duration: "ca. 35 min"
  completed: 2026-11-16
  tasks: 2
  files: 5
---

# Phase 4 Plan 13: READMEs, Sicherheitsversprechen und Changelog Summary

Die drei READMEs beschreiben den gebauten Phase-4-Stand (Wortformen, Komposita-Anfang, Zahlen, Filter, Untertitel-Entwurf als SRT/VTT/TXT, Nebendatei, Spur, Download-Sperre) mit eigenem Grenzen-Abschnitt und dem ehrlichen Satz, dass der Nextcloud-Viewer Nebendateien erst ab Nextcloud 36 erkennt; SECURITY.md nennt die neuen Versprechen und das Restrisiko T-04-42, CHANGELOG.md eine englische Faktenliste.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | READMEs DE/EN/FR im Gleichstand | e891441 |
| 2 | SECURITY.md Scope und CHANGELOG | f530317 |

## Geänderte Abschnitte (für die Owner-Freigabe vor dem Release)

- README (DE/EN/FR je gleich):
  - Status-Absatz: neuer Satz "gebaut, aber noch in keiner veröffentlichten Version"
  - "Was Audio & Video Search kann": Punkt "Verändert nie Ihre Dateien" ergänzt (neue Datei nur bei Ablage)
  - neu "### Suche": Wortformen, Komposita-Anfang ab 5 Buchstaben, Zahlen 0 bis 100 mit Ordinalzahlen, runde Hunderter/Tausender, Tausender mit Trennzeichen, Jahre 1100 bis 2099, Datums- und Personenfilter
  - neu "### Untertitel-Entwurf": SRT/VTT/TXT mit Namensmuster, Entwurf-Hinweis in VTT/TXT, Teilstand, Ablage `<Name>.<de|en|fr>.vtt` nur mit Anlegerecht und nie überschreibend, Spur am Video (aus), Freigaben ohne Download-Erlaubnis (unentscheidbar = gesperrt)
  - neu "### Grenzen": Viewer erst ab Nextcloud 36, nur Wortanfang (Plan/Bebauungsplan), Beifang Haushälterin, SRT ohne Entwurf-Hinweis, Nebendatei nie automatisch aktualisiert, Personenfilter nur geteilte Dateien, Begriff "Untertitel-Entwurf"
  - Tabelle "Zwei Apps": Rolle der PHP-App um "Untertitel-Entwurf" ergänzt
- SECURITY.md, Scope: zweiter Absatz mit den Versprechen (Leserecht plus Download-Erlaubnis, unentscheidbar = gesperrt; Ablage nur mit Anlegerecht, never overwrites; Filter verraten keine Freigaben), dritter Absatz Restrisiko T-04-42
- CHANGELOG.md: neuer Abschnitt "## Unreleased" mit acht Punkten

## Faktenquellen

Alle Zahlen und Beispiele aus den SUMMARYs 04-01 ("zwölf" findet "12", "twelfth", "12e"), 04-02 (mtime, Files-Semantik, nie geteilte Datei fällt heraus), 04-06 (5 Zeichen, Haushaltsplanberatung, 1940/neunzehnhundertvierzig, 1100 bis 2099, Haushälterin, Plan/Bebauungsplan), 04-09/04-10 (Formate, Namensmuster, T35/T15, UNKNOWN sperrt), 04-11 (Spur ohne default, nur Video), 04-12 (isCreatable, nie überschreiben, T-04-42) und 04-RESEARCH (Viewer stable33 bis 35 ohne Code, `@nextcloud/viewer` erst im Server-master = NC 36). Store-Schema 4 per `store/repo.py` (SCHEMA_VERSION 4, Migration v3 nach v4 in einer Transaktion) geprüft.

## Verifikation

- `grep -c "Nextcloud 36"` in allen drei READMEs >= 1; `grep -ci bitv` je 0; keine U+2013/U+2014; FR mit U+00A0 vor `: ;` und in Guillemets
- test_trilingual.py + test_public_texts.py: 48 passed
- ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture grün
- Volle Suite vor Task 1: 2325 passed, 15 skipped, 4 xfailed (zweiter Lauf, siehe unten); vor Task 2: 2325 passed, 15 skipped, 4 xfailed (erster Lauf grün)

## Deviations from Plan

1. **T-04-42 in der öffentlichen SECURITY.md:** Der 04-13-Plan legt akzeptierte Restrisiken in das phaseneigene 04-SECURITY.md; der Auftrag des Orchestrators und der 04-12-Plan (Threat-Register, SidecarWriter-Docblock) verlangen die öffentliche SECURITY.md. Umgesetzt nach Auftrag, weil das öffentliche Versprechen "never overwrites" sonst ohne die bekannte Ausnahme dastünde. secure-phase kann den Eintrag zusätzlich in 04-SECURITY.md führen.
2. **Status-Satz "noch in keiner veröffentlichten Version":** nicht im Plan, ergänzt, damit die README keinen Stand verspricht, der in 0.3.0 nicht enthalten ist.

## Prozessvermerk

Der erste volle Suite-Lauf vor dem Task-1-Commit endete bei 64 % ohne Fehlermeldung mit Exit 1 (Ausgabe vollständig in der Scratchpad-Datei suite-task1.txt; die Stelle liegt im Bereich `tests/test_preview_worker.py`, nach Zählung um `test_a_25_minute_wav_through_real_ffprobe_and_ffmpeg`; ein Testname mit FAILED wurde nicht ausgegeben, der Prozess brach ab). Der einmalige Wiederholungslauf war grün (2325 passed, 15 skipped, 4 xfailed). Die geänderten Dateien sind reine Markdown-Texte ohne Bezug zu diesem Test.

## Known Stubs

Keine.

## Threat Flags

Keine neuen Flächen (nur Dokumentation). T-04-49: kein BITV-Anspruch, NC-36-Satz ausdrücklich, Gate grün. T-04-50: jedes Versprechen in SECURITY.md ist durch PHPUnit-Fälle aus 04-02, 04-10, 04-12 gedeckt (CI); der E2E-Beleg folgt in 04-14/04-17.

## Self-Check: PASSED

- FOUND: README.md, README.en.md, README.fr.md, SECURITY.md, CHANGELOG.md (geändert)
- FOUND: Commits e891441, f530317
