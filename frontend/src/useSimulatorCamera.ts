import { useCallback, useEffect, useRef, useState } from 'react';
import { CAMERA_PRESETS, clampCamera, type CameraCommandId, type CameraPose } from './simulatorCamera';

export type CameraStatus = { camera?: CameraPose | null; camera_command_id?: CameraCommandId | null };

export default function useSimulatorCamera(api: string, status: CameraStatus | null) {
  const pose = useRef<CameraPose>(CAMERA_PRESETS['Whole scene']);
  const revision = useRef(0);
  const pending = useRef<{ pose: CameraPose; revision: number } | null>(null);
  const acknowledgment = useRef<{ id: CameraCommandId; revision: number } | null>(null);
  const dirty = useRef(false);
  const sending = useRef(false);
  const schedule = useRef<() => void>(() => {});
  const [state, setState] = useState<'idle' | 'sending' | 'waiting' | 'error'>('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    let timer = 0;
    let acknowledgmentTimer = 0;
    let lastSent = 0;
    let request: AbortController | null = null;
    pose.current = CAMERA_PRESETS['Whole scene'];
    pending.current = null;
    acknowledgment.current = null;
    dirty.current = false;
    sending.current = false;
    setError('');
    setState('idle');

    function enqueue() {
      if (!active || sending.current || timer || !pending.current) return;
      timer = window.setTimeout(() => { timer = 0; void send(); }, Math.max(0, 100 - (performance.now() - lastSent)));
    }

    async function send() {
      const command = pending.current;
      if (!active || sending.current || !command) return;
      pending.current = null;
      sending.current = true;
      lastSent = performance.now();
      request = new AbortController();
      const timeout = window.setTimeout(() => request?.abort(), 5000);
      setState('sending');
      try {
        const response = await fetch(`${api}/sim/camera`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(command.pose), signal: request.signal,
        });
        const result = await response.json() as { accepted?: boolean; command_id?: CameraCommandId; detail?: string };
        if (!response.ok || !result.accepted || result.command_id == null) throw new Error(typeof result.detail === 'string' ? result.detail : 'Isaac Sim could not move its camera.');
        if (!active) return;
        acknowledgment.current = { id: result.command_id, revision: command.revision };
        setState('waiting');
        setError('');
        window.clearTimeout(acknowledgmentTimer);
        acknowledgmentTimer = window.setTimeout(() => {
          if (!active || !dirty.current || sending.current || pending.current || revision.current !== command.revision || acknowledgment.current?.id !== result.command_id) return;
          // Another viewer may replace a command before Isaac Sim receives it.
          // Resume following the actual camera instead of waiting indefinitely.
          dirty.current = false;
          acknowledgment.current = null;
          setState('error');
          setError('Camera confirmation timed out. The live view will reconnect to the current camera; try a camera preset again.');
        }, 5000);
      } catch (cause) {
        if (!active) return;
        if (revision.current === command.revision) {
          dirty.current = false;
          acknowledgment.current = null;
          setState('error');
          setError(cause instanceof Error && cause.name !== 'AbortError' ? cause.message : 'The camera did not respond. Try again when Isaac Sim is connected.');
        }
      } finally {
        window.clearTimeout(timeout);
        if (active) { sending.current = false; enqueue(); }
      }
    }

    schedule.current = enqueue;
    return () => {
      active = false;
      request?.abort();
      window.clearTimeout(timer);
      window.clearTimeout(acknowledgmentTimer);
      schedule.current = () => {};
    };
  }, [api]);

  useEffect(() => {
    if (!status?.camera) return;
    const ack = acknowledgment.current;
    if (dirty.current && !sending.current && !pending.current && ack?.revision === revision.current && status.camera_command_id === ack.id) {
      dirty.current = false;
      acknowledgment.current = null;
      setState('idle');
    }
    // Do not replace newer drag input with a delayed status response from the tunnel.
    if (!dirty.current) pose.current = clampCamera(status.camera);
  }, [status]);

  const changeCamera = useCallback((update: CameraPose | ((current: CameraPose) => CameraPose)) => {
    const next = clampCamera(typeof update === 'function' ? update(pose.current) : update);
    pose.current = next;
    dirty.current = true;
    pending.current = { pose: next, revision: ++revision.current };
    setError('');
    setState('sending');
    schedule.current();
  }, []);

  return { changeCamera, state, error };
}
