// Tool Commands for Universal Processor

import type { CommandContext, CommandResult } from "./universal-processor.js";
import { processor } from "./universal-processor.js";

processor.register({
  name: "/help",
  category: "help",
  description: "Show all available commands",
  handler: async (args, ctx) => ({ text: processor.getHelp(args[0]) })
});

processor.register({
  name: "/dialectic",
  aliases: ["/d"],
  category: "dialectic",
  description: "Toggle or configure dialectic view",
  handler: async (args, ctx) => {
    const subcmd = args[0] || "toggle";
    switch (ctx.channel) {
      case "tui": return { text: "Toggling TUI dialectic panel..." };
      case "telegram": return { text: "Dialectic: " + subcmd };
      default: return { text: "Dialectic not available in this channel" };
    }
  }
});

processor.register({
  name: "/read",
  category: "tools",
  description: "Read file contents",
  permissions: ["read"],
  handler: async (args, ctx) => {
    const path = args[0];
    if (!path) return { text: "Usage: /read <path>" };
    try {
      const response = await fetch("http://localhost:7432/tools/read?path=" + encodeURIComponent(path));
      const result = await response.json();
      if (result.error) return { text: "❌ " + result.error };
      return { text: "📄 Contents of " + path + ":\n\n" + result.content };
    } catch {
      return { text: "❌ Failed to read file" };
    }
  }
});

processor.register({
  name: "/write",
  category: "tools",
  description: "Write to file",
  permissions: ["write"],
  handler: async (args, ctx) => {
    const path = args[0];
    const content = args.slice(1).join(" ");
    if (!path) return { text: "Usage: /write <path> <content>" };
    try {
      const response = await fetch("http://localhost:7432/tools/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, content })
      });
      const result = await response.json();
      if (result.error) return { text: "❌ " + result.error };
      return { text: "✅ Written to " + path + " (" + result.bytesWritten + " bytes)" };
    } catch {
      return { text: "❌ Failed to write file" };
    }
  }
});

processor.register({
  name: "/bash",
  category: "tools",
  description: "Execute shell command",
  permissions: ["admin"],
  handler: async (args, ctx) => {
    const cmd = args.join(" ");
    if (!cmd) return { text: "Usage: /bash <command>" };
    try {
      const response = await fetch("http://localhost:7432/tools/bash", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd, timeout: 30000 })
      });
      const result = await response.json();
      return { text: "$ " + cmd + "\n\n" + result.output };
    } catch {
      return { text: "❌ Command failed" };
    }
  }
});

processor.register({
  name: "/exists",
  category: "tools",
  description: "Check if file exists",
  handler: async (args, ctx) => {
    const path = args[0];
    if (!path) return { text: "Usage: /exists <path>" };
    try {
      const response = await fetch("http://localhost:7432/fs/exists?path=" + encodeURIComponent(path));
      const result = await response.json();
      return { text: result.exists ? "✅ Exists: " + path : "❌ Not found: " + path };
    } catch {
      return { text: "❌ Failed to check" };
    }
  }
});

processor.register({
  name: "/mkdir",
  category: "tools",
  description: "Create directory",
  permissions: ["write"],
  handler: async (args, ctx) => {
    const path = args[0];
    if (!path) return { text: "Usage: /mkdir <path>" };
    try {
      const response = await fetch("http://localhost:7432/tools/mkdir", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path })
      });
      const result = await response.json();
      return { text: result.error ? "❌ " + result.error : "✅ Created: " + path };
    } catch {
      return { text: "❌ Failed to create directory" };
    }
  }
});

processor.register({
  name: "/model",
  category: "system",
  description: "Show or change current model",
  handler: async (args, ctx) => {
    return { text: "Current model: kimi-coding/k2p5\nUsage: /model <provider>/<model>" };
  }
});

processor.register({
  name: "/session",
  category: "system",
  description: "Show session info",
  handler: async (args, ctx) => {
    return { text: "Session: " + ctx.sessionId + "\nUser: " + ctx.userId + "\nChannel: " + ctx.channel };
  }
});

processor.register({
  name: "/export",
  category: "system",
  description: "Export conversation to markdown",
  handler: async (args, ctx) => {
    const path = args[0] || "export-" + Date.now() + ".md";
    return { text: "✅ Exported to " + path, attachments: [{ type: "file", path }] };
  }
});

processor.register({
  name: "/search",
  category: "tools",
  description: "Search for files",
  handler: async (args, ctx) => {
    const pattern = args.join(" ") || "*";
    return { text: "🔍 Searching for: " + pattern + "\n\n(Results would appear here)" };
  }
});
