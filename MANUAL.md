# TRAKKART — Manual de usuario

Generador offline de portadas con dithering. 100% local: nada se sube,
nada se rastrea. Tus datos viven en tu equipo (carpeta de datos de la app).

## Instalación

- **Instalador:** ejecuta `TRAKKART-Setup-<versión>.exe` (acceso directo en
  el menú inicio + manual incluido).
- **Portable:** copia `TRAKKART.exe` donde quieras y ejecútalo.
- **Primer arranque:** Windows SmartScreen puede avisar si la build no está
  firmada: *Más información → Ejecutar de todas formas*.
- **Requisitos:** Windows 10/11 de 64 bits. Sin internet, sin instalación
  de Python. Para vídeo MP4: `pip install -r requirements-video.txt`
  (extra opcional).

## Inicio rápido (5 pasos)

1. **Abre una imagen:** File → Open (Ctrl+O), arrástrala a la ventana o
   pégala (Ctrl+V). También valen carpetas (ver Batch).
2. **Elige método:** los botones ◀ ▶ cambian entre 36 motores de dithering.
3. **Ajusta color:** SOURCE extrae la paleta de tu imagen, Depth limita
   tonos, los dados (🎲) remezclan sin perder lo bueno (candados 🔒).
4. **Anima (opcional):** el panel VIDEO previsualiza; GIF/MP4 salen al
   tamaño del documento.
5. **Exporta:** Export… (Ctrl+Shift+S) o Quick export (Ctrl+S) que repite
   tu última configuración. SVG para logos, JSON para metadatos.

## Paneles

| Panel | Qué hace |
|---|---|
| IMAGE | abrir, rotar, voltear, invertir, crop visual, tamaño CANVAS |
| DITHER | preset, método, píxel, motif |
| COLOR | ajustes, duotono/marca, tira custom, biblioteca de paletas |
| FX | pre/grade/textura/glitch + pila ordenable de efectos |
| DATAMOSH | sabores mosh + cantidad + semilla |
| MOTION | preview de vídeo + Signal Drift |

**Viewport** (View): Full = render inmediato; Live = con retardo (rápido
120ms / pesado 350ms); Still = solo manual (F5). Para equipos lentos o
lienzos enormes usa Still.

## Exportar
- **File name:** base para todos los archivos (caracteres raros → `_`).
- **Folder:** destino; por defecto el de Settings.
- **Format/Quality/Size:** el tamaño lo manda el CANVAS del documento.
- **Include:** imagen principal, thumb 1080p, vector SVG, GIF, JSON.
- **Colisión:** nunca se pierde nada — si el nombre existe se propone
  `nombre_2`, `nombre_3`… (o Overwrite si lo eliges).
- **Quick export** repite la última configuración sin preguntar. Si cambias
  de imagen, vuelve a preguntar (no reutiliza el nombre anterior).

## Batch (carpetas)

File → Batch folder (Ctrl+B): elige entrada/salida, Jobs 1-8
(1 = secuencial seguro, más = multiproceso), formato y salidas por
operación. Con `Drop=Batch` activado, arrastrar una carpeta pregunta
directamente si procesarla.

## Presets y Settings

- **Presets:** la combo guarda la receta actual (Save…), Export/Import
  comparte `.json` offline.
- **File → Settings (Ctrl+,):** carpeta de salida por defecto, formato/
  calidad/tamaño y salidas por defecto, jobs, Drop=Batch, viewport
  inicial, recetas recientes y carpeta de datos.
- **Backup:** en Settings, Export…/Import… guardan o restauran todo el
  `.json` de configuración.
- **Sesión:** por defecto reabre tu última imagen y preset al arrancar
  (se desactiva en Settings).

## Extras opcionales (aceleración + MP4)

El `.exe` ligero no los trae (más lento en Floyd grande, sin MP4):

- **Aceleración numba (10-50x):** Settings → Extras → Instalar aceleración.
- **Vídeo MP4:** Settings → Extras → Instalar vídeo.
- En versión de desarrollo se instalan con pip desde la propia app
  (tarda minutos, necesita internet y reiniciar).
- En el `.exe` no se pueden instalar: descarga **TRAKKART-full.exe**
  (los trae incluidos) o usa el instalador correspondiente.
- Tus presets y paletas viven en la carpeta de datos (`data/presets`,
  `data/palettes`): copia esa carpeta y viajan contigo a otro equipo.

## Editar imagen

- **Deshacer/Rehacer:** Edit → Undo (Ctrl+Z) / Redo (Ctrl+Y), 20 niveles.
- **Comparar:** mantén Espacio o *Hold to compare* para ver el ORIGINAL.
- **Zoom:** Ctrl+= / Ctrl+- / Ctrl+0 (fit) / Ctrl+1 (100%).

## Atajos principales

| Acción | Atajo |
|---|---|
| Abrir / Exportar / Quick export | Ctrl+O / Ctrl+Shift+S / Ctrl+S |
| Batch | Ctrl+B |
| Deshacer / Rehacer | Ctrl+Z / Ctrl+Y |
| Sorpréndeme | Ctrl+R |
| Copiar resultado / Pegar | Ctrl+C / Ctrl+V |
| Refresh / Método anterior/siguiente | F5 / Alt+Left / Alt+Right |
| Manual | F1 |

Ver lista completa: Help → Keyboard shortcuts.

## Privacidad y datos

- Cero red: TRAKKART no hace ninguna conexión (salvo que arrastres una
  URL de imagen, a petición tuya).
- Cero rastreo: sin telemetría ni cuentas.
- Dónde está todo: Help → Show logs folder (prefs, base de datos,
  `trakkart.log`). Borrar esa carpeta restablece la app a fábrica.

## Problemas comunes

- **La app no abre una imagen:** formato no soportado (usa PNG/JPG/WebP/
  BMP) o imagen gigante (límite 8000px / ver mensaje exacto).
- **Va lenta:** cambia a viewport Still o baja el tamaño CANVAS.
- **MP4 desactivado:** instala el extra de vídeo (arriba).
- **Algo se rompió:** Help → Show logs folder, adjunta `trakkart.log`
  al reportar el bug. Versión exacta: Help → About.
