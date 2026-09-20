import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { CassiEntityClient, CassiEntityHttpError, stableRequestId } from "./entity-client.js";
import { CassiEntityAdapter } from "./adapter.js";

export const name = "cassi-dsh-entity";
export const inject = ["connection", "tools", "llm"];

const NO_ARGS = {};

function readToken(config) {
  if (typeof config.token === "string" && config.token.length >= 32) return config.token;
  const envName = typeof config.tokenEnv === "string" && config.tokenEnv ? config.tokenEnv : "CASSI_ENTITY_API_TOKEN";
  const fromEnv = process.env[envName];
  if (typeof fromEnv === "string" && fromEnv.length >= 32) return fromEnv.trim();
  const fileName = typeof config.tokenFile === "string" && config.tokenFile ? config.tokenFile : process.env.CASSI_ENTITY_TOKEN_FILE;
  if (fileName) {
    const fromFile = readFileSync(fileName, "utf8").trim();
    if (fromFile.length >= 32) return fromFile;
  }
  throw new Error(`Cassi entity token is unavailable; set ${envName} or configure tokenFile`);
}

function projectScope(config, value) {
  const project = value ?? config.projectId ?? "cassi-workspace";
  if (typeof project !== "string" || !project.trim()) throw new TypeError("project_id must be non-empty text");
  const allowed = Array.isArray(config.allowedProjectIds) && config.allowedProjectIds.length ? config.allowedProjectIds : [config.projectId ?? "cassi-workspace"];
  if (!allowed.includes(project)) throw new Error(`project_id ${JSON.stringify(project)} is outside the configured Cassi scope`);
  return project;
}

function callId(exec, fallback) {
  const source = typeof exec?.callId === "string" && exec.callId ? exec.callId : randomUUID();
  return stableRequestId(`dsh-tool:${fallback}`, source);
}

function internalError(error) {
  return {
    ok: false,
    error: {
      code: "internal",
      message: error instanceof Error ? error.message : String(error),
      details: {},
    },
  };
}

function routePayload(payload) {
  if (payload === undefined || payload === null) return {};
  if (typeof payload !== "object" || Array.isArray(payload)) throw new TypeError("Cassi RPC payload must be an object");
  return payload;
}

function tool(name, description, parameters, execute) {
  return defineTool({
    name,
    description,
    parameters,
    output: {
      schema: { type: "json" },
      render: (_args, value) => [{ type: "text", text: JSON.stringify(value, null, 2) }],
    },
    execute,
    presentCall: (args) => ({ card: "generic", title: name, kind: "other", rawInput: args }),
  });
}

export function apply(ctx, config = {}) {
  const client = new CassiEntityClient({
    baseUrl: config.baseUrl ?? "http://127.0.0.1:8090",
    token: readToken(config),
    maxEvidenceBytes: config.maxEvidenceBytes,
  });
  const adapter = new CassiEntityAdapter(client, config);
  ctx.connection.rpc.handle(
      "/cassi",
      async (endpoint, payload, signal) => {
        try {
          const body = routePayload(payload);
          switch (endpoint) {
            case "state": return { ok: true, value: await client.state(signal) };
            case "health": return { ok: true, value: await client.health(signal) };
            case "research/status": return { ok: true, value: await client.researchStatus(signal) };
            case "research/capabilities": return { ok: true, value: await client.researchCapabilities(signal) };
            case "programs": return { ok: true, value: await client.listPrograms(signal) };
            case "program": return { ok: true, value: await client.getProgram(body.program_id, signal) };
            case "evidence": return { ok: true, value: await client.readEvidence(body.sha256, body.max_bytes, signal) };
            default: throw new Error(`unknown Cassi RPC endpoint ${JSON.stringify(endpoint)}`);
          }
        } catch (error) {
          return internalError(error);
        }
      },
      { authority: "loopback" },
    );
  ctx.llm.registerAdapter(["cassi-entity"], adapter);

  ctx.tools.register(tool(
      "cassi_entity_status",
      "Read the continuing Cassi entity identity, field revision, and research director status.",
      NO_ARGS,
      async (_args, exec) => ({
        state: await client.state(exec.signal),
        research: await client.researchStatus(exec.signal),
      }),
    ));

  ctx.tools.register(tool(
      "cassi_list_programs",
      "List the continuing entity's field-backed research programs.",
      NO_ARGS,
      async (_args, exec) => client.listPrograms(exec.signal),
    ));

  ctx.tools.register(tool(
      "cassi_read_program",
      "Read one field-backed research program by durable identifier.",
      { program_id: { type: "string", required: true } },
      async (args, exec) => client.getProgram(args.program_id, exec.signal),
    ));

  ctx.tools.register(tool(
      "cassi_admit_program",
      "Admit a bounded research mission into the continuing Cassi entity.",
      {
        title: { type: "string", required: true },
        mission: { type: "string", required: true },
        initial_question: { type: "string", required: true },
        cycle_limit: { type: "integer" },
        project_id: { type: "string" },
      },
      async (args, exec) => {
        const projectId = projectScope(config, args.project_id);
        const programId = `dsh-program:${randomUUID()}`;
        return client.admitProgram({
          requestId: callId(exec, "admit"),
          programId,
          projectId,
          title: args.title,
          mission: args.mission,
          initialQuestion: args.initial_question,
          cycleLimit: args.cycle_limit ?? config.cycleLimit,
          allowedRoots: config.allowedRoots ?? [],
          allowedTools: config.allowedTools ?? [],
          networkHosts: config.networkHosts ?? [],
          signal: exec.signal,
        });
      },
    ));

  ctx.tools.register(tool(
      "cassi_add_guidance",
      "Add owner guidance to an existing Cassi research program.",
      { program_id: { type: "string", required: true }, content: { type: "string", required: true } },
      async (args, exec) => client.addGuidance({ requestId: callId(exec, "guidance"), programId: args.program_id, content: args.content, signal: exec.signal }),
    ));

  ctx.tools.register(tool(
      "cassi_control_program",
      "Pause, resume, wake, complete, or cancel an existing Cassi research program.",
      {
        program_id: { type: "string", required: true },
        action: { type: "string", required: true, enum: ["pause", "resume", "wake", "complete", "cancel"] },
        message: { type: "string" },
      },
      async (args, exec) => client.controlProgram({ requestId: callId(exec, "control"), programId: args.program_id, action: args.action, message: args.message, signal: exec.signal }),
    ));

  ctx.tools.register(tool(
      "cassi_read_evidence",
      "Read a bounded immutable Cassi evidence artifact by its SHA-256 digest.",
      { sha256: { type: "string", required: true }, max_bytes: { type: "integer" } },
      async (args, exec) => client.readEvidence(args.sha256, args.max_bytes, exec.signal),
    ));
}

export { CassiEntityAdapter, CassiEntityClient, CassiEntityHttpError, stableRequestId };
