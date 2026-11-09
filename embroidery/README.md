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

`make_name.py` stops if a letter is missing from the font (Ink/Stitch would silently stitch a space) or if Ink/Stitch's
own checks report an error. Other options: `--text "..." --out X.JEF` for a single name, `--svg` for an editable
Inkscape file, `--out name.pes` / `.dst` / `.exp` for other machine brands, and `--measure` for a font's letter sizes.
