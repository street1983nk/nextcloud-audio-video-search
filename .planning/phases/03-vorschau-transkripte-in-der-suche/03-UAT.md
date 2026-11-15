---
status: complete
phase: 03-vorschau-transkripte-in-der-suche
source: [03-01-SUMMARY.md, 03-10-SUMMARY.md, 03-11-SUMMARY.md, 03-12-SUMMARY.md, 03-13-SUMMARY.md, 03-13b-SUMMARY.md, 03-14-SUMMARY.md, 03-15-SUMMARY.md, 03-16b-SUMMARY.md, 03-17-SUMMARY.md, 03-18-SUMMARY.md, 03-18b-SUMMARY.md, 03-19-SUMMARY.md, 03-20-SUMMARY.md, 03-21-SUMMARY.md]
started: 2026-11-15T13:05:00Z
updated: 2026-11-15T13:10:50Z
---

## Current Test

[testing complete]

## Tests

### 1. Gesprochenes Wort in der Suche finden
expected: Nach dem Hochladen einer Aufnahme (MP3, M4A, WAV, OGG, Opus, FLAC, MP4, MOV, MKV, WebM) findet der Nutzer wenige Minuten später ein gesprochenes Wort (z. B. "Universität") in der Nextcloud-Suche. Ein Klick auf den Treffer springt an die passende Stelle der Aufnahme.
beleg: 03-18 Kernweg @preview in deploy-harp; CI gruen 03-20 (SHA 4c972ea)
result: pass

### 2. Mehrere Stellen je Datei mit Zeitstempel und Kennzeichen
expected: Eine Datei mit mehreren Fundstellen erscheint als bis zu 3 Zeilen (z. B. 0:06 / 0:36 / 1:06), jeweils in der Reihenfolge Zeit, Kennzeichen "Vorläufig" (EN "Preliminary"), Ausschnitt. Auf 375 px Breite bleibt das Kennzeichen sichtbar, gekürzt wird nur der Ausschnitt.
beleg: 03-21 Owner-Abnahme S1/S3 (Screenshots Lauf 43673521607)
result: pass

### 3. "Mehr laden" ohne doppelte Treffer
expected: Mit "Mehr laden" kommt die nächste Stelle (z. B. 1:36), und kein Treffer erscheint doppelt. Der Testtreffer trägt kein Vorläufig-Kennzeichen, und kein Treffer hat zwei Kennzeichen.
beleg: 03-21 S2/S4
result: pass

### 4. Keine Treffer aus Dateien ohne Sprache
expected: Musik, Stille oder Rauschen erzeugen keinen Suchtreffer. Fremde Schrift oder Wortsalat (z. B. ein japanischer Clip) tauchen nicht im Index auf.
beleg: 03-21 S5; 03-13b
result: pass

### 5. Abspielseite mit vorläufigem Transkript bzw. Teiltranskript
expected: Unter dem Ausschnitt steht ein kleiner, gedämpfter Hinweis (kein Banner), dass das Transkript vorläufig ist. Solange die Datei noch nicht fertig verarbeitet ist, steht dort stattdessen der Hinweis auf ein Teiltranskript, nie beide Hinweise. Der Hinweis ist in hell, dunkel und Hochkontrast mit mindestens 4,5:1 lesbar.
beleg: 03-21 P1/P2 und Kontrast-Gate
result: pass

### 6. Abspielseite ohne Transkript bzw. noch in Arbeit
expected: Hat eine Datei noch kein Transkript oder ist ihre Stelle noch nicht verarbeitet, zeigt die Seite einen festen Satz im grauen Ausschnitt-Block statt eines Fehlers.
beleg: 03-21 P3/P4
result: pass

### 7. Abspielseite mit Begründung (keine Sprache, übersprungen, nicht unterstützt)
expected: Für "keine Sprache", "übersprungen: beschädigt", "übersprungen: geschützt (DRM)", "Sprache nicht unterstützt" und "anderer Grund" zeigt die Seite je einen festen, verständlichen Satz. Ein roher Fehlercode ist nie sichtbar. Bei nicht unterstütztem Format können Format-Banner und Hinweis gleichzeitig erscheinen.
beleg: 03-21 P5 bis P8, P10
result: pass

### 8. Überlange Aufnahme und zu wenig Speicherplatz
expected: Ist eine Datei länger als die eingestellte Höchstdauer, nennt die Seite die Grenze mit korrekter Pluralform ("12 Stunden" bzw. "1 Stunde") und im selben Absatz einen Satz für die Administration. Bei voller Platte erscheint ein eigener Hinweis auf zu wenig Speicherplatz.
beleg: 03-21 P9 (Screenshots); P13 nur über Unit-Tests, kein Bild
result: pass

### 9. Admin-Einstellung Höchstdauer
expected: In den Admin-Einstellungen steht das Feld "Längste Aufnahme in Stunden" (EN "Longest recording in hours", Standard 12, höchstens 24) statt der früheren MB-Grenze. Wird der Wert angehoben, verarbeitet das System zuvor als überlang übersprungene Dateien spätestens nach rund 5 Minuten neu.
beleg: 03-01 Owner-Freigabe Texte und Deckel 24 h; 03-15
result: pass

### 10. Keine Treffer ohne Leserecht
expected: Wer keine Leserechte (mehr) hat, sieht keinen Treffer aus der Datei, z. B. bei entzogener Freigabe, Gruppenordner-ACL "+read -share", Papierkorb oder Samba-Sperre. Seine Abspielseite sieht genau so aus wie bei einer Datei ohne Transkript und verrät nichts.
beleg: 03-17/03-20 search-parity PASS auf 6 Beinen; 03-21 P11/P12, EXCERPT LEAK PROBE PASS
result: pass

### 11. Dreisprachige Oberfläche DE/EN/FR
expected: Kennzeichen, Hinweise, Gründe und Einstellungstexte erscheinen in Deutsch, Englisch und Französisch korrekt, mit echten Umlauten und französischem schmalem Leerzeichen vor ";" und ":". README, Doku und CHANGELOG beschreiben die Vorschau-Transkription in allen drei Sprachen.
beleg: 03-21 Umlaut-Audit ohne Befund; 03-19 Owner-Freigabe der Doku
result: pass

### 12. Upgrade von 0.2.0 auf 0.3.0 und Fortsetzen nach Neustart
expected: Nach dem Update von 0.2.0 zeigen beide Apps 0.3.0. Vorhandene Dateien werden ohne Datenverlust für die Vorschau eingeplant, und "occ status" zeigt eine Zeile "Preview:". Wird der Container während einer langen Datei neu gestartet, macht die Vorschau beim letzten fertigen Stück weiter.
beleg: 03-19 Upgrade-Job vom echten 0.2.0; CI gruen 03-20
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
