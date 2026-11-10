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

## 9 names in one 20 × 20 hoop: `framed/NAMES9A.JEF` / `NAMES9B.JEF`

Names: ד״ר יעל עזרא, רופא, ליהי סביליה, ליאור לוגסי, הראל כהן, יסמין קאקזנוב (stacked), and ליאור זוהרה לוגסי,
דקל שרוני, הילה חמאני (turned sideways). The design is 194.6 × 182.4 mm. A 200 × 200 hoop holds at most 9 frames of
100 × 25 mm (`make_sheet.py --layout fill --hoop 196x196 --gap 6`). Names and frames use one thread (Black 002), so the
machine has no color-change stop.

The machine (Elna eXpressive 830, the same machine as the Janome MC500E) stopped after every letter, even with
*Thread Cutting: Advanced* and *Cutting Command: ON*. Every Ink/Stitch JEF writes a cut as 3 zero-length jumps;
Janome's own software writes 1 (pyembroidery issue #54). So there are two versions:

- **A** (`--cut-codes 1`): each cut is 1 code, like Janome's software. Try this first. The machine should cut by
  itself without stopping.
- **B** (`--cut-codes 0`): no cut codes. The machine cuts jumps of 3 mm or more by its own setting, and the shorter
  ones are left to snip. Gaps over 0.5 mm are jumps, never straight stitches across the fabric.

`trim_test/TEST_A.JEF` and `TEST_B.JEF` test the same two choices on one word.

`tools/make_name.py` uses a counter instead of Ink/Stitch's random 0–9999 element ids. With many copies of the same
letter in one file, those random ids could collide and crash the build. Only ids change, never stitches.

## Last 4 names incl. the special patch: `framed/NAMES4A.JEF`

דוד יצקסון, נווה לזניק, שלו מימון, and **נתנאל אדייב** in the chosen design (Magen David + double frame, written
`נתנאל אדייב @david` in the sheets file). One column of 4, 100.4 × 119.6 mm, so it fits the 14 × 14 hoop as well as the
20 × 20. One thread, 1-code cuts (version A). It replaces NAMES5A/NAMES5B, which also had אביטל ברדה; that patch is
already sewn. Each frame matches its standalone build and the same patch in NAMES5A piece for piece, and frame 4
matches the approved preview `special_preview/SPECIAL_david.JEF`.

## All 9 remaining names in one hooping: `framed/FINAL9A.JEF`

ליאור לוגסי, יסמין קאקזנוב, דוד יצקסון, נווה לזניק, שלו מימון, נתנאל אדייב (Magen David design) stacked, and
ליאור זוהרה לוגסי, דקל שרוני, הילה חמאני turned sideways. Same layout and size as NAMES9A: 194.6 × 182.4 mm, 20 × 20
hoop only (JEF hoop code 4), one thread, 1-code cuts, 29,364 needle stitches. It holds exactly the patches of
`REDO5A.JEF` + `NAMES4A.JEF`, so sew either FINAL9A or those two files, never both.

Checks: `validate_sheet.py`; every patch compared with its standalone build and with the same patch in REDO5A/NAMES4A
(drawn on exact integer JEF coordinates: 97.8–100% overlap, 0.00 mm edge shift); a rebuild differs only in the header's
date/time field; rendered and read. The earlier float-based shape check could dip below 90% on the tiny Magen David
triangles from pixel rounding alone (their stitches were identical), so the comparison now uses integer coordinates.

## 3 bird-emblem patches + the angry-face יסמין: `framed/BIRDS4A.JEF`

One column of 4 standard frames, 100.4 × 119.6 mm (14 × 14 or 20 × 20 hoop), one thread, 1-code cuts, 16,138 needle
stitches:

1. **אבירן בירן** `@bird`: the winged owl emblem with sword and crosshair (traced from `emblem/owl_wings.png`) on the
   left, 38.8 × 13 mm, and the name on the right.
2. **רומי שלם** `@bird`: same design.
3. **שקד ברנס** `@bird`: same design.
4. **יסמין קאקזנוב** `@angry`: an angry face (filled circle with the `> <` eyes and the frown left open), an anger mark
   and a cherry blossom on the left, a second cherry blossom at the right end. This is an extra, decorated patch;
   FINAL9A keeps the plain יסמין קאקזנוב.

It replaces NEW4A, which had עידן עזרא (a normal patch) instead of שקד ברנס; עידן עזרא was dropped.

Emblem tracing (`tools/emblem.py`): black areas wider than 4 source px become fill (rows along each area's long axis,
0.25 mm apart, pulled in 0.3 mm and outlined with a running stitch so thin pointed tips come out the same wherever the
patch sits); thin lines are skeletonized and sewn as triple stitch in as few continuous runs as possible (each line
once; travel back over a line is a single stitch). The faint inner rings of the crosshair are redrawn as a clean
reticle (`--emblem-crosshair 251,124,19.5,12.5,0`). `tools/emblem_patch.py` builds a single emblem patch on its own
(also a 100 × 51.5 mm "emblem above the name" layout).

Checks: `validate_sheet.py` (it now knows the side layout: ornament on the left, name centered in the rest, the
right-end flower of `@angry`); each patch compared with its standalone builds (`special.py --style bird|angry` and,
for the birds, an independent `emblem_patch.py` build): 95.4–97.2% overlap, at most 0.1 mm edge shift; a full rebuild
differs only in the header date; rendered and read. FINAL9A rebuilt with the new tools is unchanged, and all earlier
sheets still pass.

## 3 more names: `framed/NAMES3A.JEF`

ליאור זוהרה לוגסי (7.26 mm letters, as in the earlier files), יאיר פריבש, ליהי סיביליה (spelled with י after ס, as
written this time; the patch sewn earlier was ליהי סביליה). Normal framed patches, one column of 3, 100.4 × 88.2 mm,
14 × 14 or 20 × 20 hoop, one thread, 1-code cuts. Checked twice: validator; each patch vs a standalone build (and
ליאור זוהרה לוגסי vs the earlier build of the same name), all the same; a full rebuild differs only in the header date;
rendered and read.

## The emblem alone, 10 cm wide: `emblem/WINGS10.JEF`

The winged owl emblem by itself (no frame, no name), traced from the sharper picture `emblem/owl_wings_hd.png`:
100 × 32.6 mm as stitched (the emblem is ~3:1, so 10 cm wide is 3.3 cm tall), one thread, 1-code cuts, 4,104 needle
stitches, longest needle stitch 3.1 mm, 14 × 14 hoop. At this size everything is kept: the six stripes (fill, pulled in
0.15 mm so the white gaps stay open), the owl's crown, dark side, beak and pupils (fill), all crosshair rings and the
cross, the feathers and the sword with its dark center (triple-stitch lines, extended to touch the fills they run into).

```bash
python embroidery/tools/emblem_patch.py --inkstitch inkstitch --image embroidery/emblem/owl_wings_hd.png --layout alone \
  --emblem-w 100 --min-fill-area 15 --fill-inset 0.15 --inset-min-area 1000 --snap 4 --fill-outline 1 --bean 1 \
  --line-len 1.2 --out embroidery/emblem/WINGS10.JEF
```

`emblem.py` now works in "normalized px" (1/492 of the emblem's width), so pictures of any resolution get the same
settings; the old 496 px picture gives exactly the same result as before (BIRDS4A rebuilds unchanged).

Checks (twice, the second time on a full rebuild that differs only in the header date): file structure (one color,
single-code cuts, no loose jumps, size, centered), and the stitches drawn 0.45 mm wide against the picture's black at
the same scale: 99.7% of the picture's black is covered by thread and 100% of the thread lies on the picture's black
(0.35 mm tolerance); a mirrored copy would match worse (96.0%), so it is not flipped.

## Status

- **Sewn (11):** עמית ממן, עידן רוזנבלום, רועי בלאו, ע.טכנר, טכנר, אחות, הראל כהן, ד״ר יעל עזרא, רופא, ליהי סביליה,
  אביטל ברדה.
- **Still to sew (13):** `FINAL9A.JEF` (ליאור לוגסי, יסמין קאקזנוב, דוד יצקסון, נווה לזניק, שלו מימון, נתנאל אדייב,
  ליאור זוהרה לוגסי, דקל שרוני, הילה חמאני; one hooping, 20 × 20) and `BIRDS4A.JEF` (אבירן בירן, רומי שלם, שקד ברנס
  with the bird, יסמין קאקזנוב with the angry face and flowers; 14 × 14 or 20 × 20), `NAMES3A.JEF` (ליאור זוהרה
  לוגסי, יאיר פריבש, ליהי סיביליה), plus the emblem alone `emblem/WINGS10.JEF` (10 × 3.3 cm). `REDO5A.JEF` + `NAMES4A.JEF` hold the same
  patches as FINAL9A in two hoopings: sew FINAL9A or those two, never both.

## Redo: `framed/REDO5A.JEF`

NAMES9A went out of position partway through: the machine paused at stitch 22,271, in frame 6. Only 4 patches came out
usable: הראל כהן, ד״ר יעל עזרא, רופא, ליהי סביליה. `REDO5A.JEF` re-makes the other 5: ליאור לוגסי, יסמין קאקזנוב,
ליאור זוהרה לוגסי, דקל שרוני, הילה חמאני. It is one column of 5 frames, 100.4 × 151 mm, for the 20 × 20 hoop. It
replaces the earlier REDO4A, which lacked ליאור לוגסי. The file itself was correct: the machine's stitch total matched
it, 28,223 stitches. The likely cause is the fabric slipping in the hoop, or the hoop being blocked while moving, since
the 9-frame layout fills almost the whole 20 × 20 field. A single column of 5 leaves much more room.

## Special patch preview: `special_preview/`

Three designs for נתנאל אדייב (`tools/special.py`), all 100 × 25 mm in one thread: stars with a double frame, Magen
David with a double frame, and the חוכמה calligraphy font with stars. They wait for a choice before being added to a sheet.
`special.py` also has the side-ornament styles `bird` (needs `--emblem-image`) and `angry` used in BIRDS4A; in a sheets
file they are written `name @bird` / `name @angry`.

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

Sheets with emblem patches (`@bird`) also need `pip install opencv-python-headless scikit-image`:

```bash
python embroidery/tools/make_sheet.py --inkstitch inkstitch --font "פשוט מעוגל Small" \
  --sheets embroidery/framed/sheets_birds4_A.txt --outdir embroidery/framed --fit each --layout fill --hoop 196x196 \
  --gap 6 --cut-codes 1 --text-color "#000000" --frame-color "#000000" \
  --emblem-image embroidery/emblem/owl_wings.png --emblem-crosshair "251,124,19.5,12.5,0"
python embroidery/tools/validate_sheet.py embroidery/framed/sheets_birds4_A.txt embroidery/framed 140 140 --cut-codes 1 --colors 1
```

`make_name.py` stops if a letter is missing from the font (Ink/Stitch would silently stitch a space) or if Ink/Stitch's
own checks report an error. Other options: `--text "..." --out X.JEF` for a single name, `--svg` for an editable
Inkscape file, `--out name.pes` / `.dst` / `.exp` for other machine brands, and `--measure` for a font's letter sizes.
