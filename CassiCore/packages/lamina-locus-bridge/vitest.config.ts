import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    // SQLite-heavy suite (LaminaStore + vendored AuditStore both open
    // better-sqlite3): `forks` pool isolates each test file in a subprocess,
    // which is stable on Windows per the P5a lesson.
    pool: 'forks',
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
    exclude: ['tests/host-wired/**', 'node_modules/**'],
  },
})
