import { createHash } from "node:crypto";
import { readFile, realpath, stat } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";

const DEFAULT_MAX_SOURCE_BYTES = 1_048_576;
const DEFAULT_MAX_READ_BYTES = 8_192;
const MAX_PATH_BYTES = 4_096;

function numericLimit(value, fallback, maximum, label) {
  if (value === undefined) return fallback;
  if (!Number.isInteger(value) || value < 1) throw new RangeError(`${label} must be a positive integer`);
  return Math.min(value, maximum);
}

function inside(root, target) {
  const remainder = relative(root, target);
  return remainder === "" || (!remainder.startsWith(`..${sep}`) && remainder !== ".." && !isAbsolute(remainder));
}

function configuredRoot(value) {
  if (typeof value !== "string" || !value.trim()) throw new TypeError("sourceRoots must contain non-empty paths");
  if (Buffer.byteLength(value, "utf8") > MAX_PATH_BYTES) throw new RangeError("source root path is too long");
  return { configured: value, absolute: resolve(value) };
}

export function normalizeSourceRoots(sourceRoots) {
  if (sourceRoots === undefined) return [];
  if (!Array.isArray(sourceRoots)) throw new TypeError("sourceRoots must be an array");
  const roots = [];
  const seen = new Set();
  for (const value of sourceRoots) {
    const root = configuredRoot(value);
    if (seen.has(root.absolute)) continue;
    seen.add(root.absolute);
    roots.push(root);
  }
  return roots;
}

async function resolveSource(requestedPath, roots) {
  if (typeof requestedPath !== "string" || !requestedPath.trim()) throw new TypeError("path must be non-empty text");
  if (Buffer.byteLength(requestedPath, "utf8") > MAX_PATH_BYTES) throw new RangeError("path is too long");
  if (isAbsolute(requestedPath)) throw new Error("path must be relative to a configured source root");
  const matches = [];
  for (const root of roots) {
    const candidate = resolve(root.absolute, requestedPath);
    if (!inside(root.absolute, candidate)) continue;
    let target;
    try {
      target = await realpath(candidate);
    } catch (error) {
      if (error?.code === "ENOENT" || error?.code === "ENOTDIR") continue;
      throw error;
    }
    let realRoot;
    try {
      realRoot = await realpath(root.absolute);
    } catch (error) {
      if (error?.code === "ENOENT" || error?.code === "ENOTDIR") continue;
      throw error;
    }
    if (!inside(realRoot, target)) continue;
    const metadata = await stat(target);
    if (!metadata.isFile()) continue;
    matches.push({
      sourceRoot: root.configured,
      sourcePath: relative(realRoot, target).split(sep).join("/"),
      target,
      size: metadata.size,
    });
  }
  if (matches.length === 0) throw new Error("path is unavailable in the configured source scope");
  if (matches.length > 1) throw new Error("path is ambiguous across configured source roots");
  return matches[0];
}

export async function readScopedSource({
  path,
  startByte = 0,
  maxBytes,
  sourceRoots,
  maxSourceBytes = DEFAULT_MAX_SOURCE_BYTES,
  maxReadBytes = DEFAULT_MAX_READ_BYTES,
  signal,
}) {
  const roots = normalizeSourceRoots(sourceRoots);
  if (roots.length === 0) throw new Error("no source roots are configured for Harness reads");
  if (!Number.isInteger(startByte) || startByte < 0) throw new RangeError("start_byte must be a nonnegative integer");
  const sourceLimit = numericLimit(maxSourceBytes, DEFAULT_MAX_SOURCE_BYTES, DEFAULT_MAX_SOURCE_BYTES, "maxSourceBytes");
  const readLimit = numericLimit(maxReadBytes, DEFAULT_MAX_READ_BYTES, DEFAULT_MAX_READ_BYTES, "maxReadBytes");
  const requestedLimit = maxBytes === undefined
    ? readLimit
    : numericLimit(maxBytes, readLimit, readLimit, "max_bytes");
  const source = await resolveSource(path, roots);
  if (source.size > sourceLimit) throw new RangeError(`source exceeds the ${sourceLimit}-byte Harness limit`);
  const bytes = await readFile(source.target, { signal });
  if (bytes.byteLength !== source.size) throw new Error("source changed while it was being read");
  if (startByte > bytes.byteLength) throw new RangeError("start_byte is beyond the source length");
  const selected = bytes.subarray(startByte, Math.min(startByte + requestedLimit, bytes.byteLength));
  return {
    schema: "cassi.harness.source-read.v1",
    source_root: source.sourceRoot,
    source_path: source.sourcePath,
    source_sha256: createHash("sha256").update(bytes).digest("hex"),
    source_byte_length: bytes.byteLength,
    byte_start: startByte,
    byte_end: startByte + selected.byteLength,
    content_sha256: createHash("sha256").update(selected).digest("hex"),
    bytes_read: selected.byteLength,
    truncated: startByte + selected.byteLength < bytes.byteLength,
    content_base64: Buffer.from(selected).toString("base64"),
    text: Buffer.from(selected).toString("utf8"),
    text_encoding: "utf-8-with-replacement",
  };
}

export const SOURCE_READ_LIMITS = Object.freeze({
  maxSourceBytes: DEFAULT_MAX_SOURCE_BYTES,
  maxReadBytes: DEFAULT_MAX_READ_BYTES,
});
