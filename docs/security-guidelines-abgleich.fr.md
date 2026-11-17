# Comparaison avec les directives de sécurité Nextcloud (Audio & Video Search)

Annexe au dossier de sécurité. État au 16.11.2026, vérifié par rapport aux
directives de sécurité du manuel développeur Nextcloud 35
(developer_manual/prologue/security.html) et aux règles de l'app store
(app_publishing_maintenance/publishing.html). Méthode : un balayage du code
sur php/ et backend/src le 16.11.2026 (shell_exec, proc_open, passthru,
eval, SQL brut, print_unescaped, innerHTML, os.system : 0 occurrence) plus
les garde-fous CI dans backend/tests (test_php_gates.py entre autres).

## Directives développeur

| Règle | État | Preuve |
|---|---|---|
| Injection SQL : uniquement des requêtes préparées | respecté | IQueryBuilder dans tous les mappers (php/lib/Db), aucun SQL brut dans le balayage |
| XSS : assainir les templates et le DOM | respecté | Garde-fou : templates uniquement avec p(), le JS n'insère le texte utilisateur que par textContent (test_php_gates.py, test_ui_assets.py) |
| Clickjacking | respecté | Les en-têtes par défaut du serveur restent intacts |
| Exécution de code / inclusion de fichiers | respecté | Balayage 0 occurrence ; médias et modèles vivent dans le volume ExApp, jamais dans le webroot |
| Traversée de répertoires : API de fichiers | respecté | Recherche de noeuds uniquement dans FileAccess (règle 4) ; le conteneur ne lit le contenu que par la passerelle après contrôle des droits |
| Injection shell | respecté | PHP n'appelle aucun shell (balayage) ; ffmpeg et les modèles tournent en processus enfants avec listes d'arguments, sans shell |
| Contournement d'authentification / élévation de privilèges | respecté | Contrôle des droits au moment de la requête en PHP (readableFile, actAs) ; résultats uniquement via des références à l'état active ; le plan de la phase 4 durcit l'export en fail-closed (DownloadPolicy) |
| Exposition de données sensibles | respecté | Ni noms ni chemins dans les journaux (règle 6, le contexte de journal porte class au lieu de exception depuis le push 9) ; l'état vit dans le volume ExApp |
| CSRF | respecté | Standard du framework d'applications ; les POST portent le requesttoken (modèle admin.js, garde-fou prévu pour les nouvelles routes de la phase 4) |
| Redirections non validées | s. o. | Aucune redirection |
| CORS | s. o. | Aucune autorisation CORS |

## Règles de l'app store (extrait)

| Règle | État | Preuve |
|---|---|---|
| AGPL-3.0-or-later | respecté | LICENSE, info.xml des deux applications ; Parakeet CC-BY-4.0 avec attribution NVIDIA |
| Pas de « Nextcloud » dans le nom | respecté | audio_video_search / audio_video_search_backend |
| Réaction rapide aux signalements de sécurité | respecté | SECURITY.md (signalement privé GitHub plus courriel, 7 jours) |
| Installation, désinstallation et mises à niveau propres | respecté | Migrations avec tests ; preuve de mise à niveau dans la CI deploy-harp (y compris le durcissement de la fenêtre de maintenance du push 9) |
| Aucune donnée à des tiers, protection de la vie privée | respecté | Ni audio, ni texte, ni télémétrie ne quitte le serveur ; les modèles sont téléchargés depuis la release GitHub du projet avec un sha256 fixe et une liste d'hôtes autorisés (D-03-21) ; HF_HUB_OFFLINE=1 |
| Moyen de contact | respecté | Issues GitHub, SECURITY.md |

## Au-delà des directives

- SECURITY.md par phase avec audit des menaces (01/02/03 verified, threats_open 0) ; risques acceptés confirmés un par un par le propriétaire
- Épinglage des workflows et tests de garde contre la manipulation de la CI ; divulgation AI_ASSISTANCE.md
- La limitation de débit et le garde-fou CSRF pour les nouvelles routes d'export et de fichier annexe font partie des plans de la phase 4 (04-10, 04-12)

## Points ouverts

- La phase 4 ajoute de nouvelles surfaces (export, fichier annexe, piste de sous-titres) ; cette comparaison sera mise à jour après l'audit de sécurité de la phase 4 (04-SECURITY.md).
