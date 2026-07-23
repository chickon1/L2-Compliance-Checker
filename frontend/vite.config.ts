import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const pkg = JSON.parse(readFileSync(fileURLToPath(new URL('./package.json', import.meta.url)), 'utf-8'));

export default defineConfig({
  // basicSsl generates a self-signed cert on first run (cached under
  // node_modules/.vite/basic-ssl/ afterwards) and enables server.https with
  // it. It's untrusted, so browsers show a one-time warning to click
  // through — real device credentials are still worth encrypting in
  // transit if this dev server is ever reached over the network rather
  // than localhost, even without a publicly-trusted cert.
  plugins: [react(), basicSsl()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8444',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
});
