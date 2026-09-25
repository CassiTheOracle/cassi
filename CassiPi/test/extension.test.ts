import { describe, expect, test } from "bun:test";

import { createCassiPiExtension } from "../src/extension.ts";
import { FI_RUNTIME_ID, canonicalJson, sha256 } from "../src/protocol.ts";

const REVISION = "c".repeat(64);
const PREVIEW = "a".repeat(64);
const EVENT = "b".repeat(64);
const HEAD = "d".repeat(64);

function typebox() {
  const Type = {
    Array: (item: unknown, options?: unknown) => ({ kind: "array", item, options }),
    Integer: (options?: unknown) => ({ kind: "integer", options }),
    Literal: (value: string) => ({ kind: "literal", value }),
    Object: (properties: unknown, options?: unknown) => ({ kind: "object", properties, options }),
    Optional: (item: unknown) => ({ kind: "optional", item }),
    String: (options?: unknown) => ({ kind: "string", options }),
    Union: (items: unknown[]) => ({ kind: "union", items }),
  };
  return { Type };
}

function ownerStatus() {
  return {
    schema: "cassipi.owner-status.v1",
    active_state_sha256: "0".repeat(64),
    branch_id: "branch-a",
    capacity: {},
    checkpoint_hash: "1".repeat(64),
    checkpoint_id: "checkpoint-a",
    field_head_sha256: HEAD,
    journal_head_sha256: "e".repeat(64),
    persistent: true,
    profile_id: "profile-a",
    project_id: "project-a",
    revocation_epoch: 0,
    generation_id: "legacy-root",
    session_id: "session-a",
    source_root_digest: "f".repeat(64),
    task_scope: "task-a",
    protocol_id: "cassifi.cassipi-owner-rpc.v1",
    runtime_id: FI_RUNTIME_ID,
    closure_sha256: "2".repeat(64),
    manifest_sha256: "3".repeat(64),
  };
}

const PROJECTION_ACTION = "e".repeat(64);
const PROJECTION_EVENT = "f".repeat(64);
const PROJECTION_INVENTORY = "1".repeat(64);
const PROJECTION_ID = "2".repeat(64);
const PROJECTION_REVISION = "3".repeat(64);
function harness(
  confirmResult = false,
  statusError?: Error,
  sessionEntries: Array<Record<string, unknown>> = [],
  bindingRows: Array<Record<string, unknown>> = [],
  activeBranchEntries: Array<Record<string, unknown>> = sessionEntries,
  temporalOverrides: {
    proposalAuthorized?: boolean;
    selectionMutable?: boolean;
  } = {},
) {
  const operations: Array<{ operation: string; request: Record<string, unknown>; scope: unknown }> = [];
  let projectionSourceHash = "4".repeat(64);
  const notifications: string[] = [];
  const client = {
    async connect() {},
    diagnostics() {
      return {
        schema: "cassipi.worker-diagnostics.v1",
        readiness: statusError ? "unavailable" : "ready",
        recovery: { status: "clean" },
      };
    },
    async status() {
      if (statusError) throw statusError;
      return ownerStatus();
    },
    async owner(
      operation: string,
      request: Record<string, unknown>,
      _signal: AbortSignal | undefined,
      scope: unknown,
    ) {
      operations.push({ operation, request, scope });
      if (operation === "capture_status") {
        return {
          schema: "cassipi.capture-control.v1",
          paused: false,
          operation_id: null,
          profile_id: "profile-a",
        };
      }
      if (operation === "forget_preview") {
        return {
          schema: "cassipi.forget-preview.v1",
          preview_id: PREVIEW,
          binding: {
            schema: "cassipi.forget-binding.v1",
            revision_ids: [REVISION],
            field_head_sha256: HEAD,
          },
          matches: [{ revision_id: REVISION, content_sha256: "2".repeat(64) }],
          affected_heads: [HEAD],
          managed_checkpoint_ids: ["1".repeat(64)],
          external_copy_limits: ["Oh My Pi transcripts"],
        };
      }
      if (operation === "projection_inventory") {
        return {
          schema: "cassipi.projection-inventory.v1",
          inventory_sha256: PROJECTION_INVENTORY,
          candidates: [{
            event_id: PROJECTION_EVENT,
            mandatory: false,
            native_entry_id: "historical-message",
            order: 0,
            revision_id: PROJECTION_REVISION,
            source: {
              content_sha256: projectionSourceHash,
              revision_id: PROJECTION_REVISION,
            },
            representations: [{
              action_id: PROJECTION_ACTION,
              message: { role: "assistant", content: "Frozen field evidence." },
              message_sha256: "5".repeat(64),
              representation: "exact",
            }],
          }],
        };
      }
      if (operation === "project") {
        return {
          schema: "cassipi.projection.v1",
          projection_id: PROJECTION_ID,
          status: "ready",
          identity: {
            field_head_sha256: HEAD,
            journal_head_sha256: "e".repeat(64),
            revocation_epoch: 0,
          },
          messages: [{ role: "assistant", content: "Frozen field evidence." }],
          selected: [{
            action_id: PROJECTION_ACTION,
            revision_id: PROJECTION_REVISION,
            event_id: PROJECTION_EVENT,
            representation: "exact",
            source: {
              content_sha256: projectionSourceHash,
              revision_id: PROJECTION_REVISION,
            },
            tokens: 4,
          }],
          accounting: {
            context_window_tokens: 2048,
            used_tokens: 12,
            remaining_tokens: 2036,
          },
        };
      }
      if (operation === "forget_authorize") {
        return {
          schema: "cassipi.forget-authorization.v1",
          authorization_token: "one-use-secret",
          preview_id: PREVIEW,
          one_use: true,
        };
      }
      if (operation === "bindings") {
        return {
          schema: "cassipi.host-bindings.v1",
          bindings: bindingRows,
        };
      }
      if (operation === "lineage_lookup") {
        const row = bindingRows.find(candidate =>
          candidate.native_entry_id === request.native_entry_id
          && typeof candidate.head_id === "string"
        );
        return {
          schema: "cassipi.lineage-lookup.v1",
          found: Boolean(row),
          head_id: row?.head_id ?? null,
          event_id: row?.event_id ?? null,
        };
      }
      if (operation === "observe") {
        return {
          schema: "cassipi.observe.v1",
          event_id: EVENT,
          source: {
            revision_id: REVISION,
            content_sha256: "2".repeat(64),
          },
          receipt: {
            checkpoint_metadata_sha256: HEAD,
          },
        };
      }
      if (operation === "memory_remember" || operation === "memory_correct") {
        return {
          event_id: EVENT,
          source: {
            revision_id: REVISION,
            content_sha256: "2".repeat(64),
          },
          receipt: {
            checkpoint_metadata_sha256: HEAD,
          },
        };
      }
      if (operation === "lifecycle_prepare") {
        const status = ownerStatus();
        return {
          schema: "cassipi.lifecycle-prepare.v1",
          event_id: EVENT,
          binding: {
            ownerId: "cassipi",
            apiVersion: 1,
            operationId: request.operation_id,
            sourceSessionId: request.source_session_id,
            sourceLeafId: request.source_leaf_id,
            headId: request.target_head_id,
            checkpointId: status.checkpoint_id,
            checkpointHash: status.checkpoint_hash,
            sourceRootDigest: request.source_root_digest,
            coveredThroughEntryId: request.covered_through_entry_id,
            revocationEpoch: status.revocation_epoch,
          },
        };
      }
      if (operation === "lifecycle_commit") {
        const binding = request.binding as { headId: string };
        return {
          schema: "cassipi.lifecycle-commit.v1",
          event_id: EVENT,
          binding,
          active_head_id: binding.headId,
          replayed: false,
        };
      }
      if (operation === "forget_execute") {
        return {
          schema: "cassipi.forget-execute.v1",
          event_id: EVENT,
          authorization_consumed: true,
        };
      }
      if (operation === "import_preview") {
        return {
          schema: "cassipi.import-preview.v1",
          preview_id: PREVIEW,
          adapter: "omp-session",
          record_count: 2,
          memory_scope: "project",
          source_path: request.source_path,
        };
      }
      if (operation === "import_commit") {
        return {
          schema: "cassipi.import-commit.v1",
          preview_id: PREVIEW,
          imported_records: 2,
          status: "committed",
        };
      }
      if (
        operation === "configure_temporal"
        || operation === "learn_temporal"
        || operation === "advance_temporal"
        || operation === "reset_temporal"
        || operation === "bind_temporal"
        || operation === "condense_temporal_skill"
        || operation === "compose_temporal_task"
        || operation === "propose_temporal_task"
        || operation === "acknowledge_temporal_task"
      ) {
        return {
          receipt: {
            operation_id: request.operation_id,
            state_sha256: HEAD,
            ...(operation === "compose_temporal_task" || operation === "propose_temporal_task"
              ? { execution_authorized: temporalOverrides.proposalAuthorized ?? false }
              : {}),
          },
          checkpoint_receipt: { manifest_sha256: HEAD },
        };
      }
      if (operation === "select_temporal_action") {
        return {
          schema: "cassifi.temporal-resonant-action-selection.v1",
          read_only: !(temporalOverrides.selectionMutable ?? false),
          memory_unchanged: !(temporalOverrides.selectionMutable ?? false),
          selected: null,
        };
      }
      if (
        operation === "inspect_temporal"
        || operation === "inquire_temporal"
        || operation === "inspect_temporal_task"
      ) {
        return {
          schema: "cassifi.temporal-inspection.v1",
          state_sha256: HEAD,
        };
      }
      throw new Error(`unexpected operation ${operation}`);
    },
  };
  const handlers = new Map<string, Array<(event: unknown, context: unknown) => unknown>>();
  const tools: Array<Record<string, unknown>> = [];
  const commands = new Map<string, { handler(args: string, context: unknown): Promise<void> }>();
  const owners: unknown[] = [];
  const api = {
    typebox: typebox(),
    registerContextOwner(owner: unknown) {
      owners.push(owner);
    },
    registerTool(tool: Record<string, unknown>) {
      tools.push(tool);
    },
    registerCommand(name: string, command: { handler(args: string, context: unknown): Promise<void> }) {
      commands.set(name, command);
    },
    on(name: string, handler: (event: unknown, context: unknown) => unknown) {
      const rows = handlers.get(name) ?? [];
      rows.push(handler);
      handlers.set(name, rows);
    },
  };
  const context = {
    cwd: process.cwd(),
    sessionManager: {
      getBranch: () => activeBranchEntries,
      getEntries: () => sessionEntries,
      getLeafId: () => {
        const id = sessionEntries.at(-1)?.id;
        return typeof id === "string" ? id : null;
      },
      getSessionId: () => "session-a",
    },
    model: undefined,
    hasUI: true,
    ui: {
      confirm: async () => confirmResult,
      notify: (message: string) => notifications.push(message),
    },
    getContextUsage: () => undefined,
  };
  createCassiPiExtension({ profileId: "profile-a", client })(api);
  return {
    commands,
    context,
    handlers,
    notifications,
    operations,
    owners,
    setProjectionSourceHash(value: string) {
      projectionSourceHash = value;
    },
    tools,
  };
}

describe("CassiPi extension boundary", () => {
  test("registers exactly one owner, one memory tool, and one command", () => {
    const value = harness();
    expect(value.owners).toEqual([{ id: "cassipi", apiVersion: 1 }]);
    expect(value.tools).toHaveLength(1);
    expect(value.tools[0]?.name).toBe("cassi_memory");
    expect(value.tools[0]?.parameters).toMatchObject({ kind: "object" });
    expect(value.commands.size).toBe(1);
    expect(value.commands.has("cassi")).toBe(true);
  });

  test("freezes field evidence within one agent turn and invalidates collisions", async () => {
    const model = {
      provider: "openai-codex",
      id: "test-model",
      contextWindow: 32_768,
      maxTokens: 4096,
    };
    const userMessage = {
      role: "user",
      content: [{ type: "text", text: "Continue the current task." }],
      timestamp: 1,
    };
    const toolResult = {
      role: "toolResult",
      toolCallId: "call-1",
      toolName: "read",
      content: [{ type: "text", text: "Fresh tool output." }],
      isError: false,
      timestamp: 2,
    };
    const value = harness();
    Object.assign(value.context, { model });
    const contextHandler = value.handlers.get("context")![0]!;
    await value.handlers.get("agent_start")![0]!({}, value.context);
    await contextHandler({ messages: [userMessage] }, value.context);
    await contextHandler({ messages: [userMessage, toolResult] }, value.context);
    let projectRequests = value.operations
      .filter(row => row.operation === "project")
      .map(row => row.request);
    expect(projectRequests).toHaveLength(2);
    expect(projectRequests[0]?.frozen_action_ids).toBeUndefined();
    expect(projectRequests[1]?.frozen_action_ids).toEqual([PROJECTION_ACTION]);

    await value.handlers.get("agent_end")![0]!({}, value.context);
    await contextHandler({ messages: [userMessage, toolResult] }, value.context);
    projectRequests = value.operations
      .filter(row => row.operation === "project")
      .map(row => row.request);
    expect(projectRequests[2]?.frozen_action_ids).toBeUndefined();

    const collision = harness();
    Object.assign(collision.context, { model });
    collision.setProjectionSourceHash(sha256(canonicalJson(toolResult)));
    const collisionContext = collision.handlers.get("context")![0]!;
    await collision.handlers.get("agent_start")![0]!({}, collision.context);
    await collisionContext({ messages: [userMessage] }, collision.context);
    await collisionContext({ messages: [userMessage, toolResult] }, collision.context);
    const collisionRequests = collision.operations
      .filter(row => row.operation === "project")
      .map(row => row.request);
    expect(collisionRequests).toHaveLength(2);
    expect(collisionRequests[1]?.frozen_action_ids).toBeUndefined();
  });

  test("status reports readiness, scope, recovery, and unavailability", async () => {
    const ready = harness();
    await ready.commands.get("cassi")!.handler("status", ready.context);
    const readyStatus = JSON.parse(ready.notifications.at(-1)!);
    expect(readyStatus).toMatchObject({
      readiness: "ready",
      scope: {
        profile_id: "profile-a",
        session_id: "session-a",
      },
      worker: {
        readiness: "ready",
        recovery: { status: "clean" },
      },
      capture: { paused: false },
    });

    const unavailable = harness(false, new Error("owner offline"));
    await unavailable.commands.get("cassi")!.handler("status", unavailable.context);
    const unavailableStatus = JSON.parse(unavailable.notifications.at(-1)!);
    expect(unavailableStatus).toMatchObject({
      readiness: "unavailable",
      worker: { readiness: "unavailable" },
      error: { code: "OWNER_UNAVAILABLE" },
    });
  });

  test("memory writes retain explicit scope, source links, and observed time", async () => {
    const value = harness();
    const tool = value.tools[0] as {
      execute(
        id: string,
        params: unknown,
        signal: AbortSignal | undefined,
        update: undefined,
        context: unknown,
      ): Promise<{ details: unknown }>;
    };
    await tool.execute(
      "tool-remember",
      {
        schema: "cassipi.memory-tool.v1",
        action: "remember",
        content: "Keep this exact statement.",
        scope: "project",
        source_refs: ["4".repeat(64)],
      },
      undefined,
      undefined,
      value.context,
    );
    await tool.execute(
      "tool-correct",
      {
        schema: "cassipi.memory-tool.v1",
        action: "correct",
        replacement: "Use the corrected statement.",
        target_revision_id: REVISION,
        scope: "project",
        source_refs: [REVISION],
      },
      undefined,
      undefined,
      value.context,
    );

    const remember = value.operations.find(row => row.operation === "memory_remember")!;
    const correct = value.operations.find(row => row.operation === "memory_correct")!;
    expect(remember.request.payload).toEqual({
      memory_scope: "project",
      declaration_kind: "remember",
      source_refs: ["4".repeat(64)],
    });
    expect(remember.request.source).toMatchObject({
      message_role: "custom",
      fidelity: "exact-observed-bytes",
    });
    const observedTimestamp = (remember.request.source as { observed_timestamp: string }).observed_timestamp;
    expect(observedTimestamp).not.toBe("1970-01-01T00:00:00.000Z");
    expect(Number.isNaN(Date.parse(observedTimestamp))).toBe(false);
    expect(correct.request.target_revision_id).toBe(REVISION);
    expect(correct.request.payload).toMatchObject({
      declaration_kind: "correct",
      source_refs: [REVISION],
    });
  });

  test("model-facing forget can only produce a preview", async () => {
    const value = harness(true);
    const tool = value.tools[0] as {
      execute(
        id: string,
        params: unknown,
        signal: AbortSignal | undefined,
        update: undefined,
        context: unknown,
      ): Promise<{ details: unknown }>;
    };
    const result = await tool.execute(
      "tool-call-a",
      {
        schema: "cassipi.memory-tool.v1",
        action: "forget",
        target_revision_id: REVISION,
        scope: "project",
      },
      undefined,
      undefined,
      value.context,
    );

    expect(value.operations.map(row => row.operation)).toEqual(["forget_preview"]);
    expect(JSON.stringify(result.details)).not.toContain("authorization_token");
    expect(JSON.stringify(result.details)).not.toContain("forget_execute");
  });

  test("direct forget command changes nothing when confirmation is canceled", async () => {
    const value = harness(false);
    await value.commands.get("cassi")!.handler(`forget project ${REVISION}`, value.context);

    expect(value.operations.map(row => row.operation)).toEqual(["forget_preview"]);
    expect(value.notifications.at(-1)).toContain("canceled");
  });

  test("direct forget consumes a one-use token without disclosing it", async () => {
    const value = harness(true);
    await value.commands.get("cassi")!.handler(`forget project ${REVISION}`, value.context);

    expect(value.operations.map(row => row.operation)).toEqual([
      "forget_preview",
      "forget_authorize",
      "bindings",
      "forget_execute",
    ]);
    const execution = value.operations.at(-1)!;
    expect(execution.request.authorization_token).toBe("one-use-secret");
    expect(value.notifications.join("\n")).not.toContain("one-use-secret");
    expect(execution.scope).toMatchObject({
      profile_id: "profile-a",
      session_id: "session-a",
    });
  });

  test("tree navigation restores heads recorded by owner bindings", async () => {
    const compactedEntryId = "compacted-entry";
    const bindingEntryId = "binding-entry";
    const boundHead = "9".repeat(64);
    const entries = [
      { id: compactedEntryId, type: "compaction" },
      {
        id: bindingEntryId,
        parentId: compactedEntryId,
        type: "custom",
        customType: "context_owner_binding",
        data: {
          ownerId: "cassipi",
          apiVersion: 1,
          operationId: "compact-operation",
          sourceSessionId: "session-a",
          sourceLeafId: "source-entry",
          headId: boundHead,
          checkpointId: "checkpoint-bound",
          checkpointHash: "8".repeat(64),
          sourceRootDigest: "7".repeat(64),
          coveredThroughEntryId: "source-entry",
          revocationEpoch: 0,
          operationKind: "compact",
          targetSessionId: "session-a",
          targetLeafId: compactedEntryId,
          committedEntryId: compactedEntryId,
        },
      },
    ];

    for (const targetId of [compactedEntryId, bindingEntryId]) {
      const value = harness(false, undefined, entries);
      const beforeTree = value.handlers.get("session_before_tree")?.[0];
      expect(beforeTree).toBeDefined();
      const result = await beforeTree!(
        { preparation: { targetId, userWantsSummary: false } },
        value.context,
      ) as { ownerBinding: { headId: string } };
      expect(value.operations.some(row => row.operation === "lineage_lookup")).toBe(false);
      expect(value.operations.find(row => row.operation === "lifecycle_prepare")?.request.target_head_id).toBe(boundHead);
      expect(result.ownerBinding.headId).toBe(boundHead);
    }
  });
  test("tool rewrites are distinct immutable proposals, not evidence corrections", async () => {
    const value = harness();
    const handler = value.handlers.get("tool_call")?.[0];
    expect(handler).toBeDefined();
    await handler!(
      {
        toolCallId: "rewritten-tool-call",
        toolName: "write",
        input: { path: "xd://lsp", content: "{\"action\":\"references\"}" },
      },
      value.context,
    );
    await handler!(
      {
        toolCallId: "rewritten-tool-call",
        toolName: "lsp",
        input: { action: "references" },
      },
      value.context,
    );

    const proposals = value.operations.filter(row =>
      row.operation === "observe" && row.request.event_kind === "action-proposal"
    );
    expect(proposals).toHaveLength(2);
    expect(proposals[0].request.native_entry_id).not.toBe(proposals[1].request.native_entry_id);
    expect(proposals[0].request.source.source_id).not.toBe(proposals[1].request.source.source_id);
    expect(proposals.every(row => row.request.source.parent_revision_id === null)).toBe(true);
  });


  test("tree navigation resolves a credential pin from a disjoint source-leaf binding", async () => {
    const targetId = "ec47cbf3";
    const boundHead = "6".repeat(64);
    const entries = [
      {
        id: "237e99c8",
        parentId: "17579f43",
        type: "message",
        message: { role: "assistant", content: [{ type: "text", text: "SIBLING_RECORDED" }] },
      },
      { id: targetId, parentId: "237e99c8", type: "credential_pin" },
      {
        id: "bd4092f8",
        parentId: "2c252c97",
        type: "custom",
        customType: "context_owner_binding",
        data: {
          ownerId: "cassipi",
          apiVersion: 1,
          operationId: "tree-return-to-main",
          sourceSessionId: "session-a",
          sourceLeafId: targetId,
          headId: boundHead,
          checkpointId: boundHead,
          checkpointHash: "8".repeat(64),
          sourceRootDigest: "7".repeat(64),
          coveredThroughEntryId: targetId,
          revocationEpoch: 0,
          operationKind: "tree",
          targetSessionId: "session-a",
          targetLeafId: "2c252c97",
          committedEntryId: "2c252c97",
        },
      },
    ];
    const value = harness(false, undefined, entries);
    const result = await value.handlers.get("session_before_tree")![0]!(
      { preparation: { targetId, userWantsSummary: false } },
      value.context,
    ) as { ownerBinding: { headId: string } };

    expect(value.operations.some(row => row.operation === "lineage_lookup")).toBe(false);
    expect(value.operations.find(row => row.operation === "lifecycle_prepare")?.request.target_head_id).toBe(boundHead);
    expect(result.ownerBinding.headId).toBe(boundHead);
  });

  test("compacted branches retain their ancestral user task scope", async () => {
    const userId = "task-user";
    const compactedEntryId = "task-compaction";
    const boundHead = "5".repeat(64);
    const postCompaction = {
      id: "post-compaction-output",
      parentId: "task-binding",
      type: "message",
      message: {
        role: "assistant",
        content: [{ type: "text", text: "irrelevant tool output" }],
      },
    };
    const entries = [
      {
        id: userId,
        type: "message",
        message: { role: "user", content: [{ type: "text", text: "Keep this correction." }] },
      },
      {
        id: "pre-compaction-assistant",
        parentId: userId,
        type: "message",
        message: { role: "assistant", content: [{ type: "text", text: "Understood." }] },
      },
      { id: compactedEntryId, parentId: "pre-compaction-assistant", type: "compaction" },
      {
        id: "task-binding",
        parentId: compactedEntryId,
        type: "custom",
        customType: "context_owner_binding",
        data: {
          ownerId: "cassipi",
          apiVersion: 1,
          operationId: "task-compaction-operation",
          sourceSessionId: "session-a",
          sourceLeafId: "pre-compaction-assistant",
          headId: boundHead,
          checkpointId: boundHead,
          checkpointHash: "8".repeat(64),
          sourceRootDigest: "7".repeat(64),
          coveredThroughEntryId: "pre-compaction-assistant",
          revocationEpoch: 0,
          operationKind: "compact",
          targetSessionId: "session-a",
          targetLeafId: compactedEntryId,
          committedEntryId: compactedEntryId,
        },
      },
      postCompaction,
    ];
    const value = harness(false, undefined, entries, [], [postCompaction]);
    await value.handlers.get("session_before_tree")![0]!(
      { preparation: { targetId: compactedEntryId, userWantsSummary: false } },
      value.context,
    );

    const observations = value.operations.filter(row => row.operation === "observe");
    expect(observations.length).toBeGreaterThan(0);
    expect(observations.every(row => row.request.task_scope === userId)).toBe(true);
    expect(value.operations.find(row => row.operation === "lifecycle_prepare")?.request.task_scope).toBe(userId);
  });

  test("retains raw signatures while only declared transport state is replay-equivalent", async () => {
    const messageEntryId = "signed-message";
    const compactedEntryId = "signed-compaction";
    const oldRevision = "4".repeat(64);
    const boundHead = "9".repeat(64);
    const stableMessage = {
      role: "assistant",
      content: [{ type: "thinking", thinking: "semantic reasoning" }],
      timestamp: 1,
    };
    const signedMessage = {
      ...stableMessage,
      content: [{
        type: "thinking",
        thinking: "semantic reasoning",
        thinkingSignature: "opaque-provider-transport-state",
      }],
    };
    const entriesFor = (message: Record<string, unknown>) => [
      { id: messageEntryId, type: "message", message },
      { id: compactedEntryId, parentId: messageEntryId, type: "compaction" },
      {
        id: "signed-binding",
        parentId: compactedEntryId,
        type: "custom",
        customType: "context_owner_binding",
        data: {
          ownerId: "cassipi",
          apiVersion: 1,
          operationId: "signed-operation",
          sourceSessionId: "session-a",
          sourceLeafId: messageEntryId,
          headId: boundHead,
          checkpointId: "signed-checkpoint",
          checkpointHash: "8".repeat(64),
          sourceRootDigest: "7".repeat(64),
          coveredThroughEntryId: messageEntryId,
          revocationEpoch: 0,
          operationKind: "compact",
          targetSessionId: "session-a",
          targetLeafId: compactedEntryId,
          committedEntryId: compactedEntryId,
        },
      },
    ];
    const first = harness(false, undefined, entriesFor(signedMessage));
    const firstBeforeTree = first.handlers.get("session_before_tree")?.[0];
    expect(firstBeforeTree).toBeDefined();
    await firstBeforeTree!(
      { preparation: { targetId: compactedEntryId, userWantsSummary: false } },
      first.context,
    );
    const firstObservation = first.operations.find(row => row.operation === "observe");
    const source = firstObservation?.request.source as Record<string, unknown>;
    const signedRaw = canonicalJson(signedMessage);
    expect(Buffer.from(String(source.content_base64), "base64").toString("utf8")).toBe(signedRaw);
    expect(source.content_sha256).toBe(sha256(signedRaw));
    expect(source).toMatchObject({
      host_replay_schema: "cassipi.host-message-replay.v1",
      host_replay_volatile_fields: ["content[].thinkingSignature"],
    });
    expect(source.host_replay_sha256).toBe(
      "dc6816e97326609aef135684ff7dcc647afa8f72fcf0c94e8954d95fb31ae8fe",
    );

    const bindings = [{
      event_id: "6".repeat(64),
      event_kind: "observation",
      native_entry_id: messageEntryId,
      tool_call_id: null,
      provisional_observation_id: null,
      parent_head_id: "7".repeat(64),
      predecessor_event_id: null,
      producer_sequence: 0,
      sources: [{
        revision_id: oldRevision,
        content_sha256: sha256(signedRaw),
        metadata: {
          status: "active",
          host_replay_schema: source.host_replay_schema,
          host_replay_sha256: source.host_replay_sha256,
          host_replay_volatile_fields: source.host_replay_volatile_fields,
        },
      }],
    }];
    const replay = harness(false, undefined, entriesFor(stableMessage), bindings);
    await replay.handlers.get("session_before_tree")![0]!(
      { preparation: { targetId: compactedEntryId, userWantsSummary: false } },
      replay.context,
    );
    expect(replay.operations.some(row => row.operation === "observe")).toBe(false);

    const changed = harness(
      false,
      undefined,
      entriesFor({
        ...stableMessage,
        content: [{ type: "thinking", thinking: "different semantic reasoning" }],
      }),
      bindings,
    );
    await changed.handlers.get("session_before_tree")![0]!(
      { preparation: { targetId: compactedEntryId, userWantsSummary: false } },
      changed.context,
    );
    const changedObservation = changed.operations.find(row => row.operation === "observe");
    expect(changedObservation?.request.source).toMatchObject({ parent_revision_id: oldRevision });
    expect(
      (changedObservation?.request.source as Record<string, unknown>).host_replay_sha256,
    ).not.toBe(source.host_replay_sha256);
  });

  test("reload-normalized messages continue the exact source revision chain", async () => {
    const messageEntryId = "message-entry";
    const compactedEntryId = "compacted-entry";
    const oldRevision = "4".repeat(64);
    const boundHead = "9".repeat(64);
    const entries = [
      {
        id: messageEntryId,
        type: "message",
        message: {
          role: "user",
          content: [{ type: "text", text: "Reload-normalized content" }],
          timestamp: 1,
        },
      },
      { id: compactedEntryId, parentId: messageEntryId, type: "compaction" },
      {
        id: "binding-entry",
        parentId: compactedEntryId,
        type: "custom",
        customType: "context_owner_binding",
        data: {
          ownerId: "cassipi",
          apiVersion: 1,
          operationId: "compact-operation",
          sourceSessionId: "session-a",
          sourceLeafId: messageEntryId,
          headId: boundHead,
          checkpointId: "checkpoint-bound",
          checkpointHash: "8".repeat(64),
          sourceRootDigest: "7".repeat(64),
          coveredThroughEntryId: messageEntryId,
          revocationEpoch: 0,
          operationKind: "compact",
          targetSessionId: "session-a",
          targetLeafId: compactedEntryId,
          committedEntryId: compactedEntryId,
        },
      },
    ];
    const bindings = [{
      event_id: "6".repeat(64),
      event_kind: "observation",
      native_entry_id: messageEntryId,
      tool_call_id: null,
      provisional_observation_id: null,
      parent_head_id: "7".repeat(64),
      predecessor_event_id: null,
      producer_sequence: 0,
      sources: [{
        revision_id: oldRevision,
        content_sha256: "5".repeat(64),
        metadata: { status: "active" },
      }],
    }];
    const value = harness(false, undefined, entries, bindings);
    const beforeTree = value.handlers.get("session_before_tree")?.[0];
    expect(beforeTree).toBeDefined();
    await beforeTree!(
      { preparation: { targetId: compactedEntryId, userWantsSummary: false } },
      value.context,
    );

    const observation = value.operations.find(row => row.operation === "observe");
    expect(observation?.request.source).toMatchObject({ parent_revision_id: oldRevision });
  });

  test("explicit temporal commands reach v4 without adding a model-facing tool", async () => {
    const value = harness();
    const command = value.commands.get("cassi")!;
    await command.handler(
      `temporal configure ${JSON.stringify({
        memory_id: "release-flow",
        action_ids: ["open", "close"],
        observation_ids: ["ready", "closed"],
      })}`,
      value.context,
    );
    await command.handler(
      `temporal learn ${JSON.stringify({
        memory_id: "release-flow",
        source: {
          source_id: "release-flow-episode",
          content_base64: "eyJzY2hlbWEiOiJjYXNzaWZpLnRlbXBvcmFsLWVwaXNvZGUudjEiLCJzdGVwcyI6W119",
          media_type: "application/json",
          codec: "utf-8",
          observed_timestamp: "2026-09-10T00:00:00Z",
          scope: "task",
          claim_category: "observation",
          fidelity: "exact",
          parent_revision_id: null,
          span: null,
          labels: [],
        },
      })}`,
      value.context,
    );
    await command.handler(
      `temporal inspect ${JSON.stringify({ memory_id: "release-flow" })}`,
      value.context,
    );

    expect(value.tools).toHaveLength(1);
    expect(value.operations.map(row => row.operation)).toEqual([
      "configure_temporal",
      "learn_temporal",
      "inspect_temporal",
    ]);
    expect(value.operations[0]?.request).toMatchObject({
      schema: "cassipi.configure-temporal.v1",
      memory_id: "release-flow",
      action_ids: ["open", "close"],
      observation_ids: ["ready", "closed"],
    });
    expect(value.operations[0]?.request.operation_id).toMatch(/^temporal-command:/u);
    expect(value.operations[0]?.scope).toMatchObject({
      profile_id: "profile-a",
      session_id: "session-a",
    });
    expect(value.operations[2]?.request).toEqual({
      schema: "cassipi.inspect-temporal.v1",
      memory_id: "release-flow",
    });
  });

  test("temporal commands reject malformed or undeclared fields before owner mutation", async () => {
    const value = harness();
    const command = value.commands.get("cassi")!;
    await expect(command.handler("temporal configure not-json", value.context)).rejects.toThrow(
      "requires one valid JSON object",
    );
    await expect(
      command.handler(
        `temporal advance ${JSON.stringify({
          memory_id: "release-flow",
          action: "open",
          observation: "ready",
          invented: true,
        })}`,
        value.context,
      ),
    ).rejects.toThrow("unsupported fields");
    expect(value.operations).toEqual([]);
  });

  test("temporal selection stays read-only and task proposals stay host-owned", async () => {
    const safe = harness();
    const safeCommand = safe.commands.get("cassi")!;
    await safeCommand.handler(
      `temporal select ${JSON.stringify({
        memory_id: "release-flow",
        skill_ids: ["open-skill"],
        operations: [{
          action: "open",
          authorized: true,
          feasible: true,
          represented_forbidden: false,
        }],
      })}`,
      safe.context,
    );
    await safeCommand.handler(
      `temporal propose-task ${JSON.stringify({
        task_id: "release-task",
        allowed_actions: [{ participant_id: "operator", action: "open" }],
      })}`,
      safe.context,
    );

    const unsafeProposal = harness(false, undefined, [], [], [], {
      proposalAuthorized: true,
    });
    await expect(
      unsafeProposal.commands.get("cassi")!.handler(
        `temporal propose-task ${JSON.stringify({
          task_id: "release-task",
          allowed_actions: [{ participant_id: "operator", action: "open" }],
        })}`,
        unsafeProposal.context,
      ),
    ).rejects.toThrow("did not preserve host execution authority");

    const mutableSelection = harness(false, undefined, [], [], [], {
      selectionMutable: true,
    });
    await expect(
      mutableSelection.commands.get("cassi")!.handler(
        `temporal select ${JSON.stringify({
          memory_id: "release-flow",
          skill_ids: ["open-skill"],
          operations: [{
            action: "open",
            authorized: true,
            feasible: true,
            represented_forbidden: false,
          }],
        })}`,
        mutableSelection.context,
      ),
    ).rejects.toThrow("not a read-only field selection");
  });

  test("import preview is non-mutating and commit requires direct confirmation", async () => {
    const canceled = harness(false);
    const command = canceled.commands.get("cassi")!;
    await command.handler("import preview omp-session project fixture.jsonl", canceled.context);
    await command.handler(`import commit ${PREVIEW}`, canceled.context);
    expect(canceled.operations.map(row => row.operation)).toEqual(["import_preview"]);

    const approved = harness(true);
    const approvedCommand = approved.commands.get("cassi")!;
    await approvedCommand.handler("import preview omp-session project fixture.jsonl", approved.context);
    await approvedCommand.handler(`import commit ${PREVIEW}`, approved.context);
    expect(approved.operations.map(row => row.operation)).toEqual([
      "import_preview",
      "import_commit",
    ]);
    expect(approved.operations[1]?.request.preview_id).toBe(PREVIEW);
  });
});
