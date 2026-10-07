import assert from 'node:assert/strict';
import test from 'node:test';
import { classifyStudio, disconnectedConnection, normalizeEndpoint, probeStudio } from '../src/studioConnection.ts';

const endpoint = 'https://studio.example.test';
const now = Date.now();
const readiness = { service: 'sim-sketch-artist', protocol_version: 1, ok: true, astra_configured: true };
const simulation = { online: true, mode: 'robot', state: 'idle', updated_at: now / 1000 };

// A hosted frontend must never try sending API credentials to an arbitrary URL shape.
test('accepts HTTPS backend roots and local HTTP only on an HTTP page', () => {
  assert.equal(normalizeEndpoint(` ${endpoint}/ `, 'https:'), endpoint);
  assert.equal(normalizeEndpoint('http://localhost:8000/', 'http:'), 'http://localhost:8000');
  assert.equal(normalizeEndpoint('http://[::1]:8000/', 'http:'), 'http://[::1]:8000');
});

test('rejects mixed content, remote HTTP, credentials, streaming routes and non-HTTP addresses', () => {
  for (const address of ['http://localhost:8000', 'http://127.0.0.1:8000', 'http://studio.example.test', 'ssh://user@gpu', 'wss://studio.example.test', 'https://user:pass@studio.example.test', `${endpoint}/sim/view`, `${endpoint}?token=secret`, `${endpoint}#viewer`, 'not a URL']) {
    assert.throws(() => normalizeEndpoint(address, 'https:'), Error, address);
  }
  assert.throws(() => normalizeEndpoint('http://studio.example.test', 'http:'));
});

test('an arbitrary live web server is not accepted as a backend', () => {
  for (const payload of [null, {}, [], { ok: true }, { ...readiness, protocol_version: 2 }, { ...readiness, astra_configured: 'true' }]) {
    const result = classifyStudio(endpoint, payload, simulation);
    assert.equal(result.state, 'wrong_service');
    assert.equal(result.backend, false);
    assert.equal(result.simulatorOnline, false);
  }
});

test('requires a fresh robot worker rather than just a reachable API', () => {
  for (const sim of [{ ...simulation, online: false }, { ...simulation, updated_at: 0 }, { ...simulation, updated_at: Infinity }, { ...simulation, mode: 'marker' }]) {
    const result = classifyStudio(endpoint, readiness, sim);
    assert.equal(result.state, 'sim_offline');
    assert.equal(result.backend, true);
    assert.equal(result.simulatorOnline, false);
  }
  assert.equal(classifyStudio(endpoint, readiness, { ...simulation, state: 'error' }).state, 'sim_error');
});

test('separates model configuration from worker status without claiming account access', () => {
  const missing = classifyStudio(endpoint, { ...readiness, astra_configured: false }, simulation);
  assert.equal(missing.state, 'astra_missing');
  assert.equal(missing.simulatorOnline, true);
  assert.equal(missing.astraConfigured, false);
  assert.equal(classifyStudio(endpoint, readiness, simulation).state, 'ready');
  assert.equal(disconnectedConnection().endpoint, null);
});

test('discovery performs read-only requests and never sends a portrait or queues work', async () => {
  const requests = [];
  const fetcher = async (url, options) => {
    requests.push({ url, options });
    return Response.json(url.endsWith('/ready') ? readiness : { ...simulation, updated_at: Date.now() / 1000 });
  };
  const result = await probeStudio(endpoint, new AbortController().signal, fetcher);
  assert.equal(result.state, 'ready');
  assert.deepEqual(requests.map(request => request.url), [`${endpoint}/ready`, `${endpoint}/sim/status`]);
  for (const { options } of requests) {
    assert.equal(options.method, undefined);
    assert.equal(options.body, undefined);
    assert.equal(options.cache, 'no-store');
    assert.equal(options.credentials, 'same-origin');
  }
});

test('wrong service stops discovery before simulator/frame requests', async () => {
  let requests = 0;
  const result = await probeStudio(endpoint, new AbortController().signal, async () => { requests++; return new Response('<html>login</html>', { headers: { 'Content-Type': 'text/html' } }); });
  assert.equal(result.state, 'wrong_service');
  assert.equal(requests, 1);
});

test('network, gateway, missing service and worker failures have distinct useful states', async () => {
  const signal = new AbortController().signal;
  assert.equal((await probeStudio(endpoint, signal, async () => { throw new TypeError('Failed to fetch'); })).state, 'unreachable');
  assert.equal((await probeStudio(endpoint, signal, async () => new Response('', { status: 403 }))).state, 'unreachable');
  assert.equal((await probeStudio(endpoint, signal, async () => new Response('', { status: 404 }))).state, 'wrong_service');
  const result = await probeStudio(endpoint, signal, async url => url.endsWith('/ready') ? Response.json(readiness) : new Response('', { status: 503 }));
  assert.equal(result.backend, true);
  assert.equal(result.state, 'sim_unreachable');
  for (const payload of [null, {}, { ...simulation, state: 'unexpected' }]) {
    assert.equal(classifyStudio(endpoint, readiness, payload).state, 'sim_unreachable');
  }
});

test('cancelled discovery cannot be mistaken for a successful connection', async () => {
  const controller = new AbortController();
  const pending = probeStudio(endpoint, controller.signal, async (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')), { once: true });
  }));
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
});


test('native stopped worker payload is a valid offline state', () => {
  const result = classifyStudio(endpoint, readiness, { online: false, state: 'idle', mode: null, updated_at: null });
  assert.equal(result.backend, true);
  assert.equal(result.state, 'sim_offline');
  assert.equal(result.simulatorOnline, false);
});

test('simulator diagnostics remain plain text, with a fallback for missing errors', () => {
  const diagnostic = 'Pen tracking failed at stroke 4: <robot> out of range';
  const result = classifyStudio(endpoint, readiness, { ...simulation, state: 'error', error: diagnostic });
  assert.equal(result.state, 'sim_error');
  assert.equal(result.message, `Isaac Sim: ${diagnostic} Fix the error, restart the drawing worker, then recheck the connection.`);
  assert.equal(result.simulatorOnline, false);
  for (const error of [null, undefined, '', { detail: 'unsafe shape' }]) {
    assert.match(classifyStudio(endpoint, readiness, { ...simulation, state: 'error', error }).message, /Check its terminal/);
  }
});

test('server-verified live state remains usable when the browser and GPU clocks differ', () => {
  for (const offset of [-60 * 60 * 1000, 60 * 60 * 1000]) {
    assert.equal(classifyStudio(endpoint, readiness, { ...simulation, updated_at: (now + offset) / 1000 }).state, 'ready');
  }
  assert.equal(classifyStudio(endpoint, readiness, { ...simulation, online: false, updated_at: now / 1000 }).state, 'sim_offline');
});
