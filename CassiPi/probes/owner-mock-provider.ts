import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { createMockModel } from "@oh-my-pi/pi-ai/providers/mock";

const logPath = process.env.CASSIPI_OWNER_PROBE_LOG;
if (!logPath) throw new Error("CASSIPI_OWNER_PROBE_LOG is required");
mkdirSync(dirname(logPath), { recursive: true });

function log(value: Record<string, unknown>): void {
  appendFileSync(logPath!, `${JSON.stringify({ at: new Date().toISOString(), ...value })}\n`, "utf8");
}

export default function ownerMockProvider(pi: ExtensionAPI): void {
  const mock = createMockModel({
    id: "cassipi-owner-probe",
    provider: "cassipi-owner-probe",
    contextWindow: 128_000,
    maxTokens: 256,
    handler: context => {
      log({ event: "provider_request", messages: context.messages });
      return {
        content: [`Owner probe response ${context.messages.length}.`],
        usage: { input: 64, output: 8 },
      };
    },
  });
  pi.registerProvider("cassipi-owner-probe", {
    baseUrl: "mock://",
    apiKey: "CASSIPI_OWNER_PROBE_API_KEY",
    api: "mock",
    models: [
      {
        id: "cassipi-owner-probe",
        name: "CassiPi owner local probe",
        api: "mock",
        reasoning: false,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128_000,
        maxTokens: 256,
      },
    ],
    streamSimple: (_model, context, options) => mock.stream(mock, context, options),
  });
  pi.registerCommand("owner-probe-tree", {
    description: "Navigate the disposable CassiPi owner probe tree",
    handler: async (args, context) => {
      const target = args.trim();
      if (!target) throw new Error("owner-probe-tree requires an entry identity");
      const result = await context.navigateTree(target, { summarize: true });
      log({ event: "tree_result", target, ...result });
    },
  });
  pi.registerCommand("owner-probe-tree-no-summary", {
    description: "Navigate the disposable CassiPi owner probe tree without a summary",
    handler: async (args, context) => {
      const target = args.trim();
      if (!target) throw new Error("owner-probe-tree-no-summary requires an entry identity");
      const result = await context.navigateTree(target, { summarize: false });
      log({ event: "tree_no_summary_result", target, ...result });
    },
  });
  log({ event: "provider_loaded" });
}
