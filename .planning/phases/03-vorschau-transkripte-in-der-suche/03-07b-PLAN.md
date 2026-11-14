---
phase: 03-vorschau-transkripte-in-der-suche
plan: 07b
type: execute
wave: 3
depends_on: ["03-07"]
files_modified:
  - backend/src/audio_video_search_backend/models/catalog.py
  - backend/tests/test_models.py
  - backend/tests/test_model_download.py
  - backend/Dockerfile
  - backend/tests/test_dockerfile.py
  - README.md
  - README.en.md
  - README.fr.md
autonomous: false
requirements: [TRANS-01]

must_haves:
  truths:
    - "Die fünf Modelldateien (encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx, tokens.txt, silero_vad.onnx) liegen byte-gleich (sha256 und Länge aus 03-07) als Assets eines eigenen Releases im Repo street1983nk/nextcloud-audio-video-search, angelegt erst nach Owner-Freigabe"
    - "Der Downloader lädt nur noch von diesem Release; ASSET_HOSTS enthält genau die am echten Redirect gemessenen Hosts, Hugging Face ist nicht mehr erlaubt"
    - "sha256, Längen und MODEL_SHA256 sind unverändert; die Admin-Ablage (Air-Gap) prüft wie bisher"
    - "Das Image setzt HF_HUB_OFFLINE=1 und HF_HUB_DISABLE_TELEMETRY=1"
    - "Release-Text und README in DE/EN/FR nennen Parakeet TDT 0.6B v3 von NVIDIA unter CC-BY-4.0 und Silero VAD unter MIT"
  artifacts:
    - path: "backend/src/audio_video_search_backend/models/catalog.py"
      provides: "URLs auf die Release-Assets, ASSET_HOSTS aus der Messung, sha256 und Längen unverändert"
      contains: "releases/download/"
    - path: "backend/Dockerfile"
      provides: "HF_HUB_OFFLINE=1 und HF_HUB_DISABLE_TELEMETRY=1 im Runtime-ENV"
      contains: "HF_HUB_OFFLINE=1"
    - path: "backend/tests/test_models.py"
      provides: "Katalogregeln für die Release-Quelle mit Positivkontrolle"
  key_links:
    - from: "models/procure.py"
      to: "catalog.ASSET_HOSTS"
      via: "allowed_hosts=catalog.ASSET_HOSTS (unverändert, Zeile 185)"
      pattern: "allowed_hosts=catalog.ASSET_HOSTS"
    - from: "catalog.py URLs"
      to: "GitHub-Release des eigenen Repos"
      via: "https://github.com/street1983nk/nextcloud-audio-video-search/releases/download/<Tag>/<Datei>"
      pattern: "street1983nk/nextcloud-audio-video-search/releases/download"
---

## Phase Goal

**As a** Nutzerin oder Nutzer einer Nextcloud-Instanz, **I want to** gesprochenen Text meiner Aufnahmen in Minuten über die normale Nextcloud-Suche finden, als vorläufig gekennzeichnet und nur in Dateien, die ich lesen darf, **so that** ich meine Aufnahmen durchsuchen kann, ohne dass ein Inhalt den Server verlässt.

<objective>
Folgeplan zu 03-07 nach D-03-21: Die Modellquelle wird ein eigenes GitHub-Release im Repo street1983nk/nextcloud-audio-video-search statt Hugging Face, weil Hugging Face je nach Region auf wechselnde CDN-Hosts weiterleitet (gemessen `us.aws.cdn.hf.co`, 03-07-SUMMARY "Offene Punkte") und eine feste Host-Allowlist in anderen Regionen mit `foreign_host` scheitern würde. Dazu der zweite offene Punkt aus 03-07: HF_HUB_OFFLINE=1 und HF_HUB_DISABLE_TELEMETRY=1 im Dockerfile.

Purpose: TRANS-01 braucht ein Modell, das auf jeder Instanz weltweit mit fester Allowlist und festem sha256 ankommt; die Lizenzpflicht (CC-BY-4.0, Namensnennung NVIDIA) gilt auch für das eigene Release.
Output: Release mit fünf Assets (nach Owner-Freigabe), catalog.py auf das Release umgestellt, gemessene Allowlist, Dockerfile-ENV, Tests mit Positivkontrolle, README DE/EN/FR mit Namensnennung.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-CONTEXT.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-07-PLAN.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-07-SUMMARY.md
@backend/src/audio_video_search_backend/models/catalog.py
@backend/Dockerfile

Regeln: Commits nur lokal mit `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit`, ohne Claude-Session- oder Co-Authored-By-Zeile, nie "closes/fixes/resolves #N". Kein `git push`, kein lokales Docker. STATE.md, ROADMAP.md, REQUIREMENTS.md nicht schreiben. Jede nach außen gerichtete Aktion (Release anlegen, Tag anlegen, Asset hochladen, Release veröffentlichen) nur nach ausdrücklicher Owner-Freigabe in Task 1; ohne Freigabe endet der Plan nach der Frage. Echte Umlaute in deutscher Prosa, keine Gedankenstriche (U+2013, U+2014), keine Emojis. Gates vor jedem Commit grün: `cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q`. HTTP nur in nc.py (test_boundary); dieser Plan ändert nc.py und procure.py nicht. Heruntergeladene Dateien nur in einem frischen, leeren Ordner im Scratchpad, nie im Repo; Python, das sie liest, mit `-I`; danach löschen. Vorher freien Plattenplatz prüfen (mindestens 2 GB, Encoder 652 MB plus Kopie für die Gegenprobe).

Festwerte (aus 03-07, unverändert; Quelle der Wahrheit ist catalog.py):
- encoder.int8.onnx `acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247`, 652184281 Byte
- decoder.int8.onnx `179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e`, 11845275 Byte
- joiner.int8.onnx `3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3`, 6355277 Byte
- tokens.txt `d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d`, 93939 Byte
- silero_vad.onnx `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`, 643854 Byte
- MODEL_SHA256 `3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339` (bleibt; daran hängen Cache-Schlüssel aus 03-10/03-17 und die Herkunft)
- Parakeet-Quelle: Hugging Face `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` @ `2bda32ec70b097a55adaa07d9a7173915b43cc78` (sherpa-onnx-Export von `nvidia/parakeet-tdt-0.6b-v3`, CC-BY-4.0); Silero: `k2-fsa/sherpa-onnx` Release `asr-models` (Original `snakers4/silero-vad`, MIT)

Workflow-Auslöser (geprüft beim Planen, im Task erneut prüfen): docker.yml, python.yml, php.yml, deploy-harp.yml und release.yml reagieren auf Tags nur mit Muster `v[0-9]+.[0-9]+.[0-9]+`; discovery-e2e.yml, scorecard.yml und security.yml nur auf Branches; store-submit.yml nur auf workflow_dispatch. Ein Tag `models-2026-11` startet also keinen Workflow und kein Store-Release. Der Tag darf nie wie eine App-Version aussehen (kein `v` am Anfang).

<interfaces>
Aus Plan 03-07 (Bestand, nicht ändern):
- catalog.py: `ModelFile(name, url, sha256, size)`, `PARAKEET_FILES`, `SILERO_FILES`, `MODELS`, `ASSET_HOSTS: Final = frozenset({...})`, `MODEL_SHA256`, `model_bytes(name)`; heute zusätzlich `PARAKEET_REPOSITORY`, `PARAKEET_REVISION`, `_PARAKEET_BASE` (nur für die URLs genutzt).
- procure.py Zeile 185: `allowed_hosts=catalog.ASSET_HOSTS`; Kommandozeile `uv run python -m audio_video_search_backend.models.procure --root PFAD [--verify-only]`, Ausgabe `<modell> <ergebnis>`, Exit 0 nur bei present/procured für beide.
- nc.fetch_model_asset(url, dest, *, expected_size, allowed_hosts, client=None, on_chunk=None) -> str mit Codes aus MODEL_FETCH_OUTCOMES (fetched, foreign_host, http_error, too_large, network); jede Stufe https und Host in allowed_hosts, höchstens 5 Stufen.
- Tests heute: test_models.py `test_every_parakeet_url_is_pinned_to_the_commit` (Zeile 41, erwartet HF-URL), `test_every_url_starts_on_an_allowed_host_over_https`, `test_the_allowlist_has_no_pattern`, `test_model_sha256_is_the_sha256_of_the_sorted_digests`; test_model_download.py `ALLOWED = frozenset({"huggingface.co", "us.aws.cdn.hf.co"})`, `START = "https://huggingface.co/repo/resolve/abc/model.onnx"` (Zeilen 11, 12), Redirect-Tests ab Zeile 54. test_dockerfile.py: `runtime_stage(text)`, Muster "rule fires" ab Zeile 111.
- README.md / README.en.md / README.fr.md Zeile 58: veralteter Satz "Für die Transkription sind in späteren Versionen Parakeet TDT 0.6B v3 von NVIDIA (CC-BY-4.0) und Whisper (MIT) vorgesehen. Phase 1 enthält noch kein Modell." (und Entsprechungen EN/FR), Abschnitt "Lizenz" / Bestandteile Dritter.
</interfaces>
</context>

<tasks>

<task type="checkpoint:decision" gate="blocking-human">
  <name>Task 1: Owner-Freigabe, dann eigenes Modell-Release anlegen und Redirects messen</name>
  <files>(keine Repo-Dateien; Release auf GitHub nach Freigabe, Belege im SUMMARY, Dateien nur im Scratchpad)</files>
  <read_first>
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-CONTEXT.md (D-03-21)
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-07-SUMMARY.md (Tabelle "Beobachtete Weiterleitungen", Offene Punkte)
    - backend/src/audio_video_search_backend/models/catalog.py (ganze Datei, Festwerte)
    - .github/workflows/*.yml jeweils der Block `on:` (Tag-Muster erneut bestätigen)
  </read_first>
  <decision>Darf das Release `models-2026-11` (Titel z. B. "Speech models 2026-11 (not an app release)") im öffentlichen Repo street1983nk/nextcloud-audio-video-search angelegt und mit den fünf Modelldateien bestückt werden, mit dem gezeigten Release-Text und den gezeigten README-Sätzen?</decision>
  <context>D-03-21: eigene Quelle statt Hugging Face wegen regional wechselnder CDN-Hosts. Release und Upload sind nach außen gerichtet und öffentlich; die Owner-Regel verlangt vorher die Frage. Ein Release-Asset ist nachträglich austauschbar, daher bleibt der feste sha256 im Code die eigentliche Sicherung.</context>
  <options>
    <option id="freigabe">
      <name>Freigabe wie gezeigt (Tag, Titel, Text, README-Sätze)</name>
      <pros>Feste Allowlist github.com plus Asset-Host, weltweit gleich; Namensnennung erfüllt.</pros>
      <cons>Eigenes Repo trägt ca. 671 MB Release-Assets; Pflege bei Modellwechsel liegt beim Owner.</cons>
    </option>
    <option id="aenderung">
      <name>Freigabe mit Änderungen (anderer Tag, Titel oder Text)</name>
      <pros>Owner bestimmt Wortlaut.</pros>
      <cons>Neuer Entwurf, erneute Frage.</cons>
    </option>
    <option id="ablehnung">
      <name>Keine Freigabe</name>
      <pros>Nichts geht nach außen.</pros>
      <cons>Plan endet hier; Task 2 läuft nicht, 03-07 bleibt mit Hugging Face und dem offenen Regionspunkt.</cons>
    </option>
  </options>
  <action>Teil A, vor der Frage, nur lesend und lokal: (1) `gh auth status` zeigt das Konto street1983nk; `gh repo view street1983nk/nextcloud-audio-video-search --json visibility,defaultBranchRef` zeigt PUBLIC und main; `gh release view models-2026-11 --repo street1983nk/nextcloud-audio-video-search` muss "release not found" liefern (sonst anderen Tag vorschlagen); `gh api repos/street1983nk/nextcloud-audio-video-search/rulesets` lesen und im Bericht nennen, ob eine Tag-Regel das Anlegen sperrt. (2) Freien Platz prüfen, dann einen frischen leeren Ordner `<scratchpad>/models-07b/` anlegen und die Dateien über den bestehenden, geprüften Weg aus 03-07 laden: `cd backend && uv run python -m audio_video_search_backend.models.procure --root <scratchpad>/models-07b` (lädt noch von Hugging Face bzw. k2-fsa, prüft sha256 und Länge, Ausgabe muss `silero procured` und `parakeet procured` sein). Gegenprobe mit unabhängigem Werkzeug: `sha256sum` und `stat -c %s` über die fünf Dateien unter `models/<name>/<MODEL_SHA256>/` und Abgleich mit den Festwerten im context-Block (nicht mit catalog.py-Code, sondern mit den Literalwerten). (3) Für Silero den MIT-Lizenztext aus `https://raw.githubusercontent.com/snakers4/silero-vad/master/LICENSE` lesen (nur Text, in den Scratch), Copyright-Zeile wörtlich übernehmen. (4) Release-Text als englische Faktenliste (Owner-Regel für GitHub-Releases) nach `<scratchpad>/models-07b-notes.md` schreiben und vollständig im Chat zeigen. Pflichtinhalt: Satz "Model files for the Audio & Video Search backend. Not an app release; the app downloads these files itself and checks each one against a fixed sha256."; Tabelle Datei, Größe in Byte, sha256 (alle fünf); Abschnitt Parakeet mit "Parakeet TDT 0.6B v3 by NVIDIA (https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)", Export "ONNX int8 export by the sherpa-onnx project (k2-fsa), taken unchanged from csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8 at commit 2bda32ec70b097a55adaa07d9a7173915b43cc78", Änderungsvermerk "Files are byte-identical to the source (same sha256); no modification."; Abschnitt Silero VAD mit Quelle k2-fsa/sherpa-onnx Release asr-models, Original snakers4/silero-vad, Lizenz MIT mit der wörtlichen Copyright-Zeile und dem MIT-Erlaubnistext; keine Gedankenstriche, keine Emojis. (5) README-Entwurf im Chat zeigen, je ein Satz DE, EN, FR als Ersatz für Zeile 58 (README.md, README.en.md, README.fr.md): nennt Parakeet TDT 0.6B v3 von NVIDIA (CC-BY-4.0) und Silero VAD (MIT), dass die ExApp beide beim Aktivieren aus dem eigenen GitHub-Release `models-2026-11` lädt und jede Datei mit festem sha256 prüft, dass Admins dieselben Dateien ohne Internet selbst ablegen können; Whisper (MIT) als für spätere Versionen vorgesehen behalten; FR mit U+00A0 vor `:;?!`. (6) Frage stellen (decision oben) und auf Antwort warten. Teil B, nur nach Antwort "freigabe" (Wortlaut der Antwort ins SUMMARY): (7) `gh release create models-2026-11 --repo street1983nk/nextcloud-audio-video-search --target main --draft --latest=false --title "<freigegebener Titel>" --notes-file <scratchpad>/models-07b-notes.md` (Entwurf zuerst, damit kein halbes Release öffentlich steht); (8) `gh release upload models-2026-11 <die fünf Dateien> --repo street1983nk/nextcloud-audio-video-search` mit genau den Dateinamen encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx, tokens.txt, silero_vad.onnx; (9) vor dem Veröffentlichen `gh api repos/street1983nk/nextcloud-audio-video-search/releases --jq '.[] | select(.tag_name=="models-2026-11") | .assets[] | "\(.name) \(.size) \(.digest)"'` lesen: jede Zeile muss `sha256:<Festwert>` und die Festlänge tragen; bei Abweichung Asset löschen, neu hochladen, nie veröffentlichen, solange eine Zeile abweicht; (10) `gh release edit models-2026-11 --repo street1983nk/nextcloud-audio-video-search --draft=false --latest=false`; (11) `gh run list --repo street1983nk/nextcloud-audio-video-search --limit 5` zeigt keinen durch den Tag ausgelösten Lauf (Beleg ins SUMMARY); (12) Redirects je Asset einzeln messen, nur Header: `curl -sSI --max-redirs 0 https://github.com/street1983nk/nextcloud-audio-video-search/releases/download/models-2026-11/<datei>` für alle fünf, Statuszeile und Location-Host notieren, dann die Location-URL ebenso mit `curl -sSI --max-redirs 0` bis zur 200-Antwort (antwortet der Asset-Host auf HEAD mit 403 oder 405, statt dessen `curl -sS -o /dev/null -D - --max-redirs 0 -r 0-0 <Location>`, also höchstens ein Byte, und das im SUMMARY vermerken); Content-Length bzw. Gesamtlänge aus Content-Range je Datei mit der Festlänge vergleichen. Signierte Location-URLs nie vollständig ins SUMMARY oder in den Chat, nur Host und Pfadanfang. (13) Scratch-Dateien bleiben bis Task 2 Schritt "Ende-zu-Ende" liegen und werden dort gelöscht. Bei Antwort "aenderung": Entwurf anpassen, erneut fragen. Bei "ablehnung": nichts anlegen, SUMMARY schreiben, Plan endet ohne Task 2.</action>
  <verify><automated>gh release view models-2026-11 --repo street1983nk/nextcloud-audio-video-search --json isDraft,tagName,assets --jq '"\(.tagName) draft=\(.isDraft) assets=\(.assets|length)"'</automated></verify>
  <acceptance_criteria>
    - Vor der Frage stehen im Chat: Ausgabe `silero procured` und `parakeet procured`, die `sha256sum`-Zeilen aller fünf Dateien gleich den Festwerten, der vollständige Release-Text und die drei README-Sätze.
    - Die Owner-Antwort ist wörtlich im SUMMARY vermerkt; ohne "freigabe" existiert kein Release `models-2026-11` (`gh release view` liefert "release not found").
    - Nach Freigabe liefert der verify-Befehl `models-2026-11 draft=false assets=5`; die API-Zeilen zeigen für alle fünf Assets `sha256:` plus Festwert und die Festlänge.
    - Das SUMMARY enthält je Asset eine Tabellenzeile: Stufe 1 (Statuszeile, Location-Host), Stufe 2 (Statuszeile, HEAD oder Ein-Byte-GET), Länge; daraus die Menge der Hosts für ASSET_HOSTS.
    - `gh run list` zeigt keinen Lauf mit Ereignis push auf den Tag `models-2026-11`.
    - Release-Text: `grep -c "NVIDIA" <scratchpad>/models-07b-notes.md` mindestens 1, `grep -c "CC BY 4.0" <scratchpad>/models-07b-notes.md` mindestens 1, `grep -c "MIT" <scratchpad>/models-07b-notes.md` mindestens 1, `grep -cP "\x{2013}|\x{2014}" <scratchpad>/models-07b-notes.md` gleich 0.
  </acceptance_criteria>
  <done>Release `models-2026-11` öffentlich mit fünf geprüften Assets und Namensnennung, Redirect-Hosts und Längen je Asset im SUMMARY belegt; oder dokumentierte Ablehnung.</done>
  <resume-signal>"freigabe", "aenderung: ..." oder "ablehnung"</resume-signal>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Downloader auf das Release umstellen, Allowlist aus der Messung, HF-ENV im Image, Namensnennung in der Doku</name>
  <files>backend/src/audio_video_search_backend/models/catalog.py, backend/tests/test_models.py, backend/tests/test_model_download.py, backend/Dockerfile, backend/tests/test_dockerfile.py, README.md, README.en.md, README.fr.md</files>
  <read_first>
    - backend/src/audio_video_search_backend/models/catalog.py (ganze Datei)
    - backend/tests/test_models.py (ganze Datei, besonders Zeilen 27 bis 70 und 85)
    - backend/tests/test_model_download.py (ganze Datei, besonders Zeilen 11, 12, 54 bis 115, 197 bis 230)
    - backend/tests/test_dockerfile.py (runtime_stage, Muster "rule fires" ab Zeile 111)
    - backend/Dockerfile Zeilen 136 bis 141 (Runtime-ENV)
    - README.md, README.en.md, README.fr.md je Abschnitt "Lizenz"/"License"/"Licence" um Zeile 58
    - 03-07b-SUMMARY.md-Entwurf aus Task 1 (gemessene Hosts, freigegebene README-Sätze, freigegebener Tag)
  </read_first>
  <behavior>
    - Jede URL in PARAKEET_FILES und SILERO_FILES ist genau `https://github.com/street1983nk/nextcloud-audio-video-search/releases/download/<MODEL_RELEASE_TAG>/<name>`; keine URL nennt huggingface.co oder k2-fsa.
    - ASSET_HOSTS ist gleich der in Task 1 gemessenen Menge (erwartet frozenset({"github.com", "release-assets.githubusercontent.com"}), maßgeblich ist allein die Messung); kein `*`, kein Hugging-Face-Host.
    - sha256 und Länge aller fünf Dateien sind die Literalwerte aus 03-07; MODEL_SHA256 bleibt `3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339` und wird wie bisher nachgerechnet.
    - Positivkontrolle Host: fetch_model_asset mit catalog.ASSET_HOSTS und MockTransport, github.com antwortet 302 auf release-assets.githubusercontent.com, Ergebnis fetched; derselbe Aufbau mit 302 auf us.aws.cdn.hf.co ergibt foreign_host ohne Datei und ohne Anfrage an den fremden Host; Start-URL auf huggingface.co ergibt foreign_host ohne jede Anfrage.
    - Positivkontrolle Hash: procure mit gefälschtem fetch, der für eine Katalogdatei falsche Bytes gleicher Länge liefert, ergibt WRONG_DIGEST ohne installierte Datei; mit den richtigen Bytes PROCURED (gleicher Aufbau, nur die Bytes verschieden).
    - Air-Gap unverändert: eine vom Admin abgelegte richtige Datei zählt als PRESENT ohne fetch-Aufruf, eine falsche als WRONG_DIGEST (bestehende Tests bleiben grün, keine Änderung an procure.py).
    - Dockerfile: runtime_stage enthält `HF_HUB_OFFLINE=1` und `HF_HUB_DISABLE_TELEMETRY=1`; die Prüffunktion schlägt bei einem Dockerfile-Text an, der die Variablen nur in der build-Stufe setzt (Positivkontrolle).
  </behavior>
  <action>RED: Tests nach behavior schreiben bzw. anpassen und laufen lassen (müssen fehlschlagen), Commit `test(03-07b): Modellquelle eigenes Release, Allowlist und HF-ENV`. Dabei in test_models.py `test_every_parakeet_url_is_pinned_to_the_commit` ersetzen durch `test_every_url_points_at_the_own_model_release` (für alle fünf Dateien, Erwartung aus eigenen Literalen: Repo-Pfad und Tag als Konstanten im Test, nicht aus catalog gelesen), `test_the_allowlist_is_exactly_the_measured_hosts` (Gleichheit mit einem Literal-frozenset aus der Task-1-Messung, Kommentar mit Datum und Verweis auf 03-07b-SUMMARY), `test_no_url_and_no_host_names_hugging_face`, `test_the_digests_and_lengths_did_not_change` (Literale aus dem context-Block) und den Hash-Positivkontroll-Test; in test_model_download.py `ALLOWED`/`START` auf die echte GitHub-Kette umstellen (`START = "https://github.com/o/r/releases/download/t/model.onnx"`, Zwischenstufe release-assets.githubusercontent.com), die Fälle "relative Weiterleitung bleibt auf dem Host", "fremder Host", "Lookalike-Host" (z. B. `release-assets.githubusercontent.com.evil.example`), "http-Weiterleitung", "Start-URL außerhalb" auf diese Hosts umschreiben, plus zwei Tests mit `catalog.ASSET_HOSTS` (GitHub-Kette lädt, Weiterleitung auf us.aws.cdn.hf.co ist foreign_host); test_main.py Zeile 219 (Fake-URL auf huggingface.co) nur anfassen, wenn ein Test dadurch scheitert, sonst nicht (gehört nicht zu files_modified). In test_dockerfile.py `test_the_runtime_sets_the_hugging_face_hub_offline_and_without_telemetry` (Text von runtime_stage(DOCKERFILE) enthält beide Zuweisungen) und `test_the_hub_env_rule_fires_on_a_build_stage_only_env` (Text mit ENV nur in `FROM base AS build` ergibt False). GREEN: catalog.py nach D-03-21: `MODEL_RELEASE_REPOSITORY: Final = "street1983nk/nextcloud-audio-video-search"`, `MODEL_RELEASE_TAG: Final = "<freigegebener Tag, erwartet models-2026-11>"`, `_RELEASE_BASE: Final = f"https://github.com/{MODEL_RELEASE_REPOSITORY}/releases/download/{MODEL_RELEASE_TAG}"`; alle fünf `url=f"{_RELEASE_BASE}/<name>"`; sha256 und size Zeichen für Zeichen unverändert; `PARAKEET_REPOSITORY`, `PARAKEET_REVISION`, `_PARAKEET_BASE` entfernen, wenn `grep -rn "PARAKEET_REPOSITORY\|PARAKEET_REVISION" backend/src backend/tests ci scripts` außerhalb catalog.py nichts findet (vulture), sonst als Herkunftskonstanten behalten; Modul-Docstring neu: Herkunft der Dateien (Parakeet-TDT-0.6B-v3 int8 von NVIDIA, CC-BY-4.0, sherpa-onnx-Export csukuangfj/... @ 2bda32ec70b097a55adaa07d9a7173915b43cc78 byte-gleich gespiegelt; Silero VAD, MIT, aus k2-fsa/sherpa-onnx asr-models), Grund D-03-21 (regional wechselnde HF-CDN-Hosts), Release ohne `v`-Präfix, damit kein Workflow anspringt; der Commit-Hash 2bda32ec... muss in catalog.py stehen bleiben (Acceptance aus 03-07). ASSET_HOSTS genau aus der Task-1-Tabelle, Kommentar mit Messdatum und Statuszeilen (wie bisher, nur neue Kette); weicht die Messung von der Erwartung ab (z. B. objects.githubusercontent.com), gilt die Messung und der Test-Literal folgt ihr. Dockerfile: im Runtime-ENV-Block (heute Zeilen 138 bis 140) `HF_HUB_OFFLINE=1` und `HF_HUB_DISABLE_TELEMETRY=1` ergänzen, darüber ein englischer Kommentar: huggingface-hub kommt später transitiv über faster-whisper, darf nie ins Netz, Modelle kommen nur über den eigenen Downloader (STACK.md "What NOT to Use"); keine weitere Dockerfile-Änderung. README.md, README.en.md, README.fr.md: den Satz in Zeile 58 durch den in Task 1 freigegebenen Satz der jeweiligen Sprache ersetzen, wörtlich, sonst nichts an den READMEs ändern (Owner-Regel: nur erbetene Änderungen; der große Doku-Abschnitt bleibt Plan 03-19). Ende-zu-Ende mit echtem Netz, einmal: frischer leerer Ordner `<scratchpad>/models-07b-e2e/`, `cd backend && uv run python -m audio_video_search_backend.models.procure --root <scratchpad>/models-07b-e2e` muss `silero procured` und `parakeet procured` mit Exit 0 ausgeben (beweist, dass die neue Kette mit der neuen Allowlist durchläuft); danach `--verify-only` gegen denselben Ordner ergibt present für beide; Ergebnis ins SUMMARY; danach beide Scratch-Ordner `models-07b` und `models-07b-e2e` und die Notizdatei löschen. Volle Gates, Commit `feat(03-07b): Modelle aus eigenem Release mit gemessener Allowlist`. SUMMARY `.planning/phases/03-vorschau-transkripte-in-der-suche/03-07b-SUMMARY.md` schreiben und als `docs(03-07b): Modellquelle eigenes Release zusammengefasst` committen.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_models.py tests/test_model_download.py tests/test_dockerfile.py tests/test_boundary.py tests/test_main.py tests/test_trilingual.py tests/test_public_texts.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - Kein Hugging-Face-Host und keine Hugging-Face-URL im Katalog: `cd backend && uv run python -c "from audio_video_search_backend.models import catalog as c; import sys; sys.exit(any('hf.co' in h or 'huggingface' in h for h in c.ASSET_HOSTS) or any('huggingface' in f.url or 'k2-fsa' in f.url for m in c.MODELS.values() for f in m))"` endet mit Exit 0.
    - `grep -c "street1983nk/nextcloud-audio-video-search" backend/src/audio_video_search_backend/models/catalog.py` mindestens 1; `grep -c "2bda32ec70b097a55adaa07d9a7173915b43cc78" backend/src/audio_video_search_backend/models/catalog.py` mindestens 1; `grep -c "3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339" backend/src/audio_video_search_backend/models/catalog.py` gleich 1.
    - `git diff <Basis-Commit vor 03-07b> -- backend/src/audio_video_search_backend/models/catalog.py | grep -E '^[-+].*(sha256=|size=)'` liefert nichts (Hashes und Längen unverändert).
    - `grep -n "HF_HUB_OFFLINE=1" backend/Dockerfile` und `grep -n "HF_HUB_DISABLE_TELEMETRY=1" backend/Dockerfile` je ein Treffer nach der Zeile `FROM ${BASE_IMAGE} AS runtime`.
    - Die Tests für fremden Host (us.aws.cdn.hf.co, huggingface.co als Start) und falschen Hash existieren und sind grün; RED-Commit vor GREEN-Commit im Log.
    - `grep -c "NVIDIA" README.md README.en.md README.fr.md` je mindestens 1, `grep -c "CC-BY-4.0" README.md README.en.md README.fr.md` je mindestens 1, `grep -c "models-2026-11" README.md README.en.md README.fr.md` je mindestens 1 (bzw. der freigegebene Tag); `grep -cP "\x{2013}|\x{2014}" README.md README.en.md README.fr.md` je 0.
    - SUMMARY enthält die Ende-zu-Ende-Ausgabe (`silero procured`, `parakeet procured`, Exit 0) und `git status --porcelain` zeigt keine .onnx- oder tokens.txt-Datei; die Scratch-Ordner sind gelöscht.
    - Volle Gates grün; `git log -3 --format='%an <%ae>%n%b'` zeigt street1983nk <k.cherif@outlook.de> ohne Claude-Session- oder Co-Authored-By-Zeile und ohne closes/fixes/resolves.
  </acceptance_criteria>
  <done>RED-Commit, GREEN-Commit `feat(03-07b): Modelle aus eigenem Release mit gemessener Allowlist` und SUMMARY-Commit lokal; nichts gepusht.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Container nach github.com und Asset-Host | einziger ausgehender Weg für Modelle, Redirect-Kette |
| Owner-Konto nach GitHub-Release | Assets im eigenen Repo sind nachträglich austauschbar |
| Hugging Face und k2-fsa nach Scratch (einmalig, Task 1) | Quelle der gespiegelten Dateien |
| Image-Laufzeit nach huggingface-hub | transitive Bibliothek mit eigenem Netzweg |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-74 | Tampering | Lieferkette beim Spiegeln (Task 1) | mitigate | Laden nur über procure mit festem sha256 und Länge, Gegenprobe mit sha256sum gegen Literalwerte, Upload nur der geprüften Dateien, API-Digest je Asset vor dem Veröffentlichen gegen Festwert |
| T-03-75 | Tampering | Release-Manipulation (Asset ersetzt, Tag neu gesetzt, Konto übernommen) | mitigate | sha256 und Länge fest im Code, os.replace erst nach Treffer (03-07), falsches Asset ergibt WRONG_DIGEST und MODELS_FAILED statt Modell; Release als Entwurf bestückt, erst nach Digest-Prüfung veröffentlicht; Tag ohne v-Präfix startet keinen Workflow |
| T-03-76 | Spoofing | Host-Allowlist | mitigate | ASSET_HOSTS genau aus gemessener Redirect-Kette, kein Muster, Hugging-Face-Hosts entfernt; Tests mit Positivkontrolle (fremder Host, Lookalike-Host, http-Stufe, Start außerhalb) |
| T-03-77 | Information Disclosure | huggingface-hub im Image, signierte Asset-URLs | mitigate | HF_HUB_OFFLINE=1 und HF_HUB_DISABLE_TELEMETRY=1 im Runtime-ENV mit Test; signierte Location-URLs nicht in SUMMARY oder Chat, nur Host |
| T-03-78 | Repudiation | Lizenzpflicht CC-BY-4.0 / MIT | mitigate | Release-Text mit Namensnennung NVIDIA, Lizenzlink, Quell-Commit, Änderungsvermerk, MIT-Copyright wörtlich; README DE/EN/FR nach Owner-Freigabe |
| T-03-79 | Denial of Service | Release gelöscht oder GitHub nicht erreichbar | accept | gleiches Verhalten wie bisher: UNAVAILABLE, MODELS_FAILED mit freigegebenem Text, Air-Gap-Ablage bleibt als Weg; keine Hugging-Face-Ausweichquelle, weil gerade deren Hosts nicht fest sind |
</threat_model>

<verification>
Release öffentlich mit fünf Assets, deren API-Digest gleich den Festwerten ist; Redirect-Hosts je Asset im SUMMARY; volle Backend-Suite grün; Ende-zu-Ende-Download über die neue Kette einmal mit Exit 0; nichts gepusht.
</verification>

<success_criteria>
- Modellbezug weltweit mit fester Allowlist aus gemessenen GitHub-Hosts, sha256 und MODEL_SHA256 unverändert.
- Namensnennung NVIDIA im Release und im README DE/EN/FR; Image ohne Hugging-Face-Netzweg.
- Release und Upload nur nach dokumentierter Owner-Freigabe.
</success_criteria>

<output>
Create `.planning/phases/03-vorschau-transkripte-in-der-suche/03-07b-SUMMARY.md` when done
</output>
