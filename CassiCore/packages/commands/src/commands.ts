/**
 * CommandDispatcher - Direct execution of slash commands
 * 
 * Intercepts /commands before they reach the LLM pipeline and
 * handles them directly via the EventBus or internal functions.
 */

import type { ILogger, IEventBus } from '../types/interfaces.js';
import type { ISessionManager } from '../types/runtime.js';
import { bus } from './event-bus.js';

export interface CommandContext {
  sessionId: string;
  channelId: string;
  args: string[];
}

export class CommandDispatcher {
  constructor(
    private logger: ILogger,
    private sessions: ISessionManager,
    private eventBus: IEventBus = bus
  ) {
    this.logger = logger.child('commands');
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
      switch (cmd) {
        case 'status':
          return await this.handleStatus({ sessionId, channelId, args });
        case 'models':
          return await this.handleModels({ sessionId, channelId, args });
        case 'thinking':
          return await this.handleThinking({ sessionId, channelId, args });
        case 'new':
          return await this.handleNew({ sessionId, channelId, args });
        case 'help':
          return await this.handleHelp({ sessionId, channelId, args });
        default:
          this.sendDirectResponse(sessionId, channelId, `Unknown command: /${cmd}\nType /help for available commands.`);
          return true;
      }
    } catch (err) {
      this.logger.error(`Error handling command /${cmd}:`, err as any);
      this.sendDirectResponse(sessionId, channelId, `❌ Error: ${String(err)}`);
      return true;
    }
  }

  private async handleStatus(ctx: CommandContext): Promise<boolean> {
    const session = this.sessions.get(ctx.sessionId);
    if (!session) return false;

    const uptimeMinutes = Math.floor((Date.now() - session.createdAt.getTime()) / 60000);
    const hours = Math.floor(uptimeMinutes / 60);
    const mins = uptimeMinutes % 60;
    const uptimeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;

    // Extract provider and model name
    const modelFull = session.config.model || 'unknown';
    const modelParts = modelFull.split('/');
    const provider = modelParts[0] || 'unknown';
    const modelName = modelParts.slice(1).join('/') || modelFull;

    // Get context window info
    const maxTokens = session.config.maxContextTokens || 100000;
    const usedTokens = session.history?.reduce((acc: number, m: any) => {
      const content = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
      return acc + Math.ceil(content.length / 4);
    }, 0) || 0;
    const contextPercent = Math.round((usedTokens / maxTokens) * 100);

    // Build comprehensive status using Telegram HTML (more reliable than MarkdownV2)
    const statusHtml = `<b>🛸 CassiCore Dialectic Intelligence</b>

<i>System Overview</i>
├─ Session: <code>${ctx.sessionId.slice(-12)}</code>
├─ Uptime: ${uptimeStr}
└─ Architecture: Dialectic/Yin-Yang v2

<i>Active Mind</i>
├─ Provider: ${provider}
├─ Model: <code>${modelName}</code>
├─ Thinking: ${session.config.thinking || 'high'}
└─ Context: ~${Math.round(usedTokens/1000)}k / ${Math.round(maxTokens/1000)}k (${contextPercent}%)

<i>Intelligence Modules</i>
├─ Memory: ✓
├─ Continuity: ✓
├─ Rule Enforcer: ✓
├─ Thinker: ✓
├─ AI Scientist: ✓
├─ Dialectic: ✓
└─ Multi-Agent: ✓

<i>Current Settings</i>
├─ Mode: ${session.config.thinking === 'high' ? 'Deep Reasoning' : 'Fast Response'}
├─ Tool Use: Enabled
├─ MCP Servers: Serena, SCIP
└─ Rules: SOUL.md enforced

<i>Use /models to switch provider • /thinking to adjust depth</i>`;

    this.sendDirectResponseHtml(ctx.sessionId, ctx.channelId, statusHtml);
    return true;
  }

  private async handleModels(ctx: CommandContext): Promise<boolean> {
    // If an argument is provided, try to change the model
    if (ctx.args.length > 0) {
      const newModel = ctx.args[0];
      const session = this.sessions.get(ctx.sessionId);
      if (session) {
        session.config.model = newModel;
        this.sendDirectResponse(ctx.sessionId, ctx.channelId, `✅ Model updated to: \`${newModel}\``);
        return true;
      }
    }

    // Otherwise list models (updated for available providers)
    const list = [
      `📊 *Available Models*`,
      `━━━━━━━━━━━━━━━`,
      `• \`qwen-portal/coder-model\` (Primary)`,
      `• \`kimi-coding/k2p5\` (Fallback)`,
      `• \`github-copilot/gpt-5-mini\` (Memory/Dialectic)`,
      ``,
      `💡 _Use \`/models <name>\` to switch_`
    ].join('\n');

    this.sendDirectResponse(ctx.sessionId, ctx.channelId, list);
    return true;
  }

  private async handleThinking(ctx: CommandContext): Promise<boolean> {
    const validLevels = ['none', 'low', 'medium', 'high'];
    
    if (ctx.args.length > 0) {
      const level = ctx.args[0].toLowerCase();
      if (validLevels.includes(level)) {
        const session = this.sessions.get(ctx.sessionId);
        if (session) {
          session.config.thinking = level as any;
          this.sendDirectResponse(ctx.sessionId, ctx.channelId, `✅ Thinking level set to: \`${level}\``);
          return true;
        }
      } else {
        this.sendDirectResponse(ctx.sessionId, ctx.channelId, `❌ Invalid level. Use: ${validLevels.join(', ')}`);
        return true;
      }
    }

    this.sendDirectResponse(ctx.sessionId, ctx.channelId, `Current thinking level: \`${this.sessions.get(ctx.sessionId)?.config.thinking || 'high'}\``);
    return true;
  }

  private async handleNew(ctx: CommandContext): Promise<boolean> {
    const session = this.sessions.get(ctx.sessionId);
    if (session) {
      // Actually clear the session history
      (session as any).history = [];
      
      // Reset session creation time to show fresh uptime
      (session as any).createdAt = new Date();
      
      // Emit session reset event for any listeners
      this.eventBus.emit({
        type: 'session:reset',
        sessionId: ctx.sessionId,
        reason: 'user_requested_new'
      } as any);
    }
    
    // Create new session message
    const welcomeHtml = `<b>🌙 New Session Started</b>

<i>Previous context cleared. Starting fresh!</i>

<b>Active Configuration:</b>
├─ Primary: qwen-portal/coder-model
├─ Fallback: kimi-coding/k2p5
├─ Memory: github-copilot/gpt-5-mini
└─ Dialectic: Yang → Yin → Synthesizer

<i>Commands: /status /models /thinking /help</i>`;

    this.sendDirectResponseHtml(ctx.sessionId, ctx.channelId, welcomeHtml);
    return true;
  }

  private handleHelp(ctx: CommandContext): Promise<boolean> {
    const help = [
      `📜 *CassiCore Commands*`,
      `━━━━━━━━━━━━━━━`,
      `• \`/new\` - Start a fresh session (clears history)`,
      `• \`/status\` - Show system & session details`,
      `• \`/models\` - List or switch AI models`,
      `• \`/thinking\` - List or set thinking level`,
      `• \`/help\` - Show this message`,
    ].join('\n');
    
    this.sendDirectResponse(ctx.sessionId, ctx.channelId, help);
    return Promise.resolve(true);
  }

  private sendDirectResponse(sessionId: string, channelId: string, content: string): void {
    // This bypasses the pipeline and sends straight to the channel
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
    // HTML version for complex formatting (more reliable than MarkdownV2)
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
