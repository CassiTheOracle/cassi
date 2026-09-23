import {
  closeSync,
  existsSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readFileSync,
  writeSync,
} from "node:fs";
import { dirname, resolve } from "node:path";
import { createHash } from "node:crypto";
import { stableRequestId } from "./entity-client.js";

const MAX_OPERATION_BYTES = 256;
const MAX_ARGUMENT_BYTES = 65_536;
const MAX_METADATA_BYTES = 16_384;
const MAX_RESULT_BYTES = 4 * 1024 * 1024;
const EFFECT_CLASSES = new Set([
  "read-only",
  "observation",
  "workspace-write",
  "external",
  "consequential",
  "destructive",
]);
const DEFAULT_PREAUTHORIZED_EFFECTS = new Set(["read-only", "observation"]);

function canonical(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "number") {
    if (typeof value === "number" && !Number.isFinite(value)) throw new TypeError("work-order metadata must be finite JSON");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  throw new TypeError("work-order metadata must be JSON");
}

function digest(value) {
  return createHash("sha256").update(canonical(value), "utf8").digest("hex");
}

function boundedText(value, label, maxBytes = MAX_OPERATION_BYTES) {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${label} must be non-empty text`);
  if (Buffer.byteLength(value, "utf8") > maxBytes) throw new RangeError(`${label} exceeds ${maxBytes} UTF-8 bytes`);
  return value;
}

function cloneJson(value, label, maxBytes = MAX_METADATA_BYTES) {
  const encoded = canonical(value);
  if (Buffer.byteLength(encoded, "utf8") > maxBytes) throw new RangeError(`${label} exceeds ${maxBytes} UTF-8 bytes`);
  return JSON.parse(encoded);
}

function jsonObject(value, label, maxBytes = MAX_METADATA_BYTES) {
  const cloned = cloneJson(value ?? {}, label, maxBytes);
  if (!cloned || typeof cloned !== "object" || Array.isArray(cloned)) throw new TypeError(`${label} must be an object`);
  return cloned;
}

function now() {
  return new Date().toISOString();
}
function errorDetails(error) {
  return {
    code: typeof error?.info?.code === "string" && error.info.code
      ? error.info.code
      : (typeof error?.code === "string" && error.code ? error.code : "WORK_ORDER_FAILED"),
    message: error instanceof Error
      ? error.message
      : (typeof error?.message === "string" ? error.message : String(error ?? "work-order failed")),
  };
}

export function normalizeWorkOrderTools(value) {
  if (value === undefined) return [];
  if (!Array.isArray(value)) throw new TypeError("workOrderTools must be an array");
  const names = value.map((item) => boundedText(item, "work-order tool name"));
  if (new Set(names).size !== names.length) throw new TypeError("workOrderTools must not contain duplicates");
  if (names.includes("cassi_execute_work_order")) throw new TypeError("workOrderTools cannot dispatch the work-order broker recursively");
  return names;
}

function normalizeMetadataMap(value, label) {
  return jsonObject(value, label);
}

export function normalizeWorkOrder(value, allowedTools) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError("work order must be an object");
  const operationId = boundedText(value.operation_id, "operation_id");
  const programId = boundedText(value.program_id, "program_id");
  const operation = boundedText(value.operation, "operation", 2_000);
  const toolName = boundedText(value.tool_name, "tool_name");
  if (!allowedTools.has(toolName)) throw new Error(`work-order tool ${JSON.stringify(toolName)} is outside the configured Harness scope`);
  const effectClass = value.effect_class ?? "read-only";
  if (typeof effectClass !== "string" || !EFFECT_CLASSES.has(effectClass)) {
    throw new TypeError(`unsupported work-order effect class ${JSON.stringify(effectClass)}`);
  }
  const args = jsonObject(value.arguments, "arguments", MAX_ARGUMENT_BYTES);
  const authority = normalizeMetadataMap(value.authority, "authority");
  const budget = normalizeMetadataMap(value.budget, "budget");
  const expectedOutput = normalizeMetadataMap(value.expected_output, "expected_output");
  const fieldPredecessor = value.field_predecessor === undefined || value.field_predecessor === null
    ? null
    : boundedText(value.field_predecessor, "field_predecessor", 256);
  return {
    schema: "cassi.harness.work-order.v1",
    operation_id: operationId,
    program_id: programId,
    operation,
    tool_name: toolName,
    arguments: args,
    effect_class: effectClass,
    authority,
    budget,
    expected_output: expectedOutput,
    field_predecessor: fieldPredecessor,
  };
}

function outcomeBase(order, requestDigest, status) {
  return {
    schema: "cassi.harness.work-order-outcome.v1",
    operation_id: order.operation_id,
    program_id: order.program_id,
    operation: order.operation,
    tool_name: order.tool_name,
    effect_class: order.effect_class,
    request_sha256: requestDigest,
    arguments_sha256: digest(order.arguments),
    field_predecessor: order.field_predecessor,
    status,
  };
}

class WorkOrderLedger {
  constructor(file) {
    this.file = file ? resolve(file) : undefined;
    this.latest = new Map();
    if (this.file && existsSync(this.file)) {
      for (const line of readFileSync(this.file, "utf8").split(/\r?\n/)) {
        if (!line.trim()) continue;
        const row = JSON.parse(line);
        if (!row || row.schema !== "cassi.harness.work-order-ledger.v1" || typeof row.operation_id !== "string") {
          throw new Error("invalid Cassi work-order ledger row");
        }
        this.latest.set(row.operation_id, row);
      }
    }
  }

  append(row) {
    if (!this.file) {
      this.latest.set(row.operation_id, row);
      return;
    }
    mkdirSync(dirname(this.file), { recursive: true });
    const fd = openSync(this.file, "a");
    try {
      writeSync(fd, `${JSON.stringify(row)}\n`, undefined, "utf8");
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
    this.latest.set(row.operation_id, row);
  }

  reserve(order, requestDigest) {
    const previous = this.latest.get(order.operation_id);
    if (previous) {
      if (previous.request_sha256 !== requestDigest) {
        throw new Error(`work-order ${JSON.stringify(order.operation_id)} was reused with different content`);
      }
      if (previous.status === "started") {
        return {
          replay: true,
          outcome: {
            ...outcomeBase(order, requestDigest, "unknown-effect"),
            error: { code: "WORK_ORDER_RECOVERY_REQUIRED", message: "A prior Harness process started this operation but did not publish a terminal outcome; it will not be re-executed." },
            effect_disposition: "unknown",
            recovered_from: "started",
          },
        };
      }
      return { replay: true, outcome: previous.outcome };
    }
    this.append({
      schema: "cassi.harness.work-order-ledger.v1",
      operation_id: order.operation_id,
      request_sha256: requestDigest,
      status: "started",
      order,
      started_at: now(),
    });
    return { replay: false };
  }

  settle(order, requestDigest, outcome) {
    this.append({
      schema: "cassi.harness.work-order-ledger.v1",
      operation_id: order.operation_id,
      request_sha256: requestDigest,
      status: outcome.status,
      outcome,
      settled_at: now(),
    });
    return outcome;
  }
}

export class HarnessWorkOrderBroker {
  constructor(ctx, {
    workOrderTools = [],
    ledgerFile,
    approvalRequiredTools = [],
    preAuthorizedEffects = [...DEFAULT_PREAUTHORIZED_EFFECTS],
  } = {}) {
    this.ctx = ctx;
    this.allowedTools = new Set(normalizeWorkOrderTools(workOrderTools));
    this.approvalRequiredTools = new Set(normalizeWorkOrderTools(approvalRequiredTools));
    for (const toolName of this.approvalRequiredTools) {
      if (!this.allowedTools.has(toolName)) throw new TypeError(`approvalRequiredTools contains unconfigured tool ${JSON.stringify(toolName)}`);
    }
    if (!Array.isArray(preAuthorizedEffects)) throw new TypeError("preAuthorizedEffects must be an array");
    this.preAuthorizedEffects = new Set(preAuthorizedEffects);
    for (const effect of this.preAuthorizedEffects) {
      if (!EFFECT_CLASSES.has(effect)) throw new TypeError(`unsupported pre-authorized effect ${JSON.stringify(effect)}`);
    }
    this.ledger = new WorkOrderLedger(ledgerFile);
  }

  requiresApproval(order) {
    return this.approvalRequiredTools.has(order.tool_name) || !this.preAuthorizedEffects.has(order.effect_class);
  }

  async requestApproval(order, exec) {
    const approval = typeof this.ctx.get === "function" ? this.ctx.get("approval", false) : undefined;
    if (!approval || typeof approval.request !== "function" || !exec.agent) {
      return { status: "approval-unavailable", error: { code: "APPROVAL_UNAVAILABLE", message: "No active Harness approval service and agent turn is available for this work order." } };
    }
    let outcome;
    try {
      outcome = await approval.request({
        agent: exec.agent,
        toolName: order.tool_name,
        callId: exec.callId,
        reason: `Cassi work order ${order.operation_id} requests ${order.effect_class} access through ${order.tool_name}.`,
        signal: exec.signal,
      });
    } catch (error) {
      return { status: "approval-unavailable", error: errorDetails(error) };
    }
    if (outcome !== "allowed-once") {
      return {
        status: outcome === "rejected" ? "approval-rejected" : `approval-${typeof outcome === "string" ? outcome : "unavailable"}`,
        error: { code: "APPROVAL_NOT_GRANTED", message: `Harness approval outcome was ${JSON.stringify(outcome)}; only allowed-once grants execution.` },
      };
    }
    return { status: "allowed" };
  }

  async execute(rawOrder, exec) {
    const order = normalizeWorkOrder(rawOrder, this.allowedTools);
    const requestDigest = digest(order);
    const reservation = this.ledger.reserve(order, requestDigest);
    if (reservation.replay) return reservation.outcome;

    const finish = (status, extra = {}) => this.ledger.settle(order, requestDigest, {
      ...outcomeBase(order, requestDigest, status),
      ...extra,
    });

    if (exec.signal?.aborted) {
      return finish("cancelled-before-dispatch", {
        effect_disposition: "not-started",
        error: { code: "ABORTED_BEFORE_DISPATCH", message: "The work order was cancelled before the Harness tool was dispatched." },
      });
    }

    const target = typeof this.ctx.tools?.get === "function" ? this.ctx.tools.get(order.tool_name, exec.agent) : undefined;
    if (!target) {
      return finish("scope-denied", {
        effect_disposition: "not-started",
        error: { code: "WORK_ORDER_TOOL_UNAVAILABLE", message: `Harness tool ${JSON.stringify(order.tool_name)} is not visible in the current execution scope.` },
      });
    }

    if (this.requiresApproval(order)) {
      const approval = await this.requestApproval(order, exec);
      if (approval.status !== "allowed") {
        return finish(approval.status, { effect_disposition: "not-started", error: approval.error });
      }
    }

    const nestedCallId = stableRequestId("cassi-work-order", order.operation_id);
    try {
      if (typeof this.ctx.tools?.execute !== "function") {
        return finish("executor-unavailable", {
          effect_disposition: "not-started",
          error: { code: "TOOL_RUNTIME_UNAVAILABLE", message: "Harness ToolRuntime.execute is unavailable." },
        });
      }
      const nested = await this.ctx.tools.execute({
        callId: nestedCallId,
        rootCallId: exec.rootCallId,
        name: order.tool_name,
        arguments: order.arguments,
        agent: exec.agent,
        parent: exec.token,
        signal: exec.signal,
      });
      for (const context of nested.additionalContexts ?? []) {
        exec.deferContext?.(context);
      }
      if (!nested.isError) {
        return finish("succeeded", {
          effect_disposition: "completed",
          result: {
            value: cloneJson(nested.value, "tool result", MAX_RESULT_BYTES),
            content: cloneJson(nested.content, "tool result content", MAX_RESULT_BYTES),
          },
        });
      }
      const error = errorDetails(nested.error);
      const abortedBeforeDispatch = error.code === "ABORTED_BEFORE_DISPATCH";
      return finish(exec.signal?.aborted ? (abortedBeforeDispatch ? "cancelled-before-dispatch" : "unknown-effect") : "failed", {
        effect_disposition: abortedBeforeDispatch ? "not-started" : (exec.signal?.aborted ? "unknown" : "failed"),
        error,
      });
    } catch (error) {
      return finish(exec.signal?.aborted ? "unknown-effect" : "failed", {
        effect_disposition: exec.signal?.aborted ? "unknown" : "failed",
        error: errorDetails(error),
      });
    }
  }
}