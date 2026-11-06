# Product

<!-- impeccable:product-schema 1 -->

> Hervorgegangen aus der Vorlage von nextcloud-exapp-skeleton. Quelle für Nutzer und Core Value: `.planning/PROJECT.md` (Stand 06.11.2026). Aussagen ohne Quelle bestätigt der Owner mit Datum.

## Platform

web

## Users

- **Admins von Nextcloud-Instanzen** (Selfhost, kleine Organisationen, Behörden, Schulen), die beide Apps installieren und den Zustand unter Verwaltungseinstellungen, Audio & Video Search prüfen.
- **Nutzer der Instanz**, die ihre Aufnahmen (Sitzungen, Interviews, Vorlesungen, Videos) durchsuchen wollen. Ihre Frage: "In welcher Aufnahme und an welcher Stelle wurde das gesagt?" Sie suchen in der normalen Nextcloud-Suche und springen vom Treffer auf die Zeitstelle.

## Product Purpose

Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.

Erfolg heißt: Ein Nutzer findet einen gesprochenen Satz über die Nextcloud-Suche und landet mit einem Klick an der richtigen Stelle der Aufnahme, ohne dass ein Admin etwas einstellen musste.

Stand Phase 1: zwei Apps im Gleichschritt und ein Testtreffer für Entwickler (`occ audio_video_search:sample`), noch keine Transkription.

## Positioning

- Läuft komplett in der eigenen Instanz, kein Inhalt verlässt den Server, keine Telemetrie.
- Zwei Apps, beide nötig, immer dieselbe Version: PHP-App `audio_video_search` (Suche, Ereignisse, Rechte, Abspielansicht) und ExApp `audio_video_search_backend` (Python-Container über AppAPI/HaRP: Dekodieren, Erkennung, Index). AGPL-3.0-or-later, signiert im App Store.
- Treffer erscheinen in der normalen Nextcloud-Suche mit Sprung auf die Zeitstelle; das geht nur über einen Suchprovider einer PHP-App (Quelle: `.planning/research/STACK.md`, Kernbefund).

## Operating Context

- Store-Eintrag unter External Apps, Nextcloud 33 bis 35, amd64 und arm64.
- Oberfläche: Suchtreffer, Abspielansicht und Admin-Statusbereich als PHP-Templates der Begleit-App (Stufe 3), die ExApp nur mit deklarativen Einstellungen; siehe DESIGN.md.
- Texte in Deutsch, Englisch und Französisch, Deutsch zuerst.

## Capabilities and Constraints

- Phase 1: Suchprovider, Abspielansicht mit Startzeit, Admin-Statusbereich mit Zustand der Gegen-App, Testtreffer per `occ` nur im Debug-Modus.
- Geplant: automatische lokale Transkription aller Audio- und Videodateien in Deutsch, Englisch und Französisch, Suche mit Zeitmarke.
- Mobil-Apps öffnen einen Treffer ab 0:00, ohne Zeitsprung.
- Out of Scope: Inhalte an externe Dienste schicken (Owner-Regel Datenschutz zuerst).
- Texte nur über die l10n-Kataloge, drei Sprachen im Gleichstand (`backend/tests/test_trilingual.py`).

## Brand Commitments

- Keine eigene visuelle Marke: die Oberfläche folgt Nextcloud-Design und Theming (nextcloud-ui-Skill).
- Produkttexte sind kurze Faktenlisten, höchstens eine Zahl, Entwurf vor Release dem Owner zeigen.
- Deutsch mit echten Umlauten, keine Gedankenstriche, keine Emojis.

## Evidence on Hand

- Screenshots der Abnahme aus den Playwright-Specs unter `ci/playwright/` (drei Breiten, hell und dunkel), Messwerte der Spikes mit Methode in `.planning/research/`.
- Nicht vorhanden und nicht zu erfinden: Kundenstimmen, Nutzerzahlen, Preise.

## Product Principles

1. Null Konfiguration: der Werkzustand funktioniert ohne Einstellung.
2. Nichts verlässt den Server.
3. Ehrliche Zustände: Übersprungenes und Fehlgeschlagenes wird sichtbar benannt.
4. Sieht aus wie Nextcloud.

## Accessibility & Inclusion

Zielstandard WCAG 2.1 AA (BITV-relevant für öffentliche Einrichtungen): Fokus nie entfernt, Farbe nie alleiniger Träger, Icon-Knöpfe mit `aria-label`, hoher Kontrast über Server-Variablen.
