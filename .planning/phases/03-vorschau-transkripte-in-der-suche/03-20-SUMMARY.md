---
phase: 03-vorschau-transkripte-in-der-suche
plan: 20
subsystem: ci, abnahme
tags: [push-gate, discovery, deploy-harp, search-parity, leak-control, excerpt-leak, metrics]
requires: ["03-19"]
provides:
  - "CI-Abnahme der Phase 3 fuer SHA 4c972ea81f569aafcc22e6ca088946f295f7155f: vier Workflows gruen, sechs Discovery-Beine mit 22 Phasen PASS, sechs deploy-harp-Beine mit EXCERPT LEAK PROBE PASS, Kontrollbein zeigt das Leck"
  - "main und ghcr vorher/nachher unveraendert (404-Zustand, kein leak-control-Tag)"
affects: [03-21]
key-files:
  created:
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-20-SUMMARY.md
  modified: []
decisions:
  - "Owner-Freigabe push-and-dispatch lag vor (Freigabedatei push-4c972ea... mit 'push-phase-03 4c972ea...'); Push und Dispatch genau einmal"
  - "PHP gates fuer den SHA manuell per workflow_dispatch nachgereicht, weil der Fix keine php/**-Pfade beruehrt und der Push-Trigger nicht ansprang (vom Plan so vorgesehen)"
  - "RTF je Bein aus den engine-chunk-Sekunden der 10-Minuten-Stuecke der 40-min-Datei abgeleitet, weil kein RTF-Feld geloggt wird"
metrics:
  duration: "CI ca. 32 min (03:41 bis 04:14 UTC), Auswertung ca. 1 h"
  completed: 2026-11-15
  tasks: 2
  files: 1
---

# Phase 3 Plan 20: CI-Abnahme Phase 3 auf sechs Beinen Summary

Alle vier Pflicht-Workflows für SHA `4c972ea81f569aafcc22e6ca088946f295f7155f` auf phase-03 sind success: 22 Phasen PASS auf allen sechs Discovery-Beinen inkl. search-parity und play-leak, EXCERPT LEAK PROBE PASS auf allen sechs deploy-harp-Beinen, das Kontrollbein leak-control zeigt weiterhin das Leck, main und die ghcr-Paketliste sind unverändert.

## Läufe (alle für SHA 4c972ea, Branch phase-03)

| Workflow | Run | Event | Ergebnis | Zeitraum (UTC) |
|---|---|---|---|---|
| Python gates | [43673521508](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43673521508) | push | success | 03:41 bis 03:44 |
| Deploy through HaRP | [43673521607](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43673521607) | push | success | 03:41 bis 04:14 |
| Discovery acceptance (legs=all) | [43673528857](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43673528857) | workflow_dispatch | success | 03:42 bis 04:00 |
| PHP gates | [43673923342](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43673923342) | workflow_dispatch | success | 03:47 bis 03:48 |
| Discovery acceptance (Push-Lauf) | [43673521548](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43673521548) | push | cancelled | 03:41 bis 03:42 |

Vier Workflow-Namen, genau ein Discovery-Lauf mit event workflow_dispatch. Der push-getriggerte Discovery-Lauf 43673521548 wurde von der Concurrency-Gruppe zugunsten des Dispatch-Laufs abgebrochen, bevor ein Bein lief; er zählt nicht als Pflichtlauf und ist kein Fehlschlag (siehe Abweichungen).

## Push-Tor, main und ghcr

- Freigabedatei `$A/push-4c972ea...` enthält exakt `push-phase-03 4c972ea81f569aafcc22e6ca088946f295f7155f`; Push genau einmal nach `HEAD:phase-03`, kein `--force`, kein Tag.
- main vorher und nachher: `ea97b587154426a8a23daab57f34905a7089afdb refs/heads/main`, `cmp` identisch.
- ghcr `audio_video_search_backend` vorher und nachher: `STATE 404 Package not found` (erwartet, docker.yml veröffentlicht nur von main und Tags), `cmp` identisch, kein `leak-control`-Tag.
- Positivkontrolle für Endpunkt und Scope: `users/street1983nk/packages/container/findling_backend/versions` liefert Exit 0 und enthält den Tag `1.6.2`.

## Discovery acceptance (Run 43673528857, 6 Beine + leak-control, alle success)

Beine: stable33/stable34/stable35 je auf ubuntu-24.04 (amd64) und ubuntu-24.04-arm (arm64), Dauer je Bein ca. 18 min (03:42 bis ca. 04:00).

**PASS-Liste je Bein:** Auf jedem der sechs Beine stehen alle 22 Phasen im Log als `PHASE PASS <phase>` (je Phase einmal im Lauf und einmal in results.txt):
initial, read-proof, shares, access-control, upload, overwrite, copy, move-cross, rename, tag, trash, restore, exclude-user-after, exclude-storage-after, exclude-after, vanish, delete-user, reattach, foreign-change, reprove, search-parity, play-leak.
Keine einzige echte `PHASE FAIL`- oder `FAIL `-Zeile; die im Log sichtbaren `FAIL self-test:*`-Zeilen sind die gewollten Negativproben von `compare.sh --self-test` (contents, files_count, transcribed, never_in_log, session_shared_readers müssen einzeln scheitern).

**search-parity je Bein (identisch auf allen sechs Beinen):**

```text
parity ana erwartet=150,154,155 gefunden=150,154,155
parity ben erwartet=- gefunden=-
parity cem erwartet=154 gefunden=154
parity eva erwartet=- gefunden=-
parity fritz erwartet=- gefunden=-
```

Kein Treffer für eine nicht leseberechtigte oder ausgeschlossene Person (ben, eva, fritz leer); ana und cem haben Treffer, die Wahrheit sagt auch nein (ana sieht die Samba- und die files_accesscontrol-Kopie und liest beide nicht). `PARITY CONTROL SHOWED THE DIFF` auf jedem der sechs Beine (Selbsttest: zusätzliche ID, fehlende ID, doppelte ID, Treffer ohne das Vorläufig-Wort scheitern einzeln).

**play-leak je Bein:** `PLAY SELF-TEST PASSED`, `PLAY CONTROL SHOWED THE DIFF p12a` und `... p12b`, `p12a probe=156 state=unreadable,unreadable` bzw. `p12b probe PASS grund=a5_byte_equal` (Datei-IDs je Bein 62/63), dann `PHASE PASS play-leak` auf allen sechs Beinen.

**Kontrollbein:** Job leak-control success mit genau einer Zeile `LEAK CONTROL SHOWED THE LEAK`; in keinem Hauptbein taucht eine Leak-Zeile auf.

## Deploy through HaRP (Run 43673521607, 6 Beine + 4 Upgrade-Jobs, alle success)

- `EXCERPT LEAK PROBE PASS` auf allen sechs Beinen (stable33/34/35 x amd64/arm64): im Fenster des ausgeschlossenen Nutzers 0 `POST /excerpt`-Zeilen, in der Positivkontrolle mindestens 1.
- Kernpfad `a user without access finds nothing @preview` PASS auf allen sechs Beinen.
- Kontrast: Test "P1 Abspielseite eines Treffers: ... Kontrast mindestens 4,5:1" PASS auf allen geprüften Projekten je Bein (w375 hell/dunkel, w768 hell/dunkel, w1280 hell/dunkel, hc-1280); die Messung erzwingt `ratio >= 4.5` als Assertion, der Kontrast-Selbsttest (21:1 PASS, #767676 knapp über, #999999 unter 4,5:1) lief vorher auf jedem Bein. Kein Wert unter 4,5:1, sonst wäre der Lauf rot.
- Upgrade 0.2.0 nach 0.3.0: Jobs `upgrade stable33/34/35 ubuntu-24.04` und `upgrade stable35 ubuntu-24.04-arm` success.

## Messwerte

**Upload bis vorläufiger Treffer** (Testdauer `upload is found as preliminary within minutes @preview`, enthält Upload, Transkription des 11,16-s-Clips und Such-Polling):

| Bein | Zeit |
|---|---|
| stable33 amd64 | 54,5 s |
| stable33 arm64 | 43,8 s |
| stable34 amd64 | 33,5 s |
| stable34 arm64 | 23,3 s |
| stable35 amd64 | 22,6 s |
| stable35 arm64 | 22,9 s |

**RTF je Bein** (abgeleitet: die vier `engine chunk`-Zeilen der 40-min-Datei, je 600 s Audio; RTF = Chunk-Sekunden / 600):

| Bein | Chunk-Sekunden (4 Stücke) | RTF min bis max | RTF Mittel |
|---|---|---|---|
| stable33 amd64 | 62,3 / 68,0 / 54,3 / 48,9 | 0,081 bis 0,113 | 0,097 |
| stable33 arm64 | 35,6 / 34,2 / 32,6 / 29,6 | 0,049 bis 0,059 | 0,055 |
| stable34 amd64 | 52,9 / 57,3 / 47,3 / 41,9 | 0,070 bis 0,096 | 0,083 |
| stable34 arm64 | 35,0 / 33,7 / 32,4 / 29,2 | 0,049 bis 0,058 | 0,054 |
| stable35 amd64 | 48,9 / 52,9 / 43,8 / 39,2 | 0,065 bis 0,088 | 0,077 |
| stable35 arm64 | 35,2 / 34,2 / 32,6 / 29,1 | 0,049 bis 0,059 | 0,055 |

**Dauer der search-parity-Phase** (erste search-parity-Logzeile bis `PHASE PASS search-parity`): stable33 amd64 96,5 s, stable33 arm64 101,6 s, stable34 amd64 97,1 s, stable34 arm64 99,0 s, stable35 amd64 97,0 s, stable35 arm64 102,0 s.

**RAM-Spitze des Kinds:** nicht geloggt (das Backend loggt je Chunk nur code und seconds); kein Messwert verfügbar, wie im Plan mit "falls geloggt" vorgesehen.

## Python gates (Run 43673521508) und PHP gates (Run 43673923342)

- pytest mit `-q -rs --cov`: `1938 passed in 113.02s`, null `SKIPPED`-Zeilen, die Modelltests liefen also (Modell-Cache-Hit `avs-models-3a78ea81...`, `AVS_TEST_MODELS` gesetzt). Abdeckung 94,11 % bei Pflicht 90 %. ruff, format, pyright, vulture, shellcheck grün.
- PHPUnit: `OK (791 tests, 10761 assertions)`, composer validate und audit grün.

## Sicherheitsprüfungen (alle unauffällig)

1. Kein Treffer für nicht leseberechtigte Personen in search-parity (ben, eva, fritz leer auf allen sechs Beinen).
2. Kein Leak in einem Hauptbein (keine Leak-Zeile außerhalb des Kontrollbeins).
3. Kontrollbein zeigt das Leck (`LEAK CONTROL SHOWED THE LEAK`).
4. Kein Kontrast unter 4,5:1 (Assertion plus kalibrierter Selbsttest, alle P1-Tests grün).
5. `/excerpt` wird für ausgeschlossene Nutzer nie gefragt (EXCERPT LEAK PROBE PASS, sechs Beine).

## Abweichungen vom Plan

1. **Gecancelter Push-Discovery-Lauf:** Das strikte Verify (`[.[]|select(.conclusion!="success")]|length == 0` über alle Läufe des SHA) ist formal nicht erfüllbar, weil der push-getriggerte Discovery-Lauf 43673521548 von der Concurrency-Gruppe zugunsten des Dispatch-Laufs abgebrochen wurde, bevor ein Bein startete. Alle Pflichtläufe (vier Workflows, je mindestens ein Lauf) sind success; das entspricht dem in 02-22 dokumentierten Verhalten (ein zusätzlicher Lauf ist erlaubt, solange die Pflichtläufe grün sind).
2. **Kontrast-Zahlenwerte nicht erhalten:** Die gemessenen Werte stehen nur in den Playwright-Annotationen des @preview-Laufs; das `playwright-report`-Verzeichnis wird im selben Job von späteren Playwright-Aufrufen (@disabled, @unreachable, @missing) überschrieben, das hochgeladene Artefakt enthält nur den letzten Report (admin.spec.ts). Belegt ist das Gate (Assertion >= 4,5:1 plus Selbsttest), nicht der Zahlenwert. Falls die Zahlen gewünscht sind: Report je Playwright-Aufruf in ein eigenes Verzeichnis schreiben oder die Annotation zusätzlich auf stdout loggen (Kandidat für 03-21 oder eine Hülle).
3. **RTF nicht direkt geloggt:** Es gibt kein RTF-Feld; die Tabelle oben leitet die RTF aus den vier 10-Minuten-Stücken der 40-min-Datei ab (`engine chunk`-Sekunden aus exapp-preview.log der deploy-harp-Logs-Artefakte). Die kurzen Chunks der Seed-Medien sind keinem Medium zuzuordnen (Logs tragen bewusst keinen Dateibezug).
4. **EXCERPT LEAK PROBE PASS stammt aus Deploy through HaRP:** Die must_have-Formulierung "auf jedem Bein" ist über die sechs deploy-harp-Beine belegt; die Discovery-Beine tragen stattdessen die play-leak-Proben p12a/p12b. Beide Pfade sind sechsfach grün.
5. **PHP gates per Dispatch:** Der Push löste PHP gates nicht aus (Pfadfilter php/**, der Fix berührt keine php-Dateien); der Lauf wurde wie im Plan vorgesehen manuell per `gh workflow run php.yml --ref phase-03` nachgereicht.

## Self-Check: PASSED

- `.planning/phases/03-vorschau-transkripte-in-der-suche/03-20-SUMMARY.md` existiert.
- `$A/main-before-4c972ea...`, `$A/main-after-4c972ea...`, `$A/ghcr-before-4c972ea...`, `$A/ghcr-after-4c972ea...`, `$A/discovery-4c972ea....log` existieren (approvals-Ordner, via .git/info/exclude vom Repo ausgeschlossen).
- Run-IDs 43673521508, 43673521607, 43673528857, 43673923342 success für SHA 4c972ea auf phase-03; 43673521548 cancelled (Concurrency).
