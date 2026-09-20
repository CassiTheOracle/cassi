function endpointTarget(endpoint) {
  if (
    typeof endpoint !== "string"
    || !endpoint
    || endpoint.split("/").some(
      (segment) => segment === "" || segment === "." || segment === ".." || !/^[A-Za-z0-9_$-]+$/.test(segment),
    )
  ) {
    throw new TypeError("Cassi endpoint contains an invalid segment");
  }
  return endpoint;
}

function rpcId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `cassi-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function rpcOrigin() {
  const origin = globalThis.location?.origin;
  return typeof origin === "string" && origin !== "null" ? origin : "http://127.0.0.1";
}

export const inject = ["connection"];

export function createCassiRpc(doFetch = globalThis.fetch) {
  if (typeof doFetch !== "function") throw new Error("Cassi RPC fetch is unavailable");
  return {
    async call(endpoint, payload = {}, signal) {
      endpointTarget(endpoint);
      if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
        throw new TypeError("Cassi RPC payload must be an object");
      }
      const id = rpcId();
      const response = await doFetch(new URL(`/cassi/${endpoint}`, rpcOrigin()), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ type: "client-request", rpcId: id, method: endpoint, payload }),
        ...(signal === undefined ? {} : { signal }),
      });
      if (!response.ok) throw new Error(`Cassi RPC transport failed: HTTP ${response.status}`);
      const result = await response.json();
      if (result?.rpcId !== id) throw new Error("Cassi RPC correlation mismatch");
      return result.result;
    },
  };
}

export function apply(ctx) {
  const rpc = {
    call(endpoint, payload = {}, signal) {
      return ctx.connection.rpc.call("/cassi", endpointTarget(endpoint), payload, signal);
    },
  };
  ctx.provide("cassi", rpc);
}

export async function readCassiState(doFetch, signal) {
  return createCassiRpc(doFetch).call("state", {}, signal);
}

export async function listCassiPrograms(doFetch, signal) {
  return createCassiRpc(doFetch).call("programs", {}, signal);
}

export async function readCassiProgram(programId, doFetch, signal) {
  return createCassiRpc(doFetch).call("program", { program_id: programId }, signal);
}
