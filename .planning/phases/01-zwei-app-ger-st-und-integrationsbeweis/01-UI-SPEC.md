---
phase: 1
slug: zwei-app-ger-st-und-integrationsbeweis
status: approved
reviewed_at: 2026-11-06
shadcn_initialized: false
preset: none
created: 2026-11-06
---

# Phase 1: UI Design Contract

> Visueller und Interaktionsvertrag für Phase 1 (Zwei-App-Gerüst und Integrationsbeweis). Erstellt vom gsd-ui-researcher, geprüft vom gsd-ui-checker.
> Quellen: DESIGN.md (Vorrang), Skill nextcloud-ui, 01-RESEARCH.md (Entscheide 1, 6, 7, Pattern 1 und 4, Pitfalls 1, 2, 7), STATE.md (Owner-Entscheide 06.11.), Findling `php/templates/admin.php` und `php/css/admin.css` als Referenzmuster.

Phase 1 hat genau drei UI-Flächen, sonst keine:

1. **Unified-Search-Treffer** (Provider in der PHP-App `audio_video_search`)
2. **Abspielansicht** `/apps/audio_video_search/play/{fileId}?t=754.2`
3. **Admin-Statusbereich** (Zustand der Gegen-App, Debug-Schalter für den Testtreffer)

Nicht in Phase 1: Medienübersicht (v2), Navigationseintrag der App, Export (Phase 4), Kennzeichen "vorläufig" (Phase 3), Korrektur-Editor (Phase 10), Untertitelspur `<track>` (Phase 4/10), Fortschritt und Fehlerliste im Admin (Phase 9).

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (kein React/Vite, shadcn-Gate nicht anwendbar) |
| Preset | not applicable |
| Component library | none: PHP-Templates plus reines Browser-JS ohne Bundler (DESIGN.md Stufe 3, Findling-Muster `php/templates`, `php/js`, `php/css`); Nextcloud-Server-CSS (`.section`, `.settings-hint`, `input.checkbox`, `button.primary`, `.icon-loading-small`, `.hidden-visually`) |
| Icon library | Material Design Icons als Pfaddaten in Inline-SVG (`viewBox="0 0 24 24"`, `fill="currentColor"`, `aria-hidden="true" focusable="false"`), Größe 20 px; Treffer-Thumbnail über `IMimeTypeDetector::mimeTypeIcon()` (Server-Symbole) |
| Font | Server-Schrift über `var(--font-face)`, keine Webfonts |

**Verbindliche Regeln (aus DESIGN.md, nicht verhandelbar):**
- Nur Nextcloud-CSS-Variablen, kein Hex-, RGB- oder Farbname im Code, kein `!important`, kein `outline: none`, kein `style`-Attribut.
- Flach: keine Schatten, keine Verläufe, keine Karten in Karten.
- Keine Inline-Skripte (CSP-Nonce), Skripte und Styles über `\OCP\Util::addScript()` / `addStyle()` im Template (Findling-Hinweis: im Template aufrufen, nicht in `getForm()`).
- Jeder sichtbare Text über `$l->t()` bzw. `t('audio_video_search', ...)`; jede Fremdangabe (Dateiname, Ausschnitt, Versionen) mit `p()` ausgegeben, nie unescaped.
- Hell, dunkel und hoher Kontrast ohne eigenen Code, allein über Server-Variablen.
- CSS-Klassen mit Präfix `avs-` (Muster `findling-`), IDs mit Präfix `avs-`.

---

## Spacing Scale

Alle Abstände als `calc(var(--default-grid-baseline) * n)`, Grundwert 4 px.

| Token | Value | CSS | Usage |
|-------|-------|-----|-------|
| xs | 4px | `var(--default-grid-baseline)` | Abstand Icon zu Text in Kennzeichen, Innenabstand vertikal von Links in Banner |
| sm | 8px | `* 2` | Abstand Icon zu Text in Bannern, Lücke zwischen Knöpfen einer Zeile, Abstand Überschrift zu Metazeile |
| md | 16px | `* 4` | Innenabstand Banner, Abstand zwischen Blöcken (Medium, Ausschnitt, Aktionen), Seitenrand bei 375 px |
| lg | 24px | `* 6` | Seitenrand ab 768 px, Abstand zwischen Admin-Unterblöcken |
| xl | 32px | `* 8` | Oberer Abstand der Abspielansicht unter dem Kopf ab 768 px |

Nicht genutzt in Phase 1: 48 px, 64 px.

Exceptions:
- Klickflächen: mindestens `var(--default-clickable-area)` (34 px, Server-Wert), bei `@media (pointer: coarse)` mindestens 44 px. Gilt für Knöpfe, Links in Bannern und die Checkbox-Zeile.
- Lesespalte der Abspielansicht: `max-width: calc(var(--default-grid-baseline) * 240)` (960 px), linksbündig im Inhaltsbereich, nicht zentrierter Hero-Block.
- Video: `width: 100%`, `max-height: 70vh`, `object-fit: contain`; Audio: `width: 100%`. Keine feste Höhe.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body (Fließtext, Bannertext, Ausschnitt, Metazeile) | 15px = `var(--default-font-size)` | 400 | `var(--default-line-height)` |
| Label (Hinweise `.settings-hint`, Ausschnitt-Etikett, "Zuletzt geprüft") | 13px = `var(--font-size-small)` | 400 | `var(--default-line-height)` |
| Heading (h2: Dateiname auf der Abspielseite, Abschnittstitel im Admin) | 20px | 700 | `var(--default-line-height)` |
| Subheading (h3 im Admin, z. B. "Testtreffer") | 15px = `var(--default-font-size)` | 700 | `var(--default-line-height)` |

Genau drei Größen (13, 15, 20) und zwei Gewichte (400, 700). Kein Display-Grad in Phase 1. Zeilenhöhe überall ausschließlich `var(--default-line-height)`, kein Zahlenwert im Code.

Zusatzregeln:
- Zeitmarken (`12:34`, `1:02:03`) mit `font-variant-numeric: tabular-nums`, im Markup als `<time datetime="PT12M34S">12:34</time>`.
- Dateinamen und Ausschnitte: `overflow-wrap: anywhere`, damit lange Namen ohne Leerzeichen bei 375 px nicht überlaufen. Kein Abschneiden des Dateinamens in der Überschrift.
- Rang über Gewicht, nicht über weitere Größen.

---

## Color

Werte sind Server-Variablen. Die Hex-Angaben sind nur Referenz des Standard-Themes (DESIGN.md) und gehören nie in den Code.

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `--color-main-background` (Ref. #ffffff) | Seitengrund der Abspielansicht und des Admin-Bereichs |
| Secondary (30%) | `--color-background-hover` (Ref. #f5f5f5), Trennlinie `--color-border` | Fläche des Ausschnitt-Blocks, Kennzeichen (Version), Zeilen der Zustandsübersicht |
| Accent (10%) | `--color-primary-element` mit `--color-primary-element-text` (Ref. #00679e / #ffffff) | nur die unten gelisteten Elemente |
| Destructive | `--color-error` mit `--color-error-text`, Icon `--color-element-error` | nur Fehler-Banner; Phase 1 hat keine zerstörende Aktion |

Gedämpfter Text: `--color-text-maxcontrast` für Label-Rolle, Metazeile und "Zuletzt geprüft".

Statuspaare (Pair Rule, nie gemischt):

| Status | Fläche / Text | Icon-Farbe | MDI-Icon |
|--------|---------------|-----------|----------|
| Fehler | `--color-error` / `--color-error-text` | `--color-element-error` | `alert-circle-outline` |
| Warnung | `--color-warning` / `--color-warning-text` | `--color-element-warning` | `alert-outline` |
| Hinweis | `--color-info` / `--color-info-text` | `--color-element-info` | `information-outline` |
| Erfolg | `--color-success` / `--color-success-text` | `--color-element-success` | `check-circle-outline` |

Accent reserved for:
1. Die eine Aktion in einem Admin-Banner (z. B. "Apps öffnen"), als `button.primary`-gleich gestalteter Link (Findling `findling-banner__link`).
2. Den gesetzten Zustand der Debug-Checkbox (Server-Stil `input.checkbox`, kein eigener Code).

Sonst nirgends: nicht für Zeitmarken, nicht für Überschriften, nicht für Links auf der Abspielseite, nicht für "Erneut prüfen" oder "Zur Zeitstelle springen" (beide sekundäre Server-Knöpfe ohne `primary`).

Never Color Alone: Jeder Status trägt Icon und Satz; Farbe ist nie alleiniger Träger.

---

## Fläche 1: Unified-Search-Treffer

Rendert der Nextcloud-Web-Client selbst (`SearchResult.vue`); die App liefert nur Daten. Kein eigenes CSS, kein eigenes JS.

| Feld | Vertrag |
|------|---------|
| Gruppenname (Provider) | DE "Audio und Video", EN "Audio and video", FR "Audio et vidéo" |
| `title` | Dateiname (`$node->getName()`), unverändert |
| `subline` | `{zeit} · {ausschnitt}`; Trennzeichen Mittelpunkt U+00B7 mit je einem Leerzeichen, nie Gedankenstrich |
| Zeitformat | unter 1 h `m:ss` (`0:05`, `12:34`), ab 1 h `h:mm:ss` (`1:02:03`); Ziffern ohne Lokalisierung |
| Ausschnitt | reiner Text, höchstens 120 Zeichen, an Wortgrenze gekürzt, Auslassung `…` (U+2026) am gekürzten Ende; keine HTML-Hervorhebung in Phase 1 |
| Testtreffer | `subline` = `{zeit} · {Testtreffer} · {ausschnitt}` mit übersetztem Wort (siehe Copy), damit ein Debug-Treffer nie wie ein echter aussieht |
| `thumbnailUrl` | Mime-Symbol des Servers (`audio`/`video`), keine Vorschaubilder |
| `resourceUrl` | `linkToRouteAbsolute('audio_video_search.page.play', ['fileId' => …, 't' => '754.2'])`; `t` mit genau einer Nachkommastelle |
| Attribute (Mobil) | `fileId` und `path` gesetzt (Owner 06.11.): Android/iOS öffnen die Datei nativ ab 0:00, kein Zeitsprung. Nie `fileId` ohne `path` |
| Leer | Keine Treffer oder Backend gestört: Provider liefert eine leere Liste; der Client zeigt seinen eigenen Leerzustand. Kein Fehlertext für Nutzer in der Suche (Admin sieht den Grund im Statusbereich) |

---

## Fläche 2: Abspielansicht

Route `GET /apps/audio_video_search/play/{fileId}?t={sekunden}`, `TemplateResponse` im normalen Nextcloud-Rahmen (Kopfleiste sichtbar), ohne App-Navigation. Serverseitig gerendert; JS ergänzt nur Seek, Fehlerzuordnung und den Sprungknopf.

### Aufbau (Reihenfolge im DOM = Lese- und Tab-Reihenfolge)

1. Wurzel `<div id="app-content" class="avs-play">`; kein zweites `<main>` (der Server-Rahmen liefert die Landmarke). Auf NC 33, 34, 35 prüfen.
2. `h2` Dateiname.
3. Metazeile (Body, `--color-text-maxcontrast`): "Start bei {zeit}".
4. Banner-Bereich `#avs-play-state` (leer im Normalfall; bei serverseitig bekannten Fehlern gefüllt, `role="alert"`).
5. Medium: `<video>` für `video/*`, `<audio>` für `audio/*`, mit `controls`, `preload="metadata"`, `playsinline`, ohne `autoplay`, `src` = WebDAV-Adresse mit Fragment `#t={sekunden}`. `aria-label` = "Wiedergabe: {Dateiname}" (siehe Copy).
6. Aktionszeile (sm-Lücke, bricht bei 375 px um): Knopf "Zur Zeitstelle {zeit} springen" (nur mit JS sichtbar, `hidden` im Markup, JS entfernt `hidden`; nur wenn `t > 0`), Link "In Dateien anzeigen".
7. Ausschnitt-Block (Fläche `--color-background-hover`, Radius `--border-radius-container`, Innenabstand md): Label "Ausschnitt an dieser Stelle", darunter der Ausschnitt als `<blockquote>` mit Body-Typo. Bei Fehlen ersetzt durch den Leer- bzw. Nicht-abrufbar-Hinweis.

### Interaktion

- Startzeit: Server validiert `t` (Zahl, 0 bis Medienlänge falls bekannt, höchstens eine Nachkommastelle beim Ausgeben). Ungültiges oder fehlendes `t` = Start bei 0:00 ohne Fehlermeldung. Ein `#t=` in der Seitenadresse hat Vorrang vor `?t=` (Pattern 4).
- Seek: Fragment am Medium wirkt ohne JS; JS setzt zusätzlich `currentTime` nach `loadedmetadata`.
- Kein Autoplay (WCAG 1.4.2, uneinheitliche Autoplay-Regeln der Browser). Nutzer startet über die nativen Bedienelemente; Fokus wird beim Laden nicht verschoben.
- "Zur Zeitstelle springen": setzt `currentTime` auf die Zeitmarke, startet nicht von selbst, setzt danach den Fokus auf das Medium.
- Keine eigenen Tastenkürzel (Konflikt mit Nextcloud-Kürzeln vermeiden); Bedienung ausschließlich über native Medien-Bedienelemente.
- Fehlerzuordnung im Browser: Bei `error` am Medium führt JS ein `fetch(src, {method: 'HEAD', credentials: 'same-origin'})` aus (gleiche Origin, nichts verlässt den Server) und ordnet zu: 403 = Download gesperrt, 404 = verschoben, sonst nach `MediaError.code` (2 = Netz, 3/4 = Format oder beschädigt, Rest = allgemein). Das Medium wird bei jedem Fehler ausgeblendet (`hidden`), der Banner erscheint mit `role="alert"`.
- Ohne JS: Seite und Medium funktionieren vollständig ab Zeitstelle; nur Sprungknopf und Fehlerzuordnung im Browser fehlen.

### Zustände der Abspielansicht

| Zustand | Erkennung | Darstellung | Dateiname sichtbar | HTTP |
|---------|-----------|-------------|--------------------|------|
| Bereit | Datei lesbar, Mime audio/video | Aufbau wie oben | ja | 200 |
| Laden | Medium lädt Metadaten | native Lade-Anzeige des Browsers, keine eigene | ja | 200 |
| Kein Transkript (Leer) | Backend kennt die Datei nicht | Ausschnitt-Block zeigt Leer-Hinweis, Wiedergabe normal | ja | 200 |
| Ausschnitt nicht abrufbar | Backend nicht erreichbar, Versions-Drift, Zeitbudget überschritten | Ausschnitt-Block zeigt Hinweis, Wiedergabe normal | ja | 200 |
| Nicht verfügbar | Datei fehlt, keine Leserechte, Papierkorb, fremde fileId | Fehler-Banner, kein Medium, kein `h2`-Dateiname (statt dessen `h2` "Wiedergabe"); fehlend und verboten sind nicht unterscheidbar | **nein** | 404 |
| Keine Audio-/Videodatei | lesbar, Mime passt nicht | Hinweis-Banner, kein Medium, Link "In Dateien anzeigen" | ja | 200 |
| Download gesperrt | Freigabe ohne Download und `shareapi_allow_view_without_download` aus; serverseitig vorab geprüft, sonst HEAD 403 | **Hinweis**-Banner (kein Fehler), kein Medium; Treffer bleibt in der Suche | ja | 200 |
| Verschoben während der Sitzung | HEAD 404 nach Seitenaufbau | Warn-Banner, Knopf "Seite neu laden" | ja (Name vom Seitenaufbau) | 200 |
| Format oder Datei defekt | `MediaError` 3 oder 4 | Fehler-Banner, Link "Datei herunterladen" nur wenn Download erlaubt | ja | 200 |
| Verbindung abgebrochen | `MediaError` 2 | Fehler-Banner, Knopf "Seite neu laden" | ja | 200 |
| Sonstiger Fehler | übrige Fälle | Fehler-Banner, Knopf "Seite neu laden" | ja | 200 |
| Sitzung abgelaufen | Server leitet zur Anmeldung | Server-Anmeldeseite; `?t=` übersteht die Umleitung (Pitfall 1) | n. a. | 303 |

Banner-Aufbau (gilt auch für Fläche 3): `<div class="avs-banner avs-banner--{error|warning|info|success}">` mit Icon (20 px) in einem eigenen Icon-Container mit `display: flex`, `align-items: center` und `height: var(--default-line-height)`, damit es ohne Pixel-Versatz auf der ersten Textzeile sitzt; Titelzeile in 700, Satz in 400, optional eine Aktion. Innenabstand md, Radius `--border-radius-container`, Abstand sm zwischen Icon und Text, keine Rahmenlinie, kein Schatten.

### Responsives Verhalten

| Breite | Vertrag |
|--------|---------|
| 375 px | Seitenrand md, Medium volle Breite, Aktionszeile umbrechend, jeder Knopf mind. 44 px hoch (`pointer: coarse`) |
| 768 px | Seitenrand lg, oberer Abstand xl |
| 1280 px | Lesespalte max. 960 px, linksbündig |

---

## Fläche 3: Admin-Statusbereich

Eigene Admin-Sektion "Audio & Video Search" (`IIconSection`, ID `audio_video_search`, Priorität 75, monochromes App-Icon `app-dark.svg`, Findling-Muster). Seite serverseitig vollständig gerendert, ohne Lade-Skelett (Findling-Regel: ohne JS lesbar).

### Aufbau

1. `div.section` mit `h2` "Verbindung zum Backend".
2. Genau ein Zustands-Banner (Tabelle unten), `id="avs-backend-state"`, Container mit `role="status" aria-live="polite"`.
3. Zeile mit Versionen (Label-Rolle): "Diese App: {a} · Backend: {b}" (Backend-Wert "nicht bekannt", wenn nicht ermittelbar).
4. Zeile "Zuletzt geprüft: {Uhrzeit}" (Label-Rolle, `IDateTimeFormatter`, Sprache des Admins).
5. Knopf "Erneut prüfen" (sekundär). Während der Prüfung: `disabled`, `.icon-loading-small` davor, Text "Wird geprüft…", `aria-busy="true"` am Statuscontainer. Ergebnis ersetzt Banner und Zeilen an Ort und Stelle (JS ersetzt Textknoten, baut kein Markup, Findling-Muster). Ohne JS: Seite neu laden zeigt den neuen Stand.
6. Nur wenn `config.php` `'debug' => true`: Unterblock `h3` "Testtreffer" mit Checkbox (`input.checkbox` + `label`), Hinweistext, Speicherstatus. Ohne Debug-Modus wird der Block nicht gerendert und der Provider ignoriert den Schalter (serverseitig, nicht nur ausgeblendet).

### Zustände Gegen-App (Owner 06.11., Research Entscheid 6)

| Zustand | Banner | Suche | Aktion |
|---------|--------|-------|--------|
| `ok` | Erfolg | normal | keine |
| `version_patch_differs` | Hinweis | normal | keine |
| `version_drift` (Major.Minor ungleich) | Fehler | leer | Link "Apps öffnen" |
| `backend_missing` | Fehler | leer | Link "Apps öffnen" |
| `backend_disabled` | Fehler | leer | Link "Apps öffnen" |
| `backend_unreachable` | Fehler | leer | Link "Apps öffnen" |
| `no_app_api` | Fehler | leer | Link "Apps öffnen" |
| Neuprüfung gescheitert (Anfrage an die eigene Route schlägt fehl) | Warnung, zusätzlich zum letzten Banner | unverändert | keine |

Kein Banner nennt Dateinamen oder Pfade. Versionen werden genannt (für den Admin nötig, kein Personenbezug). Link "Apps öffnen" zielt auf die App-Verwaltung des Servers (ab NC 34 `appstore.page.viewApps`, bis NC 33 `settings.AppSettings.viewApps`), öffnet im selben Tab, ist der einzige Akzent im Banner.

### Debug-Schalter

- Speichern sofort beim Umschalten (Server-Muster der Admin-Einstellungen), kein Speichern-Knopf.
- Während des Speicherns Checkbox `disabled`; danach Statustext in Label-Rolle neben dem Schalter mit `role="status"`: "Gespeichert" (verschwindet nach 3 s) oder Fehlertext (bleibt, Checkbox springt auf den alten Wert zurück).
- Aus heißt: Testtreffer erscheinen sofort nicht mehr in der Suche. Die angelegten Testdaten bleiben; Entfernen nur über `occ` (keine zerstörende Aktion in der Oberfläche).
- Ist noch kein Testtreffer angelegt, steht darunter der Leer-Hinweis mit dem `occ`-Befehl in `<code>`. Der Befehlsname muss mit dem Plan übereinstimmen (Platzhalter hier: `occ audio_video_search:sample`).

### Backend-App (ExApp) selbst

Die ExApp `audio_video_search_backend` bekommt in Phase 1 keine eigene Oberfläche außer einem statischen Beschreibungssatz in ihren deklarativen Einstellungen (falls das Skelett die Seite rendert), siehe Copy "Backend-Beschreibung".

---

## Copywriting Contract

Regeln: Deutsch zuerst; `de` und `de_DE` erhalten **denselben** Text in unpersönlicher Form (weder du noch Sie, Findling-Muster), damit beide Kataloge ohne zweite Fassung im Gleichstand bleiben. Französisch mit Vous- bzw. Infinitivform und geschütztem Leerzeichen (U+00A0) vor `:` `;` `?`. Echte Umlaute, keine Gedankenstriche (U+2013, U+2014), keine Emojis, kein Ausrufezeichen, Satzanfang groß. Platzhalter als `%1$s`/`%2$s` (PHP) bzw. `{name}` (JS) in allen drei Sprachen gleich. "Audio & Video Search" und "AppAPI" werden nicht übersetzt.

### Pflichtfelder (Template)

| Element | Copy (DE) |
|---------|-----------|
| Primary CTA | Abspielansicht: native Abspieltaste des Browsers (keine eigene Hauptaktion). Admin: "Apps öffnen" im Fehler-Banner |
| Empty state heading | Abspielansicht: (kein eigener Titel, Hinweis im Ausschnitt-Block) "Für diese Datei gibt es noch kein Transkript." |
| Empty state body | Admin, Testtreffer: "Noch kein Testtreffer angelegt. Anlegen mit:" + `occ audio_video_search:sample` |
| Error state | "Diese Datei ist nicht verfügbar" / "Sie wurde gelöscht oder verschoben, oder die Freigabe besteht nicht mehr. Eine neue Suche zeigt die aktuellen Treffer." |
| Destructive confirmation | keine: Phase 1 hat keine zerstörende Aktion in der Oberfläche |

### Fläche 1: Unified Search

| Schlüssel | DE | EN | FR |
|-----------|----|----|----|
| Provider-Name | Audio und Video | Audio and video | Audio et vidéo |
| Testtreffer-Kennzeichen | Testtreffer | Test result | Résultat de test |

### Fläche 2: Abspielansicht

| Schlüssel | DE | EN | FR |
|-----------|----|----|----|
| Titel bei Fehler ohne Dateiname (h2) | Wiedergabe | Playback | Lecture |
| Metazeile | Start bei %s | Starts at %s | Début à %s |
| Medium `aria-label` | Wiedergabe: %s | Playback: %s | Lecture : %s |
| Sprungknopf | Zur Zeitstelle %s springen | Jump to %s | Aller à %s |
| Link Dateien | In Dateien anzeigen | Show in Files | Afficher dans Fichiers |
| Ausschnitt-Label | Ausschnitt an dieser Stelle | Excerpt at this point | Extrait à ce moment |
| Leer: kein Transkript | Für diese Datei gibt es noch kein Transkript. | There is no transcript for this file yet. | Il n'y a pas encore de transcription pour ce fichier. |
| Ausschnitt nicht abrufbar | Der Ausschnitt ist gerade nicht abrufbar. Die Wiedergabe funktioniert trotzdem. | The excerpt cannot be loaded right now. Playback works regardless. | L'extrait n'est pas disponible pour le moment. La lecture fonctionne quand même. |
| Nicht verfügbar, Titel | Diese Datei ist nicht verfügbar | This file is not available | Ce fichier n'est pas disponible |
| Nicht verfügbar, Satz | Sie wurde gelöscht oder verschoben, oder die Freigabe besteht nicht mehr. Eine neue Suche zeigt die aktuellen Treffer. | It was deleted or moved, or it is no longer shared. A new search shows the current results. | Il a été supprimé ou déplacé, ou il n'est plus partagé. Une nouvelle recherche affiche les résultats actuels. |
| Nicht verfügbar, Aktion | Zu Dateien | Go to Files | Aller à Fichiers |
| Kein Medium, Titel | Diese Datei ist keine Audio- oder Videodatei | This file is not an audio or video file | Ce fichier n'est ni un fichier audio ni un fichier vidéo |
| Kein Medium, Satz | Die Abspielansicht spielt nur Audio und Video ab. | This view only plays audio and video. | Cette vue ne lit que l'audio et la vidéo. |
| Download gesperrt, Titel | Abspielen ist für diese Freigabe gesperrt | Playback is blocked for this share | La lecture est bloquée pour ce partage |
| Download gesperrt, Satz | Die Freigabe erlaubt kein Herunterladen, deshalb spielt diese Instanz die Datei nicht ab. Wer die Datei freigegeben hat, kann das Herunterladen erlauben. Der Treffer bleibt in der Suche sichtbar. | This share does not allow downloads, so this instance does not play the file. The person who shared it can allow downloads. The result stays visible in search. | Ce partage n'autorise pas le téléchargement, cette instance ne lit donc pas le fichier. La personne qui l'a partagé peut autoriser le téléchargement. Le résultat reste visible dans la recherche. |
| Verschoben, Titel | Die Datei wurde inzwischen verschoben oder umbenannt | The file was moved or renamed in the meantime | Le fichier a été déplacé ou renommé entre-temps |
| Verschoben, Satz | Seite neu laden, um sie an ihrem neuen Ort zu finden. | Reload to find it at its new location. | Rechargez la page pour le retrouver à son nouvel emplacement. |
| Format/defekt, Titel | Die Datei lässt sich hier nicht abspielen | The file cannot be played here | Le fichier ne peut pas être lu ici |
| Format/defekt, Satz | Der Browser kennt das Format nicht, oder die Datei ist beschädigt. Die Datei herunterladen und mit einem anderen Programm öffnen oder einen anderen Browser versuchen. | The browser does not support the format, or the file is damaged. Download the file and open it in another program, or try another browser. | Le navigateur ne prend pas en charge ce format, ou le fichier est endommagé. Téléchargez le fichier et ouvrez-le avec un autre programme, ou essayez un autre navigateur. |
| Format/defekt, Aktion | Datei herunterladen | Download file | Télécharger le fichier |
| Netz, Titel | Die Verbindung zum Server ist abgebrochen | The connection to the server was lost | La connexion au serveur a été interrompue |
| Netz, Satz | Die Verbindung prüfen und die Seite neu laden. | Check the connection and reload the page. | Vérifiez la connexion et rechargez la page. |
| Sonstiges, Titel | Die Datei konnte nicht geladen werden | The file could not be loaded | Le fichier n'a pas pu être chargé |
| Sonstiges, Satz | Die Seite neu laden. Bleibt der Fehler, die Verwaltung dieser Instanz informieren. | Reload the page. If the error stays, tell the administrators of this instance. | Rechargez la page. Si l'erreur persiste, prévenez l'administration de cette instance. |
| Aktion Seite neu laden | Seite neu laden | Reload page | Recharger la page |

### Fläche 3: Admin-Statusbereich

| Schlüssel | DE | EN | FR |
|-----------|----|----|----|
| Sektionsname | Audio & Video Search | Audio & Video Search | Audio & Video Search |
| h2 | Verbindung zum Backend | Connection to the backend | Connexion au backend |
| `ok` | Beide Apps sind verbunden und haben die Version %s. | Both apps are connected and run version %s. | Les deux applications sont connectées et en version %s. |
| `version_patch_differs` | Beide Apps sind verbunden. Die Versionen unterscheiden sich nur in der letzten Stelle: diese App %1$s, Backend %2$s. Die Suche arbeitet normal. Beim nächsten Update beide Apps auf dieselbe Version bringen. | Both apps are connected. Their versions differ only in the last part: this app %1$s, backend %2$s. Search works normally. Bring both apps to the same version at the next update. | Les deux applications sont connectées. Leurs versions ne diffèrent que par le dernier chiffre : cette application %1$s, backend %2$s. La recherche fonctionne normalement. Mettez les deux applications à la même version lors de la prochaine mise à jour. |
| `version_drift` | Die beiden Apps haben unterschiedliche Versionen: diese App %1$s, Backend %2$s. Solange sie nicht zusammenpassen, liefert die Suche keine Treffer aus Audio und Video. Beide Apps auf dieselbe Version bringen. | The two apps run different versions: this app %1$s, backend %2$s. As long as they do not match, search returns no results from audio and video. Bring both apps to the same version. | Les deux applications ont des versions différentes : cette application %1$s, backend %2$s. Tant qu'elles ne correspondent pas, la recherche ne renvoie aucun résultat audio ou vidéo. Mettez les deux applications à la même version. |
| `backend_missing` | Die App "Audio & Video Search Backend" ist nicht installiert. Ohne sie findet die Suche nichts in Audio und Video. Die App unter Apps installieren. | The app "Audio & Video Search Backend" is not installed. Without it, search finds nothing in audio and video. Install the app under Apps. | L'application « Audio & Video Search Backend » n'est pas installée. Sans elle, la recherche ne trouve rien dans l'audio et la vidéo. Installez l'application dans Applications. |
| `backend_disabled` | Die App "Audio & Video Search Backend" ist installiert, aber deaktiviert. Solange liefert die Suche keine Treffer aus Audio und Video. Die App unter Apps aktivieren. | The app "Audio & Video Search Backend" is installed but disabled. Until it is enabled, search returns no results from audio and video. Enable the app under Apps. | L'application « Audio & Video Search Backend » est installée mais désactivée. En attendant, la recherche ne renvoie aucun résultat audio ou vidéo. Activez l'application dans Applications. |
| `backend_unreachable` | Das Backend antwortet nicht. Solange liefert die Suche keine Treffer aus Audio und Video. Unter Apps prüfen, ob "Audio & Video Search Backend" läuft, und in den AppAPI-Einstellungen, ob der Deploy-Daemon erreichbar ist. | The backend does not answer. Until it does, search returns no results from audio and video. Check under Apps that "Audio & Video Search Backend" is running, and in the AppAPI settings that the deploy daemon can be reached. | Le backend ne répond pas. En attendant, la recherche ne renvoie aucun résultat audio ou vidéo. Vérifiez dans Applications que « Audio & Video Search Backend » fonctionne, et dans les paramètres AppAPI que le démon de déploiement est joignable. |
| `no_app_api` | Die App AppAPI ist nicht aktiviert. Das Backend dieser App läuft nur über AppAPI. AppAPI unter Apps aktivieren und einen Deploy-Daemon einrichten. | The AppAPI app is not enabled. The backend of this app only runs through AppAPI. Enable AppAPI under Apps and set up a deploy daemon. | L'application AppAPI n'est pas activée. Le backend de cette application ne fonctionne qu'avec AppAPI. Activez AppAPI dans Applications et configurez un démon de déploiement. |
| Neuprüfung gescheitert | Der Zustand konnte nicht neu geprüft werden. Angezeigt ist der Stand beim Laden der Seite. | The state could not be checked again. Shown is the state from when the page was loaded. | L'état n'a pas pu être vérifié de nouveau. L'affichage correspond à l'état au chargement de la page. |
| Banner-Aktion | Apps öffnen | Open Apps | Ouvrir Applications |
| Versionszeile | Diese App: %1$s · Backend: %2$s | This app: %1$s · Backend: %2$s | Cette application : %1$s · Backend : %2$s |
| Version unbekannt | nicht bekannt | unknown | inconnue |
| Zuletzt geprüft | Zuletzt geprüft: %s | Last checked: %s | Dernière vérification : %s |
| Knopf Prüfen | Erneut prüfen | Check again | Vérifier à nouveau |
| Knopf während Prüfung | Wird geprüft… | Checking… | Vérification… |
| h3 Debug | Testtreffer | Test result | Résultat de test |
| Checkbox-Label | Testtreffer in der Suche zeigen | Show the test result in search | Afficher le résultat de test dans la recherche |
| Checkbox-Hinweis | Nur für Tests. Der Testtreffer erscheint nur, solange dieser Schalter an ist und die Instanz im Debug-Modus läuft. Ausschalten blendet ihn sofort aus, die Testdaten bleiben erhalten. | For testing only. The test result only appears while this switch is on and the instance runs in debug mode. Switching it off hides it at once, the test data stays. | Uniquement pour les tests. Le résultat de test n'apparaît que tant que cette option est activée et que l'instance est en mode débogage. La désactiver le masque immédiatement, les données de test sont conservées. |
| Leer: kein Testtreffer | Noch kein Testtreffer angelegt. Anlegen mit: | No test result yet. Create one with: | Aucun résultat de test pour l'instant. Pour en créer un : |
| Gespeichert | Gespeichert | Saved | Enregistré |
| Nicht gespeichert | Nicht gespeichert. Erneut versuchen. | Not saved. Try again. | Non enregistré. Réessayez. |
| Backend-Beschreibung (ExApp-Einstellungen) | Diese App ist das Backend von Audio & Video Search und braucht die App "Audio & Video Search". Der Zustand beider Apps steht unter Verwaltung, Audio & Video Search. | This app is the backend of Audio & Video Search and needs the app "Audio & Video Search". The state of both apps is shown under Administration, Audio & Video Search. | Cette application est le backend d'Audio & Video Search et nécessite l'application « Audio & Video Search ». L'état des deux applications figure dans Administration, Audio & Video Search. |

Hinweis für den Planer: Alle Texte gehen in `php/l10n/{de,de_DE,en,fr}.json/.js` (PHP-App) und, für die Backend-Beschreibung, in `backend/l10n/`. Der Dreisprachigkeits-Test (Muster `tests/test_trilingual.py`) und ein Umlaut-/Gedankenstrich-Audit gehören in den Plan.

---

## Barrierefreiheit (WCAG 2.1 AA, BITV)

- Tastatur: Jede Aktion per Tab erreichbar, Reihenfolge = DOM-Reihenfolge oben; native Medien-Bedienelemente (Leertaste, Pfeiltasten je Browser) ohne Eingriff.
- Fokus: Server-Fokusring sichtbar, nie entfernt. Festgelegte Fokuspunkte: **Abspielansicht = Medium-Element** (`#avs-media`), Ziel nach "Zur Zeitstelle springen"; ersetzt ein Fehler das Medium, geht der Fokus per `tabindex="-1"` auf den Fehler-Banner, der zusätzlich über `role="alert"` angesagt wird. **Admin = Zustands-Banner** (`#avs-backend-state`, `tabindex="-1"`), Ziel nach Abschluss von "Erneut prüfen". Beim Seitenaufruf wird der Fokus nirgends verschoben.
- Statusänderungen im Admin über `role="status"`/`aria-live="polite"`; Lade-Zustand über `aria-busy`.
- Icons dekorativ (`aria-hidden`), Bedeutung immer im Text. Knöpfe ohne sichtbaren Text gibt es in Phase 1 nicht.
- Seitentitel (2.4.2): Abspielansicht trägt den Dateinamen im Dokumenttitel, bei Fehler ohne Dateiname "Wiedergabe"; API je NC-Version beim Plan prüfen.
- Kein Autoplay (1.4.2). Kontrast nur über Server-Variablen, hoher-Kontrast-Theme muss lesbar bleiben.
- Zeitmarke maschinenlesbar über `<time datetime>`.

---

## Prüfvertrag für die Abnahme

- Playwright gegen NC 33, 34, 35; Breiten 375, 768, 1280 px; Theme hell und dunkel, zusätzlich hoher Kontrast bei 1280 px.
- Je Fläche mindestens: Treffer in der Unified Search (inkl. Testtreffer-Kennzeichen); Abspielansicht Bereit mit `?t=` (Medium steht nach `loadedmetadata` an der Zeitstelle, Toleranz 0,5 s); abgemeldet öffnen bleibt an der Zeitstelle; Nicht verfügbar (fremde fileId, keine Dateinamen im DOM); Download gesperrt (`shareapi_allow_view_without_download` aus); Format nicht abspielbar; Admin in `ok`, `version_patch_differs`, `version_drift`, `backend_missing`, `backend_disabled`, `backend_unreachable`; Debug-Block sichtbar nur mit `debug => true`.
- Testmedien WebM (VP9/Opus) und Ogg/Opus (Pitfall 7), `canPlayType` loggen.
- Dreisprachigkeits-Test (Muster `tests/test_trilingual.py`) prüft zusätzlich `fr.json` und `fr.js` aller Kataloge: ein normales Leerzeichen (U+0020) direkt vor `:` `;` `?` `!` oder nach `«` bzw. vor `»` lässt den Test fehlschlagen; verlangt ist U+00A0. Platzhalter wie `%1$s` und URLs sind ausgenommen. Gleicher Test lehnt U+2013/U+2014 und Emojis in allen Sprachen ab.
- Danach `impeccable critique` und `impeccable audit`, Owner-Abnahme gemeinsam per Playwright.
- Kein Browser und kein Docker-Stack in dieser Recherche gestartet (RAM-Vorgabe).

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | keine (shadcn nicht verwendet) | not applicable |
| Drittanbieter | keine | not applicable |

Keine neuen Frontend-Pakete: kein npm, kein Bundler, keine Vue-Komponenten in Phase 1.

---

## Folgeaufgabe für den Plan

DESIGN.md und PRODUCT.md enthalten noch `TODO(skeleton)`-Stellen. DESIGN.md muss die gewählte Stufe festhalten ("Stufe 3: PHP-Templates in der Begleit-App `audio_video_search`, weil Unified Search und Abspielroute nur dort möglich sind; die ExApp hat nur deklarative Einstellungen"), PRODUCT.md die Nutzer und den Core Value aus PROJECT.md. Eine kleine Aufgabe im Plan reicht.

---

## Offene Owner-Fragen (mit Empfehlung)

Die Vorgaben oben folgen jeweils der Empfehlung; ändert der Owner etwas, passt der Planer nur die betroffene Zeile an.

1. **Autoplay auf der Abspielansicht?** Empfehlung: nein. Medium steht an der Zeitstelle, Start per Abspieltaste (WCAG 1.4.2, Browser blockieren Autoplay mit Ton uneinheitlich).
2. **Eigene Admin-Sektion "Audio & Video Search" statt "Weitere Einstellungen"?** Empfehlung: eigene Sektion wie Findling, weil in späteren Phasen Fortschritt, Profile, Sprachen und Ausschlüsse dazukommen.
3. **Deutsch unpersönlich (weder du noch Sie), `de` = `de_DE`?** Empfehlung: ja, Findling-Muster, ein Text für beide Kataloge.
4. **Testtreffer in der Unterzeile sichtbar als "Testtreffer" kennzeichnen?** Empfehlung: ja (Prinzip ehrliche Zustände).
5. **Knopf "Zur Zeitstelle springen" in Phase 1?** Empfehlung: ja, kleiner Aufwand, hilft Tastatur- und Screenreader-Nutzern nach dem Spulen zurück zur Fundstelle.
6. **Debug-Schalter aus = nur ausblenden, Testdaten bleiben, Löschen nur per `occ`?** Empfehlung: ja, keine zerstörende Aktion in der Oberfläche.
7. **App-Name "Audio & Video Search" in allen drei Sprachen unübersetzt, Gruppenname der Suche dagegen übersetzt ("Audio und Video")?** Empfehlung: ja.
8. **Download gesperrt als Hinweis (blau) statt Fehler (rot)?** Empfehlung: Hinweis, weil es eine bewusste Einstellung von Freigabe und Admin ist, kein Defekt (Research Entscheid 1).

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
