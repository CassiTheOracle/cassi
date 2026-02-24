/**
 * CLI Channel Worker
 * 
 * Handles communication for CLI clients. Since the CLI uses the Admin API
 * directly for SSE streaming, this worker is minimal - it just acknowledges
 * messages. The actual response streaming is handled by the Admin API's
 * SSE endpoint which subscribes directly to bus events.
 */

import { parentPort } from "node:worker_threads";

if (!parentPort) {
  throw new Error("cli-channel must be run in worker_threads context");
}
const pp = parentPort;

pp.on("message", (msg: { type: string; [k: string]: unknown }) => {
  if (msg.type === "init") {
    pp.postMessage({ type: "ready" });
    return;
  }

  if (msg.type === "message") {
    // CLI responses are streamed directly via Admin API SSE
    // This worker just receives the messages (which are already streamed
    // to the client by the admin-api.ts SSE endpoint)
    // No action needed here - the daemon's bus event handling does the work
    return;
  }

  if (msg.type === "shutdown") {
    process.exit(0);
  }

  if (msg.type === "config:update") {
    pp.postMessage({ type: "message", payload: { info: "config updated" } });
    return;
  }
});
