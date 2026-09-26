import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

const logPath = process.env.CASSIPI_COMPARISON_NAV_LOG;
if (!logPath) throw new Error("CASSIPI_COMPARISON_NAV_LOG is required");
mkdirSync(dirname(logPath), { recursive: true });

function log(value: Record<string, unknown>): void {
  appendFileSync(logPath!, `${JSON.stringify({ at: new Date().toISOString(), ...value })}\n`, "utf8");
}

export default function comparisonNavigation(pi: ExtensionAPI): void {
  pi.registerCommand("comparison-tree-summary", {
    description: "Navigate the disposable provider-comparison tree with a summary",
    handler: async (args, context) => {
      const target = args.trim();
      if (!target) throw new Error("comparison-tree-summary requires an entry identity");
      log({ event: "tree-summary-start", target });
      try {
        const result = await context.navigateTree(target, { summarize: true });
        log({ event: "tree-summary", target, ...result });
      } catch (error) {
        log({ event: "tree-summary-error", target, error: error instanceof Error ? error.message : String(error) });
        throw error;
      }
    },
  });
  pi.registerCommand("comparison-tree-plain", {
    description: "Navigate the disposable provider-comparison tree without a summary",
    handler: async (args, context) => {
      const target = args.trim();
      if (!target) throw new Error("comparison-tree-plain requires an entry identity");
      log({ event: "tree-plain-start", target });
      try {
        const result = await context.navigateTree(target, { summarize: false });
        log({ event: "tree-plain", target, ...result });
      } catch (error) {
        log({ event: "tree-plain-error", target, error: error instanceof Error ? error.message : String(error) });
        throw error;
      }
    },
  });
}
