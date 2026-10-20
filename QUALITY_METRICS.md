# QUALITY_METRICS — TRAKKART

Gates (TRAKK family standard). All must be PASS for release.

| Gate | What it measures | Threshold | Where |
|---|---|---|---|
| `pass_rate` | % pytest tests passing | 100% | `tools/quality_metrics.py` |
| `coverage` | branch coverage over `app/` | ≥80% | `.coveragerc` + `coverage json` |
| `gherkin` | passing `.feature` scenarios | 30/30 | `features/*.feature` via pytest-bdd |
| `export_smoke` | main image + thumb bundle generated | each PNG >500B | `app/exporter.py` + smoke in metrics |
| `no_leak` | no GPL copies or personal data | 0 hits | scan of `app/`, `features/`, `tests/` |

Report: `data/quality_report.json` (generated, do not commit).

Banned in `app/`: `dither-guy`, `manoelpiovesan`, `C:\Users\...` paths, emails, `GPL-3.0 AND`.
Reason: TRAKKART is MIT with original code; dither-guy is GPL-3.0 (ideas only).
