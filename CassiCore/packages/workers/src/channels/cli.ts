/**
 * CLI Channel Worker
 * 
 * Full bidirectional streaming CLI channel with intelligence integration.
 * Handles communication between CLI clients and CassiCore intelligence layer.
 */

import { workerPort } from '../../core/worker-ipc.js'
import type { ILogger } from "../../types/interfaces.js";
import type { HostMessage, WorkerMessage, WorkerToHostMessage } from "../../types/worker-messages.js";

interface CliMessage {
  type: string;
  payload?: {
    command?: string;
    args?: string[];
    sessionId?: string;
    userId?: string;
    projectPath?: string;
    config?: Record<string, unknown>;
    // Streaming response fields from daemon
    content?: string;
    done?: boolean;
  };
}

interface CliContext {
  sessionId: string;
  userId: string;
  projectPath?: string;
  startTime: number;
}

interface CommandResult {
  text: string;
  attachments?: { type: "image" | "file"; path: string }[];
  actions?: { label: string; command: string }[];
  error?: string;
}

class CliChannelWorker {
  private pp = workerPort;
  private activeSessions = new Map<string, CliContext>();
  // WHY: Intelligence modules run in the main process; workers communicate via messages.
  // The intelligence property is kept for API compatibility but should not be used.
  private intelligence?: unknown;
  private logger?: ILogger;
  private isReady = false;

  constructor() {
    this.pp.on("message", this.handleMessage.bind(this));
    this.logger = {
      debug: (msg: string, meta?: Record<string, unknown>) => 
        this.log("debug", msg, meta),
      info: (msg: string, meta?: Record<string, unknown>) => 
        this.log("info", msg, meta),
      warn: (msg: string, meta?: Record<string, unknown>) => 
        this.log("warn", msg, meta),
      error: (msg: string, meta?: Record<string, unknown>) => 
        this.log("error", msg, meta),
      child: (component: string) => ({
        debug: (msg: string, meta?: Record<string, unknown>) => 
          this.log("debug", `[${component}] ${msg}`, meta),
        info: (msg: string, meta?: Record<string, unknown>) => 
          this.log("info", `[${component}] ${msg}`, meta),
        warn: (msg: string, meta?: Record<string, unknown>) => 
          this.log("warn", `[${component}] ${msg}`, meta),
        error: (msg: string, meta?: Record<string, unknown>) => 
          this.log("error", `[${component}] ${msg}`, meta),
        child: () => this.logger!,
      }),
    };
  }

  private log(level: string, msg: string, meta?: Record<string, unknown>): void {
    this.pp.postMessage({
      type: "log",
      payload: { level, message: msg, meta, timestamp: new Date().toISOString() },
    });
  }

  private async handleMessage(msg: CliMessage): Promise<void> {
    try {
      switch (msg.type) {
        case "init":
          await this.handleInit(msg);
          break;
        case "message":
          await this.handleCommand(msg);
          break;
        case "intelligence:inject":
          await this.handleIntelligenceInject(msg);
          break;
        case "config:update":
          await this.handleConfigUpdate(msg);
          break;
        case "shutdown":
          await this.handleShutdown();
          break;
        default:
          this.sendError(`Unknown message type: ${msg.type}`);
      }
    } catch (err) {
      const errorInfo: Record<string, unknown> = {
        operation: 'message_handler',
        message: err instanceof Error ? err.message : String(err),
      }
      if (err instanceof Error && err.stack) {
        errorInfo.stack = err.stack
      }
      this.logger?.error('CLI handler error', errorInfo)
      this.sendError(`Handler error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  private async handleInit(msg: CliMessage): Promise<void> {
    this.logger?.info("CLI channel initializing", { payload: msg.payload });
    
    // Store config if provided
    if (msg.payload?.config) {
      // Config would be used to initialize intelligence layer
      // In practice, intelligence is injected via separate message
    }

    this.isReady = true;
    this.pp.postMessage({ type: "ready", payload: { version: "0.1.0", name: "CassiCLI" } });
    this.logger?.info("CLI channel ready");
  }

  private async handleIntelligenceInject(msg: CliMessage): Promise<void> {
    // Intelligence layer injected from parent process
    // WHY: Workers should not hold references to core intelligence modules.
    // This method is kept for backward compatibility but the intelligence
    // should be accessed via message passing, not direct method calls.
    this.intelligence = msg.payload as unknown;
    this.logger?.info("Intelligence layer reference received", {
      modules: this.intelligence && typeof this.intelligence === 'object'
        ? Object.keys(this.intelligence).filter(k => k !== "all")
        : [],
    });
    this.pp.postMessage({ type: "intelligence:ready" } satisfies WorkerToHostMessage);
  }

  private async handleCommand(msg: CliMessage): Promise<void> {
    const { command, args, sessionId, userId, projectPath, content, done } = msg.payload || {};

    // Handle streaming messages from daemon (content/done) vs command messages
    if (!command) {
      if (content !== undefined) {
        // Streaming message from daemon - output to stdout
        process.stdout.write(content);
        if (done) {
          process.stdout.write('\n');
        }
        return;
      }
      this.sendError("No command provided");
      return;
    }

    // Check if this is a user message (not a slash command)
    // User messages should be forwarded to the daemon for turn pipeline processing
    if (!command.startsWith('/')) {
      // Parse potential model argument: "message --model github-copilot/gpt-5-mini"
      let userMessage = command;
      let model: string | undefined;

      const modelIdx = command.indexOf('--model ');
      if (modelIdx !== -1) {
        userMessage = command.substring(0, modelIdx).trim();
        model = command.substring(modelIdx + 8).trim().split(' ')[0];
      }

      // Forward user message to daemon for turn pipeline processing
      this.pp.postMessage({
        type: 'message',
        payload: {
          sessionId: sessionId || 'default',
          content: userMessage,
          userId: userId || 'cli-user',
          projectPath,
          timestamp: Date.now(),
          model: model,
        },
      });
      return;
    }

    const cmdStartTime = Date.now();

    // Get or create session context
    let ctx = this.activeSessions.get(sessionId || "default");
    if (!ctx) {
      ctx = {
        sessionId: sessionId || `cli-${Date.now()}`,
        userId: userId || "cli-user",
        projectPath,
        startTime: Date.now(),
      };
      this.activeSessions.set(ctx.sessionId, ctx);
      this.logger?.info("New CLI session created", { sessionId: ctx.sessionId });
    }

    // Emit command for processing by command dispatcher
    this.pp.postMessage({
      type: "command",
      payload: {
        command,
        args: args || [],
        sessionId: ctx.sessionId,
        userId: ctx.userId,
        projectPath: ctx.projectPath,
        timestamp: cmdStartTime,
      },
    } satisfies WorkerToHostMessage);

    // WHY: Direct intelligence module access is not possible from workers.
    // Intelligence runs in the main process; use message passing instead.
    // Memory storage and thinker analysis should be handled by the daemon.
  }

  private async handleConfigUpdate(msg: CliMessage): Promise<void> {
    this.logger?.info("Config update received");
    
    // Apply config updates
    if (msg.payload?.config) {
      // Update internal state based on new config
    }

    this.pp.postMessage({ 
      type: "message", 
      payload: { info: "Config updated successfully" } 
    });
  }

  private async handleShutdown(): Promise<void> {
    this.logger?.info("Shutdown requested, cleaning up");
    
    // Cleanup sessions
    for (const [sessionId, ctx] of this.activeSessions) {
      this.logger?.debug("Closing session", { sessionId, duration: Date.now() - ctx.startTime });
    }
    this.activeSessions.clear();

    this.pp.postMessage({ type: "shutdown:complete" });
    process.exit(0);
  }

  private sendError(message: string): void {
    this.logger?.error("CLI channel error", { message });
    // Send error in the format expected by plugin-host: { type: "error", message }
    this.pp.postMessage({ type: "error", message, timestamp: Date.now() } as any);
  }

  private sendResult(result: CommandResult): void {
    this.pp.postMessage({ 
      type: "result", 
      payload: { ...result, timestamp: Date.now() } 
    });
  }
}

new CliChannelWorker();
