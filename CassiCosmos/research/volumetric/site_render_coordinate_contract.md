# Site-native renderer — coordinate and seam contract

Status: **BLOCKING DESIGN CONTRACT** — no live traversal may consume site positions until these rules are implemented and verified.

## 1. Two coordinate spaces

The live mesh stores `_ml_sites` in **tile coordinates**:

```
s_tile ∈ [0, Lx) × [0, Ly) × [0, Lz)
```

The particle and camera renderer uses centered **world coordinates**. The physics engine's established relation is:

```
x_world = s_tile − extent
s_tile  = x_world + extent
```

When the tracked physics window is translated, the render transform also carries the window origin:

```
x_world = s_tile − extent + window_center
s_tile  = x_world − window_center + extent
```

The exact sign and extent source must be shared by the renderer, particle instancer, site hash, and any future volumetric upload. No renderer shader may compare a world-space ray directly against raw `[0,L)` site positions.

## 2. Stable render frame

The final renderer is world-space. The physics window is an implementation window, not a render-space origin. `_window_center` and `box_scale` may move the numerical tile, but they must not translate the camera or visibly rebase already-rendered particles.

The renderer therefore receives:

- `window_center` — the current applied physics origin;
- `extent` — the current applied tile half-extent;
- `site_to_world` — the single transform above;
- `topology_generation` — incremented after site positions/JFA labels/topology are coherently rebuilt.

History is invalid when `topology_generation` changes or when the applied transform changes enough that reprojection cannot be trusted.

## 3. Periodic seam policy

The PDE/JFA mesh retains periodic label contacts. A finite non-wrapped render cannot silently treat a periodic seam edge as an ordinary face.

The renderer must choose one explicit policy per run:

1. **Open tile:** drop seam-crossing graph edges and fade the outer finite tile into vacuum. This removes visible periodic repetition but does not claim open-boundary physics.
2. **Periodic image:** retain seam edges with an integer image offset `m ∈ {-1,0,1}³`; evaluate the neighbor at `s_tile + m·L` transformed to world coordinates. This is physically consistent with the periodic solver but displays a tiled universe.
3. **Hybrid diagnostic:** expose both modes and never call the open-tile result an exact rendering of the periodic PDE.

The initial production target is **Open tile with a continuous coherence-weighted fade**, because the user’s immediate problem is the visible box. The periodic-image mode remains the independent diagnostic for checking seam continuity.

## 4. Adjacency authority

The existing JFA label field is an accelerator-grid representation. A graph extracted from +x/+y/+z label changes is exact only with respect to that sampled label field, not necessarily every continuous Voronoi sliver or near-cocircular face.

Therefore every topology implementation must expose:

- `graph_source = sampled_jfa` or `continuous_exact`;
- `topology_generation`;
- an edge image offset for periodic mode;
- a validation report against a full all-site continuous oracle.

No fixed-K graph is adopted without passing next-face and precision gates. The rejected K=32/K=64 prototype remains diagnostic only.
