// Universal Command Processor - Yang
// Works across ALL channels: Telegram, Chat, TUI, API, Web, CLI
// Now with full CassiCore intelligence integration

// Intelligence imports - using 'any' for flexible typing due to complex module dependencies
// In production, these would be properly wired through dependency injection
type IMemory = any;
type IThinker = any;
type IDialecticSystem = any;
type IContextManager = any;

export interface IntelligenceContext {
  memory?: IMemory;
  thinker?: IThinker;
  dialectic?: IDialecticSystem;
  contextManager?: IContextManager;
}

export interface CommandContext {
  channel: "telegram" | "chat" | "tui" | "api" | "web" | "cli";
  userId: string;
  sessionId: string;
  projectPath?: string;
  permissions: string[];
  /** CassiCore intelligence layer - available for smart commands */
  intelligence?: IntelligenceContext;
  /** Full session configuration */
  sessionConfig?: Record<string, unknown>;
}

export interface CommandResult {
  text: string;
  attachments?: { type: "image" | "file"; path: string }[];
  actions?: { label: string; command: string }[];
}

export interface Command {
  name: string;
  aliases?: string[];
  description: string;
  category: "system" | "git" | "dialectic" | "tools" | "help" | "intelligence";
  permissions?: string[];
  /** Intelligence features for this command */
  intelligence?: {
    /** Get AI suggestions before execution */
    suggest?: boolean;
    /** Analyze output with AI after execution */
    analyze?: boolean;
    /** Store command in memory for recall */
    memory?: boolean;
    /** Track command effectiveness for learning */
    learn?: boolean;
  };
  handler: (args: string[], ctx: CommandContext) => Promise<CommandResult>;
}

/** Command middleware function type */
export type CommandMiddleware = (
  args: string[],
  ctx: CommandContext,
  cmd: Command,
  next: () => Promise<CommandResult>
) => Promise<CommandResult>;

export class UniversalCommandProcessor {
  private commands = new Map<string, Command>();
  private aliases = new Map<string, string>();
  private middleware: CommandMiddleware[] = [];

  register(cmd: Command): void {
    this.commands.set(cmd.name, cmd);
    cmd.aliases?.forEach(alias => this.aliases.set(alias, cmd.name));
  }

  /** Register middleware to intercept command execution */
  use(middleware: CommandMiddleware): void {
    this.middleware.push(middleware);
  }

  async process(input: string, ctx: CommandContext): Promise<CommandResult | null> {
    const parts = input.trim().split(/\s+/);
    const name = parts[0].toLowerCase();
    const args = parts.slice(1);
    const resolvedName = this.aliases.get(name) || name;
    const cmd = this.commands.get(resolvedName);
    if (!cmd) return null;
    if (cmd.permissions && !this.hasPermission(ctx, cmd.permissions)) {
      return { text: "❌ Permission denied" };
    }

    // Execute with middleware chain
    return this.executeWithMiddleware(args, ctx, cmd);
  }

  private async executeWithMiddleware(
    args: string[],
    ctx: CommandContext,
    cmd: Command
  ): Promise<CommandResult> {
    let index = 0;
    const execute = async (): Promise<CommandResult> => {
      // Pre-command intelligence hooks
      if (cmd.intelligence?.suggest && ctx.intelligence?.thinker) {
        // Suggestions could be shown to user before execution
      }

      // Execute the command
      const result = await cmd.handler(args, ctx);

      // Post-command intelligence hooks
      if (cmd.intelligence?.memory && ctx.intelligence?.memory) {
        try {
          await ctx.intelligence.memory.store({
            type: 'conversation' as any,
            content: `${cmd.name} ${args.join(' ')}`,
            metadata: { 
              commandResult: result.text.slice(0, 500),
              projectPath: ctx.projectPath,
              timestamp: Date.now(),
            },
          });
        } catch {
          // Best-effort memory storage
        }
      }

      return result;
    };

    const next = async (): Promise<CommandResult> => {
      if (index >= this.middleware.length) {
        return execute();
      }
      const mw = this.middleware[index++];
      return mw(args, ctx, cmd, next);
    };

    return next();
  }

  private hasPermission(ctx: CommandContext, required: string[]): boolean {
    return required.every(p => ctx.permissions.includes(p));
  }

  getCommandsByCategory(category?: string): Command[] {
    const cmds = Array.from(this.commands.values());
    return category ? cmds.filter(c => c.category === category) : cmds;
  }

  getHelp(category?: string): string {
    const cmds = this.getCommandsByCategory(category);
    const byCat = cmds.reduce((acc, cmd) => {
      acc[cmd.category] = acc[cmd.category] || [];
      acc[cmd.category].push(cmd);
      return acc;
    }, {} as Record<string, Command[]>);
    return Object.entries(byCat)
      .map(([cat, list]) => "\n📁 " + cat.toUpperCase() + "\n" + list.map(c => "  " + c.name.padEnd(15) + " " + c.description).join("\n")).join("\n");
  }
}

export const processor = new UniversalCommandProcessor();

// ═══════════════════════════════════════════════════════════════════════════
// INTELLIGENCE COMMANDS - Direct access to CassiCore cognitive layer
// ═══════════════════════════════════════════════════════════════════════════

processor.register({
  name: "/think",
  category: "intelligence",
  description: "Trigger a thinker cycle (ponder or deep think)",
  permissions: ["intelligence"],
  intelligence: { memory: true },
  handler: async (args, ctx) => {
    if (!ctx.intelligence?.thinker) {
      return { text: "❌ Thinker module not available" };
    }
    
    const depth = args[0] === "deep" ? "think" : "ponder";
    
    // Trigger thinking
    const result = await ctx.intelligence.thinker.think(depth as any);
    
    return { 
      text: `🧠 ${depth === "think" ? "Deep Think" : "Ponder"} result:\n\n${result}`,
      actions: [
        { label: "Deep think", command: "/think deep" },
        { label: "Stats", command: "/think-stats" },
      ],
    };
  },
});

processor.register({
  name: "/think-stats",
  category: "intelligence",
  description: "Show thinker statistics",
  permissions: ["intelligence"],
  handler: async (args, ctx) => {
    if (!ctx.intelligence?.thinker?.stats) {
      return { text: "❌ Thinker stats not available" };
    }
    
    const stats = await ctx.intelligence.thinker.stats();
    
    return {
      text: [
        "🧠 Thinker Statistics",
        "━━━━━━━━━━━━━━━━━━━",
        `Total Insights: ${stats.totalInsights || 0}`,
        `Total Turns: ${stats.totalTurns || 0}`,
        `Ponder Interval: ${stats.ponderInterval || 3}`,
        `Think Interval: ${stats.thinkInterval || 10}`,
        stats.lastPonderAt ? `Last Ponder: ${new Date(stats.lastPonderAt).toLocaleTimeString()}` : "",
        stats.lastThinkAt ? `Last Think: ${new Date(stats.lastThinkAt).toLocaleTimeString()}` : "",
      ].filter(Boolean).join("\n"),
    };
  },
});

processor.register({
  name: "/remember",
  aliases: ["/mem"],
  category: "intelligence",
  description: "Store a note in CassiCore's memory",
  permissions: ["intelligence"],
  intelligence: { memory: true },
  handler: async (args, ctx) => {
    if (!ctx.intelligence?.memory) {
      return { text: "❌ Memory module not available" };
    }
    
    const content = args.join(" ");
    if (!content) {
      return { text: "Usage: /remember \u003ccontent to remember\u003e" };
    }
    
    await ctx.intelligence.memory.store({
      type: "fact" as any,
      content,
      metadata: {
        sessionId: ctx.sessionId,
        projectPath: ctx.projectPath,
        timestamp: Date.now(),
      },
    });
    
    return { 
      text: "✅ Remembered",
      actions: [{ label: "Recall", command: "/recall " + content.split(" ")[0] }],
    };
  },
});

processor.register({
  name: "/recall",
  aliases: ["/search"],
  category: "intelligence",
  description: "Search CassiCore's memory",
  permissions: ["intelligence"],
  handler: async (args, ctx) => {
    if (!ctx.intelligence?.memory?.search) {
      return { text: "❌ Memory search not available" };
    }
    
    const query = args.join(" ");
    if (!query) {
      return { text: "Usage: /recall \u003csearch query\u003e" };
    }
    
    const results = await ctx.intelligence.memory.search(query, { limit: 5 });
    
    if (!results || results.length === 0) {
      return { text: "📝 No memories found matching that query." };
    }
    
    const formatted = results.map((r: any, i: number) => {
      const content = r.entry?.content?.slice(0, 100) || "(no content)";
      const type = r.entry?.type || "unknown";
      return `${i + 1}. [${type}] ${content}${r.entry?.content?.length > 100 ? "..." : ""}`;
    }).join("\n");
    
    return { text: `📝 Memories:\n${formatted}` };
  },
});

processor.register({
  name: "/context",
  category: "intelligence",
  description: "Show current session context",
  permissions: ["intelligence"],
  handler: async (args, ctx) => {
    const lines = [
      "🎯 Session Context",
      "━━━━━━━━━━━━━━━━━━━",
      `Session ID: ${ctx.sessionId.slice(-12)}`,
      `User: ${ctx.userId}`,
      `Channel: ${ctx.channel}`,
    ];
    
    if (ctx.projectPath) {
      lines.push(`Project: ${ctx.projectPath}`);
    }
    
    lines.push(`Permissions: ${ctx.permissions.join(", ")}`);
    
    if (ctx.intelligence) {
      const modules = Object.keys(ctx.intelligence).filter(k => 
        ctx.intelligence?.[k as keyof typeof ctx.intelligence]
      );
      lines.push(`\nActive Intelligence: ${modules.join(", ") || "none"}`);
    }
    
    return { text: lines.join("\n") };
  },
});

// Register help command
processor.register({
  name: "/help",
  aliases: ["/h"],
  category: "help",
  description: "Show all available commands",
  handler: async (args, ctx) => ({
    text: processor.getHelp(args[0]) + "\n\n💡 Use /help \u003ccategory\u003e for specific categories: system, git, tools, intelligence, help",
  }),
});
