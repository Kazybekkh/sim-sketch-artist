"""Bounded browser commands for the actual Isaac viewport camera.

The worker consumes the newest atomic command file before a rendered step. The
reported pose is read back from USD, so a command is acknowledged only after it
has changed the simulator camera.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from uuid import UUID


RENDER_RESOLUTION = (1280, 900)
DEFAULT_CAMERA = {
    "yaw": -0.7853981633974483,
    "pitch": 0.534842736717193,
    "distance": 0.6081940479813988,
    "target": [0.0, -0.17, 0.13],
}


def validate_camera_command(command):
    """Validate untrusted finite values and clamp to the camera's safe bounds."""
    if not isinstance(command, dict):
        raise ValueError("Camera command must be an object")
    if set(command) != {"command_id", "yaw", "pitch", "distance", "target"}:
        raise ValueError("Camera command has unexpected or missing fields")
    command_id = command["command_id"]
    if not isinstance(command_id, str) or len(command_id) != 36:
        raise ValueError("Camera command_id must be a UUID")
    try:
        if str(UUID(command_id)) != command_id.lower():
            raise ValueError("Camera command_id must be a UUID")
    except (ValueError, AttributeError) as error:
        raise ValueError("Camera command_id must be a UUID") from error

    def bounded(value, lower, upper):
        if type(value) not in (int, float):
            raise ValueError("Camera values must be finite numbers")
        try:
            number = float(value)
        except OverflowError as error:
            raise ValueError("Camera values must be finite numbers") from error
        if not math.isfinite(number):
            raise ValueError("Camera values must be finite numbers")
        return max(lower, min(upper, number))

    target = command["target"]
    if not isinstance(target, list) or len(target) != 3:
        raise ValueError("Camera target must be [x, y, z]")
    return {
        "command_id": command_id,
        "yaw": bounded(command["yaw"], -2 * math.pi, 2 * math.pi),
        "pitch": bounded(command["pitch"], 0.10, 1.55),
        "distance": bounded(command["distance"], 0.12, 1.5),
        "target": [bounded(target[0], -0.5, 0.5), bounded(target[1], -0.5, 0.5),
                   bounded(target[2], 0, 0.5)],
    }


def camera_eye(camera):
    radius = camera["distance"] * math.cos(camera["pitch"])
    return [camera["target"][0] + radius * math.cos(camera["yaw"]),
            camera["target"][1] + radius * math.sin(camera["yaw"]),
            camera["target"][2] + camera["distance"] * math.sin(camera["pitch"])]


class CameraController:
    def __init__(self, jobs_dir):
        from omni.kit.viewport.utility import get_active_viewport

        self.viewport = get_active_viewport()
        if self.viewport is None:
            raise RuntimeError("No Isaac viewport is available for camera control")
        self.command_path = Path(jobs_dir) / ".live" / "camera.json"
        self.command_id = None
        self._last_signature = None
        self._fix_resolution()
        self._apply(DEFAULT_CAMERA)

    def _fix_resolution(self):
        # fill_frame follows the native window size and may silently crop an
        # embedded video. Keep the GPU render product independent of that window.
        self.viewport.fill_frame = False
        self.viewport.resolution_scale = 1.0
        self.viewport.resolution = RENDER_RESOLUTION

    def _actual_pose(self):
        from omni.kit.viewport.utility.camera_state import ViewportCameraState

        state = ViewportCameraState(viewport=self.viewport)
        eye = [float(value) for value in state.position_world]
        target = [float(value) for value in state.target_world]
        return eye, target

    def _apply(self, camera):
        import numpy as np
        from isaacsim.core.utils.viewports import set_camera_view

        eye = camera_eye(camera)
        target = camera["target"]
        set_camera_view(eye=np.asarray(eye), target=np.asarray(target),
                        camera_prim_path=str(self.viewport.camera_path), viewport_api=self.viewport)
        actual_eye, actual_target = self._actual_pose()
        if any(abs(a - b) > 1e-5 for a, b in zip(actual_eye + actual_target, eye + target)):
            raise RuntimeError("Isaac camera did not reach the requested view")

    def poll(self):
        """Apply the most recent file at most once; malformed input cannot stop a job."""
        if (self.viewport.fill_frame or self.viewport.resolution_scale != 1.0
                or tuple(self.viewport.resolution) != RENDER_RESOLUTION):
            self._fix_resolution()
        try:
            info = self.command_path.stat()
            signature = (info.st_ino, info.st_mtime_ns, info.st_size)
            if signature == self._last_signature:
                return
            self._last_signature = signature
            with self.command_path.open("rb") as stream:
                content = stream.read(4097)
            if len(content) > 4096:
                raise ValueError("Camera command exceeds 4096 bytes")
            command = validate_camera_command(json.loads(content))
            if command["command_id"] == self.command_id:
                return
            self._apply(command)
            self.command_id = command["command_id"]
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError, RuntimeError) as error:
            print(f"CAMERA_COMMAND_REJECTED {error}", flush=True)

    def metadata(self):
        eye, target = self._actual_pose()
        offset = [a - b for a, b in zip(eye, target)]
        horizontal = math.hypot(offset[0], offset[1])
        return {
            "camera": {"yaw": math.atan2(offset[1], offset[0]),
                       "pitch": math.atan2(offset[2], horizontal),
                       "distance": math.hypot(horizontal, offset[2]), "target": target},
            "camera_command_id": self.command_id,
            "render_resolution": list(RENDER_RESOLUTION),
        }
