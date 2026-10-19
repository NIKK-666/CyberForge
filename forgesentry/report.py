"""Step 7: Report + Delivery.
Builds the Markdown PR comment ForgeSentry posts, from the graph result and
(optionally) the LLM verdict. No GitHub calls here -- see github_delivery.py.
"""
from __future__ import annotations

from forgesentry.graph import ReachabilityResult


def build_comment(diff, result: ReachabilityResult, llm_verdict=None) -> str:
    lines = []
    lines.append(f"## 🛡️ ForgeSentry AI -- {diff.name} {diff.old_version} -> {diff.new_version}")
    lines.append("")
    status = "🔴 REACHABLE" if result.reachable else "🟢 path broken (low priority)"
    lines.append(f"**Job:** `{result.job_name}`  |  **Status:** {status}  |  **Severity:** {result.severity}/100")
    lines.append("")
    lines.append("**Attack path:**")
    lines.append("```")
    lines.append(" -> ".join(result.path))
    lines.append("```")
    lines.append(f"_Reason: {result.reason}_")
    lines.append("")
    if llm_verdict is not None:
        lines.append(f"**AI verdict:** `{llm_verdict.verdict}` (confidence {llm_verdict.confidence}%)")
        lines.append("")
        lines.append(llm_verdict.attack_story)
        lines.append("")
        lines.append(f"**Suggested fix:** {llm_verdict.suggested_fix}")
        lines.append("")
        lines.append("---")
        lines.append("Comment `/shield fix` to open a fix pull request automatically.")
    else:
        lines.append("_No AI review needed -- install scripts cannot reach secrets on this path._")
    return "\n".join(lines)


if __name__ == "__main__":
    from forgesentry.graph import build_graph
    from forgesentry.llm_layer import judge
    from forgesentry.package_diff import diff_packages
    from forgesentry.workflow_parser import parse_workflows

    diff = diff_packages("vendor/left-padz-1.0.0.tgz", "vendor/left-padz-1.0.1.tgz")
    jobs = [j for j in parse_workflows(".") if j.installs_deps]
    for job in jobs:
        g, result = build_graph(diff, job)
        verdict = None
        if result.reachable:
            verdict = judge(
                diff.name, diff.old_version, diff.new_version, result.reason,
                result.severity, diff.new_lifecycle_scripts, diff.risky_calls, diff.decoded_payloads,
            )
        print(build_comment(diff, result, verdict))
        print("\n" + "=" * 60 + "\n")
