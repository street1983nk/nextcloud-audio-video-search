---
phase: 5
slug: ressourcen-profile-und-modellbezug
status: draft
shadcn_initialized: false
preset: none
created: 2026-11-18
base_contract: .planning/phases/01-zwei-app-ger-st-und-integrationsbeweis/01-UI-SPEC.md
extends: .planning/phases/04-suchqualit-t-und-export/04-UI-SPEC.md
---

# Phase 5: UI Design Contract

> Visueller und Interaktionsvertrag für Phase 5 (Ressourcen, Profile und Modellbezug). Erstellt vom gsd-ui-researcher, geprüft vom gsd-ui-checker.
> Quellen: 05-CONTEXT.md (D-05-01 bis D-05-15, gelockt), 05-RESEARCH.md (Pattern 1, 3, 4, 5, 7; Lizenztabelle), 01-UI-SPEC.md (Fläche 3 Admin-Statusbereich, Farbregel, Banner), 04-UI-SPEC.md (status approved, Texte bis T35), DESIGN.md, Skill nextcloud-ui, Bestand `php/templates/admin.php`, `php/css/admin.css`, `php/js/admin.js`, `php/lib/Settings/Admin.php`, `ci/playwright/admin.spec.ts`, Kataloge `php/l10n/*.json`.

**Grundsatz: Dieser Vertrag ist ein Nachtrag.** Alles aus 01-, 03- und 04-UI-SPEC.md gilt unverändert (Design System, Abstände, Typografie, Farben, Banner `avs-banner`, Texte T1 bis T35). Phase 5 ändert genau eine Fläche: **Fläche 3, Admin-Bereich "Audio & Video Search"** bekommt unter dem bestehenden Abschnitt "Verbindung zum Backend" drei neue Abschnitte:

1. **Transkriptionsprofil** (D-05-01, D-05-02, D-05-09): Vorschlag mit Grund, Auswahl Schnell, Ausgewogen, Qualität, harte Sperre mit Zahlen, Mindest-RAM-Hinweis, Rückfall-Hinweis.
2. **Rechenzeit** (RES-05, D-05-03, D-05-04, D-05-11, D-05-12): Threads (nur senken), Rechenfenster mit Zeitzone.
3. **Modelle und Lizenzen** (D-05-06, D-05-07, D-05-08, D-05-15): je Modell Herkunft, Lizenz, Größe, Zustand mit Download-Fortschritt; Offline-Schalter mit Hinweis zur Ablage; weitere Bestandteile (FFmpeg, PyAV-Codecs); Link auf THIRD-PARTY.md.

Nicht in Phase 5: neue App-Seite, Zustandsseite mit Warteschlange, Pause und Wiederholung (Phase 9), Lizenzzeile in der Abspielansicht (Deferred, Owner 18.11.2026), Instanz-Sprachen (Phase 7), CPU-basierte Profilvorwahl (Phase 11), Anzeige der Thread-Zahl in der Herkunft eines Transkripts (D-05-11 legt sie nur in die Daten). Unified Search und Abspielansicht bleiben byte-gleich. Die deklarativen Felder der ExApp (`processing_enabled`, `max_duration_hours` unter "Zusätzliche Einstellungen") bleiben, wo sie sind; keine Doppelung.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (PHP-Template plus reines Browser-JS ohne Bundler; shadcn-Gate nicht anwendbar, kein React/Vite) |
| Preset | not applicable |
| Component library | none: Nextcloud-Server-CSS. Native Elemente mit Server-Gestalt: `input[type=radio].radio` + `label`, `input[type=checkbox].checkbox` + `label`, `input[type=number]`, `input[type=time]`, `select`, `button`, `button.primary`, `progress`, Klasse `hidden-visually` |
| Icon library | Material Design Icons (Pictogrammers, Apache-2.0) als Pfaddaten in Inline-SVG, 20 px, `viewBox="0 0 24 24"`, `aria-hidden="true" focusable="false"`, `fill="currentColor"`. Bestand im Template: `error`, `warning`, `info`, `success`. Neu: `lock-outline` (Sperrgrund) und `download` (Modell wird geladen). Pfade am 2026-11-18 gegen Templarian/MaterialDesign-SVG `master/svg/<name>.svg` geprüft |
| Icon `lock-outline` | `M12,17C10.89,17 10,16.1 10,15C10,13.89 10.89,13 12,13A2,2 0 0,1 14,15A2,2 0 0,1 12,17M18,20V10H6V20H18M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V10C4,8.89 4.89,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z` |
| Icon `download` | `M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z` (gleich wie Phase 4) |
| Font | Server-Schrift über `var(--font-face)` |

Verbindliche Regeln aus 01-UI-SPEC.md gelten weiter: nur Nextcloud-CSS-Variablen, kein Hex/RGB, kein `!important`, kein `outline: none`, kein `style`-Attribut, keine Inline-Skripte (CSP), flach (keine Schatten, keine Verläufe, keine Karte in Karte), jeder Satz über `$l->t()`/`$l->n()`, jeder Wert von außen mit `p()`, Klassen-Präfix `avs-`. `admin.js` baut weiterhin **kein Markup aus Strings**: Es schaltet `hidden`, `disabled`, `checked`, setzt `value`, `aria-invalid`, `aria-busy` und ersetzt Textknoten. Alle Zustände und Sätze rendert das Template vorab (Muster der sieben Zustands-Banner).

**Kein Dateipfad auf der Seite (T-01-34 gilt weiter).** Auch kein Modellordner im Volume: Der Ablageort steht in der README (Link T89). Erlaubt sind Modellnamen, Lizenz-IDs, Zahlen und der occ-Befehl.

---

## Spacing Scale

Unverändert aus 01-UI-SPEC.md (`calc(var(--default-grid-baseline) * n)`, Grundwert 4 px). Alle Werte Vielfache von 4.

| Token | Value | Usage in Phase 5 |
|-------|-------|------------------|
| xs | 4px | Abstand Beschriftung zu Hinweiszeile; Abstand Icon zu Text in Sperr- und Zustandszeilen; Abstand zwischen Größe und Zustand eines Modells |
| sm | 8px | Abstand zwischen den drei Profil-Optionen; Spaltenabstand in Formularzeilen (`gap`); Abstand Speichern-Knopf zu Speicherstatus |
| md | 16px | Abstand Einleitung zu Optionen; Abstand Threads-Block zu Fenster-Block; Abstand zwischen zwei Modellen; Abstand zwischen Von/Bis-Feldern ab 768 px |
| lg | 24px | Abstand vor Unterüberschrift `h3` "Weitere Bestandteile" und vor dem Offline-Block (wie `.avs-admin__debug`) |
| xl | 32px | nicht neu genutzt |

Nicht genutzt: 48 px, 64 px.

Einrückung der Hinweiszeilen unter Radio und Checkbox: `padding-inline-start: calc(var(--default-grid-baseline) * 7)` (28 px), damit Hinweis und Sperrgrund bündig unter dem Beschriftungstext stehen und nicht unter dem Kreis. Prüfpunkt: Lage des Server-Kreises in NC 33 bis 35 messen; weicht er ab, Wert auf das nächste Vielfache von 4 anpassen, das bündig ist.

Exceptions:
- Klickflächen: Radio-Zeilen, Checkbox-Zeile, Zahlen-, Zeit- und Auswahlfeld, Speichern-Knopf `min-height: var(--default-clickable-area)`, bei `(pointer: coarse)` `calc(var(--default-grid-baseline) * 11)` = 44 px. Gleiche Regel wie Bestand, hinter `#avs-...`-ID (Befund aus `admin.css`: die Server-Regel für Knöpfe schlägt eine Klasse).
- Innenabstand von `.section` und der Felder kommt vom Server-CSS, nicht aus der App.
- Breite Zahlenfeld Threads: `calc(var(--default-grid-baseline) * 20)` = 80 px. Breite `progress`: `100%`, höchstens `calc(var(--default-grid-baseline) * 80)` = 320 px. Auswahlfeld Zeitzone: `max-width: 100%`, ab 768 px höchstens 320 px.

---

## Typography

Unverändert: genau drei Größen (13, 15, 20 px), genau zwei Gewichte (400, 700), Zeilenhöhe nur `var(--default-line-height)`.

| Role | Size | Weight | Line Height | Neu in Phase 5 |
|------|------|--------|-------------|----------------|
| Body | 15px `var(--default-font-size)` | 400 | `var(--default-line-height)` | Beschriftungen der Radios, Checkbox und Felder; Einleitung T37; Banner-Texte; Zustandszeile eines Modells |
| Label | 13px `var(--font-size-small)` | 400 | `var(--default-line-height)` | Profilbeschreibung T41 bis T43, Bedarf T44, Sperrgrund T45, Mindest-RAM T48, Feldhinweise T56/T64/T88/T90, Herkunft/Lizenz T72 bis T75, Größe T76, Speicherstatus, Kennzeichen "Vorschlag" T46 |
| Heading (Abschnitt) | 20px (Server-`h2` in `.section`) | 700 | `var(--default-line-height)` | "Transkriptionsprofil", "Rechenzeit", "Modelle und Lizenzen" (gleich wie Bestand "Verbindung zum Backend") |
| Heading (Unterabschnitt) | 15px `var(--default-font-size)` | 700 | `var(--default-line-height)` | Modellname je Modell (`h3`), "Weitere Bestandteile" (`h3`), Klasse `.avs-admin__subheading` aus dem Bestand |

Zahlen (GB, Uhrzeiten, Threads) mit `font-variant-numeric: tabular-nums`, wie `.avs-admin__time`.

Fehlertexte an Feldern: Label-Rolle in `--color-main-text` mit Icon `error` in `--color-element-error` davor; das Feld bekommt `aria-invalid="true"` und den Server-Fehlerrand. Nicht `--color-error-text`: Das ist der Text zur Fehlerfläche `--color-error` (Pair Rule), nicht zum Seitengrund.

---

## Color

Unverändert aus 01-UI-SPEC.md.

| Role | Value | Usage in Phase 5 |
|------|-------|------------------|
| Dominant (60%) | `--color-main-background` | Seitengrund aller drei neuen Abschnitte; Optionen, Felder und Modelle liegen **ohne eigene Fläche** direkt darauf |
| Secondary (30%) | `--color-background-hover`, Trennlinie `--color-border` | Kennzeichen "Vorschlag" (Fläche `--color-background-hover`, Radius `--border-radius-small`, Innenabstand 0 und xs); Trennlinie `1px solid var(--color-border)` zwischen zwei Modellen |
| Accent (10%) | `--color-primary-element` / `--color-primary-element-text` | nur die unten gelisteten Elemente |
| Destructive | `--color-error` / `--color-error-text`, Icon `--color-element-error` | nur Fehler-Banner "Zu wenig Arbeitsspeicher" (T49/T50), Zustand "falsche Prüfsumme" (Icon), Feldfehler (Icon). Phase 5 hat **keine zerstörende Aktion** |
| Warnung | `--color-warning` / `--color-warning-text` | Rückfall-Banner T47, Banner "Backend antwortet nicht" T53, Banner "Stand nicht aktualisiert" T95 |
| Hinweis | `--color-info` / `--color-info-text` | keiner neu |

Gedämpfter Text `--color-text-maxcontrast`: nur Label-Rolle (Profilbeschreibung, Bedarf, Mindest-RAM, Feldhinweise, Herkunft/Lizenz, Größe, Speicherstatus). **Sperrgrund T45 in `--color-main-text`**, nicht gedämpft: Er ist die eine Information, die eine gesperrte Option erklärt, und steht außerhalb des `label`, damit die Server-Dämpfung deaktivierter Beschriftungen ihn nicht trifft.

Accent reserved for (Bestand plus Phase 5, abschließend):
1. Die eine Aktion eines Admin-Banners ("Apps öffnen", Bestand).
2. Der gesetzte Zustand der Debug-Checkbox (Bestand, Server-Stil).
3. **Neu:** der gewählte Kreis des Profil-Radios und der Fenster-Radios (Server-Stil `input.radio`, kein eigener Code).
4. **Neu:** der gesetzte Zustand der Offline-Checkbox (Server-Stil `input.checkbox`).
5. **Neu:** der eine Knopf "Rechenzeit speichern" (`button.primary`), die einzige Hauptaktion der Seite, die mehrere Felder zusammen speichert.
6. **Neu:** der gefüllte Teil eines `progress` beim Modell-Download (`accent-color: var(--color-primary-element)`).

Sonst nirgends: nicht für "Vorschlag", nicht für Modellnamen, nicht für Lizenz-Links (Server-Linkstil), nicht für "Erneut prüfen". Farbe ist nie alleiniger Träger: Sperre hat Icon und Satz, Fortschritt hat Text "x von y", Zustände haben Satz.

---

## Fläche 3: Admin-Bereich (Erweiterung)

### Reihenfolge der Seite (neu fett)

```
div#avs-admin.section            Verbindung zum Backend (Bestand, unverändert)
**div#avs-profile.section**      Transkriptionsprofil
**div#avs-compute.section**      Rechenzeit
**div#avs-models.section**       Modelle und Lizenzen
```

Alle vier Abschnitte stehen im selben Template `admin.php` und kommen aus derselben `Settings\Admin::getForm()` (D-05-01). Die bestehende ID `#avs-admin` bleibt am ersten Abschnitt (Playwright-Bestand). Die Regel `#avs-admin [hidden] { display: none; }` wird auf `#avs-profile [hidden], #avs-compute [hidden], #avs-models [hidden]` erweitert.

### Datenvertrag Controller -> Template (neu)

`Admin::getForm()` holt zusätzlich zu `backendState` **einmal** `GET /resources` der ExApp (Research Pattern 7). Template und Initial State bekommen nur Codes, Zahlen (Bytes, Ganzzahlen), Uhrzeiten `HH:MM`, IANA-Zonen und Bools:

| Schlüssel | Inhalt |
|-----------|--------|
| `resources` | `null`, wenn die ExApp nicht antwortet (dann Zustand R9) |
| `availableBytes`, `minimumBytes` | sicherer Speicher ohne laufendes Kind; Mindestbedarf der App (aus der Wave-0-Messung, D-05-09, nie im Text fest) |
| `proposed`, `chosen`, `effective` | je `fast` / `balanced` / `quality` / `none` |
| `profiles[]` | je Profil `{id, locked, needBytes}` |
| `threads` | `{cpus, standard, admin, effective}` (`admin` = `null` heißt Standard) |
| `window` | `{start, end, zone, openNow, changeAt}`; `start`/`end` `null` = immer; `changeAt` = nächste Öffnung bzw. Schließung als `HH:MM` in `zone` |
| `zones` | Liste aus `DateTimeZone::listIdentifiers()` (PHP, nicht von der ExApp) |
| `defaultZone` | Zeitzone des Admin-Kontos, sonst `default_timezone`, sonst `UTC` (Research Pattern 4) |
| `models[]` | je Modell `{id, state, doneBytes, totalBytes, needFreeBytes}`, `id` aus `parakeet`, `silero`, `whisper-turbo`, `whisper-large-v3` |
| `offline` | `{value, forcedByEnv}` |

### Einheiten und Zahlenformat (Pitfall 9)

- Intern Bytes. Anzeige in **GB = 10^9 Bytes**, eine Nachkommastelle, Dezimaltrennzeichen der Admin-Sprache (de/fr Komma, en Punkt), Einheit über T96 ("GB", fr "Go").
- **Bedarf wird aufgerundet, verfügbarer Speicher abgerundet.** So zeigt eine Sperre nie "braucht 3,0 GB, verfügbar 3,0 GB". Modellgrößen und Download-Stand werden kaufmännisch gerundet (turbo 1,6 GB, large-v3 3,1 GB).
- Eine einzige PHP-Hilfsfunktion formatiert; PHPUnit prüft die Grenzfälle (Rundung, 0, unter 0,1 GB = "0,1 GB" beim Bedarf, Sprache).

### Abschnitt R-P: Transkriptionsprofil

```
div#avs-profile.section
  h2  Transkriptionsprofil                                             (T36)
  [nur R2] Fehler-Banner role="alert": T49 / T50
  [nur R3] Warn-Banner role="status": T47
  p.avs-res__intro       Vorschlag für diesen Server: {Profil}. Für die App sind {x GB} verfügbar.  (T37)
  p.avs-res__hint        Mindestbedarf der App: {y GB} Arbeitsspeicher.  (T48)
  fieldset.avs-res__options   aria-describedby="avs-profile-intro"
    legend.hidden-visually    Transkriptionsprofil                    (T36)
    je Profil in der Reihenfolge Schnell, Ausgewogen, Qualität:
      div.avs-res__option
        input.radio#avs-profile-{id} name="avs-profile" value="{id}" [checked wenn chosen] [disabled wenn locked]
                    aria-describedby="avs-profile-{id}-desc avs-profile-{id}-need"
        label for=…  {Name}  [span.avs-res__badge Vorschlag (T46), nur beim vorgeschlagenen]
        p#avs-profile-{id}-desc.avs-res__hint   Beschreibung (T41 bis T43)
        EINES von:
          p#avs-profile-{id}-need.avs-res__hint   Braucht {x GB} Arbeitsspeicher.   (T44)
          p#avs-profile-{id}-need.avs-res__lock   [Icon lock-outline] Gesperrt: braucht {x GB}, verfügbar {y GB}.  (T45)
  span#avs-profile-status.avs-admin__status role="status"   Gespeichert / Nicht gespeichert … (Bestand / T52)
```

Zustände:

| Nr. | Zustand | Bedingung | Darstellung |
|-----|---------|-----------|-------------|
| R1 | normal | `availableBytes >= minimumBytes`, `chosen` nicht gesperrt | T37, T48, drei Optionen; gesperrte Optionen mit T45, freie mit T44; "Vorschlag" am vorgeschlagenen Profil |
| R2 | unter Mindest-RAM (D-05-09) | `availableBytes < minimumBytes` oder `proposed = none` | Fehler-Banner T49/T50 oben; T37 entfällt (kein Vorschlag); T48 bleibt; alle drei Optionen `disabled` mit T45; keine Option `checked` als wirksam markiert, die gespeicherte Wahl bleibt aber `checked` |
| R3 | Rückfall | `chosen` gesperrt, `effective` ein anderes, freies Profil | Warn-Banner T47 mit Namen und Zahlen; Radio `chosen` bleibt `checked` und `disabled`, damit die gespeicherte Wahl sichtbar bleibt; die Seite sagt, womit wirklich gerechnet wird |
| R9 | Backend antwortet nicht | `resources = null` | statt der Abschnitte R-P und R-C ein einziger Warn-Banner T53 in `#avs-profile`; `#avs-compute` wird nicht gerendert; in `#avs-models` fehlen Zustand, Größe und Offline-Schalter, Herkunft und Lizenzen stehen trotzdem (statisch) |

Interaktion:
- **Speichern sofort beim Wechsel** (Server-Muster der Admin-Einstellungen, wie der Debug-Schalter): `change` am Radio sendet `POST admin/resources` mit `{profile}`. Während der Anfrage: `fieldset` `aria-busy="true"`, Radios `disabled`. Erfolg: Status "Gespeichert" (Bestandsschlüssel `Saved`) für 3 s; die Antwort ersetzt alle Zahlen, Sperren und Zustände (gleicher Weg wie Polling). Fehler: altes Radio wieder `checked`, Status "Nicht gespeichert. Erneut versuchen." (Bestand); bei 409 `profile_locked` Status T52 und Neuaufbau der Sperren aus der Antwort.
- Kein Bestätigungsdialog: Ein Profilwechsel löscht nichts und ist sofort umkehrbar. Er stößt nur den Download der nötigen Modelle an (D-05-06); den sieht der Admin im Abschnitt Modelle.
- Gesperrte Optionen sind `disabled`; ein Erzwingen gibt es nicht (D-05-02). Die PHP-Route und die ExApp lehnen ein gesperrtes Profil zusätzlich ab (409).
- Ohne JS: Werte, Sperren und Banner sind lesbar; Speichern geht nur mit JS (wie Debug-Schalter).

### Abschnitt R-C: Rechenzeit

```
div#avs-compute.section
  h2  Rechenzeit                                                       (T54)
  form#avs-compute-form novalidate
    div.avs-res__field
      label for="avs-threads"  Threads für die Erkennung              (T55)
      input#avs-threads type=number min=1 max={standard} step=1 inputmode=numeric value={admin ?? standard}
            aria-describedby="avs-threads-hint [avs-threads-error]"
      p#avs-threads-hint.avs-res__hint   Nutzbare CPUs: {n}. Standard und Höchstwert: {m}. …  (T56)
      p#avs-threads-error.avs-res__error hidden  [Icon error] Eine ganze Zahl von 1 bis {m} eingeben.  (T57)
    fieldset.avs-res__window
      legend   Wann gerechnet wird                                     (T58)
      input.radio#avs-window-always name=avs-window value=always   label Immer               (T59)
      input.radio#avs-window-set    name=avs-window value=window   label Nur im Zeitfenster  (T60)
      div#avs-window-fields [hidden, wenn "Immer"]
        div.avs-res__times
          div.avs-res__field  label for=avs-window-start Von (T61)  input#avs-window-start type=time step=60
          div.avs-res__field  label for=avs-window-end   Bis (T62)  input#avs-window-end   type=time step=60
        div.avs-res__field  label for=avs-window-zone Zeitzone (T63)  select#avs-window-zone (zones, vorgewählt zone ?? defaultZone)
        p#avs-window-hint.avs-res__hint   Über Mitternacht geht … (T64)
        p#avs-window-error.avs-res__error hidden   T65 / T66 / T67 (genau einer sichtbar)
      p#avs-window-state.avs-res__hint   T68 oder T69 (nur wenn ein Fenster gespeichert ist)
    div.avs-admin__actions
      button.primary#avs-compute-save type=submit hidden   Rechenzeit speichern   (T70)
      span#avs-compute-status.avs-admin__status role="status"
```

Interaktion:
- **Ein Speichern-Knopf** für Threads und Fenster zusammen, weil Von, Bis und Zone nur gemeinsam gültig sind (sofortiges Speichern einzelner Felder würde ungültige Zwischenstände wie `start == end` erzeugen). Knopf im Markup `hidden`, `admin.js` zeigt ihn (Muster Sprung-Knopf).
- Wechsel "Immer" / "Nur im Zeitfenster" schaltet nur `hidden` an `#avs-window-fields`, speichert nicht. Beim ersten Wechsel auf "Nur im Zeitfenster" ohne gespeichertes Fenster sind die Felder mit 22:00, 06:00 und `defaultZone` vorbelegt (Beispiel aus D-05-03).
- Prüfung im Browser vor dem Senden, gleiche Regeln wie PHP und ExApp (Research Pattern 7): Threads ganze Zahl 1 bis `standard`; Zeiten `HH:MM`; `start != end`; Zone in der Liste. Bei Fehler: Feld `aria-invalid="true"`, Fehlerzeile sichtbar und in `aria-describedby` aufgenommen, **Fokus auf das erste ungültige Feld**, nichts wird gesendet.
- Senden: Knopf `disabled` + `aria-busy="true"`, Beschriftung bleibt. Erfolg: "Gespeichert" (Bestand) 3 s, Statuszeile T68/T69 aus der Antwort neu gesetzt. Antwort 400 mit Feldcode: gleiche Fehlerzeile wie bei der Browser-Prüfung, Fokus aufs Feld. Andere Fehler: "Nicht gespeichert. Erneut versuchen." (Bestand), Werte bleiben im Formular stehen.
- "Immer" speichert `start = end = null` (D-05-03, Standard nach der Installation).
- Threads nur senken: `max` = Standard. Hat der Server nur 1 nutzbare CPU, gilt `min = max = 1`; das Feld bleibt bedienbar, T56 erklärt den Wert.
- Ohne JS: Werte lesbar, Speichern nicht möglich (Knopf bleibt verborgen).

Statuszeile Fenster (nur wenn ein Fenster gespeichert ist; Zeit in der Fenster-Zone):
- `openNow = true`: T68 "Das Zeitfenster ist offen bis {changeAt}."
- `openNow = false`: T69 "Das Zeitfenster ist geschlossen und öffnet um {changeAt}."

### Abschnitt R-M: Modelle und Lizenzen

```
div#avs-models.section
  h2  Modelle und Lizenzen                                             (T71)
  [nur R10] Warn-Banner T95
  ul.avs-models
    je Modell (Reihenfolge Parakeet, Silero VAD, Whisper large-v3-turbo, Whisper large-v3):
    li.avs-models__item
      h3.avs-admin__subheading#avs-model-{id}-name   {Modellname, nicht übersetzt}
      p.avs-res__hint   Herkunft und Lizenz (T72 bis T75), Lizenz-ID als Link
      p.avs-res__hint   Größe: {x GB}  (T76)                     [nicht bei R9]
      div.avs-models__state                                        [nicht bei R9]
        genau ein vorgerenderter Zustand sichtbar (Tabelle unten): [Icon] Satz
        progress.avs-models__progress  max={totalBytes} value={doneBytes}
                 aria-labelledby="avs-model-{id}-name" aria-describedby="avs-model-{id}-text"   (nur Zustand M5)
  span#avs-models-live.hidden-visually role="status"   Ansage bei Zustandswechsel (siehe Barrierefreiheit)
  div.avs-models__offline                                          [nicht bei R9]
    p.avs-admin__switch
      input.checkbox#avs-offline aria-describedby="avs-offline-hint [avs-offline-forced]" [checked] [disabled wenn forcedByEnv]
      label for=avs-offline   Offline-Modus, keine Verbindung ins Internet   (T87)
      span#avs-offline-status.avs-admin__status role="status"
    p#avs-offline-hint.settings-hint   T88 + code.avs-admin__command "occ audio_video_search:models --verify" + Link T89
    p#avs-offline-forced.settings-hint  T90   (nur wenn forcedByEnv)
  h3.avs-admin__subheading   Weitere Bestandteile                      (T91)
  ul.avs-models__others
    li  T92 (FFmpeg)
    li  T93 (PyAV-Codecs)
  p   a href="https://github.com/street1983nk/nextcloud-audio-video-search/blob/main/THIRD-PARTY.md"  T94
```

Modellnamen (Eigennamen, nicht übersetzt, als Konstante mit `p()`): "Parakeet TDT 0.6B v3", "Silero VAD", "Whisper large-v3-turbo", "Whisper large-v3". Lizenz-Links (feste Ziele, `rel="noreferrer noopener"`, `target` nicht gesetzt):

| Lizenz-ID | Ziel |
|-----------|------|
| CC-BY-4.0 | `https://creativecommons.org/licenses/by/4.0/` |
| MIT | `https://opensource.org/license/mit` |
| Apache-2.0 | `https://www.apache.org/licenses/LICENSE-2.0` |
| LGPL-2.1-or-later | `https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html` |
| GPL-2.0-or-later | `https://www.gnu.org/licenses/old-licenses/gpl-2.0.html` |

Links sind vom Admin geklickte Navigation; die App selbst baut dabei keine Verbindung auf (PLAT-04 unberührt). Die Lizenz-ID steht im Satz als Platzhalter und wird mit dem bestehenden Platzhalter-Verfahren (`$pieces`, Private-Use-Zeichen) als `<a>` eingesetzt, damit die Sprache die Stellung bestimmt.

Zustände eines Modells (`state`):

| Nr. | `state` | Icon | Satz | Hinweis |
|-----|---------|------|------|---------|
| M1 | `in_image` | `success` | T77 | Parakeet, Silero (RES-06) |
| M2 | `present` | `success` | T78 | Whisper, geladen oder abgelegt, Gesamt-sha256 bestätigt |
| M3 | `not_needed` | keins | T79 mit Name des wirksamen Profils | z. B. large-v3 bei Ausgewogen; gedämpft (Label-Rolle) |
| M4 | `waiting` | `download` | T80 | |
| M5 | `downloading` | `download` | T81 mit `doneBytes` / `totalBytes` + `progress` | |
| M6 | `verifying` | `download` | Bestandsschlüssel `Checking…` ("Wird geprüft…") | Gesamt-sha256 nach dem letzten Teil |
| M7 | `wrong_digest_download` | `error` | T83a | Datei verworfen, nie geladen (D-05-06) |
| M8 | `wrong_digest_placed` | `error` | T83b + `code` occ-Befehl | vom Admin abgelegte Datei, bleibt liegen |
| M9 | `offline_missing` | `warning` | T84 | nur bei Offline |
| M10 | `failed` | `warning` | T85 | Netz, Host nicht erlaubt, Zeitlimit; nie die URL |
| M11 | `disk_full` | `warning` | T86 mit `needFreeBytes` | |

Icons haben die Farbe `--color-element-{status}` auf dem Seitengrund, der Satz steht in `--color-main-text`. Kein Banner je Modell (keine Fläche in der Liste, keine Karte in Karte).

Polling (D-05-06, Admin sieht Fortschritt):
- `admin.js` fragt `GET admin/resources` alle 5 s, **nur solange** ein Modell in M4, M5 oder M6 ist und `document.visibilityState === 'visible'`. Kette über `setTimeout`, nie zwei Anfragen gleichzeitig. Sonst kein Polling.
- Die Antwort setzt `value`/`max` des `progress`, die Zahlen in T81 (Textknoten), schaltet den sichtbaren Zustand um und aktualisiert Abschnitt R-P (Sperren können sich nicht ändern, Zahlen schon).
- Drei gescheiterte Anfragen in Folge: Polling stoppt, Warn-Banner T95 erscheint (Zustand R10), letzter Stand bleibt stehen. "Erneut prüfen" im ersten Abschnitt bleibt der Weg zum Neuladen; ein Neuladen der Seite startet das Polling neu.

Offline-Schalter (D-05-07):
- Standard aus. Speichern sofort beim Umschalten (`POST admin/resources` mit `{offline}`), Status wie Debug-Schalter ("Gespeichert" / "Nicht gespeichert. Erneut versuchen.", bei Fehler alter Wert).
- Kein Bestätigungsdialog: Offline schaltet nichts ab, was nicht sofort wieder einschaltbar ist, und löscht keine Datei.
- `forcedByEnv = true`: Checkbox `checked` und `disabled`, T90 sichtbar und in `aria-describedby`.
- Nach dem Einschalten wechseln fehlende Whisper-Modelle des wirksamen Profils auf M9 (aus der Antwort).

### Barrierefreiheit (gilt für alle drei Abschnitte)

- Jedes Feld hat ein sichtbares `label for`; Radiogruppen sind `fieldset` mit `legend` (Profil: `legend.hidden-visually`, weil die `h2` darüber denselben Namen trägt; Fenster: sichtbare `legend` T58).
- Hinweise und Fehler über `aria-describedby`; ein Fehler wird beim Auftreten an die Liste angehängt und beim Beheben entfernt; dazu `aria-invalid="true"`/entfernt. Fehlertext beginnt mit dem Icon `error` (`aria-hidden`), der Satz trägt die Bedeutung.
- Gesperrte Profile: `disabled` am Radio, Sperrgrund T45 über `aria-describedby` am Radio verknüpft, damit Screenreader ihn beim Durchlaufen der Gruppe vorlesen. Kennzeichen "Vorschlag" steht im `label` und wird mitgelesen.
- Tab-Reihenfolge: Bestand (Apps öffnen, Erneut prüfen, Debug), Profil-Radios (Pfeiltasten innerhalb der Gruppe, nativ), Threads, Fenster-Radios, Von, Bis, Zeitzone, Rechenzeit speichern, Lizenz-Links der Modelle in Listenreihenfolge, Offline-Checkbox, Link Anleitung (T89), Links Weitere Bestandteile, Link THIRD-PARTY.md.
- Live-Regionen: Speicherstatus je Abschnitt `role="status"` (Bestandsmuster). Download-Fortschritt wird **nicht** je Takt angesagt; `#avs-models-live` sagt nur Zustandswechsel an, Text = Modellname + Satz des neuen Zustands (z. B. "Whisper large-v3-turbo. Vorhanden, Prüfsumme bestätigt."). Polling verschiebt nie den Fokus.
- Fokusring: Server-Standard, nie entfernt.
- Kontrast: siehe Prüfvertrag.

### CSS (neu, in `admin.css`)

| Selektor | Regeln |
|----------|--------|
| `.avs-res__options`, `.avs-res__window` | `display: flex; flex-direction: column; gap: calc(var(--default-grid-baseline) * 2); margin: calc(var(--default-grid-baseline) * 4) 0 0; padding: 0; border: 0; min-width: 0;` |
| `.avs-res__option` | `display: flex; flex-direction: column; gap: var(--default-grid-baseline);` Radio + Label in einer Zeile mit `min-height: var(--default-clickable-area)` |
| `.avs-admin .avs-res__intro` | Body-Rolle, `max-width: none; margin: 0;` (zwei Klassen gegen `.section p`) |
| `.avs-admin .avs-res__hint`, `#avs-profile .avs-res__hint`, `#avs-compute .avs-res__hint`, `#avs-models .avs-res__hint` | `max-width: none; margin: 0; color: var(--color-text-maxcontrast); font-size: var(--font-size-small); line-height: var(--default-line-height); overflow-wrap: anywhere;` |
| `.avs-res__option .avs-res__hint`, `.avs-res__lock` | `padding-inline-start: calc(var(--default-grid-baseline) * 7);` |
| `.avs-res__lock`, `.avs-res__error` | `display: flex; align-items: flex-start; gap: var(--default-grid-baseline); margin: 0; color: var(--color-main-text); font-size: var(--font-size-small); line-height: var(--default-line-height);` Icon-Container wie `.avs-banner__icon` (Höhe `var(--default-line-height)`) |
| `.avs-res__lock svg` | `color: var(--color-text-maxcontrast);` |
| `.avs-res__error svg` | `color: var(--color-element-error);` |
| `.avs-res__badge` | `margin-inline-start: calc(var(--default-grid-baseline) * 2); padding: 0 var(--default-grid-baseline); border-radius: var(--border-radius-small); background-color: var(--color-background-hover); font-size: var(--font-size-small);` |
| `.avs-res__field` | `display: flex; flex-direction: column; align-items: flex-start; gap: var(--default-grid-baseline);` |
| `#avs-threads` | `width: calc(var(--default-grid-baseline) * 20); font-variant-numeric: tabular-nums;` |
| `.avs-res__times` | `display: flex; flex-wrap: wrap; gap: calc(var(--default-grid-baseline) * 4);` |
| `#avs-window-zone` | `max-width: 100%;` ab `(min-width: 768px)` `max-width: calc(var(--default-grid-baseline) * 80);` |
| `#avs-window-fields` | `display: flex; flex-direction: column; gap: calc(var(--default-grid-baseline) * 4); padding-inline-start: calc(var(--default-grid-baseline) * 7);` |
| `.avs-models` | `list-style: none; margin: calc(var(--default-grid-baseline) * 4) 0 0; padding: 0;` |
| `.avs-models__item` | `display: flex; flex-direction: column; gap: var(--default-grid-baseline); padding-block: calc(var(--default-grid-baseline) * 4);` `+ .avs-models__item { border-top: 1px solid var(--color-border); }` |
| `.avs-models__state` | `display: flex; flex-direction: column; gap: var(--default-grid-baseline);` Zustandszeile wie `.avs-res__lock`, aber Body-Rolle (15 px) |
| `.avs-models__progress` | `width: 100%; max-width: calc(var(--default-grid-baseline) * 80); accent-color: var(--color-primary-element);` |
| `.avs-models__offline` | `margin-block-start: calc(var(--default-grid-baseline) * 6);` |
| `#avs-models .avs-admin__subheading` | Bestand; vor "Weitere Bestandteile" `margin-block-start: calc(var(--default-grid-baseline) * 6);` |
| `.avs-models__others` | `list-style: disc; padding-inline-start: calc(var(--default-grid-baseline) * 5);` Label-Rolle |
| `@media (pointer: coarse)` | `#avs-profile .avs-res__option`, `#avs-compute input`, `#avs-compute select`, `#avs-compute-save`, `#avs-models .avs-admin__switch`: `min-height: calc(var(--default-grid-baseline) * 11);` |
| `#avs-profile [hidden], #avs-compute [hidden], #avs-models [hidden]` | `display: none;` (Bestandsregel erweitert) |

Prüfpunkt vor dem Bau: Gestalt von `input.radio` + `label`, `input[type=time]`, `select` und `progress` im Server-CSS von NC 33, 34 und 35 nachsehen (`core/css/inputs.scss`, wie in Phase 4). Hat `progress` dort keine Server-Gestalt, reicht `accent-color`; keine eigene Farbe, kein eigener Verlauf.

### Responsives Verhalten

| Breite | Vertrag |
|--------|---------|
| 375 px | Alles einspaltig. Von und Bis untereinander (`flex-wrap`), Zeitzone volle Breite. `progress` volle Breite. Lange Sätze (FR T47, T50, T88, T93) brechen um, kein horizontales Scrollen. Kennzeichen "Vorschlag" darf hinter dem Namen umbrechen |
| 768 px | Von und Bis nebeneinander (Abstand md), Zeitzone darunter, höchstens 320 px |
| 1280 px | wie 768 px; Lesespalte der Einstellungsseite vom Server |

---

## Copywriting Contract

**Status aller neuen Texte: ENTWURF, Owner-Freigabe ausstehend (siehe "Owner-Freigabe Phase 5"). Vor der Antwort werden keine Kataloge geschrieben.**

Regeln (aus 01-, 03- und 04-UI-SPEC.md): `de` und `de_DE` inhaltsgleich, **unpersönlich** (weder du noch Sie; Infinitiv wie "Erneut versuchen"). Französisch in Vous- bzw. unpersönlicher Form; **U+00A0 vor `:` `;` `?` `!`** (betrifft T37, T45, T56, T76, T88; im Katalog als echtes geschütztes Leerzeichen). Echte Umlaute, keine Gedankenstriche, keine Emojis, kein Ausrufezeichen, kein "BITV-konform". Englischer Text = l10n-Schlüssel. Platzhalter: `%s` bzw. `%1$s`, `%2$s` … (Profilname, formatierte Größe mit Einheit, Uhrzeit, Lizenz-Link); `%d` für ganze Zahlen. Größen kommen immer fertig mit Einheit aus T96. Profilnamen in Sätzen kommen aus T38 bis T40.

**Nummerierung:** Phase 4 endet bei T35. Phase 5 beginnt bei **T36**.

### Pflichtfelder (Template)

| Element | Copy (DE) |
|---------|-----------|
| Primary CTA | "Rechenzeit speichern" (T70); Profil und Offline speichern sofort beim Wechsel |
| Empty state heading | kein eigener: der Abschnitt hat immer Inhalt. Ohne Fenster steht "Immer" (T59) gewählt, Modelle ohne Bedarf zeigen T79 |
| Empty state body | Modell ohne Bedarf: "Für das Profil %s nicht nötig, wird nicht geladen." (T79) |
| Error state | Unter Mindest-RAM: "Zu wenig Arbeitsspeicher" / "Die App braucht mindestens %1$s, verfügbar sind %2$s. Sie transkribiert deshalb nichts, Nextcloud läuft normal weiter. Mehr Arbeitsspeicher für den Container einstellen und das Backend neu starten." (T49/T50); Backend still: T53 |
| Destructive confirmation | keine: Phase 5 hat keine zerstörende Aktion in der Oberfläche (Profilwechsel löscht nichts, Offline löscht nichts; das Aufräumen alter Volume-Kopien nach D-05-14 läuft ohne UI und nur bei gleichem sha256 im Image) |

### Neue Texte DE / EN / FR (Entwurf)

| Nr. | Verwendung | DE | EN | FR |
|-----|------------|----|----|----|
| T36 | `h2` + `legend` Profil | Transkriptionsprofil | Transcription profile | Profil de transcription |
| T37 | Einleitung (R1, R3) | Vorschlag für diesen Server: %1$s. Für die App sind %2$s Arbeitsspeicher verfügbar. | Suggested for this server: %1$s. %2$s of memory is available to the app. | Suggestion pour ce serveur : %1$s. L'application dispose de %2$s de mémoire vive. |
| T38 | Profilname | Schnell | Fast | Rapide |
| T39 | Profilname | Ausgewogen | Balanced | Équilibré |
| T40 | Profilname | Qualität | Quality | Qualité |
| T41 | Beschreibung Schnell | Parakeet für alle Dateien. Unsichere Stellen rechnet Whisper turbo nach, wenn der Speicher reicht. | Parakeet for all files. Whisper turbo recomputes uncertain passages when memory allows. | Parakeet pour tous les fichiers. Whisper turbo recalcule les passages incertains si la mémoire le permet. |
| T42 | Beschreibung Ausgewogen | Parakeet und Whisper turbo für alle Dateien, zu einem Text vereint. | Parakeet and Whisper turbo for all files, combined into one text. | Parakeet et Whisper turbo pour tous les fichiers, réunis en un seul texte. |
| T43 | Beschreibung Qualität | Wie Ausgewogen, deutsche Aufnahmen zusätzlich mit Whisper large-v3. Am langsamsten. | Like Balanced, with Whisper large-v3 in addition for German recordings. Slowest. | Comme Équilibré, avec en plus Whisper large-v3 pour les enregistrements en allemand. Le plus lent. |
| T44 | Bedarf (frei) | Braucht %s Arbeitsspeicher. | Needs %s of memory. | Nécessite %s de mémoire vive. |
| T45 | Sperrgrund (D-05-02) | Gesperrt: braucht %1$s, verfügbar %2$s. | Locked: needs %1$s, %2$s available. | Verrouillé : nécessite %1$s, %2$s disponibles. |
| T46 | Kennzeichen | Vorschlag | Suggested | Suggéré |
| T47 | Rückfall-Banner (R3) | Das gewählte Profil %1$s passt nicht mehr in den Arbeitsspeicher (braucht %2$s, verfügbar %3$s). Die App rechnet mit %4$s, bis wieder genug Speicher frei ist. | The chosen profile %1$s no longer fits into memory (needs %2$s, %3$s available). The app uses %4$s until enough memory is free again. | Le profil choisi %1$s ne tient plus en mémoire (il nécessite %2$s, %3$s disponibles). L'application utilise %4$s jusqu'à ce qu'assez de mémoire soit à nouveau libre. |
| T48 | Mindest-RAM (D-05-09) | Mindestbedarf der App: %s Arbeitsspeicher. | The app needs at least %s of memory. | L'application nécessite au moins %s de mémoire vive. |
| T49 | Banner-Titel (R2) | Zu wenig Arbeitsspeicher | Not enough memory | Mémoire vive insuffisante |
| T50 | Banner-Text (R2) | Die App braucht mindestens %1$s, verfügbar sind %2$s. Sie transkribiert deshalb nichts, Nextcloud läuft normal weiter. Mehr Arbeitsspeicher für den Container einstellen und das Backend neu starten. | The app needs at least %1$s, %2$s is available. It therefore transcribes nothing, Nextcloud keeps running normally. Give the container more memory and restart the backend. | L'application nécessite au moins %1$s, %2$s sont disponibles. Elle ne transcrit donc rien, Nextcloud continue de fonctionner normalement. Attribuez plus de mémoire vive au conteneur et redémarrez le backend. |
| T52 | Status 409 Profil | Nicht gespeichert. Dieses Profil ist inzwischen gesperrt. | Not saved. This profile has been locked in the meantime. | Non enregistré. Ce profil a été verrouillé entre-temps. |
| T53 | Banner R9 | Profil, Rechenzeit und Zustand der Modelle sind gerade nicht abrufbar, weil das Backend nicht antwortet. Die Seite später neu laden. | Profile, computing time and model state cannot be loaded right now because the backend does not respond. Reload the page later. | Le profil, le temps de calcul et l'état des modèles ne sont pas disponibles pour le moment, car le backend ne répond pas. Rechargez la page plus tard. |
| T54 | `h2` Rechenzeit | Rechenzeit | Computing time | Temps de calcul |
| T55 | Label Threads | Threads für die Erkennung | Threads for recognition | Threads pour la reconnaissance |
| T56 | Hinweis Threads (`%1$d` CPUs, `%2$d` Standard) | Nutzbare CPUs: %1$d. Standard und Höchstwert: %2$d. Weniger Threads entlasten Nextcloud, die Transkription dauert dann länger. | Usable CPUs: %1$d. Default and maximum: %2$d. Fewer threads leave more room for Nextcloud, transcription then takes longer. | Processeurs utilisables : %1$d. Valeur par défaut et maximum : %2$d. Moins de threads ménagent Nextcloud, la transcription prend alors plus de temps. |
| T57 | Fehler Threads | Eine ganze Zahl von 1 bis %d eingeben. | Enter a whole number from 1 to %d. | Saisissez un nombre entier de 1 à %d. |
| T58 | `legend` Fenster | Wann gerechnet wird | When to compute | Quand calculer |
| T59 | Radio | Immer | Always | Toujours |
| T60 | Radio | Nur im Zeitfenster | Only within a time window | Uniquement dans une plage horaire |
| T61 | Label | Von | From | De |
| T62 | Label | Bis | To | À |
| T63 | Label | Zeitzone | Time zone | Fuseau horaire |
| T64 | Hinweis Fenster (D-05-03, D-05-04, D-05-12) | Über Mitternacht geht, etwa 22:00 bis 06:00. Das Fenster gilt für jede Transkription, auch für Vorschauen. Am Fensterende wird das laufende Stück von etwa 10 Minuten Aufnahme fertig gerechnet, danach pausiert die App bis zum nächsten Fenster. Neue Dateien werden auch außerhalb erfasst und später transkribiert. | A window across midnight works, for example 22:00 to 06:00. The window applies to every transcription, previews included. At the end of the window the current piece of about 10 minutes of recording is finished, then the app pauses until the next window. New files are registered outside the window too and transcribed later. | Une plage qui passe minuit est possible, par exemple de 22:00 à 06:00. La plage s'applique à chaque transcription, aperçus compris. À la fin de la plage, le segment en cours d'environ 10 minutes d'enregistrement est terminé, puis l'application fait une pause jusqu'à la plage suivante. Les nouveaux fichiers sont aussi pris en compte en dehors de la plage et transcrits plus tard. |
| T65 | Fehler Fenster | Beginn und Ende müssen verschieden sein. | Start and end must differ. | Le début et la fin doivent être différents. |
| T66 | Fehler Fenster | Eine Uhrzeit eingeben. | Enter a time. | Saisissez une heure. |
| T67 | Fehler Fenster | Diese Zeitzone ist unbekannt. Eine aus der Liste wählen. | This time zone is unknown. Choose one from the list. | Ce fuseau horaire est inconnu. Choisissez-en un dans la liste. |
| T68 | Statuszeile offen | Das Zeitfenster ist offen bis %s. | The time window is open until %s. | La plage horaire est ouverte jusqu'à %s. |
| T69 | Statuszeile geschlossen | Das Zeitfenster ist geschlossen und öffnet um %s. | The time window is closed and opens at %s. | La plage horaire est fermée et s'ouvre à %s. |
| T70 | Knopf (Primary CTA) | Rechenzeit speichern | Save computing time | Enregistrer le temps de calcul |
| T71 | `h2` Modelle | Modelle und Lizenzen | Models and licenses | Modèles et licences |
| T72 | Parakeet (`%1$s` = Link CC-BY-4.0) | Von NVIDIA, Lizenz %1$s. Von k2-fsa/sherpa-onnx in eine int8-Fassung umgewandelt, sonst unverändert. | By NVIDIA, license %1$s. Converted to int8 by k2-fsa/sherpa-onnx, otherwise unchanged. | Par NVIDIA, licence %1$s. Converti en int8 par k2-fsa/sherpa-onnx, sans autre modification. |
| T73 | Silero (`%1$s` = Link MIT) | Vom Silero-Team, Lizenz %1$s. | By the Silero team, license %1$s. | Par l'équipe Silero, licence %1$s. |
| T74 | turbo (`%1$s`, `%2$s` = Link MIT) | Von OpenAI, Lizenz %1$s. CTranslate2-Fassung von deepdml, Lizenz %2$s. | By OpenAI, license %1$s. CTranslate2 version by deepdml, license %2$s. | Par OpenAI, licence %1$s. Version CTranslate2 par deepdml, licence %2$s. |
| T75 | large-v3 (`%1$s` = Apache-2.0, `%2$s` = MIT; D-05-15) | Gewichte von OpenAI, laut Modellkarte Lizenz %1$s. CTranslate2-Fassung von Systran, Lizenz %2$s. | Weights by OpenAI, license %1$s according to the model card. CTranslate2 version by Systran, license %2$s. | Poids par OpenAI, licence %1$s selon la fiche du modèle. Version CTranslate2 par Systran, licence %2$s. |
| T76 | Größe | Größe: %s | Size: %s | Taille : %s |
| T77 | M1 | Im Image enthalten. | Included in the image. | Inclus dans l'image. |
| T78 | M2 | Vorhanden, Prüfsumme bestätigt. | Present, checksum confirmed. | Présent, somme de contrôle confirmée. |
| T79 | M3 (`%s` = Profilname) | Für das Profil %s nicht nötig, wird nicht geladen. | Not needed for the profile %s, not downloaded. | Inutile pour le profil %s, non téléchargé. |
| T80 | M4 | Wartet auf den Download. | Waiting for the download. | En attente du téléchargement. |
| T81 | M5 | Wird geladen, %1$s von %2$s. | Downloading, %1$s of %2$s. | Téléchargement en cours, %1$s sur %2$s. |
| T83a | M7 | Die geladene Datei hatte eine falsche Prüfsumme und wurde verworfen. Ein neuer Versuch folgt automatisch. | The downloaded file had a wrong checksum and was discarded. Another attempt follows automatically. | Le fichier téléchargé avait une somme de contrôle incorrecte et a été rejeté. Une nouvelle tentative suivra automatiquement. |
| T83b | M8 (danach `code` occ-Befehl) | Die abgelegte Datei hat eine falsche Prüfsumme und wird nie geladen. Die richtige Datei ablegen und danach prüfen mit | The placed file has a wrong checksum and is never loaded. Place the correct file, then check it with | Le fichier déposé a une somme de contrôle incorrecte et ne sera jamais chargé. Déposez le bon fichier, puis vérifiez-le avec |
| T84 | M9 | Fehlt. Im Offline-Modus lädt die App nichts, die Datei muss abgelegt werden. | Missing. In offline mode the app downloads nothing, the file has to be placed. | Manquant. En mode hors ligne, l'application ne télécharge rien, le fichier doit être déposé. |
| T85 | M10 | Download gescheitert. Ein neuer Versuch folgt automatisch. | Download failed. Another attempt follows automatically. | Échec du téléchargement. Une nouvelle tentative suivra automatiquement. |
| T86 | M11 (`%s` = Größe) | Zu wenig Speicherplatz für den Download. Nötig sind %s frei. | Not enough storage space for the download. %s of free space is needed. | Espace de stockage insuffisant pour le téléchargement. Il faut %s d'espace libre. |
| T87 | Label Offline | Offline-Modus, keine Verbindung ins Internet | Offline mode, no connection to the internet | Mode hors ligne, aucune connexion à Internet |
| T88 | Hinweis Offline (danach `code` occ-Befehl, dann Link T89) | Die App lädt dann keine Modelle. Whisper-Dateien für das gewählte Profil selbst ablegen und danach prüfen mit | The app then downloads no models. Place the Whisper files for the chosen profile yourself, then check them with | L'application ne télécharge alors aucun modèle. Déposez vous-même les fichiers Whisper du profil choisi, puis vérifiez-les avec |
| T89 | Link README | Anleitung zum Offline-Betrieb | Guide to offline operation | Guide du fonctionnement hors ligne |
| T90 | Durch Deploy-Option gesetzt | Durch die Deploy-Option AVS_OFFLINE gesetzt. Ändern nur über die Deploy-Optionen des Backends. | Set by the deploy option AVS_OFFLINE. It can only be changed in the deploy options of the backend. | Défini par l'option de déploiement AVS_OFFLINE. Modifiable uniquement dans les options de déploiement du backend. |
| T91 | `h3` | Weitere Bestandteile | Other components | Autres composants |
| T92 | FFmpeg (`%1$s` = Link LGPL-2.1-or-later) | FFmpeg zum Dekodieren, LGPL-Build, Lizenz %1$s. | FFmpeg for decoding, LGPL build, license %1$s. | FFmpeg pour le décodage, build LGPL, licence %1$s. |
| T93 | PyAV-Codecs (`%1$s` = Link GPL-2.0-or-later; D-05-15) | PyAV bringt eigene FFmpeg-Bibliotheken mit den Codecs libx264 und libx265 mit, Lizenz %1$s. Die App dekodiert damit nicht, sie liegen nur als Abhängigkeit von faster-whisper im Image. | PyAV ships its own FFmpeg libraries with the codecs libx264 and libx265, license %1$s. The app does not decode with them, they are only in the image as a dependency of faster-whisper. | PyAV fournit ses propres bibliothèques FFmpeg avec les codecs libx264 et libx265, licence %1$s. L'application ne les utilise pas pour décoder, elles ne se trouvent dans l'image qu'en tant que dépendance de faster-whisper. |
| T94 | Link THIRD-PARTY.md | Alle Drittlizenzen in THIRD-PARTY.md | All third-party licenses in THIRD-PARTY.md | Toutes les licences tierces dans THIRD-PARTY.md |
| T95 | Banner R10 | Der Download-Stand konnte nicht aktualisiert werden. Angezeigt ist der letzte bekannte Stand. | The download progress could not be refreshed. Shown is the last known state. | L'avancement du téléchargement n'a pas pu être actualisé. L'état affiché est le dernier connu. |
| T96 | Einheit (`%s` = Zahl mit einer Nachkommastelle) | %s GB | %s GB | %s Go |

T51 und T82 bleiben frei (T51: Gruppenname nutzt T36; T82: "Wird geprüft…" nutzt den Bestandsschlüssel `Checking…`).

Sätze, die mit einem Befehl enden (T83b, T88): Das Template setzt nach dem Satz ein Leerzeichen und `<code class="avs-admin__command">occ audio_video_search:models --verify</code>`, dann einen Punkt; bei T88 folgt ein Leerzeichen und der Link T89 auf `https://github.com/street1983nk/nextcloud-audio-video-search#offline` (README DE; die EN- und FR-README tragen denselben Anker `offline`). Gleiches Muster wie Bestand "No test result yet. Create one with:".

### Unverändert weiterverwendete Texte

| Schlüssel | DE | EN | FR |
|-----------|----|----|----|
| Saved | Gespeichert | Saved | Enregistré |
| Not saved. Try again. | Nicht gespeichert. Erneut versuchen. | Not saved. Try again. | Non enregistré. Réessayez. |
| Checking… | Wird geprüft… | Checking… | Vérification… |

(Wortlaut der Bestandsschlüssel gilt wie in den Katalogen; diese Tabelle legt nichts neu fest.)

**Wahrheitsbedingungen für den Planer** (Satz nur bauen, wenn er im Code stimmt):
- T45/T47/T50: Zahlen aus derselben Messung wie die Sperre (`headroom_bytes` ohne laufendes Kind), Rundung Bedarf auf, verfügbar ab; Test, dass eine Sperre nie gleiche Zahlen zeigt.
- T47 "bis wieder genug Speicher frei ist": gespeicherte Wahl bleibt erhalten, `effective` kehrt beim nächsten Profilrechner-Lauf (Start, Erneut prüfen) von selbst zur Wahl zurück.
- T50 "Nextcloud läuft normal weiter" und "transkribiert nichts": kein Kind startet unter `minimumBytes` (CI `--memory=2g`, Kriterium 2). `minimumBytes` kommt aus der Wave-0-Messung (D-05-09), nie als Zahl in den Katalog.
- T41 bis T43 beschreiben die Profile, wie Phase 6 sie rechnet. Liefert ein Store-Release Phase 5 ohne Phase 6 aus, braucht es vorher einen Owner-Entscheid zu diesen Sätzen.
- T64 "auch für Vorschauen", "laufende Stück fertig", "neue Dateien werden erfasst": Fenster-Gate vor jedem Claim, Pause an der Stückgrenze (`yield_preview`), capture ungebremst (D-05-12); je ein Test.
- T77 "Im Image enthalten": Dockerfile-Stage mit `sha256sum -c` (RES-06), Test in `test_dockerfile.py`.
- T78 "Prüfsumme bestätigt": Gesamt-sha256 gegen Katalog in diesem Prozess geprüft (kein gespeichertes Urteil, Research Pattern 5).
- T83a "neuer Versuch folgt automatisch", T85: Backoff im Modell-Worker; T83b "wird nie geladen": Test, dass `WhisperModel` nie mit einem Verzeichnis mit falschem Hash startet.
- T84/T87 "keine Verbindung ins Internet": Netzwerkmitschnitt mit Positivkontrolle (Kriterium 4).
- T93 "dekodiert damit nicht": Boundary-Test, dass kein Modul der App `av` importiert.
- T56 "Höchstwert": PHP und ExApp lehnen Werte über `standard` ab.

Dreisprachigkeits-Test und Umlaut-/Gedankenstrich-Audit decken alle neuen Schlüssel in `de`, `de_DE`, `en`, `fr` (`.json` und `.js`) ab; zusätzlich ein Test, dass FR vor `:` U+00A0 trägt. Text-Gate "BITV-konform" (jede Schreibweise) bleibt aktiv. Ausnahme Umlaut-Regel: Klassen, IDs, Routen, Profil-IDs (`fast`, `balanced`, `quality`), Modell-IDs, `AVS_OFFLINE`, occ-Befehl bleiben ASCII.

---

## Prüfvertrag für die Abnahme (Playwright, gemeinsam mit dem Owner)

Grundmatrix "6": Breiten 375, 768, 1280 px, je hell und dunkel. Sprache DE; FR zusätzlich bei 375 px hell für die längsten Texte. NC 33 und 35 Vollmatrix, NC 34 Stichprobe R1 bei 1280 hell. Hochkontrast-Theme bei 1280 px für R1 und R2. Erweiterung von `ci/playwright/admin.spec.ts`; Zustände, die die CI-Instanz nicht live erzeugen kann (R2, R3, M5 bis M11, R10), entstehen über einen Test-Schalter der ExApp, der nur im CI-Image wirkt und den `GET /resources` mit einem festen Snapshot beantwortet (nie im Release-Image; Test in `test_dockerfile.py`), nicht über eine nachgebaute Seite.

| ID | Fläche / Zustand | Screenshots | Zusätzliche Prüfung |
|----|------------------|-------------|---------------------|
| R1 | Profil normal, Qualität gesperrt | 6 + FR 375 + Hochkontrast | T37 mit Profil und Zahl; "Vorschlag" genau einmal; gesperrtes Radio `disabled`, T45 über `aria-describedby` erreichbar, Zahlen ungleich; Wechsel Schnell/Ausgewogen speichert ("Gespeichert"), Neuladen zeigt die Wahl; Klickfläche >= `--default-clickable-area`, bei coarse 44 px |
| R1a | gesperrtes Profil per Direktaufruf | kein Bild | `POST admin/resources` mit gesperrtem Profil = 409 `profile_locked`, Wert unverändert; Nicht-Admin = 403 |
| R2 | unter Mindest-RAM | 1280 hell + dunkel, 375 hell, FR 375, Hochkontrast | Fehler-Banner T49/T50 mit Zahlen; alle Radios `disabled`; kein T37 |
| R3 | Rückfall | 1280 hell, 375 hell | Warn-Banner T47 mit beiden Profilnamen und Zahlen; gewählte Option `checked` + `disabled` |
| R9 | Backend gestoppt | 1280 hell + dunkel | T53 einmal; kein `#avs-compute`; Lizenzen T72 bis T94 sichtbar; keine Zustände/Größen |
| C1 | Rechenzeit Standard ("Immer") | 6 | Fensterfelder verborgen; Threads = Standard, `max` = Standard |
| C2 | Fenster 22:00 bis 06:00 Europe/Berlin gespeichert | 6 + FR 375 | Statuszeile T68/T69 mit richtiger Ortszeit; Neuladen zeigt Werte; ExApp-Zustand gleich |
| C3 | Fehler: Threads 0, Threads > Standard, Start = Ende, leere Zeit | 1280 hell, 375 hell | richtige Fehlerzeile, `aria-invalid`, `aria-describedby` enthält die Fehler-ID, Fokus auf erstem ungültigem Feld, keine Anfrage gesendet; dieselben Werte per Direkt-POST = 400 |
| C4 | Tastatur | kein Bild | ganze Seite ohne Maus bedienbar: Radios per Pfeiltaste, Speichern per Enter, Fokus immer sichtbar |
| M-A | Modelle Ausgewogen fertig | 6 + Hochkontrast | Parakeet/Silero T77, turbo T78, large-v3 T79 mit "Ausgewogen"; Größen 1,6 GB und 3,1 GB (fr "Go") |
| M-B | Download läuft (M4, M5, M6 nacheinander) | 1280 hell + dunkel, 375 hell | `progress` `value`/`max` passen zu T81; Polling alle 5 s, stoppt nach M2; Fokus bleibt; `#avs-models-live` sagt nur den Wechsel an |
| M-C | M7, M8, M9, M10, M11 | je 1280 hell | richtiger Satz und Icon; keine URL, kein Host, kein Pfad im DOM |
| M-D | Offline umschalten, Offline per `AVS_OFFLINE` | 1280 hell + dunkel, 375 hell | Schalter speichert; bei Env `checked` + `disabled` + T90; occ-Befehl als `code`; Link T89 zeigt auf den README-Anker |
| L1 | Lizenzen | 1280 hell, FR 375 | NVIDIA + CC-BY-4.0 sichtbar; jeder Lizenz-Link mit festem Ziel aus der Tabelle; Link THIRD-PARTY.md auf `blob/main/THIRD-PARTY.md` |
| R10 | Polling scheitert dreimal | 1280 hell | Warn-Banner T95, Polling gestoppt |
| A11y | alle R-, C-, M-Seiten | kein Bild | axe ohne `serious`/`critical` |

**Kontrast-Gate** (axe-core plus berechneter Kontrast im Playwright-Lauf, hell, dunkel, Hochkontrast):
- Label-Rolle in `--color-text-maxcontrast` auf `--color-main-background` (13 px): mindestens 4,5:1. Fällt der Wert darunter, wechselt die Rolle auf `--color-main-text` (kein eigener Farbwert).
- Sperrgrund T45 und Feldfehler (`--color-main-text`): mindestens 4,5:1.
- Icons `lock-outline`, `error`, `warning`, `success`, `download` gegen Grund: mindestens 3:1 (WCAG 1.4.11).
- Rand von Zahlen-, Zeit- und Auswahlfeld, Radio-Kreis und Checkbox, Fokusring: mindestens 3:1.
- `progress`: Fortschritt steht immer auch als Text T81, deshalb ist der Balken kein alleiniger Träger; trotzdem gefüllter Teil gegen Spur mindestens 3:1 messen und Befund melden.
- Banner: Bestandspaare, Messung wie Phase 1.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | keine (shadcn nicht verwendet) | not applicable |
| Drittanbieter | keine | not applicable |

Keine neuen Frontend-Pakete, kein npm, keine Vue-Komponenten. Die faster-whisper-Pakete (D-05-10) sind Backend-Abhängigkeiten, nicht Teil der UI.

---

## Offene Gestaltungsfragen: Empfehlung + Begründung (Owner reviewt als Ganzes)

1. **O1 Texte T36 bis T96 freigeben?** Empfehlung: wie entworfen.
2. **O2 Anzeige in GB = 10^9 Bytes, Bedarf aufgerundet, verfügbar abgerundet?** Empfehlung: ja. Gleiche Einheit wie die Modellgrößen der Stack-Recherche (1,62 GB, 3,09 GB); die Rundung verhindert eine Sperre mit gleich aussehenden Zahlen. Folge: Ein Bedarf von 4,5 GiB erscheint als "4,9 GB".
3. **O3 Profil und Offline speichern sofort, Rechenzeit mit Knopf?** Empfehlung: ja. Sofort ist das Server-Muster (wie der Debug-Schalter); Von, Bis und Zone sind nur zusammen gültig.
4. **O4 Gesperrte Profile als `disabled` mit sichtbarem Grund, nicht ausgeblendet?** Empfehlung: ja. Der Admin sieht, was mit mehr Speicher ginge und warum (D-05-02 "Grund mit Zahlen").
5. **O5 Kein Modellordner auf der Seite, statt dessen Link "Anleitung zum Offline-Betrieb" in die README?** Empfehlung: ja. Hält die Regel "kein Pfad auf der Admin-Seite" (T-01-34) und die Anleitung kann den `docker cp`-Weg je Installationsart erklären. Alternative auf Zuruf: Ordner als `code` im Hinweis.
6. **O6 Modell-Zustand und Lizenzen in einem Abschnitt "Modelle und Lizenzen"?** Empfehlung: ja. D-05-08 nennt den Abschnitt so; je Modell stehen Herkunft, Lizenz, Größe und Download-Stand beieinander, kein vierter Abschnitt.
7. **O7 Statuszeile "Zeitfenster offen bis / öffnet um" (T68/T69)?** Empfehlung: ja. Ein Satz, der zeigt, dass die Zone richtig verstanden wurde (Pitfall 4); keine Zustandsseite (Phase 9).
8. **O8 Fensterfelder bei "Immer" verborgen, beim ersten Wechsel mit 22:00 bis 06:00 vorbelegt?** Empfehlung: ja (Beispiel aus D-05-03).
9. **O9 Lizenz-IDs als Links auf die Lizenztexte, THIRD-PARTY.md auf `blob/main`?** Empfehlung: ja. Alternative: Link auf den Release-Tag der installierten Version (genauer, aber bei jedem Release neu).
10. **O10 Profilbeschreibungen T41 bis T43 schon in Phase 5 im Zielwortlaut von Phase 6?** Empfehlung: ja, solange kein Store-Release zwischen Phase 5 und 6 liegt (Wahrheitsbedingung).

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

## Owner-Freigabe Phase 5

**Stand: FREIGEGEBEN vom Owner am 18.11.2026 ("Ok"): T36 bis T96 wie entworfen, O1 bis O10 nach Empfehlung.** Checker 18.11.: APPROVED, 0 Blocker. Die FLAGs übernimmt der Planer:
- Reihenfolge Banner, dann Vorschlag, dann Optionen
- 20 px Einzug durch 24 px ersetzen oder begründen
- FR U+00A0 vor ":" in T37/T45/T56/T76 im Katalog

Bisheriger Vermerk: Wie in Phase 4 (Plan 04-03): Der Owner gibt T36 bis T96 und O1 bis O10 frei; Änderungen am Wortlaut werden wörtlich in die Copywriting-Tabelle übernommen. Erst danach schreibt ein Plan die Kataloge `php/l10n/{de,de_DE,en,fr}.{json,js}`.

### Owner-Antwort

(ausstehend)
