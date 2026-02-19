import { parentPort } from "node:worker_threads";

if (!parentPort) {
  throw new Error("echo-channel must be run in a worker_threads context");
}
const pp = parentPort;

pp.on("message", (msg: { type: string; [k: string]: unknown }) => {
  if (msg.type === "init") {
    // announce ready
    pp.postMessage({ type: "ready" });
    console.log("echo-channel ready");
    return;
  }

  if (msg.type === "message") {
    const payload = msg.payload;
    if (typeof payload === "string") {
      if (payload === "crash") {
        throw new Error("deliberate crash — testing recovery");
      }
      pp.postMessage({ type: "message", payload: `echo: ${payload}` });
    } else {
      pp.postMessage({ type: "message", payload: `echo: ${String(payload)}` });
    }
    return;
  }

  if (msg.type === "shutdown") {
    process.exit(0);
  }

  if (msg.type === "config:update") {
    // for this simple worker, accept config but do nothing
    pp.postMessage({ type: "message", payload: { info: "config updated" } });
    return;
  }
});
