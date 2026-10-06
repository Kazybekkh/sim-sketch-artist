# Run with your own Isaac Sim and model account

Each operator runs their own backend and simulator and supplies their own model
API credentials. Your cloud account pays for your instance; your API account
pays for portrait generation. The project does not provide a shared GPU or API
budget. Codex helped build the project but is not needed to run it.

The worker starts this project's SO-101 drawing scene in your Isaac Sim
installation. It does not attach to an arbitrary existing Isaac scene or robot.

## Prepare your machine

Use an Ubuntu machine with a compatible NVIDIA GPU and driver, Python 3.11+,
Node.js 22+, and an Isaac Sim installation containing `python.sh`. This project
was tested with Isaac Sim 5.1; newer versions have not been validated here.
Check NVIDIA's [Isaac Sim 5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)
before choosing a local or cloud GPU.

A cloud instance must be in your own account. NVIDIA publishes an
[Isaac Sim deployment guide for Brev](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_brev.html),
but this application has not been deployed or verified on Brev. These are
application setup instructions, not a tested one-click Brev template.

Clone the repository on that machine, then install the application:

```bash
git clone https://github.com/Kazybekkh/sim-sketch-artist.git
cd sim-sketch-artist
./scripts/setup.sh
```

Setup builds the browser frontend and creates an ignored `.env` if one does not
exist. Edit that file on your backend machine:

```dotenv
OPENAI_API_KEY=your-own-api-key
ASTRA_MODEL=the-exact-model-id-your-account-can-access
ISAAC_SIM_PATH=/absolute/path/to/your/isaac-sim
PORT=8000
```

You need your own access to the configured Astra model. An API key alone does
not grant access to an event model. Keep the key in this local `.env`; never put
it in browser settings, Lovable prompts, `VITE_*` variables, or Git. The browser
needs only the backend URL. See [the main README](../README.md) for optional
endpoint and timeout settings.

## Start and test

Open two terminals in the repository directory. In the first, run:

```bash
./scripts/backend.sh
```

In the second, run:

```bash
./scripts/sim.sh --headless
```

The backend and worker must run on the same host with access to the same queue
directory. Both default to this checkout's `jobs/`; if you set `JOBS_DIR` in
`.env`, use the same absolute path for both processes. Robot assets download
when needed and remain outside Git; their own terms apply.

Open `http://localhost:8000` in a browser on the backend machine. Select your own
photo and use **Sketch me** to test portrait generation and robot drawing with
your model credentials and GPU. No drawing is generated or queued until you
request one.
The interactive camera is also available at `http://localhost:8000/sim/view`.
Keep both terminal processes running while using the app; no Codex session is
required.

## Use a Mac or the Lovable frontend

For a remote GPU machine, `localhost` on your Mac refers to the Mac, not the
GPU server. Access your backend through a private connection or an
authenticated HTTPS gateway that you own. The included backend binds to
`127.0.0.1` and has no application authentication or per-user quotas. Public
shared hosting is not ready: anyone who can reach an unprotected backend can
spend its configured API budget and queue GPU work.

If you already have SSH access to your GPU host, a private port forward lets
you use the bundled app without opening its API to the internet. On your Mac,
substitute your existing SSH login and keep this terminal open:

```bash
ssh -N -L 8000:127.0.0.1:8000 your-user@your-gpu-host
```

Then open `http://localhost:8000` on your Mac. Use another local port if 8000
is already occupied. This is the bundled reference frontend; it does not modify
the separately published Lovable app.

The simplest remote arrangement serves the bundled browser app and API
together behind your gateway. To use a separately hosted Lovable frontend, put
your own HTTPS backend URL in **Connection settings** and configure your
gateway for that browser's authenticated API and iframe requests. The current
frontend does not implement gateway sign-in, so that integration must be
configured and verified separately. Use only a backend you control or have permission to access.

The live viewer embed uses the same configured backend URL plus `/sim/view`;
see [the Lovable integration instructions](lovable-live-view.md). Changing the
browser connection changes where photos, drawing jobs and camera commands go.
Stop your backend, simulator and cloud instance when finished; a running
instance may continue to incur your provider's charges.
