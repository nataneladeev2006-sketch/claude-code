# Embroidered name patches (Ink/Stitch Lettering → Janome `.jef`)

## Files for the machine: `usb/`

Copy the `.JEF` files to the USB stick (nothing else is needed).

| File | Stitches | Size (mm) |
|---|---|---|
| `DR_YAEL.JEF` | ד״ר יעל עזרא | 55.4 × 7.8 |
| `ACHOT.JEF` | אחות | 21.8 × 6.0 |
| `LIHI_SEV.JEF` | ליהי סביליה | 48.6 × 7.4 |
| `LIOR_LOG.JEF` | ליאור לוגסי | 45.6 × 7.4 |
| `HAREL_CO.JEF` | הראל כהן | 40.6 × 9.0 |
| `YASMIN_K.JEF` | יסמין קאקזנוב | 58.2 × 7.8 |
| `LIOR_ZOH.JEF` | ליאור זוהרה לוגסי | 70.8 × 7.4 |
| `DEKEL_SH.JEF` | דקל שרוני | 41.4 × 9.0 |

`all_names_preview.png` shows all of them. The list lives in `names.txt`.

All files use the same settings:
- Font **"פשוט מעוגל Small"**, Ink/Stitch's Hebrew satin font based on Varela Round.
- 6 mm letter height (scale 18.7 %), the same as the old רס״פ מפקדה patch. Everything fits inside the old patch's 71 × 9 mm.
- Satin spacing 0.4 mm, for regular 40wt embroidery thread.
- One thread color (Violet Blue, as in the old file), centered on the hoop, JEF hoop code 3 (126 × 110).
- A trim after every letter and inside the two-piece letters ה and ק, so no loose threads are left to cut.
- File names are 8.3 uppercase ASCII, which older Janome machines can read.

Special cases:
- **ד״ר**: the font has no ״ glyph. `make_name.py` adds one, built from Varela Round's own ״ outline as two satin
  columns. The two marks are joined at the top, where the gap is narrowest.
- **ליאור זוהרה לוגסי** was 74 mm wide. Its word gaps were narrowed from 3.7 to 2.1 mm so it fits 71 mm with the same
  letter size. Do **not** shrink this font below about 18.5 %: the gap inside ה then gets sewn over and it reads as ח.
  `validate_jef.py` catches this.

## Framed patches: `framed/`

These are several names in one file, each inside a green satin frame. The layout is copied from the design on the
machine (100 × 25 mm frames, about 9 mm letters). The machine sews all the names in **Black 002** first, stops for the
thread change, then sews the frames in **Yellow Green 218**.

| File | Frames (top to bottom) | Size (mm) | Hoop |
|---|---|---|---|
| `SHEET1.JEF` | עמית ממן / עידן רוזנבלום / רועי בלאו | 100.4 × 115.4 | 140 × 140 (SQ14b) |
| `SHEET2.JEF` | ע.טכנר / טכנר | 100.4 × 70.4 | 140 × 140 (SQ14b) |
| `ALL5_BIG.JEF` | all five | 100.4 × 190.4 | 140 × 200 (RE20b) or bigger |
| `SHEET3.JEF` | ד״ר יעל עזרא / רופא / ליהי סביליה / ליאור לוגסי | 100.4 × 130.4 | 140 × 140 (SQ14b) |
| `SHEET4.JEF` | הראל כהן / יסמין קאקזנוב / ליאור זוהרה לוגסי / דקל שרוני | 100.4 × 130.4 | 140 × 140 (SQ14b) |

A 140 × 140 hoop holds at most **4** frames of 100 × 25 mm, stacked in one column. Two frames side by side are
about 21 cm wide and don't fit any hoop up to 200 × 200.

Notes:
- SHEET1, SHEET2 and ALL5_BIG use one letter size, 9.00 mm (scale 28 %), for every name. The widest name,
  עידן רוזנבלום, fits with 1.4 mm to spare.
- SHEET3 and SHEET4 size each name on its own (`--fit each`): 9 mm letters wherever the name fits.
  יסמין קאקזנוב keeps 9 mm with narrower word gaps (3.9 mm). ליאור זוהרה לוגסי gets 7.26 mm letters and 2.5 mm word
  gaps (about 35 % of the letter height, the same as its single patch).
- At these sizes the machine trims between the two marks of ״, and inside ש, ק and ה, so no thread is left between the pieces.
- Each frame is one satin column (4 mm, contour + zigzag underlay) with mitred corners and a trim after it.
- The "." in ע.טכנר is Varela Round's own dot, added like the ״.
- A JEF file has no hoop code for 140 × 140, so `SHEET1.JEF` declares 140 × 200. The machine chooses the hoop by design size.
- The files were checked three ways:
  1. `validate_sheet.py`: bytes, header, the colors 002/218, frame sizes, each letter inside its frame, sewing order.
  2. Every frame's letters compared with a standalone build of the same name: same shapes, within 0.1 mm.
  3. Rendered and read.

The old `2_rasap_mifkada.jef` (from an earlier session) stitches upside down with its letters reversed. Don't use it.

## Making more names

`tools/make_name.py` runs Ink/Stitch's own Lettering engine headless (the same fonts and stitch generation as the
Inkscape extension), then `tools/validate_jef.py` checks the result.

One-time setup:

```bash
git clone --depth 1 https://github.com/inkstitch/inkstitch.git
rmdir inkstitch/fonts && git clone --depth 1 https://github.com/inkstitch/embroidery-fonts inkstitch/fonts
python3 -m venv venv && . venv/bin/activate
pip install networkx "shapely>=2" lxml platformdirs "numpy==2.2.6" jinja2 colormath2 flask fonttools trimesh xxhash diskcache pystitch cssselect tinycss2 pyparsing pyserial scour packaging pillow pyembroidery
pip install --no-deps inkex   # inkex's PyGObject dependency is only needed for GUI dialogs
```

Add lines to `names.txt` (`FILENAME.JEF | text`), then:

```bash
python embroidery/tools/make_name.py --inkstitch inkstitch --font "פשוט מעוגל Small" \
  --batch embroidery/names.txt --outdir embroidery/usb --letter-height 6 --satin-spacing 0.4 --max-width 71
python embroidery/tools/validate_jef.py embroidery/names.txt embroidery/usb 71 9
python embroidery/tools/preview.py embroidery/all_names_preview.png 13 embroidery/usb/DR_YAEL.JEF=DR_YAEL.JEF ...
```

Framed sheets (lines `FILE.JEF | name | name | ...` in a sheets file):

```bash
python embroidery/tools/make_sheet.py --inkstitch inkstitch --font "פשוט מעוגל Small" \
  --sheets embroidery/framed/sheets_hoop140.txt --outdir embroidery/framed
python embroidery/tools/make_sheet.py --inkstitch inkstitch --font "פשוט מעוגל Small" \
  --sheets embroidery/framed/sheets_hoop200.txt --outdir embroidery/framed --max-height 190
python embroidery/tools/make_sheet.py --inkstitch inkstitch --font "פשוט מעוגל Small" \
  --sheets embroidery/framed/sheets_4per_hoop140.txt --outdir embroidery/framed --fit each --max-height 130
python embroidery/tools/validate_sheet.py embroidery/framed/sheets_hoop140.txt embroidery/framed 140 140
```

`make_name.py` stops if a letter is missing from the font (Ink/Stitch would silently stitch a space) or if Ink/Stitch's
own checks report an error. Other options: `--text "..." --out X.JEF` for a single name, `--svg` for an editable
Inkscape file, `--out name.pes` / `.dst` / `.exp` for other machine brands, and `--measure` for a font's letter sizes.
