[Deutsch](README.md) | [English](README.en.md) | Français

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![Licence](https://img.shields.io/badge/Licence-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search rend les fichiers audio et vidéo de Nextcloud consultables. L'application transcrit la parole localement sur votre propre serveur, pour retrouver réunions, interviews et enregistrements grâce à leur contenu.

**Statut :** en développement, pas encore dans l'App Store. Depuis la 0.3.0, l'application transcrit localement tous les fichiers audio et vidéo de l'instance, stockages externes compris, d'abord sous forme d'aperçu ; ses résultats portent « Provisoire » dans la recherche. Une transcription plus précise est prévue pour des versions ultérieures.

## Ce que fait Audio & Video Search

- Résultats issus de l'audio et de la vidéo dans la recherche Nextcloud habituelle, avec horodatage
- Vue de lecture qui ouvre l'enregistrement au moment du résultat
- Zone d'état pour les administrateurs avec l'état des deux applications
- Ne modifie jamais vos fichiers
- Transcription sur votre propre serveur pour l'allemand, l'anglais et le français, d'abord sous forme d'aperçu

Les applications mobiles (Android, iOS) ouvrent un résultat comme fichier à partir de 0:00, sans saut au moment précis.

## Deux applications, toutes deux nécessaires

| Application | ID | Rôle |
|---|---|---|
| Audio & Video Search | `audio_video_search` | Application PHP : recherche, droits, vue de lecture, zone d'état |
| Audio & Video Search Backend | `audio_video_search_backend` | External App (conteneur Python) : décodage, reconnaissance, index |

Les deux applications doivent être installées et avoir la même version. Si les versions ne diffèrent que par le dernier chiffre, la recherche continue de fonctionner ; sinon, elle ne renvoie aucun résultat audio ou vidéo tant que les deux applications ne correspondent pas.

## Prérequis

- Nextcloud 33 à 35 avec AppAPI et un démon de déploiement configuré (HaRP recommandé)
- CPU : amd64 ou arm64
- Mémoire : environ 2,2 Go libres (1,7 Go plus 0,5 Go de réserve) ; espace disque : environ 0,67 Go pour les modèles vocaux

## Installation

En bref : AppAPI avec un démon de déploiement, puis l'ExApp `audio_video_search_backend`, puis l'application PHP `audio_video_search`. L'état des deux applications figure ensuite dans Paramètres d'administration, Audio & Video Search. Toutes les étapes, les états de la zone d'état et le résultat de test : [docs/install.fr.md](docs/install.fr.md).

## Architecture

L'application PHP s'intègre à la recherche Nextcloud, vérifie les droits et transmet les fichiers au backend par leur identifiant. Le backend est une External App : un conteneur Python (FastAPI) qu'AppAPI démarre via le démon de déploiement et ne joint que par AppAPI/HaRP. Chaque requête vers le conteneur porte la signature d'AppAPI ; sans elle, la réponse est 401.

## Confidentialité

Tout fonctionne localement sur votre propre serveur : aucun audio, aucun texte et aucune télémétrie ne quitte le serveur. La seule connexion sortante est le téléchargement unique des modèles vocaux à l'activation.
L'application conserve transcriptions et index dans le volume de données de son conteneur.

## Licence

AGPL-3.0-or-later. Voir [LICENSE](LICENSE).

Composants tiers du backend :

- Liste de mots allemande `wngerman` (Debian), GPL-2.0-or-later, pour décomposer les mots composés ; texte de licence dans l'image sous `/usr/local/share/audio_video_search_backend/COPYING.wngerman`
- Pour la transcription, l'ExApp télécharge à l'activation Parakeet TDT 0.6B v3 de NVIDIA (CC-BY-4.0) et Silero VAD (MIT) depuis la release GitHub propre au projet `models-2026-11` et vérifie chaque fichier avec un sha256 fixe ; sans accès à Internet, les administrateurs peuvent déposer eux-mêmes les mêmes fichiers ; Whisper (MIT) est prévu pour des versions ultérieures.
- FFmpeg (build LGPL statique de BtbN, version 8.1) pour décoder les enregistrements

Icônes de l'application PHP : Material Design Icons de Pictogrammers, Apache-2.0, texte de licence dans [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt).
