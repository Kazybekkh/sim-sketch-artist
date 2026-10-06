import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { AlertCircle, ExternalLink, Maximize, Minimize, Minus, Plus, Radio, RotateCcw, Video, WifiOff } from 'lucide-react';
import useSimulatorCamera, { type CameraStatus } from './useSimulatorCamera';
import { CAMERA_PRESETS, orbitCamera, panCamera, zoomCamera } from './simulatorCamera';

type SimulatorStatus = CameraStatus & {
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

export default function LiveSimulator({ api, job, standalone = false }: { api: string; job: CurrentJob | null; standalone?: boolean }) {
  const [status, setStatus] = useState<SimulatorStatus | null>(null);
  const [frame, setFrame] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState('');
  const [dragging, setDragging] = useState(false);
  const lastReceived = useRef(0);
  const panel = useRef<HTMLElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const pointer = useRef<{ id: number; x: number; y: number; pan: boolean } | null>(null);
  const { changeCamera, state: cameraState, error: cameraError } = useSimulatorCamera(api, status);
  const cameraAvailable = connected && !!status?.camera;

  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === panel.current);
    document.addEventListener('fullscreenchange', update);
    return () => document.removeEventListener('fullscreenchange', update);
  }, []);

  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    function onWheel(event: WheelEvent) {
      if (!cameraAvailable) return;
      event.preventDefault();
      // DOM_DELTA_LINE and DOM_DELTA_PAGE need conversion on Firefox/mice.
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element!.clientHeight : 1);
      changeCamera(current => zoomCamera(current, delta));
    }
    element.addEventListener('wheel', onWheel, { passive: false });
    return () => element.removeEventListener('wheel', onWheel);
  }, [cameraAvailable, changeCamera]);

  function beginDrag(event: PointerEvent<HTMLDivElement>) {
    if (!cameraAvailable || pointer.current || ![0, 1, 2].includes(event.button)) return;
    event.preventDefault();
    event.currentTarget.focus({ preventScroll: true });
    event.currentTarget.setPointerCapture(event.pointerId);
    pointer.current = { id: event.pointerId, x: event.clientX, y: event.clientY, pan: event.shiftKey || event.button !== 0 };
    setDragging(true);
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    const previous = pointer.current;
    if (!previous || previous.id !== event.pointerId || !cameraAvailable) return;
    const dx = event.clientX - previous.x;
    const dy = event.clientY - previous.y;
    if (!dx && !dy) return;
    changeCamera(current => previous.pan || event.shiftKey ? panCamera(current, dx, dy, event.currentTarget.clientHeight) : orbitCamera(current, dx, dy));
    pointer.current = { ...previous, x: event.clientX, y: event.clientY };
  }

  function endDrag(event: PointerEvent<HTMLDivElement>) {
    if (pointer.current?.id !== event.pointerId) return;
    pointer.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  async function toggleFullscreen() {
    setFullscreenError('');
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (panel.current?.requestFullscreen) await panel.current.requestFullscreen();
      else throw new Error('unsupported');
    } catch {
      setFullscreenError('This browser cannot enter fullscreen. Use “Open separate viewer” for a larger view.');
    }
  }

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

  return <section ref={panel} id="live-simulator" className={`studio-panel simulator-panel ${standalone ? 'simulator-standalone' : ''}`} aria-label="Live Isaac Sim robot camera">
    <div className="simulator-heading">
      <div><span className="simulator-icon"><Video size={19} strokeWidth={1.5} /></span><div><h2>The robot studio</h2><p>Explore the actual Isaac Sim camera while the robot draws.</p></div></div>
      <span className={`live-badge ${connected ? 'is-live' : ''}`} role="status">{connected ? <Radio size={13} /> : <WifiOff size={13} />}{label}</span>
    </div>
    <div className="simulator-controls" aria-label="Simulator camera controls">
      <div className="camera-presets">{Object.entries(CAMERA_PRESETS).map(([name, camera]) => <button key={name} type="button" onClick={() => changeCamera(camera)} disabled={!cameraAvailable}>{name}</button>)}</div>
      <div className="camera-actions">
        <button type="button" onClick={() => changeCamera(current => zoomCamera(current, -100))} disabled={!cameraAvailable} aria-label="Zoom into Isaac Sim" title="Zoom in"><Plus size={16} /></button>
        <button type="button" onClick={() => changeCamera(current => zoomCamera(current, 100))} disabled={!cameraAvailable} aria-label="Zoom out of Isaac Sim" title="Zoom out"><Minus size={16} /></button>
        <button type="button" onClick={() => changeCamera(CAMERA_PRESETS['Whole scene'])} disabled={!cameraAvailable} aria-label="Reset Isaac Sim camera" title="Reset camera"><RotateCcw size={15} /></button>
        <button type="button" onClick={() => void toggleFullscreen()} aria-label={fullscreen ? 'Exit fullscreen' : 'View Isaac Sim in fullscreen'} title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}>{fullscreen ? <Minimize size={15} /> : <Maximize size={15} />}</button>
        {!standalone && <a className="separate-viewer" href={`${api}/sim/view`} target="_blank" rel="noreferrer" title="Open interactive Isaac Sim in a separate browser tab"><ExternalLink size={14} /><span>Open separate viewer</span></a>}
      </div>
    </div>
    <div ref={viewport} className={`simulator-camera ${cameraAvailable ? 'can-interact' : ''} ${dragging ? 'is-dragging' : ''}`} tabIndex={cameraAvailable ? 0 : -1} role="group" aria-label="Interactive Isaac Sim camera" aria-describedby="camera-gesture-help" onPointerDown={beginDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={endDrag} onContextMenu={event => event.preventDefault()} onKeyDown={event => {
      if (!cameraAvailable) return;
      if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
        event.preventDefault();
        const dx = event.key === 'ArrowLeft' ? -15 : event.key === 'ArrowRight' ? 15 : 0;
        const dy = event.key === 'ArrowUp' ? -15 : event.key === 'ArrowDown' ? 15 : 0;
        changeCamera(current => event.shiftKey ? panCamera(current, dx, dy, event.currentTarget.clientHeight) : orbitCamera(current, dx, dy));
      } else if (['+', '=', '-'].includes(event.key)) {
        event.preventDefault();
        changeCamera(current => zoomCamera(current, event.key === '-' ? 100 : -100));
      } else if (event.key.toLowerCase() === 'r') changeCamera(CAMERA_PRESETS['Whole scene']);
    }}>
      {frame ? <img src={frame} draggable={false} className={`simulator-frame ${connected ? '' : 'is-stale'}`} alt={marker ? 'Actual Isaac Sim camera showing marker fallback drawing' : 'Actual Isaac Sim camera showing the SO-101 arm and drawing surface'} />
        : <div className="simulator-empty"><Video size={34} strokeWidth={1.2} /><h3>{connecting ? 'Connecting to the robot…' : 'Waiting for Isaac Sim'}</h3><p>The live robot camera appears here when the simulator is running.</p></div>}
      {frame && !connected && <span className="stale-frame-note"><WifiOff size={14} />Last received frame · live camera disconnected</span>}
      {connected && <span className="camera-source">ISAAC SIM CAMERA</span>}
    </div>
    <div className="camera-help"><span id="camera-gesture-help">Drag to orbit · scroll to zoom · Shift-drag to pan<span className="sr-only">. Arrow keys orbit, Shift with arrow keys pans, plus and minus zoom, R resets the camera.</span></span><span role="status">{cameraState === 'sending' || cameraState === 'waiting' ? 'Moving simulator camera…' : cameraAvailable ? 'Camera changes are shared live' : 'Camera controls connect with Isaac Sim'}</span></div>
    <div className="simulator-footer"><span>{marker ? 'Marker fallback · no robot arm control' : status?.mode === 'robot' ? 'SO-101 · robot simulation' : 'Actual simulator camera'}</span><span aria-live="polite" className={currentJob?.state === 'running' || (status?.state === 'running' && connected) ? 'drawing-now' : ''}>{progress}</span></div>
    {currentJob && ['queued', 'running'].includes(currentJob.state) && <progress className="simulator-job-progress" value={currentJob.stroke} max={currentJob.total || 1} aria-label="Your portrait drawing progress" />}
    {status?.error && <p className="simulator-error" role="alert"><AlertCircle size={15} />{status.error}</p>}
    {job?.error && job.error !== status?.error && <p className="simulator-error" role="alert"><AlertCircle size={15} />{job.error}</p>}
    {cameraError && <p className="simulator-error" role="alert"><AlertCircle size={15} />{cameraError}</p>}
    {fullscreenError && <p className="simulator-error" role="alert"><AlertCircle size={15} />{fullscreenError}</p>}
  </section>;
}
