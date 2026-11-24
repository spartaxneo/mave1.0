import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  root: path.resolve(__dirname, 'src/renderer'),
  plugins: [react()],
  server: {
    port: 3007,
    host: '127.0.0.1',
  },
  resolve: {
    alias: {
      '@os1/ui': path.resolve(__dirname, '../../packages/ui/src'),
    },
  },
});
