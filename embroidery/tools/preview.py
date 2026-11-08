"""Thread-style preview of embroidery files, read back with pyembroidery (what the machine reads).
usage: preview.py OUT.png PX_PER_MM FILE[=caption] [FILE[=caption] ...]
All files are drawn at the same scale, stacked vertically, as seen from the top of the fabric."""
import sys, pyembroidery as pe
from PIL import Image, ImageDraw, ImageFont

def shade(hexc, f):
    r, g, b = (int(hexc[i:i+2], 16) for i in (1, 3, 5))
    return tuple(max(0, min(255, int(c * f))) for c in (r, g, b))

def draw_design(path, px_per_mm, ss=3, thread_mm=0.32):
    p = pe.read(path)
    x0, y0, x1, y1 = p.bounds()
    k = px_per_mm / 10 * ss              # pixels per 0.1 mm at supersampled size
    pad = int(3 * px_per_mm * ss)
    W, H = int((x1 - x0) * k) + 2 * pad, int((y1 - y0) * k) + 2 * pad
    img = Image.new("RGB", (W, H), (246, 244, 238))
    d = ImageDraw.Draw(img)
    colors = [t.hex_color() for t in p.threadlist] or ["#000000"]
    ci, prev = 0, None
    w = max(1, int(thread_mm * px_per_mm * ss))
    for x, y, cmd in p.stitches:
        c = cmd & pe.COMMAND_MASK
        pt = ((x - x0) * k + pad, (y - y0) * k + pad)
        if c == pe.STITCH and prev is not None:
            col = colors[ci % len(colors)]
            d.line([prev, pt], fill=shade(col, 0.75), width=w)
            d.line([prev, pt], fill=shade(col, 1.15), width=max(1, w // 3))
        elif c == pe.COLOR_CHANGE:
            ci += 1
        prev = pt
    img = img.resize((W // ss, H // ss), Image.LANCZOS)
    return img, (x1 - x0) / 10, (y1 - y0) / 10

def main():
    out, ppm = sys.argv[1], float(sys.argv[2])
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    panels = []
    for arg in sys.argv[3:]:
        path, _, cap = arg.partition("=")
        img, w, h = draw_design(path, ppm)
        panels.append((img, f"{cap}   ({w:.1f} x {h:.1f} mm)".strip()))
    W = max(i.width for i, _ in panels) + 40
    H = sum(i.height + 50 for i, _ in panels) + 10
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    y = 10
    for img, cap in panels:
        d.text((20, y), cap, fill="black", font=font)
        sheet.paste(img, (20, y + 36))
        y += img.height + 50
    sheet.save(out)
    print(out, sheet.size)

main()
