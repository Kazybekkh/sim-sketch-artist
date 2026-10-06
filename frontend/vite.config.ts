import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'DEV_API_URL');
  const target = env.DEV_API_URL?.trim();
  const routes = ['/health', '/portrait', '/draw', '/status', '/result', '/trail', '/previews', '/ready', '/sim'];
  return {
    plugins: [react()],
    server: target ? { proxy: Object.fromEntries(routes.map(route => [route, target])) } : {},
  };
});
