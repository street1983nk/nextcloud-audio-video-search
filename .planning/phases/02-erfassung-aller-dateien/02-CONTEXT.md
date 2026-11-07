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
- **D-02-02:** Rechte bleiben pro Nutzer: jede Kopie behält ihre eigene file_id als Verweis, die Suche prüft weiter über den Ordner des suchenden Nutzers (Findling-Lehre: Index nur einmal pro Freigabe würde Treffer für andere Nutzer verstecken).

### Anmeldung per Sitzung
- **D-02-03:** Externe Speicher mit Anmeldedaten aus der Sitzung (oder ohne gespeicherte Anmeldedaten) werden übersprungen. Der Admin sieht, welche Speicher betroffen sind, warum, und dass gespeicherte Anmeldedaten sie erfassbar machen. Keine Dateinamen in dieser Meldung. Erfassen bei Anmeldung: deferred.

### Rückwirkender Ausschluss
- **D-02-04:** Ein Ausschluss (Nutzer, Gruppe, Ordner, externer Speicher) entfernt sofort die Verweise der betroffenen Dateien, ausgeschlossene Nutzer sehen keine Treffer mehr. Transkript und Korrekturen von Hand bleiben, solange noch ein erfasster Verweis auf denselben Inhalt existiert. Fällt der letzte Verweis, werden Transkript, Index-Einträge und Korrekturen gelöscht.
- **D-02-05:** Ausschlüsse greifen vor dem ersten Durchlauf: eine ausgeschlossene Datei landet nie im Arbeitsvorrat und wird nie geladen.

### Zahl im Admin
- **D-02-06:** Die Fortschrittszahl zählt Inhalte: "X von Y Inhalten transkribiert", Zähler und Nenner beide nach Inhalts-Schlüssel (vor dem Hash nach Vorfilter-Schlüssel), klein daneben die Zahl der Dateien. Quote nie über 100 %. Ob die Anzeige selbst schon in Phase 2 oder erst in Phase 9 (ehrliche Admin-Zustände) kommt, entscheidet der Plan; die Zählung muss aber in Phase 2 stimmen und per occ abfragbar sein.
- **D-02-07:** Pflicht-Abnahmetest gegen eine UNABHÄNGIGE Zählung (nicht mit dem Code der Umsetzung): SMB-Freigabe mehrfach pro Nutzer mit unterschiedlicher Sicht, Gruppenordner, Kopie/Verschieben/Umbenennen/Taggen, verschwundener Speicher, gelöschter Nutzer, Ausschluss vor und nach dem ersten Durchlauf. Dazu eine Positivkontrolle. Findling #25 ging dreimal durch, weil nur Einzelteile getestet wurden.

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
