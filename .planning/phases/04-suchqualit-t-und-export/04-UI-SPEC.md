---
phase: 4
slug: suchqualit-t-und-export
status: approved
shadcn_initialized: false
preset: none
created: 2026-11-16
base_contract: .planning/phases/01-zwei-app-ger-st-und-integrationsbeweis/01-UI-SPEC.md
extends: .planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md
---

# Phase 4: UI Design Contract

> Visueller und Interaktionsvertrag für Phase 4 (Suchqualität und Export). Erstellt vom gsd-ui-researcher, geprüft vom gsd-ui-checker.
> Quellen: 04-CONTEXT.md (D-04-01 bis D-04-18, gelockt), 04-RESEARCH.md (Viewer-Befund, Download-Sperre, Ablage-Mechanik, Formate), 03-UI-SPEC.md (status approved, Texte T1 bis T12), 01-UI-SPEC.md (Basisvertrag), Bestand `php/templates/play.php`, `php/css/play.css`, `php/js/play.js`, `php/lib/Controller/PageController.php`.

**Grundsatz: Dieser Vertrag ist ein Nachtrag.** Alles aus 01-UI-SPEC.md und 03-UI-SPEC.md gilt unverändert (Design System, Abstände, Typografie, Farben, Banner, Ausschnitt-Block A1 bis A13, Leck-Regel, Texte T1 bis T12). Phase 4 ändert genau drei Stellen:

1. **Abspielseite, neuer Abschnitt "Untertitel-Entwurf"** unter dem Ausschnitt-Block: drei Download-Knöpfe SRT, VTT, TXT (D-04-01 bis D-04-04), Ablage als Nebendatei (D-04-05 bis D-04-08), Teil-Hinweis (D-04-17), Sperr-Hinweis (SRCH-04).
2. **Abspielseite, Medium:** Untertitel-Spur `<track>` am Video (D-04-18).
3. **Dateiinhalte:** Kopfzeile der TXT-Datei und `NOTE`-Block der VTT-Datei (D-04-03, EXP-04).

Unified Search (Fläche 1) bekommt **keine** sichtbare Änderung durch die App: Zahlen, Wortformen und Komposita ändern nur, *was* gefunden wird (D-04-11 bis D-04-14); die Filter-Bedienelemente rendert der Web-Client, die App meldet nur `since`, `until`, `person` (SRCH-06). Das Trefferbild aus 03-UI-SPEC.md bleibt byte-gleich.

Nicht in Phase 4: Files-Kontextmenü (D-04-01), Menü statt Knöpfen (D-04-02), Veraltungs-Hinweis für abgelegte Nebendateien (D-04-08), Sprachwahl durch den Nutzer (D-04-15 entscheidet automatisch), Korrektur-Editor und "geprüft" (Phase 10), Fortschrittsbalken (Phase 9), Viewer-Integration (NC 36, nur README).

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (PHP-Template plus reines Browser-JS ohne Bundler; shadcn-Gate nicht anwendbar, kein React/Vite) |
| Preset | not applicable |
| Component library | none: Nextcloud-Server-CSS. Native `<button>` und `<a class="button">` erhalten die Server-Knopfgestalt (gleiche Gestalt wie der bestehende Knopf "Zu %s springen") |
| Icon library | Material Design Icons (Pictogrammers, Apache-2.0) als Pfaddaten in Inline-SVG, 20 px, `aria-hidden="true" focusable="false"`, `fill="currentColor"`, `viewBox="0 0 24 24"`. Neu: `download` auf den drei Download-Knöpfen, `file-plus` auf dem Ablage-Knopf, `check-circle-outline` im Erfolgs-Banner E1. Fehler nutzen das vorhandene Icon `error` aus `play.php`. Pfaddaten unten, geprüft am 2026-11-16 gegen Templarian/MaterialDesign-SVG (`master/svg/<name>.svg`, Apache-2.0) |
| Icon `download` | `M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z` (stimmt mit dem bisherigen Eintrag überein) |
| Icon `file-plus` | `M14 2H6C4.89 2 4 2.89 4 4V20C4 21.11 4.89 22 6 22H13.81C13.28 21.09 13 20.05 13 19C13 15.69 15.69 13 19 13C19.34 13 19.67 13.03 20 13.08V8L14 2M13 9V3.5L18.5 9H13M23 20H20V23H18V20H15V18H18V15H20V18H23V20Z` |
| Icon `check-circle-outline` | `M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M12 20C7.59 20 4 16.41 4 12S7.59 4 12 4 20 7.59 20 12 16.41 20 12 20M16.59 7.58L10 14.17L7.41 11.59L6 13L10 17L18 9L16.59 7.58Z` |
| Font | Server-Schrift über `var(--font-face)` |

Verbindliche Regeln aus 01-UI-SPEC.md gelten weiter: nur Nextcloud-CSS-Variablen, kein Hex/RGB, kein `!important`, kein `outline: none`, kein `style`-Attribut, keine Inline-Skripte (CSP), flach (keine Schatten, keine Verläufe, keine Karte in Karte), jeder Text über `$l->t()`/`$l->n()`, jede Fremdangabe mit `p()`, Klassen-Präfix `avs-`. `play.js` baut weiterhin **kein Markup aus Strings**: Es schaltet `hidden`, setzt `disabled`/`aria-busy`, verschiebt den Fokus und setzt Dateinamen nur über `textContent`.

---

## Spacing Scale

Unverändert aus 01-UI-SPEC.md (`calc(var(--default-grid-baseline) * n)`, Grundwert 4 px). Alle Werte Vielfache von 4.

| Token | Value | Usage in Phase 4 |
|-------|-------|------------------|
| xs | 4px | Abstand Icon zu Text im Knopf (`gap`) |
| sm | 8px | Spaltenabstand innerhalb `section.avs-export`; Abstand zwischen den drei Download-Knöpfen (`gap`, auch beim Umbruch); Abstand Ablage-Beschreibung zu Ablage-Knopf |
| md | 16px | Abstand Ausschnitt-Block zum Export-Abschnitt (bestehender Spalten-`gap` der `.avs-play__column`); Abstand Download-Zeile zum Ablage-Block (`margin-block-start` sm + Spalten-gap sm = 16) |
| lg | 24px | Bestand (Seitenrand ab 768 px) |
| xl | 32px | Bestand (oberer Abstand ab 768 px) |

Nicht genutzt: 48 px, 64 px.
Exceptions: Klickflächen. Alle neuen Knöpfe `min-height: var(--default-clickable-area)`, bei `(pointer: coarse)` `calc(var(--default-grid-baseline) * 11)` = 44 px, gleiche Regel wie Bestand (`.avs-play__jump`, `.avs-banner__action`). Innenabstand der Knöpfe kommt vom Server-CSS, nicht aus der App.

---

## Typography

Unverändert: genau drei Größen (13, 15, 20 px), genau zwei Gewichte (400, 700), Zeilenhöhe nur `var(--default-line-height)`.

| Role | Size | Weight | Line Height | Neu in Phase 4 |
|------|------|--------|-------------|----------------|
| Body | 15px `var(--default-font-size)` | 400 | `var(--default-line-height)` | Teil-Hinweis `.avs-export__partial`, Knopf-Beschriftungen (Server-CSS), Texte in Ergebnis-Bannern |
| Label | 13px `var(--font-size-small)` | 400 | `var(--default-line-height)` | Erklärsatz `.avs-export__note`, Ablage-Beschreibung `.avs-export__hint`, Sperr-/Schreibrecht-Hinweis |
| Heading (Abschnitt) | 15px `var(--default-font-size)` | 700 | `var(--default-line-height)` | Abschnittstitel `h3.avs-export__title` "Untertitel-Entwurf" |
| Heading (Seite) | 20px | 700 | `var(--default-line-height)` | keine Änderung (Dateiname, `h2`) |

Begründung 15 px fett statt 20 px für den Abschnittstitel: 20 px trägt schon der Dateiname; ein zweiter 20-px-Titel würde den Export gleichrangig zur Aufnahme machen. Die Gliederung kommt aus `h2` > `h3`, nicht aus einer vierten Größe.

---

## Color

Unverändert aus 01-UI-SPEC.md.

| Role | Value | Usage in Phase 4 |
|------|-------|------------------|
| Dominant (60%) | `--color-main-background` | Seitengrund; der Export-Abschnitt liegt **ohne eigene Fläche** direkt auf dem Seitengrund (keine zweite graue Fläche unter dem grauen Ausschnitt-Block) |
| Secondary (30%) | `--color-background-hover` | nur Bestand (Ausschnitt-Block); Knopf-Hover kommt vom Server-CSS |
| Accent (10%) | `--color-primary-element` / `--color-primary-element-text` | **in Phase 4 nirgends neu** |
| Destructive | `--color-error` / `--color-error-text` | nur der Fehler-Banner bei Kollision und bei gescheiterter Ablage (Banner-Paar aus dem Bestand) |
| Erfolg | `--color-success` / `--color-success-text` | nur der Erfolgs-Banner nach der Ablage (Banner-Paar aus dem Bestand, `.avs-banner--success`) |

Gedämpfter Text `--color-text-maxcontrast`: nur `.avs-export__note` und `.avs-export__hint` (13 px).

Accent reserved for (unverändert): 1. die eine Aktion eines Admin-Banners, 2. der gesetzte Zustand der Debug-Checkbox. **Kein Akzent für die Download- oder Ablage-Knöpfe.** Begründung: Die drei Formate sind gleichrangig, keiner ist "die" Hauptaktion; die Hauptaktion der Seite bleibt die Wiedergabe. Ein farbiger Primärknopf würde einen Entwurf hervorheben, den der Nutzer erst prüfen soll.

Farbe ist nie alleiniger Bedeutungsträger: jeder Ergebnis-Banner hat Icon, Titel und Satz.

---

## Fläche 2: Abspielansicht (Erweiterung)

### Reihenfolge der Seite (neu fett)

```
h2 Dateiname
p  Startet bei 1:23
Banner (Bestand)
<video|audio> Medium               + NEU: <track> (nur Video, nur bei Export erlaubt)
div.avs-play__actions              (Bestand: Springen, In Dateien zeigen)
section.avs-excerpt                (Bestand, A1 bis A13 unverändert)
**section.avs-export**             (NEU, D-04-02: unter dem Hinweistext)
```

### Aufbau von `section.avs-export`

```
section.avs-export  aria-labelledby="avs-export-title"
  h3#avs-export-title.avs-export__title        Untertitel-Entwurf                     (T13)
  EINES von:
  [Zustand X1/X2: Export möglich]
    p.avs-export__note                          Erklärsatz                             (T14)
    p.avs-export__partial                       nur X2: Transkript bis <time>, ...     (T15)
    div.avs-export__downloads  role="group" aria-labelledby="avs-export-title"
      a.button.avs-export__download  href=…/export/{id}/srt   [Icon download] SRT herunterladen  (T16)
      a.button.avs-export__download  href=…/export/{id}/vtt   [Icon download] VTT herunterladen  (T17)
      a.button.avs-export__download  href=…/export/{id}/txt   [Icon download] TXT herunterladen  (T18)
    div.avs-export__sidecar
      EINES von:
        p.avs-export__hint                      Ablage-Beschreibung mit Zielname       (T20 bzw. T20b)
        button#avs-sidecar.avs-export__save  hidden   [Icon file-plus] Neben die Datei legen  (T19)
        div#avs-sidecar-result                  vorgerenderte, verborgene Ergebnis-Banner (E1 bis E7)
      ODER
        p.avs-export__hint                      Kein Schreibrecht                      (T23)
  [Zustand X3: Download gesperrt]
    p.avs-export__hint                          Sperr-Hinweis                          (T24)
```

Zustand X4 (kein Transkript) rendert den **ganzen Abschnitt nicht** (siehe Zustandstabelle).

### CSS (neu, in `play.css`)

| Selektor | Regeln |
|----------|--------|
| `.avs-export` | `display: flex; flex-direction: column; gap: calc(var(--default-grid-baseline) * 2);` keine Fläche, kein Rand, kein Radius |
| `.avs-export__title` | `margin: 0; font-size: var(--default-font-size); font-weight: 700; line-height: var(--default-line-height);` |
| `.avs-export__note`, `.avs-export__hint` | `margin: 0; color: var(--color-text-maxcontrast); font-size: var(--font-size-small); line-height: var(--default-line-height); overflow-wrap: anywhere;` |
| `.avs-export__partial` | `margin: 0; font-size: var(--default-font-size); line-height: var(--default-line-height); overflow-wrap: anywhere;` (Haupttextfarbe, kein Grau: der Hinweis ist inhaltlich wichtig) |
| `.avs-export__downloads` | `display: flex; flex-wrap: wrap; gap: calc(var(--default-grid-baseline) * 2);` |
| `.avs-export__download`, `.avs-export__save` | `display: inline-flex; align-items: center; gap: var(--default-grid-baseline); min-height: var(--default-clickable-area); margin: 0;` (Farbe, Rand, Hover, Fokusring vom Server-CSS) |
| `.avs-export__sidecar` | `display: flex; flex-direction: column; align-items: flex-start; gap: calc(var(--default-grid-baseline) * 2); margin-block-start: calc(var(--default-grid-baseline) * 2);` |
| `@media (pointer: coarse)` | `.avs-export__download, .avs-export__save` in die bestehende 44-px-Regel aufnehmen |
| `.avs-play__time` | bestehende `tabular-nums` gilt auch für die Zeit im Teil-Hinweis (gleiche Klasse am `<time>`) |

Prüfpunkt vor dem Bau: `<a class="button">` muss im Server-CSS von NC 33, 34 und 35 dieselbe Gestalt wie ein `<button>` bekommen. Fällt das in einer Version weg, bekommt `.avs-export__download` eigene Regeln nach dem Muster `.avs-banner__action` (Rand `2px solid var(--color-border-maxcontrast)`, Radius `var(--border-radius-element)`, Grund `var(--color-main-background)`, Hover `var(--color-background-hover)`), nie eine Akzentfarbe.

**Befund Prüfpunkt (2026-11-16, Quelle `nextcloud/server`, Datei `core/css/inputs.scss` per raw.githubusercontent.com):**

| Version | Fundstelle "Default global values" | Fundstelle "'Click' inputs" | Ergebnis |
|---------|-----------------------------------|-----------------------------|----------|
| NC 33 (`stable33`) | Zeile 72: `.button` in derselben Selektorliste wie `button:not(.button-vue, [class^="vs__"])` (ab Zeile 64) | Zeile 213: `.button` in derselben Liste wie `button:not(...)` (Liste ab Zeile 208) | gleiche Gestalt |
| NC 34 (`stable34`) | Zeile 63, Liste ab Zeile 56 | Zeile 204, Liste ab Zeile 198 | gleiche Gestalt |
| NC 35 (`stable35`) | Zeile 63 (Datei byte-gleich mit stable34) | Zeile 204 | gleiche Gestalt |

Die Regel ist klassenbasiert (`.button`), gilt also für `<a class="button">` genauso wie für `<button>`: Innenabstand `calc((var(--default-clickable-area) - 1lh) / 2) calc(3 * var(--default-grid-baseline))`, `min-height: var(--default-clickable-area)`, Grund `var(--color-primary-element-light)`, Text `var(--color-primary-element-light-text)`, Hover `var(--color-primary-element-light-hover)`, Fokusring `:focus-visible` (2px `--color-main-text`). Der Ersatz nach `.avs-banner__action` wird deshalb **nicht** gebraucht. Hinweis: Der Server-Standardknopf hat den hellen Primär-Ton (`--color-primary-element-light`), denselben wie der Bestandsknopf "Zu %s springen"; das ist die neutrale Server-Gestalt, nicht der Akzent `--color-primary-element` aus der Farbregel. Die Abnahme X1 prüft, dass beide Knöpfe gleich aussehen. Unterschied `<a>`: Die globale Link-Regel `a { text-decoration: none; color: var(--color-main-text); cursor: pointer; }` aus `core/css/styles.scss` ist in stable33, 34 und 35 gleich; der Link-Knopf bekommt also keine Unterstreichung, `.avs-export__download` braucht dafür keine eigene Regel.

### Zustände des Export-Abschnitts

Der Abschnitt erscheint nur im Seitenzustand "Bereit" (Medium sichtbar). In allen anderen Seitenzuständen (nicht verfügbar, keine Audio-/Videodatei, Wiedergabe gesperrt) fehlt er, genau wie der Ausschnitt-Block.

| Nr. | Zustand (`exportState`) | Bedingung (Controller, in dieser Reihenfolge) | Inhalt |
|-----|-------------------------|-----------------------------------------------|--------|
| X3 | `blocked` | `downloadAllowed === false` (Seite spielt trotzdem, weil `shareapi_allow_view_without_download` an ist). Geprüft **vor** jeder Container-Anfrage | Titel T13 + Hinweis T24. **Keine** Knöpfe, **kein** `<track>`, keine Export-URLs im DOM |
| X4 | `none` | Ausgeschlossen (Nutzer/Datei/Ausschlussfrage gescheitert), Container kennt die Datei nicht, kein fertiges Stück, Grund vorhanden (A6 bis A13), Container still | Abschnitt fehlt ganz. Der Ausschnitt-Block erklärt bereits, warum es keinen Text gibt |
| X2 | `partial` | Transkript vorhanden, Datei wird noch verarbeitet (`partial: true`), Endzeit des letzten fertigen Stücks bekannt | wie X1 plus Teil-Hinweis T15 mit Zeit `<time class="avs-play__time" datetime="PT…S">h:mm:ss / m:ss</time>` (gleiche Uhrformatierung wie "Startet bei") |
| X1 | `available` | Transkript vorhanden, nicht in Arbeit | T13, T14, drei Knöpfe, Ablage-Block |

**Verhältnis zu Phase 3 (geklärt 2026-11-16):** Es gibt **zwei** verschiedene Sperr-Zustände, die nicht verwechselt werden dürfen.

1. **Seitenzustand `download_blocked` (Phase 3, unverändert, 03-UI-SPEC "Zustände des Ausschnitt-Blocks"):** Die Freigabe sperrt den Download **und** der Server erlaubt Ansehen ohne Download nicht (`shareapi_allow_view_without_download` aus). Die Seite zeigt kein Medium, keinen Ausschnitt-Block und **keinen Export-Abschnitt**, auch keinen Titel T13 und keinen Satz T24.
2. **X3 (Phase 4, nur im Seitenzustand "Bereit"):** Der Server erlaubt Ansehen ohne Download, die Freigabe sperrt den Download. Das Medium spielt, der Ausschnitt-Block steht wie gewohnt, der Export-Abschnitt zeigt nur Titel T13 und Satz T24, ohne Knöpfe, Ablage, Spur oder Export-URL. Das Medium trägt `controlslist="nodownload"`, damit das Menü des nativen Players keinen Eintrag "Herunterladen" anbietet (Owner, UI-Abnahme 16.11.2026). Gesetzt wird es fail-closed wie beim Export: bei jedem Urteil außer einem klaren "erlaubt", also auch beim unentscheidbaren Attribut (Punkt 3); bei X1, X2, X4 mit erlaubtem Download nicht. Das ist eine Bedien-Hürde, keine technische Sperre: das Medium wird zum Abspielen übertragen.
3. **Unentscheidbares Freigabe-Attribut:** Lässt sich beim Export nicht sicher bestimmen, ob Download erlaubt ist (Attribut fehlt, Fehler beim Lesen), gilt X4: Der Abschnitt fehlt ganz. Nie erscheint dann ein Sperrsatz T24, der eine Sperre behauptet, die nicht feststeht, und nie erscheinen Knöpfe.

Leck-Regel (aus 03-UI-SPEC.md, erweitert): X4 ist für "ausgeschlossen", "nicht active" und "unbekannt" **byte-gleich** (kein Abschnitt). X3 hängt nur am Freigabe-Attribut, nicht am Container; der Sperr-Hinweis verrät daher nichts über Transkript oder Ausschluss. Der Controller fragt den Container für X1/X2 über denselben Weg und unter denselben Bedingungen wie für den Ausschnitt.

Datenvertrag Controller -> Template (neu): `exportState` (`available|partial|blocked|none`), `exportUntilClock`, `exportUntilIso` (nur X2), `exportUrls` (`srt|vtt|txt`, nur X1/X2), `sidecarAllowed` (bool, `Folder::isCreatable()` des Elternordners als Nutzer), `sidecarName` (fertiger Zielname `<Name>.<de|en|fr>.vtt` oder `''`, wenn die Sprache noch nicht feststeht), `sidecarUrl`, `trackUrl`, `trackLang` (`de|en|fr`), `trackLabel`. Alle Werte serverseitig validiert; `und` kommt nie im Template an (D-04-15).

### Download-Knöpfe (D-04-02 bis D-04-04)

- Reihenfolge fest: SRT, VTT, TXT. Drei sichtbare Knöpfe, kein Menü, keine Vorauswahl.
- Echte Links (`<a href>`), **ohne** `download`-Attribut: Der Server setzt `Content-Disposition: attachment` mit dem Namen `<Name>.<Sprache>.<ext>` (Umlaute und ß im Namen ersetzt: ä->ae, ö->oe, ü->ue, ß->ss; Owner 17.11.2026) (DataDownloadResponse). Ohne JS voll funktionsfähig.
- Klick lädt sofort herunter; kein Bestätigungsschritt (nichts wird verändert).
- Fehler beim Herunterladen (Container still, Zeitlimit, Sperre zwischen Seitenaufbau und Klick, Transkript inzwischen weg): Der Controller liefert **keine** JSON- oder Leerantwort, sondern eine kleine Fehlerseite im App-Rahmen mit Banner `error` (Titel T29, Text je Ursache T24, T25 oder Bestandstext A5) und Banner-Aktion "Zurück zur Wiedergabe" (T30) auf die Abspielseite mit derselben `fileId` und `?t=`. Status 403/404/503 wie der Fall.
- Ladezeit: Lange Dateien dürfen bis zum Export-Zeitlimit (eigener Wert, Plan misst) dauern; der Browser zeigt seinen eigenen Ladezustand. Kein eigenes Spinner-Element.

### Ablage als Nebendatei (D-04-05 bis D-04-08, EXP-03)

- Nur sichtbar in X1/X2 **und** `sidecarAllowed === true`. Ohne Schreibrecht steht statt Beschreibung und Knopf der Satz T23 (kein deaktivierter Knopf: ein grauer Knopf ohne Erklärung ist schlechter lesbar und im Hochkontrast oft nicht als deaktiviert erkennbar).
- Die Ablage ist ein POST mit CSRF-Token und braucht JS. Muster wie der Sprung-Knopf: Der Knopf ist im Template `hidden` und wird von `play.js` sichtbar geschaltet. Ohne JS bleibt nur die Beschreibung stehen; die Downloads funktionieren ohne JS.
- Beschreibung T20 nennt den echten Zielnamen (`sidecarName`), damit der Nutzer vorher weiß, was im Ordner landet. Steht die Sprache bei Altbestand noch nicht fest, gilt T20b ohne Namen.
- Klick: Knopf `disabled` + `aria-busy="true"`, Beschriftung bleibt. Ein schon sichtbarer Ergebnis-Banner wird vorher verborgen. Kein Bestätigungsdialog: die Aktion ist nicht zerstörend (nie überschreiben ist serverseitig hart).
- Antwort: genau ein vorgerenderter Banner in `#avs-sidecar-result` wird sichtbar; der Dateiname aus der Antwort (`name`) wird per `textContent` in `span.avs-export__name` des Banners gesetzt. Danach Knopf wieder aktiv. Ein zweiter Klick nach Erfolg zeigt ehrlich E2 (Datei existiert bereits).
- Kein automatisches Ersetzen, kein Alternativname, kein Veraltungs-Hinweis (D-04-05, D-04-08).

| Nr. | Ergebnis (Antwort) | Banner | Titel / Text | Aktion im Banner |
|-----|--------------------|--------|--------------|------------------|
| E1 | 201 angelegt | `avs-banner--success`, `role="status"`, kein Fokuswechsel | T21 mit Name | Link "In Dateien zeigen" (Bestandsschlüssel `Show in Files`, Ziel `filesUrl`) |
| E2 | 409 existiert | `avs-banner--error`, `role="alert" tabindex="-1"`, Fokus | T22a / T22b mit Name | keine |
| E3 | 403 kein Schreibrecht | error, alert, Fokus | T29b / T23 | keine |
| E4 | 403 Download gesperrt | error, alert, Fokus | T29b / T24 | keine |
| E5 | 400 Name zu lang | error, alert, Fokus | T29b / T26 | keine |
| E6 | 429 Rate-Limit | error, alert, Fokus | T29b / T27 | keine |
| E7 | 404 kein Transkript, 503/Zeitlimit/Netz, jede andere Antwort | error, alert, Fokus | T29b / T25 | keine |

Der Server nennt in E2 den Namen, den **er** geprüft hat; `play.js` übernimmt nur einen String, der dem Muster `^[^/\\]{1,255}$` entspricht, sonst E7. Kein Wert aus der Antwort außer `name` erscheint auf der Seite.

### Untertitel-Spur am Player (D-04-18)

- Nur am `<video>`, nur in X1/X2. Bei `<audio>` keine Spur (der Browser zeigt Audio-Spuren nicht an; der Text steht im Ausschnitt und im Download).
- Markup: `<track kind="subtitles" src="{trackUrl}" srclang="{trackLang}" label="{trackLabel}">`, **ohne** `default`. Begründung: Es ist ein ungeprüfter Entwurf; der Nutzer schaltet ihn über das Untertitel-Menü der nativen Bedienleiste ein. Die Spur ist trotzdem ohne Umweg erreichbar (CC-Schalter), das genügt für Gehörlose, ohne Hörenden einen Entwurf aufzuzwingen.
- `trackLabel` = T31 mit Sprachname T32 bis T34 in Anzeigesprache, z. B. "Deutsch, Untertitel-Entwurf". So steht "Entwurf" auch im Spurmenü (EXP-04).
- `trackUrl` ist eine eigene Variante der Export-Route mit `Content-Type: text/vtt; charset=utf-8` und **ohne** `attachment`, gleiche Rechte- und Sperrprüfung. Bei X3 gibt es keine Spur und keine URL im DOM.
- Lädt die Spur nicht (Fehler am `track`-Element), passiert sichtbar nichts; die Wiedergabe bleibt. Kein Banner dafür.
- Teiltranskript (X2): Die Spur endet am letzten fertigen Stück; der Hinweis T15 steht darunter. Kein Nachladen ohne Neuladen der Seite.

### Interaktion und Barrierefreiheit

- Tab-Reihenfolge: Medium, Springen, In Dateien zeigen, SRT, VTT, TXT, Neben die Datei legen, ggf. Aktion im Erfolgs-Banner.
- Die Knöpfe tragen sichtbaren Text mit Format **und** Verb (T16 bis T18); kein `aria-label`, das vom sichtbaren Text abweicht (WCAG 2.5.3). Das Icon ist `aria-hidden`.
- Gruppe `role="group"` mit dem Abschnittstitel als Name, damit Screenreader "Untertitel-Entwurf, Gruppe" vorlesen.
- Teil-Hinweis T15 ist statischer Text, keine Live-Region, kein Polling.
- Fehler-Banner der Ablage: `role="alert"`, Fokus auf den Banner (Muster `show()` in `play.js`). Erfolg: `role="status"`, Fokus bleibt auf dem Knopf.
- Fokusring: Server-Standard, nie entfernt.

### Responsives Verhalten

- 375 px: Die drei Knöpfe brechen in bis zu drei Zeilen um (`flex-wrap`), Abstand 8 px in beide Richtungen; kein horizontales Scrollen, auch nicht in FR ("Télécharger le TXT").
- Langer Zielname in T20/T21/T22 bricht dank `overflow-wrap: anywhere` um.
- 768 und 1280 px: Knöpfe in einer Zeile, linksbündig in der 960-px-Spalte.

---

## Dateiinhalte (D-04-03, EXP-04)

Sprache der Kopfzeilen = Anzeigesprache des Nutzers (IL10N in PHP), unabhängig von der Sprache des Transkripts.

**TXT** (UTF-8 ohne BOM, LF):
```
{Dateiname der Aufnahme}
{T35}
[{T15 mit Zeit}]            nur bei Teiltranskript
<Leerzeile>
{Fließtext, Absatz bei Pause > 2 s}
```

**VTT:**
```
WEBVTT

NOTE
{T35}
[{T15 mit Zeit}]            nur bei Teiltranskript

{Cues}
```
Kein Dateiname im `NOTE`-Block (ein Name mit `-->` würde den Block brechen). T35 und T15 enthalten kein `-->` (Prüfung im Text-Gate).

**SRT:** kein Kommentar-Mechanismus im Format; kein künstlicher Hinweis-Cue (würde den Text verändern, D-04-16). Die Kennzeichnung "Untertitel-Entwurf" tragen hier Abschnittstitel, Spurname und README. Dem Owner als bekannte Grenze vorlegen (Frage O4).

Text-Gate (EXP-04): "BITV-konform", "BITV compliant", "conforme BITV" (jede Schreibweise, auch "barrierefrei geprüft") in keinem Katalog, Template, README, Store-Text und keinem erzeugten Dateiinhalt; "Untertitel-Entwurf" / "Subtitle draft" / "Brouillon de sous-titres" in allen drei Katalogen vorhanden.

---

## Copywriting Contract

**Status aller neuen Texte: FREIGEGEBEN 2026-11-16 (Owner, ohne Änderungen am Wortlaut; siehe "Owner-Freigabe Phase 4").**

Regeln (aus 01- und 03-UI-SPEC.md): `de` und `de_DE` inhaltsgleich, **unpersönlich** (weder du noch Sie). Französisch in Vous- bzw. unpersönlicher Form, U+00A0 vor `:` `;` `?` `!` (die Entwürfe enthalten keines dieser Zeichen). Echte Umlaute, keine Gedankenstriche, keine Emojis, kein Ausrufezeichen. Englischer Text = l10n-Schlüssel. Platzhalter `%s` (Zeit oder Dateiname).

**Nummerierung:** T12 ist in 03-UI-SPEC.md bereits vergeben (Zu wenig Speicherplatz, Plan 03-01). Phase 4 beginnt deshalb bei **T13**.

### Pflichtfelder (Template)

| Element | Copy (DE) |
|---------|-----------|
| Primary CTA | "SRT herunterladen", "VTT herunterladen", "TXT herunterladen" (drei gleichrangige Knöpfe); dazu "Neben die Datei legen" |
| Empty state heading | kein eigener: ohne Transkript fehlt der Abschnitt (X4), der Ausschnitt-Block nennt den Grund (A5 bis A13, Bestand) |
| Empty state body | Teiltranskript (X2): "Transkript bis %s, Datei wird noch verarbeitet." (T15) |
| Error state | Kollision (E2): "Datei existiert bereits" / "Im Ordner liegt schon eine Datei namens %s. Sie wird nicht überschrieben. Für eine neue Ablage die vorhandene Datei zuerst löschen oder umbenennen." |
| Destructive confirmation | keine: Phase 4 hat keine zerstörende Aktion (Ablage überschreibt nie, Download verändert nichts) |

### Neue Texte DE / EN / FR (freigegeben 2026-11-16)

| Nr. | Verwendung | DE | EN | FR |
|-----|------------|----|----|----|
| T13 | Abschnittstitel, Gruppenname | Untertitel-Entwurf | Subtitle draft | Brouillon de sous-titres |
| T14 | Erklärsatz (X1/X2) | Automatisch erstellt und nicht geprüft. SRT und VTT enthalten Zeitmarken, TXT nur den Text. | Created automatically and not reviewed. SRT and VTT contain time marks, TXT only the text. | Créé automatiquement et non vérifié. SRT et VTT contiennent des repères temporels, TXT uniquement le texte. |
| T15 | Teil-Hinweis (X2, TXT-Kopf, VTT-NOTE; D-04-17) | Transkript bis %s, Datei wird noch verarbeitet. | Transcript up to %s, the file is still being processed. | Transcription jusqu'à %s, le fichier est encore en cours de traitement. |
| T16 | Knopf | SRT herunterladen | Download SRT | Télécharger le SRT |
| T17 | Knopf | VTT herunterladen | Download VTT | Télécharger le VTT |
| T18 | Knopf | TXT herunterladen | Download TXT | Télécharger le TXT |
| T19 | Ablage-Knopf | Neben die Datei legen | Save next to the file | Enregistrer à côté du fichier |
| T20 | Ablage-Beschreibung mit Name | Legt %s in denselben Ordner wie die Aufnahme. Eine vorhandene Datei wird nie überschrieben. | Saves %s in the same folder as the recording. An existing file is never overwritten. | Enregistre %s dans le même dossier que l'enregistrement. Un fichier existant n'est jamais remplacé. |
| T20b | Ablage-Beschreibung ohne Name (Sprache noch offen) | Legt die Untertitel als VTT-Datei in denselben Ordner wie die Aufnahme. Eine vorhandene Datei wird nie überschrieben. | Saves the subtitles as a VTT file in the same folder as the recording. An existing file is never overwritten. | Enregistre les sous-titres en fichier VTT dans le même dossier que l'enregistrement. Un fichier existant n'est jamais remplacé. |
| T21 | E1 Erfolg (Titel = Text, ein Satz) | %s liegt jetzt im selben Ordner wie die Aufnahme. | %s is now in the same folder as the recording. | %s se trouve maintenant dans le même dossier que l'enregistrement. |
| T22a | E2 Titel (D-04-05) | Datei existiert bereits | File already exists | Le fichier existe déjà |
| T22b | E2 Text | Im Ordner liegt schon eine Datei namens %s. Sie wird nicht überschrieben. Für eine neue Ablage die vorhandene Datei zuerst löschen oder umbenennen. | The folder already contains a file named %s. It is not overwritten. To save again, delete or rename the existing file first. | Le dossier contient déjà un fichier nommé %s. Il n'est pas remplacé. Pour enregistrer à nouveau, supprimez ou renommez d'abord le fichier existant. |
| T23 | Kein Schreibrecht (Hinweis statt Knopf, E3) | In diesem Ordner dürfen keine Dateien angelegt werden. Herunterladen geht trotzdem. | Files cannot be created in this folder. Downloading still works. | Il n'est pas possible de créer des fichiers dans ce dossier. Le téléchargement reste possible. |
| T24 | Download gesperrt (X3, E4, Fehlerseite) | Diese Freigabe erlaubt keine Downloads. Untertitel und Transkript lassen sich deshalb weder herunterladen noch ablegen. | This share does not allow downloads. Subtitles and transcript can therefore neither be downloaded nor saved. | Ce partage n'autorise pas les téléchargements. Les sous-titres et la transcription ne peuvent donc être ni téléchargés ni enregistrés. |
| T25 | Nicht erstellbar (E7, Fehlerseite) | Der Untertitel-Entwurf lässt sich gerade nicht erstellen. Die Wiedergabe funktioniert trotzdem. Später erneut versuchen. | The subtitle draft cannot be created right now. Playback works regardless. Try again later. | Le brouillon de sous-titres ne peut pas être créé pour le moment. La lecture fonctionne quand même. Réessayez plus tard. |
| T26 | Name zu lang (E5) | Der Name der Untertiteldatei wäre zu lang. Nach einer Umbenennung der Aufnahme in einen kürzeren Namen erneut versuchen. | The name of the subtitle file would be too long. Rename the recording to a shorter name and try again. | Le nom du fichier de sous-titres serait trop long. Renommez l'enregistrement avec un nom plus court et réessayez. |
| T27 | Rate-Limit (E6) | Zu viele Versuche in kurzer Zeit. Etwas später erneut versuchen. | Too many attempts in a short time. Try again a little later. | Trop de tentatives en peu de temps. Réessayez un peu plus tard. |
| T29 | Titel der Fehlerseite (Download) | Der Untertitel-Entwurf konnte nicht erstellt werden | The subtitle draft could not be created | Le brouillon de sous-titres n'a pas pu être créé |
| T29b | Titel der Ablage-Fehler E3 bis E7 | Die Untertitel wurden nicht abgelegt | The subtitles were not saved | Les sous-titres n'ont pas été enregistrés |
| T30 | Aktion der Fehlerseite | Zurück zur Wiedergabe | Back to playback | Retour à la lecture |
| T31 | Spurname (`%s` = Sprachname) | %s, Untertitel-Entwurf | %s, subtitle draft | %s, brouillon de sous-titres |
| T32 | Sprachname de | Deutsch | German | Allemand |
| T33 | Sprachname en | Englisch | English | Anglais |
| T34 | Sprachname fr | Französisch | French | Français |
| T35 | TXT-Kopf Zeile 2, VTT-NOTE | Untertitel-Entwurf, automatisch erstellt und nicht geprüft. | Subtitle draft, created automatically and not reviewed. | Brouillon de sous-titres, créé automatiquement et non vérifié. |

T28 bleibt frei (reserviert, damit die Nummern der Fehlerfamilie T29/T29b beieinander stehen; der Fall "Transkript inzwischen weg" nutzt T25 bzw. auf der Fehlerseite den Bestandstext A5).

FR-Imperative ("Réessayez", "supprimez") folgen dem Bestand ("Rechargez" in Phase 1 entspricht der Vous-Form). DE bleibt unpersönlich ("Später erneut versuchen.", Infinitiv wie Bestand "Seite neu laden").

### Unverändert weiterverwendete Texte

| Schlüssel | DE | EN | FR |
|-----------|----|----|----|
| In Dateien zeigen (E1-Aktion) | In Dateien zeigen | Show in Files | Afficher dans Fichiers |
| Kein Transkript (Fehlerseite, Transkript weg) | Für diese Datei gibt es noch kein Transkript. | There is no transcript for this file yet. | Il n'y a pas encore de transcription pour ce fichier. |

(Wortlaut der Bestandsschlüssel gilt wie in den Katalogen; diese Tabelle legt nichts neu fest.)

**Wahrheitsbedingungen für den Planer** (Satz nur bauen, wenn er im Code stimmt):
- T20/T20b/T22b "nie überschrieben": Existenzprüfung unter eigener Sperre vor `newFile` (Research Pattern 4), Byte-Vergleichstest.
- T23 "Herunterladen geht trotzdem": nur in X1/X2 zeigen, nie bei X3.
- T24 "weder herunterladen noch ablegen": Export- **und** Ablage-Route liefern 403 vor dem Container-Aufruf (PHPUnit + E2E mit echter Freigabe).
- T15 Zeit = Ende des letzten fertigen Stücks, nicht Dauer der Datei.
- T14 "nicht geprüft": gilt bis Phase 10; der Text wechselt erst mit dem Status "geprüft".
- Kein Text behauptet, der Nextcloud-Viewer zeige die Nebendatei (erst NC 36, nur README).

Dreisprachigkeits-Test und Umlaut-/Gedankenstrich-Audit decken alle neuen Schlüssel in `de`, `de_DE`, `en`, `fr` (`.json` und `.js`) ab. Ausnahme Umlaut-Regel: Klassen, Routen, Dateinamenmuster bleiben ASCII.

---

## Download-Sperre: Begründung der Darstellung (SRCH-04)

Vorgabe war "nicht sichtbar statt deaktiviert". Vertrag: **Knöpfe, Ablage, Spur und Export-URLs fehlen im DOM** (nicht nur `hidden`, nicht `disabled`). Zusätzlich steht im Abschnitt der eine Satz T24.

Begründung für den zusätzlichen Satz: Der Seitenzustand X3 tritt nur auf, wenn die Instanz Ansehen ohne Download erlaubt; der Empfänger sieht und hört die Aufnahme also. Fehlen die Export-Knöpfe kommentarlos, wirkt die Seite kaputt oder die Funktion unbekannt. Der Satz nennt den Grund und verrät nichts Neues (die Sperre ist dem Empfänger aus Files und dem Format-Banner bereits bekannt), er hängt nicht am Container und ist für ausgeschlossene und unbekannte Dateien gleich. Deaktivierte Knöpfe wären schlechter: sie laden zum Klicken ein, sind im Hochkontrast schwer zu erkennen und würden Export-URLs ins DOM tragen.

---

## Prüfvertrag für die Abnahme (Playwright, gemeinsam mit dem Owner)

Grundmatrix "6": Breiten 375, 768, 1280 px, je hell und dunkel. Sprache DE; FR zusätzlich bei 375 px hell für die längsten Texte. NC 33 und 35 Vollmatrix, NC 34 Stichprobe X1 bei 1280 hell. Hochkontrast-Theme bei 1280 px für X1 und E2.

| ID | Fläche / Zustand | Screenshots | Zusätzliche Prüfung |
|----|------------------|-------------|---------------------|
| X1 | Abschnitt fertig, Video | 6 + FR 375 + Hochkontrast | Reihenfolge SRT, VTT, TXT; kein Akzent an den Knöpfen; Knopfhöhe >= `--default-clickable-area`, bei coarse 44 px |
| X1a | Abschnitt fertig, Audio | 1280 hell | kein `<track>` im DOM |
| X2 | Teiltranskript | 6 + FR 375 | T15 mit Zeit; gleiche Zeit im TXT-Kopf und VTT-NOTE der heruntergeladenen Dateien |
| X3 | Freigabe mit Download-Sperre, Ansehen erlaubt | 1280 hell + dunkel, 375 hell | DOM enthält kein `avs-export__download`, kein `#avs-sidecar`, kein `<track>`, keine `/export/`-URL; direkter GET auf Export- und Track-URL = 403; POST Ablage = 403; Suche liefert Treffer; Medium mit `controlslist="nodownload"` (bei X1 ohne das Attribut) |
| X4 | ohne Transkript / ausgeschlossen / Grund | 1280 hell | Abschnitt fehlt; ausgeschlossener Nutzer und unbekannte Datei byte-gleich (Vergleich mit P4/P11 aus Phase 3) |
| X5 | ohne Schreibrecht im Ordner (Freigabe nur lesen, Download erlaubt) | 1280 hell, 375 hell | T23 statt Knopf; Downloads funktionieren |
| X6 | ohne JS | 1280 hell | Downloads funktionieren, Ablage-Knopf nicht sichtbar, T20 steht |
| D1 | Download SRT/VTT/TXT | kein Bild | Dateiname `<Name>.<de|en|fr>.<ext>` (Umlaute und ß im Namen ersetzt: ä->ae, ö->oe, ü->ue, ß->ss; Owner 17.11.2026), MIME laut Research, VTT/SRT parsen in webvtt-py, srt und ffmpeg; TXT Zeile 2 = T35 in Anzeigesprache; Text-Gate EXP-04 auf den Dateien |
| D2 | Fehlerseite Download (Container gestoppt) | 1280 hell + dunkel, 375 hell | T29 + T25 + Aktion T30 führt zurück zur Abspielseite mit gleicher Zeitmarke |
| E1 | Ablage erfolgreich | 6 | Datei im Ordner, Name aus T21 stimmt mit Datei überein; Fokus bleibt auf dem Knopf; Screenreader-Ansage (role status) |
| E2 | zweiter Klick: Kollision | 6 + FR 375 + Hochkontrast | T22a/T22b mit Name; vorhandene Datei byte-gleich (sha256 vor/nach); Fokus auf dem Banner |
| E3 bis E7 | Fehlerfälle provoziert (Recht nach Seitenaufbau entzogen, Sperre nach Seitenaufbau gesetzt, überlanger Name, Rate-Limit, Container gestoppt) | je 1280 hell | richtiger Text, kein roher Statuscode, keine JSON-Ausgabe |
| T1 | Spur im Player (Video, Chromium und Firefox) | 1280 hell | Spurmenü zeigt T31 ("Deutsch, Untertitel-Entwurf"), Spur standardmäßig aus, nach Einschalten erscheint Text zur richtigen Zeit (Toleranz 100 ms) |
| S6 | Unified Search mit Datumsfilter und mit Personenfilter (SRCH-06) | 1280 hell + dunkel | Gruppe mit dem Providernamen des Produkts ("Audio and video", deutsch "Audio und Video", französisch "Audio et vidéo"; Owner 16.11.2026) im Hauptteil, nicht unter "Partial matches"; Trefferbild gleich S1 aus Phase 3 |
| S7 | Suche "20"/"zwanzig"/"twenty"/"vingt", "zwölf"/"12"/"twelve"/"douze", "Polizist", "Polizisten", "Polizei", "Polizeipräsidium", "Seite", "Seitenverhältnis", "12:30" | 1280 hell, je Suchbegriff ein Bild | Treffer laut Erfolgskriterium 1; "12:30" ohne Fehler. Begriffe nachgezogen (Owner 16.11.2026): ursprünglich "Häuser"/"Haushalt"; die S7-Clips kommen aus FLEURS, das kein Kompositum mit dem Kopf "Haushalt" enthält. Abgenommen werden deshalb die gemessenen Formen und Komposita der Clips (Polizei/Polizeipräsidium, Seite/Seitenverhältnis). "Haushalt" findet "Haushaltsplanberatung" belegt `backend/tests/test_compounds.py` (Plan 04-06), "Häuser" `backend/tests/test_search_numbers.py` und `test_compounds.py` am Index |

**Kontrast-Gate** (axe-core plus berechneter Kontrast im Playwright-Lauf, hell, dunkel, Hochkontrast):
- `.avs-export__note`, `.avs-export__hint` (`--color-text-maxcontrast` auf `--color-main-background`, 13 px): mindestens 4,5:1. Fällt der Wert darunter, wechseln beide auf `--color-main-text` (kein eigener Farbwert).
- Knopftext und Knopfrand gegen Grund: Text 4,5:1, Rand/Fokusring 3:1 (WCAG 1.4.11).
- Erfolgs- und Fehler-Banner: Bestandspaare, Messung wie Phase 1.
- axe ohne `serious`/`critical` auf allen X-, E- und D2-Seiten.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | keine (shadcn nicht verwendet) | not applicable |
| Drittanbieter | keine | not applicable |

Keine neuen Frontend-Pakete, kein npm, keine Vue-Komponenten. (webvtt-py und srt sind nur Python-Testprüfer im Backend, siehe Research, nicht Teil der UI.)

---

## Offene Gestaltungsfragen: Empfehlung + Begründung (Owner reviewt als Ganzes)

1. **O1 Texte T13 bis T35 freigeben?** Empfehlung: wie entworfen. T15 übernimmt den Owner-Wortlaut aus D-04-17 wörtlich ("Datei wird noch verarbeitet", ohne Artikel); Alternative "die Datei wird noch verarbeitet" wäre flüssiger, nur auf Zuruf.
2. **O2 Knopftext "SRT herunterladen" statt nur "SRT"?** Empfehlung: mit Verb. Nur "SRT" ist für Screenreader und Laien mehrdeutig; ein `aria-label` mit anderem Text würde WCAG 2.5.3 riskieren. Kosten: Umbruch bei 375 px, geprüft in X1.
3. **O3 Ablage-Knopf "Neben die Datei legen" statt "Als Nebendatei ablegen"?** Empfehlung: "Neben die Datei legen". "Nebendatei" ist Fachjargon; die Beschreibung T20 nennt den echten Zielnamen und erklärt den Rest.
4. **O4 SRT ohne Entwurf-Kennzeichen im Inhalt?** Empfehlung: ja, so lassen. SRT hat keinen Kommentar; ein Hinweis-Cue verändert den Text und verletzt D-04-16. Kennzeichnung über Abschnittstitel, Spurname, VTT-NOTE, TXT-Kopf und README.
5. **O5 Untertitel-Spur standardmäßig aus?** Empfehlung: aus (kein `default`). Ungeprüfter Entwurf; der CC-Schalter der nativen Leiste macht sie mit einem Klick erreichbar. Ab Phase 10 (geprüft) kann `default` neu bewertet werden.
6. **O6 Zusätzlicher Satz bei Download-Sperre (T24) statt kommentarlosem Fehlen?** Empfehlung: ja, siehe Abschnitt "Download-Sperre". Knöpfe bleiben trotzdem komplett aus dem DOM.
7. **O7 Ohne Schreibrecht: Satz T23 statt deaktiviertem Knopf?** Empfehlung: Satz; ein grauer Knopf erklärt nichts und ist im Hochkontrast schwer lesbar.
8. **O8 Ablage nur mit JS?** Empfehlung: ja (Muster Sprung-Knopf). Ein reiner Formular-POST bräuchte Weiterleitung und Zustand in der URL; Downloads bleiben ohne JS voll nutzbar.
9. **O9 Fehler beim Download als Fehlerseite im App-Rahmen?** Empfehlung: ja. Ein Link ohne `download`-Attribut auf eine Fehlerantwort würde sonst JSON oder eine leere Datei zeigen; die Seite nennt Grund und Rückweg.
10. **O10 Hinweis "Viewer zeigt die Nebendatei ab NC 36" in der UI?** Empfehlung: nein, nur README (D-04-18). Auf NC 33 bis 35 wäre der Satz für Nutzer nicht handlungsrelevant und veraltet beim Upgrade.

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

## Owner-Freigabe Phase 4

**Stand: vorgelegt und freigegeben 2026-11-16.** Owner-Änderungen werden wörtlich in die Copywriting-Tabelle und hier übernommen. Vor der Antwort werden keine Kataloge geschrieben.

### 1. Texte T13 bis T35 (T28 frei)

| Nr. | DE | EN | FR |
|-----|----|----|----|
| T13 | Untertitel-Entwurf | Subtitle draft | Brouillon de sous-titres |
| T14 | Automatisch erstellt und nicht geprüft. SRT und VTT enthalten Zeitmarken, TXT nur den Text. | Created automatically and not reviewed. SRT and VTT contain time marks, TXT only the text. | Créé automatiquement et non vérifié. SRT et VTT contiennent des repères temporels, TXT uniquement le texte. |
| T15 | Transkript bis %s, Datei wird noch verarbeitet. | Transcript up to %s, the file is still being processed. | Transcription jusqu'à %s, le fichier est encore en cours de traitement. |
| T16 | SRT herunterladen | Download SRT | Télécharger le SRT |
| T17 | VTT herunterladen | Download VTT | Télécharger le VTT |
| T18 | TXT herunterladen | Download TXT | Télécharger le TXT |
| T19 | Neben die Datei legen | Save next to the file | Enregistrer à côté du fichier |
| T20 | Legt %s in denselben Ordner wie die Aufnahme. Eine vorhandene Datei wird nie überschrieben. | Saves %s in the same folder as the recording. An existing file is never overwritten. | Enregistre %s dans le même dossier que l'enregistrement. Un fichier existant n'est jamais remplacé. |
| T20b | Legt die Untertitel als VTT-Datei in denselben Ordner wie die Aufnahme. Eine vorhandene Datei wird nie überschrieben. | Saves the subtitles as a VTT file in the same folder as the recording. An existing file is never overwritten. | Enregistre les sous-titres en fichier VTT dans le même dossier que l'enregistrement. Un fichier existant n'est jamais remplacé. |
| T21 | %s liegt jetzt im selben Ordner wie die Aufnahme. | %s is now in the same folder as the recording. | %s se trouve maintenant dans le même dossier que l'enregistrement. |
| T22a | Datei existiert bereits | File already exists | Le fichier existe déjà |
| T22b | Im Ordner liegt schon eine Datei namens %s. Sie wird nicht überschrieben. Für eine neue Ablage die vorhandene Datei zuerst löschen oder umbenennen. | The folder already contains a file named %s. It is not overwritten. To save again, delete or rename the existing file first. | Le dossier contient déjà un fichier nommé %s. Il n'est pas remplacé. Pour enregistrer à nouveau, supprimez ou renommez d'abord le fichier existant. |
| T23 | In diesem Ordner dürfen keine Dateien angelegt werden. Herunterladen geht trotzdem. | Files cannot be created in this folder. Downloading still works. | Il n'est pas possible de créer des fichiers dans ce dossier. Le téléchargement reste possible. |
| T24 | Diese Freigabe erlaubt keine Downloads. Untertitel und Transkript lassen sich deshalb weder herunterladen noch ablegen. | This share does not allow downloads. Subtitles and transcript can therefore neither be downloaded nor saved. | Ce partage n'autorise pas les téléchargements. Les sous-titres et la transcription ne peuvent donc être ni téléchargés ni enregistrés. |
| T25 | Der Untertitel-Entwurf lässt sich gerade nicht erstellen. Die Wiedergabe funktioniert trotzdem. Später erneut versuchen. | The subtitle draft cannot be created right now. Playback works regardless. Try again later. | Le brouillon de sous-titres ne peut pas être créé pour le moment. La lecture fonctionne quand même. Réessayez plus tard. |
| T26 | Der Name der Untertiteldatei wäre zu lang. Nach einer Umbenennung der Aufnahme in einen kürzeren Namen erneut versuchen. | The name of the subtitle file would be too long. Rename the recording to a shorter name and try again. | Le nom du fichier de sous-titres serait trop long. Renommez l'enregistrement avec un nom plus court et réessayez. |
| T27 | Zu viele Versuche in kurzer Zeit. Etwas später erneut versuchen. | Too many attempts in a short time. Try again a little later. | Trop de tentatives en peu de temps. Réessayez un peu plus tard. |
| T29 | Der Untertitel-Entwurf konnte nicht erstellt werden | The subtitle draft could not be created | Le brouillon de sous-titres n'a pas pu être créé |
| T29b | Die Untertitel wurden nicht abgelegt | The subtitles were not saved | Les sous-titres n'ont pas été enregistrés |
| T30 | Zurück zur Wiedergabe | Back to playback | Retour à la lecture |
| T31 | %s, Untertitel-Entwurf | %s, subtitle draft | %s, brouillon de sous-titres |
| T32 | Deutsch | German | Allemand |
| T33 | Englisch | English | Anglais |
| T34 | Französisch | French | Français |
| T35 | Untertitel-Entwurf, automatisch erstellt und nicht geprüft. | Subtitle draft, created automatically and not reviewed. | Brouillon de sous-titres, créé automatiquement et non vérifié. |

Bestandsschlüssel "Show in Files" (E1-Aktion) bleibt mit Katalogwortlaut "In Dateien anzeigen" / "Afficher dans Fichiers".

### 2. T15 (D-04-17, Wortlaut vor dem Bau zeigen)

DE "Transkript bis %s, Datei wird noch verarbeitet." übernimmt den Owner-Wortlaut aus D-04-17 wörtlich (`%s` = Uhrzeit des letzten fertigen Stücks, z. B. "12:34" oder "1:02:03"). Steht an drei Stellen: Abspielseite (X2), TXT-Kopf Zeile 3, VTT-NOTE. Kein `-->`, kein Zeilenumbruch. Alternative nur auf Zuruf: "Transkript bis %s, die Datei wird noch verarbeitet."

### 3. Gestaltungsfragen O1 bis O10 (Empfehlung)

- O1 Texte wie oben freigeben: Empfehlung ja.
- O2 Knopftext mit Verb ("SRT herunterladen" statt "SRT"): Empfehlung ja (Screenreader, WCAG 2.5.3).
- O3 Ablage-Knopf "Neben die Datei legen" statt "Als Nebendatei ablegen": Empfehlung "Neben die Datei legen".
- O4 SRT ohne Entwurf-Kennzeichen im Dateiinhalt: Empfehlung ja (SRT hat keinen Kommentar; Kennzeichnung über Titel, Spurname, VTT-NOTE, TXT-Kopf, README).
- O5 Untertitel-Spur standardmäßig aus: Empfehlung ja (ungeprüfter Entwurf, CC-Schalter reicht).
- O6 Bei Download-Sperre Satz T24 statt kommentarlosem Fehlen: Empfehlung ja, Knöpfe trotzdem nicht im DOM.
- O7 Ohne Schreibrecht Satz T23 statt grauem Knopf: Empfehlung Satz.
- O8 Ablage nur mit JS (Downloads auch ohne JS): Empfehlung ja.
- O9 Download-Fehler als Fehlerseite im App-Rahmen (T29, Text, Aktion T30): Empfehlung ja.
- O10 Hinweis "Viewer zeigt Nebendatei ab NC 36" nur im README, nicht in der UI: Empfehlung ja.

### 4. X3-Lesart (siehe "Verhältnis zu Phase 3")

- Seite `download_blocked` (Ansehen ohne Download aus): kein Medium, kein Export-Abschnitt (wie Phase 3).
- X3 (Ansehen erlaubt, Freigabe sperrt Download): Medium spielt, Export-Abschnitt nur mit T13 und T24.
- Freigabe-Attribut unentscheidbar: Abschnitt fehlt (X4), nie ein falscher Sperrsatz.

### 5. Technische Befunde

- Icon-Pfade `download`, `file-plus`, `check-circle-outline` gegen Templarian/MaterialDesign-SVG geprüft (Design-System-Tabelle); `download` stimmt mit dem Entwurf überein.
- `<a class="button">` hat in NC 33, 34, 35 dieselbe Server-Gestalt wie `<button>` (`core/css/inputs.scss`, Befund unter CSS); kein Ersatzstil nötig. Die Knöpfe tragen den hellen Server-Standardton wie "Zu %s springen", keinen kräftigen Akzent.

### Owner-Antwort

**Freigegeben am 16.11.2026:** Texte T13 bis T35 wie vorgelegt, ohne Änderungen am Wortlaut (T15 wie D-04-17). Gestaltungsfragen O1 bis O10 alle mit der Empfehlung (ja). X3-Lesart wie vorgelegt: zwei getrennte Zustände; bei nicht sicher lesbarem Freigabe-Attribut fehlt der Abschnitt ganz. Kataloge `php/l10n/{de,de_DE,en,fr}.{json,js}` danach geschrieben (Plan 04-03, Task 3).
