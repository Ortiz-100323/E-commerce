import path from 'node:path'
import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vitest/config'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const testingRoot = path.resolve(frontendRoot, '../testing/frontend')

function resolveTestImportsFromFrontend(): Plugin {
  const anchor = path.join(frontendRoot, 'src', 'main.tsx')
  return {
    name: 'resolve-test-imports-from-frontend',
    enforce: 'pre',
    async resolveId(source, importer, options) {
      const isBare = !source.startsWith('.') && !source.startsWith('/') && !source.startsWith('\0')
      const isVitest = source === 'vitest' || source.startsWith('vitest/')
      if (isVitest) {
        return null
      }
      const fromTesting = importer !== undefined && path.resolve(importer).startsWith(testingRoot)
      if (!isBare || !fromTesting) {
        return null
      }
      return this.resolve(source, anchor, { ...options, skipSelf: true })
    },
  }
}

export default defineConfig({
  plugins: [react(), resolveTestImportsFromFrontend()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8001',
    },
    fs: {
      allow: [frontendRoot, testingRoot],
    },
  },
  test: {
    root: frontendRoot,
    dir: testingRoot,
    include: ['**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: [path.join(testingRoot, 'setup.ts')],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/**/*.d.ts'],
      reporter: ['text-summary', 'text'],
      thresholds: { lines: 80, statements: 80, functions: 80, branches: 80 },
    },
  },
})
