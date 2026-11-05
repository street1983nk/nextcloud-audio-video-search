[Deutsch](README.md) | [English](README.en.md) | Français

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![Licence](https://img.shields.io/badge/Licence-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search rend les fichiers audio et vidéo de Nextcloud consultables. L'application transcrit la parole localement sur votre propre serveur, pour retrouver réunions, interviews et enregistrements grâce à leur contenu.

**Statut :** en développement, pas encore dans l'App Store.

## Ce que fait Audio & Video Search

- Transcription sur votre propre serveur avec des modèles vocaux ouverts, pour l'allemand, l'anglais et le français
- Recherche dans le texte parlé, résultats avec horodatage
- Fonctionne entièrement dans votre propre instance, aucune télémétrie
- Ne modifie jamais vos fichiers

## Prérequis

- Nextcloud 33 à 35 avec AppAPI et un démon de déploiement configuré (HaRP recommandé)
- CPU : amd64 ou arm64

## Installation

Installer Audio & Video Search depuis la section External Apps de l'App Store. Les
réglages se trouvent ensuite dans Paramètres d'administration, Paramètres
supplémentaires.

## Architecture

Audio & Video Search est une External App : un conteneur Python (FastAPI) qu'AppAPI
démarre via le démon de déploiement et ne joint que par AppAPI/HaRP. Chaque
requête vers le conteneur porte la signature d'AppAPI ; sans elle, la réponse
est 401.

## Confidentialité

Tout fonctionne localement dans le conteneur, rien ne quitte votre serveur.
L'application conserve les transcriptions dans le volume de données de son conteneur ; aucun enregistrement ne quitte le serveur.

## Licence

AGPL-3.0-or-later. Voir [LICENSE](LICENSE).
