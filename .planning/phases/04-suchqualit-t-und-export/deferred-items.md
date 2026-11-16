# Phase 4: zurückgestellte Befunde (außerhalb des jeweiligen Plans)

## Aus Plan 04-05 (16.11.2026)

- Bestand, nicht von 04-05 verursacht: `requeue_too_long` (store/repo.py `_REQUEUE_TOO_LONG`) setzt `next_start_ms`, `chunks_done`, `attempts` und jetzt auch `words_de/en/fr` zurück, lässt aber `kept_words`, `drop_*`, `speech_ms` und `version_id` stehen. Ein zu langer Job, der mitten im Lauf übersprungen wurde (Dauer unbekannt, schon Stücke committet) und nach einer Limit-Erhöhung von vorn beginnt, zählt die alten Werte doppelt und hängt seine Wörter erneut an die bestehende Version an. Vor Phase 6 (Veredelung) prüfen und entscheiden: beim Weg zurück auch diese Felder und die Version zurücksetzen oder den Fall belegen, dass er nicht eintreten kann.

## Aus Plan 04-03 (16.11.2026)

- `backend/tests/test_trilingual.py::test_every_user_document_exists_in_three_languages` ist rot: `docs/security-guidelines-abgleich.md` (Commit 09c3297) hat keine Fassungen `.en.md` und `.fr.md`. Schon vor 04-03 vorhanden, nicht von 04-03 verursacht. Lösung: EN/FR-Fassung nachziehen oder das Dokument aus `docs/` (Nutzerdokumente) in `.planning/` verschieben. ERLEDIGT 16.11.2026: EN- und FR-Fassung nachgezogen (Commit 80f9a48), Gate wieder gruen (25 passed).

## Aus Plan 04-14 (16.11.2026)

- Wortform-Lücke, gemessen bei der S7-Vorabmessung (Wegwerf-Index mit echter ngerman-Liste, `scripts/research/phase4/measure_s7_sentences.py`): "Fischart" findet ein Transkript mit "Fischarten" nicht, "Fischarten" und der Kopf "Fisch" schon. Vermutlich zerlegt der Splitter "fischarten" anders als "fischart" (fisch|arten gegen fisch|art) oder der Stamm der Zerlegungsteile weicht ab. Nicht von 04-14 verursacht (Analyzer und Präfix-Klausel unverändert); der Kandidat wurde deshalb nicht gewählt. Vor Phase-Abschluss bewerten: als bekannte Grenze benennen oder im Analyzer (Stemming der Zerlegungsteile) nachziehen, mit Messung.
