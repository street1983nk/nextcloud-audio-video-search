# Abgleich mit den Nextcloud-Sicherheitsrichtlinien (Audio & Video Search)

Anhang zum Sicherheitsdossier. Stand: 16.11.2026, geprüft gegen die
Security guidelines des Nextcloud 35 Developer Manual
(developer_manual/prologue/security.html) und die App-Store-Regeln
(app_publishing_maintenance/publishing.html). Prüfweg: Code-Sweep über
php/ und backend/src am 16.11.2026 (shell_exec, proc_open, passthru,
eval, rohes SQL, print_unescaped, innerHTML, os.system: 0 Treffer) plus
die CI-Gates in backend/tests (test_php_gates.py u. a.).

## Developer-Guidelines

| Regel | Stand | Beleg |
|---|---|---|
| SQL-Injection: nur vorbereitete Abfragen | erfüllt | IQueryBuilder in allen Mappers (php/lib/Db), kein rohes SQL im Sweep |
| XSS: Templates und DOM sanieren | erfüllt | Gate: Templates nur mit p(), JS setzt Nutzertext nur per textContent (test_php_gates.py, test_ui_assets.py) |
| Clickjacking | erfüllt | Standard-Header unangetastet |
| Code execution / file inclusion | erfüllt | Sweep 0 Treffer; Medien/Modelle im ExApp-Volume, nie im Webroot |
| Directory traversal: Files API | erfüllt | Knotensuche nur in FileAccess (Gate-Regel 4), Container liest Inhalte nur über das Gateway nach Rechteprüfung |
| Shell injection | erfüllt | PHP ruft keine Shell (Sweep); ffmpeg/Modelle als Kindprozess mit Argumentliste ohne Shell |
| Auth bypass / privilege escalation | erfüllt | Rechteprüfung zur Abfragezeit in PHP (readableFile, actAs); Treffer nur über Verweise mit state active; Phase-4-Plan härtet Export fail-closed (DownloadPolicy) |
| Sensitive data exposure | erfüllt | Keine Namen/Pfade in Logs (Gate-Regel 6, Log-Kontext nur class statt exception seit Push 9); Zustand im ExApp-Volume |
| CSRF | erfüllt | App-Framework-Standard; POSTs mit requesttoken (Muster admin.js, Gate geplant für neue Routen in Phase 4) |
| Unvalidated redirects | n. a. | Keine Weiterleitungen |
| CORS | n. a. | Keine CORS-Freigaben |

## Store-Regeln (Auszug)

| Regel | Stand | Beleg |
|---|---|---|
| AGPL-3.0-or-later | erfüllt | LICENSE, info.xml beider Apps; Parakeet CC-BY-4.0 mit NVIDIA-Namensnennung |
| Kein "Nextcloud" im Namen | erfüllt | audio_video_search / audio_video_search_backend |
| Zeitnahe Reaktion auf Sicherheitsmeldungen | erfüllt | SECURITY.md (GitHub private reporting + Mail, 7 Tage) |
| Sauberes Auf-/Abräumen, Up-/Downgrade | erfüllt | Migrationen mit Tests; Upgrade-Beweis in deploy-harp-CI (inkl. Wartungsfenster-Härtung Push 9) |
| Keine Daten an Dritte, Datenschutz | erfüllt | Kein Audio/Text/Telemetrie verlässt den Server; Modell-Downloads vom eigenen GitHub-Release mit festem sha256 und Host-Allowlist (D-03-21); HF_HUB_OFFLINE=1 |
| Kontaktweg | erfüllt | GitHub Issues, SECURITY.md |

## Über die Richtlinien hinaus

- SECURITY.md je Phase mit Threat-Audit (01/02/03 verified, threats_open 0); ARs einzeln vom Owner bestätigt
- Workflow-Pins und Gate-Tests gegen CI-Manipulation; AI_ASSISTANCE.md-Offenlegung
- Rate-Limit und CSRF-Gate für die neuen Export-/Ablage-Routen stehen in den Phase-4-Plänen (04-10, 04-12)

## Offene Punkte

- Phase 4 fügt neue Flächen hinzu (Export, Nebendatei, Spur); der Abgleich wird nach dem Phase-4-Security-Audit (04-SECURITY.md) aktualisiert.
