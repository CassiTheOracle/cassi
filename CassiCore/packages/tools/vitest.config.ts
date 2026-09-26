import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    // Tool executor/collect-thoughts suites spin real child processes and globals;
    // `forks` isolates each file in a subprocess, stable on Windows per the P5a lesson.
    pool: 'forks',
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
    exclude: ['tests/host-wired/**', 'node_modules/**'],
  },
})
