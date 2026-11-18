"""The texts of phase 5 in the PHP catalogues, word for word (plan 05-06).

T36 to T96 (T51 and T82 stay free, T83 is T83a and T83b) as the owner approved
them on 18.11.2026 in 05-UI-SPEC.md, "Neue Texte DE / EN / FR". The English
text is the key; de and de_DE carry the German text, fr the French text with a
no-break space (U+00A0) before : ; ? ! (checker flag: T37, T45, T56, T76).

The minimum memory and every need are numbers the container measures
(D-05-09); the catalogue never names one, T48 and T50 carry placeholders only.
No dash, no emoji, no "BITV" claim in any value.
"""

# The approved texts stand on one line each, word for word as in the UI-SPEC table.
# ruff: noqa: E501

import json
import re

import pytest

from tests.conftest import REPO_ROOT

PHP_L10N = REPO_ROOT / "php" / "l10n"
LANGUAGES = ("de", "de_DE", "en", "fr")
NBSP = chr(0xA0)
DASHES = (chr(0x2013), chr(0x2014))
EMOJI = re.compile(f"[{chr(0x1F300)}-{chr(0x1FAFF)}{chr(0x2600)}-{chr(0x27BF)}]")
PLACEHOLDER = re.compile(r"%(?:\d+\$)?[sd]")
PLAIN_SPACE_BEFORE = re.compile(r" [:;?!]")

# (id, en = key, de, fr), copied from 05-UI-SPEC.md.
ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "T36",
        "Transcription profile",
        "Transkriptionsprofil",
        "Profil de transcription",
    ),
    (
        "T37",
        "Suggested for this server: %1$s. %2$s of memory is available to the app.",
        "Vorschlag für diesen Server: %1$s. Für die App sind %2$s Arbeitsspeicher verfügbar.",
        "Suggestion pour ce serveur\u00a0: %1$s. L'application dispose de %2$s de mémoire vive.",
    ),
    (
        "T38",
        "Fast",
        "Schnell",
        "Rapide",
    ),
    (
        "T39",
        "Balanced",
        "Ausgewogen",
        "Équilibré",
    ),
    (
        "T40",
        "Quality",
        "Qualität",
        "Qualité",
    ),
    (
        "T41",
        "Parakeet for all files. Whisper turbo recomputes uncertain passages when memory allows.",
        "Parakeet für alle Dateien. Unsichere Stellen rechnet Whisper turbo nach, wenn der Speicher reicht.",
        "Parakeet pour tous les fichiers. Whisper turbo recalcule les passages incertains si la mémoire le permet.",
    ),
    (
        "T42",
        "Parakeet and Whisper turbo for all files, combined into one text.",
        "Parakeet und Whisper turbo für alle Dateien, zu einem Text vereint.",
        "Parakeet et Whisper turbo pour tous les fichiers, réunis en un seul texte.",
    ),
    (
        "T43",
        "Like Balanced, with Whisper large-v3 in addition for German recordings. Slowest.",
        "Wie Ausgewogen, deutsche Aufnahmen zusätzlich mit Whisper large-v3. Am langsamsten.",
        "Comme Équilibré, avec en plus Whisper large-v3 pour les enregistrements en allemand. Le plus lent.",
    ),
    (
        "T44",
        "Needs %s of memory.",
        "Braucht %s Arbeitsspeicher.",
        "Nécessite %s de mémoire vive.",
    ),
    (
        "T45",
        "Locked: needs %1$s, %2$s available.",
        "Gesperrt: braucht %1$s, verfügbar %2$s.",
        "Verrouillé\u00a0: nécessite %1$s, %2$s disponibles.",
    ),
    (
        "T46",
        "Suggested",
        "Vorschlag",
        "Suggéré",
    ),
    (
        "T47",
        "The chosen profile %1$s no longer fits into memory (needs %2$s, %3$s available). The app uses %4$s until enough memory is free again.",
        "Das gewählte Profil %1$s passt nicht mehr in den Arbeitsspeicher (braucht %2$s, verfügbar %3$s). Die App rechnet mit %4$s, bis wieder genug Speicher frei ist.",
        "Le profil choisi %1$s ne tient plus en mémoire (il nécessite %2$s, %3$s disponibles). L'application utilise %4$s jusqu'à ce qu'assez de mémoire soit à nouveau libre.",
    ),
    (
        "T48",
        "The app needs at least %s of memory.",
        "Mindestbedarf der App: %s Arbeitsspeicher.",
        "L'application nécessite au moins %s de mémoire vive.",
    ),
    (
        "T49",
        "Not enough memory",
        "Zu wenig Arbeitsspeicher",
        "Mémoire vive insuffisante",
    ),
    (
        "T50",
        "The app needs at least %1$s, %2$s is available. It therefore transcribes nothing, Nextcloud keeps running normally. Give the container more memory and restart the backend.",
        "Die App braucht mindestens %1$s, verfügbar sind %2$s. Sie transkribiert deshalb nichts, Nextcloud läuft normal weiter. Mehr Arbeitsspeicher für den Container einstellen und das Backend neu starten.",
        "L'application nécessite au moins %1$s, %2$s sont disponibles. Elle ne transcrit donc rien, Nextcloud continue de fonctionner normalement. Attribuez plus de mémoire vive au conteneur et redémarrez le backend.",
    ),
    (
        "T52",
        "Not saved. This profile has been locked in the meantime.",
        "Nicht gespeichert. Dieses Profil ist inzwischen gesperrt.",
        "Non enregistré. Ce profil a été verrouillé entre-temps.",
    ),
    (
        "T53",
        "Profile, computing time and model state cannot be loaded right now because the backend does not respond. Reload the page later.",
        "Profil, Rechenzeit und Zustand der Modelle sind gerade nicht abrufbar, weil das Backend nicht antwortet. Die Seite später neu laden.",
        "Le profil, le temps de calcul et l'état des modèles ne sont pas disponibles pour le moment, car le backend ne répond pas. Rechargez la page plus tard.",
    ),
    (
        "T54",
        "Computing time",
        "Rechenzeit",
        "Temps de calcul",
    ),
    (
        "T55",
        "Threads for recognition",
        "Threads für die Erkennung",
        "Threads pour la reconnaissance",
    ),
    (
        "T56",
        "Usable CPUs: %1$d. Default and maximum: %2$d. Fewer threads leave more room for Nextcloud, transcription then takes longer.",
        "Nutzbare CPUs: %1$d. Standard und Höchstwert: %2$d. Weniger Threads entlasten Nextcloud, die Transkription dauert dann länger.",
        "Processeurs utilisables\u00a0: %1$d. Valeur par défaut et maximum\u00a0: %2$d. Moins de threads ménagent Nextcloud, la transcription prend alors plus de temps.",
    ),
    (
        "T57",
        "Enter a whole number from 1 to %d.",
        "Eine ganze Zahl von 1 bis %d eingeben.",
        "Saisissez un nombre entier de 1 à %d.",
    ),
    (
        "T58",
        "When to compute",
        "Wann gerechnet wird",
        "Quand calculer",
    ),
    (
        "T59",
        "Always",
        "Immer",
        "Toujours",
    ),
    (
        "T60",
        "Only within a time window",
        "Nur im Zeitfenster",
        "Uniquement dans une plage horaire",
    ),
    (
        "T61",
        "From",
        "Von",
        "De",
    ),
    (
        "T62",
        "To",
        "Bis",
        "À",
    ),
    (
        "T63",
        "Time zone",
        "Zeitzone",
        "Fuseau horaire",
    ),
    (
        "T64",
        "A window across midnight works, for example 22:00 to 06:00. The window applies to every transcription, previews included. At the end of the window the current piece of about 10 minutes of recording is finished, then the app pauses until the next window. New files are registered outside the window too and transcribed later.",
        "Über Mitternacht geht, etwa 22:00 bis 06:00. Das Fenster gilt für jede Transkription, auch für Vorschauen. Am Fensterende wird das laufende Stück von etwa 10 Minuten Aufnahme fertig gerechnet, danach pausiert die App bis zum nächsten Fenster. Neue Dateien werden auch außerhalb erfasst und später transkribiert.",
        "Une plage qui passe minuit est possible, par exemple de 22:00 à 06:00. La plage s'applique à chaque transcription, aperçus compris. À la fin de la plage, le segment en cours d'environ 10 minutes d'enregistrement est terminé, puis l'application fait une pause jusqu'à la plage suivante. Les nouveaux fichiers sont aussi pris en compte en dehors de la plage et transcrits plus tard.",
    ),
    (
        "T65",
        "Start and end must differ.",
        "Beginn und Ende müssen verschieden sein.",
        "Le début et la fin doivent être différents.",
    ),
    (
        "T66",
        "Enter a time.",
        "Eine Uhrzeit eingeben.",
        "Saisissez une heure.",
    ),
    (
        "T67",
        "This time zone is unknown. Choose one from the list.",
        "Diese Zeitzone ist unbekannt. Eine aus der Liste wählen.",
        "Ce fuseau horaire est inconnu. Choisissez-en un dans la liste.",
    ),
    (
        "T68",
        "The time window is open until %s.",
        "Das Zeitfenster ist offen bis %s.",
        "La plage horaire est ouverte jusqu'à %s.",
    ),
    (
        "T69",
        "The time window is closed and opens at %s.",
        "Das Zeitfenster ist geschlossen und öffnet um %s.",
        "La plage horaire est fermée et s'ouvre à %s.",
    ),
    (
        "T70",
        "Save computing time",
        "Rechenzeit speichern",
        "Enregistrer le temps de calcul",
    ),
    (
        "T71",
        "Models and licenses",
        "Modelle und Lizenzen",
        "Modèles et licences",
    ),
    (
        "T72",
        "By NVIDIA, license %1$s. Converted to int8 by k2-fsa/sherpa-onnx, otherwise unchanged.",
        "Von NVIDIA, Lizenz %1$s. Von k2-fsa/sherpa-onnx in eine int8-Fassung umgewandelt, sonst unverändert.",
        "Par NVIDIA, licence %1$s. Converti en int8 par k2-fsa/sherpa-onnx, sans autre modification.",
    ),
    (
        "T73",
        "By the Silero team, license %1$s.",
        "Vom Silero-Team, Lizenz %1$s.",
        "Par l'équipe Silero, licence %1$s.",
    ),
    (
        "T74",
        "By OpenAI, license %1$s. CTranslate2 version by deepdml, license %2$s.",
        "Von OpenAI, Lizenz %1$s. CTranslate2-Fassung von deepdml, Lizenz %2$s.",
        "Par OpenAI, licence %1$s. Version CTranslate2 par deepdml, licence %2$s.",
    ),
    (
        "T75",
        "Weights by OpenAI, license %1$s according to the model card. CTranslate2 version by Systran, license %2$s.",
        "Gewichte von OpenAI, laut Modellkarte Lizenz %1$s. CTranslate2-Fassung von Systran, Lizenz %2$s.",
        "Poids par OpenAI, licence %1$s selon la fiche du modèle. Version CTranslate2 par Systran, licence %2$s.",
    ),
    (
        "T76",
        "Size: %s",
        "Größe: %s",
        "Taille\u00a0: %s",
    ),
    (
        "T77",
        "Included in the image.",
        "Im Image enthalten.",
        "Inclus dans l'image.",
    ),
    (
        "T78",
        "Present, checksum confirmed.",
        "Vorhanden, Prüfsumme bestätigt.",
        "Présent, somme de contrôle confirmée.",
    ),
    (
        "T79",
        "Not needed for the profile %s, not downloaded.",
        "Für das Profil %s nicht nötig, wird nicht geladen.",
        "Inutile pour le profil %s, non téléchargé.",
    ),
    (
        "T80",
        "Waiting for the download.",
        "Wartet auf den Download.",
        "En attente du téléchargement.",
    ),
    (
        "T81",
        "Downloading, %1$s of %2$s.",
        "Wird geladen, %1$s von %2$s.",
        "Téléchargement en cours, %1$s sur %2$s.",
    ),
    (
        "T83a",
        "The downloaded file had a wrong checksum and was discarded. Another attempt follows automatically.",
        "Die geladene Datei hatte eine falsche Prüfsumme und wurde verworfen. Ein neuer Versuch folgt automatisch.",
        "Le fichier téléchargé avait une somme de contrôle incorrecte et a été rejeté. Une nouvelle tentative suivra automatiquement.",
    ),
    (
        "T83b",
        "The placed file has a wrong checksum and is never loaded. Place the correct file, then check it with",
        "Die abgelegte Datei hat eine falsche Prüfsumme und wird nie geladen. Die richtige Datei ablegen und danach prüfen mit",
        "Le fichier déposé a une somme de contrôle incorrecte et ne sera jamais chargé. Déposez le bon fichier, puis vérifiez-le avec",
    ),
    (
        "T84",
        "Missing. In offline mode the app downloads nothing, the file has to be placed.",
        "Fehlt. Im Offline-Modus lädt die App nichts, die Datei muss abgelegt werden.",
        "Manquant. En mode hors ligne, l'application ne télécharge rien, le fichier doit être déposé.",
    ),
    (
        "T85",
        "Download failed. Another attempt follows automatically.",
        "Download gescheitert. Ein neuer Versuch folgt automatisch.",
        "Échec du téléchargement. Une nouvelle tentative suivra automatiquement.",
    ),
    (
        "T86",
        "Not enough storage space for the download. %s of free space is needed.",
        "Zu wenig Speicherplatz für den Download. Nötig sind %s frei.",
        "Espace de stockage insuffisant pour le téléchargement. Il faut %s d'espace libre.",
    ),
    (
        "T87",
        "Offline mode, no connection to the internet",
        "Offline-Modus, keine Verbindung ins Internet",
        "Mode hors ligne, aucune connexion à Internet",
    ),
    (
        "T88",
        "The app then downloads no models. Place the Whisper files for the chosen profile yourself, then check them with",
        "Die App lädt dann keine Modelle. Whisper-Dateien für das gewählte Profil selbst ablegen und danach prüfen mit",
        "L'application ne télécharge alors aucun modèle. Déposez vous-même les fichiers Whisper du profil choisi, puis vérifiez-les avec",
    ),
    (
        "T89",
        "Guide to offline operation",
        "Anleitung zum Offline-Betrieb",
        "Guide du fonctionnement hors ligne",
    ),
    (
        "T90",
        "Set by the deploy option AVS_OFFLINE. It can only be changed in the deploy options of the backend.",
        "Durch die Deploy-Option AVS_OFFLINE gesetzt. Ändern nur über die Deploy-Optionen des Backends.",
        "Défini par l'option de déploiement AVS_OFFLINE. Modifiable uniquement dans les options de déploiement du backend.",
    ),
    (
        "T91",
        "Other components",
        "Weitere Bestandteile",
        "Autres composants",
    ),
    (
        "T92",
        "FFmpeg for decoding, LGPL build, license %1$s.",
        "FFmpeg zum Dekodieren, LGPL-Build, Lizenz %1$s.",
        "FFmpeg pour le décodage, build LGPL, licence %1$s.",
    ),
    (
        "T93",
        "PyAV ships its own FFmpeg libraries with the codecs libx264 and libx265, license %1$s. The app does not decode with them, they are only in the image as a dependency of faster-whisper.",
        "PyAV bringt eigene FFmpeg-Bibliotheken mit den Codecs libx264 und libx265 mit, Lizenz %1$s. Die App dekodiert damit nicht, sie liegen nur als Abhängigkeit von faster-whisper im Image.",
        "PyAV fournit ses propres bibliothèques FFmpeg avec les codecs libx264 et libx265, licence %1$s. L'application ne les utilise pas pour décoder, elles ne se trouvent dans l'image qu'en tant que dépendance de faster-whisper.",
    ),
    (
        "T94",
        "All third-party licenses in THIRD-PARTY.md",
        "Alle Drittlizenzen in THIRD-PARTY.md",
        "Toutes les licences tierces dans THIRD-PARTY.md",
    ),
    (
        "T95",
        "The download progress could not be refreshed. Shown is the last known state.",
        "Der Download-Stand konnte nicht aktualisiert werden. Angezeigt ist der letzte bekannte Stand.",
        "L'avancement du téléchargement n'a pas pu être actualisé. L'état affiché est le dernier connu.",
    ),
    (
        "T96",
        "%s GB",
        "%s GB",
        "%s Go",
    ),
)

IDS = [row[0] for row in ROWS]


def _catalogue(language: str) -> dict[str, str]:
    return json.loads((PHP_L10N / f"{language}.json").read_text(encoding="utf-8"))["translations"]


def _js_translations(language: str) -> dict[str, str]:
    text = (PHP_L10N / f"{language}.js").read_text(encoding="utf-8")
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


def test_the_table_has_sixty_rows_from_t36_to_t96() -> None:
    assert len(ROWS) == 60
    assert len(set(IDS)) == 60
    numbers = {int(ident[1:3]) for ident in IDS}
    assert numbers == set(range(36, 97)) - {51, 82}
    assert {"T83a", "T83b"} <= set(IDS)
    assert len({row[1] for row in ROWS}) == 60  # every key once


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_text_stands_word_for_word_in_the_json_and_the_js(language: str) -> None:
    column = {"de": 2, "de_DE": 2, "en": 1, "fr": 3}[language]
    catalogue = _catalogue(language)
    twin = _js_translations(language)
    missing = [ident for ident, *texts in ROWS if catalogue.get(texts[0]) != texts[column - 1]]
    assert missing == []
    assert all(twin.get(row[1]) == row[column] for row in ROWS)


def test_french_carries_no_break_spaces_before_the_high_signs() -> None:
    for ident, _en, _de, fr in ROWS:
        assert not PLAIN_SPACE_BEFORE.search(fr), ident
    flagged = {row[0]: row[3] for row in ROWS if row[0] in {"T37", "T45", "T56", "T76"}}
    assert all(f"{NBSP}:" in text for text in flagged.values())
    assert flagged["T56"].count(f"{NBSP}:") == 2


@pytest.mark.parametrize("ident", ["T48", "T50"])
def test_the_minimum_memory_is_never_a_number_in_the_catalogue(ident: str) -> None:
    row = next(row for row in ROWS if row[0] == ident)
    for text in row[1:]:
        assert not re.search(r"\d", PLACEHOLDER.sub("", text)), text


def test_no_phase5_text_carries_a_dash_an_emoji_or_a_bitv_claim() -> None:
    for row in ROWS:
        for text in row[1:]:
            assert not any(dash in text for dash in DASHES), text
            assert not EMOJI.search(text), text
            assert "bitv" not in text.lower(), text


def test_every_value_keeps_the_placeholders_of_its_key() -> None:
    for _ident, en, de, fr in ROWS:
        wanted = sorted(PLACEHOLDER.findall(en))
        assert sorted(PLACEHOLDER.findall(de)) == wanted, en
        assert sorted(PLACEHOLDER.findall(fr)) == wanted, en


def test_the_kept_keys_are_unchanged() -> None:
    assert _catalogue("de")["Saved"] == "Gespeichert"
    assert _catalogue("fr")["Not saved. Try again."] == "Non enregistré. Réessayez."
    assert _catalogue("de")["Checking…"] == "Wird geprüft…"
