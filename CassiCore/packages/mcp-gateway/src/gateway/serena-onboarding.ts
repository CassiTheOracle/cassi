#!/usr/bin/env node
/**
 * Serena Auto-Onboarding Module
 *
 * Transparently handles Serena MCP server onboarding before any Serena tool call.
 */

import type { ILogger } from '../../types/interfaces.js'

export type ToolRouter = (name: string, args: unknown) => Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: true }>

export class SerenaAutoOnboarding {
  private onboarded = false
  private onboardingPromise: Promise<void> | null = null
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger
  }

  async ensureOnboarded(router: ToolRouter): Promise<void> {
    if (this.onboarded) return
    if (this.onboardingPromise) return this.onboardingPromise
    this.onboardingPromise = this._doOnboard(router)
    return this.onboardingPromise
  }

  private async _doOnboard(router: ToolRouter): Promise<void> {
    try {
      const check = await router('serena_check_onboarding_performed', {})
      const text = check.content?.[0]?.text ?? ''
      if (text.includes('not yet') || text.includes('false') || text.includes('No')) {
        this.logger.debug('Serena not onboarded, performing auto-onboarding')
        await router('serena_initial_instructions', {})
      }
      this.onboarded = true
      this.logger.debug('Serena auto-onboarding complete')
    } catch (err) {
      this.logger.warn('Serena auto-onboarding failed, continuing without', { error: String(err) })
      // Don't set onboarded=true so we retry next time
      this.onboardingPromise = null
    }
  }

  /** Reset state (for testing) */
  reset(): void {
    this.onboarded = false
    this.onboardingPromise = null
  }
}

/**
 * Factory function to create a new SerenaAutoOnboarding instance
 */
export function createSerenaOnboarding(logger: ILogger): SerenaAutoOnboarding {
  return new SerenaAutoOnboarding(logger)
}
