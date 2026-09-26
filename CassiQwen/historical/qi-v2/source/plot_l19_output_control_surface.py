"""Render a diagnostic figure from frozen, independently verified L19 artifacts."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_DIRECTORY = HERE / "_diag" / "l19-output-control-surface"
BACKGROUND = "#10131c"
PANEL = "#171c28"
TEXT = "#e7edf7"
MUTED = "#9aa9be"
BASE = "#64d8cb"
FIELD = "#ffb454"
DIVERGED = "#f178b6"
GRID = "#334055"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def event(path: Path, index: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        for current, line in enumerate(stream):
            if current == index:
                return json.loads(line)
    raise ValueError(f"missing event {index}: {path}")


def f32(meta: dict[str, Any], key: str = "raw_f32_b64") -> np.ndarray:
    return np.frombuffer(base64.b64decode(meta[key]), dtype="<f4").copy()


def field_vector(value: dict[str, Any]) -> np.ndarray:
    field = value["field_readout"]["field"]
    return np.concatenate((
        np.frombuffer(base64.b64decode(field["ey_b64"]), dtype="<f4"),
        np.frombuffer(base64.b64decode(field["ei_b64"]), dtype="<f4"),
    )).astype(np.float64)


def escaped(piece: str) -> str:
    return piece.encode("unicode_escape").decode("ascii") or "∅"


def relative_l2(first: np.ndarray, second: np.ndarray) -> float:
    scale = 0.5 * (np.linalg.norm(first) + np.linalg.norm(second))
    return float(np.linalg.norm(first - second) / scale) if scale else 0.0


def cosine(first: np.ndarray, second: np.ndarray) -> float:
    scale = np.linalg.norm(first) * np.linalg.norm(second)
    return float(np.dot(first, second) / scale) if scale else 0.0


def safe_text_layout(figure: plt.Figure) -> None:
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    width, height = figure.get_window_extent(renderer).width, figure.get_window_extent(renderer).height
    overflow: list[str] = []
    margin = 64
    for text in figure.findobj(match=plt.Text):
        if not text.get_text() or text.axes is not None:
            continue
        bbox = text.get_window_extent(renderer)
        if bbox.x0 < -margin or bbox.y0 < -margin or bbox.x1 > width + margin or bbox.y1 > height + margin:
            overflow.append(text.get_text())
    if overflow:
        raise RuntimeError(f"figure text exceeds canvas: {overflow[:3]}")

def render(directory: Path, output: Path) -> dict[str, Any]:
    manifest = load_json(directory / "l19-manifest.json")
    verification = load_json(directory / "l19-verification.json")
    arms = {arm["name"]: arm for arm in manifest["arms"]}
    control = manifest["derivation"]["control_event"]
    baseline_id = int(control["baseline_prediction"]["first_token_id"])
    post_id = int(control["first_crossover"]["candidate_token_id"])
    crossover = float(control["first_crossover"]["coupling"])
    threshold_names = ["threshold-zero", "threshold-reference", "threshold-pre", "threshold-post"]
    threshold_records: list[tuple[str, float, dict[str, Any]]] = []
    for name in threshold_names:
        receipt = load_json(directory / f"{arms[name]['run_id']}.receipt.json")
        control_event = event(Path(receipt["event_log"]["path"]), 1)
        threshold_records.append((name, float(arms[name]["coupling"]), control_event))
    couplings = np.asarray([entry[1] for entry in threshold_records], dtype=np.float64)
    baseline_logits = np.asarray(
        [f32(entry[2]["output"]["selected_logits"])[baseline_id] for entry in threshold_records],
        dtype=np.float64,
    )
    post_logits = np.asarray(
        [f32(entry[2]["output"]["selected_logits"])[post_id] for entry in threshold_records],
        dtype=np.float64,
    )

    trajectories: dict[str, list[dict[str, Any]]] = {}
    for name in ("trajectory-zero", "trajectory-post"):
        receipt = load_json(directory / f"{arms[name]['run_id']}.receipt.json")
        log_path = Path(receipt["event_log"]["path"])
        trajectories[name] = [event(log_path, index) for index in range(int(arms[name]["max_tokens"]))]
    zero, post = trajectories["trajectory-zero"], trajectories["trajectory-post"]
    future_indices = list(range(2, len(zero)))
    l2 = [relative_l2(field_vector(zero[index]), field_vector(post[index])) for index in future_indices]
    alignment = [cosine(field_vector(zero[index]), field_vector(post[index])) for index in future_indices]

    figure = plt.figure(figsize=(16, 7.4), facecolor=BACKGROUND, constrained_layout=True)
    grid = figure.add_gridspec(2, 3, height_ratios=(1.0, 0.86), width_ratios=(1.28, 1.08, 1.05))
    first = figure.add_subplot(grid[:, 0])
    second = figure.add_subplot(grid[:, 1])
    third = figure.add_subplot(grid[:, 2])
    for axis in (first, second, third):
        axis.set_facecolor(PANEL)
        axis.tick_params(colors=MUTED, labelsize=9)
        for spine in axis.spines.values():
            spine.set_color(GRID)

    first.plot(couplings, baseline_logits, color=BASE, marker="o", linewidth=2.5, label=f"token {baseline_id}")
    first.plot(couplings, post_logits, color=FIELD, marker="o", linewidth=2.5, label=f"token {post_id}")
    first.axvline(crossover, color=TEXT, alpha=0.72, linestyle="--", linewidth=1.2)
    first.axvspan(0.95 * crossover, 1.05 * crossover, color=DIVERGED, alpha=0.12)
    for name, coupling, record in threshold_records:
        chosen = int(record["selected_token_id"])
        first.annotate(
            f"{name.replace('threshold-', '')}\n→ {chosen}",
            (coupling, max(float(f32(record['output']['selected_logits'])[chosen]), baseline_logits.min(), post_logits.min())),
            xytext=(0, 13 if name != "threshold-post" else -31),
            textcoords="offset points",
            color=DIVERGED if name == "threshold-post" else TEXT,
            fontsize=8,
            ha="center",
            arrowprops={"arrowstyle": "-", "color": MUTED, "alpha": 0.55},
        )
    first.set_title("Frozen direct-head control surface", color=TEXT, loc="left", fontsize=13, fontweight="bold", pad=14)
    first.text(0.02, 0.03, r"$\ell(\gamma)=W\,(z+\gamma f)$", transform=first.transAxes, color=TEXT, fontsize=12)
    first.text(0.02, 0.92, f"first crossover  γ* = {crossover:.6f}", transform=first.transAxes, color=MUTED, fontsize=9)
    first.set_xlabel("field-output coupling γ", color=TEXT, labelpad=8)
    first.set_ylabel("selected-head logit", color=TEXT, labelpad=8)
    first.grid(color=GRID, alpha=0.55, linewidth=0.6)
    legend = first.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="lower right", fontsize=9)
    for handle in legend.legend_handles:
        handle.set_linewidth(3)

    second.set_title("Committed token trajectories", color=TEXT, loc="left", fontsize=13, fontweight="bold", pad=14)
    second.set_xlim(-0.5, 3.5)
    second.set_ylim(-0.7, 1.7)
    second.set_xticks(range(4), [f"token {index}" for index in range(4)])
    second.set_yticks((0, 1), ("γ = 0", f"γ = {arms['trajectory-post']['coupling']:.6f}"))
    for row, (_, records) in enumerate(((0, zero), (1, post))):
        for column, record in enumerate(records):
            divergent = column >= verification["trajectory"]["first_divergent_index"] and row == 1
            face = DIVERGED if divergent else (BASE if row == 0 else FIELD)
            second.scatter(column, row, s=2450, marker="s", color=face, alpha=0.88, edgecolors=BACKGROUND, linewidths=2)
            second.text(column, row + 0.07, str(record["selected_token_id"]), color=BACKGROUND, ha="center", va="center", fontsize=10, fontweight="bold")
            second.text(column, row - 0.16, escaped(record["selected_piece"])[:13], color=BACKGROUND, ha="center", va="center", fontsize=7)
    second.axvline(1, color=TEXT, linestyle="--", alpha=0.7, linewidth=1.1)
    second.text(1.04, 1.52, "frozen control event", color=MUTED, fontsize=8)
    second.grid(False)

    third.set_title("Field separation after committed divergence", color=TEXT, loc="left", fontsize=13, fontweight="bold", pad=14)
    if future_indices:
        x = np.arange(len(future_indices))
        bars = third.bar(x - 0.16, l2, width=0.32, color=DIVERGED, label="relative L2 difference")
        third.set_xticks(x, [f"field {index}" for index in future_indices])
        third.set_ylabel("relative L2", color=TEXT)
        twin = third.twinx()
        twin.set_facecolor("none")
        twin.plot(x + 0.16, alignment, color=BASE, marker="o", linewidth=2.2, label="cosine alignment")
        twin.set_ylim(-1.02, 1.02)
        twin.tick_params(colors=MUTED, labelsize=9)
        twin.set_ylabel("cosine", color=TEXT)
        for bar, value in zip(bars, l2):
            third.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012, f"{value:.3f}", color=TEXT, ha="center", fontsize=8)
        handles = [bars, twin.lines[0]]
        third.legend(handles, ["relative L2", "cosine"], facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8, loc="lower right")
    third.grid(axis="y", color=GRID, alpha=0.55, linewidth=0.6)

    figure.suptitle("CassiQwen L19 — output control without model-weight intervention", color=TEXT, fontsize=16, fontweight="bold", x=0.015, ha="left")
    safe_text_layout(figure)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor=BACKGROUND)
    plt.close(figure)
    return {
        "output": str(output),
        "control_event_index": verification["control_event_index"],
        "threshold_tokens": verification["threshold_tokens"],
        "relative_l2": l2,
        "cosine": alignment,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or args.directory / "l19-output-control-surface.png"
    result = render(args.directory.resolve(), output.resolve())
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
