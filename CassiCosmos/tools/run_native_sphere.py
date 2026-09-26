"""Run the preregistered native-sphere arms, one windowed Godot process at a time."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import queue
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "research/stellar_cells/native_sphere_spec.json"
PREREG = ROOT / "research/stellar_cells/native_sphere_prereg.md"
ENGINE = ROOT / "scripts/cassi_physics_engine.gd"
GODOT = Path("C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe")
FREEZE_BODY = """func mesh_rebuild_due() -> bool:
\tif not meshless_mode or not _ml_ready:
\t\treturn false
\tif _rd_global:
\t\t_mesh_rebuild_pending = false
\t\treturn false
\tif freeze_field:
\t\treturn false
\treturn _step_count % ML_REBUILD == 13"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def source_closure() -> dict[str, str]:
    pending = [ENGINE, ROOT / "scripts/cassi_tree_consts.gd", ROOT / "scripts/probe_native_sphere.gd"]
    found: dict[str, str] = {}
    while pending:
        path = pending.pop()
        relative = path.relative_to(ROOT).as_posix()
        if relative in found:
            continue
        data = path.read_bytes()
        found[relative] = digest(data)
        for resource in re.findall(r'res://([^\s"\'()]+\.(?:gd|glsl))', data.decode("utf-8")):
            candidate = ROOT / resource
            if candidate.is_file():
                pending.append(candidate)
        if path.suffix == ".glsl":
            imported = path.with_suffix(path.suffix + ".import")
            if not imported.is_file():
                raise RuntimeError(f"Missing shader import metadata: {relative}; import once before campaign")
            for resource in re.findall(r'path="res://([^"]+)"', imported.read_text(encoding="utf-8")):
                compiled = ROOT / resource
                if not compiled.is_file():
                    raise RuntimeError(f"Missing compiled shader: {resource}")
                found[resource] = digest(compiled.read_bytes())
    for path in [SPEC, PREREG, ROOT / "tools/run_native_sphere.py", ROOT / "scenes/probe_native_sphere.tscn"]:
        found[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
    return dict(sorted(found.items()))


def assert_no_godot() -> None:
    result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Godot*", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, check=True)
    for row in csv.reader(result.stdout.splitlines()):
        if row and row[0].lower().startswith("godot"):
            raise RuntimeError("A Godot editor/runtime is already active; not starting a competing GPU process: " + str(row[:2]))


def exact_replace(text: str, before: str, after: str, changes: list[dict[str, str]]) -> str:
    if text.count(before) != 1:
        raise RuntimeError("Source-bound variant anchor is not unique: " + before)
    changes.append({"before": before, "after": after})
    return text.replace(before, after, 1)


def engine_variant(campaign: Path, config: dict) -> tuple[Path, dict]:
    original = ENGINE.read_text(encoding="utf-8")
    text = original
    changes: list[dict[str, str]] = []
    text = exact_replace(text, FREEZE_BODY,
                         "func mesh_rebuild_due() -> bool:\n\t# Registered fixed geometry after the complete native setup.\n\treturn false", changes)
    n1 = int(config["site_lattice_n1"])
    if n1 != 16:
        text = exact_replace(text, "const ML_N1 := 16", f"const ML_N1 := {n1}", changes)
    for anchor, expression in [
        ("_site_physics_pc_bytes.encode_float(16, site_spacing * site_spacing)",
         f"_site_physics_pc_bytes.encode_float(16, site_spacing * site_spacing * {float(config['c2_multiplier'])!r})"),
        ("_site_physics_pc_bytes.encode_float(20, ML_OM2)",
         f"_site_physics_pc_bytes.encode_float(20, ML_OM2 * {float(config['conversion_multiplier'])!r})"),
        ("_site_physics_pc_bytes.encode_float(56, 0.001 * site_cell_volume)",
         f"_site_physics_pc_bytes.encode_float(56, 0.001 * site_cell_volume * {float(config['mass_source_multiplier'])!r})"),
    ]:
        multiplier = expression.rsplit(" * ", 1)[1].removesuffix(")")
        if float(multiplier) != 1.0:
            text = exact_replace(text, anchor, expression, changes)
    # Reverse the complete declared edits; any undeclared source change is rejected.
    reversed_text = text
    for item in reversed(changes):
        if reversed_text.count(item["after"]) != 1:
            raise RuntimeError("Variant reverse check is ambiguous")
        reversed_text = reversed_text.replace(item["after"], item["before"], 1)
    if reversed_text != original:
        raise RuntimeError("Variant differs beyond registered source substitutions")
    encoded = text.encode("utf-8")
    variant_dir = campaign / "variants"
    variant_dir.mkdir(exist_ok=True)
    path = variant_dir / ("engine_" + digest(encoded)[:16] + ".gd")
    if path.exists() and path.read_bytes() != encoded:
        raise RuntimeError("Existing engine variant bytes changed")
    if not path.exists():
        path.write_bytes(encoded)
    receipt = {"canonical_source_sha256": digest(ENGINE.read_bytes()),
               "variant_sha256": digest(encoded), "changes": changes,
               "reverse_exactness": True, "path": path.relative_to(ROOT).as_posix()}
    save_json(path.with_suffix(".json"), receipt)
    return path, receipt


def run_child(args: list[str], log_path: Path, timeout: float) -> tuple[int, bool]:
    assert_no_godot()
    lines: queue.Queue[str | None] = queue.Queue()
    process = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    def collect() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    start = time.monotonic()
    timed_out = False
    stream_ended = False
    with log_path.open("w", encoding="utf-8") as log:
        while not stream_ended or process.poll() is None:
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                line = ""
            if line is None:
                stream_ended = True
            elif line:
                log.write(line)
                log.flush()
                if "[NativeSphere]" in line or "ERROR" in line or "Error" in line:
                    print(line.rstrip(), flush=True)
                if ("SCRIPT ERROR:" in line or "Parse Error:" in line or "Failed to load script" in line) and process.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, text=True, check=False)
                    break
            if process.poll() is None and time.monotonic() - start > timeout:
                timed_out = True
                # This PID is the Popen-owned live wrapper, never a discovered editor.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, text=True, check=False)
                break
        returncode = process.wait(timeout=30)
        while not lines.empty():
            line = lines.get_nowait()
            if line:
                log.write(line)
    reader.join(timeout=5)
    return returncode, timed_out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--arm", action="append", default=[])
    parser.add_argument("--godot", type=Path, default=GODOT)
    parser.add_argument("--import-first", action="store_true")
    args = parser.parse_args()
    campaign = args.out.resolve()
    campaign.relative_to(ROOT)  # engine variants must remain within the Godot project.
    campaign.mkdir(parents=True, exist_ok=True)
    if args.import_first:
        code, timed_out = run_child([str(args.godot), "--headless", "--path", str(ROOT), "--import"],
                                   campaign / "import.log", 240)
        if code or timed_out:
            raise RuntimeError("Godot import did not complete cleanly")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    source_hashes = source_closure()
    source_hashes["godot_executable"] = digest(args.godot.read_bytes())
    manifest_path = campaign / "campaign.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["source_hashes"] != source_hashes:
            raise RuntimeError("Campaign source closure changed; preserve this campaign and use a new output directory")
    else:
        manifest = {"schema": "cassi_native_sphere_campaign_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                    "source_hashes": source_hashes, "spec": spec, "runs": [], "complete": False}
        save_json(manifest_path, manifest)
        (campaign / "preregistration.md").write_bytes(PREREG.read_bytes())
        save_json(campaign / "spec.json", spec)
    ids = {arm["id"] for arm in spec["arms"]}
    if set(args.arm) - ids:
        raise ValueError("Unregistered arm selection: " + str(set(args.arm) - ids))
    failures = 0
    for arm in spec["arms"]:
        if args.arm and arm["id"] not in args.arm:
            continue
        config = {**spec["defaults"], **arm}
        out = campaign / config["id"]
        receipt_path = out / "receipt.json"
        if receipt_path.is_file():
            old = json.loads(receipt_path.read_text(encoding="utf-8"))
            if old.get("status") == "COMPLETE" and old.get("completed_steps") == config["target_steps"]:
                print("[NativeSphere] RETAIN completed " + config["id"], flush=True)
                continue
        if out.exists():
            attempts = campaign / "attempts"
            attempts.mkdir(exist_ok=True)
            out.rename(attempts / (config["id"] + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")))
        out.mkdir()
        variant, variant_receipt = engine_variant(campaign, config)
        relative_variant = "res://" + variant.relative_to(ROOT).as_posix()
        input_path = out / "input.json"
        save_json(input_path, {"config": config, "out_dir": out.as_posix(),
                               "engine_variant": relative_variant,
                               "source_hashes": {**source_hashes, "engine_variant": variant_receipt["variant_sha256"]}})
        command = [str(args.godot), "--path", str(ROOT), "--resolution", "640x360", "--disable-vsync",
                   "--max-fps", "0", "res://scenes/probe_native_sphere.tscn", "--", "--input=" + input_path.as_posix()]
        started = time.monotonic()
        print("[NativeSphere] LAUNCH " + config["id"], flush=True)
        code, timed_out = run_child(command, out / "godot.log", float(config["wall_timeout_seconds"]) + 60)
        stable = all((ROOT / path).is_file() and digest((ROOT / path).read_bytes()) == expected
                     for path, expected in source_hashes.items() if path != "godot_executable")
        record = {"id": config["id"], "returncode": code, "watchdog_timeout": timed_out,
                  "runtime_seconds": time.monotonic() - started, "source_closure_unchanged": stable,
                  "variant": variant_receipt, "command": command}
        manifest["runs"].append(record)
        save_json(manifest_path, manifest)
        if code or timed_out or not stable or not receipt_path.is_file():
            failures += 1
            print("[NativeSphere] ARM_FAILED " + config["id"], flush=True)
        if not stable:
            raise RuntimeError("Source changed while arm was executing; no mixed-source continuation")
    complete = True
    for arm in spec["arms"]:
        path = campaign / arm["id"] / "receipt.json"
        if not path.is_file() or json.loads(path.read_text(encoding="utf-8")).get("status") != "COMPLETE":
            complete = False
    manifest["complete"] = complete
    save_json(manifest_path, manifest)
    print(f"[NativeSphere] CAMPAIGN complete={complete} failures_this_launch={failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
