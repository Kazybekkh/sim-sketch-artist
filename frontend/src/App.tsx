import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, Camera, Check, ChevronDown, CircleHelp, ImagePlus, LoaderCircle, PenLine, RefreshCw, Settings2, Sparkles, Upload, VideoOff, X } from 'lucide-react';
import LiveSimulator from './LiveSimulator';
import { API_STORAGE, initialApi } from './apiConfig';

type Point = [number, number];
type Portrait = { title: string; strokes: Point[][]; preview_url?: string };
type JobStatus = { state: 'queued' | 'running' | 'done' | 'error'; stroke: number; total: number; error: string | null };
type Phase = 'idle' | 'generating' | 'submitting' | 'queued' | 'running' | 'done' | 'error' | 'poll_error';
type Photo = { blob: Blob; url: string; name: string };

const SAMPLE: Portrait = {
  title: 'Sample smiley',
  strokes: [
    Array.from({ length: 25 }, (_, i) => [0.5 + 0.32 * Math.cos(i * Math.PI / 12), 0.5 + 0.32 * Math.sin(i * Math.PI / 12)] as Point),
    [[0.36, 0.4], [0.39, 0.37], [0.42, 0.4]],
    [[0.58, 0.4], [0.61, 0.37], [0.64, 0.4]],
    [[0.34, 0.57], [0.38, 0.63], [0.44, 0.67], [0.5, 0.68], [0.56, 0.67], [0.62, 0.63], [0.66, 0.57]],
  ],
};

function apiUrl(base: string, path: string) { return `${base}${path}`; }

async function request<T>(url: string, options: RequestInit = {}, timeout = 120_000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) {
      let message = `The studio returned an error (${response.status}).`;
      try {
        const body = await response.json();
        if (typeof body.detail === 'string') message = body.detail;
        else if (typeof body.error === 'string') message = body.error;
        else if (Array.isArray(body.detail)) message = body.detail.map((item: { msg?: string }) => item.msg ?? 'Invalid request').join('. ');
      } catch { /* Keep the useful HTTP error. */ }
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('The studio took too long to respond. Check the Ubuntu backend and your connection.');
    if (error instanceof TypeError) throw new Error('Cannot reach the studio. Check the API address in Connection settings and make sure the backend is running.');
    throw error;
  } finally { window.clearTimeout(timer); }
}

function StrokeCanvas({ portrait }: { portrait: Portrait }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const size = 1000;
    const total = portrait.strokes.reduce((sum, stroke) => sum + stroke.length, 0);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const duration = reducedMotion ? 0 : Math.min(6500, Math.max(1400, total * 22));
    let frame = 0;
    const started = performance.now();
    function paint(now: number) {
      if (!context) return;
      const fraction = duration ? Math.min(1, (now - started) / duration) : 1;
      let budget = Math.ceil(total * fraction);
      context.clearRect(0, 0, size, size);
      context.strokeStyle = '#343a32';
      context.lineWidth = 3;
      context.lineCap = 'round';
      context.lineJoin = 'round';
      for (const stroke of portrait.strokes) {
        if (!budget || !stroke.length) break;
        context.beginPath();
        context.moveTo(stroke[0][0] * size, stroke[0][1] * size);
        const count = Math.min(stroke.length, budget);
        for (let i = 1; i < count; i++) context.lineTo(stroke[i][0] * size, stroke[i][1] * size);
        context.stroke();
        budget -= count;
      }
      if (fraction < 1) frame = requestAnimationFrame(paint);
    }
    frame = requestAnimationFrame(paint);
    return () => cancelAnimationFrame(frame);
  }, [portrait]);
  return <canvas ref={canvas} width={1000} height={1000} className="stroke-canvas" role="img" aria-label={`Stroke preview: ${portrait.title}`} />;
}

function EmptyDrawing() {
  return <svg className="empty-drawing" viewBox="0 0 240 240" fill="none" aria-hidden="true">
    <path d="M65 205C72 184 91 175 105 174M141 174C161 178 176 188 182 205M91 150L92 171C103 183 132 184 146 170L147 145" />
    <path d="M77 105C70 73 86 47 112 44C135 34 167 57 164 91L158 125C153 151 137 166 120 167C99 166 84 146 80 120C68 122 66 103 73 100L81 102" />
    <path d="M80 98C93 92 102 75 105 67C118 88 144 91 161 92M91 111C96 107 102 107 107 110M133 109C138 105 144 107 148 110M121 108L114 130L123 133M105 146C114 151 125 151 137 143" />
    <path d="M101 116L100 119M139 115L139 118M91 56C70 61 60 83 66 107M122 39C150 36 177 60 172 92" />
    <path className="accent-line" d="M45 155L50 144M39 148L57 152M185 45L184 60M177 51L192 53" />
  </svg>;
}

export default function App() {
  const [api, setApi] = useState(initialApi);
  const [apiDraft, setApiDraft] = useState(api);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsError, setSettingsError] = useState('');
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [astraConfigured, setAstraConfigured] = useState<boolean | null>(null);
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [portrait, setPortrait] = useState<Portrait | null>(null);
  const [samplePortrait, setSamplePortrait] = useState(false);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [queueStarted, setQueueStarted] = useState(0);
  const [longWait, setLongWait] = useState(false);
  const [pollRevision, setPollRevision] = useState(0);
  const [resultError, setResultError] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const mounted = useRef(true);
  const busy = ['generating', 'submitting', 'queued', 'running'].includes(phase);
  const operationPending = busy || phase === 'poll_error';

  const stopCamera = useCallback(() => {
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    setCameraOn(false);
    setCameraReady(false);
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      stream.current?.getTracks().forEach(track => track.stop());
    };
  }, []);
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => { if (cameraOn && video.current) video.current.srcObject = stream.current; }, [cameraOn]);

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const readiness = await request<{ astra_configured: boolean }>(apiUrl(api, '/ready'), {}, 8000);
        if (active) { setReachable(true); setAstraConfigured(readiness.astra_configured); }
      } catch { if (active) setReachable(false); }
    }
    setReachable(null);
    setAstraConfigured(null);
    void check();
    const interval = window.setInterval(check, 15_000);
    return () => { active = false; window.clearInterval(interval); };
  }, [api]);

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer = 0;
    async function poll() {
      try {
        const next = await request<JobStatus>(apiUrl(api, `/status/${encodeURIComponent(jobId!)}`), {}, 15_000);
        if (!active) return;
        setStatus(next);
        if (next.state === 'done') { setPhase('done'); return; }
        if (next.state === 'error') { setPhase('error'); setError(next.error || 'Isaac Sim could not finish this sketch. Check the simulator and try again.'); return; }
        setPhase(next.state === 'running' ? 'running' : 'queued');
        setLongWait(next.state === 'queued' && Date.now() - queueStarted > 120_000);
        timer = window.setTimeout(poll, 1000);
      } catch (cause) {
        if (!active) return;
        setPhase('poll_error');
        setError(`${cause instanceof Error ? cause.message : 'Unable to check drawing progress.'} Your drawing may still be queued or running.`);
      }
    }
    void poll();
    return () => { active = false; window.clearTimeout(timer); };
  }, [jobId, api, pollRevision, queueStarted]);

  async function enableCamera() {
    setError('');
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Camera access needs HTTPS or localhost. Open this studio through an HTTPS address on your Mac, or upload a photo.');
      return;
    }
    setCameraLoading(true);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 1280 } }, audio: false });
      if (!mounted.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current?.getTracks().forEach(track => track.stop());
      stream.current = media;
      setCameraOn(true);
    } catch (cause) {
      const name = cause instanceof DOMException ? cause.name : '';
      setError(name === 'NotAllowedError' ? 'Camera access was denied. Allow camera access in your browser settings, or upload a photo.' : name === 'NotFoundError' ? 'No camera was found. You can upload a photo instead.' : 'Could not open your camera. Check that another app is not using it, or upload a photo.');
    } finally { if (mounted.current) setCameraLoading(false); }
  }

  function setNewPhoto(blob: Blob, name: string) {
    setPhoto({ blob, url: URL.createObjectURL(blob), name });
    setPortrait(null);
    setJobId(null);
    setStatus(null);
    setPhase('idle');
    setError('');
    setResultError(false);
    stopCamera();
  }

  function capture() {
    if (!video.current || !cameraReady) return;
    const source = video.current;
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1600 / Math.max(source.videoWidth, source.videoHeight));
    canvas.width = Math.round(source.videoWidth * scale);
    canvas.height = Math.round(source.videoHeight * scale);
    canvas.getContext('2d')!.drawImage(source, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => { if (blob && mounted.current) setNewPhoto(blob, 'webcam-portrait.jpg'); }, 'image/jpeg', 0.92);
  }

  function upload(file: File | undefined) {
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Choose a JPG, PNG, or WebP photo.'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('Choose a photo no larger than 10 MB.'); return; }
    setNewPhoto(file, file.name);
  }

  async function draw(nextPortrait: Portrait) {
    setPhase('submitting');
    const job = await request<{ job_id: string }>(apiUrl(api, '/draw'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: nextPortrait.title, strokes: nextPortrait.strokes }),
    });
    if (!mounted.current) return;
    setQueueStarted(Date.now());
    setLongWait(false);
    setStatus({ state: 'queued', stroke: 0, total: nextPortrait.strokes.length, error: null });
    setJobId(job.job_id);
    setPhase('queued');
    document.getElementById('live-simulator')?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'start',
    });
  }

  async function sketch(sample = false, redraw = false) {
    if (operationPending || (!photo && !sample && !redraw)) return;
    setError('');
    setJobId(null);
    setStatus(null);
    setResultError(false);
    if (!redraw) setSamplePortrait(sample);
    stopCamera();
    try {
      let next = sample ? SAMPLE : redraw ? portrait : null;
      if (!next) {
        setPhase('generating');
        setPortrait(null);
        const form = new FormData();
        form.append('image', photo!.blob, photo!.name);
        const response = await request<Portrait>(apiUrl(api, '/portrait'), { method: 'POST', body: form }, 420_000);
        next = { ...response, title: response.title || 'Your portrait' };
      }
      if (!mounted.current) return;
      setPortrait(next);
      await draw(next);
    } catch (cause) {
      if (!mounted.current) return;
      setPhase('error');
      setError(cause instanceof Error ? cause.message : 'Something went wrong. Please try again.');
    }
  }

  function saveConnection() {
    const value = apiDraft.trim().replace(/\/+$/, '');
    if (value) {
      try {
        const url = new URL(value);
        const localhost = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
        if (url.protocol !== 'https:' && !(url.protocol === 'http:' && localhost)) throw new Error();
        if (url.username || url.password || url.search || url.hash) throw new Error();
      } catch { setSettingsError('Use an HTTPS URL, or http://localhost for local development. Do not include credentials or query parameters.'); return; }
    }
    try { localStorage.setItem(API_STORAGE, value); } catch { /* The connection still works for this session. */ }
    setApi(value);
    setApiDraft(value);
    setSettingsError('');
    setError('');
  }

  const progress = status?.total ? Math.max(0, Math.min(100, (status.stroke / status.total) * 100)) : 0;
  const statusTitle = phase === 'generating' ? 'Astra is finding your lines' : phase === 'submitting' ? 'Sending your sketch to the studio' : phase === 'queued' ? 'Waiting for Isaac Sim' : phase === 'running' ? 'Your robot is drawing' : phase === 'done' ? 'A little likeness. Made by a robot.' : phase === 'poll_error' ? 'Connection interrupted' : phase === 'error' ? 'Let’s give that another try' : astraConfigured === false ? 'Your studio needs Astra connected' : 'Your portrait begins with a photo';
  const resultUrl = jobId ? apiUrl(api, `/result/${encodeURIComponent(jobId)}`) : '';

  return <div className="app-shell">
    <header className="site-header">
      <a className="brand" href="#" aria-label="Sim Sketch studio"><span className="brand-mark"><PenLine size={22} strokeWidth={1.8} /></span><span>sim<span className="brand-slash">/</span>sketch<span className="brand-label">THE ROBOT PORTRAIT STUDIO</span></span></a>
      <button className="connection-pill" onClick={() => setSettingsOpen(!settingsOpen)} aria-expanded={settingsOpen} aria-controls="connection-settings"><span className={`connection-dot ${reachable === true ? 'online' : reachable === false ? 'offline' : ''}`} />{reachable === true ? 'API reachable' : reachable === false ? 'Connect your studio' : 'Checking studio'}<Settings2 size={14} /></button>
    </header>

    <main>
      <section className="intro">
        <div><div className="eyebrow"><span />A SMALL EXPERIMENT IN HUMAN + MACHINE</div><h1>You. In a few<br /><span>beautiful lines.</span></h1><p>A photo of you. A little Astra imagination.<br className="desktop-break" /> A real sketch, drawn inside Isaac Sim.</p></div>
        <div className="intro-note"><svg width="76" height="68" viewBox="0 0 76 68" fill="none" aria-hidden="true"><path d="M12 14C40 2 68 18 55 36C45 48 26 29 42 23C68 13 71 54 21 57M21 57L33 48M21 57L35 63" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg><span>One photo.<br />Your own robot artist.</span></div>
      </section>

      <LiveSimulator api={api} job={jobId && status ? { id: jobId, ...status } : null} />

      <section className="workspace" aria-label="Portrait studio">
        <div className="studio-panel photo-panel">
          <div className="panel-heading"><div><span className="step-number">01</span><h2>The inspiration</h2></div><span className="panel-tag">YOUR PHOTO</span></div>
          <div className={`photo-stage ${photo || cameraOn ? 'has-photo' : ''}`}>
            {cameraOn ? <><video ref={video} autoPlay playsInline muted onLoadedData={() => setCameraReady(true)} className="camera-video" /><span className="viewfinder-corner top-left" /><span className="viewfinder-corner top-right" /><span className="viewfinder-corner bottom-left" /><span className="viewfinder-corner bottom-right" /><div className="camera-guidance">Find your light. Be yourself.</div><button className="close-camera" onClick={stopCamera} aria-label="Close camera"><X size={18} /></button></> : photo ? <><img className="photo-preview" src={photo.url} alt="Your selected portrait" /><span className="photo-badge"><Check size={13} />Ready for your close-up</span><button className="close-camera" disabled={operationPending} onClick={() => { setPhoto(null); setPortrait(null); setPhase('idle'); setJobId(null); }} aria-label="Remove photo"><X size={18} /></button></> : <div className="camera-empty"><div className="camera-icon"><Camera size={31} strokeWidth={1.35} /><span className="tiny-spark">✦</span></div><h3>Make yourself the muse.</h3><p>Find a little light, look this way,<br />and let the robot do the rest.</p><button className="button dark" onClick={enableCamera} disabled={cameraLoading || operationPending}>{cameraLoading ? <LoaderCircle className="spin" size={16} /> : <Camera size={16} />}{cameraLoading ? 'Opening camera…' : 'Enable camera'}</button><span className="camera-privacy">Your camera opens only when you choose.</span></div>}
          </div>
          <div className="photo-toolbar">
            <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-label="Upload a portrait" onChange={event => { upload(event.target.files?.[0]); event.target.value = ''; }} />
            {cameraOn ? <><button className="button capture" onClick={capture} disabled={!cameraReady}><span className="shutter" />Capture photo</button><button className="icon-button" onClick={stopCamera} aria-label="Turn camera off"><VideoOff size={19} /></button></> : <><button className="text-button" onClick={() => input.current?.click()} disabled={operationPending}><Upload size={16} />{photo ? 'Change photo' : 'Or upload a photo'}</button>{photo ? <button className="text-button muted" onClick={enableCamera} disabled={operationPending || cameraLoading}><RefreshCw size={14} />Retake</button> : <span className="file-hint">JPG, PNG, WEBP</span>}</>}
          </div>
        </div>

        <div className="studio-panel drawing-panel">
          <div className="panel-heading"><div><span className="step-number">02</span><h2>The interpretation</h2></div><span className={`panel-tag ${phase === 'done' ? 'complete-tag' : ''}`}>{phase === 'done' ? 'ROBOT RESULT' : portrait ? 'STROKE PREVIEW' : 'THE CANVAS'}</span></div>
          <div className={`drawing-stage ${portrait ? 'has-drawing' : ''}`}>
            <div className="paper-corner corner-one" /><div className="paper-corner corner-two" />
            {phase === 'done' && !resultError ? <img className="result-image" src={resultUrl} alt="Completed sketch rendered from the robot's recorded pen trail" onError={() => setResultError(true)} /> : portrait ? <StrokeCanvas portrait={portrait} /> : <div className={`drawing-empty ${phase === 'generating' ? 'thinking' : ''}`}><EmptyDrawing /><span>{phase === 'generating' ? 'Finding the lines that make you, you…' : 'A blank page. A thousand possibilities.'}</span>{phase === 'generating' && <span className="generating-indicator"><LoaderCircle size={15} className="spin" />Astra is sketching your portrait</span>}</div>}
            {portrait && <div className="drawing-caption"><span>{portrait.title}</span><span>{portrait.strokes.length} strokes</span></div>}
          </div>
          <div className="drawing-toolbar"><span className="tiny-ink-dot" /><span>{phase === 'done' ? resultError ? 'Result image unavailable. Showing planned strokes.' : 'Drawn from the recorded simulator pen trail' : portrait ? samplePortrait ? 'Sample strokes · simulator result follows' : 'Astra’s planned strokes · simulator result follows' : 'Astra imagines. Isaac Sim brings it to life.'}</span>{phase === 'done' && <a className="icon-button" href={resultUrl} target="_blank" rel="noreferrer" aria-label="Open the completed robot sketch"><ArrowDownToLine size={18} /></a>}</div>
        </div>
      </section>

      <section className="action-strip" aria-label="Sketch controls">
        <div className="action-copy" aria-live="polite"><div className={`status-icon ${phase === 'done' ? 'success' : ''}`}>{busy ? <LoaderCircle size={20} className="spin" /> : phase === 'done' ? <Check size={20} /> : <Sparkles size={20} strokeWidth={1.5} />}</div><div><h3>{statusTitle}</h3><p>{phase === 'generating' ? 'Turning your photo into a simple line portrait.' : phase === 'submitting' ? 'Adding your strokes to the drawing queue.' : phase === 'queued' ? longWait ? 'Still queued. Start the Isaac Sim watcher on your Ubuntu machine.' : 'Your strokes are queued for the simulator on Ubuntu.' : phase === 'running' ? `Drawing stroke ${status?.stroke ?? 0} of ${status?.total ?? portrait?.strokes.length ?? 0}.` : phase === 'done' ? 'Your finished sketch is ready above.' : phase === 'poll_error' ? 'Resume checking this drawing when the connection is back.' : phase === 'error' ? 'Check the message below, then retry when you’re ready.' : astraConfigured === false ? 'Configure Astra on Ubuntu to create portraits, or try sample strokes below.' : photo ? 'All set. Let’s turn this moment into a sketch.' : 'Use your webcam or choose a photo to get started.'}</p>{phase === 'running' && <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)} aria-label="Robot drawing progress"><span style={{ width: `${progress}%` }} /></div>}</div></div>
        {phase === 'poll_error' ? <button className="button primary" onClick={() => { setError(''); setPhase('queued'); setPollRevision(value => value + 1); }}><RefreshCw size={17} />Resume checking</button> : phase === 'done' || (phase === 'error' && portrait) ? <button className="button primary" onClick={() => void sketch(false, true)}><RefreshCw size={17} />Draw again</button> : <button className="button primary" onClick={() => void sketch()} disabled={!photo || operationPending || astraConfigured === false}>{busy ? <LoaderCircle className="spin" size={18} /> : <PenLine size={18} />}{busy ? phase === 'generating' ? 'Imagining…' : phase === 'running' ? 'Drawing…' : 'In the queue…' : 'Sketch me'}{!busy && <ArrowRight size={18} />}</button>}
      </section>
      {error && <div className="error-message" role="alert"><CircleHelp size={19} /><p>{error}</p><button onClick={() => setError('')} className="icon-button" aria-label="Dismiss message"><X size={17} /></button></div>}

      <section className="how-it-works" aria-label="How it works"><div><span className="process-icon"><Camera size={18} strokeWidth={1.5} /></span><p><strong>A moment from you</strong><span>A webcam photo or upload</span></p></div><ArrowRight className="process-arrow" size={18} /><div><span className="process-icon"><Sparkles size={18} strokeWidth={1.5} /></span><p><strong>A few lines from Astra</strong><span>Your likeness, simplified</span></p></div><ArrowRight className="process-arrow" size={18} /><div><span className="process-icon"><PenLine size={18} strokeWidth={1.5} /></span><p><strong>A sketch from Isaac Sim</strong><span>Every stroke drawn in simulation</span></p></div></section>

      <div className="settings-section" id="connection-settings"><button className="settings-toggle" aria-expanded={settingsOpen} aria-controls="settings-content" onClick={() => setSettingsOpen(!settingsOpen)}><Settings2 size={14} />Connection settings<ChevronDown size={14} className={settingsOpen ? 'rotate' : ''} /></button><button className="sample-button" onClick={() => void sketch(true)} disabled={operationPending}><ImagePlus size={14} />Try sample strokes</button></div>
      {settingsOpen && <section className="settings-panel" id="settings-content"><label htmlFor="api-url">Ubuntu studio API address</label><p>On your Mac, paste the HTTPS tunnel URL connected to the Ubuntu backend. Leave blank when this page is served by the backend.</p><div className="settings-form"><input id="api-url" type="url" placeholder="https://your-studio-tunnel.example.com" value={apiDraft} onChange={event => setApiDraft(event.target.value)} disabled={busy} autoCapitalize="off" autoCorrect="off" spellCheck={false} /><button className="button dark" onClick={saveConnection} disabled={busy}>Save connection</button></div>{settingsError && <p className="settings-error" role="alert">{settingsError}</p>}<span className="settings-note">{api ? `Current API: ${api}` : 'Current API: same address as this page'} · Saved only in this browser.<br />Sample strokes send a real drawing job to Isaac Sim, without calling Astra.</span></section>}
    </main>

    <footer><span>SIM / SKETCH</span><p>A little human. A little machine. Entirely you.</p><span>MADE OF LINES & CURIOSITY</span></footer>
  </div>;
}
