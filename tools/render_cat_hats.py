"""Render the cat's six hats as sprites that sit on the head of the cat from tools/rig_cat.py.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P tools/render_cat_hats.py -- [--hats assets/meshy/cathats.glb] [--only top,halo]
    .venv/bin/python tools/pack_cat_hats.py

The hats come from one Meshy prop sheet (assets/meshy/cathats_ref_0.png -> cathats.glb, six hats in a row, front facing -Y).
They are split by X like tools/fit_headgear.py, except the halo, which overlaps the wizard hat's brim in X: a circle is fitted
to its free left arc and every vertex near that circle is the halo. Each hat is scaled and placed on the cat's rest head
(numbers in SPECS, cat model units: the head is ~0.85 wide, the skull top is at z ~0.68, ear tips at x +-0.27, z 0.69),
weighted 100% to the cat's head bone, and rendered in the stand and sit poses from the cat's own camera and 8 directions
with the cat as a holdout: wherever the cat is in front of the hat (an ear, the back of the head) the hat is cut away,
so in game the hat sprite can simply be drawn over the cat.

Output: art/sprites_cat/hats/full/<hat>_<pose>_<dir>.png (the cat frame widened FRAME x, at 4x, hat only) and full/anchors.json (where the
head top is per pose and direction, plus WINDOW: anchor -+0.35 across, -0.2 .. +0.5 up, in cell units), which
tools/pack_cat_hats.py cuts into the sheet. --preview draws the cat too (into preview/) to check the fit.
"""
import argparse, math, os, sys

import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_sprites as rs
import rig_cat as rc

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HATS = ["top", "party", "crown", "bow", "halo", "wizard"]      # CatAccessory.all order
WINDOW = (0.35, 0.2, 0.5)                                      # half width, below, above the head anchor (cell units)
CELL = 128
FRAME = 1.5                                                    # rendered view / cat cell (room for tall hats)
SCALE = 4                                                      # render at 4x the cat's 192 px frame, then cut the window
# hat: (width in cat units, centre x, centre y, bottom z, tilt about Y (deg), tilt about X, turn about Z[, extra height stretch[, extra depth stretch]])
SPECS = {      # well larger than life: the cat is ~24 pt tall on screen and the hat has to read at that size
    "top":    (0.92, 0.02, -0.62, 0.63, -9, 0, 8),
    "party":  (0.70, -0.04, -0.62, 0.64, 13, -4, -20, 1.2),
    "crown":  (0.84, 0.0, -0.62, 0.59, -5, 3, 0),
    "bow":    (0.80, 0.27, -0.64, 0.52, -24, 0, 38, 1.0, 2.6),   # turned and made deeper so it never shows only a thin edge
    "halo":   (0.80, 0.0, -0.64, 0.99, 5, -4, 0),
    "wizard": (1.12, 0.0, -0.62, 0.67, 6, 0, 60, 1.7),  # the bent tip points sideways-back; stretched up so the cone reads
}

def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--hats", default=os.path.join(ROOT, "assets", "meshy", "cathats.glb"))
    p.add_argument("--out", default=os.path.join(ROOT, "art", "sprites_cat", "hats"))
    p.add_argument("--only", default="")
    p.add_argument("--poses", default="stand,sit")
    p.add_argument("--preview", action="store_true", help="draw the cat too (to check the fit), into <out>/preview")
    return p.parse_args(argv)

def fit_circle(pts):
    """Plane + circle through 3D points: (centre, normal, radius)."""
    c0 = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c0)
    u, v, n = vt[0], vt[1], vt[2]
    a, b = (pts - c0) @ u, (pts - c0) @ v
    A = np.c_[2 * a, 2 * b, np.ones(len(a))]
    sol = np.linalg.lstsq(A, a * a + b * b, rcond=None)[0]
    centre = c0 + sol[0] * u + sol[1] * v
    return centre, n, math.sqrt(sol[2] + sol[0] ** 2 + sol[1] ** 2)

def ring_dist(pts, centre, n, r):
    d = pts - centre
    h = d @ n
    radial = np.linalg.norm(d - np.outer(h, n), axis=1)
    return np.hypot(radial - r, h)

def split(path):
    """The prop-sheet model -> {hat: mesh object}, each centred on x/y with its bottom at z 0 and normalised orientation."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    src = next(o for o in bpy.data.objects if o not in before and o.type == "MESH")
    src.data.transform(src.matrix_world); src.matrix_world = Matrix()
    co = np.array([v.co[:] for v in src.data.vertices])
    x, z = co[:, 0], co[:, 2]
    arc = co[(x > 0.36) & (x < 0.50) & (z > -0.12) & (z < 0.16)]
    centre, n, r = fit_circle(arc)
    res = ring_dist(arc, centre, n, r)
    rd = ring_dist(co, centre, n, r)
    tol = max(0.025, 3 * float(np.median(res)))
    halo = (x > 0.30) & (rd < tol)
    gap = (x > 0.30) & (rd >= tol) & (rd < tol + 0.025)         # a no-man's band: neither halo nor wizard hat
    print("HALO centre %s normal %s r %.3f, %d verts" % (np.round(centre, 3), np.round(n, 3), r, halo.sum()))
    pom = (x > -0.31) & (x < -0.20) & (z > 0.11)
    label = np.full(len(co), -1)
    label[x < -0.591] = 0
    label[(x >= -0.591) & (x < -0.27)] = 1
    label[(x >= -0.27) & (x < -0.004)] = 2
    label[pom] = 1
    label[(x >= -0.004) & (x < 0.319)] = 3
    label[x >= 0.319] = 5
    label[halo] = 4
    label[gap] = -1
    out = {}
    for i, name in enumerate(HATS):
        obj = src.copy(); obj.data = src.data.copy(); obj.name = "hat_" + name
        bpy.context.scene.collection.objects.link(obj)
        bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if label[v.index] != i], context="VERTS")
        bm.to_mesh(obj.data); bm.free()
        if name == "halo":     # lay the ring flat: its normal becomes +Z
            nz = Vector(n if n[2] >= 0 else -n)
            obj.data.transform(nz.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4())
        vs = np.array([v.co[:] for v in obj.data.vertices])
        lo, hi = vs.min(axis=0), vs.max(axis=0)
        obj.data.transform(Matrix.Translation(Vector((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))))
        print("HAT %-6s %6d verts  size %s" % (name, len(vs), np.round(hi - lo, 3)))
        out[name] = obj
    for o in [o for o in bpy.data.objects if o not in before and o not in out.values()]:
        bpy.data.objects.remove(o, do_unlink=True)
    return out

def place(obj, arm, spec):
    w, cx, cy, bz, ty, tx, tz = spec[:7]
    stretch = spec[7] if len(spec) > 7 else 1.0
    deep = spec[8] if len(spec) > 8 else 1.0
    vs = np.array([v.co[:] for v in obj.data.vertices])
    k = w / (vs[:, 0].max() - vs[:, 0].min())
    m = (Matrix.Translation((cx, cy, bz)) @ Matrix.Rotation(math.radians(tz), 4, "Z") @ Matrix.Rotation(math.radians(tx), 4, "X")
         @ Matrix.Rotation(math.radians(ty), 4, "Y") @ Matrix.Diagonal((k, k * deep, k * stretch, 1)))
    obj.data.transform(m)
    g = obj.vertex_groups.new(name="head"); g.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.parent = arm
    mod = obj.modifiers.new("rig", "ARMATURE"); mod.object = arm

def main():
    args = parse()
    rs.clear()
    objs = rs.import_model(os.environ.get("CAT_GLB", os.path.join(ROOT, "assets", "meshy", "cat.glb")))
    mesh = next(o for o in objs if o.type == "MESH")
    arm = rc.build(mesh)
    # Framing: exactly as tools/rig_cat.py (rest pose + every pose's extents), so the anchors match anchors.json.
    frames = 8
    jobs = [("walk", i / frames, i) for i in range(frames)] + [("stand", 0, 0), ("sit", 0, 0)]
    rc.pose(arm, "stand")
    pts = rs.eval_points([mesh])
    cx, cy = pts[:, :2].mean(axis=0)
    ground = float(pts[:, 2].min())
    rmax = float(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy).max())
    zmax = float(pts[:, 2].max()) - ground
    for kind, ph, _ in jobs:
        rc.pose(arm, kind, ph)
        p = rs.eval_points([mesh])
        rmax = max(rmax, float(np.hypot(p[:, 0] - cx, p[:, 1] - cy).max()))
        zmax = max(zmax, float(p[:, 2].max()) - ground)
    c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    top, bottom = zmax * c30 + rmax * s30, -rmax * s30
    ortho = 2 * max((top - bottom) / 2, rmax) * 1.06
    size = 192 * SCALE
    # The big hats stick out above the cat's own frame: render a FRAME x larger view around the same centre, so
    # cat-cell coordinates u map to 0.5 + (u - 0.5) / FRAME of this image (the anchors below stay in cat-cell units).
    scene, cam = rs.setup_scene(int(size * FRAME), ortho * FRAME)
    cam.data.shift_y = ((top + bottom) / 2) / ortho / FRAME
    pivot = bpy.data.objects.new("pivot", None)
    scene.collection.objects.link(pivot)
    arm.parent = pivot
    mesh.is_holdout = not args.preview

    hats = split(args.hats)
    rc.pose(arm, "stand")                         # the rest pose: hats are placed on the rest head
    for name, obj in hats.items(): place(obj, arm, SPECS[name])
    only = [h for h in args.only.split(",") if h] or HATS

    head_pts = np.array([v.co[:] for v in mesh.data.vertices])
    centre = head_pts[np.abs(head_pts[:, 0]) < 0.08]
    anchor_rest = Vector(centre[np.argmax(centre[:, 2])])
    head_bone = arm.data.bones["head"]
    os.makedirs(args.out, exist_ok=True)
    boxes = {}
    full = os.path.join(args.out, "preview" if args.preview else "full")
    for kind in args.poses.split(","):
        rs.reset_pivot(pivot)
        rc.pose(arm, kind)
        for d in range(8):
            ang = math.radians(-360.0 * d / 8)
            pivot.rotation_euler[2] = ang
            pivot.location = (-(cx * math.cos(ang) - cy * math.sin(ang)), -(cx * math.sin(ang) + cy * math.cos(ang)), -ground)
            bpy.context.view_layer.update()
            world = arm.matrix_world @ arm.pose.bones["head"].matrix @ head_bone.matrix_local.inverted() @ anchor_rest
            uv = world_to_camera_view(scene, cam, world)
            boxes["%s_%d" % (kind, d)] = [round(0.5 + (uv.x - 0.5) * FRAME, 4), round(0.5 + (uv.y - 0.5) * FRAME, 4)]
            for name in only:
                for n2, o in hats.items(): o.hide_render = n2 != name
                scene.render.filepath = os.path.join(full, "%s_%s_%d.png" % (name, kind, d))
                bpy.ops.render.render(write_still=True)
        print("rendered", kind)
    import json
    json.dump({"size": size, "frame": FRAME, "window": WINDOW, "anchors": boxes}, open(os.path.join(full, "anchors.json"), "w"), indent=0)

main()
