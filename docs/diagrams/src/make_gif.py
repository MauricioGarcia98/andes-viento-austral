"""Une los frames de render_frames.mjs en un GIF optimizado: python make_gif.py <frames_dir> <out.gif>"""
import json
import sys
from pathlib import Path

from PIL import Image

frames_dir, out = Path(sys.argv[1]), sys.argv[2]
manifest = json.loads((frames_dir / "manifest.json").read_text())
images = [Image.open(m["file"]).convert("RGB") for m in manifest]
palette_src = images[-1].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
frames = [im.quantize(palette=palette_src, dither=Image.Dither.NONE) for im in images]
frames[0].save(out, save_all=True, append_images=frames[1:], duration=[m["ms"] for m in manifest],
               loop=0, optimize=True, disposal=1)
print(out, f"{Path(out).stat().st_size / 1e6:.1f} MB")
