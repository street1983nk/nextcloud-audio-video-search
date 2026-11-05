---
name: Audio & Video Search
description: TODO(skeleton) ein Satz, was die Oberfläche zeigt. Gestaltet als Teil der Nextcloud-Oberfläche ohne eigene Marke.
colors:
  color-primary-element: "#00679e"
  color-primary-element-text: "#ffffff"
  color-main-background: "#ffffff"
  color-main-text: "#222222"
  color-text-maxcontrast: "#6b6b6b"
  color-background-hover: "#f5f5f5"
  color-border: "#ededed"
  color-error: "#ffe7e7"
  color-error-text: "#8a0000"
  color-warning: "#ffeec5"
  color-warning-text: "#664700"
  color-success: "#d8f3da"
  color-success-text: "#005416"
  color-info: "#d5f1fa"
  color-info-text: "#0066ac"
typography:
  headline:
    fontFamily: "var(--font-face)"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "var(--font-face)"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "var(--font-face)"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  small: "4px"
  element: "8px"
  container: "12px"
spacing:
  baseline: "4px"
  2x: "8px"
  4x: "16px"
  6x: "24px"
  clickable-area: "34px"
  coarse-pointer: "44px"
components:
  button-primary:
    backgroundColor: "{colors.color-primary-element}"
    textColor: "{colors.color-primary-element-text}"
    rounded: "{rounded.element}"
    height: "{spacing.clickable-area}"
  note-card-error:
    backgroundColor: "{colors.color-error}"
    textColor: "{colors.color-error-text}"
    rounded: "{rounded.container}"
    padding: "16px"
---

# Design System: Audio & Video Search

Vorlage aus nextcloud-exapp-skeleton. Folgt der Skill nextcloud-ui; diese Datei hat bei UI-Arbeit Vorrang vor der Skill. Die mit TODO(skeleton) markierten Stellen füllt jede App selbst.

## Overview

Die App hat kein eigenes Erscheinungsbild und soll keins bekommen. Jede Oberfläche soll aussehen, als käme sie aus dem Nextcloud-Server selbst, und jedes Theming mitmachen: Akzentfarbe des Admins, hell, dunkel, hoher Kontrast. Die Hex-Werte im Frontmatter sind nur Referenzwerte des Standard-Themes und gehören nie in den Code.

Stufen der Oberfläche, in dieser Reihenfolge prüfen:

1. **Deklarative Einstellungen** (Standard im Skelett, `src/audio_video_search/settings.py`): AppAPI rendert das Formular mit Nextcloud-Komponenten. Kein eigenes CSS, kein Build-Schritt.
2. **Eigene Seite mit Vue** nur wenn Stufe 1 nicht reicht: `@nextcloud/vue` 9 wie in Gameworld, Komponenten statt Eigenbau, ausgeliefert über `js/` im Container und `nc.ui.resources`.
3. **PHP-Templates** nur in einer PHP-Begleit-App (siehe SKELETON.md, Abschnitt PHP-Begleit-App).

TODO(skeleton): welche Stufe diese App nutzt und warum.

**Key Characteristics:**
- Nur Nextcloud-CSS-Variablen, kein Farbliteral im Code.
- Abstände als Vielfache von `var(--default-grid-baseline)`.
- Schrift des Servers, zwei Gewichte (400, 700), keine Webfonts.
- Flach: keine Schatten, Zustände über Flächenwechsel.
- Icons aus Material Design Icons (`vue-material-design-icons`), Größe 20, keine Emojis.

## Colors

Die Palette ist die des Servers: neutrale Flächen, eine Akzentfarbe und vier Statuspaare.

### Primary
- **Theming-Akzent** (`--color-primary-element` mit `--color-primary-element-text`): nur für die eine Hauptaktion pro Bereich.
- **Heller Akzent** (`--color-primary-element-light` mit `--color-primary-element-light-text`): Zustände, keine Aufforderungen.

### Neutral
- **Seitengrund** (`--color-main-background`), **Haupttext** (`--color-main-text`), **gedämpfter Text** (`--color-text-maxcontrast`), **Hover-Fläche** (`--color-background-hover`), **Trennlinie** (`--color-border`).

### Statuspaare
- Fehler, Warnung, Erfolg, Hinweis jeweils als Paar `--color-<status>` und `--color-<status>-text`, Icon in `--color-element-<status>`. In Vue über `NcNoteCard`.

### Named Rules
**The Pair Rule.** Fläche und Text eines Status immer als Server-Paar, nie gemischt.

**The Never Color Alone Rule.** Farbe ist nie der einzige Träger: Icon und Satz gehören dazu.

## Typography

Schrift des Servers über `--font-face`. Rang über Gewicht, nicht über zusätzliche Größen: Headline 20 px, Body `--default-font-size`, Label `--font-size-small`.

## Layout

Eine Lesespalte, Abstände als `calc(var(--default-grid-baseline) * n)`. Klickflächen mindestens `--default-clickable-area`, bei `pointer: coarse` 44 px. Prüfbreiten 375, 768 und 1280 px.

## Elevation & Depth

**The Flat Rule.** Keine Schatten, keine Verläufe, kein Glas. Ein Zustandswechsel ist ein Flächenwechsel.

## Shapes

Radien nur über `--border-radius-small`, `--border-radius-element`, `--border-radius-container`. Keine Karten in Karten.

## Components

| Zweck | Komponente |
|---|---|
| Aktion | `NcButton` (variant primary nur für die Hauptaktion) |
| Hinweis, Warnung, Fehler, Erfolg | `NcNoteCard` |
| Laden | `NcLoadingIcon` |
| Leerer Zustand | `NcEmptyContent` |
| Schalter, Auswahl | `NcCheckboxRadioSwitch`, `NcSelect` |
| Dialog | `NcDialog` |
| Einstellungsblock | `NcSettingsSection` |

Jede Ansicht braucht die Zustände Laden, leer, Fehler, Erfolg und keine Berechtigung.

## Texte

- Jeder sichtbare Text dreisprachig (Deutsch, Englisch, Französisch) über `l10n/` bzw. `t('audio_video_search', ...)`, nie hart codiert.
- Deutsch mit echten Umlauten, Satzanfang groß, kein Ausrufezeichen, keine Gedankenstriche, keine Emojis.
- Fehlertexte sagen, was passiert ist und was der Nutzer tun kann.

## Do's and Don'ts

### Do:
- **Do** zuerst eine deklarative Einstellung oder eine Nc-Komponente suchen, bevor eigenes Markup entsteht.
- **Do** jede Ansicht hell, dunkel und mit hohem Kontrast bei 375, 768 und 1280 px per Playwright prüfen, danach `impeccable critique` und `impeccable audit`.
- **Do** Icon-Knöpfe mit `aria-label` versehen und den Fokusring sichtbar lassen.

### Don't:
- **Don't** Hex-, RGB- oder benannte Farben, eigene Schriften oder eigene Schatten.
- **Don't** Verläufe, Glassmorphism, zentrierte Hero-Blöcke, Karten in Karten.
- **Don't** `!important` gegen Server-Styles oder `outline: none`.
