# Deferred Items, Phase 2

| Gefunden in | Datei | Befund | Warum nicht jetzt |
|-------------|-------|--------|-------------------|
| 02-08 | backend/src/audio_video_search_backend/nc.py `_hash_stream` (Probe-Weg aus Phase 1) | Antworten 3xx (und 1xx/2xx außer 200) gelten dort als Inhalt; nur `>= 400` ist ein Fehler. Ohne Content-Length würde der Text einer Umleitung gehasht. Betrifft nur `occ :sample` (Debug-Weg), nicht die Erfassung: `fetch_to_tempfile` nimmt nur 200 mit exakter Länge. | Außerhalb des Plans; Fix ist eine Zeile (`!= 200`) plus Test, passt in den nächsten Plan, der `api/sample.py` berührt. |
| 02-11 (D-02-15a) | Plan 16 (Ausschluss), Phase 8 (endgültiges Vergessen) | Probe der betroffenen Datei mitentfernen: `DELETE FROM sample_ref WHERE file_id = ?` beim Ausschluss und beim Vergessen, plus Test, dass danach kein Probetreffer bleibt. Die Verwaist-Marke selbst bleibt nur an echten Verweisen. | Gehört zu Plan 16 und Phase 8; heute gibt es weder Ausschluss-Löschen noch Vergessen. |
| 02-11 (reason_77, Owner 07.11.) | php/lib/Controller/GatewayController.php (02-10) | files_accesscontrol per Tag: Gateway antwortet 404 statt 403 access_control (Lauf 42387720556, Datei 77), Grund not_found, Wiederholung 60 s statt 300 s, kein Leck. | Owner: "In Plan 13 einplanen (Empfohlen)"; steht als Task 3 in 02-13-PLAN.md. |
