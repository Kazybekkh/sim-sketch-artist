Run the persistent SO-101 drawing worker with Isaac Sim's Python:

```bash
python sim/fetch_assets.py
/home/cal/isaac-sim/python.sh sim/draw_sim.py
```

The worker claims jobs from `jobs/`, executes joint position targets in PhysX,
and records the measured pen-tip path. It never executes model-generated code.
Configuration is JSON-compatible YAML. The paper is a 10 × 11 cm plane in front
of the arm. The pen is fixed to the gripper and the gripper joint stays closed.
The arm uses gravity compensation (gravity is disabled for its links) and stiff
position drives. Ink is emitted geometrically when the measured nib is within
2 mm of the page; this does not model paper contact forces or pencil pressure.
`JOBS_DIR` overrides the default queue, and `--jobs-dir` overrides the environment.

`--sample --once --headless` runs a small local test without Astra. `--mode marker`
explicitly selects a marker-only visualization; it is never selected as an
automatic substitute for an SO-101 failure. The result identifies the mode.
`--sample path/to/drawing.json --once --headless` runs a saved drawing instead.

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
simulator from a stale screenshot. It never uses the result PNG or demo video.
Use `--no-live` to disable capture for isolated headless tests.

Drawing is paced at real simulation time by default, so the arm's physical
motion is visible in the browser. `--playback-speed 2` runs at up to twice real
time, and `--playback-speed 0` disables pacing for tests. Slow rendering naturally
reduces playback speed; poses and measured ink are still produced by PhysX.

An optional bounded video captures only the Isaac viewport, then uses `ffmpeg`
to encode an MP4. The output must be a new path. This feature requires `--once`:

```bash
/home/cal/isaac-sim/python.sh sim/draw_sim.py --sample samples/smiley.json \
  --headless --once --jobs-dir sim/smoke-jobs --record /tmp/isaac-drawing.mp4
```

Video plays captured rendered frames at 24 fps; it is a simulation demonstration,
not a real-time timing measurement or evidence of a live webcam session.
The bundled [`isaac-drawing.mp4`](../docs/demo/isaac-drawing.mp4) is a 36-second
prerecorded simulation of Astra's response to a synthetic portrait test image.
It contains 13 strokes and shows the actual SO-101 simulation, not marker mode.

Assets are downloaded from NVIDIA's Isaac Sim 5.1 asset collection, cached
locally, and excluded from source control. NVIDIA's asset terms apply. This is
a simulation demonstration; no hardware is controlled.
