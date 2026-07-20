import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        proxyTimeout: 0,
        timeout: 0,
        configure(proxy) {
          proxy.on('proxyRes', proxyResponse => {
            if ((proxyResponse.headers['content-type'] || '').startsWith('text/event-stream')) {
              proxyResponse.headers['cache-control'] = 'no-cache, no-transform';
              proxyResponse.headers['x-accel-buffering'] = 'no';
            }
          });
        }
      }
    }
  }
});
