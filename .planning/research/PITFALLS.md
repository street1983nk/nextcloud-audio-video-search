# Pitfalls Research

**Domain:** Lokale Audio-/Video-Transkription mit Volltextsuche als Nextcloud-ExApp (CPU, amd64 + arm64, DE/EN/FR)
**Researched:** 2026-11-06
**Confidence:** MEDIUM bis HIGH (Modell- und Pipeline-Fallen aus eigenen Messungen in Spike 1 bis 3 belegt; Nextcloud-Rechte- und Lebenszyklus-Fallen aus echten Findling-Issues #14, #15, #18, #19, #25, #33, #36, #44, #45; Format- und Untertitel-Regeln aus W3C-Spezifikation; einzelne Nextcloud-Interna nur MEDIUM bis LOW, jeweils markiert)

Phasen-Bezeichner in dieser Datei (Vorschlag für die Roadmap, Namen frei änderbar):

| Kürzel | Phase |
|--------|-------|
| P-ARCH | Architektur-Tor: ExApp plus PHP-Begleit-App, Datenmodell, Schlüssel je Datei |
| P-RES | Ressourcen und Prozessmodell: RAM-Wächter (cgroup), Kindprozesse, Priorität, Hardware-Profil |
| P-WALK | Dateierkennung, Warteschlange, Reconcile, externe Speicher, Ausschlüsse |
| P-MEDIA | Medien-Eingang: Download, ffprobe/ffmpeg, Spurwahl, Formatfehler, Sicherheit |
| P-PREV | Vorschau-Pipeline: VAD, Parakeet, Schluck-Wächter, Abfangregel |
| P-SEARCH | Index und Unified-Search-Provider mit Rechtegrenze |
| P-QUAL | Qualitätsdurchgang: turbo/large-v3, ROVER, Sprachwechsel, atomarer Tausch |
| P-LIFE | Lebenszyklus: Löschen, Papierkorb, Versionen, Verschieben, DSGVO |
| P-SUB | SRT/VTT-Export |
| P-MODEL | Modellbezug, Offline-Betrieb, Lizenzen, Namensnennung |
| P-REL | arm64/N100/Pi-5-Messung, Release-Gate, i18n-Volltest DE/EN/FR, Store |

---

## Critical Pitfalls

### Pitfall 1: Unified Search und Datei-Ereignisse sind aus einer reinen Python-ExApp nicht erreichbar

**What goes wrong:**
Die Roadmap plant "Python-ExApp aus dem Skeleton" und setzt den Suchprovider als späte Aufgabe an. Beim Bau zeigt sich: AppAPI bietet ExApps deklarative Einstellungen, Menüeinträge, Datei-Aktionen und TaskProcessing-Provider, aber keinen Unified-Search-Provider. nc_py_api 0.30.3 (im Skeleton installiert) enthält keinerlei Search-Provider-API. Ohne PHP-Teil gibt es weder Suchtreffer in der Nextcloud-Suche noch synchrone Datei-Ereignisse (Erstellen, Ändern, Löschen, Verschieben) ohne zusätzliche Abhängigkeit von `webhook_listeners`.

**Why it happens:**
Das Skeleton stammt aus einer reinen Container-App; Findling hat für genau diese Aufgaben eine PHP-App (`php/lib/Search/Provider.php`, Event-Listener, Crawl-Jobs), die man leicht übersieht, wenn nur der Container-Teil übernommen wird.

**How to avoid:**
Im ersten Architektur-Tor entscheiden und festschreiben: PHP-Begleit-App (Store-Eintrag oder gebündelt, Versions-Gleichschritt mit der ExApp) für Suchprovider, Event-Listener, Rechteprüfung und Crawl, Container nur für Rechnen und Index. Findlings Aufteilung, Migration je Minor-Sprung und Upgrade-Beweis in CI übernehmen. Alternative `webhook_listeners` nur prüfen, wenn der PHP-Teil vermieden werden muss: `NodeDeletedEvent` trägt dort keine Datei-ID mehr (nur Pfad), dafür braucht es `BeforeNodeDeletedEvent` [MEDIUM, Nextcloud-Doku webhook_listeners].

**Warning signs:**
Ein Plan "Suchprovider" ohne PHP-Dateien; Recherche nach "AppAPI register search provider" ohne Treffer; Löschungen, die im Container nur als Pfad ankommen.

**Phase to address:** P-ARCH (vor jeder anderen Bauphase).

---

### Pitfall 2: RAM-Wächter misst den Host statt des Containers, der OOM-Killer trifft die Datenbank

**What goes wrong:**
Der Wächter liest `/proc/meminfo` oder `psutil.virtual_memory()` und sieht den freien Speicher des Hosts. Mit Docker-Limit wird der Container trotzdem per OOM beendet (Exit 137), mitten in einer Datei. Ohne Limit (AppAPI setzt standardmäßig keins) wählt der Host-OOM-Killer den Prozess mit dem höchsten Score, oft MariaDB/PostgreSQL oder PHP-FPM: die ganze Nextcloud fällt aus, nicht nur die App. Gleiches gilt für `os.cpu_count()`: liefert Host-Kerne, nicht die CPU-Quote, also zu viele Threads.

**Why it happens:**
Auf dem Spike-Laptop lief alles als normaler Prozess ohne cgroup; dort stimmte die Host-Messung. Spike 3 misst turbo bei 1,9 GB, ohne Stückelung 3,4 GB, large-v3 bis 4,5 GB: der Abstand zur Grenze eines 4-GB-Pi oder 8-GB-NAS ist klein.

**How to avoid:**
- Freien Speicher aus cgroup v2 lesen (`/sys/fs/cgroup/memory.max` minus `memory.current`, dazu `memory.stat` für Datei-Cache), Rückfall auf cgroup v1 und erst dann auf meminfo; CPU-Quote aus `cpu.max`.
- Bedarf je Modell wie Spike 3 (Parakeet 1,4 GB, turbo 2,0 bis 2,5 GB, large-v3 4,0 bis 4,5 GB) plus 1 GB Reserve; zusätzlich Host-Reserve für Nextcloud selbst.
- Jedes Modell in einem Kindprozess laufen lassen, der sich vor dem Laden `oom_score_adj` auf 1000 setzt (unprivilegiert erlaubt): der Kernel opfert dann zuerst den Rechenprozess, nie die Datenbank.
- Einen getöteten Kindprozess als Ereignis behandeln (Exit-Code -9/137), Datei mit Grund "Speicher reichte nicht" zurückstellen, Profil für diese Datei eine Stufe kleiner.

**Warning signs:**
Container-Neustarts ohne Python-Traceback; `dmesg` mit "Killed process"; Nextcloud-Fehler "database gone away" während der Transkription; Thread-Zahl gleich Host-Kernen auf einem Rechner mit `--cpus`.

**Phase to address:** P-RES (vor der ersten Pipeline, damit P-PREV schon geschützt läuft); Negativtest mit `docker run --memory=2g` in CI.

---

### Pitfall 3: Ein Giftfile hält die ganze Warteschlange an, abgestürzte Jobs bleiben "in Arbeit"

**What goes wrong:**
Eine Datei bringt den Encoder zum Absturz (Restsegment unter 0,1 s: `ConvInteger ... Invalid input shape: {0,128}`, Spike 1), ffmpeg hängt auf einer kaputten Datei, oder der OOM-Killer beendet den Prozess. Der Job steht danach dauerhaft auf "läuft", der nächste Start nimmt dieselbe Datei wieder zuerst, und der Bestand bewegt sich nie. Genau dieses Muster hatte Findling: einzelne UTF-16-Surrogate warfen in `add_text` und hielten den ganzen Durchgang an (#44); kurze Lesungen endeten als "repeatedly_stuck" (F-29-03).

**Why it happens:**
Status wird vor der Arbeit gesetzt und erst nach Erfolg zurückgenommen; kein Lease, kein Versuchszähler, keine Zeitgrenze je Datei.

**How to avoid:**
- Lease mit Ablauf je Datei (Herzschlag aus dem Kindprozess), beim Start abgelaufene Leases zurück in die Warteschlange.
- Versuchszähler: nach 3 Abbrüchen Endzustand `failed` mit Grund (z. B. `repeatedly_stuck`, `decoder_error`, `out_of_memory`), sichtbar im Admin-Status, nie stilles Überspringen.
- Zeitgrenze je Datei aus Dauer mal erwarteter RTF mal Sicherheitsfaktor; ffmpeg mit eigener Zeitgrenze.
- Fehler einer Datei dürfen nie den Stapel abbrechen: Ausnahme je Datei fangen, protokollieren, weiter.
- Segmente unter 0,5 s auffüllen oder verwerfen (Spike 1), als Regressionstest festnageln; Texte vor dem Index mit Findlings `_without_surrogates`-Muster säubern.

**Warning signs:**
Zähler "in Arbeit" bleibt über Stunden gleich; dieselbe Datei-ID taucht nach jedem Neustart als erste im Log auf; Fortschritt 0 trotz CPU-Last.

**Phase to address:** P-WALK (Warteschlangen-Modell) und P-PREV (Mini-Segment-Test); Absturz-Fuzzing in P-REL.

---

### Pitfall 4: Rechte werden im Container gespeichert statt bei jeder Suche geprüft

**What goes wrong:**
Der Index speichert "Nutzer X darf Datei Y" beim Transkribieren. Wird eine Freigabe entzogen, ein Nutzer aus einer Gruppe entfernt oder eine Gruppenordner-ACL geändert, findet X weiter gesprochenen Text aus Y. Bei Transkripten ist das ein Datenleck mit Inhalt (Sitzungen, Personalgespräche), nicht nur mit Dateinamen.

**Why it happens:**
Rechteprüfung zur Abfragezeit ist teuer, also wird sie vorgezogen. Die Projektanforderung "Rechte wie die Datei, entzogen wirkt sofort" ist damit unvereinbar.

**How to avoid:**
- Der Index kennt nur Datei-IDs, nie Nutzerrechte. Der PHP-Suchprovider prüft jeden Treffer im Kontext des suchenden Nutzers (`getUserFolder($uid)->getFirstNodeById()` plus `isReadable()`), wie Findling.
- Überabruf mit Nachladen: Top-k aus dem Index, filtern, bei Unterfüllung die nächste Seite holen, sonst zeigt die Suche leere Seiten trotz vorhandener Treffer.
- Negativtests in CI: Freigabe entziehen, Gruppe verlassen, ACL `-read` setzen, Datei in Papierkorb: Treffer muss in derselben Sekunde verschwinden.
- Snippets erst nach bestandener Prüfung erzeugen, nie im Container vorab an den Nutzer gebunden.

**Warning signs:**
Ein Feld `user_id` oder `allowed_users` im Transkript-Schema; Suchprovider ohne Aufruf von `getUserFolder`; Trefferzahl, die nach Rechteentzug unverändert bleibt.

**Phase to address:** P-ARCH (Schema ohne Rechte) und P-SEARCH (Prüfung plus Negativtests).

---

### Pitfall 5: Gruppenordner-ACL verbirgt Dateien vor dem Lese-Pfad der App (Findling #14)

**What goes wrong:**
Die App lädt eine Gruppenordner-Datei im Namen eines Mitglieds über einen HTTP-Aufruf aus dem ExApp-Kontext. groupfolders wertet dann die "inShare"-Heuristik aus (Nicht-CLI-Anfrage, Sitzungsnutzer ungleich Mount-Nutzer) und verlangt READ plus SHARE. Bei ACL-Regeln mit `-share` (häufig in Behörden und Firmen) ist die Datei für jedes Mitglied unlesbar. Bei Findling endeten so rund 250 000 Dateien als "unreadable", Abdeckung 22 %.

**Why it happens:**
Im CLI-Test (occ, PHP-Skript) ist alles lesbar; der Fehler tritt nur im echten Claim-Pfad über HTTP auf.

**How to avoid:**
Findlings Fix für #14 übernehmen (Lese-Kontext so aufbauen, dass die Prüfung im Kontext des Mitglieds läuft, siehe `quick/260929-s7p-issue14-acl-reader-context`). Testaufbau aus der Findling-Debug-Session als festen CI-Fall: Gruppenordner mit ACL `+read -share`, Gruppen mit führendem `/`, Upload per WebDAV, echter Claim-Pfad.

**Warning signs:**
Gruppenordner-Dateien landen gehäuft als "nicht lesbar"; Abdeckung auf Instanzen mit Gruppenordnern deutlich unter Home-Ordnern.

**Phase to address:** P-WALK (Lese-Pfad) mit CI-Fall; erneut in P-REL auf der budachst-ähnlichen Testinstanz.

---

### Pitfall 6: Externe Speicher je Nutzer werden N-fach transkribiert oder sind im Hintergrund gar nicht lesbar

**What goes wrong:**
- Ein SMB-Share, das für jeden Nutzer einzeln eingebunden ist (Nutzer-Anmeldedaten, `$user` im Pfad), ist in Nextcloud je Nutzer ein eigener Storage mit eigenen Datei-IDs. Dieselbe Sitzungsaufnahme wird dann 30-mal transkribiert, und der Fortschrittsnenner zählt 30-fach (Findling #25: angezeigt 7 %, real rund 100 %). Bei Transkription mit RTF 0,5 ist das kein Schönheitsfehler, sondern Wochen Rechenzeit.
- Speicher mit "Anmeldedaten in der Sitzung speichern" sind außerhalb einer Nutzersitzung nicht lesbar; Hintergrund-Transkription scheitert dauerhaft [MEDIUM, Mechanismus der Sitzungs-Anmeldedaten].
- Änderungen direkt auf dem SMB-Server kommen ohne Nextcloud-Scan nie als Ereignis an.

**Why it happens:**
Datei-ID wird als einziger Schlüssel benutzt; externe Speicher werden wie Home-Ordner behandelt.

**How to avoid:**
- Ergebnis-Schlüssel ist ein Inhalts-Fingerabdruck (siehe Pitfall 12), nicht die Datei-ID; mehrere Datei-IDs zeigen auf dasselbe Transkript, die Rechteprüfung bleibt je Datei-ID (keine Rechte über den Fingerabdruck vererben, Findlings Dedup-Weg B "kein neues ACL-Risiko").
- Share-Gruppen wie Findling nach dem größten Mitglied zählen (Plan 41-02).
- Sitzungs-Anmeldedaten erkennen und als eigener Überspring-Grund "nur mit Anmeldung lesbar" ausweisen.
- Admin-Schalter "ganzen externen Mount ausschließen" von Anfang an (Findling #45 wurde nachträglich gewünscht).

**Warning signs:**
Gleiche Dateigröße und Dauer vielfach in der Warteschlange; Fortschritt bleibt bei Mounts mit vielen Nutzern niedrig; viele "unreadable" nur auf einem Mount.

**Phase to address:** P-ARCH (Schlüssel), P-WALK (Mounts, Zählung, Ausschlüsse).

---

### Pitfall 7: Das "bessere" Transkript verliert Text, den die Vorschau hatte

**What goes wrong:**
Whisper lässt ganze Sätze aus (Spike 3: fleurs_en turbo 24,4 % WER, 229 von 310 Fehlern Deletions). Ersetzt der Leerlauf-Durchgang die Parakeet-Vorschau, sind Suchtreffer, die der Nutzer gestern gefunden hat, heute weg. Umgekehrt verschluckt Parakeet Passagen (ls_clean 28,7 % ohne Wächter), und in französischer Spontansprache driftet es ins Englische (long_fr_summre 79,9 % WER).

**Why it happens:**
"Besser" wird an der Gesamt-WER festgemacht, nicht an der Abdeckung je Zeitfenster; ein Austausch prüft nicht, ob einzelne Fenster schlechter geworden sind.

**How to avoid:**
- Ersetzen nur über ROVER mit den Spike-3-Parametern (0,15 / 0,2 / 0,6), nie als blinder Austausch.
- Abdeckungs-Wächter je VAD-Fenster: hat das neue Transkript in einem Fenster deutlich weniger Wörter als die Vorschau (Schwelle am Release-Gate kalibrieren), Vorschau-Wörter für dieses Fenster behalten oder Fenster einzeln nachrechnen.
- Schluck-Wächter für Parakeet immer an (Segment ab 1 s mit weniger als 1 Wort/s neu dekodieren).
- Release-Gate-Kennzahl ergänzen: "Wörter, die in der Vorschau korrekt waren und im Endtranskript fehlen", getrennt ausweisen.

**Warning signs:**
Deletion-Anteil an der WER steigt nach dem Qualitätsdurchgang; Nutzerberichte "Treffer verschwunden"; Fenster mit 0 Wörtern im Endtranskript, die in der Vorschau Text hatten.

**Phase to address:** P-QUAL; Kennzahl in P-REL (Release-Gate).

---

### Pitfall 8: Halluzinations-Abfangregel löscht echte Aufnahmen in nicht unterstützten Sprachen still

**What goes wrong:**
Die Regel "Sprache außerhalb der Instanz-Sprachen mit Sicherheit unter 0,5 verwerfen, fremde Schrift verwerfen" trifft nicht nur Café-Halluzinationen ("감사합니다"), sondern auch echte türkische, arabische, ukrainische oder russische Aufnahmen, wie sie in Schulen und Behörden üblich sind. Die Datei steht dann als "fertig" mit leerem Transkript da. Parakeet kennt nur 25 EU-Sprachen und schreibt bei anderen Sprachen sinnlosen lateinischen Text, den die Regel nicht als fremde Schrift erkennt.

**Why it happens:**
Spike 3 hat die Regel auf Stille, Rauschen, Musik und Café gemessen, nicht auf echter Sprache außerhalb DE/EN/FR.

**How to avoid:**
- Die Regel nur auf Einzelsegmente anwenden, nie auf die ganze Datei; erkennt Whisper für die Datei mit hoher Sicherheit eine nicht unterstützte Sprache, Endzustand `skipped` mit Grund "Sprache nicht unterstützt: tr", sichtbar im Admin-Status.
- Release-Gate um einen Negativsatz mit echter Sprache außerhalb der Instanz-Sprachen erweitern (FLEURS hat tr, ar, uk unter CC-BY-4.0): Erwartung "ausgewiesen", nicht "leer fertig".
- Verworfene Segmente zählen und je Datei speichern; ein Anteil über einer Schwelle ist ein Warnsignal.

**Warning signs:**
Dateien mit Dauer über 1 min und 0 Wörtern im Zustand "fertig"; hoher Anteil verworfener Segmente in einer Datei.

**Phase to address:** P-PREV (Regel je Segment, Zustände), P-REL (Gate-Satz).

---

### Pitfall 9: ffmpeg als Angriffsfläche und als Stolperstein bei realen Dateien

**What goes wrong:**
- Sicherheit: Nutzer laden beliebige Dateien hoch. Eine `.m3u8`, `.ffconcat` oder ein präparierter Container kann ffmpeg dazu bringen, lokale Dateien (`file:`) oder Netzadressen (`http:`) zu lesen: Daten aus dem Container oder SSRF ins interne Netz. Das widerspricht direkt "kein Inhalt verlässt den Server".
- MP4/MOV mit `moov`-Atom am Dateiende (Standard bei vielen Kameras und Handys) sind über eine Pipe nicht lesbar ("moov atom not found"); der Spike-Vorschlag "per Pipe streamen" gilt nur für den Ausgang, nicht für den Eingang.
- Mehrere Tonspuren: ffmpeg nimmt ohne `-map` die "beste" Spur, oft Kommentar, Dolmetsch-Spur oder Stereo-Musik statt Originalton; Videos ohne Tonspur (Bildschirmaufnahmen) und DRM-geschützte Dateien (`.m4p`, verschlüsselte Container) enden als kryptischer Fehler.
- Startversatz: Container mit `start_time` größer 0 oder MP4-Edit-Lists (iPhone) verschieben die Zeitachse; Zeitmarken stimmen dann im Player um Sekunden nicht.
- Dateien, die noch hochgeladen werden (`.part`, Chunked Upload), werden halb transkribiert.

**Why it happens:**
Spike 1 hat ffmpeg nur mit einem sauberen MP4 gemessen (0,46 s für 10 min).

**How to avoid:**
- Immer `ffprobe` zuerst, mit `-protocol_whitelist file,pipe` und einer Demuxer-Positivliste (`-format_whitelist` bzw. `-f` aus der ffprobe-Erkennung, Playlists und Concat ablehnen); ffmpeg ohne Netz im Container laufen lassen, Kindprozess mit Zeit- und Speichergrenze.
- Eingang als Datei auf Platte (nicht Pipe), Ausgang `-f s16le -` per Pipe in den VAD-Puffer; Temp-Platz vorab prüfen.
- Spurwahl ausdrücklich: Standard-Spur laut Disposition, sonst erste Spur mit Sprachtag aus den Instanz-Sprachen, sonst erste; gewählte Spur im Transkript speichern.
- Zeitachse auf den Player beziehen: `start_time` aus ffprobe auslesen und gegen das Verhalten des Nextcloud-Players prüfen (Testdatei mit Edit-List).
- Eigene Endzustände: `no_audio_stream`, `encrypted`, `unsupported_codec`, `truncated`; Dateien erst bearbeiten, wenn ETag und Größe über ein Ruhefenster stabil sind.
- Medienkorpus für CI per Skript erzeugen: VFR, Edit-List, moov am Ende, 2 Tonspuren, ohne Ton, 0-Byte, abgeschnitten, Opus/WebM (Talk-Aufnahmen), AMR, 8-kHz-Telefonaudio, 10-h-Datei (synthetisch).

**Warning signs:**
ffmpeg-Fehler im Log mit Inhalt statt Grundcode; Zeitmarken einer Handy-Datei konstant verschoben; Kommentarspur im Transkript; ffprobe öffnet Netzverbindungen.

**Phase to address:** P-MEDIA (vor P-PREV), Sicherheitsfälle zusätzlich als Negativtests in P-REL.

---

### Pitfall 10: Speicherwachstum bei langen Dateien

**What goes wrong:**
`WhisperModel.transcribe(pfad)` dekodiert die ganze Datei als float32 in den Speicher (60 min rund 230 MB, 10 h rund 2,3 GB) und hält zusätzlich Merkmale; Spike 3 maß 3,4 GB bei einer 41-min-Datei ohne Stückelung statt 1,9 GB. Über viele Dateien wächst der RSS eines langlebigen Prozesses zusätzlich durch Heap-Fragmentierung (glibc-Arenen je Thread) und ONNX-Runtime-Arenen bei wechselnden Eingabeformen, ohne dass ein Leck im Python-Code sichtbar ist.

**Why it happens:**
Bibliotheks-Komfort-APIs laden ganz; Messungen im Spike liefen je Lauf in einem frischen Prozess, also wurde Wachstum über Dateien nie gesehen.

**How to avoid:**
- Audio immer gestreamt aus ffmpeg lesen; faster-whisper nur Stücke von etwa 10 min (Spike-3-Vorgabe) an VAD-Pausen geschnitten übergeben, mit Überlappung und Duplikat-Bereinigung an der Naht.
- Rechen-Kindprozess nach N Dateien oder X Audiostunden beenden und neu starten; `MALLOC_ARENA_MAX=2` im Image; ONNX `enable_cpu_mem_arena` messen.
- Dauertest: 50 Dateien hintereinander, RSS nach jeder Datei protokollieren; Abnahmekriterium "Rückkehr zur Grundlast" (Findling-Messregel MEM-02), nicht nur Spitze.

**Warning signs:**
RSS nach jeder Datei höher als vorher; RAM-Spitze skaliert mit Dateidauer statt mit Stückgröße.

**Phase to address:** P-RES (Prozessmodell, Recycling), P-QUAL (Stückelung faster-whisper), Dauertest in P-REL.

---

### Pitfall 11: Vorschau-Transkript wird nicht atomar ersetzt, oder ein veraltetes Ergebnis überschreibt ein neues

**What goes wrong:**
Beim Ersetzen werden alte Zeilen gelöscht und neue eingefügt: in der Lücke findet die Suche nichts oder doppelte Treffer. Schlimmer: Während turbo eine Stunde rechnet, lädt der Nutzer eine neue Version hoch; Parakeet liefert die neue Vorschau, danach überschreibt das turbo-Ergebnis der alten Version die neue Vorschau. Index und Datei passen nicht mehr zusammen.

**Why it happens:**
Kein Versionsbezug am Ergebnis; Schreiben in mehreren Schritten.

**How to avoid:**
- Jedes Transkript trägt Inhalts-Fingerabdruck, ETag, Engine, Modell-sha256 und Konfigurationsversion.
- Ersetzen in einer Transaktion (oder Index-Segment-Tausch wie Findlings atomarer Umbau) mit bedingtem Schreiben: nur wenn der Fingerabdruck noch dem aktuellen Dateistand entspricht, sonst Ergebnis verwerfen.
- Test: Suche läuft in Schleife während des Tauschs, darf nie 0 oder doppelt liefern.

**Warning signs:**
Trefferzahl schwankt kurzzeitig auf 0; Transkript passt nicht zur aktuellen Dateilänge; Zeitmarken jenseits des Dateiendes.

**Phase to address:** P-ARCH (Datenmodell mit Provenienz), P-QUAL (Tausch).

---

### Pitfall 12: Neuberechnungs-Stürme nach Verschieben, Kopieren, Tag-Änderungen und Profilwechsel

**What goes wrong:**
- Verschieben zwischen Storages (Home in Gruppenordner, auf SMB, in einen anderen Mount) ist für Nextcloud Kopieren plus Löschen: neue Datei-ID, also volle Neutranskription.
- Ändern von ID3/MP4-Tags (Musik- oder Podcast-Verwaltung) ändert Datei-Hash und ETag, aber keinen Ton.
- Admin wechselt das Profil oder ein Modell-Update erscheint: ohne Provenienz wird alles neu eingereiht, Tage Volllast.
- Reconcile läuft während des Erst-Crawls und reiht alle noch nicht gecrawlten Dateien ein zweites Mal ein (Findling "crawl-unfinished-zweitlauf": Ruhe-Tor maß nur die Vorratslänge, nicht den Crawl-Zustand).
- `occ files:scan --all`, Wiederherstellung aus Backup oder geänderte Mount-Konfiguration erzeugen neue IDs für ganze Speicher.

**Why it happens:**
Schlüssel ist Datei-ID oder Datei-Hash; Re-Analyse ist nicht gezielt möglich.

**How to avoid:**
- Ergebnis-Schlüssel ist ein Fingerabdruck des dekodierten Tons (PCM-Hash nach Resampling; Dekodieren kostet etwa 0,5 s je 10 min, verglichen mit Minuten für ASR), Datei-IDs verweisen darauf. Neue Datei-ID mit bekanntem Fingerabdruck übernimmt das Transkript ohne Rechnen.
- Provenienz je Transkript (Pitfall 11) erlaubt gezieltes Nachrechnen ("nur DE-Dateien, die noch nicht large-v3 haben") mit niedriger Priorität und Admin-Anzeige "x Dateien warten auf das neue Profil".
- Reconcile mit Findlings Crawl-Flag-Tor ("reconcile stands down, the crawl is unfinished").
- Löschen von Transkripten verzögert (Karenz von z. B. 24 h nach dem letzten Verweis), damit Kopieren plus Löschen das Ergebnis nicht wegwirft; DSGVO-Pflicht bleibt mit kurzer, dokumentierter Frist erfüllt (Pitfall 13).

**Warning signs:**
Warteschlange springt nach einer Ordner-Umstrukturierung auf den Gesamtbestand; viele Durchgänge mit Ergebnis "unverändert"; CPU-Last nach jedem Musik-Tagging.

**Phase to address:** P-ARCH (Schlüssel, Provenienz), P-WALK (Reconcile-Tor), P-LIFE (Karenz).

---

### Pitfall 13: Transkripte überleben die Datei (DSGVO)

**What goes wrong:**
Transkripte sind personenbezogene Daten, oft besonders sensible (Gesundheit, Personal, Beratung). Typische Lecks:
- Löschen in den Papierkorb ist kein Löschen; das endgültige Löschen durch den Ablauf-Job des Papierkorbs löst nicht unbedingt das Ereignis aus, auf das die App hört [LOW, Verhalten je Version prüfen].
- Wiederherstellen einer alten Version ändert den Inhalt, das alte Transkript bleibt.
- Gelöschte Nutzer, gelöschte Gruppenordner, ausgehängte externe Speicher hinterlassen Waisen.
- Temporäre WAV- und Videodateien bleiben nach OOM-Abbruch im Container liegen; Logs enthalten Dateinamen oder Textstücke; das Daten-Volume landet so im Backup.

**Why it happens:**
Löschung wird nur über Ereignisse gebaut; Ereignisse fehlen in Randfällen, und es gibt keinen Abgleich.

**How to avoid:**
- Zweigleisig: Ereignis (Löschen, Verschieben in den Papierkorb, Versionswiederherstellung) plus periodischer Abgleich gegen `oc_filecache`, der Transkripte ohne lebenden Verweis nach der Karenz endgültig löscht.
- Papierkorb: Treffer sofort verbergen (Suchprovider findet die Datei nicht mehr im Nutzerordner), Transkript bis zur Wiederherstellung oder zum endgültigen Löschen behalten; nach Wiederherstellung Fingerabdruck prüfen.
- Temp-Verzeichnis beim Start leeren, Kindprozess räumt in `finally`; Logs nur Zustandswörter und IDs (Findling-Regel).
- Löschfrist und Abgleichtakt in README und Admin-Seite dreisprachig dokumentieren (Behörden fragen danach).
- CI-Negativtest: Datei löschen, Papierkorb leeren, Nutzer löschen, Version wiederherstellen; danach 0 Zeilen und 0 Index-Dokumente zu diesem Inhalt.

**Warning signs:**
Anzahl Transkripte größer als Anzahl lebender Mediendateien; wachsendes Temp-Verzeichnis; Dateinamen in `docker logs`.

**Phase to address:** P-LIFE (eigene Phase, nicht als Rest von P-SEARCH).

---

### Pitfall 14: Inferenz blockiert Status, Admin-Seite und Nextcloud selbst (Findling #19)

**What goes wrong:**
Transkription läuft im FastAPI-Prozess oder mit normaler Priorität. Die Status-Route antwortet nicht innerhalb der Frist der Admin-Seite, AppAPI-Heartbeat und HaRP melden die App als tot, PHP-FPM und Datenbank auf demselben Rechner werden langsam. Bei Findling geschah genau das mit Tesseract.

**Why it happens:**
CPU-gebundene Arbeit im Event-Loop oder in Threads mit GIL-freien nativen Bibliotheken, die alle Kerne belegen.

**How to avoid:**
Inferenz nur in Kindprozessen mit `os.nice(19)` (und `ionice` idle für ffmpeg), Threads auf Quote minus 1, nie im Web-Prozess. "Leerlauf" für den Qualitätsdurchgang an Host-Last messen (Load, Nextcloud-Anfragen), nicht an der eigenen Warteschlange. Status-Route liest nur gecachte Zustände.

**Warning signs:**
Admin-Seite meldet "Backend nicht erreichbar" nur während der Transkription; Nextcloud-Web wird träge, sobald turbo läuft.

**Phase to address:** P-RES.

---

## Moderate Pitfalls

### Pitfall 15: Zeitmarken driften zwischen Engines und an Stücknähten

**What goes wrong:**
Parakeet liefert Token-Zeiten im 0,08-s-Raster, nie mehr als 0,09 s zu früh (Spike 2); Whisper setzt Wortanfänge nach Pausen bis zu 1 s zu früh. ROVER übernimmt je Wort die Zeit des gewählten Systems: dabei entstehen nicht monotone Zeitfolgen, die SRT/VTT verletzen (Pitfall 18) und Sprungmarken falsch setzen. An den 10-min-Nähten von faster-whisper entstehen doppelte oder fehlende Wörter und Versatz, wenn der Stückversatz falsch addiert wird. Bei Parakeet muss das Polster (0,5 s) abgezogen und der Fensterstart addiert werden.

**Prevention:**
Whisper-Wortanfänge auf den VAD-Sprachbeginn klemmen (Spike-2-Empfehlung); nach ROVER Zeitfolge monoton erzwingen; Zeitmarken-Test aus Spike 2 (Wortbeginn im richtigen Clip, Toleranz 0,3 s) als festen Gate-Teil für jede Engine und für das ROVER-Ergebnis; Naht-Test mit einem Satz genau über der 10-min-Grenze. Sprungmarke in der Suche 1 bis 2 s vor dem Wort setzen.
**Phase:** P-PREV (Parakeet-Offsets), P-QUAL (ROVER, Nähte), P-SUB.

### Pitfall 16: VAD-Randfälle jenseits der 0,1 s

**What goes wrong:**
Neben Mini-Segmenten (Absturz): Dauersprache ohne Pausen (schnelle Redner, Lesungen mit Musikbett) wird bei 25 s hart geschnitten, Wörter an der Schnittstelle gehen verloren; Silero hält Gesang und Stimmengewirr für Sprache (Café: Whisper erzeugt fremde Schrift, Spike 3); VAD-Zustand wird zwischen Dateien nicht zurückgesetzt; 0-Sekunden-Dateien und Dateien nur aus Stille liefern 0 Segmente und werden als Fehler statt als "keine Sprache" gemeldet. Rohe VAD-Schnipsel ohne Kontext driften die Sprache (DE-WER 10 % auf 17 %, Spike 1).

**Prevention:**
Fenster-Zusammenfassung bis 25 s plus 0,4 s Kontext plus 0,5 s Polster als Pflicht mit Regressionstest; harte 25-s-Schnitte mit Überlappung und Wort-Bereinigung; VAD-Objekt je Datei neu; Endzustand `no_speech` als Erfolg mit Hinweis; VAD nicht abschaltbar (Projektentscheid), auch nicht über eine versteckte Umgebungsvariable.
**Phase:** P-PREV.

### Pitfall 17: Zahlen- und Schreibweisen-Unterschiede zwischen Engines brechen die Suche

**What goes wrong:**
Whisper schreibt "2024", "15 %", "Dr."; Parakeet teils ausgeschrieben, andere Groß- und Kleinschreibung, Interpunktion. Die Suche nach "2024" findet die Vorschau nicht, nach dem Austausch plötzlich doch, oder umgekehrt. Spike 2 brauchte num2words schon für eine faire Zweitmetrik: die Unterschiede sind real.

**Prevention:**
Im Index beide Formen ableiten (Ziffern zu Wörtern und zurück für DE/EN/FR), Kleinschreibung und Interpunktion normalisieren, deutsche Komposita mit Findlings `split_compound`-Ansatz; angezeigter Text bleibt Original. Suchfall-Tests "Zahl als Ziffer und als Wort" je Sprache.
**Phase:** P-SEARCH.

### Pitfall 18: SRT und VTT verletzen die Formate, BITV wird überbehauptet

**What goes wrong:**
- VTT: fehlender `WEBVTT`-Kopf, Komma statt Punkt bei Millisekunden, roher `&` oder `<` im Text (muss `&amp;` / `&lt;` sein), `-->` im Text verboten, Startzeiten nicht aufsteigend, Ende nicht größer als Start, Datei nicht UTF-8 [HIGH, W3C WebVTT].
- SRT: Komma als Millisekunden-Trenner, Zählung ab 1, Leerzeile zwischen Blöcken; ältere Windows-Player zeigen Umlaute ohne UTF-8-BOM falsch [MEDIUM].
- Lesbarkeit: Wortstrom statt Untertitel (Zeilen über 42 Zeichen, mehr als 2 Zeilen, Einblendungen unter 1 s oder über 7 s).
- BITV/WCAG 1.2.2: Untertitel müssen Sprache und für das Verständnis nötige Nicht-Sprach-Information enthalten, Auslassen von Dialog ist Fehler F8 [HIGH, W3C Understanding 1.2.2]. Automatische Transkripte ohne Prüfung und ohne Sprecherkennung (Diarisierung ist v2) erfüllen das nicht vollständig.

**Prevention:**
Generator mit Validierung (Gegenprobe mit einem unabhängigen Parser, nicht mit dem eigenen Code, Findling-Regel) und Property-Tests (monoton, Ende größer Start, Escaping); Segmentierung an Satzgrenzen und Pausen mit Längenregeln; Text in Store und README: "Untertitel-Entwurf als Grundlage für barrierefreie Untertitel, vor Veröffentlichung prüfen", nie "BITV-konform".
**Phase:** P-SUB; Wortlaut-Prüfung in P-REL.

### Pitfall 19: Modelldownload in Offline- und Air-Gap-Instanzen

**What goes wrong:**
Behörden und Schulen betreiben Nextcloud oft ohne Internet. Lädt der Container beim ersten Start Parakeet (465 MiB), turbo und large-v3 von Hugging Face oder GitHub, hängt die Initialisierung, AppAPI meldet einen Fehler oder einen ewigen Fortschritt. Weitere Fallen: Download bei jedem Container-Update neu, weil nicht im persistenten Volume; abgebrochene Downloads ohne Fortsetzen; `huggingface_hub` sendet Telemetrie und User-Agent (widerspricht "keine Telemetrie"); `WhisperModel("large-v3-turbo")` lädt ungeprüft die jeweils neueste Revision (Lieferkette); large-v3 im float16-Format erzeugt beim int8-Umrechnen eine RAM-Spitze beim Laden (Spike 2: 1,9 GB Spitze bei Parakeet-ähnlichem Effekt für turbo, Vorab-Konvertierung empfohlen).

**Prevention:**
Vorschau-Modell (Parakeet + Silero) ins Image legen, damit die App ohne Netz sofort arbeitet; größere Modelle nachladen in das persistente App-Volume mit fester Revision und sha256 (Werte aus dem Release-Gate), Fortsetzen, `HF_HUB_OFFLINE`/`HF_HUB_DISABLE_TELEMETRY=1`, eigene Spiegel-URL als Admin-Einstellung und dokumentierter Weg "Modelle per Hand in den Ordner legen"; Modelle vorab nach int8 konvertiert beziehen. Admin-Status zeigt je Modell: vorhanden, lädt (Prozent), fehlt (Grund). Ohne Qualitätsmodell läuft Schnell-Profil, nicht gar nichts.
**Phase:** P-MODEL; Air-Gap-Test (Container ohne Netz) in P-REL.

### Pitfall 20: CC-BY-4.0-Namensnennung und weitere Lizenzpflichten vergessen

**What goes wrong:**
Parakeet-TDT-0.6B-v3 ist CC-BY-4.0: Namensnennung NVIDIA, Lizenz-Link und Hinweis auf Änderungen (int8-ONNX-Export durch sherpa-onnx ist eine Bearbeitung) sind Pflicht, sobald das Modell im Image mitgeliefert wird. Whisper-Gewichte (MIT) und Silero (MIT) verlangen den Lizenztext bei Weitergabe; ffmpeg im Image muss ein LGPL-Build sein (BtbN `lgpl`, nicht Debian- oder gyan.dev-GPL-Build), mit Lizenz und Quellverweis. Gate-Daten (Metamorphosis-Referenz, ns_music, CC-BY-SA-Teile) gehören nicht ins Repo (Spike 3).

**Prevention:**
Namensnennung an vier Stellen gleichlautend und per Gate gehalten (README DE/EN/FR, info.xml-Beschreibung, Admin-Seite "Über", `LICENSES/` plus `REUSE.toml` und Hinweisdatei im Image); Image-Build prüft, dass ffmpeg `--enable-gpl` nicht enthält (`ffmpeg -buildconf`); CI-Gate verbietet Audio-/Referenzdateien des Gates im Repo.
**Phase:** P-MODEL; Gate-Prüfung in P-REL.

### Pitfall 21: Profil-Vorwahl nach RAM und Kernzahl statt nach gemessener Geschwindigkeit

**What goes wrong:**
Kernzahl sagt wenig: Pi 5 (4x A76, Drosselung ohne aktive Kühlung), N100, NAS-Celerons ohne AVX und Hybrid-CPUs mit E-Kernen unterscheiden sich um Faktoren. Auf langsamer Hardware wird der Qualitätsdurchgang nie fertig (turbo RTF 0,47 auf dem i5; auf ARM unbekannt), die Leerlauf-Warteschlange wächst unbegrenzt, und der Admin sieht "Ausgewogen" ohne Hinweis, dass es nie ankommt. CTranslate2 liefert aarch64-Wheels, nutzt auf ARM aber andere Rechen-Backends (Ruy/OpenBLAS statt oneDNN/MKL); belastbare ARM-Zahlen gibt es nicht [MEDIUM für Wheels, LOW für Geschwindigkeit].

**Prevention:**
Beim ersten Start kurzer Eigentest mit eingebetteter Testdatei (30 s Audio je Engine), gemessene RTF und freier cgroup-RAM bestimmen die Vorwahl; Profil nur anbieten, wenn die geschätzte Abarbeitungszeit des Bestands endlich bleibt (Rückstand mal RTF gegen Zufluss), sonst mit Begründung ausgrauen. Admin-Status zeigt "Qualitätsdurchgang: x Stunden Rückstand". Pi 5 und N100 vor Release echt messen (Projektvorgabe), dazu ein Rechner ohne AVX2, falls verfügbar.
**Phase:** P-RES (Eigentest), P-REL (echte Messung).

### Pitfall 22: Sprachwechsel und Spracherkennung auf den ersten 30 Sekunden

**What goes wrong:**
Whisper bestimmt die Sprache aus dem Anfang der Datei. Beginnt eine Aufnahme mit englischem Intro, Musik oder Smalltalk, wird die ganze Sitzung in der falschen Sprache dekodiert oder übersetzt. Spike 3: Whisper versagt bei Sprachwechsel mit 70 % WER (mixlang), Parakeet wechselt in FR-Spontansprache ins Englische. Fenster-weise Nachrechnung mit eigener Erkennung senkt das auf 35 %, verursacht aber Mehrkosten und neue Nähte.

**Prevention:**
Spracherkennung je VAD-Fenster (textbasiert auf dem Transkript oder Whisper-Erkennung je Fenster), nur Fenster mit abweichender Sprache und hoher Sicherheit nachrechnen; Ergebnis je Fenster mit Konfidenz vergleichen, besseres behalten; Sprache je Fenster speichern (für Stemming im Index und für den `lang`-Bezug der Untertitel). mixlang-Satz im Release-Gate halten.
**Phase:** P-QUAL; Spracherkennung je Fenster schon in P-PREV vorbereiten.

### Pitfall 23: Unified Search wird bei großen Beständen langsam oder liefert Rauschen

**What goes wrong:**
Jede Eingabe in der Suchleiste ruft alle Provider; ein Provider, der pro Anfrage in den Container proxyt, Treffer einzeln rechteprüft und Snippets aus großen Transkripten schneidet, belegt PHP-Worker und kommt nach den anderen Providern oder gar nicht. Eine 3-Stunden-Sitzung mit 200 Treffern auf "und" überschwemmt die Liste. Erste Suche nach Container-Neustart antwortete bei Findling lexikalisch 0 Treffer (Kaltstart-Fix 1.3.0).

**Prevention:**
Echter Volltextindex im Container (FTS5 oder tantivy wie Findling), nicht SQL-LIKE; Treffer je Datei bündeln (eine Zeile je Datei mit bester Stelle und Zahl weiterer Stellen); Mindestlänge der Anfrage; Zeitbudget je Anfrage mit Teilergebnis; Kaltstart-Messung mit Trefferpflicht (Findling-Regel); Lasttest mit synthetischem Bestand (z. B. 10 000 Stunden Transkript) vor Release.
**Phase:** P-SEARCH, Messung in P-REL.

### Pitfall 24: Sprung an die Zeitstelle funktioniert im Nextcloud-Player nicht

**What goes wrong:**
"Klick öffnet Datei an der Stelle" setzt voraus, dass Viewer/Files einen Startzeitpunkt aus der URL übernehmen. Ob das in NC 33 bis 35 ohne eigenen Frontend-Code geht, ist nicht belegt [LOW]. Ohne das öffnet der Klick die Datei bei 0:00, und das Kernversprechen ist halb erfüllt.

**Prevention:**
Früh als Spike in P-SEARCH prüfen (Viewer-Quelltext, Media-Fragment `#t=`), sonst kleines Viewer-Skript in der PHP-Begleit-App einplanen; Abnahme per Playwright in drei Breiten hell/dunkel.
**Phase:** P-SEARCH (frühe Klärung, ggf. eigene Teilphase).

---

## Minor Pitfalls

### Pitfall 25: i18n-Gleichstand DE/EN/FR bricht an Rändern

**What goes wrong:**
Gründe für übersprungene und fehlgeschlagene Dateien kommen als freier englischer Text aus dem Container; "Deutsch (Sie)" bzw. `de_DE` fällt auf Englisch zurück (Findling v1.1); Pluralformen fehlen; französische Typografie (geschütztes Leerzeichen vor `:`, `?`, `!`) fehlt; Store-Texte, README und Katalog laufen auseinander; ASCII-Ersatz statt Umlauten in Katalogen.
**Prevention:**
Container liefert nur Schlüssel (`no_audio_stream`), PHP/l10n übersetzt; Kataloge `de` und `de_DE` gleich; Katalog-Gates wie Findling (gleiche Schlüsselmenge in allen Sprachen, keine englischen Quellsätze im FR/DE-Katalog, Umlaut-Audit); FR-Muttersprachler-Abnahme als blockierender Checkpoint; Volltest aller Meldungen DE/EN/FR vor Store-Release.
**Phase:** jede Phase mit UI-Text, Abschluss in P-REL.

### Pitfall 26: Dateinamen und Pfade mit Sonderzeichen

**What goes wrong:**
Emojis, kombinierte Umlaute (NFD von macOS-Clients), sehr lange Pfade und Surrogate in Metadaten führen zu Fehlern bei WebDAV-Pfaden, Logs oder Index (Findling #15, #44).
**Prevention:**
Ausschließlich über Datei-ID laden, nie über zusammengesetzte Pfade; Texte und Titel vor dem Index säubern; Testkorpus mit Emoji im Ordnernamen (Fall aus Findling #15) und NFD-Namen.
**Phase:** P-WALK, P-MEDIA.

### Pitfall 27: Verbindungsverlust nach Neustart und Zertifikatswechsel

**What goes wrong:**
Nach Host-Neustart oder HaRP-Netz-Neuanlage verliert der Container die Verbindung (Findling #33: Zertifikate für uid 1000 nicht lesbar, frpc "session shutdown"); laufende Transkriptionen gehen verloren, wenn das Ergebnis nur im Speicher liegt.
**Prevention:**
Findlings Zert-Rotation und Wiederverbindung übernehmen; Ergebnisse stückweise (je Fenster) persistieren, damit eine 3-h-Datei nach Abbruch nicht von vorn beginnt.
**Phase:** P-RES (Persistenz), Skeleton-Übernahme in P-ARCH.

### Pitfall 28: Hintergrund-Erkennung hängt am PHP-Cron

**What goes wrong:**
Neue Dateien werden erst beim nächsten Cron-Lauf gefunden; bei AJAX-Cron oder seltenem Cron bleibt die App scheinbar stehen (Findling #36).
**Prevention:**
Ereignisse für neue Dateien plus selbst angestoßene Crawl-Scheiben wie Findling seit 1.2; Admin-Status warnt bei AJAX-Cron.
**Phase:** P-WALK.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Datei-ID als einziger Transkript-Schlüssel | Einfaches Schema | Stürme bei Verschieben/Kopieren, N-fach-Rechnen auf Nutzer-Mounts | Nie (Fingerabdruck ab P-ARCH) |
| Transkript ohne Provenienz (Engine, Modell-sha, Konfig) | Weniger Felder | Kein gezieltes Nachrechnen, Modell-Update erzwingt Vollneulauf | Nie |
| `transcribe(pfad)` mit ganzer Datei | Wenig Code | RAM wächst mit Dateidauer, OOM bei langen Sitzungen | Nur im Spike |
| Inferenz im Web-Prozess oder Thread | Kein IPC | Status-Ausfälle, kein OOM-Schutz, Fragmentierung | Nie |
| Rechte im Index | Schnelle Suche | Datenleck nach Rechteentzug | Nie |
| psutil/meminfo für RAM-Wächter | Plattformgleich | Falsche Werte im Container | Nur als Rückfall ohne cgroup |
| Modelle ungepinnt von HF laden | Kein Verwaltungsaufwand | Lieferkette, Telemetrie, Offline-Ausfall | Nie |
| Fehlertexte aus dem Container direkt anzeigen | Schnell | i18n-Bruch, Datenleck über Pfade | Nie |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| AppAPI/HaRP | Unified Search aus der ExApp erwarten | PHP-Begleit-App für Provider, Events, Rechte |
| groupfolders | Lese-Pfad nur im CLI getestet | Echter HTTP-Claim-Pfad mit ACL `-share` in CI (Findling #14) |
| files_external | Jeder Mount wie Home behandelt | Nutzer-Mounts gruppieren, Sitzungs-Anmeldedaten ausweisen, Mount-Ausschluss |
| files_trashbin / files_versions | Nur auf Löschereignis reagieren | Ereignis plus Abgleich gegen Dateicache, Karenz, Wiederherstellung prüfen |
| webhook_listeners (falls genutzt) | `NodeDeletedEvent` für ID nutzen | `BeforeNodeDeletedEvent`, da danach nur der Pfad bleibt |
| ffmpeg | Pipe-Eingang, keine Protokoll-Positivliste | Datei-Eingang, `-protocol_whitelist file,pipe`, Demuxer-Positivliste, kein Netz |
| faster-whisper | Automatischer Modelldownload, ganze Datei | Gepinnte Revision mit sha256, Stücke ab etwa 10 min |
| sherpa-onnx | Segmente beliebiger Länge | Mindestlänge 0,5 s auffüllen oder verwerfen |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Leerlauf-Warteschlange wächst schneller als abgearbeitet | Rückstand steigt monoton | Rückstands-Schätzung, Profil-Vorwahl nach Eigentest | Archive über einige 100 h auf N100/Pi |
| Rechteprüfung je Treffer ohne Überabruf | Leere Ergebnisseiten | Top-k mit Nachladen, Bündelung je Datei | Ab einigen 1000 Transkripten mit geteilten Ordnern |
| Threads gleich Host-Kerne | Nextcloud träge, Drosselung | Threads aus cgroup-Quote minus 1, nice 19 | Sofort auf kleinen Hosts |
| Heap-Fragmentierung im langlebigen Prozess | RSS wächst je Datei | Kindprozess-Recycling, `MALLOC_ARENA_MAX=2` | Nach Dutzenden Dateien |
| Neuberechnung nach Profilwechsel | Tage Volllast | Gezielt über Provenienz, niedrige Priorität | Bei jedem Profil- oder Modellwechsel |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| ffmpeg liest Playlists/Concat mit `file:`/`http:` | Lokale Dateien aus dem Container, SSRF | Protokoll- und Demuxer-Positivliste, Container-Netz nur zu Nextcloud |
| Rechte im Container zwischengespeichert | Transkript-Inhalt nach Rechteentzug sichtbar | Prüfung zur Abfragezeit im PHP-Provider |
| Dedup über Fingerabdruck vererbt Rechte | Nutzer sieht Treffer aus Datei, die er nicht hat | Rechte je Datei-ID, Fingerabdruck nur für Rechenersparnis |
| Transkript-Text oder Pfade in Logs | Personenbezogene Daten in Log-Sammlern | Nur Zustandswörter und IDs loggen |
| Ungeprüfte Modell-Downloads | Manipulierte Gewichte | Feste Revision, sha256 aus Release-Gate |
| Telemetrie durch Bibliotheken | Verstoß gegen Owner-Regel | `HF_HUB_DISABLE_TELEMETRY=1`, Container ohne Internet testen |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Leeres Transkript als "fertig" | Nutzer hält Datei für durchsucht | Eigene Zustände: keine Sprache, Sprache nicht unterstützt, keine Tonspur |
| Treffer verschwinden nach Qualitätsdurchgang | Vertrauensverlust | Abdeckungs-Wächter je Fenster (Pitfall 7) |
| Fortschritt zählt Nutzer-Mounts mehrfach | "7 %" trotz fertig (Findling #25) | Gruppierte Zählung |
| Profil gewählt, das nie fertig wird | Falsche Erwartung | Rückstand in Stunden anzeigen, unsichere Profile ausgrauen mit Grund |
| "BITV-konform" im Store-Text | Rechtliche Fehlannahme bei Behörden | "Untertitel-Entwurf, vor Veröffentlichung prüfen" |

## "Looks Done But Isn't" Checklist

- [ ] **Suche:** Treffer verschwinden nach Freigabe-Entzug, Gruppen-Austritt, ACL `-read`, Papierkorb sofort (CI-Negativtest)
- [ ] **Gruppenordner:** ACL `+read -share` im echten HTTP-Pfad lesbar
- [ ] **Externe Speicher:** Nutzer-Mount mit 30 Nutzern wird einmal gerechnet, einmal gezählt
- [ ] **Löschen:** Nach Papierkorb leeren, Nutzer löschen, Version wiederherstellen 0 Transkript-Zeilen und 0 Index-Dokumente zu altem Inhalt
- [ ] **Austausch:** Suche liefert während des Tauschs nie 0 oder doppelt; veraltetes Ergebnis überschreibt keine neuere Vorschau
- [ ] **Robustheit:** Medienkorpus (moov am Ende, 2 Tonspuren, ohne Ton, verschlüsselt, abgeschnitten, 0 Byte, 10 h, Playlist) endet je Datei in benanntem Zustand, keine hängt
- [ ] **OOM:** Mit `--memory=2g` überlebt die Nextcloud-Datenbank, die Datei landet mit Grund in der Liste
- [ ] **Offline:** Container ohne Internet transkribiert mit Vorschau-Modell, Admin sieht fehlende Modelle mit Grund
- [ ] **Untertitel:** VTT/SRT besteht unabhängigen Parser; Escaping, Monotonie, Ende größer Start
- [ ] **Lizenzen:** NVIDIA-Namensnennung an allen vier Stellen gleichlautend; ffmpeg-Build ohne `--enable-gpl`
- [ ] **i18n:** Alle Zustände und Gründe in DE, `de_DE`, EN, FR; Umlaut-Audit; FR-Muttersprachler abgenommen
- [ ] **Hardware:** Pi 5 und N100 echt gemessen, Rückstands-Anzeige plausibel

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Rechte im Index gespeichert | HIGH | Schema-Migration, Provider neu, Sicherheitshinweis an Nutzer |
| Datei-ID als Schlüssel | HIGH | Fingerabdruck nachträglich je Datei berechnen (Dekodieren des Bestands), Migration |
| Keine Provenienz | MEDIUM | Bestand als "unbekannte Herkunft" markieren, gezielter Neulauf im Leerlauf |
| Hängende Jobs | LOW | Lease-Ablauf einführen, Altzeilen per Migration zurücksetzen (Findling recheck-Muster) |
| Transkript-Waisen | LOW | Einmal-Abgleich gegen Dateicache, danach periodisch |
| Überbehauptung BITV im Store | LOW | Store-Text in-place korrigieren plus neue Version (Findling-Muster) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 ExApp ohne Search/Events | P-ARCH | Architektur-Entscheid schriftlich, Upgrade-Beweis beider Teile in CI |
| 2 RAM-Wächter/OOM | P-RES | `--memory`-Negativtest, DB überlebt |
| 3 Giftfile/hängende Jobs | P-WALK, P-PREV | Absturz-Korpus, Lease-Ablauf-Test |
| 4 Rechte zur Abfragezeit | P-ARCH, P-SEARCH | Negativtests Rechteentzug |
| 5 Gruppenordner-ACL | P-WALK | CI-Fall aus Findling #14 |
| 6 Externe Speicher | P-ARCH, P-WALK | 30-Nutzer-Mount einmal gerechnet |
| 7 Textverlust beim Austausch | P-QUAL, P-REL | Gate-Kennzahl "verlorene korrekte Wörter" |
| 8 Abfangregel löscht echte Sprache | P-PREV, P-REL | FLEURS tr/ar/uk-Negativsatz |
| 9 ffmpeg | P-MEDIA, P-REL | Medienkorpus, Playlist-Angriff |
| 10 Speicherwachstum | P-RES, P-QUAL | 50-Dateien-Dauertest, Rückkehr zur Grundlast |
| 11 Atomarer Tausch | P-ARCH, P-QUAL | Such-Schleife während Tausch |
| 12 Neuberechnungs-Stürme | P-ARCH, P-WALK, P-LIFE | Ordner-Umzug ohne Neurechnung |
| 13 DSGVO-Löschung | P-LIFE | Lösch-Negativtests, Waisen-Zähler 0 |
| 14 Inferenz blockiert | P-RES | Status-Route unter Last unter Frist |
| 15 Zeitmarken-Drift | P-PREV, P-QUAL, P-SUB | Spike-2-Zeitmarkentest im Gate |
| 16 VAD-Randfälle | P-PREV | Regressionstests Fenster/Polster/Mini-Segment |
| 17 Zahlen-Schreibweisen | P-SEARCH | Suchfälle Ziffer/Wort je Sprache |
| 18 SRT/VTT/BITV | P-SUB, P-REL | Unabhängiger Parser, Wortlaut-Gate |
| 19 Offline-Modelle | P-MODEL, P-REL | Container ohne Netz |
| 20 Lizenzen | P-MODEL, P-REL | Namensnennungs-Gate, buildconf-Prüfung |
| 21 Profil-Vorwahl | P-RES, P-REL | Eigentest, Pi 5/N100-Messung |
| 22 Sprachwechsel | P-QUAL | mixlang im Gate |
| 23 Suchleistung | P-SEARCH, P-REL | Lasttest, Kaltstart mit Trefferpflicht |
| 24 Zeitsprung im Player | P-SEARCH | Früher Spike, Playwright-Abnahme |
| 25 i18n | alle, P-REL | Katalog-Gates, FR-Abnahme, Volltest |
| 26 Sonderzeichen | P-WALK, P-MEDIA | Emoji/NFD-Korpus |
| 27 Neustart/Zertifikat | P-ARCH, P-RES | Neustart-Test, Fortsetzen je Fenster |
| 28 Cron-Abhängigkeit | P-WALK | Selbst angestoßene Crawl-Scheiben |

## Sources

- Eigene Messungen: `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE-REPORT.md` (Mini-Segment-Absturz, Sprachdrift roher VAD-Schnipsel, Token-Zeitraster, ffmpeg, LGPL), `SPIKE2-REPORT.md` (Zeitmarken Parakeet/Whisper, RAM-Spitze beim Laden, Canary ohne Wortzeiten), `SPIKE3-REPORT.md` (Halluzinationen mit/ohne VAD, Deletions Whisper/Parakeet, Schluck-Wächter, ROVER, RAM je Modell, Release-Gate, Lizenzen der Gate-Daten) [HIGH]
- Findling-Erfahrungen: `C:/Users/Student/nextcloud-search/.planning/RETROSPECTIVE.md`, `debug/issue14-acl-unreadable.md`, `debug/crawl-unfinished-zweitlauf.md`, Phase 41 (Issues #25, #37), 41-AUDIT (Issue #44); GitHub-Issues street1983nk/nextcloud-search #14, #15, #18, #19, #25, #33, #36, #44, #45 [HIGH]
- AppAPI-Quelltext `nextcloud/app_api` lib/Listener (kein Search-Provider-Listener, nur DeclarativeSettings, TaskProcessing, Menü, Files-Plugin), nc_py_api 0.30.3 im Skeleton ohne Search-API [MEDIUM bis HIGH]
- Nextcloud webhook_listeners, NodeDeletedEvent ohne ID: https://docs.nextcloud.com/server/stable/admin_manual/webhook_listeners/index.html [MEDIUM]
- Nextcloud External Storage (Authentifizierungsarten, Änderungen außerhalb von Nextcloud): https://docs.nextcloud.com/server/stable/admin_manual/configuration_files/external_storage_configuration_gui.html [MEDIUM]
- W3C WebVTT: https://www.w3.org/TR/webvtt1/ (Kopf, Zeitformat, Escaping, Reihenfolge, Ende größer Start) [HIGH]
- W3C Understanding SC 1.2.2: https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html (Nicht-Sprach-Information, Fehler F8) [HIGH]
- CTranslate2 auf PyPI (aarch64-Wheels, Ruy/OpenBLAS auf ARM): https://pypi.org/project/ctranslate2 [MEDIUM]; faster-whisper Issue #833 (langsame Segment-Iteration auf aarch64 bei Halluzination) https://github.com/SYSTRAN/faster-whisper/issues/833 [LOW]
- faster-whisper Speicherverhalten bei langen Dateien: https://github.com/SYSTRAN/faster-whisper/pull/846, https://bbs.pyvideotrans.com/show/4100 [LOW, durch Spike-3-Messung 3,4 GB auf 41 min gestützt]
- cgroup v2, `oom_score_adj`, ffmpeg `-protocol_whitelist`, moov-Atom-Verhalten bei Pipes, glibc-Arenen: Fachwissen, nicht eigens nachgeschlagen [MEDIUM, in P-RES/P-MEDIA per Test bestätigen]
- Trash-Ablauf ohne Löschereignis, Sitzungs-Anmeldedaten im Hintergrund, Viewer-Zeitsprung per URL: nicht belegt [LOW, Recherche-Flags für P-LIFE, P-WALK, P-SEARCH]

---
*Pitfalls research for: Audio & Video Search (Nextcloud-ExApp, lokale Transkription)*
*Researched: 2026-11-06*
