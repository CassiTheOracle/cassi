"""Read the Qi field's learned mode-bank controls from the real op.

The bank, the absolute read, and the unwritten latch all change what the native
`cassi_qi_field_step` operator computes. This probe runs that operator inside a
real model context through `NativeLlamaSession.graph_trial` and reports each
arm's logits against a reference where the field is alive but reaches nothing,
so a claim about these controls rests on the op rather than on the port.

The field has two independent channels into the model, and they are set by
different flags:

  * the additive reach, `intervention 0` with `injection_scale > 0`, which adds
    the readout's leading `n_embd` channels to the final normed hidden state;
  * the substitution seam, a positive `substitute` share at displacement level 3
    or deeper, which fills the state write the displacement suppressed.

`llama_cassi_qi_state_field_width` reports the second one only, so it stays zero
in the additive family even though the field reaches the model there. The probe
measures both families, each against `reach-off` (`injection_scale 0`, no
substitute, no displacement), where the field evolves and nothing consumes it.

    python research/probe_cassi_qi_mode_bank.py
    python research/probe_cassi_qi_mode_bank.py --bank _diag/field-bank/power-law-32.bin
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

from cassi_llama_capture import (  # noqa: E402
    NativeLlamaSession,
    _read_f32,
    _sha_path,
    write_zero_state,
)

RUNTIME = ROOT / "native" / "llama.cpp" / "b8-learn" / "bin" / "Release"
MODEL = ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
DEFAULT_BANK = ROOT / "_diag" / "field-bank" / "measured-32.bin"
DEFAULT_PROMPT = "Cassi field memory probe: the resonant pond remembers the stone."
# Enough continuation turns for the seam's write to be read several times over.
LONG_CONTINUATION = (" and the resonant pond still remembers the stone that fell into it"
                     " long ago, though the surface shows nothing at all.")
MODE_COUNT = 6144
SCALE_COUNT = 4
STATE_FLOATS = SCALE_COUNT * 9 * MODE_COUNT
# The 0.8B holds 24 blocks, so its middle layer is 12; its embedding is 1024 wide.
DEFAULT_LAYER = 12
DEFAULT_ROW_WIDTH = 1024
# Reads and writes that define an arm, independent of the channel it uses.
READ_ARMS = {
    "ramp-normalized": dict(read_absolute=False, unwritten_latch=False),
    "bank-normalized": dict(read_absolute=False, unwritten_latch=False),
    "ramp-absolute": dict(read_absolute=True, unwritten_latch=False),
    "bank-absolute": dict(read_absolute=True, unwritten_latch=False),
    "bank-absolute-latch": dict(read_absolute=True, unwritten_latch=True),
}
BANKED = {"bank-normalized", "bank-absolute", "bank-absolute-latch"}


def channel_knobs(channel: str) -> dict:
    if channel == "additive":
        return {"displacement": 0, "substitute": 0.0, "injection_scale": 1.0,
                "row_width": 0, "memory_fill": False}
    if channel == "seam":
        return {"displacement": 3, "substitute": 1.0, "injection_scale": 0.0,
                "row_width": DEFAULT_ROW_WIDTH, "memory_fill": True}
    if channel == "reach-off":
        return {"displacement": 0, "substitute": 0.0, "injection_scale": 0.0,
                "row_width": 0, "memory_fill": False}
    raise ValueError(channel)


def arm_plan(bank: Path) -> list[tuple[str, str, dict]]:
    plan = [("reach-off", "reach-off", dict(read_absolute=False, unwritten_latch=False, mode_bank=None))]
    for channel in ("additive", "seam"):
        for name, read in READ_ARMS.items():
            plan.append((f"{channel}/{name}", channel, dict(read, mode_bank=bank if name in BANKED else None)))
    return plan


def arm_dir(slot: str, out: Path) -> Path:
    return out / slot.replace("/", "__")


def bank_identity(recorded: dict | None, expected: Path | None) -> None:
    """A resumed arm must have been measured with the bank this run is asking about.

    Arms are keyed by slot name, not by bank identity, so a re-run over an existing output
    directory would otherwise replay receipts for a different bank and report them as this
    bank's measurement. The receipt carries the bank's digest, so the check is exact.
    """
    if expected is None:
        if recorded is not None:
            raise RuntimeError("a cached arm ran without a bank but this run asks for none")
        return
    if recorded is None:
        raise RuntimeError(f"a cached arm ran without a bank but this run asks for {expected}")
    digest = _sha_path(expected)
    if recorded["sha256"] != digest:
        raise RuntimeError(f"a cached arm used bank {recorded['sha256'][:12]} but {expected} is "
                           f"{digest[:12]}; remove the arm directory and re-run")


def run_arm(slot: str, channel: str, read: dict, args, state: Path,
            out: Path) -> dict:
    directory = arm_dir(slot, out)
    receipt_path = directory / "graph-trial-receipt.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        bank_identity(receipt["configuration"]["mode_bank"],
                      Path(read["mode_bank"]) if read["mode_bank"] is not None else None)
        # The taper changes the readout and so the logits an arm records, so a cached arm
        # built under a different taper is a different measurement, not a replay.
        recorded_taper = float(receipt["configuration"].get("scale_read_taper", 0.0))
        if recorded_taper != float(read["scale_read_taper"]):
            raise RuntimeError(f"a cached arm used scale_read_taper {recorded_taper:g} but this "
                               f"run asks for {float(read['scale_read_taper']):g}; remove the arm "
                               f"directory and re-run")
        return receipt
    if directory.exists():
        raise RuntimeError(f"{directory} exists without a receipt; remove it and re-run")
    knobs = dict(channel_knobs(channel), **read)
    with NativeLlamaSession(RUNTIME, args.model, gpu_layers=args.gpu_layers,
                            context_tokens=args.context_tokens) as session:
        if not 0 <= args.layer < session.layer_count:
            raise RuntimeError(f"layer {args.layer} is outside this model's {session.layer_count} blocks")
        # A substitution seam writes the recurrent-state row that the displaced layer reads on
        # the next decode, so the reading pass needs at least one continuation token.
        continuation = session.tokenize_text(args.continuation) if args.continuation else ()
        result = session.graph_trial(
            sequence_id="qi-mode-bank",
            prompt=args.prompt,
            state_path=state,
            output_dir=directory,
            layer=args.layer,
            capture_id=f"qi-mode-bank-{slot}",
            continuation_tokens=continuation,
            **knobs,
        )
    return result["receipt"]


def kl_between(left: np.ndarray, right: np.ndarray) -> float:
    a = np.exp(left - left.max())
    b = np.exp(right - right.max())
    a /= a.sum()
    b /= b.sum()
    return float(np.sum(a * np.log((a + 1e-12) / (b + 1e-12))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=str(MODEL))
    parser.add_argument("--bank", default=str(DEFAULT_BANK),
                        help="learned mode bank; the file must hold exactly mode_count f32 symbols")
    parser.add_argument("--out", default=str(ROOT / "_diag" / "qi-mode-bank"))
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--continuation", default=LONG_CONTINUATION,
                        help="tokens decoded after the prompt; the seam is read on these passes")
    parser.add_argument("--layer", type=int, default=DEFAULT_LAYER)
    parser.add_argument("--gpu-layers", type=int, default=0)
    parser.add_argument("--context-tokens", type=int, default=256)
    parser.add_argument("--scale-read-taper", type=float, default=0.0,
                        help="readout scale taper; 0 is the pinned readout")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bank = Path(args.bank)
    if not bank.is_file():
        raise FileNotFoundError(bank)
    if bank.stat().st_size != MODE_COUNT * 4:
        raise RuntimeError(f"{bank} holds {bank.stat().st_size} bytes, expected {MODE_COUNT * 4}")

    seed_state = out / "seed" / "state-after.f32"
    if not seed_state.is_file():
        write_zero_state(out / "zero-state.f32")
        # The seed is one pass of the field at its defaults, so every arm starts from the same
        # written state. The read flags never change the state, so their setting here is immaterial.
        seed_read = dict(read_absolute=False, unwritten_latch=False, scale_read_taper=0.0,
                         mode_bank=None)
        seed_receipt = run_arm("seed", "reach-off", seed_read, args, out / "zero-state.f32", out)
        if seed_receipt["configuration"]["mode_bank"] is not None:
            raise RuntimeError("the seed arm must run without a bank")
    seed_values = _read_f32(seed_state, elements=STATE_FLOATS)

    plan = [(slot, channel, dict(read, scale_read_taper=args.scale_read_taper))
            for slot, channel, read in arm_plan(bank)]
    receipts: dict[str, dict] = {}
    logits: dict[str, np.ndarray] = {}
    states: dict[str, np.ndarray] = {}
    for slot, channel, read in plan:
        receipt = run_arm(slot, channel, read, args, seed_state, out)
        receipts[slot] = receipt
        directory = out / slot.replace("/", "__")
        logits[slot] = _read_f32(directory / receipt["logits"]["path"],
                                 elements=int(receipt["logits"]["elements"]))
        successor = receipt["state_successor"]
        states[slot] = _read_f32(directory / successor["path"], elements=int(successor["elements"]))

    descriptor = next(r["configuration"]["mode_bank"] for r in receipts.values()
                      if r["configuration"]["mode_bank"] is not None)
    print(f"seed state: norm {float(np.linalg.norm(seed_values)):.6f}  "
          f"modes written {int(np.count_nonzero(seed_values))}")
    print(f"bank: {descriptor['path']} {descriptor['bytes']} bytes {descriptor['modes']} modes "
          f"damping {descriptor['damping_min']:.6f}..{descriptor['damping_max']:.6f}")

    reference = "reach-off"
    print()
    print("against the reach-off reference (the field evolves, nothing consumes its readout):")
    print(f"{'arm':32s} {'reach':>4s} {'logits max|d|':>14s} {'logits KL':>12s} "
          f"{'state max|d|':>14s} {'state rel':>12s} {'written':>8s}")
    for slot, _, _ in plan:
        if slot == reference:
            continue
        max_logits = float(np.max(np.abs(logits[slot] - logits[reference])))
        kl = kl_between(logits[slot], logits[reference])
        max_state = float(np.max(np.abs(states[slot] - states[reference])))
        relative = float(np.linalg.norm(states[slot] - states[reference])) / max(
            float(np.linalg.norm(states[reference])), 1e-30)
        graph = receipts[slot]["graph"]
        reach = graph["qi_state_field_width"]
        print(f"{slot:32s} {reach:4d} {max_logits:14.6e} {kl:12.6e} "
              f"{max_state:14.6e} {relative:12.6e} {int(np.count_nonzero(states[slot])):8d}")

    print()
    print("within each channel, so the state is held and only the named control moves:")
    for channel in ("additive", "seam"):
        members = [slot for slot, member_channel, _ in plan if member_channel == channel]
        for index, left in enumerate(members):
            for right in members[index + 1:]:
                max_logits = float(np.max(np.abs(logits[left] - logits[right])))
                kl = kl_between(logits[left], logits[right])
                max_state = float(np.max(np.abs(states[left] - states[right])))
                print(f"{channel:9s} {left.split('/')[1]:22s} vs {right.split('/')[1]:22s} "
                      f"logits {max_logits:12.6e}  KL {kl:12.6e}  state {max_state:12.6e}")

    widths = {slot: receipts[slot]["graph"]["qi_state_field_width"] for slot, _, _ in plan}
    vocab = int(receipts[reference]["logits"]["elements"])
    steps = receipts[reference]["logit_steps"]
    focus = ["additive/ramp-normalized", "additive/bank-normalized",
             "seam/ramp-normalized", "seam/bank-normalized"]
    distance: list[dict[str, float]] = []
    seam_first_read: int | None = None
    for step, step_descriptor in enumerate(steps):
        base = _read_f32(arm_dir(reference, out) / step_descriptor["path"], elements=vocab)
        row: dict[str, float] = {"step": float(step),
                                 "position": float(step_descriptor["position"]), reference: 0.0}
        for name, _, _ in plan:
            if name == reference:
                continue
            entry = receipts[name]["logit_steps"][step]
            row[name] = kl_between(
                _read_f32(arm_dir(name, out) / entry["path"], elements=vocab), base)
        distance.append(row)
        if seam_first_read is None and any(
                row[f"seam/{arm}"] > 1e-12
                for arm in ("ramp-normalized", "bank-normalized", "ramp-absolute",
                            "bank-absolute", "bank-absolute-latch")):
            seam_first_read = step

    print()
    print(f"logits KL against the reference at each decode, step 0 being the last prompt token; "
          f"{steps[-1]['position'] + 1} tokens total")
    header = "  ".join(f"{slot.split('/')[1][:22]:>22s}" for slot in focus)
    print(f"{'step':>4s} {'pos':>4s}  {header}")
    for row in distance:
        cells = "  ".join(f"{row[slot]:22.6e}" for slot in focus)
        print(f"{int(row['step']):>4d} {int(row['position']):>4d}  {cells}")

    summary = {
        "model": receipts[reference]["model"],
        "bank": descriptor,
        "seed_state_norm": float(np.linalg.norm(seed_values)),
        "seed_written_modes": int(np.count_nonzero(seed_values)),
        "state_field_width": widths,
        "written_modes": {slot: int(np.count_nonzero(states[slot])) for slot, _, _ in plan},
        "configuration": {slot: receipts[slot]["configuration"] for slot, _, _ in plan},
        "distance_kl": distance,
        "seam_first_read_step": seam_first_read,
    }
    (out / "probe-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nsummary {out / 'probe-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
