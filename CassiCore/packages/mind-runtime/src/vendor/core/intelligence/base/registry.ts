/**
 * IntelligenceRegistry — Dynamic auto-loader for BaseCognitiveModule subclasses.
 *
 * Responsibilities:
 *   - Discovers modules extending BaseCognitiveModule from the intelligence directory
 *   - Manages dependency injection (eventBus, memory, provider, config, tools)
 *   - Drives lifecycle (init → start → stop) in priority order
 *   - Coexists with legacy factory-based modules in createIntelligence()
 *
 * Usage:
 *   const registry = new IntelligenceRegistry(logger)
 *   await registry.discover(intelligenceDir)  // scan folders
 *   registry.wire({ eventBus, memory, provider, config, toolRegistry, toolExecutor })
 *   await registry.initAll()
 *   await registry.startAll()
 *   // ... on shutdown:
 *   await registry.stopAll()
 *
 * Modules are sorted by priority (descending) — higher priority runs first.
 */

import { readdir, stat } from 'node:fs/promises'
import { join, basename } from 'node:path'
import { pathToFileURL } from 'node:url'

import { BaseCognitiveModule } from './cognitive-module.js'

import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus, IConfig, IntelligenceModule } from '@cassicore/foundation'
import type { IProvider } from '@cassicore/foundation'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'

// Types

/** Constructor type for BaseCognitiveModule subclasses */
export type CognitiveModuleConstructor = new (
  logger: ILogger,
  modelConfig?: Record<string, unknown>,
) => BaseCognitiveModule

/** Dependencies that the registry injects into discovered modules */
export interface RegistryDependencies {
  eventBus?: IEventBus
  memory?: IMemory
  provider?: IProvider
  config?: IConfig
  toolRegistry?: ToolRegistry
  toolExecutor?: ToolExecutor
}

/** Export metadata for a well-known module export shape */
interface ModuleExportCandidate {
  name: string
  constructor: CognitiveModuleConstructor
}

// Registry

export class IntelligenceRegistry {
  private readonly logger: ILogger
  private readonly modules: Map<string, BaseCognitiveModule> = new Map()
  private deps: RegistryDependencies = {}
  private wired = false

  constructor(logger: ILogger) {
    this.logger = logger.child('intelligence-registry')
  }

  // Manual Registration

  /**
   * Register a pre-constructed module instance.
   * Use this for modules that need custom construction (non-default constructor args).
   */
  registerInstance(module: BaseCognitiveModule): void {
    if (this.modules.has(module.name)) {
      this.logger.warn(`Module '${module.name}' already registered — skipping duplicate`)
      return
    }
    this.modules.set(module.name, module)
    this.logger.info(`Registered module '${module.name}' (priority=${module.priority})`)
  }

  /**
   * Register a module class. The registry will construct it with a child logger.
   */
  registerClass(
    ModuleClass: CognitiveModuleConstructor,
    modelConfig?: Record<string, unknown>,
  ): BaseCognitiveModule | undefined {
    try {
      const instance = new ModuleClass(this.logger, modelConfig)
      if (this.modules.has(instance.name)) {
        this.logger.warn(`Module '${instance.name}' already registered — skipping duplicate`)
        return undefined
      }
      this.modules.set(instance.name, instance)
      this.logger.info(`Registered module class '${instance.name}' (priority=${instance.priority})`)
      return instance
    } catch (err) {
      this.logger.error('Failed to construct module from class', { error: String(err) })
      return undefined
    }
  }

  // Auto-Discovery

  /**
   * Scan a directory for subdirectories containing BaseCognitiveModule exports.
   *
   * Convention:
   *   - Each subdirectory under `baseDir` may contain an `index.ts` (compiled to `index.js`)
   *   - The module file should export a named class extending BaseCognitiveModule
   *   - Alternatively, it can export a `MODULE_CLASS` named export
   *
   * Skips directories that don't export a valid module (e.g., legacy factory modules).
   * This is safe to run alongside legacy modules — it won't interfere with them.
   *
   * @param baseDir - Absolute path to the intelligence directory (compiled JS)
   * @param skipDirs - Directory names to skip (e.g., 'base', 'memory', 'continuity')
   */
  async discover(baseDir: string, skipDirs?: Set<string>): Promise<void> {
    this.logger.info(`Discovering modules in ${baseDir}`)

    let entries: string[]
    try {
      entries = await readdir(baseDir)
    } catch (err) {
      this.logger.error('Failed to read intelligence directory', { dir: baseDir, error: String(err) })
      return
    }

    for (const entry of entries) {
      // Skip non-directories and explicitly excluded names
      if (skipDirs?.has(entry)) continue
      if (entry.startsWith('.') || entry.startsWith('_')) continue

      const dirPath = join(baseDir, entry)
      try {
        const dirStat = await stat(dirPath)
        if (!dirStat.isDirectory()) continue
      } catch {
        continue
      }

      // Try to load index.js (compiled) or index.ts (source/tsx) from the subdirectory
      let indexPath = join(dirPath, 'index.js')
      try {
        const indexStat = await stat(indexPath)
        if (!indexStat.isFile()) {
          // Try .ts fallback for tsx-based execution
          indexPath = join(dirPath, 'index.ts')
          const tsStat = await stat(indexPath)
          if (!tsStat.isFile()) continue
        }
      } catch {
        // No index.js — try index.ts for tsx-based execution
        try {
          indexPath = join(dirPath, 'index.ts')
          const tsStat = await stat(indexPath)
          if (!tsStat.isFile()) continue
        } catch {
          continue
        }
      }

      await this.tryLoadModule(indexPath, entry)
    }

    this.logger.info(`Discovery complete: ${this.modules.size} module(s) registered`)
  }

  /**
   * Attempt to dynamically import a module file and extract a BaseCognitiveModule class.
   */
  private async tryLoadModule(filePath: string, dirName: string): Promise<void> {
    try {
      const fileUrl = pathToFileURL(filePath).href
      const mod = await import(fileUrl)

      const candidate = this.findModuleExport(mod, dirName)
      if (!candidate) return // Not a BaseCognitiveModule — silently skip (likely a legacy module)

      // Check for duplicates
      if (this.modules.has(candidate.name)) {
        this.logger.debug(`Skipping '${dirName}' — module '${candidate.name}' already registered`)
        return
      }

      // Construct with a child logger
      const instance = new candidate.constructor(this.logger.child(candidate.name))
      this.modules.set(instance.name, instance)
      this.logger.info(`Auto-discovered module '${instance.name}' from ${dirName}/ (priority=${instance.priority})`)
    } catch (err) {
      // Non-fatal: legacy modules or modules with constructor errors are skipped
      this.logger.debug(`Skipping '${dirName}/' — not a BaseCognitiveModule`, { error: String(err) })
    }
  }

  /**
   * Inspect a module's exports to find a BaseCognitiveModule constructor.
   *
   * Checks in order:
   *   1. A named export `MODULE_CLASS` (explicit opt-in)
   *   2. Any named export that is a class extending BaseCognitiveModule
   */
  private findModuleExport(
    mod: Record<string, unknown>,
    dirName: string,
  ): ModuleExportCandidate | null {
    // 1. Explicit MODULE_CLASS export
    if (mod.MODULE_CLASS && this.isCognitiveModuleClass(mod.MODULE_CLASS)) {
      return {
        name: dirName,
        constructor: mod.MODULE_CLASS as CognitiveModuleConstructor,
      }
    }

    // 2. Scan all named exports for a class extending BaseCognitiveModule
    for (const [exportName, exportValue] of Object.entries(mod)) {
      if (exportName === 'default') continue // We don't use default exports
      if (this.isCognitiveModuleClass(exportValue)) {
        return {
          name: dirName,
          constructor: exportValue as CognitiveModuleConstructor,
        }
      }
    }

    return null
  }

  /**
   * Check if a value is a constructor function that extends BaseCognitiveModule.
   */
  private isCognitiveModuleClass(value: unknown): value is CognitiveModuleConstructor {
    if (typeof value !== 'function') return false
    try {
      // Walk the prototype chain to check for BaseCognitiveModule
      let proto = value.prototype
      while (proto) {
        if (proto.constructor === BaseCognitiveModule) return true
        proto = Object.getPrototypeOf(proto)
      }
      return false
    } catch {
      return false
    }
  }

  // Dependency Injection

  /**
   * Wire dependencies into all registered modules.
   * Can be called multiple times — later calls add/update dependencies.
   */
  wire(deps: RegistryDependencies): void {
    this.deps = { ...this.deps, ...deps }

    for (const module of Array.from(this.modules.values())) {
      this.wireModule(module)
    }

    this.wired = true
    this.logger.info(`Wired ${this.modules.size} module(s) with dependencies`)
  }

  /**
   * Wire a single module with the current dependency set.
   */
  private wireModule(module: BaseCognitiveModule): void {
    if (this.deps.eventBus) {
      // Use onEventBus() instead of setEventBus() — it triggers wireEventSubscriptions()
      // which sets up turn:start, turn:end, and other event handlers.
      module.onEventBus(this.deps.eventBus)
    }
    if (this.deps.memory) {
      module.setMemory(this.deps.memory)
    }
    if (this.deps.provider) {
      module.setProvider(this.deps.provider)
    }
    if (this.deps.config) {
      module.setConfig(this.deps.config)
    }
    if (this.deps.toolRegistry) {
      module.setToolRegistry(this.deps.toolRegistry)
    }
    if (this.deps.toolExecutor) {
      module.setToolExecutor(this.deps.toolExecutor)
    }
  }

  // Lifecycle

  /**
   * Initialize all modules in priority order (highest first).
   * Errors in individual modules are logged but don't block others.
   */
  async initAll(): Promise<void> {
    const sorted = this.sortedModules()
    this.logger.info(`Initializing ${sorted.length} module(s)...`)

    for (const module of sorted) {
      try {
        await module.init()
      } catch (err) {
        this.logger.error(`Failed to initialize module '${module.name}'`, { error: String(err) })
      }
    }
  }

  /**
   * Start all modules in priority order (highest first).
   * Ensures wire() has been called first.
   */
  async startAll(): Promise<void> {
    if (!this.wired) {
      this.logger.warn('startAll() called before wire() — modules may lack dependencies')
    }

    const sorted = this.sortedModules()
    this.logger.info(`Starting ${sorted.length} module(s)...`)

    for (const module of sorted) {
      try {
        await module.start()
      } catch (err) {
        this.logger.error(`Failed to start module '${module.name}'`, { error: String(err) })
      }
    }
  }

  /**
   * Stop all modules in reverse priority order (lowest first).
   */
  async stopAll(): Promise<void> {
    const sorted = this.sortedModules().reverse()
    this.logger.info(`Stopping ${sorted.length} module(s)...`)

    for (const module of sorted) {
      try {
        await module.stop()
      } catch (err) {
        this.logger.error(`Failed to stop module '${module.name}'`, { error: String(err) })
      }
    }
  }

  // Accessors

  /** Get a specific module by name. */
  get(name: string): BaseCognitiveModule | undefined {
    return this.modules.get(name)
  }

  /** Check if a module is registered. */
  has(name: string): boolean {
    return this.modules.has(name)
  }

  /** Get all modules sorted by priority (descending). */
  getAll(): BaseCognitiveModule[] {
    return this.sortedModules()
  }

  /**
   * Get all modules as IntelligenceModule[] for integration with the existing
   * IntelligenceLayer.all array. This allows new-style modules to coexist
   * with legacy factory-based modules.
   */
  getAllAsIntelligenceModules(): IntelligenceModule[] {
    return this.sortedModules()
  }

  /** Number of registered modules. */
  get size(): number {
    return this.modules.size
  }

  /**
   * Get metrics for all modules.
   */
  getMetrics(): Record<string, { status: string; metrics: unknown }> {
    const result: Record<string, { status: string; metrics: unknown }> = {}
    for (const [name, module] of Array.from(this.modules.entries())) {
      result[name] = {
        status: module.status,
        metrics: module.metrics,
      }
    }
    return result
  }

  // Private Helpers

  private sortedModules(): BaseCognitiveModule[] {
    return Array.from(this.modules.values()).sort((a, b) => b.priority - a.priority)
  }
}

/**
 * Create a pre-configured IntelligenceRegistry.
 *
 * This factory creates the registry and optionally discovers modules from the
 * intelligence directory. Legacy modules (those using createXxx factories) are
 * automatically excluded from discovery via the skipDirs set.
 *
 * @param logger - Parent logger
 * @param intelligenceDir - Absolute path to the compiled intelligence directory (optional)
 * @returns A configured registry (not yet wired or started)
 */
export async function createIntelligenceRegistry(
  logger: ILogger,
  intelligenceDir?: string,
): Promise<IntelligenceRegistry> {
  const registry = new IntelligenceRegistry(logger)

  if (intelligenceDir) {
    // Skip directories that contain legacy factory modules (already wired in createIntelligence)
    const legacyDirs = new Set([
      'base',             // This framework itself
      'memory',           // createMemory
      'continuity',       // createContinuity
      'thinker',          // createThinker
      // REMOVED: 'optimizer' — OptimizerModule deleted
      'dialectic',        // createDialecticSystem
      'ai-scientist',     // createAIScientist
      'rule-enforcer',    // createRuleEnforcer
      'subconscious',     // createSubconscious
      'team-orchestrator', // createTeamOrchestrator
      // self-healer is instantiated via createSelfHealingAgent() in createIntelligence()
      // — must be skipped here to prevent a duplicate entry in intelligence.all[]
      'self-healer',
      // These modules extend BaseCognitiveModule but are manually created in
      // createIntelligence() and wired with extra dependencies (pipeline,
      // sessionManager, pluginHost, etc.) in bootIntelligencePostPipeline().
      // Auto-discovery would create a second instance lacking those dependencies.
      'heart',                  // createHeartModule
      'dreamer',                // createDreamer
      'smart-rules',            // createSmartRulesModule
      'reflex',                 // createReflex
      'consequence-estimator',  // createConsequenceEstimator
      'trust-ledger',           // createTrustLedger
      'permission-oracle',      // createPermissionOracle
      // Also skip non-module directories
      'embeddings',
      'yang',
      'yin',
      'synthesizer',
      'serenity',
    ])

    await registry.discover(intelligenceDir, legacyDirs)
  }

  return registry
}
