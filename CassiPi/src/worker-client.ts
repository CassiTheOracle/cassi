import { randomUUID } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, type ChildProcess } from "node:child_process";

import {
  DESCRIPTOR_SCHEMA,
  PROTOCOL_ID,
  REQUEST_SCHEMA,
  RESPONSE_SCHEMA,
  canonicalJson,
  decodeOwnerStatus,
  isRecord,
  jsonRecord,
  jsonValue,
  requiredString,
  type AuthenticatedHostScope,
  type Json,
  type OwnerDescriptor,
  type OwnerStatus,
} from "./protocol.js";

const MAX_RESPONSE_BYTES = 64 * 1024 * 1024;
const START_TIMEOUT_MS = 30_000;
const RPC_TIMEOUT_MS = 30_000;

const RECOVERY: Record<string, string> = {
  AUTH_FAILED: "Restart the private CassiPi owner worker.",
  CHECKPOINT_IDENTITY_MISMATCH: "Reinstall the verified FI runtime artifact.",
  CLIENT_NOT_ATTACHED: "Reload the CassiPi extension so it can attach again.",
  DEPENDENCY_MISSING: "Repair the packaged FI runtime dependencies, then restart OMP.",
  MANDATORY_CAPACITY: "Select a larger-context model or reduce protected current material.",
  OWNER_CONTENTION: "Wait for the existing owner process or close the stale OMP session.",
  OWNER_NOT_PERSISTENT: "Configure a writable CASSIPI_DATA_HOME and restart OMP.",
  PROTOCOL_MISMATCH: "Install matching CassiPi host and FI runtime versions.",
  RUNTIME_IDENTITY_MISMATCH: "Reinstall the verified FI runtime artifact.",
  STALE_FIELD_HEAD: "Retry from a fresh owner projection.",
  STALE_JOURNAL_HEAD: "Retry from a fresh owner projection.",
  TOKEN_ACCOUNTING_MISMATCH: "Retry after recounting every rendered candidate with the selected model.",
};

export class CassiPiOwnerError extends Error {
  readonly name = "CassiPiOwnerError";
  readonly ownerMessage: string;

  constructor(
    readonly code: string,
    message: string,
    readonly status = 500,
    readonly details: Record<string, Json> = {},
  ) {
    super(`${message} Recovery: ${RECOVERY[code] ?? "Inspect the owner diagnostic and retry safely."}`);
    this.ownerMessage = message;
  }
}

export interface WorkerClientOptions {
  clientId?: string;
  dataHome?: string;
  python?: string;
  runtimeRoot?: string;
  startTimeoutMs?: number;
  rpcTimeoutMs?: number;
}

function defaultRuntimeRoot(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, "..", "fi-runtime");
}

function parseDescriptor(value: unknown): OwnerDescriptor {
  if (!isRecord(value)) throw new Error("owner descriptor is not an object");
  if (value.schema !== DESCRIPTOR_SCHEMA || value.protocol_id !== PROTOCOL_ID) {
    throw new Error("owner descriptor fields are incompatible");
  }
  const endpointValue = requiredString(value.endpoint, "owner endpoint");
  const secret = requiredString(value.bearer_secret, "owner bearer secret");
  const launchId = requiredString(value.launch_id, "owner launch id");
  const runtimeId = requiredString(value.runtime_id, "owner runtime id");
  const endpoint = new URL(endpointValue);
  if (endpoint.protocol !== "http:" || endpoint.hostname !== "127.0.0.1") {
    throw new Error("owner endpoint is not private loopback HTTP");
  }
  if (!/^[A-Za-z0-9_-]{32,}$/.test(secret)) {
    throw new Error("owner descriptor secret is invalid");
  }
  return {
    schema: DESCRIPTOR_SCHEMA,
    endpoint: endpointValue,
    secret,
    launch_id: launchId,
    protocol_id: PROTOCOL_ID,
    runtime_id: runtimeId,
  };
}

async function boundedResponseText(response: Response): Promise<string> {
  const declared = response.headers.get("content-length");
  if (declared !== null && Number(declared) > MAX_RESPONSE_BYTES) {
    throw new CassiPiOwnerError("RESPONSE_TOO_LARGE", "owner response exceeded the supported envelope", 502);
  }
  if (!response.body) return "";
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    bytes += chunk.value.byteLength;
    if (bytes > MAX_RESPONSE_BYTES) {
      await reader.cancel();
      throw new CassiPiOwnerError("RESPONSE_TOO_LARGE", "owner response exceeded the supported envelope", 502);
    }
    chunks.push(chunk.value);
  }
  return Buffer.concat(chunks, bytes).toString("utf8");
}

async function delay(milliseconds: number): Promise<void> {
  await new Promise(resolveDelay => setTimeout(resolveDelay, milliseconds));
}

export class CassiPiWorkerClient {
  readonly clientId: string;
  readonly dataHome: string;
  readonly runtimeRoot: string;
  readonly python: string;
  readonly startTimeoutMs: number;
  readonly rpcTimeoutMs: number;
  #descriptor: OwnerDescriptor | undefined;
  #spawned: ChildProcess | undefined;
  #attached = false;
  #scopeTokens = new Map<string, string>();
  #readiness: "not-connected" | "ready" | "unavailable" = "not-connected";
  #recovery: Json = { status: "not-checked" };

  constructor(options: WorkerClientOptions = {}) {
    this.clientId = options.clientId ?? `omp-${process.pid}-${randomUUID()}`;
    this.dataHome = resolve(options.dataHome ?? process.env.CASSIPI_DATA_HOME ?? join(homedir(), ".omp", "cassipi"));
    this.runtimeRoot = resolve(options.runtimeRoot ?? process.env.CASSIPI_FI_RUNTIME ?? defaultRuntimeRoot());
    this.python = options.python ?? process.env.CASSIPI_PYTHON ?? "python";
    this.startTimeoutMs = options.startTimeoutMs ?? START_TIMEOUT_MS;
    this.rpcTimeoutMs = options.rpcTimeoutMs ?? RPC_TIMEOUT_MS;
  }

  diagnostics(): Json {
    return {
      schema: "cassipi.worker-diagnostics.v1",
      readiness: this.#readiness,
      recovery: this.#recovery,
    };
  }

  async connect(): Promise<OwnerStatus> {
    if (this.#attached) return this.status();
    await this.#findOrStart();
    const result = jsonRecord(
      await this.rpc("attach", {
        client_id: this.clientId,
        expected: { protocol_id: PROTOCOL_ID },
      }),
      "attach result",
    );
    const owner = decodeOwnerStatus(result.owner);
    this.#attached = true;
    return owner;
  }

  async close(): Promise<void> {
    if (!this.#attached) return;
    try {
      await this.rpc("detach", { client_id: this.clientId });
    } finally {
      this.#scopeTokens.clear();
      this.#attached = false;
    }
  }

  async status(): Promise<OwnerStatus> {
    await this.#findOrStart();
    const result = jsonRecord(await this.rpc("status", {}), "status result");
    return decodeOwnerStatus(result.owner);
  }

  async owner(
    operation: string,
    request: Record<string, unknown>,
    signal: AbortSignal | undefined,
    authenticatedScope: AuthenticatedHostScope,
  ): Promise<Json> {
    if (!this.#attached) await this.connect();
    const scopeKey = canonicalJson(authenticatedScope);
    let scopeToken = this.#scopeTokens.get(scopeKey);
    if (!scopeToken) {
      const bound = jsonRecord(
        await this.rpc(
          "bind_scope",
          {
            client_id: this.clientId,
            scope: {
              schema: "cassipi.authenticated-host-scope.v1",
              ...authenticatedScope,
            },
          },
          signal,
        ),
        "authenticated host scope",
      );
      scopeToken = requiredString(bound.scope_token, "authenticated host scope token");
      this.#scopeTokens.set(scopeKey, scopeToken);
    }
    try {
      return await this.rpc(operation, { client_id: this.clientId, scope_token: scopeToken, request }, signal);
    } catch (error) {
      if (error instanceof CassiPiOwnerError) {
        throw new CassiPiOwnerError(
          error.code,
          `${operation}: ${error.ownerMessage}`,
          error.status,
          error.details,
        );
      }
      throw error;
    }
  }

  async rpc(
    operation: string,
    params: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<Json> {
    const descriptor = this.#descriptor;
    if (!descriptor) throw new CassiPiOwnerError("OWNER_UNAVAILABLE", "owner is not connected", 503);
    const requestId = randomUUID();
    const controller = new AbortController();
    const abortFromCaller = (): void => controller.abort(signal?.reason);
    if (signal?.aborted) abortFromCaller();
    else signal?.addEventListener("abort", abortFromCaller, { once: true });
    const timeout = setTimeout(() => controller.abort(new Error("owner request timed out")), this.rpcTimeoutMs);
    this.#readiness = "ready";
    let response: Response;
    try {
      response = await fetch(descriptor.endpoint, {
        method: "POST",
        headers: {
          authorization: `Bearer ${descriptor.secret}`,
          "content-type": "application/json",
        },
        body: canonicalJson({
          schema: REQUEST_SCHEMA,
          request_id: requestId,
          operation,
          params,
        }),
        signal: controller.signal,
      });
    } catch (error) {
      this.#readiness = "unavailable";
      const canceled = signal?.aborted === true;
      if (!canceled && !controller.signal.aborted) {
        this.#descriptor = undefined;
        this.#attached = false;
        this.#scopeTokens.clear();
      }
      throw new CassiPiOwnerError(
        canceled ? "OPERATION_CANCELED" : controller.signal.aborted ? "OWNER_TIMEOUT" : "OWNER_UNAVAILABLE",
        error instanceof Error ? error.message : "owner request failed",
        canceled ? 409 : 503,
      );
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abortFromCaller);
    }
    const text = await boundedResponseText(response);
    let decoded: unknown;
    try {
      decoded = JSON.parse(text);
    } catch {
      throw new CassiPiOwnerError("INVALID_RESPONSE", "owner returned invalid JSON", 502);
    }
    if (!isRecord(decoded) || decoded.schema !== RESPONSE_SCHEMA || decoded.request_id !== requestId) {
      throw new CassiPiOwnerError("INVALID_RESPONSE", "owner response identity is invalid", 502);
    }
    if (!response.ok || decoded.ok !== true || !Object.hasOwn(decoded, "result")) {
      const errorBody = isRecord(decoded.error) ? decoded.error : {};
      let details: Record<string, Json> = {};
      if (errorBody.details !== undefined) {
        try {
          details = jsonRecord(errorBody.details, "owner error details");
        } catch {
          throw new CassiPiOwnerError("INVALID_RESPONSE", "owner returned invalid error details", 502);
        }
      }
      throw new CassiPiOwnerError(
        typeof errorBody.code === "string" ? errorBody.code : "OWNER_REQUEST_FAILED",
        typeof errorBody.message === "string"
          ? errorBody.message
          : `owner request failed with HTTP ${response.status}`,
        response.status,
        details,
      );
    }
    return jsonValue(decoded.result);
  }

  async #readDescriptor(): Promise<OwnerDescriptor | undefined> {
    try {
      return parseDescriptor(JSON.parse(await readFile(join(this.dataHome, "runtime.json"), "utf8")));
    } catch {
      return undefined;
    }
  }

  async #handshake(): Promise<void> {
    const result = jsonRecord(
      await this.rpc("handshake", { expected: { protocol_id: PROTOCOL_ID } }),
      "handshake result",
    );
    this.#recovery = jsonValue(result.recovery);
  }

  async #findOrStart(): Promise<void> {
    if (this.#descriptor) return;
    const existing = await this.#readDescriptor();
    if (existing) {
      this.#descriptor = existing;
      try {
        await this.#handshake();
        return;
      } catch {
        this.#descriptor = undefined;
      }
    }
    await access(join(this.runtimeRoot, "runtime-manifest.json")).catch(() => {
      throw new CassiPiOwnerError(
        "RUNTIME_NOT_INSTALLED",
        `verified FI runtime is missing at ${this.runtimeRoot}`,
        503,
      );
    });
    this.#spawned = spawn(
      this.python,
      ["-I", "-B", join(this.runtimeRoot, "cassi_cassipi_worker.py"), "--data-home", this.dataHome],
      {
        cwd: this.runtimeRoot,
        detached: false,
        windowsHide: true,
        stdio: "ignore",
      },
    );
    const deadline = Date.now() + this.startTimeoutMs;
    while (Date.now() < deadline) {
      const descriptor = await this.#readDescriptor();
      if (descriptor) {
        this.#descriptor = descriptor;
        try {
          await this.#handshake();
          return;
        } catch {
          this.#descriptor = undefined;
        }
      }
      await delay(50);
    }
    throw new CassiPiOwnerError("OWNER_START_TIMEOUT", "private owner did not become ready", 503);
  }
}
