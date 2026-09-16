import { createHash, randomUUID } from "node:crypto";
import { readFile, realpath, stat } from "node:fs/promises";
import { resolve } from "node:path";

import { Tokenizer, type AgentMessage } from "@oh-my-pi/pi-agent-core";
import type { Api, Model } from "@oh-my-pi/pi-catalog/types";
import type { AssistantMessage } from "@oh-my-pi/pi-ai";
import {
  OWNER_API_VERSION,
  OWNER_ID,
  PROTOCOL_ID,
  canonicalJson,
  assertHostOwnedProposal,
  decodeTemporalMutationResult,
  decodeTemporalReadResult,
  decodeTemporalSelectionResult,
  decodeLifecycleCancel,
  decodeLifecycleCommit,
  decodeLifecyclePending,
  decodeCaptureStatus,
  decodeLifecyclePrepare,
  decodeLineageLookup,
  decodeObservedResult,
  decodeProjectionInventory,
  decodeProjectionResult,
  decodeSourceBindings,
  decodeHostOperationBinding,
  isRecord,
  jsonRecord,
  requiredInteger,
  requiredString,
  sha256,
  type HostOperationBinding,
  type AuthenticatedHostScope,
  type HostProjectionBinding,
  type Json,
  type OwnerStatus,
  type ProjectionResult,
} from "./protocol.js";
import { CassiPiOwnerError, CassiPiWorkerClient, type WorkerClientOptions } from "./worker-client.js";

type EventHandler = (event: unknown, context: ExtensionContext) => unknown | Promise<unknown>;
type MemoryScope = "task" | "branch" | "project" | "profile";
type TemporalCommandName =
  | "acknowledge-task"
  | "advance"
  | "bind"
  | "compose-task"
  | "configure"
  | "inquire"
  | "inspect"
  | "inspect-task"
  | "learn"
  | "propose-task"
  | "register-skill"
  | "reset"
  | "select";

interface TemporalCommandSpec {
  operation: string;
  schema: string;
  required: readonly string[];
  optional: readonly string[];
  mutation: boolean;
  hostOwnedProposal?: boolean;
  readOnlySelection?: boolean;
}


interface TypeBoxBuilder {
  Array(item: unknown, options?: Record<string, unknown>): unknown;
  Integer(options?: Record<string, unknown>): unknown;
  Literal(value: string): unknown;
  Object(properties: Record<string, unknown>, options?: Record<string, unknown>): unknown;
  Optional(item: unknown): unknown;
  String(options?: Record<string, unknown>): unknown;
  Union(items: unknown[]): unknown;
}

interface ToolExecutionResult {
  content: Array<{ type: "text"; text: string }>;
  details?: Json;
  isError?: boolean;
}

interface ExtensionAPI {
  typebox: { Type: TypeBoxBuilder };
  registerContextOwner(registration: { id: string; apiVersion: 1 }): void;
  registerTool(tool: {
    name: string;
    label: string;
    description: string;
    parameters: unknown;
    approval: "write";
    strict: true;
    execute(
      toolCallId: string,
      params: unknown,
      signal: AbortSignal | undefined,
      onUpdate: ((result: ToolExecutionResult) => void) | undefined,
      context: ExtensionContext,
    ): Promise<ToolExecutionResult>;
  }): void;
  registerCommand(
    name: string,
    command: {
      description: string;
      handler(args: string, context: ExtensionContext): Promise<void>;
    },
  ): void;
  on(event: string, handler: EventHandler): void;
}

interface SessionMessageEntry {
  id: string;
  parentId?: string | null;
  timestamp?: number | string;
  type: "message";
  message: AgentMessage;
}

interface SessionOtherEntry {
  id: string;
  type: string;
  customType?: string;
  data?: unknown;
  [key: string]: unknown;
}

interface SessionManagerView {
  getBranch(leafId?: string | null): Array<SessionMessageEntry | SessionOtherEntry>;
  getEntries(): Array<SessionMessageEntry | SessionOtherEntry>;
  getLeafId(): string | null;
  getSessionId(): string;
}

interface ExtensionContext {
  cwd: string;
  sessionManager: SessionManagerView;
  model: Model<Api> | undefined;
  hasUI: boolean;
  ui: {
    confirm(title: string, message: string): Promise<boolean>;
    notify(message: string, type?: "info" | "warning" | "error"): void;
  };
  getContextUsage(): { tokens: number; contextWindow: number; source: string } | undefined;
}

interface BranchScope {
  profileId: string;
  projectId: string;
  sessionId: string;
  branchId: string;
  taskScope: string;
  producerId: string;
}

interface Cursor {
  lastEventId: string | null;
  nextSequence: number;
  revisionsByNativeAndContent: Map<string, string>;
  revisionByNative: Map<string, string>;
  revisionsByNativeAndReplay: Map<string, string>;
  provisionalByToolStage: Map<string, { eventId: string; revisionIds: string[] }>;
}

interface OwnerClient {
  connect(): Promise<OwnerStatus>;
  close(): Promise<void>;
  status(): Promise<OwnerStatus>;
  diagnostics?(): Json;
  owner(
    operation: string,
    request: Record<string, unknown>,
    signal: AbortSignal | undefined,
    authenticatedScope: AuthenticatedHostScope,
  ): Promise<Json>;
}

interface CassiPiExtensionOptions extends WorkerClientOptions {
  client?: OwnerClient;
  profileId?: string;
  outputReserveTokens?: number;
  maxEvidenceTokens?: number;
}
interface ProjectMessagesOptions {
  allowedMemoryScopes?: MemoryScope[];
  mandatoryRevisionIds?: string[];
  protectedNative?: AgentMessage[];
  purpose?: string;
  query?: string;
  signal?: AbortSignal;
  tokenBudget?: number;
}

interface ProjectMessagesResult {
  binding: HostProjectionBinding;
  messages: AgentMessage[];
  projection: ProjectionResult;
  sourceRootDigest: string;
}

interface ProviderTurnSelection {
  key: string;
  actionIds: string[];
  contentHashes: string[];
}
interface OwnerMarker {
  binding: HostOperationBinding;
  entryId: string;
  committedEntryId: string;
  operationKind: string;
  targetLeafId: string | null;
  targetSessionId: string;
}

interface TargetSessionSnapshot {
  latestEntryId: string | null;
  ownerHeadId: string | null;
  sessionId: string;
}
interface PendingLifecycle {
  binding: HostOperationBinding;
  operationKind: string;
}


interface PreparedRewrite {
  binding: HostOperationBinding;
  details: Record<string, unknown>;
  summary: string;
}

const ZERO_USAGE: AssistantMessage["usage"] = {
  input: 0,
  output: 0,
  cacheRead: 0,
  cacheWrite: 0,
  totalTokens: 0,
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
};

function asEvidenceMessage(content: string, model: Model<Api>): AssistantMessage {
  return {
    role: "assistant",
    content: [{ type: "text", text: content }],
    api: model.api,
    provider: model.provider,
    model: model.id,
    usage: ZERO_USAGE,
    stopReason: "stop",
    timestamp: 0,
  };
}
const MAX_SESSION_FILE_BYTES = 64 * 1024 * 1024;

function contentOf(value: unknown): unknown {
  if (value !== null && typeof value === "object" && "content" in value) return value.content;
  return undefined;
}

function stringField(value: unknown, field: string): string | undefined {
  if (!isRecord(value)) return undefined;
  const candidate = value[field];
  return typeof candidate === "string" ? candidate : undefined;
}

function booleanField(value: unknown, field: string): boolean | undefined {
  if (!isRecord(value)) return undefined;
  const candidate = value[field];
  return typeof candidate === "boolean" ? candidate : undefined;
}

function integerField(value: unknown, field: string): number | undefined {
  if (!isRecord(value)) return undefined;
  const candidate = value[field];
  return Number.isSafeInteger(candidate) ? Number(candidate) : undefined;
}

function stringArrayField(value: unknown, field: string): string[] {
  if (!isRecord(value)) return [];
  const candidate = value[field];
  if (candidate === undefined) return [];
  if (!Array.isArray(candidate) || !candidate.every(item => typeof item === "string")) {
    throw new CassiPiOwnerError("INVALID_TOOL_REQUEST", `${field} must be an array of strings`, 400);
  }
  return candidate;
}

function memoryScopeField(value: unknown): MemoryScope {
  const candidate = stringField(value, "scope");
  if (
    candidate !== "task"
    && candidate !== "branch"
    && candidate !== "project"
    && candidate !== "profile"
  ) {
    throw new CassiPiOwnerError("INVALID_MEMORY_SCOPE", "memory scope is unsupported", 400);
  }
  return candidate;
}

function exactRevisionId(value: unknown, field: string): string {
  const candidate = stringField(value, field);
  if (!candidate || !/^[0-9a-f]{64}$/u.test(candidate)) {
    throw new CassiPiOwnerError(
      "INVALID_SOURCE_IDENTITY",
      `${field} must be an exact lowercase SHA-256 revision identity`,
      400,
    );
  }
  return candidate;
}

function toolResult(details: Json, isError = false): ToolExecutionResult {
  return {
    content: [{ type: "text", text: canonicalJson(details) }],
    details,
    ...(isError ? { isError: true } : {}),
  };
}

function memoryToolParameters(type: TypeBoxBuilder): unknown {
  const version = type.Literal("cassipi.memory-tool.v1");
  const scope = type.Union([
    type.Literal("task"),
    type.Literal("branch"),
    type.Literal("project"),
    type.Literal("profile"),
  ]);
  const revision = type.String({ pattern: "^[0-9a-f]{64}$" });
  const sourceRefs = type.Optional(type.Array(revision, { maxItems: 64 }));
  const closed = { additionalProperties: false };
  return type.Object(
    {
      schema: version,
      action: type.Union([
        type.Literal("recall"),
        type.Literal("remember"),
        type.Literal("correct"),
        type.Literal("forget"),
        type.Literal("inspect"),
      ]),
      scope,
      query: type.Optional(type.String({ maxLength: 4096 })),
      ref: type.Optional(revision),
      token_budget: type.Optional(type.Integer({ minimum: 32, maximum: 4096 })),
      content: type.Optional(type.String({ minLength: 1, maxLength: 65536 })),
      source_refs: sourceRefs,
      target_revision_id: type.Optional(revision),
      replacement: type.Optional(type.String({ minLength: 1, maxLength: 65536 })),
      selector: type.Optional(
        type.Union([
          type.Literal("state"),
          type.Literal("projection"),
          type.Literal("operation"),
          type.Literal("source"),
        ]),
      ),
    },
    closed,
  );
}
const TEMPORAL_COMMAND_SPECS: Record<TemporalCommandName, TemporalCommandSpec> = {
  "acknowledge-task": {
    operation: "acknowledge_temporal_task",
    schema: "cassipi.acknowledge-temporal-task.v1",
    required: ["task_id", "proposal_id", "participant_id", "action", "observation"],
    optional: ["expected_state_sha256"],
    mutation: true,
  },
  advance: {
    operation: "advance_temporal",
    schema: "cassipi.advance-temporal.v1",
    required: ["memory_id", "action", "observation"],
    optional: ["participant_id", "expected_state_sha256"],
    mutation: true,
  },
  bind: {
    operation: "bind_temporal",
    schema: "cassipi.bind-temporal.v1",
    required: ["memory_id", "participant_id"],
    optional: ["known_start", "expected_state_sha256"],
    mutation: true,
  },
  "compose-task": {
    operation: "compose_temporal_task",
    schema: "cassipi.compose-temporal-task.v1",
    required: ["task_id", "steps"],
    optional: ["expected_state_sha256"],
    mutation: true,
    hostOwnedProposal: true,
  },
  configure: {
    operation: "configure_temporal",
    schema: "cassipi.configure-temporal.v1",
    required: ["memory_id", "action_ids", "observation_ids"],
    optional: ["max_states", "expected_state_sha256"],
    mutation: true,
  },
  inquire: {
    operation: "inquire_temporal",
    schema: "cassipi.inquire-temporal.v1",
    required: ["memory_id", "operations"],
    optional: [
      "participant_id",
      "skill_id",
      "goal_observations",
      "horizon",
      "max_nodes",
      "forbidden_observations",
    ],
    mutation: false,
  },
  inspect: {
    operation: "inspect_temporal",
    schema: "cassipi.inspect-temporal.v1",
    required: ["memory_id"],
    optional: ["action", "skill_id", "participant_id"],
    mutation: false,
  },
  "inspect-task": {
    operation: "inspect_temporal_task",
    schema: "cassipi.inspect-temporal-task.v1",
    required: ["task_id"],
    optional: [],
    mutation: false,
  },
  learn: {
    operation: "learn_temporal",
    schema: "cassipi.learn-temporal.v1",
    required: ["memory_id", "source"],
    optional: ["expected_state_sha256"],
    mutation: true,
  },
  "propose-task": {
    operation: "propose_temporal_task",
    schema: "cassipi.propose-temporal-task.v1",
    required: ["task_id", "allowed_actions"],
    optional: ["expected_state_sha256"],
    mutation: true,
    hostOwnedProposal: true,
  },
  "register-skill": {
    operation: "condense_temporal_skill",
    schema: "cassipi.condense-temporal-skill.v1",
    required: ["memory_id", "skill_id", "goal_observations"],
    optional: ["forbidden_observations", "expected_state_sha256"],
    mutation: true,
  },
  reset: {
    operation: "reset_temporal",
    schema: "cassipi.reset-temporal.v1",
    required: ["memory_id"],
    optional: ["participant_id", "known_start", "expected_state_sha256"],
    mutation: true,
  },
  select: {
    operation: "select_temporal_action",
    schema: "cassipi.select-temporal-action.v1",
    required: ["memory_id", "skill_ids", "operations"],
    optional: ["participant_id", "minimum_margin", "expected_state_sha256"],
    mutation: false,
    readOnlySelection: true,
  },
};

function temporalCommandName(value: string): TemporalCommandName {
  if (Object.hasOwn(TEMPORAL_COMMAND_SPECS, value)) return value as TemporalCommandName;
  throw new CassiPiOwnerError(
    "COMMAND_USAGE",
    "usage: /cassi temporal <configure|learn|advance|reset|bind|register-skill|inspect|select|inquire|compose-task|inspect-task|propose-task|acknowledge-task> <json-object>",
    400,
  );
}

function temporalCommandPayload(
  command: TemporalCommandName,
  text: string,
): Record<string, Json> {
  let decoded: unknown;
  try {
    decoded = JSON.parse(text);
  } catch {
    throw new CassiPiOwnerError(
      "COMMAND_USAGE",
      `/cassi temporal ${command} requires one valid JSON object`,
      400,
    );
  }
  const payload = jsonRecord(decoded, `temporal ${command} payload`);
  const spec = TEMPORAL_COMMAND_SPECS[command];
  const unexpected = Object.keys(payload).filter(
    key => !spec.required.includes(key) && !spec.optional.includes(key),
  );
  if (unexpected.length > 0) {
    throw new CassiPiOwnerError(
      "INVALID_TEMPORAL_COMMAND",
      `temporal ${command} has unsupported fields: ${unexpected.sort().join(", ")}`,
      400,
    );
  }
  const missing = spec.required.filter(key => payload[key] === undefined);
  if (missing.length > 0) {
    throw new CassiPiOwnerError(
      "INVALID_TEMPORAL_COMMAND",
      `temporal ${command} is missing required fields: ${missing.join(", ")}`,
      400,
    );
  }
  return payload;
}

function isAgentMessage(value: unknown): value is AgentMessage {
  return isRecord(value) && typeof value.role === "string";
}

const HOST_REPLAY_SCHEMA = "cassipi.host-message-replay.v1";
const HOST_REPLAY_VOLATILE_FIELDS = ["content[].thinkingSignature"] as const;

function stableObservedMessage(value: unknown): unknown {
  if (!isAgentMessage(value)) return value;
  const originalContent = contentOf(value);
  if (!Array.isArray(originalContent)) return value;
  let changed = false;
  const content = (originalContent as unknown[]).map((part: unknown) => {
    if (!isRecord(part) || !("thinkingSignature" in part)) return part;
    const stable = { ...part };
    delete stable.thinkingSignature;
    changed = true;
    return stable;
  });
  return changed ? { ...value, content } : value;
}

function updateReplayHash(hash: ReturnType<typeof createHash>, value: unknown): void {
  const length = (size: number): void => {
    const encoded = Buffer.allocUnsafe(8);
    encoded.writeBigUInt64BE(BigInt(size));
    hash.update(encoded);
  };
  if (value === null) {
    hash.update(Uint8Array.of(0));
    return;
  }
  if (typeof value === "boolean") {
    hash.update(Uint8Array.of(1, value ? 1 : 0));
    return;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("non-finite replay number");
    const encoded = Buffer.allocUnsafe(9);
    encoded[0] = 2;
    encoded.writeDoubleBE(Object.is(value, -0) ? 0 : value, 1);
    hash.update(encoded);
    return;
  }
  if (typeof value === "string") {
    const encoded = Buffer.from(value, "utf8");
    hash.update(Uint8Array.of(3));
    length(encoded.length);
    hash.update(encoded);
    return;
  }
  if (Array.isArray(value)) {
    hash.update(Uint8Array.of(4));
    length(value.length);
    for (const item of value) updateReplayHash(hash, item);
    return;
  }
  if (isRecord(value)) {
    const keys = Object.keys(value)
      .filter(key => value[key] !== undefined)
      .sort((left, right) => Buffer.compare(Buffer.from(left, "utf8"), Buffer.from(right, "utf8")));
    hash.update(Uint8Array.of(5));
    length(keys.length);
    for (const key of keys) {
      updateReplayHash(hash, key);
      updateReplayHash(hash, value[key]);
    }
    return;
  }
  throw new TypeError(`value is not replayable JSON: ${typeof value}`);
}

function hostReplaySha256(message: unknown): string {
  const hash = createHash("sha256");
  hash.update(`${HOST_REPLAY_SCHEMA}\0`, "utf8");
  updateReplayHash(hash, stableObservedMessage(message));
  return hash.digest("hex");
}

function messageText(message: AgentMessage): string {
  const content = contentOf(message);
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return canonicalJson(message);
  const text: string[] = [];
  for (const part of content) {
    if (isRecord(part) && part.type === "text" && typeof part.text === "string") {
      text.push(part.text);
    }
  }
  return text.join("\\n");
}

function messageRole(message: AgentMessage): string {
  return stringField(message, "role") ?? "custom";
}

function toolCallId(message: AgentMessage): string | undefined {
  const direct = stringField(message, "toolCallId");
  if (direct) return direct;
  const content = contentOf(message);
  if (!Array.isArray(content)) return undefined;
  for (const part of content) {
    if (isRecord(part) && part.type === "toolCall" && typeof part.id === "string") {
      return part.id;
    }
  }
  return undefined;
}

function authenticatedScope(current: BranchScope): AuthenticatedHostScope {
  return {
    profile_id: current.profileId,
    project_id: current.projectId,
    session_id: current.sessionId,
    branch_id: current.branchId,
    task_scope: current.taskScope,
  };
}

function latestUserMessage(entries: SessionMessageEntry[]): AgentMessage | undefined {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (messageRole(entries[index].message) === "user") return entries[index].message;
  }
  return undefined;
}

function contextMessages(event: unknown): AgentMessage[] {
  if (!isRecord(event) || !Array.isArray(event.messages) || !event.messages.every(isAgentMessage)) {
    throw new CassiPiOwnerError("INVALID_HOST_EVENT", "context event messages are invalid", 500);
  }
  return event.messages;
}

interface ToolLifecycle {
  toolCallId: string;
  toolName: string;
  input: unknown;
  isError: boolean;
  approved: boolean | undefined;
}

function toolLifecycle(event: unknown): ToolLifecycle {
  if (!isRecord(event) || typeof event.toolCallId !== "string") {
    throw new CassiPiOwnerError("INVALID_HOST_EVENT", "tool lifecycle event is invalid", 500);
  }
  return {
    toolCallId: event.toolCallId,
    toolName: typeof event.toolName === "string" ? event.toolName : "unknown",
    input: event.input ?? event.args ?? null,
    isError: event.isError === true,
    approved: typeof event.approved === "boolean" ? event.approved : undefined,
  };
}

function providerPayload(event: unknown): unknown {
  if (!isRecord(event) || !("payload" in event)) {
    throw new CassiPiOwnerError("INVALID_HOST_EVENT", "provider request event is invalid", 500);
  }
  return event.payload;
}

function lastUserIndex(messages: AgentMessage[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messageRole(messages[index]) === "user") return index;
  }
  return 0;
}


function abortSignal(event: unknown): AbortSignal | undefined {
  if (!isRecord(event) || !(event.signal instanceof AbortSignal)) return undefined;
  return event.signal;
}

function agentMessages(value: unknown, label: string): AgentMessage[] {
  if (!Array.isArray(value) || !value.every(isAgentMessage)) {
    throw new CassiPiOwnerError("INVALID_HOST_EVENT", `${label} contains invalid messages`, 409);
  }
  return value;
}

function messagesFromEntries(value: unknown, label: string): AgentMessage[] {
  if (!Array.isArray(value)) {
    throw new CassiPiOwnerError("INVALID_HOST_EVENT", `${label} is not an entry list`, 409);
  }
  const result: AgentMessage[] = [];
  for (const item of value) {
    if (!isRecord(item) || typeof item.type !== "string") {
      throw new CassiPiOwnerError("INVALID_HOST_EVENT", `${label} contains an invalid entry`, 409);
    }
    if (item.type === "message") {
      if (!isAgentMessage(item.message)) {
        throw new CassiPiOwnerError("INVALID_HOST_EVENT", `${label} contains an invalid message entry`, 409);
      }
      result.push(item.message);
    }
  }
  return result;
}

function compactionPreparation(event: unknown): Record<string, unknown> {
  if (!isRecord(event) || !isRecord(event.preparation)) {
    throw new CassiPiOwnerError("INVALID_HOST_EVENT", "compaction preparation is missing", 409);
  }
  return event.preparation;
}

function stringCollection(value: unknown): string[] {
  const items = value instanceof Set ? [...value] : Array.isArray(value) ? value : [];
  return items.filter((item): item is string => typeof item === "string").sort();
}

function compactionFileDetails(preparation: Record<string, unknown>): {
  readFiles: string[];
  modifiedFiles: string[];
} {
  const fileOps = isRecord(preparation.fileOps) ? preparation.fileOps : {};
  return {
    readFiles: stringCollection(fileOps.read),
    modifiedFiles: [...new Set([...stringCollection(fileOps.written), ...stringCollection(fileOps.edited)])].sort(),
  };
}

function compactionTokenBudget(context: ExtensionContext, preparation: Record<string, unknown>): number {
  const contextWindow = context.model?.contextWindow;
  if (!contextWindow || contextWindow < 1) {
    throw new CassiPiOwnerError("MODEL_CONTEXT_WINDOW_MISSING", "selected provider model has no usable context window", 409);
  }
  const settings = isRecord(preparation.settings) ? preparation.settings : {};
  const configuredReserve =
    typeof settings.reserveTokens === "number" && Number.isSafeInteger(settings.reserveTokens)
      ? settings.reserveTokens
      : undefined;
  const proportionalReserve = Math.max(1, Math.floor(contextWindow * 0.15));
  let reserve = Math.max(proportionalReserve, configuredReserve ?? 16_384);
  if (
    reserve >= contextWindow
    || (configuredReserve === undefined && reserve >= contextWindow - proportionalReserve)
  ) {
    reserve = proportionalReserve;
  }
  return Math.max(1, Math.min(Math.floor(0.8 * reserve), 4096));
}
function exactTimestamp(value: number | string | undefined): string {
  if (typeof value === "number" && Number.isFinite(value)) return new Date(value).toISOString();
  if (typeof value === "string" && value.length > 0) return value;
  return "1970-01-01T00:00:00.000Z";
}

function errorWithCode(error: unknown): Error {
  if (error instanceof CassiPiOwnerError) return error;
  return new CassiPiOwnerError(
    "HOST_ADAPTER_FAILED",
    error instanceof Error ? error.message : String(error),
    500,
  );
}

function ownerMarker(entry: SessionMessageEntry | SessionOtherEntry): OwnerMarker | undefined {
  if (entry.type !== "custom" || entry.customType !== "context_owner_binding") return undefined;
  if (!isRecord(entry.data)) {
    throw new CassiPiOwnerError("HOST_BINDING_INVALID", "persisted owner binding is malformed", 409);
  }
  try {
    const binding = decodeHostOperationBinding(entry.data);
    const targetLeafValue = entry.data.targetLeafId;
    if (targetLeafValue !== null && typeof targetLeafValue !== "string") {
      throw new TypeError("targetLeafId is invalid");
    }
    const targetSessionId = requiredString(entry.data.targetSessionId, "targetSessionId");
    return {
      entryId: entry.id,
      binding,
      committedEntryId:
        typeof entry.data.committedEntryId === "string" ? entry.data.committedEntryId : entry.id,
      operationKind: requiredString(entry.data.operationKind, "operationKind"),
      targetLeafId: targetLeafValue,
      targetSessionId,
    };
  } catch (error) {
    throw new CassiPiOwnerError(
      "HOST_BINDING_INVALID",
      error instanceof Error ? error.message : "persisted owner binding is malformed",
      409,
    );
  }
}

function boundHeadForTreeTarget(
  entries: Array<SessionMessageEntry | SessionOtherEntry>,
  targetId: string,
  sessionId: string,
): string | undefined {
  let headId: string | undefined;
  for (const entry of entries) {
    const marker = ownerMarker(entry);
    if (
      marker
      && marker.binding.sourceSessionId === sessionId
      && marker.binding.sourceLeafId === targetId
      && marker.targetSessionId === sessionId
    ) {
      headId = marker.binding.headId;
      continue;
    }
    const isTarget = entry.id === targetId;
    const isTargetChild = entry.parentId === targetId;
    if (
      marker
      && (marker.operationKind === "compact" || marker.operationKind === "handoff")
      && marker.targetSessionId === sessionId
      && (isTarget || (isTargetChild && marker.targetLeafId === targetId))
    ) {
      headId = marker.binding.headId;
    }
  }
  return headId;
}

function treeTargetLineage(
  entries: Array<SessionMessageEntry | SessionOtherEntry>,
  targetId: string,
): string[] {
  const byId = new Map(entries.map(entry => [entry.id, entry]));
  const lineage: string[] = [];
  const seen = new Set<string>();
  let current: string | null | undefined = targetId;
  while (current && !seen.has(current)) {
    seen.add(current);
    lineage.push(current);
    const parentId: unknown = byId.get(current)?.parentId;
    current = typeof parentId === "string" ? parentId : null;
  }
  return lineage;
}
async function readTargetSession(sessionFile: string): Promise<TargetSessionSnapshot> {
  const file = await stat(sessionFile);
  if (!file.isFile() || file.size > MAX_SESSION_FILE_BYTES) {
    throw new CassiPiOwnerError("TARGET_SESSION_INVALID", "target session file is unavailable or too large", 409);
  }
  const body = await readFile(sessionFile, "utf8");
  if (Buffer.byteLength(body, "utf8") > MAX_SESSION_FILE_BYTES) {
    throw new CassiPiOwnerError("TARGET_SESSION_INVALID", "target session file grew beyond the supported size", 409);
  }
  let sessionId: string | undefined;
  let latestEntryId: string | null = null;
  let ownerHeadId: string | null = null;
  for (const line of body.split(/\r?\n/u)) {
    if (!line.trim()) continue;
    let decoded: unknown;
    try {
      decoded = JSON.parse(line);
    } catch {
      throw new CassiPiOwnerError("TARGET_SESSION_INVALID", "target session contains invalid JSON", 409);
    }
    if (!isRecord(decoded)) {
      throw new CassiPiOwnerError("TARGET_SESSION_INVALID", "target session contains a non-object entry", 409);
    }
    if (decoded.type === "session") {
      sessionId = requiredString(decoded.id, "target session id");
      continue;
    }
    if (typeof decoded.id === "string") latestEntryId = decoded.id;
    if (
      decoded.type === "custom"
      && decoded.customType === "context_owner_binding"
      && typeof decoded.id === "string"
    ) {
      const marker = ownerMarker({
        id: decoded.id,
        type: "custom",
        customType: "context_owner_binding",
        data: decoded.data,
      });
      if (marker) ownerHeadId = marker.binding.headId;
    }
  }
  if (!sessionId) throw new CassiPiOwnerError("TARGET_SESSION_INVALID", "target session header is missing", 409);
  return { latestEntryId, ownerHeadId, sessionId };
}


export function createCassiPiExtension(options: CassiPiExtensionOptions = {}) {
  const configuredProfileId = options.profileId ?? process.env.CASSIPI_PROFILE_ID;
  if (!configuredProfileId) {
    throw new CassiPiOwnerError(
      "PROFILE_ID_MISSING",
      "CASSIPI_PROFILE_ID is required for an owned profile",
      503,
    );
  }
  const profileId = configuredProfileId;
  const client: OwnerClient = options.client ?? new CassiPiWorkerClient(options);
  const outputReserveTokens = options.outputReserveTokens ?? Number(process.env.CASSIPI_OUTPUT_RESERVE_TOKENS ?? 8192);
  if (!Number.isSafeInteger(outputReserveTokens) || outputReserveTokens < 1) {
    throw new CassiPiOwnerError("INVALID_CONFIGURATION", "output reserve must be a positive integer", 500);
  }
  const maxEvidenceTokens = options.maxEvidenceTokens ?? Number(process.env.CASSIPI_MAX_EVIDENCE_TOKENS ?? 16_384);
  if (!Number.isSafeInteger(maxEvidenceTokens) || maxEvidenceTokens < 1) {
    throw new CassiPiOwnerError("INVALID_CONFIGURATION", "evidence budget must be a positive integer", 500);
  }
  const cursors = new Map<string, Cursor>();
  const branchIds = new Map<string, string>();
  const pendingLifecycle = new Map<string, PendingLifecycle>();
  const importPreviews = new Map<string, Json>();
  let pendingProjection: HostProjectionBinding | undefined;
  let lastProjectionReceipt: Record<string, Json> | undefined;
  let providerTurnSelection: ProviderTurnSelection | undefined;
  const memoryObservedTimestamps = new Map<string, string>();
  let queue: Promise<void> = Promise.resolve();

  const serialize = <T>(work: () => Promise<T>): Promise<T> => {
    const result = queue.then(work, work);
    queue = result.then(() => undefined, () => undefined);
    return result;
  };

  async function projectIdentity(cwd: string): Promise<string> {
    const canonical = await realpath(resolve(cwd)).catch(() => resolve(cwd));
    return `project:${sha256(process.platform === "win32" ? canonical.toLowerCase() : canonical)}`;
  }

  function branchId(context: ExtensionContext): string {
    const sessionId = context.sessionManager.getSessionId();
    let value = branchIds.get(sessionId);
    if (!value) {
      value = `branch:${sha256(`root:${sessionId}`)}`;
      branchIds.set(sessionId, value);
    }
    return value;
  }

  function branchEntries(context: ExtensionContext): SessionMessageEntry[] {
    return context.sessionManager
      .getBranch()
      .filter((entry): entry is SessionMessageEntry => entry.type === "message" && "message" in entry);
  }

  function ancestralUserEntryId(context: ExtensionContext): string | undefined {
    const entries = context.sessionManager.getEntries();
    const byId = new Map(entries.map(entry => [entry.id, entry]));
    const seen = new Set<string>();
    let current = context.sessionManager.getLeafId();
    while (current && !seen.has(current)) {
      seen.add(current);
      const entry = byId.get(current);
      if (!entry) return undefined;
      if (
        entry.type === "message"
        && "message" in entry
        && isAgentMessage(entry.message)
        && messageRole(entry.message) === "user"
      ) {
        return entry.id;
      }
      current = typeof entry.parentId === "string" ? entry.parentId : null;
    }
    return undefined;
  }

  async function scope(context: ExtensionContext): Promise<BranchScope> {
    const sessionId = context.sessionManager.getSessionId();
    const taskScope = ancestralUserEntryId(context)
      ?? context.sessionManager.getLeafId()
      ?? sessionId;
    const currentBranch = branchId(context);
    return {
      profileId,
      projectId: await projectIdentity(context.cwd),
      sessionId,
      branchId: currentBranch,
      taskScope,
      producerId: `omp:${sha256(`${sessionId}:${currentBranch}`)}`,
    };
  }

  async function cursorFor(current: BranchScope, refresh = false): Promise<Cursor> {
    const key = `${current.sessionId}\0${current.branchId}`;
    const cached = cursors.get(key);
    if (cached && !refresh) return cached;
    const response = decodeSourceBindings(
      await client.owner(
        "bindings",
        {
          schema: "cassipi.host-bindings.v1",
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          producer_id: current.producerId,
        },
        undefined,
        authenticatedScope(current),
      ),
    );
    const ordered = [...response.bindings].sort(
      (left, right) => left.producer_sequence - right.producer_sequence,
    );
    const revisionsByNativeAndContent = new Map<string, string>();
    const revisionByNative = new Map<string, string>();
    const revisionsByNativeAndReplay = new Map<string, string>();
    const provisionalByToolStage = new Map<
      string,
      { eventId: string; revisionIds: string[] }
    >();
    for (const row of ordered) {
      if (row.native_entry_id) {
        for (const source of row.sources) {
          revisionsByNativeAndContent.set(
            `${row.native_entry_id}\0${source.content_sha256}`,
            source.revision_id,
          );
          const replayHash = source.metadata.host_replay_sha256;
          const replayFields = source.metadata.host_replay_volatile_fields;
          if (
            source.metadata.host_replay_schema === HOST_REPLAY_SCHEMA
            && typeof replayHash === "string"
            && /^[0-9a-f]{64}$/.test(replayHash)
            && Array.isArray(replayFields)
            && replayFields.length === HOST_REPLAY_VOLATILE_FIELDS.length
            && replayFields.every((field, index) => field === HOST_REPLAY_VOLATILE_FIELDS[index])
          ) {
            revisionsByNativeAndReplay.set(
              `${row.native_entry_id}\0${replayHash}`,
              source.revision_id,
            );
          }
          revisionByNative.set(row.native_entry_id, source.revision_id);
        }
      }
      if (
        row.tool_call_id
        && row.native_entry_id?.startsWith("tool:")
        && (
          row.event_kind === "action-proposal"
          || row.event_kind === "action-start"
          || row.event_kind === "action-outcome"
        )
      ) {
        provisionalByToolStage.set(`${row.tool_call_id}\0${row.event_kind}`, {
          eventId: row.event_id,
          revisionIds: row.sources.map(source => source.revision_id),
        });
      }
    }
    const latest = ordered.at(-1);
    const result: Cursor = {
      lastEventId: latest?.event_id ?? null,
      nextSequence: (latest?.producer_sequence ?? -1) + 1,
      revisionsByNativeAndContent,
      revisionByNative,
      revisionsByNativeAndReplay,
      provisionalByToolStage,
    };
    cursors.set(key, result);
    return result;
  }

  async function captureStatus(current: BranchScope) {
    return decodeCaptureStatus(
      await client.owner(
        "capture_status",
        {
          schema: "cassipi.capture-status.v1",
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
        },
        undefined,
        authenticatedScope(current),
      ),
    );
  }

  async function setCaptureStatus(current: BranchScope, paused: boolean) {
    return decodeCaptureStatus(
      await client.owner(
        "capture_set",
        {
          schema: "cassipi.capture-set.v1",
          operation_id: `capture:${paused ? "pause" : "resume"}:${randomUUID()}`,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
          paused,
        },
        undefined,
        authenticatedScope(current),
      ),
    );
  }

  async function observe(
    context: ExtensionContext,
    current: BranchScope,
    nativeEntryId: string,
    message: unknown,
    eventKind: string,
    claimCategory: string,
    timestamp: string,
    payload: Record<string, Json>,
    actionId?: string,
    provisionalObservationId?: string,
  ): Promise<void> {
    const encoded = canonicalJson(message);
    const contentHash = sha256(encoded);
    const replayHash = hostReplaySha256(message);
    const cursor = await cursorFor(current);
    const activeRevision = cursor.revisionByNative.get(nativeEntryId);
    const known = cursor.revisionsByNativeAndContent.get(`${nativeEntryId}\0${contentHash}`);
    if (known && known === activeRevision) return;
    const replayed = cursor.revisionsByNativeAndReplay.get(`${nativeEntryId}\0${replayHash}`);
    if (replayed && replayed === activeRevision) {
      cursor.revisionsByNativeAndContent.set(`${nativeEntryId}\0${contentHash}`, replayed);
      return;
    }
    const status = await client.status();
    const nativeIdentity = `${nativeEntryId}:${contentHash}:${eventKind}`;
    const result = decodeObservedResult(
      await client.owner(
        "observe",
        {
          schema: "cassipi.observe.v1",
          operation_id: `observe:${sha256(`${current.producerId}:${nativeIdentity}`)}`,
          native_identity: nativeIdentity,
          producer_id: current.producerId,
          producer_sequence: cursor.nextSequence,
          predecessor_event_id: cursor.lastEventId,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
          parent_head_id: status.field_head_sha256,
          event_kind: eventKind,
          source: {
            source_id: `omp:${current.sessionId}:${nativeEntryId}`,
            content_base64: Buffer.from(encoded, "utf8").toString("base64"),
            content_sha256: contentHash,
            mime_type: "application/vnd.omp.event+json",
            codec: "utf-8",
            host_replay_schema: HOST_REPLAY_SCHEMA,
            host_replay_sha256: replayHash,
            host_replay_volatile_fields: [...HOST_REPLAY_VOLATILE_FIELDS],
            profile_id: current.profileId,
            project_id: current.projectId,
            session_id: current.sessionId,
            branch_id: current.branchId,
            task_scope: current.taskScope,
            native_source_entry_id: nativeEntryId,
            author_origin: "omp-host",
            message_role: isAgentMessage(message)
              ? messageRole(message)
              : eventKind === "action-outcome"
                ? "toolResult"
                : "custom",
            observed_timestamp: timestamp,
            claim_category: claimCategory,
            parent_revision_id: activeRevision ?? null,
            fidelity: "exact-observed-bytes",
            ...(actionId ? { action_id: actionId } : {}),
          },
          payload,
          native_entry_id: nativeEntryId,
          ...(actionId ? { tool_call_id: actionId } : {}),
          ...(provisionalObservationId
            ? { provisional_observation_id: provisionalObservationId }
            : {}),
        },
        undefined,
        authenticatedScope(current),
      ),
    );
    cursor.lastEventId = result.event_id;
    cursor.nextSequence += 1;
    cursor.revisionsByNativeAndContent.set(
      `${nativeEntryId}\0${contentHash}`,
      result.source.revision_id,
    );
    cursor.revisionsByNativeAndReplay.set(
      `${nativeEntryId}\0${replayHash}`,
      result.source.revision_id,
    );
    cursor.revisionByNative.set(nativeEntryId, result.source.revision_id);
  }

  async function syncBranch(
    context: ExtensionContext,
  ): Promise<{
    current: BranchScope;
    revisions: Map<string, string>;
    entries: SessionMessageEntry[];
    paused: boolean;
  }> {
    await client.connect();
    const entries = branchEntries(context);
    const current = await scope(context);
    const cursor = await cursorFor(current, true);
    const capture = await captureStatus(current);
    if (capture.paused) {
      return { current, revisions: cursor.revisionsByNativeAndContent, entries, paused: true };
    }
    let activeTask = current.taskScope;
    for (const entry of entries) {
      if (messageRole(entry.message) === "user") activeTask = entry.id;
      const entryScope = { ...current, taskScope: activeTask };
      const role = messageRole(entry.message);
      const actionId = toolCallId(entry.message);
      const kind = role === "toolResult" ? "action-outcome" : "observation";
      const claim =
        role === "user"
          ? "user-instruction"
          : role === "assistant"
            ? "assistant-claim"
            : role === "toolResult"
              ? "action-outcome"
              : "tool-observation";
      const provisionalOutcome =
        kind === "action-outcome" && actionId
          ? cursor.provisionalByToolStage.get(`${actionId}\0action-outcome`)
          : undefined;
      const observedKind = provisionalOutcome ? "host-binding" : kind;
      const payload: Record<string, Json> = {
        memory_scope: "branch",
        message_role: role,
        ...(actionId ? { action_id: actionId } : {}),
        ...(provisionalOutcome
          ? {
              binding_kind: "provisional-observation",
              provisional_event_id: provisionalOutcome.eventId,
              provisional_revision_ids: provisionalOutcome.revisionIds,
            }
          : {}),
      };
      if (kind === "action-outcome") {
        payload.action_text = actionId ?? "unknown tool action";
        payload.task_text = messageText(latestUserMessage(entries) ?? entry.message);
        payload.outcome_status =
          booleanField(entry.message, "isError") === true ? "failed" : "succeeded";
      }
      await observe(
        context,
        entryScope,
        entry.id,
        entry.message,
        observedKind,
        claim,
        exactTimestamp(entry.timestamp),
        payload,
        actionId,
        provisionalOutcome?.eventId,
      );
    }
    return {
      current: await scope(context),
      revisions: cursor.revisionsByNativeAndContent,
      entries,
      paused: false,
    };
  }

  function protectedMessages(messages: AgentMessage[]): AgentMessage[] {
    if (messages.length === 0) return [];
    const start = lastUserIndex(messages);
    return messages.slice(start);
  }

  function binding(
    context: ExtensionContext,
    status: OwnerStatus,
    operationId: string,
    sourceRootDigest = status.source_root_digest,
    coveredThroughEntryId: string | null = context.sessionManager.getLeafId(),
  ): HostOperationBinding {
    return {
      ownerId: OWNER_ID,
      apiVersion: OWNER_API_VERSION,
      operationId,
      sourceSessionId: context.sessionManager.getSessionId(),
      sourceLeafId: context.sessionManager.getLeafId(),
      headId: status.field_head_sha256,
      checkpointId: status.checkpoint_id,
      checkpointHash: status.checkpoint_hash,
      sourceRootDigest,
      coveredThroughEntryId,
      revocationEpoch: status.revocation_epoch,
    };
  }

  async function prepareLifecycle(
    context: ExtensionContext,
    operationKind: string,
    reason: string,
    sourceRootDigest: string,
    projectionId: string | null,
    signal?: AbortSignal,
    targetHeadId?: string,
  ): Promise<HostOperationBinding> {
    const synced = await syncBranch(context);
    const status = await client.status();
    const sourceLeafId = context.sessionManager.getLeafId();
    const operationId = `${operationKind}:${sha256(
      canonicalJson({
        head: status.field_head_sha256,
        projection: projectionId,
        reason,
        sourceLeafId,
        sourceRootDigest,
        sourceSessionId: synced.current.sessionId,
        targetHeadId: targetHeadId ?? status.field_head_sha256,
      }),
    )}`;
    const prepared = decodeLifecyclePrepare(
      await client.owner(
        "lifecycle_prepare",
        {
          schema: "cassipi.lifecycle-prepare.v1",
          operation_id: operationId,
          profile_id: synced.current.profileId,
          project_id: synced.current.projectId,
          session_id: synced.current.sessionId,
          branch_id: synced.current.branchId,
          task_scope: synced.current.taskScope,
          parent_head_id: status.field_head_sha256,
          checkpoint_id: status.checkpoint_id,
          checkpoint_hash: status.checkpoint_hash,
          revocation_epoch: status.revocation_epoch,
          operation_kind: operationKind,
          source_session_id: synced.current.sessionId,
          source_leaf_id: sourceLeafId,
          covered_through_entry_id: sourceLeafId,
          source_root_digest: sourceRootDigest,
          target_head_id: targetHeadId ?? status.field_head_sha256,
        },
        signal,
        authenticatedScope(synced.current),
      ),
    );
    pendingLifecycle.set(operationId, { binding: prepared.binding, operationKind });
    return prepared.binding;
  }

  function markers(context: ExtensionContext): OwnerMarker[] {
    const result: OwnerMarker[] = [];
    for (const entry of context.sessionManager.getEntries()) {
      const marker = ownerMarker(entry);
      if (marker) result.push(marker);
    }
    return result;
  }

  async function commitLifecycle(context: ExtensionContext, pending: PendingLifecycle): Promise<void> {
    const marker = markers(context).find(row => row.binding.operationId === pending.binding.operationId);
    if (!marker || marker.operationKind !== pending.operationKind) {
      throw new CassiPiOwnerError(
        "HOST_BINDING_MISSING",
        `native ${pending.operationKind} commit has no matching owner receipt`,
        409,
      );
    }
    const current = await scope(context);
    const result = decodeLifecycleCommit(
      await client.owner(
        "lifecycle_commit",
        {
          schema: "cassipi.lifecycle-commit.v1",
          operation_id: pending.binding.operationId,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
          committed_entry_id: marker.committedEntryId,
          old_leaf_id: marker.binding.sourceLeafId,
          new_leaf_id: marker.targetLeafId,
          owner_marker_entry_id: marker.entryId,
          binding: pending.binding,
        },
        undefined,
        authenticatedScope(current),
      ),
    );
    pendingLifecycle.delete(pending.binding.operationId);
    if (pending.operationKind !== "compact" && pending.operationKind !== "handoff") {
      branchIds.set(
        marker.targetSessionId,
        `branch:${sha256(`${marker.targetSessionId}:${marker.targetLeafId ?? "root"}:${result.active_head_id}`)}`,
      );
    }
  }

  async function cancelLifecycle(
    context: ExtensionContext,
    pending: PendingLifecycle,
    reason: string,
  ): Promise<void> {
    const current = await scope(context);
    decodeLifecycleCancel(
      await client.owner(
        "lifecycle_cancel",
        {
          schema: "cassipi.lifecycle-cancel.v1",
          operation_id: pending.binding.operationId,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
          reason,
        },
        undefined,
        authenticatedScope(current),
      ),
    );
    pendingLifecycle.delete(pending.binding.operationId);
  }

  function pendingForKind(operationKind: string): PendingLifecycle {
    const matches = [...pendingLifecycle.values()].filter(row => row.operationKind === operationKind);
    if (matches.length !== 1) {
      throw new CassiPiOwnerError(
        "LIFECYCLE_PREPARATION_MISSING",
        `native ${operationKind} commit does not match one prepared owner operation`,
        409,
      );
    }
    return matches[0];
  }

  async function reconcileLifecycle(context: ExtensionContext): Promise<void> {
    await client.connect();
    const current = await scope(context);
    const pending = decodeLifecyclePending(
      await client.owner(
        "lifecycle_pending",
        {
          schema: "cassipi.lifecycle-pending.v1",
          profile_id: current.profileId,
          project_id: current.projectId,
        },
        undefined,
        authenticatedScope(current),
      ),
    );
    const persisted = markers(context);
    for (const row of pending.pending) {
      const local: PendingLifecycle = {
        binding: row.binding,
        operationKind: row.operation_kind,
      };
      pendingLifecycle.set(row.binding.operationId, local);
      const marker = persisted.find(item => item.binding.operationId === row.binding.operationId);
      if (marker) {
        await commitLifecycle(context, local);
      } else if (
        row.binding.sourceSessionId === context.sessionManager.getSessionId()
        && (row.operation_kind === "compact" || row.operation_kind === "handoff")
      ) {
        await cancelLifecycle(context, local, "native host has no committed owner marker after restart");
      }
    }
  }

  async function recordToolLifecycle(event: unknown, context: ExtensionContext, eventKind: string): Promise<void> {
    const lifecycle = toolLifecycle(event);
    await serialize(async () => {
      const entries = branchEntries(context);
      const current = await scope(context);
      if ((await captureStatus(current)).paused) return;
      const outcome =
        eventKind === "action-outcome" && (lifecycle.isError || lifecycle.approved === false)
          ? "failed"
          : eventKind === "action-outcome"
            ? "succeeded"
            : "pending";
      const taskMessage = latestUserMessage(entries);
      const eventIdentity = sha256(canonicalJson(event));
      await observe(
        context,
        current,
        `tool:${lifecycle.toolCallId}:${eventKind}:${eventIdentity}`,
        event,
        eventKind,
        eventKind === "action-proposal"
          ? "action-proposal"
          : eventKind === "action-outcome"
            ? "action-outcome"
            : "tool-observation",
        "1970-01-01T00:00:00.000Z",
        {
          memory_scope: "branch",
          action_id: lifecycle.toolCallId,
          action_text: canonicalJson({ toolName: lifecycle.toolName, input: lifecycle.input }),
          task_text: taskMessage ? messageText(taskMessage) : "",
          outcome_status: outcome,
        },
        lifecycle.toolCallId,
      );
    });
  }
  async function projectMessages(
    context: ExtensionContext,
    inputMessages: AgentMessage[],
    options: ProjectMessagesOptions = {},
  ): Promise<ProjectMessagesResult> {
    const model = context.model;
    if (!model) throw new CassiPiOwnerError("MODEL_MISSING", "no provider model is selected", 409);
    const modelContextWindow = model.contextWindow;
    if (!modelContextWindow || modelContextWindow < 1) {
      throw new CassiPiOwnerError(
        "MODEL_CONTEXT_WINDOW_MISSING",
        "selected provider model has no usable context window",
        409,
      );
    }
    if (
      options.tokenBudget !== undefined
      && (!Number.isSafeInteger(options.tokenBudget) || options.tokenBudget < 1)
    ) {
      throw new CassiPiOwnerError("INVALID_TOKEN_BUDGET", "projection token budget must be a positive integer", 409);
    }
    const synced = await syncBranch(context);
    const status = await client.status();
    const protectedNative =
      options.protectedNative ?? (synced.paused ? inputMessages : protectedMessages(inputMessages));
    const protectedHashes = new Set(protectedNative.map(message => sha256(canonicalJson(message))));
    const excludedRevisionIds = [...synced.revisions.entries()]
      .filter(([key]) => protectedHashes.has(key.slice(key.indexOf("\0") + 1)))
      .map(([, revision]) => revision);
    const taskMessage = latestUserMessage(
      inputMessages.map((message, index) => ({ id: `context:${index}`, type: "message", message })),
    );
    const task = taskMessage ? messageText(taskMessage) : "continue current task";
    const revision = sha256(canonicalJson(inputMessages));
    const purpose = options.purpose ?? "provider";
    const providerOperationId = `${purpose}:${sha256(`${synced.current.sessionId}:${context.sessionManager.getLeafId() ?? "root"}:${revision}:${status.field_head_sha256}:${model.provider}:${model.id}`)}`;
    const tokenizer = new Tokenizer(model);
    const tokenizerId =
      tokenizer.encoding === null
        ? process.env.PI_TOKENIZER_ACCURATE === "1"
          ? "omp:o200k-fallback"
          : "omp:byte-estimate"
        : `omp:${tokenizer.encoding}`;
    const scopeRequest = {
      profile_id: synced.current.profileId,
      project_id: synced.current.projectId,
      session_id: synced.current.sessionId,
      branch_id: synced.current.branchId,
      task_scope: synced.current.taskScope,
      task: options.query?.trim() || task || "continue current task",
      expected_head_id: status.field_head_sha256,
      expected_journal_head_sha256: status.journal_head_sha256,
      expected_revocation_epoch: status.revocation_epoch,
      input_revision_sha256: revision,
      provider_call_id: providerOperationId,
      model_id: `${model.provider}:${model.id}`,
      tokenizer_id: tokenizerId,
      allowed_memory_scopes: options.allowedMemoryScopes ?? ["branch", "task"],
      mandatory_revision_ids: options.mandatoryRevisionIds ?? [],
      excluded_revision_ids: [...new Set(excludedRevisionIds)].sort(),
    };
    const inventory = decodeProjectionInventory(
      await client.owner(
        "projection_inventory",
        scopeRequest,
        options.signal,
        authenticatedScope(synced.current),
      ),
    );
    const tokenCounts: Record<string, number> = {};
    for (const candidate of inventory.candidates) {
      for (const representation of candidate.representations) {
        tokenCounts[representation.action_id] = tokenizer.countMessage(
          asEvidenceMessage(representation.message.content, model),
        );
      }
    }
    const protectedTokens = tokenizer.countMessages(protectedNative);
    const currentTokens = tokenizer.countMessages(inputMessages);
    const usage = context.getContextUsage();
    const explicitBudget = options.tokenBudget;
    const contextWindow = explicitBudget === undefined
      ? modelContextWindow
      : Math.min(modelContextWindow, explicitBudget);
    const hostOverhead = explicitBudget === undefined
      ? Math.max(0, (usage?.tokens ?? currentTokens) - currentTokens)
      : 0;
    const reserve = explicitBudget === undefined
      ? Math.min(
          outputReserveTokens,
          model.maxTokens ?? outputReserveTokens,
          Math.floor(contextWindow / 2),
        )
      : 0;
    const projectionContextWindow = explicitBudget === undefined
      ? Math.min(contextWindow, protectedTokens + hostOverhead + reserve + maxEvidenceTokens)
      : contextWindow;
    const providerTurnKey =
      !synced.paused
      && purpose === "provider"
      && options.allowedMemoryScopes === undefined
      && options.mandatoryRevisionIds === undefined
      && options.protectedNative === undefined
      && options.query === undefined
      && options.tokenBudget === undefined
        ? sha256(canonicalJson({
            profile_id: synced.current.profileId,
            project_id: synced.current.projectId,
            session_id: synced.current.sessionId,
            branch_id: synced.current.branchId,
            task_scope: synced.current.taskScope,
            task_message_sha256: taskMessage ? sha256(canonicalJson(taskMessage)) : null,
            revocation_epoch: status.revocation_epoch,
            model_id: `${model.provider}:${model.id}`,
            tokenizer_id: tokenizerId,
            context_window_tokens: contextWindow,
            output_reserve_tokens: reserve,
            max_evidence_tokens: maxEvidenceTokens,
          }))
        : undefined;
    const reusableSelection =
      providerTurnKey !== undefined
      && providerTurnSelection?.key === providerTurnKey
      && providerTurnSelection.contentHashes.every(hash => !protectedHashes.has(hash))
        ? providerTurnSelection
        : undefined;
    if (providerTurnKey !== undefined && providerTurnSelection !== undefined && reusableSelection === undefined) {
      providerTurnSelection = undefined;
    }
    const projected = decodeProjectionResult(
      await client.owner(
        "project",
        {
          schema: "cassipi.projection.v1",
          scope: scopeRequest,
          inventory_sha256: inventory.inventory_sha256,
          budget: {
            schema: "cassipi.projection-budget.v1",
            context_window_tokens: projectionContextWindow,
            system_tokens: 0,
            tool_schema_tokens: 0,
            protected_tokens: protectedTokens,
            image_tokens: 0,
            current_request_tokens: 0,
            reserved_output_tokens: reserve,
            host_overhead_tokens: hostOverhead,
          },
          token_counts: tokenCounts,
          ...(reusableSelection ? { frozen_action_ids: reusableSelection.actionIds } : {}),
        },
        options.signal,
        authenticatedScope(synced.current),
      ),
    );
    const evidenceMessages = projected.messages.map(message => asEvidenceMessage(message.content, model));
    const messages: AgentMessage[] = [...evidenceMessages, ...protectedNative];
    const tokenCount = tokenizer.countMessages(messages);
    const tokenBudget = projectionContextWindow - hostOverhead - reserve;
    if (tokenCount > tokenBudget) {
      throw new CassiPiOwnerError(
        "PROJECTION_OVER_BUDGET",
        `projection used ${tokenCount} tokens against budget ${tokenBudget}`,
        409,
      );
    }
    const sourceRootDigest = sha256(canonicalJson(projected.selected.map(row => row.revision_id).sort()));
    if (providerTurnKey !== undefined) {
      providerTurnSelection = {
        key: providerTurnKey,
        actionIds: projected.selected.map(row => row.action_id),
        contentHashes: projected.selected.flatMap(row =>
          typeof row.source.content_sha256 === "string" ? [row.source.content_sha256] : []
        ),
      };
    }
    const projectionBinding: HostProjectionBinding = {
      ...binding(context, status, providerOperationId, sourceRootDigest),
      projectionId: projected.projection_id,
      tokenCount,
      tokenBudget,
    };
    lastProjectionReceipt = {
      projection_id: projected.projection_id,
      status: projected.status,
      selected_count: projected.selected.length,
      source_root_digest: sourceRootDigest,
      token_count: tokenCount,
      token_budget: tokenBudget,
      accounting: {
        context_window_tokens: projected.accounting.context_window_tokens,
        used_tokens: projected.accounting.used_tokens,
        remaining_tokens: projected.accounting.remaining_tokens,
      },
      max_evidence_tokens: explicitBudget === undefined ? maxEvidenceTokens : null,
      turn_selection_reused: reusableSelection !== undefined,
    };
    return {
      messages,
      projection: projected,
      sourceRootDigest,
      binding: projectionBinding,
    };
  }
  async function prepareFieldRewrite(
    context: ExtensionContext,
    operationKind: string,
    messages: AgentMessage[],
    tokenBudget: number,
    reason: string,
    signal?: AbortSignal,
    targetHeadId?: string,
  ): Promise<PreparedRewrite | undefined> {
    const projected = await projectMessages(context, messages, {
      protectedNative: [],
      purpose: operationKind,
      signal,
      tokenBudget,
    });
    if (projected.projection.status !== "ready" || projected.projection.messages.length === 0) {
      return undefined;
    }
    const summary = projected.projection.messages.map(message => message.content).join("\n\n");
    const ownerBinding = await prepareLifecycle(
      context,
      operationKind,
      reason,
      projected.sourceRootDigest,
      projected.projection.projection_id,
      signal,
      targetHeadId,
    );
    const status = await client.status();
    return {
      binding: ownerBinding,
      summary,
      details: {
        cassipi: {
          protocolId: PROTOCOL_ID,
          runtimeId: status.runtime_id,
          closureSha256: status.closure_sha256,
          manifestSha256: status.manifest_sha256,
          operationId: ownerBinding.operationId,
          checkpointHash: ownerBinding.checkpointHash,
          sourceRootDigest: ownerBinding.sourceRootDigest,
          coveredThroughEntryId: ownerBinding.coveredThroughEntryId,
          revocationEpoch: ownerBinding.revocationEpoch,
          projectionId: projected.projection.projection_id,
          selected: projected.projection.selected.map(row => ({
            eventId: row.event_id,
            representation: row.representation,
            revisionId: row.revision_id,
            source: row.source,
          })),
        },
      },
    };
  }
  async function lineageHead(
    context: ExtensionContext,
    mode: "native" | "baseline",
    sessionId: string,
    nativeEntryId: string | null,
    branchId: string | null,
  ): Promise<string | null> {
    const current = await scope(context);
    const projectId = await projectIdentity(context.cwd);
    const targetScope: BranchScope = {
      ...current,
      projectId,
      sessionId,
      branchId: branchId ?? current.branchId,
    };
    const result = decodeLineageLookup(
      await client.owner(
        "lineage_lookup",
        {
          schema: "cassipi.lineage-lookup.v1",
          profile_id: profileId,
          project_id: projectId,
          session_id: sessionId,
          branch_id: branchId,
          mode,
          native_entry_id: nativeEntryId,
        },
        undefined,
        authenticatedScope(targetScope),
      ),
    );
    return result.head_id;
  }

  async function treeOrBranchTargetHead(
    context: ExtensionContext,
    targetId: string,
  ): Promise<string | null> {
    const sessionId = context.sessionManager.getSessionId();
    const entries = context.sessionManager.getEntries();
    const byId = new Map(entries.map(entry => [entry.id, entry]));
    for (const candidateId of treeTargetLineage(entries, targetId)) {
      const bound = boundHeadForTreeTarget(entries, candidateId, sessionId);
      if (bound) return bound;
      const entry = byId.get(candidateId);
      if (!entry || entry.type === "message") {
        const recovered = await lineageHead(context, "native", sessionId, candidateId, null);
        if (recovered) return recovered;
      }
    }
    return null;
  }

  async function switchTargetHead(
    event: unknown,
    context: ExtensionContext,
    operationKind: string,
  ): Promise<string> {
    await syncBranch(context);
    const status = await client.status();
    if (operationKind === "new" || operationKind === "clear") {
      const baseline = await lineageHead(
        context,
        "baseline",
        context.sessionManager.getSessionId(),
        null,
        null,
      );
      if (!baseline) throw new CassiPiOwnerError("LINEAGE_TARGET_MISSING", "field baseline is unavailable", 409);
      return baseline;
    }
    const targetSessionFile = stringField(event, "targetSessionFile");
    if (targetSessionFile) {
      const target = await readTargetSession(targetSessionFile);
      if (target.ownerHeadId) return target.ownerHeadId;
      if (target.latestEntryId) {
        const recovered = await lineageHead(context, "native", target.sessionId, target.latestEntryId, null);
        if (recovered) return recovered;
      }
      const baseline = await lineageHead(context, "baseline", target.sessionId, null, null);
      if (baseline) return baseline;
    }
    return status.field_head_sha256;
  }

  async function prepareTransition(
    context: ExtensionContext,
    operationKind: string,
    reason: string,
    signal?: AbortSignal,
    targetHeadId?: string,
  ): Promise<HostOperationBinding> {
    await syncBranch(context);
    const status = await client.status();
    return prepareLifecycle(
      context,
      operationKind,
      reason,
      status.source_root_digest,
      null,
      signal,
      targetHeadId ?? status.field_head_sha256,
    );
  }



  async function memoryMutation(
    context: ExtensionContext,
    action: "remember" | "correct",
    nativeEntryId: string,
    content: string,
    memoryScope: MemoryScope,
    sourceRefs: string[],
    targetRevisionId: string | undefined,
    signal: AbortSignal | undefined,
  ): Promise<Json> {
    const current = await scope(context);
    await client.connect();
    if ((await captureStatus(current)).paused) {
      throw new CassiPiOwnerError(
        "CAPTURE_PAUSED",
        "CassiPi capture is paused; resume before writing memory",
        409,
      );
    }
    const cursor = await cursorFor(current, true);
    const observedTimestamp =
      memoryObservedTimestamps.get(nativeEntryId) ?? new Date().toISOString();
    memoryObservedTimestamps.set(nativeEntryId, observedTimestamp);
    const status = await client.status();
    const contentBytes = Buffer.from(content, "utf8");
    const contentHash = sha256(contentBytes);
    const request: Record<string, unknown> = {
      schema: action === "remember" ? "cassipi.memory-remember.v1" : "cassipi.memory-correct.v1",
      operation_id: `${action}:${sha256(`${current.sessionId}:${nativeEntryId}:${contentHash}:${memoryScope}:${targetRevisionId ?? ""}`)}`,
      native_identity: nativeEntryId,
      producer_id: current.producerId,
      producer_sequence: cursor.nextSequence,
      predecessor_event_id: cursor.lastEventId,
      profile_id: current.profileId,
      project_id: current.projectId,
      session_id: current.sessionId,
      branch_id: current.branchId,
      task_scope: current.taskScope,
      parent_head_id: status.field_head_sha256,
      source: {
        source_id: `cassi-memory:${current.sessionId}:${nativeEntryId}`,
        content_base64: contentBytes.toString("base64"),
        content_sha256: contentHash,
        mime_type: "text/plain",
        codec: "utf-8",
        profile_id: current.profileId,
        project_id: current.projectId,
        session_id: current.sessionId,
        branch_id: current.branchId,
        task_scope: current.taskScope,
        native_source_entry_id: nativeEntryId,
        author_origin: "omp-cassi-memory-tool",
        message_role: "custom",
        observed_timestamp: observedTimestamp,
        claim_category: "explicit-memory",
        fidelity: "exact-observed-bytes",
      },
      payload: {
        memory_scope: memoryScope,
        declaration_kind: action,
        source_refs: sourceRefs,
      },
      native_entry_id: nativeEntryId,
      ...(targetRevisionId ? { target_revision_id: targetRevisionId } : {}),
    };
    const observed = decodeObservedResult(
      await client.owner(
        action === "remember" ? "memory_remember" : "memory_correct",
        request,
        signal,
        authenticatedScope(current),
      ),
    );
    cursor.lastEventId = observed.event_id;
    cursor.nextSequence += 1;
    cursor.revisionsByNativeAndContent.set(
      `${nativeEntryId}\0${observed.source.content_sha256}`,
      observed.source.revision_id,
    );
    return {
      schema: `cassipi.memory-${action}-result.v1`,
      memory_scope: memoryScope,
      revision_id: observed.source.revision_id,
      content_sha256: observed.source.content_sha256,
      event_id: observed.event_id,
      checkpoint_metadata_sha256: observed.receipt.checkpoint_metadata_sha256,
      ...(targetRevisionId ? { supersedes_revision_id: targetRevisionId } : {}),
    };
  }

  async function forgetPreview(
    context: ExtensionContext,
    targetRevisionId: string,
    memoryScope: MemoryScope,
    signal?: AbortSignal,
  ): Promise<Json> {
    const current = await scope(context);
    const result = await client.owner(
      "forget_preview",
      {
        schema: "cassipi.forget-preview.v1",
        profile_id: current.profileId,
        project_id: current.projectId,
        session_id: current.sessionId,
        branch_id: current.branchId,
        task_scope: current.taskScope,
        memory_scope: memoryScope,
        revision_ids: [targetRevisionId],
      },
      signal,
      authenticatedScope(current),
    );
    if (!isRecord(result) || typeof result.preview_id !== "string" || !Array.isArray(result.matches)) {
      throw new CassiPiOwnerError("INVALID_OWNER_RESPONSE", "forget preview is malformed", 502);
    }
    return result;
  }

  async function memoryRecall(
    context: ExtensionContext,
    query: string,
    exactRef: string | undefined,
    memoryScope: MemoryScope,
    tokenBudget: number,
    signal?: AbortSignal,
  ): Promise<Json> {
    const messages = branchEntries(context).map(entry => entry.message);
    const projected = await projectMessages(context, messages, {
      allowedMemoryScopes: [memoryScope],
      mandatoryRevisionIds: exactRef ? [exactRef] : [],
      protectedNative: [],
      purpose: "memory-recall",
      query,
      signal,
      tokenBudget,
    });
    return {
      schema: "cassipi.memory-recall-result.v1",
      memory_scope: memoryScope,
      projection_id: projected.projection.projection_id,
      status: projected.projection.status,
      source_root_digest: projected.sourceRootDigest,
      accounting: projected.projection.accounting,
      messages: projected.projection.messages,
      selected: projected.projection.selected,
    };
  }

  async function memoryInspect(
    context: ExtensionContext,
    selector: string,
    exactRef: string | undefined,
    memoryScope: MemoryScope,
    signal?: AbortSignal,
  ): Promise<Json> {
    const current = await scope(context);
    if (selector === "state") {
      const status = await client.status();
      const capture = await captureStatus(current);
      return {
        schema: "cassipi.memory-inspect-result.v1",
        selector,
        readiness: "ready",
        scope: {
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
        },
        worker: client.diagnostics?.() ?? {
          schema: "cassipi.worker-diagnostics.v1",
          readiness: "ready",
          recovery: { status: "unreported" },
        },
        state: {
          field_head_sha256: status.field_head_sha256,
          journal_head_sha256: status.journal_head_sha256,
          source_root_digest: status.source_root_digest,
          checkpoint_id: status.checkpoint_id,
          revocation_epoch: status.revocation_epoch,
          protocol_id: status.protocol_id,
          runtime_id: status.runtime_id,
          closure_sha256: status.closure_sha256,
          manifest_sha256: status.manifest_sha256,
          generation_id: status.generation_id,
        },
        capture: {
          schema: capture.schema,
          paused: capture.paused,
          operation_id: capture.operation_id,
          profile_id: capture.profile_id,
          ...(capture.replayed === undefined ? {} : { replayed: capture.replayed }),
        },
        projection: lastProjectionReceipt ?? null,
        current_context_receipt: pendingProjection ? { ...pendingProjection } : null,
      };
    }
    if (selector === "operation") {
      const pending = decodeLifecyclePending(
        await client.owner(
          "lifecycle_pending",
          {
            schema: "cassipi.lifecycle-pending.v1",
            profile_id: current.profileId,
            project_id: current.projectId,
          },
          signal,
          authenticatedScope(current),
        ),
      );
      return {
        schema: "cassipi.memory-inspect-result.v1",
        selector,
        pending: pending.pending.map(row => ({
          event_id: row.event_id,
          operation_kind: row.operation_kind,
          binding: {
            ownerId: row.binding.ownerId,
            apiVersion: row.binding.apiVersion,
            operationId: row.binding.operationId,
            sourceSessionId: row.binding.sourceSessionId,
            sourceLeafId: row.binding.sourceLeafId,
            headId: row.binding.headId,
            checkpointId: row.binding.checkpointId,
            checkpointHash: row.binding.checkpointHash,
            sourceRootDigest: row.binding.sourceRootDigest,
            coveredThroughEntryId: row.binding.coveredThroughEntryId,
            revocationEpoch: row.binding.revocationEpoch,
          },
        })),
      };
    }
    if (selector === "source") {
      if (!exactRef) {
        throw new CassiPiOwnerError(
          "SOURCE_IDENTITY_REQUIRED",
          "source inspection requires an exact revision identity",
          400,
        );
      }
      return {
        schema: "cassipi.memory-inspect-result.v1",
        selector,
        preview: await forgetPreview(context, exactRef, memoryScope, signal),
      };
    }
    return memoryRecall(
      context,
      "inspect the current task-relevant field projection",
      exactRef,
      memoryScope,
      1024,
      signal,
    );
  }

  async function executeMemoryTool(
    toolCallId: string,
    params: unknown,
    signal: AbortSignal | undefined,
    context: ExtensionContext,
  ): Promise<ToolExecutionResult> {
    if (!isRecord(params) || params.schema !== "cassipi.memory-tool.v1") {
      throw new CassiPiOwnerError("INVALID_TOOL_REQUEST", "cassi_memory schema is incompatible", 400);
    }
    const action = requiredString(params.action, "cassi_memory action");
    const memoryScope = memoryScopeField(params);
    if (action === "recall") {
      const query = stringField(params, "query")?.trim();
      const exactRef = stringField(params, "ref")
        ? exactRevisionId(params, "ref")
        : undefined;
      if (!query && !exactRef) {
        throw new CassiPiOwnerError(
          "RECALL_SELECTOR_REQUIRED",
          "recall requires a query or exact revision identity",
          400,
        );
      }
      return toolResult(
        await memoryRecall(
          context,
          query || `recall exact source ${exactRef}`,
          exactRef,
          memoryScope,
          integerField(params, "token_budget") ?? 1024,
          signal,
        ),
      );
    }
    if (action === "remember" || action === "correct") {
      const sourceRefs = stringArrayField(params, "source_refs");
      for (const sourceRef of sourceRefs) {
        exactRevisionId({ source_ref: sourceRef }, "source_ref");
      }
      const target =
        action === "correct" ? exactRevisionId(params, "target_revision_id") : undefined;
      const content =
        action === "correct"
          ? requiredString(params.replacement, "cassi_memory replacement")
          : requiredString(params.content, "cassi_memory content");
      return toolResult(
        await memoryMutation(
          context,
          action,
          `memory-tool:${toolCallId}`,
          content,
          memoryScope,
          sourceRefs,
          target,
          signal,
        ),
      );
    }
    if (action === "forget") {
      const target = exactRevisionId(params, "target_revision_id");
      const preview = await forgetPreview(context, target, memoryScope, signal);
      return toolResult({
        schema: "cassipi.forget-preview-only.v1",
        executed: false,
        preview,
        required_user_action: `/cassi forget ${memoryScope} ${target}`,
        reason: "forget requires direct interactive user approval; tool arguments cannot authorize it",
      });
    }
    if (action === "inspect") {
      const selector = requiredString(params.selector, "cassi_memory selector");
      const exactRef = stringField(params, "ref")
        ? exactRevisionId(params, "ref")
        : undefined;
      return toolResult(await memoryInspect(context, selector, exactRef, memoryScope, signal));
    }
    throw new CassiPiOwnerError("INVALID_TOOL_ACTION", "cassi_memory action is unsupported", 400);
  }

  function notifyJson(
    context: ExtensionContext,
    value: Json,
    type: "info" | "warning" | "error" = "info",
  ): void {
    const encoded = canonicalJson(value);
    const bounded =
      encoded.length <= 16_384
        ? encoded
        : `${encoded.slice(0, 16_300)}\n{"truncated":true}`;
    context.ui.notify(bounded, type);
  }

  function commandScope(value: string): MemoryScope {
    return memoryScopeField({ scope: value });
  }
  async function runTemporalCommand(args: string, context: ExtensionContext): Promise<void> {
    const separator = args.search(/\s/u);
    const command = temporalCommandName(separator < 0 ? args : args.slice(0, separator));
    const payloadText = separator < 0 ? "" : args.slice(separator).trim();
    const spec = TEMPORAL_COMMAND_SPECS[command];
    const payload = temporalCommandPayload(command, payloadText);
    const request: Record<string, unknown> = {
      schema: spec.schema,
      ...payload,
    };
    if (spec.mutation) request.operation_id = `temporal-command:${randomUUID()}`;

    const current = await scope(context);
    const raw = await client.owner(
      spec.operation,
      request,
      undefined,
      authenticatedScope(current),
    );
    let result: Record<string, Json>;
    if (spec.mutation) {
      const mutation = decodeTemporalMutationResult(raw, `temporal ${command} result`);
      if (spec.hostOwnedProposal) {
        assertHostOwnedProposal(mutation.receipt, `temporal ${command} result`);
      }
      result = mutation;
      pendingProjection = undefined;
    } else if (spec.readOnlySelection) {
      result = decodeTemporalSelectionResult(raw, `temporal ${command} result`);
    } else {
      result = decodeTemporalReadResult(raw, `temporal ${command} result`);
    }
    notifyJson(context, result);
  }


  async function runCassiCommand(args: string, context: ExtensionContext): Promise<void> {
    const trimmed = args.trim();
    const [action = "status", ...rest] = trimmed ? trimmed.split(/\s+/u) : [];
    if (action === "temporal") {
      await runTemporalCommand(trimmed.slice(action.length).trim(), context);
      return;
    }
    if (action === "status") {
      try {
        notifyJson(context, await memoryInspect(context, "state", undefined, "branch"));
      } catch (error) {
        notifyJson(
          context,
          {
            schema: "cassipi.memory-inspect-result.v1",
            selector: "state",
            readiness: "unavailable",
            worker: client.diagnostics?.() ?? {
              schema: "cassipi.worker-diagnostics.v1",
              readiness: "unavailable",
              recovery: { status: "unreported" },
            },
            error: {
              code: error instanceof CassiPiOwnerError ? error.code : "OWNER_UNAVAILABLE",
              message: error instanceof Error ? error.message : "CassiPi owner is unavailable",
            },
          },
          "error",
        );
      }
      return;
    }
    if (action === "inspect") {
      const selector = rest[0] ?? "state";
      const memoryScope = rest[1] ? commandScope(rest[1]) : "branch";
      const exactRef = rest[2] ? exactRevisionId({ ref: rest[2] }, "ref") : undefined;
      notifyJson(context, await memoryInspect(context, selector, exactRef, memoryScope));
      return;
    }
    if (action === "pause" || action === "resume") {
      const current = await scope(context);
      const capture = await setCaptureStatus(current, action === "pause");
      notifyJson(context, {
        schema: "cassipi.capture-command-result.v1",
        paused: capture.paused,
        operation_id: capture.operation_id,
        profile_id: capture.profile_id,
      });
      return;
    }
    if (action === "recovery") {
      await reconcileLifecycle(context);
      notifyJson(context, await memoryInspect(context, "state", undefined, "branch"));
      return;
    }
    if (action === "remember") {
      if (rest.length < 2) {
        throw new CassiPiOwnerError(
          "COMMAND_USAGE",
          "usage: /cassi remember <task|branch|project|profile> <content>",
          400,
        );
      }
      const memoryScope = commandScope(rest[0]);
      notifyJson(
        context,
        await memoryMutation(
          context,
          "remember",
          `memory-command:${randomUUID()}`,
          rest.slice(1).join(" "),
          memoryScope,
          [],
          undefined,
          undefined,
        ),
      );
      return;
    }
    if (action === "correct") {
      if (rest.length < 3) {
        throw new CassiPiOwnerError(
          "COMMAND_USAGE",
          "usage: /cassi correct <task|branch|project|profile> <revision-id> <replacement>",
          400,
        );
      }
      const memoryScope = commandScope(rest[0]);
      const target = exactRevisionId({ target_revision_id: rest[1] }, "target_revision_id");
      notifyJson(
        context,
        await memoryMutation(
          context,
          "correct",
          `memory-command:${randomUUID()}`,
          rest.slice(2).join(" "),
          memoryScope,
          [],
          target,
          undefined,
        ),
      );
      return;
    }
    if (action === "forget") {
      if (rest.length !== 2) {
        throw new CassiPiOwnerError(
          "COMMAND_USAGE",
          "usage: /cassi forget <task|branch|project|profile> <revision-id>",
          400,
        );
      }
      if (!context.hasUI) {
        throw new CassiPiOwnerError(
          "INTERACTIVE_APPROVAL_REQUIRED",
          "forget requires an interactive Oh My Pi UI",
          403,
        );
      }
      const memoryScope = commandScope(rest[0]);
      const target = exactRevisionId({ target_revision_id: rest[1] }, "target_revision_id");
      const preview = await forgetPreview(context, target, memoryScope);
      const approved = await context.ui.confirm(
        "Forget CassiPi source?",
        `${canonicalJson(preview)}\n\nThis revokes the exact source from CassiPi-managed field generations. Oh My Pi transcripts, external files/exports, backups, and provider records are outside this operation.`,
      );
      if (!approved) {
        context.ui.notify("CassiPi forget canceled; no field state changed.", "info");
        return;
      }
      const current = await scope(context);
      const previewId = requiredString(
        isRecord(preview) ? preview.preview_id : undefined,
        "forget preview_id",
      );
      const authorization = await client.owner(
        "forget_authorize",
        {
          schema: "cassipi.forget-authorize.v1",
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
          memory_scope: memoryScope,
          revision_ids: [target],
          preview_id: previewId,
        },
        undefined,
        authenticatedScope(current),
      );
      const authorizationToken = requiredString(
        isRecord(authorization) ? authorization.authorization_token : undefined,
        "forget authorization token",
      );
      if (!isRecord(authorization) || authorization.one_use !== true) {
        throw new CassiPiOwnerError(
          "INVALID_OWNER_RESPONSE",
          "forget authorization is not one-use",
          502,
        );
      }
      const cursor = await cursorFor(current, true);
      const status = await client.status();
      const result = await client.owner(
        "forget_execute",
        {
          schema: "cassipi.forget-execute.v1",
          operation_id: `forget:${previewId}`,
          native_identity: `forget:${previewId}`,
          producer_id: current.producerId,
          producer_sequence: cursor.nextSequence,
          predecessor_event_id: cursor.lastEventId,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
          parent_head_id: status.field_head_sha256,
          memory_scope: memoryScope,
          revision_ids: [target],
          preview_id: previewId,
          authorization_token: authorizationToken,
        },
        undefined,
        authenticatedScope(current),
      );
      const eventId = requiredString(
        isRecord(result) ? result.event_id : undefined,
        "forget result event_id",
      );
      cursor.lastEventId = eventId;
      cursor.nextSequence += 1;
      pendingProjection = undefined;
      notifyJson(context, result);
      return;
    }
    if (action === "import" && rest[0] === "preview") {
      if (rest.length < 4) {
        throw new CassiPiOwnerError(
          "COMMAND_USAGE",
          "usage: /cassi import preview <mnemic|thalamus|mnemopi|omp-session> <task|branch|project|profile> <path>",
          400,
        );
      }
      const adapter = rest[1] ?? "";
      const memoryScope = memoryScopeField({ scope: rest[2] });
      const pathText = rest.slice(3).join(" ");
      const unquotedPath =
        pathText.length >= 2
        && (
          (pathText.startsWith("\"") && pathText.endsWith("\""))
          || (pathText.startsWith("'") && pathText.endsWith("'"))
        )
          ? pathText.slice(1, -1)
          : pathText;
      const current = await scope(context);
      const preview = await client.owner(
        "import_preview",
        {
          schema: "cassipi.import-preview.v1",
          adapter,
          source_path: resolve(context.cwd, unquotedPath),
          memory_scope: memoryScope,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
        },
        undefined,
        authenticatedScope(current),
      );
      const previewId = requiredString(
        isRecord(preview) ? preview.preview_id : undefined,
        "import preview_id",
      );
      importPreviews.set(previewId, preview);
      notifyJson(context, preview);
      return;
    }
    if (action === "import" && rest[0] === "commit") {
      const previewId = exactRevisionId({ preview_id: rest[1] }, "preview_id");
      const preview = importPreviews.get(previewId);
      if (!preview) {
        throw new CassiPiOwnerError(
          "IMPORT_PREVIEW_NOT_LOADED",
          "run the matching /cassi import preview command in this process before committing",
          409,
        );
      }
      if (!context.hasUI) {
        throw new CassiPiOwnerError(
          "INTERACTIVE_APPROVAL_REQUIRED",
          "legacy import commit requires direct interactive approval",
          403,
        );
      }
      const approved = await context.ui.confirm(
        "Commit this Cassi memory import?",
        canonicalJson(preview),
      );
      if (!approved) {
        context.ui.notify("Cassi memory import canceled; no records were committed.", "info");
        return;
      }
      const current = await scope(context);
      const result = await client.owner(
        "import_commit",
        {
          schema: "cassipi.import-commit.v1",
          preview_id: previewId,
          profile_id: current.profileId,
          project_id: current.projectId,
          session_id: current.sessionId,
          branch_id: current.branchId,
          task_scope: current.taskScope,
        },
        undefined,
        authenticatedScope(current),
      );
      pendingProjection = undefined;
      notifyJson(context, result);
      return;
    }
    throw new CassiPiOwnerError(
      "COMMAND_USAGE",
      "usage: /cassi [status|inspect|remember|correct|forget|pause|resume|recovery|temporal <operation> <json-object>|import preview|import commit]",
      400,
    );
  }

  return function cassiPiExtension(api: ExtensionAPI): void {
    api.registerContextOwner({ id: OWNER_ID, apiVersion: OWNER_API_VERSION });

    api.registerTool({
      name: "cassi_memory",
      label: "Cassi Memory",
      description:
        "Recall, declare, correct, preview forgetting, or inspect source-backed CassiPi field memory. Scope identities are derived from the authenticated host session; tool calls cannot authorize forgetting.",
      parameters: memoryToolParameters(api.typebox.Type),
      approval: "write",
      strict: true,
      execute: (toolCallId, params, signal, _onUpdate, context) => {
        providerTurnSelection = undefined;
        return serialize(() => executeMemoryTool(toolCallId, params, signal, context));
      },
    });
    api.registerCommand("cassi", {
      description: "Inspect and control CassiPi memory ownership",
      handler: (args, context) => {
        providerTurnSelection = undefined;
        return serialize(() => runCassiCommand(args, context));
      },
    });

    api.on("agent_start", () => {
      providerTurnSelection = undefined;
    });
    api.on("agent_end", () => {
      providerTurnSelection = undefined;
    });

    api.on("context", async (event, context) =>
      serialize(async () => {
        try {
          const projected = await projectMessages(context, contextMessages(event));
          pendingProjection = projected.binding;
          return { messages: projected.messages, ownerProjection: projected.binding };
        } catch (error) {
          pendingProjection = undefined;
          throw errorWithCode(error);
        }
      }),
    );

    api.on("before_provider_request", event => {
      if (!pendingProjection) {
        throw new CassiPiOwnerError("OWNER_PROJECTION_MISSING", "provider request has no fresh FI projection", 409);
      }
      return { payload: providerPayload(event), ownerProjection: pendingProjection };
    });

    api.on("tool_call", (event, context) => recordToolLifecycle(event, context, "action-proposal"));
    api.on("tool_execution_start", (event, context) => recordToolLifecycle(event, context, "action-start"));
    api.on("tool_execution_end", (event, context) => recordToolLifecycle(event, context, "action-outcome"));
    api.on("tool_approval_resolved", (event, context) =>
      booleanField(event, "approved") === false ? recordToolLifecycle(event, context, "action-outcome") : undefined,
    );

    api.on("session_before_compact", (event, context) =>
      serialize(async () => {
        const preparation = compactionPreparation(event);
        const messages = [
          ...agentMessages(preparation.messagesToSummarize, "compaction messagesToSummarize"),
          ...agentMessages(preparation.turnPrefixMessages, "compaction turnPrefixMessages"),
        ];
        const rewrite = await prepareFieldRewrite(
          context,
          "compact",
          messages,
          compactionTokenBudget(context, preparation),
          stringField(event, "reason") ?? "compact",
          abortSignal(event),
        );
        if (!rewrite) return { cancel: true };
        const tokensBefore = requiredInteger(preparation.tokensBefore, "compaction tokensBefore");
        if (tokensBefore < 0) throw new CassiPiOwnerError("INVALID_HOST_EVENT", "compaction tokensBefore is negative", 409);
        return {
          compaction: {
            summary: rewrite.summary,
            firstKeptEntryId: requiredString(preparation.firstKeptEntryId, "compaction firstKeptEntryId"),
            tokensBefore,
            details: { ...compactionFileDetails(preparation), ...rewrite.details },
          },
          ownerBinding: rewrite.binding,
        };
      }),
    );
    api.on("session_compact", (_event, context) =>
      serialize(() => commitLifecycle(context, pendingForKind("compact"))),
    );

    api.on("session_before_handoff", (event, context) =>
      serialize(async () => {
        const preparation = compactionPreparation(event);
        const messages = [
          ...agentMessages(preparation.messagesToSummarize, "handoff messagesToSummarize"),
          ...agentMessages(preparation.turnPrefixMessages, "handoff turnPrefixMessages"),
        ];
        const rewrite = await prepareFieldRewrite(
          context,
          "handoff",
          messages,
          compactionTokenBudget(context, preparation),
          stringField(event, "customInstructions") ?? "handoff",
          abortSignal(event),
        );
        return rewrite
          ? { handoff: { document: rewrite.summary }, ownerBinding: rewrite.binding }
          : { cancel: true };
      }),
    );
    api.on("session_handoff", (_event, context) =>
      serialize(() => commitLifecycle(context, pendingForKind("handoff"))),
    );

    api.on("session_before_switch", (event, context) =>
      serialize(async () => {
        const operationKind = stringField(event, "reason");
        if (!operationKind) throw new CassiPiOwnerError("INVALID_HOST_EVENT", "session switch reason is missing", 409);
        const targetHeadId = await switchTargetHead(event, context, operationKind);
        return {
          ownerBinding: await prepareTransition(
            context,
            operationKind,
            operationKind,
            abortSignal(event),
            targetHeadId,
          ),
        };
      }),
    );
    api.on("session_switch", (event, context) =>
      serialize(async () => {
        const operationKind = stringField(event, "reason");
        if (!operationKind) throw new CassiPiOwnerError("INVALID_HOST_EVENT", "session switch reason is missing", 409);
        await commitLifecycle(context, pendingForKind(operationKind));
      }),
    );

    api.on("session_before_branch", (event, context) =>
      serialize(async () => {
        const entryId = stringField(event, "entryId");
        if (!entryId) throw new CassiPiOwnerError("INVALID_HOST_EVENT", "branch target entry is missing", 409);
        await syncBranch(context);
        const targetHeadId = await treeOrBranchTargetHead(context, entryId);
        if (!targetHeadId) {
          throw new CassiPiOwnerError("LINEAGE_TARGET_MISSING", "branch target has no durable field version", 409);
        }
        return {
          ownerBinding: await prepareTransition(context, "branch", entryId, abortSignal(event), targetHeadId),
        };
      }),
    );
    api.on("session_branch", (_event, context) =>
      serialize(() => commitLifecycle(context, pendingForKind("branch"))),
    );

    api.on("session_before_tree", (event, context) =>
      serialize(async () => {
        const preparation = compactionPreparation(event);
        const targetId = requiredString(preparation.targetId, "tree targetId");
        await syncBranch(context);
        const targetHeadId = await treeOrBranchTargetHead(context, targetId);
        if (!targetHeadId) {
          throw new CassiPiOwnerError("LINEAGE_TARGET_MISSING", "tree target has no durable field version", 409);
        }
        if (booleanField(preparation, "userWantsSummary") === true) {
          const rewrite = await prepareFieldRewrite(
            context,
            "tree",
            messagesFromEntries(preparation.entriesToSummarize, "tree entriesToSummarize"),
            Math.min(outputReserveTokens, 16_384),
            targetId,
            abortSignal(event),
            targetHeadId,
          );
          return rewrite
            ? { summary: { summary: rewrite.summary, details: rewrite.details }, ownerBinding: rewrite.binding }
            : { cancel: true };
        }
        return {
          ownerBinding: await prepareTransition(context, "tree", targetId, abortSignal(event), targetHeadId),
        };
      }),
    );
    api.on("session_tree", (_event, context) =>
      serialize(() => commitLifecycle(context, pendingForKind("tree"))),
    );

    api.on("session_start", async (_event, context) => {
      await serialize(async () => {
        await reconcileLifecycle(context);
        await cursorFor(await scope(context), true);
      });
    });
    api.on("session_resume", async (_event, context) => {
      await serialize(async () => {
        await reconcileLifecycle(context);
        await cursorFor(await scope(context), true);
      });
    });
    api.on("session_shutdown", async () => {
      await queue;
      await client.close();
    });
  };
}

export default function cassiPi(api: ExtensionAPI): void {
  createCassiPiExtension()(api);
}
