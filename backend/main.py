"""Run with: uvicorn backend.main:app --host 127.0.0.1 --port 8000."""
from __future__ import annotations

import base64
import io
import math
import os
from pathlib import Path
import tempfile
import time
from uuid import UUID, uuid4
import warnings

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from backend.astra import AstraPortraits, PortraitError
from backend.camera import CameraPose
from backend.jobs import atomic_write_json, create_job, job_path, read_json, read_status
from backend.strokes import Drawing, render_preview

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
LIVE_MAX_AGE = 5
NO_CACHE = {"Cache-Control": "no-store, no-cache, max-age=0", "Pragma": "no-cache"}


def live_status(directory: Path) -> dict:
    """Only report a live camera when both its metadata and image are fresh."""
    result = {"updated_at": None, "frame_id": None, "state": "idle", "job_id": None,
              "stroke": 0, "total": 0, "mode": None, "error": None,
              "online": False, "frame_url": "/sim/frame",
              "camera": None, "camera_command_id": None}
    try:
        raw = read_json(directory / "status.json")
        if not isinstance(raw, dict):
            raise ValueError("invalid metadata")
        timestamp = raw["updated_at"]
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
            raise ValueError("invalid timestamp")
        if any(type(raw[key]) is not int or raw[key] < 0 for key in ("frame_id", "stroke", "total")):
            raise ValueError("invalid counters")
        if raw["stroke"] > raw["total"] or raw["state"] not in {"idle", "running", "error"}:
            raise ValueError("invalid state")
        if raw["mode"] not in {"robot", "marker"}:
            raise ValueError("invalid mode")
        if raw["job_id"] is not None and not isinstance(raw["job_id"], str):
            raise ValueError("invalid job")
        if raw["error"] is not None and not isinstance(raw["error"], str):
            raise ValueError("invalid error")
        result.update({key: raw[key] for key in ("updated_at", "frame_id", "state", "job_id", "stroke", "total", "mode", "error")})
        now = time.time()
        frame = (directory / "frame.jpg").stat()
        result["online"] = (0 <= now - timestamp <= LIVE_MAX_AGE
                            and 0 <= now - frame.st_mtime <= LIVE_MAX_AGE and frame.st_size > 0)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        result["error"] = "The simulator camera status is unavailable."
    # Camera metadata is optional for older workers.
    if result["online"]:
        try:
            result["camera"] = CameraPose.from_simulator(raw["camera"]).model_dump()
            command_id = raw.get("camera_command_id")
            if command_id is not None:
                result["camera_command_id"] = str(UUID(command_id))
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
    return result


def normalize_image(raw: bytes) -> str:
    """Decode, verify, strip metadata, and downsize entirely in memory."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(415, "Use a JPEG, PNG, or WebP image.")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "Image dimensions are too large. Use a photo under 25 megapixels.")
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source = ImageOps.exif_transpose(source)
                source.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
                if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
                    rgba = source.convert("RGBA")
                    normalized = Image.new("RGB", rgba.size, "white")
                    normalized.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    normalized = source.convert("RGB")
                output = io.BytesIO()
                normalized.save(output, format="JPEG", quality=88)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "This is not a valid JPEG, PNG, or WebP image.") from None
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def create_app(*, jobs_dir: str | Path | None = None, preview_dir: str | Path | None = None,
               portrait_service=None) -> FastAPI:
    app = FastAPI(title="Sim Sketch Artist", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])
    app.state.jobs_dir = Path(jobs_dir or os.getenv("JOBS_DIR") or ROOT / "jobs").resolve()
    app.state.preview_dir = Path(preview_dir or os.getenv("PREVIEWS_DIR") or ROOT / "previews").resolve()
    app.state.jobs_dir.mkdir(parents=True, exist_ok=True)
    app.state.preview_dir.mkdir(parents=True, exist_ok=True)
    app.state.portrait_service = portrait_service
    frontend = ROOT / "frontend" / "dist"

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, exc):
        # Exclude raw input: NaN/Infinity cannot be serialized in JSON errors,
        # and an upload should never be echoed back to the browser.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]})

    def path_for(job_id: str) -> Path:
        try:
            path = job_path(app.state.jobs_dir, job_id)
        except ValueError:
            raise HTTPException(404, "Job not found.") from None
        if not path.is_dir():
            raise HTTPException(404, "Job not found.")
        return path

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/ready")
    def ready():
        return {"ok": True,
                "astra_configured": bool(os.getenv("OPENAI_API_KEY", "").strip() and os.getenv("ASTRA_MODEL", "").strip()),
                "astra_model": os.getenv("ASTRA_MODEL", "").strip() or None,
                "frontend_built": (frontend / "index.html").is_file()}

    @app.get("/sim/status")
    def simulator_status():
        return JSONResponse(live_status(app.state.jobs_dir / ".live"), headers=NO_CACHE)

    @app.get("/sim/frame")
    def simulator_frame():
        directory = app.state.jobs_dir / ".live"
        if not live_status(directory)["online"]:
            return JSONResponse({"detail": "The simulator camera is offline or its last frame is stale."},
                                status_code=503, headers=NO_CACHE)
        try:
            # Read the atomic snapshot now, avoiding a FileResponse stat/open race.
            image = (directory / "frame.jpg").read_bytes()
        except OSError:
            return JSONResponse({"detail": "The simulator frame is temporarily unavailable."},
                                status_code=503, headers=NO_CACHE)
        return Response(image, media_type="image/jpeg", headers=NO_CACHE)

    @app.post("/sim/camera", status_code=202)
    def simulator_camera(camera: CameraPose):
        directory = app.state.jobs_dir / ".live"
        status = live_status(directory)
        if not status["online"] or status["camera"] is None:
            raise HTTPException(503, "The interactive simulator camera is unavailable.")
        command_id = str(uuid4())
        # One atomic file: newer camera gestures replace older pending poses.
        atomic_write_json(directory / "camera.json", {"command_id": command_id, **camera.model_dump()})
        return JSONResponse({"accepted": True, "command_id": command_id}, status_code=202, headers=NO_CACHE)

    @app.get("/sim/view", response_class=HTMLResponse)
    def simulator_view():
        index = frontend / "index.html"
        if not index.is_file():
            return HTMLResponse("Build the browser viewer with npm --prefix frontend run build.", status_code=503,
                                headers=NO_CACHE)
        return FileResponse(index, media_type="text/html",
                            headers={**NO_CACHE, "Content-Security-Policy": "frame-ancestors *"})

    @app.post("/portrait")
    async def portrait(image: UploadFile = File(...)):
        try:
            raw = await image.read(MAX_IMAGE_BYTES + 1)
        finally:
            await image.close()
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Photo must be 10 MB or smaller.")
        if not raw:
            raise HTTPException(400, "Choose a photo first.")
        image_data_url = await run_in_threadpool(normalize_image, raw)
        service = None
        owns_service = app.state.portrait_service is None
        try:
            service = app.state.portrait_service or AstraPortraits()
            drawing = await service.generate(image_data_url)
        except PortraitError as exc:
            raise HTTPException(exc.status_code, str(exc)) from None
        finally:
            if owns_service and service is not None:
                await service.client.close()
        preview_name = f"{uuid4()}.png"
        await run_in_threadpool(render_preview, drawing.strokes, app.state.preview_dir / preview_name)
        return {**drawing.model_dump(), "preview_url": f"/previews/{preview_name}"}

    @app.post("/draw", status_code=202)
    def draw(drawing: Drawing):
        return {"job_id": create_job(app.state.jobs_dir, drawing.model_dump())}

    @app.get("/status/{job_id}")
    @app.get("/jobs/{job_id}", include_in_schema=False)
    def status(job_id: str):
        path_for(job_id)
        try:
            value = read_status(app.state.jobs_dir, job_id)
        except (OSError, ValueError):
            raise HTTPException(503, "Job status is temporarily unavailable.") from None
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    @app.get("/trail/{job_id}")
    @app.get("/jobs/{job_id}/trail", include_in_schema=False)
    def trail(job_id: str):
        path = path_for(job_id) / "trail.json"
        if not path.is_file():
            raise HTTPException(409, "The simulator has not produced a pen trail yet.")
        return FileResponse(path, media_type="application/json", headers={"Cache-Control": "no-store"})

    @app.get("/result/{job_id}")
    @app.get("/jobs/{job_id}/result", include_in_schema=False)
    def result(job_id: str):
        path = path_for(job_id)
        destination = path / "result.png"
        if not destination.is_file():
            try:
                status_value = read_status(app.state.jobs_dir, job_id)
                if status_value["state"] != "done" or not (path / "trail.json").is_file():
                    raise HTTPException(409, "The drawing result is not ready yet.")
                actual = read_json(path / "trail.json")["strokes"]
                # Simulator trails can have more points than the model contract.
                if not isinstance(actual, list) or not any(len(stroke) >= 2 for stroke in actual):
                    raise ValueError("empty trail")
                for stroke in actual:
                    for point in stroke:
                        if len(point) != 2 or not all(type(c) in (int, float) and math.isfinite(c) for c in point):
                            raise ValueError("invalid trail")
                fd, temp_name = tempfile.mkstemp(suffix=".png", prefix=".result-", dir=path)
                os.close(fd)
                try:
                    render_preview(actual, Path(temp_name))
                    os.replace(temp_name, destination)
                finally:
                    Path(temp_name).unlink(missing_ok=True)
            except (OSError, ValueError, KeyError, TypeError, OverflowError):
                raise HTTPException(503, "The simulator result could not be rendered.") from None
        return FileResponse(destination, media_type="image/png", headers={"Cache-Control": "no-store"})

    app.mount("/previews", StaticFiles(directory=app.state.preview_dir), name="previews")
    if (frontend / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        def root():
            return {"app": "Sim Sketch Artist", "docs": "/docs", "message": "Build frontend/dist and restart the backend to serve the browser app here."}
    return app


app = create_app()
