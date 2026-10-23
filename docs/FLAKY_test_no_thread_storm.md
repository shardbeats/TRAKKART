# FLAKY — test_no_thread_storm_on_rapid_refresh

Estado: **FALLO CONFIRMADO / RELEASE RETRASADA**. No borrar el test. Cuarentena + fix offline.
Fecha: 2026-10-22. Repo: `shardbeats/TRAKKART`. HEAD en la detección: `b847fad`.

## 1. Resumen

El test de estabilidad `tests/test_stability.py::test_no_thread_storm_on_rapid_refresh`
falla de forma intermitente en corrida serial completa: crea **3 workers** cuando el
invariante exige **≤2**. Aislado pasa 3/3 y en paralelo (`-n auto`) la suite va 100% verde.
Es un flake de timing/scheduling de hilos Qt, **preexistente** y no causado por el
rebranding TRAKK SUITE ni por el cambio de icono.

Decisión: se retrasa el release de TRAKKART hasta fijar o endurecer este punto.
Este documento reúne toda la evidencia disponible hasta el momento.

## 2. Firma del fallo

```
FAILED tests/test_stability.py::test_no_thread_storm_on_rapid_refresh
tests/test_stability.py:91: in test_no_thread_storm_on_rapid_refresh
    assert len(created) <= 2, f"thread storm: {len(created)} workers"
E   AssertionError: thread storm: 3 workers
E   assert 3 <= 2
E    +  where 3 = len([1, 1, 1])
```

Comando que lo cazó (serie, frenando en el primer fallo):

```bat
python -m pytest tests -q -x --tb=short -rf > fail_serial.log 2>&1
```

Cola de `fail_serial.log`:

```
......s............................s................s...s............... [ 16%]
........................................................................ [ 32%]
.................................................................s...... [ 49%]
.......................................................................F [ 65%]
FAILED tests/test_stability.py::test_no_thread_storm_on_rapid_refresh - Asser...
```

El `F` cae ~65% de la suite serial (orden alfabético de archivos).

## 3. El test (tests/test_stability.py:41-92)

* Marcado `pytestmark = pytest.mark.slow` (fuera del fast loop `-m "not slow"`).
* Fuerza ruta asíncrona: `monkeypatch.setattr(A, "has_numba", lambda: False)`.
* Envuelve `PreviewWorker` en `Counting` (cuenta construcciones) y bloquea `work()` en un `gate = threading.Event()`.
* `window.src = Image.new("RGB", (900, 900), ...)`; `window.refresh()` → worker 1 arranca y se bloquea en el gate.
* Espera con `processEvents + sleep(0.01)` hasta `isRunning()`, luego 4× `window.refresh()`
  que **deberían** coalescar (`_preview_pending = True`, sin crear workers).
* `gate.set()` libera worker 1; el pendiente dispara exactamente 1 worker más.
* Aserción: `len(created) <= 2` y `window.result is not None`.

El docstring afirma "Deterministic (no wall-clock race)". La evidencia muestra que no lo es
(ver §6).

## 4. Código de producción implicado

* `app/ui/main_window.py:356` — `refresh()`: si `src` existe y `_video_on` es falso,
  delega en `_pc.render_still(self)`.
* `app/ui/preview_controller.py:12-20` — `render_still()`: si `should_render_async(src)`
  (900×900 sin numba → sí), va a `start_async()`.
* `app/ui/preview_controller.py:35-49` — `start_async()`:

```python
if win._preview_worker is not None and win._preview_worker.isRunning():
    win._preview_pending = True
    return
win._preview_token += 1
win._preview_worker = PreviewWorker(...)
win._preview_worker.start()
```

La ventana de carrera está entre `isRunning()` y la construcción/arranque: `isRunning()`
no es visible inmediatamente tras `start()`, y `processEvents()` puede entregar
timers/signals (p. ej. debounce 350 ms de `test_debounce_coalesces_renders`) que llaman
`refresh()` de forma reentrante.

* Fixtures `tests/conftest.py`: `qt_app` es `scope="module"` (QApplication compartido),
  `window` es por función pero sobre el mismo loop de eventos; un timer/worker tardío de
  un test previo puede interferir con el siguiente en corrida serial.

## 5. Evidencia de flake (no regresión)

| Corrida | Resultado |
|---|---|
| Serial completa `-q` (usuario) | 1×F (~65%) |
| Serial `-q -x --tb=short -rf` (caza) | F en `test_no_thread_storm_on_rapid_refresh`, 3 workers |
| Solo ese test, 3 repeticiones seriales | 3× verde (`.`) |
| Paralelo `-q -n auto --tb=short -rf` | 100% verde, 0 fallos, solo warnings de `QMouseEvent` deprecado |

Diff de lógica `9ae4118..HEAD -- app/ tests/`: 9 archivos, 9 líneas de 1 cambio cada una,
todas renombres de comentario `family → SUITE` (`app/__init__.py`, `app/history.py`,
`app/kernels.py`, `app/palettes.py`, `app/paths.py`, `app/ui/about_dialog.py`,
`app/ui/main_window.py`, `app/ui/theme.qss`, `tests/test_theme.py`).
**Ningún cambio toca el path de preview/hilos.** El flake es preexistente.

Nota: `.pytest_cache/v/cache/lastfailed` contenía 33 entradas viejas (bdd + ui_smoke +
stability + extras). Caché obsoleta, no corresponde a la corrida actual; se deja constancia
y no se usa como evidencia primaria.

## 6. Entorno de las corridas

* Sistema (usado en la corrida con F): `python`,
  Python **3.14.7**, **sin numba** (`import numba` falla).
* `.venv` del proyecto: `<repo>\.venv\Scripts\python.exe`,
  Python **3.14.8**, numba **0.68.0**.
* Paquetes (sistema): imageio 2.38.1, imageio-ffmpeg 0.6.0, numpy 2.5.4, pillow 12.3.0,
  PySide6 6.11.2, pytest 9.1.1, pytest-bdd 9.0.0, pytest-cov 7.1.0, pytest-timeout 2.4.0,
  pytest-xdist 3.8.0.
* `pytest.ini`: `testpaths = tests`, `addopts = -q`, marcador `slow` registrado.
* `QT_QPA_PLATFORM=offscreen` en `tests/conftest.py`.
* Sin numba, `should_render_async` manda a hilo más a menudo y los renders numpy son más
  lentos (referencia del repo: Floyd color 3000px ~45 s numpy vs <1 s numba), lo que
  ensancha las ventanas de timing del test.

## 7. Causa raíz (hipótesis de trabajo)

1. `gate` solo bloquea dentro de `work()`, **no la creación/arranque del hilo**.
   Si un `refresh()` observa `isRunning() == False` (startup aún no visible, o signal
   `finished` ya entregado pero puntero no actualizado), construye un worker extra
   que también se bloquea en el gate → 3 construcciones.
2. `processEvents()` en los bucles de espera del propio test (y timers vivos de tests
   vecinos en corrida serial: debounce 350 ms, `QTimer.singleShot(400)` de diálogos)
   introduce reentrancia que el diseño "determinista" no contempla.
3. En `xdist` cada worker corre un subconjunto en procesos separados: menos estado
   acumulado y menos contención → el flake no se manifiesta.

## 8. Por qué NO borrarlo (investigación)

* **Google** (1.5% runs flaky; 84% de transiciones pass→fail son flakes): re-ejecutar,
  marcar flaky (fallar solo si falla 3 seguidas) y **cuarentenar** (sacar del critical
  path + bug abierto), nunca borrar a ciegas.
  https://googledata.org/google-testing/flaky-tests-at-google-and-how-we-mitigate-them/
* **Fuchsia**: el flake se saca de CQ de inmediato (disable), pero es obligatorio
  diagnosticarlo y re-habilitarlo; no se fija con CQ en rojo.
  https://fuchsia.googlesource.com/fuchsia/+show/5037d7006939/docs/concepts/testing/test_flake_policy.md
* **GitLab**: cuarentena temporal (máx. 3 meses); el borrado solo procede si el test es
  de bajo valor/redundante o si tras 3 meses sigue sin resolverse.
  https://handbook.gitlab.com/handbook/engineering/testing/quarantine-process/

Este test protege el invariante anti-cuelgue más importante de la UI (v0.15: anti-freeze,
`PreviewWorker` con tokens). Es único en la suite para coalescing de hilos. Borrarlo nos
dejaría ciegos. Ya está marcado `slow`, es decir, medio-cuarentenado del fast loop.

## 9. Fix aplicado (vía 3 de las opciones originales)

Archivo: `app/ui/preview_controller.py` (único archivo tocado, +29 líneas).

1. `start_async()`: guard `if win._preview_pending: return` tras el chequeo de
   `isRunning()`. Si ya hay un render encolado y el worker aún no terminó (o su
   señal `finished` viene en camino), no se construye otro worker.
2. `on_done()` / `on_error()`: en vez de liberar el slot a ciegas, se hace
   `wait(5000)` y luego se verifica `isRunning()`:
   - Si sigue vivo de verdad (o fake busy en tests) → `pending = True` y return,
     sin spawnear y sin loopear.
   - Si terminó → slot a `None` y se drena el pendiente con un único `start_async()`.

   Esto hizo determinista el `on_done` (el `wait` garantiza que el hilo terminó
   antes de decidir) y preservó la semántica que exige
   `tests/test_ui_video.py::test_video_start_async_and_pending`
   ("error with pending retries → pending again, no loop"): la primera versión
   del fix (liberación incondicional) rompía ese test porque descartaba el worker
   busy y spawneaba un worker real; la versión final lo respeta.

## 10. Validación (código final) — 2026-10-23

| Corrida | Resultado |
|---|---|
| `test_no_thread_storm_on_rapid_refresh` 5× serie aislado | 5× exit 0 |
| `test_stability.py` + `test_ui_video.py` serie | exit 0 (21 tests) |
| Chunks serie A+B (lógica/render) | exit 0 |
| Chunks serie C+D1 (stability/ventana/UI-export) | exit 0 |
| Chunk serie D2 (palette/presets/render/video) | exit 0 |
| `tests/bdd` serie | exit 0 |
| Suite completa `-n auto` | exit 0 |

La suite serial completa en una sola corrida excede 10 min en esta máquina,
por eso se validó por chunks que cubren el 100% de los archivos de test.
La F original no volvió a aparecer en ninguna corrida.

## 11. Plan restante

* [x] Repetir el test aislado en serie y registrar tasa (base: F 1/1 en suite, 3/3 verde aislado).
* [x] Implementar fix (vía 3).
* [x] Re-correr `test_stability.py` + vecinos + chunks serie sin F.
* [x] Suite completa `-n auto` verde.
* [ ] Commit + push del fix y este doc (siguiente paso).
* [ ] Re-abrir release de TRAKKART (decisión del dueño).

## Anexos

* `fail_serial.log` (generado 2026-10-22 en la raíz del repo, gitignored): contiene la
  salida serial con el F y el traceback corto.
* `icon.png` / `icon.ico` raíz: nuevos (05_bayer_dots), 0 píxeles slime — sin relación
  con este fallo; `out/icon_*` viejos y `build/` con icono antiguo ya eliminados.
* `git log --oneline -- icon.png icon.ico`: `b847fad` (nuevo) sobre `f91ba66`.
