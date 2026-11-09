#!/usr/bin/env python3
"""
special.py - one "special" framed name patch (same 100 x 25 mm frame as the sheets, one thread color):
  stars        : name between two filled 5-point stars + double frame (satin + thin inner line)
  david        : name between two Magen David outlines (triple stitch) + double frame
  calligraphy  : name in the calligraphic font (חוכמה) between two small stars + satin frame
Sewing order: name, ornaments, inner line, satin frame (last, so it covers the edges).
"""
import argparse
import math
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_name as mn  # noqa: E402
import make_sheet as ms  # noqa: E402

NS = mn.INKSTITCH_NS


def star_d(cx, cy, R, r, rot=-90):
    pts = []
    for k in range(10):
        a = math.radians(rot + k * 36)
        rad = R if k % 2 == 0 else r
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in pts) + " Z"


def david_d(cx, cy, R):
    tri = lambda rot: [(cx + R * math.cos(math.radians(rot + k * 120)), cy + R * math.sin(math.radians(rot + k * 120)))
                       for k in range(3)]
    sub = lambda pts: "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in pts + [pts[0]])
    return sub(tri(-90)) + " " + sub(tri(90))


def rect_d(cx, cy, w, h):
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    # start mid-bottom and go round, ending where it started (like the satin frame)
    pts = [(cx, y1), (x0, y1), (x0, y0), (x1, y0), (x1, y1), (cx, y1)]
    return "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in pts)


def path(layer, d, style, params, eid):
    import inkex
    el = inkex.PathElement()
    el.set("d", d); el.set("style", style); el.set("id", eid)
    for k, v in params.items():
        el.set(NS + k, v)
    layer.append(el)
    return el


def build_special(layer, svg, text, style, cx, cy, args, ppm, tmpdir, idx=0, trims=True):
    """Adds one special patch centered at (cx, cy) [px]; returns a short description."""
    color = args.color
    cut = "True" if trims else "False"
    nojump = {} if trims else {"min_jump_stitch_length_mm": "0.5"}
    line_inset = args.border + 1.0                      # inner line: 1 mm inside the satin
    if style == "calligraphy":
        fontname, orn, orn_w, gap = "חוכמה Medium ", "star", 3.6, 2.2
        room_h = args.frame_h - 2 * args.border - 2 * 1.0
        inner_line = False
    else:
        fontname, orn, gap = "פשוט מעוגל Small", ("star" if style == "stars" else "david"), 2.5
        orn_w = 4.8 if orn == "star" else 5.6
        room_h = args.frame_h - 2 * line_inset - 2 * 1.2
        inner_line = True
    class F: font = fontname; font_path = None
    font = mn.load_font(F, set(text) | {"ש"}, tempfile.mkdtemp(dir=tmpdir))
    edge = (line_inset + 1.2) if inner_line else (args.border + 1.5)
    room_w = args.frame_w - 2 * edge - 2 * (orn_w + gap)
    _, ref, _, _ = mn.build("ש", font, 1.0, "off", None, "r.svg")
    scale = max(font.min_scale, min(font.max_scale, args.letter_height / mn.plan_size_mm(ref)[1]))
    w, h = mn.plan_size_mm(mn.build(text, font, scale, "off", None, "w.svg")[1])
    if w > room_w or h > room_h:
        scale *= min(room_w / w, room_h / h) * 0.995
    if scale < font.min_scale - 1e-9:
        sys.exit(f"STOP: '{text}' does not fit with the {style} style (needs {scale*100:.1f}% < font minimum)")
    g = mn.add_lettering(layer, text, font, scale, "glyph" if trims else "off", color, args.satin_spacing)
    if not trims:
        for node in g.iter():
            if node.get(NS + "min_jump_stitch_length_mm") is not None:
                node.set(NS + "min_jump_stitch_length_mm", "0.5")
    plan, _ = mn.plan_from_nodes(svg, root=g)
    x0, y0, x1, y1 = plan.bounding_box
    g.set("transform", f"translate({cx - (x0 + x1) / 2:.4f},{cy - (y0 + y1) / 2:.4f}) {g.get('transform') or ''}".strip())
    name_w = (x1 - x0) / ppm
    # ornaments, one each side of the name
    for side, sx in (("r", 1), ("l", -1)):
        ox = cx + sx * (name_w / 2 + gap + orn_w / 2) * ppm
        if orn == "star":
            R = orn_w / 2 * ppm
            path(layer, star_d(ox, cy, R, R * 0.42), f"fill:{color};stroke:none",
                 {"fill_underlay": "False", "row_spacing_mm": "0.3", "angle": "90", "max_stitch_length_mm": "3",
                  "running_stitch_length_mm": "1", "trim_after": "False", **nojump}, f"orn_{idx}_{side}")
            # thin outline around the small fill: crisp star points
            path(layer, star_d(ox, cy, R, R * 0.42), f"fill:none;stroke:{color};stroke-width:0.5",
                 {"running_stitch_length_mm": "0.8", "trim_after": cut, **nojump}, f"orn_{idx}_{side}_outline")
        else:
            R = orn_w / 2 / math.cos(math.radians(30)) * ppm      # hexagram width = 2 R cos30
            path(layer, david_d(ox, cy, R), f"fill:none;stroke:{color};stroke-width:0.5",
                 {"running_stitch_length_mm": "1.2", "bean_stitch_repeats": "1", "trim_after": cut, **nojump}, f"orn_{idx}_{side}")
    if inner_line:
        lw, lh = (args.frame_w - 2 * line_inset) * ppm, (args.frame_h - 2 * line_inset) * ppm
        path(layer, rect_d(cx, cy, lw, lh), f"fill:none;stroke:{color};stroke-width:0.5",
             {"running_stitch_length_mm": "2", "bean_stitch_repeats": "1", "trim_after": cut, **nojump}, f"line_{idx}")
    return dict(font=font.name.strip(), letters=mn.plan_size_mm(ref)[1] * scale, name_w=name_w, group=g)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inkstitch", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--style", choices=("stars", "david", "calligraphy"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame-w", type=float, default=100.0)
    ap.add_argument("--frame-h", type=float, default=25.0)
    ap.add_argument("--border", type=float, default=4.0)
    ap.add_argument("--letter-height", type=float, default=9.0)
    ap.add_argument("--satin-spacing", type=float, default=0.4)
    ap.add_argument("--frame-spacing", type=float, default=0.4)
    ap.add_argument("--color", default="#000000")
    ap.add_argument("--cut-codes", type=int, default=1)
    args = ap.parse_args()
    sys.path.insert(0, os.path.abspath(args.inkstitch))
    mn.install_wx_placeholder()
    from lib.output import write_embroidery_file
    from lib.svg import PIXELS_PER_MM as ppm
    tmpdir = tempfile.mkdtemp(prefix="special_")
    try:
        text = mn.normalize_text(args.text)
        svg, layer = mn.new_document(os.path.basename(args.out) + ".svg", args.frame_w + 20, args.frame_h + 20)
        cx, cy = (args.frame_w / 2 + 10) * ppm, (args.frame_h / 2 + 10) * ppm
        info = build_special(layer, svg, text, args.style, cx, cy, args, ppm, tmpdir, trims=args.cut_codes != 0)
        args.frame_color = args.color
        ms.add_frame(layer, cx, cy, args, ppm, 0)
        plan, problems = mn.plan_from_nodes(svg, check=True, trim_jumps=args.cut_codes != 0)
        for p in problems:
            print(f"   {p[0]}: {p[1]} on {p[2]}")
        if any(p[0] == "ERROR" for p in problems):
            sys.exit("STOP: Ink/Stitch reports errors")
        write_embroidery_file(os.path.abspath(args.out), plan, svg, {"trim_at": args.cut_codes} if args.cut_codes else {})
        w, h = mn.plan_size_mm(plan)
        print(f"wrote {args.out}: '{text}' style={args.style} font={info['font']} letters {info['letters']:.2f} mm, "
              f"name {info['name_w']:.1f} mm wide, patch {w:.1f} x {h:.1f} mm, ~{sum(len(b) for b in plan)} stitches, colors={len(plan)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
