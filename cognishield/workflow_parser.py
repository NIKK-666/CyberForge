"""Step 3: Workflow Parser.
Reads .github/workflows/*.yml and extracts, per job: trigger, permissions,
secrets referenced, install commands, and whether scripts are ignored.
Pure deterministic parsing -- no AI, no code execution.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

import yaml

SECRET_RE = re.compile(r"secrets\.([A-Za-z0-9_]+)")
INSTALL_RE = re.compile(r"\bnpm\s+(ci|install|i)\b")


@dataclass
class JobInfo:
    workflow_file: str
    job_name: str
    triggers: list[str]
    permissions: str  # "write-all" | "read" | "none" | "default" | explicit dict summary
    secrets_used: list[str] = field(default_factory=list)
    installs_deps: bool = False
    ignore_scripts: bool = False
    checks_out_pr_head: bool = False

    @property
    def has_secrets(self) -> bool:
        return len(self.secrets_used) > 0

    @property
    def is_privileged(self) -> bool:
        return self.permissions in ("write-all",) or self.has_secrets


def _triggers(doc: dict) -> list[str]:
    on = doc.get("on", doc.get(True, {}))  # PyYAML can parse bare `on:` as True
    if isinstance(on, str):
        return [on]
    if isinstance(on, list):
        return on
    if isinstance(on, dict):
        return list(on.keys())
    return []


def _job_permissions(doc: dict, job: dict) -> str:
    perm = job.get("permissions", doc.get("permissions"))
    if perm == "write-all":
        return "write-all"
    if isinstance(perm, dict):
        if any(v == "write" for v in perm.values()):
            return "write-all"
        return "read"
    if perm is None:
        return "default"
    return str(perm)


def _scan_steps(job: dict) -> tuple[list[str], bool, bool, bool]:
    secrets_used: list[str] = []
    installs = False
    ignore_scripts = False
    checks_out_head = False
    for step in job.get("steps", []):
        run = step.get("run", "") or ""
        env = step.get("with", {}) or {}
        secrets_used += SECRET_RE.findall(run)
        for v in (step.get("env", {}) or {}).values():
            if isinstance(v, str):
                secrets_used += SECRET_RE.findall(v)
        if "secrets." in str(step.get("with", {})):
            secrets_used += SECRET_RE.findall(str(step.get("with", {})))
        if INSTALL_RE.search(run):
            installs = True
            if "--ignore-scripts" in run:
                ignore_scripts = True
        if step.get("uses", "").startswith("actions/checkout"):
            ref = str(env.get("ref", ""))
            if "pull_request.head" in ref:
                checks_out_head = True
    return sorted(set(secrets_used)), installs, ignore_scripts, checks_out_head


def parse_workflows(repo_path: str) -> list[JobInfo]:
    jobs: list[JobInfo] = []
    pattern = os.path.join(repo_path, ".github", "workflows", "*.y*ml")
    for path in sorted(glob.glob(pattern)):
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        triggers = _triggers(doc)
        for job_name, job in (doc.get("jobs") or {}).items():
            perm = _job_permissions(doc, job)
            secrets_used, installs, ignore_scripts, checks_out_head = _scan_steps(job)
            jobs.append(
                JobInfo(
                    workflow_file=os.path.relpath(path, repo_path),
                    job_name=job_name,
                    triggers=triggers,
                    permissions=perm,
                    secrets_used=secrets_used,
                    installs_deps=installs,
                    ignore_scripts=ignore_scripts,
                    checks_out_pr_head=checks_out_head,
                )
            )
    return jobs


if __name__ == "__main__":
    import json
    import sys

    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    result = [j.__dict__ for j in parse_workflows(repo)]
    print(json.dumps(result, indent=2))
