import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { createMockModel } from "@oh-my-pi/pi-ai/providers/mock";

const logPath = process.env.CASSIPI_PROBE_LOG;
if (!logPath) throw new Error("CASSIPI_PROBE_LOG is required");
const probeLogPath: string = logPath;
mkdirSync(dirname(probeLogPath), { recursive: true });

function log(event: string, data: Record<string, unknown> = {}): void {
	appendFileSync(probeLogPath, `${JSON.stringify({ event, at: new Date().toISOString(), ...data })}\n`, "utf8");
}

function mode(value: string | undefined): "normal" | "cancel" | "error" | "timeout" {
	if (value === "cancel" || value === "error" || value === "timeout") return value;
	return "normal";
}

export default function hostLifecycleProbe(pi: ExtensionAPI): void {
	let compactMode = mode(process.env.CASSIPI_PROBE_COMPACT_MODE);
	let treeMode = mode(process.env.CASSIPI_PROBE_TREE_MODE);
	const mock = createMockModel({
		id: "host-lifecycle-probe",
		provider: "cassipi-probe",
		contextWindow: 32_000,
		maxTokens: 512,
		handler: context => ({
			content: [`Probe response ${context.messages.length}: lifecycle turn complete.`],
			usage: { input: 64, output: 8 },
		}),
	});

	pi.registerProvider("cassipi-probe", {
		baseUrl: "mock://",
		apiKey: "CASSIPI_PROBE_API_KEY",
		api: "mock",
		models: [
			{
				id: "host-lifecycle-probe",
				name: "CassiPi host lifecycle probe",
				api: "mock",
				reasoning: false,
				input: ["text"],
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
				contextWindow: 32_000,
				maxTokens: 512,
			},
		],
		streamSimple: (_model, context, options) => mock.stream(mock, context, options),
	});

	pi.registerCommand("probe-compact-mode", {
		description: "Set disposable host-probe compaction behavior",
		handler: async args => {
			compactMode = mode(args.trim());
			log("probe_mode", { target: "compact", mode: compactMode });
		},
	});
	pi.registerCommand("probe-tree-mode", {
		description: "Set disposable host-probe tree behavior",
		handler: async args => {
			treeMode = mode(args.trim());
			log("probe_mode", { target: "tree", mode: treeMode });
		},
	});
	pi.registerCommand("probe-tree", {
		description: "Navigate the disposable probe session tree",
		handler: async (args, ctx) => {
			const [targetId, summarizeValue = "true"] = args.trim().split(/\s+/, 2);
			if (!targetId) throw new Error("probe-tree requires an entry ID");
			const result = await ctx.navigateTree(targetId, { summarize: summarizeValue !== "false" });
			log("probe_tree_command", { targetId, summarize: summarizeValue !== "false", ...result });
		},
	});

	pi.on("session_start", (_event, ctx) => {
		log("session_start", {
			sessionId: ctx.sessionManager.getSessionId(),
			sessionFile: ctx.sessionManager.getSessionFile(),
		});
	});
	pi.on("context", event => {
		log("context", {
			messageCount: event.messages.length,
			roles: event.messages.map(message => message.role),
		});
	});
	pi.on("session_before_compact", async event => {
		log("session_before_compact", {
			mode: compactMode,
			customInstructions: event.customInstructions ?? null,
			firstKeptEntryId: event.preparation.firstKeptEntryId,
			tokensBefore: event.preparation.tokensBefore,
			messagesToSummarize: event.preparation.messagesToSummarize.length,
			recentMessages: event.preparation.recentMessages.length,
			branchEntries: event.branchEntries.length,
		});
		if (compactMode === "cancel") return { cancel: true };
		if (compactMode === "error") throw new Error("intentional stock-host compaction probe failure");
		if (compactMode === "timeout") await new Promise<void>(() => {});
		return {
			compaction: {
				summary: `probe-compaction:${event.customInstructions ?? "automatic"}`,
				shortSummary: "probe compaction",
				firstKeptEntryId: event.preparation.firstKeptEntryId,
				tokensBefore: event.preparation.tokensBefore,
				details: { probe: true, requested: event.customInstructions !== undefined },
			},
		};
	});
	pi.on("session_compact", event => {
		log("session_compact", {
			fromExtension: event.fromExtension,
			summary: event.compactionEntry.summary,
			firstKeptEntryId: event.compactionEntry.firstKeptEntryId,
			details: event.compactionEntry.details ?? null,
		});
	});
	pi.on("session_before_tree", async event => {
		log("session_before_tree", {
			mode: treeMode,
			targetId: event.preparation.targetId,
			oldLeafId: event.preparation.oldLeafId,
			commonAncestorId: event.preparation.commonAncestorId,
			entriesToSummarize: event.preparation.entriesToSummarize.length,
			userWantsSummary: event.preparation.userWantsSummary,
		});
		if (treeMode === "cancel") return { cancel: true };
		if (treeMode === "error") throw new Error("intentional stock-host tree probe failure");
		if (treeMode === "timeout") await new Promise<void>(() => {});
		return {
			summary: {
				summary: `probe-tree-summary:${event.preparation.targetId}`,
				details: { probe: true, requested: event.preparation.userWantsSummary },
			},
		};
	});
	pi.on("session_tree", event => {
		log("session_tree", {
			newLeafId: event.newLeafId,
			oldLeafId: event.oldLeafId,
			fromExtension: event.fromExtension ?? null,
			summary: event.summaryEntry?.summary ?? null,
		});
	});
	pi.on("session_shutdown", () => log("session_shutdown"));
	log("extension_loaded");
}
