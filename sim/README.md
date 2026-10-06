Set `ISAAC_SIM_PATH` in the repository's `.env` to your Isaac Sim installation,
then run the persistent SO-101 drawing worker with its Python environment:

```bash
python sim/fetch_assets.py
./scripts/sim.sh
```

The worker claims jobs from `jobs/`, executes joint position targets in PhysX,
and records the measured pen-tip path. It never executes model-generated code.
Configuration is JSON-compatible YAML. The paper is a 10 × 11 cm plane in front
of the arm. The pen is fixed to the gripper and the gripper joint stays closed.
The arm uses gravity compensation (gravity is disabled for its links) and stiff
position drives. Ink is emitted geometrically when the measured nib is within
2 mm of the page; this does not model paper contact forces or pencil pressure.
`JOBS_DIR` overrides the default queue, and `--jobs-dir` overrides the environment.

The worker waits for submitted drawings; it has no built-in drawing. To enqueue
your own saved drawing, use `--drawing /path/to/drawing.json`. The JSON must
contain a `title` and `strokes`: 1–40 strokes, each with 2–25 `[x, y]` points
normalized to the range 0–1. `--once` processes one queued job and then exits,
or exits immediately if the queue is empty. `--headless` disables the native
Isaac window. `--mode marker` explicitly selects a marker-only diagnostic
visualization; it is never selected as an automatic substitute for an SO-101
failure. The result identifies the mode.

The result PNG is rasterized from `trail.json`, containing the measured path in
normalized page coordinates. `execution.json` includes the mode and measured
world coordinates. `scene.png` captures the Isaac viewport when available.
The worker remains open after jobs unless `--once` is supplied.

While the worker is open, `jobs/.live/frame.jpg` contains a fresh capture of the
actual Isaac rendered viewport at up to 5 fps. `jobs/.live/status.json` records
the capture timestamp, increasing frame ID, robot/marker mode, current job,
stroke progress, and execution state. A single capture is allowed in flight;
JPEG encoding runs in a bounded background worker and publishes files by atomic
rename. The live feed includes idle frames so clients can distinguish a running
simulator from a stale screenshot. Frames come directly from the renderer.
Use `--no-live` to disable capture for isolated headless tests.

Drawing is paced at real simulation time by default, so the arm's physical
motion is visible in the browser. `--playback-speed 2` runs at up to twice real
time, and `--playback-speed 0` disables pacing for tests. Slow rendering naturally
reduces playback speed; poses and measured ink are still produced by PhysX.

An optional bounded video captures only the Isaac viewport, then uses `ffmpeg`
to encode an MP4. The output must be a new path. This feature requires `--once`:

```bash
./scripts/sim.sh --drawing /path/to/drawing.json --headless --once \
  --jobs-dir /path/to/empty-queue --record /path/to/recording.mp4
```

Use an empty queue for a recording so `--once` processes your supplied drawing.
Video plays captured rendered frames at 24 fps; it is not a real-time timing
measurement.

Assets are downloaded from NVIDIA's Isaac Sim 5.1 asset collection, cached
locally, and excluded from source control. NVIDIA's asset terms apply. This is
a simulator; no hardware is controlled.
