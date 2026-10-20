"""STL 讀取、簡化面數(保留 N%)與輸出二進位 STL。只用 Python 標準函式庫。

簡化方法:Garland-Heckbert 二次誤差(QEM)邊收合。
會避免翻面與破洞,開放邊界(沒封閉的邊)會加強保護。
"""
import heapq
import math
import re
import struct


# ---------------------------------------------------------------- 讀取

def read_stl(raw):
    """回傳三角形清單 [(v0, v1, v2), ...],每個 v 是 (x, y, z)。支援二進位與 ASCII。"""
    if len(raw) >= 84:
        n = struct.unpack_from("<I", raw, 80)[0]
        if 84 + n * 50 == len(raw):
            tris = []
            off = 84
            for _ in range(n):
                v = struct.unpack_from("<9f", raw, off + 12)
                tris.append(((v[0], v[1], v[2]), (v[3], v[4], v[5]), (v[6], v[7], v[8])))
                off += 50
            return tris
    text = raw.decode("utf-8", errors="ignore")
    nums = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    pts = [(float(a), float(b), float(c)) for a, b, c in nums]
    return [(pts[i], pts[i + 1], pts[i + 2]) for i in range(0, len(pts) - 2, 3)]


def _normal(p0, p1, p2):
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / ln, ny / ln, nz / ln) if ln > 1e-30 else (0.0, 0.0, 0.0)


def write_binary_stl(tris):
    out = bytearray(b"AssemblyViewer".ljust(80, b"\0"))
    out += struct.pack("<I", len(tris))
    for p0, p1, p2 in tris:
        n = _normal(p0, p1, p2)
        out += struct.pack("<12fH", n[0], n[1], n[2], *p0, *p1, *p2, 0)
    return bytes(out)


# ---------------------------------------------------------------- 簡化

def _weld(tris):
    index = {}
    verts, faces = [], []
    seen = set()  # 有些 CAD 匯出會把同一個三角形重複寫兩次,先去重,否則邊會被 4 個面共用而無法簡化
    for tri in tris:
        ids = []
        for p in tri:
            key = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
            i = index.get(key)
            if i is None:
                i = len(verts)
                index[key] = i
                verts.append([p[0], p[1], p[2]])
            ids.append(i)
        if ids[0] != ids[1] and ids[1] != ids[2] and ids[0] != ids[2]:
            key = tuple(sorted(ids))
            if key in seen:
                continue
            seen.add(key)
            faces.append(ids)
    return verts, faces


def _plane_quadric(p0, p1, p2, weight=None):
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-30:
        return [0.0] * 10
    w = ln / 2 if weight is None else weight  # 預設以面積加權
    a, b, c = nx / ln, ny / ln, nz / ln
    d = -(a * p0[0] + b * p0[1] + c * p0[2])
    return [w * a * a, w * a * b, w * a * c, w * a * d, w * b * b, w * b * c, w * b * d, w * c * c, w * c * d, w * d * d]


def _err(q, x, y, z):
    return (q[0] * x * x + 2 * q[1] * x * y + 2 * q[2] * x * z + 2 * q[3] * x
            + q[4] * y * y + 2 * q[5] * y * z + 2 * q[6] * y
            + q[7] * z * z + 2 * q[8] * z + q[9])


def _best_target(q, pa, pb):
    """在 a、b、中點、(可解時的)最佳點之中挑誤差最小的位置。"""
    mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, (pa[2] + pb[2]) / 2)
    cands = [mid, (pa[0], pa[1], pa[2]), (pb[0], pb[1], pb[2])]
    a2, ab, ac, ad, b2, bc, bd, c2, cd = q[:9]
    det = a2 * (b2 * c2 - bc * bc) - ab * (ab * c2 - bc * ac) + ac * (ab * bc - b2 * ac)
    if abs(det) > 1e-12:
        x = -(ad * (b2 * c2 - bc * bc) - ab * (bd * c2 - bc * cd) + ac * (bd * bc - b2 * cd)) / det
        y = -(a2 * (bd * c2 - bc * cd) - ad * (ab * c2 - bc * ac) + ac * (ab * cd - bd * ac)) / det
        z = -(a2 * (b2 * cd - bd * bc) - ab * (ab * cd - bd * ac) + ad * (ab * bc - b2 * ac)) / det
        elen = math.dist(pa, pb)
        if math.dist((x, y, z), mid) <= 1.5 * elen + 1e-9:
            cands.append((x, y, z))
    best = min(cands, key=lambda p: _err(q, p[0], p[1], p[2]))
    return best, max(_err(q, best[0], best[1], best[2]), 0.0)


def simplify(tris, keep_percent):
    """保留約 keep_percent% 的三角形數(1~100)。回傳新的三角形清單。"""
    n0 = len(tris)
    target = max(int(round(n0 * keep_percent / 100.0)), min(n0, 12))
    if target >= n0:
        return tris
    verts, faces = _weld(tris)
    nf = len(faces)

    vf = [set() for _ in verts]
    for fi, f in enumerate(faces):
        for v in f:
            vf[v].add(fi)
    Q = [[0.0] * 10 for _ in verts]
    edge_faces = {}
    for fi, f in enumerate(faces):
        q = _plane_quadric(verts[f[0]], verts[f[1]], verts[f[2]])
        for v in f:
            Qv = Q[v]
            for k in range(10):
                Qv[k] += q[k]
        for i in range(3):
            e = tuple(sorted((f[i], f[(i + 1) % 3])))
            edge_faces.setdefault(e, []).append(fi)
    # 開放邊界:加一個垂直於該面的平面,避免邊緣被吃掉
    for (a, b), fl in edge_faces.items():
        if len(fl) == 1:
            f = faces[fl[0]]
            nrm = _normal(verts[f[0]], verts[f[1]], verts[f[2]])
            ex, ey, ez = [verts[b][i] - verts[a][i] for i in range(3)]
            bx, by, bz = ey * nrm[2] - ez * nrm[1], ez * nrm[0] - ex * nrm[2], ex * nrm[1] - ey * nrm[0]
            bl = math.sqrt(bx * bx + by * by + bz * bz)
            if bl < 1e-30:
                continue
            elen2 = ex * ex + ey * ey + ez * ez
            p0 = verts[a]
            p1 = (p0[0] + bx / bl, p0[1] + by / bl, p0[2] + bz / bl)
            p2 = (p0[0] + ex, p0[1] + ey, p0[2] + ez)
            q = _plane_quadric(p0, p1, p2, weight=elen2 * 10)
            for v in (a, b):
                for k in range(10):
                    Q[v][k] += q[k]

    alive = [True] * len(verts)
    stamp = [0] * len(verts)
    heap = []
    counter = 0

    def neighbors(v):
        s = set()
        for fi in vf[v]:
            s.update(faces[fi])
        s.discard(v)
        return s

    def push(a, b):
        nonlocal counter
        q = [Q[a][k] + Q[b][k] for k in range(10)]
        pos, cost = _best_target(q, verts[a], verts[b])
        counter += 1
        heapq.heappush(heap, (cost, counter, a, b, stamp[a], stamp[b], pos))

    for (a, b) in edge_faces:
        push(a, b)

    def collapse_ok(a, b, pos, shared):
        na, nb = neighbors(a), neighbors(b)
        if len((na & nb)) != len(shared):
            return False
        for fi in (vf[a] | vf[b]) - shared:
            f = faces[fi]
            old = [verts[v] for v in f]
            new = [pos if v in (a, b) else verts[v] for v in f]
            o = _cross(old)
            n = _cross(new)
            lo = math.sqrt(o[0] ** 2 + o[1] ** 2 + o[2] ** 2)
            ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
            if ln < 1e-20 or lo < 1e-20:
                return False
            if (o[0] * n[0] + o[1] * n[1] + o[2] * n[2]) < 0.2 * lo * ln:
                return False
        return True

    cur = nf
    while cur > target and heap:
        cost, _, a, b, sa, sb, pos = heapq.heappop(heap)
        if not (alive[a] and alive[b]) or stamp[a] != sa or stamp[b] != sb:
            continue
        shared = vf[a] & vf[b]
        if not shared or not collapse_ok(a, b, pos, shared):
            continue
        # 收合 b → a
        verts[a] = [pos[0], pos[1], pos[2]]
        for k in range(10):
            Q[a][k] += Q[b][k]
        for fi in shared:
            for v in faces[fi]:
                if v != a and v != b:
                    vf[v].discard(fi)
            vf[a].discard(fi)
            faces[fi] = None
        for fi in list(vf[b]):
            if fi in shared:
                continue
            faces[fi] = [a if v == b else v for v in faces[fi]]
            vf[a].add(fi)
        vf[b] = set()
        alive[b] = False
        stamp[a] += 1
        cur -= len(shared)
        for n in neighbors(a):
            push(a, n) if a < n else push(n, a)

    out = []
    for f in faces:
        if f is not None:
            out.append((tuple(verts[f[0]]), tuple(verts[f[1]]), tuple(verts[f[2]])))
    return out


def _cross(p):
    ux, uy, uz = p[1][0] - p[0][0], p[1][1] - p[0][1], p[1][2] - p[0][2]
    vx, vy, vz = p[2][0] - p[0][0], p[2][1] - p[0][1], p[2][2] - p[0][2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
