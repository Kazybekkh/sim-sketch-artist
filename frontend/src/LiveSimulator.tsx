import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Radio, Video, WifiOff } from 'lucide-react';

type SimulatorStatus = {
  online: boolean;
  updated_at: number | null;
  frame_id: number | null;
  state: 'idle' | 'running' | 'error';
  job_id: string | null;
  stroke: number;
  total: number;
  mode: 'robot' | 'marker' | null;
  error: string | null;
};

type CurrentJob = {
  id: string;
  state: 'queued' | 'running' | 'done' | 'error';
  stroke: number;
  total: number;
  error: string | null;
};

export default function LiveSimulator({ api, job }: { api: string; job: CurrentJob | null }) {
  const [status, setStatus] = useState<SimulatorStatus | null>(null);
  const [frame, setFrame] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const lastReceived = useRef(0);

  useEffect(() => () => { if (frame) URL.revokeObjectURL(frame); }, [frame]);

  useEffect(() => {
    let active = true;
    let timer = 0;
    let request: AbortController | null = null;
    let lastId: number | null = null;
    lastReceived.current = 0;
    setStatus(null);
    setFrame(null);
    setConnected(false);
    setConnecting(true);

    async function poll() {
      request = new AbortController();
      const timeout = window.setTimeout(() => request?.abort(), 4500);
      try {
        const response = await fetch(`${api}/sim/status`, { cache: 'no-store', signal: request.signal });
        if (!response.ok) throw new Error('The simulator camera is unavailable.');
        const next = await response.json() as SimulatorStatus;
        if (!active) return;
        setStatus(next);
        if (!next.online) { setConnected(false); return; }

        const imageResponse = await fetch(`${api}/sim/frame?t=${Date.now()}`, { cache: 'no-store', signal: request.signal });
        if (!imageResponse.ok) throw new Error('The simulator frame is unavailable.');
        const imageBlob = await imageResponse.blob();
        if (!active) return;
        const nextUrl = URL.createObjectURL(imageBlob);
        try {
          const decoded = new Image();
          decoded.src = nextUrl;
          await decoded.decode();
        } catch (cause) {
          URL.revokeObjectURL(nextUrl);
          throw cause;
        }
        if (!active) { URL.revokeObjectURL(nextUrl); return; }
        setFrame(nextUrl);
        if (next.frame_id !== lastId) {
          lastReceived.current = performance.now();
          lastId = next.frame_id;
        }
        setConnected(performance.now() - lastReceived.current < 5000);
      } catch {
        if (active) setConnected(false);
      } finally {
        window.clearTimeout(timeout);
        if (active) {
          setConnecting(false);
          // Chain requests so slow tunnels never accumulate overlapping frames.
          timer = window.setTimeout(poll, 400);
        }
      }
    }

    const freshness = window.setInterval(() => {
      if (lastReceived.current && performance.now() - lastReceived.current > 5000) setConnected(false);
    }, 1000);
    void poll();
    return () => {
      active = false;
      request?.abort();
      window.clearTimeout(timer);
      window.clearInterval(freshness);
    };
  }, [api]);

  const marker = status?.mode === 'marker';
  const label = connected ? 'Live Isaac Sim' : connecting ? 'Connecting…' : frame ? 'Camera disconnected' : 'Simulator offline';
  const currentJob = job && status?.job_id === job.id && connected && status.state === 'running' ? status : job;
  const progress = currentJob ? currentJob.state === 'queued' ? 'Your portrait is queued for the robot'
    : currentJob.state === 'done' ? `Your portrait is finished · ${currentJob.total} strokes`
    : currentJob.state === 'error' ? 'Your portrait needs attention'
    : `Your portrait · stroke ${currentJob.stroke} of ${currentJob.total}`
    : status?.state === 'error' ? 'Simulator error' : connected && status?.state === 'running'
    ? `Drawing stroke ${status.stroke} of ${status.total}` : connected ? 'Robot ready for your next portrait' : 'Reconnecting automatically';

  return <section id="live-simulator" className="studio-panel simulator-panel" aria-label="Live Isaac Sim robot camera">
    <div className="simulator-heading">
      <div><span className="simulator-icon"><Video size={19} strokeWidth={1.5} /></span><div><h2>The robot studio</h2><p>Watch your portrait take shape inside Isaac Sim.</p></div></div>
      <span className={`live-badge ${connected ? 'is-live' : ''}`} role="status">{connected ? <Radio size={13} /> : <WifiOff size={13} />}{label}</span>
    </div>
    <div className="simulator-camera">
      {frame ? <img src={frame} className={`simulator-frame ${connected ? '' : 'is-stale'}`} alt={marker ? 'Actual Isaac Sim camera showing marker fallback drawing' : 'Actual Isaac Sim camera showing the SO-101 arm and drawing surface'} />
        : <div className="simulator-empty"><Video size={34} strokeWidth={1.2} /><h3>{connecting ? 'Connecting to the robot…' : 'Waiting for Isaac Sim'}</h3><p>The live robot camera appears here when the simulator is running.</p></div>}
      {frame && !connected && <span className="stale-frame-note"><WifiOff size={14} />Last received frame · live camera disconnected</span>}
      {connected && <span className="camera-source">ISAAC SIM CAMERA</span>}
    </div>
    <div className="simulator-footer"><span>{marker ? 'Marker fallback · no robot arm control' : status?.mode === 'robot' ? 'SO-101 · robot simulation' : 'Actual simulator camera'}</span><span aria-live="polite" className={currentJob?.state === 'running' || (status?.state === 'running' && connected) ? 'drawing-now' : ''}>{progress}</span></div>
    {currentJob && ['queued', 'running'].includes(currentJob.state) && <progress className="simulator-job-progress" value={currentJob.stroke} max={currentJob.total || 1} aria-label="Your portrait drawing progress" />}
    {status?.error && <p className="simulator-error" role="alert"><AlertCircle size={15} />{status.error}</p>}
    {job?.error && job.error !== status?.error && <p className="simulator-error" role="alert"><AlertCircle size={15} />{job.error}</p>}
  </section>;
}
