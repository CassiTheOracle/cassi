// Universal Command Processor - Yang
// Works across ALL channels: Telegram, Chat, TUI, API, Web

export interface CommandContext {
  channel: "telegram" | "chat" | "tui" | "api" | "web";
  userId: string;
  sessionId: string;
  projectPath?: string;
  permissions: string[];
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
  category: "system" | "git" | "dialectic" | "tools" | "help";
  permissions?: string[];
  handler: (args: string[], ctx: CommandContext) => Promise<CommandResult>;
}

export class UniversalCommandProcessor {
  private commands = new Map<string, Command>();
  private aliases = new Map<string, string>();

  register(cmd: Command): void {
    this.commands.set(cmd.name, cmd);
    cmd.aliases?.forEach(alias => this.aliases.set(alias, cmd.name));
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
    return cmd.handler(args, ctx);
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
