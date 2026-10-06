"""Publish actual Isaac viewport frames without blocking the simulation queue.

Only the current LdrColor render buffer is captured. The bounded publisher never
substitutes the result image, an animation, or a previously recorded video.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
from pathlib import Path
import time

from backend.jobs import atomic_write_json


class LiveViewport:
    def __init__(self, jobs_dir, *, mode, fps=5, width=960, quality=75):
        from omni.kit.viewport.utility import get_active_viewport

        self.viewport = get_active_viewport()
        if self.viewport is None:
            raise RuntimeError("No Isaac viewport is available for live capture")
        self.directory = Path(jobs_dir) / ".live"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.interval = 1 / fps
        self.width = width
        self.quality = quality
        self.mode = mode
        self.frame_id = 0
        try:
            self.frame_id = int(json.loads((self.directory / "status.json").read_text())["frame_id"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="isaac-live-jpeg")
        self._capture = None
        self._encoding = None
        self._in_flight = False
        self._next_capture = 0.0
        self._closed = False
        self._state = {"state": "idle", "job_id": None, "stroke": 0, "total": 0, "error": None}

    def set_state(self, *, state, job_id=None, stroke=0, total=0, error=None):
        self._state = {"state": state, "job_id": job_id, "stroke": stroke,
                       "total": total, "error": str(error)[:1000] if error is not None else None}

    def tick(self):
        """Call after rendered simulation steps; at most one capture/encode exists."""
        if self._closed:
            return
        if self._encoding is not None and self._encoding.done():
            try:
                self._encoding.result()
            except Exception as error:
                print(f"LIVE_CAPTURE_ERROR {error}", flush=True)
            self._encoding = None
            self._capture = None
            self._in_flight = False
        now = time.monotonic()
        if self._in_flight or now < self._next_capture:
            return
        self._next_capture = now + self.interval
        self._in_flight = True
        state = dict(self._state)

        def captured(buffer, buffer_size, width, height, byte_format):
            try:
                if self._closed:
                    return
                # The callback owns this capsule only for its duration. Copy it
                # before offloading JPEG encoding; never retain the GPU buffer.
                if buffer_size != width * height * 4:
                    raise RuntimeError(f"Unexpected LdrColor buffer: {width}x{height}, {buffer_size} bytes")
                pointer = ctypes.pythonapi.PyCapsule_GetPointer
                pointer.restype = ctypes.c_void_p
                pointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
                raw = ctypes.string_at(pointer(buffer, None), buffer_size)
                self._encoding = self._executor.submit(self._publish, raw, width, height, state)
            except Exception as error:
                self._in_flight = False
                print(f"LIVE_CAPTURE_ERROR {error}", flush=True)

        try:
            from omni.kit.viewport.utility import capture_viewport_to_buffer
            self._capture = capture_viewport_to_buffer(self.viewport, captured)
        except Exception as error:
            self._in_flight = False
            print(f"LIVE_CAPTURE_ERROR {error}", flush=True)

    def _publish(self, raw, width, height, state):
        from PIL import Image

        frame = Image.frombytes("RGBA", (width, height), raw).convert("RGB")
        if frame.width > self.width:
            frame = frame.resize((self.width, round(frame.height * self.width / frame.width)), Image.Resampling.LANCZOS)
        temporary = self.directory / ".frame.partial.jpg"
        try:
            frame.save(temporary, format="JPEG", quality=self.quality)
            temporary.replace(self.directory / "frame.jpg")
        finally:
            temporary.unlink(missing_ok=True)
        self.frame_id += 1
        atomic_write_json(self.directory / "status.json", {
            **state, "mode": self.mode, "updated_at": time.time(), "frame_id": self.frame_id,
        })

    def close(self):
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
