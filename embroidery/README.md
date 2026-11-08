# Embroidered name patches (Ink/Stitch Lettering → Janome `.jef`)

## Files

| File | What it is |
|---|---|
| `dekel_sharoni_40wt.jef` | **דקל שרוני** for regular 40wt embroidery thread (satin spacing 0.4 mm) |
| `dekel_sharoni_60wt.jef` | same design, for thin 60wt thread (the font's own 0.25 mm spacing) |
| `dekel_sharoni.svg` | the Ink/Stitch file; open it in Inkscape and edit the text with *Extensions › Ink/Stitch › Lettering* |
| `dekel_sharoni_preview.png` | preview of both versions, plus the old `2_rasap_mifkada.jef` for comparison |

Design settings: Ink/Stitch font **"פשוט מעוגל Small"** (Hebrew satin font based on Varela Round),
letter height 6 mm (the same as the old רס״פ מפקדה patch), finished size 41.4 × 9.0 mm, one thread color
(Violet Blue, as before), a trim after every letter, centered on the hoop, JEF hoop code 3 (126 × 110), like the old file.

The old `2_rasap_mifkada.jef` (from an earlier session) stitches **upside down with its letters in reverse order**:
no rotation or mirroring on the machine fixes both problems. Remake it with the tool below instead of reusing it.
Note that "פשוט מעוגל" has no ״ (gershayim) glyph; the "חוכמה" fonts have one, but they only go down to about 9.6 mm letters.

## Making another name

`tools/make_name.py` runs Ink/Stitch's own Lettering engine headless: the same fonts and stitch generation as the
Inkscape extension, without the GUI.

One-time setup:

```bash
git clone --depth 1 https://github.com/inkstitch/inkstitch.git
rmdir inkstitch/fonts && git clone --depth 1 https://github.com/inkstitch/embroidery-fonts inkstitch/fonts
python3 -m venv venv && . venv/bin/activate
pip install networkx "shapely>=2" lxml platformdirs "numpy==2.2.6" jinja2 colormath2 flask fonttools trimesh xxhash diskcache pystitch cssselect tinycss2 pyparsing pyserial scour packaging pillow pyembroidery
pip install --no-deps inkex   # inkex's PyGObject dependency is only needed for GUI dialogs
```

Make a name (6 mm letters, regular thread) and a preview image:

```bash
python embroidery/tools/make_name.py --inkstitch inkstitch --font "פשוט מעוגל Small" \
  --text "דקל שרוני" --letter-height 6 --satin-spacing 0.4 --out dekel_sharoni_40wt.jef --svg dekel_sharoni.svg
python embroidery/tools/preview.py preview.png 20 dekel_sharoni_40wt.jef="caption"
```

Useful options: leave out `--satin-spacing` for 60wt thread; `--measure` prints a font's letter sizes;
`--trim word|glyph|off`; `--out name.pes` / `.dst` / `.exp` for other machine brands. The script keeps the
scale inside each font's allowed range (for "פשוט מעוגל Small": 15–30 %, i.e. about 4.8–9.7 mm letters).
