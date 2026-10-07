export const API_STORAGE = 'sim-sketch-api-url-v2';
const DEFAULT_API = import.meta.env.VITE_API_BASE_URL?.trim() ?? '';

/** null means explicitly disconnected; empty means try same-origin discovery once. */
export function initialApi(): string | null {
  try {
    // Old builds could remember a shared event endpoint. Require a new choice.
    localStorage.removeItem('sim-sketch-api-url');
    const saved = localStorage.getItem(API_STORAGE);
    return saved === '' ? null : saved ?? DEFAULT_API;
  } catch { return DEFAULT_API; }
}
