# Product

<!-- impeccable:product-schema 1 -->

> Vorlage aus nextcloud-exapp-skeleton. Jede mit TODO(skeleton) markierte Stelle füllt die App mit Quellenangabe. Aussagen ohne Quelle bestätigt der Owner mit Datum.

## Platform

web

## Users

- **Admins von Nextcloud-Instanzen** (Selfhost, kleine Organisationen, Behörden), die die App installieren und unter Verwaltungseinstellungen, Weitere Einstellungen konfigurieren.
- TODO(skeleton): die Nutzer, die das Ergebnis der App sehen, und mit welcher Frage sie kommen.

## Product Purpose

TODO(skeleton): ein Absatz, was nach der Installation ohne weitere Konfiguration funktioniert (Core Value).

Erfolg heißt: TODO(skeleton).

## Positioning

- Läuft komplett in der eigenen Instanz, kein Inhalt verlässt den Server, keine Telemetrie.
- External App: Python-Container über AppAPI/HaRP, AGPL-3.0-or-later, signiert im App Store.
- TODO(skeleton): Differenzierer gegenüber vorhandenen Lösungen, mit Quelle.

## Operating Context

- Store-Eintrag unter External Apps, Nextcloud 33 bis 35, amd64 und arm64.
- Oberfläche: deklarative Admin-Einstellungen (AppAPI), siehe DESIGN.md.
- Texte in Deutsch, Englisch und Französisch, Deutsch zuerst.

## Capabilities and Constraints

- TODO(skeleton): Fähigkeiten als Liste.
- Out of Scope: Inhalte an externe Dienste schicken (Owner-Regel Datenschutz zuerst).
- Texte nur über die l10n-Kataloge, drei Sprachen im Gleichstand (tests/test_trilingual.py).

## Brand Commitments

- Keine eigene visuelle Marke: die Oberfläche folgt Nextcloud-Design und Theming (nextcloud-ui-Skill).
- Produkttexte sind kurze Faktenlisten, höchstens eine Zahl, Entwurf vor Release dem Owner zeigen.
- Deutsch mit echten Umlauten, keine Gedankenstriche, keine Emojis.

## Evidence on Hand

- TODO(skeleton): Screenshots unter `store/media/`, Messwerte mit Methode.
- Nicht vorhanden und nicht zu erfinden: Kundenstimmen, Nutzerzahlen, Preise.

## Product Principles

1. Null Konfiguration: der Werkzustand funktioniert ohne Einstellung.
2. Nichts verlässt den Server.
3. Ehrliche Zustände: Übersprungenes und Fehlgeschlagenes wird sichtbar benannt.
4. Sieht aus wie Nextcloud.

## Accessibility & Inclusion

Zielstandard WCAG 2.1 AA (BITV-relevant für öffentliche Einrichtungen): Fokus nie entfernt, Farbe nie alleiniger Träger, Icon-Knöpfe mit `aria-label`, hoher Kontrast über Server-Variablen.
