---
phase: 03-vorschau-transkripte-in-der-suche
plan: 16b
type: execute
wave: 5
depends_on: ["03-01", "03-16"]
files_modified:
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
autonomous: true
requirements: [SRCH-02, MEDIA-04]

must_haves:
  truths:
    - "Die Abspielseite zeigt bei einem Vorschau-Transkript unter dem Ausschnitt T2, bei einer Datei in Arbeit T3 statt T2, für eine noch nicht transkribierte Stelle T4"
    - "Statt 'kein Transkript' stehen T5 bis T12 im grauen Ausschnitt-Block; überlang nennt die Höchstdauer mit Singular/Plural und T10 im selben Absatz"
    - "Alle Texte stammen wörtlich aus 03-UI-SPEC.md (T12 aus der dort freigegebenen Zeile), in de, de_DE, en, fr; der Bestandszweig für none bleibt zeichengleich"
  artifacts:
    - path: "php/templates/play.php"
      provides: "p.avs-excerpt__note und neue hint-Zweige"
      contains: "avs-excerpt__note"
    - path: "php/css/play.css"
      provides: ".avs-excerpt__note laut UI-SPEC"
      contains: ".avs-excerpt__note"
  key_links:
    - from: "play.php"
      to: "PageController-Parameter excerptState, excerptNote, excerptHours (Plan 03-16)"
      via: "defensives Lesen, p() für jeden Text"
      pattern: "excerptNote"
---

## Phase Goal

**As a** Nutzerin oder Nutzer einer Nextcloud-Instanz, **I want to** gesprochenen Text meiner Aufnahmen in Minuten über die normale Nextcloud-Suche finden, als vorläufig gekennzeichnet und nur in Dateien, die ich lesen darf, **so that** ich meine Aufnahmen durchsuchen kann, ohne dass ein Inhalt den Server verlässt.

<objective>
Darstellung der Fläche 2 der UI-SPEC: Template-Zweige, CSS-Regel `.avs-excerpt__note`, Kataloge T2 bis T12 in DE/EN/FR (D-03-04, D-03-07, D-03-13, D-03-17).

Purpose: Die in Plan 03-16 abgeleiteten Zustände werden sichtbar, dreisprachig und barrierearm.
Output: play.php, play.css, Kataloge, test_ui_assets.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>


<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-16-SUMMARY.md
@php/lib/Controller/PageController.php
@php/templates/play.php

Regeln: Commits nur lokal mit `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit`, ohne Claude-Session- oder Co-Authored-By-Zeile, nie "closes/fixes/resolves #N". Kein Push. Kein lokales Docker. STATE.md, ROADMAP.md, REQUIREMENTS.md nicht schreiben. Kein PHP lokal (phpunit in CI, Plan 03-20). Texte T1 bis T12 wörtlich aus 03-UI-SPEC.md (T12 aus der freigegebenen Zeile "| T12 |" in 03-UI-SPEC.md, nicht aus einem SUMMARY), englisch als Schlüssel; de und de_DE inhaltsgleich, unpersönlich; FR mit U+00A0 vor : ; ? ! (die neuen Texte enthalten keines); keine Gedankenstriche, keine Emojis, kein Ausrufezeichen. CSS nur mit Nextcloud-Variablen, kein Hex, kein !important, kein outline: none, kein style-Attribut, keine Inline-Skripte, kein JS, kein aria-live.

<interfaces>
PageController (Bestand): `EXCERPT_OK = 'ok'`, `EXCERPT_NONE = 'none'`, `EXCERPT_UNAVAILABLE = 'unavailable'`, `EXCERPT_SKIPPED = 'skipped'`; `private function excerpt(string $uid, int $fileId, int $startMs): array` liefert `[state, text]` (Ausschluss zuerst, scheiternde Ausschlussfrage = ausgeschlossen, dann searchAllowed, dann Container).
ExAppService::excerpt (Bestand, Zeilen 206 bis 227): prüft `known` bool, `excerpt` string|null mit plainText, sonst null.
play.php Zeilen 45 bis 46 (defensives Lesen von excerptState, excerpt), 181 bis 190 (section.avs-excerpt).
Container ab Plan 03-14: `/excerpt` -> `{known: false}` oder `{known: true, excerpt: string|null, stage: "preview"|"final"|"sample"|null, partial: bool, pendingHere: bool, reason: string|null, limitHours?: int}`.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Template, CSS und Kataloge T2 bis T12</name>
  <files>php/templates/play.php, php/css/play.css, php/l10n/de.json, php/l10n/de.js, php/l10n/de_DE.json, php/l10n/de_DE.js, php/l10n/en.json, php/l10n/en.js, php/l10n/fr.json, php/l10n/fr.js, backend/tests/test_ui_assets.py</files>
  <read_first>
    - php/templates/play.php (ganze Datei)
    - php/css/play.css Zeilen 200 bis 240
    - php/l10n/de.json, en.json, fr.json, de_DE.json
    - scripts/l10n_js.py
    - backend/tests/test_ui_assets.py, backend/tests/test_trilingual.py
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md Copywriting Contract, Aufbau des Ausschnitt-Blocks, Barrierefreiheit
  </read_first>
  <action>play.php: excerptNote und excerptHours defensiv lesen wie excerptState (string bzw. int, sonst '' bzw. 0). Im Block: ok mit Text: blockquote wie heute, danach bei note preview `<p class="avs-excerpt__note">` mit T2, bei note partial mit T3 (nie beide); A4 hint T4; A6 T5; A7 T6; A8 T7; A9 T8; A10 in EINEM `p.avs-excerpt__hint`: `$l->n('This file is longer than %n hour and was therefore not transcribed.', 'This file is longer than %n hours and was therefore not transcribed.', $excerptHours)`, ein Leerzeichen, T10; A11 T11; A13 T12; none: Bestandszweig unverändert (Byte-Gleichheit); sonst (unavailable): Bestandszweig unverändert. Alles mit p(). play.css: neue Regel `.avs-excerpt__note` genau mit `margin: calc(var(--default-grid-baseline) * 2) 0 0; color: var(--color-text-maxcontrast); font-size: var(--font-size-small); line-height: var(--default-line-height); overflow-wrap: anywhere;` und sonst nichts; prüfen, dass `.avs-excerpt__hint` `overflow-wrap: anywhere` hat (sonst ergänzen, UI-SPEC Responsives Verhalten). Kataloge: T2 bis T8, T9 als Plural-Schlüssel `_This file is longer than %n hour and was therefore not transcribed._::_This file is longer than %n hours and was therefore not transcribed._` mit Array-Wert je Sprache, T10, T11, T12 in de, de_DE, en, fr; `.js` mit scripts/l10n_js.py neu erzeugen. test_ui_assets.py: Regel `.avs-excerpt__note` exakt mit den fünf Eigenschaften, keine Hexfarbe, kein !important; im Template steht note nach blockquote im DOM-Text. Umlaut-Audit der neuen Werte (keine ae/oe/ue-Ersatzschreibung in DE-Werten, kein U+2013/U+2014).</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_ui_assets.py tests/test_trilingual.py tests/test_public_texts.py tests/test_php_gates.py -x -q && grep -q "Vorläufiges Transkript. Es kann Fehler enthalten." ../php/l10n/de.json && grep -q "Transcription provisoire. Elle peut contenir des erreurs." ../php/l10n/fr.json && python -c "import sys,pathlib; bad=[p for p in sys.argv[1:] if any(c in pathlib.Path(p).read_text(encoding='utf-8') for c in (chr(0x2013), chr(0x2014)))]; print(bad); sys.exit(1 if bad else 0)" ../php/l10n/*.json ../php/templates/play.php</automated>
  </verify>
  <acceptance_criteria>
    - Alle zwölf neuen Texte (T2 bis T12, T9 als Plural) stehen in de, de_DE, en, fr (json und js); test_trilingual grün.
    - `grep -c "avs-excerpt__note" php/templates/play.php` ist mindestens 2 (preview und partial).
    - Der Zweig für none ist gegenüber dem Stand vor dem Plan zeichengleich (`git diff` zeigt keine Änderung an dieser Zeile).
  </acceptance_criteria>
  <done>Commit `feat(03-16): Hinweise und Gründe auf der Abspielseite in DE, EN und FR`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Controller-Parameter nach HTML | Werte im Template |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-72 | Tampering / XSS | Template-Ausgabe | mitigate | jeder Text über $l->t/$l->n und p(), excerptNote/excerptHours defensiv gelesen, kein Rohcode |
| T-03-73 | Information Disclosure | A5-Zweig verändert | mitigate | Bestandszweig zeichengleich, Byte-Vergleich aus Plan 03-16 und P11 in 03-18 |
</threat_model>

<verification>
Python-Gates über CSS und Kataloge grün; visuelle Abnahme in Plan 03-21.
</verification>

<success_criteria>
- Alle Zustände A1 bis A13 dargestellt, dreisprachig, Bestandszweig unverändert.
</success_criteria>

<output>
Create `.planning/phases/03-vorschau-transkripte-in-der-suche/03-16b-SUMMARY.md` when done
</output>
