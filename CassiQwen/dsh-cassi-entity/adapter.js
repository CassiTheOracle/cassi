import { LlmAdapter, LlmError } from "@deepseek-ai/dsh-llm";
import { stableRequestId } from "./entity-client.js";

function messageText(message) {
  if (!message || message.role !== "user" || !Array.isArray(message.content)) return "";
  return message.content
    .filter((block) => block?.type === "text" && typeof block.text === "string")
    .map((block) => block.text)
    .join("\n")
    .trim();
}

function auxiliaryPrompt(options) {
  const system = typeof options.system === "string" ? options.system : "";
  const messages = Array.isArray(options.messages) ? options.messages : [];
  return [
    "You are Cassi's live pretrained brain serving a non-learning Harness auxiliary request.",
    "Do not update field memory, create commitments, claim external actions, or treat this request as a user turn.",
    `PURPOSE: ${options.purpose}`,
    system ? `SYSTEM:\n${system}` : "",
    `MESSAGES:\n${JSON.stringify(messages, null, 2)}`,
  ].filter(Boolean).join("\n\n");
}

function sessionKey(value) {
  return typeof value === "string" && value ? value : "default";
}
function tokenUsage(raw) {
  if (!raw || typeof raw !== "object") return undefined;
  const input = Number(raw.input_tokens ?? raw.prompt_tokens);
  const output = Number(raw.output_tokens ?? raw.completion_tokens);
  if (!Number.isFinite(input) || !Number.isFinite(output) || input < 0 || output < 0) return undefined;
  return {
    inputTokens: input,
    outputTokens: output,
    ...(Number.isFinite(Number(raw.cache_read_tokens)) ? { cacheReadTokens: Number(raw.cache_read_tokens) } : {}),
    ...(Number.isFinite(Number(raw.cache_write_tokens)) ? { cacheWriteTokens: Number(raw.cache_write_tokens) } : {}),
    ...(Number.isFinite(Number(raw.reasoning_tokens)) ? { reasoningTokens: Number(raw.reasoning_tokens) } : {}),
  };
}

function pendingToolFromReplay(message) {
  const response = message?.source?.replayState?.response;
  if (!response || response.status !== "awaiting-tool") return undefined;
  const pending = response.pendingTool;
  if (
    typeof response.turnId !== "string" ||
    typeof response.requestId !== "string" ||
    !pending ||
    typeof pending.call_id !== "string" ||
    typeof pending.name !== "string" ||
    !pending.arguments ||
    typeof pending.arguments !== "object" ||
    Array.isArray(pending.arguments)
  ) {
    throw new LlmError("Cassi entity replay state has an invalid pending tool", "INVALID_REPLAY_STATE");
  }
  return { response, pending };
}

function toolResultFromMessage(message, callId) {
  if (message?.role !== "user" && message?.role !== "tool") return undefined;
  return (Array.isArray(message.content) ? message.content : [])
    .find((block) => block?.type === "tool-result" && block.toolCallId === callId);
}

function findToolContinuation(messages) {
  const list = Array.isArray(messages) ? messages : [];
  for (let assistantIndex = list.length - 1; assistantIndex >= 0; assistantIndex -= 1) {
    const assistant = list[assistantIndex];
    const replay = pendingToolFromReplay(assistant);
    if (!replay) continue;
    for (let index = assistantIndex + 1; index < list.length; index += 1) {
      const message = list[index];
      const result = toolResultFromMessage(message, replay.pending.call_id);
      if (!result) continue;
      for (let later = index + 1; later < list.length; later += 1) {
        if (list[later]?.role !== "user") continue;
        const blocks = Array.isArray(list[later].content) ? list[later].content : [];
        if (blocks.some((block) => block?.type !== "tool-result")) return undefined;
      }
      return { ...replay, result };
    }
    return undefined;
  }
  return undefined;
}

function payloadFrom(admission, events) {
  const committed = [...events].reverse().find((event) => event.kind === "turn-committed");
  const failed = [...events].reverse().find((event) => event.kind === "turn-failed");
  return {
    committed,
    failed,
    payload: committed?.data?.payload ?? committed?.data ?? admission,
  };
}

export class CassiEntityAdapter extends LlmAdapter {
  constructor(client, {
    projectId = "cassi-workspace",
    modelId = "cassi-entity",
    modelName = "Cassi — Continuing Entity",
    contextWindow = 32_768,
    defaultMaxTokens = 2_048,
  } = {}) {
    super();
    this.client = client;
    this.projectId = projectId;
    this.modelId = modelId;
    this.modelName = modelName;
    this.contextWindow = contextWindow;
    this.defaultMaxTokens = defaultMaxTokens;
  }

  providerInfo(provider) {
    return { id: provider, name: "Cassi — Continuing Entity" };
  }

  async listModels(provider) {
    return [{
      provider,
      id: this.modelId,
      name: this.modelName,
      description: "One continuing field-backed Cassi entity; current brain identity is reported by the entity service.",
      inputModalities: ["text"],
    }];
  }

  async resolveModel(provider, model) {
    return {
      provider,
      id: model || this.modelId,
      name: this.modelName,
      description: "One continuing field-backed Cassi entity; current brain identity is reported by the entity service.",
      inputModalities: ["text"],
      context: { contextWindow: this.contextWindow },
      defaultMaxTokens: this.defaultMaxTokens,
    };
  }

  async *stream(options) {
    if (options.purpose) {
      const purpose = options.purpose;
      const requestId = stableRequestId("dsh-auxiliary", {
        purpose,
        sessionId: sessionKey(options.sessionId),
        system: options.system ?? "",
        messages: options.messages ?? [],
      });
      const auxiliary = await this.client.auxiliary({
        requestId,
        purpose,
        prompt: auxiliaryPrompt(options),
        maxTokens: options.maxTokens ?? 256,
        signal: options.signal,
      });
      const text = typeof auxiliary.response === "string" ? auxiliary.response.trim() : "";
      if (!text) {
        throw new LlmError("Cassi entity returned no auxiliary response", "EMPTY_AUXILIARY_RESPONSE");
      }
      yield { type: "block-start", index: 0, blockType: "text" };
      yield { type: "text-delta", index: 0, text };
      yield { type: "block-end", index: 0, block: { type: "text", text } };
      const usage = tokenUsage(auxiliary.usage);
      if (usage) yield { type: "usage", usage };
      yield { type: "finish", reason: { kind: "stop" } };
      return;
    }
    const continuation = findToolContinuation(options.messages);
    let admission;
    let events;
    let turnId;
    let requestId;
    if (continuation) {
      const { response, pending, result } = continuation;
      turnId = response.turnId;
      requestId = response.requestId;
      const toolRequestId = stableRequestId("dsh-tool-result", {
        turnId,
        callId: pending.call_id,
        name: pending.name,
        arguments: pending.arguments,
        content: result.content,
        isError: result.isError === true,
      });
      admission = await this.client.submitTurnToolResults({
        turnId,
        requestId: toolRequestId,
        results: [{
          call_id: result.toolCallId,
          name: pending.name,
          arguments: pending.arguments,
          content: result.content,
          is_error: result.isError === true,
        }],
        signal: options.signal,
      });
      events = await this.client.turnEvents(turnId, { after: 0, signal: options.signal });
    } else {
      const latest = [...(options.messages ?? [])].reverse().find((message) => (
        message?.role === "user" && (
          message.source === undefined ||
          message.source?.kind === "user"
        )
      ));
      const content = messageText(latest);
      if (!latest || !content) {
        throw new LlmError("Cassi entity requires a non-empty newest user message", "EMPTY_REQUEST");
      }
      const session = sessionKey(options.sessionId == null ? undefined : String(options.sessionId));
      const identity = {
        session,
        messageId: String(latest.id ?? content),
        content,
        projectId: this.projectId,
      };
      const conversationId = `dsh:${session}`;
      requestId = stableRequestId("dsh-message", identity);
      turnId = stableRequestId("dsh-turn", identity);
      admission = await this.client.createTurn({
        turnId,
        requestId,
        conversationId,
        projectId: this.projectId,
        content,
        kind: "user-message",
        source: {
          kind: "harness-user",
          session_id: session,
          message_id: identity.messageId,
        },
        toolCatalog: options.tools ?? [],
        hostScope: {
          provider: options.provider,
          model: options.model,
        },
        signal: options.signal,
      });
      events = await this.client.turnEvents(turnId, { after: 0, signal: options.signal });
    }
    const { failed, payload } = payloadFrom(admission, events);
    if (admission.status === "failed" || failed) {
      const message = admission.error?.message ?? failed?.data?.payload?.error?.message ?? "Cassi typed turn failed";
      throw new LlmError(message, admission.error?.code ?? "ENTITY_TURN_FAILED");
    }
    const status = payload.status ?? admission.status;
    const usage = tokenUsage(payload.usage);
    if (status === "awaiting-tool") {
      const pending = payload.pending_tool;
      if (
        !pending ||
        typeof pending.call_id !== "string" ||
        typeof pending.name !== "string" ||
        !pending.arguments ||
        typeof pending.arguments !== "object" ||
        Array.isArray(pending.arguments)
      ) {
        throw new LlmError("Cassi entity returned an invalid pending tool", "INVALID_TOOL_PROPOSAL");
      }
      const argumentsText = JSON.stringify(pending.arguments);
      yield { type: "block-start", index: 0, blockType: "tool-call" };
      yield {
        type: "tool-call-delta",
        index: 0,
        id: pending.call_id,
        name: pending.name,
        argumentsDelta: argumentsText,
      };
      yield {
        type: "block-end",
        index: 0,
        block: {
          type: "tool-call",
          id: pending.call_id,
          name: pending.name,
          arguments: argumentsText,
        },
      };
      if (usage) yield { type: "usage", usage };
      yield {
        type: "finish",
        reason: { kind: "tool-calls" },
        replayState: {
          response: {
            turnId,
            requestId,
            status,
            pendingTool: pending,
            model: payload.model ?? admission.model,
            fieldStateSha256: payload.field_state_sha256 ?? admission.field_state_sha256,
            eventCursor: events.at(-1)?.id ?? null,
          },
        },
      };
      return;
    }
    const text = typeof payload.response === "string" ? payload.response.trim() : "";
    if (status !== "committed" || !text) {
      throw new LlmError("Cassi entity returned no committed typed-turn response", "EMPTY_RESPONSE");
    }
    yield { type: "block-start", index: 0, blockType: "text" };
    yield { type: "text-delta", index: 0, text };
    yield { type: "block-end", index: 0, block: { type: "text", text } };
    if (usage) yield { type: "usage", usage };
    yield {
      type: "finish",
      reason: { kind: "stop" },
      replayState: {
        response: {
          turnId,
          requestId,
          status,
          model: payload.model ?? admission.model,
          fieldStateSha256: payload.field_state_sha256 ?? admission.field_state_sha256,
          eventCursor: events.at(-1)?.id ?? null,
        },
      },
    };
  }
}
