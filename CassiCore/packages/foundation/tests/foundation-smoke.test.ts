/**
 * Foundation smoke tests — public surface + paths port.
 *
 * Defends the observable contracts that later @cassicore/* packages build against:
 *   1. The public barrel (src/index.ts) exports the load-bearing names.
 *   2. The paths port honors CASSICORE_HOME, falls back to ~/.cassicore, and
 *      honors a resolver injected via setRootResolver().
 *
 * These are SMOKE tests only — P1 ships no standalone unit tests (0 direct test
 * files for the migrated types per the P1 migration table). They exist solely so
 * `npm test` has a real, passing suite that pins the package boundary.
 */

import { describe, it, expect, afterEach, vi } from 'vitest'
import path from 'node:path'
import os from 'node:os'

// --- Value exports: their presence/runtime shape is asserted below ---
import {
  BaseCognitiveModule,
  DEFAULT_MODULE_MODEL_CONFIG,
  envRootResolver,
  MODEL_DEFAULTS,
  SYSTEM_SETTINGS,
  SPAWN_EVALUATION_PHRASES,
  getCassiCoreHome,
  getDataDir,
  getRepoRoot,
  setRootResolver,
} from '../src/index.js'

// --- Type-only exports: importability itself is the contract (compile-time).
// Used in the `_typedContract` block so they cannot silently disappear. ---
import type {
  ModuleModelConfig,
  ILogger,
  IEventBus,
  IConfig,
  IntelligenceModule,
  CassiCoreRootResolver,
  IProvider,
  Message,
  RuntimeEvent,
  PluginManifest,
} from '../src/index.js'

// Compile-time contract: every listed type must resolve from the barrel.
const _typedContract: {
  modelConfig: ModuleModelConfig
  logger: ILogger
  bus: IEventBus
  config: IConfig
  module: IntelligenceModule
  resolver: CassiCoreRootResolver
  provider: IProvider | undefined
  message: Message | undefined
  event: RuntimeEvent | undefined
  manifest: PluginManifest | undefined
} = {
  modelConfig: { model: 'm', providerId: 'p' },
  logger: undefined as unknown as ILogger,
  bus: undefined as unknown as IEventBus,
  config: undefined as unknown as IConfig,
  module: undefined as unknown as IntelligenceModule,
  resolver: undefined as unknown as CassiCoreRootResolver,
  provider: undefined,
  message: undefined,
  event: undefined,
  manifest: undefined,
}
void _typedContract

// Restore stubbed envs after every test so ordering never matters.
afterEach(() => {
  vi.unstubAllEnvs()
  // Re-pin the default resolver in case a test overrode it.
  setRootResolver(envRootResolver)
})

describe('public barrel (src/index.ts)', () => {
  it('exports the BaseCognitiveModule base class', () => {
    expect(typeof BaseCognitiveModule).toBe('function')
    expect(BaseCognitiveModule.prototype).toBeDefined()
  })

  it('exports a usable DEFAULT_MODULE_MODEL_CONFIG', () => {
    expect(DEFAULT_MODULE_MODEL_CONFIG).toBeTypeOf('object')
    // Could be undefined within an object graph; assert the load-bearing keys.
    expect('model' in DEFAULT_MODULE_MODEL_CONFIG).toBe(true)
    expect('providerId' in DEFAULT_MODULE_MODEL_CONFIG).toBe(true)
  })

  it('exports nested SYSTEM_SETTINGS with MODEL_DEFAULTS wired as models', () => {
    expect(SYSTEM_SETTINGS).toBeTypeOf('object')
    expect(SYSTEM_SETTINGS.models).toBe(MODEL_DEFAULTS)
    // Every top-level model slot carries { provider, model } strings.
    const slots = (Object.keys(MODEL_DEFAULTS) as Array<keyof typeof MODEL_DEFAULTS>)
      .filter((k) => { const v = MODEL_DEFAULTS[k]; return v && typeof v === 'object' && ('provider' in v) })
    expect(slots.length).toBeGreaterThan(0)
    for (const slot of slots) {
      expect(typeof MODEL_DEFAULTS[slot].provider).toBe('string')
      expect(typeof MODEL_DEFAULTS[slot].model).toBe('string')
    }
  })

  it('exports phrase prototypes as a PhrasePrototypeSet', () => {
    expect(SPAWN_EVALUATION_PHRASES).toBeTypeOf('object')
    expect(SPAWN_EVALUATION_PHRASES.phrases).toBeTypeOf('object')
    expect(Object.keys(SPAWN_EVALUATION_PHRASES.phrases).length).toBeGreaterThan(0)
    expect(Array.isArray(SPAWN_EVALUATION_PHRASES.labels)).toBe(true)
  })
})

describe('paths port', () => {
  // "Unset" semantics use '' (falsy): vi.stubEnv('K', undefined) coerces to the
  // truthy string "undefined" in process.env and would defeat the || fallback.
  it('defaults to ~/.cassicore when no env override is set', () => {
    vi.stubEnv('CASSICORE_HOME', '')
    vi.stubEnv('CASSICORE_DATA_DIR', '')
    const expected = path.join(os.homedir(), '.cassicore')
    expect(getCassiCoreHome()).toBe(expected)
    expect(getDataDir()).toBe(path.join(expected, 'data'))
  })

  it('honors the CASSICORE_HOME env override', () => {
    vi.stubEnv('CASSICORE_HOME', '/tmp/cassi-smoke-home')
    expect(getCassiCoreHome()).toBe('/tmp/cassi-smoke-home')
    expect(getDataDir()).toBe(path.join('/tmp/cassi-smoke-home', 'data'))
  })

  it('honors CASSICORE_DATA_DIR (legacy) when CASSICORE_HOME is unset', () => {
    vi.stubEnv('CASSICORE_HOME', '')
    vi.stubEnv('CASSICORE_DATA_DIR', '/tmp/cassi-smoke-data')
    expect(getCassiCoreHome()).toBe('/tmp/cassi-smoke-data')
  })

  it('redirects getDataDir through an injected root resolver', () => {
    const fake: CassiCoreRootResolver = {
      getCassiCoreHome: () => '/fake/cassi-root',
    }
    setRootResolver(fake)
    expect(getCassiCoreHome()).toBe('/fake/cassi-root')
    expect(getDataDir()).toBe(path.join('/fake/cassi-root', 'data'))
  })

  it('restores the default environment resolver after injection', () => {
    // afterEach already restored the default; assert it is wired back.
    vi.stubEnv('CASSICORE_HOME', '/tmp/cassi-smoke-restore')
    expect(getCassiCoreHome()).toBe('/tmp/cassi-smoke-restore')
  })

  it('exposes a string-valued getRepoRoot (walk-up heuristic)', () => {
    expect(typeof getRepoRoot()).toBe('string')
  })
})
