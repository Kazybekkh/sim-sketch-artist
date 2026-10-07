/** Read-only discovery for an operator-owned Sim Sketch backend. No paid calls. */
export type ConnectionState = 'disconnected' | 'checking' | 'unreachable' | 'wrong_service' | 'sim_unreachable' | 'sim_offline' | 'sim_error' | 'astra_missing' | 'ready';
export type StudioConnection = {
  state: ConnectionState;
  endpoint: string | null;
  backend: boolean;
  astraConfigured: boolean | null;
  simulatorOnline: boolean;
  message: string;
};
export const disconnectedConnection = (): StudioConnection => ({
  state: 'disconnected', endpoint: null, backend: false, astraConfigured: null,
  simulatorOnline: false, message: 'Connect your own running simulator to begin.',
});

export function normalizeEndpoint(value: string, pageProtocol: string): string {
  let url: URL;
  try { url = new URL(value.trim()); } catch { throw new Error('Paste the full HTTPS address of your Sim Sketch backend.'); }
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback && pageProtocol === 'http:')) {
    throw new Error('Use an HTTPS backend address. For a private SSH connection, open http://localhost:8000 directly in a new tab.');
  }
  if (url.username || url.password || url.search || url.hash) throw new Error('Use the backend root URL, without credentials, query parameters or a fragment.');
  if (url.pathname !== '/') throw new Error('Paste the backend root address, without /sim/view or another path.');
  return url.origin;
}

export function classifyStudio(endpoint: string, readiness: unknown, simulation: unknown): StudioConnection {
  const base: StudioConnection = { ...disconnectedConnection(), endpoint };
  if (!readiness || typeof readiness !== 'object') return { ...base, state: 'wrong_service', message: 'This address does not identify a Sim Sketch backend.' };
  const ready = readiness as Record<string, unknown>;
  if (ready.service !== 'sim-sketch-artist' || ready.protocol_version !== 1 || ready.ok !== true || typeof ready.astra_configured !== 'boolean') {
    return { ...base, state: 'wrong_service', message: 'This is not a compatible Sim Sketch backend. Use the backend root URL and update the project if needed.' };
  }
  base.backend = true;
  base.astraConfigured = ready.astra_configured;
  const sim = simulation && typeof simulation === 'object' ? simulation as Record<string, unknown> : {};
  if (typeof sim.online !== 'boolean' || !['idle', 'running', 'error'].includes(String(sim.state))) return { ...base, state: 'sim_unreachable', message: 'Your backend is connected, but its simulator status could not be read. Check backend logs and gateway access to /sim/status, then retry.' };
  // The backend validates frame and worker freshness using its own clock.
  // Comparing its timestamp with the browser clock breaks healthy remote hosts.
  const timestampValid = typeof sim.updated_at === 'number' && Number.isFinite(sim.updated_at) && sim.updated_at > 0;
  base.simulatorOnline = sim.online === true && sim.mode === 'robot' && timestampValid && ['idle', 'running'].includes(String(sim.state));
  const simulatorError = typeof sim.error === 'string' && sim.error.trim() ? `Isaac Sim: ${sim.error.trim().slice(0, 1000)} Fix the error, restart the drawing worker, then recheck the connection.` : 'The simulator reported an error. Check its terminal, fix the error, restart the drawing worker, then recheck the connection.';
  if (!base.simulatorOnline) return { ...base, state: sim.state === 'error' ? 'sim_error' : 'sim_offline', message: sim.state === 'error' ? simulatorError : sim.mode === 'marker' ? 'The worker is in marker mode. Start it in robot mode to draw with the SO-101 arm.' : 'Your backend is connected. Start the Isaac Sim drawing worker on the same machine; its live camera will appear here.' };
  if (!ready.astra_configured) return { ...base, state: 'astra_missing', message: 'Isaac Sim is live. Configure your own model ID and API key on your backend before generating a portrait.' };
  return { ...base, state: 'ready', message: 'Your backend and Isaac Sim are ready. Portrait generation uses your configured model account.' };
}

export async function probeStudio(endpoint: string, signal: AbortSignal, fetcher: typeof fetch = fetch): Promise<StudioConnection> {
  let readiness: unknown;
  try {
    const response = await fetcher(`${endpoint}/ready`, { signal, cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) return { ...disconnectedConnection(), endpoint, state: response.status === 404 ? 'wrong_service' : 'unreachable', message: response.status === 404 ? 'The address has no Sim Sketch backend. Paste its root URL, not an Isaac Sim streaming link.' : `Backend returned HTTP ${response.status}. Check that your gateway permits this browser to connect.` };
    try { readiness = await response.json(); } catch (error) { if (signal.aborted) throw error; return { ...disconnectedConnection(), endpoint, state: 'wrong_service', message: 'This address returned a web page instead of the Sim Sketch API. Use the backend root URL.' }; }
  } catch (error) {
    if (signal.aborted) throw error;
    return { ...disconnectedConnection(), endpoint, state: 'unreachable', message: 'Cannot reach your backend. Keep it running and check its HTTPS address, network access and browser CORS settings.' };
  }
  const identified = classifyStudio(endpoint, readiness, null);
  if (!identified.backend) return identified;
  let simulation: unknown = null;
  try {
    const response = await fetcher(`${endpoint}/sim/status`, { signal, cache: 'no-store', credentials: 'same-origin' });
    if (response.ok) simulation = await response.json();
  } catch (error) { if (signal.aborted) throw error; }
  return classifyStudio(endpoint, readiness, simulation);
}
