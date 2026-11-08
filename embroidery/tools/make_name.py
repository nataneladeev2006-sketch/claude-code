#!/usr/bin/env python3
"""
make_name.py - make embroidery files (JEF, PES, DST, ...) for names using
Ink/Stitch's Lettering engine, without opening Inkscape.

It does what Inkscape > Extensions > Ink/Stitch > Lettering does: places the
pre-digitized font glyphs, then runs Ink/Stitch's stitch planner and file writer.

Extras over the plain Lettering tool:
  * adds a ״ (gershayim) glyph to fonts that lack it ("פשוט מעוגל" / "Small"),
    built from Varela Round's own ״ outline as two satin columns, so ד״ר works;
  * refuses to run if a letter is missing from the font (Ink/Stitch would
    silently turn it into a space);
  * runs Ink/Stitch's element validation (Troubleshoot) and fails on errors;
  * batch mode: one file per line of a list.

Examples:
  make_name.py --inkstitch ~/inkstitch --measure --font "פשוט מעוגל Small"
  make_name.py --inkstitch ~/inkstitch --font "פשוט מעוגל Small" --text "דקל שרוני" \\
      --letter-height 6 --satin-spacing 0.4 --out DEKEL_SH.JEF
  make_name.py --inkstitch ~/inkstitch --font "פשוט מעוגל Small" --batch names.txt \\
      --outdir usb --letter-height 6 --satin-spacing 0.4
      (names.txt lines:  FILENAME.JEF | text)
"""
import argparse
import copy
import importlib.abc
import importlib.machinery
import io
import json
import os
import shutil
import sys
import tempfile
import types


def install_wx_placeholder():
    """Ink/Stitch's library imports wxPython (its GUI toolkit) in a few GUI-only
    modules. No window is ever opened here, so when wxPython is not installed we
    register inert placeholder modules for `wx` and `wx.*`."""
    try:
        import wx  # noqa: F401
        return
    except ImportError:
        pass

    class Inert:
        def __init__(self, *a, **k): pass
        def __call__(self, *a, **k): return Inert()
        def __getattr__(self, name): return Inert()
        def __iter__(self): return iter((Inert(), Inert()))
        def __or__(self, other): return self
        __ror__ = __or__
        def __int__(self): return 0
        def __bool__(self): return False

    class InertMeta(type):
        def __getattr__(cls, name): return Inert()

    class InertModule(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            if name in ("NewEvent", "NewCommandEvent"):
                return lambda *a, **k: (InertMeta("Event", (object,), {}), Inert())
            if name[:1].isupper():
                cls = InertMeta(name, (object,), {"__init__": lambda self, *a, **k: None})
                setattr(self, name, cls)
                return cls
            return Inert()

    class Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path, target=None):
            if fullname == "wx" or fullname.startswith("wx."):
                return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
            return None

        def create_module(self, spec):
            module = InertModule(spec.name)
            module.__path__ = []
            return module

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, Finder())


# ----------------------------------------------------------------------------
# ״ (gershayim) for the "פשוט מעוגל" fonts.
# Those fonts are digitized from Varela Round Hebrew (1000 units/em) with
# svg_x = 0.2 * x and svg_y = 200 - 0.2 * y (checked on all 27 letters).
# Outline + advance below are Varela Round's U+05F4 (SIL OFL 1.1).
# ----------------------------------------------------------------------------
GERSHAYIM = "״"
GERSHAYIM_OUTLINE_TTF = (
    "M190 437Q180 441 174.5 453Q169 465 173 480L206 612Q211 632 226.5 641Q242 650 262 645"
    "Q280 638 286.5 622Q293 606 286 588L231 456Q218 429 190 437Z"
    "M59 437Q48 441 43 453Q38 465 42 480L74 612Q79 632 94.5 640.5Q110 649 130 644"
    "Q148 638 154.5 622.5Q161 607 153 588L99 456Q94 443 83 438Q72 433 59 437Z")
GERSHAYIM_ADVANCE_TTF = 311
# Satin rails (bottom -> top) following each stroke's sides, ending part-way
# into the round caps like the font's own ו and י.
GERSHAYIM_STROKES_TTF = [
    # right stroke (sewn first, bottom -> top)
    {"left": [(174.5, 453), (173, 480), (206, 612), (226.5, 641)],
     "right": [(214.25, 437.75), (231, 456), (286, 588), (286.5, 622)], "reverse": False},
    # left stroke (sewn second, top -> bottom): the strokes connect at the top,
    # where the gap between them is narrowest (~0.45 mm at 6 mm letters)
    {"left": [(43, 453), (42, 480), (74, 612), (94.5, 640.5)],
     "right": [(83, 438), (99, 456), (153, 588), (154.5, 622.5)], "reverse": True},
]


def _ttf_to_svg(pt):
    return (0.2 * pt[0], 200.0 - 0.2 * pt[1])


def _gershayim_satin_d(stroke):
    """Satin column path data: two rails + three rungs perpendicular to the stroke."""
    from shapely.geometry import LineString
    left = [_ttf_to_svg(p) for p in stroke["left"]]
    right = [_ttf_to_svg(p) for p in stroke["right"]]
    bottom = ((left[0][0] + right[0][0]) / 2, (left[0][1] + right[0][1]) / 2)
    top = ((left[-1][0] + right[-1][0]) / 2, (left[-1][1] + right[-1][1]) / 2)
    ax, ay = top[0] - bottom[0], top[1] - bottom[1]
    length = (ax ** 2 + ay ** 2) ** 0.5
    ux, uy = ax / length, ay / length          # along the stroke
    px, py = -uy, ux                            # across the stroke
    rungs = []
    for t in (0.15, 0.5, 0.85):
        cx, cy = bottom[0] + ax * t, bottom[1] + ay * t
        half = 14.0                             # rails are <= ~9 units from the axis
        rungs.append([(cx - px * half, cy - py * half), (cx + px * half, cy + py * half)])
    for rung in rungs:                          # each rung must cross each rail exactly once
        for rail in (left, right):
            hit = LineString(rung).intersection(LineString(rail))
            if hit.geom_type != "Point":
                raise RuntimeError("gershayim rung does not cross rail once")
    if stroke["reverse"]:
        left, right = left[::-1], right[::-1]
    sub = lambda pts: "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
    return " ".join([sub(left), sub(right)] + [sub(r) for r in rungs])


def add_gershayim(font_dir, out_dir):
    """Copy an Ink/Stitch font and add a ״ glyph to its variant SVGs and font.json."""
    import inkex
    from lxml import etree
    shutil.copytree(font_dir, out_dir)
    with open(os.path.join(out_dir, "font.json"), encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("units_per_em") != 200.0 or "Varela" not in meta.get("original_font", ""):
        raise RuntimeError("gershayim geometry is only calibrated for the Varela Round based fonts")
    outline = inkex.Path(GERSHAYIM_OUTLINE_TTF).transform(
        inkex.Transform(matrix=((0.2, 0, 0), (0, -0.2, 200)))).to_absolute()
    for variant in ("rtl", "ltr"):
        path = os.path.join(out_dir, f"{variant}.svg")
        if not os.path.exists(path):
            continue
        svg = inkex.load_svg(path).getroot()
        template = next(e for e in svg.iter() if e.get("{http://inkstitch.org/namespace}satin_column") == "True")
        layer = inkex.Layer()
        layer.label = f"GlyphLayer-{GERSHAYIM}"
        layer.set("style", "display:none")
        layer.set("id", f"glyph_gershayim_{variant}")
        hidden = inkex.PathElement()
        hidden.set("d", str(outline))
        hidden.set("style", "display:none;fill:none;stroke:#000000")
        hidden.set("id", f"gershayim_outline_{variant}")
        layer.append(hidden)
        strokes = GERSHAYIM_STROKES_TTF if variant == "rtl" else GERSHAYIM_STROKES_TTF[::-1]
        for i, stroke in enumerate(strokes):
            satin = inkex.PathElement()
            for k, v in template.attrib.items():
                if k.startswith("{http://inkstitch.org/namespace}"):
                    satin.set(k, v)
            # the ~1.3 mm hop between the two strokes is sewn, not jumped (no loose thread)
            satin.set("{http://inkstitch.org/namespace}min_jump_stitch_length_mm", "2")
            satin.set("style", template.get("style"))
            satin.set("inkscape:label", f"Colonne satin {i}")
            satin.set("id", f"gershayim_satin_{variant}_{i}")
            satin.set("d", _gershayim_satin_d(stroke))
            layer.append(satin)
        svg.append(layer)
        with open(path, "wb") as f:
            f.write(etree.tostring(svg.getroottree(), xml_declaration=True, encoding="UTF-8"))
    meta.setdefault("glyphs", [])
    if GERSHAYIM not in meta["glyphs"]:
        meta["glyphs"].append(GERSHAYIM)
    meta["horiz_adv_x"][GERSHAYIM] = round(GERSHAYIM_ADVANCE_TTF * 0.2)
    meta["name"] = meta["name"].strip() + " + ״"
    with open(os.path.join(out_dir, "font.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def normalize_text(text):
    """Use the real Hebrew ״ for ASCII/typographic double quotes typed between letters."""
    for q in ('"', "“", "”", "''"):
        text = text.replace(q, GERSHAYIM)
    return " ".join(text.split())


# ----------------------------------------------------------------------------

BLANK_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
     xmlns:inkstitch="http://inkstitch.org/namespace"
     sodipodi:docname="{docname}"
     width="200mm" height="100mm" viewBox="0 0 755.90551 377.95276">
  <sodipodi:namedview id="namedview1" inkscape:document-units="mm"/>
  <g inkscape:label="Layer 1" inkscape:groupmode="layer" id="layer1"/>
</svg>
"""

TRIM_OPTIONS = {"off": 0, "line": 1, "word": 2, "glyph": 3}
INKSTITCH_NS = "{http://inkstitch.org/namespace}"


def add_trims_before_jumps(stitch_plan):
    """Ink/Stitch leaves short jumps inside two-piece letters (ה, ק) untrimmed, which
    leaves a loose thread to snip by hand. Put a trim before every such jump.
    The tie-off/tie-in lock stitches around these jumps are already there."""
    from lib.stitch_plan import Stitch
    added = 0
    for block in stitch_plan:
        out = []
        for i, st in enumerate(block.stitches):
            prev = out[-1] if out else None
            if (st.jump and prev is not None and not (prev.trim or prev.jump or prev.stop or prev.color_change)):
                out.append(Stitch(prev.x, prev.y, trim=True))
                added += 1
            out.append(st)
        block.replace_stitches(out)
    return added


def build(text, font, scale, trim, color, docname, satin_spacing=None, check=False, trim_jumps=False,
          word_spacing=0):
    """Render `text` with `font` at `scale` into a fresh SVG.
    Returns (svg_root, stitch_plan, lettering_group, problems)."""
    import inkex
    from inkex import Group
    from lib.elements import iterate_nodes, nodes_to_elements
    from lib.metadata import InkStitchMetadata
    from lib.stitch_plan import stitch_groups_to_stitch_plan
    from lib.svg import get_correction_transform
    from lib.threads import ThreadCatalog

    svg = inkex.load_svg(io.BytesIO(BLANK_SVG.format(docname=docname).encode("utf-8"))).getroot()
    layer = svg.getElementById("layer1")

    settings = {
        "text": text, "text_align": 0, "back_and_forth": True,
        "font": font.marked_custom_font_id, "scale": int(round(scale * 100)),
        "trim_option": TRIM_OPTIONS[trim], "use_trim_symbols": False, "color_sort": 0,
        "letter_spacing": 0, "word_spacing": word_spacing, "line_height": 0,
    }
    lettering_group = Group()
    lettering_group.label = "Ink/Stitch Lettering"
    lettering_group.set("inkstitch:lettering", json.dumps(settings))
    layer.append(lettering_group)
    lettering_group.set("transform", get_correction_transform(lettering_group, child=True))

    destination_group = Group()
    destination_group.label = f"{font.name} scale {scale * 100:.0f}%"
    lettering_group.append(destination_group)
    font.render_text(text, destination_group, trim_option=TRIM_OPTIONS[trim],
                     use_trim_symbols=False, color_sort=0, text_align=0,
                     letter_spacing=0, word_spacing=word_spacing, line_height=0)
    destination_group.attrib["transform"] = f"scale({scale})"

    if satin_spacing:
        for node in destination_group.iter():
            if node.get(INKSTITCH_NS + "satin_column") == "True":
                node.set(INKSTITCH_NS + "zigzag_spacing_mm", str(satin_spacing))

    if color:
        for node in destination_group.iter():
            style = node.get("style")
            if style and "display:none" not in style.replace(" ", ""):
                st = node.style
                if st.get("stroke") not in (None, "none"):
                    st["stroke"] = color
                if st.get("fill") not in (None, "none"):
                    st["fill"] = color
                node.style = st

    metadata = InkStitchMetadata(svg)
    elements = nodes_to_elements(iterate_nodes(svg))
    problems = []
    if check:
        for element in elements:
            for err in element.validation_errors():
                problems.append(("ERROR", type(err).__name__, element.node.get_id()))
            for warn in element.validation_warnings():
                problems.append(("warning", type(warn).__name__, element.node.get_id()))
    stitch_groups = []
    for i, element in enumerate(elements):
        nxt = elements[i + 1] if i + 1 < len(elements) else None
        last = stitch_groups[-1] if stitch_groups else None
        stitch_groups.extend(element.embroider(last, nxt))
    stitch_plan = stitch_groups_to_stitch_plan(stitch_groups,
                                               collapse_len=metadata["collapse_len_mm"],
                                               min_stitch_len=metadata["min_stitch_len_mm"])
    ThreadCatalog().match_and_apply_palette(stitch_plan, metadata["thread-palette"])
    if trim_jumps:
        add_trims_before_jumps(stitch_plan)
    return svg, stitch_plan, lettering_group, problems


def fit_page(svg, lettering_group, stitch_plan, margin_mm=5):
    """Resize the SVG page to the design (+margin) and center the lettering on it,
    so it opens neatly in Inkscape. Does not affect the stitches."""
    from lib.svg import PIXELS_PER_MM
    x0, y0, x1, y1 = stitch_plan.bounding_box
    m = margin_mm * PIXELS_PER_MM
    w, h = (x1 - x0) + 2 * m, (y1 - y0) + 2 * m
    old = lettering_group.get("transform") or ""
    lettering_group.set("transform", f"translate({m - x0:.4f},{m - y0:.4f}) {old}".strip())
    svg.set("width", f"{w / PIXELS_PER_MM:.3f}mm")
    svg.set("height", f"{h / PIXELS_PER_MM:.3f}mm")
    svg.set("viewBox", f"0 0 {w:.4f} {h:.4f}")


def plan_size_mm(stitch_plan):
    from lib.svg import PIXELS_PER_MM
    x0, y0, x1, y1 = stitch_plan.bounding_box
    return (x1 - x0) / PIXELS_PER_MM, (y1 - y0) / PIXELS_PER_MM


def glyph_names(font):
    font._load_variants()
    return set(font.get_variant(font.default_variant).glyphs)


def load_font(args, needed_chars, tmpdir):
    from lib.lettering import Font, get_font_by_name
    if args.font_path:
        font = Font(os.path.abspath(args.font_path))
    else:
        font = get_font_by_name(args.font, False)
        if font is None:
            sys.exit(f"Font not found: {args.font}")
    have = glyph_names(font)
    if GERSHAYIM in needed_chars and GERSHAYIM not in have:
        patched = os.path.join(tmpdir, "font_with_gershayim")
        add_gershayim(font.path, patched)
        font = Font(patched)
        have = glyph_names(font)
    missing = sorted(set(needed_chars) - have - {" "})
    if missing:
        sys.exit(f"STOP: font '{font.name}' has no glyph for: {' '.join(missing)}")
    return font


def make_one(font, text, out, args, scale):
    from lib.output import write_embroidery_file
    docname = os.path.splitext(os.path.basename(out))[0] + ".svg"
    kw = dict(satin_spacing=args.satin_spacing, check=True, trim_jumps=not args.no_trim_jumps)
    svg, plan, group, problems = build(text, font, scale, args.trim, args.color or None, docname, **kw)
    spaces = text.count(" ")
    if args.max_width and plan_size_mm(plan)[0] > args.max_width and spaces:
        # 1) narrow the word gaps (keeps every name at the same letter size)
        from lib.svg import PIXELS_PER_MM
        gap = font.word_spacing * scale / PIXELS_PER_MM                    # mm, as stitched
        cut = min((plan_size_mm(plan)[0] - args.max_width + 0.3) / spaces, gap - args.min_word_gap)
        if cut > 0:
            ws = -cut / scale
            print(f"   note: '{text}' is {plan_size_mm(plan)[0]:.1f} mm wide; word gaps {gap:.1f} -> {gap - cut:.1f} mm "
                  f"to fit --max-width {args.max_width} mm")
            kw["word_spacing"] = ws
            svg, plan, group, problems = build(text, font, scale, args.trim, args.color or None, docname, **kw)
    if args.max_width and plan_size_mm(plan)[0] > args.max_width:
        # 2) last resort: smaller letters. NOTE: below ~18.5 % the gap inside ה gets sewn
        #    over (looks like ח) - validate_jef.py checks for that.
        new_scale = max(scale * args.max_width / plan_size_mm(plan)[0] * 0.995, font.min_scale)
        print(f"   WARNING: '{text}' still {plan_size_mm(plan)[0]:.1f} mm wide; scaling to {new_scale*100:.1f}%")
        scale = new_scale
        svg, plan, group, problems = build(text, font, scale, args.trim, args.color or None, docname, **kw)
    errors = [p for p in problems if p[0] == "ERROR"]
    for p in problems:
        print(f"   {p[0]}: {p[1]} on {p[2]}")
    if errors:
        sys.exit(f"STOP: Ink/Stitch reports errors for '{text}'")
    write_embroidery_file(os.path.abspath(out), plan, svg)
    if out.lower().endswith(".jef") and args.jef_hoop is not None:
        import struct
        with open(out, "r+b") as f:   # int32 at offset 32 = hoop code; other fields don't depend on it
            f.seek(32)
            f.write(struct.pack("<i", args.jef_hoop))
    w, h = plan_size_mm(plan)
    n = sum(len(block) for block in plan)
    glyphs = len(text.replace(" ", ""))
    print(f"wrote {out}: '{text}' ({glyphs} letters) font={font.name} scale={scale*100:.1f}% "
          f"satin-spacing={args.satin_spacing or 'font default'} size={w:.1f} x {h:.1f} mm, "
          f"~{n} stitches, colors={len(plan)}")
    if args.svg:
        svg_out = args.svg if not args.batch else os.path.splitext(out)[0] + ".svg"
        fit_page(svg, group, plan)
        with open(svg_out, "wb") as f:
            f.write(svg.tostring())
        print(f"wrote {svg_out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inkstitch", required=True, help="path to an Ink/Stitch source checkout (with fonts/)")
    ap.add_argument("--font", help='Ink/Stitch font name, e.g. "פשוט מעוגל Small"')
    ap.add_argument("--font-path", help="or: path to an Ink/Stitch font folder")
    ap.add_argument("--text", help="text to stitch")
    ap.add_argument("--out", help="output embroidery file (.jef, .pes, .dst, .exp, .vp3, ...)")
    ap.add_argument("--batch", help="file with lines 'FILENAME | text' (makes one file per line)")
    ap.add_argument("--outdir", default=".", help="folder for --batch output")
    ap.add_argument("--measure", action="store_true", help="print the font's native letter sizes and exit")
    ap.add_argument("--reference", default="ש", help="letter without ascender/descender used for --letter-height")
    ap.add_argument("--letter-height", type=float, help="height in mm of a normal letter (like ש)")
    ap.add_argument("--scale", type=float, help="font scale in percent (alternative to --letter-height)")
    ap.add_argument("--allow-out-of-range", action="store_true", help="don't clamp to the font's min/max scale")
    ap.add_argument("--trim", choices=TRIM_OPTIONS, default="glyph", help="where to add trims (default: after each letter)")
    ap.add_argument("--satin-spacing", type=float,
                    help="override satin density, mm peak-to-peak (font default for the Small font is 0.25 "
                         "= for 60wt thread; Ink/Stitch's normal default 0.4 suits regular 40wt thread)")
    ap.add_argument("--jef-hoop", type=int, default=3,
                    help="JEF header hoop code (0=110x110, 1=50x50, 2=140x200, 3=126x110, 4=200x200); default 3")
    ap.add_argument("--max-width", type=float,
                    help="fit names wider than this (mm): first narrower word gaps, then smaller letters")
    ap.add_argument("--min-word-gap", type=float, default=1.8, help="smallest word gap allowed by --max-width, mm")
    ap.add_argument("--no-trim-jumps", action="store_true",
                    help="don't add trims at the short jumps inside two-piece letters (ה, ק)")
    ap.add_argument("--color", default="#523a97", help="thread color (hex); empty keeps the font's colors")
    ap.add_argument("--svg", help="also save the Ink/Stitch SVG (with --batch: any value = one .svg per file)")
    args = ap.parse_args()
    if not (args.font or args.font_path):
        sys.exit("--font or --font-path is required")

    sys.path.insert(0, os.path.abspath(args.inkstitch))
    install_wx_placeholder()

    jobs = []
    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.lstrip().startswith("#"):
                    name, _, text = line.partition("|")
                    jobs.append((os.path.join(args.outdir, name.strip()), normalize_text(text)))
        os.makedirs(args.outdir, exist_ok=True)
    elif args.text and args.out:
        jobs.append((args.out, normalize_text(args.text)))
    elif not args.measure:
        sys.exit("give --text and --out, or --batch, or --measure")

    tmpdir = tempfile.mkdtemp(prefix="make_name_")
    try:
        needed = set("".join(text for _, text in jobs)) | set(args.reference)
        font = load_font(args, needed, tmpdir)

        if args.measure:
            print(f"font: {font.name} | scale range {font.min_scale:.2f}-{font.max_scale:.2f}")
            for ch in [args.reference, "ל", "ק", "דקל"]:
                _, plan, _, _ = build(ch, font, 1.0, "off", None, "measure.svg")
                w, h = plan_size_mm(plan)
                print(f"  '{ch}' at 100%: {w:.2f} x {h:.2f} mm")
            return

        if args.scale:
            scale = args.scale / 100.0
        elif args.letter_height:
            _, ref, _, _ = build(args.reference, font, 1.0, "off", None, "measure.svg")
            scale = args.letter_height / plan_size_mm(ref)[1]
        else:
            scale = 1.0
        if not args.allow_out_of_range:
            clamped = min(max(scale, font.min_scale), font.max_scale)
            if abs(clamped - scale) > 1e-9:
                print(f"note: scale {scale*100:.1f}% is outside this font's range "
                      f"{font.min_scale*100:.0f}-{font.max_scale*100:.0f}%; using {clamped*100:.1f}%")
            scale = clamped

        for out, text in jobs:
            make_one(font, text, out, args, scale)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
