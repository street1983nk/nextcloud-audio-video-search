"""The parsers on the real downloads of the end-to-end run (plan 04-14, EXP-01, EXP-02, EXP-04).

The step @phase4 of deploy-harp.yml saves every SRT, VTT and TXT the browser
downloaded (D1 in plan 04-17) into AVS_DOWNLOADS_DIR and runs this file with
CI=true afterwards. Without the variable (python.yml, a laptop) the test skips:
there are no downloads there. With it, a missing folder or a folder without at
least one .srt, one .vtt and one .txt fails, never skips (T-04-59).

For every file: the name is ``<name>.<de|en|fr>.<srt|vtt|txt>``; SRT and VTT
pass check_srt/check_vtt and ffmpeg (tests/subtitle_checkers.py, plan 04-04;
ffmpeg over find_tool, so a missing ffmpeg fails under CI=true); line 2 of a TXT
is T35 in one of the three catalogue languages (php/l10n); no file says "BITV"
(EXP-04 on the file contents). The self tests at the end run the same check on
folders in tmp_path, never on the environment of the session.
"""

import json
import os
import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from tests.subtitle_checkers import SubtitleCheckError, check_ffmpeg, check_srt, check_vtt

DOWNLOADS_ENV = "AVS_DOWNLOADS_DIR"
NAME = re.compile(r"^.+\.(de|en|fr)\.(srt|vtt|txt)$")
FORMATS = ("srt", "vtt", "txt")
# The source string of T35 (UI-SPEC 04); the catalogues carry its German and French text.
T35_SOURCE = "Subtitle draft, created automatically and not reviewed."
CATALOGUES = ("de", "fr")
FORBIDDEN = "BITV"


def t35_texts() -> frozenset[str]:
    """T35 in English, German and French, read from php/l10n like the page reads it."""
    texts = {T35_SOURCE}
    for language in CATALOGUES:
        catalogue = json.loads((REPO_ROOT / "php" / "l10n" / f"{language}.json").read_text(encoding="utf-8"))
        texts.add(catalogue["translations"][T35_SOURCE])
    return frozenset(texts)


def by_format(folder: Path) -> dict[str, list[Path]]:
    """The downloads of the folder by format; a missing folder, a stray name or a missing format fails."""
    if not folder.is_dir():
        pytest.fail(f"{DOWNLOADS_ENV} points at no folder: the step @phase4 saved no download")
    found: dict[str, list[Path]] = {fmt: [] for fmt in FORMATS}
    for path in sorted(folder.iterdir()):
        match = NAME.fullmatch(path.name)
        if match is None or not path.is_file():
            pytest.fail(f"{path.name}: not a download named <name>.<de|en|fr>.<srt|vtt|txt>")
        found[match.group(2)].append(path)
    absent = [fmt for fmt in FORMATS if not found[fmt]]
    if absent:
        pytest.fail(f"no .{', .'.join(absent)} among the downloads: every format has to be proven on a real file")
    return found


def check_download(path: Path, t35: frozenset[str]) -> None:
    """One downloaded file: parsers and ffmpeg for subtitles, T35 for text, no BITV anywhere."""
    text = path.read_bytes().decode("utf-8")
    if FORBIDDEN in text:
        pytest.fail(f"{path.name} says {FORBIDDEN} (EXP-04)")
    suffix = path.suffix
    try:
        if suffix == ".srt":
            check_srt(text)
            check_ffmpeg(text, ".srt")
        elif suffix == ".vtt":
            check_vtt(text)
            check_ffmpeg(text, ".vtt")
    except SubtitleCheckError as error:
        pytest.fail(f"{path.name}: {error}")
    if suffix == ".txt":
        lines = text.splitlines()
        if len(lines) < 2 or lines[1] not in t35:
            pytest.fail(f"{path.name}: line 2 is not T35 in de, en or fr")


def check_folder(folder: Path) -> int:
    """Every download of the folder; answers how many files passed."""
    t35 = t35_texts()
    files = [path for paths in by_format(folder).values() for path in paths]
    for path in files:
        check_download(path, t35)
    return len(files)


def test_the_real_downloads_pass_the_parsers() -> None:
    value = os.environ.get(DOWNLOADS_ENV, "").strip()
    if not value:
        pytest.skip(f"{DOWNLOADS_ENV} is not set: only the step @phase4 of deploy-harp.yml has downloads")
    assert check_folder(Path(value)) >= len(FORMATS)


# -- self tests: the check on folders of this test, not on the session environment --

VTT = (
    "WEBVTT\n\nNOTE\nSubtitle draft, created automatically and not reviewed.\n\n"
    "00:00:01.000 --> 00:00:02.500\nHallo Welt\n"
)
SRT = "1\n00:00:01,000 --> 00:00:02,500\nHallo Welt\n"
TXT = "sitzung.wav\nUntertitel-Entwurf, automatisch erstellt und nicht geprüft.\n\nHallo Welt\n"


def _folder(tmp_path: Path, files: dict[str, str]) -> Path:
    folder = tmp_path / "downloads"
    folder.mkdir()
    for name, text in files.items():
        (folder / name).write_bytes(text.encode("utf-8"))
    return folder


def _complete() -> dict[str, str]:
    return {"sitzung.de.srt": SRT, "sitzung.de.vtt": VTT, "Sitzung März.de.txt": TXT}


def test_t35_is_read_in_three_languages() -> None:
    assert t35_texts() == {
        T35_SOURCE,
        "Untertitel-Entwurf, automatisch erstellt und nicht geprüft.",
        "Brouillon de sous-titres, créé automatiquement et non vérifié.",
    }


def test_an_empty_folder_fails(tmp_path: Path) -> None:
    with pytest.raises(pytest.fail.Exception, match=r"no \.srt, \.vtt, \.txt"):
        check_folder(_folder(tmp_path, {}))


def test_a_missing_folder_fails(tmp_path: Path) -> None:
    with pytest.raises(pytest.fail.Exception, match="points at no folder"):
        check_folder(tmp_path / "never-made")


def test_a_folder_without_vtt_fails(tmp_path: Path) -> None:
    files = _complete()
    del files["sitzung.de.vtt"]
    with pytest.raises(pytest.fail.Exception, match=r"no \.vtt"):
        check_folder(_folder(tmp_path, files))


def test_a_stray_name_fails(tmp_path: Path) -> None:
    files = {**_complete(), "sitzung.vtt": VTT}
    with pytest.raises(pytest.fail.Exception, match=r"sitzung\.vtt"):
        check_folder(_folder(tmp_path, files))


def test_a_complete_folder_passes(tmp_path: Path) -> None:
    assert check_folder(_folder(tmp_path, _complete())) == len(FORMATS)


def test_a_txt_without_t35_fails(tmp_path: Path) -> None:
    files = {**_complete(), "Sitzung März.de.txt": "sitzung.wav\nAutomatisch erstellt.\n\nHallo Welt\n"}
    with pytest.raises(pytest.fail.Exception, match="line 2 is not T35"):
        check_folder(_folder(tmp_path, files))


def test_bitv_in_a_download_fails(tmp_path: Path) -> None:
    files = {**_complete(), "sitzung.de.srt": SRT.replace("Hallo Welt", "BITV-konform")}
    with pytest.raises(pytest.fail.Exception, match="BITV"):
        check_folder(_folder(tmp_path, files))


def test_a_broken_vtt_fails(tmp_path: Path) -> None:
    files = {**_complete(), "sitzung.de.vtt": VTT.replace("-->", "->")}
    with pytest.raises(pytest.fail.Exception, match=r"sitzung\.de\.vtt"):
        check_folder(_folder(tmp_path, files))
