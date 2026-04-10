import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // './' base so all asset paths are relative — required for S3 static hosting
  base: './',
  server: {
    port: 5173,
    // When running locally, the FastAPI server handles the API.
    // The React app reads the API URL from window.RAG_API_URL / Settings modal.
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          motion: ['framer-motion'],
        },
      },
    },
  },
})
