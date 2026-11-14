---
phase: 3
slug: vorschau-transkripte-in-der-suche
status: approved
reviewed_at: 2026-11-14
shadcn_initialized: false
preset: none
created: 2026-11-14
base_contract: .planning/phases/01-zwei-app-ger-st-und-integrationsbeweis/01-UI-SPEC.md
---

# Phase 3: UI Design Contract

> Visueller und Interaktionsvertrag für Phase 3 (Vorschau-Transkripte in der Suche). Erstellt vom gsd-ui-researcher, geprüft vom gsd-ui-checker.
> Quellen: 03-CONTEXT.md (D-03-01 bis D-03-14), 01-UI-SPEC.md (Basisvertrag, status approved), 02-CONTEXT.md (D-02-15c, D-02-16), Bestand `php/lib/Search/Provider.php`, `php/lib/Controller/PageController.php`, `php/templates/play.php`, `php/css/play.css`, `php/js/play.js`, `php/l10n/*.json`, DESIGN.md.

**Grundsatz: Dieser Vertrag ist ein Nachtrag.** Alles, was 01-UI-SPEC.md festlegt (Design System, Abstände, Typografie, Farben, Banner-Aufbau, Aufbau und Zustände der Abspielansicht, Barrierefreiheit, Copy-Regeln), gilt unverändert und wird hier nicht neu verhandelt. Phase 3 ändert genau zwei Stellen:

1. **Unified-Search-Untertitel:** Kennzeichen "Vorläufig" (D-03-01 bis D-03-03).
2. **Ausschnitt-Block der Abspielansicht:** Hinweis bei Vorschau-Transkript (D-03-04), Teiltranskript (D-03-07) und Gründe statt "kein Transkript" (D-03-08, D-03-13), unter der Leck-Regel D-02-15c/D-02-16.

Nicht in Phase 3: Admin-Oberfläche für Gründe und Höchstdauer (Phase 9, in Phase 3 nur occ bzw. deklarative Einstellung, D-03-09), Hervorhebung des Suchworts im Ausschnitt, eigener Fortschrittsbalken, Filter (Phase 4), Kennzeichen "geprüft" (Phase 10). Admin-Statusbereich (Fläche 3) bleibt unverändert.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (PHP-Templates, kein React/Vite; shadcn-Gate nicht anwendbar) |
| Preset | not applicable |
| Component library | none: wie 01-UI-SPEC.md (PHP-Templates plus reines Browser-JS ohne Bundler, Nextcloud-Server-CSS). Kein @nextcloud/vue, weil die App keine Vue-Oberfläche hat; das bestehende App-Muster gilt |
| Icon library | Material Design Icons als Pfaddaten in Inline-SVG, 20 px, `aria-hidden="true" focusable="false"`. Phase 3 braucht **kein neues Icon** |
| Font | Server-Schrift über `var(--font-face)` |

Verbindliche Regeln aus 01-UI-SPEC.md gelten weiter: nur Nextcloud-CSS-Variablen, kein Hex/RGB im Code, kein `!important`, kein `outline: none`, kein `style`-Attribut, keine Inline-Skripte, flach (keine Schatten, keine Verläufe, keine Karte in Karte), jeder Text über `$l->t()` bzw. `$l->n()`, jede Fremdangabe mit `p()`, Präfix `avs-`.

---

## Spacing Scale

Unverändert aus 01-UI-SPEC.md (`calc(var(--default-grid-baseline) * n)`, Grundwert 4 px).

| Token | Value | Usage in Phase 3 |
|-------|-------|------------------|
| xs | 4px | nicht neu genutzt |
| sm | 8px | Abstand Ausschnitt (`blockquote`) zum Vorschau-Hinweis darunter; Abstand Label zu Text im Ausschnitt-Block (Bestand) |
| md | 16px | Innenabstand Ausschnitt-Block (Bestand) |
| lg | 24px | Bestand (Seitenrand ab 768 px) |
| xl | 32px | Bestand (oberer Abstand ab 768 px) |

Nicht genutzt: 48 px, 64 px. Exceptions: keine neuen; Klickflächen-Regel aus 01-UI-SPEC.md gilt (Phase 3 bringt keine neue Bedienfläche).

---

## Typography

Unverändert: genau drei Größen (13, 15, 20 px) und zwei Gewichte (400, 700), Zeilenhöhe nur `var(--default-line-height)`.

| Role | Size | Weight | Line Height | Neu in Phase 3 |
|------|------|--------|-------------|----------------|
| Body | 15px `var(--default-font-size)` | 400 | `var(--default-line-height)` | Grund-Hinweise im Ausschnitt-Block (`.avs-excerpt__hint`, Bestandsklasse) |
| Label | 13px `var(--font-size-small)` | 400 | `var(--default-line-height)` | Vorschau-Hinweis unter dem Ausschnitt (`.avs-excerpt__note`, neu) |
| Heading | 20px | 700 | `var(--default-line-height)` | keine Änderung |

"Vorläufig" im Suchergebnis rendert der Web-Client in seiner Untertitel-Schrift; die App setzt dort keine Typografie.

---

## Color

Unverändert aus 01-UI-SPEC.md.

| Role | Value | Usage in Phase 3 |
|------|-------|------------------|
| Dominant (60%) | `--color-main-background` | Seitengrund (Bestand) |
| Secondary (30%) | `--color-background-hover` | Fläche des Ausschnitt-Blocks, der alle neuen Zustände trägt |
| Accent (10%) | `--color-primary-element` / `--color-primary-element-text` | **in Phase 3 nirgends neu** |
| Destructive | `--color-error` / `--color-error-text` | in Phase 3 nirgends neu; keiner der neuen Zustände ist ein Fehler |

Gedämpfter Text `--color-text-maxcontrast`: nur Label des Ausschnitt-Blocks (Bestand) und der Vorschau-Hinweis `.avs-excerpt__note`.

Accent reserved for (unverändert): 1. die eine Aktion eines Admin-Banners, 2. der gesetzte Zustand der Debug-Checkbox. Kein Akzent für "Vorläufig", keinen Hinweis, keinen Grund.

**Begründung "keine Farbe, kein Banner" für die Gründe:** MEDIA-04 verlangt "keine Sprache" ausdrücklich "nicht als Fehler". Die Wiedergabe funktioniert in allen neuen Zuständen; betroffen ist nur der Transkript-Teil. Deshalb stehen alle neuen Zustände als Satz im bestehenden grauen Ausschnitt-Block, nicht als farbiger Banner oberhalb des Mediums. Farbe ist nie Bedeutungsträger, die Bedeutung steht im Satz.

---

## Fläche 1: Unified-Search-Treffer (Änderung)

Rendert weiter der Web-Client; die App liefert nur Daten. Kein CSS, kein JS. Alle Felder aus 01-UI-SPEC.md Fläche 1 gelten, neu bzw. präzisiert:

| Feld | Vertrag Phase 3 |
|------|-----------------|
| Zeilen je Stelle | Eine `SearchResultEntry` je Stelle, eigener `resourceUrl` mit eigener Zeitmarke (D-03-01). Keine Gruppierung je Datei, kein Zähler "3 Stellen" |
| Stellen je Datei | Höchstens 3 Zeilen je Datei je Ergebnisseite, danach die nächste Datei; weitere Stellen über die Paginierung des Clients ("Mehr laden"), ohne Dublette und ohne Lücke (D-03-02). Reihenfolge der Stellen einer Datei: nach Rang des Containers |
| `title` | Dateiname, unverändert. Drei Zeilen derselben Datei tragen denselben Titel; unterscheidbar sind sie über Zeitmarke und Ausschnitt |
| `subline` echter Treffer, Vorschau | `{zeit} · {Vorläufig} · {ausschnitt}` |
| `subline` echter Treffer, Endfassung (ab Phase 6) | `{zeit} · {ausschnitt}` (Kennzeichen entfällt) |
| `subline` Testtreffer | `{zeit} · {Testtreffer} · {ausschnitt}` wie bisher, **ohne** "Vorläufig". Nie zwei Kennzeichen in einer Zeile |
| Reihenfolge der Teile | Zeitmarke, Kennzeichen, Ausschnitt. Das Kennzeichen steht vor dem Ausschnitt, damit ein Abschneiden des Untertitels durch den Client (eine Zeile, Auslassung am Ende) nie das Kennzeichen trifft |
| Trennzeichen | Mittelpunkt U+00B7 mit je einem Leerzeichen (`Provider::SEPARATOR`), nie Gedankenstrich |
| Kennzeichen-Schreibweise | ein Wort, großer Anfangsbuchstabe, ohne Klammern, ohne Doppelpunkt, ohne Icon: "Vorläufig" / "Preliminary" / "Provisoire" |
| Ausschnitt | unverändert: reiner Text, höchstens 120 Zeichen inkl. `…`, an Wortgrenze gekürzt (`Provider::shorten`). Die 120 gelten nur für den Ausschnitt; Zeitmarke und Kennzeichen zählen nicht mit |
| Leerer Ausschnitt | `{zeit} · {Vorläufig}` (kein abschließender Trenner), wie die bestehende Logik bei leerem Ausschnitt |
| Teiltreffer laufender langer Dateien (D-03-07) | gleiche Darstellung wie jeder Vorschau-Treffer (`Vorläufig`), kein zusätzliches Wort wie "Teil" im Untertitel |
| `thumbnailUrl` | Mime-Symbol des Servers, unverändert (D-03-03: "Dateityp-Icon bleibt") |
| Dateien mit Grund (keine Sprache, übersprungen, Sprache nicht unterstützt, überlang) | erscheinen **nie** in der Suche; es gibt keinen Text, der gefunden werden könnte. Kein Grund-Text im Untertitel |
| Leer / Backend gestört / ausgeschlossen | unverändert: leere Liste, Leerzustand des Clients |

**Datenvertrag für den Planer (UI-relevant):** Jeder Vorschlag des Containers trägt eine Stufe `stage` mit den Werten `preview`, `final`, `sample`. Regel im Provider: `sample` (bzw. bestehendes `sample: true`) zeigt "Testtreffer"; `final` zeigt kein Kennzeichen; `preview` **und jeder fehlende oder unbekannte Wert** zeigen "Vorläufig" (im Zweifel ehrlich vorläufig, nie fälschlich endgültig). In Phase 3 gibt es nur `preview` und `sample`.

Barrierefreiheit: Der Untertitel ist reiner Text; ein Screenreader liest "1:23 Punkt Vorläufig Punkt ..." bzw. je nach Leser den Mittelpunkt still. Kein `aria`-Zusatz möglich und keiner nötig.

---

## Fläche 2: Abspielansicht (Änderung nur im Ausschnitt-Block)

Aufbau, Reihenfolge, Banner, Fokusregeln, Responsivität und alle Zustände aus 01-UI-SPEC.md bleiben. Neu ist nur, was im Ausschnitt-Block `section.avs-excerpt` unter dem Label "Ausschnitt an dieser Stelle" steht. Kein neuer Banner, kein neues Icon, keine neue Aktion, kein JS.

### Aufbau des Ausschnitt-Blocks

```
section.avs-excerpt (Fläche --color-background-hover, Innenabstand md, Radius --border-radius-container)
  p.avs-excerpt__label        Ausschnitt an dieser Stelle             (Label, gedämpft, Bestand)
  EINES von:
    blockquote.avs-excerpt__text   {Ausschnitt}                        (Body, Bestand)
    + p.avs-excerpt__note          {Vorschau-Hinweis | Teil-Hinweis}  (Label, gedämpft, NEU, Abstand sm nach oben)
  ODER
    p.avs-excerpt__hint            {Zustandssatz}                      (Body, Bestand)
```

CSS für `.avs-excerpt__note` (neu, in `play.css`): `margin: calc(var(--default-grid-baseline) * 2) 0 0; color: var(--color-text-maxcontrast); font-size: var(--font-size-small); line-height: var(--default-line-height); overflow-wrap: anywhere;`. Sonst nichts.

### Zustände des Ausschnitt-Blocks

Der Block erscheint wie bisher nur im Seitenzustand "Bereit" (Medium sichtbar). In allen anderen Seitenzuständen (nicht verfügbar, keine Audio-/Videodatei, Download gesperrt) bleibt er weg, auch wenn ein Grund bekannt wäre.

| Nr. | Ausschnitt-Zustand (`excerptState`) | Erkennung (Antwort `/excerpt`) | Inhalt des Blocks |
|-----|-------------------------------------|--------------------------------|-------------------|
| A1 | `ok` + Stufe `preview` | Text vorhanden, Stufe preview oder unbekannt | `blockquote` Ausschnitt + `note` "Vorschau-Hinweis" |
| A2 | `ok` + Teiltranskript | Text vorhanden, Datei noch in Arbeit (`partial: true`) | `blockquote` Ausschnitt + `note` "Teil-Hinweis" (statt A1, nie beide) |
| A3 | `ok` + Stufe `final` (ab Phase 6) | Text vorhanden, Stufe final | `blockquote` ohne `note` |
| A4 | `pending_here` | Datei teilweise fertig, aber die Zeitstelle liegt hinter dem letzten fertigen Stück | `hint` "Stelle noch nicht transkribiert" |
| A5 | `none` (Bestand) | unbekannt, in der Warteschlange, noch kein Stück fertig, **ausgeschlossen, nicht erlaubter Verweis, Ausschlussfrage gescheitert** | `hint` "Für diese Datei gibt es noch kein Transkript." (Bestandstext, Wortlaut unverändert) |
| A6 | `no_speech` | Grund `no_speech` | `hint` "Keine Sprache" |
| A7 | `skipped_damaged` | Grund `damaged` | `hint` "Beschädigt" |
| A8 | `skipped_protected` | Grund `protected` | `hint` "Geschützt" |
| A9 | `unsupported_language` | Grund `unsupported_language` | `hint` "Sprache nicht unterstützt" |
| A10 | `too_long` | Grund `too_long` | `hint` "Überlang" mit der aktuell eingestellten Höchstdauer in ganzen Stunden (`$l->n`, Plural) |
| A11 | `skipped_other` | Grund vorhanden, aber nicht in der Positivliste | `hint` "Anderer Grund" (nie der rohe Code) |
| A12 | `unavailable` (Bestand) | Container still, Drift, ungültige Antwort | `hint` "Ausschnitt nicht abrufbar" (Bestandstext) |

Die Gründe A6 bis A11 gelten für die ganze Datei und stehen deshalb unabhängig von `?t=` gleich da.

### Leck-Regel (D-02-15c, D-02-16, D-03-13), nicht verhandelbar

- Reihenfolge im Controller bleibt: Ausschlussprüfung zuerst. Ausgeschlossener Nutzer, ausgeschlossene Datei oder eine Ausschlussfrage, die scheitert: **A5**, ohne den Container zu fragen. Kein Grund, kein Hinweis, kein Unterschied im DOM.
- Der Container liefert Grund, Stufe und `partial` nur unter genau den Bedingungen, unter denen er auch Ausschnitt-Text liefern dürfte (Verweis mit state active für diesen Nutzer). Für jeden anderen Verweis antwortet er wie für eine unbekannte Datei: `known: false`, ohne Grund. Die PHP-Seite zeigt dann A5.
- PHP prüft den Grund gegen eine feste Positivliste (`no_speech`, `damaged`, `protected`, `unsupported_language`, `too_long`); ein unbekannter String wird A11, ein Grund mit falschem Typ macht die ganze Antwort ungültig (A12). Kein Wert aus der Antwort erscheint ungefiltert im HTML.
- A5 muss für "ausgeschlossen" und "unbekannt" **byte-gleich** sein (gleiches Markup, gleiche Klassen, gleicher Text). Beleg im Plan: ein PHPUnit- bzw. Playwright-Vergleich des Ausschnitt-Blocks zwischen ausgeschlossenem Nutzer mit Grund-Datei und Nutzer mit unbekannter Datei.
- Die Höchstdauer in A10 ist eine Instanz-Einstellung, kein Dateiinhalt; sie darf genannt werden. Dateigröße, tatsächliche Dauer, Codec, Tonspur oder technische Fehlermeldung werden nie genannt.

### Interaktion

- Keine neue Bedienung. Die Hinweise sind statischer, serverseitig gerenderter Text; kein `role="alert"`, kein `aria-live`, keine Fokusverschiebung (die Seite verschiebt beim Aufruf weiterhin nirgends den Fokus).
- Ohne JS identisch.
- A7 und ein Abspielfehler des Browsers können zusammen auftreten: Der Format-Banner aus Phase 1 erscheint (play.js), das Medium wird ausgeblendet, der Ausschnitt-Block mit A7 bleibt darunter sichtbar. Beide Aussagen widersprechen sich nicht und bleiben so.
- Der Teil-Hinweis (A2) und A4 aktualisieren sich nicht von selbst; ein Neuladen zeigt den neuen Stand. Kein Polling.

### Responsives Verhalten

Keine neuen Regeln. Prüfpunkt: die längsten Sätze (A7, A8, A10, FR) brechen bei 375 px ohne horizontales Scrollen um (`overflow-wrap: anywhere` liegt auf `.avs-excerpt__hint` und der neuen `.avs-excerpt__note`).

---

## Copywriting Contract

**Status aller neuen Texte: VOM OWNER FREIGEGEBEN am 14.11.2026 (D-03-04), T2 ohne Verbesserungsversprechen. Offene Fragen 1 bis 9 unten: alle nach Empfehlung entschieden, Frage 3 abweichend (T2 schon in Phase 3 ohne Versprechen).**

Regeln (aus 01-UI-SPEC.md, im Bestand geprüft): `de` und `de_DE` tragen denselben Text in **unpersönlicher Form** (weder du noch Sie); die Kataloge `php/l10n/de.json` und `de_DE.json` sind heute inhaltsgleich, einen getrennten du-Katalog gibt es nicht. Französisch in Vous- bzw. unpersönlicher Form mit U+00A0 vor `:` `;` `?` `!` (die neuen FR-Texte enthalten keines dieser Zeichen). Echte Umlaute, keine Gedankenstriche, keine Emojis, kein Ausrufezeichen. Plural über `$l->n()` mit `%n`; im JSON-Katalog als Schlüssel `_Singular_::_Plural_` mit Array-Wert.

### Pflichtfelder (Template)

| Element | Copy (DE, Entwurf) |
|---------|--------------------|
| Primary CTA | keine neue: Treffer-Zeile in der Suche (Klick öffnet die Abspielansicht an der Stelle), auf der Seite die native Abspieltaste |
| Empty state heading | kein eigener Titel; Hinweis im Ausschnitt-Block: "Für diese Datei gibt es noch kein Transkript." (Bestand) |
| Empty state body | A4: "Diese Stelle ist noch nicht transkribiert. Die Datei wird gerade transkribiert." |
| Error state | A7: "Diese Datei wurde nicht transkribiert, weil sie beschädigt oder unvollständig ist. Wird sie ersetzt, startet die Transkription automatisch neu." |
| Destructive confirmation | keine: Phase 3 hat keine zerstörende Aktion |

### Neue Texte DE / EN / FR (freigegeben 14.11.2026)

Der englische Text ist der l10n-Schlüssel.

| Nr. | Schlüssel | DE | EN | FR |
|-----|-----------|----|----|----|
| T1 | Kennzeichen Suche | Vorläufig | Preliminary | Provisoire |
| T2 | Vorschau-Hinweis (A1) | Vorläufiges Transkript. Es kann Fehler enthalten. | Preliminary transcript. It may contain errors. | Transcription provisoire. Elle peut contenir des erreurs. |
| T3 | Teil-Hinweis (A2) | Vorläufiges Transkript. Die Datei wird noch transkribiert, spätere Stellen folgen. | Preliminary transcript. The file is still being transcribed, later passages will follow. | Transcription provisoire. Le fichier est encore en cours de transcription, la suite suivra. |
| T4 | Stelle noch nicht transkribiert (A4) | Diese Stelle ist noch nicht transkribiert. Die Datei wird gerade transkribiert. | This point has not been transcribed yet. The file is being transcribed right now. | Ce passage n'est pas encore transcrit. Le fichier est en cours de transcription. |
| T5 | Keine Sprache (A6) | In dieser Datei wurde keine Sprache erkannt, etwa weil sie nur Musik, Stille oder Rauschen enthält. | No speech was found in this file, for example because it only contains music, silence or noise. | Aucune parole n'a été détectée dans ce fichier, par exemple parce qu'il ne contient que de la musique, du silence ou du bruit. |
| T6 | Beschädigt (A7) | Diese Datei wurde nicht transkribiert, weil sie beschädigt oder unvollständig ist. Wird sie ersetzt, startet die Transkription automatisch neu. | This file was not transcribed because it is damaged or incomplete. If it is replaced, transcription starts again automatically. | Ce fichier n'a pas été transcrit car il est endommagé ou incomplet. S'il est remplacé, la transcription redémarre automatiquement. |
| T7 | Geschützt (A8) | Diese Datei wurde nicht transkribiert, weil sie geschützt ist, etwa durch einen Kopierschutz. Eine ungeschützte Fassung wird automatisch transkribiert. | This file was not transcribed because it is protected, for example by copy protection. An unprotected copy is transcribed automatically. | Ce fichier n'a pas été transcrit car il est protégé, par exemple contre la copie. Une version non protégée sera transcrite automatiquement. |
| T8 | Sprache nicht unterstützt (A9) | Die Sprache dieser Aufnahme wird nicht unterstützt. Transkribiert werden Deutsch, Englisch und Französisch. | The language of this recording is not supported. Transcription covers German, English and French. | La langue de cet enregistrement n'est pas prise en charge. Sont transcrits l'allemand, l'anglais et le français. |
| T9a | Überlang (A10), Singular | Diese Datei ist länger als %n Stunde und wurde deshalb nicht transkribiert. | This file is longer than %n hour and was therefore not transcribed. | Ce fichier dure plus de %n heure et n'a donc pas été transcrit. |
| T9b | Überlang (A10), Plural | Diese Datei ist länger als %n Stunden und wurde deshalb nicht transkribiert. | This file is longer than %n hours and was therefore not transcribed. | Ce fichier dure plus de %n heures et n'a donc pas été transcrit. |
| T10 | Überlang (A10), zweiter Satz | Die Verwaltung dieser Instanz kann die Grenze anheben. | The administrators of this instance can raise the limit. | L'administration de cette instance peut relever cette limite. |
| T11 | Anderer Grund (A11) | Diese Datei wurde nicht transkribiert. Den Grund sieht die Verwaltung dieser Instanz. | This file was not transcribed. The administrators of this instance can see why. | Ce fichier n'a pas été transcrit. L'administration de cette instance en connaît la raison. |
| T12 | Zu wenig Speicherplatz (A13, D-03-17; Owner-Freigabe 14.11.2026) | Diese Datei wurde noch nicht transkribiert, weil auf dem Server gerade zu wenig Speicherplatz frei ist. Die Transkription wird später automatisch erneut versucht. | This file has not been transcribed yet because there is currently not enough free storage space on the server. Transcription will be retried automatically later. | Ce fichier n'a pas encore été transcrit car l'espace de stockage disponible sur le serveur est actuellement insuffisant. La transcription sera relancée automatiquement plus tard. |

Darstellung: T9 und T10 in **einem** `p.avs-excerpt__hint`, durch ein Leerzeichen getrennt (zwei l10n-Schlüssel, damit der Plural sauber bleibt). Alle anderen Hinweise sind je ein Schlüssel.

### Unverändert weiterverwendete Texte (nur zur Vollständigkeit)

| Schlüssel | DE | EN | FR |
|-----------|----|----|----|
| Testtreffer-Kennzeichen | Testtreffer | Test result | Résultat de test |
| Ausschnitt-Label | Ausschnitt an dieser Stelle | Excerpt at this point | Extrait à ce moment |
| Kein Transkript (A5) | Für diese Datei gibt es noch kein Transkript. | There is no transcript for this file yet. | Il n'y a pas encore de transcription pour ce fichier. |
| Nicht abrufbar (A12) | Der Ausschnitt ist gerade nicht abrufbar. Die Wiedergabe funktioniert trotzdem. | The excerpt cannot be loaded right now. Playback works regardless. | L'extrait n'est pas disponible pour le moment. La lecture fonctionne quand même. |

**Wahrheitsbedingungen für den Planer** (Text nur bauen, wenn die Aussage im Code stimmt, sonst Satz streichen und Owner fragen):
- T6 zweiter Satz: Ein Ersatz der Datei (neuer Inhalt, gleiche oder neue file_id) muss über den Ereignisweg aus Phase 2 erneut in den Arbeitsvorrat kommen.
- T7 zweiter Satz: wie T6, eine neue ungeschützte Datei wird normal erfasst.
- T2 enthält bewusst kein Versprechen der Verbesserung (Owner 14.11.2026). Der Zusatz "und wird automatisch verbessert" kommt erst mit Phase 6 (Veredelung) und nur für Profile, die wirklich veredeln.
- T8 nennt DE/EN/FR fest (D-03-14); ab Phase 7 (Instanz-Sprachen einstellbar) muss der Satz die eingestellten Sprachen nennen.
- T10: Die Höchstdauer ist in Phase 3 über occ/deklarative Einstellung änderbar (D-03-09), die Aussage stimmt also.

Dreisprachigkeits-Test und Umlaut-/Gedankenstrich-Audit (Muster aus Phase 1) decken alle neuen Schlüssel in `de`, `de_DE`, `en`, `fr` (`.json` und `.js`) ab, inklusive der Plural-Schlüssel.

---

## Barrierefreiheit

Gilt vollständig aus 01-UI-SPEC.md. Zusätzlich:
- Alle neuen Hinweise sind Text im Lesefluss nach dem Label, keine Live-Regionen, keine Icons, kein `title`-Attribut.
- Der Vorschau-Hinweis steht **nach** dem Ausschnitt im DOM, damit der Ausschnitt zuerst gelesen wird.
- Kontrast: `--color-text-maxcontrast` auf `--color-background-hover` in 13 px muss im Standard-Theme hell und dunkel sowie im Hochkontrast-Theme mindestens 4,5:1 erreichen; Messung im Playwright-Lauf (axe oder berechneter Kontrast). Fällt der Wert darunter, bekommt `.avs-excerpt__note` `--color-main-text` statt der gedämpften Farbe (kein eigener Farbwert).

---

## Prüfvertrag für die Abnahme (Playwright, gemeinsam mit dem Owner)

Grundmatrix je Zustand: Breiten 375, 768, 1280 px, je hell und dunkel = 6 Screenshots. Sprache der Screenshots DE; zusätzlich FR bei 375 px hell für die längsten Texte. NC-Version: 33 und 35 für die Vollmatrix, 34 Stichprobe A1 bei 1280 hell.

| ID | Fläche / Zustand | Screenshots | Zusätzliche Prüfung |
|----|------------------|-------------|---------------------|
| S1 | Suche: Datei mit 4+ Stellen, dazu eine zweite Datei | 6 (Vollmatrix) | genau 3 Zeilen der ersten Datei auf Seite 1, jede mit "Vorläufig"; Untertitel-Reihenfolge Zeit · Vorläufig · Ausschnitt |
| S2 | Suche: "Mehr laden" (Seite 2) | 1280 hell + dunkel | 4. Stelle erscheint, keine Dublette (Vergleich der `resourceUrl`) |
| S3 | Suche: langer Ausschnitt bei 375 px | 375 hell + dunkel | Kennzeichen sichtbar, Abschneiden nur am Ausschnitt |
| S4 | Suche: Testtreffer neben echtem Treffer (`debug => true`) | 1280 hell | Testtreffer ohne "Vorläufig", echter mit |
| S5 | Suche: Datei mit Grund (no_speech) | 1280 hell | Datei erscheint nicht |
| P1 | Abspielseite A1 Vorschau | 6 + Hochkontrast 1280 | Kontrastmessung `.avs-excerpt__note` |
| P2 | Abspielseite A2 Teiltranskript | 6 | Hinweis T3, nicht T2 |
| P3 | Abspielseite A4 Stelle noch nicht fertig | 1280 hell + dunkel, 375 hell | |
| P4 | Abspielseite A5 kein Transkript (Basis) | 1280 hell + dunkel | Referenz für P11 |
| P5 | Abspielseite A6 keine Sprache | 6 + Hochkontrast 1280 | |
| P6 | Abspielseite A7 beschädigt | 1280 hell + dunkel, 375 hell, FR 375 hell | Zusammenspiel mit Format-Banner, falls der Browser die Datei nicht abspielt |
| P7 | Abspielseite A8 geschützt | 1280 hell + dunkel, 375 hell, FR 375 hell | |
| P8 | Abspielseite A9 Sprache nicht unterstützt | 1280 hell + dunkel, 375 hell | |
| P9 | Abspielseite A10 überlang | 6, FR 375 hell | Zahl der Stunden folgt der Einstellung (12 und 1 testen: Plural/Singular) |
| P10 | Abspielseite A11 anderer Grund | 1280 hell | kein roher Code im DOM |
| P11 | Leck-Probe: ausgeschlossener Nutzer öffnet eine Datei mit Grund `no_speech` | 1280 hell | Ausschnitt-Block byte-gleich mit P4; Container-Log zeigt keine `/excerpt`-Anfrage |
| P12 | Leck-Probe: Verweis nicht active (z. B. entzogene Freigabe, Datei noch lesbar über anderen Weg ohne active-Verweis) | 1280 hell | Ausschnitt-Block gleich P4 |

Summe: 14 Vollmatrix-Shots (S1) plus Einzelaufnahmen, rund 60 Bilder. Kein Browser und kein Docker in dieser Recherche gestartet.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | keine (shadcn nicht verwendet) | not applicable |
| Drittanbieter | keine | not applicable |

Keine neuen Frontend-Pakete, kein npm, keine Vue-Komponenten.

---

## Owner-Entscheide 14.11.2026 (vormals offene Fragen)

Die Vorgaben oben folgen jeweils der Empfehlung, außer Frage 3 (siehe Kopf des Copywriting-Abschnitts).

1. **Texte T1 bis T11 freigeben?** (D-03-04 verlangt Freigabe vor dem Bau.) Empfehlung: wie entworfen.
2. **EN "Preliminary" oder "Preview"?** Empfehlung: "Preliminary" (entspricht "vorläufig"; "Preview" klingt nach Vorschaubild, "Draft" ist für den Untertitel-Entwurf aus Phase 4 belegt).
3. **"Wird automatisch verbessert" (T2) auch für Installationen, die nie veredeln?** Owner 14.11.2026: T2 schon in Phase 3 ohne Versprechen ("Vorläufiges Transkript. Es kann Fehler enthalten."); der Zusatz zur Verbesserung kommt erst mit Phase 6 und nur für Profile, die veredeln.
4. **Testtreffer zeigt nur "Testtreffer", nie zusätzlich "Vorläufig"?** Empfehlung: ja, ein Kennzeichen je Zeile.
5. **Gründe als ruhiger Satz im grauen Ausschnitt-Block statt farbiger Banner?** Empfehlung: ja, weil die Wiedergabe funktioniert und MEDIA-04 "keine Sprache" ausdrücklich nicht als Fehler zeigen will.
6. **Eigener Zustand "wird gerade transkribiert" für eine Datei ohne fertiges Stück?** Empfehlung: nein in Phase 3, sie bleibt bei "noch kein Transkript" (A5), damit der Bestandstext und die Leck-Gleichheit unberührt bleiben; Fortschritt kommt mit Phase 9.
7. **Teiltranskript (A2/A4) überhaupt auf der Abspielseite zeigen?** Empfehlung: ja, weil Teiltreffer laut D-03-07 schon in der Suche stehen und der Nutzer sonst nicht versteht, warum spätere Stellen fehlen.
8. **Überlang: Höchstdauer nennen ("länger als 12 Stunden") und auf die Verwaltung verweisen?** Empfehlung: ja; die Grenze ist eine Instanz-Einstellung, kein Dateiinhalt, und der Verweis nennt den einzigen Weg zur Lösung.
9. **Unbekannter Grund (A11) als eigener Satz statt "kein Transkript"?** Empfehlung: eigener Satz, damit nichts still aussieht wie "noch nicht erledigt"; der rohe Code wird nie gezeigt.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
