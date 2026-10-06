# Paste into your Lovable project

Build a single-page app called Sim Sketch Artist. It takes a webcam portrait on a Mac and makes a simulated SO-101 robot on the user’s own local or cloud Ubuntu machine draw it. Use React and TypeScript. Use a warm paper background, dark ink, restrained green buttons and a large square sketch canvas.

The backend already exists. Call it directly over HTTPS with a configurable `VITE_API_BASE_URL`. Also allow a user to paste the backend URL in a collapsible Connection settings section and remember it in localStorage. Each user connects their own backend; require a user-supplied address or use the same origin when served by their backend. The URL is public configuration, not an API credential. Do not add OpenAI calls, an API key, a mock backend, Supabase or a database to the browser app.

The main flow is: enable webcam, take a photo, click **Sketch me**. Upload is an alternative. Clicking Sketch me should POST the photo to `/portrait`, animate the returned strokes on a canvas, then automatically POST them to `/draw`. Poll `/status/{job_id}` once a second and show the finished `/result/{job_id}` image when state is done. The robot is simulated in Isaac Sim on Ubuntu. Embed the actual live camera using the configured backend’s `/sim/view` page, following `docs/lovable-live-view.md`. This viewer includes real camera controls; keep the planned stroke canvas separately labelled.

API contract:

- `GET /health` returns `{"ok":true}`.
- `POST /portrait` is multipart/form-data with field `image` containing a JPEG, PNG or WebP. Let the browser set the multipart Content-Type boundary. Response includes `title`, `strokes` (arrays of `[x,y]` point arrays), and `preview_url`. It can take a minute; show a real waiting state.
- `POST /draw` accepts exactly the `title` and `strokes` from the generated portrait and returns `{"job_id":"uuid"}`.
- `GET /status/{job_id}` returns `state` (`queued`, `running`, `done` or `error`), completed `stroke` count, `total` count and nullable `error`. Display queued as “Waiting for Isaac Sim”, running as “Drawing stroke i of n”, done as complete, and the error message when state is error. Stop polling on done/error. Retrying a network read must never enqueue a second drawing.
- `GET /result/{job_id}` returns image/png after completion.

Coordinates have the origin at the top-left; x and y range from 0 to 1. Each stroke is a separate polyline, so never join the end of one stroke to the next. At most 40 strokes, each with 2–25 points. Use a square canvas and retain this orientation for previews and results.

Webcam: call `navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false})` only after a button click. Use an inline muted video, stop all tracks on capture, switch or unmount, and show permission errors. Captured photos should not be unintentionally mirrored just because the live preview is mirrored. Support JPEG/PNG/WebP upload, max 10 MB. Explain that clicking Sketch me sends the photo to the Ubuntu service and OpenAI for drawing generation. Never upload before the user clicks Sketch me.

Use visible errors with a retry action, disable duplicate submissions during generation/drawing, clean up timers and object URLs, make the layout work on mobile and desktop, and use accessible buttons and labels. Generate each portrait from the selected user photo. Use neutral empty states with no preloaded portraits or drawing paths.

Publish the app over HTTPS so the Mac webcam is available. Set its backend URL to the HTTPS tunnel URL supplied by the Ubuntu service.

## Connecting to code

Lovable supports creating a project then exporting/syncing it to GitHub. Its documentation says existing GitHub repositories cannot be imported directly as new Lovable projects. Start the Lovable project using the prompt above; optionally connect its GitHub repository afterward to refine its code.

Source: https://docs.lovable.dev/integrations/github
