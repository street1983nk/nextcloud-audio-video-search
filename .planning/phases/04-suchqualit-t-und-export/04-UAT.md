---
status: complete
phase: 04-suchqualit-t-und-export
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md, 04-07-SUMMARY.md, 04-08-SUMMARY.md, 04-09-SUMMARY.md, 04-10-SUMMARY.md, 04-11-SUMMARY.md, 04-12-SUMMARY.md, 04-13-SUMMARY.md, 04-14-SUMMARY.md, 04-15-SUMMARY.md, 04-16-SUMMARY.md, 04-17-SUMMARY.md]
started: 2026-11-17T12:00:00Z
updated: 2026-11-17T18:00:00Z
---

<!-- Keine lokale Live-Instanz (kein Docker). Belege sind Bilder und CI-Läufe.
     Bildordner "auswahl/" = C:/Users/Student/AppData/Local/Temp/claude/f797e4cbc4775e2e/477371b3-2eea-43f1-b45d-94414ba9acec/scratchpad/ui-abnahme-04b/auswahl/
     (69 Auswahlbilder aus nc35-amd64 des grünen Laufs "Deploy through HaRP" https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43942105866, phase-04 e5a2479).
     Kein Cold-Start-Test: Dockerfile und Startup (backend/Dockerfile, backend/docker, main.py) in Phase 4 unverändert (git log origin/phase-03..HEAD ohne Treffer). -->

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Wortformen und Komposita-Anfang finden
expected: Die Suche nach "Polizist", "Polizisten", "Polizei", "Polizeipräsidium", "Seite" und "Seitenverhältnis" liefert je 2 Treffer in der Gruppe "Audio und Video". Ein Wortanfang wie "Polizei" oder "Seite" findet auch das gesprochene Kompositum ("Polizeipräsidium", "Seitenverhältnis").
beleg: auswahl/S7__s7-term-05-polizist-w1280-light.png bis S7__s7-term-08-polizeiprasidium-w1280-light.png, S7__s7-term-13-seite-w1280-light.png, S7__s7-term-14-seitenverhaltnis-w1280-light.png; Lauf https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43942105866 (in allen sechs Beinen gleich)
result: pass

### 2. Zahlen als Wort und als Ziffer finden
expected: "20", "zwanzig", "twenty" und "vingt" finden dieselben 2 Treffer, ebenso "zwölf", "12", "twelve" und "douze", egal ob die Zahl gesprochen als Wort oder Ziffer im Transkript steht. Die Suche nach "12:30" liefert 0 Treffer ohne Fehlermeldung.
beleg: auswahl/S7__s7-term-01-20-w1280-light.png bis S7__s7-term-04-vingt-w1280-light.png, S7__s7-term-09-12-w1280-light.png bis S7__s7-term-12-douze-w1280-light.png, S7__s7-term-15-12-30-w1280-light.png, S7__s7-number-w1280-light.png; Lauf 43942105866
result: pass

### 3. Datums- und Personenfilter in der Suche
expected: Mit gesetztem Datumsfilter (2 Treffer) oder Personenfilter (1 Treffer) bleibt die Gruppe "Audio und Video" im Hauptteil der Suche, nicht unter "Partial matches" (Teiltreffer). Gefiltert wird wie in der Dateien-Suche (Änderungsdatum, Grenzen inklusiv; Person = Eigentümer oder Freigabe an Person bzw. Gruppe).
beleg: auswahl/S6__s6-date-w1280-light.png, S6__s6-date-w1280-dark.png, S6__s6-person-w1280-light.png, S6__s6-person-w1280-dark.png; Lauf 43942105866
result: pass

### 4. Untertitel-Entwurf auf der Abspielseite herunterladen
expected: Unter dem Player steht der Abschnitt "Untertitel-Entwurf" mit dem Satz "Automatisch erstellt und nicht geprüft. SRT und VTT enthalten Zeitmarken, TXT nur den Text." und drei gleich hellen Knöpfen in der Reihenfolge "SRT herunterladen", "VTT herunterladen", "TXT herunterladen". Auf 375 px und auf Französisch läuft nichts über; in Hochkontrast gut lesbar.
beleg: auswahl/X1__x1-section-w1280-light.png, X1__x1-section-w1280-dark.png, X1__x1-section-w375-light.png, X1__x1-section-w768-light.png, X1__x1-section-fr-w375-light.png, X1__x1-section-hc-1280.png, X1__x1-w1280-light.png; Audio: X1a__x1a-section-w1280-light.png; Lauf 43942105866
result: pass

### 5. Dateiname und Kopf der heruntergeladenen Datei
expected: Die heruntergeladene Datei heißt wie die Aufnahme plus Sprache und Format, auch mit Umlaut, z. B. "S7-Übung.de.srt", "S7-Übung.de.vtt", "S7-Übung.de.txt". Die TXT-Datei beginnt mit dem Dateinamen und in Zeile 2 "Untertitel-Entwurf, automatisch erstellt und nicht geprüft."; die VTT-Datei trägt denselben Satz als NOTE.
beleg: kein Bild; Downloads je Bein im Artefakt von Lauf 43942105866 (6 Dateien je Bein), Schritt "The parsers on the real downloads of phase 4" grün in Lauf https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43955067783 (11 passed je Bein)
result: pass
reported: "Kein Umlaut bei Dateinamen" (Owner-Klärung 17.11.: Umlaute ersetzen, ue/oe/ae/ss, für Download UND Nebendatei)
severity: major
retest: pass (Owner 17.11.2026, nach Gap-Plan 04-18, CI-Beleg Push 6 ee6bd68, Lauf 44019004773: S7-Uebung.de.srt/.vtt/.txt)

### 6. Hinweis auf Teilstand, solange die Datei noch verarbeitet wird
expected: Ist die Aufnahme noch nicht fertig verarbeitet, zeigt der Abschnitt zusätzlich "Transkript bis <Zeit>, Datei wird noch verarbeitet.", wobei <Zeit> die Endzeit des letzten fertigen Stücks ist (z. B. m:ss). Downloads sind trotzdem möglich; der französische Text ist vollständig und läuft auf 375 px nicht über.
beleg: auswahl/X2__x2-section-w1280-light.png, X2__x2-section-w1280-dark.png, X2__x2-section-w375-light.png, X2__x2-section-w768-light.png, X2__x2-section-fr-w375-light.png; Lauf 43942105866
result: pass

### 7. Freigabe mit Download-Sperre
expected: Bei einer Freigabe "Ansehen ohne Download" spielt die Aufnahme, der Abschnitt zeigt nur den Titel "Untertitel-Entwurf" und "Diese Freigabe erlaubt keine Downloads. Untertitel und Transkript lassen sich deshalb weder herunterladen noch ablegen." Es gibt keine Knöpfe, keine Untertitel-Spur, und das Drei-Punkte-Menü des Players bietet kein "Herunterladen". Die Suche findet die Datei weiterhin.
beleg: auswahl/X3__x3-w1280-light.png, X3__x3-section-w1280-light.png, X3__x3-section-w1280-dark.png, X3__x3-section-w375-light.png (Bilder vor dem Player-Menü-Fix); Player-Menü: Lauf https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43955067783 (Push 4, X3 controlslist=nodownload grün in sechs Beinen)
result: pass

### 8. Kein Abschnitt bei fehlender Sprache oder ausgeschlossener Datei
expected: Hat eine Datei keine Sprache, einen Grund wie "übersprungen", ist noch nicht verarbeitet oder ausgeschlossen, fehlt der Abschnitt "Untertitel-Entwurf" ganz; der graue Ausschnitt-Block erklärt bereits, warum es keinen Text gibt. Eine ausgeschlossene Datei sieht genau so aus wie eine unbekannte und verrät den Ausschluss nicht.
beleg: auswahl/X4__x4-w1280-light.png, X4__x4-reason-w1280-light.png, X4__x4-pending-w1280-light.png, X4__x4-excluded-w1280-light.png; Lauf 43942105866
result: pass

### 9. Ohne Schreibrecht im Ordner
expected: Bei einer Freigabe nur zum Lesen (Download erlaubt) steht statt "Neben die Datei legen" der Hinweis "In diesem Ordner dürfen keine Dateien angelegt werden. Herunterladen geht trotzdem." Die drei Download-Knöpfe sind gleich hell und funktionieren.
beleg: auswahl/X5__x5-section-w1280-light.png, X5__x5-section-w375-light.png; Lauf 43942105866
result: pass

### 10. Abspielseite ohne JavaScript
expected: Ohne JavaScript funktionieren die drei Downloads weiter. Der Knopf "Neben die Datei legen" ist nicht sichtbar, der Beschreibungssatz "Legt … in denselben Ordner wie die Aufnahme. Eine vorhandene Datei wird nie überschrieben." steht ohne Knopf (vom Owner so gewollt).
beleg: auswahl/X6__x6-w1280-light.png, X6__x6-section-w1280-light.png; Lauf 43942105866
result: pass

### 11. Fehlerseite mit Rückweg an die Zeitstelle
expected: Kann der Entwurf nicht erstellt werden (z. B. Container gestoppt), zeigt der Download eine Seite "Der Untertitel-Entwurf konnte nicht erstellt werden" mit "Der Untertitel-Entwurf lässt sich gerade nicht erstellen. Die Wiedergabe funktioniert trotzdem. Später erneut versuchen." Der Knopf "Zurück zur Wiedergabe" führt zur Abspielseite an dieselbe Zeitstelle; kein roher Statuscode, kein JSON.
beleg: auswahl/D2__d2-w1280-light.png, D2__d2-banner-w1280-light.png, D2__d2-banner-w1280-dark.png, D2__d2-banner-w375-light.png; Lauf 43942105866 (Zeitstelle ?t= nur im Test)
result: pass

### 12. Neben die Datei legen, nie überschreiben
expected: Ein Klick auf "Neben die Datei legen" legt die Untertiteldatei in den Ordner der Aufnahme und meldet "<Name> liegt jetzt im selben Ordner wie die Aufnahme." mit Link "In Dateien zeigen"; der Fokus bleibt auf dem Knopf. Ein zweiter Klick zeigt "Datei existiert bereits" mit "Im Ordner liegt schon eine Datei namens <Name>. Sie wird nicht überschrieben. …", die vorhandene Datei bleibt unverändert.
beleg: auswahl/E1__e1-banner-w1280-light.png, E1__e1-banner-w1280-dark.png, E1__e1-banner-w375-light.png, E1__e1-banner-w768-light.png, E2__e2-banner-w1280-light.png, E2__e2-banner-w1280-dark.png, E2__e2-banner-w375-light.png, E2__e2-banner-w768-light.png, E2__e2-banner-fr-w375-light.png, E2__e2-banner-hc-1280.png; Fehlerfälle E3 bis E7: E3__ bis E7__e*-banner-w1280-light.png; Lauf 43942105866
result: pass

### 13. Untertitel-Spur am Video standardmäßig aus
expected: Beim Öffnen eines Videos ist die Untertitel-Spur aus (bei 0:00 kein Text im Bild). Nach dem Einschalten erscheint der Untertitel zur passenden Zeit (Chromium 0:03, Firefox 0:04). Audio-Dateien haben keine Spur.
beleg: auswahl/Spur__track-off-w1280-light.png, Spur__track-off-firefox-w1280-light.png, Spur__track-w1280-light.png, Spur__track-firefox-w1280-light.png; Spurname "Deutsch, Untertitel-Entwurf" ohne Bild, nur DOM-Test (vom Owner akzeptiert); Lauf 43942105866
result: pass

### 14. Container-Routen für normale Nutzer gesperrt
expected: Ein normaler Nutzer kann Suche, Ausschnitt und Export nicht am PHP-Teil vorbei direkt beim Container abrufen: Anfragen über HaRP und über den AppAPI-Proxy enden mit 404, der Container sieht keine neue Anfrage. Über die Nextcloud-Oberfläche funktionieren Suche und Export für denselben Nutzer weiter.
beleg: Lauf https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44009336794 (Push 5, 7d9b6c3), Schritt "Container routes with user data are not reachable past the PHP app" in allen sechs deploy-Beinen grün; 04-SECURITY.md threats_open 0
result: pass

## Summary

total: 14
passed: 14
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->
- truth: "Exportierte und neben die Aufnahme gelegte Untertiteldateien tragen keine Umlaute im Dateinamen (ä->ae, ö->oe, ü->ue, Ä->Ae, Ö->Oe, Ü->Ue, ß->ss), z. B. S7-Übung.webm -> S7-Uebung.de.srt"
  status: resolved
  reason: "User reported: Kein Umlaut bei Dateinamen (Klärung: Umlaute ersetzen, für Download und Nebendatei)"
  severity: major
  test: 5
  artifacts: []
  missing: []
