"""Step 4: npm Package Diff + Deterministic Unpacking.
Reads two local tarballs (old/new version of a package), compares their
lifecycle scripts and source, and decodes any base64 payloads it finds.
No code from the package is ever executed here.
"""
from __future__ import annotations

import base64
import io
import json
import re
import tarfile
from dataclasses import dataclass, field

LIFECYCLE_KEYS = ("preinstall", "install", "postinstall")
RISKY_CALL_RE = re.compile(r"\b(child_process|require\(['\"]http['\"]\)|eval\s*\(|process\.env)\b")
B64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


@dataclass
class PackageDiff:
    name: str
    old_version: str
    new_version: str
    new_lifecycle_scripts: dict = field(default_factory=dict)
    risky_calls: list[str] = field(default_factory=list)
    decoded_payloads: list[str] = field(default_factory=list)

    @property
    def has_new_lifecycle_script(self) -> bool:
        return bool(self.new_lifecycle_scripts)

    @property
    def is_suspicious(self) -> bool:
        return self.has_new_lifecycle_script and (bool(self.risky_calls) or bool(self.decoded_payloads))


def _read_tarball(path: str) -> dict[str, str]:
    """Return {relative_path: text_content} for every file in a package/ tarball."""
    files: dict[str, str] = {}
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name.split("package/", 1)[-1]
            data = tar.extractfile(member).read()
            try:
                files[name] = data.decode("utf-8", errors="replace")
            except Exception:
                files[name] = ""
    return files


def _decode_base64_strings(source: str) -> list[str]:
    decoded = []
    for match in B64_RE.findall(source):
        try:
            text = base64.b64decode(match + "===").decode("utf-8", errors="strict")
            if text.isprintable():
                decoded.append(text)
        except Exception:
            continue
    return decoded


def diff_packages(old_tarball: str, new_tarball: str) -> PackageDiff:
    old_files = _read_tarball(old_tarball)
    new_files = _read_tarball(new_tarball)

    old_pkg = json.loads(old_files.get("package.json", "{}"))
    new_pkg = json.loads(new_files.get("package.json", "{}"))

    old_scripts = {k: v for k, v in old_pkg.get("scripts", {}).items() if k in LIFECYCLE_KEYS}
    new_scripts = {k: v for k, v in new_pkg.get("scripts", {}).items() if k in LIFECYCLE_KEYS}
    added_scripts = {k: v for k, v in new_scripts.items() if k not in old_scripts}

    all_new_source = "\n".join(text for name, text in new_files.items() if name.endswith(".js"))
    risky = sorted(set(RISKY_CALL_RE.findall(all_new_source)))
    decoded = []
    for text in _decode_base64_strings(all_new_source):
        decoded.append(text)
        # payload may itself contain more risky calls once decoded
        risky += sorted(set(RISKY_CALL_RE.findall(text)))
    risky = sorted(set(risky))

    return PackageDiff(
        name=new_pkg.get("name", "unknown"),
        old_version=old_pkg.get("version", "?"),
        new_version=new_pkg.get("version", "?"),
        new_lifecycle_scripts=added_scripts,
        risky_calls=risky,
        decoded_payloads=decoded,
    )


if __name__ == "__main__":
    import sys
    from dataclasses import asdict

    old, new = sys.argv[1], sys.argv[2]
    print(json.dumps(asdict(diff_packages(old, new)), indent=2))
