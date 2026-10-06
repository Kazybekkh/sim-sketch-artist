#!/usr/bin/env python3
"""Persistent Isaac Sim worker: bounded strokes -> SO-101 -> measured pen trail."""
from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.jobs import atomic_write_json, claim_next_job, create_job, job_path, update_job


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "sim/config.yaml")
    parser.add_argument("--jobs-dir", type=Path, default=Path(os.environ.get("JOBS_DIR", ROOT / "jobs")))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--once", action="store_true", help="Exit after one queued job, or immediately if empty")
    parser.add_argument("--sample", nargs="?", const="builtin", help="Enqueue the built-in smile, or a supplied drawing JSON file")
    parser.add_argument("--mode", choices=("robot", "marker"), default="robot")
    parser.add_argument("--record", type=Path, help="Record this --once run's Isaac viewport to a new MP4 file")
    result = parser.parse_args()
    if result.record and not result.once:
        parser.error("--record requires --once so the recording has a bounded end")
    if result.record and result.record.exists():
        parser.error("--record output already exists; choose a new file")
    return result


def sample():
    outline = [[0.5 + 0.32 * math.cos(t), 0.47 + 0.37 * math.sin(t)]
               for t in [i * 2 * math.pi / 24 for i in range(25)]]
    smile = [[0.5 + 0.19 * math.cos(t), 0.56 + 0.12 * math.sin(t)]
             for t in [i * math.pi / 10 for i in range(11)]]
    return {"title": "SO-101 sample smile (no Astra)", "strokes": [outline,
        [[0.32, 0.36], [0.39, 0.36]], [[0.61, 0.36], [0.68, 0.36]], smile]}


def validate(job):
    if not isinstance(job.get("title"), str) or not 1 <= len(job["title"]) <= 120:
        raise ValueError("Invalid drawing title")
    if not isinstance(job.get("strokes"), list) or not 1 <= len(job["strokes"]) <= 40:
        raise ValueError("Expected 1–40 strokes")
    for stroke in job["strokes"]:
        if not isinstance(stroke, list) or not 2 <= len(stroke) <= 25:
            raise ValueError("Expected 2–25 points per stroke")
        for point in stroke:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Expected [x,y] points")
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
                raise ValueError("Coordinates must be finite numbers between zero and one")


def render_result(strokes, destination):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (1600, 1600), "#fffef9")
    draw = ImageDraw.Draw(image)
    for stroke in strokes:
        if len(stroke) >= 2:
            draw.line([(x * 1599, y * 1599) for x, y in stroke], fill="#202322", width=5, joint="curve")
    image.resize((800, 800), Image.Resampling.LANCZOS).save(destination)


def main():
    args = arguments()
    args.jobs_dir = args.jobs_dir.resolve()
    args.jobs_dir.mkdir(parents=True, exist_ok=True)
    # A process lock supplements per-job atomic claims and prevents two simulators.
    lock = open(args.jobs_dir / ".sim-worker.lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("A simulator worker already owns this jobs directory.")
    config = json.loads(args.config.read_text())
    if args.sample:
        drawing = sample() if args.sample == "builtin" else json.loads(Path(args.sample).read_text())
        drawing = {key: drawing[key] for key in ("title", "strokes")}
        validate(drawing)
        print("SAMPLE_JOB=" + create_job(args.jobs_dir, drawing), flush=True)
    asset = ROOT / config["robot_asset"]
    if args.mode == "robot" and not asset.is_file():
        from sim.fetch_assets import fetch
        asset = fetch()

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": args.headless, "width": 1280, "height": 900,
                         "renderer": "RaytracedLighting", "anti_aliasing": 3})
    import numpy as np
    from pxr import Gf, UsdGeom, UsdLux, UsdPhysics, PhysxSchema
    from isaacsim.core.api import World
    from isaacsim.core.prims import SingleArticulation, SingleRigidPrim
    from isaacsim.core.utils.stage import add_reference_to_stage
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.viewports import set_camera_view
    from sim.kinematics import JOINT_NAMES, PenKinematics, quat_matrix

    world = World(stage_units_in_meters=1.0, physics_dt=config["physics_dt"], rendering_dt=1 / 60)
    recorder = None

    def simulation_step(render=True):
        world.step(render=render)
        if render and recorder is not None:
            recorder.capture()

    stage = world.stage
    center = np.asarray(config["page_center"], dtype=float)
    size = np.asarray(config["page_size"], dtype=float)
    tip_local = np.asarray(config["pen_tip_local"], dtype=float)
    root = config["robot_root"]

    def cube(path, location, scale, color):
        item = UsdGeom.Cube.Define(stage, path)
        item.CreateSizeAttr(1.0)
        item.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in location]))
        item.AddScaleOp().Set(Gf.Vec3d(*[float(v) for v in scale]))
        item.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        return item

    cube("/World/Table", [0, -.14, -.0125], [.64, .66, .025], [.075, .10, .14])
    cube("/World/DrawingPad", [*center[:2], (center[2] - .003) / 2],
         [size[0] + .008, size[1] + .008, center[2] - .003], [.14, .17, .21])
    cube("/World/Paper", [*center[:2], center[2] - .0015], [*size, .003], [.97, .96, .92])
    lamp = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
    lamp.CreateIntensityAttr(1100)
    sun = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
    sun.CreateIntensityAttr(1800)
    sun.AddRotateXYZOp().Set(Gf.Vec3f(30, -25, -25))
    set_camera_view(eye=np.array([.45, -.58, .50]), target=np.array([.0, -.17, .12]))

    robot = gripper = kinematics = None
    if args.mode == "robot":
        add_reference_to_stage(str(asset.resolve()), root)
        articulation = stage.GetPrimAtPath(root + "/root_joint")
        if not articulation.HasAPI(UsdPhysics.ArticulationRootAPI):
            raise RuntimeError("Downloaded SO-101 has no expected articulation root")
        PhysxSchema.PhysxArticulationAPI(articulation).CreateEnabledSelfCollisionsAttr(False)
        for prim in stage.Traverse():
            if str(prim.GetPath()).startswith(root) and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                PhysxSchema.PhysxRigidBodyAPI.Apply(prim).CreateDisableGravityAttr(True)
        for name in (*JOINT_NAMES, "gripper"):
            joint = stage.GetPrimAtPath(f"{root}/joints/{name}")
            drive = UsdPhysics.DriveAPI(joint, "angular")
            drive.GetMaxForceAttr().Set(50.0)
        robot = world.scene.add(SingleArticulation(prim_path=root + "/root_joint", name="sketch_arm"))
        gripper = world.scene.add(SingleRigidPrim(prim_path=root + "/gripper", name="pen_holder"))
        kinematics = PenKinematics(stage, root, tip_local)
        # The nib extends 45 mm beyond the asset's gripperframe.
        pen = UsdGeom.Cylinder.Define(stage, root + "/gripper/SketchPen")
        pen.CreateAxisAttr("Z")
        pen.CreateRadiusAttr(.003)
        pen.CreateHeightAttr(.09)
        pen.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in tip_local + [0, 0, .045]]))
        pen.CreateDisplayColorAttr([Gf.Vec3f(.08, .08, .10)])
        nib = UsdGeom.Sphere.Define(stage, root + "/gripper/PenNib")
        nib.CreateRadiusAttr(.002)
        nib.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in tip_local]))
        nib.CreateDisplayColorAttr([Gf.Vec3f(.04, .04, .04)])
    else:
        marker = UsdGeom.Sphere.Define(stage, "/World/ExplicitMarkerMode")
        marker.CreateRadiusAttr(.004)
        marker.CreateDisplayColorAttr([Gf.Vec3f(.9, .22, .08)])
        marker_transform = marker.AddTranslateOp()

    world.reset()
    if robot is not None:
        controller = robot.get_articulation_controller()
        controller.set_gains(kps=np.full(6, 400.0), kds=np.full(6, 20.0))
        indices = np.array([robot.get_dof_index(name) for name in JOINT_NAMES])
        q = kinematics.solve(center + [0, 0, config["pen_lift_m"]], np.zeros(5))
        pose = np.zeros(6)
        pose[indices] = q
        robot.set_joint_positions(pose)
        controller.apply_action(ArticulationAction(joint_positions=pose))
        for _ in range(30):
            simulation_step(render=True)
    else:
        q = np.zeros(5)

    def measured_tip():
        if gripper is None:
            return marker_position.copy()
        position, orientation = gripper.get_world_pose()
        return np.asarray(position) + quat_matrix(orientation) @ tip_local

    def world_point(point, lift=0):
        # Page origin is upper left. Image y increases toward the front edge.
        return np.array([center[0] + (point[0] - .5) * size[0],
                         center[1] + (.5 - point[1]) * size[1], center[2] + lift])

    def normalized(position):
        return [float((position[0] - center[0]) / size[0] + .5),
                float(.5 - (position[1] - center[1]) / size[1])]

    def move(target, *, record=None):
        nonlocal q, marker_position
        if robot is None:
            marker_position = np.asarray(target)
            marker_transform.Set(Gf.Vec3d(*[float(v) for v in target]))
            simulation_step(render=True)
        else:
            q = kinematics.solve(target, q)
            pose = np.zeros(6)
            pose[indices] = q
            controller.apply_action(ArticulationAction(joint_positions=pose))
            for step in range(config["max_settle_steps"]):
                simulation_step(render=step % config["substeps_per_point"] == 0)
                if not app.is_running():
                    raise InterruptedError("Simulator window closed")
                error = float(np.linalg.norm(measured_tip() - target))
                if record is not None:
                    intermediate = measured_tip()
                    if abs(intermediate[2] - center[2]) <= config["tracking_tolerance_m"]:
                        record.append(intermediate.copy())
                if step >= config["substeps_per_point"] and error <= config["tracking_tolerance_m"]:
                    break
            else:
                raise RuntimeError(f"SO-101 did not reach target; measured pen error {error:.4f} m")
        actual = measured_tip()
        if record is not None:
            if abs(actual[2] - center[2]) > config["tracking_tolerance_m"]:
                raise RuntimeError("Measured pen left the page while drawing")
            record.append(actual.copy())
        return actual

    def travel(target):
        origin = measured_tip()
        count = max(1, int(np.ceil(np.linalg.norm(target - origin) / .006)))
        for alpha in np.linspace(0, 1, count + 1)[1:]:
            move(origin * (1 - alpha) + target * alpha)

    def ink_curve(index, points):
        curve = UsdGeom.BasisCurves.Define(stage, f"/World/Ink/Stroke_{index:03}")
        curve.CreateTypeAttr("linear")
        curve.CreateWrapAttr("nonperiodic")
        curve.CreateCurveVertexCountsAttr([len(points)])
        curve.CreatePointsAttr([Gf.Vec3f(float(p[0]), float(p[1]), float(center[2] + .0005)) for p in points])
        curve.CreateWidthsAttr([.00065])
        curve.SetWidthsInterpolation("constant")
        curve.CreateDisplayColorAttr([Gf.Vec3f(.018, .026, .036)])

    marker_position = center + [0, 0, config["pen_lift_m"]]
    print(f"SIM_READY mode={args.mode} jobs={args.jobs_dir}", flush=True)
    current_job = None
    had_error = False
    try:
        while app.is_running():
            current_job = claim_next_job(args.jobs_dir)
            if current_job is None:
                if args.once:
                    break
                simulation_step(render=True)
                time.sleep(.02)
                continue
            job_id = current_job["job_id"]
            destination = job_path(args.jobs_dir, job_id)
            started = time.monotonic()
            try:
                validate(current_job)
                if args.record:
                    from sim.recording import ViewportRecorder
                    recorder = ViewportRecorder(args.record)
                stage.RemovePrim("/World/Ink")
                trails = []
                world_trails = []
                for index, stroke in enumerate(current_job["strokes"]):
                    travel(measured_tip() + [0, 0, config["pen_lift_m"]])
                    travel(world_point(stroke[0], config["pen_lift_m"]))
                    travel(world_point(stroke[0]))
                    actual_points = []
                    move(world_point(stroke[0]), record=actual_points)
                    for start, finish in zip(stroke, stroke[1:]):
                        a, b = world_point(start), world_point(finish)
                        count = max(1, int(np.ceil(np.linalg.norm(b - a) / config["path_spacing_m"])))
                        for alpha in np.linspace(0, 1, count + 1)[1:]:
                            move(a * (1 - alpha) + b * alpha, record=actual_points)
                            if len(actual_points) >= 2:
                                ink_curve(index, actual_points)
                    world_trails.append([p.tolist() for p in actual_points])
                    trails.append([normalized(p) for p in actual_points])
                    atomic_write_json(destination / "trail.json", {"title": current_job["title"], "strokes": trails})
                    update_job(args.jobs_dir, job_id, stroke=index + 1)
                travel(measured_tip() + [0, 0, config["pen_lift_m"]])
                render_result(trails, destination / "result.png")
                atomic_write_json(destination / "execution.json", {
                    "mode": args.mode, "engine": "Isaac Sim PhysX", "robot": "SO-101" if robot else None,
                    "measured_tip_world": world_trails, "duration_s": time.monotonic() - started,
                    "tracking_tolerance_m": config["tracking_tolerance_m"],
                })
                try:
                    from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport
                    capture_viewport_to_file(get_active_viewport(), str(destination / "scene.png"))
                    for _ in range(15):
                        simulation_step(render=True)
                except Exception as capture_error:
                    print(f"Scene capture unavailable: {capture_error}", flush=True)
                if recorder is not None:
                    finished_recorder, recorder = recorder, None
                    for _ in range(10):
                        simulation_step(render=True)
                    try:
                        frames = finished_recorder.finish()
                        print(f"VIDEO_DONE {args.record.resolve()} frames={frames}", flush=True)
                    finally:
                        finished_recorder.close()
                update_job(args.jobs_dir, job_id, status="done")
                print(f"JOB_DONE {job_id} mode={args.mode} result={destination / 'result.png'}", flush=True)
            except Exception as error:
                if recorder is not None:
                    recorder.close()
                    recorder = None
                had_error = True
                update_job(args.jobs_dir, job_id, status="error", error=str(error))
                print(f"JOB_ERROR {job_id}: {error}", file=sys.stderr, flush=True)
            current_job = None
            if args.once:
                break
    except KeyboardInterrupt:
        if current_job:
            update_job(args.jobs_dir, current_job["job_id"], status="error", error="Simulator worker interrupted")
    finally:
        app.close()
        lock.close()
    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
