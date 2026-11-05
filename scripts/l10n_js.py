"""Write l10n/<lang>.js out of l10n/<lang>.json, the Nextcloud catalogue pair.

The JSON file is the source; Nextcloud's PHP side reads it, the browser reads the
.js twin. AppAPI copies the whole l10n/ directory out of the release archive into
the apps directory at installation time, so both files ship in the archive.

usage: uv run python scripts/l10n_js.py [--check]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L10N = ROOT / "l10n"


def app_id() -> str:
    """The app id out of appinfo/info.xml, read without an XML parser on purpose."""
    text = (ROOT / "appinfo" / "info.xml").read_text(encoding="utf-8")
    return text.split("<id>", 1)[1].split("</id>", 1)[0].strip()


def render(app: str, catalogue: dict[str, object]) -> str:
    """The .js twin of one catalogue, in the layout Nextcloud's own tooling writes."""
    translations = json.dumps(catalogue["translations"], ensure_ascii=False, indent=4)
    plural = json.dumps(catalogue["pluralForm"], ensure_ascii=False)
    return f'OC.L10N.register(\n    "{app}",\n    {translations},\n{plural});\n'


def main(argv: list[str]) -> int:
    """Write every .js twin, or with --check report the ones that drifted."""
    check = "--check" in argv
    app = app_id()
    drifted = []
    for source in sorted(L10N.glob("*.json")):
        wanted = render(app, json.loads(source.read_text(encoding="utf-8")))
        target = source.with_suffix(".js")
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != wanted:
            drifted.append(target.name)
            if not check:
                target.write_text(wanted, encoding="utf-8", newline="\n")
    if check and drifted:
        print("out of date, run scripts/l10n_js.py:", ", ".join(drifted))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
