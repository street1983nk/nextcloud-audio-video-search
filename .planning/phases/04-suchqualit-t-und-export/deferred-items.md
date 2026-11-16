# Phase 4: zurückgestellte Befunde (außerhalb des jeweiligen Plans)

## Aus Plan 04-03 (16.11.2026)

- `backend/tests/test_trilingual.py::test_every_user_document_exists_in_three_languages` ist rot: `docs/security-guidelines-abgleich.md` (Commit 09c3297) hat keine Fassungen `.en.md` und `.fr.md`. Schon vor 04-03 vorhanden, nicht von 04-03 verursacht. Lösung: EN/FR-Fassung nachziehen oder das Dokument aus `docs/` (Nutzerdokumente) in `.planning/` verschieben.
