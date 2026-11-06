"""Write <root>/<lang>.js out of <root>/<lang>.json, the Nextcloud catalogue pair.

The JSON file is the source; Nextcloud's PHP side reads it, the browser reads the
.js twin. Both halves of the app carry a catalogue directory (backend/l10n for
the ExApp, php/l10n for the PHP app); the app id of each comes out of the
appinfo/info.xml beside it, so one root never registers under the other's id.

usage: uv run python scripts/l10n_js.py [--check] [--root DIR]...
Without --root the backend catalogues are meant (backend/l10n).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "backend" / "l10n"


def app_id(root: Path) -> str:
    """The app id out of the info.xml beside a catalogue root, read without an XML parser on purpose."""
    text = (root.parent / "appinfo" / "info.xml").read_text(encoding="utf-8")
    return text.split("<id>", 1)[1].split("</id>", 1)[0].strip()


def render(app: str, catalogue: dict[str, object]) -> str:
    """The .js twin of one catalogue, in the layout Nextcloud's own tooling writes."""
    translations = json.dumps(catalogue["translations"], ensure_ascii=False, indent=4)
    plural = json.dumps(catalogue["pluralForm"], ensure_ascii=False)
    return f'OC.L10N.register(\n    "{app}",\n    {translations},\n{plural});\n'


def roots(argv: list[str]) -> list[Path]:
    """Every catalogue root named with --root, or the backend default."""
    named = [Path(argv[index + 1]) for index, arg in enumerate(argv[:-1]) if arg == "--root"]
    return [path if path.is_absolute() else Path.cwd() / path for path in named] or [DEFAULT_ROOT]


def main(argv: list[str]) -> int:
    """Write every .js twin, or with --check report the ones that drifted."""
    check = "--check" in argv
    drifted = []
    for root in roots(argv):
        app = app_id(root)
        for source in sorted(root.glob("*.json")):
            wanted = render(app, json.loads(source.read_text(encoding="utf-8")))
            target = source.with_suffix(".js")
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != wanted:
                drifted.append(target.as_posix())
                if not check:
                    target.write_text(wanted, encoding="utf-8", newline="\n")
    if check and drifted:
        print("out of date, run scripts/l10n_js.py:", ", ".join(drifted))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
