# 第三版模型：bpy 程式建模，無頭執行
#   blender.exe -b -P src/build_models.py
# 產出 models/leo.glb（主衛星 SAT、手機直連衛星 D2C、用戶終端 UT、閘道站 GW 四個根節點）
# 座標一律用頁面（three.js、Y 朝上）的單位寫，最後統一轉成 Blender 的 Z 朝上，匯出時再轉回去
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Matrix, Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
TEX = os.path.join(ROOT, '.tmp', 'B3', 'tex')
OUT = os.path.join(ROOT, 'models', 'leo.glb')
os.makedirs(TEX, exist_ok=True)
rng = np.random.default_rng(7)
PI = math.pi

bpy.ops.wm.read_factory_settings(use_empty=True)
SCN = bpy.context.scene
COL = SCN.collection
CONV = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # 頁面 (x,y,z) -> Blender (x,-z,y)

# ---------------------------------------------------------------- 貼圖（numpy）
def save_img(name, arr, noncolor=False):
    h, w = arr.shape[:2]
    if arr.ndim == 2: arr = np.stack([arr] * 3, -1)
    rgba = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], -1)[::-1].astype(np.float32)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(rgba.ravel())
    p = os.path.join(TEX, name + '.png')
    img.filepath_raw = p; img.file_format = 'PNG'; img.save()
    img.source = 'FILE'; img.filepath = p; img.reload()
    if noncolor: img.colorspace_settings.name = 'Non-Color'
    return img

def normal_from_h(hm, strength):
    gy, gx = np.gradient(hm)
    nx, ny = -gx * strength, gy * strength
    l = np.sqrt(nx * nx + ny * ny + 1)
    return np.stack([nx / l * .5 + .5, ny / l * .5 + .5, 1 / l * .5 + .5], -1)

def blur(a, k=1):
    for _ in range(k):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5
    return a

def vnoise(h, w, cell, seed):
    r = np.random.default_rng(seed)
    gh, gw = h // cell + 2, w // cell + 2
    g = r.random((gh, gw))
    y = np.arange(h) / cell; x = np.arange(w) / cell
    y0 = y.astype(int); x0 = x.astype(int); fy = (y - y0)[:, None]; fx = (x - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]; b = g[y0][:, x0 + 1]; c = g[y0 + 1][:, x0]; d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

# 匯流排頂板（p72：深石墨色、沿長邊分兩半、每半再分成長方形面板，中間一條亮的脊）
def tex_deck():
    W, H = 2048, 1232  # 4.0 x 2.4
    yy, xx = np.mgrid[0:H, 0:W]
    hgt = np.zeros((H, W)); col = np.zeros((H, W)); rough = np.full((H, W), .5)
    # 面板格：沿 x 6 格（不等寬）、每半 z 方向 2 格
    xs = np.cumsum([0, 300, 380, 330, 360, 320, 358]); xs = (xs / xs[-1] * W).astype(int)
    zs = [0, 300, 590, 642, 940, H]
    pid = np.zeros((H, W), int)
    for i in range(6):
        for j in range(5):
            if j == 2: continue
            m = (xx >= xs[i]) & (xx < xs[i + 1]) & (yy >= zs[j]) & (yy < zs[j + 1])
            pid[m] = i * 7 + j + 1
            col[m] = .055 + rng.random() * .03
            rough[m] = .42 + rng.random() * .16
    seam = np.zeros((H, W), bool)
    for x in xs: seam |= np.abs(xx - x) < 4
    for z in zs: seam |= np.abs(yy - z) < 4
    hgt[:] = 1.0
    hgt[seam] = 0.0
    # 中央脊（兩半之間），高起
    spine = (yy > 592) & (yy < 640)
    hgt[spine] = 1.6; col[spine] = .16; rough[spine] = .3
    # 每塊面板內細格紋（太陽遮罩／熱控貼片）
    grid = ((xx % 64) < 2) | ((yy % 48) < 2)
    hgt -= grid * .12; col -= grid * .012
    # 鉚釘
    riv = np.zeros((H, W))
    for x in xs:
        for z in range(10, H, 40):
            d = (xx - x - 12) ** 2 + (yy - z) ** 2; riv = np.maximum(riv, np.clip(1 - d / 25, 0, 1))
    hgt += riv * .5; col += riv * .08
    n = vnoise(H, W, 6, 3) * .6 + vnoise(H, W, 40, 4) * .4
    col *= .85 + n * .3; rough += (n - .5) * .1
    hgt = blur(hgt, 2)
    base = np.stack([col * .92, col * .97, col * 1.08], -1)
    base = np.where(seam[..., None], base * .35, base)
    mr = np.stack([np.zeros_like(col), np.clip(rough, .2, .8), np.full_like(col, .55)], -1)
    return save_img('deck_base', base), save_img('deck_mr', mr, True), save_img('deck_nrm', normal_from_h(hgt, 2.5), True)

# 太陽電池（p72：藍灰電池格、銀色細格線；一張貼圖＝翼寬 x 1/4 翼長）
def tex_cell():
    W, H = 1024, 2048
    yy, xx = np.mgrid[0:H, 0:W]
    cw, ch = W / 4, H / 8
    i = (xx // cw).astype(int); j = (yy // ch).astype(int)
    fx = xx - i * cw; fy = yy - j * ch
    gap = (fx < 5) | (fx > cw - 5) | (fy < 5) | (fy > ch - 5)
    tone = rng.random((8, 4))[j, i]
    g = fy / ch
    col = np.stack([.035 + .012 * g, .055 + .015 * g, .11 + .03 * g], -1) * (.85 + tone[..., None] * .3)
    fing = ((yy % 7) == 0)
    col = col + fing[..., None] * .012
    bus = (np.abs(fx - cw * .33) < 2.2) | (np.abs(fx - cw * .67) < 2.2)
    col = np.where(bus[..., None], [.42, .45, .5], col)
    col = np.where(gap[..., None], [.5, .53, .58], col)
    hgt = np.where(gap, 0., 1.)
    return save_img('cell_base', col), save_img('cell_nrm', normal_from_h(blur(hgt, 1), 1.5), True)

# 相位陣列（朝地面）：一塊面板 16x16 個方形貼片
def tex_array():
    W = 2048; n = 16; s = W / n
    yy, xx = np.mgrid[0:W, 0:W]
    fx = xx % s; fy = yy % s
    patch = (fx > 26) & (fx < s - 26) & (fy > 26) & (fy < s - 26)
    inner = (fx > 44) & (fx < s - 44) & (fy > 44) & (fy < s - 44)
    col = np.full((W, W, 3), [.035, .038, .045])
    col = np.where(patch[..., None], [.16, .14, .11], col)
    col = np.where(inner[..., None], [.42, .33, .2], col)
    via = ((fx - s / 2) ** 2 + (fy - s * .3) ** 2) < 36
    col = np.where(via[..., None], [.05, .05, .05], col)
    hgt = patch * .6 + inner * .4
    emi = np.zeros((1024, 1024))
    e2 = inner[::2, ::2]; emi[:] = e2
    return save_img('array_base', col), save_img('array_nrm', normal_from_h(blur(hgt, 1), 2.), True), save_img('array_emit', emi)

# 電路板：綠色防焊、金色走線、焊墊、白色網印
def tex_pcb():
    W = 2048
    col = np.zeros((W, W, 3)); col[:] = [.02, .1, .065]
    emi = np.zeros((W // 2, W // 2))
    r = np.random.default_rng(91)
    tr = np.zeros((W, W), bool)
    for _ in range(420):
        x, y = r.integers(0, W, 2)
        w = int(r.choice([3, 4, 6, 10]))
        for k in range(4):
            L = int(r.integers(30, 260)); d = r.integers(0, 4)
            if d == 0: tr[y:y + w, x:min(W, x + L)] = True; x = min(W - 1, x + L)
            elif d == 1: tr[y:min(W, y + L), x:x + w] = True; y = min(W - 1, y + L)
            elif d == 2: tr[y:y + w, max(0, x - L):x] = True; x = max(0, x - L)
            else: tr[max(0, y - L):y, x:x + w] = True; y = max(0, y - L)
    col[tr] = [.36, .27, .1]
    pads = np.zeros((W, W), bool)
    for _ in range(900):
        x, y = r.integers(0, W - 20, 2); a, b = r.integers(6, 18, 2); pads[y:y + b, x:x + a] = True
    col[pads] = [.75, .6, .3]
    for _ in range(60):  # 網印框
        x, y = r.integers(0, W - 200, 2); a, b = r.integers(60, 200, 2)
        col[y:y + 3, x:x + a] = [.75, .78, .72]; col[y + b:y + b + 3, x:x + a] = [.75, .78, .72]
        col[y:y + b, x:x + 3] = [.75, .78, .72]; col[y:y + b, x + a:x + a + 3] = [.75, .78, .72]
    sel = tr & (r.random((W, W)) > -1)
    emi[:] = tr[::2, ::2] * (np.random.default_rng(3).random((W // 2, W // 2)) > -1)
    n = vnoise(W, W, 30, 5)
    col *= (.95 + n[..., None] * .1)
    hgt = tr * .5 + pads * 1.
    return save_img('pcb_base', col), save_img('pcb_nrm', normal_from_h(blur(hgt.astype(float), 1), 1.5), True), save_img('pcb_emit', emi)

# 機房外牆：直條金屬面板
def tex_panel():
    W = 1024
    yy, xx = np.mgrid[0:W, 0:W]
    rib = (xx % 64)
    hgt = np.where(rib < 6, 0., np.where(rib < 10, .5, 1.)) - ((yy % 512) < 4) * 1.
    col = np.full((W, W, 3), [.16, .165, .17]) * (.9 + vnoise(W, W, 50, 9)[..., None] * .2)
    col = np.where((rib < 6)[..., None], col * .4, col)
    return save_img('panel_base', col), save_img('panel_nrm', normal_from_h(blur(hgt, 1), 2.), True)

# ---------------------------------------------------------------- 材質
MATS = {}
def mat(name, color, metal=0., rough=.5, base=None, mr=None, nrm=None, nstr=1., emis=None, emis_tex=None, alpha=1.):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if base:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = base
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    if mr:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = mr
        sp = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(t.outputs['Color'], sp.inputs['Color'])
        nt.links.new(sp.outputs['Green'], b.inputs['Roughness'])
        nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    if nrm:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = nrm
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if emis_tex:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = emis_tex
        nt.links.new(t.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = 1.
    elif emis:
        b.inputs['Emission Color'].default_value = (*emis, 1); b.inputs['Emission Strength'].default_value = 1.
    MATS[name] = m
    return m

# ---------------------------------------------------------------- 幾何
PIECES = {}  # 節點名 -> [物件]
def _finish(bm, node, m, M=None, sharp=32, uv=False):
    if M is not None: bm.transform(M)
    for f in bm.faces: f.smooth = True
    for e in bm.edges:
        if (not e.is_manifold) or e.calc_face_angle(0) > math.radians(sharp): e.smooth = False
    me = bpy.data.meshes.new(node); bm.to_mesh(me); bm.free()
    me.materials.append(MATS[m])
    ob = bpy.data.objects.new(node, me); COL.objects.link(ob)
    PIECES.setdefault(node, []).append(ob)
    return ob

def TR(c=(0, 0, 0), r=(0, 0, 0)):
    return Matrix.Translation(Vector(c)) @ Euler(r, 'ZYX').to_matrix().to_4x4()

def box(node, m, c, s, bev=0., seg=2, r=(0, 0, 0), uvp=None, M=None):
    """s=(寬x, 高y, 深z)。uvp=(軸, 重複u, 重複v) 時給平面投影的 UV"""
    bm = bmesh.new()
    if uvp: bm.loops.layers.uv.new('UVMap')
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts)
    if bev > 0:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=min(bev, min(s) * .45), offset_type='OFFSET',
                        segments=seg, profile=.5, affect='EDGES', clamp_overlap=True)
    if uvp:
        ax, ru, rv = uvp; ul = bm.loops.layers.uv.active
        for f in bm.faces:
            for l in f.loops:
                v = l.vert.co
                if ax == 'y': l[ul].uv = ((v.x / s[0] + .5) * ru, (.5 - v.z / s[2]) * rv)
                else: l[ul].uv = ((v.x / s[0] + .5) * ru, (v.y / s[1] + .5) * rv)
    T = TR(c, r)
    if M is not None: T = M @ T
    return _finish(bm, node, m, T, uv=bool(uvp))

def cyl(node, m, c, rad, h, segs=24, r=(0, 0, 0), r2=None, M=None, cap=True, bev=0.):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, segments=segs, radius1=rad, radius2=rad if r2 is None else r2, depth=h)
    if bev > 0:
        es = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 1.]
        bmesh.ops.bevel(bm, geom=es, offset=bev, offset_type='OFFSET', segments=2, profile=.5, affect='EDGES', clamp_overlap=True)
    T = TR(c, r) @ Matrix.Rotation(-PI / 2, 4, 'X')  # 圓柱軸 Z -> Y
    if M is not None: T = M @ T
    return _finish(bm, node, m, T, sharp=40)

def rod(node, m, a, b, rad, segs=8, M=None):
    a, b = Vector(a), Vector(b); d = b - a
    q = Vector((0, 1, 0)).rotation_difference(d.normalized())
    T = Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4()
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=rad, radius2=rad, depth=d.length)
    T = T @ Matrix.Rotation(-PI / 2, 4, 'X')
    if M is not None: T = M @ T
    return _finish(bm, node, m, T, sharp=50)

def lathe(node, m, prof, segs=32, M=None, closed=False, sharp=50):
    """prof=[(半徑, y)]，繞 Y 軸旋轉"""
    bm = bmesh.new(); rings = []
    for k in range(segs):
        a = 2 * PI * k / segs; ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((r * ca, y, r * sa)) for r, y in prof])
    for k in range(segs):
        A, B = rings[k], rings[(k + 1) % segs]
        for i in range(len(prof) - 1):
            try: bm.faces.new((A[i], A[i + 1], B[i + 1], B[i]))
            except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.normal_update()
    return _finish(bm, node, m, M, sharp=sharp)

def sphere(node, m, c, rad, u=32, v=16, M=None, sc=(1, 1, 1)):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=rad)
    bmesh.ops.scale(bm, vec=Vector(sc), verts=bm.verts)
    T = TR(c)
    if M is not None: T = M @ T
    return _finish(bm, node, m, T, sharp=80)

def tube(node, m, pts, rad, segs=6, M=None, raw=False):
    """沿折線拉管子（簡單的 Catmull-Rom 取樣）"""
    P = [Vector(p) for p in pts]; S = [] if not raw else P[:-1]
    if raw: P = P[-1:]
    for i in range(len(P) - 1):
        p0 = P[max(0, i - 1)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(len(P) - 1, i + 2)]
        for t in np.linspace(0, 1, 8, endpoint=False):
            t2, t3 = t * t, t * t * t
            S.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    S.append(P[-1])
    bm = bmesh.new(); rings = []
    up = Vector((0, 1, 0))
    for i, p in enumerate(S):
        d = (S[min(i + 1, len(S) - 1)] - S[max(i - 1, 0)]).normalized()
        a = d.cross(up)
        if a.length < 1e-3: a = d.cross(Vector((1, 0, 0)))
        a.normalize(); b = d.cross(a)
        rings.append([bm.verts.new(p + (a * math.cos(2 * PI * k / segs) + b * math.sin(2 * PI * k / segs)) * rad) for k in range(segs)])
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    return _finish(bm, node, m, M, sharp=80)

def ortho_path(pts, rc=.035):
    """直角折線 -> 轉角換成小圓弧的取樣點"""
    P = [Vector(p) for p in pts]; out = [P[0]]
    for i in range(1, len(P) - 1):
        v = P[i]; a = v + (P[i - 1] - v).normalized() * rc; b = v + (P[i + 1] - v).normalized() * rc
        for t in np.linspace(0, 1, 7):
            out.append((1 - t) ** 2 * a + 2 * (1 - t) * t * v + t * t * b)
    out.append(P[-1]); return out

def offset_xz(pts, o):
    """水平面上的直角折線往左側平移 o（轉角用斜接）"""
    P = [Vector(p) for p in pts]; R = []
    for i, v in enumerate(P):
        ns = []
        for a, b in ((P[i - 1], v) if i > 0 else (None, None), (v, P[i + 1]) if i < len(P) - 1 else (None, None)):
            if a is None: continue
            d = (b - a); d.y = 0; d.normalize(); ns.append(Vector((-d.z, 0, d.x)))
        n = ns[0] if len(ns) == 1 else ns[0] + ns[1]
        R.append(v + n * o)
    return R

def rr_prism(node, m, w, h, t, r, c=(0, 0, 0), seg=6, M=None, bev=0.):
    """圓角矩形板（xy 平面、厚度沿 z）"""
    bm = bmesh.new(); loop = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, PI / 2), (-w / 2 + r, -h / 2 + r, PI), (w / 2 - r, -h / 2 + r, 1.5 * PI)):
        for k in range(seg + 1):
            a = a0 + k / seg * PI / 2; loop.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    F = [bm.verts.new((x, y, t / 2)) for x, y in loop]; B = [bm.verts.new((x, y, -t / 2)) for x, y in loop]
    bm.faces.new(F); bm.faces.new(B[::-1]); n = len(loop)
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((B[i], B[j], F[j], F[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    if bev > 0:
        es = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 1.2]
        bmesh.ops.bevel(bm, geom=es, offset=bev, offset_type='OFFSET', segments=2, profile=.5, affect='EDGES', clamp_overlap=True)
    bm.normal_update()
    T = TR(c)
    if M is not None: T = M @ T
    return _finish(bm, node, m, T, sharp=50)

def grid_plane(node, m, c, w, d, ru=1, rv=1, r=(0, 0, 0), M=None, flip=False):
    """水平面板（朝 +Y），UV 0..ru / 0..rv"""
    bm = bmesh.new(); ul = bm.loops.layers.uv.new('UVMap')
    v = [bm.verts.new((-w / 2, 0, -d / 2)), bm.verts.new((w / 2, 0, -d / 2)), bm.verts.new((w / 2, 0, d / 2)), bm.verts.new((-w / 2, 0, d / 2))]
    f = bm.faces.new((v[3], v[2], v[1], v[0]) if not flip else (v[0], v[1], v[2], v[3]))
    for l in f.loops:
        co = l.vert.co; l[ul].uv = ((co.x / w + .5) * ru, (.5 - co.z / d) * rv)
    T = TR(c, r)
    if M is not None: T = M @ T
    return _finish(bm, node, m, T)

# ---------------------------------------------------------------- 開始建
deck_b, deck_mr, deck_n = tex_deck()
cell_b, cell_n = tex_cell()
pan_b, pan_n = tex_panel()

mat('m_deck', (1, 1, 1), base=deck_b, mr=deck_mr, nrm=deck_n)
mat('m_frame', (.11, .12, .135), .85, .38)
mat('m_wall', (.025, .028, .032), .7, .42)
mat('m_edge', (.62, .65, .7), 1., .22)
mat('m_alu', (.45, .48, .52), .95, .3)
mat('m_dark', (.03, .033, .038), .6, .5)
mat('m_black', (.008, .009, .01), .2, .7)
mat('m_mli', (.55, .45, .22), 1., .32)       # 金色隔熱毯（推進器、雷射終端周邊）
mat('m_array', (1, 1, 1), .35, .55)   # 貼圖由頁面在執行時以 2K 畫布產生（省檔案）
mat('m_pcb', (1, 1, 1), .2, .5)       # 同上
mat('m_chip', (.035, .037, .04), .3, .45)
mat('m_copper', (.75, .45, .2), 1., .3)
mat('m_ceramic', (.62, .55, .42), .0, .5)
mat('m_can', (.75, .78, .82), 1., .18)
mat('m_cell', (1, 1, 1), .25, .32, base=cell_b, nrm=cell_n, nstr=.8)
mat('m_cellback', (.06, .065, .07), .3, .7)
mat('m_dish', (.7, .72, .75), 1., .26)        # 回傳碟反射面（p72 銀色）
mat('m_glass', (.01, .015, .02), .9, .08)     # 雷射終端光學窗
mat('m_battery', (.06, .065, .07), .7, .45)
mat('m_label', (.55, .5, .2), .3, .5, emis=(1., .55, .18))   # 電池標籤條微微發暖光
mat('m_harness', (.12, .085, .05), .3, .55, emis=(1., .55, .15))
mat('m_copv', (.07, .075, .08), .4, .5)
mat('m_plume', (.05, .03, .1), .0, .5, emis=(.62, .52, 1.))
mat('m_rad', (.62, .64, .66), .2, .35)
mat('m_ut_white', (.78, .78, .77), .0, .55)
mat('m_ut_grey', (.22, .23, .24), .5, .45)
mat('m_ut_rf', (.03, .05, .04), .2, .5)
mat('m_radome', (.66, .67, .68), .0, .62)
mat('m_concrete', (.3, .3, .29), .0, .9)
mat('m_panel', (1, 1, 1), .6, .45, base=pan_b, nrm=pan_n)
mat('m_d2c_ant', (1, 1, 1), .7, .32, base=cell_b, nrm=cell_n)

BW, BD = 4.0, 2.4

# ============ s5_struct：底板、側牆、四角立柱、邊條、內部隔板、側邊的小盒子 ============
N = 's5_struct'
box(N, 'm_frame', (0, -.08, 0), (BW, .04, BD), .012)
box(N, 'm_wall', (0, 0, BD / 2 - .012), (BW - .2, .15, .02), .004)
box(N, 'm_wall', (0, 0, -BD / 2 + .012), (BW - .2, .15, .02), .004)
box(N, 'm_wall', (BW / 2 - .012, 0, 0), (.02, .15, BD - .2), .004)
box(N, 'm_wall', (-BW / 2 + .012, 0, 0), (.02, .15, BD - .2), .004)
for sx in (1, -1):
    for sz in (1, -1):
        box(N, 'm_edge', (sx * (BW / 2 - .055), 0, sz * (BD / 2 - .055)), (.11, .2, .11), .02, 3)
for y in (.09, -.09):
    for sz in (1, -1):
        box(N, 'm_edge', (0, y, sz * BD / 2), (BW - .1, .016, .028), .005)
    for sx in (1, -1):
        box(N, 'm_edge', (sx * BW / 2, y, 0), (.028, .016, BD - .1), .005)
for i in (-1, 0, 1):
    box(N, 'm_frame', (i * 1.3, -.005, 0), (.03, .14, BD - .12), .005)
box(N, 'm_frame', (0, -.005, 0), (BW - .12, .14, .03), .005)
# p72 V3 本體四周一圈不規則的小盒子（電子盒、接頭、熱控）
for side in range(4):
    n = 16 if side < 2 else 9
    for k in range(n):
        t = (k + .5) / n + (rng.random() - .5) * .03
        w = .05 + rng.random() * .11; h = .03 + rng.random() * .07; d = .025 + rng.random() * .035
        m = 'm_dark' if rng.random() < .65 else ('m_alu' if rng.random() < .7 else 'm_mli')
        y = -.03 + rng.random() * .08
        if side < 2:
            sz = 1 if side == 0 else -1
            box(N, m, ((t - .5) * (BW - .4), y, sz * (BD / 2 + d / 2)), (w, h, d))
        else:
            sx = 1 if side == 2 else -1
            if abs((t - .5) * (BD - .4)) < .3 and sx < 0: continue  # 推進器位置留空
            box(N, m, (sx * (BW / 2 + d / 2), y, (t - .5) * (BD - .4)), (d, h, w))

# ============ s5_lid：頂板（拆開時往上掀） ============
N = 's5_lid'
box(N, 'm_deck', (0, .092, 0), (BW, .035, BD), .01, 2, uvp=('y', 1, 1))
box(N, 'm_edge', (0, .113, 0), (BW - .2, .012, .05), .004)        # 中央脊
for x in (-1.3, 0, 1.3):
    box(N, 'm_frame', (x, .112, 0), (.04, .01, BD - .2), .003)
# 星象儀：兩個小盒＋遮光罩，在頂板一端
for k, (x, z) in enumerate([(1.55, -.75), (1.55, -.45)]):
    box(N, 'm_dark', (x, .14, z), (.12, .06, .1), .01)
    cyl(N, 'm_black', (x + .02, .2, z), .035, .07, 16, r2=.05, r=(0, 0, -.35))
# 頂面幾個低矮的設備盒（低調）
for (x, z, w, d) in [(.45, .55, .26, .16), (-.35, -.6, .3, .14), (.95, .3, .18, .18)]:
    box(N, 'm_dark', (x, .125, z), (w, .03, d), .006)

# ============ s1_array：朝地面的相位陣列（8 塊） ============
N = 's1_array'
for i in range(4):
    for j in range(2):
        x = -1.44 + i * .96; z = .56 if j else -.56
        box(N, 'm_frame', (x, -.104, z), (.94, .012, 1.1), .004)
        grid_plane(N, 'm_array', (x, -.131, z), .9, 1.06, 1, 1, r=(PI, 0, 0))
        box(N, 'm_dark', (x, -.118, z), (.9, .024, 1.06), .006)

# ============ s4_pcb：本體內的五片電路板 ============
N = 's4_pcb'
for (x, z) in [(-1.2, -.55), (0, -.55), (1.2, -.55), (-1.2, .55), (0, .55)]:
    grid_plane(N, 'm_pcb', (x, -.003, z), 1.12, 1.0, 1, 1)
    box(N, 'm_pcb', (x, -.02, z), (1.12, .032, 1.0), .004)
    box(N, 'm_copper', (x, -.042, z), (1.14, .008, 1.02))
    for k in range(3):
        cx = x - .3 + k * .3; cz = z + (.18 if k % 2 else -.15)
        box(N, 'm_chip', (cx, .012, cz), (.2, .03, .2), .008)
        box(N, 'm_can', (cx, .03, cz), (.12, .008, .12), .002)       # 散熱蓋
    for k in range(6):
        box(N, 'm_chip', (x - .4 + k * .16, .002, z + .38), (.08, .012, .06), .002)
    box(N, 'm_black', (x, .01, z - .44), (.8, .025, .05), .003)     # 板邊連接器

# ============ s7_avionics：一塊小板上的被動元件、記憶體、時脈、感測 ============
N = 's7_avionics'
bx, bz = .95, .55
grid_plane(N, 'm_pcb', (bx, -.003, bz), 1.12, 1.0, 1, 1)
box(N, 'm_pcb', (bx, -.02, bz), (1.12, .032, 1.0), .004)
box(N, 'm_chip', (.7, .015, .38), (.26, .04, .26), .008)
box(N, 'm_chip', (1.18, .015, .62), (.2, .04, .32), .008)
box(N, 'm_chip', (.82, .01, .78), (.32, .03, .12), .006)
box(N, 'm_chip', (1.25, .01, .28), (.14, .03, .14), .006)
for i in range(3):
    cyl(N, 'm_can', (.5 + i * .11, .03, .66), .04, .06, 20, bev=.006)
box(N, 'm_can', (1.05, .02, .36), (.16, .05, .1), .01)
for i in range(48):
    box(N, 'm_dark', (.48 + (i % 12) * .08, .005, .84 - (i // 12) * .06), (.045, .02, .025))
for i in range(48):
    box(N, 'm_ceramic', (.98 + (i % 8) * .05, .005, .82 - (i // 8) * .05), (.03, .02, .03))
    box(N, 'm_can', (.98 + (i % 8) * .05 - .013, .006, .82 - (i // 8) * .05), (.006, .022, .031))

# ============ s2_feeder：四角回傳碟＋雙軸雲台＋波導＋濾波器 ============
N = 's2_feeder'
f, R0 = .17, .27
prof = [(i / 12 * R0, (i / 12 * R0) ** 2 / (4 * f)) for i in range(13)]
prof += [(R0 + .012, R0 * R0 / (4 * f) + .004), (R0 + .012, R0 * R0 / (4 * f) - .012)]
prof += [(R0 * .97 * (8 - i) / 8, ((R0 * .97 * (8 - i) / 8) ** 2) / (4 * f) - .02) for i in range(9)]
dep = R0 * R0 / (4 * f)
for (sx, sz) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
    px, pz = sx * 1.7, sz * 1.36; bz = pz - sz * .17
    cyl(N, 'm_dark', (px, -.115, bz), .09, .03, 32, bev=.006)
    cyl(N, 'm_alu', (px, -.15, bz), .062, .05, 32, bev=.005)
    cyl(N, 'm_alu', (px, -.172, (bz + pz) / 2), .02, .2, 12, r=(PI / 2, 0, 0))
    for dx in (-.1, .1):
        box(N, 'm_alu', (px + dx, -.235, pz), (.02, .12, .05), .006)
        cyl(N, 'm_dark', (px + dx * 1.1, -.29, pz), .042, .02, 24, r=(0, 0, PI / 2), bev=.004)
    box(N, 'm_alu', (px, -.18, pz), (.22, .02, .05), .006)
    Md = TR((px, -.3, pz), (PI + sz * .8, 0, -sx * .5))
    lathe(N, 'm_dish', prof, 32, M=Md, sharp=60)
    cyl(N, 'm_dark', (0, -.035, 0), .06, .04, 24, M=Md, bev=.005)
    for k in range(8):
        an = k * PI / 4
        rod(N, 'm_dark', (math.cos(an) * .05, -.03, math.sin(an) * .05), (math.cos(an) * R0 * .85, dep * .7 - .03, math.sin(an) * R0 * .85), .007, 6, M=Md)
    cyl(N, 'm_dark', (0, f * .95, 0), .016, .06, 16, r2=.034, M=Md)
    for k in range(3):
        an = k * 2.094 + .5
        rod(N, 'm_alu', (math.cos(an) * R0 * .93, dep - .006, math.sin(an) * R0 * .93), (0, f * .92, 0), .005, 6, M=Md)
    # 波導（矩形截面）＋法蘭＋濾波器（帶調諧螺絲）
    box(N, 'm_copper', (px - sx * .36, -.125, bz), (.5, .03, .045), .004)
    for x in (px - sx * .6, px - sx * .12):
        box(N, 'm_copper', (x, -.125, bz), (.014, .06, .075), .003)
    box(N, 'm_copper', (px - sx * .76, -.14, bz), (.24, .06, .11), .01)
    for k in range(5):
        cyl(N, 'm_alu', (px - sx * .76 - .09 + k * .045, -.175, bz), .009, .022, 8)

# ============ s3_laser：三個雷射終端 ============
N = 's3_laser'
for (x, y, z) in [(1.8, .27, .98), (-1.8, .27, .98), (1.8, .27, -.98)]:
    cyl(N, 'm_dark', (x, y - .2, z), .2, .05, 40, bev=.01)
    cyl(N, 'm_alu', (x, y - .1, z), .165, .16, 40, bev=.012)
    for k in range(12):
        a = k * PI / 6
        box(N, 'm_dark', (x + math.cos(a) * .172, y - .1, z + math.sin(a) * .172), (.018, .13, .04), r=(0, -a, 0))
    cyl(N, 'm_mli', (x, y - .17, z), .185, .03, 40)
    prof_d = [(math.sin(t) * .15, math.cos(t) * .15) for t in np.linspace(0, PI / 2, 12)]
    lathe(N, 'm_glass', prof_d, 40, M=TR((x, y - .02, z)), sharp=80)
    cyl(N, 'm_edge', (x, y - .02, z), .158, .012, 40)

# ============ s6_power：兩片太陽翼、桁架、電池、線束 ============
N = 's6_power'
L, Wd = 8.6, 2.7
for sz in (1, -1):
    Mw = TR((0, 0, sz * 2.35), (0, 0, -.38))
    grid_plane(N, 'm_cell', (0, .0105, sz * L / 2), Wd, L, 1, 4, M=Mw)
    grid_plane(N, 'm_cellback', (0, -.0105, sz * L / 2), Wd, L, 1, 1, M=Mw, flip=True)
    box(N, 'm_cellback', (0, 0, sz * L / 2), (Wd - .02, .018, L - .02), M=Mw)
    for xx in (Wd / 2, -Wd / 2):
        box(N, 'm_alu', (xx, 0, sz * L / 2), (.03, .034, L), .006, M=Mw)
    box(N, 'm_alu', (0, 0, sz * (L - .015)), (Wd, .034, .03), .006, M=Mw)
    box(N, 'm_edge', (0, 0, sz * .03), (Wd + .04, .05, .06), .012, M=Mw)   # p72 翼根那條亮的金屬條
    for k in range(1, 8):
        box(N, 'm_cellback', (0, -.024, sz * k * L / 8), (Wd, .012, .035), M=Mw)
    box(N, 'm_cellback', (0, -.024, sz * L / 2), (.05, .012, L), M=Mw)
    # 桁架：p72 是兩根細桿從本體長邊伸到翼根，加一組菱形
    a1, a2 = (-.5, 0, sz * 1.2), (.5, 0, sz * 1.2)
    m1, m2 = (0, .18, sz * 1.78), (0, -.18, sz * 1.78)
    e1, e2 = (-.35, 0, sz * 2.33), (.35, 0, sz * 2.33)
    for p, q in [(a1, m1), (a2, m1), (a1, m2), (a2, m2), (m1, e1), (m1, e2), (m2, e1), (m2, e2), (m1, m2)]:
        rod(N, 'm_alu', p, q, .012, 8)
    for p in (m1, m2):
        sphere(N, 'm_dark', p, .025, 12, 8)
    cyl(N, 'm_alu', (0, 0, sz * 2.34), .032, .8, 20, r=(0, 0, PI / 2), bev=.006)
    box(N, 'm_dark', (0, 0, sz * 1.22), (1.15, .06, .05), .008)          # 驅動機構
# 電池組：六個模組（深色金屬外殼、銅端子、標籤條）
for k in range(6):
    x = -1.62 + (k % 3) * .42; z = .38 + (k // 3) * .34
    box(N, 'm_battery', (x, -.01, z), (.38, .12, .3), .012, 2)
    box(N, 'm_label', (x, .051, z + .08), (.22, .002, .06))
    for dx in (-.12, .12):
        cyl(N, 'm_copper', (x + dx, .058, z - .08), .018, .02, 12)
# 線束：從電池走到桁架、再沿桁架到翼根（發光的流動脈衝由頁面加上）
HY = .072
ROUTES = [[(-.59, HY, .62), (-.25, HY, .62), (-.25, HY, 1.0), (.12, HY, 1.0), (.12, HY, 2.27)],
          [(-.59, HY, .3), (-.4, HY, .3), (-.4, HY, -1.0), (.12, HY, -1.0), (.12, HY, -2.27)]]
for rt in ROUTES:
    for o in (-.026, 0, .026):
        tube(N, 'm_harness', ortho_path(offset_xz(rt, o), .05 + o), .0105, 8, raw=True)
    for a, b in zip(rt[:-1], rt[1:]):                     # 線槽：每段直線下面一條淺槽
        a, b = Vector(a), Vector(b); mid = (a + b) / 2; d = b - a
        L = d.length + .09
        sz_ = (L, .012, .1) if abs(d.x) > abs(d.z) else (.1, .012, L)
        box(N, 'm_dark', (mid.x, HY - .018, mid.z), sz_)
        n = int(d.length / .35)
        for k in range(1, n + 1):                          # 束線夾
            q = a + d * (k / (n + 1))
            box(N, 'm_alu', (q.x, HY, q.z), (.02, .03, .1) if abs(d.x) > abs(d.z) else (.1, .03, .02))

# ============ s8_prop：霍爾推進器、氣瓶 ============
N = 's8_prop'
Mt = TR((-2.03, -.02, 0), (0, 0, PI / 2))  # 推進器軸朝 -x
lathe(N, 'm_alu', [(.11, 0), (.125, .02), (.13, .1), (.125, .17), (.105, .18)], 40, M=Mt)
lathe(N, 'm_dark', [(.105, .18), (.095, .18), (.095, .16)], 40, M=Mt)
lathe(N, 'm_plume', [(.094, .165), (.064, .165)], 40, M=Mt)               # 放電通道（發光）
lathe(N, 'm_alu', [(.062, .18), (.04, .18), (.0, .175)], 40, M=Mt)        # 中心磁極
cyl(N, 'm_dark', (0, -.02, 0), .085, .03, 32, M=Mt)
box(N, 'm_mli', (-1.92, -.02, 0), (.16, .15, .3), .01)
cyl(N, 'm_alu', (-2.08, .08, .12), .012, .06, 10)                          # 陰極
# 氣瓶：本體內的長圓柱複材瓶
cyl(N, 'm_copv', (-1.55, 0, -.55), .12, .8, 32, r=(0, 0, PI / 2))
sphere(N, 'm_copv', (-1.95, 0, -.55), .12, 32, 16)
sphere(N, 'm_copv', (-1.15, 0, -.55), .12, 32, 16)
for k in range(5):
    cyl(N, 'm_alu', (-1.85 + k * .15, 0, -.55), .123, .012, 32, r=(0, 0, PI / 2))
tube(N, 'm_alu', [(-1.95, 0, -.55), (-2.0, -.01, -.3), (-1.98, -.02, -.1)], .011, 6)

# ============ s8_rad：上蓋一端的散熱面（跟上蓋一起掀） ============
N = 's8_rad'
box(N, 'm_rad', (-1.3, .114, 0), (1.2, .01, 2.2), .003)
for i in range(9):
    box(N, 'm_edge', (-1.82 + i * .13, .121, 0), (.016, .006, 2.1), .002)

# ============ D2C：手機直連衛星（p73） ============
N = 'd2c'
box(N, 'm_deck', (0, 0, 0), (1.6, .22, 1.0), .03, 2, uvp=('y', .5, .5))
box(N, 'm_edge', (0, .116, 0), (1.62, .01, 1.02), .004)
for i in range(4):
    box(N, 'm_alu', (-.6 + i * .4, .123, 0), (.012, .006, .98))
# 大天線板：銀色框格＋陣列面
grid_plane(N, 'm_d2c_ant', (-2.9, .027, 0), 3.6, 2.6, 2, 1)
grid_plane(N, 'm_array', (-2.9, -.027, 0), 3.6, 2.6, 4, 3, r=(PI, 0, 0))   # 朝地面那面是陣列
box(N, 'm_dark', (-2.9, 0, 0), (3.6, .05, 2.6), .012)
for i in range(7):
    box(N, 'm_alu', (-4.7 + i * .6, .034, 0), (.022, .016, 2.6), .004)
for j in range(5):
    box(N, 'm_alu', (-2.9, .034, -1.3 + j * .65), (3.6, .016, .022), .004)
for zz in (.2, -.2):
    rod(N, 'm_alu', (-.8, 0, zz), (-1.1, 0, zz), .035, 12)
# 頂上一個銀色碟（p73 左側）
lathe(N, 'm_dish', [(0, .14), (.06, .135), (.12, .11), (.15, .06), (.16, 0)], 32, M=TR((-.55, .11, .3)))
# 兩片太陽翼：p73 一片往上、一片往下，各用菱形桁架接在本體兩端
for sz, xo in ((1, .35), (-1, -.35)):
    grid_plane(N, 'm_cell', (xo, .011, sz * 4.5), 1.9, 6, 1, 3)
    box(N, 'm_cellback', (xo, 0, sz * 4.5), (1.9, .02, 6), .004)
    for xx in (xo - .95, xo + .95):
        box(N, 'm_alu', (xx, 0, sz * 4.5), (.03, .03, 6), .005)
    box(N, 'm_edge', (xo, 0, sz * 1.5), (1.95, .045, .05), .01)
    a1, a2, tip1, tip2 = (xo - .2, 0, sz * .5), (xo + .2, 0, sz * .5), (xo - .25, 0, sz * 1.5), (xo + .25, 0, sz * 1.5)
    mid1, mid2 = (xo, .12, sz * 1.0), (xo, -.12, sz * 1.0)
    for p, q in [(a1, mid1), (a2, mid1), (a1, mid2), (a2, mid2), (mid1, tip1), (mid1, tip2), (mid2, tip1), (mid2, tip2)]:
        rod(N, 'm_alu', p, q, .02, 8)

# ============ 用戶終端（p69 標準碟）：四層＋支架＋路由器＋組好的整台 ============
box('ut_l0', 'm_ut_white', (0, 0, 0), (1.0, .05, .64), .02, 3)
box('ut_l1', 'm_pcb', (0, 0, 0), (.98, .025, .62), .006, uvp=('y', 1, .65))
box('ut_l2', 'm_ut_rf', (0, 0, 0), (.98, .025, .62), .006)
for a in range(5):
    for c in range(3):
        box('ut_l2', 'm_chip', (-.36 + a * .18, .02, -.18 + c * .18), (.1, .02, .1), .005)
        box('ut_l2', 'm_copper', (-.36 + a * .18, .031, -.18 + c * .18), (.06, .003, .06))
box('ut_l3', 'm_ut_grey', (0, 0, 0), (1.0, .06, .64), .025, 3)
for k in range(5):
    box('ut_l3', 'm_ut_grey', (-.36 + k * .18, -.035, 0), (.02, .02, .56), .005)
cyl('ut_l3', 'm_dark', (0, -.06, .02), .05, .06, 20)
# 支架：直桿＋底座（p69 是深灰金屬桿）
cyl('ut_mast', 'm_ut_grey', (0, .47, 0), .022, .94, 20)
box('ut_mast', 'm_dark', (0, .02, 0), (.46, .04, .34), .015, 2)
box('ut_mast', 'm_ut_grey', (0, .93, -.05), (.05, .26, .05), .01, r=(-.6, 0, 0))
box('ut_router', 'm_ut_white', (1.25, .2, .7), (.24, .4, .09), .03, 3)
box('ut_router', 'm_dark', (.78, .04, .85), (.2, .08, .12), .015)
# 組好的整台
box('ut_dish', 'm_ut_white', (0, .03, 0), (1.0, .06, .64), .025, 3)
box('ut_dish', 'm_ut_grey', (0, -.03, 0), (.96, .05, .6), .02, 2)
cyl('ut_dish', 'm_dark', (0, -.07, .02), .05, .06, 20)

# ============ 閘道站（p51）：雷達罩、平台、機房 ============
N = 'gw'
Rd = 1.05
dome_prof = [(math.sin(t) * Rd, math.cos(t) * Rd) for t in np.linspace(0, 2.0, 18)]
for (x, z) in [(-3.6, 0), (0, -.3), (3.6, 0), (1.8, -3.6)]:
    box(N, 'm_alu', (x, .11, z), (2.3, .22, 2.3), .03, 2)
    box(N, 'm_concrete', (x, .005, z), (2.5, .01, 2.5))
    cyl(N, 'm_ut_grey', (x, .3, z), Rd * .86, .16, 40)
    cyl(N, 'm_radome', (x, .4, z), Rd * .78, .06, 40, cap=False)
    lathe(N, 'm_radome', dome_prof, 48, M=TR((x, .38 + Rd * .42, z)), sharp=80)
    for k in range(8):  # 平台四周欄杆柱
        a = k * PI / 4
        cyl(N, 'm_alu', (x + math.cos(a) * 1.05, .38, z + math.sin(a) * 1.05), .012, .3, 8)
box(N, 'm_panel', (-1.3, .55, 3.2), (2.8, 1.1, 1.4), .015, uvp=('z', 3, 1.2))
box(N, 'm_alu', (-1.3, 1.12, 3.2), (2.9, .05, 1.5), .01)
box(N, 'm_ut_grey', (-.6, 1.3, 3.1), (.9, .32, .7), .02)                 # 屋頂空調箱（p51）
for i in range(5):
    box(N, 'm_dark', (-.95 + i * .17, 1.3, 3.46), (.1, .2, .01))
box(N, 'm_dark', (-2.2, .42, 3.91), (.5, .84, .02), .005)                 # 門

# ============ 手機＋手機架 ============
mat('m_phone_frame', (.42, .43, .46), .95, .3)
mat('m_phone_back', (.035, .037, .042), .1, .28)
mat('m_screen', (0, 0, 0), .0, .15, emis=(1, 1, 1))     # 頁面會換上螢幕畫面
mat('m_stand', (.03, .032, .035), .2, .7)
PW, PHh, PT, PR = .0715, .1475, .0078, .0095
th = -.26
Mp = TR((0, .0782, -.0049), (th, 0, 0))
rr_prism('phone', 'm_phone_frame', PW, PHh, PT, PR, M=Mp, bev=.0011)
rr_prism('phone', 'm_phone_back', PW - .0012, PHh - .0012, .0008, PR - .0006, c=(0, 0, -PT / 2 - .0002), M=Mp)
rr_prism('phone', 'm_glass', PW - .0016, PHh - .0016, .0006, PR - .0008, c=(0, 0, PT / 2 + .0001), M=Mp)
grid_plane('phone', 'm_screen', (0, 0, PT / 2 + .00045), .064, .138, 1, 1, r=(PI / 2, 0, 0), M=Mp)
rr_prism('phone', 'm_black', .0125, .0036, .0003, .0018, c=(0, .0625, PT / 2 + .0007), M=Mp)
rr_prism('phone', 'm_phone_back', .031, .031, .0018, .0075, c=(.0165, .0545, -PT / 2 - .0012), M=Mp)
for lx, ly in ((.0225, .0605), (.0105, .0605), (.0165, .0485)):
    cyl('phone', 'm_edge', (lx, ly, -PT / 2 - .0026), .0058, .0016, 24, r=(PI / 2, 0, 0), M=Mp)
    cyl('phone', 'm_glass', (lx, ly, -PT / 2 - .0032), .0042, .0006, 24, r=(PI / 2, 0, 0), M=Mp)
box('phone', 'm_phone_frame', (PW / 2 + .0004, .028, 0), (.0012, .017, .0034), M=Mp)
for y in (.042, .028, .056):
    box('phone', 'm_phone_frame', (-PW / 2 - .0004, y, 0), (.0012, .0085 if y < .05 else .005, .0034), M=Mp)
# 手機架：底板＋前緣擋片＋背後斜撐
box('phone_stand', 'm_stand', (0, .003, -.012), (.078, .006, .075), .002)
box('phone_stand', 'm_stand', (0, .010, .021), (.078, .014, .007), .002)
box('phone_stand', 'm_stand', (0, .055, -.026), (.05, .1, .005), .002, r=(th, 0, 0))
box('phone_stand', 'm_stand', (0, .025, -.045), (.04, .05, .005), .002, r=(-.9, 0, 0))

# ---------------------------------------------------------------- 組節點、轉座標、匯出
GROUPS = {
    'SAT': ['s1_array', 's2_feeder', 's3_laser', 's4_pcb', 's5_struct', 's5_lid', 's6_power', 's7_avionics', 's8_prop', 's8_rad'],
    'D2C': ['d2c'], 'PHONE': ['phone', 'phone_stand'], 'UT': ['ut_l0', 'ut_l1', 'ut_l2', 'ut_l3', 'ut_mast', 'ut_router', 'ut_dish'], 'GW': ['gw'],
}
ctx = bpy.context
for root, nodes in GROUPS.items():
    emp = bpy.data.objects.new(root, None); COL.objects.link(emp)
    for nd in nodes:
        obs = PIECES[nd]
        for o in ctx.view_layer.objects: o.select_set(False)
        for o in obs: o.select_set(True)
        ctx.view_layer.objects.active = obs[0]
        if len(obs) > 1: bpy.ops.object.join()
        ob = ctx.view_layer.objects.active; ob.name = nd; ob.data.name = nd
        ob.data.transform(CONV)
        # 沒貼圖的網格拿掉 UV，省檔案
        if ob.data.uv_layers and not any(m.node_tree.nodes.get('Image Texture') or m.name in ('m_pcb', 'm_array', 'm_screen') for m in ob.data.materials):
            while ob.data.uv_layers: ob.data.uv_layers.remove(ob.data.uv_layers[0])
        if ob.data.uv_layers:                              # 指定作用中與算圖用的 UV，匯出器才不會寫出 texCoord -1
            ob.data.uv_layers.active_index = 0; ob.data.uv_layers[0].active_render = True
        ob.parent = emp

tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in SCN.objects if o.type == 'MESH')
print('TRIS', tris)
for o in SCN.objects:
    if o.type == 'MESH': print('NODE', o.name, sum(len(p.vertices) - 2 for p in o.data.polygons), len(o.data.materials))
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_image_format='JPEG', export_jpeg_quality=85,
                          export_yup=True, export_apply=False, export_vertex_color='NONE', export_draco_mesh_compression_enable=False,
                          export_materials='EXPORT', export_cameras=False, export_lights=False)
print('GLB', os.path.getsize(OUT))
