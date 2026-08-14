import { MODELS } from "./models.generated.js";
export { MODELS } from "./models.generated.js";
import type { Api, KnownProvider, Model, Usage } from "./types.js";

const modelRegistry: Map<string, Map<string, Model<Api>>> = new Map();

// Initialize registry from MODELS on module load
for (const [provider, models] of Object.entries(MODELS)) {
	const providerModels = new Map<string, Model<Api>>();
	for (const [id, model] of Object.entries(models)) {
		providerModels.set(id, model as Model<Api>);
	}
	modelRegistry.set(provider, providerModels);
}

type ModelApi<
	TProvider extends keyof typeof MODELS,
	TModelId extends keyof (typeof MODELS)[TProvider],
> = (typeof MODELS)[TProvider][TModelId] extends { api: infer TApi } ? (TApi extends Api ? TApi : never) : never;

/**
 * @dep callers: ai-model-defaults.test.ts (tests/ai-model-defaults.test.ts), fromRegistry (core/intelligence/triad-team/model-capabilities.ts)
 * @dep calls: get
 * @dep module: Triad-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function getModel<TProvider extends keyof typeof MODELS, TModelId extends keyof (typeof MODELS)[TProvider]>(
	provider: TProvider,
	modelId: TModelId,
): Model<ModelApi<TProvider, TModelId>> {
	const providerModels = modelRegistry.get(provider);
	return providerModels?.get(modelId as string) as Model<ModelApi<TProvider, TModelId>>;
}

/**
 * @dep callers: ai-model-defaults.test.ts (tests/ai-model-defaults.test.ts), handleModelsRoutes (core/admin-api/models.ts), handleProvidersRoutes (core/admin-api/providers.ts)
 * @dep module: Providers
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function getProviders(): KnownProvider[] {
	return Array.from(modelRegistry.keys()) as KnownProvider[];
}

/**
 * @dep callers: ai-model-defaults.test.ts (tests/ai-model-defaults.test.ts), enableAllGitHubCopilotModels (ai/src/utils/oauth/github-copilot.ts)
 * @dep calls: get
 * @dep module: Oauth
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function getModels<TProvider extends keyof typeof MODELS>(
	provider: TProvider,
): Model<ModelApi<TProvider, keyof (typeof MODELS)[TProvider]>>[] {
	const models = modelRegistry.get(provider);
	return models ? (Array.from(models.values()) as Model<ModelApi<TProvider, keyof (typeof MODELS)[TProvider]>>[]) : [];
}

/**
 * @dep callers: ai-model-defaults.test.ts (tests/ai-model-defaults.test.ts), streamOpenAICompletions (ai/src/providers/openai-completions.ts), processResponsesStream (ai/src/providers/openai-responses-shared.ts), handleMetadata (ai/src/providers/amazon-bedrock.ts), streamAnthropic (ai/src/providers/anthropic.ts) [+3]
 * @dep module: Providers
 * @dep risk: HIGH | 8 callers, 0 flows, 1 module
 */

export function calculateCost<TApi extends Api>(model: Model<TApi>, usage: Usage): Usage["cost"] {
	usage.cost.input = (model.cost.input / 1000000) * usage.input;
	usage.cost.output = (model.cost.output / 1000000) * usage.output;
	usage.cost.cacheRead = (model.cost.cacheRead / 1000000) * usage.cacheRead;
	usage.cost.cacheWrite = (model.cost.cacheWrite / 1000000) * usage.cacheWrite;
	usage.cost.total = usage.cost.input + usage.cost.output + usage.cost.cacheRead + usage.cost.cacheWrite;
	return usage.cost;
}

/**
 * Check if a model supports xhigh thinking level.
 *
 * Supported today:
 * - GPT-5.2 / GPT-5.3 model families
 * - Anthropic Messages API Opus 4.6 models (xhigh maps to adaptive effort "max")
 * @dep callers: ai-model-defaults.test.ts (tests/ai-model-defaults.test.ts), streamSimpleOpenAICompletions (ai/src/providers/openai-completions.ts), streamSimpleOpenAIResponses (ai/src/providers/openai-responses.ts), streamSimpleAzureOpenAIResponses (ai/src/providers/azure-openai-responses.ts), streamSimpleOpenAICodexResponses (ai/src/providers/openai-codex-responses.ts)
 * @dep module: Providers
 * @dep risk: MEDIUM | 5 callers, 0 flows, 1 module
 */
export function supportsXhigh<TApi extends Api>(model: Model<TApi>): boolean {
	if (model.id.includes("gpt-5.2") || model.id.includes("gpt-5.3")) {
		return true;
	}

	if (model.api === "anthropic-messages") {
		return model.id.includes("opus-4-6") || model.id.includes("opus-4.6");
	}

	return false;
}

/**
 * Check if two models are equal by comparing both their id and provider.
 * Returns false if either model is null or undefined.
 */
export function modelsAreEqual<TApi extends Api>(
	a: Model<TApi> | null | undefined,
	b: Model<TApi> | null | undefined,
): boolean {
	if (!a || !b) return false;
	return a.id === b.id && a.provider === b.provider;
}
