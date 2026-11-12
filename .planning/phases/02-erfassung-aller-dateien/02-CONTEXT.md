# Phase 2: Erfassung aller Dateien - Context

**Gathered:** 2026-11-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Ohne Konfiguration kennt das System alle Audio- und Videodateien der Instanz (alle Nutzer, Gruppenordner, externe Speicher), respektiert Ausschlüsse von Anfang an und rechnet gleichen Inhalt nur einmal (DISC-01 bis DISC-06). Transkription selbst ist nicht Teil dieser Phase, nur der Arbeitsvorrat.

</domain>

<decisions>
## Implementation Decisions

### Freigabe pro Nutzer (Lehre aus Findling #25)
- **D-02-01:** Vorfilter vor dem Hash: gleiche Freigabe (Speicher-Schlüssel ohne Nutzeranteil, Muster Findling `StorageService::countingKey`), gleicher Pfad innerhalb der Freigabe, gleiche Größe und gleiches Änderungsdatum gelten als dieselbe Datei. Sie wird nur einmal geladen und gehasht (sha256 der Bytes bleibt der Inhalts-Schlüssel aus Phase 1), weitere Kopien hängen sich an dieselbe media_id. Jede Abweichung (Größe, mtime, etag) führt zu neuem Hash.
- **D-02-01a (Owner 07.11., korrigiert nach Recherche):** Der Vorfilter allein ist ein Rechteleck (Findling-Messung A6, CI-Lauf 40716240639, `39-DEDUP-ERGEBNIS.md`: SMB-ACL sperrt die Datei, Nextcloud listet sie und `isReadable()` sagt ja, nur der Download scheitert bzw. hängt). Darum hängt sich jede weitere Kopie erst nach einem LESEBEWEIS an: die ersten 64 KiB über die eigene file_id und den eigenen Leser, mit Zeitgrenze, deren Hash muss zum Kopf der media passen. Scheitert oder hängt der Lesebeweis, gibt es für diese Kopie keinen Verweis und keine Treffer. Voll geladen und gehasht wird weiter nur einmal. Pflicht-Negativtest: Lauf ohne Lesebeweis muss das Leck zeigen (Positivkontrolle).
  - **Nachtrag (Owner 12.11.2026, "Ja"):** Liest der Nutzer beim erneuten Lesebeweis erfolgreich, aber andere Bytes als der Kopf der media, wird der Verweis nicht unreadable, sondern sofort von der media gelöst und voll geladen; ab der Abweichung gibt es für ihn keine Treffer aus dem alten Transkript mehr. Der Satz "jeder Fehlschlag wird unreadable" in 02-13-PLAN.md gilt für alle anderen Fehlschläge unverändert.
- **D-02-02:** Rechte bleiben pro Nutzer: jede Kopie behält ihre eigene file_id als Verweis, die Suche prüft weiter über den Ordner des suchenden Nutzers (Findling-Lehre: Index nur einmal pro Freigabe würde Treffer für andere Nutzer verstecken).

### Anmeldung per Sitzung
- **D-02-03:** Externe Speicher mit Anmeldedaten aus der Sitzung (oder ohne gespeicherte Anmeldedaten) werden übersprungen. Der Admin sieht, welche Speicher betroffen sind, warum, und dass gespeicherte Anmeldedaten sie erfassbar machen. Keine Dateinamen in dieser Meldung. Erfassen bei Anmeldung: deferred.

### Rückwirkender Ausschluss
- **D-02-04:** Ein Ausschluss (Nutzer, Gruppe, Ordner, externer Speicher) entfernt sofort die Verweise der betroffenen Dateien, ausgeschlossene Nutzer sehen keine Treffer mehr. Transkript und Korrekturen von Hand bleiben, solange noch ein erfasster Verweis auf denselben Inhalt existiert. Fällt der letzte Verweis, werden Transkript, Index-Einträge und Korrekturen gelöscht.
- **D-02-05:** Ausschlüsse greifen vor dem ersten Durchlauf: eine ausgeschlossene Datei landet nie im Arbeitsvorrat und wird nie geladen.

### Ausschluss-Bedeutung und Papierkorb (Owner 07.11.)
- **D-02-08:** Nutzer ausschließen = die Speicher, die ihm gehören (Home, eigene externe Mounts), werden nicht erfasst, und er bekommt keine Treffer. Dateien, die andere mit ihm teilen, bleiben für die anderen erfasst. Gruppenausschluss gilt für jedes Mitglied.
- **D-02-09:** Papierkorb: Transkript nur als verwaist vormerken (`orphaned_at`), nicht mehr findbar, bei Wiederherstellung sofort zurück. Endgültiges Löschen in Phase 8. D-02-04 (Löschen beim letzten Verweis) gilt für Ausschlüsse und endgültig gelöschte Dateien.
- **D-02-11 (Owner 07.11.):** Ein vom Admin angelegter SMB-Mount mit Anmeldedaten je Nutzer gilt beim Ausschluss als Eigentum dieses Nutzers (D-02-08): sein Speicher wird nicht erfasst. Die Kopien anderer Nutzer derselben Freigabe bleiben erfasst.

### Erneuter Lesebeweis und endgültiges Löschen (Owner 07.11.)
- **D-02-12:** Periodischer erneuter Lesebeweis: Jeder aktive Verweis auf SMB- und SFTP-Speichern wird beim Abgleich mit dem 64-KiB-Lesebeweis erneut geprüft, mindestens alle 7 Tage, und sofort bei vanished nach active sowie bei Wiederherstellung aus dem Papierkorb. Scheitert der Lesebeweis, verschwinden die Treffer dieses Nutzers sofort.
- **D-02-13:** Auch endgültiges Löschen (und ein gelöschter Nutzer) wird nur vorgemerkt (`orphaned_at`) und nach 7 Tagen vergessen; das endgültige Löschen baut Phase 8. Taucht innerhalb von 7 Tagen eine Kopie mit gleichem Inhalt auf, hängt sie sich an und behält Transkript und Korrekturen. D-02-04 (sofortiges Löschen beim letzten Verweis) gilt damit nur noch für Ausschlüsse.

### Kein Abschaltweg für den Lesebeweis (Owner 07.11.)
- **D-02-10:** Das Produkt hat KEINEN Weg, den Lesebeweis abzuschalten: kein Env, keine Einstellung, keine Markendatei, kein Debug-Schalter. Die Leck-Positivkontrolle aus D-02-01a läuft über ein eigenes CI-only-Image: der Workflow wendet einen Patch unter `ci/` (nie im ausgelieferten Quellbaum) auf eine Kopie an, der den Lesebeweis entfernt; das Image wird nie in eine öffentliche Registry oder unter einem Tag veröffentlicht und nur im Kontrollbein genutzt. Ein Gate schlägt an, wenn `php/` oder `backend/src` einen Weg enthält, der den Lesebeweis überspringt oder abschaltet. Positivkontrolle B (monkeypatch) bleibt in den Unit-Tests.

### Zahl im Admin
- **D-02-06:** Die Fortschrittszahl zählt Inhalte: "X von Y Inhalten transkribiert", Zähler und Nenner beide nach Inhalts-Schlüssel (vor dem Hash nach Vorfilter-Schlüssel), klein daneben die Zahl der Dateien. Quote nie über 100 %. Owner 07.11.: In Phase 2 nur per occ und Abnahmetest, die Admin-Oberfläche kommt in Phase 9 (ehrliche Admin-Zustände). Kein UI-Vertrag für Phase 2.
- **D-02-07:** Pflicht-Abnahmetest gegen eine UNABHÄNGIGE Zählung (nicht mit dem Code der Umsetzung): SMB-Freigabe mehrfach pro Nutzer mit unterschiedlicher Sicht, Gruppenordner, Kopie/Verschieben/Umbenennen/Taggen, verschwundener Speicher, gelöschter Nutzer, Ausschluss vor und nach dem ersten Durchlauf. Dazu eine Positivkontrolle. Findling #25 ging dreimal durch, weil nur Einzelteile getestet wurden.

### Testwerkzeug der Abnahme (Owner 07.11.)
- **D-02-14 (Owner 07.11.):** S3-Bein der Abnahme mit SeaweedFS 4.52 statt MinIO (MinIO-Image nicht mehr frei erhältlich), nur CI, nicht Produkt.

### Probe und Erfassung getrennt (Owner 07.11.)
- **D-02-15 (Owner 07.11., "Getrennte Schichten"):** Eine Probe (Testtreffer per occ :sample) und der echte Verweis der Erfassung für dieselbe Datei überschreiben einander nie. Die Probe liegt in einer eigenen Tabelle `sample_ref` (file_id, media_id), nicht in `file_ref`; `file_ref` kennt keinen Zustand `sample` mehr. Die Suche liefert beides: aktive Verweise und Proben, eine Probe aber nur, solange die Erfassung für diese Datei keinen Verweis hält, der keine Treffer gibt (unreadable, vanished, trashed). Proben bleiben hinter dem Debug-Schalter (Kennzeichen sample im Treffer). Das Entfernen einer Probe schreibt nie `file_ref`; Intake und Verwaist-Regel lesen und schreiben `sample_ref` nie (die Verwaist-Marke richtet sich nur nach echten Verweisen und versteckt keinen Probetreffer). Anlass: Push 2, deploy-harp arm64 (Lauf 42375022170), beide Reihenfolgen Intake/Probe verloren Treffer. Folgen für spätere Pläne: Ausschluss (Plan 16) und endgültiges Vergessen (Phase 8) müssen die Probe einer ausgeschlossenen bzw. vergessenen Datei mit entfernen, sonst bliebe ein Probetreffer.
- **D-02-15a (Owner 07.11., "Ja, so lassen"):** Die Verwaist-Marke (`orphaned_at`) richtet sich nur nach echten Verweisen. Eine Probe schützt eine media nicht vor der Marke, und die Marke versteckt keinen Probetreffer. Ausschluss (Plan 16) und endgültiges Vergessen (Phase 8) entfernen die Probe der betroffenen Datei mit (`sample_ref` dieser file_id), damit kein Probetreffer für eine ausgeschlossene oder vergessene Datei bleibt.

### Claude's Discretion
- Ereignisweg (AppAPI node_event) und periodischer Abgleich nach Findling-Muster (reconcile, Quiet-Gate, Sweep), inklusive der 1.6.3-Lehre: der Sweep verschwundener Speicher darf nicht hinter dem Quiet-Gate hängen.
- Sperrfrist für lange Vorschauen, SMB/S3-Timeouts, files_accesscontrol, Crawl-Flag-Tor: Recherche.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` Phase 2 (Erfolgskriterien, Research flag)
- `.planning/REQUIREMENTS.md` DISC-01 bis DISC-06
- `.planning/phases/01-zwei-app-ger-st-und-integrationsbeweis/01-RESEARCH.md` Entscheid 3 (Inhalts-Schlüssel, media_key-Indirektion)
- Findling (C:/Users/Student/nextcloud-search): `backend/src/findling/worker/reconcile.py`, `php/lib/Service/StorageService.php` (countingKey, classifyAbsent), `php/lib/Service/QueueService.php`, `.planning/phases/43-findling-1-6-3-sweep-und-zaehler/43-CONTEXT.md` und `43-RESEARCH.md` (Lehren aus #25)
- GitHub street1983nk/nextcloud-search Issue #25 (Topologie mbozem)

</canonical_refs>

<deferred>
## Deferred Ideas

- Speicher mit Sitzungs-Anmeldedaten erfassen, während der Nutzer angemeldet ist.

</deferred>

---

*Phase: 02-erfassung-aller-dateien*
*Context gathered: 2026-11-07*
