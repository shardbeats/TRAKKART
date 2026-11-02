# QUALITY_METRICS — TRAKKART

Gates (TRAKK SUITE standard). All must be PASS for release.

| Gate | What it measures | Threshold | Where |
|---|---|---|---|
| `pass_rate` | % pytest tests passing | 100% | `tools/quality_metrics.py` |
| `coverage` | branch coverage over `app/` | ≥80% | `.coveragerc` + `coverage json` |
| `gherkin` | passing `.feature` scenarios | 59/59 | `features/*.feature` via pytest-bdd |
| `export_smoke` | main image + thumb bundle generated | each PNG >500B | `app/exporter.py` + smoke in metrics |
| `no_leak` | no banned content or personal data | 0 hits | scan of `app/`, `features/`, `tests/` |

Report: `data/quality_report.json` (generated, do not commit).

Banned in `app/`: local user paths, emails, non-MIT license expressions.
Reason: keep the codebase MIT-only with no personal data.
