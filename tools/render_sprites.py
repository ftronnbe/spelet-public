"""Render a rigged, animated 3D character to 8-direction sprite frames (the way Diablo II made its sprites).

Run inside Blender, not plain Python:

    blender --background --python tools/render_sprites.py -- \
        --model assets/models/Ranger.glb --name ranger --out art/sprites \
        --anims "Idle,Walking_A,Running_A,Ranged_Bow_Shoot" --size 256 --frames 8

    blender --background --python tools/render_sprites.py -- --test --out art/sprites   # built-in dummy figure

Output: <out>/<name>/<anim>_<dir>_<frame>.png  (transparent PNGs; dir 0..7 = S, SW, W, NW, N, NE, E, SE)
Animations named with --anims are matched case-insensitively as substrings of the action names found in the file;
run with --list to print every action in the model.
"""
import argparse, math, os, sys

import numpy as np

import bpy
from mathutils import Vector

DIRS = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]

def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--model")
    p.add_argument("--name", default="char")
    p.add_argument("--out", default="art/sprites")
    p.add_argument("--anims", default="", help="comma-separated substrings of action names to render")
    p.add_argument("--attach", default="", help="weapons to mount: comma-separated path:bone, e.g. bow.gltf:handslot.l,blade.gltf:handslot.r")
    p.add_argument("--anim-files", default="", help="comma-separated .glb/.fbx files holding extra animations on the same rig")
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--frames", type=int, default=8, help="frames sampled per animation")
    p.add_argument("--dirs", type=int, default=8)
    p.add_argument("--ortho", type=float, default=0, help="fixed frame size in world units (same scale for every character); 0 = auto-fit")
    p.add_argument("--shift", type=float, default=0.38, help="vertical lens shift (fraction of frame) when --ortho is fixed; larger moves the model lower")
    p.add_argument("--scale", type=float, default=1.0, help="model scale multiplier")
    p.add_argument("--list", action="store_true")
    p.add_argument("--test", action="store_true")
    return p.parse_args(argv)

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def import_model(path):
    before = set(bpy.data.objects)
    if path.lower().endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise SystemExit("unsupported model format: " + path)
    return [o for o in bpy.data.objects if o not in before]

def import_animations(paths):
    """Import animation-only files; keep their actions, delete the throwaway rigs they came with."""
    names = []
    for path in [p for p in paths.split(",") if p.strip()]:
        before_actions = set(bpy.data.actions)
        objs = import_model(path.strip())
        for a in set(bpy.data.actions) - before_actions:
            a.use_fake_user = True
            names.append(a.name)
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)
    return names

def attach_weapons(objs, spec):
    """Glue each weapon model to a hand bone (a Copy Transforms constraint follows the bone every frame)."""
    arm = next(o for o in objs if o.type == "ARMATURE")
    for item in [i for i in spec.split(",") if i.strip()]:
        path, bone = item.rsplit(":", 1)
        new = import_model(path.strip())
        for o in new:
            if o.parent is None:
                c = o.constraints.new("COPY_TRANSFORMS")
                c.target, c.subtarget = arm, bone.strip()
        objs.extend(new)

def build_test_figure():
    """A tiny jointed dummy so the pipeline can be checked without downloading anything."""
    objs = []
    def add(kind, loc, scale, color):
        getattr(bpy.ops.mesh, kind)()
        o = bpy.context.active_object
        o.location, o.scale = loc, scale
        m = bpy.data.materials.new("m"); m.diffuse_color = color
        o.data.materials.append(m)
        objs.append(o)
        return o
    add("primitive_cube_add", (0, 0, 0.9), (0.28, 0.18, 0.5), (0.5, 0.3, 0.2, 1))
    head = add("primitive_uv_sphere_add", (0, 0, 1.7), (0.2, 0.2, 0.2), (0.8, 0.6, 0.45, 1))
    add("primitive_cube_add", (0.45, 0, 1.0), (0.45, 0.04, 0.04), (0.6, 0.5, 0.3, 1))      # "bow"
    legs = [add("primitive_cube_add", (0, y, 0.25), (0.1, 0.08, 0.3), (0.25, 0.2, 0.2, 1)) for y in (-0.12, 0.12)]
    for i, leg in enumerate(legs):
        leg.animation_data_create()
        act = bpy.data.actions.new("Walk_test")
        leg.animation_data.action = act
        for f, ang in ((1, 0.5), (5, -0.5), (9, 0.5)):
            leg.rotation_euler[1] = ang * (1 if i == 0 else -1)
            leg.keyframe_insert("rotation_euler", index=1, frame=f)
    return objs

def collect_actions(objs):
    return sorted({a.name for a in bpy.data.actions})

def bounds(objs):
    pts = []
    for o in objs:
        if o.type == "MESH":
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi

def setup_scene(size, ortho_scale):
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else ("BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "CYCLES")
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = size
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 24
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"

    # Dark moody world: low ambient, slightly cool.
    world = bpy.data.worlds.new("w"); scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.10, 0.11, 0.16, 1)
    bg.inputs[1].default_value = 0.8

    # 2:1 dimetric camera: elevation 30 degrees, looking along +Y rotated into the screen.
    cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    elev = math.radians(30)
    dist = 20
    cam.location = (0, -dist * math.cos(elev), dist * math.sin(elev))
    cam.rotation_euler = (math.radians(90) - elev, 0, 0)
    scene.camera = cam

    def sun(name, rot, energy, color):
        d = bpy.data.lights.new(name, "SUN"); d.energy = energy; d.color = color
        o = bpy.data.objects.new(name, d); o.rotation_euler = rot
        scene.collection.objects.link(o)
    sun("key", (math.radians(50), math.radians(10), math.radians(-35)), 3.2, (1.0, 0.82, 0.6))     # warm torch, upper left
    sun("rim", (math.radians(60), 0, math.radians(150)), 1.6, (0.45, 0.55, 1.0))                   # cool back light
    return scene, cam

def pick_jobs(args):
    """--anims tokens: "Walking_A" (substring), "=Walking_A" (exact), optional ":N" frame count, e.g. "=Idle_A:4"."""
    tokens = []
    for raw in [w.strip() for w in args.anims.split(",") if w.strip()]:
        name, _, fr = raw.partition(":")
        tokens.append((name.lstrip("=").lower(), name.startswith("="), int(fr) if fr else args.frames))
    jobs = []
    for a in bpy.data.actions:
        if not tokens:
            jobs.append((a, args.frames)); continue
        for name, exact, fr in tokens:
            if (a.name.lower() == name) if exact else (name in a.name.lower()):
                jobs.append((a, fr)); break
    return jobs or [(None, 1)]     # static pose when nothing matches

def activate(act, armatures):
    """Assign an action to the character's rig and return its (first, last) frame."""
    if act and armatures:
        ad = armatures[0].animation_data_create()
        ad.action = act
        if hasattr(ad, "action_slot") and getattr(act, "slots", None):
            ad.action_slot = act.slots[0]
    if act:
        return int(act.frame_range[0]), int(act.frame_range[1])
    return 1, 1

def sample(f0, f1, n):
    return [f0] if f1 <= f0 or n <= 1 else [f0 + (f1 - f0) * i / n for i in range(n)]

def eval_points(objs):
    """World-space vertices of every mesh at the current frame, as an Nx3 numpy array."""
    dg = bpy.context.evaluated_depsgraph_get()
    chunks = []
    for o in objs:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        m = np.array(ev.matrix_world, dtype=np.float32)
        co = co.reshape(-1, 3)
        chunks.append(co @ m[:3, :3].T + m[:3, 3])
        ev.to_mesh_clear()
    return np.concatenate(chunks)

def measure(objs, jobs, armatures):
    """Largest posed extents over every sampled frame, measured around each frame's own centre
    (so root motion and falling-over death poses do not blow up the framing): (min z, max z, max radius)."""
    scene = bpy.context.scene
    zmin, zmax, rmax = 0.0, 0.0, 0.0
    for act, n in jobs:
        a_r, a_z = 0.0, 0.0
        f0, f1 = activate(act, armatures)
        per_frame = []
        for f in sample(f0, f1, n):
            scene.frame_set(int(f), subframe=f - int(f))
            pts = eval_points(objs)
            c = pts[:, :2].mean(axis=0)
            per_frame.append((float(np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1]).max()), float(pts[:, 2].min()), float(pts[:, 2].max())))
        ground = min(z0 for _, z0, _ in per_frame)
        for r, z0, z1 in per_frame:
            zmax, rmax = max(zmax, z1 - ground), max(rmax, r)
            a_r, a_z = max(a_r, r), max(a_z, z1 - ground)
        print("  extents %-36s height=%.2f radius=%.2f" % (act.name if act else "static", a_z, a_r))
    return zmin, zmax, rmax

def reset_pivot(pivot):
    pivot.location = (0, 0, 0)
    pivot.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

def render_all(objs, args):
    armatures = [o for o in objs if o.type == "ARMATURE"]
    jobs = pick_jobs(args)
    bpy.context.view_layer.update()
    zmin, zmax, rmax = measure(objs, jobs, armatures)
    c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    top = zmax * c30 + rmax * s30
    bottom = zmin * c30 - rmax * s30
    if args.ortho > 0:
        ortho = args.ortho
        shift = args.shift     # same framing for every character so relative scale is preserved
        fits = top <= 0.88 * ortho and rmax <= 0.5 * ortho
    else:
        ortho = 2 * max((top - bottom) / 2, rmax) * 1.06
        shift = ((top + bottom) / 2) / ortho
        fits = True
    print("EXTENTS %s: height=%.2f radius=%.2f ortho=%.2f%s" % (args.name, zmax - zmin, rmax, ortho, "" if fits else "  ** CLIPPED: raise --ortho"))
    scene, cam = setup_scene(args.size, ortho)
    cam.data.shift_y = shift
    # Rotate the model about the feet (world origin) for each of the 8 directions.
    pivot = bpy.data.objects.new("pivot", None)
    scene.collection.objects.link(pivot)
    for o in objs:
        if o.parent is None:
            o.parent = pivot
    outdir = os.path.join(args.out, args.name)
    os.makedirs(outdir, exist_ok=True)
    for act, nframes in jobs:
        label = act.name if act else "static"
        f0, f1 = activate(act, armatures)
        frames = sample(f0, f1, nframes)
        # Ground anchor: the lowest point reached in this animation rests on the floor (models differ in where
        # their origin sits relative to the feet), while walking bob and hops inside the animation are preserved.
        ground = 1e9
        for frame in frames:
            scene.frame_set(int(frame), subframe=frame - int(frame))
            reset_pivot(pivot)
            ground = min(ground, float(eval_points(objs)[:, 2].min()))
        for fi, frame in enumerate(frames):
            scene.frame_set(int(frame), subframe=frame - int(frame))
            reset_pivot(pivot)                    # measure the un-rotated pose, not the previous direction's
            pts = eval_points(objs)
            cx, cy = pts[:, :2].mean(axis=0)      # keep the model centred on the pivot (cancels root motion)
            for d in range(args.dirs):
                ang = math.radians(-360.0 * d / args.dirs)
                pivot.rotation_euler[2] = ang
                pivot.location = (-(cx * math.cos(ang) - cy * math.sin(ang)), -(cx * math.sin(ang) + cy * math.cos(ang)), -ground)
                scene.render.filepath = os.path.join(outdir, "%s_%d_%02d.png" % (label.replace(" ", "_"), d, fi))
                bpy.ops.render.render(write_still=True)
        print("rendered", label, "->", len(frames), "frames x", args.dirs, "dirs")

def main():
    args = parse()
    clear()
    if args.test:
        objs = build_test_figure()
        args.name = "test_figure"
        args.anims = "walk"
    else:
        if not args.model:
            raise SystemExit("--model is required (or use --test)")
        objs = import_model(args.model)
        if args.anim_files:
            import_animations(args.anim_files)
        if args.attach.strip():
            attach_weapons(objs, args.attach)
    if args.scale != 1.0:
        for o in objs:
            if o.parent is None:
                o.scale *= args.scale
    bpy.context.view_layer.update()
    if args.list:
        for a in collect_actions(objs):
            print("ACTION:", a)
        return
    render_all(objs, args)

if __name__ == "__main__":
    main()
