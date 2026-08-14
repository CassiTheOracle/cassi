#!/usr/bin/env node
/**
 * CassiCore Claude Code Hook — Command Wrapper
 *
 * A lightweight command hook that forwards requests to the HTTP hook server
 * (port 7434) and gracefully returns {} if the server is unavailable.
 *
 * This replaces the direct HTTP hook type to avoid errors when the hook
 * server isn't running. Claude Code shows errors for failed HTTP hooks
 * but treats command hooks returning {} as no-op.
 *
 * Usage in .claude/settings.json:
 *   { "type": "command", "command": "node <path>/hook-command.cjs", "timeout": 5000 }
 */

const http = require("node:http");
const fs = require("node:fs");

const PORT = parseInt(process.env.CASSICORE_HOOK_PORT || "7434", 10);
const HOST = "127.0.0.1";
const TIMEOUT_MS = 4000;

function readStdin() {
  try {
    return fs.readFileSync(0, "utf-8");
  } catch {
    return "{}";
  }
}

function forward(body) {
  return new Promise((resolve) => {
    const req = http.request(
      {
        hostname: HOST,
        port: PORT,
        method: "POST",
        path: "/",
        headers: {
          "content-type": "application/json",
          "content-length": Buffer.byteLength(body),
        },
        timeout: TIMEOUT_MS,
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          resolve(Buffer.concat(chunks).toString());
        });
      },
    );

    req.on("error", () => resolve("{}"));
    req.on("timeout", () => {
      req.destroy();
      resolve("{}");
    });

    req.write(body);
    req.end();
  });
}

async function main() {
  const input = readStdin();
  const result = await forward(input);
  process.stdout.write(result);
}

main().catch(() => {
  process.stdout.write("{}");
});
