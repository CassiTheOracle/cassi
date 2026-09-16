import { createHash } from "node:crypto";
import { createReadStream, existsSync } from "node:fs";
import { join, resolve } from "node:path";

interface HostPin {
	package: {
		name: string;
		version: string;
		tarball: string;
		tarballIntegrity: string;
		installedPackageJsonSha256: string;
	};
	binary: { defaultPath: string; version: string; versionOutput: string; sha256: string };
}

interface PackageLock {
	packages: Record<string, { version?: string; resolved?: string; integrity?: string }>;
}

const root = resolve(import.meta.dir, "..");
const pin = (await Bun.file(join(root, "host", "upstream-18.1.10.json")).json()) as HostPin;
const lock = (await Bun.file(join(root, "package-lock.json")).json()) as PackageLock;
const packagePath = join(root, "node_modules", "@oh-my-pi", "pi-coding-agent", "package.json");
const binaryPath = process.env.CASSIPI_OMP_BINARY ?? pin.binary.defaultPath;

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

assert(existsSync(packagePath), `Pinned host package is not installed: ${packagePath}`);
assert(existsSync(binaryPath), `Pinned OMP binary is not installed: ${binaryPath}`);

const manifest = (await Bun.file(packagePath).json()) as { name?: string; version?: string };
assert(manifest.name === pin.package.name, `Wrong host package: ${manifest.name}`);
assert(manifest.version === pin.package.version, `Wrong host package version: ${manifest.version}`);
assert(
	(await sha256(packagePath)) === pin.package.installedPackageJsonSha256,
	"Installed host package manifest differs from the pinned npm artifact",
);

const locked = lock.packages[`node_modules/${pin.package.name}`];
assert(locked?.version === pin.package.version, `Lockfile does not pin ${pin.package.name}@${pin.package.version}`);
assert(locked.resolved === pin.package.tarball, "Lockfile host tarball URL differs from the pin");
assert(locked.integrity === pin.package.tarballIntegrity, "Lockfile host integrity differs from the pin");

const binaryHash = await sha256(binaryPath);
assert(binaryHash === pin.binary.sha256, `OMP binary hash mismatch: ${binaryHash}`);
const versionProcess = Bun.spawn([binaryPath, "--version"], { stdout: "pipe", stderr: "pipe" });
const [stdout, stderr, exitCode] = await Promise.all([
	new Response(versionProcess.stdout).text(),
	new Response(versionProcess.stderr).text(),
	versionProcess.exited,
]);
assert(exitCode === 0, `OMP --version failed: ${stderr.trim()}`);
assert(stdout.trim() === pin.binary.versionOutput, `OMP binary version mismatch: ${stdout.trim()}`);

console.log(
	JSON.stringify(
		{
			package: `${manifest.name}@${manifest.version}`,
			packageIntegrity: locked.integrity,
			binaryPath,
			binaryVersion: stdout.trim(),
			binarySha256: binaryHash,
		},
		null,
		2,
	),
);
