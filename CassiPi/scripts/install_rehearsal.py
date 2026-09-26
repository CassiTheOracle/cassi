from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
from typing import Any, Sequence
import uuid


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = "cassipi-rehearsal"
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_root(profile_name: str) -> Path:
    if not PROFILE_RE.fullmatch(profile_name) or profile_name in {".", ".."}:
        raise RuntimeError("profile name must use only letters, numbers, dots, underscores, and hyphens")
    return Path.home() / ".omp" / "profiles" / profile_name


def _load_release(release_root: Path) -> tuple[Path, Path, str, str]:
    manifest_path = release_root / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "cassipi.private-release.v1":
        raise RuntimeError("release manifest schema is incompatible")
    artifacts = manifest.get("artifacts")
    host_manifest = manifest.get("host")
    if not isinstance(artifacts, dict) or not isinstance(host_manifest, dict):
        raise RuntimeError("release manifest has no artifact or host map")
    plugin_names = [name for name in artifacts if name.endswith(".tgz")]
    host_names = [name for name in artifacts if name.endswith(".exe")]
    patch_names = [name for name in artifacts if name.endswith(".patch")]
    if len(plugin_names) != 1 or len(host_names) != 1 or len(patch_names) != 1:
        raise RuntimeError("release must contain exactly one plugin, host binary, and context-owner patch")
    plugin = release_root / plugin_names[0]
    host = release_root / host_names[0]
    patch = release_root / patch_names[0]
    for path in (plugin, host, patch):
        row = artifacts.get(path.name)
        if not path.is_file() or not isinstance(row, dict) or _sha256(path) != row.get("sha256"):
            raise RuntimeError(f"release artifact failed identity verification: {path.name}")
    host_binary_sha256 = _sha256(host)
    patch_sha256 = _sha256(patch)
    if host_binary_sha256 != host_manifest.get("binary_sha256"):
        raise RuntimeError("release host binary disagrees with host identity")
    if patch_sha256 != host_manifest.get("patch_sha256"):
        raise RuntimeError("release patch disagrees with host identity")
    upstream_commit = host_manifest.get("upstream_commit")
    if not isinstance(upstream_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", upstream_commit):
        raise RuntimeError("release upstream commit identity is incompatible")
    patched_source_identity = hashlib.sha256(
        json.dumps(
            {"patch_sha256": patch_sha256, "upstream_commit": upstream_commit},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if patched_source_identity != host_manifest.get("patched_source_identity"):
        raise RuntimeError("release patched source identity is incompatible")
    return plugin, host, patch_sha256, patched_source_identity


def _run(arguments: Sequence[str], *, profile_name: str | None) -> Any:
    environment = dict(os.environ)
    if profile_name is None:
        environment.pop("OMP_PROFILE", None)
    else:
        environment["OMP_PROFILE"] = profile_name
    environment.pop("PI_PROFILE", None)
    environment.pop("PI_CODING_AGENT_DIR", None)
    completed = subprocess.run(
        list(arguments),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise RuntimeError(f"{Path(arguments[0]).name} failed: {detail}")
    output = completed.stdout.strip()
    return json.loads(output) if output else None


def _extract_plugin(archive_path: Path, profile_root: Path) -> Path:
    staging = profile_root / f".cassipi-package-staging-{uuid.uuid4().hex}"
    destination = profile_root / "local-plugins" / "cassipi"
    backup = profile_root / f".cassipi-package-backup-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    moved = False
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            if not members or any(
                (
                    member.name.replace("\\", "/") != "package"
                    and not member.name.replace("\\", "/").startswith("package/")
                )
                or ".." in PurePosixPath(member.name.replace("\\", "/")).parts
                or member.issym()
                or member.islnk()
                for member in members
            ):
                raise RuntimeError("plugin archive contains an unsafe member")
            archive.extractall(staging, filter="data")
        extracted = staging / "package"
        if not (extracted / "package.json").is_file():
            raise RuntimeError("plugin archive has no package/package.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            os.replace(destination, backup)
            moved = True
        os.replace(extracted, destination)
        if moved:
            shutil.rmtree(backup)
        return destination
    except BaseException:
        if moved and not destination.exists() and backup.exists():
            os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and destination.exists():
            shutil.rmtree(backup)


def install(
    release_root: Path,
    profile_name: str,
    *,
    reuse: bool,
    main_profile: bool = False,
) -> dict[str, Any]:
    release_root = release_root.resolve()
    plugin, host, host_patch_sha256, host_patched_source_identity = _load_release(release_root)
    profile_root = Path.home() / ".omp" if main_profile else _profile_root(profile_name)
    runtime_profile = None if main_profile else profile_name
    if profile_root.exists() and any(profile_root.iterdir()) and not reuse:
        raise RuntimeError("profile already exists; pass --reuse only for an intentional rehearsal upgrade")
    profile_root.mkdir(parents=True, exist_ok=True)
    main_config = profile_root / "agent" / "config.yml"
    main_config_existed_before = main_config.is_file() if main_profile else False
    main_config_sha256_before = (
        _sha256(main_config) if main_profile and main_config_existed_before else None
    )

    plugin_directory = _extract_plugin(plugin, profile_root)
    runtime_root = plugin_directory / "fi-runtime"
    if not (runtime_root / "runtime-manifest.json").is_file():
        raise RuntimeError("installed plugin has no verified FI runtime manifest")
    data_home = profile_root / "cassipi"
    data_home.mkdir(parents=True, exist_ok=True)
    profile_id = "omp-profile:main" if main_profile else f"omp-profile:{profile_name}"
    install_result = _run(
        [str(host), "plugin", "install", str(plugin_directory), "--json"],
        profile_name=runtime_profile,
    )
    registry_disable_result = (
        _run(
            [str(host), "plugin", "disable", "@cassi/cassipi", "--json"],
            profile_name=runtime_profile,
        )
        if main_profile
        else None
    )
    profile_settings: dict[str, Any] = {
        "memory.backend": "off",
        "autolearn.enabled": False,
        "autolearn.autoContinue": False,
        "compaction.enabled": True,
        "compaction.methodOrder": ["soft"],
        "compaction.asyncEnabled": False,
        "compaction.autoContinue": False,
        "compaction.idleEnabled": False,
        "compaction.midTurnEnabled": True,
        "compaction.dropUseless": False,
        "compaction.supersedeReads": False,
        # The host's threshold must clear the floor it cannot summarize: the fixed
        # provider overhead (system prompt plus tool catalog, ~22k tokens) plus the
        # field summary the owner writes (~4k tokens). A threshold at the floor makes
        # the host compact, find nothing left to summarize, and drop the pending turn
        # without an error. 60000 leaves room for a pending prompt at any window size.
        "compaction.thresholdTokens": 60000,
        "compaction.reserveTokens": 4000,
        # The owner supplies the thread: its projection carries field-selected
        # evidence and the pending turn is protected natively, so the host keeps
        # only a token tail of raw history verbatim.
        "compaction.keepRecentTokens": 64,
        "startup.setupWizard": False,
        "startup.showSplash": False,
    }
    if main_profile:
        context_owner_result = {"key": "context.owner", "value": "cassipi", "location": "launcher-overlay"}
        owner_overlay = profile_root / "cassipi-owner.json"
        overlay_config: dict[str, Any] = {"context": {"owner": "cassipi"}}
        for dotted_key, value in profile_settings.items():
            section, key = dotted_key.split(".", maxsplit=1)
            overlay_config.setdefault(section, {})[key] = value
        owner_overlay.write_text(
            json.dumps(overlay_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (profile_root / "cassipi-owner.yml").unlink(missing_ok=True)
        applied_settings: dict[str, Any] = {}
    else:
        context_owner_result = _run(
            [str(host), "config", "set", "context.owner", "cassipi", "--json"],
            profile_name=runtime_profile,
        )
        owner_overlay = None
        applied_settings = {}
        for key, expected in profile_settings.items():
            argument = expected if isinstance(expected, str) else json.dumps(expected, separators=(",", ":"))
            applied_settings[key] = _run(
                [str(host), "config", "set", key, argument, "--json"],
                profile_name=runtime_profile,
            )
            observed = _run(
                [str(host), "config", "get", key, "--json"],
                profile_name=runtime_profile,
            )
            if observed.get("value") != expected:
                raise RuntimeError(f"profile did not persist {key}={expected!r}")

    plugins = _run([str(host), "plugin", "list", "--json"], profile_name=runtime_profile)
    encoded_plugins = json.dumps(plugins, sort_keys=True)
    plugin_rows = plugins.get("npm")
    if not isinstance(plugin_rows, list):
        raise RuntimeError("plugin list omitted npm registry rows")
    cassipi_rows = [
        row for row in plugin_rows
        if isinstance(row, dict) and row.get("name") == "@cassi/cassipi"
    ]
    if len(cassipi_rows) != 1:
        raise RuntimeError("installed profile does not list exactly one CassiPi plugin")
    if main_profile and cassipi_rows[0].get("enabled") is not False:
        raise RuntimeError("main profile must keep CassiPi disabled in the global registry")
    remote_rows = [
        row for row in plugin_rows
        if isinstance(row, dict) and row.get("name") == "remote-pi" and row.get("enabled") is True
    ]
    if not main_profile and remote_rows:
        raise RuntimeError("named rehearsal profile unexpectedly enabled the global remote-pi plugin")

    profile_host = profile_root / "bin" / "omp-cassipi.exe"
    profile_host.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(host, profile_host)
    launcher = profile_root / "launch-cassipi.cmd"
    launcher_profile = (
        "set OMP_PROFILE=\r\n"
        "set PI_PROFILE=\r\n"
        f'set "PI_CODING_AGENT_DIR={profile_root / "agent"}"\r\n'
        if main_profile
        else (
            f'set "OMP_PROFILE={profile_name}"\r\n'
            "set PI_PROFILE=\r\n"
            "set PI_CODING_AGENT_DIR=\r\n"
        )
    )
    launcher_extensions = (
        f'--config "{owner_overlay}" --no-extensions '
        f'-e "{plugin_directory / "src" / "index.ts"}" '
        if main_profile
        else ""
    )
    launcher.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f"{launcher_profile}"
        f'set "CASSIPI_PROFILE_ID={profile_id}"\r\n'
        f'set "CASSIPI_DATA_HOME={data_home}"\r\n'
        f'set "CASSIPI_FI_RUNTIME={runtime_root}"\r\n'
        f'"{profile_host}" {launcher_extensions}%*\r\n',
        encoding="utf-8",
    )
    if main_profile:
        global_launcher = Path.home() / ".bun" / "bin" / "cassipi.cmd"
        global_launcher.parent.mkdir(parents=True, exist_ok=True)
        global_launcher.write_text(
            "@echo off\r\n"
            f'call "{launcher}" %*\r\n',
            encoding="utf-8",
        )
    else:
        global_launcher = None
    main_config_existed_after = main_config.is_file() if main_profile else False
    main_config_sha256_after = (
        _sha256(main_config) if main_profile and main_config_existed_after else None
    )
    if main_profile and (
        main_config_existed_after != main_config_existed_before
        or main_config_sha256_after != main_config_sha256_before
    ):
        raise RuntimeError("main-profile installation changed agent/config.yml")

    receipt = {
        "schema": "cassipi.rehearsal-install.v1",
        "profile_name": "main" if main_profile else profile_name,
        "profile_root": str(profile_root),
        "context_owner": "launcher-overlay" if main_profile else "cassipi",
        "cassi_profile_id": profile_id,
        "cassi_data_home": str(data_home),
        "cassi_runtime_root": str(runtime_root),
        "plugin_sha256": _sha256(plugin),
        "main_registry_enabled": False if main_profile else cassipi_rows[0].get("enabled"),
        "launcher_loads_cassipi_explicitly": main_profile,
        "launcher_disables_global_extensions": main_profile,
        "ordinary_remote_pi_enabled": bool(remote_rows) if main_profile else False,
        "registry_disable_result": registry_disable_result,
        "owner_overlay": None if owner_overlay is None else str(owner_overlay),
        "owner_overlay_sha256": None if owner_overlay is None else _sha256(owner_overlay),
        "profile_settings_location": "launcher-overlay" if main_profile else "named-profile",
        "ordinary_main_settings_unchanged": main_profile,
        "ordinary_main_config_existed_before": main_config_existed_before if main_profile else None,
        "ordinary_main_config_existed_after": main_config_existed_after if main_profile else None,
        "ordinary_main_config_sha256_before": main_config_sha256_before,
        "ordinary_main_config_sha256_after": main_config_sha256_after,
        "startup_setup_wizard": False,
        "startup_show_splash": False,
        "profile_settings": profile_settings,
        "host_binary_sha256": _sha256(host),
        "host_patch_sha256": host_patch_sha256,
        "host_patched_source_identity": host_patched_source_identity,
        "release_manifest_sha256": _sha256(release_root / "release-manifest.json"),
        "upgrade_rehearsal": reuse,
        "plugin_list_sha256": hashlib.sha256(encoded_plugins.encode("utf-8")).hexdigest(),
        "launcher_global_plugins_loaded": False if main_profile else None,
        "launcher": str(launcher),
        "global_launcher": None if global_launcher is None else str(global_launcher),
        "global_launcher_sha256": None if global_launcher is None else _sha256(global_launcher),
        "launcher_sha256": _sha256(launcher),
        "install_result": install_result,
        "config_result": context_owner_result,
    }
    (profile_root / "cassipi-install-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install CassiPi into an isolated named Oh My Pi profile")
    parser.add_argument("--release", type=Path, default=ROOT / "dist")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument(
        "--main",
        action="store_true",
        help="install into the main ~/.omp profile while retaining unrelated plugins",
    )
    parser.add_argument("--reuse", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = install(args.release, args.profile, reuse=args.reuse, main_profile=args.main)
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError, tarfile.TarError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
