# Sim Sketch Artist

Take a webcam portrait on your Mac. Astra turns it into simple pen strokes, and
an SO-101 in Isaac Sim draws them on a virtual sheet of paper.

**Connect your own setup:** this public repository supplies the code, not a shared
GPU or model-credit service. Each operator supplies their own Isaac Sim machine, OpenAI API credentials and
model access. Follow the [self-hosting handoff](docs/self-hosting.md).

Run the reference studio at `http://localhost:8000` on your simulator host, or
connect a browser frontend to your own protected backend address using Connection
settings. The interactive viewer is available at your backend's `/sim/view` path.
Codex helped build the project; it is not required while the app runs.

```text
Mac webcam / upload in Lovable
              |
         HTTPS tunnel
              |
Ubuntu FastAPI ---> OpenAI Responses API (ASTRA_MODEL)
              |
       atomic jobs/<uuid>/ files
              |
Isaac Sim 5.1 Python ---> SO-101 joint motion + measured pen trail
              |
       live viewport + result.png ---> Mac browser
```

The browser's **Sketch me** action creates the portrait and queues the drawing.
Astra receives the photo and returns only bounded line coordinates. No model
output is executed as code. The backend uses a regular Python environment;
Isaac Sim uses its own `python.sh`. The file queue keeps those environments separate.

## Run on Ubuntu

Requirements: Python 3.11+, Node.js 22+, an installed Isaac Sim 5.1 with a supported
NVIDIA GPU, and OpenAI API access to the Astra model you configure.

```bash
./scripts/setup.sh
```

Edit the ignored `.env` file:

```dotenv
OPENAI_API_KEY=your-api-key
ASTRA_MODEL=the-exact-model-id-enabled-for-your-account
ISAAC_SIM_PATH=/absolute/path/to/isaac-sim
OPENAI_TIMEOUT_SECONDS=180
```

The key and model have no code defaults. The browser never receives the API key.
An event-provided API endpoint can be set with `OPENAI_BASE_URL`.
`ASTRA_STRUCTURED_OUTPUTS=false` disables schema enforcement only if the selected
endpoint does not support it; validation and the one correction retry remain.

Build the browser app before starting the backend (setup does this). Run these
in separate terminals from the repository root:

```bash
./scripts/backend.sh
./scripts/sim.sh
```

Open `http://localhost:8000` for the reference browser app. It supports webcam
capture, upload, animated preview, automatic queueing, progress and results.
Its live camera shows actual rendered frames from the running Isaac Sim worker,
including the SO-101's motion and ink. The camera publisher captures at up to
5 frames per second; the browser requests frames sequentially about every
400 ms. Disconnected or stale frames are clearly labelled. This is a live
simulator view, separate from the planned stroke preview.

Drag the camera image to orbit, scroll to zoom, and Shift-drag or right-drag to
pan. The **Whole scene**, **Paper close-up** and **Top view** presets move the
actual Isaac Sim camera. **Open separate viewer** opens `/sim/view`; fullscreen
is also available. Arrow keys orbit, Shift+arrows pan, +/− zoom and R resets.
Camera changes are shared between viewers and work while the arm draws. These
controls change the scene camera; they do not expose the native Isaac editor.
The renderer uses a fixed 1280×900 image, fitted without cropping in the browser.
`GET /health` verifies the HTTP service only; it does not assert that Isaac Sim
or the model is working. `GET /ready` reports whether model credentials are configured.

The SO-101 asset is fetched from NVIDIA's Isaac Sim 5.1 asset collection when
needed and kept out of Git. See [sim/README.md](sim/README.md) for drawing modes,
paper calibration and testing. The default is the robot; the explicit marker
fallback is a visualization and is labelled as such.

## Connect your browser and Lovable

Use your own protected backend address. For a remote GPU machine, follow the
private SSH forwarding or authenticated gateway options in the
[self-hosting guide](docs/self-hosting.md). Keep the backend and simulator
running while using the app.

To create a Lovable frontend, use [the app prompt](docs/lovable-prompt.md) and
[live-view integration](docs/lovable-live-view.md). Configure that app's
Connection settings with your backend's HTTPS address. Keep model credentials
only on the backend machine.

The `frontend/` directory runs independently and includes the interactive
simulator view. A separately hosted Lovable project must be connected and
published in that project; changes here do not update it automatically.

## Frontend development

The production backend serves the built frontend from the same address. For
Vite development, copy `frontend/.env.example` to `frontend/.env.local` and set
`DEV_API_URL` to your backend's address to enable the development proxy. Set
`VITE_API_BASE_URL` only when browser requests should use a separate backend
origin directly. Then run `npm --prefix frontend run dev`.

## API and drawing format

| Endpoint | Contract |
| --- | --- |
| `GET /health` | `{"ok":true}` |
| `POST /portrait` | Multipart `image` (JPEG/PNG/WebP, max 10 MB); returns `title`, `strokes`, `preview_url` |
| `POST /draw` | JSON with `title` and `strokes`; returns `{"job_id":"uuid"}` with HTTP 202 |
| `GET /status/{job_id}` | `state`, `stroke`, `total`, `error` |
| `GET /trail/{job_id}` | Measured normalized pen-tip strokes |
| `GET /result/{job_id}` | PNG rendering of the measured trail |
| `GET /sim/status` | Current camera state, job progress and frame freshness |
| `GET /sim/frame` | Latest actual viewport JPEG; HTTP 503 if unavailable or stale |
| `POST /sim/camera` | Bounded `yaw`, `pitch`, `distance`, `target`; HTTP 202 with `command_id` |
| `GET /sim/view` | Interactive camera page, ready to embed in Lovable |

A drawing contains a `title` string and `strokes`, an array of polylines. Each
polyline contains `[x, y]` points supplied by Astra or by the caller.

Camera commands are atomically replaced with the newest requested pose. The
worker acknowledges `camera_command_id` in `/sim/status` only after applying
and reading back the actual USD camera. Offline workers reject camera commands.

Coordinates are in `[0,1]`, origin top-left. There are 1–40 strokes with 2–25
points per stroke. Astra output is validated, repaired within these limits and
ordered to reduce pen travel. `/draw` rejects invalid input. The simulator
interpolates intermediate targets; its measured trail can contain more points.
The same stroke format can target a physical SO-101 after calibration and an
appropriate hardware controller; this project controls only the simulation.

Each job folder holds `strokes.json`, `status.json`, `trail.json` and `result.png`.
States are `queued`, `running`, `done`, `error`. JSON writes and job publication
are atomic. A claimed job is never automatically replayed after a crash. Inspect
the simulator and submit a new job if a run was interrupted.

## Verify

```bash
.venv/bin/python -m pytest tests -q
npm --prefix frontend run build
```

To verify the full pipeline, start your backend and simulator, select your own
photo, and use **Sketch me**. Confirm the job progresses from queued to done,
the arm moves in the live view, and the result renders its measured pen trail.
This uses the API credentials and GPU configured on your backend.

## Access and data

Each operator pays for their own GPU and API use. This backend has permissive
CORS and no user accounts. Keep it private or behind authenticated access;
anyone who can reach an unprotected backend can queue work and spend its API
budget. A temporary tunnel URL is not authentication.

Input photos are processed in memory and sent to OpenAI. Derived previews,
strokes and results stay in ignored runtime folders. The repository includes
no input photos, generated portraits, saved drawings, prerecorded videos or
model credentials. See [attribution](docs/attribution.md) for third-party
components and robot asset provenance.

## References

- [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Lovable GitHub integration](https://docs.lovable.dev/integrations/github)
- [Cloudflare quick tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
