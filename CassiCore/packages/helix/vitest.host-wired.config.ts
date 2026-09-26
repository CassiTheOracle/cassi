import { defineConfig } from 'vitest/config'

// Host-wired configuration: runs ONLY the tests under tests/host-wired/.
// These tests import the CassiCore daemon runtime (core/intelligence/...,
// core/workflow/..., core/runtime/audit/...) or otherwise require a mounted
// host. No host is wired inside this standalone package, so they are expected
// to fail with module-resolution (not-connected) errors. This config exists so
// `npm run test:host-wired` actually attempts them instead of silently
// excluding them.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/host-wired/**/*.test.ts'],
    exclude: ['node_modules/**'],
  },
})
