import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cognishield.graph import build_graph
from cognishield.package_diff import diff_packages
from cognishield.patcher import make_patch, validate_patch
from cognishield.workflow_parser import parse_workflows

REPO = os.path.join(os.path.dirname(__file__), "..")
OLD = os.path.join(REPO, "vendor", "safe-pad-1.0.0.tgz")
NEW = os.path.join(REPO, "vendor", "safe-pad-1.0.1.tgz")


def test_parser_finds_both_jobs():
    jobs = {j.job_name: j for j in parse_workflows(REPO) if j.workflow_file.endswith("ci.yml")}
    assert jobs["build"].has_secrets
    assert jobs["build"].permissions == "write-all"
    assert not jobs["build"].ignore_scripts
    assert jobs["lint"].ignore_scripts
    assert not jobs["lint"].has_secrets


def test_diff_flags_new_postinstall_and_payload():
    diff = diff_packages(OLD, NEW)
    assert "postinstall" in diff.new_lifecycle_scripts
    assert diff.is_suspicious
    assert any("127.0.0.1" in d or "http" in d for d in diff.decoded_payloads)


def test_build_job_is_reachable_lint_job_is_not():
    diff = diff_packages(OLD, NEW)
    jobs = {j.job_name: j for j in parse_workflows(REPO) if j.workflow_file.endswith("ci.yml")}
    _, build_result = build_graph(diff, jobs["build"])
    _, lint_result = build_graph(diff, jobs["lint"])
    assert build_result.reachable and build_result.severity >= 80
    assert not lint_result.reachable and lint_result.severity < 20


def test_patch_is_valid_and_minimal():
    path = os.path.join(REPO, ".github", "workflows", "ci.yml")
    with open(path) as f:
        original = f.read()
    patched = make_patch(path, "build")
    ok, reason = validate_patch(original, patched)
    assert ok, reason
    assert "--ignore-scripts" in patched
    assert "contents: read" in patched
