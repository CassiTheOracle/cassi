"""Run a deterministic single-field successor-learning smoke experiment."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import torch

from cassi_field_intelligence import CassiFieldIntelligence, CassiFieldIntelligenceConfig

def _config() -> CassiFieldIntelligenceConfig:
    return CassiFieldIntelligenceConfig(
        mode_count=256,
        alphabet_size=8,
        grid_n=8,
        dt=0.002,
        fast_omega2=8.0,
        slow_omega2=0.02,
        fast_damping=0.8,
        slow_damping=0.02,
        nonlinear_gain=0.001,
        settle_steps=1,
        consolidation_steps=1,
        plasticity_gain=0.08,
        slow_retention=0.999,
        max_mode_amplitude=8.0,
        max_mean_energy=32.0,
    )


def _predict(
    intelligence: CassiFieldIntelligence,
    state,
    symbols: torch.Tensor,
):
    sensed = intelligence.sense(state, symbols)
    settled = intelligence.evolve(sensed)
    return intelligence.emit(settled)


def _train(
    intelligence: CassiFieldIntelligence,
    *,
    cycles: int,
    target_shift: int = 0,
):
    state = intelligence.initial_state(1)
    for _ in range(cycles):
        for value in range(8):
            current = torch.tensor([value], dtype=torch.int64)
            target = torch.tensor([(3 * value + 1 + target_shift) % 8], dtype=torch.int64)
            state = intelligence.cycle(
                state,
                current,
                target_symbols=target,
                learn=True,
            ).state
    return state


def _evaluate(
    intelligence: CassiFieldIntelligence,
    state,
) -> dict[str, Any]:
    symbols = torch.arange(8, dtype=torch.int64)
    expanded = type(state)(state.field.expand(-1, 8).clone())
    emission = _predict(intelligence, expanded, symbols)
    expected = (3 * symbols + 1) % 8
    valid = emission.available
    predicted = emission.symbols
    correct = valid & (predicted == expected)
    score = emission.scores.gather(1, expected.reshape(-1, 1)).squeeze(1)
    best = emission.scores.max(dim=1).values
    return {
        "available": int(valid.sum().item()),
        "top1": float(correct.to(torch.float32).mean().item()),
        "mean_target_score": float(score.mean().item()),
        "mean_best_score": float(best.mean().item()),
        "mean_margin": float(emission.margin.mean().item()),
        "predicted": predicted.tolist(),
        "expected": expected.tolist(),
        "uncertainty": float(emission.uncertainty.mean().item()),
    }


def run(cycles: int = 32) -> dict[str, Any]:
    torch.manual_seed(20260823)
    intelligence = CassiFieldIntelligence(_config())
    frozen = _evaluate(intelligence, intelligence.initial_state(1))
    trained_state = _train(intelligence, cycles=cycles)
    trained = _evaluate(intelligence, trained_state)
    shuffled_state = _train(intelligence, cycles=cycles, target_shift=3)
    shuffled = _evaluate(intelligence, shuffled_state)
    restored_path: Path | None = None
    restored_equal = False
    with torch.no_grad():
        from cassi_field_intelligence import load_field_state, save_field_state
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            restored_path = Path(directory) / "field.pt"
            save_field_state(restored_path, intelligence, trained_state)
            restored = load_field_state(restored_path, intelligence)
            restored_equal = bool(torch.equal(restored.field, trained_state.field))
    finite = bool(torch.isfinite(trained_state.field).all().item())
    if not finite:
        raise AssertionError("trained field contains non-finite values")
    if not restored_equal:
        raise AssertionError("field-only checkpoint did not restore exactly")
    if trained["top1"] <= frozen["top1"]:
        raise AssertionError("trained field did not beat frozen control")
    if trained["mean_target_score"] <= shuffled["mean_target_score"]:
        raise AssertionError("trained field did not beat shuffled-target control")
    result = {
        "schema": "cassi.field-intelligence.smoke.v1",
        "cycles": cycles,
        "mapping": "f(x)=(3*x+1)%8",
        "frozen": frozen,
        "trained": trained,
        "shuffled_target": shuffled,
        "finite": finite,
        "max_abs": float(trained_state.field.abs().max().item()),
        "mean_energy": float(intelligence.component_energy(trained_state).mean().item()),
        "field_only_restore_exact": restored_equal,
        "state_shape": list(trained_state.field.shape),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=32)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = run(cycles=args.cycles)
    encoded = json.dumps(result, sort_keys=True, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
