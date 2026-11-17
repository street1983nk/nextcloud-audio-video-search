[Deutsch](README.md) | [English](README.en.md) | Français

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![Licence](https://img.shields.io/badge/Licence-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search rend les fichiers audio et vidéo de Nextcloud consultables. L'application transcrit la parole localement sur votre propre serveur, pour retrouver réunions, interviews et enregistrements grâce à leur contenu.

**Statut :** en développement, pas encore dans l'App Store. Depuis la 0.3.0, l'application transcrit localement tous les fichiers audio et vidéo de l'instance, stockages externes compris, d'abord sous forme d'aperçu ; ses résultats portent « Provisoire » dans la recherche. Une transcription plus précise est prévue pour des versions ultérieures. La recherche étendue et le brouillon de sous-titres (ci-dessous) sont construits dans le dépôt, mais ne font encore partie d'aucune version publiée.

## Ce que fait Audio & Video Search

- Résultats issus de l'audio et de la vidéo dans la recherche Nextcloud habituelle, avec horodatage
- Vue de lecture qui ouvre l'enregistrement au moment du résultat
- Zone d'état pour les administrateurs avec l'état des deux applications
- Ne modifie jamais vos fichiers ; un nouveau fichier n'est créé que si vous déposez un brouillon de sous-titres à côté de l'enregistrement
- Transcription sur votre propre serveur pour l'allemand, l'anglais et le français, d'abord sous forme d'aperçu

Les applications mobiles (Android, iOS) ouvrent un résultat comme fichier à partir de 0:00, sans saut au moment précis.

### Recherche

- Formes des mots : « Häuser » trouve « Haus »
- Début des mots composés allemands : un mot recherché de 5 lettres ou plus trouve aussi les mots qui commencent par lui (« Haushalt » trouve « Haushaltsplanberatung »)
- Nombres en chiffres et en lettres en allemand, en anglais et en français : de 0 à 100, ordinaux compris (« zwölf » trouve « 12 », « twelfth » et « 12e »), centaines et milliers ronds, milliers avec séparateur (30.000, 30,000, 30 000) et années de 1100 à 2099 (« 1940 » trouve « neunzehnhundertvierzig »)
- Filtres de date et de personne de la recherche Nextcloud : la date est la date de modification du fichier, la personne compte comme dans la recherche de fichiers de Nextcloud

### Brouillon de sous-titres

- Téléchargement sur la page de lecture en SRT, VTT et TXT, nom de fichier `<nom>.<de|en|fr>.<srt|vtt|txt>`, trémas allemands et ß du nom transcrits (Übung devient Uebung)
- VTT et TXT portent la mention « Brouillon de sous-titres, créé automatiquement et non vérifié. »
- Tant que le fichier est encore en cours de traitement, le brouillon contient l'état jusqu'au moment indiqué et le signale
- Déposer à côté du fichier : `<nom>.<de|en|fr>.vtt`, trémas allemands et ß du nom transcrits (Übung devient Uebung), dans le dossier de l'enregistrement, uniquement avec le droit d'y créer des fichiers ; un fichier existant n'est jamais écrasé
- Piste de sous-titres sur les vidéos de la page de lecture, désactivée jusqu'à ce que vous l'activiez
- Partages qui n'autorisent pas le téléchargement : résultats dans la recherche oui, téléchargement et dépôt du brouillon de sous-titres non ; si le réglage ne peut pas être déterminé, le téléchargement est considéré comme bloqué

### Limites

- La visionneuse de Nextcloud ne reconnaît les fichiers de sous-titres annexes qu'à partir de Nextcloud 36 ; Nextcloud 33 à 35 n'ont pas de code pour cela. Là, seule la page de lecture de cette application affiche la piste.
- Mots composés uniquement par leur début : « Plan » ne trouve pas « Bebauungsplan »
- Résultats en trop : « Haushalt » trouve aussi « Haushälterin »
- Le SRT ne porte aucune mention de brouillon dans son contenu, car le format ne connaît pas de commentaires
- Un fichier annexe déposé n'est jamais mis à jour automatiquement ; pour un état plus récent, supprimer l'ancien fichier et déposer à nouveau
- Comme la recherche de fichiers, le filtre de personne ne compte que les fichiers partagés ; un fichier jamais partagé est exclu
- Les sous-titres qu'aucune personne n'a vérifiés s'appellent partout « brouillon de sous-titres »

## Deux applications, toutes deux nécessaires

| Application | ID | Rôle |
|---|---|---|
| Audio & Video Search | `audio_video_search` | Application PHP : recherche, droits, vue de lecture, brouillon de sous-titres, zone d'état |
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
