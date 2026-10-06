"""Atomic, dependency-free file queue shared with Isaac Sim's Python.

A .claim lock is intentionally retained after a claim. A crashed running job is
never retried automatically: inspect the simulator before manual recovery or
submit a fresh job. This avoids repeating a partially completed drawing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import UUID, uuid4

STATES = {"queued", "running", "done", "error"}


def valid_job_id(job_id: str) -> bool:
    try:
        return isinstance(job_id, str) and str(UUID(job_id)) == job_id
    except (ValueError, TypeError, AttributeError):
        return False


def job_path(jobs_dir: str | Path, job_id: str) -> Path:
    if not valid_job_id(job_id):
        raise ValueError("invalid job id")
    root = Path(jobs_dir).resolve()
    candidate = root / job_id
    if candidate.resolve().parent != root:
        raise ValueError("job path must remain inside jobs directory")
    return candidate


def atomic_write_json(destination: str | Path, value: Any) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def create_job(jobs_dir: str | Path, drawing: dict) -> str:
    root = Path(jobs_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid4())
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
    try:
        atomic_write_json(staging / "strokes.json", drawing)
        atomic_write_json(staging / "status.json", {
            "state": "queued", "stroke": 0, "total": len(drawing["strokes"]), "error": None,
        })
        # Publish the complete folder in a single rename, after both files exist.
        os.rename(staging, job_path(root, job_id))
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return job_id


def read_job(jobs_dir: str | Path, job_id: str) -> dict:
    return read_json(job_path(jobs_dir, job_id) / "strokes.json")


def read_status(jobs_dir: str | Path, job_id: str) -> dict:
    return read_json(job_path(jobs_dir, job_id) / "status.json")


def update_job(jobs_dir: str | Path, job_id: str, *, status: str | None = None,
               state: str | None = None, stroke: int | None = None,
               total: int | None = None, error: str | None = None) -> dict:
    path = job_path(jobs_dir, job_id)
    value = read_status(jobs_dir, job_id)
    next_state = state if state is not None else status
    if next_state is not None:
        if next_state not in STATES:
            raise ValueError("invalid job state")
        value["state"] = next_state
    if stroke is not None:
        value["stroke"] = int(stroke)
    if total is not None:
        value["total"] = int(total)
    if value["stroke"] < 0 or value["total"] < 0 or value["stroke"] > value["total"]:
        raise ValueError("invalid stroke progress")
    value["error"] = str(error)[:1000] if error is not None else None
    atomic_write_json(path / "status.json", value)
    return value


def claim_next_job(jobs_dir: str | Path) -> dict | None:
    """Atomically claim a queued job, returning job_id plus its drawing payload."""
    root = Path(jobs_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # UUID order is deterministic; directory mtime preserves normal queue order.
    candidates = [entry for entry in root.iterdir() if valid_job_id(entry.name) and entry.is_dir() and not entry.is_symlink()]
    candidates.sort(key=lambda entry: (entry.stat().st_mtime_ns, entry.name))
    for path in candidates:
        try:
            if read_status(root, path.name).get("state") != "queued":
                continue
            claim_fd = os.open(path / ".claim", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except (FileExistsError, FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
        with os.fdopen(claim_fd, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        # The .claim is persistent: other processes cannot execute this job.
        try:
            drawing = read_job(root, path.name)
            update_job(root, path.name, state="running", stroke=0)
            return {"job_id": path.name, **drawing}
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            try:
                update_job(root, path.name, state="error", error="Could not read the queued drawing.")
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
    return None
