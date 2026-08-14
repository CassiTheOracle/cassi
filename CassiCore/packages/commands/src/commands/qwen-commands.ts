// Qwen Provider Commands for Universal Processor
// User-facing /qwen command for managing Qwen accounts and renewal.

import type { CommandResult } from "./universal-processor.js";
import { processor } from "./universal-processor.js";

const ADMIN_BASE = "http://localhost:7433";

processor.register({
  name: "/qwen",
  category: "system",
  description: "Manage Qwen provider accounts — status, renew, accounts",
  handler: async (args): Promise<CommandResult> => {
    const subcmd = (args[0] || "help").toLowerCase();
    const rest = args.slice(1);

    switch (subcmd) {
      case "status":
      case "stats":
        return handleQwenStatus();

      case "accounts":
      case "list":
        return handleQwenAccounts();

      case "renew":
      case "refresh":
        return handleQwenRenew(rest);

      case "help":
      default:
        return {
          text: [
            "Qwen Provider Commands:",
            "",
            "  /qwen status      Show Qwen load balancer stats",
            "  /qwen accounts    List configured Qwen accounts",
            "  /qwen renew       Bulk renew all Qwen OAuth tokens",
            "",
            "Accounts are stored in ~/.cassicore/qwen-accounts.json",
          ].join("\n"),
        };
    }
  },
});

async function handleQwenStatus(): Promise<CommandResult> {
  try {
    const resp = await fetch(`${ADMIN_BASE}/providers/qwen/stats`);
    if (!resp.ok) {
      return { text: `Failed to get Qwen stats: ${resp.status} ${resp.statusText}` };
    }
    const data = await resp.json() as Record<string, unknown>;

    if (!data.loadBalancing) {
      return { text: "Qwen: single-account mode (no load balancer)" };
    }

    const accounts = data.accounts as Array<Record<string, unknown>>;
    const lines = [
      "Qwen Load Balancer Status",
      `Active accounts: ${data.activeCount ?? "unknown"}`,
      "",
    ];

    if (Array.isArray(accounts)) {
      for (const acc of accounts) {
        const cool = acc.onCooldown ? " [COOLDOWN]" : "";
        lines.push(`  ${acc.profileId}: ${acc.requests ?? 0} req, ${acc.errors ?? 0} err${cool}`);
      }
    }

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to reach daemon: ${String(err)}` };
  }
}

async function handleQwenAccounts(): Promise<CommandResult> {
  try {
    const resp = await fetch(`${ADMIN_BASE}/providers/qwen/accounts`);
    if (!resp.ok) {
      return { text: `Failed to get accounts: ${resp.status} ${resp.statusText}` };
    }
    const data = await resp.json() as Record<string, unknown>;
    const accounts = data.accounts as Array<Record<string, unknown>>;

    const lines = [
      `Qwen Accounts (${data.count ?? 0})`,
      `File: ${data.file ?? "unknown"}`,
      "",
    ];

    if (Array.isArray(accounts) && accounts.length > 0) {
      for (const acc of accounts) {
        const cred = acc.hasCredentials ? "OAuth" : acc.hasApiKey ? "API key" : "none";
        lines.push(`  ${acc.profileId}: auth=${cred}${acc.baseUrl ? ` url=${acc.baseUrl}` : ""}`);
      }
    } else {
      lines.push("  No accounts configured");
    }

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to reach daemon: ${String(err)}` };
  }
}

async function handleQwenRenew(args: string[]): Promise<CommandResult> {
  try {
    const resp = await fetch(`${ADMIN_BASE}/providers/qwen/renew`, { method: "POST" });
    if (!resp.ok) {
      return { text: `Renewal failed: ${resp.status} ${resp.statusText}` };
    }
    const data = await resp.json() as Record<string, unknown>;

    const details = data.details as Array<Record<string, string>> | undefined;
    const lines = [
      "Qwen Account Renewal Results",
      `  Renewed: ${data.renewed ?? 0}`,
      `  Reauthenticated: ${data.reauthenticated ?? 0}`,
      `  Failed: ${data.failed ?? 0}`,
    ];

    if (Array.isArray(details) && details.length > 0) {
      lines.push("");
      for (const d of details) {
        const err = d.error ? ` (${d.error})` : "";
        lines.push(`  ${d.profileId}: ${d.status}${err}`);
      }
    }

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to reach daemon: ${String(err)}` };
  }
}
