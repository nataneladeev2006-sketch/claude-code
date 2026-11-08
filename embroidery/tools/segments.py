"""Split a JEF into trim-separated segments (= letters with glyph trims) by parsing the raw bytes."""
import struct, math, sys

def parse_jef(path):
    b = open(path, "rb").read()
    off = struct.unpack_from("<i", b, 0)[0]
    data = b[off:]
    x = y = 0; i = 0; zero_jumps = 0
    segs = [[]]; moves = []
    while i + 1 < len(data):
        if data[i] == 0x80:
            op = data[i + 1]
            if op == 0x10:
                break
            dx = struct.unpack("b", data[i+2:i+3])[0]; dy = -struct.unpack("b", data[i+3:i+4])[0]
            i += 4
            if op == 0x02 and dx == 0 and dy == 0:
                zero_jumps += 1
                if zero_jumps == 3:
                    segs.append([]); zero_jumps = 0
                continue
            zero_jumps = 0
            moves.append(((x, y), (x + dx, y + dy), op))
            x += dx; y += dy
            segs[-1].append(("move", x, y))
        else:
            dx = struct.unpack("b", data[i:i+1])[0]; dy = -struct.unpack("b", data[i+1:i+2])[0]
            i += 2; zero_jumps = 0
            x += dx; y += dy
            segs[-1].append(("st", x, y))
    return [s for s in segs if any(k == "st" for k, _, _ in s)], moves

if __name__ == "__main__":
    segs, moves = parse_jef(sys.argv[1])
    print(f"{len(segs)} trim-separated segments")
    for n, s in enumerate(segs):
        st = [(x, y) for k, x, y in s if k == "st"]
        inner_moves = [(i, s[i]) for i in range(1, len(s)) if s[i][0] == "move" and any(k == "st" for k, _, _ in s[:i])]
        lens = [math.hypot(b[0]-a[0], b[1]-a[1]) / 10 for a, b in zip(st, st[1:])]
        xs = [p[0] for p in st]; ys = [p[1] for p in st]
        print(f"  seg {n}: {len(st):4d} stitches, x {min(xs)/10:6.1f}..{max(xs)/10:6.1f} y {min(ys)/10:5.1f}..{max(ys)/10:5.1f} mm, "
              f"longest stitch {max(lens):.2f} mm, jumps inside (no trim): {len(inner_moves)}")
