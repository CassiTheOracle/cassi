import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    // Isolate each file in a subprocess (stable on Windows; boot/canald tests hold
    // temp homes + open sqlite/lmdb files).
    pool: 'forks',
    include: ['src/**/*.test.ts', 'test/**/*.test.ts'],
    exclude: ['node_modules/**'],
    testTimeout: 30_000,
  },
})
