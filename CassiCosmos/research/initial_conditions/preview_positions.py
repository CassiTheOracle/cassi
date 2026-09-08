"""Illustrative particle-position designs only; no dynamics or field simulation.

Each panel has the same particle count and is centered and uniformly rescaled
into a unit bounding sphere for comparison. Color encodes camera depth only.
The generators describe proposed geometry, not production-ready equilibrium ICs.

Regenerate from the repository root:
    python research/initial_conditions/preview_positions.py

Proposed UI: choose a shape, its arrangement, and initial motion independently.
Shared shape controls are size, thickness, clumpiness, asymmetry, orientation,
and seed; each geometry adds its own small set of controls. The recipes below
are fixed preview configurations, not a production spawning or velocity API.
"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

OUT = Path(__file__).resolve().parents[2] / "_diag" / "initial_condition_design"
COUNT = 12000
SEED = 20260908


def ball(rng, n, radius=1.0):
    direction = rng.normal(size=(n, 3))
    direction /= np.linalg.norm(direction, axis=1)[:, None]
    return direction * (radius * rng.random(n) ** (1.0 / 3.0))[:, None]


def rotate(points, angle, axis=0):
    angle = np.deg2rad(angle)
    c, s = np.cos(angle), np.sin(angle)
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    matrix = np.eye(3)
    matrix[i, i] = matrix[j, j] = c
    matrix[i, j] = -s
    matrix[j, i] = s
    return points @ matrix.T


def disc(rng, n, radius=1.0, height=0.035):
    r = radius * np.sqrt(rng.random(n))
    theta = rng.uniform(0.0, 2.0 * np.pi, n)
    return np.column_stack((r * np.cos(theta), r * np.sin(theta),
                            rng.uniform(-height, height, n)))


def spiral(rng, n):
    arms = int(n * 0.72)
    smooth = int(n * 0.18)
    r = rng.uniform(0.14, 1.0, arms)
    theta = np.log(r / 0.14) / np.tan(np.deg2rad(22.0))
    theta += rng.integers(0, 3, arms) * (2.0 * np.pi / 3.0)
    cloud = np.column_stack((r * np.cos(theta), r * np.sin(theta), np.zeros(arms)))
    cloud += ball(rng, arms, 0.038)
    return np.vstack((cloud, disc(rng, smooth), ball(rng, n - arms - smooth, 0.16)))


def encounter(rng, n):
    split = 2 * n // 3
    first = rotate(disc(rng, split, 0.65), 12, 0) + (-0.61, -0.18, 0.0)
    second = rotate(disc(rng, n - split, 0.46), 72, 0) + (0.76, 0.25, 0.18)
    return np.vstack((first, second))


def pearl_ring(rng, n):
    smooth = int(n * 0.58)
    theta = rng.uniform(0.0, 2.0 * np.pi, smooth)
    loop = np.column_stack((0.8 * np.cos(theta), 0.8 * np.sin(theta),
                            0.065 * np.sin(3.0 * theta)))
    loop += ball(rng, smooth, 0.055)
    pearl_theta = rng.integers(0, 8, n - smooth) * (2.0 * np.pi / 8.0)
    pearls = np.column_stack((0.8 * np.cos(pearl_theta), 0.8 * np.sin(pearl_theta),
                              0.065 * np.sin(3.0 * pearl_theta)))
    pearls += ball(rng, n - smooth, 0.105)
    return np.vstack((loop, pearls))


def shells(rng, n):
    pieces = []
    counts = (n // 3, n // 3, n - 2 * (n // 3))
    for k, (radius, count) in enumerate(zip((0.34, 0.65, 1.0), counts)):
        direction = rng.normal(size=(count, 3))
        direction /= np.linalg.norm(direction, axis=1)[:, None]
        inner, outer = radius - 0.018, radius + 0.018
        radial = (rng.uniform(inner ** 3, outer ** 3, count)) ** (1.0 / 3.0)
        layer = direction * radial[:, None] * (1.0, 0.88, 0.76)
        pieces.append(rotate(layer, k * 24, 1))
    return np.vstack(pieces)


def double_helix(rng, n):
    t = rng.uniform(-1.0, 1.0, n)
    theta = (t + 1.0) * (2.5 * np.pi) + rng.integers(0, 2, n) * np.pi
    points = np.column_stack((0.30 * np.cos(theta), 0.30 * np.sin(theta), t))
    return points + ball(rng, n, 0.045)


def filament_web(rng, n):
    nodes = ball(rng, 16, 1.0)
    d = np.linalg.norm(nodes[:, None, :] - nodes[None, :, :], axis=2)
    visited = {0}
    edges = []
    while len(visited) < len(nodes):
        _, i, j = min((d[i, j], i, j) for i in visited
                      for j in range(len(nodes)) if j not in visited)
        edges.append((i, j))
        visited.add(j)
    for i in range(len(nodes)):
        j = int(np.argsort(d[i])[2])
        edge = (min(i, j), max(i, j))
        if edge not in {(min(a, b), max(a, b)) for a, b in edges}:
            edges.append(edge)
    edges = np.asarray(edges)
    start, end = nodes[edges[:, 0]], nodes[edges[:, 1]]
    lengths = np.linalg.norm(end - start, axis=1)
    tubes = int(n * 0.80)
    chosen = rng.choice(len(edges), tubes, p=lengths / lengths.sum())
    t = rng.random(tubes)[:, None]
    bend = ball(rng, len(edges), 0.13)
    cloud = ((1.0 - t) * start[chosen] + t * end[chosen]
             + 4.0 * t * (1.0 - t) * bend[chosen] + ball(rng, tubes, 0.022))
    junctions = nodes[rng.integers(0, len(nodes), n - tubes)] + ball(rng, n - tubes, 0.065)
    return np.vstack((cloud, junctions))


def hierarchical_cloud(rng, n):
    parents = np.zeros((1, 3))
    levels = []
    scale = 0.76
    for _ in range(3):
        parents = np.repeat(parents, 5, axis=0) + ball(rng, len(parents) * 5, scale)
        levels.append((parents.copy(), scale * 0.4))
        scale *= 0.42
    assigned = rng.choice(3, n, p=(0.12, 0.25, 0.63))
    pieces = []
    for i, (centers, width) in enumerate(levels):
        count = int(np.sum(assigned == i))
        weights = rng.uniform(0.25, 1.0, len(centers))
        weights /= weights.sum()
        pieces.append(centers[rng.choice(len(centers), count, p=weights)]
                      + ball(rng, count, width))
    return np.vstack(pieces)


def folded_sheet(rng, n):
    x, y = rng.uniform(-1.0, 1.0, (2, n))
    z = 0.30 * np.sin(1.2 * np.pi * x) + 0.13 * np.sin(2.0 * np.pi * y)
    return np.column_stack((x, y, z)) + ball(rng, n, 0.022)


def trefoil(rng, n):
    # Invert a tabulated arc-length CDF instead of bunching at slow parameter speeds.
    grid = np.linspace(0.0, 2.0 * np.pi, 4097)
    def curve(t):
        r = 0.65 + 0.25 * np.cos(3.0 * t)
        return np.column_stack((r * np.cos(2.0 * t), r * np.sin(2.0 * t),
                                0.25 * np.sin(3.0 * t)))
    base = curve(grid)
    cumulative = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(base, axis=0), axis=1))]
    t = np.interp(rng.random(n) * cumulative[-1], cumulative, grid)
    return curve(t) + ball(rng, n, 0.035)


DESIGNS = [
    ("Spiral disc", "3 broad arms + a diffuse disc and core", spiral),
    ("Tilted encounter", "Two offset discs in different planes", encounter),
    ("Pearl ring", "A continuous torus with 8 dense knots", pearl_ring),
    ("Nested shells", "3 hollow, finite-thickness ellipsoids", shells),
    ("Double helix", "Two thick streams, wound through 2.5 turns", double_helix),
    ("Filament web", "Connected strands, dense nodes, open voids", filament_web),
    ("Hierarchical cloud", "Clumps inside clumps across 3 scales", hierarchical_cloud),
    ("Folded sheet", "A thin, rippled membrane of particles", folded_sheet),
    ("Trefoil cloud", "One closed stream tied into a knot", trefoil),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(15, 15.8), dpi=150, facecolor="#070c17")
    cmap = LinearSegmentedColormap.from_list("cassi_depth", ["#397d9f", "#69e2ce", "#ffe2a0"])
    fig.text(0.045, 0.973, "NINE WAYS TO BEGIN", color="#f3d391", fontsize=26, weight="bold")
    fig.text(0.045, 0.949, "Proposed CassiCosmos initial particle positions", color="#d3dee8", fontsize=14)
    fig.text(0.045, 0.928, "Geometry previews only  |  Equal particle counts  |  Color = viewing depth, not field state",
             color="#8295ac", fontsize=10.5)
    receipt = {"kind": "illustrative_geometry_only", "dynamics_simulated": False,
               "points_per_panel": COUNT, "normalization": "equal-weight centroid zero; maximum radius one",
               "presets": []}
    arrays = {}
    caption_boxes = []
    for index, (name, description, generator) in enumerate(DESIGNS):
        seed = SEED + index
        points = generator(np.random.default_rng(seed), COUNT)
        if points.shape != (COUNT, 3) or not np.isfinite(points).all():
            raise ValueError(f"Invalid positions: {name}")
        if not np.array_equal(points, generator(np.random.default_rng(seed), COUNT)):
            raise ValueError(f"Non-deterministic positions: {name}")
        points -= points.mean(axis=0)
        radius = np.linalg.norm(points, axis=1).max()
        points /= radius
        arrays[name.replace(" ", "_").lower()] = points.astype(np.float32)
        radius_max = float(np.linalg.norm(points, axis=1).max())
        centroid_norm = float(np.linalg.norm(points.mean(axis=0)))
        if radius_max > 1.0 + 1e-12 or centroid_norm > 1e-12:
            raise ValueError(f"Normalization failed: {name}")
        row, col = divmod(index, 3)
        x = 0.04 + col * 0.322
        top = 0.885 - row * 0.286
        title = fig.text(x + 0.008, top + 0.010, f"{index + 1:02d}  {name}", color="#f3d391", fontsize=15, weight="bold")
        caption = fig.text(x + 0.008, top - 0.010, description, color="#9eafc4", fontsize=9.2)
        caption_boxes.extend((title, caption))
        ax = fig.add_axes((x, top - 0.253, 0.306, 0.226), facecolor="#090f1c")
        # Identical orthographic viewing basis across panels.
        elev, az = np.deg2rad(37.0), np.deg2rad(28.0)
        right = np.array((-np.sin(az), np.cos(az), 0.0))
        up = np.array((-np.sin(elev) * np.cos(az), -np.sin(elev) * np.sin(az), np.cos(elev)))
        toward = np.cross(right, up)
        screen = points @ np.column_stack((right, up, toward))
        order = np.argsort(screen[:, 2])
        ax.scatter(screen[order, 0], screen[order, 1], c=screen[order, 2],
                   s=0.85, alpha=0.82, cmap=cmap, vmin=-1.0, vmax=1.0,
                   edgecolors="none", rasterized=True)
        ax.set_xlim(-1.065, 1.065)
        ax.set_ylim(-1.065, 1.065)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#1d2b40")
        receipt["presets"].append({"name": name, "seed": seed, "count": len(points),
                                    "centroid_norm": centroid_norm, "maximum_radius": radius_max,
                                    "deterministic": True})
        print(f"{name}: {len(points)} finite points; seeded repeat identical; radius={radius_max:.6f}")
    fig.text(0.045, 0.022, "These shapes are seeded, not emergent. Their later evolution and stability have not been tested.",
             color="#9eafc4", fontsize=10.5)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for i, text in enumerate(caption_boxes):
        box = text.get_window_extent(renderer)
        if not fig.bbox.contains(box.x0, box.y0) or not fig.bbox.contains(box.x1, box.y1):
            raise ValueError("A caption extends beyond the figure")
        for other in caption_boxes[i + 1:]:
            if box.overlaps(other.get_window_extent(renderer)):
                raise ValueError("Figure captions overlap")
    image = OUT / "initial_positions_contact_sheet.png"
    fig.savefig(image, facecolor=fig.get_facecolor())
    plt.close(fig)
    np.savez_compressed(OUT / "preview_positions.npz", **arrays)
    (OUT / "preview_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"PREVIEW COMPLETE: 9 designs, {COUNT * len(DESIGNS)} points, no dynamics simulated")
    print(image)


if __name__ == "__main__":
    main()
