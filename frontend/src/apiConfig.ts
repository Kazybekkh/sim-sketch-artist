export const API_STORAGE = 'sim-sketch-api-url';
const DEFAULT_API = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';

export function initialApi() {
  try { return localStorage.getItem(API_STORAGE) ?? DEFAULT_API; } catch { return DEFAULT_API; }
}
