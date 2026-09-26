"""Plot the measured native-sphere primary arms; no illustrative trajectories."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    args = parser.parse_args()
    analysis_path = args.campaign_root / "analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if analysis["status"] != "VALID" or analysis["arm_count"] != 25:
        raise ValueError("Figure requires the complete independently verified campaign")
    plt.rcParams.update({"figure.facecolor": "#101923", "axes.facecolor": "#172330",
        "text.color": "#e7edf3", "axes.labelcolor": "#dce5ef", "xtick.color": "#bac8d8",
        "ytick.color": "#bac8d8", "axes.edgecolor": "#637386", "grid.color": "#435468",
        "font.size": 10, "axes.titlesize": 12, "savefig.facecolor": "#101923"})
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.6), sharex=True)
    fig.subplots_adjust(left=.075, right=.985, top=.78, bottom=.095, wspace=.27, hspace=.30)
    fig.suptitle("Native spheres: evolving versus frozen field", y=.977, fontsize=17, weight="bold")
    subtitle = fig.text(.5, .927,
        "Physical matter and radiation OFF  |  fixed site geometry  |  two seeds  |  code units only",
        ha="center", fontsize=11, color="#bac8d8")
    colors = {"dynamic": "#68c6e8", "frozen": "#f2b66c"}
    styles = {20260915: "-", 20260916: "--"}
    start = analysis["criteria"]["final_window_start"]
    for col, radius in enumerate((12, 9, 6)):
        for mode in ("dynamic", "frozen"):
            for seed in styles:
                summary = analysis["arms"][f"r{radius}_{mode}_s{seed}"]
                frames = summary["frames"]
                t = [f["t"] for f in frames]
                style = dict(color=colors[mode], linestyle=styles[seed], linewidth=1.65)
                axes[0, col].plot(t, [f["R50"] / radius for f in frames], **style)
                axes[1, col].plot(t, [100 * f["outside_domain_fraction"] for f in frames], **style)
        axes[0, col].set_title(f"Initial radius R = {radius}")
        axes[0, col].set_ylabel(r"Half-mass radius $R_{50}/R$")
        axes[1, col].set_ylabel("Particle mass outside tile (%)")
        axes[1, col].set_xlabel("Time (code units)")
        axes[1, col].axhline(100 * analysis["criteria"]["outside_domain_fraction_max"],
                           color="#d7dfeb", linestyle=":", linewidth=1.1)
        for row in range(2):
            axes[row, col].axvspan(start, 32, color="#a2b2c4", alpha=.11, linewidth=0)
            axes[row, col].set_xlim(0, 32)
            axes[row, col].set_xticks((0, 8, 16, 24, 32))
            axes[row, col].grid(alpha=.35)
    handles = [Line2D([0], [0], color=colors[mode], linestyle=styles[seed], linewidth=2,
        label=f"{'Evolving' if mode == 'dynamic' else 'Frozen'} / seed {seed - 20260914}")
        for mode in ("dynamic", "frozen") for seed in styles]
    legend = fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .893),
                        ncol=4, frameon=False, fontsize=10)
    footnote = fig.text(.5, .022, "Shading: registered final window (24–32). Dotted line: 2% domain-exit limit.",
                       ha="center", fontsize=10, color="#bac8d8")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    artists = [subtitle, legend, footnote, fig._suptitle]
    for ax in axes.flat:
        artists.extend((ax.title, ax.xaxis.label, ax.yaxis.label))
        artists.extend(ax.get_xticklabels())
        artists.extend(ax.get_yticklabels())
    clipped = []
    for artist in artists:
        if not artist.get_visible():
            continue
        box = artist.get_window_extent(renderer)
        if box.x0 < 0 or box.y0 < 0 or box.x1 > width or box.y1 > height:
            clipped.append(str(artist))
    if clipped:
        raise ValueError("Clipped figure labels: " + "; ".join(clipped))
    image = args.campaign_root / "native_spheres.png"
    fig.savefig(image, dpi=160)
    plt.close(fig)
    metadata = {"schema": "cassi_native_sphere_figure_v1", "analysis_sha256": digest(analysis_path),
                "plot_script_sha256": digest(Path(__file__)), "image_sha256": digest(image),
                "panel_count": 6, "primary_arms_plotted": 12, "clipped_labels": clipped}
    (args.campaign_root / "figure_receipt.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
