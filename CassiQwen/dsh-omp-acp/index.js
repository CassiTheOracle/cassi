/**
 * DeepSeek Harness plugin: the user's own oh-my-pi sessions, selectable as
 * models in any harness surface.
 *
 * The plugin owns no conversation state. It registers one `llm` provider route
 * whose model list is the live oh-my-pi session store, and continues whichever
 * session a request names through the Agent Client Protocol. With
 * `permission: "ask"` an oh-my-pi tool permission question becomes a harness
 * approval question, so the decision is taken in the harness window.
 *
 * @module dsh-omp-acp
 */
import { OmpAcpAdapter } from "./adapter.js";
import { OmpAcpSessions } from "./omp-sessions.js";

export const name = "dsh-omp-acp";
export const inject = ["llm"];

/**
 * Route an oh-my-pi permission question through the harness approval service.
 *
 * The question is asked for the exact harness session that started the turn, so
 * a connected surface answers it where the work is happening. Every failure
 * path returns `"unavailable"`, which the pool answers with its static allow
 * instead of blocking the session.
 *
 * @param {object} ctx - the plugin context.
 * @param {(level: string, message: string) => void} onLog - diagnostic sink.
 * @returns {((request: object) => Promise<string>) | undefined} the asker, or `undefined` when the harness exposes no approval service.
 */
function approvalAsker(ctx, onLog) {
  return async ({ harnessSessionId, toolName, reason, signal }) => {
    // Resolved per question, not at mount: the approval and agent services are
    // composed by other rows, and which of them exist is their business.
    const approval = ctx.approval;
    if (approval === undefined || typeof approval.request !== "function") return "unavailable";
    const agent = typeof ctx.agents?.get === "function" ? ctx.agents.get(harnessSessionId) : undefined;
    if (agent === undefined) {
      onLog("warn", `no harness agent for session ${harnessSessionId}; oh-my-pi permission question not asked`);
      return "unavailable";
    }
    try {
      const outcome = await approval.request({
        agent,
        toolName,
        ...(reason === undefined ? {} : { reason: `oh-my-pi: ${reason}` }),
        ...(signal === undefined ? {} : { signal }),
      });
      return typeof outcome === "string" ? outcome : "unavailable";
    } catch (error) {
      onLog("warn", `harness approval question failed: ${error instanceof Error ? error.message : String(error)}`);
      return "unavailable";
    }
  };
}

/**
 * Register the oh-my-pi provider route.
 *
 * @param {object} ctx - the plugin context.
 * @param {object} [config] - plugin configuration (see {@link OmpAcpSessions} and {@link OmpAcpAdapter}).
 * @returns {void}
 */
export function apply(ctx, config = {}) {
  const logger = typeof ctx.logger === "function" ? ctx.logger("omp-acp") : undefined;
  const onLog = (level, message) => {
    const write = typeof logger?.[level] === "function" ? logger[level].bind(logger) : logger?.info?.bind(logger);
    if (write !== undefined) write(message);
  };
  const provider = typeof config.provider === "string" && config.provider.length > 0 ? config.provider : "omp";
  const askPermission = config.permission === "ask" ? approvalAsker(ctx, onLog) : undefined;
  const sessions = new OmpAcpSessions({ ...config, onLog, ...(askPermission === undefined ? {} : { askPermission }) });
  const adapter = new OmpAcpAdapter(sessions, { ...config, onLog });
  const registration = ctx.llm.registerAdapter([provider], adapter);
  ctx.effect(() => () => {
    registration();
    sessions.dispose();
  }, "dsh-omp-acp");
}

export { OmpAcpAdapter } from "./adapter.js";
export { AcpConnection, AcpTransportError } from "./acp-client.js";
export { OmpAcpSessions, selectPermission } from "./omp-sessions.js";
