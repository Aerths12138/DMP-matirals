import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/');
          if (!normalized.includes('/node_modules/')) return undefined;

          const modulePath = normalized.split('/node_modules/')[1];
          const segments = modulePath.split('/');
          const packageName = segments[0].startsWith('@')
            ? `${segments[0]}-${segments[1]}`
            : segments[0];
          if (packageName === 'antd') {
            if (segments[1] !== 'es') return 'vendor-antd-core';

            const section = segments[2] || 'core';
            if (['_util', 'config-provider', 'style', 'theme'].includes(section)) {
              return 'vendor-antd-core';
            }
            const first = section[0].toLowerCase();
            if ('abcdefghi'.includes(first)) return 'vendor-antd-a-i';
            if ('jklmnopqr'.includes(first)) return 'vendor-antd-j-r';
            return 'vendor-antd-s-z';
          }
          return `vendor-${packageName.replace('@', '')}`;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
