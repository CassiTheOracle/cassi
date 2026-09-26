import { createHash } from "node:crypto";
import { createReadStream, existsSync } from "node:fs";
import { join, resolve } from "node:path";

interface ReleaseManifest {
  schema?: string;
  artifacts?: Record<string, { sha256?: string }>;
  host?: {
    binary_sha256?: string;
    package_version?: string;
    patch_sha256?: string;
    patched_source_identity?: string;
    upstream_commit?: string;
    upstream_tree?: string;
  };
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

async function sha256(path: string): Promise<string> {
  const hash = createHash("sha256");
  await new Promise<void>((resolvePromise, reject) => {
    const input = createReadStream(path);
    input.on("data", chunk => hash.update(chunk));
    input.on("error", reject);
    input.on("end", resolvePromise);
  });
  return hash.digest("hex");
}

const root = resolve(import.meta.dir, "..");
const releaseRoot = resolve(process.env.CASSIPI_RELEASE_ROOT ?? join(root, "dist"));
const manifestPath = join(releaseRoot, "release-manifest.json");
const binaryPath = join(releaseRoot, "omp-cassipi-18.1.10-win-x64.exe");
const patchPath = join(releaseRoot, "oh-my-pi-18.1.10-context-owner.patch");
assert(existsSync(manifestPath), `release manifest is missing: ${manifestPath}`);
assert(existsSync(binaryPath), `patched release host is missing: ${binaryPath}`);
assert(existsSync(patchPath), `context-owner patch is missing: ${patchPath}`);
const manifest = await Bun.file(manifestPath).json() as ReleaseManifest;
assert(manifest.schema === "cassipi.private-release.v1", `unexpected release schema: ${manifest.schema}`);
assert(manifest.host?.package_version === "18.1.10", `unexpected patched host package: ${manifest.host?.package_version}`);
assert(
  manifest.artifacts?.["omp-cassipi-18.1.10-win-x64.exe"]?.sha256 === manifest.host.binary_sha256,
  "release artifact and host binary hashes disagree",
);
assert(
  manifest.artifacts?.["oh-my-pi-18.1.10-context-owner.patch"]?.sha256 === manifest.host.patch_sha256,
  "release artifact and host patch hashes disagree",
);
assert(/^[0-9a-f]{64}$/u.test(manifest.host.patched_source_identity ?? ""), "patched source identity is missing");
assert(/^[0-9a-f]{40}$/u.test(manifest.host.upstream_commit ?? ""), "upstream commit identity is missing");
assert(/^[0-9a-f]{40}$/u.test(manifest.host.upstream_tree ?? ""), "upstream tree identity is missing");
const binaryHash = await sha256(binaryPath);
assert(binaryHash === manifest.host.binary_sha256, `patched host hash mismatch: ${binaryHash}`);
const patchHash = await sha256(patchPath);
assert(patchHash === manifest.host.patch_sha256, `context-owner patch hash mismatch: ${patchHash}`);
const patchedSourceIdentity = createHash("sha256").update(JSON.stringify({
  patch_sha256: patchHash,
  upstream_commit: manifest.host.upstream_commit,
})).digest("hex");
assert(
  patchedSourceIdentity === manifest.host.patched_source_identity,
  `patched source identity mismatch: ${patchedSourceIdentity}`,
);
const child = Bun.spawn([binaryPath, "--version"], { stdout: "pipe", stderr: "pipe" });
const [stdout, stderr, exitCode] = await Promise.all([
  new Response(child.stdout).text(),
  new Response(child.stderr).text(),
  child.exited,
]);
assert(exitCode === 0, `patched host --version failed: ${stderr.trim()}`);
assert(stdout.trim() === "omp/18.1.10", `unexpected patched host version: ${stdout.trim()}`);
console.log(JSON.stringify({
  schema: manifest.schema,
  binary: binaryPath,
  binary_sha256: binaryHash,
  patch: patchPath,
  patch_sha256: patchHash,
  patched_source_identity: patchedSourceIdentity,
  version: stdout.trim(),
  verdict: "PASS",
}, null, 2));
