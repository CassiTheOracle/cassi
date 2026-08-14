import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from './cortex.js'
import type {
  ForwardTrace, BackpropConfig, BackpropResult, TraceGradientResult,
  ActivationFunction, NeuralKindlingConfig,
} from './types.js'
import { BACKPROP_DEFAULTS, NEURAL_KINDLING_DEFAULTS } from './types.js'

/**
 * The Gradient Engine: backpropagation through forward traces during consolidation.
 *
 * During live retrieval (kindling), the forward pass records a trace of every
 * contribution — which synapse, what weight, what activation, what output.
 * When the user gives feedback ("this memory was helpful / not helpful"),
 * a gradient request is stored linking that feedback to the trace.
 *
 * During consolidation (sleep), this engine:
 * 1. Loads pending gradient requests
 * 2. Replays each forward trace in reverse to compute ∂Loss/∂weight per synapse
 * 3. Applies Adam optimizer updates to synapse weights
 *
 * This closes the learning loop: retrieval quality directly shapes connection strengths.
 *
 * Loss function:
 *   For each engram in the luminal set, if feedback says "helpful" → target = 1,
 *   "not helpful" → target = 0. Loss = (output_charge - target)².
 *   We backpropagate ∂Loss/∂weight through the recorded forward trace
 *   using the chain rule and the activation function derivative.
 */
export class GradientEngine {
  private logger: ILogger
  private config: BackpropConfig
  private activationFn: ActivationFunction
  private leakyReluSlope: number

  constructor(
    private cortex: Cortex,
    logger: ILogger,
    config?: Partial<BackpropConfig>,
    neuralConfig?: Partial<NeuralKindlingConfig>,
  ) {
    this.logger = logger.child ? logger.child('gradient-engine') : logger
    this.config = { ...BACKPROP_DEFAULTS, ...config }
    const nc = { ...NEURAL_KINDLING_DEFAULTS, ...neuralConfig }
    this.activationFn = nc.activationFn
    this.leakyReluSlope = nc.leakyReluSlope
  }

  getConfig(): BackpropConfig {
    return { ...this.config }
  }

  setConfig(config: Partial<BackpropConfig>): void {
    this.config = { ...this.config, ...config }
  }

  /**
   * Process all pending gradient requests: compute gradients and update synapse weights.
   * This is the main entry point, called from ConsolidationEngine.
   */
  async processGradients(): Promise<BackpropResult> {
    const start = Date.now()
    const requests = this.cortex.getPendingGradientRequests(this.config.batchSize)

    if (requests.length === 0) {
      return this.emptyResult(Date.now() - start)
    }

    const traceGradients: TraceGradientResult[] = []
    const processedIds: number[] = []
    let skippedStaleTraces = 0

    for (const request of requests) {
      const trace = this.cortex.getForwardTrace(request.traceId)
      if (!trace || trace.records.length < this.config.minTraceRecords) {
        skippedStaleTraces++
        processedIds.push(request.id)
        continue
      }

      const gradient = this.computeTraceGradients(trace, request.feedback)
      if (gradient.synapseGradients.size > 0) {
        traceGradients.push(gradient)
      }

      processedIds.push(request.id)
    }

    const { synapsesUpdated, avgMagnitude, maxMagnitude } =
      this.applyAggregatedGradients(traceGradients)

    if (processedIds.length > 0) {
      this.cortex.markGradientRequestsProcessed(processedIds)
    }

    const durationMs = Date.now() - start
    this.logger.info('Gradient processing complete', {
      requestsProcessed: processedIds.length,
      tracesProcessed: traceGradients.length,
      synapsesUpdated,
      avgGradientMagnitude: avgMagnitude,
      skippedStaleTraces,
      durationMs,
    })

    return {
      requestsProcessed: processedIds.length,
      tracesProcessed: traceGradients.length,
      synapsesUpdated,
      avgGradientMagnitude: avgMagnitude,
      maxGradientMagnitude: maxMagnitude,
      skippedStaleTraces,
      durationMs,
    }
  }

  /**
   * Compute per-synapse gradients from a single forward trace + feedback.
   *
   * The loss for each engram with feedback is:
   *   L(engram) = (output_charge - target)²
   *   target = 1.0 for helpful, 0.0 for not-helpful
   *
   * Then for each ForwardRecord contributing to that engram's charge:
   *   ∂L/∂weight = ∂L/∂output × ∂output/∂preActivation × ∂preActivation/∂weight
   *
   * Where:
   *   ∂L/∂output = 2 × (output_charge - target)
   *   ∂output/∂preActivation = σ'(preActivation)
   *   ∂preActivation/∂weight = sourceCharge × propagation × distDecay × temporalRelevance × potBoost × emotionalDamping
   */
  computeTraceGradients(
    trace: ForwardTrace,
    feedback: Record<string, boolean>,
  ): TraceGradientResult {
    const synapseGradients = new Map<string, number>()
    let positiveCount = 0
    let negativeCount = 0

    const targetIndex = new Map<string, typeof trace.records>()
    for (const record of trace.records) {
      const existing = targetIndex.get(record.targetId)
      if (existing) existing.push(record)
      else targetIndex.set(record.targetId, [record])
    }

    for (const [engramId, helpful] of Object.entries(feedback)) {
      if (helpful) positiveCount++
      else negativeCount++

      const outputCharge = trace.outputCharges[engramId]
      if (outputCharge === undefined) continue

      const target = helpful ? 1.0 : 0.0
      const dLoss_dOutput = 2 * (outputCharge - target)

      const contributions = targetIndex.get(engramId)
      if (!contributions) continue

      for (const record of contributions) {
        // Skip records from non-neural kindling where preActivation defaults to 0.
        // With zero preActivation, the gradient becomes zero regardless of output
        // charge, producing silent learning failures that waste compute.
        if (record.preActivation === 0 && record.activatedOutput === 0) {
          this.logger?.debug('Skipping zero-activation trace record', {
            traceId: trace.id,
            sourceId: record.sourceId,
            targetId: record.targetId,
          })
          continue
        }
        const dOutput_dPreAct = this.activationDerivative(record.preActivation)

        const dPreAct_dWeight = record.sourceCharge
          * record.propagationFactor
          * record.distDecay
          * record.temporalRelevance
          * record.potBoost
          * record.emotionalDamping

        const gradient = dLoss_dOutput * dOutput_dPreAct * dPreAct_dWeight

        const key = synapseKey(record.sourceId, record.targetId, record.edgeType)
        synapseGradients.set(key, (synapseGradients.get(key) ?? 0) + gradient)
      }
    }

    return {
      traceId: trace.id,
      synapseGradients,
      feedbackCount: Object.keys(feedback).length,
      positiveCount,
      negativeCount,
    }
  }

  /**
   * Aggregate gradients across all traces and apply Adam optimizer updates.
   *
   * Adam update rule:
   *   m_t = β₁ × m_{t-1} + (1 - β₁) × g
   *   v_t = β₂ × v_{t-1} + (1 - β₂) × g²
   *   m̂_t = m_t / (1 - β₁ᵗ)
   *   v̂_t = v_t / (1 - β₂ᵗ)
   *   w_t = w_{t-1} - α × m̂_t / (√v̂_t + ε)
   */
  applyAggregatedGradients(
    traceResults: TraceGradientResult[],
  ): { synapsesUpdated: number; avgMagnitude: number; maxMagnitude: number } {
    if (traceResults.length === 0) {
      return { synapsesUpdated: 0, avgMagnitude: 0, maxMagnitude: 0 }
    }

    const aggregated = new Map<string, number>()
    for (const result of traceResults) {
      for (const [key, grad] of result.synapseGradients) {
        aggregated.set(key, (aggregated.get(key) ?? 0) + grad)
      }
    }

    const n = traceResults.length
    for (const [key, totalGrad] of aggregated) {
      aggregated.set(key, totalGrad / n)
    }

    this.clipGradients(aggregated)

    let totalMagnitude = 0
    let maxMagnitude = 0
    const weightUpdates: Array<{ sourceId: string; targetId: string; edgeType: string; weight: number }> = []
    const optimizerUpdates: Array<{ sourceId: string; targetId: string; edgeType: string; m: number; v: number; step: number }> = []

    for (const [key, gradient] of aggregated) {
      const [sourceId, targetId, edgeType] = parseSynapseKey(key)
      const magnitude = Math.abs(gradient)
      totalMagnitude += magnitude
      maxMagnitude = Math.max(maxMagnitude, magnitude)

      const synapse = this.cortex.getSynapse(sourceId, targetId, edgeType)
      if (!synapse) continue

      const state = this.cortex.getOptimizerState(sourceId, targetId, edgeType)
      const m_prev = state?.m ?? 0
      const v_prev = state?.v ?? 0
      const step = (state?.step ?? 0) + 1

      const { beta1, beta2, epsilon, learningRate, weightMin, weightMax } = this.config

      const m = beta1 * m_prev + (1 - beta1) * gradient
      const v = beta2 * v_prev + (1 - beta2) * gradient * gradient

      const mHat = m / (1 - Math.pow(beta1, step))
      const vHat = v / (1 - Math.pow(beta2, step))

      const weightDelta = learningRate * mHat / (Math.sqrt(vHat) + epsilon)
      const newWeight = Math.max(weightMin, Math.min(weightMax, synapse.weight - weightDelta))

      weightUpdates.push({ sourceId, targetId, edgeType, weight: newWeight })
      optimizerUpdates.push({ sourceId, targetId, edgeType, m, v, step })
    }

    if (weightUpdates.length > 0) {
      this.cortex.bulkUpdateSynapseWeights(weightUpdates)
      this.cortex.bulkUpsertOptimizerStates(optimizerUpdates)
    }

    const avgMagnitude = aggregated.size > 0 ? totalMagnitude / aggregated.size : 0

    return {
      synapsesUpdated: weightUpdates.length,
      avgMagnitude,
      maxMagnitude,
    }
  }

  /**
   * Clip gradient vector by global norm to prevent exploding gradients.
   * If ‖g‖ > maxGradNorm, scale all gradients by maxGradNorm / ‖g‖.
   */
  private clipGradients(gradients: Map<string, number>): void {
    let normSq = 0
    for (const g of gradients.values()) {
      normSq += g * g
    }
    const norm = Math.sqrt(normSq)

    if (norm > this.config.maxGradNorm) {
      const scale = this.config.maxGradNorm / norm
      for (const [key, g] of gradients) {
        gradients.set(key, g * scale)
      }
    }
  }

  /**
   * Compute the derivative of the activation function at x.
   * Must match the activation function used during the forward pass.
   */
  private activationDerivative(x: number): number {
    switch (this.activationFn) {
      case 'leaky_relu':
        return x > 0 ? 1 : this.leakyReluSlope
      case 'sigmoid': {
        const s = 1 / (1 + Math.exp(-x))
        return s * (1 - s)
      }
      case 'tanh': {
        const t = Math.tanh(x)
        return 1 - t * t
      }
      case 'linear':
      default:
        return 1
    }
  }

  private emptyResult(durationMs: number): BackpropResult {
    return {
      requestsProcessed: 0,
      tracesProcessed: 0,
      synapsesUpdated: 0,
      avgGradientMagnitude: 0,
      maxGradientMagnitude: 0,
      skippedStaleTraces: 0,
      durationMs,
    }
  }
}


function synapseKey(sourceId: string, targetId: string, edgeType: string): string {
  return `${sourceId}|${targetId}|${edgeType}`
}

function parseSynapseKey(key: string): [string, string, string] {
  const parts = key.split('|')
  return [parts[0], parts[1], parts[2]]
}
