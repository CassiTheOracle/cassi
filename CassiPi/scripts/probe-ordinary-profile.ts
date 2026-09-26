import { createHash } from "node:crypto";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { RpcClient } from "@oh-my-pi/pi-coding-agent/modes/rpc/rpc-client";

interface PluginRegistration {
  enabled?: boolean;
}

interface PluginRegistry {
  plugins?: Record<string, PluginRegistration>;
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

const root = resolve(import.meta.dir, "..");
const ompRoot = resolve(process.argv[2] ?? join(process.env.USERPROFILE ?? "C:/Users/Carina", ".omp"));
const agentDir = resolve(process.env.CASSIPI_ORDINARY_AGENT_DIR ?? join(ompRoot, "agent"));
const registryPath = join(ompRoot, "plugins", "omp-plugins.lock.json");
const host = process.env.CASSIPI_ORDINARY_OMP_BINARY ?? "C:/Users/Carina/.bun/bin/omp.exe";
const provider = join(root, "probes", "owner-mock-provider.ts");
const config = join(root, "probes", "ordinary-smoke-config.yml");
const runRoot = join(root, ".probe", "ordinary-profile");
const sessionDir = join(runRoot, "sessions");
const providerLog = join(runRoot, "provider.jsonl");

assert(existsSync(host), `ordinary OMP host is missing: ${host}`);
assert(existsSync(config), `ordinary smoke config is missing: ${config}`);
assert(existsSync(registryPath), `plugin registry is missing: ${registryPath}`);
const agentConfig = join(agentDir, "config.yml");
assert(existsSync(agentConfig), `ordinary agent config is missing: ${agentConfig}`);
const agentConfigSha256 = createHash("sha256").update(readFileSync(agentConfig)).digest("hex");
const registry = JSON.parse(readFileSync(registryPath, "utf8")) as PluginRegistry;
assert(registry.plugins?.["@cassi/cassipi"]?.enabled === false, "ordinary profile globally enabled CassiPi");
const remotePiEnabled = registry.plugins?.["remote-pi"]?.enabled === true;

rmSync(runRoot, { recursive: true, force: true });
const client = new RpcClient({
  command: [host],
  cwd: root,
  env: {
    PI_CODING_AGENT_DIR: agentDir,
    CASSIPI_OWNER_PROBE_API_KEY: "local-probe-only",
    CASSIPI_OWNER_PROBE_LOG: providerLog,
  },
  sessionDir,
  args: ["-e", provider, "--config", config],
});

try {
  await client.start();
  const models = await client.getAvailableModels();
  assert(
    models.some(model => model.provider === "cassipi-owner-probe" && model.id === "cassipi-owner-probe"),
    "ordinary profile did not load the local smoke provider",
  );
  await client.setModel("cassipi-owner-probe", "cassipi-owner-probe");
  await client.promptAndWait("ordinary active-profile smoke", undefined, 30_000);
  const providerEvents = readFileSync(providerLog, "utf8")
    .split(/\r?\n/u)
    .filter(Boolean)
    .map(line => JSON.parse(line) as { event?: string });
  assert(providerEvents.some(row => row.event === "provider_request"), "ordinary profile made no local provider request");
  console.log(JSON.stringify({
    schema: "cassipi.ordinary-profile-smoke.v1",
    cassipi_global_enabled: false,
    remote_pi_enabled: remotePiEnabled,
    local_provider_request: true,
    agent_dir: agentDir,
    agent_config_sha256: agentConfigSha256,
    config_overlay: config,
    verdict: "PASS",
  }, null, 2));
} finally {
  await client.stop();
  rmSync(runRoot, { recursive: true, force: true });
}
