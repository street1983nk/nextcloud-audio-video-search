# Phase 5: Discussion Log

**Datum:** 2026-11-18. Nur zur Nachvollziehbarkeit; maßgeblich ist 05-CONTEXT.md.

| Bereich | Frage | Optionen | Owner-Wahl |
|---|---|---|---|
| Profil | Wo sieht der Admin das Profil? | Admin-Einstellungen / nur occ | Admin-Einstellungen |
| Profil | Gesperrtes Profil erzwingen? | Nein, hart gesperrt / Ja mit Warnung | Nein, hart gesperrt |
| Rechenfenster | Standard nach Installation | Immer / Vorschau immer, Veredelung nachts / Alles nachts | Immer rechnen |
| Rechenfenster | Laufender Auftrag am Fensterende | Stück fertig, dann Pause / Sofort abbrechen | Stück fertig, dann Pause |
| Modellbezug | Quelle Whisper | Eigenes GitHub-Release / HF mit Commit | Eigenes GitHub-Release |
| Modellbezug | Zeitpunkt | Automatisch nach Profilwahl / Admin-Klick | Automatisch |
| Modellbezug | Offline-Modus | Standard aus mit Schalter / Standard an | Standard aus, Schalter |
| Lizenzen | Ort in der App | Admin-Abschnitt / zusätzlich Abspielansicht | Admin-Abschnitt "Modelle und Lizenzen" |

Hinweis: In der Frage standen zu kleine Modellgrößen (turbo 0,8 GB, large-v3 1,5 GB). Richtig sind laut Stack-Recherche 1,62 GB bzw. 3,09 GB. Die Wahl hängt daran nicht; die 2-GiB-Grenze für GitHub-Assets steht als Recherchepunkt in D-05-05.

Claude's Discretion: Profilschwellen, Form der Thread-Grenze, OOM-Isolation, Reihenfolge (siehe CONTEXT).
