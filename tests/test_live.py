"""A frozen or missing camera must never be presented as live simulator footage."""
import io
import json
import os
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.jobs import atomic_write_json
import backend.main as api
from backend.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ROOT", tmp_path)
    frontend = tmp_path / "frontend" / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text('<!doctype html><div id="root"></div><script src="/assets/app.js"></script>')
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
    assert '<div id="root">' in response.text
    assert '/assets/app.js' in response.text


def test_viewer_without_frontend_build_explains_next_step(client):
    (api.ROOT / "frontend" / "dist" / "index.html").unlink()
    response = client.get("/sim/view")
    assert response.status_code == 503
    assert "npm --prefix frontend run build" in response.text


def test_live_routes_support_cross_origin_lovable(client):
    publish(client)
    response = client.get("/sim/status", headers={"Origin": "https://example.lovable.app"})
    assert response.headers["access-control-allow-origin"] == "*"


POSE = {"yaw": -0.785, "pitch": 0.535, "distance": 0.608, "target": [0, -0.17, 0.13]}


def test_camera_command_requires_interactive_live_worker(client):
    assert client.post("/sim/camera", json=POSE).status_code == 503
    directory, _ = publish(client)
    assert client.post("/sim/camera", json=POSE).status_code == 503
    assert not (directory / "camera.json").exists()
    publish(client, camera=POSE, updated_at=time.time() - 10)
    assert client.post("/sim/camera", json=POSE).status_code == 503


def test_camera_commands_replace_pending_pose_and_only_worker_acknowledges(client):
    directory, _ = publish(client, camera=POSE)
    first = client.post("/sim/camera", json=POSE)
    assert first.status_code == 202
    assert first.json()["accepted"] is True
    second_pose = {**POSE, "pitch": 1.55, "target": [0.02, -0.215, 0.025]}
    second = client.post("/sim/camera", json=second_pose)
    assert second.status_code == 202
    assert second.json()["command_id"] != first.json()["command_id"]
    assert json.loads((directory / "camera.json").read_text()) == {
        **second_pose, "command_id": second.json()["command_id"]}
    assert client.get("/sim/status").json()["camera_command_id"] is None
    publish(client, camera={**second_pose, "pitch": 1.5500000000001}, camera_command_id=second.json()["command_id"])
    status = client.get("/sim/status").json()
    assert status["camera_command_id"] == second.json()["command_id"]
    assert status["camera"] == second_pose


@pytest.mark.parametrize("changes", [
    {"yaw": 8}, {"yaw": True}, {"pitch": 0}, {"pitch": "1.0"},
    {"distance": 0.119}, {"distance": 1.501}, {"distance": float("nan")},
    {"target": [0, 0]}, {"target": [0, 0, 0, 0]}, {"target": [0, 0, -0.01]},
    {"target": [0.51, 0, 0]}, {"target": [0, float("inf"), 0]},
    {"target": [True, 0, 0]}, {"command_id": "browser-id"}, {"code": "anything"},
])
def test_camera_rejects_invalid_commands_without_overwriting(client, changes):
    directory, _ = publish(client, camera=POSE)
    valid = client.post("/sim/camera", json=POSE)
    before = (directory / "camera.json").read_bytes()
    response = client.post("/sim/camera", content=json.dumps({**POSE, **changes}),
                           headers={"Content-Type": "application/json"})
    assert valid.status_code == 202
    assert response.status_code == 422
    assert (directory / "camera.json").read_bytes() == before


def test_bad_camera_metadata_does_not_hide_valid_live_frame(client):
    publish(client, camera={**POSE, "distance": None})
    status = client.get("/sim/status").json()
    assert status["online"] is True
    assert status["camera"] is None


def test_usd_float_error_at_bounds_keeps_camera_controls_available(client):
    publish(client, camera={**POSE, "distance": 0.11999999, "target": [0.50000001, -0.50000001, -0.00000001]})
    status = client.get("/sim/status").json()
    assert status["online"] is True
    assert status["camera"]["distance"] == 0.12
    assert status["camera"]["target"] == [0.5, -0.5, 0]


def test_camera_control_supports_lovable_cross_origin(client):
    publish(client, camera=POSE)
    response = client.post("/sim/camera", json=POSE,
                           headers={"Origin": "https://example.lovable.app"})
    assert response.status_code == 202
    assert response.headers["access-control-allow-origin"] == "*"
    response = client.get("/sim/frame", headers={"Origin": "https://example.lovable.app"})
    assert response.headers["access-control-allow-origin"] == "*"
