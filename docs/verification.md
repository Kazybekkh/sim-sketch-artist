# Verification — 6 October 2026

Local environment: Ubuntu 24.04.4, NVIDIA GeForce RTX 5070 Ti (16 GB), driver
580.178.04, Isaac Sim 5.1.0-rc.19. APIs were checked against this installation.

- 65 backend tests pass: input validation, model request shape/retry/error
  handling, image limits and normalization, concurrent queue claims, path
  validation, previews and result rendering from dense measured trails.
- Camera API checks cover finite bounds, rejected commands preserving the pending
  pose, latest-command replacement, offline rejection, worker acknowledgment
  and cross-origin requests.
- React/TypeScript production build passes. Camera gesture bounds and mocked
  transport checks cover throttling, latest input, one request at a time, stale
  acknowledgments, timeout recovery and component cleanup.
- OpenAI authenticated model listing succeeded; the configured Astra model was
  selected from that response rather than guessed.
- Live `/portrait` request: an explicitly synthetic portrait image produced a
  13-stroke, 131-point portrait in 23.7 seconds. Preview inspected visually.
- Isaac Sim SO-101 smiley test: 4 strokes completed with real joint drives.
- Isaac Sim SO-101 Astra portrait test: all 13 strokes completed, 2,058 measured
  pen samples, 6.9 seconds of warm execution. Maximum sampled pen-height deviation
  was 1.24 mm versus a 2 mm threshold. Result and simulator scene inspected visually.
- Numerical inverse kinematics preflight: 50 page and pen-lift targets reached;
  worst target error 0.39 mm.
- The public HTTPS tunnel's `/health` returned `{"ok":true}`.
- A persistent GUI worker reached `SIM_READY mode=robot` on the main jobs folder.
- The reference browser app completed its sample job through the live GUI worker.
- The actual Lovable preview completed both its sample job and an uploaded
  synthetic portrait through HTTPS → Astra → job queue → GUI SO-101 → result.
  The portrait completed 13 strokes and its finished image was visually checked
  in Lovable. This was the real external API, not a browser mock.
- The Lovable app was published at https://sim-sketch-artist.lovable.app/.
- The published site completed a fresh sample job and displayed “Finished — 4
  strokes drawn” with the real result image.
- A 36.375-second H.264 viewport recording contains 873 frames of the SO-101
  drawing the synthetic Astra portrait. Early and late frames were checked.
- Added a live Isaac viewport to the reference browser app and `/sim/view`.
  The simulator publishes real JPEG frames at up to 5 fps; the browser polls
  sequentially and flags images as disconnected after 5 seconds without updates.
- Live HTTPS test: submitted the saved Astra portrait as a new job and fetched
  44 distinct JPEG frames while all 13 strokes completed in 22.7 seconds.
  Early, middle and final network-received frames were visually inspected:
  they show different joint poses, accumulating ink, and the final portrait.
  This checks the actual current simulator, not prerecorded video playback.
- `/sim/view` and `/sim/frame` return HTTP 200 through the public tunnel; JPEGs
  have no-store headers, and CORS accepts the published Lovable origin.
- The reference frontend includes a live panel and scrolls it into view once
  a drawing is queued. The new iframe has not yet been applied to the separate
  Lovable deployment; browser automation is unavailable in the current task.

- Interactive viewer: three camera presets sent over public HTTPS were accepted
  and acknowledged by the actual worker in 0.43–0.72 seconds. Retrieved JPEGs
  were 1280×900 and visually showed the requested different views. The paper
  close-up was adjusted after inspection to keep the nib and paper visible.
- A separate Isaac run completed a two-stroke drawing while receiving camera
  changes. Camera metadata is read back from USD after application.
- Fixed image sizing in the frontend and added fullscreen plus a separate
  `/sim/view` page. Browser rendering and physical mouse gestures could not be
  inspected in this task because the browser automation inventory is empty;
  HTTP routing, production assets, actual camera movement and frames were checked.

![Actual measured pen trace](demo/actual-pen-trail.png)

The simulator uses SO-101 joint drives and a gripper-attached pen. Gravity is
disabled for the arm. Ink appears geometrically when the measured pen tip is
near the paper; pencil pressure and contact forces are not simulated.

These checks do not establish likeness quality for the user's photo, webcam
permission behavior on their Mac, or three real-photo runs. Those require the
user to use the finished app with their webcam. No private photos were accessed
for testing. Demo screenshots are from the synthetic test image.
