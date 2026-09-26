"""Protected anchor workloads for Cassi's self-improvement program.

This file is the fixed yardstick of the loop: every candidate version of Cassi
is measured by running these exact workloads against its own source tree.  The
self-improvement engine hash-locks this file; a changed anchor stops the loop.

Run as a subprocess:

    python anchor_worker.py --source-root <tree> --corpus <frozen git repo>
        --warm-corpus <small frozen git repo> [--overlay <dir>] [--workload <name>]...
        [--profile <out.json>] [--modules <out.json>] --out <result.json>

``--overlay`` directories shadow modules of ``--source-root`` (a candidate
patch lives there).  Every workload runs ``(scratch, variant)``: a warmup pass
on variant 1 first loads every lazy import, so the timed pass on variant 0
measures steady-state work.  The owner and library workloads change their
inputs between the passes; the test workloads run a fixed list of CassiFI's
own tests, whose outcomes are their digest.  ``--workload`` (repeatable) runs
a subset; the default runs all of them.
Each workload reports wall seconds, process CPU seconds, and its reading: the one
of the two it declares steady, which the engine sums into the whole-anchor total.
The digest of each workload is its exact observable output; a candidate is
correct only when every digest matches the base tree.  Durable-write counts
(``os.fsync``/``os.replace``) are part of the observation so a candidate cannot
buy speed by dropping durability.

``--profile`` profiles each workload's timed pass separately and writes merged
rows, each naming the workloads that reach the function, so a function's
timing needs only the workloads that run it.

``--target module:qualname`` (repeatable) clocks the inclusive seconds spent
inside those functions during the timed pass.  The clock listens to the
functions' own code objects through ``sys.monitoring``, so every call counts no
matter how the function was imported, and only the outermost activation per
thread is timed.
"""
from __future__ import annotations
import argparse
import contextlib
import functools
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import threading
from pathlib import Path

LIBRARY_QUERIES = (
    "vortex tube coherence margin",
    "golden ratio cascade scale",
    "two fluid yang yin field equations",
    "baryon asymmetry origin",
    "neutrino masses from the lattice",
    "dimensionful constants status",
    "bubble lattice fabric geometry",
    "interscale current soliton",
    "stationary action closure particle",
    "phi attractor synthesis renormalization",
    "planck crossover length",
    "microcascade mirror negative steps",
    "loop to bubble projection theorem",
    "endpoint link localization",
    "trapped charge core support",
    "cascade suppression formula",
)


class _DurableCounter:
    def __init__(self) -> None:
        self.fsync = 0
        self.replace = 0
        self._fsync = os.fsync
        self._replace = os.replace

    def install(self) -> None:
        def fsync(fd):
            self.fsync += 1
            return self._fsync(fd)

        def replace(src, dst, *args, **kwargs):
            self.replace += 1
            return self._replace(src, dst, *args, **kwargs)

        os.fsync = fsync
        os.replace = replace


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class _Touched:
    """Source files whose code runs during a workload, in any thread.

    Each code object reports its first start and then disables itself, so the recorder costs one event per
    function.  The engine screens a candidate on the workloads that run its module.
    """

    TOOL = 1

    def __init__(self) -> None:
        self.files: set[str] = set()

    def _start(self, code, offset):
        self.files.add(code.co_filename)
        return sys.monitoring.DISABLE

    def __enter__(self) -> "_Touched":
        monitoring = sys.monitoring
        monitoring.use_tool_id(self.TOOL, "cassi-anchor-touched")
        monitoring.register_callback(self.TOOL, monitoring.events.PY_START, self._start)
        monitoring.set_events(self.TOOL, monitoring.events.PY_START)
        return self

    def __exit__(self, *_) -> None:
        monitoring = sys.monitoring
        monitoring.set_events(self.TOOL, 0)
        monitoring.register_callback(self.TOOL, monitoring.events.PY_START, None)
        monitoring.free_tool_id(self.TOOL)
        monitoring.restart_events()


class _TargetClock:
    """Inclusive seconds inside chosen functions, observed on their code objects."""

    TOOL = 4

    def __init__(self, names) -> None:
        self.names = list(names)
        self.codes: dict = {}
        self.seconds = {name: 0.0 for name in self.names}
        self.calls = {name: 0 for name in self.names}
        self.missing: list = []
        self._depth: dict = {}
        self._started: dict = {}

    @staticmethod
    def _function(name: str):
        import importlib

        module_name, _, qualname = name.partition(":")
        target = importlib.import_module(module_name)
        for part in qualname.split("."):
            target = getattr(target, part)
        if isinstance(target, property):
            target = target.fget
        if hasattr(target, "func") and not hasattr(target, "__code__"):
            target = target.func  # functools.cached_property / partial
        if hasattr(target, "__func__"):
            target = target.__func__
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        return target

    def install(self) -> None:
        for name in self.names:
            try:
                self.codes[self._function(name).__code__] = name
            except Exception as exc:  # the name is reported, the run continues
                self.missing.append([name, f"{type(exc).__name__}: {exc}"])
        monitoring = sys.monitoring
        events = monitoring.events
        monitoring.use_tool_id(self.TOOL, "cassi-anchor-clock")
        monitoring.register_callback(self.TOOL, events.PY_START, self._start)
        monitoring.register_callback(self.TOOL, events.PY_RESUME, self._resume)
        monitoring.register_callback(self.TOOL, events.PY_RETURN, self._leave)
        monitoring.register_callback(self.TOOL, events.PY_YIELD, self._leave)
        monitoring.register_callback(self.TOOL, events.PY_UNWIND, self._unwind)
        local = events.PY_START | events.PY_RESUME | events.PY_RETURN | events.PY_YIELD
        for code in self.codes:
            monitoring.set_local_events(self.TOOL, code, local)
        monitoring.set_events(self.TOOL, events.PY_UNWIND)

    def remove(self) -> None:
        monitoring = sys.monitoring
        monitoring.set_events(self.TOOL, 0)
        for code in self.codes:
            monitoring.set_local_events(self.TOOL, code, 0)
        monitoring.free_tool_id(self.TOOL)

    def _enter(self, code) -> None:
        key = (threading.get_ident(), code)
        depth = self._depth.get(key, 0)
        if depth == 0:
            self._started[key] = time.perf_counter()
        self._depth[key] = depth + 1

    def _exit(self, code) -> None:
        key = (threading.get_ident(), code)
        depth = self._depth.get(key, 0) - 1
        if depth < 0:
            return
        self._depth[key] = depth
        if depth == 0:
            self.seconds[self.codes[code]] += time.perf_counter() - self._started.pop(key)

    def _start(self, code, offset):
        self.calls[self.codes[code]] += 1
        self._enter(code)

    def _resume(self, code, offset):
        self._enter(code)

    def _leave(self, code, offset, value):
        self._exit(code)

    def _unwind(self, code, offset, exception):
        if code in self.codes:
            self._exit(code)

    def report(self) -> dict:
        return {
            "targets": {name: {"seconds": self.seconds[name], "calls": self.calls[name]} for name in self.names},
            "missing": self.missing,
        }


def workload_owner(scratch: Path, variant: int) -> dict:
    from cassi_field_owner import FieldIntelligenceOwner, FieldIntelligenceSurface, RPC_SCHEMA

    def call(owner, op, action, **arguments):
        return FieldIntelligenceSurface(owner).handle({
            "schema": RPC_SCHEMA, "request_id": op, "operation": "computer",
            "params": {"operation_id": op, "computer_id": "main", "action": action, "arguments": arguments},
        })["result"]

    advances = 16 if variant == 0 else 2
    root = scratch / "owner"
    states = []
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure", profile={"mode_count": 16_384, "max_steps": 128, "max_events": 256})
        call(owner, "load", "load", program=[[0, 0, 0, 0, 0]])
        for index in range(advances // 2):
            call(owner, f"advance-{index}", "advance", steps=64)
            states.append(owner.state.state_sha256)
        for index in range(advances // 2, advances):
            call(owner, f"advance-{index}", "advance", steps=128)
        states.append(owner.state.state_sha256)
    with FieldIntelligenceOwner(root) as owner:
        states.append(owner.state.state_sha256)
        states.append(owner.state.computers[0].inspect()["task"])
    return {"states": states}


_CORPORA: dict[int, Path] = {}


def workload_library(scratch: Path, variant: int) -> dict:
    import cassi_field_foundry as foundry

    queries = LIBRARY_QUERIES if variant == 0 else ("warm field start",)
    destination = scratch / "library"
    receipt = foundry.build_field("library", {"root": str(_CORPORA[variant]), "patterns": ["*.md", "*.py"]}, destination)
    reader = foundry.open_field(destination).reader()
    hits = []
    for query in queries:
        result = reader.search(query, limit=8, with_text=True)
        hits.append([result["terms"], [
            [hit["passage"], hit["path"], hit["title"], hit["start"], hit["end"], round(hit["score"], 9),
             hit["sha256"], hashlib.sha256(hit["text"].encode("utf-8")).hexdigest()]
            for hit in result["hits"]
        ]])
    texts = reader.read_many([row[0] for row in reader.files[:6]])
    return {
        "root": receipt["root_sha256"],
        "state": receipt["state_sha256"],
        "summary": receipt["summary"],
        "hits": hits,
        "reads": {path: hashlib.sha256(data).hexdigest() for path, data in texts.items()},
    }


def _failure(kind: str, text: str) -> str:
    """``kind:ExceptionType`` from a traceback's last line; messages hold paths and addresses."""

    last = text.strip().splitlines()[-1] if text.strip() else ""
    return f"{kind}:{last.split(':', 1)[0].strip() or 'unknown'}"


def workload_tests(nodes: tuple[str, ...], scratch: Path, variant: int) -> dict:
    """Run a fixed list of CassiFI's own tests against the tree under measurement.

    The digest is every test's outcome, so a candidate that breaks any behavior these tests assert changes
    it.  Tests have fixed inputs, so warmup and timed pass run the same list.  Each test gets fresh
    directories under the workload's scratch, and ``tempfile`` points there too.
    """

    import importlib
    import inspect
    import unittest

    import pytest

    temporary = scratch / "tmp"
    temporary.mkdir()
    previous, tempfile.tempdir = tempfile.tempdir, str(temporary)
    outcomes: dict[str, str] = {}
    try:
        index = 0
        while index < len(nodes):
            file, *parts = nodes[index].split("::")
            module = importlib.import_module(Path(file).stem)
            owner = getattr(module, parts[0])
            if isinstance(owner, type) and issubclass(owner, unittest.TestCase):
                # Consecutive methods of one TestCase share a suite, so class fixtures run once for them.
                group = []
                while index < len(nodes) and nodes[index].split("::")[:2] == [file, parts[0]]:
                    group.append(nodes[index])
                    index += 1
                result = unittest.TestResult()
                unittest.TestSuite([owner(node.split("::")[2]) for node in group]).run(result)
                found = {}
                for kind, entries in (("error", result.errors), ("failed", result.failures)):
                    for case, text in entries:
                        found[case.id()] = _failure(kind, text)
                for case, _ in result.skipped:
                    found[case.id()] = "skipped"
                for node in group:
                    identity = f"{module.__name__}.{parts[0]}.{node.split('::')[2]}"
                    outcomes[node] = found.pop(identity, "passed")
                for identity, outcome in sorted(found.items()):  # class and module fixtures
                    outcomes[f"{file}::{identity}"] = outcome
                continue
            function = getattr(owner(), parts[1]) if len(parts) == 2 else owner
            arguments: dict = {}
            patch = pytest.MonkeyPatch()
            for name in inspect.signature(function).parameters:
                if name == "tmp_path":
                    arguments[name] = scratch / f"t{index}"
                    arguments[name].mkdir()
                elif name == "monkeypatch":
                    arguments[name] = patch
                else:
                    raise TypeError(f"{nodes[index]} needs the unsupported fixture {name!r}")
            try:
                function(**arguments)
                outcomes[nodes[index]] = "passed"
            except pytest.skip.Exception:
                outcomes[nodes[index]] = "skipped"
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # a failing test is an observation
                outcomes[nodes[index]] = f"failed:{type(exc).__name__}"
            finally:
                patch.undo()
            index += 1
    finally:
        tempfile.tempdir = previous
    return {"outcomes": outcomes}


# Each test workload names the tests it runs, as pytest node ids relative to the source root.
TEST_WORKLOADS: dict[str, tuple[str, ...]] = {
    "t00_alias_cut_complexity": (
        "test_alias_cut_complexity.py::test_source_clause_witness_uses_the_canonical_four_clause_basis",
        "test_alias_cut_complexity.py::test_c7_count_only_dp_matches_bounded_enumeration",
        "test_alias_cut_field.py::test_each_small_obstruction_cut_is_independently_verified",
        "test_alias_cut_field.py::test_cut_solver_supports_noncontiguous_cubic_ids",
        "test_alias_cut_field.py::test_cut_solver_checkpoint_roundtrip_preserves_complete_result",
        "test_alias_cut_field.py::test_cut_solver_exhaustion_carries_no_false_assignment_or_refutation",
        "test_alias_cut_field.py::test_cut_state_is_a_snapshot_and_rejects_profile_mismatch",
        "test_alias_cut_field.py::test_regional_alias_cut_quantum_roundtrip_resume_matches_public_result",
        "test_alias_exact_one_field.py::test_every_four_variable_occurrence_multiset_matches_truth_table",
        "test_alias_exact_one_field.py::test_persistent_field_size_is_linear_in_clause_count",
        "test_alias_exact_one_field.py::test_degree_three_aliases_produce_both_outcomes",
        "test_alias_exact_one_field.py::test_public_branch_steps_bulk_solve_and_checkpoint_are_identical",
        "test_alias_exact_one_field.py::test_recognizer_and_state_fail_closed",
        "test_alias_obstruction.py::test_regional_obstruction_quantum_one_roundtrip_and_public_parity",
        "test_cassi_autonomous_physics_residency.py::test_periodic_topology_separates_compression_and_rotation",
        "test_cassi_autonomous_physics_residency.py::test_autonomous_physics_curriculum_is_deterministic_bounded_and_sealed",
        "test_cassi_circulation.py::test_operator_residual_is_roundoff_on_declared_blocks_and_visible_when_rewired",
        "test_cassi_circulation.py::test_every_exchange_cancels_first_order_work_and_bounds_its_remainder",
        "test_cassi_circulation.py::test_circulate_pass_closes_the_balance_and_measures_geometry_on_the_second_pass",
    ),
    "t01_cassi_circulation": (
        "test_cassi_circulation.py::test_circulate_is_bounded_and_resumes_to_identical_bytes",
        "test_cassi_circulation.py::test_bounded_dispatches_defer_and_discharge_circulation_units",
        "test_cassi_circulation.py::test_circulate_requires_a_declared_and_enabled_segment",
        "test_cassi_circulation.py::test_stage_guard_refuses_a_foreign_version_and_rebinds_after_a_refresh",
        "test_cassi_circulation.py::test_orientation_retune_descends_on_the_tangent_or_refuses_and_reports",
        "test_cassi_circulation.py::test_attention_hysteresis_holds_an_unsettled_frame_and_releases_on_settle",
        "test_cassi_circulation.py::test_activity_modulation_is_bounded_geometry_sensitive_and_single_sourced",
        "test_cassi_circulation.py::test_passive_frame_change_moves_no_work_and_preserves_scalars",
        "test_cassi_circulation.py::test_over_budget_agenda_finishes_without_a_progress_continuation",
        "test_cassi_circulation.py::test_pending_saturated_agenda_finishes_when_resumed",
        "test_cassi_circulation.py::test_agenda_selects_the_same_obligation_across_one_work_quanta",
    ),
    "t02_cassi_circulation": (
        "test_cassi_circulation.py::test_flow_modulates_eligible_work_without_changing_eligibility",
        "test_cassi_circulation.py::test_spectral_feedback_is_concern_scoped_signed_and_operator_measured",
        "test_cassi_circulation.py::test_paused_regional_task_refuses_spectral_feedback_without_tuning",
        "test_cassi_circulation.py::test_v2_spectrum_state_is_upgraded_by_a_writable_circulation_unit",
        "test_cassi_circulation.py::test_working_field_exchange_view_requires_exact_source_and_concern",
        "test_cassi_circulation.py::test_working_field_exchange_view_preserves_unknown_and_truncation",
        "test_cassi_equation_discovery.py::test_known_world_calibrations_recover_the_registered_laws",
        "test_cassi_equation_discovery.py::test_initial_speed_provenance_accepts_both_bound_receipt_shapes",
        "test_cassi_equation_discovery.py::test_candidate_identity_is_content_addressed_and_field_contract_is_opaque",
        "test_cassi_field_affect.py::test_recall_consequence_is_eligible_grounded_affect_evidence",
        "test_cassi_field_affect.py::test_same_experience_under_different_operation_ids_appraises_once",
        "test_cassi_field_affect.py::test_one_experience_can_have_distinct_stable_contextual_projections",
        "test_cassi_field_affect.py::test_explicit_context_change_revises_same_affect_projection",
        "test_cassi_field_affect.py::test_introspection_and_regulation_refs_cannot_become_evidence",
        "test_cassi_field_affect.py::test_revoked_or_revised_evidence_does_not_remain_trusted",
        "test_cassi_field_affect.py::test_assessed_research_world_fixture_is_admitted_but_frozen_reporting_is_refused",
        "test_cassi_field_affect.py::test_save_reload_preserves_affect_context_and_learning_selection",
        "test_cassi_field_affect.py::test_two_projects_keep_distinct_local_affect_states",
        "test_cassi_field_affect.py::test_grounded_experience_can_change_agenda_choice_without_changing_obligations",
        "test_cassi_field_affect.py::test_regulation_learns_from_a_later_outcome_not_from_its_own_record",
        "test_cassi_field_affect.py::test_regulation_outcome_joins_actual_action_result_and_resolves_once",
        "test_cassi_field_affect.py::test_legacy_affect_choice_migrates_once_with_unknown_consequence_links",
        "test_cassi_field_hive.py::test_hive_objects_are_content_addressed_and_mutation_visible",
        "test_cassi_field_hive.py::test_bundle_requires_independent_support_and_preserves_lineage",
        "test_cassi_field_hive.py::test_admission_accepts_valid_successor_and_rejects_wrong_profile_without_mutation",
        "test_cassi_field_hive.py::test_admission_rejects_stale_common_generation",
        "test_cassi_field_hive.py::test_multi_program_preflight_rejects_late_invalid_entry_without_mutation",
        "test_cassi_field_hive.py::test_multi_program_runtime_failure_restores_durable_owner",
        "test_cassi_field_input.py::test_fixed_codecs_emit_deterministic_source_linked_pages",
        "test_cassi_field_input.py::test_source_pages_are_bounded_paged_and_fail_closed",
    ),
    "t03_cassi_field_input": (
        "test_cassi_field_input.py::test_autonomous_representation_refines_and_exposes_novel_encoding",
        "test_cassi_field_open_vocab.py::test_semantic_open_vocab_bridge_returns_bindings_without_goal_state_write",
        "test_cassi_field_open_vocab.py::test_semantic_open_vocab_bridge_refuses_unsupported_template_read_only",
        "test_cassi_field_open_vocab.py::test_fixed_bytes_and_recursive_alpha_equivalence",
        "test_cassi_field_open_vocab.py::test_nested_unification_and_occurs_type_refusals",
        "test_cassi_field_open_vocab.py::test_induction_nonce_renaming_and_held_out_plan",
        "test_cassi_field_open_vocab.py::test_repeated_entity_roles_are_shared_across_pre_action_effect",
        "test_cassi_field_open_vocab.py::test_schema_admission_rejects_support_mutation_without_state_write",
        "test_cassi_field_open_vocab.py::test_semantic_admission_and_idempotent_replay_without_hypothesis_write",
        "test_cassi_field_open_vocab.py::test_scope_unit_frame_and_guard_refusals_are_explicit",
        "test_cassi_field_open_vocab.py::test_resource_bound_is_deterministic_and_statuses_are_distinct",
        "test_cassi_field_open_vocab.py::test_two_step_plan_and_observation_suffix_repair_rebind",
        "test_cassi_field_open_vocab.py::test_bounds_are_explicit_not_false_impossibility",
        "test_cassi_field_open_vocab.py::test_proposal_plan_repair_are_read_only_and_no_model_fallback",
        "test_cassi_field_open_vocab.py::test_nonfinite_numbers_are_rejected_but_finite_numbers_are_canonical",
        "test_cassi_field_open_vocab.py::test_guard_codec_type_and_holdout_fail_closed",
        "test_cassi_field_open_vocab.py::test_goal_binding_supports_effect_only_variable",
        "test_cassi_field_open_vocab.py::test_unbound_effect_only_variable_cannot_support_goal",
        "test_cassi_field_open_vocab.py::test_goal_binds_novel_destination_and_multi_fact_transition",
        "test_cassi_field_open_vocab.py::test_repair_rejects_bad_observation_and_plan_closure",
        "test_cassi_field_open_vocab.py::test_autonomous_learning_discovers_action_schema_from_resident_episodes",
        "test_cassi_field_open_vocab.py::test_resident_procedure_discovery_requires_and_uses_trajectory_metadata",
        "test_cassi_field_open_vocab.py::test_resident_procedure_discovery_segments_untagged_events",
        "test_cassi_field_open_vocab.py::test_resident_procedure_discovery_keeps_failed_trajectories_as_holdout",
        "test_cassi_field_open_vocab.py::test_autonomous_learning_scores_resident_outcomes",
        "test_cassi_field_open_vocab.py::test_procedure_steps_select_feedback_branches",
        "test_cassi_field_open_vocab.py::test_autonomous_agenda_prioritizes_pending_obligations",
        "test_cassi_field_open_vocab.py::test_autonomous_agenda_honors_declared_obligation_priority",
        "test_cassi_field_open_vocab.py::test_autonomous_curiosity_generates_prediction_error_goal",
        "test_cassi_field_open_vocab.py::test_autonomous_agenda_promotes_novel_observation_goal",
        "test_cassi_field_open_vocab.py::test_autonomous_perception_selects_goal_relevant_observation_channel",
        "test_cassi_field_open_vocab.py::test_autonomous_agenda_turns_curiosity_into_active_perception_request",
        "test_cassi_field_operator_invention.py::test_operator_calibrations_recover_four_known_worlds",
        "test_cassi_full_observable_invention.py::test_complete_observable_alphabet_is_finite_deterministic_and_fires",
        "test_cassi_full_observable_invention.py::test_registered_observable_supports_are_exactly_recoverable",
        "test_cassi_full_observable_invention.py::test_environment_families_are_readable_and_target_independent",
        "test_cassi_full_observable_invention.py::test_v4_excludes_only_unscorable_stationary_development_arm",
        "test_cassi_full_observable_invention.py::test_field_alone_selects_every_stage_with_bounded_candidate_sets",
        "test_cassi_hive_collective.py::test_signed_identity_and_independence_reject_shared_lineage",
        "test_cassi_hive_collective.py::test_outcome_evidence_is_control_backed_and_expirable",
        "test_cassi_hive_collective.py::test_weighted_quorum_requires_profiles_and_independence",
        "test_cassi_hive_collective.py::test_hypothesis_graph_preserves_contradiction_branches",
        "test_cassi_hive_collective.py::test_collective_indexes_reload_branches_offers_and_roles",
        "test_cassi_hive_collective.py::test_collaboration_protocol_is_typed_attributed_and_reloadable",
        "test_cassi_hive_collective.py::test_collaborative_partial_methods_compile_execute_and_expose_gaps",
        "test_cassi_hive_collective.py::test_query_router_matches_demand_to_specialized_offer",
        "test_cassi_hive_collective.py::test_diversity_selector_keeps_different_profiles",
        "test_cassi_hive_collective.py::test_specialist_router_assigns_least_loaded_capable_instance",
        "test_cassi_hive_collective.py::test_composed_program_is_typed_and_bounded",
        "test_cassi_hive_collective.py::test_local_adaptation_and_memory_consolidation_persist",
        "test_cassi_hive_collective.py::test_consolidated_memory_expiration_is_explicit",
        "test_cassi_hive_collective.py::test_bridge_emits_bounded_causally_linked_events",
        "test_cassi_hive_collective.py::test_bridge_emits_population_outcome_event",
        "test_cassi_hive_collective.py::test_collective_facade_records_identity_and_outcome",
    ),
    "t04_cassi_hive_rollout": (
        "test_cassi_hive_rollout.py::test_successive_rounds_compare_members_and_calibrate_future_promotion",
        "test_cassi_hive_rollout.py::test_population_rollout_rejects_duplicate_profiles_before_opening_members",
        "test_cassi_hive_runtime.py::test_owner_facade_automatically_exports_transition",
        "test_cassi_hive_runtime.py::test_three_stage_scout_review_member_flow",
        "test_cassi_hive_runtime.py::test_member_adoption_binds_receipt_to_outcome_evidence",
    ),
    "t05_cassi_hive_runtime": (
        "test_cassi_hive_runtime.py::test_manual_import_stages_then_adopts_and_replays",
        "test_cassi_hive_runtime.py::test_incompatible_profile_does_not_mutate_member",
        "test_cassi_hive_runtime.py::test_fork_creates_new_instance_lineage",
        "test_cassi_hive_runtime.py::test_attach_wraps_existing_owner_boundary",
        "test_cassi_hive_runtime.py::test_revoked_bundle_is_blocked_before_owner_mutation",
        "test_cassi_hive_runtime.py::test_deterministic_promotion_loop_and_portable_member_adoption",
        "test_cassi_math_bytes_experiment.py::test_byte_equation_generation_is_deterministic_and_split_safe",
        "test_cassi_math_dataset.py::test_gsm8k_parser_keeps_questions_reasoning_and_declared_answers",
        "test_cassi_math_dataset.py::test_audit_admits_only_exact_equation_answer_replays",
        "test_cassi_math_dataset.py::test_lesson_miner_emits_typed_train_and_holdout_contract",
        "test_cassi_math_language.py::test_english_and_latex_surfaces_share_one_canonical_term",
        "test_cassi_math_language.py::test_latex_fraction_and_exact_rational_evaluation_round_trip",
        "test_cassi_math_language.py::test_exact_linear_solver_returns_replayable_derivation",
        "test_cassi_math_language.py::test_linear_fraction_equation_and_degenerate_cases_are_exact",
        "test_cassi_math_language.py::test_exact_linear_inequality_returns_interval_and_reversal_certificate",
        "test_cassi_math_language.py::test_linear_inequality_degenerate_and_nonlinear_cases_are_exact",
        "test_cassi_math_language.py::test_math_kernel_refuses_unsafe_or_out_of_scope_operations",
        "test_cassi_math_language.py::test_typed_math_template_validates_surfaces_and_holdout",
        "test_cassi_morphology_observables.py::test_morphology_atoms_are_finite_deterministic_and_target_independent",
        "test_cassi_morphology_observables.py::test_morphology_coordinates_distinguish_shell_scale_shape_and_flow",
        "test_cassi_morphology_observables.py::test_morphology_operator_language_merges_exact_successor_alphabet",
        "test_cassi_morphology_operator_invention.py::test_morphology_activation_is_complete_and_restores_v4_language",
        "test_cassi_morphology_residual_authority.py::test_conditional_authority_recovers_real_added_channel",
        "test_cassi_morphology_residual_authority.py::test_conditional_spectrum_duplicate_control_loses_no_rank",
        "test_cassi_packet_reasoning.py::test_adapter_dispatch_consumes_one_bounded_return",
        "test_cassi_packet_reasoning.py::test_collective_method_wait_survives_round_trip_and_resumes_exactly",
        "test_cassi_packet_reasoning.py::test_enforced_allocation_refuses_a_reservation_that_does_not_fit",
        "test_cassi_packet_reasoning.py::test_readout_decides_within_its_bound_and_refuses_an_uncertified_norm",
        "test_cassi_packet_reasoning.py::test_correction_blocks_stale_reads_and_resumes_after_bounded_repair",
        "test_cassi_packet_reasoning.py::test_repeated_subproblem_reuses_completed_work_without_redispatch",
        "test_cassi_packet_reasoning.py::test_readout_reuse_shares_one_certified_result_between_items",
        "test_cassi_packet_reasoning.py::test_branch_item_keeps_incompatible_hypotheses_distinct",
        "test_cassi_packet_reasoning.py::test_acquired_selector_program_orders_the_frontier",
        "test_cassi_packet_reasoning.py::test_acquired_selector_program_refuses_an_unresolvable_score",
        "test_cassi_packet_reasoning.py::test_undeclared_reservation_holds_only_the_remaining_allowance",
        "test_cassi_packet_reasoning.py::test_work_item_source_binding_records_the_span_it_reads",
        "test_cassi_packet_reasoning.py::test_work_item_source_binding_refuses_an_unadmitted_source",
        "test_cassi_packet_reasoning.py::test_work_item_source_binding_refuses_a_span_outside_its_admission",
        "test_cassi_packet_reasoning.py::test_spanless_admission_does_not_authorize_a_span",
        "test_cassi_packet_reasoning.py::test_admitted_input_span_requires_an_identity",
        "test_cassi_reality_residency.py::test_reality_curriculum_is_deterministic_disjoint_and_sealed",
        "test_cassi_reality_residency.py::test_control_search_contains_an_exact_net_zero_intervention",
        "test_cassi_reality_residency.py::test_global_response_family_can_identify_cross_channel_coupling",
        "test_cassi_temporal_residual_authority.py::test_trajectory_alignment_preserves_identity_across_every_lag",
        "test_cassi_temporal_residual_authority.py::test_identity_break_changes_tracers_without_changing_time_slots",
        "test_cassi_temporal_residual_authority.py::test_conditional_reading_recovers_history_residual_not_identity_broken_history",
        "test_cassi_temporal_residual_authority.py::test_effective_rank_is_unchanged_by_an_exact_duplicate_history_block",
    ),
    "t06_clause_field": (
        "test_clause_field.py::test_field_owned_solver_returns_sat_certificate_and_complete_unsat_result",
        "test_clause_field.py::test_conflict_nogoods_are_field_resident_and_logically_entailed",
        "test_clause_field.py::test_each_step_is_immutable_and_checkpoint_roundtrip_is_exact",
        "test_clause_field.py::test_unsat_run_emits_an_independently_checkable_resolution_refutation",
        "test_clause_field.py::test_root_level_conflict_is_a_complete_one_leaf_refutation",
        "test_clause_field.py::test_independent_checker_rejects_resolution_and_closure_tampering",
        "test_clause_field.py::test_transition_bound_exposes_exhaustion_without_false_decision",
        "test_clause_field.py::test_variable_clause_and_literal_permutations_preserve_the_decision",
        "test_clause_field.py::test_profile_capacity_and_malformed_state_fail_closed",
        "test_clause_field.py::test_regional_clause_quantum_one_roundtrip_resume_and_terminal_parity",
        "test_computation_policy.py::test_context_is_structural_and_bounded",
        "test_computation_policy.py::test_context_key_reuses_structural_bucket_across_source_scale",
        "test_computation_policy.py::test_complexity_refinement_splits_one_coarse_structural_context",
        "test_computation_policy.py::test_refined_context_uses_sibling_evidence_only_until_locally_observed",
        "test_computation_policy.py::test_related_evidence_guides_unseen_exploration_completion_first",
        "test_computation_policy.py::test_budget_classes_isolate_evidence_for_the_same_structure",
        "test_computation_policy.py::test_selection_interleaves_structural_incumbent_challengers_and_empirical_use",
        "test_computation_policy.py::test_stale_method_reevaluation_and_field_counterfactual_are_deterministic",
        "test_computation_policy.py::test_policy_inspection_is_a_read_only_context_projection",
        "test_computation_policy.py::test_policy_field_is_immutable_and_round_trips",
        "test_computation_policy.py::test_recent_and_long_windows_decay_and_clip_at_exact_bounds",
        "test_computation_policy.py::test_v2_policy_round_trips_losslessly_then_migrates_evidence_and_epochs",
        "test_computation_policy.py::test_v3_policy_round_trips_and_migrates_losslessly_to_v4",
        "test_computation_policy.py::test_compiled_and_raw_envelope_sources_are_equivalent",
        "test_computation_policy.py::test_invalid_methods_and_workspace_refusals_are_policy_errors",
        "test_computation_policy.py::test_solve_receipt_is_json_and_witness_is_audited_against_source",
        "test_computation_policy.py::test_shared_budget_and_exhaustion_carry_no_decided_evidence",
        "test_computation_policy.py::test_learn_false_preserves_policy_field_bytes_and_freezes_selection",
        "test_computation_policy.py::test_no_unsat_claim_from_unverified_synthetic_evidence",
        "test_computation_policy.py::test_solver_continuation_restores_the_exact_running_field",
        "test_computation_policy.py::test_continuation_rejects_unpayable_atomic_episode",
        "test_computation_policy.py::test_continuation_defers_learning_and_rejects_source_changes",
        "test_computation_policy.py::test_regional_policy_selects_and_learns_from_typed_field_data",
        "test_constraint_dynamics.py::test_two_identical_runs_replay_to_identical_digests_and_selections",
        "test_constraint_dynamics.py::test_selection_is_confined_to_eligible_variables_and_absent_without_any",
        "test_constraint_dynamics.py::test_signed_literal_follows_the_activity_polarity",
        "test_constraint_dynamics.py::test_intervention_flips_an_equal_activity_selection_and_changes_its_score",
        "test_constraint_dynamics.py::test_intervention_writes_only_one_excitation_lane_and_is_exactly_bounded",
        "test_constraint_dynamics.py::test_selected_site_is_consumed_and_left_refractory",
        "test_constraint_dynamics.py::test_equal_activity_decisions_walk_across_the_ring",
        "test_constraint_dynamics.py::test_relaxation_matches_the_documented_fixed_point_recurrence",
    ),
    "t07_constraint_dynamics": (
        "test_constraint_dynamics.py::test_long_horizon_ticks_stay_exact_integer_and_bounded",
        "test_constraint_dynamics.py::test_tick_budget_is_a_bounded_terminal_lifetime",
        "test_constraint_dynamics.py::test_header_lanes_record_magic_geometry_and_counters",
        "test_constraint_dynamics.py::test_descriptor_round_trip_preserves_the_field_and_its_continuation",
        "test_constraint_dynamics.py::test_descriptor_tampering_is_rejected",
        "test_constraint_dynamics.py::test_malformed_activity_and_eligibility_inputs_fail_closed",
        "test_constraint_dynamics.py::test_numpy_activity_and_eligibility_sequences_are_accepted",
        "test_constraint_dynamics.py::test_malformed_interventions_fail_closed",
        "test_constraint_dynamics.py::test_malformed_states_fail_closed",
        "test_constraint_dynamics.py::test_profile_bounds_and_fingerprint_are_strict",
        "test_constraint_field.py::test_payload_shape_and_digest_are_exact",
        "test_constraint_field.py::test_transition_timed_clause_targets_declared_time",
        "test_constraint_field.py::test_compile_is_deterministic_and_order_insensitive",
        "test_constraint_field.py::test_relation_encodings_match_parity_and_bounds",
        "test_constraint_field.py::test_compiled_clauses_are_canonical_and_auditable",
        "test_constraint_field.py::test_transition_encoding_matches_the_reference_simulator",
        "test_constraint_field.py::test_horizon_zero_transition_is_boundary_only",
        "test_constraint_field.py::test_local_mode_stalls_instead_of_branching",
        "test_constraint_field.py::test_propagation_only_refutes_root_conflicts",
        "test_constraint_field.py::test_algebraic_prepass_refutes_without_a_backend",
        "test_constraint_field.py::test_sat_witnesses_satisfy_the_source",
        "test_constraint_field.py::test_unsat_certificates_pass_the_independent_audit",
        "test_constraint_field.py::test_admitted_augmentations_are_entailed_by_the_source",
        "test_constraint_field.py::test_augmentation_arity_is_declared_and_bounded",
    ),
    "t08_constraint_field": (
        "test_constraint_field.py::test_binary_augmentation_rows_are_entailed_and_reach_the_backend",
        "test_constraint_field.py::test_augmentation_arity_is_inert_without_a_prepass",
        "test_constraint_field.py::test_exhausted_claims_nothing",
        "test_constraint_field.py::test_terminal_steps_are_idempotent",
        "test_constraint_field.py::test_solve_matches_repeated_steps",
        "test_constraint_field.py::test_deterministic_replays_agree",
        "test_constraint_field.py::test_descriptor_tampering_is_rejected",
        "test_constraint_field.py::test_descriptor_codec_keeps_its_own_geometry",
        "test_constraint_field.py::test_controller_drives_decisions_and_keeps_verdicts",
        "test_constraint_field.py::test_intervention_is_journaled_and_keeps_the_verdict",
        "test_constraint_field.py::test_intervention_requires_a_controller_and_a_running_field",
        "test_constraint_field.py::test_compile_rejects_sources_outside_the_vocabulary",
        "test_constraint_field.py::test_profile_and_capacity_limits_fail_closed",
        "test_constraint_field.py::test_already_contradictory_sources_refute_in_every_configuration",
        "test_constraint_field.py::test_unknown_gate_arguments_are_refused_by_compilation",
        "test_constraint_field.py::test_regional_constraint_kernel_quantum_one_json_resume_and_parity",
        "test_constraint_implication.py::test_xor_chain_implication_holds_with_audited_certificate",
        "test_constraint_implication.py::test_unasserted_circuit_implication_is_refuted_by_a_replayed_counterexample",
        "test_constraint_implication.py::test_gate_output_consequence_is_refuted_with_its_own_witness",
        "test_constraint_implication.py::test_transition_gate_output_consequence_uses_clause_route",
        "test_constraint_implication.py::test_independent_screen_resolves_unused_transition_gate_output",
        "test_constraint_implication.py::test_implication_can_request_binary_augmentation",
        "test_constraint_implication.py::test_vacuous_outcome_distinguishes_boundary_clashes",
        "test_constraint_implication.py::test_boundary_consequence_is_holds_not_vacuous",
        "test_constraint_implication.py::test_relation_derived_unit_is_not_mislabeled_vacuous",
        "test_constraint_implication.py::test_final_boundary_clash_is_vacuous_for_derived_signals",
        "test_constraint_implication.py::test_deep_premise_unsatisfiability_reports_holds",
        "test_constraint_implication.py::test_exhaustion_reports_unresolved_without_certificate",
        "test_constraint_implication.py::test_unknown_or_malformed_query_literals_are_refused",
        "test_constraint_implication.py::test_transition_query_rejects_illegal_signal_times",
        "test_constraint_implication.py::test_independent_transition_evaluator_rejects_negative_input_assertion_time",
        "test_constraint_implication.py::test_implication_rejects_invalid_augmentation_arity",
        "test_constraint_implication.py::test_supplied_profile_controls_augmentation_arity",
    ),
    "t09_constraint_implication": (
        "test_constraint_implication.py::test_imply_does_not_mutate_the_source",
        "test_constraint_implication.py::test_regional_implication_quantum_one_round_trips_and_preserves_verdict_evidence",
        "test_constraint_solver_integrity.py::test_binding_accepts_json_transport_and_rejects_mutation",
        "test_constraint_solver_integrity.py::test_proof_and_learning_evidence_cannot_be_tampered",
        "test_constraint_solver_integrity.py::test_decision_frames_track_assignments_across_backtracking",
        "test_constraint_solver_integrity.py::test_learned_tail_invariant_is_enforced",
        "test_cubic_admissible_cell_probe.py::test_prism_exchange_graph_and_independent_reconstruction_agree",
        "test_cubic_admissible_cell_probe.py::test_disconnected_truth_fibres_are_explicitly_rejected",
        "test_cubic_admissible_cell_probe.py::test_alternate_pair_partition_is_recorded_up_to_orientation",
        "test_cubic_admissible_cell_probe.py::test_auxiliary_column_shadow_is_recorded",
        "test_cubic_admissible_cell_probe.py::test_duplicate_primal_columns_are_not_admissible_cells",
        "test_cubic_admissible_cell_probe.py::test_no_width_two_fixture_is_not_applicable",
        "test_cubic_admissible_cell_probe.py::test_pair_work_cap_is_inconclusive_not_a_negative",
        "test_cubic_admissible_cell_probe.py::test_verifier_rejects_mutated_real_certificate_witness",
        "test_cubic_degeneracy_quotient_population_probe.py::test_compact_twin_case_matches_independent_reconstruction",
        "test_cubic_degeneracy_quotient_population_probe.py::test_compact_dual_case_matches_independent_recursive_evidence",
        "test_cubic_degeneracy_quotient_population_probe.py::test_compact_receipt_comparison_rejects_digest_tampering",
        "test_cubic_degeneracy_quotient_population_probe.py::test_source_join_validation_rejects_declared_pair_count_mismatch",
        "test_cubic_degeneracy_quotient_population_probe.py::test_source_join_validation_rejects_duplicate_lift_formula_hash",
        "test_cubic_degeneracy_quotient_probe.py::test_primal_twin_sum_quotient_preserves_projected_solutions",
        "test_cubic_degeneracy_quotient_probe.py::test_dual_parallel_equality_quotient_reaches_constructive_terminal",
        "test_cubic_degeneracy_quotient_probe.py::test_case_reconstruction_detects_relation_tampering",
        "test_cubic_degeneracy_quotient_probe.py::test_independent_substitution_refuses_false_pair_category",
        "test_cubic_degeneracy_structure_probe.py::test_known_cubic_target_reconstructs_the_twin_mode_independently",
        "test_cubic_degeneracy_structure_probe.py::test_general_vector_controls_prove_the_implication_check_can_fire",
        "test_cubic_degeneracy_structure_probe.py::test_basis_family_canonicalization_is_relabeling_invariant",
    ),
    "t10_cubic_exchange_boundary_prob": (
        "test_cubic_exchange_boundary_probe.py::test_every_boundary_edge_is_the_oriented_port_swap",
        "test_cubic_exclusive_pair_neighborhood_probe.py::test_frozen_seeds_and_complete_switch_populations_are_pinned",
        "test_cubic_exclusive_pair_neighborhood_probe.py::test_runner_and_verifier_agree_on_real_seed_baselines",
        "test_cubic_exclusive_pair_neighborhood_probe.py::test_real_no_width_two_neighbor_is_explicitly_not_applicable",
        "test_cubic_exclusive_width_barrier_probe.py::test_synthetic_controls_make_the_width_barrier_predicate_falsifiable",
        "test_cubic_exclusive_width_barrier_probe.py::test_runner_and_verifier_agree_on_frozen_seed_all_pair_censuses",
    ),
    "t11_cubic_exclusive_width_barrie": (
        "test_cubic_exclusive_width_barrier_probe.py::test_complete_switch_population_reconstructs_independently",
        "test_cubic_kernel_decision.py::test_matrix_certificate_uses_kernel_basis_complement_and_bit_bounds",
        "test_cubic_kernel_decision.py::test_matrix_certificate_rejects_malformed_inputs_and_bad_witnesses",
        "test_cubic_kernel_decision.py::test_line_profile_is_exact_at_nullity_three_and_conservative_beyond",
        "test_cubic_kernel_decision.py::test_short_line_class_bound_is_exact_and_long_lines_stay_unresolved",
    ),
    "t12_cubic_kernel_decision": (
        "test_cubic_kernel_decision.py::test_complete_width_two_recognizer_handles_long_lines_and_decision_seam",
        "test_cubic_kernel_decision.py::test_rank_alphabet_and_witness_outcomes_are_distinct",
        "test_cubic_kernel_decision.py::test_support_three_boundary_uses_exact_fallback_for_sat_and_unsat",
        "test_cubic_kernel_decision.py::test_basis_optimization_expands_binary_support_decisions",
        "test_cubic_kernel_decision.py::test_basis_exchange_profile_exposes_strict_descent_traps",
        "test_cubic_kernel_decision.py::test_dual_triangle_profile_recovers_clause_circuits_and_extras",
        "test_cubic_kernel_decision.py::test_some_ternary_kernel_systems_have_no_binary_support_basis",
        "test_cubic_kernel_decision.py::test_exact_one_witness_induces_a_zero_valid_dual_basis",
        "test_cubic_kernel_decision.py::test_basis_width_is_invariant_under_variable_relabeling",
        "test_cubic_kernel_decision.py::test_basis_width_limits_and_nonbasis_columns_are_rejected",
        "test_cubic_kernel_decision.py::test_clause_and_variable_relabeling_preserve_the_decision",
        "test_cubic_kernel_decision.py::test_all_fixed_gauge_cubic_formulas_through_six_variables_match_bruteforce",
        "test_cubic_lift_realization_probe.py::test_nullity_three_control_reconstructs_exact_basis_degeneracy",
        "test_cubic_order10_exact_target_probe.py::test_runner_and_verifier_agree_on_exact_target_control",
        "test_cubic_order10_exact_target_probe.py::test_runner_and_verifier_agree_on_modular_false_positive_control",
        "test_cubic_order10_exact_target_probe.py::test_exact_target_contract_constants_match",
        "test_cubic_order10_feasibility_screen.py::test_small_cycle_cover_and_factorization_controls_match",
        "test_cubic_order10_feasibility_screen.py::test_hash_of_formula_keys_is_explicit_and_deterministic",
        "test_cubic_order10_feasibility_screen.py::test_sorted_hash_digests_use_only_sqlite_keys",
        "test_cubic_order10_feasibility_screen.py::test_invalid_formula_control_fires",
        "test_cubic_order10_feasibility_screen.py::test_stable_contract_constants_match_without_reading_a_receipt",
        "test_cubic_reduction_discovery.py::test_canonical_system_normalizes_scale_sign_order_and_duplicates",
        "test_cubic_reduction_discovery.py::test_private_cover_uses_distinct_columns_only_for_nonzero_targets",
        "test_cubic_reduction_discovery.py::test_low_arity_projection_fast_path_matches_independent_rref",
        "test_cubic_reduction_discovery.py::test_fixed_nullity_terminals_make_only_checked_truth_claims",
    ),
    "t13_cubic_reduction_discovery": (
        "test_cubic_reduction_discovery.py::test_growing_nullity_uses_exact_pairs_then_checked_sparse_witness",
        "test_cubic_reduction_discovery.py::test_nonnegative_row_bound_resolves_former_hard_core_with_checked_lift",
        "test_cubic_reduction_discovery.py::test_nonnegative_row_bound_has_a_clean_negative_control",
        "test_cubic_reduction_discovery.py::test_literal_conflict_forcing_is_exact_and_independently_replayed",
        "test_cubic_reduction_discovery.py::test_cap_five_unsat_control_exhausts_exactly_thirty_two_candidates",
        "test_cubic_reduction_discovery.py::test_duplicate_components_share_exact_residual_without_persistent_cache",
        "test_cubic_reduction_discovery.py::test_preference_field_records_exact_evidence_only_within_one_invocation",
        "test_cubic_reduction_discovery.py::test_exported_algorithm_is_finite_uniform_and_explicitly_incomplete",
        "test_cubic_reduction_discovery.py::test_adversarial_generator_is_deterministic_connected_and_cubic",
        "test_cubic_reduction_discovery.py::test_cap_five_unresolved_profile_exhausts_only_its_active_schedule",
    ),
    "t14_cubic_reduction_discovery": (
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_literal_witness_coordinate_tamper",
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_literal_conflict_coordinate_tamper",
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_tampered_affine_guard",
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_tampered_sparse_certificate",
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_tampered_row_bound_certificate",
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_schedule_profile_proof_mismatch",
        "test_cubic_reduction_discovery.py::test_independent_verifier_rejects_non_decreasing_progress",
        "test_cubic_reduction_discovery.py::test_invalid_profiles_and_non_cubic_inputs_fail_closed",
        "test_cubic_truth_state_cell_probe.py::test_producer_and_independent_verifier_agree_on_small_fixture",
        "test_cubic_truth_state_cell_probe.py::test_identical_primal_support_is_rejected_as_a_truth_port",
        "test_cubic_truth_state_cell_probe.py::test_degree_preserving_switch_keeps_cubic_connected_formula",
        "test_cubic_truth_state_cell_probe.py::test_independent_verifier_rejects_tampered_fixture_census",
        "test_field_computer.py::test_each_public_primitive_step_matches_independent_two_stack_model",
        "test_field_computer.py::test_empty_push_acc_fault_preserves_tape_and_does_not_choose_a_symbol",
        "test_field_computer.py::test_resize_and_budget_boundaries_preserve_configuration",
        "test_field_computer.py::test_descriptor_round_trip_and_field_alias_protection",
        "test_field_computer.py::test_batched_run_is_full_field_equivalent_and_seals_once_across_boundaries",
        "test_field_computer.py::test_batched_pause_matches_public_steps_and_resumes_at_exact_checkpoint",
        "test_field_computer.py::test_hot_basic_blocks_are_field_learned_restart_stable_and_exact",
        "test_field_computer.py::test_compiled_tm_boundaries_cover_algorithms_and_both_directions",
    ),
    "t15_field_computer": (
        "test_field_computer.py::test_exhaustive_small_tm_table_coverage_is_bounded_and_independent",
        "test_field_computer.py::test_malformed_programs_and_tm_descriptors_are_rejected",
        "test_field_computer.py::test_stored_propagation_pause_reload_and_result_consumption",
        "test_field_computer.py::test_automaton_excitation_changes_which_ready_deduction_executes_first",
        "test_field_computer.py::test_legacy_descriptor_remains_exact_and_new_instruction_cannot_downgrade",
        "test_field_computer.py::test_regional_computer_executes_cross_region_program_and_round_trips",
        "test_field_computer.py::test_regional_failed_move_is_atomic_and_fault_is_visible",
        "test_field_computer.py::test_regional_kernel_catalog_is_frozen_and_unknown_kernels_are_rejected",
        "test_field_computer.py::test_regional_automaton_intervention_changes_event_selection_causally",
        "test_field_computer.py::test_regional_native_catalog_rejects_stateful_kernel_closures",
        "test_field_computer.py::test_paged_activity_selection_matches_dense_and_needs_a_regional_profile",
        "test_field_program.py::test_structured_program_executes_functions_flow_arithmetic_and_lexical_variable",
        "test_field_program.py::test_lexical_binding_isolated_by_balanced_user_stack_effects_and_nested_scopes",
        "test_field_program.py::test_live_lexical_binding_rejects_burial_boundary_crossing_and_unbalanced_flow",
        "test_field_program.py::test_unknown_byte_addition_wraps_255_to_zero_with_bounded_lowering_cost",
        "test_field_program.py::test_static_value_folding_matches_same_source_unoptimized_lowering",
        "test_field_program.py::test_constant_condition_discards_unreachable_expensive_lowering",
        "test_field_program.py::test_while_loop_obeys_explicit_machine_step_boundary_and_resumes",
        "test_field_program.py::test_structured_source_rejects_ambiguous_or_unbounded_forms",
        "test_field_python_runtime.py::test_resource_growth_retries_only_the_unfinished_effect_request",
    ),
    "t16_field_regions_paging": (
        "test_field_regions_paging.py::test_paged_transition_matches_the_dense_image_byte_for_byte",
        "test_field_regions_paging.py::test_unverifiable_paged_delta_is_rejected",
        "test_field_regions_paging.py::test_predecessor_survives_a_faulting_transition",
        "test_field_regions_paging.py::test_faulted_kernel_leaves_the_predecessor_unchanged",
        "test_field_regions_paging.py::test_residency_wait_is_typed_and_resumes_without_replaying_work",
        "test_field_regions_paging.py::test_bounded_run_never_exceeds_its_page_allowance",
        "test_field_regions_paging.py::test_segments_cover_used_words_without_reserved_capacity_pages",
        "test_field_regions_paging.py::test_unchanged_pages_reuse_leaf_records_and_tree_nodes",
        "test_field_regions_paging.py::test_page_audit_path_verifies_and_rejects_a_tampered_sibling",
        "test_field_regions_paging.py::test_missing_or_corrupt_page_objects_are_typed_failures",
        "test_field_regions_paging.py::test_ram_page_placement_is_resident_idempotent_and_rejects_fake_vram",
        "test_field_regions_paging.py::test_descriptor_reopen_preserves_identity_and_is_demand_paged",
        "test_field_regions_paging.py::test_run_paged_image_stops_on_halt_and_reports_its_work",
        "test_field_regions_paging.py::test_residency_wait_during_a_run_is_reported_with_a_continuation",
        "test_field_regions_paging.py::test_staging_spills_within_its_declared_dirty_bound",
        "test_field_regions_paging.py::test_vector_page_writes_preserve_order_for_unsorted_duplicate_offsets",
        "test_field_regions_paging.py::test_layout_migration_binds_the_predecessor_identity",
        "test_field_regions_paging.py::test_activity_reorders_eligible_work_without_touching_eligibility",
        "test_field_regions_paging.py::test_activity_modulation_is_bounded_recorded_and_never_removes_drive",
        "test_field_regions_paging.py::test_paged_activity_matches_dense_activity_byte_for_byte",
        "test_field_regions_paging.py::test_foreground_await_lends_to_its_writer_with_flat_paged_parity",
        "test_field_regions_paging.py::test_closed_await_cycle_is_reported_without_falsely_running_a_writer",
        "test_field_regions_paging.py::test_residency_wait_continuation_is_canonical_and_carries_identity",
        "test_field_regions_paging.py::test_paged_object_history_preserves_live_keys_and_precedence",
        "test_field_regions_paging.py::test_paged_prefetch_is_bounded_reopenable_and_credited_only_on_use",
        "test_field_regions_paging.py::test_bound_object_prefetch_uses_current_exact_object_pages",
        "test_field_transceiver.py::test_empty_extension_preserves_existing_v2_descriptor_shape",
        "test_fractal_bidirectional_recursive_memory_cell.py::test_live_child_detail_transition_rejects_frozen_parent",
        "test_fractal_durability_exploration.py::test_workspace_round_trip_preserves_the_state_and_the_read_frame",
        "test_fractal_durability_exploration.py::test_analysis_only_reads_leave_the_canonical_state_unchanged",
        "test_fractal_durability_exploration.py::test_declared_item_writes_respect_their_energy_bound",
        "test_fractal_geometry_exploration.py::test_every_arrangement_constructs_an_antisymmetric_bounded_rail",
    ),
    "t17_fractal_geometry_exploration": (
        "test_fractal_geometry_exploration.py::test_declared_strength_budget_matches_the_rail_actually_used",
        "test_fractal_geometry_exploration.py::test_matched_density_rewire_reproduces_the_ladder_interaction_budget",
        "test_fractal_geometry_exploration.py::test_isolated_couples_no_pools",
        "test_fractal_geometry_exploration.py::test_ladder_couples_only_its_declared_neighbours",
        "test_fractal_geometry_exploration.py::test_topology_is_metadata_only_when_the_rail_is_projected",
        "test_fractal_geometry_exploration.py::test_quartic_weights_leave_the_linear_spectrum_untouched",
        "test_fractal_geometry_exploration.py::test_constructions_are_deterministic",
        "test_fractal_geometry_exploration.py::test_mode_localization_distinguishes_a_chain_from_an_all_to_all_rail",
        "test_fractal_geometry_exploration.py::test_cross_pool_gain_probe_is_exact_at_unit_gain_and_moves_the_spectrum_when_stronger",
        "test_fractal_lattice_exploration.py::test_rung_laws_are_two_declared_sets_with_declared_scales",
        "test_fractal_lattice_exploration.py::test_rung_writer_sets_one_oriented_rung_at_every_position",
        "test_fractal_lattice_exploration.py::test_nested_depth1_anchor_reproduces_the_cited_construction",
        "test_fractal_lattice_exploration.py::test_runtime_stays_under_the_declared_budget",
        "test_fractal_lattice_exploration.py::test_rung_control_laws_declare_the_same_channel_under_different_shapes",
        "test_fractal_memory_exploration.py::test_analysis_only_packet_passes_leave_the_canonical_state_untouched",
        "test_fractal_metric_exploration.py::test_declared_family_is_bounded_complete_and_seeded",
        "test_fractal_metric_exploration.py::test_every_profile_has_positive_inverse_mass_and_a_set_hook",
        "test_fractal_metric_exploration.py::test_randomized_construction_is_seed_bound_and_reproducible",
        "test_fractal_metric_exploration.py::test_graded_family_is_monotone_in_pool_distance",
        "test_fractal_metric_exploration.py::test_the_declared_1_3_ladder_is_the_fields_own_inertia_ladder",
        "test_fractal_metric_exploration.py::test_ladder_normalization_holds_the_total_inertia_fixed",
        "test_fractal_metric_exploration.py::test_matched_random_control_keeps_the_multiset_and_breaks_the_order",
        "test_fractal_metric_exploration.py::test_decay_gap_bands_follow_the_declared_tolerance_can_fail",
        "test_fractal_parent_summary_application_exploration.py::test_frozen_parent_blocks_l_register_rewrite",
        "test_fractal_parent_summary_nested_exploration.py::test_partial_and_duplicate_paths_fail_closed",
        "test_fractal_parent_summary_nested_exploration.py::test_direct_reads_are_page_owned_and_roundtrip",
        "test_fractal_parent_summary_nested_exploration.py::test_marker_partial_and_unsupported_map_mutations_fail_closed",
        "test_fractal_parent_summary_nested_exploration.py::test_resolution_and_regional_paths_reject_active_map",
        "test_fractal_parent_summary_retention.py::test_absent_legacy_workspace_remains_compatible",
        "test_fractal_parent_summary_retention.py::test_active_register_is_explicitly_rejected_by_other_layout_paths",
        "test_fractal_parent_summary_retention.py::test_write_predecessor_is_immutable_and_bind_advance_impulse_preserve",
        "test_fractal_recursive_memory_cell.py::test_frozen_parent_route_remains_locked_until_release",
        "test_fractal_survival_exploration.py::test_default_profile_is_the_canonical_default",
        "test_frame_search_probe.py::test_search_bookkeeping_finds_the_greedy_exchange_trap_frame",
        "test_frame_search_probe.py::test_span_test_is_dimension_general",
    ),
    "t18_frame_search_probe": (
        "test_frame_search_probe.py::test_connected_chain_verdict_and_connectivity",
        "test_frame_search_probe.py::test_certificates_reverify_on_every_frame_case",
        "test_frame_search_probe.py::test_switch_population_digest_is_pinned",
        "test_frame_search_probe.py::test_full_rank_dual_and_frame_screen_are_zero_dimensional",
        "test_frame_search_probe.py::test_rank_one_dual_uses_singleton_coverage",
    ),
    "t19_frame_separation_probe": (
        "test_frame_separation_probe.py::test_direct_sum_width_law_and_block_witness",
        "test_general_intelligence_program.py::test_training_blocks_have_three_construction_and_one_selection_event",
        "test_general_matched_field.py::test_public_steps_bulk_solve_and_checkpoint_are_identical",
        "test_general_matched_field.py::test_tampered_checkpoint_and_malformed_formulas_fail_closed",
        "test_generation2_isotropic_rollout_field.py::test_same_regime_chunks_cannot_release_anisotropy",
        "test_generation2_isotropic_rollout_field.py::test_unguarded_control_reenters_after_two_calls_and_checkpoint_preserves_guard",
    ),
    "t20_generation2_isotropic_rollou": (
        "test_generation2_isotropic_rollout_field.py::test_distinct_regimes_release_once_and_repeated_chunks_stay_bounded",
        "test_generation2_isotropic_rollout_field.py::test_distinct_release_is_nonworse_on_chronological_holdout",
        "test_hierarchical_covariant_recurrent_field.py::test_hierarchical_shrinkage_releases_only_supported_departure",
        "test_hierarchical_covariant_recurrent_field.py::test_same_field_commutes_with_units_and_rigid_rotation",
        "test_hierarchical_covariant_recurrent_field.py::test_checkpoint_target_blindness_and_row_order_are_exact",
    ),
    "t21_hybrid_inference": (
        "test_hybrid_inference.py::test_parity_proof_recovers_cnf_equations_and_cancels_them",
        "test_hybrid_inference.py::test_mixed_proof_requires_the_counting_to_parity_bridge",
        "test_hybrid_inference.py::test_connected_matched_class_has_the_claimed_checked_proof_formula",
        "test_hybrid_inference.py::test_mixed_class_recognizer_rejects_disconnected_local_components",
        "test_hybrid_inference.py::test_incomplete_parity_block_and_missing_capacity_edge_do_not_prove_unsat",
        "test_hybrid_inference.py::test_extension_definition_is_used_by_a_checked_resolution_refutation",
        "test_hybrid_inference.py::test_independent_checker_rejects_semantically_false_cross_system_steps",
        "test_hybrid_inference.py::test_state_is_immutable_exactly_persistent_and_deterministic",
        "test_hybrid_inference.py::test_resource_exhaustion_never_becomes_an_unsat_claim",
        "test_hybrid_inference.py::test_regional_hybrid_quantum_one_round_trips_and_preserves_native_outcomes",
        "test_lagrangian_recurrent_field.py::test_recurrent_field_transfers_delayed_identity_authority",
        "test_lagrangian_recurrent_field.py::test_forecast_is_prewrite_restart_exact_and_target_blind",
        "test_lagrangian_recurrent_field.py::test_identity_row_order_is_canonical_field_input",
        "test_learning_computer_owner.py::test_a_resource_wait_while_validating_is_a_wait_not_an_invalid_image",
        "test_learning_computer_owner.py::test_paged_resource_wait_releases_staged_pages_for_retry",
        "test_learning_computer_owner.py::test_resident_model_fused_resume_preserves_next_stage_and_token",
    ),
    "t22_learning_computer_owner": (
        "test_learning_computer_owner.py::test_resident_model_cycle_commits_exact_scheduler_result_once",
        "test_learning_computer_owner.py::test_optional_computer_page_does_not_change_empty_atlas_encoding",
        "test_learning_computer_owner.py::test_semantic_mechanism_coverage_causal_meanings_and_planner_contract",
        "test_learning_computer_owner.py::test_semantic_prediction_preserves_set_probability_and_model_family",
        "test_learning_computer_owner.py::test_semantic_predictive_state_freezes_signature_and_first_split",
        "test_learning_computer_owner.py::test_semantic_weighted_mechanism_requires_named_probability_model",
        "test_learning_computer_owner.py::test_semantic_parameter_statistics_analytic_family_and_deduplication",
        "test_learning_computer_owner.py::test_semantic_parameter_refinement_conserves_current_mass_and_zero_support",
        "test_learning_computer_owner.py::test_semantic_candidate_activation_freezes_boundary_before_new_evidence",
        "test_learning_computer_owner.py::test_semantic_representation_uses_training_fit_after_equal_holdout",
        "test_learning_computer_owner.py::test_semantic_discovery_transfers_into_ordinary_query_and_language",
        "test_learning_computer_owner.py::test_semantic_affine_representation_reads_exact_binding_packet_transiently",
        "test_learning_computer_owner.py::test_semantic_migration_consolidation_recovery_and_revocation",
        "test_learning_computer_owner.py::test_autonomous_learning_selects_and_executes_field_owned_opportunity",
        "test_learning_computer_owner.py::test_regional_program_resolution_floor_blocks_subprecision_promotion",
        "test_mandatory_class_obstruction_probe.py::test_general_position_has_minimal_mandatory_obstruction",
        "test_mandatory_class_obstruction_probe.py::test_cap_is_inconclusive_not_negative",
        "test_mandatory_class_obstruction_probe.py::test_original_column_census_preserves_projective_duplicates",
        "test_mixed_exact_one_decision.py::test_step_checkpoint_and_bulk_solve_are_exactly_equivalent",
        "test_mixed_exact_one_decision.py::test_descriptor_corruption_and_noncanonical_formula_fail_closed",
        "test_owner_nested_cycle.py::test_an_incomplete_factor_table_is_not_a_factorial",
        "test_owner_nested_cycle.py::test_the_declared_margin_predicate_can_fail_both_ways",
        "test_owner_surface_options.py::test_the_opt_in_input_helper_reproduces_the_shipped_declared_input",
        "test_owner_surface_options.py::test_a_second_reading_of_the_shipped_default_leaves_the_owner_state_alone",
        "test_owner_surface_options.py::test_the_coupled_realization_carries_nothing_at_zero_drive",
        "test_owner_write_path_exploration.py::test_the_design_quotes_in_the_port_reading_are_verbatim",
    ),
    "t23_regime_covariant_recurrent_f": (
        "test_regime_covariant_recurrent_field.py::test_field_learns_identity_bound_covariant_correction",
        "test_regime_covariant_recurrent_field.py::test_same_field_commutes_with_units_and_rigid_rotation",
        "test_regime_covariant_recurrent_field.py::test_checkpoint_target_blindness_and_row_order_are_exact",
        "test_resonant_field.py::test_metric_restriction_is_reversible_and_unweighted_control_fails",
        "test_resonant_field.py::test_reciprocal_exchange_cancels_and_nonreciprocal_control_does_not",
        "test_resonant_field.py::test_stage_guard_and_interface_work_survive_regional_roundtrip",
        "test_resonant_field.py::test_alignment_symmetry_tangency_and_unprojected_control",
        "test_resonant_field.py::test_hierarchy_bounds_acyclic_degenerate_axis_and_stale_coverage",
        "test_resonant_field.py::test_activity_values_empty_bounded_and_geometry_sensitive",
        "test_resonant_owner.py::test_temporal_pool_impulse_is_work_bounded_and_propagates",
        "test_resonant_owner.py::test_resonant_regional_advance_pauses_and_restarts_exactly",
        "test_resonant_owner.py::test_dual_helical_packet_hierarchy_roundtrips_and_rejects_mixed_sources",
        "test_resonant_owner.py::test_helical_packet_impulse_matches_the_regional_field_transition",
        "test_scale_composition_surface.py::test_a_missing_control_is_never_read_as_evidence",
        "test_scale_composition_surface.py::test_the_composition_branch_needs_presence_separation_and_the_count_test",
        "test_scale_composition_surface.py::test_a_sweep_that_keeps_climbing_is_named_a_budget_artifact",
        "test_scale_composition_surface.py::test_a_silent_sweep_is_not_measurable_and_is_not_an_absent_reading",
        "test_scale_composition_surface.py::test_the_declared_budget_sweep_publishes_both_floor_terms_separately",
        "test_scale_composition_surface.py::test_a_reading_that_scales_with_the_drive_can_never_clear_the_declared_rule",
        "test_scale_composition_surface.py::test_an_equal_count_test_alone_does_not_make_a_composition_verdict",
        "test_scale_composition_surface.py::test_a_nonfinite_arm_makes_the_level_inconclusive",
        "test_store_addressing_capacity.py::test_the_declared_family_is_the_port_count_at_every_resolution",
        "test_store_addressing_tree.py::test_the_declared_cap_selects_the_head_and_the_tail_of_the_level_order",
        "test_store_addressing_tree.py::test_the_declared_family_leaves_the_deeper_triples_to_the_port_fallback",
        "test_switch_neighborhood_probe.py::test_complete_one_switch_populations_are_pinned",
        "test_switch_neighborhood_probe.py::test_switch_replay_preserves_cubic_canonical_structure",
        "test_switch_neighborhood_probe.py::test_runner_and_independent_search_agree_on_controls_and_neighbors",
        "test_switch_neighborhood_probe.py::test_low_nullity_search_is_trivially_frame",
        "test_switch_neighborhood_probe.py::test_trivial_evaluators_record_an_independent_witness",
        "test_switch_neighborhood_probe.py::test_synthetic_positive_and_negative_anchors_fire",
        "test_switch_neighborhood_probe.py::test_two_switch_walk_replay_is_seed_deterministic",
        "test_temporal_field.py::test_skills_make_progress_and_remain_independently_addressable",
        "test_temporal_field.py::test_skill_pool_signal_is_a_fixed_readout_of_safe_temporal_rank",
        "test_temporal_field.py::test_supported_step_recovers_active_context_without_erasing_prior_gap",
        "test_temporal_field.py::test_context_discovery_preserves_conflicting_continuations_and_rebuild_counts",
        "test_temporal_field.py::test_numeric_and_metadata_corruption_cannot_enter_canonical_state",
        "test_temporal_field.py::test_codec_relabel_cannot_reinterpret_serialized_transitions",
        "test_temporal_field.py::test_equal_outcome_sets_do_not_erase_distinct_observed_frequencies",
        "test_temporal_field.py::test_partial_action_coverage_preserves_recurrent_history",
        "test_temporal_field.py::test_participant_bindings_keep_independent_numeric_working_coordinates",
        "test_temporal_field.py::test_learning_replays_retained_events_after_state_number_remapping",
        "test_temporal_field.py::test_unknown_reset_false_exposes_all_candidates_without_hidden_state",
        "test_temporal_field.py::test_numeric_history_and_participants_survive_exact_reload",
        "test_temporal_field.py::test_learning_revalidates_skill_identity_and_safe_action",
        "test_temporal_field.py::test_registered_skill_forms_only_after_a_supported_safe_root_path_exists",
        "test_temporal_field.py::test_history_overflow_is_reported_unresolved_on_learning",
        "test_temporal_field.py::test_at_state_is_ephemeral_and_cannot_consume",
        "test_temporal_field.py::test_unknown_start_history_replays_without_inventing_root_context",
        "test_temporal_field.py::test_learning_preserves_observed_completion_but_projection_cannot_claim_it",
        "test_temporal_field.py::test_participant_relabel_cannot_reinterpret_serialized_working_memory",
        "test_temporal_field.py::test_missing_probe_does_not_erase_a_hazard_bearing_alternative",
        "test_temporal_field.py::test_forbidden_outcomes_refine_recursively_merged_successor_contexts",
        "test_temporal_field.py::test_supported_effects_transfer_orders_and_long_delays_without_losing_context",
        "test_temporal_field.py::test_small_sampling_difference_does_not_split_equivalent_stochastic_contexts",
        "test_temporal_field.py::test_first_codec_action_can_be_condensed_and_executed",
        "test_temporal_field.py::test_regional_temporal_pause_replay_participants_and_unknown_support",
        "test_temporal_inquiry.py::test_two_step_observation_policy_resolves_when_no_one_step_test_does",
        "test_temporal_inquiry.py::test_unauthorized_or_infeasible_operations_are_refused",
        "test_temporal_inquiry.py::test_forbidden_or_missing_support_cannot_be_certified",
        "test_temporal_inquiry.py::test_repeated_noninformative_observations_remain_unresolved",
        "test_temporal_inquiry.py::test_input_schema_and_budget_are_bounded",
        "test_temporal_inquiry.py::test_permitted_missing_support_is_acquisition_not_resolution",
        "test_temporal_inquiry.py::test_acquisition_prefers_observed_information_over_name_and_cost",
        "test_temporal_inquiry.py::test_singleton_gap_can_request_bounded_acquisition",
        "test_temporal_inquiry.py::test_missing_support_without_permission_remains_refused",
        "test_temporal_inquiry.py::test_known_forbidden_outcome_blocks_acquisition",
        "test_temporal_inquiry.py::test_supported_observation_discrimination_precedes_acquisition",
        "test_temporal_inquiry.py::test_transient_goal_policy_acts_without_persisting_a_skill",
        "test_temporal_inquiry.py::test_carried_unknown_branch_cannot_certify_apparent_discrimination",
        "test_temporal_inquiry.py::test_regional_inquiry_pause_resume_preserves_policy_and_logical_work",
        "test_temporal_inquiry.py::test_regional_inquiry_failed_assumption_is_explicit_and_non_authoritative",
        "test_temporal_materialized_composition.py::test_mismatch_fails_closed_without_field_mutation",
        "test_temporal_materialized_composition.py::test_wrong_expected_state_is_rejected_without_owner_mutation",
        "test_temporal_tasks.py::test_regional_temporal_task_state_resumes_reset_and_projects_scope",
        "test_variational_field.py::test_conflicting_writes_settle_to_the_covariance_conditional",
        "test_variational_field.py::test_robust_readout_checks_more_than_the_nominal_runner_up",
        "test_variational_field.py::test_regional_variational_pause_resume_preserves_allowance_and_work",
        "test_width_two_constructor_probe.py::test_candidate_verifier_fails_closed_on_missing_or_invalid_basis",
        "test_yang_mills_compression_matrix.py::test_fuse_perturbation_control_fires",
        "test_yang_mills_compression_matrix.py::test_mf_invariance_recomputed_in_process",
        "test_yang_mills_finite_obligations.py::test_fuse_rule_is_the_declared_half_integer_spectrum",
        "test_yang_mills_finite_obligations.py::test_corner_shift_drops_the_down_shift_only_at_label_zero",
        "test_yang_mills_finite_obligations.py::test_reachable_count_is_sensitive_to_the_down_shift",
        "test_yang_mills_finite_obligations.py::test_anchor_table_recomputed_and_check_fires_on_corruption",
    ),
    "t24_yang_mills_finite_obligation": (
        "test_yang_mills_finite_obligations.py::test_pairing_independence_with_falsification_margin",
        "test_yang_mills_finite_obligations.py::test_relabelling_invariance_check_can_fail",
        "test_yang_mills_finite_obligations.py::test_fine_multiplicity_never_zero_with_spread_margin",
        "test_yang_mills_finite_obligations.py::test_rank_screen_is_sensitive_to_the_margin_d",
    ),
}


# Each workload and the reading it declares steady: wall seconds for in-process work, process CPU seconds
# where wall time includes spawned processes (the library's git reads) or durable-write waits (the tests).
WORKLOADS = {
    "owner": (workload_owner, "seconds"),
    "library": (workload_library, "cpu"),
    **{name: (functools.partial(workload_tests, nodes), "cpu") for name, nodes in TEST_WORKLOADS.items()},
}


def run(corpus: Path, warm_corpus: Path, names, *, profilers=None, touched=None, targets=(), dump=None) -> tuple[dict, dict]:
    _CORPORA.update({0: corpus, 1: warm_corpus})
    counter = _DurableCounter()
    counter.install()
    results = {}
    clock = _TargetClock(targets)
    scratch_root = Path(tempfile.mkdtemp(prefix="cassi-anchor-"))
    try:
        for name in names:
            scratch = scratch_root / "warm" / name
            scratch.mkdir(parents=True)
            WORKLOADS[name][0](scratch, 1)
        if targets:
            clock.install()
        for name in names:
            function, reading = WORKLOADS[name]
            scratch = scratch_root / name
            scratch.mkdir()
            before = (counter.fsync, counter.replace)
            profiler = None
            if profilers is not None:
                import cProfile

                profiler = profilers[name] = cProfile.Profile()
                profiler.enable()
            recorder = _Touched() if touched is not None else contextlib.nullcontext()
            with recorder:
                cpu = time.process_time()
                started = time.perf_counter()
                value = function(scratch, 0)
                seconds = time.perf_counter() - started
                cpu = time.process_time() - cpu
            if profiler is not None:
                profiler.disable()
            if touched is not None:
                touched[name] = recorder.files
            if dump is not None:
                dump[name] = value
            results[name] = {
                "seconds": seconds,
                "cpu": cpu,
                "reading": seconds if reading == "seconds" else cpu,
                "digest": _sha(value),
                "fsync": counter.fsync - before[0],
                "replace": counter.replace - before[1],
            }
        if targets:
            clock.remove()
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
    return results, clock.report()


def _profile_rows(profilers: dict) -> list[dict]:
    import pstats

    merged = None
    members: dict[tuple, list[str]] = {}
    for name, profiler in profilers.items():
        stats = pstats.Stats(profiler)
        for key in stats.stats:
            members.setdefault(key, []).append(name)
        if merged is None:
            merged = stats
        else:
            merged.add(stats)
    rows = []
    for key, (_cc, ncalls, tottime, cumtime, callers) in (merged.stats.items() if merged else ()):
        filename, lineno, function = key
        rows.append({
            "file": filename, "lineno": lineno, "function": function,
            "ncalls": ncalls, "tottime": tottime, "cumtime": cumtime,
            "callers": [[caller[0], caller[1], caller[2], edge[1], edge[3]] for caller, edge in callers.items()],
            "workloads": members[key],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--overlay", action="append", default=[])
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--warm-corpus", required=True)
    parser.add_argument("--workload", action="append", choices=list(WORKLOADS), default=[])
    parser.add_argument("--profile")
    parser.add_argument("--modules")
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--dump")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    for path in [args.source_root, *reversed(args.overlay)]:
        sys.path.insert(0, str(Path(path).resolve()))
    os.chdir(args.source_root)
    corpus = Path(args.corpus).resolve()
    warm_corpus = Path(args.warm_corpus).resolve()
    names = [name for name in WORKLOADS if not args.workload or name in args.workload]
    roots = [Path(path).resolve() for path in [args.source_root, *args.overlay]]

    def inside(file: str) -> bool:
        return any(Path(file).resolve().is_relative_to(root) for root in roots)

    try:
        if args.profile:
            profilers: dict = {}
            touched: dict = {}
            result, clock = run(corpus, warm_corpus, names, profilers=profilers, touched=touched, targets=args.target)
            Path(args.profile).write_text(json.dumps({
                "rows": _profile_rows(profilers),
                "touched": {name: sorted(file for file in files if inside(file)) for name, files in touched.items()},
            }), encoding="utf-8")
        else:
            dump = {} if args.dump else None
            result, clock = run(corpus, warm_corpus, names, targets=args.target, dump=dump)
            if dump is not None:
                Path(args.dump).write_text(json.dumps(dump), encoding="utf-8")
        if args.modules:
            loaded = sorted({
                str(Path(module.__file__).resolve())
                for module in list(sys.modules.values())
                if getattr(module, "__file__", None) and inside(module.__file__)
            })
            Path(args.modules).write_text(json.dumps(loaded), encoding="utf-8")
        payload = {"ok": True, "workloads": result, **clock}
    except BaseException as exc:  # a broken candidate is an observation, not a crash of the loop
        import traceback

        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-4000:]}
    Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
