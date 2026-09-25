from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

import pytest

import cassi_trading_field as trading_field  # type: ignore[import-not-found]
from cassi_trading_field import (  # type: ignore[import-not-found]
    MODEL_OUTPUTS,
    CanonicalFieldConsumer,
    CanonicalFieldPaperConsumer,
    MarketBar,
    _declared_workspace_bytes,
    TradingField,
    TradingFieldConfig,
    generate_demo_bars,
)
from cassi_paper import PaperConfig  # type: ignore[import-not-found]
from cassi_field_hive import Review  # type: ignore[import-not-found]
from cassi_field_program import semantic_program_payload  # type: ignore[import-not-found]
from cassi_hive_coordinator import HiveCoordinator  # type: ignore[import-not-found]
from cassi_market_ingestion import IngestionStore  # type: ignore[import-not-found]


def small_config() -> TradingFieldConfig:
    return TradingFieldConfig(
        symbol="BTC-USD",
        feature_windows=(1, 2, 4, 8),
        outcome_horizons=(1, 3),
        action_levels=(-1.0, 0.0, 1.0),
        warmup_bars=8,
        decision_interval=2,
        model_window=16,
        semantic_evaluation_decisions=4,
        episode_batch_decisions=4,
        update_thresholds=(4,),
        update_interval=16,
        field_mode_count=196_608,
        minimum_action_edge=0.0,
    )


def test_rich_multihorizon_experience_restarts_exactly() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = generate_demo_bars(32, symbol=config.symbol)
        def loaded_programs(resident: TradingField) -> dict[int, dict]:
            programs: dict[int, dict] = {}
            for horizon in config.outcome_horizons:
                model = resident._load_model_for_horizon(horizon)
                assert model is not None
                program = model["program"]
                assert isinstance(program, dict)
                programs[horizon] = program
            return programs

        with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
            first = field.run(bars)
            assert first["decision_count"] >= 8
            assert first["model_update_count"] == 2
            assert first["ownership"]["computer_count"] == 1
            assert first["ownership"]["computer_id"] == "main"
            assert first["ownership"]["legacy_adaptive_objects"] == 0
            before_state = first["field_state_sha256"]
            before_ledger = first["ledger_head_sha256"]
            outcomes = field.ledger.rows("outcome")
            assert {int(row["payload"]["horizon"]) for row in outcomes} == {1, 3}
            example = outcomes[0]["payload"]
            assert example["causal_status"] == "observational-no-market-impact-model"
            assert example["observed_policy_path"]["provenance"] == "observed-account-path-with-later-policy-actions"
            assert len(example["modeled_actions"]) == len(config.action_levels)
            assert sum(bool(row["selected_action"]) for row in example["modeled_actions"]) == 1
            state = example["state"]
            assert {
                "regime_trend_up",
                "regime_trend_down",
                "regime_range",
                "regime_transition",
                "regime_reversal",
                "regime_volatility_expansion",
                "regime_volatility_compression",
                "regime_liquidity_shock",
            }.issubset(state)
            assert (
                state["regime_trend_up"]
                + state["regime_trend_down"]
                + state["regime_range"]
                == 1.0
            )
            updates = field.ledger.rows("model-update")
            assert all(
                "regime-conditioned"
                in row["payload"]["candidate_diagnostics"]
                for row in updates
            )
            assert all(
                row["payload"]["diagnostics"]["context_selection"]["mode"]
                == "discovered-hierarchy"
                for row in updates
            )
            before_programs = loaded_programs(field)
            assert all(
                program["program_kind"] == "context-tree"
                for program in before_programs.values()
            )
            assert all(row["provenance"] == "modeled-fixed-exposure-on-observed-price-path" for row in example["modeled_actions"])
            later_decisions = [row["payload"] for row in field.ledger.rows("decision") if row["payload"]["bar_index"] >= 16]
            assert any(any(candidate["predictions"] for candidate in row["candidate_predictions"]) for row in later_decisions)

        with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
            assert reopened.status()["field_state_sha256"] == before_state
            assert reopened.status()["ledger_head_sha256"] == before_ledger
            assert loaded_programs(reopened) == before_programs
            replay = reopened.run(bars)
            assert replay["admitted_bars"] == 0
            assert replay["replayed_bars"] == len(bars)
            assert replay["field_state_sha256"] == before_state
            assert replay["ledger_head_sha256"] == before_ledger


def test_hive_exports_semantic_skills_and_import_toggle_is_independent() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
            field.run(generate_demo_bars(32, symbol=config.symbol))
            status = field.skill_status()
            assert status["export_enabled"] is True
            assert status["import_enabled"] is False
            documents = field.session.hive.list_documents(
                schema="cassifi.hive.experience.v1"
            )
            semantic = [
                document["content"]["candidate"]["object"]
                for document in documents
                if document["content"]["candidate"]["kind"] == "reasoning-strategy"
                and document["content"]["candidate"]["object"].get("schema")
                == "cassi.trading-semantic-skill.v1"
            ]
            assert {int(skill["horizon"]) for skill in semantic} == {1, 3}
            coordinator = HiveCoordinator(
                field.session.hive,
                leader_instance_id="trading-test-leader",
            )
            group = next(
                group
                for group in coordinator.groups()
                if any(
                    int(capsule.candidate.object.get("horizon", -1)) == 1
                    for capsule in group.capsules
                )
            )
            for reviewer in ("trading-reviewer-a", "trading-reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(
                            hashlib.sha256(reviewer.encode("utf-8")).hexdigest(),
                        ),
                    ),
                    candidate_id=group.candidate_id,
                )
            bundle = coordinator.promote(candidate_id=group.candidate_id)
            enabled = field.enable_skill_imports()
            assert enabled["import_enabled"] is True
            assert enabled["export_enabled"] is True
            assert bundle.object_id in enabled["imported_bundle_ids"]

        with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
            assert reopened.skill_status()["import_enabled"] is True
            assert bundle.object_id in reopened.skill_status()["imported_bundle_ids"]
            reopened.run(generate_demo_bars(48, symbol=config.symbol))
            updates = [
                row["payload"]
                for row in reopened.ledger.rows("model-update")
                if int(row["payload"]["horizon"]) == 1
            ]
            assert bundle.object_id in updates[-1]["imported_bundle_ids"]
            imported = {
                candidate_id: domain
                for candidate_id, domain in updates[-1]["candidate_diagnostics"].items()
                if candidate_id.startswith("hive-")
            }
            assert imported
            for domain in imported.values():
                # The contributing field's evidence is the method's provenance,
                # while admissibility is measured here, on the same reserved
                # slice and row count as every locally fitted candidate.
                assert domain["source_bundle_id"] == bundle.object_id
                assert domain["source_verification"]
                assert domain["reserved_support_gap_rows"] >= 0
                assert domain["validation_rows"] == updates[-1]["diagnostics"]["validation_rows"]
            disabled = reopened.disable_skill_imports()
            assert disabled["import_enabled"] is False
            assert disabled["export_enabled"] is True

        with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
            assert reopened.skill_status()["import_enabled"] is False
            assert reopened.skill_status()["export_enabled"] is True


def test_duplicate_bar_is_idempotent_but_revision_conflict_fails() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bar = generate_demo_bars(32, symbol=config.symbol)[0]
        with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
            admitted = field.ingest_bar(bar)
            assert admitted["status"] == "admitted"
            assert field.ingest_bar(bar)["status"] == "replayed"
            changed = {
                **bar.as_dict(),
                "close": bar.close * 1.01,
                "high": max(bar.high, bar.close * 1.01),
            }
            with pytest.raises(ValueError, match="conflicts"):
                field.ingest_bar(changed)
            assert len(field.ledger.rows("bar")) == 1


def test_proven_candidate_steers_when_the_field_choice_does_not() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = TradingFieldConfig(
            symbol="BTC-USD",
            feature_windows=(1, 2, 4, 8),
            outcome_horizons=(1, 3),
            action_levels=(-1.0, 0.0, 1.0),
            warmup_bars=8,
            decision_interval=2,
            model_window=32,
            semantic_evaluation_decisions=4,
            episode_batch_decisions=4,
            update_thresholds=(12,),
            update_interval=16,
            field_mode_count=196_608,
            minimum_action_edge=0.0,
        )
        with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
            field.run(generate_demo_bars(40, symbol=config.symbol))
            updates = [row["payload"] for row in field.ledger.rows("model-update")]
            assert updates
            for update in updates:
                proven = [
                    candidate_id
                    for candidate_id, domain in update["candidate_diagnostics"].items()
                    if domain["adequate_for_trading"]
                ]
                selected = update["selected_candidate"]
                fallback = update["proven_candidate_fallback"]
                if fallback is not None:
                    # A locally fitted candidate that proved itself better than
                    # the retained mechanism guides instead of it.
                    assert fallback in proven
                    assert selected == fallback
                elif selected == "discovered-context-tree":
                    # A retained composite carries its own reserved-slice
                    # verdict. When candidates proved themselves, the composite
                    # only keeps the role by proving itself better.
                    diagnostics = update["diagnostics"]
                    assert diagnostics["reserved_support_gap_rows"] >= 0
                    assert diagnostics["validation_rows"] > 0
                    if proven:
                        assert diagnostics["adequate_for_trading"] is True
                        assert float(diagnostics["relative_objective_loss"]) <= min(
                            update["candidate_diagnostics"][candidate_id][
                                "relative_objective_loss"
                            ]
                            for candidate_id in proven
                        )
                else:
                    assert selected in proven
            steered = [
                row["payload"]
                for row in field.ledger.rows("decision")
                if row["payload"]["selection_source"] == "field-mechanism"
            ]
            assert steered
            for decision in steered:
                chosen = float(decision["target"])
                for entry in decision["candidate_predictions"]:
                    if float(entry["target"]) != chosen:
                        continue
                    # Nothing guides a decision without proving itself first.
                    assert any(
                        prediction["adequate_for_trading"]
                        for prediction in entry["predictions"]
                    )
            state = field.status()["field_state_sha256"]
        with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
            assert reopened.status()["field_state_sha256"] == state
            assert any(
                update["kernel_selected_candidate"] == "discovered-context-tree"
                for update in (row["payload"] for row in reopened.ledger.rows("model-update"))
            )


def test_hard_stop_releases_after_cooldown_and_reenters_capped() -> None:
    def run(config: TradingFieldConfig, bars: int) -> tuple[list[dict], dict]:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
                field.run(generate_demo_bars(bars, symbol=config.symbol))
                decisions = [
                    dict(row["payload"]) for row in field.ledger.rows("decision")
                ]
                status = dict(field.status())
            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                assert reopened.status()["field_state_sha256"] == status["field_state_sha256"]
                assert reopened.status()["account"] == status["account"]
            return decisions, status

    recovery = TradingFieldConfig(
        symbol="BTC-USD",
        feature_windows=(1, 2, 4, 8),
        outcome_horizons=(1, 3),
        action_levels=(-1.0, -0.25, 0.0, 0.25, 1.0),
        warmup_bars=8,
        decision_interval=2,
        model_window=16,
        semantic_evaluation_decisions=4,
        episode_batch_decisions=4,
        update_thresholds=(8,),
        update_interval=16,
        field_mode_count=196_608,
        minimum_action_edge=0.0,
        soft_drawdown=0.01,
        hard_drawdown=0.02,
        hard_stop_cooldown_bars=8,
        hard_stop_reentry_bars=4,
        hard_stop_reentry_cap=0.25,
    )
    decisions, status = run(recovery, 96)
    sources = [decision["selection_source"] for decision in decisions]
    assert "hard-risk-gate" in sources
    assert "recovery-reentry" in sources
    halted = sources.index("hard-risk-gate")
    reentry = sources.index("recovery-reentry")
    assert reentry > halted
    assert all(
        float(decision["target"]) == 0.0 for decision in decisions[halted:reentry]
    )
    released = decisions[reentry]
    assert abs(float(released["target"])) == 0.25
    assert released["hard_stop_bar_index"] is None
    assert released["risk_drawdown"] < recovery.hard_drawdown
    assert any(
        decision["selection_source"] not in {"hard-risk-gate", "recovery-reentry"}
        for decision in decisions[reentry:]
    )

    latched = TradingFieldConfig.from_mapping(
        {
            **recovery.as_dict(),
            "hard_stop_cooldown_bars": 10_000_000,
            "hard_stop_reentry_bars": 10_000_000,
        }
    )
    latched_decisions, _ = run(latched, 48)
    latched_sources = [decision["selection_source"] for decision in latched_decisions]
    assert "hard-risk-gate" in latched_sources
    assert "recovery-reentry" not in latched_sources
    first_halt = latched_sources.index("hard-risk-gate")
    assert all(
        float(decision["target"]) == 0.0 for decision in latched_decisions[first_halt:]
    )


def test_widened_panel_carries_selected_action_levels_only() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        base = small_config()
        config = TradingFieldConfig(
            **{
                **{
                    name: getattr(base, name)
                    for name in base.as_dict()
                    if name != "compatibility_sha256"
                },
                "semantic_panel_decisions": 8,
                "semantic_panel_actions": (-1.0, 1.0),
            }
        )
        with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
            field.run(generate_demo_bars(200, symbol=config.symbol))
            updates = [row["payload"] for row in field.ledger.rows("model-update")]
            assert len(updates) >= 2
            panels = []
            for update in updates:
                decisions = (
                    update["semantic_training_decisions"]
                    + update["semantic_holdout_decisions"]
                )
                panels.append(decisions)
                # Observations are the panel decisions carried at the two
                # selected action levels, never the full action fan.
                assert update["semantic_observation_count"] == decisions * len(
                    config.semantic_panel_actions
                )
            # A later update reaches the configured panel width while the
            # action fan stays at the selected levels.
            assert max(panels) == config.semantic_panel_decisions

        # A resident field keeps the widened panel across a plain resume.
        with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
            assert reopened.config.semantic_panel_actions == config.semantic_panel_actions
            assert reopened.config.semantic_panel_decisions == config.semantic_panel_decisions
            assert reopened.config.field_mode_count == config.field_mode_count
            assert reopened.status()["bar_count"] == 200


def test_steering_gate_requires_support_margin_and_evidence() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        with TradingField.open(root / "field", hive_home=root / "hive", config=config) as field:
            field.run(generate_demo_bars(80, symbol=config.symbol))
            horizon = config.outcome_horizons[0]
            selected = field._select_model_outcomes(horizon)
            holdout_count = max(
                1,
                min(config.semantic_evaluation_decisions, len(selected) // 5),
            )
            train_rows = field._modeled_rows(selected[:-holdout_count])
            holdout_rows = field._modeled_rows(selected[-holdout_count:])
            assert holdout_rows
            program, baseline = field._fit_affine(
                train_rows,
                holdout_rows,
                state_features=(),
                action_features=(),
                candidate_id="constant-baseline",
            )
            measured, unsupported = field._program_loss(
                program,
                holdout_rows,
                candidate_id="constant-baseline",
                baseline_objective_rmse=float(baseline["objective_rmse"]),
                training_rows=len(train_rows),
                training_decisions=len(train_rows),
            )
            # A program supported everywhere but no better than the baseline it
            # is measured against cannot guide.
            assert unsupported == 0
            assert measured["validation_rows"] == len(holdout_rows)
            assert measured["adequate_for_trading"] is False
            # The same program with a two-percent margin and enough supporting
            # decisions does guide, so the gate is reachable.
            reaching, _ = field._program_loss(
                program,
                holdout_rows,
                candidate_id="constant-baseline",
                baseline_objective_rmse=2.0 * float(baseline["objective_rmse"]),
                training_rows=len(train_rows),
                training_decisions=12,
            )
            assert reaching["adequate_for_trading"] is True
            # Thin evidence and abstention each close the gate again.
            thin, _ = field._program_loss(
                program,
                holdout_rows,
                candidate_id="constant-baseline",
                baseline_objective_rmse=2.0 * float(baseline["objective_rmse"]),
                training_rows=len(train_rows),
                training_decisions=5,
            )
            assert thin["adequate_for_trading"] is False
            leaf = {"kind": "leaf", "leaf_id": "leaf-000", "program": program}
            abstaining = semantic_program_payload(
                program_kind="context-tree",
                body={
                    "features": [
                        {
                            "key": "state.absent_context",
                            "kind": "numeric",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        }
                    ],
                    "tree": {
                        "kind": "split",
                        "test": {
                            "key": "state.absent_context",
                            "operator": "le",
                            "value": 0.5,
                        },
                        "match": leaf,
                        "otherwise": {**leaf, "leaf_id": "leaf-001"},
                    },
                },
                reads=["state.absent_context"],
                writes=list(MODEL_OUTPUTS),
                max_work=len(MODEL_OUTPUTS),
            )
            gapped, gapped_unsupported = field._program_loss(
                abstaining,
                holdout_rows,
                candidate_id="discovered-context-tree",
                baseline_objective_rmse=2.0 * float(baseline["objective_rmse"]),
                training_rows=len(holdout_rows),
                training_decisions=12,
            )
            assert gapped_unsupported == len(holdout_rows)
            assert gapped["adequate_for_trading"] is False


def test_declared_workspace_covers_the_field_geometry() -> None:
    # The owner reserves nine eight-byte words per declared mode; a widened
    # geometry must carry a workspace ceiling that covers it and its evidence.
    for modes in (196_608, 786_432, 2_097_152):
        declared = _declared_workspace_bytes(modes)
        assert declared >= modes * 9 * 8
        assert declared >= 64 * 1024 * 1024
    assert _declared_workspace_bytes(786_432) > 64 * 1024 * 1024
    with TemporaryDirectory() as directory:
        root = Path(directory)
        base = small_config()
        modes = base.field_mode_count
        with TradingField.open(root / "field", hive_home=root / "hive", config=base) as field:
            field.run(generate_demo_bars(40, symbol=base.symbol))
            capacity = field.status()["learning_capacity"]
            # The semantic region holds six bytes per declared field mode.
            assert capacity["semantic_task_capacity_bytes"] == modes * 6
            assert capacity["max_workspace_bytes"] == _declared_workspace_bytes(modes)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = generate_demo_bars(32, symbol=config.symbol)[:3]
        with IngestionStore(root / "market.sqlite3") as store:
            for index, bar in enumerate(bars):
                result = store.ingest_bar(
                    bar,
                    source_id="coinbase",
                    source_revision="fixture",
                    granularity=3600,
                    available_at=f"2025-01-01T{index + 1:02d}:00:00Z",
                    raw_id=None,
                    origin="test-fixture",
                )
                assert result.status == "accepted"

            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                consumer = CanonicalFieldConsumer(
                    store=store,
                    field=field,
                    symbol=config.symbol,
                    consumer_id="canonical-field-test",
                )
                first = consumer.drain(max_bars=2)
                assert first["admitted_bars"] == 2
                assert first["pending_after"] == 1
                second = consumer.drain()
                assert second["admitted_bars"] == 1
                assert second["pending_after"] == 0
                assert len(field.ledger.rows("source-delivery")) == 3

            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
            ) as reopened:
                consumer = CanonicalFieldConsumer(
                    store=store,
                    field=reopened,
                    symbol=config.symbol,
                    consumer_id="canonical-field-test",
                )
                replay = consumer.drain()
                assert replay["processed"] == 0
                assert replay["field"]["bar_count"] == 3


def _paper_test_bars(count: int, symbol: str) -> tuple[MarketBar, ...]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 * (1.02**index)
        rows.append(
            MarketBar(
                timestamp=(start + timedelta(hours=index)).isoformat().replace("+00:00", "Z"),
                symbol=symbol,
                open=close,
                high=close * 1.002,
                low=close * 0.998,
                close=close,
                volume=1_000.0,
            )
        )
    return tuple(rows)


def _ingest_paper_test_bars(store: IngestionStore, bars: tuple[MarketBar, ...]) -> None:
    for bar in bars:
        result = store.ingest_bar(
            bar,
            source_id="paper-fixture",
            source_revision="closed-bar-v1",
            granularity=3600,
            available_at=(
                datetime.fromisoformat(bar.timestamp.replace("Z", "+00:00"))
                + timedelta(hours=1)
            ).isoformat().replace("+00:00", "Z"),
            raw_id=None,
            origin="field-paper-test",
        )
        assert result.status == "accepted"



def _set_paper_host_clock(
    bar: MarketBar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host_time = (
        datetime.fromisoformat(bar.timestamp.replace("Z", "+00:00"))
        + timedelta(hours=1, minutes=1)
    ).isoformat(timespec="microseconds").replace("+00:00", "Z")
    monkeypatch.setattr(
        trading_field,
        "_paper_now",
        lambda host_time=host_time: host_time,
    )


def _drain_paper_bars(
    consumer: CanonicalFieldPaperConsumer,
    store: IngestionStore,
    bars: tuple[MarketBar, ...],
    health: Mapping[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> list[Mapping[str, Any]]:
    drained: list[Mapping[str, Any]] = []
    for bar in bars:
        _ingest_paper_test_bars(store, (bar,))
        _set_paper_host_clock(bar, monkeypatch)
        drained.append(consumer.drain(max_bars=1, health=health))
    return drained

def _force_field_targets(field: TradingField, targets: dict[int, float]) -> None:
    choose_action = field._choose_action

    def choose(index: int, state: Mapping[str, float]) -> Mapping[str, Any]:
        selection = dict(choose_action(index, state))
        if index in targets:
            selection["target"] = targets[index]
        return selection

    field._choose_action = choose


_GREEN_HEALTH = {"schema": "cassi.market-data-health.v1", "state": "GREEN", "can_open_exposure": True}
_RED_HEALTH = {"schema": "cassi.market-data-health.v1", "state": "RED", "can_open_exposure": False}


def test_field_decision_fills_only_on_later_eligible_close_with_visible_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(10, config.symbol)
        paper_config = PaperConfig(
            initial_cash=1_000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            max_position_fraction=0.25,
            max_turnover=0.1,
        )
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-test",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                drained = _drain_paper_bars(
                    consumer, store, bars, _GREEN_HEALTH, monkeypatch
                )
                status = consumer.paper_status()
                events = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )
                signal_receipt = consumer._paper_receipts[events[8].event_id]
                assert drained[8]["paper_fills"] == 0
                assert signal_receipt["fill"] is None
                assert signal_receipt["pending_order"]["signal_reference_price"] == bars[8].close
                assert signal_receipt["field_target"] == 1.0
                assert signal_receipt["target_application"]["applied_target"] == 0.1
                assert signal_receipt["target_application"]["size_limited_target"] == 0.25
                assert {
                    item["rule"]
                    for item in signal_receipt["target_application"]["adjustments"]
                } == {"maximum-position-fraction", "maximum-turnover"}
                assert drained[9]["paper_fills"] == 1
                assert status["latest_fill"]["side"] == "buy"
                assert status["latest_fill"]["event_id"] == events[9].event_id
                assert status["last_execution"]["signal_event_id"] == events[8].event_id
                assert status["last_execution"]["execution_event_id"] == events[9].event_id
                assert status["last_execution"]["execution_price"] == bars[9].close
                assert status["last_execution"]["signal_reference_price"] == bars[8].close
                assert status["last_execution"]["execution_reference_price"] == bars[9].close
                assert status["last_execution"]["signal_to_execution_seconds"] > 0
                assert status["account"]["positions"][config.symbol] > 0.0
                assert status["paper_only"] is True
                assert status["external_effect"] == "none"
                assert drained[9]["pending_after"] == 0

def test_one_bar_drain_bounds_selection_and_preserves_pending_backlog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(3, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-one-bar",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _ingest_paper_test_bars(store, bars)
                for index, bar in enumerate(bars):
                    _set_paper_host_clock(bar, monkeypatch)
                    result = consumer.drain(max_bars=1, health=_GREEN_HEALTH)
                    assert result["processed"] == 1
                    assert result["pending_after"] == len(bars) - index - 1
                status = consumer.paper_status()
                assert status["processed"] == len(bars)
                assert status["pending"] == 0
                assert status["fill_count"] == 0


def test_pending_order_survives_restart_and_fills_from_next_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(10, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-pending-restart",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars[:9], _GREEN_HEALTH, monkeypatch
                )
                pending = consumer.paper_status()["pending_order"]
                assert pending is not None
                assert consumer.paper_status()["fill_count"] == 0
            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                recovered = CanonicalFieldPaperConsumer(
                    store,
                    reopened,
                    config.symbol,
                    "field-paper-pending-restart",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                assert recovered.paper_status()["pending_order"] == pending
                _drain_paper_bars(
                    recovered, store, bars[9:], _GREEN_HEALTH, monkeypatch
                )
                status = recovered.paper_status()
                events = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )
                assert status["fill_count"] == 1
                assert status["last_execution"]["signal_event_id"] == events[8].event_id
                assert status["last_execution"]["execution_event_id"] == events[9].event_id


def test_cancelled_pending_order_stays_retired_across_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(10, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-operator-cancel",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars[:9], _GREEN_HEALTH, monkeypatch
                )
                pending = consumer.paper_status()["pending_order"]
                assert pending is not None
                cancelled = consumer.cancel_pending("operator-stop")
                assert cancelled["cancelled"] is True
                assert cancelled["pending_order"] == pending
                assert consumer.cancel_pending("operator-stop")["cancelled"] is False
                assert consumer.paper_status()["pending_order"] is None
            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                recovered = CanonicalFieldPaperConsumer(
                    store,
                    reopened,
                    config.symbol,
                    "field-paper-operator-cancel",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                before = recovered.paper_status()
                assert before["pending_order"] is None
                assert before["last_expiry"]["kind"] == "cancelled"
                assert before["last_expiry"]["pending_order"] == pending
                _drain_paper_bars(
                    recovered, store, bars[9:], _GREEN_HEALTH, monkeypatch
                )
                after = recovered.paper_status()
                assert after["fill_count"] == 0
                assert after["last_execution"] is None


def test_pending_order_expires_when_next_bar_was_available_at_signal_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(10, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-availability-expiry",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars[:8], _GREEN_HEALTH, monkeypatch
                )
                _ingest_paper_test_bars(store, (bars[8],))
                late_signal = (
                    datetime.fromisoformat(bars[8].timestamp.replace("Z", "+00:00"))
                    + timedelta(hours=2, minutes=1)
                ).isoformat(timespec="microseconds").replace("+00:00", "Z")
                monkeypatch.setattr(trading_field, "_paper_now", lambda: late_signal)
                consumer.drain(max_bars=1, health=_GREEN_HEALTH)
                stale = bars[9]
                _ingest_paper_test_bars(store, (stale,))
                _set_paper_host_clock(stale, monkeypatch)
                consumer.drain(max_bars=1, health=_GREEN_HEALTH)
                status = consumer.paper_status()
                assert status["fill_count"] == 0
                assert status["pending_order"] is None
                assert status["last_expiry"]["reason"] == "source-already-available-at-signal"
                assert status["last_expiry"]["pending_order"]["signal_event_id"] == store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[8].event_id


def test_receipt_retry_rejects_mutated_field_decision_and_source_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(9, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-mutation",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars, _GREEN_HEALTH, monkeypatch
                )
                event = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[8]
                receipt = consumer._paper_receipts[event.event_id]
                decision = dict(receipt["field_decision"])
                decision["target"] = 0.0
                with pytest.raises(ValueError, match="retry source or field decision"):
                    consumer._verify_existing_receipt(
                        receipt,
                        event,
                        receipt["trading_bar_event_id"],
                        receipt["field_decision_event_id"],
                        decision,
                    )
                changed_event = replace(
                    event,
                    payload={**event.payload, "close": float(event.payload["close"]) + 1.0},
                )
                with pytest.raises(ValueError, match="retry source or field decision"):
                    consumer._verify_existing_receipt(
                        receipt,
                        changed_event,
                        receipt["trading_bar_event_id"],
                        receipt["field_decision_event_id"],
                        receipt["field_decision"],
                    )


def test_legacy_v1_receipt_is_immutable_across_causal_cutover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = replace(small_config(), warmup_bars=1, feature_windows=(1,), decision_interval=1)
        bars = _paper_test_bars(3, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                field.ingest_bar(bars[0])
                _force_field_targets(field, {1: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-legacy-cutover",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _ingest_paper_test_bars(store, (bars[1],))
                event = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[0]
                field_result = field.ingest_bar(bars[1])
                decision_id, decision = consumer._field_decision_for_bar(
                    str(field_result["bar_event_id"])
                )
                assert decision_id is not None and decision is not None
                consumer._mark_account(bars[1])
                application, fill = consumer._apply_order_target(
                    bars[1],
                    float(decision["target"]),
                    _GREEN_HEALTH,
                    operation_id=f"legacy:{event.event_id}",
                    canonical_event_id=event.event_id,
                )
                assert fill is not None
                event_document = event.as_dict()
                legacy_receipt: dict[str, Any] = {
                    "schema": trading_field.PAPER_CONSUMER_EVENT_SCHEMA,
                    "consumer_id": consumer.consumer_id,
                    "symbol": config.symbol,
                    "paper_config_sha256": consumer._config_sha256,
                    "receipt_sequence": 1,
                    "previous_receipt_sha256": "0" * 64,
                    "canonical_event_id": event.event_id,
                    "canonical_event": event_document,
                    "canonical_event_sha256": trading_field._digest(event_document),
                    "source_payload_sha256": trading_field._digest(event.payload),
                    "trading_bar_event_id": str(field_result["bar_event_id"]),
                    "field_decision_event_id": decision_id,
                    "field_decision": dict(decision),
                    "field_decision_sha256": trading_field._digest(decision),
                    "field_target": float(decision["target"]),
                    "target_application": application,
                    "disposition": "paper-filled",
                    "fill": fill,
                    "account": consumer.account.as_dict(),
                    "data_health": dict(_GREEN_HEALTH),
                    "paper_only": True,
                    "external_effect": "none",
                }
                legacy_receipt["content_sha256"] = trading_field._digest(legacy_receipt)
                legacy_row, replayed = field.ledger.append("paper-event", legacy_receipt)
                assert not replayed
                legacy_account = dict(legacy_receipt["account"])
                source_row = consumer._source_delivery(
                    event, legacy_row, legacy_receipt
                )
                store.mark_delivered(
                    consumer.consumer_id,
                    event.event_id,
                    disposition="trading-field-paper-filled",
                    receipt_sha256=str(source_row["content_sha256"]),
                )
                legacy_row_id = str(legacy_row["event_id"])
                legacy_payload = dict(legacy_row["payload"])
                legacy_snapshot = {
                    "schema": trading_field.PAPER_CONSUMER_LEGACY_STATE_SCHEMA,
                    "consumer_id": consumer.consumer_id,
                    "symbol": config.symbol,
                    "paper_config": consumer._config_document,
                    "paper_config_sha256": consumer._config_sha256,
                    "activation": consumer._activation,
                    "account": legacy_account,
                    "last_event_id": event.event_id,
                    "last_receipt_event_id": legacy_row_id,
                    "last_receipt_sha256": legacy_receipt["content_sha256"],
                    "paper_only": True,
                    "external_effect": "none",
                }
                (root / "paper-state.json").write_text(
                    json.dumps(
                        {
                            **legacy_snapshot,
                            "content_sha256": trading_field._digest(legacy_snapshot),
                        }
                    ),
                    encoding="utf-8",
                )

            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                recovered = CanonicalFieldPaperConsumer(
                    store,
                    reopened,
                    config.symbol,
                    "field-paper-legacy-cutover",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                _force_field_targets(reopened, {2: 1.0})
                assert json.loads((root / "paper-state.json").read_text(encoding="utf-8"))[
                    "schema"
                ] == trading_field.PAPER_CONSUMER_STATE_SCHEMA
                before = recovered.paper_status()
                assert before["legacy_fill_count"] == 1
                assert before["causal_fill_count"] == 0
                assert before["latest_fill"]["execution_model"] == "legacy-same-bar-v1"
                _drain_paper_bars(
                    recovered, store, (bars[2],), _GREEN_HEALTH, monkeypatch
                )
                after = recovered.paper_status()
                preserved = reopened.ledger.get(legacy_row_id)
                assert preserved is not None
                assert preserved["payload"] == legacy_payload
                assert preserved["payload"]["account"] == legacy_account
                assert after["causal_cutover"]["legacy_account"] == legacy_account
                assert after["legacy_fill_count"] == 1
                assert after["causal_fill_count"] == 0
                assert after["latest_fill"]["execution_model"] == "legacy-same-bar-v1"
def test_initial_history_is_warmup_across_restart_and_activation_is_fixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        initial = _paper_test_bars(9, config.symbol)
        later = _paper_test_bars(12, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            _ingest_paper_test_bars(store, initial)
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-warmup",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                warm = consumer.paper_status()
                assert warm["activation_boundary"]["event_id"] == store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[-1].event_id
                assert warm["fill_count"] == 0
                assert warm["account"]["positions"] == {}
            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    reopened,
                    config.symbol,
                    "field-paper-warmup",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                _force_field_targets(reopened, {10: 1.0})
                assert consumer.paper_status()["fill_count"] == 0
                drained = _drain_paper_bars(
                    consumer, store, later[9:], _GREEN_HEALTH, monkeypatch
                )
                status = consumer.paper_status()
                assert status["activation_boundary"]["bootstrap_event_count"] == 9
                assert status["fill_count"] == 1
                assert drained[-2]["paper_fills"] == 0
                assert drained[-1]["paper_fills"] == 1
                assert status["latest_fill"]["event_id"] == store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[-1].event_id
                assert status["last_event"]["canonical_event_id"] == store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[-1].event_id


def test_unhealthy_feed_blocks_increases_at_signal_and_settlement_but_allows_reduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = replace(
            small_config(),
            action_levels=(-1.0, -0.5, 0.0, 0.5, 1.0),
        )
        bars = _paper_test_bars(16, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 0.5, 10: 1.0, 12: 1.0, 14: -1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-health",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars[:9], _GREEN_HEALTH, monkeypatch
                )
                assert consumer.paper_status()["fill_count"] == 0
                assert consumer.paper_status()["pending_order"]["target_exposure"] == 0.5
                _drain_paper_bars(
                    consumer, store, bars[9:10], _GREEN_HEALTH, monkeypatch
                )
                held = consumer.paper_status()["account"]["positions"][config.symbol]
                assert held > 0.0

                _drain_paper_bars(
                    consumer, store, bars[10:11], _RED_HEALTH, monkeypatch
                )
                signal_block = consumer._paper_receipts[
                    store.accepted_events(
                        event_type="market-bar", subject_id=config.symbol
                    )[10].event_id
                ]
                assert signal_block["target_application"]["applied_target"] < 1.0
                assert any(
                    item["rule"] == "unhealthy-feed-blocks-increase"
                    for item in signal_block["target_application"]["adjustments"]
                )
                _drain_paper_bars(
                    consumer, store, bars[11:12], _GREEN_HEALTH, monkeypatch
                )
                assert consumer.paper_status()["fill_count"] == 1
                assert consumer.paper_status()["account"]["positions"][config.symbol] == held

                _drain_paper_bars(
                    consumer, store, bars[12:13], _GREEN_HEALTH, monkeypatch
                )
                pending = consumer.paper_status()["pending_order"]
                assert pending["target_exposure"] > held / consumer.paper_status()["account"]["equity"]
                _drain_paper_bars(
                    consumer, store, bars[13:14], _RED_HEALTH, monkeypatch
                )
                blocked = consumer.paper_status()
                assert blocked["fill_count"] == 1
                assert blocked["account"]["positions"][config.symbol] == held
                assert blocked["pending_order"] is None
                assert blocked["last_execution"]["status"] == "blocked-health-increase"
                assert blocked["last_execution"]["signal_health"]["state"] == "GREEN"
                assert blocked["last_execution"]["settlement_health"]["state"] == "RED"

                _drain_paper_bars(
                    consumer, store, bars[14:15], _RED_HEALTH, monkeypatch
                )
                order = consumer.paper_status()["pending_order"]
                assert order["target_exposure"] == 0.0
                assert order["signal_health"]["state"] == "RED"
                reduction_signal = consumer._paper_receipts[
                    store.accepted_events(
                        event_type="market-bar", subject_id=config.symbol
                    )[14].event_id
                ]
                assert any(
                    item["rule"] == "long-only-negative-target-clipped"
                    for item in reduction_signal["target_application"]["adjustments"]
                )
                _drain_paper_bars(
                    consumer, store, bars[15:16], _RED_HEALTH, monkeypatch
                )
                status = consumer.paper_status()
                events = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )
                assert status["fill_count"] == 2
                assert status["latest_fill"]["side"] == "sell"
                assert status["latest_fill"]["event_id"] == events[15].event_id
                assert status["last_execution"]["signal_event_id"] == events[14].event_id
                assert status["last_execution"]["execution_event_id"] == events[15].event_id
                assert status["account"]["positions"][config.symbol] == 0.0
                assert status["health"]["state"] == "RED"



def test_drawdown_freeze_blocks_increases_but_not_liquidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = list(_paper_test_bars(14, config.symbol))
        crash_price = bars[9].close * 0.7
        bars[10] = MarketBar(
            timestamp=bars[10].timestamp,
            symbol=config.symbol,
            open=crash_price,
            high=crash_price * 1.002,
            low=crash_price * 0.998,
            close=crash_price,
            volume=1_000.0,
        )
        paper_config = PaperConfig(
            initial_cash=1_000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            max_drawdown=0.1,
        )
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0, 10: 0.0, 12: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-freeze",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, tuple(bars[:10]), _GREEN_HEALTH, monkeypatch
                )
                assert consumer.paper_status()["fill_count"] == 1
                _drain_paper_bars(
                    consumer, store, tuple(bars[10:12]), _GREEN_HEALTH, monkeypatch
                )
                assert consumer.paper_status()["account"]["frozen"] is True
                _drain_paper_bars(
                    consumer, store, tuple(bars[12:]), _GREEN_HEALTH, monkeypatch
                )
                status = consumer.paper_status()
                events = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )
                blocked_increase = consumer._paper_receipts[events[12].event_id]
                assert status["account"]["frozen"] is True
                assert status["fill_count"] == 2
                assert status["latest_fill"]["side"] == "sell"
                assert status["latest_fill"]["event_id"] == events[11].event_id
                assert status["account"]["positions"][config.symbol] == 0.0
                assert blocked_increase["target_application"]["applied_target"] == 0.0
                assert any(
                    item["rule"] == "drawdown-freeze-blocks-increase"
                    for item in blocked_increase["target_application"]["adjustments"]
                )


def test_receipt_before_snapshot_crash_recovers_without_duplicate_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(10, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-crash",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars[:9], _GREEN_HEALTH, monkeypatch
                )
                write_snapshot = consumer._write_snapshot

                def fail_after_fill_receipt() -> None:
                    if (
                        consumer._latest_receipt is not None
                        and consumer._latest_receipt["fill"] is not None
                    ):
                        raise OSError("simulated stop after durable paper receipt")
                    write_snapshot()

                monkeypatch.setattr(consumer, "_write_snapshot", fail_after_fill_receipt)
                with pytest.raises(OSError, match="durable paper receipt"):
                    _drain_paper_bars(
                        consumer, store, bars[9:], _GREEN_HEALTH, monkeypatch
                    )
                assert store.pending_count(
                    "field-paper-crash",
                    event_type="market-bar",
                    subject_id=config.symbol,
                ) == 1
            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                recovered = CanonicalFieldPaperConsumer(
                    store,
                    reopened,
                    config.symbol,
                    "field-paper-crash",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                expected_event_id = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[9].event_id
                replay = recovered.drain(health=_RED_HEALTH)
                assert replay["paper_fills"] == 0
                assert replay["pending_after"] == 0
                assert recovered.paper_status()["fill_count"] == 1
                assert recovered.paper_status()["latest_fill"]["event_id"] == expected_event_id


def test_source_link_precedes_watermark_and_mark_crash_reuses_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config = small_config()
        bars = _paper_test_bars(10, config.symbol)
        paper_config = PaperConfig(initial_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
        with IngestionStore(root / "market.sqlite3") as store:
            with TradingField.open(
                root / "field",
                hive_home=root / "hive",
                config=config,
            ) as field:
                _force_field_targets(field, {8: 1.0})
                consumer = CanonicalFieldPaperConsumer(
                    store,
                    field,
                    config.symbol,
                    "field-paper-mark-crash",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                consumer.drain(health=_GREEN_HEALTH)
                _drain_paper_bars(
                    consumer, store, bars[:9], _GREEN_HEALTH, monkeypatch
                )
                _ingest_paper_test_bars(store, (bars[9],))
                expected_event_id = store.accepted_events(
                    event_type="market-bar", subject_id=config.symbol
                )[9].event_id
                _set_paper_host_clock(bars[9], monkeypatch)
                mark_delivered = store.mark_delivered
                failed = False

                def fail_mark_once(
                    consumer_id: str,
                    event_id: str,
                    *,
                    disposition: str,
                    receipt_sha256: str | None = None,
                    processed_at: str | None = None,
                ) -> None:
                    nonlocal failed
                    if event_id == expected_event_id and not failed:
                        failed = True
                        raise OSError("simulated stop after source-delivery link")
                    mark_delivered(
                        consumer_id,
                        event_id,
                        disposition=disposition,
                        receipt_sha256=receipt_sha256,
                        processed_at=processed_at,
                    )

                monkeypatch.setattr(store, "mark_delivered", fail_mark_once)
                with pytest.raises(OSError, match="source-delivery link"):
                    consumer.drain(max_bars=1, health=_GREEN_HEALTH)
                paper_receipt = consumer.paper_status()["last_receipt"]
                source_links = [
                    row["payload"]
                    for row in field.ledger.rows("source-delivery")
                    if row["payload"].get("canonical_event_id") == expected_event_id
                    and row["payload"].get("consumer_id") == "field-paper-mark-crash"
                ]
                assert source_links[-1]["paper_receipt_sha256"] == paper_receipt["content_sha256"]
                assert store.pending_count(
                    "field-paper-mark-crash",
                    event_type="market-bar",
                    subject_id=config.symbol,
                ) == 1
            with TradingField.open(root / "field", hive_home=root / "hive") as reopened:
                recovered = CanonicalFieldPaperConsumer(
                    store,
                    reopened,
                    config.symbol,
                    "field-paper-mark-crash",
                    paper_config=paper_config,
                    paper_state_path=root / "paper-state.json",
                )
                replay = recovered.drain(health=_RED_HEALTH)
                assert replay["paper_fills"] == 0
                assert replay["pending_after"] == 0
                assert recovered.paper_status()["fill_count"] == 1
                assert recovered.paper_status()["latest_fill"]["event_id"] == expected_event_id
