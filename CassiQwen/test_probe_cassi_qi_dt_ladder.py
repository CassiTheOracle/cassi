#!/usr/bin/env python3
"""Focused coverage for the dt-ladder comparator.

The comparator is the part of the probe that can lie: its first version here
read the answer text from guessed keys, found none of them, compared the empty
string against itself, and reported 34/34 identical completions for a campaign
whose field arm had actually moved four answers.  These tests fire that failure
mode instead of trusting the shape of a receipt.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from probe_cassi_qi_dt_ladder import (
    arm_rows,
    compare_runs,
    compare_table,
    implementation_manifest,
    row_text,
    server_argv,
    write_implementation_sidecar,
)

CASES = ("case-a", "case-b", "case-c")


class ServerArgvContract(unittest.TestCase):
    """The launch receipt is the record of the measured configuration, so a flag the
    caller sets must reach argv and a flag the caller leaves unset must stay absent."""

    def test_substitute_and_injection_scale_reach_the_launch_argv(self) -> None:
        argv = server_argv(Path("m.gguf"), port=8084, layer=32, scales=4, displacement=3, dt=0.005,
                           substitute=1.0, injection_scale=0.0)
        self.assertEqual(argv[argv.index("--cassi-qi-substitute") + 1], "1.0")
        self.assertEqual(argv[argv.index("--cassi-qi-injection-scale") + 1], "0.0")
        self.assertEqual(argv[argv.index("--cassi-qi-displacement") + 1], "3")

    def test_an_unset_injection_scale_leaves_the_engine_default_alone(self) -> None:
        argv = server_argv(Path("m.gguf"), port=8084, layer=32, scales=4, displacement=3, dt=0.005,
                           substitute=0.5)
        self.assertNotIn("--cassi-qi-injection-scale", argv)
        self.assertNotIn("--cassi-qi-substitute", server_argv(
            Path("m.gguf"), port=8084, layer=32, scales=4, displacement=3, dt=0.005))


def write_receipt(run_dir: Path, *, texts: dict[str, str], passes: dict[str, bool]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "id": case,
            "raw_output": texts[case],
            "answer_pass": passes[case],
            "usage": {"completion_tokens": 10},
        }
        for case in CASES
    ]
    for arm in ("baseline", "field"):
        (run_dir / f"{arm}.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")


def write_legacy_receipt(run_dir: Path) -> None:
    """A receipt whose rows carry only grading, no text."""
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [{"id": case, "answer_pass": True, "usage": {"completion_tokens": 10}} for case in CASES]
    for arm in ("baseline", "field"):
        (run_dir / f"{arm}.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")


class ComparatorTests(unittest.TestCase):
    def test_text_change_is_reported_even_when_the_score_holds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, run = root / "ref", root / "run"
            write_receipt(ref, texts={"case-a": "1", "case-b": "2", "case-c": "3"},
                          passes={"case-a": True, "case-b": True, "case-c": False})
            write_receipt(run, texts={"case-a": "1", "case-b": "2 changed", "case-c": "3"},
                          passes={"case-a": True, "case-b": True, "case-c": False})
            receipt = compare_runs(ref, [run])
            entry = receipt["arms"]["field"]["runs"]["run"]
            self.assertEqual(entry["changed"], ["case-b"])
            self.assertEqual(entry["text_identical"], 2)
            self.assertEqual(entry["passes"], 2)
            self.assertEqual(receipt["arms"]["field"]["ref_passes"], 2)

    def test_missing_text_is_refused_instead_of_compared_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, run = root / "ref", root / "run"
            write_legacy_receipt(ref)
            write_legacy_receipt(run)
            with self.assertRaises(KeyError):
                compare_runs(ref, [run])
            with self.assertRaises(KeyError):
                row_text({"id": "case-a", "answer": "1"})

    def test_missing_case_is_flagged_not_silently_equal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, run = root / "ref", root / "run"
            write_receipt(ref, texts={"case-a": "1", "case-b": "2", "case-c": "3"},
                          passes={"case-a": True, "case-b": True, "case-c": True})
            write_receipt(run, texts={"case-a": "1", "case-b": "2", "case-c": "3"},
                          passes={"case-a": True, "case-b": True, "case-c": True})
            rows = json.loads((run / "field.json").read_text(encoding="utf-8"))
            rows["rows"] = [row for row in rows["rows"] if row["id"] != "case-c"]
            (run / "field.json").write_text(json.dumps(rows), encoding="utf-8")
            entry = compare_runs(ref, [run])["arms"]["field"]["runs"]["run"]
            self.assertEqual(entry["missing"], ["case-c"])
            self.assertEqual(entry["cases"], 2)
            self.assertEqual(arm_rows(run, "field").keys(), {"case-a", "case-b"})


class ImplementationManifestTests(unittest.TestCase):
    def test_manifest_pins_every_sibling_and_fires_on_a_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "llama-server.exe"
            binary.write_bytes(b"stub")
            for name in ("llama-server-impl.dll", "llama.dll"):
                (root / name).write_bytes(b"implementation")
            before = implementation_manifest(binary, ("llama-server-impl.dll", "llama.dll", "absent.dll"))
            self.assertEqual(sorted(before), ["llama-server-impl.dll", "llama-server.exe", "llama.dll"])
            self.assertEqual(before["llama.dll"]["bytes"], len(b"implementation"))
            (root / "llama.dll").write_bytes(b"implementation rebuilt")
            after = implementation_manifest(binary, ("llama-server-impl.dll", "llama.dll", "absent.dll"))
            self.assertNotEqual(before["llama.dll"]["sha256"], after["llama.dll"]["sha256"])
            self.assertEqual(before["llama-server-impl.dll"], after["llama-server-impl.dll"])


class ReferenceManifestTests(unittest.TestCase):
    def test_ref_implementation_comes_from_the_reference_dir_not_a_reconstructed_path(self) -> None:
        """The table used to rebuild `_diag/<ref>`, so a reference outside `_diag`
        printed "unrecorded" while its sidecar sat right there."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, run = root / "elsewhere" / "ref", root / "run"
            build = root / "bin"
            build.mkdir(parents=True)
            binary = build / "llama-server.exe"
            binary.write_bytes(b"stub")
            (build / "llama.dll").write_bytes(b"implementation")
            rows = [{"id": "case-a", "raw_output": "1", "answer_pass": True, "usage": {"completion_tokens": 5}}]
            for target in (ref, run):
                target.mkdir(parents=True, exist_ok=True)
                for arm in ("baseline", "field"):
                    (target / f"{arm}.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
            write_implementation_sidecar(ref, binary, role="reference", note="test fixture")
            receipt = compare_runs(ref, [run])
            self.assertIsNotNone(receipt["ref_implementation"])
            self.assertEqual(receipt["ref_implementation"]["llama.dll"]["sha256"],
                             hashlib.sha256(b"implementation").hexdigest())
            table = compare_table(receipt)
            label = table.splitlines()[0]
            self.assertTrue(label.startswith("ref ref "), label)
            self.assertNotIn("unrecorded", label)
            self.assertIn(receipt["ref_implementation"]["llama-server.exe"]["sha256"][:8], label)


if __name__ == "__main__":
    unittest.main()
