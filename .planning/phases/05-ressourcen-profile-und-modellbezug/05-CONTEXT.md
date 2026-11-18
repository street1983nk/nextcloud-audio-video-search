# Phase 5: Ressourcen, Profile und Modellbezug - Context

**Gathered:** 2026-11-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Die App läuft auf jeder unterstützten Hardware sicher:
- Sie schlägt das beste sicher lauffähige Profil (Schnell, Ausgewogen, Qualität) vor.
- Sie startet kein Modell ohne genug Speicher.
- Bei Speichermangel trifft sie nie Nextcloud oder die Datenbank.
- Sie hält Thread-Grenze und Rechenfenster ein, rechnet Vorschauen vor der Veredelung und die neueste Datei zuerst.
- Sie bezieht Whisper-Modelle nachprüfbar (fester Commit, sha256, Host-Allowlist) oder offline.
- Sie nennt alle Lizenzen.

Requirements: RES-01 bis RES-07, PLAT-04.

Nicht in dieser Phase:
- die Veredelung selbst (turbo, large-v3, ROVER, atomarer Ersatz; Phase 6)
- Instanz-Sprachen (Phase 7)
- die große Zustandsseite mit Fortschritt, Pause und Wiederholung (Phase 9)

Phase 5 liefert die Ressourcen-Grundlage und den Modellbezug, auf denen Phase 6 aufsetzt. Die Profilvorwahl bleibt bis Phase 11 nur RAM-basiert (Research flag ROADMAP).

</domain>

<decisions>
## Implementation Decisions

### Profil-Vorschlag und Sperre
- **D-05-01:** Vorgeschlagenes Profil, Grund und Auswahl stehen in den bestehenden Admin-Einstellungen der App (php/lib/Settings/Admin.php, php/templates/admin.php). Es gibt kein eigenes neues Panel; die große Zustandsseite kommt in Phase 9.
- **D-05-02:** Profile, die mehr RAM brauchen, als der Container sicher hat, sind HART gesperrt. Ein Erzwingen ist nicht möglich. Die Sperre zeigt einen Grund mit Zahlen (Bedarf und verfügbarer Speicher, z. B. "braucht 4,5 GB, verfügbar 3,1 GB"). Der RAM-Wächter je Modell (RES-02) prüft zusätzlich vor jedem Start.

### Rechenfenster
- **D-05-03:** Standard nach der Installation: immer rechnen (kein Fenster), passend zum Kernwert "ohne Konfiguration durchsuchbar". Der Admin kann ein Fenster setzen (Uhrzeiten, z. B. 22 bis 6 Uhr, über Mitternacht möglich). Gesetzt gilt es für alle Rechenarbeit, also auch für Vorschauen (ROADMAP-Kriterium 3).
- **D-05-04:** Am Fensterende wird das aktuell laufende Stück (ca. 10 min Medienlänge) fertig gerechnet und gespeichert, danach pausiert die App bis zum nächsten Fenster. Es gibt keinen harten Abbruch und keinen Rechenverlust; ein Überziehen um wenige Minuten ist akzeptiert.

### Whisper-Modellbezug
- **D-05-05:** Quelle ist das EIGENE GitHub-Release (street1983nk/nextcloud-audio-video-search), wie Parakeet nach D-03-21.
  - Allowlist nur github.com und release-assets.githubusercontent.com (am echten Redirect prüfen).
  - Commit und sha256 sind fest im Katalog.
  - Das Anlegen oder Hochladen der Release-Assets (turbo, large-v3) ist nach außen gerichtet: VORHER den Owner fragen.
  - Größen laut Stack-Recherche: turbo model.bin 1,62 GB, large-v3 3,09 GB. GitHub-Release-Assets haben eine Obergrenze von 2 GiB je Datei. Das muss die Recherche lösen, ohne die sha256-Kette aufzuweichen, z. B. mit Teilen mit sha256 je Teil und für das Ganze. Eine int8-Vorkonvertierung kommt nur in Frage, wenn das Release-Gate dieselbe WER zeigt.
- **D-05-06:** Die App lädt die Modelle des gewählten bzw. vorgeschlagenen Profils automatisch, ohne Admin-Klick. Der Admin sieht Größe und Fortschritt des Downloads in den Admin-Einstellungen. Ein Modell, dessen sha256 nicht passt, wird verworfen und nie geladen.
- **D-05-07:** Offline-Modus: Standard AUS, ein Schalter ist vorhanden. Bei Offline gibt es keinerlei ausgehende Verbindung, belegt per Netzwerkmitschnitt (ROADMAP-Kriterium 4). Der Admin legt die Modelldateien selbst ab (per occ oder in einen Ordner), die sha256-Prüfung gilt auch dann.

### Lizenzen in der App
- **D-05-08:** Die Admin-Einstellungen bekommen einen eigenen Abschnitt "Modelle und Lizenzen":
  - Namensnennung NVIDIA Parakeet (CC-BY-4.0)
  - Whisper (MIT), Silero VAD (MIT), ffmpeg (LGPL), PyAV-Codecs
  - Link auf THIRD-PARTY.md

  Dazu kommen README (DE/EN/FR) und eine neue THIRD-PARTY.md. In der Abspielansicht gibt es keine Lizenzzeile.

### Nachentscheide nach der Recherche (Owner 18.11.2026)
- **D-05-09:** 2 GB RAM ist kein Pflichtziel.
  - Zuerst die Linux-Spitze von Parakeet in der CI messen, auf amd64 und arm64 (ru_maxrss, Wave 0).
  - Danach ein Mindest-RAM festlegen und in README und im Admin-Hinweis nennen.
  - Darunter bleibt die App sicher, rechnet nicht und sagt das klar.
- **D-05-10:** faster-whisper 1.2.1 mit CTranslate2 4.8.5 und onnxruntime 1.31.1 kommt schon in Phase 5 ins Image, damit RAM-Schwellen und Thread-Nachweis unter Linux gemessen werden. Bei den gemessenen Pins bleiben, keine 4.9.0 oder 1.32.0.
- **D-05-11:** Die Thread-Zahl kommt in die Herkunft der Transkripte. Der Admin darf Threads senken. Ein CI-Test misst, ob 1 und 2 Threads unterschiedliche Wörter liefern.
- **D-05-12:** Das Rechenfenster pausiert nur das Rechnen. Das Erfassen neuer Dateien (capture) läuft immer.
- **D-05-13:** Die Whisper-Assets kommen unter ein NEUES Release-Tag (z. B. whisper-2026-11); models-2026-11 bleibt unverändert. Beide Modelle werden in 1-GiB-Teilen abgelegt, mit sha256 je Teil und für die ganze Datei (Gesamtwert gleich HF-LFS). Den Upload macht nur der Owner bzw. er erfolgt erst nach dessen Ok.
- **D-05-14:** Parakeet und Silero kommen ins Image (RES-06). Die alten Kopien auf dem Volume löscht die App nur, wenn die Image-Datei mit gleichem sha256 vorhanden ist. MODEL_SHA256 bleibt unverändert.
- **D-05-15:** THIRD-PARTY.md nennt für large-v3 beide Lizenzangaben mit Quelle: Gewichte von OpenAI, laut Modellkarte Apache-2.0; CTranslate2-Konvertierung von Systran, MIT. PyAV 19.0.2 bündelt libx264/libx265, deshalb gehört ein GPL-Hinweis dazu. Fremde Lizenztexte kommen nicht nach LICENSES/ (wegen reuse lint).

### Claude's Discretion
- Profilschwellen (RAM je Profil) aus den Spike-3-Kennzahlen plus Reserve ableiten:
  - Parakeet 1,2 GB
  - turbo 1,9 GB, ohne Stückelung bis 3,4 GB
  - large-v3 3,3 bis 4,5 GB

  Kurzen Eigentest nur so weit, wie er die RAM-Entscheidung stützt.
- Form der Thread-Grenze (RES-05):
  - Standard aus cgroup cpu.max und Affinität mit einem Deckel.
  - Der Admin kann ihn nur senken.
- OOM-Isolation (RES-03): oom_score_adj hoch und nice für die Erkennungs-Kinder; Nachweis per provoziertem Speichermangel in einem Container mit --memory=2g in der CI.
- Reihenfolge (RES-04) in der vorhandenen Warteschlange: erst Vorschauen, dann Veredelung, je neueste Datei zuerst.
- Texte dreisprachig DE/EN/FR (Dauerregel), echte Umlaute, keine Gedankenstriche.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Anforderungen und Ziel
- `.planning/ROADMAP.md` (Phase 5): Goal, 5 Erfolgskriterien, Research flag
- `.planning/REQUIREMENTS.md`: RES-01 bis RES-07, PLAT-04
- `.planning/PROJECT.md`: Profile laut Spike 3, Kennzahlen, Lizenzen, RAM-Wächter-Grundsatz

### Frühere Entscheide
- `.planning/phases/03-vorschau-transkripte-in-der-suche/03-CONTEXT.md`: D-03-21 (eigenes GitHub-Release statt HF, Allowlist, HF_HUB_OFFLINE), Parakeet-Kindprozess, "voller cgroup-Wächter in Phase 5"
- `.planning/phases/04-suchqualit-t-und-export/04-CONTEXT.md`: Abgrenzung der Phasen

### Spike-Quellen (außerhalb des Repos)
- `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE3-REPORT.md` Abschnitt 11: feste Einstellungen und Profile, RAM- und RTF-Kennzahlen

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/audio_video_search_backend/memory_guard.py`: cgroup-v2-Lesen (memory.max, anon, memory.events), `headroom_bytes`, `admits`; die Grundlage für RES-01 und RES-02
- `backend/src/audio_video_search_backend/engine/child.py`:
  - Kindprozess mit `ENGINE_NICE = 10` und `THREAD_ENV` (OMP_NUM_THREADS 2)
  - Prüfung des Headrooms vor dem Start (`NO_ROOM`)
  - Hier kommen oom_score_adj und die Thread-Grenze dazu.
- `backend/src/audio_video_search_backend/models/catalog.py` und `procure.py`: Modellkatalog mit sha256 und Bezug, Begründung GitHub statt HF
- `backend/src/audio_video_search_backend/nc.py` `fetch_model_asset`: eigener Client mit Host-Allowlist
- `php/lib/Settings/Admin.php`, `php/templates/admin.php`, `ci/playwright/admin.spec.ts`: bestehende Admin-Einstellungen und deren Playwright-Test

### Established Patterns
- Zwei-App-Muster (PHP-App und ExApp im Lockstep); Einstellungen laufen über die PHP-Seite zur ExApp.
- Fail-closed bei Modellen: falscher sha256 führt zu Verwerfen.
- Lehre aus PII 02-16 (18.11.2026): OMP_THREAD_LIMIT=1 zusammen mit einer Bibliothek, die mehr Threads plant, ließ arm64 hängen. Deshalb Threads einheitlich setzen (OMP_NUM_THREADS und die Thread-Zahl der Bibliothek, z. B. CTranslate2 cpu_threads) und auf amd64 UND arm64 in der CI messen.

### Integration Points
- Warteschlange (`nc_queue.py`, `worker/`) für Reihenfolge und Rechenfenster
- `settings.py` / `config.py` für Profil, Threads, Fenster, Offline-Schalter
- Dockerfile: Parakeet und Silero liegen im Image (RES-06), HF_HUB_OFFLINE/Telemetrie aus

</code_context>

<specifics>
## Specific Ideas

- Der Sperrgrund nennt konkrete Zahlen, keine Floskel.
- Download-Fortschritt und Modellgröße sind für den Admin sichtbar, bevor die Veredelung startet.

</specifics>

<deferred>
## Deferred Ideas

- Lizenzzeile in der Abspielansicht für Nutzer: bewusst nicht (Owner 18.11.2026).
- Hardware-basierte Profilvorwahl mit CPU-Messung über RAM hinaus: Phase 11 (Hardware-Messung).

</deferred>

---

*Phase: 05-ressourcen-profile-und-modellbezug*
*Context gathered: 2026-11-18*
