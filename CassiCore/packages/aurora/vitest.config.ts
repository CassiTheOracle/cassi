import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    // SQLite/LMDB-heavy suite: the default `threads` pool's worker teardown
    // flakes with exit-5 on Windows after the long store tests keep handles
    // open. Panel `forks` isolates each test file in a subprocess, which is
    // stable here.
    pool: 'forks',
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
    exclude: ['tests/host-wired/**', 'node_modules/**'],
  },
})
