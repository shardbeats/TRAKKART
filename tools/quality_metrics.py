"""TRAKKART quality gates (SUITE standard).

Runs: pytest + coverage + Gherkin count + export smoke + no-leak scan.
Writes data/quality_report.json and exits 0 if everything passes, 1 if not.

Usage:
  .venv\\Scripts\\python tools\\quality_metrics.py
  .venv\\Scripts\\python tools\\quality_metrics.py --no-cov   :: no coverage (fast)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT = DATA / "quality_report.json"

GATES = {
    "pass_rate": 100.0,      # % tests passing
    "coverage": 80.0,        # % branch coverage over app/
    "gherkin": 62,           # .feature scenarios that must pass
    "export_smoke_bytes": 500,
}

BANNED = [
    "@gmail.com",
    "@hotmail.com",
    "GPL-3.0 AND",  # only our own MIT is accepted
]

#: Personal Windows profile paths (``C:\Users\<name>\...``) and emails in
#: files that ship with the public repo/docs.
PROFILE_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"'`]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _public_docs() -> list[Path]:
    """Docs visible in the public repo (must stay path/email free)."""
    return sorted((ROOT / "docs").rglob("*.md")) + sorted(ROOT.glob("*.md"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def _count_scenarios() -> int:
    n = 0
    for f in (ROOT / "features").glob("*.feature"):
        n += len(re.findall(r"(?m)^\s*Scenario\s*:", f.read_text(encoding="utf-8")))
    return n


def _no_leak_scan() -> list[str]:
    hits: list[str] = []
    root_low = str(ROOT).lower()
    for f in list((ROOT / "app").rglob("*.py")) + [ROOT / "main.py"] + _public_docs():
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        low = txt.lower()
        for b in BANNED:
            if b.lower() in low:
                hits.append(f"{f.relative_to(ROOT)}: {b}")
        if PROFILE_RE.search(txt):
            hits.append(f"{f.relative_to(ROOT)}: user profile path")
        if root_low in low:
            hits.append(f"{f.relative_to(ROOT)}: local checkout path")
    # seed/data with personal data: presets and tests must not contain emails
    for f in (list((ROOT / "features").glob("*.feature"))
              + list((ROOT / "tests").glob("*.py")) + _public_docs()):
        txt = f.read_text(encoding="utf-8")
        if EMAIL_RE.search(txt):
            hits.append(f"{f.relative_to(ROOT)}: email?")
    return hits


def _has_plugin(module: str) -> bool:
    """True if an optional test plugin (xdist/pytest-cov) is installed."""
    try:
        __import__(module)
    except ImportError:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cov", action="store_true")
    ap.add_argument("-m", default="", help="pytest -m filter (e.g. 'not slow')")
    args = ap.parse_args()
    py = sys.executable

    # xdist (fast: full suite ~1min instead of ~30min); legacy path without
    # it still works, just slow. pytest-cov combines xdist workers; plain
    # `coverage run` collects nothing under xdist (workers are subprocesses).
    xdist = ["-n", "auto"] if _has_plugin("xdist") else []
    use_cov_plugin = not args.no_cov and _has_plugin("pytest_cov")

    # 1) pytest (+ coverage) — no -q so the "N passed" summary always shows
    if args.no_cov or not use_cov_plugin:
        cmd = [py, "-m", "pytest", "tests", "-p", "no:cacheprovider", *xdist]
        if args.m:
            cmd += ["-m", args.m]
        r = _run(cmd)
        cov = None
    else:
        covf = DATA / "coverage.json"
        cmd = [py, "-m", "pytest", "tests", "-p", "no:cacheprovider", *xdist,
               "--cov=app", "--cov-branch", f"--cov-report=json:{covf}"]
        if args.m:
            cmd += ["-m", args.m]
        r = _run(cmd)
        cov = None
        if covf.exists():
            try:
                cov = json.loads(covf.read_text(encoding="utf-8"))["totals"]["percent_covered"]
            except Exception:
                cov = None

    out = (r.stdout or "") + (r.stderr or "")
    # pytest -q: "6 passed" / "1 failed"
    m_pass = re.search(r"(\d+) passed", out)
    m_fail = re.search(r"(\d+) failed", out)
    passed = int(m_pass.group(1)) if m_pass else 0
    failed = int(m_fail.group(1)) if m_fail else (0 if r.returncode == 0 else 1)
    total = passed + failed
    pass_rate = (passed / total * 100.0) if total else 0.0

    # 2) gherkin: scenarios in features/ (pytest-bdd runs them inside pytest)
    scenarios = _count_scenarios()

    # 3) own export smoke (independent of tests)
    smoke_ok, smoke_detail = False, ""
    try:
        sys.path.insert(0, str(ROOT))
        from PIL import Image

        from app.dither import apply_method
        from app.exporter import export_bundle
        from app.palettes import get_palette

        img = Image.new("RGB", (128, 128), (200, 50, 90))
        res = apply_method(img, method="floyd", palette=get_palette("VAPOR"))
        with tempfile.TemporaryDirectory() as td:
            paths = export_bundle(res, Path(td), base="qc")
            pngs = {k: p for k, p in paths.items() if str(p).endswith(".png")}
            sizes = {k: p.stat().st_size for k, p in pngs.items()}
            smoke_ok = len(pngs) == 3 and all(s > GATES["export_smoke_bytes"] for s in sizes.values())
            smoke_detail = str(sizes)
    except Exception as e:  # noqa: BLE001
        smoke_detail = f"ERROR: {e}"

    # 4) no-leak
    leaks = _no_leak_scan()

    gates = {
        "pass_rate": {"value": round(pass_rate, 1), "need": GATES["pass_rate"], "ok": pass_rate >= GATES["pass_rate"] and total > 0},
        "coverage": {"value": round(cov, 1) if cov is not None else None, "need": GATES["coverage"], "ok": (cov is not None and cov >= GATES["coverage"]) if not args.no_cov else True},
        "gherkin": {"value": scenarios, "need": GATES["gherkin"], "ok": scenarios >= GATES["gherkin"] and failed == 0},
        "export_smoke": {"value": smoke_detail, "need": f">{GATES['export_smoke_bytes']}B each", "ok": smoke_ok},
        "no_leak": {"value": leaks, "need": "0 hits", "ok": len(leaks) == 0},
    }
    all_ok = all(g["ok"] for g in gates.values())

    DATA.mkdir(exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {"ok": all_ok, "pytest": {"passed": passed, "failed": failed, "rc": r.returncode}, "gates": gates},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"[TRAKKART] pytest: {passed} passed, {failed} failed")
    for name, g in gates.items():
        print(f"  gate {name}: {'PASS' if g['ok'] else 'FAIL'} (value={g['value']}, need={g['need']})")
    print(f"[TRAKKART] report -> {REPORT} :: {'OK' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
