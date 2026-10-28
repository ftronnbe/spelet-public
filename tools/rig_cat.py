"""Rig the static Meshy cat (assets/meshy/cat.glb, no skeleton) procedurally and render a walk cycle, a stand and a sit pose
to 8-direction sprites with the same camera, lights and framing as tools/render_sprites.py.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P tools/rig_cat.py -- [--out art/sprites_cat] [--size 192] [--frames 8]
    .venv/bin/python tools/pack_cat.py

Rig: a body bone (pivot at the hips), a head, four legs (upper + lower) and a three-bone tail. Weights come from the rest
geometry (the model faces -Y, legs are stubs under the body corners, the tail leaves the rump at y ~0.56): each region gets a
smooth falloff and the body takes the rest, so the many loose pieces Meshy produces move together and nothing tears.
Walk: a trot (diagonal pairs swing together), the paw lifted by the lower leg during the forward swing, the body dips so the
standing paws stay on the floor, the head counters the dip, the tail sways with a delay along the chain.

Output: <out>/cat/{walk_<dir>_<frame>,stand_<dir>_00,sit_<dir>_00}.png (dir 0..7 = S, SW, W, NW, N, NE, E, SE)
and <out>/cat/anchors.json: the projected top-of-head point per pose and direction (where the cat's hat sits).
Meshy's own auto-rigger was tried first (5 credits): it is humanoid-only and folds the cat into a biped.
"""
import argparse, json, math, os, sys

import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_sprites as rs      # same camera, lights and helpers as every other sprite

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))

def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=os.path.join(ROOT, "assets", "meshy", "cat.glb"))
    p.add_argument("--out", default=os.path.join(ROOT, "art", "sprites_cat"))
    p.add_argument("--size", type=int, default=192)
    p.add_argument("--frames", type=int, default=8)
    p.add_argument("--only", default="", help="comma list of poses to render (walk,stand,sit); default all")
    return p.parse_args(argv)

def ss(e0, e1, x):
    """Smoothstep from e0 (0) to e1 (1); works for e0 > e1 too."""
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)

# Rest-pose landmarks (model space, metres; cat faces -Y, feet at z = -0.746).
LEGS = {"leg_fl": (0.19, -0.415), "leg_fr": (-0.19, -0.415), "leg_hl": (0.215, 0.34), "leg_hr": (-0.215, 0.34)}
HIP_Z, KNEE_Z, FOOT_Z = -0.38, -0.60, -0.746
TAIL = [(0.0, 0.54, -0.06), (0.03, 0.66, -0.20), (0.13, 0.76, -0.34), (0.19, 0.93, -0.40)]

def weights(co):
    w = {}
    for name, (lx, ly) in LEGS.items():
        d = np.hypot(co[:, 0] - lx, co[:, 1] - ly)
        leg = (1 - ss(0.13, 0.21, d)) * ss(-0.30, -0.48, co[:, 2])
        low = ss(-0.56, -0.66, co[:, 2])
        w[name + "_up"], w[name + "_lo"] = leg * (1 - low), leg * low
    w["head"] = ss(-0.15, -0.40, co[:, 1]) * ss(-0.34, -0.06, co[:, 2])
    tail = ss(0.53, 0.60, co[:, 1]) * (1 - ss(0.14, 0.24, np.abs(co[:, 0] - np.clip((co[:, 1] - 0.6) * 0.8, 0, 0.19))))
    s2, s3 = ss(0.62, 0.70, co[:, 1]), ss(0.73, 0.80, co[:, 1])
    w["tail1"], w["tail2"], w["tail3"] = tail * (1 - s2), tail * s2 * (1 - s3), tail * s3
    total = sum(w.values())
    over = np.maximum(total, 1)
    for k in w: w[k] = w[k] / over
    w["body"] = 1 - sum(w.values())
    return w

def build(mesh):
    arm_data = bpy.data.armatures.new("cat_rig")
    arm = bpy.data.objects.new("cat_rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    def bone(name, h, t, parent=None, connect=False):
        b = eb.new(name); b.head, b.tail = Vector(h), Vector(t); b.roll = 0
        if parent: b.parent = eb[parent]; b.use_connect = connect
        return b
    bone("body", (0, 0.34, -0.55), (0, 0.34, -0.25))
    bone("head", (0, -0.35, -0.15), (0, -0.55, 0.40), "body")
    for name, (lx, ly) in LEGS.items():
        bone(name + "_up", (lx, ly, HIP_Z), (lx, ly, KNEE_Z), "body")
        bone(name + "_lo", (lx, ly, KNEE_Z), (lx, ly, FOOT_Z), name + "_up", True)
    for i in range(3):
        bone("tail%d" % (i + 1), TAIL[i], TAIL[i + 1], "body" if i == 0 else "tail%d" % i, i > 0)
    bpy.ops.object.mode_set(mode="OBJECT")
    co = np.array([v.co[:] for v in mesh.data.vertices])
    for name, wv in weights(co).items():
        g = mesh.vertex_groups.new(name=name)
        for i in np.nonzero(wv > 1e-3)[0]:
            g.add([int(i)], float(wv[i]), "REPLACE")
    mod = mesh.modifiers.new("rig", "ARMATURE"); mod.object = arm
    mesh.parent = arm
    for pb in arm.pose.bones: pb.rotation_mode = "QUATERNION"
    return arm

def rot(arm, name, axis, deg):
    """Rotate a pose bone about a model-space axis (composes with what is already set)."""
    pb = arm.pose.bones[name]
    local = (arm.data.bones[name].matrix_local.to_3x3().inverted() @ axis).normalized()
    pb.rotation_quaternion = Quaternion(local, math.radians(deg)) @ pb.rotation_quaternion

def move(arm, name, v):
    pb = arm.pose.bones[name]
    pb.location = arm.data.bones[name].matrix_local.to_3x3().inverted() @ Vector(v)

def pose(arm, kind, phase=0.0):
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0)
    if kind == "walk":
        a = 2 * math.pi * phase
        swing = 24.0                      # degrees; + about X sends the paw backwards (+Y)
        th = swing * math.sin(a)
        for name, sign in (("leg_fl", 1), ("leg_hr", 1), ("leg_fr", -1), ("leg_hl", -1)):
            rot(arm, name + "_up", X, sign * th)
            lift = max(0.0, -sign * math.cos(a))             # forward swing: paw up
            rot(arm, name + "_lo", X, 55 * lift if name.startswith("leg_f") else -40 * lift)
        leg = HIP_Z - FOOT_Z
        dip = -leg * (1 - math.cos(math.radians(th))) - 0.012 * (0.5 + 0.5 * math.cos(2 * a))
        move(arm, "body", (0, 0, dip))
        rot(arm, "body", Vector((0, 1, 0)), 2.0 * math.sin(a))          # a little roll onto the standing pair
        rot(arm, "head", X, -3.0 * math.cos(2 * a))                      # head counters the dip
        rot(arm, "head", Z, 2.5 * math.sin(a))
        for i, amp in enumerate((10, 14, 18)):
            rot(arm, "tail%d" % (i + 1), Z, amp * math.sin(a - 0.7 * (i + 1)))
            rot(arm, "tail%d" % (i + 1), X, -4 + 3 * math.sin(2 * a - 0.5 * i))
    elif kind == "sit":
        # The rump sinks about the front paws, the hind legs fold forward, the front legs stay upright, the tail curls round.
        tilt = -18.0
        pivot = Vector((0, -0.42, FOOT_Z)); body_head = Vector((0, 0.34, -0.55))
        q = Quaternion(X, math.radians(tilt))
        move(arm, "body", (q @ (body_head - pivot)) + pivot - body_head)
        rot(arm, "body", X, tilt)
        for n in ("leg_fl", "leg_fr"): rot(arm, n + "_up", X, -tilt)
        for n in ("leg_hl", "leg_hr"): rot(arm, n + "_up", X, -62); rot(arm, n + "_lo", X, 25)
        rot(arm, "head", X, 9)
        rot(arm, "tail1", X, 12); rot(arm, "tail1", Z, 45); rot(arm, "tail2", Z, 40); rot(arm, "tail2", X, 10); rot(arm, "tail3", Z, 40)
    bpy.context.view_layer.update()

def main():
    args = parse()
    rs.clear()
    objs = rs.import_model(args.model)
    mesh = next(o for o in objs if o.type == "MESH")
    arm = build(mesh)
    objs = [arm, mesh]
    jobs = [("walk", i / args.frames, i) for i in range(args.frames)] + [("stand", 0, 0), ("sit", 0, 0)]
    if args.only:
        keep = args.only.split(",")
        jobs = [j for j in jobs if j[0] in keep]

    # Framing: the rest pose decides scale and the floor line, exactly like the old static render (auto-fit) did;
    # every pose shares it, so the sheet has one scale and one baseline.
    pose(arm, "stand")
    pts = rs.eval_points([mesh])
    cx, cy = pts[:, :2].mean(axis=0)
    ground = float(pts[:, 2].min())
    rmax = float(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy).max())
    zmax = float(pts[:, 2].max()) - ground
    for kind, ph, _ in jobs:
        pose(arm, kind, ph)
        p = rs.eval_points([mesh])
        rmax = max(rmax, float(np.hypot(p[:, 0] - cx, p[:, 1] - cy).max()))
        zmax = max(zmax, float(p[:, 2].max()) - ground)
    c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    top, bottom = zmax * c30 + rmax * s30, -rmax * s30
    ortho = 2 * max((top - bottom) / 2, rmax) * 1.06
    print("FRAMING ortho=%.3f height=%.3f radius=%.3f" % (ortho, zmax, rmax))
    scene, cam = rs.setup_scene(args.size, ortho)
    cam.data.shift_y = ((top + bottom) / 2) / ortho
    pivot = bpy.data.objects.new("pivot", None)
    scene.collection.objects.link(pivot)
    arm.parent = pivot

    head_pts = np.array([v.co[:] for v in mesh.data.vertices])
    centre = head_pts[np.abs(head_pts[:, 0]) < 0.08]
    anchor_rest = Vector(centre[np.argmax(centre[:, 2])])           # top of the skull between the ears
    head_bone = arm.data.bones["head"]
    outdir = os.path.join(args.out, "cat")
    os.makedirs(outdir, exist_ok=True)
    anchors = {}
    for kind, ph, fi in jobs:
        rs.reset_pivot(pivot)
        pose(arm, kind, ph)
        for d in range(8):
            ang = math.radians(-360.0 * d / 8)
            pivot.rotation_euler[2] = ang
            pivot.location = (-(cx * math.cos(ang) - cy * math.sin(ang)), -(cx * math.sin(ang) + cy * math.cos(ang)), -ground)
            bpy.context.view_layer.update()
            pb = arm.pose.bones["head"]
            world = arm.matrix_world @ pb.matrix @ head_bone.matrix_local.inverted() @ anchor_rest
            uv = world_to_camera_view(scene, cam, world)
            anchors.setdefault(kind, {}).setdefault(str(fi), {})[str(d)] = [round(uv.x, 4), round(uv.y, 4)]
            scene.render.filepath = os.path.join(outdir, "%s_%d_%02d.png" % (kind, d, fi))
            bpy.ops.render.render(write_still=True)
        print("rendered", kind, fi)
    path = os.path.join(outdir, "anchors.json")
    old = json.load(open(path)) if os.path.exists(path) and args.only else {}
    old.update(anchors)
    json.dump(old, open(path, "w"), indent=0)

if __name__ == "__main__":      # tools/render_cat_hats.py imports the rig and poses from here
    main()
