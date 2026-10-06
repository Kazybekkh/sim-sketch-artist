"""A frozen or missing camera must never be presented as live simulator footage."""
import io
import json
import os
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.jobs import atomic_write_json
from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(jobs_dir=tmp_path / "jobs", preview_dir=tmp_path / "previews"))


def publish(client, **changes):
    directory = client.app.state.jobs_dir / ".live"
    directory.mkdir(exist_ok=True)
    buffer = io.BytesIO()
    Image.new("RGB", (24, 16), "green").save(buffer, "JPEG")
    (directory / "frame.jpg").write_bytes(buffer.getvalue())
    metadata = {"updated_at": time.time(), "frame_id": 42, "state": "running",
                "job_id": "test-job", "stroke": 2, "total": 13, "mode": "robot", "error": None}
    metadata.update(changes)
    atomic_write_json(directory / "status.json", metadata)
    return directory, buffer.getvalue()


def test_missing_camera_is_offline(client):
    response = client.get("/sim/status")
    assert response.status_code == 200
    assert response.json()["online"] is False
    assert response.json()["frame_url"] == "/sim/frame"
    assert client.get("/sim/frame").status_code == 503
    assert "no-store" in response.headers["cache-control"]
    assert "no-store" in client.get("/sim/frame").headers["cache-control"]


def test_live_frames_and_robot_progress(client):
    _, data = publish(client)
    response = client.get("/sim/status")
    metadata = response.json()
    assert metadata["online"] is True
    assert metadata["frame_id"] == 42
    assert metadata["mode"] == "robot"
    assert metadata["stroke"] == 2 and metadata["total"] == 13
    frame = client.get("/sim/frame?t=123")
    assert frame.status_code == 200
    assert frame.content == data
    assert frame.headers["content-type"] == "image/jpeg"
    assert "no-store" in frame.headers["cache-control"]
    assert "etag" not in frame.headers


def test_stale_status_does_not_serve_frame(client):
    publish(client, updated_at=time.time() - 10)
    assert client.get("/sim/status").json()["online"] is False
    assert client.get("/sim/frame").status_code == 503


def test_stale_frame_with_fresh_heartbeat_is_offline(client):
    directory, _ = publish(client)
    old = time.time() - 10
    os.utime(directory / "frame.jpg", (old, old))
    assert client.get("/sim/status").json()["online"] is False
    assert client.get("/sim/frame").status_code == 503


def test_missing_or_empty_frame_is_offline(client):
    directory, _ = publish(client)
    (directory / "frame.jpg").write_bytes(b"")
    assert client.get("/sim/status").json()["online"] is False
    (directory / "frame.jpg").unlink()
    assert client.get("/sim/frame").status_code == 503


def test_marker_and_simulator_errors_remain_explicit(client):
    publish(client, mode="marker", state="error", error="Joint command failed")
    status = client.get("/sim/status").json()
    assert status["online"] is True
    assert status["mode"] == "marker"
    assert status["error"] == "Joint command failed"
    assert status["state"] == "error"


@pytest.mark.parametrize("bad", [None, [], {}, {"updated_at": "yesterday"}, {"frame_id": -1},
                                {"mode": "rendered_preview"}, {"state": ["running"]},
                                {"stroke": 14}, {"stroke": True}, {"error": {}},
                                {"updated_at": float("nan")}, {"updated_at": float("inf")}])
def test_invalid_metadata_never_appears_live(client, bad):
    directory, _ = publish(client)
    original = json.loads((directory / "status.json").read_text())
    value = {**original, **bad} if isinstance(bad, dict) and bad else bad
    (directory / "status.json").write_text(json.dumps(value))
    response = client.get("/sim/status")
    assert response.status_code == 200
    assert response.json()["online"] is False
    assert response.json()["error"]
    assert client.get("/sim/frame").status_code == 503


def test_future_metadata_not_live(client):
    publish(client, updated_at=time.time() + 60)
    assert client.get("/sim/status").json()["online"] is False


def test_viewer_can_be_embedded_by_lovable(client):
    response = client.get("/sim/view")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["content-security-policy"] == "frame-ancestors *"
    assert "x-frame-options" not in response.headers
    assert "no-store" in response.headers["cache-control"]
    assert "Last received frame" in response.text
    assert "Marker fallback" in response.text
    assert "fetch('/sim/frame" in response.text
    assert "fetch('/sim/status" in response.text


def test_live_routes_support_cross_origin_lovable(client):
    publish(client)
    response = client.get("/sim/status", headers={"Origin": "https://example.lovable.app"})
    assert response.headers["access-control-allow-origin"] == "*"
    response = client.get("/sim/frame", headers={"Origin": "https://example.lovable.app"})
    assert response.headers["access-control-allow-origin"] == "*"
