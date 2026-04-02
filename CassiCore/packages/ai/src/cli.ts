#!/usr/bin/env node

import { existsSync, readFileSync, writeFileSync } from "fs";
import { createInterface } from "readline";
import { getOAuthProvider, getOAuthProviders } from "./utils/oauth/index.js";
import type { OAuthCredentials, OAuthProviderId } from "./utils/oauth/types.js";

const AUTH_FILE = "auth.json";
const PROVIDERS = getOAuthProviders();

/**
 * @dep callers: promptFn (ai/src/cli.ts), main (ai/src/cli.ts)
 * @dep module: Oauth
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function prompt(rl: ReturnType<typeof createInterface>, question: string): Promise<string> {
	return new Promise((resolve) => rl.question(question, resolve));
}

function loadAuth(): Record<string, { type: "oauth" } & OAuthCredentials> {
	if (!existsSync(AUTH_FILE)) return {};
	try {
		return JSON.parse(readFileSync(AUTH_FILE, "utf-8"));
	} catch {
		return {};
	}
}

function saveAuth(auth: Record<string, { type: "oauth" } & OAuthCredentials>): void {
	writeFileSync(AUTH_FILE, JSON.stringify(auth, null, 2), "utf-8");
}

/**
 * @dep callers: login (ai/src/cli.ts), main (ai/src/cli.ts)
 * @dep calls: getOAuthProvider, promptFn, login, saveAuth, loadAuth
 * @dep module: Oauth
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

async function login(providerId: OAuthProviderId): Promise<void> {
	const provider = getOAuthProvider(providerId);
	if (!provider) {
		console.error(`Unknown provider: ${providerId}`); // contributing:ignore - CLI error output
		process.exit(1);
	}

	const rl = createInterface({ input: process.stdin, output: process.stdout });
	const promptFn = (msg: string) => prompt(rl, `${msg} `);

	try {
		const credentials = await provider.login({
			onAuth: (info) => {
				console.log(`\nOpen this URL in your browser:\n${info.url}`); // contributing:ignore - CLI user output
				if (info.instructions) console.log(info.instructions); // contributing:ignore - CLI user output
				console.log(); // contributing:ignore - CLI formatting
			},
			onPrompt: async (p) => {
				return await promptFn(`${p.message}${p.placeholder ? ` (${p.placeholder})` : ""}:`);
			},
			onProgress: (msg) => console.log(msg), // contributing:ignore - CLI progress output
		});

		const auth = loadAuth();
		auth[providerId] = { type: "oauth", ...credentials };
		saveAuth(auth);

		console.log(`\nCredentials saved to ${AUTH_FILE}`); // contributing:ignore - CLI success message
	} finally {
		rl.close();
	}
}

async function main(): Promise<void> {
	const args = process.argv.slice(2);
	const command = args[0];

	if (!command || command === "help" || command === "--help" || command === "-h") {
		const providerList = PROVIDERS.map((p) => `  ${p.id.padEnd(20)} ${p.name}`).join("\n");
		console.log(`Usage: npx @cassicore/ai <command> [provider]

Commands:
  login [provider]  Login to an OAuth provider
  list              List available providers

Providers:
${providerList}

Examples:
  npx @cassicore/ai login              # interactive provider selection
  npx @cassicore/ai login anthropic    # login to specific provider
  npx @cassicore/ai list               # list providers
`); // contributing:ignore - CLI help output
		return;
	}

	if (command === "list") {
		console.log("Available OAuth providers:\n"); // contributing:ignore - CLI list output
		for (const p of PROVIDERS) {
			console.log(`  ${p.id.padEnd(20)} ${p.name}`); // contributing:ignore - CLI list output
		}
		return;
	}

	if (command === "login") {
		let provider = args[1] as OAuthProviderId | undefined;

		if (!provider) {
			const rl = createInterface({ input: process.stdin, output: process.stdout });
			console.log("Select a provider:\n"); // contributing:ignore - CLI prompt output
			for (let i = 0; i < PROVIDERS.length; i++) {
				console.log(`  ${i + 1}. ${PROVIDERS[i].name}`); // contributing:ignore - CLI list output
			}
			console.log(); // contributing:ignore - CLI formatting

			const choice = await prompt(rl, `Enter number (1-${PROVIDERS.length}): `);
			rl.close();

			const index = parseInt(choice, 10) - 1;
			if (index < 0 || index >= PROVIDERS.length) {
				console.error("Invalid selection"); // contributing:ignore - CLI error output
				process.exit(1);
			}
			provider = PROVIDERS[index].id;
		}

		if (!PROVIDERS.some((p) => p.id === provider)) {
			console.error(`Unknown provider: ${provider}`); // contributing:ignore - CLI error output
			console.error(`Use 'npx @cassicore/ai list' to see available providers`); // contributing:ignore - CLI error output
			process.exit(1);
		}

		console.log(`Logging in to ${provider}...`); // contributing:ignore - CLI status output
		await login(provider);
		return;
	}

	console.error(`Unknown command: ${command}`); // contributing:ignore - CLI error output
	console.error(`Use 'npx @cassicore/ai --help' for usage`); // contributing:ignore - CLI error output
	process.exit(1);
}

main().catch((err) => {
	console.error("Error:", err.message); // contributing:ignore - CLI error output
	process.exit(1);
});
