import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    // Suite touches lmdb/better-sqlite3-backed stores via @cassicore/mnemic-field;
    // the `forks` pool isolates each file in a subprocess (Windows-stable per the
    // P5a lesson) instead of the default threads worker teardown that flakes.
    pool: 'forks',
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
    exclude: ['tests/host-wired/**', 'node_modules/**'],
  },
})
