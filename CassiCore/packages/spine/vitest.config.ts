import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    // No live ohmypi in CI — spine tests stub the ExtensionAPI (recon §1.1 factory
    // shape) + the runtime channel client.
    pool: 'forks',
    include: ['src/**/*.test.ts', 'test/**/*.test.ts'],
    exclude: ['node_modules/**'],
  },
})
