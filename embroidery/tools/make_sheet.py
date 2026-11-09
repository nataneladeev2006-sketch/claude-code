#!/usr/bin/env python3
"""
make_sheet.py - several framed name patches in one embroidery file (like a
"3 names in frames" design): all names first (color 1), then a satin frame
around each name (color 2). Text uses Ink/Stitch's Lettering engine via
make_name.py (same font, ״ and "." support, trims, checks).

Sheets file, one line per output file, names from top to bottom:
    NAMES_1.JEF | עמית ממן | עידן רוזנבלום | רועי

Example:
  make_sheet.py --inkstitch ~/inkstitch --font "פשוט מעוגל Small" --sheets sheets.txt --outdir usb
"""
import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_name as mn  # noqa: E402


def frame_d(cx, cy, w, h, b, ext, d):
    """Satin column for a rectangular frame: two rails + rungs.
    The rails run from the middle of the bottom edge all the way round and back
    to it (open paths without 'Z', which Ink/Stitch asks for). Each corner has a
    mitre rung plus a square-on rung `d` past the inner corner on both edges, so
    stitches stay square along the straight sides and only turn in the corner."""
    xl, xr, yt, yb = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    xli, xri, yti, ybi = xl + b, xr - b, yt + b, yb - b
    outer = [(cx, yb), (xl, yb), (xl, yt), (xr, yt), (xr, yb), (cx, yb)]
    inner = [(cx, ybi), (xli, ybi), (xli, yti), (xri, yti), (xri, ybi), (cx, ybi)]
    rungs = []
    for o, i in zip(outer[1:5], inner[1:5]):
        dx, dy = i[0] - o[0], i[1] - o[1]
        n = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / n, dy / n
        rungs.append([(o[0] - ux * ext, o[1] - uy * ext), (i[0] + ux * ext, i[1] + uy * ext)])
        # square-on rungs on the horizontal and the vertical edge next to this corner
        sx = 1 if i[0] > o[0] else -1      # direction from the corner into the frame, x
        sy = 1 if i[1] > o[1] else -1      # ... and y
        x = i[0] + sx * d                  # on the horizontal edge, just past the inner corner
        rungs.append([(x, o[1] - sy * ext), (x, i[1] + sy * ext)])
        y = i[1] + sy * d                  # on the vertical edge, just past the inner corner
        rungs.append([(o[0] - sx * ext, y), (i[0] + sx * ext, y)])
    sub = lambda pts: "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in pts)
    return " ".join([sub(outer), sub(inner)] + [sub(r) for r in rungs])


def add_frame(layer, cx, cy, args, ppm, index):
    import inkex
    el = inkex.PathElement()
    el.set("d", frame_d(cx, cy, args.frame_w * ppm, args.frame_h * ppm, args.border * ppm, 0.5 * ppm, 1.0 * ppm))
    el.set("style", f"fill:none;stroke:{args.frame_color};stroke-width:1")
    el.set("id", f"frame_{index}")
    el.label = f"frame {index + 1}"
    params = {
        "satin_column": "True",
        "zigzag_spacing_mm": str(args.frame_spacing),
        "pull_compensation_mm": "0.2",
        "contour_underlay": "True",
        "zigzag_underlay": "True",
        "center_walk_underlay": "False",
        "trim_after": "True",
    }
    for k, v in params.items():
        el.set(mn.INKSTITCH_NS + k, v)
    layer.append(el)
    return el


def glyph_text(lettering_group):
    """Read back the letters Ink/Stitch actually placed (sewing order), for checking."""
    out = []
    for node in lettering_group.iter():
        if node.get(mn.INKSTITCH_NS + "letter-group") == "glyph":
            label = (node.label or "").strip()
            out.append(label[11:] if label.startswith("GlyphLayer-") else label)
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inkstitch", required=True)
    ap.add_argument("--font", help='Ink/Stitch font name, e.g. "פשוט מעוגל Small"')
    ap.add_argument("--font-path")
    ap.add_argument("--sheets", required=True, help="file: FILE.JEF | name | name | ...")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--frame-w", type=float, default=100.0, help="frame outside width, mm")
    ap.add_argument("--frame-h", type=float, default=25.0, help="frame outside height, mm")
    ap.add_argument("--border", type=float, default=4.0, help="satin frame width, mm")
    ap.add_argument("--gap", type=float, default=20.0, help="space between frames, mm (reduced to fit --max-height)")
    ap.add_argument("--max-height", type=float, help="whole design height limit, mm (e.g. 190 for a 140x200 hoop)")
    ap.add_argument("--letter-height", type=float, default=9.0, help="target height of a normal letter (ש), mm")
    ap.add_argument("--side-margin", type=float, default=3.0, help="min space between text and frame inside, mm")
    ap.add_argument("--satin-spacing", type=float, default=0.4, help="text satin density, mm")
    ap.add_argument("--frame-spacing", type=float, default=0.4, help="frame satin density, mm")
    ap.add_argument("--text-color", default="#000000", help="JEF: #000000 = Black 002")
    ap.add_argument("--frame-color", default="#7fc21c", help="JEF: #7fc21c = Yellow Green 218")
    ap.add_argument("--trim", choices=mn.TRIM_OPTIONS, default="glyph")
    ap.add_argument("--fit", choices=("all", "each"), default="all",
                    help="all: one letter size for every name (fits the widest); each: every name gets the target "
                         "size unless too long, then narrower word gaps, then smaller letters for that name only")
    ap.add_argument("--min-word-gap", type=float, default=0.35,
                    help="smallest word gap for --fit each, as a fraction of the letter height (kept when letters shrink)")
    args = ap.parse_args()

    sys.path.insert(0, os.path.abspath(args.inkstitch))
    mn.install_wx_placeholder()
    from lib.output import write_embroidery_file
    from lib.svg import PIXELS_PER_MM as ppm

    sheets = []
    with open(args.sheets, encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.lstrip().startswith("#"):
                parts = [p.strip() for p in line.split("|")]
                sheets.append((os.path.join(args.outdir, parts[0]), [mn.normalize_text(p) for p in parts[1:] if p]))
    os.makedirs(args.outdir, exist_ok=True)

    tmpdir = tempfile.mkdtemp(prefix="make_sheet_")
    try:
        needed = set("".join(n for _, names in sheets for n in names)) | {"ש"}
        font = mn.load_font(args, needed, tmpdir)

        _, ref, _, _ = mn.build("ש", font, 1.0, "off", None, "ref.svg")
        ref_h = mn.plan_size_mm(ref)[1]                       # ש height at 100 %, mm
        target = args.letter_height / ref_h
        room = args.frame_w - 2 * args.border - 2 * args.side_margin
        all_names = sorted({n for _, names in sheets for n in names})
        width = lambda n, sc, ws=0: mn.plan_size_mm(mn.build(n, font, sc, "off", None, "w.svg", word_spacing=ws)[1])[0]
        widths = {n: width(n, target) for n in all_names}
        sizing = {}
        if args.fit == "all":
            # one letter size for every name: the target, or smaller if the widest name needs it
            widest = max(widths, key=widths.get)
            scale = target * min(1.0, room / widths[widest] * 0.995)
            sizing = {n: (scale, 0.0) for n in all_names}
        else:
            for n in all_names:
                scale, ws = target, 0.0
                if widths[n] > room and " " in n:
                    gap = font.word_spacing * scale / ppm               # mm, as stitched
                    cut = min((widths[n] - room + 0.3) / n.count(" "), gap - args.min_word_gap * args.letter_height)
                    if cut > 0:
                        ws = -cut / scale
                w = width(n, scale, ws)
                if w > room:
                    scale = scale * room / w * 0.995
                    w = width(n, scale, ws)
                sizing[n] = (scale, ws)
        for n in all_names:
            scale, ws = sizing[n]
            if not (font.min_scale <= scale <= font.max_scale):
                sys.exit(f"STOP: '{n}': scale {scale*100:.1f}% outside the font's range")
            if scale < 0.19:
                sys.exit(f"STOP: '{n}': below ~18.5% this font sews over the gap in ה (reads as ח)")
            gap_mm = (font.word_spacing + ws * ppm) * scale / ppm
            print(f"   size: '{n}' letters {ref_h * scale:.2f} mm (scale {scale*100:.1f}%)"
                  + (f", word gap {gap_mm:.1f} mm" if " " in n else ""))
        # where the letter body (ש) sits relative to the baseline, at each size used
        body_mids = {}
        for scale in {sc for sc, _ in sizing.values()}:
            _, refplan, _, _ = mn.build("ש", font, scale, "off", None, "ref.svg")
            body_mids[scale] = (refplan.bounding_box[1] + refplan.bounding_box[3]) / 2
        print(f"font: {font.name}")

        for out, names in sheets:
            n = len(names)
            gap = args.gap
            if args.max_height and n > 1:
                gap = min(gap, (args.max_height - n * args.frame_h) / (n - 1))
            if gap < 3:
                sys.exit(f"STOP: {out}: {n} frames don't fit in {args.max_height} mm")
            total_h = n * args.frame_h + (n - 1) * gap
            page_w, page_h = args.frame_w + 20, total_h + 20
            svg, layer = mn.new_document(os.path.basename(out) + ".svg", page_w, page_h)
            cx = page_w / 2 * ppm
            centers = [(10 + args.frame_h / 2 + i * (args.frame_h + gap)) * ppm for i in range(n)]

            groups = []
            for i, (text, cy) in enumerate(zip(names, centers)):
                scale, ws = sizing[text]
                body_mid = body_mids[scale]                    # baseline-relative middle of the letters
                g = mn.add_lettering(layer, text, font, scale, args.trim, args.text_color, args.satin_spacing, ws)
                # at these bigger sizes, trim between the two marks of ״ instead of sewing a joining stitch
                for node in g.iter():
                    if node.get("data-extra-glyph") == mn.GERSHAYIM:
                        node.set(mn.INKSTITCH_NS + "min_jump_stitch_length_mm", "1")
                placed = glyph_text(g)
                if placed != text.replace(" ", ""):
                    sys.exit(f"STOP: '{text}' was placed as '{placed}'")
                plan, _ = mn.plan_from_nodes(svg, root=g)
                x0, y0, x1, y1 = plan.bounding_box
                dx, dy = cx - (x0 + x1) / 2, cy - body_mid
                g.set("transform", f"translate({dx:.4f},{dy:.4f}) {g.get('transform') or ''}".strip())
                groups.append((text, g))
            for i, cy in enumerate(centers):
                add_frame(layer, cx, cy, args, ppm, i)

            plan, problems = mn.plan_from_nodes(svg, check=True, trim_jumps=True)
            for p in problems:
                print(f"   {p[0]}: {p[1]} on {p[2]}")
            if any(p[0] == "ERROR" for p in problems):
                sys.exit(f"STOP: Ink/Stitch reports errors in {out}")

            # every name must sit inside its frame, clear of the satin border
            for i, ((text, g), cy) in enumerate(zip(groups, centers)):
                gx0, gy0, gx1, gy1 = mn.plan_from_nodes(svg, root=g)[0].bounding_box
                ix0 = cx - (args.frame_w / 2 - args.border) * ppm
                ix1 = cx + (args.frame_w / 2 - args.border) * ppm
                iy0 = cy - (args.frame_h / 2 - args.border) * ppm
                iy1 = cy + (args.frame_h / 2 - args.border) * ppm
                clear = min(gx0 - ix0, ix1 - gx1, gy0 - iy0, iy1 - gy1) / ppm
                if clear < 1.0:
                    sys.exit(f"STOP: '{text}' is only {clear:.2f} mm from its frame")
                print(f"   frame {i+1}: '{text}' {(gx1-gx0)/ppm:.1f} x {(gy1-gy0)/ppm:.1f} mm, "
                      f"clearance to frame {clear:.1f} mm")

            write_embroidery_file(os.path.abspath(out), plan, svg)
            w, h = mn.plan_size_mm(plan)
            print(f"wrote {out}: {n} names, gap {gap:.1f} mm, size {w:.1f} x {h:.1f} mm, "
                  f"~{sum(len(b) for b in plan)} stitches, colors={len(plan)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
