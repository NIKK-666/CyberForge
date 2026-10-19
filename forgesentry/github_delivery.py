"""Step 10: GitHub delivery -- PR comment, failing check, and /shield fix.
Uses the GitHub REST API directly (requests) so there's no extra SDK
dependency; swap in PyGithub if you prefer.
Requires env vars: GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_EVENT_PATH (all
set automatically inside a GitHub Action).
"""
from __future__ import annotations

import json
import os

import requests

API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def post_pr_comment(repo: str, pr_number: int, body: str) -> None:
    url = f"{API}/repos/{repo}/issues/{pr_number}/comments"
    r = requests.post(url, headers=_headers(), json={"body": body})
    r.raise_for_status()


def set_check_status(repo: str, sha: str, passed: bool, summary: str) -> None:
    url = f"{API}/repos/{repo}/statuses/{sha}"
    r = requests.post(
        url, headers=_headers(),
        json={
            "state": "success" if passed else "failure",
            "context": "ForgeSentry",
            "description": summary[:140],
        },
    )
    r.raise_for_status()


def commenter_has_write_access(repo: str, username: str) -> bool:
    url = f"{API}/repos/{repo}/collaborators/{username}/permission"
    r = requests.get(url, headers=_headers())
    if r.status_code != 200:
        return False
    perm = r.json().get("permission", "")
    return perm in ("admin", "write", "maintain")


def open_fix_pr(repo: str, base_branch: str, head_branch: str, title: str, body: str, file_path: str, file_content: str) -> str:
    """Creates a branch from base, commits the patched file, opens a PR. Returns PR URL."""
    h = _headers()

    base_ref = requests.get(f"{API}/repos/{repo}/git/ref/heads/{base_branch}", headers=h).json()
    base_sha = base_ref["object"]["sha"]

    requests.post(
        f"{API}/repos/{repo}/git/refs", headers=h,
        json={"ref": f"refs/heads/{head_branch}", "sha": base_sha},
    ).raise_for_status()

    existing = requests.get(f"{API}/repos/{repo}/contents/{file_path}?ref={base_branch}", headers=h).json()
    requests.put(
        f"{API}/repos/{repo}/contents/{file_path}", headers=h,
        json={
            "message": "ForgeSentry: harden workflow against reachable secret exfiltration",
            "content": __import__("base64").b64encode(file_content.encode()).decode(),
            "sha": existing["sha"],
            "branch": head_branch,
        },
    ).raise_for_status()

    pr = requests.post(
        f"{API}/repos/{repo}/pulls", headers=h,
        json={"title": title, "head": head_branch, "base": base_branch, "body": body},
    ).json()
    return pr["html_url"]


def handle_shield_fix_comment() -> None:
    """Entry point for the issue_comment workflow. Reads the GitHub event
    payload, checks permission, validates the patch, opens the fix PR."""
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)

    comment_body = event["comment"]["body"].strip()
    if comment_body != "/shield fix":
        return

    repo = os.environ["GITHUB_REPOSITORY"]
    username = event["comment"]["user"]["login"]
    pr_number = event["issue"]["number"]

    if not commenter_has_write_access(repo, username):
        post_pr_comment(repo, pr_number, f"@{username} you need write access to run `/shield fix`.")
        return

    from forgesentry.patcher import make_patch, validate_patch

    workflow_path = ".github/workflows/ci.yml"
    with open(workflow_path) as f:
        original = f.read()
    patched = make_patch(workflow_path, "build")
    ok, reason = validate_patch(original, patched)

    if not ok:
        post_pr_comment(repo, pr_number, f"⚠️ Could not safely generate a fix: {reason}")
        return

    pr_url = open_fix_pr(
        repo=repo, base_branch="main", head_branch=f"forgesentry/fix-{pr_number}",
        title="ForgeSentry: harden CI workflow",
        body="Automated fix: requires `contents: read` and `--ignore-scripts` for the install job.\n\nGenerated in response to `/shield fix`.",
        file_path=workflow_path, file_content=patched,
    )
    post_pr_comment(repo, pr_number, f"✅ Opened fix PR: {pr_url}")


if __name__ == "__main__":
    handle_shield_fix_comment()
