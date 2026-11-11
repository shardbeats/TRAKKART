# FLAKY — test_no_thread_storm_on_rapid_refresh

Status: **CONFIRMED FAILURE / RELEASE DELAYED**. Do not delete the test. Quarantine + offline fix.
Date: 2026-10-22. Repo: `shardbeats/TRAKKART`. HEAD at detection: `b847fad`.

## 1. Summary

The stability test `tests/test_stability.py::test_no_thread_storm_on_rapid_refresh`
fails intermittently in full serial runs: it creates **3 workers** when the
invariant requires **≤2**. Isolated it passes 3/3, and in parallel (`-n auto`) the suite
is 100% green. It is a Qt thread timing/scheduling flake, **pre-existing** and not
caused by the TRAKK SUITE rebranding or the icon change.

Decision: delay the TRAKKART release until this is fixed or hardened.
This document gathers all evidence available so far.

## 2. Failure signature

```
FAILED tests/test_stability.py::test_no_thread_storm_on_rapid_refresh
tests/test_stability.py:91: in test_no_thread_storm_on_rapid_refresh
    assert len(created) <= 2, f"thread storm: {len(created)} workers"
E   AssertionError: thread storm: 3 workers
E   assert 3 <= 2
E    +  where 3 = len([1, 1, 1])
```

Command that caught it (serial, stopping at the first failure):

```bat
python -m pytest tests -q -x --tb=short -rf > fail_serial.log 2>&1
```

Tail of `fail_serial.log`:

```
......s............................s................s...s............... [ 16%]
........................................................................ [ 32%]
.................................................................s...... [ 49%]
.......................................................................F [ 65%]
FAILED tests/test_stability.py::test_no_thread_storm_on_rapid_refresh - Asser...
```

The `F` lands ~65% into the serial suite (alphabetical file order).

## 3. The test (tests/test_stability.py:41-92)

* Marked `pytestmark = pytest.mark.slow` (outside the fast loop `-m "not slow"`).
* Forces the async path: `monkeypatch.setattr(A, "has_numba", lambda: False)`.
* Wraps `PreviewWorker` in `Counting` (counts constructions) and blocks `work()` on a `gate = threading.Event()`.
* `window.src = Image.new("RGB", (900, 900), ...)`; `window.refresh()` → worker 1 starts and blocks on the gate.
* Waits with `processEvents + sleep(0.01)` until `isRunning()`, then 4× `window.refresh()`
  which **should** coalesce (`_preview_pending = True`, no workers created).
* `gate.set()` releases worker 1; the pending flag spawns exactly 1 more worker.
* Assertion: `len(created) <= 2` and `window.result is not None`.

The docstring claims "Deterministic (no wall-clock race)". The evidence shows it is not
(see §6).

## 4. Production code involved

* `app/ui/main_window.py:356` — `refresh()`: if `src` exists and `_video_on` is false,
  it delegates to `_pc.render_still(self)`.
* `app/ui/preview_controller.py:12-20` — `render_still()`: if `should_render_async(src)`
  (900×900 without numba → yes), it goes to `start_async()`.
* `app/ui/preview_controller.py:35-49` — `start_async()`:

```python
if win._preview_worker is not None and win._preview_worker.isRunning():
    win._preview_pending = True
    return
win._preview_token += 1
win._preview_worker = PreviewWorker(...)
win._preview_worker.start()
```

The race window sits between `isRunning()` and construction/startup: `isRunning()`
is not visible immediately after `start()`, and `processEvents()` can deliver
timers/signals (e.g. the 350 ms debounce from `test_debounce_coalesces_renders`) that call
`refresh()` reentrantly.

* Fixtures `tests/conftest.py`: `qt_app` is `scope="module"` (shared QApplication),
  `window` is function-scoped but on the same event loop; a late timer/worker from a
  previous test can interfere with the next one in serial runs.

## 5. Flake evidence (not a regression)

| Run | Result |
|---|---|
| Full serial `-q` (user) | 1×F (~65%) |
| Serial `-q -x --tb=short -rf` (hunt) | F in `test_no_thread_storm_on_rapid_refresh`, 3 workers |
| That test alone, 3 serial repetitions | 3× green (`.`) |
| Parallel `-q -n auto --tb=short -rf` | 100% green, 0 failures, only deprecated `QMouseEvent` warnings |

Logic diff `9ae4118..HEAD -- app/ tests/`: 9 files, 9 one-line changes each,
all `family → SUITE` comment renames (`app/__init__.py`, `app/history.py`,
`app/kernels.py`, `app/palettes.py`, `app/paths.py`, `app/ui/about_dialog.py`,
`app/ui/main_window.py`, `app/ui/theme.qss`, `tests/test_theme.py`).
**No change touches the preview/thread path.** The flake is pre-existing.

Note: `.pytest_cache/v/cache/lastfailed` held 33 stale entries (bdd + ui_smoke +
stability + extras). Obsolete cache, not matching the current run; recorded here
and not used as primary evidence.

## 6. Run environment

* System python (used in the run with F): `<system python>` (python.exe),
  Python **3.14.7**, **no numba** (`import numba` fails).
* Project `.venv`: `<repo>\.venv\Scripts\python.exe`,
  Python **3.14.8**, numba **0.68.0**.
* Packages (system): imageio 2.38.1, imageio-ffmpeg 0.6.0, numpy 2.5.4, pillow 12.3.0,
  PySide6 6.11.2, pytest 9.1.1, pytest-bdd 7.0.0, pytest-cov 7.1.0, pytest-timeout 2.4.0,
  pytest-xdist 3.8.0.
* `pytest.ini`: `testpaths = tests`, `addopts = -q`, `slow` marker registered.
* `QT_QPA_PLATFORM=offscreen` in `tests/conftest.py`.
* Without numba, `should_render_async` sends more work to threads and numpy renders are
  slower (repo reference: Floyd color 3000px ~45 s numpy vs <1 s numba), widening the
  test's timing windows.

## 7. Root cause (working hypothesis)

1. `gate` only blocks inside `work()`, **not construction/startup of the thread**.
   If a `refresh()` observes `isRunning() == False` (startup not yet visible, or
   `finished` signal already delivered but pointer not updated), it builds an extra
   worker that also blocks on the gate → 3 constructions.
2. `processEvents()` in the test's own wait loops (and live timers from neighboring
   tests in serial runs: 350 ms debounce, `QTimer.singleShot(400)` dialogs)
   introduces reentrancy the "deterministic" design does not account for.
3. Under `xdist` each worker runs a subset in separate processes: less accumulated
   state and less contention → the flake does not show.

## 8. Why NOT delete it (research)

* **Google** (1.5% flaky runs; 84% of pass→fail transitions are flakes): re-run,
  mark flaky (fail only if it fails 3 times in a row) and **quarantine** (remove from the
  critical path + open bug), never delete blindly.
  https://googledata.org/google-testing/flaky-tests-at-google-and-how-we-mitigate-them/
* **Fuchsia**: the flake is removed from CQ immediately (disable), but diagnosing
  and re-enabling it is mandatory; never fix with CQ red.
  https://fuchsia.googlesource.com/fuchsia/+show/5037d700693/docs/concepts/testing/test_flake_policy.md
* **GitLab**: temporary quarantine (3 months max); deletion only applies if the test is
  low-value/redundant or still unresolved after 3 months.
  https://handbook.gitlab.com/handbook/engineering/testing/quarantine-process/

This test guards the most important anti-hang invariant in the UI (v0.15: anti-freeze,
`PreviewWorker` with tokens). It is unique in the suite for thread coalescing. Deleting it
would leave us blind. It is already marked `slow`, i.e. half-quarantined out of the fast loop.

## 9. Applied fix (option 3 from above)

File: `app/ui/preview_controller.py` (only file touched, +29 lines).

1. `start_async()`: guard `if win._preview_pending: return` after the `isRunning()`
   check. If a render is already queued and the worker has not finished yet (or its
   `finished` signal is in flight), no extra worker is built.
2. `on_done()` / `on_error()`: instead of releasing the slot blindly, `wait(5000)`
   first and then check `isRunning()`:
   - If still truly alive (or fake-busy in tests) → `pending = True` and return,
     without spawning and without looping.
   - If finished → slot to `None` and drain the pending flag with a single `start_async()`.

   This made `on_done` deterministic (the `wait` guarantees the thread is done
   before deciding) and preserved the semantics required by
   `tests/test_ui_video.py::test_video_start_async_and_pending`
   ("error with pending retries → pending again, no loop"): the first version of
   the fix (unconditional release) broke that test by discarding the busy worker
   and spawning a real one; the final version respects it.

## 10. Validation (final code) — 2026-10-23

| Run | Result |
|---|---|
| `test_no_thread_storm_on_rapid_refresh` 5× serial, isolated | 5× exit 0 |
| `test_stability.py` + `test_ui_video.py` serial | exit 0 (21 tests) |
| Serial chunks A+B (logic/render) | exit 0 |
| Serial chunks C+D1 (stability/window/UI-export) | exit 0 |
| Serial chunk D2 (palette/presets/render/video) | exit 0 |
| `tests/bdd` serial | exit 0 |
| Full suite `-n auto` | exit 0 |

A full serial suite in one run exceeds 10 min on this machine,
so it was validated in chunks covering 100% of the test files.
The original F did not reappear in any run.

## 11. Remaining plan

* [x] Repeat the isolated test serially and record the rate (baseline: F 1/1 in suite, 3/3 green isolated).
* [x] Implement the fix (option 3).
* [x] Re-run `test_stability.py` + neighbors + serial chunks with no F.
* [x] Full suite `-n auto` green.
* [ ] Commit + push the fix and this doc (next step).
* [ ] Re-open the TRAKKART release (owner decision).

## Appendix

* `fail_serial.log` (generated 2026-10-22 in the repo root, gitignored): holds the
  serial output with the F and the short traceback.
* `icon.png` / `icon.ico` at root: new (05_bayer_dots), 0 slime pixels — unrelated
  to this failure; old `out/icon_*` and `build/` with the old icon already removed.
* `git log --oneline -- icon.png icon.ico`: `b847fad` (new) on top of `f91ba66`.
