# Connect an operator's simulator before showing the viewer

Apply this to the separately published Lovable project. The reusable reference
implementation lives in `frontend/`; updating this repository does not publish
changes to an existing Lovable project.

## Product behavior

Show a prominent **Connect your Isaac Sim** panel before the camera or drawing
controls. Explain: **Sim Sketch uses your own running Isaac Sim installation
and model account. Start the Sim Sketch backend and drawing worker on your GPU
machine, then connect its backend URL here.**

The address is the Sim Sketch backend root, not an SSH address, an arbitrary
Isaac Sim livestream URL, a CloudXR URL, or the `/sim/view` page. A native Isaac
installation alone does not implement this application's drawing API.

Use an editable **Simulator backend URL** field and a **Check connection**
button. Keep the address only in this browser. Do not prefill the author's
machine or deployment. No API keys, SSH passwords, or private keys belong in
this form. Show the configured endpoint so the operator can verify where
photos and jobs will go.

## Connection checks

Make only bounded, abortable, read-only requests while checking connection:

1. `GET /ready` must identify `service: "sim-sketch-artist"`,
   `protocol_version: 1` and `ok: true`. Reject HTML, an unrelated JSON service,
   or incompatible protocol with a helpful address/update message.
2. `GET /sim/status` must report `online: true`, a valid `updated_at`,
   `mode: "robot"` and no simulator error before enabling drawing. Freshness is
   five seconds in the current protocol, checked by the backend against both
   metadata and the frame file using its own clock. Do not compare the worker
   timestamp with the browser's clock: remote machines can have clock skew.
   Backend reachability alone does not
   mean that Isaac Sim is running.
3. `astra_configured: true` means credentials and a model ID are configured on
   the backend. Label this **Model configured**, not **API credits verified**.
   This check does not make a paid model call or establish account model access.

Represent these states with clear text and actionable controls:

| State | Message / action |
| --- | --- |
| No connection | Connect your Isaac Sim. Enter your backend address. |
| Checking | Checking backend and simulator… |
| Backend unreachable | Could not reach your backend. Check the address, network access and running backend. Retry / edit address. |
| Wrong service or protocol | This address is not a compatible Sim Sketch backend. Use its root URL or update the backend. |
| Backend reachable, simulator offline | Backend connected. Start the Isaac Sim drawing worker on that machine. |
| Simulator error | Show the simulator's actual error. Ask the operator to address it and restart the worker, then recheck. |
| Model configuration missing | Configure your own model credentials on your backend. |
| Ready | Isaac Sim connected. Model configured. |
| Connection lost | Connection interrupted. Your running job may continue; reconnect to check its status. |

Only mount the live viewer after a successful backend and simulator check.
Remove it when the connection is lost and show a designed reconnect state.
Do not render a broken iframe, blank error rectangle, fake stream or sample
portrait. An iframe load event alone does not prove the simulator is ready.
If embedding `/sim/view`, also provide **Open viewer in a new tab** for
embedding/authentication restrictions.

Disable **Sketch me** until a photo, live simulator and configured model are
available. Explain the missing requirement next to the action. Recheck before
sending a photo. Preserve the selected photo and existing job when a connection
is interrupted. Do not enqueue another drawing merely because a status request
was retried. Prevent switching the endpoint while a job is pending.

## Setup help

Put technical setup inside an expandable **How do I connect?** section:

- Use a compatible GPU machine you own or a cloud instance in your own account.
- Follow `docs/self-hosting.md` to configure the model and Isaac Sim path.
- Run `./scripts/backend.sh` and `./scripts/sim.sh --headless` on that machine.
- Use your own authenticated HTTPS gateway for a separately hosted Lovable app.
  Its cross-origin API and iframe authentication must be configured and tested.
- For private SSH forwarding, use your own terminal and the bundled browser app
  at the forwarded local address. Do not ask the website to log into a PC.

Keep setup and recurring GPU/API costs assigned to the operator. The application
requires its backend and simulator processes; it does not require Codex at runtime.

## Streaming technology

The current viewer displays real Isaac renderer frames with bounded camera
commands. Changing streaming transport does not remove the need for a running
GPU simulator or the application's backend.

NVIDIA's [Omniverse WebRTC library](https://docs.omniverse.nvidia.com/ov-web-sdk/latest/web-streaming-library/overview.html)
is a possible future transport for native viewport streaming and messaging.
The project's Isaac Sim 5.1 integration must be compatibility-tested before
switching to it. [Isaac Sim 5.1 livestreaming requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html)
cover streaming-mode startup, GPU and networking requirements.

[CloudXR.js](https://docs.nvidia.com/cloudxr-sdk/latest/usr_guide/cloudxr_js/index.html)
is aimed at OpenXR/VR/AR experiences and is not required for the current desktop
portrait viewer. Neither SDK provides the photo-to-strokes and drawing-job API.
