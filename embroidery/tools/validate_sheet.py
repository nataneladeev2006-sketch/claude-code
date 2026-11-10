"""Independent checks of framed multi-name .jef sheets (raw bytes + pyembroidery).
usage: validate_sheet.py sheets.txt folder max_w_mm max_h_mm [--cut-codes N] [--colors 1|2]
  --cut-codes N : each cut is a run of exactly N zero-length jumps (default 3); 0 = file has no cut codes
  --colors 1|2  : 2 = names Black 002 then frames Yellow Green 218 (default); 1 = everything Black 002
Frames may be horizontal or turned sideways (rotate -90: text reads top to bottom)."""
import os
import struct
import sys

import pyembroidery as pe

FW, FH, BORDER = 100.4, 25.4, 4.0            # stitched frame size (with pull compensation), satin width


def parse(path, cut_codes):
    """Raw JEF walk -> header facts + pieces (stitch lists) in sewing order, split at cuts
    (or at every jump when the file has no cut codes) and at color changes."""
    b = open(path, "rb").read()
    off = struct.unpack_from("<i", b, 0)[0]
    ncol, npts, hoop = struct.unpack_from("<iii", b, 24)
    palette = list(struct.unpack_from("<%di" % ncol, b, 0x74))
    types = list(struct.unpack_from("<%di" % ncol, b, 0x74 + 4 * ncol))
    data = b[off:]
    i = units = x = y = zero = maxd = 0
    end = False; unknown = []; zero_runs = []; colorchanges = 0; loose = 0
    pieces = [[]]; piece_color = [0]; color = 0; after_cut = True
    def new_piece():
        if pieces[-1]:
            pieces.append([]); piece_color.append(color)
        else:
            piece_color[-1] = color
    while i + 1 < len(data):
        if data[i] == 0x80:
            op = data[i + 1]
            if op == 0x10:
                units += 1; end = True; break
            dx, dy = struct.unpack("bb", data[i+2:i+4]); dy = -dy
            maxd = max(maxd, abs(dx), abs(dy)); i += 4; units += 2
            if op == 0x01:
                if zero: zero_runs.append(zero); zero = 0
                colorchanges += 1; color += 1; new_piece(); after_cut = True
                x += dx; y += dy; continue
            if op != 0x02:
                unknown.append(op); continue
            if dx == 0 and dy == 0:
                zero += 1; continue
            if zero:
                zero_runs.append(zero)
                if cut_codes and zero == cut_codes:
                    new_piece(); after_cut = True
                zero = 0
            if cut_codes == 0:
                new_piece(); after_cut = True             # no cut codes: every jump starts a piece
            elif pieces[-1] and not after_cut:
                loose += 1                                # jump inside a piece without a cut
            x += dx; y += dy
        else:
            if zero:
                zero_runs.append(zero)
                if cut_codes and zero == cut_codes:
                    new_piece(); after_cut = True
                zero = 0
            dx, dy = struct.unpack("bb", data[i:i+2]); dy = -dy
            maxd = max(maxd, abs(dx), abs(dy)); i += 2; units += 1
            x += dx; y += dy
            pieces[-1].append((x / 10, y / 10)); after_cut = False
    keep = [k for k, p in enumerate(pieces) if p]
    return dict(off=off, ncol=ncol, npts=npts, hoop=hoop, palette=palette, types=types, units=units, end=end,
                stray=len(data) - i - 2, maxd=maxd, unknown=unknown, zero_runs=zero_runs,
                colorchanges=colorchanges, loose=loose,
                pieces=[pieces[k] for k in keep], colors=[piece_color[k] for k in keep])


def bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def frame_kind(bb):
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    if abs(w - FW) <= 0.8 and abs(h - FH) <= 0.8: return "h"
    if abs(w - FH) <= 0.8 and abs(h - FW) <= 0.8: return "v"
    return None


def check(path, names, max_w, max_h, cut_codes, ncolors, specials=()):
    P = []
    special_report = []
    r = parse(path, cut_codes)
    if r["off"] != 0x74 + 8 * r["ncol"]: P.append("bad header offset")
    if r["ncol"] != ncolors: P.append(f"{r['ncol']} colors (expected {ncolors})")
    if r["palette"] != ([1, 22] if ncolors == 2 else [1]): P.append(f"thread palette {r['palette']}")
    if r["types"] != [0x0D] * r["ncol"]: P.append("bad thread type table")
    if r["units"] != r["npts"]: P.append(f"header point count {r['npts']} != {r['units']}")
    if not r["end"] or r["stray"]: P.append("END missing / stray bytes")
    if r["unknown"]: P.append(f"unknown commands {r['unknown']}")
    if r["maxd"] > 127: P.append("stitch longer than 12.7 mm")
    if r["colorchanges"] != ncolors - 1: P.append(f"{r['colorchanges']} color changes (expected {ncolors - 1})")
    if cut_codes and set(r["zero_runs"]) - {cut_codes}: P.append(f"cut code runs {sorted(set(r['zero_runs']))} (expected {cut_codes})")
    if not cut_codes and r["zero_runs"]: P.append("file has cut codes but should have none")
    if r["loose"]: P.append(f"{r['loose']} loose jumps (no cut)")
    pieces = r["pieces"]
    kinds = [frame_kind(bbox(p)) for p in pieces]
    frame_idx = [k for k, kd in enumerate(kinds) if kd]
    text_idx = [k for k, kd in enumerate(kinds) if not kd]
    n = len(names)
    if len(frame_idx) != n: P.append(f"{len(frame_idx)} frames, expected {n}")
    if text_idx and frame_idx and max(text_idx) > min(frame_idx): P.append("a frame is sewn before some names")
    if ncolors == 2 and any(r["colors"][k] != 1 for k in frame_idx): P.append("frames not in color 2")
    frames = [(bbox(pieces[k]), kinds[k]) for k in frame_idx]
    for a in range(len(frames)):
        for c in range(a + 1, len(frames)):
            A, C = frames[a][0], frames[c][0]
            if not (A[2] + 2.5 <= C[0] or C[2] + 2.5 <= A[0] or A[3] + 2.5 <= C[1] or C[3] + 2.5 <= A[1]):
                P.append(f"frames {a+1} and {c+1} overlap or are too close")
    inner = [(b[0] + BORDER, b[1] + BORDER, b[2] - BORDER, b[3] - BORDER) for b, _ in frames]
    per = [[] for _ in frames]; order = []
    for k in text_idx:
        bx0, by0, bx1, by1 = bbox(pieces[k])
        hits = [f for f, (ix0, iy0, ix1, iy1) in enumerate(inner)
                if bx0 >= ix0 + 0.8 and bx1 <= ix1 - 0.8 and by0 >= iy0 + 0.8 and by1 <= iy1 - 0.8]
        if len(hits) != 1:
            P.append(f"text piece at ({bx0:.1f},{by0:.1f}) not inside one frame"); continue
        per[hits[0]].append((bx0, by0, bx1, by1)); order.append(hits[0])
    # names are sewn one after the other, each finished before the next, in the same order as their frames
    seen = []
    for f in order:
        if not seen or seen[-1] != f: seen.append(f)
    if seen != sorted(set(seen), key=seen.index) or len(seen) != len(set(seen)): P.append("names not sewn one at a time")
    if seen != list(range(len(frames)))[:len(seen)]: P.append("names not sewn in the same order as their frames")
    for f, pcs in enumerate(per):
        name = names[seen.index(f)] if f in seen else "?"
        side_style = specials.get(name) in ("bird", "angry") if isinstance(specials, dict) else False
        if side_style and pcs:
            # ornament on the left, name on the right: the first cluster of pieces from the left (gaps < 1.8 mm) is
            # the ornament; it must end >= 1.8 mm before the name, and the name sits centered in the rest of the frame
            fb = frames[f][0]; fcy = (fb[1] + fb[3]) / 2
            srt = sorted(pcs, key=lambda q: q[0]); reach = srt[0][2]; orn = [srt[0]]
            for q in srt[1:]:
                if q[0] < reach + 1.8: orn.append(q); reach = max(reach, q[2])
                else: break
            pcs = [q for q in pcs if q not in orn]
            rorn = []
            if specials[name] == "angry" and pcs:             # flower at the right end
                srt = sorted(pcs, key=lambda q: -q[2]); reach = srt[0][0]; rorn = [srt[0]]
                for q in srt[1:]:
                    if q[2] > reach - 1.8: rorn.append(q); reach = min(reach, q[0])
                    else: break
                pcs = [q for q in pcs if q not in rorn]
            ox0, oy0 = min(q[0] for q in orn), min(q[1] for q in orn)
            ox1, oy1 = max(q[2] for q in orn), max(q[3] for q in orn)
            if not pcs: P.append(f"frame {f+1} '{name}': no name next to the ornament")
            else:
                nx0, nx1 = min(q[0] for q in pcs), max(q[2] for q in pcs)
                ny0, ny1 = min(q[1] for q in pcs), max(q[3] for q in pcs)
                rlim = (min(q[0] for q in rorn) - 2.5) if rorn else (fb[2] - BORDER - 1.6)
                area = (ox1 + 2.5 + rlim) / 2
                if rorn:
                    rx0, ry0, rx1, ry1 = min(q[0] for q in rorn), min(q[1] for q in rorn), max(q[2] for q in rorn), max(q[3] for q in rorn)
                    if abs(rx1 - (fb[2] - BORDER - 1.6)) > 0.6: P.append(f"frame {f+1} '{name}': right ornament not at the right end")
                    if abs((ry0 + ry1) / 2 - fcy) > 0.6: P.append(f"frame {f+1} '{name}': right ornament not centered vertically")
                    if nx1 > rx0 - 1.8: P.append(f"frame {f+1} '{name}': name too close to the right ornament")
                if abs((nx0 + nx1) / 2 - area) > 0.8: P.append(f"frame {f+1} '{name}': name not centered next to the ornament")
                if abs((ny0 + ny1) / 2 - fcy) > 0.6: P.append(f"frame {f+1} '{name}': name not centered vertically")
            if abs(ox0 - (fb[0] + BORDER + 1.6)) > 0.6: P.append(f"frame {f+1} '{name}': ornament not at the left")
            if abs((oy0 + oy1) / 2 - fcy) > 0.6: P.append(f"frame {f+1} '{name}': ornament not centered vertically")
            special_report.append(f"frame {f+1}: {specials[name]} ornament {ox1-ox0:.1f} x {oy1-oy0:.1f} mm in {len(orn)} pieces"
                                  + (f", right ornament {len(rorn)} piece(s)" if rorn else "") + f", letters {len(pcs)} pieces")
        elif name in specials and pcs:
            # special patch: inner frame line (long), two ornaments (outside the name), then the letters
            fb = frames[f][0]; fcx = (fb[0] + fb[2]) / 2; fcy = (fb[1] + fb[3]) / 2
            line = [q for q in pcs if q[2] - q[0] > 80]
            orn = [q for q in pcs if q not in line and abs((q[0] + q[2]) / 2 - fcx) > 37.5]
            pcs = [q for q in pcs if q not in line and q not in orn]
            if len(line) != 1 or abs((line[0][0] + line[0][2]) / 2 - fcx) > 0.3 or abs((line[0][1] + line[0][3]) / 2 - fcy) > 0.3:
                P.append(f"frame {f+1} '{name}': inner frame line missing or off-center")
            right = [q for q in orn if (q[0] + q[2]) / 2 > fcx]; left = [q for q in orn if (q[0] + q[2]) / 2 < fcx]
            if not right or not left:
                P.append(f"frame {f+1} '{name}': ornament missing on one side")
            else:
                rx = (min(q[0] for q in right) + max(q[2] for q in right)) / 2
                lx = (min(q[0] for q in left) + max(q[2] for q in left)) / 2
                if abs((rx - fcx) - (fcx - lx)) > 0.6: P.append(f"frame {f+1} '{name}': ornaments not symmetric")
            special_report.append(f"frame {f+1}: line ok, ornaments {len(left)}+{len(right)} pieces, letters {len(pcs)} pieces")
        letters = len(name.replace(" ", ""))
        if len(pcs) < letters: P.append(f"frame {f+1} '{name}': {len(pcs)} pieces < {letters} letters")
        if not pcs: continue
        horizontal = frames[f][1] == "h"
        mids = [((p[0] + p[2]) / 2) if horizontal else ((p[1] + p[3]) / 2) for p in pcs]
        if not horizontal: mids = [-m for m in mids]          # sideways: right-to-left = top-to-bottom
        if any(b > a + 2.0 for a, b in zip(mids, mids[1:])) or mids[0] < max(mids) - 2.0 or mids[-1] > min(mids) + 2.0:
            P.append(f"frame {f+1} '{name}': not sewn right-to-left")
        fb = frames[f][0]
        tx = (min(p[0] for p in pcs) + max(p[2] for p in pcs)) / 2
        ty = (min(p[1] for p in pcs) + max(p[3] for p in pcs)) / 2
        if horizontal and not side_style and abs(tx - (fb[0] + fb[2]) / 2) > 0.5: P.append(f"frame {f+1}: text off-center")
        if not horizontal and abs(ty - (fb[1] + fb[3]) / 2) > 0.5: P.append(f"frame {f+1}: text off-center")
    p = pe.read(path)
    x0, y0, x1, y1 = p.bounds()
    w, h = (x1 - x0) / 10, (y1 - y0) / 10
    if w > max_w or h > max_h: P.append(f"size {w:.1f} x {h:.1f} exceeds {max_w} x {max_h}")
    if abs(x0 + x1) > 4 or abs(y0 + y1) > 4: P.append("not centered")
    r.update(size=(w, h), per=[len(x) for x in per], sideways=sum(1 for _, kd in frames if kd == "v"),
             special_report=special_report)
    return P, r


def main():
    args = sys.argv[1:]
    cut_codes, ncolors = 3, 2
    if "--cut-codes" in args:
        i = args.index("--cut-codes"); cut_codes = int(args[i + 1]); del args[i:i + 2]
    if "--colors" in args:
        i = args.index("--colors"); ncolors = int(args[i + 1]); del args[i:i + 2]
    sheets, folder, max_w, max_h = args[0], args[1], float(args[2]), float(args[3])
    bad = 0
    for line in open(sheets, encoding="utf-8"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [x.strip() for x in line.split("|")]
        f = parts[0]
        names, specials = [], {}
        for x in parts[1:]:
            if not x: continue
            nm = " ".join(x.split("@")[0].split())
            names.append(nm)
            if "@" in x: specials[nm] = x.split("@", 1)[1].strip()
        P, r = check(os.path.join(folder, f), names, max_w, max_h, cut_codes, ncolors, specials)
        size = r.get("size", (0, 0))
        print(f"{'PASS' if not P else 'FAIL'} {f:12s} {size[0]:5.1f} x {size[1]:5.1f} mm  frames {len(r.get('per', []))} "
              f"({r.get('sideways', 0)} sideways)  text pieces per frame {r.get('per')}  {'; '.join(P)}")
        for line_ in r.get("special_report", []):
            print(f"     special {line_}")
        bad += bool(P)
    print("ALL PASS" if not bad else f"{bad} FILE(S) FAILED")
    sys.exit(1 if bad else 0)


main()
