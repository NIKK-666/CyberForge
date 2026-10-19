"""Step 8a: Patch generation + deterministic validation.
The LLM only *suggests* a fix in plain English (suggested_fix). The actual
edit applied to the repo is a small, surgical TEXT patch produced by plain
code -- never a full YAML round-trip, which can silently reformat or corrupt
the file. validate_patch() then re-checks the result line by line.
"""
from __future__ import annotations

import re

import yaml

INSTALL_LINE_RE = re.compile(r"^(\s*run:\s*npm\s+(?:ci|install|i))\s*$")


def make_patch(workflow_path: str, job_name: str) -> str:
    """Returns the NEW full file content with the vulnerable job hardened:
    - adds `permissions: {contents: read}` under the target job
    - appends `--ignore-scripts` to its npm install/ci line
    Implemented as line-level text edits, so every other line is untouched."""
    with open(workflow_path) as f:
        lines = f.readlines()

    doc = yaml.safe_load("".join(lines))
    job_indent = None
    in_target_job = False
    out: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        m = re.match(rf"^(\s\s)({re.escape(job_name)}):\s*$", stripped)
        if re.match(r"^\s\sjobs:\s*$", stripped) is None and m and job_indent is None:
            # only treat as job header if previous non-target context is `jobs:` block;
            # for our single-file demo this simple check is sufficient
            pass
        if stripped.strip() == f"{job_name}:" and stripped.startswith("  ") and not stripped.startswith("    "):
            in_target_job = True
            job_indent = len(stripped) - len(stripped.lstrip())
            out.append(line)
            out.append(" " * (job_indent + 2) + "permissions:\n")
            out.append(" " * (job_indent + 4) + "contents: read\n")
            continue
        if in_target_job and stripped.strip() and not stripped.startswith(" " * (job_indent + 1)):
            in_target_job = False  # left the job block (dedent back to job_indent or less)

        install_match = INSTALL_LINE_RE.match(stripped)
        if in_target_job and install_match:
            out.append(install_match.group(1) + " --ignore-scripts\n")
            continue

        out.append(line)

    return "".join(out)


def validate_patch(original_text: str, patched_text: str) -> tuple[bool, str]:
    """Deterministic guardrail: the patch must
    (1) parse as valid YAML with the same job names as before, and
    (2) differ from the original ONLY by added permissions/contents lines
        or an appended --ignore-scripts flag."""
    try:
        orig_doc = yaml.safe_load(original_text)
        patched_doc = yaml.safe_load(patched_text)
    except yaml.YAMLError as e:
        return False, f"invalid YAML: {e}"

    if set(orig_doc.get("jobs", {})) != set(patched_doc.get("jobs", {})):
        return False, "patch changed the set of jobs"

    orig_lines = original_text.splitlines()
    new_lines = patched_text.splitlines()

    added = [l for l in new_lines if l not in orig_lines]
    removed = [l for l in orig_lines if l not in new_lines]

    for line in added:
        s = line.strip()
        allowed = s in ("permissions:", "contents: read") or s.endswith("--ignore-scripts")
        if not allowed:
            return False, f"patch adds an unexpected line: {s!r}"

    for line in removed:
        s = line.strip()
        allowed = s.startswith("run: npm") and "--ignore-scripts" not in s
        if not allowed:
            return False, f"patch removes an unexpected line: {s!r}"

    return True, "ok"


if __name__ == "__main__":
    path = ".github/workflows/ci.yml"
    with open(path) as f:
        original = f.read()
    patched = make_patch(path, "build")
    ok, reason = validate_patch(original, patched)
    print("valid:", ok, "--", reason)
    print("\n--- patched file ---\n")
    print(patched)
