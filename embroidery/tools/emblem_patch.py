#!/usr/bin/env python3
"""
emblem_patch.py - a framed name patch with an embroidered emblem traced from a picture (one thread color).
  --layout top  : emblem on top, name below, taller frame (100 mm wide, height to fit)
  --layout side : standard 100 x 25 mm frame, small emblem on the left, name on the right
  --layout alone: just the emblem, --emblem-w wide (no frame, no name)
Emblem: thick black areas = fill stitch (+ crisp running outline), thin lines = running stitch
(triple stitch where --bean 1), routed into continuous runs. Sewing order: emblem fills, emblem lines, name, frame.
"""
import argparse, math, os, shutil, sys, tempfile
import numpy as np
from shapely.geometry import LineString

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_name as mn      # noqa: E402
import make_sheet as ms     # noqa: E402
import emblem as em         # noqa: E402

NS = mn.INKSTITCH_NS


def add_path(layer, d, style, params, eid):
    import inkex
    el = inkex.PathElement(); el.set("d", d); el.set("style", style); el.set("id", eid)
    for k, v in params.items(): el.set(NS + k, str(v))
    layer.append(el); return el


def poly_d(poly, T):
    def ring(coords):
        pts = [T(x, y) for x, y in coords]
        return "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in pts) + " Z"
    return " ".join([ring(poly.exterior.coords)] + [ring(h.coords) for h in poly.interiors])


def line_d(pts, T):
    q = [T(x, y) for x, y in pts]
    return "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in q)


def long_axis_angle(poly):
    r = list(poly.minimum_rotated_rectangle.exterior.coords)
    e = max(((r[i], r[i + 1]) for i in range(4)), key=lambda ab: math.dist(*ab))
    return math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))


def add_emblem(layer, geo, x0_mm, y0_mm, w_mm, ppm, a, color, prefix="emb"):
    """geo = (polys, runs, box) in source px; places the emblem with its top-left at (x0, y0) mm, width w_mm."""
    polys, runs, (bx0, by0, bx1, by1) = geo
    s = w_mm / (bx1 - bx0)
    T = lambda x, y: ((x0_mm + (x - bx0) * s) * ppm, (y0_mm + (y - by0) * s) * ppm)
    items = []
    if float(a.fill_inset) > 0:                     # small sizes: pull fills in so the white gaps survive
        out = []
        for p in polys:
            if p.area < getattr(a, "inset_min_area", 0.0):
                out.append(p); continue
            q = p.buffer(-float(a.fill_inset) / s, join_style=2)
            parts = [g for g in (q.geoms if hasattr(q, "geoms") else [q]) if not g.is_empty]
            # keep a small fill as it is when pulling it in would shrink it too much
            if not parts or sum(g.area for g in parts) < 0.5 * p.area: out.append(p)
            else: out.extend(parts)
        polys = out
    for i, p in enumerate(polys):
        small = (p.area ** 0.5) * s < 4.0
        ang = -long_axis_angle(p)
        items.append(("fill", p.centroid.x, i, dict(
            d=poly_d(p, T), style=f"fill:{color};fill-rule:evenodd;stroke:none",
            params={"angle": f"{ang:.1f}", "row_spacing_mm": a.fill_spacing, "max_stitch_length_mm": "3",
                    "running_stitch_length_mm": "1.2", "fill_underlay": "False" if small else "True",
                    "trim_after": "False"},
            outline=line_d(list(p.exterior.coords), T))))
    for i, run in enumerate(runs):
        xs = [x for pts, _, _ in run for x, _ in pts]
        items.append(("run", min(xs), i, run))
    # sew fills first (left to right), then line runs (left to right)
    fills = sorted([it for it in items if it[0] == "fill"], key=lambda it: it[1])
    lines = sorted([it for it in items if it[0] == "run"], key=lambda it: it[1])
    n = 0
    for _, _, i, f in fills:
        if a.fill_outline == "1":
            add_path(layer, f["d"], f["style"], f["params"], f"{prefix}_fill_{i}")
            add_path(layer, f["outline"], f"fill:none;stroke:{color};stroke-width:0.3",
                     {"running_stitch_length_mm": a.outline_len, "bean_stitch_repeats": "0", "trim_after": "True"}, f"{prefix}_fill_{i}_edge")
        else:
            add_path(layer, f["d"], f["style"], {**f["params"], "trim_after": "True"}, f"{prefix}_fill_{i}")
    for _, _, i, run in lines:
        # merge consecutive segments with the same pass type
        groups = []
        for pts, first, cls in run:
            heavy = first and cls != "thin"           # triple stitch only on a line's first pass
            if groups and groups[-1][1] == heavy:
                groups[-1][0].extend(list(map(tuple, pts))[1:])
            else:
                groups.append([list(map(tuple, pts)), heavy])
        for j, (pts, first) in enumerate(groups):
            if len(pts) < 2 or LineString(pts).length * s < 0.15: continue
            last = j == len(groups) - 1
            add_path(layer, line_d(pts, T), f"fill:none;stroke:{color};stroke-width:0.4",
                     {"running_stitch_length_mm": a.line_len, "bean_stitch_repeats": a.bean if first else "0",
                      "trim_after": "True" if last else "False"}, f"{prefix}_run_{i}_{j}")
            n += 1
    return s, n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inkstitch", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--layout", choices=("top", "side", "alone"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--font", default="פשוט מעוגל Small")
    ap.add_argument("--emblem-w", type=float, help="emblem width mm (top: default 78; side: from --emblem-h)")
    ap.add_argument("--emblem-h", type=float, default=13.0, help="side layout: emblem height mm")
    ap.add_argument("--letter-height", type=float, default=9.0)
    ap.add_argument("--min-fill-px", type=float, default=4.0)
    ap.add_argument("--min-fill-area", type=float, default=150.0, help="smallest solid area sewn as fill (normalized px^2)")
    ap.add_argument("--line-len", default="1.2"); ap.add_argument("--bean", default="1")
    ap.add_argument("--outline-len", default="1.0"); ap.add_argument("--fill-spacing", default="0.25")
    ap.add_argument("--fill-inset", default="0", help="mm to pull each fill in (small sizes)")
    ap.add_argument("--inset-min-area", type=float, default=0.0, help="only pull in fills at least this big (n-px^2)")
    ap.add_argument("--snap", type=float, default=0.0, help="extend line ends within this many n-px of a fill to it")
    ap.add_argument("--fill-outline", default="1", help="1 = running stitch around each fill")
    ap.add_argument("--frame-w", type=float, default=100.0); ap.add_argument("--border", type=float, default=4.0)
    ap.add_argument("--clear", type=float, default=1.6, help="space between frame and content, mm")
    ap.add_argument("--gap", type=float, default=2.5, help="space between emblem and name, mm")
    ap.add_argument("--color", default="#000000")
    ap.add_argument("--crosshair", default="", help="cx,cy,r_cut,r_inner[,r_mid] in source px: redraw a scope reticle")
    a = ap.parse_args()
    sys.path.insert(0, os.path.abspath(a.inkstitch))
    mn.install_wx_placeholder()
    from lib.output import write_embroidery_file
    from lib.svg import PIXELS_PER_MM as ppm
    tmp = tempfile.mkdtemp(prefix="emblem_")
    try:
        mask, box = em.load_mask(a.image)
        thick, thin = em.split(mask, a.min_fill_px, a.min_fill_area)
        polys = em.fill_polygons(thick)
        M = em.centerlines(thin)
        if a.snap > 0:
            print(f"   lines extended to touch a fill: {em.snap_to_fills(M, polys, a.snap)}")
        if a.crosshair:
            v = [float(t) for t in a.crosshair.split(",")]
            em.replace_crosshair(M, v[0], v[1], v[2], v[3], v[4] if len(v) > 4 and v[4] > 0 else None)
        runs = em.route(M)
        b = tuple(v / em.UP for v in box)
        aspect = (b[3] - b[1]) / (b[2] - b[0])
        if a.layout == "alone":
            ew = a.emblem_w or 100.0; eh = ew * aspect
            svg, layer = mn.new_document(os.path.basename(a.out) + ".svg", ew + 20, eh + 20)
            s, nruns = add_emblem(layer, (polys, runs, b), 10.0, 10.0, ew, ppm, a, a.color)
            plan, problems = mn.plan_from_nodes(svg, check=True, trim_jumps=True)
            for p in problems: print(f"   {p[0]}: {p[1]} on {p[2]}")
            if any(p[0] == "ERROR" for p in problems): sys.exit("STOP: Ink/Stitch reports errors")
            write_embroidery_file(os.path.abspath(a.out), plan, svg, {"trim_at": 1})
            open(os.path.abspath(a.out) + ".svg", "w", encoding="utf-8").write(svg.tostring().decode("utf-8"))
            w, h = mn.plan_size_mm(plan)
            print(f"wrote {a.out}: emblem alone {ew:.1f} x {eh:.1f} mm ({s:.4f} mm/n-px, {len(polys)} fills, {len(runs)} line runs), "
                  f"stitched {w:.1f} x {h:.1f} mm, ~{sum(len(x) for x in plan)} stitches")
            return
        text = mn.normalize_text(a.text)
        class F: font = a.font; font_path = None
        font = mn.load_font(F, set(text) | {"ש"}, tmp)
        _, ref, _, _ = mn.build("ש", font, 1.0, "off", None, "r.svg")
        scale = max(font.min_scale, min(font.max_scale, a.letter_height / mn.plan_size_mm(ref)[1]))
        nw, nh = mn.plan_size_mm(mn.build(text, font, scale, "off", None, "w.svg")[1])
        inner_w = a.frame_w - 2 * a.border - 2 * a.clear
        if a.layout == "top":
            ew = a.emblem_w or 78.0; eh = ew * aspect
            if nw > inner_w:
                scale *= inner_w / nw * 0.995; nw, nh = mn.plan_size_mm(mn.build(text, font, scale, "off", None, "w.svg")[1])
            frame_h = 2 * a.border + 2 * a.clear + eh + a.gap + nh
        else:
            frame_h = 25.0
            eh = a.emblem_h; ew = a.emblem_w or eh / aspect
            room_w, room_h = inner_w - ew - a.gap, frame_h - 2 * a.border - 2 * a.clear
            if nw > room_w or nh > room_h:
                scale *= min(room_w / nw, room_h / nh) * 0.995
                nw, nh = mn.plan_size_mm(mn.build(text, font, scale, "off", None, "w.svg")[1])
        if scale < font.min_scale - 1e-9:
            sys.exit(f"STOP: name too small ({scale*100:.1f}% < font minimum)")
        W, H = a.frame_w + 20, frame_h + 20
        svg, layer = mn.new_document(os.path.basename(a.out) + ".svg", W, H)
        cx, cy = W / 2, H / 2
        top, left = cy - frame_h / 2 + a.border + a.clear, cx - a.frame_w / 2 + a.border + a.clear
        if a.layout == "top":
            ex, ey = cx - ew / 2, top
            ncx, ncy = cx, top + eh + a.gap + nh / 2
        else:
            ex, ey = left, cy - eh / 2
            ncx, ncy = left + ew + a.gap + (inner_w - ew - a.gap) / 2, cy
        s, nruns = add_emblem(layer, (polys, runs, b), ex, ey, ew, ppm, a, a.color)
        g = mn.add_lettering(layer, text, font, scale, "glyph", a.color, 0.4)
        plan, _ = mn.plan_from_nodes(svg, root=g)
        x0, y0, x1, y1 = plan.bounding_box
        g.set("transform", f"translate({ncx * ppm - (x0 + x1) / 2:.4f},{ncy * ppm - (y0 + y1) / 2:.4f}) {g.get('transform') or ''}".strip())
        class FA: pass
        fa = FA(); fa.frame_w, fa.frame_h, fa.border, fa.frame_spacing, fa.frame_color, fa.cut_codes = a.frame_w, frame_h, a.border, 0.4, a.color, 1
        ms.add_frame(layer, cx * ppm, cy * ppm, fa, ppm, 0)
        plan, problems = mn.plan_from_nodes(svg, check=True, trim_jumps=True)
        for p in problems: print(f"   {p[0]}: {p[1]} on {p[2]}")
        if any(p[0] == "ERROR" for p in problems): sys.exit("STOP: Ink/Stitch reports errors")
        write_embroidery_file(os.path.abspath(a.out), plan, svg, {"trim_at": 1})
        open(os.path.abspath(a.out) + ".svg", "w", encoding="utf-8").write(svg.tostring().decode("utf-8"))
        w, h = mn.plan_size_mm(plan)
        print(f"wrote {a.out}: '{text}' layout={a.layout} emblem {ew:.1f} x {eh:.1f} mm ({s:.4f} mm/px, {len(polys)} fills, "
              f"{len(runs)} line runs), letters {mn.plan_size_mm(ref)[1]*scale:.2f} mm, name {nw:.1f} x {nh:.1f} mm, "
              f"frame {a.frame_w:.1f} x {frame_h:.1f} mm, patch {w:.1f} x {h:.1f} mm, ~{sum(len(x) for x in plan)} stitches")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
