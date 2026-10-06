export type CameraPose = { yaw: number; pitch: number; distance: number; target: [number, number, number] };
export type CameraCommandId = string | number;

export const CAMERA_PRESETS: Record<string, CameraPose> = {
  'Whole scene': { yaw: -Math.PI / 4, pitch: 0.534842736717193, distance: 0.6081940479813988, target: [0, -0.17, 0.13] },
  'Paper close-up': { yaw: -0.85, pitch: 0.65, distance: 0.34, target: [0.02, -0.215, 0.055] },
  'Top view': { yaw: -Math.PI / 2, pitch: 1.55, distance: 0.72, target: [0, -0.10, 0.10] },
};

const bound = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

export function clampCamera(camera: CameraPose): CameraPose {
  return {
    yaw: bound(camera.yaw, -2 * Math.PI, 2 * Math.PI),
    pitch: bound(camera.pitch, 0.1, 1.55),
    distance: bound(camera.distance, 0.12, 1.5),
    target: [bound(camera.target[0], -0.5, 0.5), bound(camera.target[1], -0.5, 0.5), bound(camera.target[2], 0, 0.5)],
  };
}

export function orbitCamera(camera: CameraPose, dx: number, dy: number): CameraPose {
  return clampCamera({ ...camera, yaw: camera.yaw - dx * 0.006, pitch: camera.pitch + dy * 0.006 });
}

export function panCamera(camera: CameraPose, dx: number, dy: number, height: number): CameraPose {
  const scale = camera.distance * 1.2 / Math.max(height, 1);
  const right = [-Math.sin(camera.yaw), Math.cos(camera.yaw), 0];
  const up = [-Math.cos(camera.yaw) * Math.sin(camera.pitch), -Math.sin(camera.yaw) * Math.sin(camera.pitch), Math.cos(camera.pitch)];
  return clampCamera({ ...camera, target: camera.target.map((value, index) => value + (-dx * right[index] + dy * up[index]) * scale) as CameraPose['target'] });
}

export function zoomCamera(camera: CameraPose, delta: number): CameraPose {
  return clampCamera({ ...camera, distance: camera.distance * Math.exp(bound(delta, -1000, 1000) * 0.0015) });
}
