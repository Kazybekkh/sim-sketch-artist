"""Contract, queue safety, and mocked Responses API checks (no network calls)."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
import json
import math
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from PIL import Image
import pytest
from pydantic import ValidationError

from backend.astra import AstraPortraits, PortraitError
from backend.jobs import atomic_write_json, claim_next_job, create_job, job_path, read_job, read_status, update_job
from backend.main import create_app, normalize_image
from backend.strokes import Drawing, clean_model_drawing, order_strokes

DRAWING = {"title": "Test sketch", "strokes": [[[0.1, 0.2], [0.8, 0.9]]]}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(jobs_dir=tmp_path / "jobs", preview_dir=tmp_path / "previews"))


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, "JPEG")
    return buffer.getvalue()


def test_health_and_cors(client):
    assert client.get("/health").json() == {"ok": True}
    response = client.options("/draw", headers={"Origin": "https://a.lovable.app", "Access-Control-Request-Method": "POST"})
    assert response.headers["access-control-allow-origin"] == "*"
    assert "OPENAI_API_KEY" not in client.get("/ready").text


def test_readiness_identifies_bridge_without_claiming_simulator_is_running(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-test-key")
    monkeypatch.setenv("ASTRA_MODEL", "configured-test-model")
    response = client.get("/ready")
    body = response.json()
    assert body["service"] == "sim-sketch-artist"
    assert body["protocol_version"] == 1
    assert body["astra_configured"] is True
    assert body["astra_model"] == "configured-test-model"
    assert "private-test-key" not in response.text
    assert "no-store" in response.headers["cache-control"]
    assert client.get("/sim/status").json()["online"] is False
    monkeypatch.delenv("OPENAI_API_KEY")
    assert client.get("/ready").json()["astra_configured"] is False


@pytest.mark.parametrize("point", [[-0.1, 0.2], [1.1, 0.2], [True, 0.2], ["0.1", 0.2], [0.1, 0.2, 0.3]])
def test_draw_rejects_invalid_coordinates(client, point):
    assert client.post("/draw", json={"title": "Bad", "strokes": [[point, [0.5, 0.5]]]}).status_code == 422


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_schema_rejects_nonfinite(value):
    with pytest.raises(ValidationError):
        Drawing(title="Bad", strokes=[[[value, 0.1], [0.2, 0.2]]])


def test_api_rejects_nonfinite_without_server_error(client):
    response = client.post("/draw", content='{"title":"Bad","strokes":[[[NaN,0],[1,1]]]}',
                           headers={"content-type": "application/json"})
    assert response.status_code == 422


def test_stroke_and_point_limits(client):
    assert client.post("/draw", json={"title": "Too many", "strokes": DRAWING["strokes"] * 41}).status_code == 422
    assert client.post("/draw", json={"title": "Too many", "strokes": [[[0, 0]] * 26]}).status_code == 422
    assert client.post("/draw", json={"title": "Empty", "strokes": []}).status_code == 422
    assert client.post("/draw", json={"title": "Short", "strokes": [[[0, 0]]]}).status_code == 422


def test_model_repair_and_ordering():
    drawing = clean_model_drawing({"title": "  Portrait  ", "strokes": [None, [[1, 1]], [[-1, 0], [float("nan"), 0], [2, 1]] ]})
    assert drawing.model_dump() == {"title": "Portrait", "strokes": [[[0.0, 0.0], [1.0, 1.0]]]}
    long = clean_model_drawing({"strokes": [[[i / 100, i / 100] for i in range(100)]] * 50})
    assert len(long.strokes) == 40 and len(long.strokes[0]) == 25
    result = order_strokes(Drawing(title="Order", strokes=[[[0.8, 0.8], [0.9, 0.9]], [[0.3, 0.3], [0.1, 0.1]]]))
    assert result.strokes[0] == [[0.1, 0.1], [0.3, 0.3]]


def test_queue_publication_and_atomic_claim(tmp_path):
    root = tmp_path / "jobs"
    job_id = create_job(root, DRAWING)
    assert read_job(root, job_id) == DRAWING
    assert read_status(root, job_id) == {"state": "queued", "stroke": 0, "total": 1, "error": None}
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: claim_next_job(root), range(8)))
    assert sum(claim is not None for claim in claims) == 1
    assert read_status(root, job_id)["state"] == "running"
    assert claim_next_job(root) is None
    update_job(root, job_id, state="done", stroke=1)
    assert read_status(root, job_id)["state"] == "done"
    assert not list(root.glob(".pending-*"))


def test_partial_jobs_and_path_traversal(tmp_path, client):
    root = tmp_path / "jobs"
    (root / ".pending-incomplete").mkdir(parents=True)
    assert claim_next_job(root) is None
    for bad in ("../private", "/tmp", "not-a-job", "00000000-0000-0000-0000-000000000000/../"):
        with pytest.raises(ValueError):
            job_path(root, bad)
    assert client.get("/status/not-a-job").status_code == 404
    assert client.get("/status/00000000-0000-0000-0000-000000000000").status_code == 404
    actual_id = "00000000-0000-0000-0000-000000000001"
    (root / actual_id).symlink_to(tmp_path)
    with pytest.raises(ValueError):
        job_path(root, actual_id)


def test_atomic_write_preserves_existing_on_failure(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"good": True})
    with pytest.raises(ValueError):
        atomic_write_json(path, {"bad": float("nan")})
    assert json.loads(path.read_text()) == {"good": True}
    assert len(list(tmp_path.iterdir())) == 1


def test_api_job_lifecycle_and_actual_trail_result(client):
    response = client.post("/draw", json=DRAWING)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert client.get(f"/status/{job_id}").json()["state"] == "queued"
    assert client.get(f"/result/{job_id}").status_code == 409
    root = client.app.state.jobs_dir
    claim_next_job(root)
    trail = {"title": "Actual", "strokes": [[[i / 99, 0.5] for i in range(100)]]}
    atomic_write_json(job_path(root, job_id) / "trail.json", trail)
    update_job(root, job_id, status="done", stroke=1)
    assert client.get(f"/trail/{job_id}").json() == trail
    result = client.get(f"/result/{job_id}")
    assert result.status_code == 200 and result.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(result.content)).size == (1024, 1024)


def test_invalid_and_oversized_image(client):
    assert client.post("/portrait", files={"image": ("photo.png", b"not an image", "image/png")}).status_code == 415
    assert client.post("/portrait", files={"image": ("photo.png", b"", "image/png")}).status_code == 400
    assert client.post("/portrait", files={"image": ("photo.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")}).status_code == 413


def test_normalization_checks_pixels_and_strips_metadata():
    normalized = normalize_image(jpeg())
    assert normalized.startswith("data:image/jpeg;base64,")


def test_portrait_only_saves_preview(tmp_path):
    class FakePortraits:
        async def generate(self, data_url):
            assert data_url.startswith("data:image/jpeg;base64,")
            return Drawing(**DRAWING)
    client = TestClient(create_app(jobs_dir=tmp_path / "jobs", preview_dir=tmp_path / "previews", portrait_service=FakePortraits()))
    response = client.post("/portrait", files={"image": ("private-photo.jpg", jpeg(), "image/jpeg")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["strokes"] == DRAWING["strokes"]
    assert client.get(payload["preview_url"]).status_code == 200
    assert len(list(tmp_path.rglob("*.png"))) == 1
    assert not list(tmp_path.rglob("*.jpg"))


def test_missing_astra_config(client, monkeypatch):
    monkeypatch.delenv("ASTRA_MODEL", raising=False)
    response = client.post("/portrait", files={"image": ("photo.jpg", jpeg(), "image/jpeg")})
    assert response.status_code == 503
    assert "ASTRA_MODEL" in response.json()["detail"]


def response_object(text):
    return {"id": "resp_test", "created_at": 1, "object": "response", "model": "test-model", "status": "completed",
            "output": [{"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}]}]}


def test_astra_responses_transport_validation_retry():
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        output = "not valid JSON" if len(requests) == 1 else json.dumps(DRAWING)
        return httpx.Response(200, json=response_object(output))
    async def run():
        async with AsyncOpenAI(api_key="test-never-real", base_url="https://unit.test/v1", max_retries=0,
                               http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))) as api:
            return await AstraPortraits(client=api, model="test-model").generate("data:image/jpeg;base64,AAAA")
    result = asyncio.run(run())
    assert result.title == DRAWING["title"] and len(requests) == 2
    assert requests[0]["text"]["format"]["type"] == "json_schema"
    assert requests[0]["text"]["format"]["strict"] is True
    assert requests[0]["store"] is False
    assert requests[0]["input"][0]["content"][1]["type"] == "input_image"


def test_astra_fails_after_two_invalid_outputs():
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=response_object('{"title":"Bad","strokes":[]}'))
    async def run():
        async with AsyncOpenAI(api_key="test-never-real", max_retries=0,
                               http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))) as api:
            await AstraPortraits(client=api, model="test-model", structured_outputs=False).generate("data:image/jpeg;base64,AAAA")
    with pytest.raises(PortraitError, match="two attempts"):
        asyncio.run(run())
    assert len(calls) == 2
    assert "text" not in json.loads(calls[0].content)


def test_provider_error_does_not_leak_credentials():
    def handle(request):
        return httpx.Response(401, json={"error": {"message": "SECRET-KEY-IN-UPSTREAM", "type": "authentication_error"}})
    async def run():
        async with AsyncOpenAI(api_key="test-never-real", max_retries=0,
                               http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))) as api:
            await AstraPortraits(client=api, model="test-model").generate("data:image/jpeg;base64,AAAA")
    with pytest.raises(PortraitError) as error:
        asyncio.run(run())
    assert "SECRET" not in str(error.value)
    assert "credentials" in str(error.value)
