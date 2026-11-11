"""TRAKKART screenshot driver: real window grabs for the user README.

Isolated data dir (TRAKKART_DATA_DIR) so no personal paths leak into shots.
Outputs: docs/screenshots/{main-window,dither-panel,export-dialog}.png + anim-preview.gif
"""
import os
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTDATA = os.environ.get("TRAKKART_SHOT_DIR", "").strip() or tempfile.mkdtemp(prefix="trakkart-shots-")
OUT = os.path.join(REPO, "docs", "screenshots")

os.environ["TRAKKART_DATA_DIR"] = SHOTDATA
os.makedirs(SHOTDATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, REPO)

from PIL import Image, ImageDraw


def make_source(path):
    W, H = 1080, 1350
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(12 + 60 * t)
        g = int(8 + 20 * t)
        b = int(40 + 140 * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    d = ImageDraw.Draw(im)
    d.ellipse([W * 0.22, H * 0.10, W * 0.78, H * 0.48], fill=(255, 150, 60))
    d.ellipse([W * 0.28, H * 0.15, W * 0.72, H * 0.43], fill=(255, 90, 120))
    for i in range(12):
        y0 = int(H * 0.55 + i * H * 0.037)
        d.line([(0, y0), (W, y0)], fill=(245, 166, 35), width=2)
    d.polygon([(0, H), (0, H * 0.62), (W * 0.3, H * 0.45),
               (W * 0.55, H * 0.62), (W, H * 0.50), (W, H)], fill=(16, 10, 26))
    d.text((W * 0.08, H * 0.86), "NEON / COVER", fill=(245, 245, 245))
    d.text((W * 0.08, H * 0.90), "TRAKKART STUDIO", fill=(245, 166, 35))
    im.save(path, "PNG")
    return path


def wait_result(win, timeout=40):
    from PySide6.QtWidgets import QApplication
    t0 = time.time()
    while time.time() - t0 < timeout:
        QApplication.processEvents()
        if getattr(win, "result", None) is not None:
            QApplication.processEvents()
            time.sleep(0.6)
            QApplication.processEvents()
            return True
        time.sleep(0.25)
    return False


def main():
    from PySide6.QtWidgets import QApplication

    src = make_source(os.path.join(SHOTDATA, "source.png"))

    app = QApplication(sys.argv[:1])
    app.setApplicationName("TRAKKART")
    app.setOrganizationName("ShardBeats")

    from app.ui.main_window import MainWindow
    win = MainWindow()
    win.resize(1440, 900)
    win._load_path(src)
    try:
        from app.ui.params_controller import apply_preset
        apply_preset(win, "SLIME_FS")
    except Exception as e:
        print("preset warn:", e)
    win.show()
    app.processEvents()
    ok = wait_result(win)
    print("render ready:", ok)
    time.sleep(1.0)
    app.processEvents()

    shot_main = os.path.join(OUT, "main-window.png")
    pm = win.grab()
    pm.save(shot_main, "PNG")
    print("saved", shot_main, pm.width(), "x", pm.height())

    # Dither panel close-up: open the DITHER accordion page, grab its content.
    pages = getattr(win, "_accordion_pages", [])
    for btn, content in pages:
        try:
            if "DITHER" in btn.text().upper():
                btn.setChecked(True)
                break
        except Exception:
            pass
    app.processEvents()
    time.sleep(0.8)
    app.processEvents()
    shot_dither = os.path.join(OUT, "dither-panel.png")
    for btn, content in pages:
        try:
            if "DITHER" in btn.text().upper() and content.isVisible():
                content.grab().save(shot_dither, "PNG")
                print("saved", shot_dither)
                break
        except Exception as e:
            print("dither grab warn:", e)

    # Export dialog: real dialog with a neutral plan.
    from app.exporter import ExportSelection
    from app.ui.export_dialog import ExportDialog
    img = getattr(win, "result", None) or Image.open(src)
    sel = ExportSelection()
    sel.image, sel.thumb_1080p, sel.vector, sel.anim, sel.metadata = True, True, True, True, True
    dlg = ExportDialog(img, {"preset": "SLIME_FS"}, base="neon_cover",
                       out_dir="out", selection=sel, parent=win)
    try:
        dlg.chk_webp.setChecked(True)
    except Exception:
        pass
    dlg.show()
    app.processEvents()
    time.sleep(0.8)
    app.processEvents()
    shot_export = os.path.join(OUT, "export-dialog.png")
    dlg.grab().save(shot_export, "PNG")
    print("saved", shot_export)
    dlg.close()

    # Animated preview: genuine product GIF (phase/hue march), small for docs.
    try:
        from app.presets import load_preset
        from app.anim.frames import gif_frames
        from app.anim.io import save_gif
        preset = load_preset("SLIME_FS")
        frames = gif_frames(img.convert("RGB"), preset, frames=8, mode="both", max_side=480)
        gif_path = os.path.join(OUT, "anim-preview.gif")
        save_gif(frames, gif_path, fps=8)
        print("saved", gif_path, os.path.getsize(gif_path), "bytes")
    except Exception as e:
        print("gif warn:", repr(e))

    # Downscale stills to doc-friendly widths.
    for name, maxw in (("main-window.png", 1600), ("dither-panel.png", 1200),
                       ("export-dialog.png", 1200)):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            im = Image.open(p)
            if im.width > maxw:
                im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
                im.save(p, "PNG")
                print("scaled", name, im.width, "x", im.height)

    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
