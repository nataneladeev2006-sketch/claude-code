#!/usr/bin/env python3
"""
make_name.py - make an embroidery file (JEF, PES, DST, ...) for a name using
Ink/Stitch's Lettering engine, without opening Inkscape.

It does exactly what Inkscape > Extensions > Ink/Stitch > Lettering (or Batch
Lettering) does: places the pre-digitized font glyphs, then runs Ink/Stitch's
stitch planner and file writer.

Examples:
  make_name.py --inkstitch ~/inkstitch --measure --font "פשוט מעוגל Small"
  make_name.py --inkstitch ~/inkstitch --font "פשוט מעוגל Small" --text "דקל שרוני" \
      --letter-height 6 --satin-spacing 0.4 --out dekel_40wt.jef --svg dekel.svg
"""
import argparse
import importlib.abc
import importlib.machinery
import io
import json
import os
import sys
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


def build(text, font, scale, trim, color, docname, satin_spacing=None):
    """Render `text` with `font` at `scale` into a fresh SVG.
    Returns (svg_root, stitch_plan, lettering_group)."""
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
        "letter_spacing": 0, "word_spacing": 0, "line_height": 0,
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
                     letter_spacing=0, word_spacing=0, line_height=0)
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
    stitch_groups = []
    for i, element in enumerate(elements):
        nxt = elements[i + 1] if i + 1 < len(elements) else None
        last = stitch_groups[-1] if stitch_groups else None
        stitch_groups.extend(element.embroider(last, nxt))
    stitch_plan = stitch_groups_to_stitch_plan(stitch_groups,
                                               collapse_len=metadata["collapse_len_mm"],
                                               min_stitch_len=metadata["min_stitch_len_mm"])
    ThreadCatalog().match_and_apply_palette(stitch_plan, metadata["thread-palette"])
    return svg, stitch_plan, lettering_group


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inkstitch", required=True, help="path to an Ink/Stitch source checkout (with fonts/)")
    ap.add_argument("--font", required=True, help='Ink/Stitch font name, e.g. "פשוט מעוגל"')
    ap.add_argument("--text", help="text to stitch")
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
    ap.add_argument("--color", default="#523a97", help="thread color (hex); empty keeps the font's colors")
    ap.add_argument("--out", help="output embroidery file (.jef, .pes, .dst, .exp, .vp3, ...)")
    ap.add_argument("--svg", help="also save the Ink/Stitch SVG (open/edit it in Inkscape)")
    args = ap.parse_args()

    sys.path.insert(0, os.path.abspath(args.inkstitch))
    install_wx_placeholder()
    from lib.lettering import get_font_by_name
    from lib.output import write_embroidery_file

    font = get_font_by_name(args.font, False)
    if font is None:
        sys.exit(f"Font not found: {args.font}")

    if args.measure:
        print(f"font: {font.name} | scale range {font.min_scale:.2f}-{font.max_scale:.2f}")
        for ch in [args.reference, "ל", "ק", "דקל"]:
            _, plan, _ = build(ch, font, 1.0, "off", None, "measure.svg")
            w, h = plan_size_mm(plan)
            print(f"  '{ch}' at 100%: {w:.2f} x {h:.2f} mm")
        return

    if not (args.text and args.out):
        sys.exit("--text and --out are required (or use --measure)")

    if args.scale:
        scale = args.scale / 100.0
    elif args.letter_height:
        _, ref, _ = build(args.reference, font, 1.0, "off", None, "measure.svg")
        scale = args.letter_height / plan_size_mm(ref)[1]
    else:
        scale = 1.0
    if not args.allow_out_of_range:
        clamped = min(max(scale, font.min_scale), font.max_scale)
        if abs(clamped - scale) > 1e-9:
            print(f"note: scale {scale*100:.1f}% is outside this font's range "
                  f"{font.min_scale*100:.0f}-{font.max_scale*100:.0f}%; using {clamped*100:.1f}%")
        scale = clamped

    docname = os.path.splitext(os.path.basename(args.out))[0] + ".svg"
    svg, plan, group = build(args.text, font, scale, args.trim, args.color or None, docname,
                             satin_spacing=args.satin_spacing)
    write_embroidery_file(os.path.abspath(args.out), plan, svg)
    if args.out.lower().endswith(".jef") and args.jef_hoop is not None:
        import struct
        with open(args.out, "r+b") as f:   # int32 at offset 32 = hoop code; other fields don't depend on it
            f.seek(32)
            f.write(struct.pack("<i", args.jef_hoop))
    w, h = plan_size_mm(plan)
    n = sum(len(block) for block in plan)
    print(f"wrote {args.out}: '{args.text}' font={font.name} scale={scale*100:.1f}% "
          f"satin-spacing={args.satin_spacing or 'font default'} "
          f"size={w:.1f} x {h:.1f} mm, ~{n} stitches, colors={len(plan)}")
    if args.svg:
        fit_page(svg, group, plan)
        with open(args.svg, "wb") as f:
            f.write(svg.tostring())
        print(f"wrote {args.svg}")


if __name__ == "__main__":
    main()
