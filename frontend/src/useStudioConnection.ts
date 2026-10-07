import { useCallback, useEffect, useRef, useState } from 'react';
import { API_STORAGE, initialApi } from './apiConfig';
import { disconnectedConnection, normalizeEndpoint, probeStudio, type StudioConnection } from './studioConnection';

export default function useStudioConnection() {
  const [connection, setConnection] = useState<StudioConnection>(disconnectedConnection);
  const endpoint = useRef<string | null>(null);
  const latest = useRef(0);
  const activeProbe = useRef<{ endpoint: string; controller: AbortController; promise: Promise<StudioConnection>; detecting: boolean } | null>(null);
  const alive = useRef(true);
  const [revision, setRevision] = useState(0);

  const check = useCallback((candidate = endpoint.current, detecting = false): Promise<StudioConnection> => {
    if (!candidate) return Promise.resolve(disconnectedConnection());
    if (activeProbe.current?.endpoint === candidate) {
      // Preflight, recheck and periodic status share one in-flight discovery.
      if (!detecting) activeProbe.current.detecting = false;
      return activeProbe.current.promise;
    }
    const sequence = ++latest.current;
    activeProbe.current?.controller.abort();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 6500);
    setConnection(previous => previous.endpoint === candidate && previous.backend ? previous : { ...disconnectedConnection(), endpoint: candidate, state: 'checking', message: 'Checking backend identity, simulator activity and model configuration…' });
    const pending = (async (): Promise<StudioConnection> => {
      let next: StudioConnection;
      try {
        next = await probeStudio(candidate, controller.signal);
      } catch {
        next = { ...disconnectedConnection(), endpoint: candidate, state: 'unreachable', message: 'Connection timed out. Check that your backend is running and reachable from this browser.' };
      } finally { window.clearTimeout(timeout); }
      if (sequence !== latest.current || !alive.current) return disconnectedConnection();
      const detectionOnly = activeProbe.current?.detecting ?? detecting;
      if (activeProbe.current?.controller === controller) activeProbe.current = null;
      if (detectionOnly && !next.backend) {
        endpoint.current = null;
        next = disconnectedConnection();
      } else endpoint.current = candidate;
      setConnection(next);
      return next;
    })();
    activeProbe.current = { endpoint: candidate, controller, promise: pending, detecting };
    return pending;
  }, []);

  useEffect(() => {
    alive.current = true;
    const saved = initialApi();
    if (saved !== null) {
      try {
        const candidate = normalizeEndpoint(saved || window.location.origin, window.location.protocol);
        endpoint.current = candidate;
        void check(candidate, !saved);
      } catch { setConnection({ ...disconnectedConnection(), state: 'unreachable', message: 'Your saved address is invalid for this page. Enter your HTTPS backend URL below.' }); }
    }
    return () => { alive.current = false; latest.current++; activeProbe.current?.controller.abort(); activeProbe.current = null; };
  }, [check]);

  useEffect(() => {
    if (!connection.endpoint || connection.state === 'checking') return;
    const timer = window.setInterval(() => { if (!activeProbe.current) void check(); }, 8000);
    return () => window.clearInterval(timer);
  }, [connection.endpoint, connection.state, revision, check]);

  const connect = useCallback(async (value: string) => {
    const candidate = normalizeEndpoint(value, window.location.protocol);
    endpoint.current = candidate;
    try { localStorage.setItem(API_STORAGE, candidate); } catch { /* Session-only connection. */ }
    setRevision(value => value + 1);
    return check(candidate);
  }, [check]);

  const disconnect = useCallback(() => {
    latest.current++;
    activeProbe.current?.controller.abort();
    activeProbe.current = null;
    endpoint.current = null;
    try { localStorage.setItem(API_STORAGE, ''); } catch { /* Session-only disconnection. */ }
    setConnection(disconnectedConnection());
  }, []);

  return { connection, connect, disconnect, check };
}
