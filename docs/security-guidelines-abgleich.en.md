# Cross-check against the Nextcloud security guidelines (Audio & Video Search)

Appendix to the security dossier. As of 2026-11-16, checked against the
security guidelines of the Nextcloud 35 developer manual
(developer_manual/prologue/security.html) and the app store rules
(app_publishing_maintenance/publishing.html). Method: a code sweep over
php/ and backend/src on 2026-11-16 (shell_exec, proc_open, passthru,
eval, raw SQL, print_unescaped, innerHTML, os.system: 0 hits) plus the
CI gates in backend/tests (test_php_gates.py and others).

## Developer guidelines

| Rule | Status | Evidence |
|---|---|---|
| SQL injection: prepared queries only | met | IQueryBuilder in all mappers (php/lib/Db), no raw SQL in the sweep |
| XSS: sanitise templates and DOM | met | Gate: templates use p() only, JS sets user text via textContent only (test_php_gates.py, test_ui_assets.py) |
| Clickjacking | met | Server default headers untouched |
| Code execution / file inclusion | met | Sweep 0 hits; media and models live in the ExApp volume, never in the webroot |
| Directory traversal: files API | met | Node lookup only in FileAccess (gate rule 4), the container reads content only through the gateway after the permission check |
| Shell injection | met | PHP calls no shell (sweep); ffmpeg and models run as child processes with argument lists, no shell |
| Auth bypass / privilege escalation | met | Permission check at query time in PHP (readableFile, actAs); hits only through references with state active; the phase 4 plan hardens the export fail-closed (DownloadPolicy) |
| Sensitive data exposure | met | No names or paths in logs (gate rule 6, log context carries class instead of exception since push 9); state lives in the ExApp volume |
| CSRF | met | App framework default; POSTs carry the requesttoken (pattern admin.js, gate planned for the new routes in phase 4) |
| Unvalidated redirects | n/a | No redirects |
| CORS | n/a | No CORS grants |

## Store rules (excerpt)

| Rule | Status | Evidence |
|---|---|---|
| AGPL-3.0-or-later | met | LICENSE, info.xml of both apps; Parakeet CC-BY-4.0 with NVIDIA attribution |
| No "Nextcloud" in the name | met | audio_video_search / audio_video_search_backend |
| Timely response to security reports | met | SECURITY.md (GitHub private reporting plus mail, 7 days) |
| Clean install, uninstall, up- and downgrade | met | Migrations with tests; upgrade proof in the deploy-harp CI (including the maintenance window hardening of push 9) |
| No data to third parties, privacy | met | No audio, text or telemetry leaves the server; model downloads come from the project's own GitHub release with a fixed sha256 and a host allowlist (D-03-21); HF_HUB_OFFLINE=1 |
| Contact channel | met | GitHub issues, SECURITY.md |

## Beyond the guidelines

- SECURITY.md per phase with a threat audit (01/02/03 verified, threats_open 0); accepted risks confirmed by the owner one by one
- Workflow pins and gate tests against CI manipulation; AI_ASSISTANCE.md disclosure
- Rate limiting and a CSRF gate for the new export and sidecar routes are part of the phase 4 plans (04-10, 04-12)

## Open points

- Phase 4 adds new surfaces (export, sidecar file, subtitle track); this cross-check is updated after the phase 4 security audit (04-SECURITY.md).
