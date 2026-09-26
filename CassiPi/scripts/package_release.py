from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Sequence
import uuid


ROOT = Path(__file__).resolve().parents[1]
FI_RUNTIME = ROOT.parent / "CassiFI" / "runtime"
sys.path.insert(0, str(FI_RUNTIME))

from build_cassipi_runtime import verify_runtime  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(arguments: Sequence[str], *, cwd: Path) -> str:
    command = list(arguments)
    executable = shutil.which(command[0])
    if executable is None:
        raise RuntimeError(f"required executable is unavailable: {command[0]}")
    if Path(executable).suffix.lower() in {".bat", ".cmd"}:
        executable_path = Path(executable)
        node = executable_path.with_name("node.exe")
        npm_cli = executable_path.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if executable_path.name.lower() != "npm.cmd" or not node.is_file() or not npm_cli.is_file():
            raise RuntimeError(f"unsupported command wrapper: {executable_path}")
        command = [str(node), str(npm_cli), *command[1:]]
    else:
        command[0] = executable
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _artifact(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": _sha256(path)}


def _package_members(package_path: Path, runtime_manifest: dict[str, Any]) -> list[str]:
    with tarfile.open(package_path, "r:gz") as archive:
        names = sorted(
            member.name.replace("\\", "/")
            for member in archive.getmembers()
            if member.isfile()
        )
    expected = {
        "package/package.json",
        "package/fi-runtime/runtime-manifest.json",
        *{
            f"package/src/{path.relative_to(ROOT / 'src').as_posix()}"
            for path in (ROOT / "src").rglob("*")
            if path.is_file()
        },
        *{
            f"package/fi-runtime/{row['path']}"
            for row in runtime_manifest["files"]
        },
    }
    if (ROOT / "README.md").is_file():
        expected.add("package/README.md")
    actual = set(names)
    if actual != expected:
        raise RuntimeError(
            "plugin artifact violates its exact source/runtime allowlist: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return names


def _install_tree(staging: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    moved = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved = True
        os.replace(staging, destination)
        if moved:
            shutil.rmtree(backup)
    except BaseException:
        if moved and not destination.exists() and backup.exists():
            os.replace(backup, destination)
        raise
    finally:
        if backup.exists() and destination.exists():
            shutil.rmtree(backup)


def package_release(destination: Path) -> dict[str, Any]:
    destination = destination.resolve()
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    if package_json.get("omp", {}).get("extensions") != ["./src/index.ts"]:
        raise RuntimeError("CassiPi must expose exactly one omp.extensions entry")

    runtime = verify_runtime(ROOT / "fi-runtime")
    runtime_manifest = runtime["manifest"]
    runtime_manifest_sha256 = _sha256(ROOT / "fi-runtime" / "runtime-manifest.json")
    # Exercising the runtime writes Python bytecode caches next to the modules. They
    # are not source, npm keeps them when a directory is listed in `files`, and the
    # allowlist check below rejects them, so prune them before packing.
    for cache in list((ROOT / "fi-runtime").rglob("__pycache__")) + list((ROOT / "src").rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)
    upstream_path = ROOT / "host" / "upstream-18.1.10.json"
    upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
    pinned_package = upstream["package"]
    upstream_checkout = ROOT / ".host-work" / "upstream"
    patched_checkout = ROOT / ".host-work" / "patched"
    patch_path = ROOT / "host" / "patches" / "oh-my-pi-18.1.10-context-owner.patch"
    host_binary = patched_checkout / "packages" / "coding-agent" / "dist" / "omp.exe"
    if not host_binary.is_file():
        raise RuntimeError("compatible host binary is missing; run the pinned host build first")

    actual_commit = _run(["git", "rev-parse", "HEAD"], cwd=upstream_checkout)
    actual_tree = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=upstream_checkout)
    if actual_commit != pinned_package["gitCommit"]:
        raise RuntimeError("upstream checkout does not match the pinned host commit")
    _run(["git", "apply", "--check", str(patch_path)], cwd=upstream_checkout)

    staging_parent = Path(tempfile.mkdtemp(prefix=".cassipi-release-", dir=destination.parent))
    staging = staging_parent / "release"
    staging.mkdir()
    try:
        packed = json.loads(
            _run(
                ["npm", "pack", "--json", "--ignore-scripts", "--pack-destination", str(staging)],
                cwd=ROOT,
            )
        )
        if isinstance(packed, dict):
            packed_rows = list(packed.values())
        elif isinstance(packed, list):
            packed_rows = packed
        else:
            packed_rows = []
        if (
            len(packed_rows) != 1
            or not isinstance(packed_rows[0], dict)
            or not isinstance(packed_rows[0].get("filename"), str)
        ):
            raise RuntimeError("npm pack returned an unexpected result")
        plugin_path = staging / packed_rows[0]["filename"]
        members = _package_members(plugin_path, runtime_manifest)

        runtime_manifest_path = staging / "cassipi-fi-runtime-manifest.json"
        shutil.copy2(ROOT / "fi-runtime" / "runtime-manifest.json", runtime_manifest_path)
        release_patch_path = staging / patch_path.name
        shutil.copy2(patch_path, release_patch_path)
        release_upstream_path = staging / upstream_path.name
        shutil.copy2(upstream_path, release_upstream_path)
        release_host_path = staging / "omp-cassipi-18.1.10-win-x64.exe"
        shutil.copy2(host_binary, release_host_path)

        artifact_paths = [
            plugin_path,
            runtime_manifest_path,
            release_patch_path,
            release_upstream_path,
            release_host_path,
        ]
        patch_sha256 = _sha256(patch_path)
        patched_source_identity = hashlib.sha256(
            json.dumps(
                {"patch_sha256": patch_sha256, "upstream_commit": actual_commit},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        manifest = {
            "schema": "cassipi.private-release.v1",
            "package": {
                "name": package_json["name"],
                "version": package_json["version"],
                "omp_extensions": package_json["omp"]["extensions"],
                "members_sha256": hashlib.sha256("\n".join(members).encode("utf-8")).hexdigest(),
            },
            "runtime": {
                "runtime_id": runtime_manifest["runtime_id"],
                "closure_sha256": runtime_manifest["closure_sha256"],
                "manifest_sha256": runtime_manifest_sha256,
            },
            "host": {
                "package_version": pinned_package["version"],
                "upstream_commit": actual_commit,
                "upstream_tree": actual_tree,
                "patch_sha256": patch_sha256,
                "patched_source_identity": patched_source_identity,
                "binary_platform": "windows-x64",
                "binary_sha256": _sha256(host_binary),
            },
            "artifacts": {path.name: _artifact(path) for path in artifact_paths},
        }
        manifest_path = staging / "release-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _install_tree(staging, destination)
        return {
            "status": "PASS",
            "release_root": str(destination),
            "release_manifest_sha256": _sha256(destination / "release-manifest.json"),
            "plugin_artifact": plugin_path.name,
            "host_binary_sha256": manifest["host"]["binary_sha256"],
            "runtime_manifest_sha256": runtime_manifest_sha256,
        }
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the private CassiPi release artifacts")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)
    try:
        result = package_release(args.output)
    except (OSError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
