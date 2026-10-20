# CogniShield -- Working Demo Prototype

An attack-path and blast-radius engine for CI/CD. It correlates a risky
npm dependency update with the GitHub Actions job that would install it,
decides whether that job can actually reach your secrets, and only then
brings in an LLM to judge intent, explain the attack and draft a fix.

## What's in this repo

| Path | What it does | Pipeline step |
|---|---|---|
| `cognishield/workflow_parser.py` | Reads `.github/workflows/*.yml` with PyYAML | 1. Workflow parsing |
| `cognishield/package_diff.py` | Diffs two npm tarballs, decodes base64/hex payloads | 2+3. Package diff + unpacking |
| `cognishield/graph.py` | Builds the NetworkX reachability graph, scores severity | 4. Reachability graph |
| `cognishield/llm_layer.py` | Calls the LLM (or a deterministic mock) for ambiguous cases | 5. LLM layer |
| `cognishield/report.py` | Builds the Markdown PR comment | 6. Report |
| `cognishield/patcher.py` | Generates + validates the fix patch (plain code, not AI) | 7. Fix PR |
| `cognishield/github_delivery.py` | Posts the PR comment, sets the check, handles `/shield fix` | 7. Delivery |
| `cognishield/main.py` | Wires everything together; this is what the Action runs | entrypoint |
| `.github/workflows/cognishield.yml` | The REAL CogniShield Action (minimal permissions) | -- |
| `.github/workflows/ci.yml` | The DELIBERATELY VULNERABLE demo victim workflow | demo only |
| `demo/make_fixtures.py` | Builds the clean (1.0.0) and "malicious" (1.0.1) fixture package | demo only |
| `demo/listener.py` | Local-only HTTP listener standing in for an attacker's server | demo only |
| `demo/run_full_demo.sh` | Runs the entire attack -> detect -> fix -> replay flow | demo only |
| `tests/test_pipeline.py` | pytest suite covering parser, diff, graph, and patch validation | -- |

## Run it yourself

```bash
pip install -r requirements.txt requests --break-system-packages
PYTHONPATH=. pytest tests/ -q          # 4 tests, should all pass
bash demo/run_full_demo.sh             # the full live demo, ~5 seconds
```

No API key is required -- `llm_layer.py` falls back to a deterministic mock
response when `LLM_API_KEY` is unset, so the demo works offline and free.
Set `LLM_API_KEY` and fill in `_call_real_llm()` to use a real provider.

## The demo, in order

1. **Attack, unprotected:** a PR bumps a fake package `safe-pad` from
   1.0.0 to 1.0.1. The new version's `postinstall` script decodes a
   base64 payload and sends a fake secret to a local listener.
2. **CogniShield scans:** the `build` job (has secrets, no
   `--ignore-scripts`) is flagged reachable, severity 100, verdict
   `malicious`. The `lint` job (`--ignore-scripts`, no secrets) is
   correctly scored low and still listed, not hidden.
3. **`/shield fix`:** a safe patch is generated as a small text edit
   (not a full YAML rewrite) and deterministically validated before
   anything is applied.
4. **Replay:** the same install, now with the generated fix, leaks
   nothing.

## Safety notes

- The "malicious" package is a local fixture tarball under `vendor/`,
  never published to the real npm registry.
- The "exfiltration" target is `demo/listener.py`, bound to
  `127.0.0.1` only.
- `FAKE_SECRET` is a made-up string, not a real credential.

## Wiring this into a real GitHub repo

1. Push this repo to GitHub.
2. Add a repo secret `FAKE_SECRET` with any placeholder value (for the
   demo workflow) -- skip this for real usage.
3. Enable branch protection on `main` requiring the `CogniShield`
   status check, so the failing check actually blocks merges.
4. Open a PR that bumps `safe-pad` to `1.0.1` and watch
   `.github/workflows/cognishield.yml` run.
5. Comment `/shield fix` on that PR to see the fix PR open.
