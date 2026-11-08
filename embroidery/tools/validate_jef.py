"""Independent checks of Janome .jef files (raw bytes + pyembroidery), against an expected text.
usage: validate_jef.py names.txt folder [max_w_mm max_h_mm]"""
import sys, os, struct, math
import pyembroidery as pe
sys.path.insert(0, os.path.dirname(__file__))
from segments import parse_jef

def check(path, text, max_w, max_h):
    probs = []
    b = open(path, "rb").read()
    off, flags = struct.unpack_from("<iI", b, 0)
    ncol, npts, hoop = struct.unpack_from("<iii", b, 24)
    if off != 0x74 + 8 * ncol: probs.append(f"header offset {off} != {0x74 + 8*ncol}")
    if ncol != 1: probs.append(f"{ncol} colors (expected 1)")
    if hoop != 3: probs.append(f"hoop code {hoop}")
    if not b[8:22].decode("ascii").isdigit(): probs.append("bad date field")
    # walk records: every byte pair must be a stitch or a known 0x80 command; END must close the data
    # point count is in 2-byte units: stitch = 1, 4-byte command = 2, END = 1 (same as the old file's writer)
    data = b[off:]; i = 0; recs = 0; end = False; maxd = 0
    while i + 1 < len(data):
        if data[i] == 0x80:
            op = data[i+1]
            if op == 0x10: recs += 1; end = True; break
            if op not in (0x01, 0x02): probs.append(f"unknown command 0x80 0x{op:02x}")
            dx, dy = struct.unpack("bb", data[i+2:i+4]); maxd = max(maxd, abs(dx), abs(dy)); i += 4; recs += 2
        else:
            dx, dy = struct.unpack("bb", data[i:i+2]); maxd = max(maxd, abs(dx), abs(dy)); i += 2; recs += 1
    if not end: probs.append("no END command")
    if i + 2 != len(data): probs.append(f"{len(data) - i - 2} stray bytes after END")
    if recs != npts: probs.append(f"header point count {npts} != {recs} records")
    if maxd > 127: probs.append("stitch longer than 12.7 mm")
    # pyembroidery (independent reader)
    p = pe.read(path)
    x0, y0, x1, y1 = p.bounds()
    w, h = (x1 - x0) / 10, (y1 - y0) / 10
    if w > max_w + 0.05 or h > max_h + 0.15: probs.append(f"size {w:.1f} x {h:.1f} mm exceeds {max_w} x {max_h}")
    cx, cy = (x0 + x1) / 20, (y0 + y1) / 20
    if abs(cx) > 0.2 or abs(cy) > 0.2: probs.append(f"not centered ({cx:.1f},{cy:.1f})")
    hw, hh = struct.unpack_from("<ii", b, 36)
    if abs(hw * 2 / 10 - w) > 0.2 or abs(hh * 2 / 10 - h) > 0.2: probs.append("header extents disagree with stitches")
    nst = sum(1 for s in p.stitches if (s[2] & pe.COMMAND_MASK) == pe.STITCH)
    # letters: one trim-separated piece per letter, +1 for each two-piece letter (ה, ק)
    segs, moves = parse_jef(path)
    letters = text.replace(" ", "")
    expected = len(letters) + letters.count("ה") + letters.count("ק")
    if len(segs) != expected: probs.append(f"{len(segs)} pieces, expected {expected}")
    loose = 0
    for s in segs:
        for k in range(1, len(s)):
            if s[k][0] == "move" and any(t == "st" for t, _, _ in s[:k]): loose += 1
    if loose: probs.append(f"{loose} jumps without trim (loose threads)")
    # pieces must go right -> left (Hebrew order): each piece starts left of the previous piece's right edge
    rights = [max(x for t, x, y in s if t == "st") for s in segs]
    if rights != sorted(rights, reverse=True): probs.append("pieces not sewn right-to-left")
    return w, h, nst, len(segs), probs

def main():
    names, folder = sys.argv[1], sys.argv[2]
    max_w = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
    max_h = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
    jobs = []
    for line in open(names, encoding="utf-8"):
        if "|" in line and not line.lstrip().startswith("#"):
            f, t = line.split("|"); jobs.append((f.strip(), " ".join(t.split())))
    bad = 0
    for f, t in jobs:
        path = os.path.join(folder, f)
        if not os.path.exists(path):
            print(f"FAIL {f}: missing"); bad += 1; continue
        w, h, nst, nseg, probs = check(path, t, max_w, max_h)
        print(f"{'PASS' if not probs else 'FAIL'} {f:13s} {w:5.1f} x {h:4.1f} mm {nst:5d} stitches {nseg:3d} pieces  {'; '.join(probs)}")
        bad += bool(probs)
    extra = sorted(set(os.listdir(folder)) - {f for f, _ in jobs})
    if extra: print("note: extra files in folder:", extra)
    print("ALL PASS" if not bad else f"{bad} FILE(S) FAILED")
    sys.exit(1 if bad else 0)

main()
