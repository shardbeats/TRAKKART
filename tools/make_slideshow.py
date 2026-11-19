"""Build TRAKKART promo slideshow MP4 from real screenshots + demo art."""
import os, subprocess
from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "out", "video_promo")
os.makedirs(OUT, exist_ok=True)

W, H = 1920, 1080
def fit(img_path):
    im = Image.open(img_path).convert("RGB")
    im.thumbnail((W, H-220), Image.LANCZOS)
    return im

slides = [
    ("TRAKKART — cover-art studio offline", "docs/screenshots/main-window.png"),
    ("36 motores de dither", "docs/screenshots/dither-panel.png"),
    ("Color: paletas TRAKK + SOURCE", "out/v19_floyd.png"),
    ("FX + datamosh + particulas", "out/v19_dizzy.png"),
    ("Export bundle: PNG + GIF + MP4 + SVG", "docs/screenshots/export-dialog.png"),
    ("100% local. Sin cuentas. Sin subidas.", "out/v19_ostromoukhov.png"),
]

frames_dir = os.path.join(OUT, "frames")
os.makedirs(frames_dir, exist_ok=True)
paths = []
for i, (title, rel) in enumerate(slides):
    src = os.path.join(REPO, rel)
    canvas = Image.new("RGB", (W, H), (10, 8, 20))
    d = ImageDraw.Draw(canvas)
    d.text((80, 60), f"{i+1}/6  {title}", fill=(245, 166, 35))
    d.text((80, 990), "TRAKKART - ShardBeats TRAKK SUITE", fill=(150, 150, 150))
    if os.path.exists(src):
        im = fit(src)
        canvas.paste(im, ((W-im.width)//2, (H-im.height)//2 + 20))
    else:
        d.text((80, 500), f"falta {rel}", fill=(255, 80, 80))
    p = os.path.join(frames_dir, f"slide_{i:02d}.png")
    canvas.save(p)
    paths.append(p)

mp4 = os.path.join(OUT, "trakkart_slideshow.mp4")
# 4s per slide = 24s total, 30fps, zoompan-free simple concat
subprocess.run(["ffmpeg", "-y", "-framerate", "1/4",
    "-i", os.path.join(frames_dir, "slide_%02d.png"),
    "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p", mp4],
    check=True, cwd=REPO)
print("OK", mp4, os.path.getsize(mp4))
