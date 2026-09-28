/// <reference types="vitest/config" />
import path from 'path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  // Tests de componentes: React montado en jsdom, con los matchers de jest-dom (setup.ts).
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
})
