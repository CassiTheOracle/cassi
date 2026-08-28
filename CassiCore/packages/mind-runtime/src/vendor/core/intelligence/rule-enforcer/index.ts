/**
 * RuleEnforcer — Compliance and Alignment Monitor
 * 
 * Ensures Cassi follows rules from SOUL.md, AGENTS.md, and philosophical guidelines.
 * Runs checks on responses and behavior patterns.
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

import { PathManager } from '../../workspace/paths.js';

import type { IMemory } from '@cassicore/foundation';
import type { IEventBus , ILogger } from '@cassicore/foundation';

export interface RuleEnforcerConfig {
  enabled: boolean;
  strictMode?: boolean;        // If true, blocks on violations
  selfCorrect?: boolean;       // If true, auto-corrects before sending
  logViolations?: boolean;     // Log to memory for learning
  sensitivity?: number;        // 0-1, how strict the checks are
}

export interface ComplianceCheck {
  rule: string;
  source: 'soul' | 'agents' | 'philosophy';
  passed: boolean;
  severity: 'low' | 'medium' | 'high';
  message?: string;
}

export interface RuleSet {
  soul: string[];
  agents: string[];
  philosophy: string[];
}

export class RuleEnforcer {
  readonly name = 'rule-enforcer';
  readonly priority = 100;  // High priority - runs early
  
  private logger: ILogger;
  private config: RuleEnforcerConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;
  private rules: RuleSet = { soul: [], agents: [], philosophy: [] };
  private workspacePath: string;
  private violationCount = 0;
  private correctionCount = 0;

  constructor(logger: ILogger, config?: Partial<RuleEnforcerConfig>) {
    this.logger = logger.child?.('rule-enforcer') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      strictMode: config?.strictMode ?? false,
      selfCorrect: config?.selfCorrect ?? true,
      logViolations: config?.logViolations ?? true,
      sensitivity: config?.sensitivity ?? 0.7,
    };
    
    this.workspacePath = PathManager.resolve('workspace-main', 'cassi');
    
    if (this.config.enabled) {
      this.loadRules();
      this.logger.info('RuleEnforcer: enabled', { 
        strictMode: this.config.strictMode,
        selfCorrect: this.config.selfCorrect,
        sensitivity: this.config.sensitivity,
        rulesLoaded: this.rules.soul.length + this.rules.agents.length + this.rules.philosophy.length
      });
    } else {
      this.logger.info('RuleEnforcer: disabled');
    }
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.logger.info('RuleEnforcer: memory wired');
  }

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('RuleEnforcer: event bus wired');
    
    // Listen for responses to check
    (bus as any).on?.('response:pre-send', (e: any) => {
      void this.checkResponse(e.response, e.context);
    });
    
    // Listen for violations flagged by other modules
    (bus as any).on?.('compliance:violation', (e: any) => {
      void this.handleViolation(e);
    });
  }

  /**
   * Load rules from SOUL.md, AGENTS.md, and philosophy files
   */
  private loadRules(): void {
    try {
      // Load SOUL.md
      const soulPath = join(this.workspacePath, 'SOUL.md');
      if (existsSync(soulPath)) {
        const soulContent = readFileSync(soulPath, 'utf-8');
        this.rules.soul = this.extractRules(soulContent, 'soul');
      }
      
      // Load AGENTS.md
      const agentsPath = join(this.workspacePath, 'AGENTS.md');
      if (existsSync(agentsPath)) {
        const agentsContent = readFileSync(agentsPath, 'utf-8');
        this.rules.agents = this.extractRules(agentsContent, 'agents');
      }
      
      // Load philosophy from SOUL.md "Core Truths" section
      this.rules.philosophy = [
        'Be genuinely helpful, not performatively helpful',
        'Skip filler words like "Great question!"',
        'Have opinions and preferences',
        'Be resourceful before asking',
        'Respect boundaries (privacy, group chat etiquette)',
        'Know when to speak vs stay silent',
        'Be concise when needed, thorough when it matters',
        'Not a corporate drone, not a sycophant',
        'Remember I am a guest in user\'s life',
        'Quality over quantity in responses',
        // Meta-cognition: use introspection tools for self-awareness
        'Use introspection tools (cassi_*) rather than speculating about internal state',
        'When uncertain about own behavior, check activity or trace before guessing',
        'Periodically review blindspots to identify systematic gaps',
        'Ground self-assessments in effectiveness data, not assumptions',
      ];
      
      this.logger.info('RuleEnforcer: rules loaded', {
        soul: this.rules.soul.length,
        agents: this.rules.agents.length,
        philosophy: this.rules.philosophy.length,
      });
    } catch (error) {
      this.logger.error('RuleEnforcer: failed to load rules', { error: String(error) });
    }
  }

  /**
   * Extract rules from markdown content
   */
  private extractRules(content: string, source: string): string[] {
    const rules: string[] = [];
    
    // Look for bullet points, numbered lists, and headers
    const lines = content.split('\n');
    
    for (const line of lines) {
      const trimmed = line.trim();
      
      // Match bullet points and numbered lists
      if (trimmed.match(/^[\*\-\•]\s+/) || trimmed.match(/^\d+\.\s+/)) {
        const rule = trimmed.replace(/^[\*\-\•\d\.\s]+/, '').trim();
        if (rule.length > 10 && rule.length < 200) {
          rules.push(rule);
        }
      }
      
      // Match headers that look like rules
      if (trimmed.match(/^#{1,3}\s+/) && !trimmed.includes('---')) {
        const rule = trimmed.replace(/^#{1,3}\s+/, '').trim();
        if (rule.length > 5 && rule.length < 100) {
          rules.push(rule);
        }
      }
    }
    
    return rules.slice(0, 50);  // Limit to top 50 rules
  }

  /**
   * Check a response for compliance
   */
  async checkResponse(response: string, context: any): Promise<ComplianceCheck[]> {
    if (!this.config.enabled) return [];
    
    const checks: ComplianceCheck[] = [];
    const responseLower = response.toLowerCase();
    
    // Check SOUL.md rules
    for (const rule of this.rules.soul) {
      const check = this.evaluateRule(rule, response, 'soul', responseLower);
      if (check) checks.push(check);
    }
    
    // Check AGENTS.md rules
    for (const rule of this.rules.agents) {
      const check = this.evaluateRule(rule, response, 'agents', responseLower);
      if (check) checks.push(check);
    }
    
    // Check philosophy rules
    checks.push(...this.checkPhilosophy(response, responseLower));
    
    // Handle violations
    const violations = checks.filter(c => !c.passed);
    if (violations.length > 0) {
      this.violationCount += violations.length;
      
      if (this.config.logViolations) {
        await this.logViolations(violations, response);
      }
      
      if (this.config.selfCorrect) {
        // Emit correction event
        (this.eventBus as any)?.emit({
          type: 'rule-enforcer:correction-needed',
          violations: violations.map(v => ({ rule: v.rule, severity: v.severity })),
          originalResponse: response.slice(0, 200),
        });
      }
      
      this.logger.info('RuleEnforcer: violations detected', {
        count: violations.length,
        highSeverity: violations.filter(v => v.severity === 'high').length,
      });
    }
    
    return checks;
  }

  /**
   * Evaluate a specific rule against a response
   */
  private evaluateRule(rule: string, response: string, source: 'soul' | 'agents' | 'philosophy', responseLower: string): ComplianceCheck | null {
    // Skip if rule is too vague
    if (rule.length < 10) return null;
    
    const ruleLower = rule.toLowerCase();
    
    // Check for specific violation patterns
    
    // Filler words check
    if (ruleLower.includes('filler') || ruleLower.includes('great question')) {
      const fillers = ['great question', 'happy to help', 'i\'d be happy', 'i would love', 'gladly'];
      const hasFiller = fillers.some(f => responseLower.includes(f));
      return {
        rule: 'Avoid filler words',
        source,
        passed: !hasFiller,
        severity: hasFiller ? 'medium' : 'low',
        message: hasFiller ? 'Response contains filler words' : undefined,
      };
    }
    
    // Corporate speak check
    if (ruleLower.includes('corporate') || ruleLower.includes('drone')) {
      const corporate = ['leverage', 'synergy', 'paradigm', 'moving forward', 'circle back', 'touch base'];
      const hasCorporate = corporate.some(c => responseLower.includes(c));
      return {
        rule: 'Avoid corporate speak',
        source,
        passed: !hasCorporate,
        severity: hasCorporate ? 'high' : 'low',
        message: hasCorporate ? 'Response contains corporate jargon' : undefined,
      };
    }
    
    // Opinion check - ensure we have opinions
    if (ruleLower.includes('opinion') || ruleLower.includes('preference')) {
      const weakPhrases = ['it depends', 'some people', 'others may', 'there are different'];
      const hasWeak = weakPhrases.some(p => responseLower.includes(p));
      // This is a heuristic - weak phrases might indicate lack of opinion
      return {
        rule: 'Have opinions and preferences',
        source,
        passed: !hasWeak || response.length > 100,  // Allow weak if detailed
        severity: 'low',
        message: hasWeak ? 'Consider expressing a clear opinion' : undefined,
      };
    }
    
    return null;  // Rule not applicable or couldn't be evaluated
  }

  /**
   * Check philosophical guidelines
   */
  private checkPhilosophy(response: string, responseLower: string): ComplianceCheck[] {
    const checks: ComplianceCheck[] = [];
    
    // Check for over-helpfulness in group chats
    if (response.length < 50 && response.match(/^(yes|no|yeah|sure|ok|okay)$/i)) {
      checks.push({
        rule: 'Quality over quantity - avoid minimal responses',
        source: 'philosophy',
        passed: false,
        severity: 'low',
        message: 'Very short response - consider if this adds value',
      });
    }
    
    // Check for performative helpfulness
    const performativePatterns = [
      /i hope this helps/i,
      /let me know if you need/i,
      /feel free to ask/i,
      /i\'m here to help/i,
    ];
    const hasPerformative = performativePatterns.some(p => p.test(response));
    if (hasPerformative) {
      checks.push({
        rule: 'Avoid performative helpfulness',
        source: 'philosophy',
        passed: false,
        severity: 'medium',
        message: 'Response ends with performative offer',
      });
    }
    
    // Check response length appropriateness
    if (response.length > 2000) {
      checks.push({
        rule: 'Be concise when needed',
        source: 'philosophy',
        passed: false,
        severity: 'low',
        message: 'Very long response - could be more concise',
      });
    }
    
    // Check for speculation about internal state when introspection tools exist
    const introspectionSpeculation = [
      /i think my .*(memory|dialectic|thinker|subconscious|optimizer).*(is|was|might)/i,
      /i believe my internal .*(state|process)/i,
      /my cognitive .*(module|system).*(probably|likely|might|may)/i,
    ];
    const speculatesAboutInternals = introspectionSpeculation.some(p => p.test(response));
    if (speculatesAboutInternals) {
      checks.push({
        rule: 'Use introspection tools instead of speculating about internal state',
        source: 'philosophy',
        passed: false,
        severity: 'medium',
        message: 'Speculating about internal cognitive state — use activity, trace, or thinker instead',
      });
    }
    
    return checks;
  }

  /**
   * Log violations for learning
   */
  private async logViolations(violations: ComplianceCheck[], response: string): Promise<void> {
    if (!this.memory) return;
    
    try {
      await this.memory.store({
        type: 'reflection',
        content: JSON.stringify({
          violations: violations.map(v => ({ rule: v.rule, severity: v.severity })),
          responsePreview: response.slice(0, 100),
          timestamp: Date.now(),
        }),
        metadata: {
          violationCount: violations.length,
          highSeverityCount: violations.filter(v => v.severity === 'high').length,
        },
      });
    } catch (error) {
      this.logger.warn('RuleEnforcer: failed to log violations', { error: String(error) });
    }
  }

  /**
   * Handle violation events from other modules
   */
  private async handleViolation(event: any): Promise<void> {
    this.logger.info('RuleEnforcer: violation reported by other module', {
      rule: event.rule,
      source: event.source,
    });
    
    // Could trigger immediate correction or escalation
    if (event.severity === 'high' && this.config.strictMode) {
      (this.eventBus as any)?.emit({
        type: 'rule-enforcer:block',
        reason: event.rule,
        details: event,
      });
    }
  }

  /**
   * Get current compliance stats
   */
  getStats(): { violations: number; corrections: number; rulesLoaded: number } {
    return {
      violations: this.violationCount,
      corrections: this.correctionCount,
      rulesLoaded: this.rules.soul.length + this.rules.agents.length + this.rules.philosophy.length,
    };
  }

  /**
   * Manual check function for testing
   */
  async manualCheck(response: string): Promise<ComplianceCheck[]> {
    return this.checkResponse(response, {});
  }
}

export const createRuleEnforcer = (logger: ILogger, config?: Partial<RuleEnforcerConfig>): RuleEnforcer =>
  new RuleEnforcer(logger, config);
