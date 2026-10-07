# Add the real live simulator to Lovable

The Ubuntu service now publishes live frames from the actual Isaac Sim viewport.
The reference app at the backend root includes this camera. The separately
published Lovable app needs the following small integration.

First apply [the connection flow](lovable-connection-flow.md). Only mount the viewer after the backend and active simulator are verified.

Paste this into the existing Lovable project:

> Add a prominent "Live Isaac Sim" panel to the current Sim Sketch Artist app.
> Embed an iframe whose src is the current configured backend API base URL plus
> `/sim/view`. Each user supplies their own backend address in Connection
> settings; do not default to the project author’s computer or credentials.
> This page already displays actual simulator frames, live/offline state,
> SO-101 motion, ink and stroke progress, plus drag-to-orbit, Shift-drag pan,
> scroll zoom and camera presets. Allow fullscreen. Give it a descriptive iframe title,
> width 100%, and a responsive height of about 550px (400px on mobile).
> When Sketch me successfully queues a job, scroll this
> panel into view once, respecting reduced-motion preferences. Preserve the
> current webcam/upload, Astra request, status polling and result display.
> Keep the planned stroke canvas separately labelled as a preview. Do not
> replace the actual simulator view with fabricated frames or prerecorded media. Use the same backend URL as the rest of the app so the
> iframe follows Connection settings. Build and publish the update.

Minimal React embed, with `apiBase` supplied by the existing connection setting:

```tsx
<iframe
  title="Live Isaac Sim SO-101 drawing camera"
  src={`${apiBase.replace(/\/$/, '')}/sim/view`}
  allow="fullscreen"
  allowFullScreen
  style={{ width: '100%', height: 550, border: 0, borderRadius: 16 }}
/>
```

The iframe needs no OpenAI credentials or webcam permission. Its camera is the
Isaac Sim renderer on Ubuntu. The outer Lovable app still handles the Mac webcam.
Keep the backend, tunnel and simulator processes running. A restarted quick
tunnel changes the base URL.
