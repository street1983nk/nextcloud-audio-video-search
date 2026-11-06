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

La phase 1 ne transcrit pas encore. Pour la preuve d'intégration, une commande crée un court résultat de test pour un vrai fichier audio ou vidéo. Elle exige le mode débogage dans `config.php` :

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

## Remarques

- La lecture à partir d'un moment précis peut démarrer lentement sur un stockage externe qui ne permet pas de sauter dans le flux de données, car le serveur lit le fichier jusqu'à la position de départ.
- Les applications mobiles ouvrent un résultat à partir de 0:00, sans saut au moment précis.
