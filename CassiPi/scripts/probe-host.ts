import { createHash } from "node:crypto";
import { createReadStream, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { RpcClient } from "@oh-my-pi/pi-coding-agent/modes/rpc/rpc-client";

interface ProbeRecord {
	event: string;
	at: string;
	[key: string]: unknown;
}

const root = resolve(import.meta.dir, "..");
const binary = process.env.CASSIPI_OMP_BINARY ??
	"C:/Users/Carina/.bun/bin/omp.exe";
const extension = join(root, "probes", "host-lifecycle-extension.ts");
const config = join(root, "probes", "host-probe-config.yml");
const runRoot = join(root, ".probe", "stock-18.1.10");
const agentDir = join(runRoot, "agent");
const sessionDir = join(runRoot, "sessions");
const logPath = join(runRoot, "events.jsonl");
const receiptPath = join(root, "probes", "receipts", "stock-18.1.10.json");

function assert(condition: unknown, message: string): asserts condition {
	if (!condition) throw new Error(message);
}

function records(): ProbeRecord[] {
	if (!existsSync(logPath)) return [];
	return readFileSync(logPath, "utf8")
		.split(/\r?\n/)
		.filter(Boolean)
		.map(line => JSON.parse(line) as ProbeRecord);
}

function progress(step: string, data: Record<string, unknown> = {}): void {
	console.log(JSON.stringify({ step, ...data }));
}
async function waitForRecord(
	predicate: (record: ProbeRecord, all: ProbeRecord[]) => boolean,
	description: string,
	timeoutMs = 10_000,
): Promise<ProbeRecord> {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		const all = records();
		const found = all.findLast(record => predicate(record, all));
		if (found) return found;
		await Bun.sleep(25);
	}
	throw new Error(`Timed out waiting for ${description}`);
}

async function sha256(path: string): Promise<string> {
	const hash = createHash("sha256");
	await new Promise<void>((resolvePromise, reject) => {
		const input = createReadStream(path);
		input.on("data", chunk => hash.update(chunk));
		input.on("error", reject);
		input.on("end", resolvePromise);
	});
	return hash.digest("hex");
}

async function runLocalCommand(client: RpcClient, command: string): Promise<void> {
	await client.prompt(command);
}

async function main(): Promise<void> {
	assert(existsSync(binary), `Installed OMP binary not found: ${binary}`);
	rmSync(runRoot, { recursive: true, force: true });
	mkdirSync(agentDir, { recursive: true });
	mkdirSync(sessionDir, { recursive: true });
	mkdirSync(dirname(receiptPath), { recursive: true });

	const client = new RpcClient({
		command: [binary],
		cwd: root,
		env: {
			PI_CODING_AGENT_DIR: agentDir,
			CASSIPI_PROBE_API_KEY: "local-probe-only",
			CASSIPI_PROBE_LOG: logPath,
			CASSIPI_PROBE_RESPONSE_REPEATS: "32",
		},
		sessionDir,
		args: ["--no-extensions", "-e", extension, "--config", config],
	});

	const observations: Record<string, unknown> = {};
	try {
		await client.start();
		await waitForRecord(record => record.event === "extension_loaded", "extension load");
		const availableModels = await client.getAvailableModels();
		progress("extension-loaded", { availableModelCount: availableModels.length });
		assert(
			availableModels.some(model => model.provider === "cassipi-probe" && model.id === "host-lifecycle-probe"),
			"Loaded extension did not register its mock provider",
		);
		await client.setModel("cassipi-probe", "host-lifecycle-probe");
		const state = await client.getState();
		assert(state.model?.contextWindow === 32_000, `Unexpected probe context window: ${state.model?.contextWindow}`);
		progress("mock-model-selected", {
			provider: state.model?.provider,
			model: state.model?.id,
			contextWindow: state.model?.contextWindow,
		});
		observations.session = { sessionId: state.sessionId, sessionFile: state.sessionFile };

		await client.setAutoCompaction(true);
		await client.promptAndWait(`automatic-threshold-seed ${"field context ".repeat(3000)}`, undefined, 30_000);
		progress("automatic-threshold-turn");
		await client.promptAndWait(`automatic-threshold-trigger ${"field context ".repeat(3000)}`, undefined, 60_000);
		await waitForRecord(
			record => record.event === "session_before_compact" && record.customInstructions === null,
			"automatic threshold compaction hook",
			30_000,
		);
		const automaticBefore = records().find(
			record => record.event === "session_before_compact" && record.customInstructions === null,
		);
		assert(automaticBefore, "Installed binary did not exercise automatic session_before_compact");
		const automaticAfter = records().find(
			record => record.event === "session_compact" && record.summary === "probe-compaction:automatic",
		);
		assert(automaticAfter?.fromExtension === true, "Automatic custom compaction result was not committed as extension-owned");
		observations.automaticCompaction = { before: automaticBefore, after: automaticAfter };
		progress("automatic-compaction-observed", { tokensBefore: automaticBefore.tokensBefore });
		await client.setAutoCompaction(false);

		for (let index = 0; index < 4; index++) {
			await client.promptAndWait(`manual-compaction-${index} ${"evidence ".repeat(1400)}`, undefined, 60_000);
		}
		const manual = await client.compact("manual-shape");
		assert(manual.summary === "probe-compaction:manual-shape", "Manual custom compaction result was not returned");
		const manualBefore = records().find(
			record => record.event === "session_before_compact" && record.customInstructions === "manual-shape",
		);
		assert(manualBefore, "Manual session_before_compact shape was not observed");
		observations.manualCompaction = { before: manualBefore, result: manual };

		await client.promptAndWait("tree-main-one", undefined, 60_000);
		await client.promptAndWait("tree-main-two", undefined, 60_000);
		const branchMessages = await client.getBranchMessages();
		assert(branchMessages.length >= 2, "Probe session lacks tree targets");
		const treePostsBefore = records().filter(record => record.event === "session_tree").length;
		await runLocalCommand(client, `/probe-tree ${branchMessages[0]!.entryId} false`);
		const unrequestedTree = await waitForRecord(
			(record, all) => record.event === "session_tree" && all.filter(item => item.event === "session_tree").length > treePostsBefore,
			"unrequested tree navigation",
		);
		const unrequestedBefore = records().findLast(
			record => record.event === "session_before_tree" && record.userWantsSummary === false,
		);
		assert(unrequestedBefore, "Tree navigation without summary was not observed");
		assert(unrequestedTree.summary === null, "Host used a custom tree summary when none was requested");
		const abandonedMainLeaf = unrequestedTree.oldLeafId;
		assert(typeof abandonedMainLeaf === "string", "Unrequested navigation did not expose the abandoned leaf");
		observations.treeWithoutSummary = { before: unrequestedBefore, after: unrequestedTree };

		await client.promptAndWait("tree-sibling-work", undefined, 60_000);
		const requestedPostsBefore = records().filter(record => record.event === "session_tree").length;
		await runLocalCommand(client, `/probe-tree ${abandonedMainLeaf} true`);
		const requestedTree = await waitForRecord(
			(record, all) =>
				record.event === "session_tree" && all.filter(item => item.event === "session_tree").length > requestedPostsBefore,
			"requested tree summary",
		);
		const requestedBefore = records().findLast(
			record => record.event === "session_before_tree" && record.userWantsSummary === true,
		);
		assert(requestedBefore, "Tree navigation with summary was not observed");
		assert(requestedTree.fromExtension === true, "Requested custom tree summary was not extension-owned");
		observations.treeWithSummary = { before: requestedBefore, after: requestedTree };

		const cancelledTarget = requestedTree.oldLeafId;
		assert(typeof cancelledTarget === "string", "Requested navigation did not preserve a cancellation target");
		await runLocalCommand(client, "/probe-tree-mode cancel");
		await waitForRecord(record => record.event === "probe_mode" && record.target === "tree" && record.mode === "cancel", "tree cancel mode");
		const cancelledPostsBefore = records().filter(record => record.event === "session_tree").length;
		await runLocalCommand(client, `/probe-tree ${cancelledTarget} true`);
		const cancelledCommand = await waitForRecord(
			record => record.event === "probe_tree_command" && record.targetId === cancelledTarget && record.cancelled === true,
			"cancelled tree command",
		);
		assert(
			records().filter(record => record.event === "session_tree").length === cancelledPostsBefore,
			"Cancelled tree navigation still emitted session_tree",
		);
		observations.treeCancellation = cancelledCommand;

		await runLocalCommand(client, "/probe-tree-mode error");
		await waitForRecord(record => record.event === "probe_mode" && record.target === "tree" && record.mode === "error", "tree error mode");
		const errorTreePostsBefore = records().filter(record => record.event === "session_tree").length;
		await runLocalCommand(client, `/probe-tree ${cancelledTarget} true`);
		const errorTree = await waitForRecord(
			(record, all) =>
				record.event === "session_tree" && all.filter(item => item.event === "session_tree").length > errorTreePostsBefore,
			"tree error fallback",
			60_000,
		);
		assert(errorTree.fromExtension !== true, "Errored tree hook unexpectedly remained extension-owned");
		observations.treeErrorFailOpen = errorTree;

		await runLocalCommand(client, "/probe-compact-mode cancel");
		await waitForRecord(record => record.event === "probe_mode" && record.target === "compact" && record.mode === "cancel", "compact cancel mode");
		for (let index = 0; index < 4; index++) {
			await client.promptAndWait(`compact-cancel-${index} ${"data ".repeat(800)}`, undefined, 60_000);
		}
		const compactHooksBeforeCancel = records().filter(record => record.event === "session_before_compact").length;
		const compactPostsBeforeCancel = records().filter(record => record.event === "session_compact").length;
		let cancelResult: unknown;
		try {
			cancelResult = await client.compact("cancelled-compaction");
		} catch (error) {
			cancelResult = { error: error instanceof Error ? error.message : String(error) };
		}
		const cancelHook = records().findLast(record => record.event === "session_before_compact");
		assert(
			records().filter(record => record.event === "session_before_compact").length > compactHooksBeforeCancel &&
				cancelHook?.mode === "cancel",
			"Cancellation request never reached session_before_compact",
		);
		assert(
			records().filter(record => record.event === "session_compact").length === compactPostsBeforeCancel,
			"Explicitly cancelled compaction committed a result",
		);
		observations.compactionCancellation = { requestResult: cancelResult ?? null, before: cancelHook };

		await runLocalCommand(client, "/probe-compact-mode error");
		await client.promptAndWait("compact-error-source " + "data ".repeat(400), undefined, 60_000);
		const errorCompaction = await client.compact("error-fallback");
		const errorCompactionPost = records().findLast(record => record.event === "session_compact");
		assert(errorCompactionPost?.fromExtension === false, "Errored stock hook did not fall through to native compaction");
		observations.compactionErrorFailOpen = { result: errorCompaction, after: errorCompactionPost };

		await runLocalCommand(client, "/probe-compact-mode timeout");
		for (let index = 0; index < 4; index++) {
			await client.promptAndWait(`compact-timeout-${index} ${"data ".repeat(800)}`, undefined, 60_000);
		}
		const timeoutPostsBefore = records().filter(record => record.event === "session_compact").length;
		const timeoutStarted = Date.now();
		let timeoutCompaction: unknown;
		try {
			timeoutCompaction = await client.compact("timeout-fallback");
		} catch (error) {
			timeoutCompaction = { rpcError: error instanceof Error ? error.message : String(error) };
		}
		const timeoutCompactionPost = await waitForRecord(
			(record, all) =>
				record.event === "session_compact" &&
				all.filter(item => item.event === "session_compact").length > timeoutPostsBefore,
			"timed-out hook native fallback commit",
			10_000,
		);
		const timeoutElapsedMs = Date.now() - timeoutStarted;
		assert(timeoutElapsedMs >= 29_000, `Stock handler timeout fired too early (${timeoutElapsedMs}ms)`);
		assert(timeoutCompactionPost.fromExtension === false, "Timed-out stock hook did not fall through to native compaction");
		observations.compactionTimeoutFailOpen = {
			elapsedMs: timeoutElapsedMs,
			result: timeoutCompaction,
			after: timeoutCompactionPost,
		};

		const allRecords = records();
		const receipt = {
			schemaVersion: 1,
			probe: "untouched-stock-host-lifecycle",
			createdAt: new Date().toISOString(),
			host: {
				version: "18.1.10",
				binary,
				binarySha256: await sha256(binary),
				package: "@oh-my-pi/pi-coding-agent@18.1.10",
			},
			isolation: { agentDir, sessionDir, extension, config },
			observations,
			verdict: {
				customManualAndAutomaticCompaction: "observed",
				requestedAndUnrequestedTreeSummaries: "observed",
				treeCancellation: "observed",
				compactionCancellation: "observed",
				errorBehavior: "fail-open to native implementation",
				timeoutBehavior: "fail-open to native implementation",
			},
			eventCounts: Object.fromEntries(
				Array.from(new Set(allRecords.map(record => record.event))).sort().map(event => [
					event,
					allRecords.filter(record => record.event === event).length,
				]),
			),
		};
		writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
		console.log(JSON.stringify({ receiptPath, verdict: receipt.verdict, eventCounts: receipt.eventCounts }, null, 2));
	} finally {
		await client.stop();
	}
}

await main();
