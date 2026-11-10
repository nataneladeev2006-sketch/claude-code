#!/usr/bin/env python3
"""
special.py - one "special" framed name patch (same 100 x 25 mm frame as the sheets, one thread color):
  stars        : name between two filled 5-point stars + double frame (satin + thin inner line)
  david        : name between two Magen David outlines (triple stitch) + double frame
  calligraphy  : name in the calligraphic font (חוכמה) between two small stars + satin frame
  bird         : emblem traced from a picture (--emblem-image) on the left, name on the right
  angry        : angry face (> < eyes and frown left open in a filled circle) with an anger mark and a cherry
                 blossom on the left, the name, and another cherry blossom at the right end
Sewing order: name, ornaments, inner line, satin frame (last, so it covers the edges);
for bird / angry: ornament, name, satin frame.
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


def angry_geometry(R, gap_w=1.0):
    """Angry face centered at (0, 0), radius R mm: (filled face with the eyes and mouth cut out, anger-mark arcs).
    Eyes '>' '<' and a frown as gap_w-wide openings; the anger mark (four arcs bulging toward its middle)
    sits up and to the left of the face."""
    import numpy as np
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
    face = Point(0, 0).buffer(R, quad_segs=24)
    eye_l = [(-0.58 * R, -0.37 * R), (-0.22 * R, -0.155 * R), (-0.58 * R, 0.06 * R)]
    eye_r = [(0.58 * R, -0.37 * R), (0.22 * R, -0.155 * R), (0.58 * R, 0.06 * R)]
    t = np.radians(np.linspace(-78, 78, 27))
    mouth = [(0.355 * R * math.sin(a), 0.555 * R - 0.355 * R * math.cos(a)) for a in t]
    cut = unary_union([LineString(q).buffer(gap_w / 2, cap_style="round", join_style="round", quad_segs=8)
                       for q in (eye_l, eye_r, mouth)])
    shape = face.difference(cut)
    mcx, mcy, h = -1.225 * R, -0.918 * R, 0.39 * R
    arcs = []
    for ang in (-90, 0, 90, 180):                      # top, right, bottom, left (y points down)
        ccx, ccy = mcx + 1.03 * h * math.cos(math.radians(ang)), mcy + 1.03 * h * math.sin(math.radians(ang))
        rho, base = 0.52 * h, ang + 180                # the part of the circle that faces the mark's middle
        arcs.append([(ccx + rho * math.cos(math.radians(base + d)), ccy + rho * math.sin(math.radians(base + d)))
                     for d in np.linspace(-75, 75, 11)])
    return shape, arcs


def flower_points(cx, cy, Rf, rot=-90.0, n=5, notch=0.16, nw=0.11, dot=0.42):
    """Cherry blossom as ONE continuous line (mm): a small center dot, a short step out to the cusp between two petals,
    then the 5-petal outline (each petal with a little notch at its tip) all the way round."""
    import numpy as np
    rr = math.radians(rot)
    cusp = rr + math.pi / n
    pts = [(cx + dot * math.cos(cusp + t), cy + dot * math.sin(cusp + t)) for t in np.linspace(0, 2 * math.pi, 13)]
    N = 180
    for i in range(N + 1):
        a = cusp + 2 * math.pi * i / N
        local = a - rr
        r = Rf * (0.38 + 0.62 * abs(math.cos(n * local / 2)))
        phi = ((local + math.pi / n) % (2 * math.pi / n)) - math.pi / n
        r -= Rf * notch * math.exp(-(phi / nw) ** 2)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


_EMBLEMS = {}


def emblem_geo(image, crosshair):
    import emblem as em
    key = (os.path.abspath(image), crosshair or "")
    if key not in _EMBLEMS:
        mask, box = em.load_mask(image)
        thick, thin = em.split(mask, 4.0)
        polys = em.fill_polygons(thick)
        M = em.centerlines(thin)
        if crosshair:
            v = [float(t) for t in crosshair.split(",")]
            em.replace_crosshair(M, v[0], v[1], v[2], v[3], v[4] if len(v) > 4 and v[4] > 0 else None)
        _EMBLEMS[key] = (polys, em.route(M), tuple(v / em.UP for v in box))
    return _EMBLEMS[key]


def build_side_special(layer, svg, text, style, cx, cy, args, ppm, tmpdir, idx, trims):
    """Ornament on the left (bird emblem 13 mm high, or angry face R 5.5 mm), name centered in the space on the right."""
    if not trims:
        sys.exit(f"STOP: style {style} is made with cut codes only")
    from types import SimpleNamespace
    import emblem_patch as ep
    color, clear, gap = args.color, 1.6, 2.5
    left = cx / ppm - args.frame_w / 2 + args.border + clear
    inner_w = args.frame_w - 2 * args.border - 2 * clear
    if style == "bird":
        if not getattr(args, "emblem_image", None):
            sys.exit("STOP: style bird needs --emblem-image")
        geo = emblem_geo(args.emblem_image, getattr(args, "emblem_crosshair", ""))
        b = geo[2]
        eh = 13.0; ew = eh / ((b[3] - b[1]) / (b[2] - b[0]))
        ns = SimpleNamespace(fill_spacing="0.25", line_len="1.0", bean="1", outline_len="1.0",
                             fill_inset="0.3", fill_outline="1")
        ep.add_emblem(layer, geo, left, cy / ppm - eh / 2, ew, ppm, ns, color, prefix=f"bird{idx}")
        orn_w, right_w = ew, 0.0
    else:
        R, Rf, sw = 5.5, 2.2, 0.25                      # face radius, flower radius, half a triple-stitch line
        shape, arcs = angry_geometry(R)
        fl1 = flower_points(-8.1, 3.0, Rf)              # flower below the anger mark, clear of the face
        ax = [x for arc in arcs for x, _ in arc] + [x for x, _ in fl1]
        ay = [y for arc in arcs for _, y in arc] + [y for _, y in fl1]
        ox0, oy0 = min(shape.bounds[0], min(ax) - sw), min(shape.bounds[1], min(ay) - sw)
        ox1, oy1 = max(shape.bounds[2], max(ax) + sw), max(shape.bounds[3], max(ay) + sw)
        fx, fy = left - ox0, cy / ppm - (oy0 + oy1) / 2
        T = lambda x, y: ((fx + x) * ppm, (fy + y) * ppm)
        ring = lambda coords: "M " + " L ".join(f"{T(x, y)[0]:.4f},{T(x, y)[1]:.4f}" for x, y in coords) + " Z"
        line = lambda coords: "M " + " L ".join(f"{T(x, y)[0]:.4f},{T(x, y)[1]:.4f}" for x, y in coords)
        d = " ".join([ring(shape.exterior.coords)] + [ring(hh.coords) for hh in shape.interiors])
        path(layer, d, f"fill:{color};fill-rule:evenodd;stroke:none",
             {"angle": "90", "row_spacing_mm": "0.25", "max_stitch_length_mm": "3", "running_stitch_length_mm": "1.2",
              "fill_underlay": "True", "fill_underlay_inset_mm": "0.3", "trim_after": "False"}, f"angry_{idx}_face")
        path(layer, ring(shape.exterior.coords), f"fill:none;stroke:{color};stroke-width:0.3",
             {"running_stitch_length_mm": "0.8", "bean_stitch_repeats": "0", "trim_after": "True"}, f"angry_{idx}_edge")
        for k, arc in enumerate(arcs):
            path(layer, line(arc), f"fill:none;stroke:{color};stroke-width:0.5",
                 {"running_stitch_length_mm": "0.7", "bean_stitch_repeats": "1", "trim_after": "True"}, f"angry_{idx}_mark{k}")
        flower = {"running_stitch_length_mm": "0.5", "running_stitch_tolerance_mm": "0.1", "bean_stitch_repeats": "1",
                  "trim_after": "True"}
        path(layer, line(fl1), f"fill:none;stroke:{color};stroke-width:0.5", flower, f"angry_{idx}_flower1")
        orn_w = ox1 - ox0
        # second flower at the right end of the patch (sewn before the name, so the name stays the last thing)
        right_edge = cx / ppm + args.frame_w / 2 - args.border - clear
        probe = flower_points(0.0, 0.0, Rf, rot=-75.0)          # place it by its real outline (petal notches included)
        rfx = right_edge - sw - max(x for x, _ in probe)
        rfy = cy / ppm - (min(y for _, y in probe) + max(y for _, y in probe)) / 2
        fl2 = flower_points(rfx, rfy, Rf, rot=-75.0)
        path(layer, "M " + " L ".join(f"{x * ppm:.4f},{y * ppm:.4f}" for x, y in fl2), f"fill:none;stroke:{color};stroke-width:0.5",
             flower, f"angry_{idx}_flower2")
        right_w = right_edge - (min(x for x, _ in fl2) - sw) + gap
    class F: font = "פשוט מעוגל Small"; font_path = None
    font = mn.load_font(F, set(text) | {"ש"}, tempfile.mkdtemp(dir=tmpdir))
    _, ref, _, _ = mn.build("ש", font, 1.0, "off", None, "r.svg")
    scale = max(font.min_scale, min(font.max_scale, args.letter_height / mn.plan_size_mm(ref)[1]))
    nw, nh = mn.plan_size_mm(mn.build(text, font, scale, "off", None, "w.svg")[1])
    room_w, room_h = inner_w - orn_w - gap - right_w, args.frame_h - 2 * args.border - 2 * clear
    if nw > room_w or nh > room_h:
        scale *= min(room_w / nw, room_h / nh) * 0.995
    if scale < font.min_scale - 1e-9 or scale < 0.19:
        sys.exit(f"STOP: '{text}' does not fit next to the {style} ornament ({scale*100:.1f}%)")
    g = mn.add_lettering(layer, text, font, scale, "glyph", color, args.satin_spacing)
    plan, _ = mn.plan_from_nodes(svg, root=g)
    x0, y0, x1, y1 = plan.bounding_box
    ncx = (left + orn_w + gap + room_w / 2) * ppm
    g.set("transform", f"translate({ncx - (x0 + x1) / 2:.4f},{cy - (y0 + y1) / 2:.4f}) {g.get('transform') or ''}".strip())
    return dict(font=font.name.strip(), letters=mn.plan_size_mm(ref)[1] * scale, name_w=(x1 - x0) / ppm, group=g,
                ornament_w=orn_w)


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
    if style in ("bird", "angry"):
        return build_side_special(layer, svg, text, style, cx, cy, args, ppm, tmpdir, idx, trims)
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
    ap.add_argument("--style", choices=("stars", "david", "calligraphy", "bird", "angry"), required=True)
    ap.add_argument("--emblem-image", help="bird style: black-and-white emblem picture")
    ap.add_argument("--emblem-crosshair", default="", help="bird style: cx,cy,r_cut,r_inner[,r_mid] (source px)")
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
