"""Step 5: Reachability Graph.
Builds a NetworkX graph: PackageDelta -> InstallStep -> Job -> Secrets/Permissions.
Decides if a suspicious package change can actually reach something valuable,
and computes a severity score. This is the core of CogniShield.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from cognishield.package_diff import PackageDiff
from cognishield.workflow_parser import JobInfo


@dataclass
class ReachabilityResult:
    job_name: str
    reachable: bool
    reason: str
    severity: int  # 0-100
    path: list[str]


def _severity(diff: PackageDiff, job: JobInfo, reachable: bool) -> int:
    if not reachable:
        return 5 if diff.has_new_lifecycle_script else 0
    score = 40  # base: scripts will run
    if job.has_secrets:
        score += 30
    if job.permissions == "write-all":
        score += 15
    if diff.risky_calls:
        score += 10
    if diff.decoded_payloads:
        score += 5
    return min(score, 100)


def build_graph(diff: PackageDiff, job: JobInfo) -> tuple[nx.DiGraph, ReachabilityResult]:
    g = nx.DiGraph()
    pkg_node = f"package:{diff.name}@{diff.new_version}"
    install_node = f"install:{job.workflow_file}:{job.job_name}"
    job_node = f"job:{job.job_name}"
    secret_node = f"secrets:{','.join(job.secrets_used) or 'none'}"

    g.add_node(pkg_node, kind="package", suspicious=diff.is_suspicious)
    g.add_node(install_node, kind="install", ignore_scripts=job.ignore_scripts)
    g.add_node(job_node, kind="job", permissions=job.permissions)
    g.add_node(secret_node, kind="secrets", has_secrets=job.has_secrets)

    g.add_edge(pkg_node, install_node, label="lifecycle script runs on install")
    g.add_edge(install_node, job_node, label="runs inside")
    g.add_edge(job_node, secret_node, label="has access to")

    # --- the core reachability decision ---
    if not diff.has_new_lifecycle_script:
        reachable, reason = False, "package adds no new install-time script"
    elif job.ignore_scripts:
        reachable, reason = False, "job installs with --ignore-scripts; script never runs"
    elif not job.has_secrets and job.permissions != "write-all":
        reachable, reason = False, "job has no secrets and no write permissions"
    else:
        reachable, reason = True, "new install script runs in a job with secrets/write access"

    severity = _severity(diff, job, reachable)
    path = [pkg_node, install_node, job_node, secret_node] if reachable else [pkg_node, install_node]

    g.graph["reachable"] = reachable
    g.graph["reason"] = reason
    g.graph["severity"] = severity

    result = ReachabilityResult(
        job_name=job.job_name, reachable=reachable, reason=reason, severity=severity, path=path
    )
    return g, result


def render_dot(g: nx.DiGraph, path: str) -> None:
    """Write a Graphviz .dot file for the report image."""
    try:
        from networkx.drawing.nx_pydot import write_dot

        write_dot(g, path)
    except Exception:
        # Fallback: minimal manual DOT writer, no extra dependency needed.
        with open(path, "w") as f:
            f.write("digraph G {\n")
            for n in g.nodes:
                f.write(f'  "{n}";\n')
            for a, b, d in g.edges(data=True):
                label = d.get("label", "")
                f.write(f'  "{a}" -> "{b}" [label="{label}"];\n')
            f.write("}\n")


if __name__ == "__main__":
    import sys

    from cognishield.package_diff import diff_packages
    from cognishield.workflow_parser import parse_workflows

    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    old, new = sys.argv[2], sys.argv[3]

    diff = diff_packages(old, new)
    jobs = parse_workflows(repo)
    for job in jobs:
        if not job.installs_deps:
            continue
        g, result = build_graph(diff, job)
        print(f"\n=== job: {job.job_name} ===")
        print("reachable:", result.reachable)
        print("reason:   ", result.reason)
        print("severity: ", result.severity)
        print("path:     ", " -> ".join(result.path))
        render_dot(g, f"graph_{job.job_name}.dot")
