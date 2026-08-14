import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { 
  getModel, 
  getProviders, 
  getModels, 
  calculateCost, 
  supportsXhigh, 
  modelsAreEqual 
} from '../src/models.js'
import { MODELS } from '../src/models.generated.js'
import type { Model } from '../src/types.js'

/**
 * AI Model Defaults - Functional Tests
 * 
 * Tests the exported functions from ai/src/models.ts that provide
 * model default configuration and utilities.
 */

describe('AI Model Defaults - Functional Tests', () => {
  describe('getProviders', () => {
    it('returns array of registered provider names', () => {
      const providers = getProviders()
      expect(Array.isArray(providers)).toBe(true)
      expect(providers.length).toBeGreaterThan(0)
    })

    it('includes amazon-bedrock provider', () => {
      const providers = getProviders()
      expect(providers).toContain('amazon-bedrock')
    })

    it('returns providers that match MODELS keys', () => {
      const providers = getProviders()
      const modelKeys = Object.keys(MODELS)
      providers.forEach(provider => {
        expect(modelKeys).toContain(provider)
      })
    })
  })

  describe('getModels', () => {
    it('returns array of models for a provider', () => {
      const models = getModels('amazon-bedrock')
      expect(Array.isArray(models)).toBe(true)
      expect(models.length).toBeGreaterThan(0)
    })

    it('returns empty array for unknown provider', () => {
      const models = getModels('unknown-provider' as any)
      expect(models).toEqual([])
    })

    it('returns models with required properties', () => {
      const models = getModels('amazon-bedrock')
      expect(models.length).toBeGreaterThan(0)
      const model = models[0]
      expect(model).toHaveProperty('id')
      expect(model).toHaveProperty('provider')
      expect(model).toHaveProperty('api')
      expect(model).toHaveProperty('cost')
      expect(model).toHaveProperty('contextWindow')
      expect(model).toHaveProperty('maxTokens')
    })

    it('model ids match MODELS configuration', () => {
      const models = getModels('amazon-bedrock')
      const modelIds = models.map(m => m.id)
      const configuredIds = Object.keys(MODELS['amazon-bedrock'])
      configuredIds.forEach(id => {
        expect(modelIds).toContain(id)
      })
    })
  })

  describe('getModel', () => {
    it('returns specific model by provider and id', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(model).toBeDefined()
      expect(model.id).toBe('amazon.nova-lite-v1:0')
      expect(model.provider).toBe('amazon-bedrock')
    })

    it('returns undefined for unknown model', () => {
      const model = getModel('amazon-bedrock', 'unknown-model' as any)
      expect(model).toBeUndefined()
    })

    it('returns undefined for unknown provider', () => {
      const model = getModel('unknown-provider' as any, 'some-model' as any)
      expect(model).toBeUndefined()
    })

    it('model has correct cost structure', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(model.cost).toHaveProperty('input')
      expect(model.cost).toHaveProperty('output')
      expect(model.cost).toHaveProperty('cacheRead')
      expect(model.cost).toHaveProperty('cacheWrite')
    })

    it('model has reasoning flag', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(typeof model.reasoning).toBe('boolean')
    })

    it('model has input types array', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(Array.isArray(model.input)).toBe(true)
    })

    it('retrieves Nova Premier with reasoning enabled', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-premier-v1:0')
      expect(model.reasoning).toBe(true)
    })

    it('retrieves Nova Lite with reasoning disabled', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(model.reasoning).toBe(false)
    })
  })

  describe('calculateCost', () => {
    it('calculates cost based on usage', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      const usage = {
        input: 1000000,
        output: 500000,
        cacheRead: 0,
        cacheWrite: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      
      const cost = calculateCost(model, usage)
      
      // nova-lite-v1:0 costs $0.06/1M input, $0.24/1M output
      expect(cost.input).toBeCloseTo(0.06, 4)
      expect(cost.output).toBeCloseTo(0.12, 4)
      expect(cost.total).toBeCloseTo(0.18, 4)
    })

    it('calculates cache read costs', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      const usage = {
        input: 0,
        output: 0,
        cacheRead: 1000000,
        cacheWrite: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      
      const cost = calculateCost(model, usage)
      expect(cost.cacheRead).toBeCloseTo(0.015, 4)
    })

    it('calculates cache write costs', () => {
      const model = getModel('amazon-bedrock', 'anthropic.claude-3-5-haiku-20241022-v1:0')
      const usage = {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 1000000,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      
      const cost = calculateCost(model, usage)
      expect(cost.cacheWrite).toBeCloseTo(1.0, 4)
    })

    it('returns total as sum of all cost components', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      const usage = {
        input: 1000000,
        output: 1000000,
        cacheRead: 1000000,
        cacheWrite: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      
      const cost = calculateCost(model, usage)
      expect(cost.total).toBeCloseTo(cost.input + cost.output + cost.cacheRead + cost.cacheWrite, 4)
    })

    it('handles zero usage', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      const usage = {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      
      const cost = calculateCost(model, usage)
      expect(cost.total).toBe(0)
    })

    it('scales linearly with usage', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      
      const usage1 = {
        input: 1000000,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      const usage2 = {
        input: 2000000,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
      }
      
      const cost1 = calculateCost(model, usage1)
      const cost2 = calculateCost(model, usage2)
      
      expect(cost2.input).toBeCloseTo(cost1.input * 2, 4)
    })
  })

  describe('supportsXhigh', () => {
    it('returns true for GPT-5.2 models', () => {
      // Create a mock GPT-5.2 model
      const mockModel = {
        id: 'gpt-5.2-turbo',
        provider: 'openai',
        api: 'chat-completions' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096,
        reasoning: true,
        input: ['text'] as const
      }
      
      expect(supportsXhigh(mockModel as any)).toBe(true)
    })

    it('returns true for GPT-5.3 models', () => {
      const mockModel = {
        id: 'gpt-5.3-preview',
        provider: 'openai',
        api: 'chat-completions' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096,
        reasoning: true,
        input: ['text'] as const
      }
      
      expect(supportsXhigh(mockModel as any)).toBe(true)
    })

    it('returns true for Opus 4.6 models', () => {
      const mockModel = {
        id: 'claude-opus-4-6',
        provider: 'anthropic',
        api: 'anthropic-messages' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 200000,
        maxTokens: 8192,
        reasoning: true,
        input: ['text'] as const
      }
      
      expect(supportsXhigh(mockModel as any)).toBe(true)
    })

    it('returns true for Opus 4.6 with dot notation', () => {
      const mockModel = {
        id: 'claude-opus-4.6-sonnet',
        provider: 'anthropic',
        api: 'anthropic-messages' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 200000,
        maxTokens: 8192,
        reasoning: true,
        input: ['text'] as const
      }
      
      expect(supportsXhigh(mockModel as any)).toBe(true)
    })

    it('returns false for non-supported models', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(supportsXhigh(model)).toBe(false)
    })

    it('returns false for models without xhigh in id', () => {
      const mockModel = {
        id: 'gpt-4-turbo',
        provider: 'openai',
        api: 'chat-completions' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096,
        reasoning: false,
        input: ['text'] as const
      }
      
      expect(supportsXhigh(mockModel as any)).toBe(false)
    })

    it('returns false for non-anthropic-messages API models', () => {
      const mockModel = {
        id: 'claude-opus-4-6',
        provider: 'anthropic',
        api: 'chat-completions' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 200000,
        maxTokens: 8192,
        reasoning: true,
        input: ['text'] as const
      }
      
      expect(supportsXhigh(mockModel as any)).toBe(false)
    })
  })

  describe('modelsAreEqual', () => {
    it('returns true for identical models', () => {
      const model1 = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      const model2 = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      
      expect(modelsAreEqual(model1, model2)).toBe(true)
    })

    it('returns false for different model ids', () => {
      const model1 = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      const model2 = getModel('amazon-bedrock', 'amazon.nova-pro-v1:0')
      
      expect(modelsAreEqual(model1, model2)).toBe(false)
    })

    it('returns false for same id but different providers', () => {
      const mockModel1: Model<any> = {
        id: 'gpt-4',
        provider: 'openai',
        api: 'chat-completions' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096,
        reasoning: false,
        input: ['text'] as const
      }
      const mockModel2: Model<any> = {
        id: 'gpt-4',
        provider: 'azure',
        api: 'chat-completions' as const,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096,
        reasoning: false,
        input: ['text'] as const
      }
      
      expect(modelsAreEqual(mockModel1, mockModel2)).toBe(false)
    })

    it('returns false when first model is null', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(modelsAreEqual(null, model)).toBe(false)
    })

    it('returns false when second model is null', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(modelsAreEqual(model, null)).toBe(false)
    })

    it('returns false when both models are null', () => {
      expect(modelsAreEqual(null, null)).toBe(false)
    })

    it('returns false when first model is undefined', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(modelsAreEqual(undefined, model)).toBe(false)
    })

    it('returns false when second model is undefined', () => {
      const model = getModel('amazon-bedrock', 'amazon.nova-lite-v1:0')
      expect(modelsAreEqual(model, undefined)).toBe(false)
    })
  })
})
