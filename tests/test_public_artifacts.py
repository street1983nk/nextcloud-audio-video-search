"""No key, token or private material in anything this repository publishes.

A lean form of Findling's public artifact gate. It scans every tracked file, not
a list of names, so a file added tomorrow is checked on the day it arrives. The
app's private key lives outside the repository
(C:\\Users\\Student\\.nextcloud\\certificates\\<app_id>.key) and in CI only as the
secret APP_PRIVATE_KEY.

The prefixes the gate looks for are assembled from halves, so this file does not
carry what it keeps out.
"""

import re

from tests.conftest import REPO_ROOT
from tests.test_public_texts import BINARY_SUFFIXES, tracked_files

PEM_PRIVATE_KEY = re.compile("-----BEGIN(?: [A-Z0-9]+)* " + "PRIVATE KEY-----")
SSH_KEY = re.compile(r"ssh-(?:rsa|ed25519)\s+" + "AAAA" + r"[0-9A-Za-z+/=]{20,}")
CLOUD_KEY = re.compile(r"\b(?:" + "AK" + "IA|AS" + "IA)" + r"[0-9A-Z]{12,}\b")
GITHUB_TOKEN = re.compile(r"\b(?:" + "gh" + "[pousr]_[0-9A-Za-z]{30,}|" + "github" + "_pat_[0-9A-Za-z_]{30,})")
STORE_TOKEN_LINE = re.compile(r"(?i)Authorization:\s*Token\s+[0-9a-f]{20,}")
FAMILIES = {
    "private key": PEM_PRIVATE_KEY,
    "ssh key": SSH_KEY,
    "cloud access key": CLOUD_KEY,
    "github token": GITHUB_TOKEN,
    "store token": STORE_TOKEN_LINE,
}
FORBIDDEN_SUFFIXES = (".key", ".pem", ".p12", ".csr")


def secret_findings(name: str, source: str) -> list[str]:
    return [f"{name}: {family}" for family, pattern in FAMILIES.items() if pattern.search(source)]


def test_no_tracked_file_is_key_material() -> None:
    files = tracked_files()

    assert [path.name for path in files if path.name.endswith(FORBIDDEN_SUFFIXES)] == []


def test_no_tracked_file_carries_a_secret() -> None:
    findings = []
    for path in tracked_files():
        if path.suffix in BINARY_SUFFIXES:
            continue
        findings += secret_findings(path.relative_to(REPO_ROOT).as_posix(), path.read_text(encoding="utf-8"))

    assert findings == []


def test_gitignore_and_dockerignore_keep_keys_out() -> None:
    for name in (".gitignore", ".dockerignore"):
        lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
        assert "*.key" in lines, name
        assert "*.pem" in lines, name


def test_every_family_fires_on_a_sample() -> None:
    samples = {
        "private key": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "ssh key": "ssh-ed25519 " + "AAAA" + "C3NzaC1lZDI1NTE5AAAAIExample",
        "cloud access key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "github token": "gh" + "p_" + "a" * 36,
        "store token": "Authorization: Token " + "0123456789abcdef" * 2,
    }
    for family, sample in samples.items():
        assert secret_findings("s", sample) == [f"s: {family}"], family

    assert secret_findings("s", "APP_PRIVATE_KEY: ${{ secrets.APP_PRIVATE_KEY }}") == []
