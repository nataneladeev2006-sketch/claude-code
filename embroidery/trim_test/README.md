# Cut-code test (Elna eXpressive 830 / Janome MC500E)

The machine stopped after every letter even with Thread Cutting set to Advanced and **Cutting Command: ON**.
Both files sew the word רופא at 9 mm letters, with exactly the same stitches as the normal files. Only the cut code differs:

| File | Cut after each letter written as |
|---|---|
| (normal files) | 3 zero-length jumps (Ink/Stitch / pystitch default) |
| `TEST_A.JEF` | 1 zero-length jump (how Janome's own software writes a cut; see pyembroidery issue #54) |
| `TEST_B.JEF` | no cut codes (the machine cuts jumps of 3 mm or longer by its own setting) |

Made with `make_name.py ... --jef-trim-codes 1` (A) and `--trim off --no-trim-jumps` (B).
