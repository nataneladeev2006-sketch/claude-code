#!/usr/bin/env python3
"""
emblem.py - turn a black-and-white emblem picture into embroidery geometry:
  * thick black areas (wider than --min-fill px in the source)  -> fill polygons
  * thin black lines                                             -> centerlines, routed into as few
    continuous runs as possible (each line sewn once as a triple stitch; repeated travel = single stitch)
All coordinates returned in source pixels (float); the caller scales them to mm.
"""
import math
import numpy as np
import cv2
import networkx as nx
from PIL import Image
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union
from skimage.morphology import skeletonize

REF_W = 492.0   # emblem width (source px) the size settings below were tuned on
UP = 4.0        # working px per "normalized px" (1/492 of the emblem width); set by load_mask() for each picture
# All sizes given to these functions and all coordinates they return are in normalized px, so a sharper or bigger
# picture of the same emblem gives the same proportions: the picture is worked at ~4 working px per normalized px.


def load_mask(path, min_area=12, drop_border=True):
    global UP
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    g = np.array(bg.convert("L"))
    dark = (g < 128).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    H, W = dark.shape
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        touches = x == 0 or y == 0 or x + w == W or y + h == H
        if drop_border and touches and ((w > 0.8 * W and h < 0.06 * H) or (h > 0.8 * H and w < 0.06 * W)):
            continue                                       # screenshot edge line / bar
        keep[i] = True
    # emblem width (ignoring specks) sets the scale; then drop specks relative to that scale
    big_ones = [i for i in range(1, n) if keep[i] and st[i, 4] >= min_area]
    x0 = min(st[i, 0] for i in big_ones); x1 = max(st[i, 0] + st[i, 2] - 1 for i in big_ones)
    norm = (x1 - x0 + 1) / REF_W                           # source px per normalized px
    for i in range(1, n):
        if keep[i] and st[i, 4] < min_area * norm * norm: keep[i] = False
    up = max(1, int(round(4 * REF_W / (x1 - x0 + 1))))     # integer upscale so we work at ~4 px per normalized px
    UP = up * norm
    clean = keep[lab]
    g2 = np.where(clean | (g >= 128), g, 255).astype(np.uint8)
    g2 = np.where(~clean & (g < 128), 255, g2).astype(np.uint8)
    big = cv2.resize(g2, (W * up, H * up), interpolation=cv2.INTER_CUBIC) if up > 1 else g2
    mask = big < 128
    ys, xs = np.nonzero(mask)
    box = (xs.min(), ys.min(), xs.max(), ys.max())
    return mask, box


def split(mask, min_fill_px, min_fill_area=150):
    """thick = parts at least min_fill_px (source px) wide and min_fill_area (source px^2) big -> fill;
    thin = all other black (small blobs stay lines)."""
    r = max(1, int(round(min_fill_px * UP / 2)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    thick = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(thick.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        if st[i, 4] < min_fill_area * UP * UP: thick[lab == i] = False
    # give each fill its original outline back (pointed tips etc.): the black within r+1 px of its core
    kr = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 3, 2 * r + 3))
    thick = mask & cv2.dilate(thick.astype(np.uint8), kr).astype(bool)
    # no lines within ~1.5 normalized px of a big fill (removes leftover slivers along fill edges); small fills
    # (below 150 normalized px^2: pupils, a beak, where a line gets thicker) only take their own pixels, so the lines
    # running into them stay whole
    e = 2 * int(round(1.5 * UP)) + 1                       # 13 x 13 at 4 working px per normalized px
    k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (e, e))
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(thick.astype(np.uint8), connectivity=8)
    big = np.zeros(n2, bool); big[1:] = st2[1:, 4] >= 150 * UP * UP
    big_fill = big[lab2]; small_fill = thick & ~big_fill
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thin = mask & ~cv2.dilate(big_fill.astype(np.uint8), k2).astype(bool) & ~cv2.dilate(small_fill.astype(np.uint8), k3).astype(bool)
    return thick, thin


def fill_polygons(thick, eps=1.0):
    cs, hier = cv2.findContours(thick.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = []
    if hier is None: return polys
    hier = hier[0]
    for i, c in enumerate(cs):
        if hier[i][3] != -1: continue                       # holes handled with their parent
        outer = cv2.approxPolyDP(c, eps, True)[:, 0, :] / UP
        holes = []
        j = hier[i][2]
        while j != -1:
            h = cv2.approxPolyDP(cs[j], eps, True)[:, 0, :] / UP
            if len(h) >= 3: holes.append(h)
            j = hier[j][0]
        if len(outer) >= 3:
            p = Polygon(outer, holes).buffer(0)          # may split a self-touching outline into parts
            polys.extend(g for g in (p.geoms if hasattr(p, "geoms") else [p]) if not g.is_empty)
    return polys


def _pixel_graph(sk):
    ys, xs = np.nonzero(sk)
    S = set(zip(xs.tolist(), ys.tolist()))
    G = nx.Graph()
    for (x, y) in S:
        G.add_node((x, y))
        for dx, dy in ((1, 0), (0, 1)):
            if (x + dx, y + dy) in S: G.add_edge((x, y), (x + dx, y + dy))
        for dx, dy in ((1, 1), (1, -1)):
            q = (x + dx, y + dy)
            # diagonal only when no orthogonal detour exists (avoids little triangles at corners)
            if q in S and (x + dx, y) not in S and (x, y + dy) not in S: G.add_edge((x, y), q)
    return G


def _chains(G):
    """split a pixel graph into chains between key nodes (degree != 2); loops become closed chains."""
    key = {n for n in G if G.degree(n) != 2}
    seen = set(); chains = []
    for a in key:
        for b in G[a]:
            e = frozenset((a, b))
            if e in seen: continue
            path = [a, b]; seen.add(e)
            while path[-1] not in key:
                nxt = [c for c in G[path[-1]] if frozenset((path[-1], c)) not in seen]
                if not nxt: break
                seen.add(frozenset((path[-1], nxt[0]))); path.append(nxt[0])
            chains.append(path)
    for comp in nx.connected_components(G):                # pure loops (no key node)
        if any(n in key for n in comp): continue
        start = next(iter(comp)); path = [start]; prev = None; cur = start
        while True:
            nxt = [c for c in G[cur] if c != prev]
            if not nxt or (nxt[0] == start and len(path) > 2): path.append(start); break
            prev, cur = cur, nxt[0]; path.append(cur)
            if len(path) > len(comp) + 2: break
        chains.append(path)
    return chains


def centerlines(thin, min_spur_px=4.0, simplify_px=0.35):
    """returns a networkx MultiGraph: nodes = junction/end points (source px), edges carry 'pts' polylines."""
    sk = skeletonize(thin)
    G = _pixel_graph(sk)
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])
    chains = _chains(G)
    # prune short spurs (chain ending in a dead end) repeatedly
    for _ in range(3):
        deg = {}
        for c in chains:
            for n in (c[0], c[-1]):
                deg[n] = deg.get(n, 0) + 1
        keep = []
        for c in chains:
            L = sum(math.dist(c[i], c[i + 1]) for i in range(len(c) - 1)) / UP
            dead = (deg[c[0]] == 1) != (deg[c[-1]] == 1)
            if dead and L < min_spur_px: continue
            if deg[c[0]] == 1 and deg[c[-1]] == 1 and L < min_spur_px * 2: continue   # isolated speck
            keep.append(c)
        if len(keep) == len(chains): break
        chains = keep
    M = nx.MultiGraph()
    for c in chains:
        pts = np.array(c, float) / UP
        ls = LineString(pts)
        if ls.length == 0: continue
        sim = np.array(ls.simplify(simplify_px).coords)
        a, b = tuple(c[0]), tuple(c[-1])
        M.add_edge(a, b, pts=sim)
    return M


def route(M):
    """cover every edge of every connected component with one continuous run.
    returns [ [ (pts, first_pass_bool), ... ] per component ]"""
    runs = []
    for comp in nx.connected_components(M):
        H = M.subgraph(comp).copy()
        E = nx.MultiGraph(H)
        # weights = polyline lengths
        for u, v, k, d in E.edges(keys=True, data=True):
            d["weight"] = LineString(d["pts"]).length
        if not nx.is_eulerian(E):
            odd = [n for n in E if E.degree(n) % 2]
            # simple graph with the cheapest edge between each pair of nodes, for shortest travel paths
            G1 = nx.Graph()
            for u, v, k, d in E.edges(keys=True, data=True):
                if not G1.has_edge(u, v) or d["weight"] < G1[u][v]["weight"]:
                    G1.add_edge(u, v, weight=d["weight"], key=k)
            dist, paths = {}, {}
            for a in odd:
                dd, pp = nx.single_source_dijkstra(G1, a, weight="weight")
                dist[a], paths[a] = dd, pp
            # pair odd nodes so the doubled travel is as short as possible (min-weight perfect matching)
            K = nx.Graph()
            for i, a in enumerate(odd):
                for b in odd[i + 1:]:
                    K.add_edge(a, b, weight=-dist[a][b])
            pairs = sorted(nx.max_weight_matching(K, maxcardinality=True), key=lambda p: dist[p[0]][p[1]])
            pairs = pairs[:-1]          # leave the longest pair unpaired: the run starts at one and ends at the other
            for a, b in pairs:
                path = paths[a][b]
                for u, v in zip(path, path[1:]):
                    k = G1[u][v]["key"]; d0 = E[u][v][k]
                    E.add_edge(u, v, pts=d0["pts"], weight=d0["weight"], dup=True, cls=d0.get("cls", "line"))
        odd = [n for n in E if E.degree(n) % 2]
        start = odd[0] if odd else next(iter(E))
        walk = list(nx.eulerian_path(E, source=start, keys=True)) if odd else list(nx.eulerian_circuit(E, source=start, keys=True))
        used = set(); seq = []
        for u, v, k in walk:
            d = E[u][v][k]; pts = d["pts"]
            # orient the polyline from u to v
            if math.dist(pts[0] * UP, u) > math.dist(pts[-1] * UP, u): pts = pts[::-1]
            base = (min(u, v), max(u, v), round(float(LineString(pts).length), 3))
            first = base not in used and not d.get("dup", False)
            if first: used.add(base)
            seq.append((pts, first, d.get("cls", "line")))
        runs.append(seq)
    return runs


def replace_crosshair(M, cx, cy, r_cut, r_inner, r_mid=None, n=72):
    """Drop traced lines inside r_cut of (cx, cy) [source px] and add a clean reticle instead:
    inner ring (r_inner) + cross, as one connected piece; optional middle ring (r_mid) as a thin single line."""
    drop = []
    for u, v, k, d in M.edges(keys=True, data=True):
        pts = d["pts"]
        inside = sum(1 for x, y in pts if math.hypot(x - cx, y - cy) < r_cut)
        if inside >= 0.5 * len(pts): drop.append((u, v, k))
    M.remove_edges_from(drop)
    M.remove_nodes_from([q for q in list(M) if M.degree(q) == 0])
    node = lambda x, y: (x * UP + 0.123, y * UP + 0.123)      # off-grid keys: never collide with traced nodes
    c = node(cx, cy)
    ends = []
    for a in (0, 90, 180, 270):                                # spokes from the center to the inner ring
        ex, ey = cx + r_inner * math.cos(math.radians(a)), cy + r_inner * math.sin(math.radians(a))
        e = node(ex, ey); ends.append((a, e))
        M.add_edge(c, e, pts=np.array([(cx, cy), (ex, ey)]))
    for i, (a, e) in enumerate(ends):                          # four quarter arcs between the spoke ends
        a2, e2 = ends[(i + 1) % 4]
        angs = np.linspace(math.radians(a), math.radians(a + 90), n // 4 + 1)
        M.add_edge(e, e2, pts=np.c_[cx + r_inner * np.cos(angs), cy + r_inner * np.sin(angs)])
    if r_mid:
        angs = np.linspace(math.radians(225), math.radians(225 + 360), n + 1)
        st = node(cx + r_mid * math.cos(angs[0]), cy + r_mid * math.sin(angs[0]))
        M.add_edge(st, st, pts=np.c_[cx + r_mid * np.cos(angs), cy + r_mid * np.sin(angs)], cls="thin")
    return M


def snap_to_fills(M, polys, max_d=2.5):
    """Lines that end within max_d normalized px of a fill are extended to touch it (closes the small gaps the
    keep-away zone leaves where an outline runs into a solid area). Returns the number of ends extended."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points, unary_union
    if not polys: return 0
    fills = unary_union(polys)
    n = 0
    for node in [q for q in list(M) if M.degree(q) == 1]:
        u, v, k, d = next(iter(M.edges(node, keys=True, data=True)))
        pts = d["pts"]
        at_start = math.dist(pts[0] * UP, node) <= math.dist(pts[-1] * UP, node)
        end = Point(pts[0] if at_start else pts[-1])
        dist = end.distance(fills)
        if 0.05 < dist <= max_d:
            q = nearest_points(end, fills)[1]
            ext = np.array([[q.x, q.y]])
            d["pts"] = np.vstack([ext, pts]) if at_start else np.vstack([pts, ext])
            n += 1
    return n
