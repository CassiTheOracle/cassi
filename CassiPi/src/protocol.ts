import { createHash } from "node:crypto";

export const OWNER_ID = "cassipi";
export const OWNER_API_VERSION = 1;
export const REQUEST_SCHEMA = "cassifi.cassipi-owner-request.v1";
export const RESPONSE_SCHEMA = "cassifi.cassipi-owner-response.v1";
export const DESCRIPTOR_SCHEMA = "cassifi.cassipi-owner-descriptor.v1";
export const PROTOCOL_ID = "cassifi.cassipi-owner-rpc.v1";
export const FI_RUNTIME_ID = "cassifi.cassipi-field-intelligence.v4";

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

export interface OwnerDescriptor {
  schema: typeof DESCRIPTOR_SCHEMA;
  endpoint: string;
  secret: string;
  launch_id: string;
  protocol_id: typeof PROTOCOL_ID;
  runtime_id: string;
}

export interface AuthenticatedHostScope {
  profile_id: string;
  project_id: string;
  session_id: string;
  branch_id: string;
  task_scope: string;
}

export interface CaptureStatus {
  schema: "cassipi.capture-control.v1";
  paused: boolean;
  operation_id: string | null;
  profile_id: string | null;
  replayed?: boolean;
}

export interface OwnerStatus {
  active_state_sha256: string;
  branch_id: string | null;
  capacity: Record<string, Json>;
  checkpoint_hash: string;
  checkpoint_id: string;
  field_head_sha256: string;
  journal_head_sha256: string;
  persistent: true;
  profile_id: string | null;
  project_id: string | null;
  revocation_epoch: number;
  session_id: string | null;
  source_root_digest: string;
  task_scope: string | null;
  protocol_id: string;
  generation_id: string;
  runtime_id: string;
  closure_sha256: string;
  manifest_sha256: string;
}

export interface OwnerRpcErrorBody {
  code: string;
  message: string;
  details?: Record<string, Json>;
}

export interface ObservedResult {
  event_id: string;
  source: { revision_id: string; content_sha256: string };
  receipt: { checkpoint_metadata_sha256: string };
}



export interface SourceBindingRow {
  event_id: string;
  event_kind: string;
  native_entry_id: string | null;
  parent_head_id: string;
  tool_call_id: string | null;
  provisional_observation_id: string | null;
  predecessor_event_id: string | null;
  producer_sequence: number;
  sources: Array<{
    revision_id: string;
    content_sha256: string;
    metadata: Record<string, Json>;
  }>;
}

export interface HostOperationBinding {
  ownerId: typeof OWNER_ID;
  apiVersion: typeof OWNER_API_VERSION;
  operationId: string;
  sourceSessionId: string;
  sourceLeafId: string | null;
  headId: string;
  checkpointId: string;
  checkpointHash: string;
  sourceRootDigest: string;
  coveredThroughEntryId: string | null;
  revocationEpoch: number;
}

export interface HostProjectionBinding extends HostOperationBinding {
  projectionId: string;
  tokenCount: number;
  tokenBudget: number;
}

export interface ProjectionInventory {
  schema: "cassipi.projection-inventory.v1";
  inventory_sha256: string;

  candidates: Array<{
    event_id: string;
    mandatory: boolean;
    native_entry_id: string | null;
    order: number;
    revision_id: string;
    source: Record<string, Json>;
    representations: Array<{
      action_id: string;
      message: { role: "assistant"; content: string };
      message_sha256: string;
      representation: string;
    }>;
  }>;
}
export interface LifecyclePrepareResult {
  schema: "cassipi.lifecycle-prepare.v1";
  event_id: string;
  binding: HostOperationBinding;
}

export interface LifecyclePendingResult {
  schema: "cassipi.lifecycle-pending.v1";
  pending: Array<{
    event_id: string;
    operation_kind: string;
    binding: HostOperationBinding;
  }>;
}

export interface LifecycleCommitResult {
  schema: "cassipi.lifecycle-commit.v1";
  event_id: string;
  binding: HostOperationBinding;
  active_head_id: string;
  replayed: boolean;
}

export interface LifecycleCancelResult {
  schema: "cassipi.lifecycle-cancel.v1";
  event_id: string;
}

export interface LineageLookupResult {
  schema: "cassipi.lineage-lookup.v1";
  found: boolean;
  head_id: string | null;
  event_id: string | null;
}

export interface ProjectionResult {
  schema: "cassipi.projection.v1";
  projection_id: string;
  status: "ready" | "abstained" | "no-fit";
  identity: {
    field_head_sha256: string;
    journal_head_sha256: string;
    revocation_epoch: number;
  };
  messages: Array<{ role: "assistant"; content: string }>;
  selected: Array<{
    action_id: string;
    revision_id: string;
    event_id: string;
    representation: string;
    source: Record<string, Json>;
    tokens: number;
  }>;
  accounting: {
    context_window_tokens: number;
    used_tokens: number;
    remaining_tokens: number;
  };
}

export function sha256(value: string | Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}
export function jsonValue(value: unknown): Json {
  return canonicalValue(value);
}

export function jsonRecord(value: unknown, label: string): Record<string, Json> {
  const decoded = jsonValue(value);
  if (decoded === null || Array.isArray(decoded) || typeof decoded !== "object") {
    throw new TypeError(`${label} is not an object`);
  }
  return decoded;
}

export function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) throw new TypeError(`${label} is not a nonempty string`);
  return value;
}

export function optionalString(value: unknown, label: string): string | null {
  if (value === null) return null;
  return requiredString(value, label);
}

export function requiredInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) throw new TypeError(`${label} is not an integer`);
  return value;
}

export function decodeOwnerStatus(value: unknown): OwnerStatus {
  if (!isRecord(value)) throw new TypeError("owner status is not an object");
  const persistent = value.persistent;
  if (persistent !== true) throw new TypeError("owner status is not persistent");
  const revocationEpoch = requiredInteger(value.revocation_epoch, "owner revocation_epoch");
  if (revocationEpoch < 0) throw new TypeError("owner revocation_epoch is negative");
  return {
    active_state_sha256: requiredString(value.active_state_sha256, "owner active_state_sha256"),
    branch_id: optionalString(value.branch_id, "owner branch_id"),
    capacity: jsonRecord(value.capacity, "owner capacity"),
    checkpoint_hash: requiredString(value.checkpoint_hash, "owner checkpoint_hash"),
    checkpoint_id: requiredString(value.checkpoint_id, "owner checkpoint_id"),
    field_head_sha256: requiredString(value.field_head_sha256, "owner field_head_sha256"),
    journal_head_sha256: requiredString(value.journal_head_sha256, "owner journal_head_sha256"),
    persistent,
    profile_id: optionalString(value.profile_id, "owner profile_id"),
    project_id: optionalString(value.project_id, "owner project_id"),
    revocation_epoch: revocationEpoch,
    generation_id: requiredString(value.generation_id, "owner generation_id"),
    session_id: optionalString(value.session_id, "owner session_id"),
    source_root_digest: requiredString(value.source_root_digest, "owner source_root_digest"),
    task_scope: optionalString(value.task_scope, "owner task_scope"),
    protocol_id: requiredString(value.protocol_id, "owner protocol_id"),
    runtime_id: requiredString(value.runtime_id, "owner runtime_id"),
    closure_sha256: requiredString(value.closure_sha256, "owner closure_sha256"),
    manifest_sha256: requiredString(value.manifest_sha256, "owner manifest_sha256"),
  };
}

function requiredJsonArray(value: unknown, label: string): Json[] {
  const decoded = jsonValue(value);
  if (!Array.isArray(decoded)) throw new TypeError(`${label} is not an array`);
  return decoded;
}
export function decodeHostOperationBinding(value: unknown): HostOperationBinding {
  const row = jsonRecord(value, "host operation binding");
  if (row.ownerId !== OWNER_ID || row.apiVersion !== OWNER_API_VERSION) {
    throw new TypeError("host operation binding identity is incompatible");
  }
  const revocationEpoch = requiredInteger(row.revocationEpoch, "binding revocationEpoch");
  if (revocationEpoch < 0) throw new TypeError("binding revocationEpoch is negative");
  return {
    ownerId: OWNER_ID,
    apiVersion: OWNER_API_VERSION,
    operationId: requiredString(row.operationId, "binding operationId"),
    sourceSessionId: requiredString(row.sourceSessionId, "binding sourceSessionId"),
    sourceLeafId: optionalString(row.sourceLeafId, "binding sourceLeafId"),
    headId: requiredString(row.headId, "binding headId"),
    checkpointId: requiredString(row.checkpointId, "binding checkpointId"),
    checkpointHash: requiredString(row.checkpointHash, "binding checkpointHash"),
    sourceRootDigest: requiredString(row.sourceRootDigest, "binding sourceRootDigest"),
    coveredThroughEntryId: optionalString(row.coveredThroughEntryId, "binding coveredThroughEntryId"),
    revocationEpoch,
  };
}

export function decodeLifecyclePrepare(value: unknown): LifecyclePrepareResult {
  const root = jsonRecord(value, "lifecycle prepare result");
  if (root.schema !== "cassipi.lifecycle-prepare.v1") {
    throw new TypeError("lifecycle prepare schema is incompatible");
  }
  return {
    schema: "cassipi.lifecycle-prepare.v1",
    event_id: requiredString(root.event_id, "lifecycle prepare event_id"),
    binding: decodeHostOperationBinding(root.binding),
  };
}

export function decodeLifecyclePending(value: unknown): LifecyclePendingResult {
  const root = jsonRecord(value, "lifecycle pending result");
  if (root.schema !== "cassipi.lifecycle-pending.v1") {
    throw new TypeError("lifecycle pending schema is incompatible");
  }
  const pending = requiredJsonArray(root.pending, "lifecycle pending rows").map((item, index) => {
    const row = jsonRecord(item, `lifecycle pending row ${index}`);
    return {
      event_id: requiredString(row.event_id, "lifecycle pending event_id"),
      operation_kind: requiredString(row.operation_kind, "lifecycle pending operation_kind"),
      binding: decodeHostOperationBinding(row.binding),
    };
  });
  return { schema: "cassipi.lifecycle-pending.v1", pending };
}

export function decodeLifecycleCommit(value: unknown): LifecycleCommitResult {
  const root = jsonRecord(value, "lifecycle commit result");
  if (root.schema !== "cassipi.lifecycle-commit.v1") {
    throw new TypeError("lifecycle commit schema is incompatible");
  }
  if (typeof root.replayed !== "boolean") throw new TypeError("lifecycle commit replayed is not boolean");
  const activeHeadId = requiredString(root.active_head_id, "lifecycle commit active_head_id");
  assertDigest(activeHeadId, "lifecycle commit active_head_id");
  return {
    schema: "cassipi.lifecycle-commit.v1",
    event_id: requiredString(root.event_id, "lifecycle commit event_id"),
    binding: decodeHostOperationBinding(root.binding),
    active_head_id: activeHeadId,
    replayed: root.replayed,
  };
}

export function decodeLifecycleCancel(value: unknown): LifecycleCancelResult {
  const root = jsonRecord(value, "lifecycle cancel result");
  if (root.schema !== "cassipi.lifecycle-cancel.v1") {
    throw new TypeError("lifecycle cancel schema is incompatible");
  }
  return {
    schema: "cassipi.lifecycle-cancel.v1",
    event_id: requiredString(root.event_id, "lifecycle cancel event_id"),
  };
}

export function decodeLineageLookup(value: unknown): LineageLookupResult {
  const root = jsonRecord(value, "lineage lookup result");
  if (root.schema !== "cassipi.lineage-lookup.v1") {
    throw new TypeError("lineage lookup schema is incompatible");
  }
  if (typeof root.found !== "boolean") throw new TypeError("lineage lookup found is not boolean");
  const headId = optionalString(root.head_id, "lineage lookup head_id");
  const eventId = optionalString(root.event_id, "lineage lookup event_id");
  if (root.found !== (headId !== null)) {
    throw new TypeError("lineage lookup result is internally inconsistent");
  }
  return {
    schema: "cassipi.lineage-lookup.v1",
    found: root.found,
    head_id: headId,
    event_id: eventId,
  };
}

export function decodeCaptureStatus(value: unknown): CaptureStatus {
  const root = jsonRecord(value, "capture status");
  if (root.schema !== "cassipi.capture-control.v1") {
    throw new TypeError("capture status schema is incompatible");
  }
  if (typeof root.paused !== "boolean") throw new TypeError("capture status paused is not boolean");
  if (root.replayed !== undefined && typeof root.replayed !== "boolean") {
    throw new TypeError("capture status replayed is not boolean");
  }
  return {
    schema: "cassipi.capture-control.v1",
    paused: root.paused,
    operation_id: optionalString(root.operation_id, "capture status operation_id"),
    profile_id: optionalString(root.profile_id, "capture status profile_id"),
    ...(root.replayed === undefined ? {} : { replayed: root.replayed }),
  };
}


export function decodeSourceBindings(value: unknown): { bindings: SourceBindingRow[] } {
  const root = jsonRecord(value, "source bindings");
  const bindings = requiredJsonArray(root.bindings, "source bindings.bindings").map((item, rowIndex) => {
    const row = jsonRecord(item, `source binding ${rowIndex}`);
    const sequence = requiredInteger(row.producer_sequence, `source binding ${rowIndex} producer_sequence`);
    if (sequence < 0) throw new TypeError(`source binding ${rowIndex} producer_sequence is negative`);
    const sources = requiredJsonArray(row.sources, `source binding ${rowIndex} sources`).map((source, sourceIndex) => {
      const sourceRow = jsonRecord(source, `source binding ${rowIndex} source ${sourceIndex}`);
      return {
        revision_id: requiredString(sourceRow.revision_id, "source revision_id"),
        content_sha256: requiredString(sourceRow.content_sha256, "source content_sha256"),
        metadata: jsonRecord(sourceRow.metadata, "source metadata"),
      };
    });
    return {
      event_id: requiredString(row.event_id, "source event_id"),
      event_kind: requiredString(row.event_kind, "source event_kind"),
      native_entry_id: optionalString(row.native_entry_id, "source native_entry_id"),
      tool_call_id: optionalString(row.tool_call_id, "source tool_call_id"),
      provisional_observation_id: optionalString(
        row.provisional_observation_id,
        "source provisional_observation_id",
      ),
      parent_head_id: requiredString(row.parent_head_id, "source parent_head_id"),
      predecessor_event_id: optionalString(row.predecessor_event_id, "source predecessor_event_id"),
      producer_sequence: sequence,
      sources,
    };
  });
  return { bindings };
}

export function decodeObservedResult(value: unknown): ObservedResult {
  const root = jsonRecord(value, "observe result");
  const source = jsonRecord(root.source, "observe source");
  const receipt = jsonRecord(root.receipt, "observe receipt");
  return {
    event_id: requiredString(root.event_id, "observe event_id"),
    source: {
      revision_id: requiredString(source.revision_id, "observe revision_id"),
      content_sha256: requiredString(source.content_sha256, "observe content_sha256"),
    },
    receipt: {
      checkpoint_metadata_sha256: requiredString(
        receipt.checkpoint_metadata_sha256,
        "observe checkpoint_metadata_sha256",
      ),
    },
  };
}

export function decodeProjectionInventory(value: unknown): ProjectionInventory {
  const root = jsonRecord(value, "projection inventory");
  if (root.schema !== "cassipi.projection-inventory.v1") {
    throw new TypeError("projection inventory schema is incompatible");
  }
  const candidates = requiredJsonArray(root.candidates, "projection candidates").map((item, candidateIndex) => {
    const candidate = jsonRecord(item, `projection candidate ${candidateIndex}`);
    const mandatory = candidate.mandatory;
    if (typeof mandatory !== "boolean") throw new TypeError("projection candidate mandatory is not boolean");
    const order = requiredInteger(candidate.order, "projection candidate order");
    const representations = requiredJsonArray(candidate.representations, "projection representations").map<
      ProjectionInventory["candidates"][number]["representations"][number]
    >((item, representationIndex) => {
      const representation = jsonRecord(item, `projection representation ${representationIndex}`);
      const message = jsonRecord(representation.message, "projection representation message");
      if (message.role !== "assistant") throw new TypeError("projection representation role is invalid");
      return {
        action_id: requiredString(representation.action_id, "projection action_id"),
        message: {
          role: "assistant",
          content: requiredString(message.content, "projection message content"),
        },
        message_sha256: requiredString(representation.message_sha256, "projection message_sha256"),
        representation: requiredString(representation.representation, "projection representation"),
      };
    });
    return {
      event_id: requiredString(candidate.event_id, "projection candidate event_id"),
      mandatory,
      native_entry_id: optionalString(candidate.native_entry_id, "projection candidate native_entry_id"),
      order,
      revision_id: requiredString(candidate.revision_id, "projection candidate revision_id"),
      source: jsonRecord(candidate.source, "projection candidate source"),
      representations,
    };
  });
  return {
    schema: "cassipi.projection-inventory.v1",
    inventory_sha256: requiredString(root.inventory_sha256, "projection inventory_sha256"),
    candidates,
  };
}

export function decodeProjectionResult(value: unknown): ProjectionResult {
  const root = jsonRecord(value, "projection result");
  if (root.schema !== "cassipi.projection.v1") throw new TypeError("projection result schema is incompatible");
  if (root.status !== "ready" && root.status !== "abstained" && root.status !== "no-fit") {
    throw new TypeError("projection status is invalid");
  }
  const identity = jsonRecord(root.identity, "projection identity");
  const accounting = jsonRecord(root.accounting, "projection accounting");
  const messages = requiredJsonArray(root.messages, "projection messages").map<ProjectionResult["messages"][number]>(
    item => {
      const message = jsonRecord(item, "projection message");
      if (message.role !== "assistant") throw new TypeError("projection message role is invalid");
      return { role: "assistant", content: requiredString(message.content, "projection message content") };
    },
  );
  const selected = requiredJsonArray(root.selected, "projection selected").map(item => {
    const row = jsonRecord(item, "selected projection row");
    const tokens = requiredInteger(row.tokens, "selected projection tokens");
    if (tokens < 0) throw new TypeError("selected projection tokens is negative");
    return {
      action_id: requiredString(row.action_id, "selected action_id"),
      revision_id: requiredString(row.revision_id, "selected revision_id"),
      event_id: requiredString(row.event_id, "selected event_id"),
      representation: requiredString(row.representation, "selected representation"),
      source: jsonRecord(row.source, "selected source"),
      tokens,
    };
  });
  return {
    schema: "cassipi.projection.v1",
    projection_id: requiredString(root.projection_id, "projection_id"),
    status: root.status,
    identity: {
      field_head_sha256: requiredString(identity.field_head_sha256, "projection field_head_sha256"),
      journal_head_sha256: requiredString(identity.journal_head_sha256, "projection journal_head_sha256"),
      revocation_epoch: requiredInteger(identity.revocation_epoch, "projection revocation_epoch"),
    },
    messages,
    selected,
    accounting: {
      context_window_tokens: requiredInteger(accounting.context_window_tokens, "projection context_window_tokens"),
      used_tokens: requiredInteger(accounting.used_tokens, "projection used_tokens"),
      remaining_tokens: requiredInteger(accounting.remaining_tokens, "projection remaining_tokens"),
    },
  };
}


function canonicalValue(value: unknown): Json {
  if (value === null || typeof value === "boolean" || typeof value === "string") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("non-finite JSON number");
    return Object.is(value, -0) ? 0 : value;
  }
  if (Array.isArray(value)) return value.map(item => canonicalValue(item));
  if (isRecord(value)) {
    const result: Record<string, Json> = {};
    for (const key of Object.keys(value).sort()) {
      const item = value[key];
      if (item !== undefined) result[key] = canonicalValue(item);
    }
    return result;
  }
  throw new TypeError(`value is not canonical JSON: ${typeof value}`);
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalValue(value));
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function assertDigest(value: unknown, label: string): asserts value is string {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/.test(value)) {
    throw new Error(`${label} is not a SHA-256 digest`);
  }
}
