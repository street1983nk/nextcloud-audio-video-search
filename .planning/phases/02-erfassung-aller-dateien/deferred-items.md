# Deferred Items, Phase 2

| Gefunden in | Datei | Befund | Warum nicht jetzt |
|-------------|-------|--------|-------------------|
| 02-08 | backend/src/audio_video_search_backend/nc.py `_hash_stream` (Probe-Weg aus Phase 1) | Antworten 3xx (und 1xx/2xx außer 200) gelten dort als Inhalt; nur `>= 400` ist ein Fehler. Ohne Content-Length würde der Text einer Umleitung gehasht. Betrifft nur `occ :sample` (Debug-Weg), nicht die Erfassung: `fetch_to_tempfile` nimmt nur 200 mit exakter Länge. | Außerhalb des Plans; Fix ist eine Zeile (`!= 200`) plus Test, passt in den nächsten Plan, der `api/sample.py` berührt. |
