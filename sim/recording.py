"""Optional viewport-only recording; no desktop or webcam capture."""
from pathlib import Path
import shutil
import subprocess
import tempfile


class ViewportRecorder:
    def __init__(self, destination, fps=24):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("Viewport video requires ffmpeg")
        self.destination = Path(destination).resolve()
        if self.destination.exists():
            raise FileExistsError(f"Recording already exists: {self.destination}")
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.frames = Path(tempfile.mkdtemp(prefix=".isaac-frames-", dir=self.destination.parent))
        self.count = 0
        self.fps = fps
        self.pending = []
        from omni.kit.viewport.utility import get_active_viewport
        self.viewport = get_active_viewport()
        if self.viewport is None:
            raise RuntimeError("No Isaac viewport is available to record")

    def capture(self):
        from omni.kit.viewport.utility import capture_viewport_to_file
        self.pending.append(capture_viewport_to_file(
            self.viewport, str(self.frames / f"{self.count:06d}.png")))
        self.count += 1

    def finish(self):
        import omni.renderer_capture
        omni.renderer_capture.acquire_renderer_capture_interface().wait_async_capture()
        missing = [i for i in range(self.count) if not (self.frames / f"{i:06d}.png").is_file()]
        if self.count < 2 or missing:
            raise RuntimeError(f"Incomplete viewport recording ({self.count} requested, {len(missing)} missing)")
        temporary = self.destination.with_name(self.destination.stem + ".partial.mp4")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
                   "-framerate", str(self.fps), "-i", str(self.frames / "%06d.png"),
                   "-vf", "scale=1280:-2", "-c:v", "libx264", "-preset", "fast",
                   "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                   str(temporary)]
        try:
            subprocess.run(command, check=True, timeout=120, capture_output=True)
            temporary.replace(self.destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        self.close()
        return self.count

    def close(self):
        shutil.rmtree(self.frames, ignore_errors=True)
        self.pending.clear()
