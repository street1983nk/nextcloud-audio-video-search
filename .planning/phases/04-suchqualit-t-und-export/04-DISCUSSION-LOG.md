# Phase 4: Suchqualität und Export - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md , this log preserves the alternatives considered.

**Date:** 2026-11-16
**Phase:** 04-Suchqualität und Export
**Areas discussed:** Export-Ort und Bedienung, Nebendatei-Ablage, Filter-Semantik, Zahlen und Wortformen

---

## Export-Ort und Bedienung

| Option | Description | Selected |
|--------|-------------|----------|
| Nur Abspielseite | Download-Bereich auf der bestehenden Abspielseite, passt zur v1-Regel | ✓ |
| Abspielseite + Files-Menü | Zusätzlich Eintrag im Dateien-Kontextmenü | |
| Nur Files-Menü | Export nur über das Kontextmenü | |

| Option | Description | Selected |
|--------|-------------|----------|
| Drei Buttons | SRT, VTT, TXT als drei sichtbare Download-Knöpfe | ✓ |
| Ein Menü | Ein Knopf mit Formatauswahl | |

| Option | Description | Selected |
|--------|-------------|----------|
| Fließtext ohne Zeiten | Reines Transkript, Kopfzeile mit Dateiname und Entwurf-Hinweis | ✓ |
| Mit Zeitmarken | Je Abschnitt eine Zeitmarke | |
| Beides anbieten | Zwei TXT-Varianten | |

| Option | Description | Selected |
|--------|-------------|----------|
| `<Name>.<Sprache>.srt` | Gleiches Muster wie die Nebendatei (EXP-03) | ✓ |
| `<Name>.srt` | Kürzer, Sprache nicht im Namen | |

**User's choice:** Alle vier Empfehlungen übernommen.

---

## Nebendatei-Ablage

| Option | Description | Selected |
|--------|-------------|----------|
| Meldung, kein Ablegen | Klare Fehlermeldung, Nutzer entscheidet selbst | ✓ |
| Alternativname | Automatisch `sitzung.de (2).vtt` | |

| Option | Description | Selected |
|--------|-------------|----------|
| Schreibrecht am Ordner | Nextcloud-Rechteprüfung, Download-Sperre blockiert zusätzlich | ✓ |
| Nur Eigentümer | Enger, Teamordner gehen leer aus | |

| Option | Description | Selected |
|--------|-------------|----------|
| ISO-Kurzform de/en/fr | `sitzung.de.vtt`, übliches Untertitel-Muster | ✓ |
| Voller Name | `sitzung.deutsch.vtt` | |

| Option | Description | Selected |
|--------|-------------|----------|
| Kein Veraltungs-Hinweis | Nutzer legt bei Bedarf neu ab | ✓ |
| Hinweis auf Abspielseite | Vergleichslogik plus neue Texte | |

**User's choice:** Alle vier Empfehlungen übernommen.

---

## Filter-Semantik

| Option | Description | Selected |
|--------|-------------|----------|
| Änderungsdatum (mtime) | Wie die Files-Suche, immer vorhanden | ✓ |
| Aufnahmedatum | Aus Medien-Metadaten, lückig | |

| Option | Description | Selected |
|--------|-------------|----------|
| Wie Files-Suche | Dateien der Person gehörend oder von ihr geteilt; Research prüft NC 33-35 | ✓ |
| Nur Eigentümer | Enger, weicht vom Files-Verhalten ab | |

**User's choice:** Beide Empfehlungen übernommen.

---

## Zahlen und Wortformen

| Option | Description | Selected |
|--------|-------------|----------|
| 0 bis 100 + runde Größen | Dazu Hunderter/Tausender und Jahreszahlen-Muster | ✓ |
| 0 bis 20 | Minimal | |
| Voller Zahlenparser | Beliebige Zahlwörter, fehleranfällig | |

| Option | Description | Selected |
|--------|-------------|----------|
| Ordinale ja | Im gleichen Zahlenraum (zwölfter, twelfth, douzième) | ✓ |
| Nein | Nur Kardinalzahlen | |

| Option | Description | Selected |
|--------|-------------|----------|
| Findling-Muster 1:1 | Gleiche Analyzer-Kette und Wortlisten-Beschaffung | ✓ |
| Research soll Alternativen prüfen | Vorher messen | |

**User's choice:** Alle drei Empfehlungen übernommen.

## Claude's Discretion

- Untertitel-Segmentierungsalgorithmus (EXP-02-Grenzen) und unabhängiger Parser
- Technik der Zahlen-Normalisierung (Index- vs. Abfrage-Zeit) nach Research
- Ablage-Mechanik der Nebendatei (PHP-Filesystem-API, Namens-Härtung)
- Reindex-Strategie bei Analyzer-Umbau (Schema-Version nach Findling-Muster)

## Deferred Ideas

Keine , die Diskussion blieb im Phasenrahmen.
