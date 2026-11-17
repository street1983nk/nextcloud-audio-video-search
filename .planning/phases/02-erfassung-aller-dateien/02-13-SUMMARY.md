---
phase: 02-erfassung-aller-dateien
plan: 13
subsystem: backend-erfassung
tags: [disc-05, lesebeweis, d-02-01a, d-02-10, d-02-12, sperrkreis, files_accesscontrol, reason_77, gate]
requires:
  - phase: 02-08
    provides: "Erfassung per Temp-Download, Claim-Identität, Zustandsmaschine, mark_keyed"
  - phase: 02-10
    provides: "Kopf-Route /files/{fileId}/head, 403 access_control und 423 locked mit X-AVS-Reason"
  - phase: 02-11
    provides: "Befund reason_77 und Owner-Entscheid, ihn hier zu beheben"
  - phase: 02-12
    provides: "prefilter_key für SMB und SFTP, readerUid je Kopie"
provides:
  - "nc.fetch_head(file_id, user_id, *, client) -> HeadResult(sha256, length, error, status); HEAD_TIMEOUT (connect 10 s, read 30 s), HEAD_DEADLINE_SECONDS 45, HEAD_TOO_LONG"
  - "worker/read_proof.py: prove_read(ref, media_head_sha256, expected_length, fetch) -> ProofOutcome, head_length(size), StorageBreaker(closes_at, record), STORAGE_PAUSED"
  - "Store.prefilter_sibling, media_head, attach_by_proof(file_id, media_id, expected_etag, now), confirm_proof(file_id, expected_etag, now), fail_proof(claimed, reason, retry_at, bump, now), release_media(claimed, now)"
  - "Store.next_capture nimmt auch stage probing mit media_id (erneuter Beweis fällig)"
  - "Capture(services, *, head, breaker): Lesebeweis vor dem Anhängen, erneuter Beweis, Sperrkreis je Speicher"
  - "tests/test_read_proof_gate.py: scan(root) mit Regeln a bis f"
  - "ci/leak-control/read-proof-off.patch und README.md"
  - "FileAccess::nodeById, FileAccess::refusedByAccessControl; GatewayController::resolve wirft ForbiddenException für reason_77"
affects: [02-14, 02-15, 02-16, 02-17, 02-19, 02-20, 02-22]
tech-stack:
  added: []
  patterns:
    - "Ein Urteil, eine Stelle: nur prove_read sagt ok, mit genau einem return hinter Längenprüfung und hmac.compare_digest"
    - "Anhängen nur bedingt und nur im Zweig outcome is ProofOutcome.OK; ein AST-Gate hält das fest"
    - "Abschaltweg nur als CI-Patch auf einer Kopie, nie im Quellbaum des Produkts"
    - "Sperrkreis im Speicher des Prozesses: nach drei Zeitüberschreitungen in Folge eine Stunde keine Anfrage an diesen Speicher"
    - "Grund eines 403 entscheidet das Gateway, der Container deutet eine 404 nie um"
key-files:
  created:
    - backend/src/audio_video_search_backend/worker/read_proof.py
    - backend/tests/test_read_proof.py
    - backend/tests/test_read_proof_gate.py
    - ci/leak-control/read-proof-off.patch
    - ci/leak-control/README.md
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/worker/capture.py
    - backend/tests/test_capture.py
    - php/lib/Service/FileAccess.php
    - php/lib/Controller/GatewayController.php
    - php/tests/Unit/GatewayControllerTest.php
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
key-decisions:
  - "02-13: Kopfabweichung beim erneuten Beweis (andere Bytes, kein Lesefehler) löst den Verweis von der media und führt zum eigenen vollen Download, statt ihn unreadable zu setzen; Auslegung, Owner bitte bestätigen"
  - "02-13: locked beim erneuten Beweis macht den Verweis unreadable (keine Treffer ohne Beweis), verbraucht aber keinen Versuch; nächster Versuch nach 120 s"
  - "02-13: Sperrkreis zählt Zeitüberschreitungen von Kopf und vollem Download je storage_id; jede andere Antwort setzt die Zählung zurück; disk_full und too_large zählen nicht, weil keine Anfrage hinausging"
  - "02-13: Ein fehlgeschlagener erneuter Beweis behält media_id, damit der nächste Versuch wieder ein Lesebeweis ist und kein Download; Treffer gibt es nur für state active"
  - "02-13: Sofort fällig nach einem vollen Download werden nur wartende Geschwister (pending mit künftigem next_try_at), nicht fehlgeschlagene"
  - "02-13: attach_by_proof prüft in derselben Transaktion erneut, dass ein aktiver, keyed Geschwister mit gleichem Vorfilter-Schlüssel die media noch hält"
  - "02-13: 403 excluded der Kopf-Route gilt im Lesebeweis als read_denied (geschlossene Ergebnisliste), offen für Plan 16"
  - "02-13 (reason_77): 403 access_control nur, wenn der Wrapper von files_accesscontrol nein sagt und der Speicher direkt darunter ja; sonst bleibt die 404"
requirements-completed: []
metrics:
  duration: "ca. 30 min (ab Zeitmarke nach dem Einlesen)"
  completed: 2026-11-12
  tasks: 3
  files: 12
---

# Phase 2 Plan 13: Lesebeweis je Kopie, erneuter Beweis und reason_77 Summary

Eine Kopie mit dem Vorfilter-Schlüssel eines keyed Verweises hängt sich jetzt erst an dessen Inhalt, nachdem ihr eigener Leser die ersten 64 KiB über ihre eigene file_id gelesen hat (Zeitgrenze 45 s, Länge genau min(65536, size), sha256 gleich media.head_sha256); ein Verweis in stage probing mit media_id wird auf demselben Weg neu geprüft, und das Gateway meldet eine Sperre durch files_accesscontrol als 403 access_control statt als 404.

## Performance

- **Dauer:** ca. 30 min ab der Zeitmarke nach dem Einlesen der Planunterlagen
- **Beginn:** 2026-11-12T14:03:43Z
- **Ende:** 2026-11-12T14:33Z
- **Tasks:** 3 von 3
- **Dateien:** 12 (5 neu, 7 geändert, dazu deferred-items.md)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Negativtests, Positivkontrolle B und Gate (RED) | 42726a7 | backend/tests/test_read_proof.py, backend/tests/test_read_proof_gate.py |
| 2 | Lesebeweis und erneuter Beweis (GREEN), CI-Patch | 1a060b8 | nc.py, store/repo.py, worker/capture.py, worker/read_proof.py, tests/test_capture.py, beide Testdateien aus Task 1, ci/leak-control/read-proof-off.patch, ci/leak-control/README.md |
| 3 | reason_77: access_control statt 404 | 7c4784f | php/lib/Service/FileAccess.php, php/lib/Controller/GatewayController.php, php/tests/Unit/GatewayControllerTest.php, backend/tests/test_capture.py |

Alle drei Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht.

## Was gebaut wurde

**Kopf-Abruf (nc.py).** `fetch_head` liest die Kopf-Route des Gateways als der genannte Leser, hasht im Strom und behält nichts. Nur 200 mit höchstens 65536 Bytes ist ein Ergebnis; 403, 422, 423 und 404 werden wie beim vollen Download über `refusal_code` gelesen, mehr als 65536 Bytes ist `head_too_long` (über die angekündigte Länge und im Strom), Zeitüberschreitung und die Gesamtfrist von 45 s sind `read_timeout`. Keine Leser-ID und kein Pfad in den eigenen Logzeilen.

**Urteil (worker/read_proof.py).** `prove_read` fragt mit file_id und readerUid des Verweises und keines anderen. Ohne Leser gibt es keine Anfrage. Ein Fehlercode ist nie ok, auch wenn ein passender Hash daneben steht. 403, 422, 404 und excluded werden read_denied, access_control und locked bleiben, was sie sind, alles Unbekannte ist gateway_failed. Die Länge muss der erwarteten entsprechen, und die erwartete muss min(65536, ref.size) sein. Erst danach vergleicht `hmac.compare_digest`, und nur in dessen Zweig steht das einzige `return ProofOutcome.OK`. Andere Bytes sind head_mismatch.

**Sperrkreis (StorageBreaker).** Drei Zeitüberschreitungen in Folge auf einer storage_id öffnen ihn für 3600 s. Solange er offen ist, setzt die Stufe jeden fälligen Verweis dieses Speichers (neuer Beweis, erneuter Beweis, Download) ohne Anfrage auf unreadable, failed, storage_paused mit next_try_at gleich der Schließzeit; Versuche werden dabei nicht gezählt. Danach wird jeder neu geprüft. Andere Speicher laufen weiter.

**Store.** `prefilter_sibling` findet nur aktive, keyed Verweise, deren media einen Kopf hat. `attach_by_proof` ist ein bedingtes UPDATE (file_id, etag, media_id IS NULL, stage fetching) und prüft davor in derselben Transaktion, dass der Geschwister die media noch hält. `confirm_proof` setzt active, keyed, proved_at und nimmt der media die Verwaist-Marke. `fail_proof` setzt unreadable und behält media_id. `release_media` löst einen Verweis von seiner media. `mark_keyed` macht wartende Geschwister sofort fällig, gefunden über den Schlüssel, geschrieben über die file_id.

**Stufe (worker/capture.py).** Drei Wege je Schritt: Kopie ohne media mit Geschwister bekommt ihren Lesebeweis (ok hängt an, head_mismatch führt zum eigenen Download, sonst Urteil mit Grund nach der Zustandsmaschine aus Plan 08); Verweis mit media bekommt den erneuten Beweis gegen den Kopf seiner eigenen media; alle anderen laden voll. Parallelität bleibt 1.

**Gate (tests/test_read_proof_gate.py).** `scan(root)` liest php/ (ohne Tests) und backend/src: Regel a (Schaltwörter zusammen mit Lesebeweis oder Kopf, feste Namen, Markennamen), b (read_proof.py und capture.py ohne os.environ, getenv, settings., exists(, is_file(, debug, dazu Importlisten), c (AST: ein return ok im Zweig von hmac.compare_digest nach der Längenprüfung; attach_by_proof und confirm_proof nur in capture.py im Zweig `outcome is ProofOutcome.OK` einer Antwort von prove_read derselben Funktion), d (getFileHead und seine Helfer ohne Konfiguration), e (Patch nur unter ci/leak-control/, kein ci/ im Build-Kontext, kein anderer Workflow nennt ihn), f0 (mark_keyed nur in capture.py mit dem Hash des eigenen Abrufs), f (nur `_KEY_REF` und `_ATTACH_REF` setzen media_id per UPDATE, kein UPDATE mit prefilter_key in der WHERE-Klausel, attach bedingt).

**CI-Patch.** `ci/leak-control/read-proof-off.patch` ändert genau eine Datei: prove_read antwortet sofort ok. Erzeugt per `git diff --no-index` aus einer geänderten Kopie, das Original ist unverändert. Die README (englisch) nennt Zweck, Regeln (nur `localhost:5000`, nie ghcr, kein save, kein Artefakt) und den Weg, ihn nach einer Änderung an read_proof.py neu zu erzeugen.

**reason_77.** Siehe eigener Abschnitt.

## Prüfungen

Alle Befehle seriell, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| Task 1 verify (`! pytest ... -x && ! ... grep -q SyntaxError`) | Exit 0: Tests rot, kein Syntaxfehler |
| Task 2 verify: pytest der vier Dateien | Exit 0, 225 grün |
| ruff check . | Exit 0 |
| ruff format --check . | Exit 0, 66 Dateien |
| pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest) | Exit 0, 0 Fehler, 0 Warnungen |
| vulture | Exit 0 |
| pytest gesamt nach Task 2 | Exit 0, 756 grün |
| Task 3 verify: pytest tests/test_capture.py, dann gesamt | Exit 0, 95 grün und 766 grün |
| php -l, PHPUnit | **nicht gelaufen** (kein PHP lokal, Docker aus) |

Testzahlen am Ende: test_read_proof.py 118, test_read_proof_gate.py 18, test_capture.py 95 (vorher 85), test_php_gates.py 27, gesamt 766 (vorher 620).

**RED aus dem richtigen Grund (Task 1):** test_read_proof.py scheiterte am Import von `worker.read_proof`; das Gate meldete auf dem echten Baum genau: read_proof.py fehlt (b, c), Patch fehlt (e), `_ATTACH_REF` fehlt und attach nicht bedingt (f). Die Selbsttests des Gates auf Quelltext-Proben liefen schon.

**Positivkontrolle B:** Mit `monkeypatch` von `read_proof.prove_read` auf ok hängt sich dieselbe 403-Kopie an die media des Geschwisters und steht in `file_ids_for_media`; mit dem echten Urteil bleibt sie draußen.

**Gegenproben des Gates (Regel g), alle auf einer Kopie in tmp_path:** Patch per `git apply --check` und `git apply` angewandt, danach meldet Regel c zwei `return ProofOutcome.OK`, und nur read_proof.py unterscheidet sich vom Original; eingefügtes `os.environ.get` in capture.py lässt Regel b anschlagen; eingefügtes `UPDATE file_ref SET media_id ... WHERE prefilter_key` lässt Regel f zweimal anschlagen. Dazu je Regel Selbsttests auf Proben.

**Mutationen (Produkt geändert, Tests gelaufen, Datei zurückgesetzt; 19 von 19 wurden rot):** Längenprüfung entfernt (7 rot); erwartete Länge nicht an den Verweis gebunden (1); jeder Kopf gilt als gleich (14); Fehlercode mit Hash nicht abgewiesen (25); Sperrkreis öffnet nie (4); Anhängen ohne Geschwisterprüfung (3); ohne etag (1); ohne Claim (1); Geschwister muss nicht aktiv sein (3); muss nicht keyed sein (3); erneuter Beweis wird nie geholt (15); fehlgeschlagener erneuter Beweis bleibt aktiv (8); wartende Geschwister nicht geweckt (1); Bestätigen ohne etag (1); Kopfabweichung beim erneuten Beweis behält die media (1); offener Sperrkreis wird ignoriert (2); Zeitüberschreitungen des Kopfs zählen nicht für den Sperrkreis (1); Kopf länger als 64 KiB angenommen (1); Kopf ohne Gesamtfrist (3). Danach liefen alle Gates erneut grün, und die Gegenprobe mit dem Patch belegt, dass read_proof.py wieder dem Stand entspricht, aus dem der Patch erzeugt wurde.

## reason_77: Beleg und Umsetzung

**Beleg (am Quelltext gelesen, nicht per Lauf):** nextcloud/server stable33 (b752e78) und nextcloud/files_accesscontrol stable33 (91f744f).

- files_accesscontrol hängt seinen Wrapper in Webanfragen um jeden Speicher außer `/` (`lib/AppInfo/Application.php:44-56`), mit Priorität -10; die StorageFactory wendet höhere Prioritäten zuerst an, der Wrapper liegt damit außen.
- `StorageWrapper::getCache` liefert den `CacheWrapper` der App. Dessen `formatCacheEntry` (`lib/CacheWrapper.php:38-54`) fängt die ForbiddenException der Regel und nimmt der Cache-Zeile nur die Rechte READ, CREATE, UPDATE, DELETE. Die Zeile bleibt.
- `Root::getByIdInPath` (server `lib/private/Files/Node/Root.php`) baut den Knoten aus `$mount->getStorage()->getCache()->get($id)`. Er entsteht also, `getFirstNodeById` liefert ihn.
- `Node::isReadable` geht über `FileInfo::isReadable` auf `checkPermissions(PERMISSION_READ)` der Zeile und ist false.

Ergebnis: Auf stable33 verweigert die Regel bei **isReadable false**, nicht bei getFirstNodeById null und nicht mit einer Ausnahme beim Auflösen. `FileAccess::readableNode` gab deshalb null zurück und das Gateway 404. Das passt zum Zugriffslog aus Push 4 (Lauf 42387720556, Datei 77: 200 vor dem Tag, 404 danach). Klassenname und die benutzten Methoden (`getWrapperStorage`, `isReadable`, `instanceOfStorage`) habe ich auch auf stable34 und stable35 nachgesehen, sie sind gleich.

**Umsetzung:** `FileAccess::refusedByAccessControl($node)` ist nur wahr, wenn der Knoten eine Datei ist, nicht lesbar, der Speicher `instanceOfStorage('OCA\FilesAccessControl\StorageWrapper')` meldet (Klassenname als String, keine Abhängigkeit) und beim Abstieg durch die Wrapper die Schicht der App `isReadable` nein sagt, während der Speicher direkt darunter ja sagt. Die Datei wird dafür nicht geöffnet. Kein Knoten, ein Ordner, eine lesbare Datei, kein Wrapper, ein Speicher darunter, der selbst nein sagt, ein Jail über dem Wrapper und jeder Fehler beim Fragen ergeben false. `GatewayController::resolve` wirft im wahren Fall die ForbiddenException mit festem Text, `failure()` antwortet wie bisher 403 mit `X-AVS-Reason: access_control`, für Inhalts- und Kopf-Route. Alles andere bleibt die bisherige 404 mit unverändertem Körper. Der Container ist unverändert: 404 bleibt not_found (60 s), nur 403 mit Header ist access_control (300 s), im Lesebeweis `ProofOutcome.ACCESS_CONTROL`.

**Tests:** GatewayControllerTest 23 auf 35 Methoden (+12): 403 mit Header und Feld code ohne Pfad und mit zurückgesetztem Nutzer, dasselbe für die Kopf-Route, Logzeile nur mit fileId und reason, Wrapper unter einem weiteren Wrapper, und als 404: nicht lesbar ohne Wrapper, Speicher darunter verweigert selbst, Wrapper hätte nichts einzuwenden, Datei für den Nutzer nicht sichtbar, Ordner, Speicher wirft beim Fragen, Datei ohne Speicher; eine lesbare Datei wird ausgeliefert, ohne den Speicher zu fragen. Python: 10 Fälle in test_capture.py für Inhalts- und Kopf-Route.

## Lokal nicht belegbar (offen bis zum nächsten freigegebenen Push)

- **PHPUnit und php -l** für `FileAccess.php`, `GatewayController.php` und `GatewayControllerTest.php` sind nicht gelaufen: kein PHP im PATH, Docker bleibt aus. Die 12 neuen PHPUnit-Fälle sind ungeprüft geschrieben, RED und GREEN konnten nicht ausgeführt werden. Ersatzweise gelaufen: die statischen PHP-Gates in Python (test_php_gates.py 27 grün, Regel d des neuen Gates) und eine Klammerbilanz der drei Dateien. Das ist kein Syntaxbeweis.
- **Abnahme:** access-control:reason_77 und sperre_reason (erwartet access_control), read-proof, reprove und das Kontrollbein leak-control laufen nur in CI (Plan 17 und 22). Der Patch ist lokal per `git apply` auf einer Kopie geprüft, das Image des Kontrollbeins wurde nicht gebaut.
- **Annahme zur Pfadgleichheit:** `refusedByAccessControl` fragt den Wrapper mit `getInternalPath()` des Knotens. Das stimmt, solange über dem Wrapper der App kein Jail liegt (dann antwortet die Funktion false, also 404). Dass der Wrapper außen liegt, ist am Quelltext belegt, nicht per Lauf.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Sicherheit] attach_by_proof prüft den Geschwister erneut in der Transaktion**
- **Gefunden bei:** Task 2
- **Problem:** Zwischen Lesebeweis und Anhängen kann der Geschwister eine neue Version bekommen; die Kopie hinge dann an einer media, die kein geprüfter Verweis mehr hält.
- **Fix:** `_SIBLING_HOLDS` (SELECT) vor dem bedingten UPDATE; zusätzlich Bedingung stage fetching. Schlägt das Anhängen fehl und ist der Verweis noch der beanspruchte, lädt die Kopie selbst voll; hat er sich geändert, ist das Ergebnis stale.
- **Commit:** 1a060b8

**2. [Rule 2 - Sicherheit] Kopfabweichung beim erneuten Beweis gibt sofort keine Treffer mehr**
- **Problem:** Ein Verweis mit media, dessen eigener Kopf nicht mehr passt, hätte bis zum Ende seines Downloads (auch bei disk_full oder locked) weiter Treffer für die alte media gegeben.
- **Fix:** `Store.release_media` löst ihn vor dem Download von der media (media_id NULL, alte media nach der Verwaist-Regel).
- **Commit:** 1a060b8

**3. [Rule 1 - Fehler] test_capture.py an den Lesebeweis angepasst**
- Zwei Tests aus Plan 08 gingen davon aus, dass ein gleicher Vorfilter-Schlüssel nie anhängt. Der erste nutzt jetzt zwei verschiedene Schlüssel (zwei Downloads, eine media über den Inhalts-Schlüssel), der zweite lässt den Lesebeweis andere Bytes finden und prüft danach die neun Fehlerfälle des vollen Downloads wie bisher. Die Kopf-Route ist in dieser Datei ein Fake, der jeden unerwarteten Lesebeweis per Fixture rot macht; kein Test erreicht das Netz. Keine Erwartung wurde gelockert.
- **Commit:** 1a060b8

**4. [Rule 1 - Fehler] Korrekturen an den Tests aus Task 1 in Task 2**
- Typen für pyright, `RETURNING` zählt im Gate nicht als WHERE-Bedingung (sonst Fehlalarm bei `_CLAIM_CAPTURE`), zwei Selbsttest-Erwartungen des Gates berichtigt (Regel d sieht Zeichenketten bewusst nicht; `is not` ergibt zwei Befunde). Der RED-Commit 42726a7 enthält noch die falschen Erwartungen.
- **Commit:** 1a060b8

### Abweichungen von den Schnittstellen des Plans

- **mark_keyed und Regel f0:** Der Plan beschreibt mark_keyed mit einer media_id aus `media_for_file_sha256(<res>.sha256)`. Seit Plan 08 (dort Abweichung 4) nimmt mark_keyed den sha256 und legt die media selbst an. Das Gate prüft deshalb, dass der sha256 über `_validated(ref, result)` aus `await self._fetch(ref.file_id, ...)` desselben Verweises in derselben Funktion stammt und dass `_validated` die Hashes des Ergebnisses unverändert weitergibt. Der Selbsttest mit fremdem Hash schlägt an.
- **fail_proof:** Plan `fail_proof(file_id, reason)`, gebaut `fail_proof(claimed, reason, *, retry_at, bump, now)` nach dem Claim-Muster aus Plan 08 (schreibt nur bei unverändertem etag, size, mtime).
- **attach_by_proof und confirm_proof** haben zusätzlich den Parameter `now`.
- **Zusätzliche Store-Methoden:** `media_head`, `release_media`.
- **Dritte Schreibstelle für media_id:** `upsert_file_ref` (seit Phase 1, schreibt eine Zeile vollständig) setzt media_id ebenfalls. Im Paket ruft niemand sie auf, nur Tests. Das Gate hält genau das fest (Regel f: kein Aufruf im Paket) und lässt die einmalige Kopie der Migration v1 nach v2 zu. Die must_have-Aussage "nur mark_keyed und attach_by_proof" gilt damit für alles, was im Produkt läuft.
- **Regel a** läuft über Bezeichner und Zeichenketten (Python per AST, PHP unter lib/ ohne Kommentare) und zeilenweise über alle übrigen Produktdateien; Kommentare dürfen sagen, dass es keinen Abschaltweg gibt.
- **Regel e** prüft alle Workflows außer discovery-e2e.yml, nicht nur docker.yml und release.yml.
- **Task 3 in einem Commit:** RED und GREEN stehen zusammen in 7c4784f, weil der Plan einen Commit nennt und PHPUnit lokal ohnehin nicht läuft. Die Python-Tests zu reason_77 waren nie rot: Sie halten das unveränderte Verhalten des Containers fest.
- **Import-Reihenfolge im RED-Commit:** ruff meldete in 42726a7 I001 für test_read_proof.py, weil das Modul read_proof noch fehlte; ab 1a060b8 grün ohne Änderung der Zeilen.

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Kopfabweichung beim erneuten Beweis.** must_have: "jeder Fehlschlag -> state unreadable mit Grund". Gebaut: Lesefehler (403, 404, 422, Zeitüberschreitung, access_control, locked, gateway_failed) machen unreadable mit Grund. Liest der Nutzer aber erfolgreich und der Kopf ist ein anderer, ist das kein Lesefehler: Der Verweis wird von der media gelöst und voll geladen, er hängt danach am Inhalt seiner eigenen Bytes. Treffer für die alte media gibt es ab der Abweichung nicht mehr. Für die wörtliche Lesart fehlt ein Grund in der geschlossenen Liste (head_mismatch ist kein Zustandsgrund).
- **locked beim erneuten Beweis.** Unreadable mit Grund locked, nächster Versuch nach 120 s, ohne einen der fünf Versuche zu verbrauchen. Bei einer neuen Kopie bleibt locked wie in Plan 08 ein Aufschub ohne Urteil.
- **Sperrkreis.** "3 read_timeout in Folge" zähle ich über Kopf und Download zusammen; jede andere Antwort des Speichers setzt zurück. Der Zustand liegt im Speicher des Prozesses und beginnt nach einem Neustart neu.
- **Wartende Geschwister.** Geweckt werden nur aufgeschobene (pending mit künftigem next_try_at), nicht fehlgeschlagene; deren Wartezeit ist ein Urteil über das eigene Lesen.

## Known Stubs

- Wann ein erneuter Beweis fällig wird (stage probing mit media_id setzen), bauen Plan 15 (Wiederherstellung) und Plan 20 (Abgleich, alle 7 Tage). Dieser Plan führt ihn nur aus.
- `REQUIREMENTS` DISC-05 ist nicht abgehakt und steht deshalb nicht unter requirements-completed: wie in den Vorgängern erst nach der Abnahme (Plan 17 und 22). STATE.md und ROADMAP.md habe ich nicht angefasst.

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus. T-02-45 (eigener Leser, Länge, Kopf-Hash, bedingtes UPDATE, AST-Gate), T-02-46 (erneuter Beweis), T-02-47 (Regeln a bis e, Gegenprobe g), T-02-48 (Regel f mit Gegenprobe), T-02-49 (Zeitgrenzen, seriell, Sperrkreis) und T-02-50 (Regel e) sind umgesetzt. Die Frage an den Speicher in `refusedByAccessControl` ist eine Metadatenabfrage ohne Öffnen der Datei und läuft nur für Dateien, die der Nutzer sieht und nicht lesen darf.

## Offene Punkte

- PHPUnit, php -l und die Abnahme beim nächsten freigegebenen Push (Plan 17).
- 403 excluded im Lesebeweis (deferred-items.md), Entscheidung in Plan 16.
- `backend/src/audio_video_search_backend/.claude-active` liegt lokal im Quellbaum (per .gitignore ausgenommen) und fehlt in `backend/.dockerignore`; nur lokale Builds betroffen (deferred-items.md).

## Self-Check: PASSED

- Dateien vorhanden: read_proof.py, test_read_proof.py, test_read_proof_gate.py, ci/leak-control/read-proof-off.patch, ci/leak-control/README.md.
- Commits vorhanden: 42726a7, 1a060b8, 7c4784f.
