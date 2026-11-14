[Deutsch](install.md) | [English](install.en.md) | Français

# Installer Audio & Video Search

Audio & Video Search se compose de deux applications. Les deux sont nécessaires et doivent avoir la même version :

- `audio_video_search_backend` : External App (conteneur Python), décode, reconnaît et indexe
- `audio_video_search` : application PHP, relie le backend à la recherche Nextcloud et affiche la vue de lecture

## Ordre

1. Activer AppAPI et configurer un démon de déploiement (HaRP recommandé).
2. Installer l'External App « Audio & Video Search Backend » (`audio_video_search_backend`) et attendre qu'elle soit activée.
3. Installer et activer l'application « Audio & Video Search » (`audio_video_search`) dans la même version.
4. Vérifier l'état dans Paramètres d'administration, Audio & Video Search. Après une mise à jour, mettre les deux applications à la même version.

## États de la zone d'état

La zone d'état affiche un seul état :

- **Succès, les deux applications sont connectées :** Les deux applications sont dans la même version, la recherche fonctionne normalement.
- **Information, la version diffère par le dernier chiffre :** La recherche fonctionne normalement ; aligner les deux applications lors de la prochaine mise à jour.
- **Erreur, versions différentes :** Les versions diffèrent par le premier ou le deuxième chiffre, la recherche ne renvoie aucun résultat audio ou vidéo tant que les deux applications n'ont pas la même version.
- **Erreur, backend non installé :** `audio_video_search_backend` manque, la recherche ne trouve rien dans l'audio et la vidéo.
- **Erreur, backend désactivé :** `audio_video_search_backend` est installé mais désactivé ; l'activer dans Applications.
- **Erreur, le backend ne répond pas :** Le conteneur ne fonctionne pas ou le démon de déploiement n'est pas joignable ; vérifier dans Applications et dans les paramètres AppAPI.
- **Erreur, AppAPI non activé :** Sans AppAPI, le backend ne fonctionne pas ; activer AppAPI et configurer un démon de déploiement.
- **Avertissement, nouvelle vérification échouée :** « Vérifier à nouveau » n'a pas abouti ; l'état au chargement de la page reste affiché.

À chaque erreur, le lien « Ouvrir Applications » mène à la gestion des applications.

## Résultat de test (pour les développeurs)

Pour la preuve d'intégration sans véritable enregistrement de parole, une commande crée un court résultat de test pour un vrai fichier audio ou vidéo. Elle exige le mode débogage dans `config.php` :

```php
'debug' => true,
```

Sans mode débogage, la commande refuse et la recherche n'affiche aucun résultat de test. Une instance de production ne reçoit donc jamais un résultat de test par erreur.

Créer :

```sh
occ audio_video_search:sample <fileId> [--at=<secondes>] [--user=<utilisateur>]
```

- `<fileId>` : identifiant numérique du fichier, par exemple `12345`
- `--at` : moment du résultat de test en secondes, de 0 à 86400, trois décimales au plus, 42 par défaut
- `--user` : lire en tant que cet utilisateur au lieu du propriétaire du fichier

Ensuite, dans Paramètres d'administration, Audio & Video Search, activer « Afficher le résultat de test dans la recherche » dans le bloc « Résultat de test ». La désactiver masque immédiatement le résultat de test, les données de test sont conservées.

Supprimer, uniquement ainsi :

```sh
occ audio_video_search:sample <fileId> --remove
```

La commande supprime le résultat de test et ses entrées d'index ; le fichier lui-même reste inchangé. Elle ne supprime jamais une vraie transcription. La suppression exige aussi le mode débogage. L'interface n'a aucune action de suppression.

## Détection

- Les stockages externes sont pris en compte par défaut. Pour en désactiver un : `occ audio_video_search:exclude --storage=<id du montage>` (id via `occ files_external:list`).
- Les stockages dont les identifiants ne valent que pour la session sont ignorés. Ils ne deviennent exploitables que lorsque l'administrateur choisit « Identifiants de connexion, sauvegarder dans la base de données » pour ce stockage. Nextcloud enregistre alors le mot de passe de chaque utilisateur, chiffré, sur le serveur et peut accéder au stockage sans que l'utilisateur se connecte. Quiconque contrôle le serveur et la base de données peut en principe le récupérer. C'est une décision délibérée ; sans elle, ces stockages restent exclus de la recherche.
- Exclure des utilisateurs, des groupes et des dossiers : `occ audio_video_search:exclude --user=<uid>`, `--group=<gid>` ou `--folder=<chemin>`. Cela fonctionne aussi avant l'installation du backend.
- Un stockage SMB monté par l'administrateur avec des identifiants propres à chaque utilisateur appartient à cet utilisateur pour les exclusions.
- `occ audio_video_search:status` indique combien de contenus sont transcrits (X sur Y).
- Les modifications faites directement sur le NAS apparaissent au plus tard après 24 heures, immédiatement avec `occ audio_video_search:rescan --all`, durablement plus vite avec `occ files_external:notify`.
- Les droits de lecture sur SMB et SFTP sont vérifiés à nouveau au moins tous les 7 jours.
- Les fichiers supprimés disparaissent aussitôt de la recherche. Leur transcription est conservée 7 jours au cas où une copie réapparaît.
- Chaque fichier est lu une fois en entier.
- Avec php-fpm, définir `request_terminate_timeout` pour qu'un accès SMB bloqué n'occupe pas un worker indéfiniment.

## Transcription (aperçu)

- Le backend transcrit localement tous les fichiers audio et vidéo détectés avec Parakeet TDT 0.6B v3 (int8) et Silero VAD. Le résultat est d'abord un aperçu : ses résultats portent le mot « Provisoire » dans la recherche, et la page de lecture affiche « Transcription provisoire. Elle peut contenir des erreurs. »
- Sont reconnus l'allemand, l'anglais et le français ; les passages dans d'autres langues sont écartés.
- Formats, entre autres : MP3, M4A, WAV, OGG, Opus, FLAC, MP4, MOV, MKV et WebM. S'il y a plusieurs pistes audio, celle marquée par défaut compte, sinon la première.
- Les fichiers nouveaux et modifiés passent avant les fichiers existants, ceux-ci par date de modification, les plus récents d'abord. Les longs fichiers sont traités par tranches de 10 minutes et sont trouvables après chaque tranche terminée.
- Durée maximale 12 heures, réglable jusqu'à 24 sous Paramètres d'administration, Paramètres supplémentaires, « Durée maximale d'un enregistrement en heures ». Les fichiers plus longs sont ignorés comme trop longs ; si la limite est relevée, ils reviennent dans la file d'attente.
- Un fichier reste sans transcription s'il ne contient pas de parole, s'il est endommagé ou protégé, si sa langue n'est pas prise en charge ou s'il est trop long. Si l'espace disque manque, le backend réessaie plus tard. Les utilisateurs voient la raison sur la page de lecture de leur fichier, les administrateurs voient les chiffres avec `occ audio_video_search:status` (sans noms de fichiers).
- Mémoire : l'aperçu a besoin d'environ 1,7 Go de RAM plus 0,5 Go de réserve ; s'il y en a moins de libre, il attend.
- Modèles : à l'activation, le backend télécharge une seule fois environ 0,67 Go depuis la release GitHub `models-2026-11` du projet, uniquement via `github.com` et `release-assets.githubusercontent.com`, et vérifie chaque fichier avec un sha256 fixe. En dehors de ce téléchargement, rien ne quitte le serveur.
- Sans accès à Internet : avant l'installation, créer le volume `nc_app_audio_video_search_backend_data` et y déposer les mêmes fichiers, `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx` et `tokens.txt` sous `models/parakeet/<somme de contrôle>/`, `silero_vad.onnx` sous `models/silero/<somme de contrôle>/`, propriétaire l'utilisateur 10001 du conteneur. `<somme de contrôle>` vaut `3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339`. Le backend vérifie les fichiers avec le même sha256 et ne télécharge alors rien.
- Attribution : Parakeet TDT 0.6B v3 by NVIDIA, CC-BY-4.0 ; Silero VAD, MIT ; FFmpeg, LGPL (build statique, uniquement pour le décodage).

## Remarques

- La lecture à partir d'un moment précis peut démarrer lentement sur un stockage externe qui ne permet pas de sauter dans le flux de données, car le serveur lit le fichier jusqu'à la position de départ.
- Les applications mobiles ouvrent un résultat à partir de 0:00, sans saut au moment précis.
