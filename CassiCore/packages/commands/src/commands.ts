/**
 * CommandDispatcher - Direct execution of slash commands
 * 
 * Intercepts /commands before they reach the LLM pipeline and
 * handles them directly via the EventBus or internal functions.
 * 
 * NOW INTEGRATED: Uses UniversalCommandProcessor for unified command handling
 * across all channels (Telegram, Chat, TUI, API, Web, CLI)
 */

import type { ILogger, IEventBus } from '../types/interfaces.js';
import type { ISessionManager } from '../types/runtime.js';
import type { IntelligenceLayer } from './intelligence/index.js';
import { bus } from './event-bus.js';
import { processor, type CommandContext as UniversalContext } from '../commands/universal-processor.js';
import '../commands/git-commands.js';
import '../commands/tool-commands.js';

export interface CommandContext {
  sessionId: string;
  channelId: string;
  args: string[];
}

export class CommandDispatcher {
  private intelligence?: IntelligenceLayer;

  constructor(
    private logger: ILogger,
    private sessions: ISessionManager,
    private eventBus: IEventBus = bus
  ) {
    this.logger = logger.child('commands');
  }

  /**
   * Set the intelligence layer for smart command handling.
   */
  setIntelligence(intelligence: IntelligenceLayer): void {
    this.intelligence = intelligence;
    this.logger.info('CommandDispatcher: Intelligence layer connected');
  }

  /**
   * Check if a message is a command and handle it if so.
   * Returns true if handled, false otherwise.
   */
  async handle(sessionId: string, channelId: string, text: string): Promise<boolean> {
    if (!text.startsWith('/')) return false;

    const parts = text.trim().split(/\s+/);
    const cmd = parts[0].slice(1).toLowerCase();
    const args = parts.slice(1);

    this.logger.info(`Handling command: /${cmd}`, { sessionId, args });

    try {
      // Get session for context
      const session = this.sessions.get(sessionId);
      if (!session) {
        this.sendDirectResponse(sessionId, channelId, '❌ Session not found');
        return true;
      }

      // Build unified command context with intelligence access
      const ctx: UniversalContext = {
        channel: 'telegram',
        userId: (session as any).userId || session.senderId || 'unknown',
        sessionId,
        projectPath: (session as any).projectPath,
        permissions: ['read', 'write', 'admin'],
        intelligence: this.intelligence ? {
          memory: this.intelligence.memory,
          thinker: this.intelligence.thinker,
          dialectic: this.intelligence.dialectic,
          contextManager: this.intelligence.contextManager,
        } : undefined,
        sessionConfig: session.config as unknown as Record<string, unknown>,
      };

      // Try UniversalCommandProcessor first
      const result = await processor.process(text, ctx);
      
      if (result) {
        this.logger.info(`Command handled by UniversalProcessor: /${cmd}`);
        
        const parseMode = result.text.includes('<') && result.text.includes('>') 
          ? 'HTML' 
          : 'MarkdownV2';
        
        if (parseMode === 'HTML') {
          this.sendDirectResponseHtml(sessionId, channelId, result.text);
        } else {
          this.sendDirectResponse(sessionId, channelId, result.text);
        }
        
        if (result.actions && result.actions.length > 0) {
          const actionText = '\n\n*Quick Actions:*\n' + 
            result.actions.map(a => `• ${a.label}: \`${a.command}\``).join('\n');
          this.sendDirectResponse(sessionId, channelId, actionText);
        }
        
        return true;
      }

      // Fall back to legacy handlers
      return await this.handleLegacy(sessionId, channelId, cmd, args);

    } catch (err) {
      this.logger.error(`Error handling command /${cmd}:`, err as any);
      this.sendDirectResponse(sessionId, channelId, `❌ Error: ${String(err)}`);
      return true;
    }
  }

  private async handleLegacy(
    sessionId: string,
    channelId: string,
    cmd: string,
    args: string[]
  ): Promise<boolean> {
    this.logger.debug(`Command falling back to legacy handler: /${cmd}`);
    
    switch (cmd) {
      case 'status':
        return await this.handleStatus(sessionId, channelId);
      case 'models':
        return await this.handleModels(sessionId, channelId, args);
      case 'thinking':
        return await this.handleThinking(sessionId, channelId, args);
      case 'new':
        return await this.handleNew(sessionId, channelId);
      case 'help':
        return await this.handleHelp(sessionId, channelId, args);
      default:
        this.sendDirectResponse(sessionId, channelId, `Unknown command: /${cmd}\nType /help for available commands.`);
        return true;
    }
  }

  private async handleStatus(sessionId: string, channelId: string): Promise<boolean> {
    const session = this.sessions.get(sessionId);
    if (!session) return false;

    const uptimeMinutes = Math.floor((Date.now() - session.createdAt.getTime()) / 60000);
    const hours = Math.floor(uptimeMinutes / 60);
    const mins = uptimeMinutes % 60;
    const uptimeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;

    const modelFull = session.config.model || 'unknown';
    const modelParts = modelFull.split('/');
    const provider = modelParts[0] || 'unknown';
    const modelName = modelParts.slice(1).join('/') || modelFull;

    const maxTokens = session.config.maxContextTokens || 100000;
    const usedTokens = session.history?.reduce((acc: number, m: any) => {
      const content = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
      return acc + Math.ceil(content.length / 4);
    }, 0) || 0;
    const contextPercent = Math.round((usedTokens / maxTokens) * 100);

    const statusHtml = `<b>🛸 CassiCore Dialectic Intelligence</b>

<i>System Overview</i>
├─ Session: <code>${sessionId.slice(-12)}</code>
├─ Uptime: ${uptimeStr}
└─ Architecture: Dialectic/Yin-Yang v2

<i>Active Mind</i>
├─ Provider: ${provider}
├─ Model: <code>${modelName}</code>
├─ Thinking: ${session.config.thinking || 'high'}
└─ Context: ~${Math.round(usedTokens/1000)}k / ${Math.round(maxTokens/1000)}k (${contextPercent}%)

<i>Intelligence Modules</i>
├─ Memory: ${this.intelligence?.memory ? '✓' : '○'}
├─ Continuity: ${this.intelligence?.continuity ? '✓' : '○'}
├─ Rule Enforcer: ${this.intelligence?.ruleEnforcer ? '✓' : '○'}
├─ Thinker: ${this.intelligence?.thinker ? '✓' : '○'}
├─ AI Scientist: ${this.intelligence?.aiScientist ? '✓' : '○'}
├─ Dialectic: ${this.intelligence?.dialectic ? '✓' : '○'}
└─ Multi-Agent: ${this.intelligence?.multiAgent ? '✓' : '○'}

<i>Commands</i>
├─ /status — Show this view
├─ /models — Switch AI model
├─ /thinking — Adjust reasoning depth
├─ /new — Fresh session
└─ /help — All commands

<i>Use /help for unified commands (git, tools, intelligence)</i>`;

    this.sendDirectResponseHtml(sessionId, channelId, statusHtml);
    return true;
  }

  private async handleModels(sessionId: string, channelId: string, args: string[]): Promise<boolean> {
    if (args.length > 0) {
      const newModel = args[0];
      const session = this.sessions.get(sessionId);
      if (session) {
        session.config.model = newModel;
        this.sendDirectResponse(sessionId, channelId, `✅ Model updated to: \`${newModel}\``);
        return true;
      }
    }

    const list = [
      `📊 *Available Models*`,
      `━━━━━━━━━━━━━━━`,
      `• \`qwen-portal/coder-model\` (Primary)`,
      `• \`kimi-coding/k2p5\` (Fallback)`,
      `• \`github-copilot/gpt-5-mini\` (Memory/Dialectic)`,
      ``,
      `💡 _Use \`/models <name>\` to switch_`
    ].join('\n');

    this.sendDirectResponse(sessionId, channelId, list);
    return true;
  }

  private async handleThinking(sessionId: string, channelId: string, args: string[]): Promise<boolean> {
    const validLevels = ['none', 'low', 'medium', 'high'];
    
    if (args.length > 0) {
      const level = args[0].toLowerCase();
      if (validLevels.includes(level)) {
        const session = this.sessions.get(sessionId);
        if (session) {
          session.config.thinking = level as any;
          this.sendDirectResponse(sessionId, channelId, `✅ Thinking level set to: \`${level}\``);
          return true;
        }
      } else {
        this.sendDirectResponse(sessionId, channelId, `❌ Invalid level. Use: ${validLevels.join(', ')}`);
        return true;
      }
    }

    this.sendDirectResponse(sessionId, channelId, `Current thinking level: \`${this.sessions.get(sessionId)?.config.thinking || 'high'}\``);
    return true;
  }

  private async handleNew(sessionId: string, channelId: string): Promise<boolean> {
    const session = this.sessions.get(sessionId);
    if (session) {
      (session as any).history = [];
      (session as any).createdAt = new Date();
      this.eventBus.emit({
        type: 'session:reset',
        sessionId,
        reason: 'user_requested_new'
      } as any);
    }
    
    const welcomeHtml = `<b>🌙 New Session Started</b>

<i>Previous context cleared. Starting fresh!</i>

<b>Active Configuration:</b>
├─ Primary: qwen-portal/coder-model
├─ Fallback: kimi-coding/k2p5
├─ Memory: github-copilot/gpt-5-mini
└─ Dialectic: Yang → Yin → Serenity

<i>Commands: /status /models /thinking /help</i>`;

    this.sendDirectResponseHtml(sessionId, channelId, welcomeHtml);
    return true;
  }

  private async handleHelp(sessionId: string, channelId: string, args: string[]): Promise<boolean> {
    const category = args[0];
    const universalHelp = processor.getHelp(category);
    
    const help = [
      `📜 *CassiCore Commands*`,
      `━━━━━━━━━━━━━━━`,
      `*Legacy Commands:*`,
      `• \`/new\` - Start a fresh session`,
      `• \`/status\` - System & session details`,
      `• \`/models\` - List or switch AI models`,
      `• \`/thinking\` - Adjust reasoning depth`,
      ``,
      universalHelp,
      ``,
      `💡 Use /help <category> for specific: system, git, tools, intelligence, help`,
    ].join('\n');
    
    this.sendDirectResponse(sessionId, channelId, help);
    return true;
  }

  private sendDirectResponse(sessionId: string, channelId: string, content: string): void {
    this.eventBus.emit({
      type: 'worker:message',
      pluginId: `session:${sessionId}`,
      payload: { 
        type: 'turn:direct_message', 
        sessionId,
        content,
        parse_mode: 'MarkdownV2'
      }
    } as any);
  }

  private sendDirectResponseHtml(sessionId: string, channelId: string, content: string): void {
    this.eventBus.emit({
      type: 'worker:message',
      pluginId: `session:${sessionId}`,
      payload: { 
        type: 'turn:direct_message', 
        sessionId,
        content,
        parse_mode: 'HTML'
      }
    } as any);
  }
}
