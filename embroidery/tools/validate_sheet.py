"""Independent checks of framed multi-name .jef sheets (raw bytes + pyembroidery).
usage: validate_sheet.py sheets.txt folder max_w_mm max_h_mm [frame_w frame_h border]"""
import math
import os
import struct
import sys

import pyembroidery as pe


def parse(path):
    """Raw JEF walk -> header, list of color blocks; each block = list of pieces (stitch lists split at trims),
    plus counts of moves that are not preceded by a trim (loose threads)."""
    b = open(path, "rb").read()
    off = struct.unpack_from("<i", b, 0)[0]
    ncol, npts, hoop = struct.unpack_from("<iii", b, 24)
    palette = list(struct.unpack_from("<%di" % ncol, b, 0x74))
    types = list(struct.unpack_from("<%di" % ncol, b, 0x74 + 4 * ncol))
    data = b[off:]
    i = 0; units = 0; x = y = 0; zero = 0; end = False; maxd = 0; unknown = []
    blocks = [[[]]]; loose = 0; after_trim = True
    while i + 1 < len(data):
        if data[i] == 0x80:
            op = data[i + 1]
            if op == 0x10:
                units += 1; end = True; break
            dx, dy = struct.unpack("bb", data[i+2:i+4]); dy = -dy
            maxd = max(maxd, abs(dx), abs(dy)); i += 4; units += 2
            if op == 0x01:                       # color change: new block, machine cuts thread
                blocks.append([[]]); after_trim = True; zero = 0
                x += dx; y += dy
                continue
            if op != 0x02:
                unknown.append(op); continue
            if dx == 0 and dy == 0:
                zero += 1
                if zero == 3:                     # trim = 3 zero-length jumps
                    blocks[-1].append([]); after_trim = True; zero = 0
                continue
            zero = 0
            if blocks[-1][-1] and not after_trim:
                loose += 1                        # move inside a piece without a trim
            x += dx; y += dy
        else:
            dx, dy = struct.unpack("bb", data[i:i+2]); dy = -dy
            maxd = max(maxd, abs(dx), abs(dy)); i += 2; units += 1; zero = 0
            x += dx; y += dy
            blocks[-1][-1].append((x / 10, y / 10)); after_trim = False
    blocks = [[p for p in blk if p] for blk in blocks]
    return dict(off=off, ncol=ncol, npts=npts, hoop=hoop, palette=palette, types=types, units=units, end=end,
                stray=len(data) - i - 2, maxd=maxd, unknown=unknown, blocks=blocks, loose=loose)


def bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def check(path, names, max_w, max_h, fw, fh, border):
    P = []
    r = parse(path)
    if r["off"] != 0x74 + 8 * r["ncol"]: P.append("bad header offset")
    if r["ncol"] != 2: P.append(f"{r['ncol']} colors (expected 2)")
    if r["palette"] != [1, 22]: P.append(f"thread palette {r['palette']} (expected Black 002 = 1, Yellow Green 218 = 22)")
    if r["types"] != [0x0D] * r["ncol"]: P.append("bad thread type table")
    if r["units"] != r["npts"]: P.append(f"header point count {r['npts']} != {r['units']}")
    if not r["end"] or r["stray"]: P.append("END missing / stray bytes")
    if r["unknown"]: P.append(f"unknown commands {r['unknown']}")
    if r["maxd"] > 127: P.append("stitch longer than 12.7 mm")
    if r["loose"]: P.append(f"{r['loose']} loose jumps (no trim)")
    if len(r["blocks"]) != 2: P.append(f"{len(r['blocks'])} color blocks"); return P, r
    text, frames = r["blocks"]
    n = len(names)
    # frames: n pieces, each a full rectangle of the right size, top to bottom, same column
    if len(frames) != n: P.append(f"{len(frames)} frame pieces, expected {n}")
    fb = [bbox(p) for p in frames]
    for k, (x0, y0, x1, y1) in enumerate(fb):
        if abs((x1 - x0) - fw) > 0.8 or abs((y1 - y0) - fh) > 0.8:
            P.append(f"frame {k+1} is {x1-x0:.1f} x {y1-y0:.1f} mm")
    if [b[1] for b in fb] != sorted(b[1] for b in fb): P.append("frames not sewn top to bottom")
    if fb and max(b[0] for b in fb) - min(b[0] for b in fb) > 0.3: P.append("frames not aligned")
    for a, c in zip(fb, fb[1:]):
        if c[1] - a[3] < 2.5: P.append("frames too close / overlapping")
    # text pieces: each inside exactly one frame's inner area (clear of the border)
    inner = [(x0 + border, y0 + border, x1 - border, y1 - border) for x0, y0, x1, y1 in fb]
    per = [[] for _ in fb]; order = []
    for piece in text:
        bx0, by0, bx1, by1 = bbox(piece)
        hits = [k for k, (ix0, iy0, ix1, iy1) in enumerate(inner)
                if bx0 >= ix0 + 0.8 and bx1 <= ix1 - 0.8 and by0 >= iy0 + 0.8 and by1 <= iy1 - 0.8]
        if len(hits) != 1: P.append(f"text piece at ({bx0:.1f},{by0:.1f}) not inside one frame"); continue
        per[hits[0]].append((bx0, bx1)); order.append(hits[0])
    if order != sorted(order): P.append("names not sewn top to bottom")
    for k, (name, pcs) in enumerate(zip(names, per)):
        letters = len(name.replace(" ", ""))
        if len(pcs) < letters: P.append(f"frame {k+1} '{name}': {len(pcs)} pieces < {letters} letters")
        rights = [p[1] for p in pcs]
        if rights != sorted(rights, reverse=True): P.append(f"frame {k+1}: not sewn right-to-left")
        if pcs:
            cx_text = (min(p[0] for p in pcs) + max(p[1] for p in pcs)) / 2
            cx_frame = (fb[k][0] + fb[k][2]) / 2
            if abs(cx_text - cx_frame) > 0.5: P.append(f"frame {k+1}: text off-center by {cx_text - cx_frame:.1f} mm")
    # pyembroidery (independent reader)
    p = pe.read(path)
    x0, y0, x1, y1 = p.bounds()
    w, h = (x1 - x0) / 10, (y1 - y0) / 10
    if w > max_w or h > max_h: P.append(f"size {w:.1f} x {h:.1f} exceeds {max_w} x {max_h}")
    if abs(x0 + x1) > 4 or abs(y0 + y1) > 4: P.append("not centered")
    cols = [t.hex_color() for t in p.threadlist]
    if cols != ["#000000", "#7fc21c"]: P.append(f"colors {cols}")
    r["size"] = (w, h); r["per"] = [len(x) for x in per]
    return P, r


def main():
    sheets, folder = sys.argv[1], sys.argv[2]
    max_w, max_h = float(sys.argv[3]), float(sys.argv[4])
    fw, fh, border = (float(v) for v in (sys.argv[5:8] if len(sys.argv) > 7 else (100.4, 25.4, 4.0)))
    bad = 0
    for line in open(sheets, encoding="utf-8"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [x.strip() for x in line.split("|")]
        f, names = parts[0], [" ".join(x.split()) for x in parts[1:] if x]
        P, r = check(os.path.join(folder, f), names, max_w, max_h, fw, fh, border)
        size = r.get("size", (0, 0))
        print(f"{'PASS' if not P else 'FAIL'} {f:12s} {size[0]:5.1f} x {size[1]:5.1f} mm  "
              f"text pieces per frame {r.get('per')}  {'; '.join(P)}")
        bad += bool(P)
    print("ALL PASS" if not bad else f"{bad} FILE(S) FAILED")
    sys.exit(1 if bad else 0)


main()
