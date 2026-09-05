from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_persistent_provider import (
    PersistentFieldProvider,
    ProviderConfig,
    ProviderError,
)
from cassi_qi_world import DeterministicQiWorld
from run_text_abstraction_comparison import (
    TextAbstractionController,
    TextProgram,
    TextToken,
    evaluate_text_program,
    generate_text_programs,
)


SCHEMA = "cassi.implementation-evaluation.v2"
CANDIDATES = ("action.gaze-left", "action.gaze-right", "action.hold")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value) + b"\n")


def _provider_config(state_dir: Path) -> ProviderConfig:
    return ProviderConfig(
        phi_config_path=CONFIG_DIR / "cassi-phi-harmonic-language.json",
        corpus_checkpoint_path=(
            ARTIFACT_DIR / "cassi-phi-harmonic-language" / "field-state.pt"
        ),
        state_dir=state_dir,
        device="cpu",
        max_output_symbols=64,
    )


def _start(state_dir: Path) -> PersistentFieldProvider:
    provider = PersistentFieldProvider(_provider_config(state_dir))
    provider.start()
    return provider


def _request(
    user: str,
    operation: str,
    request_id: str,
    task_scope: str,
    **payload: Any,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "user": user,
        "identity_scope": user,
        "task_scope": task_scope,
        "request_id": request_id,
        **payload,
    }


def _action_request(
    *,
    user: str,
    task_scope: str,
    request_id: str,
    text: str,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "user": user,
        "identity_scope": user,
        "task_scope": task_scope,
        "request_id": request_id,
        "text": text,
        "selected_action": plan["decision"]["selected_action"],
        "value": 0.75,
        "authority": 1.0,
        "required_authority": 0.5,
        "authorization_path": ["publication-evaluation.explicit-authorization"],
        "plan_receipt_sha256": plan["receipt_sha256"],
    }


def _state(provider: PersistentFieldProvider, user: str) -> tuple[Any, str]:
    assert provider.store is not None
    loaded = provider.store.load(user)
    if loaded is None:
        assert provider.initial_state is not None
        state = provider.store.initial(provider.initial_state)
    else:
        state = loaded[0]
    return state, provider.store.layout.state_sha256(state)


def _scenario_and_lifecycle(
    state_dir: Path,
) -> tuple[dict[str, Any], PersistentFieldProvider]:
    provider = _start(state_dir)
    taught = provider.canonical_transition(
        _request(
            "alice",
            "teach",
            "teach-amber-right",
            "teaching",
            text="gaze right to inspect the amber marker",
            action="action.gaze-right",
        )
    )
    recalled = provider.canonical_transition(
        _request(
            "alice",
            "recall",
            "recall-new-marker",
            "recall",
            text="gaze right to inspect a new marker",
            candidates=CANDIDATES,
        )
    )
    plan = provider.canonical_transition(
        _request(
            "alice",
            "plan",
            "plan-new-marker",
            "world-inspection",
            text="gaze right to inspect a new marker",
            candidates=CANDIDATES,
        )
    )
    world = DeterministicQiWorld(
        seed=101,
        world_id="world.integrated-scenario",
        episode_id="episode.integrated-scenario",
        session_id="integrated-world",
    )
    action = provider.execute_canonical_action(
        _action_request(
            user="alice",
            task_scope="world-inspection",
            request_id="execute-new-marker",
            text="gaze right to inspect a new marker",
            plan=plan,
        ),
        world,
    )
    provider.canonical_transition(
        _request(
            "alice",
            "teach",
            "teach-blue-wrong",
            "correction",
            text="blue warning marker means gaze toward safety",
            action="action.gaze-right",
        )
    )
    corrected = provider.canonical_transition(
        _request(
            "alice",
            "correct",
            "correct-blue-left",
            "correction",
            text="blue warning marker means gaze toward safety",
            previous_action="action.gaze-right",
            action="action.gaze-left",
        )
    )
    provider.close()

    provider = _start(state_dir)
    post_restart = provider.canonical_transition(
        _request(
            "alice",
            "plan",
            "plan-blue-after-restart",
            "unseen-restart-task",
            text="blue warning marker: gaze toward safety now",
            candidates=CANDIDATES,
        )
    )
    state, state_sha256 = _state(provider, "alice")
    assert provider.store is not None
    assert provider.agency_controller is not None
    mnemic = provider.store.layout.mnemic(state)
    intact = provider.agency_controller.decide(
        mnemic,
        identity_scope="alice",
        text="blue warning marker: gaze toward safety now",
        candidates=CANDIDATES,
    )
    relevant_addresses = tuple(
        dict.fromkeys(intact.addresses["action.gaze-left"])
    )
    relevant_state = provider.agency_controller.lesion(mnemic, relevant_addresses)
    relevant = provider.agency_controller.decide(
        relevant_state,
        identity_scope="alice",
        text="blue warning marker: gaze toward safety now",
        candidates=CANDIDATES,
    )
    occupied = set().union(*map(set, intact.addresses.values()))
    unrelated_address = next(
        index for index in range(mnemic.field.numel()) if index not in occupied
    )
    unrelated_state = provider.agency_controller.lesion(mnemic, (unrelated_address,))
    unrelated = provider.agency_controller.decide(
        unrelated_state,
        identity_scope="alice",
        text="blue warning marker: gaze toward safety now",
        candidates=CANDIDATES,
    )

    crash_text = "gaze right to inspect the restart beacon"
    provider.canonical_transition(
        _request(
            "bob",
            "teach",
            "teach-crash-action",
            "crash-recovery",
            text=crash_text,
            action="action.gaze-right",
        )
    )
    crash_plan = provider.canonical_transition(
        _request(
            "bob",
            "plan",
            "plan-crash-action",
            "crash-recovery",
            text=crash_text,
            candidates=CANDIDATES,
        )
    )
    crash_request = _action_request(
        user="bob",
        task_scope="crash-recovery",
        request_id="execute-crash-action",
        text=crash_text,
        plan=crash_plan,
    )
    crash_world = DeterministicQiWorld(
        seed=102,
        world_id="world.crash-recovery",
        episode_id="episode.crash-recovery",
        session_id="crash-world",
    )
    _, before_crash_sha256 = _state(provider, "bob")
    simulated_crash = False
    try:
        provider.execute_canonical_action(
            crash_request,
            crash_world,
            crash_after_dispatch=True,
        )
    except ProviderError as error:
        simulated_crash = "simulated crash" in str(error)
    _, after_crash_sha256 = _state(provider, "bob")
    provider.close()
    provider = _start(state_dir)
    recovered = provider.reconcile_canonical_actions(
        identity_scope="bob",
        world=crash_world,
    )
    duplicate = provider.execute_canonical_action(crash_request, crash_world)
    _, after_recovery_sha256 = _state(provider, "bob")

    withheld_text = "gaze left to inspect the withheld marker"
    provider.canonical_transition(
        _request(
            "carol",
            "teach",
            "teach-withheld",
            "withheld-observation",
            text=withheld_text,
            action="action.gaze-left",
        )
    )
    withheld_plan = provider.canonical_transition(
        _request(
            "carol",
            "plan",
            "plan-withheld",
            "withheld-observation",
            text=withheld_text,
            candidates=CANDIDATES,
        )
    )
    withheld_world = DeterministicQiWorld(
        seed=103,
        world_id="world.withheld",
        episode_id="episode.withheld",
        session_id="withheld-world",
    )
    _, withheld_before = _state(provider, "carol")
    withheld = provider.execute_canonical_action(
        _action_request(
            user="carol",
            task_scope="withheld-observation",
            request_id="execute-withheld",
            text=withheld_text,
            plan=withheld_plan,
        ),
        withheld_world,
        withhold_observation=True,
    )
    _, withheld_after = _state(provider, "carol")

    assert provider.agency_controller is not None
    result = {
        "sequence": [
            "teach",
            "recall",
            "plan",
            "authorize",
            "execute",
            "observe",
            "correct",
            "restart",
            "unseen-task",
        ],
        "teach_receipt_sha256": taught["receipt_sha256"],
        "recall_selected_action": recalled["decision"]["selected_action"],
        "plan_selected_action": plan["decision"]["selected_action"],
        "action": {
            "stage": action["stage"],
            "status": action["status"],
            "world_effect": action["world_effect"],
            "receipt_sha256": action["receipt_sha256"],
        },
        "correction_receipt_sha256": corrected["receipt_sha256"],
        "post_restart_selected_action": post_restart["decision"]["selected_action"],
        "post_restart_state_sha256": state_sha256,
        "lesions": {
            "intact": intact.selected_action,
            "relevant": relevant.selected_action,
            "unrelated": unrelated.selected_action,
            "relevant_address_count": len(relevant_addresses),
        },
        "crash_recovery": {
            "simulated_crash_reached": simulated_crash,
            "field_unchanged_before_reconcile": (
                before_crash_sha256 == after_crash_sha256
            ),
            "recovered_count": len(recovered),
            "recovered_stage": None if not recovered else recovered[0]["stage"],
            "field_changed_once": after_recovery_sha256 != before_crash_sha256,
            "duplicate_response_identical": duplicate == recovered[0],
            "world_tick_after_duplicate": crash_world.logical_tick,
        },
        "withheld_observation": {
            "stage": withheld["stage"],
            "world_tick": withheld_world.logical_tick,
            "field_unchanged": withheld_before == withheld_after,
        },
        "ownership": {
            "provider_fingerprint": provider.provider_fingerprint,
            "agency_codec_fingerprint": provider.agency_controller.fingerprint,
            "adaptive_sidecars": taught["receipt"]["adaptive_sidecars"],
            "external_model_calls": taught["receipt"]["external_model_calls"],
        },
    }
    result["status"] = (
        "supported"
        if (
            result["recall_selected_action"] == "action.gaze-right"
            and result["plan_selected_action"] == "action.gaze-right"
            and result["action"]["stage"] == "observed"
            and result["post_restart_selected_action"] == "action.gaze-left"
            and result["lesions"]["relevant"] != result["lesions"]["intact"]
            and result["lesions"]["unrelated"] == result["lesions"]["intact"]
            and all(
                (
                    result["crash_recovery"]["simulated_crash_reached"],
                    result["crash_recovery"]["field_unchanged_before_reconcile"],
                    result["crash_recovery"]["recovered_count"] == 1,
                    result["crash_recovery"]["field_changed_once"],
                    result["crash_recovery"]["duplicate_response_identical"],
                    result["crash_recovery"]["world_tick_after_duplicate"] == 1,
                    result["withheld_observation"]["field_unchanged"],
                )
            )
        )
        else "unsupported"
    )
    return result, provider


def _capacity_and_supersession(provider: PersistentFieldProvider) -> dict[str, Any]:
    assert provider.agency_controller is not None
    address_by_feature: dict[str, int] = {}
    address_writes = 0
    prior_state = None
    last_state = None
    for index in range(32):
        text = f"signal token{index} means gaze right"
        learned = provider.canonical_transition(
            _request(
                "capacity",
                "teach",
                f"capacity-{index}",
                "capacity",
                text=text,
                action="action.gaze-right",
            )
        )
        features = provider.agency_controller.features(text)
        learned_addresses = learned["addresses"]
        address_writes += len(learned_addresses)
        for feature, address in zip(features, learned_addresses, strict=True):
            address_by_feature[f"{feature}\0action.gaze-right"] = address
        prior_state = learned["receipt"]["state_in_sha256"]
        last_state = learned["receipt"]["state_out_sha256"]
    provider.canonical_transition(
        _request(
            "capacity",
            "teach",
            "contradiction-right",
            "contradiction",
            text="contradictory marker",
            action="action.gaze-right",
        )
    )
    provider.canonical_transition(
        _request(
            "capacity",
            "teach",
            "contradiction-left",
            "contradiction",
            text="contradictory marker",
            action="action.gaze-left",
        )
    )
    contradiction = provider.canonical_transition(
        _request(
            "capacity",
            "plan",
            "contradiction-plan",
            "contradiction",
            text="contradictory marker",
            candidates=CANDIDATES,
        )
    )
    provider.canonical_transition(
        _request(
            "capacity",
            "teach",
            "supersession-old",
            "supersession",
            text="supersession marker",
            action="action.gaze-right",
        )
    )
    corrected = provider.canonical_transition(
        _request(
            "capacity",
            "correct",
            "supersession-correct",
            "supersession",
            text="supersession marker",
            previous_action="action.gaze-right",
            action="action.gaze-left",
        )
    )
    supersession = provider.canonical_transition(
        _request(
            "capacity",
            "plan",
            "supersession-plan",
            "supersession",
            text="supersession marker",
            candidates=CANDIDATES,
        )
    )
    state, _ = _state(provider, "capacity")
    assert provider.store is not None
    field_cells = provider.store.layout.mnemic(state).field.numel()
    distinct_feature_addresses = tuple(address_by_feature.values())
    unique = len(set(distinct_feature_addresses))
    collision_rate = 1.0 - unique / max(1, len(distinct_feature_addresses))
    result = {
        "fact_count": 32,
        "field_cell_count": field_cells,
        "address_writes": address_writes,
        "distinct_feature_action_keys": len(distinct_feature_addresses),
        "unique_addresses": unique,
        "collision_rate": collision_rate,
        "address_load": unique / field_cells,
        "contradiction_abstained": contradiction["decision"]["abstained"],
        "supersession_selected_action": supersession["decision"]["selected_action"],
        "revision_lineage": {
            "prior_state_sha256": prior_state,
            "capacity_state_sha256": last_state,
            "correction_parent_sha256": corrected["receipt"]["causal_parent_sha256"],
            "correction_state_out_sha256": corrected["receipt"]["state_out_sha256"],
        },
    }
    result["status"] = (
        "supported"
        if result["contradiction_abstained"]
        and result["supersession_selected_action"] == "action.gaze-left"
        and result["collision_rate"] < 0.1
        else "unsupported"
    )
    return result


def _target_blind_language() -> dict[str, Any]:
    programs = generate_text_programs()
    variable_programs = tuple(
        program for program in programs if len(program.tokens) <= 3
    )
    variable_controller = TextAbstractionController(
        programs=variable_programs,
        regimes=("variable",),
    )
    variable_program = TextProgram(
        (
            TextToken.PROMPT,
            TextToken.REVERSE_WORDS,
            TextToken.EMIT,
        )
    )
    training_prompts = (
        b"red fox",
        b"small amber marker",
        b"one two three four",
        b"mixed seed ends aB3z",
    )
    variable_state = variable_controller.learn_regime(
        variable_controller.new_state(),
        "variable",
        tuple(
            (prompt, evaluate_text_program(variable_program, prompt))
            for prompt in training_prompts
        ),
    )
    variable_selection = variable_controller.select(variable_state, "variable")
    variable_selected = variable_controller.selected_program(
        variable_state, "variable"
    )
    heldout = (
        b"x y",
        b"this held out sentence is much longer than every short seed",
        b"mixed CASE representation SHIFT",
    )
    variable_outputs = (
        []
        if variable_selected is None
        else [
            evaluate_text_program(variable_selected, prompt) for prompt in heldout
        ]
    )
    variable_expected = [
        evaluate_text_program(variable_program, prompt) for prompt in heldout
    ]
    zero_selection = variable_controller.select(
        variable_controller.new_state(), "variable"
    )

    composition_program = TextProgram(
        (
            TextToken.PROMPT,
            TextToken.ASCII_UPPER,
            TextToken.SUFFIX_4,
            TextToken.REVERSE_BYTES,
            TextToken.EMIT,
        )
    )
    composition_controller = TextAbstractionController(
        programs=programs,
        regimes=("composition",),
    )
    composition_targets = [
        evaluate_text_program(composition_program, prompt)
        for prompt in training_prompts
    ]
    composition_state = composition_controller.learn_regime(
        composition_controller.new_state(),
        "composition",
        tuple(zip(training_prompts, composition_targets, strict=True)),
    )
    composition_selection = composition_controller.select(
        composition_state, "composition"
    )
    composition_selected = composition_controller.selected_program(
        composition_state, "composition"
    )
    composition_exact = composition_selected is not None and all(
        evaluate_text_program(composition_selected, prompt)
        == evaluate_text_program(composition_program, prompt)
        for prompt in heldout
    )
    shuffled_state = composition_controller.learn_regime(
        composition_controller.new_state(),
        "composition",
        tuple(
            zip(
                training_prompts,
                composition_targets[1:] + composition_targets[:1],
                strict=True,
            )
        ),
    )
    shuffled_selection = composition_controller.select(
        shuffled_state, "composition"
    )
    variable_status = (
        "supported"
        if variable_selection.status == "selected"
        and variable_selection.program_sha256 == variable_program.sha256
        and variable_outputs == variable_expected
        and len({len(value) for value in variable_outputs}) > 1
        and zero_selection.status == "exhausted"
        else "unsupported"
    )
    composition_status = (
        "supported"
        if composition_selection.status == "selected"
        and composition_selection.program_sha256 == composition_program.sha256
        and composition_exact
        and shuffled_selection.program_sha256 != composition_program.sha256
        else "unsupported"
    )
    return {
        "status": variable_status,
        "target_blind": True,
        "target_length_supplied": False,
        "termination": "finite typed program ending in EMIT",
        "training_lengths": [len(value) for value in training_prompts],
        "heldout_lengths": [len(value) for value in heldout],
        "output_lengths": [len(value) for value in variable_outputs],
        "selected_status": variable_selection.status,
        "selected_program_sha256": variable_selection.program_sha256,
        "target_program_sha256": variable_program.sha256,
        "heldout_exact": variable_outputs == variable_expected,
        "field_zero_status": zero_selection.status,
        "field_counterfactual_changes_result": (
            zero_selection.status != variable_selection.status
        ),
        "composition_status": composition_status,
        "selected_composition_depth": (
            None if composition_selected is None else len(composition_selected.tokens) - 2
        ),
        "composition_heldout_exact": composition_exact,
        "shuffled_composition_program_sha256": (
            shuffled_selection.program_sha256
        ),
    }


def _risk_and_baselines(provider: PersistentFieldProvider) -> tuple[dict[str, Any], dict[str, Any]]:
    training = (
        ("red beacon means gaze right", "action.gaze-right"),
        ("amber beacon means gaze right", "action.gaze-right"),
        ("blue barrier means gaze left", "action.gaze-left"),
        ("violet barrier means gaze left", "action.gaze-left"),
    )
    for index, (text, action) in enumerate(training):
        provider.canonical_transition(
            _request(
                "risk",
                "teach",
                f"risk-teach-{index}",
                "risk",
                text=text,
                action=action,
            )
        )
    queries = (
        ("red beacon means gaze right now", "action.gaze-right"),
        ("amber beacon means gaze right again", "action.gaze-right"),
        ("blue barrier means gaze left now", "action.gaze-left"),
        ("violet barrier means gaze left again", "action.gaze-left"),
        ("unseen quartz object", None),
        ("novel silver condition", None),
        ("unknown moving pattern", None),
        ("unrelated task request", None),
    )
    decisions = []
    for index, (text, expected) in enumerate(queries):
        response = provider.canonical_transition(
            _request(
                "risk",
                "plan",
                f"risk-plan-{index}",
                "risk-evaluation",
                text=text,
                candidates=CANDIDATES,
            )
        )
        decision = response["decision"]
        selected_action = decision["selected_action"]
        action_correct = expected is not None and selected_action == expected
        appropriate_abstention = expected is None and selected_action is None
        decisions.append(
            {
                "text": text,
                "expected": expected,
                "selected": selected_action,
                "selection_strength": decision["selection_strength"],
                "action_correct": action_correct,
                "appropriate_abstention": appropriate_abstention,
                "correct": action_correct or appropriate_abstention,
            }
        )
    attempted = [item for item in decisions if item["selected"] is not None]
    risk_curve = []
    for threshold in (0.0, 0.25, 0.5, 0.75):
        selected = [
            item
            for item in attempted
            if item["selection_strength"] >= threshold
        ]
        risk_curve.append(
            {
                "threshold": threshold,
                "coverage": len(selected) / len(decisions),
                "selective_accuracy": (
                    None
                    if not selected
                    else sum(bool(item["action_correct"]) for item in selected)
                    / len(selected)
                ),
            }
        )
    known = [item for item in decisions if item["expected"] is not None]
    unknown = [item for item in decisions if item["expected"] is None]
    risk = {
        "case_count": len(decisions),
        "score_semantics": "nonprobabilistic normalized field support-separation",
        "probabilities_emitted": False,
        "ece": "not_measured",
        "brier": "not_measured",
        "risk_coverage": risk_curve,
        "known_action_accuracy": (
            sum(bool(item["action_correct"]) for item in known) / len(known)
        ),
        "unknown_abstention_rate": (
            sum(bool(item["appropriate_abstention"]) for item in unknown)
            / len(unknown)
        ),
        "cases": decisions,
    }
    risk["status"] = (
        "supported"
        if risk["known_action_accuracy"] == 1.0
        and risk["unknown_abstention_rate"] == 1.0
        else "unsupported"
    )

    state, _ = _state(provider, "risk")
    assert provider.store is not None
    assert provider.agency_controller is not None
    mnemic = provider.store.layout.mnemic(state)
    benchmark_queries = tuple((text, expected) for text, expected in queries if expected)
    start = time.perf_counter_ns()
    for _ in range(100):
        for text, _ in benchmark_queries:
            provider.agency_controller.decide(
                mnemic,
                identity_scope="risk",
                text=text,
                candidates=CANDIDATES,
            )
    field_ns = time.perf_counter_ns() - start

    def tokens(text: str) -> set[str]:
        return set(text.casefold().split())

    def nearest(text: str) -> str:
        query = tokens(text)
        score, action = max(
            (
                len(query & tokens(train_text)) / len(query | tokens(train_text)),
                train_action,
            )
            for train_text, train_action in training
        )
        assert score >= 0.0
        return action

    start = time.perf_counter_ns()
    for _ in range(100):
        for text, _ in benchmark_queries:
            nearest(text)
    nearest_ns = time.perf_counter_ns() - start
    field_accuracy = sum(
        provider.agency_controller.decide(
            mnemic,
            identity_scope="risk",
            text=text,
            candidates=CANDIDATES,
        ).selected_action
        == expected
        for text, expected in benchmark_queries
    ) / len(benchmark_queries)
    nearest_accuracy = sum(
        nearest(text) == expected for text, expected in benchmark_queries
    ) / len(benchmark_queries)
    resources = {
        "case_count": len(benchmark_queries),
        "repetitions": 100,
        "field": {
            "accuracy": field_accuracy,
            "latency_ns_per_case": field_ns / (100 * len(benchmark_queries)),
            "adaptive_bytes": mnemic.field.numel() * mnemic.field.element_size(),
        },
        "nearest_neighbor": {
            "accuracy": nearest_accuracy,
            "latency_ns_per_case": nearest_ns / (100 * len(benchmark_queries)),
            "adaptive_bytes": sum(
                len(text.encode("utf-8")) + len(action.encode("utf-8"))
                for text, action in training
            ),
        },
        "symbolic_oracle": {"accuracy": 1.0},
        "flop_accounting": "not measured",
        "energy_joules": None,
        "energy_measurement": "not available from the Python runtime",
        "status": "not_ready",
    }
    return risk, resources


def _cross_view_alignment(provider: PersistentFieldProvider) -> dict[str, Any]:
    pairs = (
        ("red square", "hue7 form2", "action.gaze-left"),
        ("red triangle", "hue7 form8", "action.gaze-left"),
        ("blue square", "hue3 form2", "action.gaze-right"),
        ("blue triangle", "hue3 form8", "action.gaze-right"),
    )
    for index, (view_a, view_b, action) in enumerate(pairs):
        for view, text in (("a", view_a), ("b", view_b)):
            provider.canonical_transition(
                _request(
                    "alignment",
                    "teach",
                    f"align-{index}-{view}",
                    "paired-views",
                    text=text,
                    action=action,
                )
            )
    holdout = (
        ("red circle", "action.gaze-left"),
        ("hue7 form5", "action.gaze-left"),
        ("blue circle", "action.gaze-right"),
        ("hue3 form5", "action.gaze-right"),
    )
    learned = []
    for index, (text, expected) in enumerate(holdout):
        response = provider.canonical_transition(
            _request(
                "alignment",
                "plan",
                f"align-holdout-{index}",
                "unseen-view-pairs",
                text=text,
                candidates=CANDIDATES,
            )
        )
        learned.append(response["decision"]["selected_action"] == expected)

    shuffled_actions = (
        "action.gaze-right",
        "action.gaze-left",
        "action.gaze-left",
        "action.gaze-right",
    )
    for index, ((view_a, view_b, _), action) in enumerate(zip(pairs, shuffled_actions)):
        for view, text in (("a", view_a), ("b", view_b)):
            provider.canonical_transition(
                _request(
                    "alignment-shuffled",
                    "teach",
                    f"shuffle-{index}-{view}",
                    "shuffled-pairs",
                    text=text,
                    action=action,
                )
            )
    shuffled = []
    for index, (text, expected) in enumerate(holdout):
        response = provider.canonical_transition(
            _request(
                "alignment-shuffled",
                "plan",
                f"shuffle-holdout-{index}",
                "unseen-view-pairs",
                text=text,
                candidates=CANDIDATES,
            )
        )
        shuffled.append(response["decision"]["selected_action"] == expected)
    learned_accuracy = sum(learned) / len(learned)
    shuffled_accuracy = sum(shuffled) / len(shuffled)
    result = {
        "train_pair_count": len(pairs),
        "heldout_pair_count": len(holdout),
        "learned_accuracy": learned_accuracy,
        "shuffled_correspondence_accuracy": shuffled_accuracy,
        "fixed_projection_used": False,
        "nuisance": "held-out shape/form tokens",
    }
    result["status"] = (
        "supported"
        if learned_accuracy == 1.0 and shuffled_accuracy <= 0.5
        else "unsupported"
    )
    return result


def _orthogonal_controls(scenario: Mapping[str, Any]) -> dict[str, Any]:
    lesions = scenario["lesions"]
    result = {
        "intact_selected_action": lesions["intact"],
        "relevant_field_lesion_selected_action": lesions["relevant"],
        "unrelated_field_lesion_selected_action": lesions["unrelated"],
        "deterministic_codec_ablation": "field-zero counterfactual in target-blind language evaluation",
        "conventional_baseline": "nearest-neighbor token Jaccard",
        "symbolic_oracle": "declared synthetic rule",
    }
    result["status"] = (
        "supported"
        if lesions["intact"] == "action.gaze-left"
        and lesions["relevant"] != lesions["intact"]
        and lesions["unrelated"] == lesions["intact"]
        else "unsupported"
    )
    return result


def run(state_dir: Path) -> dict[str, Any]:
    scenario, provider = _scenario_and_lifecycle(state_dir)
    try:
        capacity = _capacity_and_supersession(provider)
        language = _target_blind_language()
        risk, resources = _risk_and_baselines(provider)
        alignment = _cross_view_alignment(provider)
        orthogonal = _orthogonal_controls(scenario)
        deterministic = {
            "scenario": scenario,
            "gaps": {
                "1_capacity_contradiction_supersession": capacity,
                "2_target_blind_variable_length_language": language,
                "3_risk_coverage_calibration": risk,
                "4_learned_cross_view_alignment": alignment,
                "5_composition_representation_shift": {
                    "status": language["composition_status"],
                    "composition_depth": language["selected_composition_depth"],
                    "heldout_exact": language["composition_heldout_exact"],
                    "representation_shift": "mixed case and out-of-envelope lengths",
                    "randomized_control": "shuffled training correspondences",
                },
                "7_orthogonal_lesions_and_baselines": orthogonal,
            },
        }
        deterministic_sha256 = _sha(deterministic)
        bridge = {
            "status": "not_ready",
            "required_transport": (
                "authenticated receipt-bearing Qi-world action/observation transport"
            ),
            "adapter_present": False,
            "live_windowed_run_performed": False,
            "local_cassicosmos_learner_in_canonical_path": False,
            "rejected_substitutes": [
                "7599 deposit/step/readout mind-engine protocol",
                "retained read-only bridge receipts",
                "CPU analytic world",
            ],
            "reason": (
                "The separately authorized CassiCosmos Qi-world adapter and its "
                "windowed GPU receipt are absent. Existing 7599 field I/O cannot "
                "establish the required canonical action/observation lifecycle."
            ),
        }
        all_gaps = {
            **deterministic["gaps"],
            "6_matched_resource_benchmarks": resources,
            "8_cassifi_cassicosmos_bridge": bridge,
        }
        gap_receipts = {
            key: {
                "present": isinstance(value, Mapping),
                "status": value.get("status") if isinstance(value, Mapping) else None,
                "evidence_fields": sorted(
                    field for field in value if field != "status"
                )
                if isinstance(value, Mapping)
                else [],
            }
            for key, value in all_gaps.items()
        }
        blocking_gaps = [
            key for key, value in all_gaps.items() if value["status"] != "supported"
        ]
        result = {
            "schema": SCHEMA,
            "deterministic": deterministic,
            "deterministic_sha256": deterministic_sha256,
            "gaps": all_gaps,
            "gap_receipts": gap_receipts,
            "execution": {
                "state_root": (
                    state_dir.resolve().relative_to(ROOT).as_posix()
                    if state_dir.resolve().is_relative_to(ROOT)
                    else None
                ),
                "source_files": {
                    relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                    for relative in (
                        "cassi_canonical_runtime.py",
                        "cassi_persistent_provider.py",
                        "cassi_qi_world.py",
                        "run_text_abstraction_comparison.py",
                        "run_general_task_gauntlet.py",
                        "verification/run_implementation_evaluation.py",
                    )
                },
            },
            "readiness": {
                "canonical_runtime_complete": all(
                    value["status"] == "supported"
                    for value in deterministic["gaps"].values()
                ),
                "gap_receipts_complete": all(
                    receipt["present"] and bool(receipt["evidence_fields"])
                    for receipt in gap_receipts.values()
                ),
                "evaluation_receipts_complete": all(
                    receipt["present"] and receipt["status"] == all_gaps[key]["status"]
                    for key, receipt in gap_receipts.items()
                ),
                "implementation_complete": not blocking_gaps,
                "blocking_gaps": blocking_gaps,
                "paper_rewrite_started": False,
                "publication_status": "not_ready",
            },
        }
        return result
    finally:
        provider.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the canonical implementation and publication evaluation."
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Fresh provider state directory; defaults to a temporary directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_DIR / "portable-release" / "implementation-evaluation.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.state_dir is None:
        with tempfile.TemporaryDirectory(prefix="cassi-implementation-") as temporary:
            result = run(Path(temporary) / "state")
    else:
        if args.state_dir.exists() and any(args.state_dir.iterdir()):
            raise SystemExit("--state-dir must be empty for deterministic evaluation")
        result = run(args.state_dir)
    _write(args.output, result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
