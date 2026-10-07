import { useEffect, useState } from 'react';
import { Check, ChevronDown, Circle, ExternalLink, Link2, LoaderCircle, PlugZap, RefreshCw, Server, Unplug, Video } from 'lucide-react';
import type useStudioConnection from './useStudioConnection';

type Props = ReturnType<typeof useStudioConnection> & { locked?: boolean; onEndpointChange?: () => void };
const GUIDE = 'https://github.com/Kazybekkh/sim-sketch-artist/blob/main/docs/self-hosting.md';
const labels = { disconnected: 'Connect your Isaac Sim', checking: 'Checking your setup…', unreachable: 'Backend unreachable', wrong_service: 'Check the backend address', sim_unreachable: 'Simulator status unavailable', sim_offline: 'Isaac Sim is not active', sim_error: 'Isaac Sim needs attention', astra_missing: 'Add your model credentials', ready: 'Your studio is connected' };

export default function ConnectionSetup({ connection, connect, disconnect, check, locked = false, onEndpointChange }: Props) {
  const [draft, setDraft] = useState(connection.endpoint ?? '');
  const [inputError, setInputError] = useState('');
  useEffect(() => { setDraft(connection.endpoint ?? ''); }, [connection.endpoint]);
  const checking = connection.state === 'checking';
  const ready = connection.state === 'ready';
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (locked || checking) return;
    setInputError('');
    try {
      await connect(draft);
      onEndpointChange?.();
    } catch (cause) { setInputError(cause instanceof Error ? cause.message : 'Check the backend address.'); }
  }
  return <section className={`connection-setup ${ready ? 'connection-ready' : ''}`} id="connection-settings" aria-labelledby="connection-title">
    <div className="connection-heading"><div className="connection-symbol">{ready ? <Check size={23} /> : <PlugZap size={23} />}</div><div><span className="connection-eyebrow">YOUR GPU · YOUR MODEL ACCOUNT</span><h2 id="connection-title">{labels[connection.state]}</h2></div><span className={`live-badge ${ready ? 'is-live' : ''}`}>{checking ? <LoaderCircle size={13} className="spin" /> : ready ? <Check size={13} /> : <Link2 size={13} />}{ready ? 'Ready to sketch' : checking ? 'Checking' : 'Setup required'}</span></div>
    <p className="connection-description">This app draws on your own Isaac Sim machine. Keep the Sim Sketch backend and its Isaac Sim drawing worker running, then connect their backend address here.</p>
    <div className="connection-checks" aria-label="Connection checklist">{[
      ['Backend', connection.backend], ['Isaac Sim robot', connection.simulatorOnline], ['Model configured', connection.astraConfigured === true],
    ].map(([title, okay]) => <span key={String(title)} className={okay ? 'check-passed' : ''}>{okay ? <Check size={13} /> : <Circle size={11} />}{title}</span>)}</div>
    <p className="connection-status" role="status">{connection.message || 'Checking backend identity, simulator activity and model configuration…'}</p>
    <form className="connection-form" onSubmit={event => void submit(event)}>
      <label htmlFor="studio-endpoint">Your Sim Sketch backend URL</label>
      <div><input id="studio-endpoint" type="url" placeholder="https://your-gpu-backend.example.com" value={draft} onChange={event => { setDraft(event.target.value); setInputError(''); }} required disabled={locked || checking} autoCapitalize="off" autoCorrect="off" spellCheck={false} aria-describedby="connection-address-help" /><button className="button dark" type="submit" disabled={locked || checking || !draft.trim()}>{checking ? <LoaderCircle size={15} className="spin" /> : <Link2 size={15} />}{connection.endpoint ? 'Change connection' : 'Connect'}</button></div>
      <small id="connection-address-help">Use the backend root URL, not a WebRTC, CloudXR or SSH address. Saved only in this browser. Never paste an API key here.</small>
    </form>
    {inputError && <p className="connection-input-error" role="alert">{inputError}</p>}
    <div className="connection-links">{connection.endpoint && <><button type="button" className="text-button" onClick={() => void check()} disabled={checking}><RefreshCw size={14} />Recheck connection</button><button type="button" className="text-button muted" disabled={locked || checking} onClick={() => { disconnect(); onEndpointChange?.(); }}><Unplug size={14} />Disconnect</button></>}<a href={GUIDE} target="_blank" rel="noreferrer">Full setup guide<ExternalLink size={12} /></a></div>
    {locked && <p className="connection-locked">A drawing request is in progress. Keep this address until it finishes. If connection is lost, your photo and drawing are retained; recheck and resume the same job.</p>}
    <details className="connection-instructions"><summary><Server size={15} />First time? Start your own studio<ChevronDown size={14} /></summary><div className="setup-steps"><div><span>1</span><h3>Prepare your GPU machine</h3><p>Install Isaac Sim and this project on your own compatible NVIDIA GPU machine or cloud instance. Set your model ID and API key in its local <code>.env</code>. Your API account and GPU account cover usage; this site provides neither.</p></div><div><span>2</span><h3>Start both processes</h3><p>From the project directory, keep these commands running in separate terminals:</p><pre><code>./scripts/backend.sh{'\n'}./scripts/sim.sh --headless</code></pre><p>The worker starts this project’s SO-101 drawing scene. It cannot connect to an arbitrary Isaac Sim scene.</p></div><div><span>3</span><h3>Connect from your browser</h3><p>Use your own HTTPS backend gateway, with access restricted to authorized users. Paste its root URL above. The live viewer appears once the worker is active.</p></div></div><details className="ssh-instructions"><summary>Using SSH from a Mac or another computer?</summary><p>SSH runs in your terminal. With existing SSH access to your GPU machine, create a private port forward:</p><pre><code>ssh -N -L 8000:127.0.0.1:8000 your-user@your-gpu-host</code></pre><p>Keep that terminal open, then open <a href="http://localhost:8000" target="_blank" rel="noreferrer">http://localhost:8000</a> in a new tab. That serves the bundled studio through your private connection. This hosted app requires an HTTPS backend URL; use the local studio tab for an HTTP port forward.</p></details><p className="configuration-note"><Video size={14} />“Model configured” checks backend settings only. Your account’s model access is checked when you request a portrait. Connection checks do not generate images or start a drawing.</p></details>
  </section>;
}
