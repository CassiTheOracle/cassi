import "./providers/register-builtins.js";
import "./utils/http-proxy.js";

import { getApiProvider } from "./api-registry.js";
import type {
	Api,
	AssistantMessage,
	AssistantMessageEventStream,
	Context,
	Model,
	ProviderStreamOptions,
	SimpleStreamOptions,
	StreamOptions,
} from "./types.js";

export { getEnvApiKey } from "./env-api-keys.js";

/**
 * @dep callers: streamSimple (ai/src/stream.ts), stream (ai/src/stream.ts)
 * @dep calls: getApiProvider
 * @dep module: Triad-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function resolveApiProvider(api: Api) {
	const provider = getApiProvider(api);
	if (!provider) {
		throw new Error(`No API provider registered for api: ${api}`);
	}
	return provider;
}

/**
 * @dep callers: complete (ai/src/stream.ts), stream (ai/src/stream.ts)
 * @dep calls: resolveApiProvider, stream
 * @dep module: Triad-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function stream<TApi extends Api>(
	model: Model<TApi>,
	context: Context,
	options?: ProviderStreamOptions,
): AssistantMessageEventStream {
	const provider = resolveApiProvider(model.api);
	return provider.stream(model, context, options as StreamOptions);
}

export async function complete<TApi extends Api>(
	model: Model<TApi>,
	context: Context,
	options?: ProviderStreamOptions,
): Promise<AssistantMessage> {
	const s = stream(model, context, options);
	return s.result();
}

/**
 * @dep callers: wrapStreamSimple (ai/src/api-registry.ts), completeSimple (ai/src/stream.ts), streamSimple (ai/src/stream.ts)
 * @dep calls: resolveApiProvider, streamSimple
 * @dep module: Triad-team
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function streamSimple<TApi extends Api>(
	model: Model<TApi>,
	context: Context,
	options?: SimpleStreamOptions,
): AssistantMessageEventStream {
	const provider = resolveApiProvider(model.api);
	return provider.streamSimple(model, context, options);
}

export async function completeSimple<TApi extends Api>(
	model: Model<TApi>,
	context: Context,
	options?: SimpleStreamOptions,
): Promise<AssistantMessage> {
	const s = streamSimple(model, context, options);
	return s.result();
}
