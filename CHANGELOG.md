# CHANGELOG — TRAKKART

Release history (newest first). Details live in `git log` and `ROADMAP.md`.

## [2.15.0] - 2026-11-23 — 9:16 exacto para Spotify Canvas
- Nuevo preset `SPOTIFY_916` (9:16, `576×1024` exacto, dissolve 64f/30fps/Hold 1.5 = 154f ≈ 5.1s en loop): sube donde `1080×1920` (1920 de alto) es rechazado.
- Helpers exactos en `app/canvas.py`: `exact_canvas_size_for()` (par exacto más cercano; a 3000 clavado es imposible → `1692×3008`), `is_exact_ratio()`, `snap_to_exact_ratio()`. El default `1688×3000` no se mueve (presets/docs/tests lo pinean).
- MP4: `mp4_dims_exact()` — los docs ~9:16 salen con ratio bit-exacto (Canvas ajusta al más cercano, 720p/1080p solo hacia abajo sin superar el presupuesto); el resto de ratios sale idéntico a `mp4_dims`. Pin: `tests/test_spotify_exact.py` (7).
- Diálogo de export: la línea del plan muestra las dims ajustadas y el aviso explica snap/altura 720-1080/ventana 3-8s en vez del viejo "quiere 720p/1080p".
- Gates 5/5, flake8 0.

## [2.14.5] - 2026-11-19 — UI + a11y §12 Fase A-D
- A11y bloqueante: insignia zoom con foco + Enter/Espacio y nombres
  accesibles; `ValueSlider` con Inicio (Home) como reset de teclado;
  etiquetas vinculadas (`buddy`) + descripciones; contraste disabled
  `#383B40` → `#6B6E73`; anillo de foco en todos los interactivos;
  `TRAKKART_REDUCED_MOTION=1` (preview 700ms, video/resize 500ms).
  Pin: `tests/test_ui_a11y.py` (8).
- Tokens visuales: rejilla 8px, radios 6px + 8px heroe, alturas min
  boton 24px / input 22px / handle-indicador 18px, fuente
  `Inter,Segoe UI,system-ui` + piso 12px, `dice 🎲` → boton `Roll`,
  borde del canvas por paleta (radio 8). Sin romper `test_layout`
  (panel ≤480 con margenes 4 + `Roll` 56px).
- Estados: vacio con CTA `Open image… (Ctrl+O)` (solo sin imagen);
  error de preview con `Retry preview (F5)` + foco + descripcion
  accesible; export `560x720` adaptativo a pantalla + lista 140-220px.
- Docs: MANUAL (teclado canvas, movimiento reducido, vacio/retry);
  ROADMAP §12 pasa a DONE. Gates 5/5, flake8 0.

## [2.14.4] - 2026-11-18 — caza de bugs: glitch, partículas y video
- Glitch: `slice_shift` con `max_offset` negativo reventaba en numpy
  (`ValueError: low >= high`); cero/negativo ahora es identidad, igual
  que `slice_shift_loop`. Pin: `tests/test_glitch.py` (+1).
- Partículas: `_resolve_anim_spec` con `wind` malformado (`()`, 1-tupla)
  tumbaba el export con `IndexError`; ahora cae al viento por defecto.
  Pin: `tests/test_disintegrate.py` (+1).
- Partículas: la rama de rejillas distintas recortaba las columnas RGB
  de tintas por los límites del canvas (R → `0..h-1`) y destruía las
  tintas de paleta; los colores viajan 1:1 con las coords, intactos.
  Pin: `tests/test_disintegrate.py` (+1).
- Video: `on_done`/`on_error` nunca retiraban el `VideoWorker`
  terminado (hilos acumulados sin `deleteLater`); ahora se retira como
  el preview. Pin: `tests/test_ui_video.py` (+1).
- Export: `resolve_collision` ignoraba el BMP del SP-404 y el diálogo
  no avisaba cuando solo ese archivo chocaba; ahora lo lista. Pin:
  `tests/test_ui_export.py` (+1).
- Higiene: `sync_stale_badge` traía un bloque muerto copiado de
  `_morph_imgs`; los tres `blockSignals(False)` del video van en
  `finally`; el docstring de `fps_changed` ya no promete "sin re-render".
- Gates 5/5, flake8 0.

## [2.14.3] - 2026-11-17 — caza de bugs: pegado Qt, batch y texturas
- Pegar/arrastrar una imagen cuyo ancho no es múltiplo de 4 fallaba con
  "No image in the clipboard": `qimage_to_pil` daba por hecho filas
  empaquetadas, pero Qt rellena cada fila a 4 bytes. Ahora usa
  `bytesPerLine` y recorta el relleno. Pin: `tests/test_stability.py` (+1).
- Batch: `run_batch` cableaba el worker dos veces (señales duplicadas y
  doble `start()`), así que al terminar salían dos diálogos "Batch done".
  Ahora se conecta y arranca una sola vez. Pin: `tests/test_ui_dialogs.py`.
- Textura polvo: una imagen de 1-2 px de alto con `dust` >= 20 reventaba
  en el rango de longitud de las rayas (`rng.integers(0, 0)`). Ahora se
  omiten las rayas en tiras sin altura útil. Pin: `tests/test_texture.py` (+1).
- Motivo: un preset compartido con `motif.bands` que no es lista de
  objetos (texto, `null`…) pasaba `validate()` y rompía el render con
  `AttributeError`. Ahora cae a los valores por defecto de banda. Pin:
  `tests/test_gaps.py`.
- Gates 5/5, flake8 0.

## [2.14.2] - 2026-11-17 — caza de bugs: batch, packs y nombres reservados
- Batch: dos entradas con el mismo tallo (`cover.png` + `cover.jpg`)
  escribían el mismo bundle y la segunda pisaba a la primera en
  silencio. Ahora el tallo duplicado se desambigua por extensión
  (`cover_png`, `cover_jpg`) de forma determinista; los tallos únicos
  no cambian. Pin: `tests/test_batch.py` (+1).
- Nombres reservados de Windows (`CON`, `NUL`, `COM1`…`LPT9`) como
  base de export: `app/names.py` y `sanitize_base` añaden un `_` final
  (también tras recortar bordes). Pin: `tests/test_presets.py` (+1).
- Packs: un nombre vacío ya no genera `presets/.json` / `palettes/.json`
  (fallback `pack`); al importar una paleta sin nombre se usa el tallo
  del miembro. Pin: `tests/test_pack.py` (+1).
- MCP: `estimate` reutiliza `plan_export` (mismas dimensiones/frames
  que el bundle real, `gif_size` incluido) y las notificaciones JSON-RPC
  (sin `id`) ya no reciben respuesta. Pins: `tests/test_mcp.py` (+2).
- Prefs: un `export_prefs.json` con JSON válido pero que no es objeto
  (`[]`, `null`, texto) tumbaba `load_prefs` con `AttributeError` al
  arrancar; ahora cae a los valores por defecto como el JSON roto. Pin:
  `tests/test_settings.py` (+1).
- Clip MP4: el archivo temporal de salida (`{base}_silent.mp4`, `.part.mp4`)
  podía pisar un archivo del usuario con ese nombre en la carpeta destino.
  Ahora se reserva un nombre único junto al destino y se renombra al
  terminar. Pins: `tests/test_v21_bughunt.py`.
- Limpieza: rama muerta en `load_preset` y en `export_full`
  (`vector_cells` nunca se usaba). Gates 5/5, flake8 0.

## [2.14.1] - 2026-11-17 — clip con start obsoleto: autocorrección
- Abrir un clip con "Start at" más allá de su duración ya no muestra
  el aviso modal: carga desde 0, resetea el spinner y lo anota en la
  línea de estado. Pin: `tests/test_clip_strip.py` (+1).

## [2.14.0] - 2026-11-17 — MCP stdio + fuzzer (v2.x #9, #10: roadmap done)
- Servidor MCP stdio (`python main.py --mcp`): JSON-RPC 2.0 por
  stdin/stdout con la superficie headless (spec primero en
  `docs/MCP_SPEC.md`; 3 herramientas: list_presets/render/estimate;
  sin red, sin Qt, extras de diálogo fuera). Pins:
  `tests/test_mcp.py` (7).
- Fuzzer de presets en CI (`tools/fuzz_presets.py`, guiado por el
  esquema `FIELDS`, determinista; 1050 casos, 0 crashes) + paso en el
  job fast + `tests/test_preset_fuzz.py` (2).
- Resto de #10 cerrado con mediciones (cortes honestos, sin
  gold-plate): SSIM, blue-noise, NeuQuant/Wu, tile renderer, JPEG XL
  y PyAV no ganan — números en `ROADMAP.md`. Docs (MANUAL/ROADMAP),
  gates 5/5, flake8 0.

## [2.13.0] - 2026-11-17 — APNG animado (v2.x #8)
- Extra solo-diálogo `{base}_anim.png`: mismos frames que el GIF, a
  todo color como WebP (Pillow, sin deps; el primer frame sirve de
  still). Estimador ~4x GIF medido en ruido dithered, línea de plan
  honesta. Pins: `tests/test_apng.py` (4) + Gherkin +1
  (export.feature). Docs (MANUAL/ROADMAP), gates 5/5, flake8 0.

## [2.12.0] - 2026-11-17 — cross-dissolve opt-in (v2.x #7)
- `app.xfade`: mezclas lineales entre frames de clip/dissolve
  (numpy, determinista; `xfade` 0..1 x `xfade_steps`, con cap que
  nunca recorta inputs). Cableado al motor (dissolve + morph, lista
  y streaming) con default off = bytes legacy; sin knob en UI.
  Pins: `tests/test_xfade.py` (7) + Gherkin +1 (clip.feature). Docs
  (MANUAL/ROADMAP), gates 5/5, flake8 0.

## [2.11.0] - 2026-11-17 — SVG por capas de tinta (v2.x #6)
- Vector SVG con una capa `<g id="ink-RRGGBB">` por tinta (fill del
  grupo, rects heredan; RLE por fila intacto, mismo nº de rects,
  menos bytes). Reúso directo para separaciones; black-vector en una
  sola capa `ink-000000`. Pins: `tests/test_svg_layers.py` (6) +
  Gherkin +1 (vector.feature). Docs (MANUAL/ROADMAP), gates 5/5,
  flake8 0.

## [2.10.0] - 2026-11-17 — modos CRT temporales (v2.x #5)
- MOTION modo `crt` ("CRT drift"): scanline roll + tracking wobble +
  chroma bleed sobre el matrix march (congelado en error-diffusion,
  como phase). Cada canal sigue su knob FX (0 = off, motion 0 =
  freeze); presets limpios en ordered siguen con march. Pins:
  `tests/test_crt.py` (7) + Gherkin +1 (motion.feature). Docs
  (MANUAL/ROADMAP), gates 5/5, flake8 0.

## [2.9.0] - 2026-11-17 — gradient-map multistop (v2.x #4)
- GRADE → Gradient map: rampa de N tintas sobre luminancia (duotone
  con más paradas: Ember/Abyss/Acid/Bone, Off = bypass) como item del
  FX STACK post-dither (reordenable); <2 paradas válidas = identidad.
  Stops planos en preset/meta (`grade.gradient_map`); presets legacy
  byte-idénticos. Pins: `tests/test_gradient_map.py` (8) + Gherkin +1
  (fx_stack.feature). Docs (MANUAL/ROADMAP), gates 5/5, flake8 0.

## [2.8.0] - 2026-11-17 — selector res/calidad MP4 de clip
Primera release que empaqueta v1.8 (delivery), v1.9 (motores/print),
v2.0 (clip import + dither + export), v2.1 (caza de bugs QThread/mux)
y las candidatas v2.x #1 (in-point seek) y #2 (VFR), más la pasada de
orden visual de la UI. Los bloques `[Unreleased]` de abajo quedan como
bitácora detallada por fase.
### Added
- In-point seek en el import de clip (candidata v2.x #1): control
  "Start at (s)" junto a Open clip; MP4 con `-ss` de entrada (rápido y
  exacto en ffmpeg 7.1), GIF/WebP con salto de frames. `info` gana
  `start_s` + `source_duration`, `truncated` honesto (hay frames antes
  o después de la ventana) y error limpio si el inicio supera el final.
  Medido en 1080p/38MB real: `start=10s` importa en ~1.0s, píxeles
  distintos al `start=0`. Pins: unit (GIF skip, MP4 `-ss`, clamps) +
  Gherkin +1 (68).
- Clip unificado (UX, nov-2026, pedido de usuario): el export de clip
  (GIF/MP4/ZIP + soundtrack) vive en la ventana Export, sección Clip
  con plan honesto (`(clip, rendered at export)`) y colisiones; funciona
  sin still abierto (clip-only, stills apagados) y no toca prefs ni el
  quick export. El panel Clip ahora es solo ver: ▶ Play en bucle del
  trim + slider, canvas siempre dithered (fuera el toggle
  "Dithered preview", los 3 botones de export, la fila Track y el spin
  FPS del panel — el FPS y el track viven en el diálogo). El núcleo de
  render (`render_clip_export`) se comparte entre ambos caminos.
- MOTION de una sola línea (UX, nov-2026): fuente conmutable Animate still XOR Clip footage (radios + cajas por fuente, Timing/proxy colapsado en Details); una sola escritura al canvas.
- Clip framing opción B (UX, nov-2026): sin crop propio — el clip sigue IMAGE → Crop del still (etiqueta visible + tooltip, pin en test_ux).
- Link W×H (UX, nov-2026): botón 🔗 estilo Photoshop entre los spins del canvas — con el link puesto, editar un lado escala el otro (cuadrado entra, cuadrado sale: 3000 → 3000×3000). Presets de ratio re-derivan el link; SP-404 lo desactiva. Pin en test_ui_render.
  Pins: 3 (sección/plan/opciones del diálogo, clip-only, export real
  GIF vía `export_flow`).
- VFR normalizado en el import de clip (candidata v2.x #2): el reader
  lleva siempre `-vf fps=N` (N = fps fuente redondeado, 2–60). En CFR
  es passthrough (verificado: mismos 30 frames, mismos bytes); en VFR
  el pase nativo duplicaba (30 reales → 57 leídos) y ahora sale un CFR
  honesto (29 ≈ duración × N). El `fps` de `info` es el efectivo.
  Medido en real CFR (1080p y 4K): mismo 120f/30fps, mismo ~1.2s.
  Pins: unit (VFR sintético + CFR intacto).
### Changed
- Pasada de orden visual (UX, nov-2026): cada página del panel usa
  cabeceras de sección (subrayado fino) y el acordeón se lee como
  navegación (chevron ▸/▾, barra ámbar en la página abierta). Los radios,
  listas y toggles siguen el tema oscuro; los checkboxes llevan tick
  dibujado (no un cuadrado ámbar ambiguo).
- Lecturas numéricas honestas: los sliders normalizados muestran `1.0×`,
  `50%` o `0.0` en vez de un `1`/`0` que ocultaba la escala; sliders de
  porcentaje llevan sufijo `%` y los multiplicadores `×`.
- Controles autoexplicativos: `Ratio:`/`Crop:` con etiqueta propia,
  `Preset:` visible, `Pixel size` en su fila, `Scanlines`/`Border` con
  etiquetas y `Color...` en el borde, `Paper:`/`Blend:` en Paste-Up.
- Cadena W×H dibujada con QPainter (sin depender del font de emoji) y
  botones de play/pause solo texto; los títulos de preview usan `×`.
- Ventana Export ordenada: grupos **Stills / Motion / Print & device** en
  dos columnas, `Format` + `Quality` en una fila, barra de acciones fija
  y contenido con scroll para pantallas bajas; plan y total más claros.
- Una sola línea de estado (el status bar ya no duplica el mensaje) y
  cabecera `DITHER / HALFTONE STUDIO` junto al título.
- Código: helpers de seed unificados en `panels/widgets.roll_seed`,
  `contextlib.suppress` en los toggles SP-404 y assets de tema generados
  en `app/ui/icons.py`.
### Fixed
- **Crash duro al cargar un clip y hacer New project / cerrar** (sin
  traceback, `0xC0000409`): se soltaba la referencia de un `QThread`
  en marcha (`on_done/on_error` del preview, `new_project`, cierre de
  ventana, export, watch y el instalador de extras). Nuevo guardián
  `app/ui/thread_safe.py`: retira workers ociosos y retiene los vivos
  hasta su señal `finished`; el cierre espera con tope y "orfana" un
  render atascado en vez de destruirlo.
- New project ahora cierra el clip de sesión (libera ≤120 frames proxy
  + caché de dither), cancela el preview en vuelo e invalida el token
  de VIDEO (un resultado tardío ya no resucita frames tras el wipe).
- Abrir otro clip limpia `_clip_dither_cache`: el frame 0 del clip B
  ya no mostraba el bitmap cacheado del clip A.
- MP4 largos: `nframes=inf` de imageio ya no borra el aviso de tope
  120f (un video de 54 min se anunciaba sin truncar).
- Mux de soundtrack: corte por duración de vídeo (`-t`); un track de
  0.4s ya no encoge un clip de 2s. `-af apad -shortest` se descartó
  porque **cuelga** ffmpeg con vídeo copiado. Salida atómica `.part`
  y, si el mux falla, se conserva el MP4 silencioso ya codificado.
- `has_video()` verifica también el binario ffmpeg del bundle
  (`VideoBackendMissing` limpio si falta, sin fallo crudo de ffmpeg).
- Los exports de clip ya no sobrescriben: GIF/ZIP/MP4 toman el primer
  nombre libre (`base_2`, `base_3`…), igual que el export de stills.
### Changed
- Import de clip: el proxy 720p se genera **dentro de ffmpeg**
  (`size=`/`-s` en el reader) en vez de decodificar frames nativos y
  redimensionar en Python. Medido: 4K/452MB 12.9s → **1.2s** (11x),
  1080p/2GB 5.4s → **0.5s**, 1080p/38MB 3.3s → **1.1s**; mismo tope
  120f, mismo aviso `truncated` y mismas dimensiones de proxy. Una
  sonda de cabecera (sin decodificar) da el tamaño fuente.
- Investigación de vídeo (nov-2026, ver ROADMAP): `-ss` antes de `-i`
  es exacto en ffmpeg 7.1 (base para el in-point seek), la
  autorrotación de móviles ya funciona, `nframes=inf` es normal (nunca
  llamar a `count_frames`) y las fuentes VFR duplican frames (nueva
  candidata v2.x).
### Tests
- `tests/test_v21_bughunt.py` +28 (ciclo de vida QThread en preview/
  export/watch/pip, wipe de proyecto, caché de clip, entrada corrupta,
  nframes desconocido, mux con track corto, restos parciales de
  mux/encode, colisión de nombres, proxy escalado en ffmpeg) +
  `tests/test_clip.py` +2 (in-point seek GIF/MP4).
  `tests/test_ui_export.py` +3 (clip dialog section/clip-only/real GIF).
  Suite: 788 (644 fast + 144 slow). Gherkin 68/68.
- Envolventes de timeline (candidata v2.x #3, nov-2026): curvas
  session-only (Off/Flat/Ramp/LFO) para Motion/Drift/Grain en
  MOTION → Details; motor `app/envelopes.py` (loop-perfect,
  determinista, firma para stale-check); still-motion y clip dither
  las aplican por frame; batch sigue plano. Pins:
  `tests/test_envelopes.py` + Gherkin +2 (clip.feature 5). Suite 804
  (659 fast + 145 slow). Gherkin 70/70.
- MP4 completo por streaming (nov-2026, a pedido): el import de 120f
  es solo la ventana de preview — **Full length MP4** en Export
  renderiza el clip entero desde Start at (s) hasta el final
  (tope 3600f/60s), decodificado en ventanas de 120f con RAM plana.
  Mismos píxeles que un render full-RAM (seeds globales + envolventes).
  Trim no aplica al completo; GIF/ZIP siguen en el trim. Pins:
  `tests/test_clip_long.py` + Gherkin +1 (clip.feature 6). Suite 812
  (665 fast + 147 slow). Gherkin 71/71.
- P0 video (nov-2026, a pedido): preview de clip en worker
  (`ClipFrameWorker`: un render en vuelo + pending coalescido, latest
  token pinta; cache-hit pinta sync). El preview ya aplicaba la receta
  pero ignoraba las envolventes — ahora preview == export y la clave
  de caché incluye la firma. Cierre limpio (closeEvent une el worker).
  Pins: `tests/test_clip_async.py` (píxeles, tokens, coalescing,
  stale, envolventes) + Gherkin +1 (clip.feature 8). Suite 823
  (675 fast + 148 slow). Gherkin 73/73.
- P1 video (nov-2026, a pedido): whitelist de contenedores
  (`.mov/.mkv/.avi/.m4v/.webm` por el mismo reader ffmpeg; diálogo +
  DnD; still WebP sigue imagen) + probe de track (`audio_duration`
  vía header ffmpeg, nota `track_fit_note` en el plan: silencio al
  final / corte al final / silent MP4 si falta). Pins:
  `tests/test_clip_ingress.py` + drop en `test_ui_dnd.py` + nota en
  `test_ui_export.py` + Gherkin +1 (clip.feature 9). Suite 830
  (680 fast + 150 slow). Gherkin 74/74.
- P2 video (nov-2026, a pedido): filmstrip de hasta 10 miniaturas
  (proxy crudo, click salta; resaltado ámbar sigue al canvas) +
  Motion de envolventes descansa con footage (fila deshabilitada con
  hint; Drift/Grain siguen en ambos paths). Pins:
  `tests/test_clip_strip.py` + Gherkin +1 (clip.feature 10). Suite 834
  (684 fast + 150 slow). Gherkin 75/75.
- Selector res/calidad MP4 de clip (nov-2026, a pedido): tamaño Proxy
  720p (defecto, rápido) / Source ≤1920 (re-decode nativo del
  trim/full, sin upscale de proxy; mismo crop de canvas) + calidad
  q5/q8/q10 (Compact ~0.5x / Balanced / High ~1.5x, medido en ruido).
  Estimador con factor de calidad, plan taggea `720p`/`source` + `q`;
  GIF/ZIP quedan proxy. Pins: `tests/test_clip_resquality.py` (6) +
  Gherkin +1 (clip.feature 11). Suite 841 (691 fast + 150 slow).
  Gherkin 76/76.
- P0 video (nov-2026, a pedido): ventanas MP4 pineadas contiguas
  (test: 200f ventana == lectura única) + estimador de peso del MP4 de
  clip (`estimate_clip_mp4`: 0.03 B/px + 0.006 por punto de ruido,
  calibrado 720p bayer4 q8) en las filas del plan (trim y full, con
  pico de envolvente) + avisos 100/400MB. Pins: contigüidad, bracket
  del estimador, `envelope_peak`, fila con peso + Gherkin +1
  (clip.feature 7). Suite 817 (669 fast + 148 slow). Gherkin 72/72.

## [Unreleased] - v2.0 Fase A: clip import + timeline (DONE nov-2026)
### Added
- Clip import (`app/clip.py`): MP4/GIF/WebP vía backend de video
  (limpio `VideoBackendMissing` sin el extra), solo-sesión, tope
  120f, proxy 720p (lado largo), `trim_clip` inclusivo + `clip_duration`.
  Pinned por `tests/test_clip.py` (proxy/caps, determinismo, trim,
  backend-ausente, MP4 real).
- Timeline editor mínimo (MOTION → Clip): Open/Close clip (menú File
  y panel), info de sesión, spins Trim inicio/fin, scrub del proxy
  fuente (`app/ui/clip_controller.py`, preview visual sin audio).
  Batch sigue stills-only por diseño (sin ruta de clip).
## [Unreleased] - v2.0 Fase B: dither por frame (DONE nov-2026)
### Added
- `dither_clip` / `iter_dither_clip` (`app/clip.py`): la receta viva
  del preset por frame vía `render_spec` (seed = base + índice en
  grain/dust/slice/wave/mosh/drift/paste/pixelsort; drift 0→1 en el
  clip; flicker por frame es la estética, documentado). Streaming
  O(1) RAM para el MP4 largo de Fase C. Pinned por
  `tests/test_clip.py` (determinismo, receta, flicker con/semilla).
- Preview ditherizado en el timeline: checkbox "Dithered preview"
  (off = proxy fuente); el scrub renderiza el frame con el preset
  vivo (caché por receta, se invalida al cambiar el preset vía
  `refresh`). Sin hilos: un frame proxy es barato, el caché lo deja
  en instantáneo al revisitar.
## [Unreleased] - v2.0 Fase C: export del clip (DONE nov-2026)
### Added
- `save_clip_zip` (PNG `frame_0001.png…`, stdlib), `write_clip_mp4`
  (libx264-only, mismo writer que el MP4 de stills) y
  `mux_soundtrack` (`-c:v copy -c:a aac -shortest`, sin re-encodear;
  MP4 silencioso cuando no hay track). Pinned por
  `tests/test_clip.py` (ZIP determinista, MP4 silencioso + mux con
  WAV sintético, audios/rutas ausentes).
- Export en el timeline: FPS editable (= duración del trim),
  soundtrack opcional (Browse/X, solo se muxea en MP4), botones
  GIF/ZIP/MP4 (`{base}_clip.gif`, `{base}_frames.zip`,
  `{base}_clip.mp4`, a `out_dir`). Batch sigue stills-only.
## [Unreleased] - v1.9 Fase A: ostromoukhov + dizzy + serpentine
### Added
- Motores `ostromoukhov` (difusión de error de coeficientes variables:
  el error escala por nivel de gris, medios limpios) y `dizzy`
  (modulación IGN del umbral, estilo blue-noise, sin vetas). Ambos
  deterministas, Pillow+numpy con paridad numba bit a bit.
  Pinned por `tests/test_dither.py` (determinismo, distinción,
  paridad numpy/numba).
- Toggle `serpentine` para los 13 kernels ED (filas impares de
  derecha a izquierda, sin streaks direccionales): campo de preset,
  RenderSpec, metadata y checkbox en DITHER (solo se habilita en ED;
  el resto de motores lo ignoran). Combo/stack/GIF/batch lo heredan
  por `apply_method`. Pinned por `tests/test_dither.py` +
  roundtrip UI en `tests/test_ui_presets.py`.
- Roster 36 → 38 (`tests/test_dither.py::test_engine_roster_frozen_r14`
  y `tests/test_engines3.py` actualizados a la lista exacta nueva).
### v1.9 Fase C: color confidence — DONE (nov-2026)
- Daltonismo preview (`app/color_access.py::simulate_cvd`: matrices
  protan/deutan/tritan, display-only como safe-areas/SP-404, View →
  Daltonism preview, wipe incluido). Pinned por
  `tests/test_color_access.py` (anchors por tinta + determinismo) y
  Gherkin `color_pro.feature` (+1 escenario).
- Accesibilidad de paleta: reporte WCAG 2.1 entre tintas vecinas
  (`contrast_ratio`, `accessibility_report`: ✓ ok / ⚠ <3:1 /
  BW-collapse <1.5:1) en el hint del strip COLOR.
  Pinned por `tests/test_color_access.py`.
- Lospec offline import: parsers `.hex`/`.txt` (un `#RRGGBB` por línea)
  + `.pal` (JASC-PAL) + despacho unificado
  (`palette_library.parse_palette_path`), Import acepta
  `.json/.gpl/.hex/.txt/.pal` locales; >16 tintas trunca a 16.
  Pinned por `tests/test_color_access.py`.
- Pack curado: 16 rampas originales dark→light en `palettes/`
  (21 con las 5 previas, todas válidas 2-16 y ordenadas por
  luminancia). NIGHT re-entonada (la 2ª tinta colapsaba a 1.45:1).
### v1.9 Fase D: docs + gates — DONE (nov-2026)
- MANUAL cubre el flujo print (DPI/LPI, trap, rosetas, mirror),
  daltonismo, contraste WCAG y Lospec; fila DITHER con
  ostromoukhov/dizzy.
- QA.md al día: 65/65 escenarios (color_pro +daltonismo, morph_modes
  11), suite 738 (597 fast + 141 slow), gate gherkin a 65, línea
  flake8 sin `build_exe.py` (no existe en el repo).
- Test stale de v1.8C cazado por los gates: `bundle_zip` en el dict
  esperado de `test_batch_dialog_outputs`.
- 5/5 gates PASS (`tools/quality_metrics.py`: pass_rate 100%,
  coverage ≥80%, gherkin 65, smoke, no-leak) + flake8 limpio.
  v1.9 cerrada.
### v1.9 Fase B: print-shop — DONE (nov-2026)
- RISO trap (`sep_trap`: opción de export + prefs): expande cada tinta
  1px (`MinFilter`), el overprint esconde las hairlines de
  misregistro. Pinned por `tests/test_separations.py` (64→100px).
- Mirror-wrap (`fit_mirror` en `app/canvas.py`, `np.pad` reflect):
  tercer framing junto a stretch/blur — bleed sin smear; modo
  `mirror` en `CROP_MODES` (UI + presets + crop editor lo heredan).
  Pinned por `tests/test_canvas.py`.
- Rosetas CMYK (`standard` clásica byte-idéntica, `alt`, `single`):
  campo de preset + combo DITHER (solo CMYK). LPI ligado al DPI:
  `cmyk_lpi` (0 = celda fija 8px legacy, si no `cell = dpi/lpi`
  clamp 2–64px); preview usa 300 de referencia, el export usa el DPI
  del diálogo. Pinned por `tests/test_print.py` + UI roundtrip en
  `tests/test_ui_presets.py`.

## [Unreleased] - v1.8 Delivery (distro + social + motion + packs)
### Added
- Preset `DISTRO_3000` (1:1, 3000px, JPG q90) + validador
  `app/distro.py` (sesión viva y archivo en disco; hints honestos en el
  diálogo, nada bloqueado). Pinned por `tests/test_distro.py`.
- Extra de diálogo "Print TIFF (LZW)": `{base}.tif` full-doc RGB con
  tags de resolución.
- Presets `APPLE_MOTION` (1:1, 4000px) y `APPLE_MOTION_TALL` (3:4,
  2250×3000): dissolve en loop, primer frame = still, loop perfecto.
  Nuevo ratio `3:4` en canvas.
- Social pack en un click: `{base}_social_yt/_916/_11` (1280×720 +
  1080×1920 + 1080×1080, ancla centrada, mismo formato). Pinned por
  `tests/test_social.py` (stems, tamaños, anchor, presets, safe-areas).
- Safe-areas de texto (display-only): bandas de título sup/inf +
  recorte 1:1 de grid en `app/ui/safeareas.py`.
### v1.8 Fase C: preset-pack + batch ZIP — DONE (nov-2026)
- Preset-pack share (`app/pack.py`): File → Export/Import pack mueve
  la librería entera (presets + paletas) como un `.zip` offline con
  manifiesto; single-JSON intacto; import con validación, sin
  sobrescribir (skip + reporte) y rechazo de traversal.
  Pinned por `tests/test_pack.py` + roundtrip UI en
  `tests/test_ui_presets.py`.
- Batch "Bundle as ZIP": checkbox en el diálogo; al terminar, todo lo
  de la carpeta output va a `<output>_bundle.zip` (stdlib zipfile,
  mismo helper que usará el frame-ZIP de v2.0). Utilidad verificada en
  batch real (9 ficheros → 1 zip) — se queda.
### v2.0 Fase D: docs + gates — DONE (nov-2026)
- MANUAL: fila MOTION con clip + sección "Clip import" (input
  solo-sesión, timeline, preview ditherizado, export GIF/ZIP/MP4 con
  soundtrack opcional).
- QA.md al día: 67/67 escenarios (clip.feature +2), suite 750
  (609 fast + 141 slow), gate gherkin a 67.
- Test guard obsoleto actualizado a la regla nueva (`test_ux.py`:
  widgets de clip existen, sin modelo de layers; la vieja "no clip
  import" quedó void en v2.0).
- 5/5 gates PASS (`tools/quality_metrics.py`: pass_rate 100%,
  coverage ≥80%, gherkin 67, smoke, no-leak) + flake8 limpio.
  v2.0 cerrada.
- DPI (72–600, defecto 300) en `ExportOptions` + diálogo: tags en
  JPG/PNG/TIFF, separaciones y metadata JSON. Prefs lo recuerdan.

## [1.7.0] - 2026-11-14
### Added
- v1.7 Fase A: modos codec `bleed`/`hold`/`tear` en `app/mosh.py`
  (direccional echo, bandas P congeladas, band rolls de macrobloque;
  mismas reglas: amount/seed/size, 0=off, determinista). Combo DATAMOSH,
  FX stack y GIF mix los adoptan solos; presets viejos byte-idénticos.
  Pinned por `tests/test_mosh.py` (loops genéricos sobre los 10 modos).
- v1.7 Fase B: segment timeline (`Segment` + `plan_segments` en
  `app/anim/plan.py`, `repeats` en el engine/frames con replay
  determinista, spin Repeat ×1-8 por leg en MORPH, Length cuenta
  repeats). Pinned por `tests/test_segments.py` (6 tests).
- v1.7 Fase C: export hygiene (fingerprint de preview + badge Rebuild,
  MP4 siempre en software `libx264`, sin probing de hardware).
  Pinned por `tests/test_export_hygiene.py`.
- v1.7 Fase D: manual v1.7 (10 flavors, Repeat, Rebuild, encoder), README
  actualizado y checklist portable en QA. `tests/test_v17_release.py`
  cubre roundtrip de presets a archivo (campos nuevos + presets viejos
  byte-idénticos), determinismo/conteo de frames con repeats (GIF +
  streaming) y el camino sin extra de video (`VideoBackendMissing`
  limpio, stills/GIF intactos).
### Changed
- Versión 1.6.0 → 1.7.0 (app, pyproject, installer).
- MP4: revert del selector HW/SW antes de publicar (nunca salió en
  release; queda un solo encoder `libx264`).

## [1.6.0] - 2026-11-12
### Added
- File > New project (empty: clears image + resets to SLIME_FS defaults) and
  File > Reset settings (keep image). Opening another image keeps the recipe;
  these two are the explicit way back to init.
- IMAGE-panel "SP-404 OLED Preview: ON/OFF" toggle: same display-only flag
  as View menu, independent from the "SP-404 128x64" canvas preset button.
### Fixed
- Empty-project race: stale preview worker after New project no longer
  crashes (`'NoneType' has no attribute 'size'`); `render_still`/`on_done`
  guard `src is None` and the token is invalidated.
- Morph video preview with a 1-color custom strip no longer raises
  (`custom palette needs 2-16 colors`); morph falls back to the BW engine.

## [1.5.0] - 2026-11-11
### Added
- SP-404MKII still export: `app/sp404.py` frames any art to the
  128x64 1-bit OLED (cover-fit + luminance cut, no re-dither, optional
  white-on-black invert); the export dialog writes one `{base}_sp404.bmp`
  for the user to rename/organize on the device.
  Pinned by `tests/test_sp404.py`.
- Live OLED workflow: View > "SP-404 OLED preview" (display-only 128x64
  1-bit still preview, threshold = DITHER slider) + "SP-404 128x64"
  one-click canvas button in IMAGE (also enables the 1-bit preview).
  What you see is `sp404_frame` of the result — byte-identical to the
  exported BMP.
- `Dots shape` control: `square` (legacy kxk blocks) or `round`
  (inscribed discs, needs Dots > 1; Dots = 1 identical either way).
- New preset fields `dissolve_match` (default `smooth`) and
  `dissolve_dot_shape` (default `square`); old presets load unchanged.
### Fixed
- Morph travel no longer tears the image into Morton Z-order blocks:
  new `Match` control (`smooth` default = organic pour, `hilbert` =
  thread flow, `radial` = center-out bloom, `morton` = legacy).
- Long trails no longer repaint the source photo: ghost strength is now
  normalized by trail length (joints stay ghost-free, short trails read
  as before).
- Full tint no longer repaints the source mid-flight: dot color now fades
  with displacement (dots at home keep full color, dispersed clouds go
  abstract; joints stay black = byte-exact stills).
### Changed
- Export dialog: no output is pre-ticked anymore (was: main + thumb +
  metadata). The user picks; every box persists through prefs
  (dialog + Quick), including WebP/separations/SP-404/MP4.

## [1.3.1] - 2026-11-10
### Changed
- Portable is now a one-dir ZIP (`TRAKKART-portable-<version>.zip`): instant startup, no per-launch extraction to `%TMP%`.
- Installer installs the same one-dir build; output moved to `dist-installer/`.
- Removed the one-file build (`build_exe.py`); use `build_portable.py`.

## [1.4.0] - 2026-11-11
- Frozen CLI fix: `--cli` now seeds bundled presets/palettes like the GUI,
  so it works on a fresh machine before the first GUI launch (empty data dir
  + no repo `presets/` inside the bundle used to exit 2 with `have:` empty).
  Pinned by `test_cli_seeds_bundled_on_empty_data_dir`.
- User-facing README: real app captures, requirements,
  download/install, SmartScreen note, MANUAL + license links. The former
  developer reference moved intact to `docs/DEVELOPMENT.md`; captures are
  reproducible via `tools/capture_readme_shots.py`.
- Repo hygiene: redacted the dev profile/checkout paths from
  `docs/FLAKY_test_no_thread_storm.md` and `CHANGELOG.md`; the no-leak
  gate now scans `docs/` + top-level markdown for Windows user-profile
  paths (C:/Users/…), the local checkout path and emails, with a test
  guarding it.
- Legal: corrected `THIRD-PARTY-NOTICES.md` — the bundled FFmpeg is a
  **GPLv3** build (gyan.dev “essentials” on Windows, BtbN on Linux/macOS;
  `--enable-gpl --enable-version3`, libx264/libx265), not LGPL. The bundle
  now ships `licenses/GPL-3.0.txt` + `licenses/LGPL-3.0.txt` and a generated
  `FFMPEG-BUILD-INFO.txt` (exact binary, configure line, SHA-256, source
  links, written offer); the About box names the GPLv3 component. Tests
  guard the notice against the old claim.
- Particle density is now canvas-relative (`point_cap()`): the 120k budget
  scales with area (1200px reference, 900k hard cap). A 3000px document used
  to get the same fixed 120k dots as a 1600px preview, so it looked 3.5x
  sparser and morph color/form washed out at Full/doc; 1:1 ink density is now
  equal (~9% at both sizes). Also applies to chromatic palette stills.
- Output pixel budget (soft): docs above 36 MP (`OUTPUT_MP_BUDGET`) show an
  amber `⚠ <n> MP` in the Document panel and the export dialog with a
  tooltip explaining the render time/RAM cost. Nothing is blocked.
- Tiny-source canvas: stretch/blur frames resize with NEAREST when the
  source is 64px or less (a stretched checkerboard keeps its inks) and the
  blur radius is now `max(1, min(w, h) / 24)` instead of an 8px floor, so a
  small canvas no longer becomes one flat smear.
- The preview zoom badge is clickable: Fit <-> 100% (same flags as the
  View menu).
- Morph travel is now the default (`dissolve_travel` 1.0 = pour; 0 still
  selects the legacy cloud-reform path byte-identical). Dots stay on-canvas
  through the transition instead of bursting off-frame, so color and form
  return together; MORPH Travel slider initial is 100.
- ASCII mode integration: `ascii` config in Preset/RenderSpec/metadata
  (charset + presets, columns 20-300, gamma, color mono/source/palette,
  ink/bg, invert, Bayer dither); DITHER page box visible only for `ascii`;
  `pixel_size` ignored (columns rule); fonts bundled
  (`app/fonts/JetBrainsMono-Regular.ttf`, OFL in THIRD-PARTY-NOTICES).
- Canvas preview redesign: the fixed 520px QLabel is now a fit/zoom/pan
  canvas (`app/ui/preview_canvas.py`). Fit fills the viewport (small images
  up to 3x), 100% is real 1:1 (not 4x), wheel zooms at the cursor, drag pans,
  double-click fits, and a big pixmap can no longer force the window wider
  (minimumSizeHint stays 200x200). The title row shows Fit / %.
- 100% now renders full/document pixels on demand (async for heavy presets;
  document size when the source has enough detail) instead of 1:1 of the
  proxy. The preview proxy is adaptive (640px floor, viewport-sized up to
  1600px, HiDPI aware) and resizing schedules one debounced Live re-render.
- Wipe compare is draggable directly on the canvas (left drag; middle-drag
  pans), keeping the slider in sync. Wipe 100% keeps the framed original
  (no raw-source geometry jump), safe-area guides stay visible during wipe,
  and the aligned original is cached per canvas state (wipe ticks ~28ms on
  a 12MP source, was 75-311ms).
- Crop editor contain/stretch/blur cache their canvas + pixmap: repaints are
  ~1-4ms on a 12MP photo instead of 160-520ms.
- Canvas correctness (bug hunt): `contain` no longer inflates the working
  canvas (a 3000x2000 landscape into 9:16 used to render 3000x5333; it now
  caps at the document long side), `cover` can no longer return a 0-pixel
  side (1px sources + extreme custom ratios), exports validate empty renders
  before writing and build the thumbnail first (no partial bundles), vector
  grids cap at the document size so large sources/`contain` no longer trip
  the cell limit, and changing the ratio inside the crop editor now keeps
  W/H in sync with the main canvas (label/export/metadata agree).
- CI fix (#148): `test_debounce_coalesces_renders` mocked
  `render_service.render_full`, but previews have rendered through `app.gpu.*`
  since `5ea3e58`, so the counter stayed at 0. The test now patches the stable
  `preview_controller.render_still` seam and delegates to the real render.
  `QA.md`/`MAINTENANCE.md` document the rule (and the no-hardcoded-local-paths
  rule from `64e5d0c`) so it does not come back.

## v1.3.0 — 2026-11-03
- CI fix: subprocess tests used a hardcoded local checkout path (`cwd`) and failed on runners with `NotADirectoryError`; both now use the repo root (`Path(__file__).parents[1]`).
- Docs synced to reality: 572 tests (440 fast + 132 slow) + 61 Gherkin scenarios + 13 bundled presets (`README.md`, `MAINTENANCE.md`, `QA.md`, `ROADMAP.md` handoff); numba ships in the bundle with numpy fallback (was documented as optional).
- Correctness (R4): `normalize_stack` warns on unknown effect ids instead of dropping them silently; preview compensates pixel-unit FX (`glow_radius/border/scanlines/grille/halftone/letterbox`) by the downscale factor; `RenderSpec.meta()` now includes grade/texture/drift/paste/motif blocks.
- No more GUI freezes: preview slots no longer `wait(5000)` on the worker (token + `deleteLater`, re-queue on pending); single export runs on an `ExportWorker` thread with snapshotted inputs (tests keep the sync path via `win._export_sync`).
- R2 split (zero logic change, byte-identical, shims keep every import working): `app/disintegrate.py` (1252 → 33 lines) is now `app/particles/` (modes/fields/color/raster/travel/engine); `app/gif.py` (935 → 48 lines) is now `app/anim/` (limits/plan/io/frames). Shared `_resolve_anim_spec()` helper removes the duplicated preset→spec prologue in the 4 particle builders.
- Removed BPM beat grid (too fiddly): no more ♫ BPM/Bars row + Set Hold in VIDEO, no `apply_bpm()`/`hold_for_target()`.
- Fixed morph crash with travel/tint on multi-leg chains (closed loop or 2+ chain images): per-frame color temps shadowed the frame budget (`base`) and legs after the first blew up with "truth value of an array is ambiguous". Pinned by a regression test (plus a 1024-combo sweep).
- Error reporting you can actually use: every failure logs a numbered report (`[E0007]`: action + params + full traceback) to `trakkart.log`; workers report in-thread so nothing is lost crossing threads; the UI shows a plain-language hint + code instead of raw tracebacks; Help → Copy last error report copies the full report for bug reports.
- Sacred Length (editable total, all modes): the VIDEO Length spin is editable again (0.5–60s) — particle modes solve the Hold needed to reach it (clamped 0–3s, honest short-message), other modes set n = Length x FPS (Frames combo shows the derived total, capped at 256f); FPS changes keep the seconds and only gain/lose frames; Hold-manda (no pad) stays the engine rule; no new preset fields (`dissolve_length` stays ignored compat). Non-particle GIF/MP4 lists cap at 256f.
- Customizable keyboard shortcuts: single registry (`app/shortcuts.py`) drives menus, method-step keys and hold-to-compare — no more hardcoded strings drifting from the reference table. Help → Keyboard shortcuts is now an editor (click a cell, press keys; Esc cancels, Del clears, conflicts refused naming the other action, Reset defaults). Bindings persist in `shortcuts.json` (portable data dir, travels with your data). Previous/Next method now show Alt+Left/Right in the menu itself.

## v1.2.0 — 2026-11-02
- Morph F3 travel/pour (§7.6): `dissolve_travel` 0-1 preset field + MORPH Travel slider; non-blocks legs pour src→dst through seeded-greedy 1:1 matching (uneven counts padded, empties fall back to legacy); leg joints stay byte-exact, stagger shifts the pour, ease gates the cloud; travel=0 keeps the legacy cloud path byte-identical; strict 0=off still hard-cuts. Gherkin 57.
- Morph F4 color particles (§7.6): `dissolve_tint` 0-1 preset field + MORPH Tint slider; dots carry their source colors mid-flight (travel legs lerp src→dst hues), gated by the loop envelope so joints land black = byte-exact stills; tint=0 keeps the legacy BW path byte-identical; strict 0=off freezes tint too; blocks tints its pops. Gherkin 58.
- Morph F5 motion trails (§7.6): `dissolve_trail` 0-8 preset field + MORPH Trail slider; past dots linger as fading ghosts (BW gray / tinted hues), strength = decay(age) x loop envelope so joints stay ghost-free = byte-exact stills; trail=0 keeps the legacy path byte-identical; strict 0=off skips ghosts; works in dissolve, morph legs, travel and blocks. Gherkin 59.
- Morph F6 Heckel shade (§7.6): `dissolve_shade` bool preset field + MORPH Shade checkbox; dot size scales with source darkness (dark→full `dissolve_dotsize`, light→1px), envelope-gated so joints stay 1px; shade off or Dots=1 keeps the legacy path byte-identical; works in dissolve, morph legs, travel and blocks. Gherkin 60.
- Morph F7 palette following: morph animates the graded still — IMAGE adjust (brightness/contrast/saturation/mid/highlights) grades the dots, COLOR palette prints the inks (chromatic palettes render full-strength dots, joints = ink stills = holds, no pop); BW/SLIME-less presets keep the legacy path byte-identical; strict 0=off holds; works with travel/tint/trail/shade/blocks. Gherkin 61.

## v1.1.0 — 2026-11-02
- Exact-canvas MP4 (R5): `mp4_dims` always even + `macro_block_size=2` in
  both writers — 1080x1920 ships as 1080x1920 (was 1088x1920), 404x720 intact,
  721x721 -> 720x720.
- MP4 faststart (R6): `-movflags +faststart` in `write_mp4`/`write_mp4_iter`
  (moov before mdat, progressive playback).
- Morph loop closure: new `dissolve_loop` preset field + MORPH "Loop (last → first)" checkbox (default ON); the last form morphs back into the first (byte-identical joint), A's hold split across both loop ends; ping-pong skipped when the loop is closed.
- Equal holds: Length pad shared across every form (≤1 frame apart) instead of all-to-last; per-joint hold lists end-to-end (engine + GIF + streaming + labels).
- Honest MP4 weight: MP4 size selector (Canvas/1080p/720p, default 1080p; stills stay full-doc) + content-aware estimate (transitions ~0.43 B/px, holds ~0.011 B/px, calibrated) + heavy-file hints.
- Export dialog fix: animation spec always comes from the live VIDEO section, never stale prefs (morph leaked into mix exports); session chain gated by mode in export + preview.
- Length 0.5–60s via MP4 streaming (up to 3600f, O(1) RAM); GIF/preview stay capped at 256f with honest labels.
- Hold-manda: clip total = transitions + holds (no Length pad); Length is now a derived readout (read-only spin); `dissolve_length` kept as ignored compat; holds only yield to the frame cap.
- Canvas delivery (R1+R2+R3): bundled `CANVAS_916` (9:16 1080x1920, dissolve 64f/30fps/Hold 2.7 = 7.53s loop); Canvas check hints (duration label for 3–8s, export dialog for 720p/1080p); ♫ BPM/Bars row solves Hold for the beat grid (`hold_for_target`).
- Social recipes (R4): bundled `YT_THUMB` (16:9 1280x720), `SQUARE_11` (1:1 1080x1080), `PORTRAIT_45` (4:5 1080x1350); master = `CANVAS_916`.
- Animated WebP (R7): `save_webp()` mirrors the GIF frames (full color, ~1/3 weight) to `{base}_anim.webp`; dialog checkbox with plan + collision cover; dialog-only like MP4.
- Honest GIF/WebP weight (R8): hold-collapse-aware estimates (transitions full cost + 1 frame per still form; measured 12.7x→3.8x over on real 480p dither).
- Ink separations (R9): one PNG per palette ink + corner registration marks (`{base}_sep_{NN}_{RRGGBB}.png`, dialog-only, pairs with Vector Pro black-ink).
- Headless CLI (R10): `TRAKKART.exe --cli --preset X --in ... --out ...` (file/folder, batch bundle, skip-existing, exit 0/1/2, Qt-free; MP4/WebP/seps stay dialog-only).
- Watch folder (R11): File → Watch folder auto-batches arrivals with a fixed preset (2s debounce, 3s settle, skip-existing, sequential, stateless, no modals).
- Morph F1 (§7.7): 11 particle fields (burst/suction/vortex/rain/rise/wave/ripple/flow/blocks) × 5 staggers (joint-pinned) × 3 eases; legacy wind/off/sine byte-identical; MORPH combos; Gherkin 55.
- Morph F2 (§7.7): elastic/bounce eases + dot-size swell (`dissolve_dotsize` 1-4, joints at 1px) + bundled EMBER_RISE/GRAVITY_DROP/POUR_FAKE; Gherkin 56.
- Engine roster frozen at 36 (R14 decision, exact-list test; particle fields are a separate axis).
- Perf round (measured): streaming `save_gif` (peak ~-70%, byte-identical) + GIF RAM budget guard (`MAX_GIF_PIXELS`, fail-fast MemoryError); lazy numba import (startup 0.86→0.39s, parity intact); history prune-when-needed + fast prune test (29→0.8s); bilinear MP4 downscale (~5s per long export); dropped duplicate `-pix_fmt` (warning-only).
- Polish (R12+R13): 9:16 safe-area chrome guides (still preview + crop editor, View toggle, display-only) + wipe compare slider (ORIGINAL/result divider, aligned canvas, survives refreshes).

## v1.0.1
- New icon: 05_bayer_dots (TRAKK SUITE dark + amber).
- Fixed flaky thread-storm test (pending guard + slot release in preview controller).
- Build gate: fast parallel `-n auto -m "not slow"` by default, `--full-tests` for release.
- Copy cleanup: no GPL/clean-room disclaimers, no competitor names; MANUAL fully in English.
- MANUAL.md bundled in English.

## v1.0.0
- First stable: single flavor with numba + MP4 bundled, portable + installer.
- Minimal identity: window title and header without taglines.
- Test speed: pytest-xdist in dev deps; fast loop is now `-n auto`
  (~11x: 6.4 min → ~35 s locally). CI split: fast suite + lint per push,
  full suite nightly + on demand. CI actions bumped off deprecated Node 20.
- CI fixes: MP4 export test skips without the video extra (was a hard
  VideoBackendMissing on runners without imageio); thread-storm test is now
  deterministic (gate-held worker instead of a wall-clock race).
- Single flavor v1: numba + MP4 always bundled (light/full split removed;
  `requirements-video.txt` merged into `requirements.txt`; Extras group is
  now status-only in the exe).
- Settings → Extras: accel/MP4 state with 1-click pip install on dev (threaded);
  frozen exe points to TRAKKART-full.exe. MP4 tooltip updated.
- Portable user data: presets/palettes now live in `data/` (seeded from
  bundled, user edits shadow them); frozen-safe, test seams preserved.
- Release build: exe embeds version metadata; bundled MANUAL.md + icon;
  optional Authenticode signing via `TRAKKART_PFX` (`installer/SIGNING.md`).
- Installer: `installer/trakkart.iss` (Inno Setup 6, EN/ES) + builder
  `build_installer.py` (version from `app.__version__`, signs the setup too).
- User manual: `MANUAL.md` (ES) bundled with the app; Help → User manual (F1).
- Session restore: reopens last image + preset on startup (opt-out in
  Settings); Help → Show logs folder (prefs/db/`trakkart.log`).
- Undo/redo: 20-level `ImageHistory` with redo branch; Edit → Redo (Ctrl+Y).
- Settings backup: Export…/Import… of the full `.json` (validated import).
- Prefs hardened: every numeric/enum clamped (`normalize_prefs`); writable
  output resolution (`resolve_out_dir`); shared dialog builders
  (`app/ui/dialog_fields.py`), Settings split into `settings_flow` + builders.
- Grouped menus (File/Edit/View/Help with separators; clipboard in Edit).
- Panel as a 5-page accordion: IMAGE / DITHER / COLOR / FX / MOTION.
- VIDEO preview ON pre-checks Animation GIF in the Export dialog.
- Help → About TRAKKART; post-export dialog with Show in folder.
- Help → Keyboard shortcuts; File → Open recent (last 5, in prefs).
- Refactor P1+M2: CropView caches its pixmap across paints (invalidated by
  identity on rotate); filename sanitizers unified in `app/names.py`
  (byte-identical outputs).
- MOTIF section only visible for method `motif`; friendlier empty canvas.
- File logging (`data/trakkart.log`, rotating) + friendly crash dialog.
- Crop editor zoom/pan loop fixed (owned box, exact anchor, frame follows
  finger, anchor clamped over black bars, free corner/edge positioning).
- Datamosh module (`app/mosh.py`): 7 flavors (blocks legacy byte-identical +
  smear/ghost/rows/chroma/crush/speckle), `mosh_mode`/`mosh_seed`/`mosh_size`
  preset fields, dedicated DATAMOSH page (mode/amount/size/seed+dice),
  same envelope in GIF mix.
- Export naming: MP4 shares the GIF stem (`*_anim.mp4`, was `*_clip.mp4`);
  sanitizer collapses/trims (`mi cover!` → `mi_cover`); dedicated File name
  section (live preview + Reset); accepted dialogs no longer hoard hidden
  windows (fixes E2E modal flake).
- MOTION duration readout: live `= Xs loop` label from frames ÷ fps (no
  driver spin: three linked controls disagreed; readout never lies). No new
  preset fields.
- Animation suffixes: `{base}_gif.gif` + `{base}_vid.mp4` (lowercase pair;
  legacy `_anim.gif` writer untouched for compat).
- FPS combo: preset default 8 is a first-class entry; custom values insert
  sorted instead of dangling at the end.
- `build_exe.py` excludes numba/llvmlite/imageio (base exe stays light per
  policy); `dist/TRAKKART.exe` rebuilt (66MB) + offscreen smoke green.
- Stale export names fixed: prefs remember their image (`src_name`); a new
  image gets a fresh default (dialog opens instead of silent quick reuse);
  pasted/dropped/downloaded pixels get `pasted_YYYYMMDD_HHMMSS`.
- Collision policy fixed to rename: existing files are never replaced nor
  skipped (repeats save as `name_2`, `name_3`); batch keeps its own policy.
- Collision alert: post-Accept modal lists clashing files (Overwrite / Rename
  as `base_2` / Cancel, safe default Rename); plan shows a ⚠ hint; quick stays
  silent-rename. Test seam hardened (visible-dialog accept, no modal in CI).
- CHANGELOG started (this file).

## v0.18.0
- Iteration UX: viewport Full/Live/Still, fast/slow debounce, in-app tutorial
  + offline samples, 4 themes, batch in File menu.
- Panel clipping fixes, video-proxy combo restore, layout audit tests.
- 375 tests, 51 Gherkin scenarios, 5/5 gates (coverage 92.1%).

## v0.17.0
- Lock-free threaded preview + ValueSlider on every slider.

## v0.16.0 — v0.15.0
- Safe drop classification with ON/OFF batch-drop toggle.
- Anti-freeze hardening: size guards, 350ms debounce, batch cancel,
  vector cap, history prune, action bar outside the scroll.

## v0.14.0 — v0.11.0
- Text layer removed. Numba optional accelerator (bit-identical).
- Multiprocess batch, animated GIF (Pillow only), TRAKK SUITE theme.

## v0.10.0 — v0.7.0
- Image ops + undo, randomize, zoom, drag&drop, clipboard, glitch pack.
- Vector SVG export. Halftone/cluster/diffusion engines. Pre/post FX.

## v0.6.0 — v0.2.0
- Canvas ratios + crop, portable data dir, SQLite history, custom icon.
- Adjustments (brightness/contrast/saturation), JSON presets, folder batch.

## v0.1.0
- Initial modular app: ordered + Floyd-Steinberg dither, 4 original
  palettes, PySide6 preview, canvas-size export + 1080p thumb + metadata.
