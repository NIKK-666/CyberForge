"""Step 9: Pipeline entrypoint.
Wires steps 1-8 together: parse workflows -> diff package -> build graph ->
(maybe) call the LLM -> write the PR comment + exit code for the check.
Called by the GitHub Action with: python -m forgesentry.main <repo_dir> <old.tgz> <new.tgz>
"""
from __future__ import annotations

import sys

from forgesentry.graph import build_graph
from forgesentry.llm_layer import judge
from forgesentry.package_diff import diff_packages
from forgesentry.report import build_comment
from forgesentry.workflow_parser import parse_workflows


def run(repo_dir: str, old_tarball: str, new_tarball: str) -> int:
    diff = diff_packages(old_tarball, new_tarball)
    jobs = [j for j in parse_workflows(repo_dir) if j.installs_deps]

    any_reachable = False
    comments = []

    for job in jobs:
        g, result = build_graph(diff, job)
        verdict = None
        if result.reachable:
            any_reachable = True
            verdict = judge(
                diff.name, diff.old_version, diff.new_version, result.reason,
                result.severity, diff.new_lifecycle_scripts, diff.risky_calls, diff.decoded_payloads,
            )
        comments.append(build_comment(diff, result, verdict))

    full_comment = "\n\n---\n\n".join(comments)
    with open("forgesentry_comment.md", "w") as f:
        f.write(full_comment)

    print(full_comment)
    # Non-zero exit = failing check in CI
    return 1 if any_reachable else 0


if __name__ == "__main__":
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    old_tarball = sys.argv[2]
    new_tarball = sys.argv[3]
    sys.exit(run(repo_dir, old_tarball, new_tarball))
