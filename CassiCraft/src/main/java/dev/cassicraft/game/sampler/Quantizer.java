package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;

/**
 * MODULE 2/3 — field→1&nbsp;m-block quantization (BUILD-PLAN.md §5.3,
 * chunk-field-quantization.md §1.3, §3). The load-bearing mapping from a
 * published {@link FieldSnapshot} to Minecraft block states.
 *
 * <p>This class is deliberately <b>Minecraft-free</b>: it returns a
 * {@link BlockKind} per block, never a {@code net.minecraft} type. That keeps
 * the quantization math (and the determinism gate that replays it) headlessly
 * testable without a running server, while the game-side writer maps
 * {@link BlockKind} → {@code BlockState} (see
 * {@code dev.cassicraft.game.writer.WorldWriter}).
 *
 * <p><b>Geometry.</b> The Phase-1 box is the chunk-aligned 192³&nbsp;m cube
 * (half-extent {@link TwoFluidSolver#EXTENT} = 96 per axis) over a 64³ grid of
 * 3&nbsp;m whole cells; a 1&nbsp;m Cassi block is a 1/3 trilinear sub-cell
 * sample at the block center ({@code blockPos + 0.5}). A block center maps to
 * normalized grid coords exactly as the shader sampler does
 * (chunk-field-quantization.md §1.2, §1.3):
 * <pre>
 *   gc = ((pos − window_center)·inv_extent)·hn + hn,  hn = N/2
 * </pre>
 * then the 8 surrounding cell corners are gathered in one fused traversal and
 * tri-lerped (the same neighbourhood traversal the GPU sampler uses).
 *
 * <p><b>Block mapping (quantization dials, calibrated from the measured settled
 * field — see the constant javadocs):</b>
 * <table>
 *   <caption>Block mapping table</caption>
 *   <tr><th>Channel</th><th>Condition</th><th>Block</th></tr>
 *   <tr><td>ρ density</td><td>ρ ≥ {@link #TAU_C} (hysteresis band, {@link #HYSTERESIS_DELTA})</td>
 *       <td>solid → STONE or COPPER_ORE (the registry-dressed kind)</td></tr>
 *   <tr><td>q coherence</td><td>solid and q ≥ {@link #Q_ORE_THRESHOLD}</td>
 *       <td>ore → COPPER_ORE (the q-precipitated vein, material-regimes §3)</td></tr>
 *   <tr><td>ρ dense-metal regime</td><td>solid and ρ ≥ {@code MaterialRegistry.COPPER_THETA_C} (the
 *       deep-dense metal tail)</td><td>ore → COPPER_ORE (the density-regime copper dressing, §1)</td></tr>
 *   <tr><td>ε² decoherence</td><td>solid and ε² ≥ {@link #EPS2_FLOOR}</td>
 *       <td>dissolution → AIR (carved)</td></tr>
 *   <tr><td>otherwise</td><td>ρ &lt; {@link #TAU_C} (below hysteresis band)</td>
 *       <td>air → AIR</td></tr>
 * </table>
 * The COPPER_ORE kind is the registry's honest dressing: a solid block becomes
 * copper only when its regime reaches the copper identity — the deep-dense
 * metal tail ({@code ρ ≥ MaterialRegistry.COPPER_THETA_C}, the registry's
 * density-θ_c — the densest demo material's condensation band) OR the
 * coherence-precipitated vein ({@code q ≥ Q_ORE_THRESHOLD}, the existing
 * terrain ore dial). Everything else in the solid regime is the iron/silicate
 * stone. The AIR/SOLID/ORE boundaries stay the calibrated dials; only the
 * kind within the solid regime follows the field's own material position
 * (material-regimes.md §1, §3 — the registry lands, the 'regime dressing' is
 * no longer surface).
 * ε² is not a published array in the ported {@link FieldSnapshot} (it rides
 * the ρ read per chunk-field-quantization.md §2); it is re-derived from the
 * published ρ and q via the φ-locked branch {@code EY=max, EI=min} →
 * {@code ε² = (EY − φ·EI)²} (see {@link #eps2}). This is a deterministic pure
 * function of the published channels.
 */
public final class Quantizer {

	/**
	 * Condensation threshold — solid above this ρ (a labeled quantization dial;
	 * material-regimes.md §1 θ_c). Calibrated from the measured settled-box ρ
	 * distribution (TerrainCensusMain, seed 42 @ 12 generations): the field's
	 * density body runs p50=1.007, p90=1.197, and 23.3% of the box sits below
	 * 0.90 — the thinner field reads as air/void, the dense 77% as organized
	 * condensate. τ_c = 0.90 cuts the actual density continuum so a meaningful
	 * fraction is air (not a monolith) and a meaningful fraction is stone.
	 * A labeled statistic, not a free-energy grant — it only classifies the
	 * published ρ; the physics (src/domain) is untouched.
	 */
	public static final float TAU_C = 0.90f;
	/**
	 * Hysteresis half-width — a solid block only dissolves below τ_c−δ. Held at
	 * 0.1 (~11% of the τ_c=0.90 band, the [0.80,0.90] dissolve floor): a field
	 * jittering around the measured boundary (the ~8% of the box with ρ<0.80) is
	 * mostly at the thin edge, so the 0.10 band keeps a solid from flickering
	 * each tick. Small relative to the body (p50=1.007), so re-quantization is
	 * flicker-free without blurring the structure.
	 */
	public static final float HYSTERESIS_DELTA = 0.1f;
	/**
	 * Decoherence floor — at/above this ε² a solid region dissolves (carves to
	 * air). Calibrated from the measured settled-box ε² distribution: p90=0.248,
	 * p99=0.515; 0.35 sits ≈p96, so dissolution opens the genuinely decoherent
	 * scars/edges (≈1.8% of the condensed field) into voids while the coherent
	 * bulk (mean ε²=0.109) stays solid. A labeled statistic of the published
	 * ε²= (EY−φ·EI)² — never a boost.
	 */
	public static final float EPS2_FLOOR = 0.35f;
	/**
	 * Coherence threshold — solid plus q ≥ this precipitates ore. Calibrated from
	 * the measured settled-box q distribution: p90=0.856, p99=1.117; 1.25 sits in
	 * the deep coherent tail, so ore precipitates as veins only in the
	 * best-locked field (≈0.3–0.4% of the box — present but not everywhere),
	 * the corpus's "coherence accumulates above a second threshold"
	 * (volumetric-terrain.md; material-regimes.md §3). A labeled statistic of the
	 * published q — never mints ore.
	 */
	public static final float Q_ORE_THRESHOLD = 1.25f;

	private static final int N = TwoFluidSolver.N;
	private static final int HN = N / 2;
	private static final float INV_EXTENT = 1.0f / TwoFluidSolver.EXTENT;

	/** Per-block quantized state (a scalar channel — not a worldgen height range). */
	public enum BlockKind {
		AIR, SOLID, ORE
	}

	/** The three field channels sampled at one block center (fused traversal). */
	public record CellSample(float rho, float q, float eps2) {
	}

	/**
	 * The full reader sample at one block center — ρ, q, derived ε², and the
	 * published river gradient {@code ∇(g·Φ)} (the Weatherglass's four channels,
	 * field-instruments §1.2). Gathered in one fused 8-corner traversal.
	 */
	public record FieldReading(float rho, float q, float eps2,
			float gradX, float gradY, float gradZ) {
	}

	/**
	 * A bounded region of quantized blocks — the pure output of a (cold)
	 * quantization pass. {@code cells} is indexed {@code dx + sizeX·(dy + sizeY·dz)}.
	 */
	public record QuantizedRegion(int minX, int minY, int minZ,
			int sizeX, int sizeY, int sizeZ, BlockKind[] cells) {
		public QuantizedRegion {
			cells = cells.clone();
		}

		public BlockKind at(int dx, int dy, int dz) {
			return cells[idx(dx, dy, dz)];
		}

		private int idx(int dx, int dy, int dz) {
			return dx + sizeX * (dy + sizeY * dz);
		}

		/**
		 * Salt-stable hash over the non-air blocks, sorted by position — the
		 * determinism fingerprint (BUILD-PLAN.md §9.5: same field → same blocks).
		 */
		public String contentHash() {
			java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(quantizedCount() * 12);
			for (int dz = 0; dz < sizeZ; dz++) {
				for (int dy = 0; dy < sizeY; dy++) {
					for (int dx = 0; dx < sizeX; dx++) {
						BlockKind k = at(dx, dy, dz);
						if (k == BlockKind.AIR) {
							continue;
						}
						bb.putInt(minX + dx);
						bb.putInt(minY + dy);
						bb.putInt(minZ + dz);
					}
				}
			}
			return sha256(bb.array());
		}

		/** Number of solid-or-ore blocks (excluding air). */
		public int quantizedCount() {
			int n = 0;
			for (BlockKind k : cells) {
				if (k != BlockKind.AIR) {
					n++;
				}
			}
			return n;
		}
	}

	private Quantizer() {
	}

	/**
	 * Map one block-center world coordinate to a normalized grid coordinate.
	 * {@code gc = ((pos + 0.5 − window_center)·inv_extent)·hn + hn}.
	 */
	public static double gridCoord(double blockPos, double windowCenter) {
		return ((blockPos + 0.5) - windowCenter) * INV_EXTENT * HN + HN;
	}

	/**
	 * Sample ρ, q (and derived ε²) at a block center — the fused 8-corner
	 * traversal the GPU sampler uses, one walk fetching all channels.
	 *
	 * <p><b>Box boundary.</b> The field exists only inside the anchored 192³ box
	 * (grid coords in {@code [0, N]}). A block whose center is <b>outside</b> the
	 * box reads as empty air — the box's outer face is the world's iso-surface
	 * (the previous clamp-to-edge made every outside block sample the boundary
	 * cell, so a player standing above or beyond the box was embedded in a
	 * degenerate solid slab — the "falls through the ground" bug). Out-of-box →
	 * air, deterministically. The 8-corner gather <b>clamps</b> a corner that
	 * would fall one cell beyond a face back into the boundary cell — it never
	 * wraps to the far side (world-seams.md §2.4: the zenith is the window's
	 * boundary, not its door). A block in the topmost cell therefore reads the
	 * top vacuum, not the dense floor row wrapped around a periodic torus (the
	 * altitude-seam artifact: "full chunks of stone in the sky", measured by
	 * SkyStoneProbeMain); the SOLVER torus is periodic, the publish is not.
	 */
	public static CellSample sampleAt(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		double gx = gridCoord(blockX, windowCenter[0]);
		double gy = gridCoord(blockY, windowCenter[1]);
		double gz = gridCoord(blockZ, windowCenter[2]);
		if (isOutsideBox(gx, gy, gz)) {
			return new CellSample(0f, 0f, 0f);
		}
		int i0 = floor(gx);
		int j0 = floor(gy);
		int k0 = floor(gz);
		double fx = gx - i0;
		double fy = gy - j0;
		double fz = gz - k0;
		float[] rho = snap.rho();
		float[] q = snap.q();
		// 8-corner gather — boundary corners CLAMP to the boundary cell (the box's
		// outer face is the iso-surface; no far-side periodic wrap at the publish).
		float[] r = new float[8];
		float[] qv = new float[8];
		int c = 0;
		for (int kk = 0; kk < 2; kk++) {
			for (int jj = 0; jj < 2; jj++) {
				for (int ii = 0; ii < 2; ii++) {
					int cell = flat(clamp(i0 + ii), clamp(j0 + jj), clamp(k0 + kk));
					r[c] = rho[cell];
					qv[c] = q[cell];
					c++;
				}
			}
		}
		float rhoMix = trilinear(r, fx, fy, fz);
		float qMix = trilinear(qv, fx, fy, fz);
		return new CellSample(rhoMix, qMix, eps2(rhoMix, qMix));
	}

	/**
	 * Clamp a grid-corner index to the box's in-bound interior {@code [0, N−1]} —
	 * a corner one cell beyond a face (index {@code N}) reverts to the boundary
	 * cell, so the outer faces are the iso-surface and never the periodic far side.
	 */
	private static int clamp(int grid) {
		return grid < 0 ? 0 : Math.min(grid, N - 1);
	}

	/**
	 * True when a block center maps to a grid coordinate outside the box
	 * ({@code [0, N]} inclusive) — such a position has no field, so it reads air.
	 * A block centered exactly at the boundary ({@code grid == N}) is the box's
	 * outer surface cell (inside); anything beyond is empty.
	 */
	private static boolean isOutsideBox(double gx, double gy, double gz) {
		return gx < 0 || gx > N || gy < 0 || gy > N || gz < 0 || gz > N;
	}

	/**
	 * Sample the Weatherglass's full read at a block center: ρ, q, derived ε²,
	 * and the published river gradient {@code ∇(g·Φ)} — one fused 8-corner walk
	 * over the rho/q/grad channels (the same fused traversal the GPU sampler
	 * uses). This is the corpus's "one extra sample at the player's position"
	 * (field-instruments §1.4); it costs the same as {@link #sampleAt} plus one
	 * vec3 per corner and presents no new channel. Boundary corners clamp to the
	 * boundary cell exactly as {@link #sampleAt} (the box's outer face is the
	 * iso-surface, not a periodic far side).
	 */
	public static FieldReading sampleReading(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		double gx = gridCoord(blockX, windowCenter[0]);
		double gy = gridCoord(blockY, windowCenter[1]);
		double gz = gridCoord(blockZ, windowCenter[2]);
		if (isOutsideBox(gx, gy, gz)) {
			return new FieldReading(0f, 0f, 0f, 0f, 0f, 0f);
		}
		int i0 = floor(gx);
		int j0 = floor(gy);
		int k0 = floor(gz);
		double fx = gx - i0;
		double fy = gy - j0;
		double fz = gz - k0;
		float[] rho = snap.rho();
		float[] q = snap.q();
		float[][] grad = snap.grad();
		float[] r = new float[8];
		float[] qv = new float[8];
		float[] gx8 = new float[8];
		float[] gy8 = new float[8];
		float[] gz8 = new float[8];
		int c = 0;
		for (int kk = 0; kk < 2; kk++) {
			for (int jj = 0; jj < 2; jj++) {
				for (int ii = 0; ii < 2; ii++) {
					int cell = flat(clamp(i0 + ii), clamp(j0 + jj), clamp(k0 + kk));
					r[c] = rho[cell];
					qv[c] = q[cell];
					float[] g = grad[cell];
					gx8[c] = g[0];
					gy8[c] = g[1];
					gz8[c] = g[2];
					c++;
				}
			}
		}
		float rhoMix = trilinear(r, fx, fy, fz);
		float qMix = trilinear(qv, fx, fy, fz);
		return new FieldReading(rhoMix, qMix, eps2(rhoMix, qMix),
				trilinear(gx8, fx, fy, fz),
				trilinear(gy8, fx, fy, fz),
				trilinear(gz8, fx, fy, fz));
	}

	/**
	 * Trilinear mix of an 8-corner gathered channel; corner order is
	 * {@code [z0/z1]×[y0/y1]×[x0/x1]} with x slowest — the shader's traversal.
	 */
	static float trilinear(float[] corners, double fx, double fy, double fz) {
		double wx0 = 1.0 - fx, wx1 = fx;
		double wy0 = 1.0 - fy, wy1 = fy;
		double wz0 = 1.0 - fz, wz1 = fz;
		double v = 0.0;
		int c = 0;
		for (int kk = 0; kk < 2; kk++) {
			double wk = kk == 0 ? wz0 : wz1;
			for (int jj = 0; jj < 2; jj++) {
				double wj = jj == 0 ? wy0 : wy1;
				for (int ii = 0; ii < 2; ii++) {
					double wi = ii == 0 ? wx0 : wx1;
					v += corners[c++] * wi * wj * wk;
				}
			}
		}
		return (float) v;
	}

	/**
	 * Re-derive ε² = (EY − φ·EI)² from the published ρ and q. With ρ = EY+EI
	 * and q = EY²+EI² the two roots are EY = max|min(EY,EI); this picks the
	 * {@code EY = (ρ+|EY−EI|)/2 ≥ EI} branch (the IC noise keeps EY ≥ EI in
	 * practice). Deterministic, a pure function of the published channels.
	 */
	public static float eps2(float rho, float q) {
		float d2 = 2.0f * q - rho * rho;
		float d = (float) Math.sqrt(Math.max(0.0f, d2));
		float ey = (rho + d) * 0.5f;
		float ei = (rho - d) * 0.5f;
		float eps = ey - (float) TwoFluidSolver.PHI * ei;
		return eps * eps;
	}

	/**
	 * Cold-start quantization (no prior state): a block solidifies at exactly
	 * {@code ρ ≥ τ_c}; dissolution overrides solid; the registry-dressed copper
	 * kind overrides plain solid. The ORE kind (the demo's COPPER_ORE block) is
	 * fired when the regime reaches the copper identity — the deep-dense metal
	 * tail (ρ ≥ the registry's copper θ_c, {@link
	 * dev.cassicraft.game.material.MaterialRegimeRead#isCopperRegime}) OR the
	 * coherence-precipitated q vein ({@link #Q_ORE_THRESHOLD}). The AIR/SOLID
	 * boundary stays the calibrated dial; only the kind within the solid regime
	 * follows the field's own material position (material-regimes §1, §3).
	 */
	public static BlockKind quantizeCold(float rho, float q, float eps2) {
		if (rho < TAU_C || eps2 >= EPS2_FLOOR) {
			return BlockKind.AIR;
		}
		return isCopperDressed(rho, q) ? BlockKind.ORE : BlockKind.SOLID;
	}

	/**
	 * Hysteresis-aware quantization for a re-quantized block. A {@code SOLID} or
	 * {@code ORE} block stays solid while {@code ρ ≥ τ_c − δ} (so a field
	 * jitter around the boundary does not flicker the block each tick); an
	 * {@code AIR} block must cross {@code ρ ≥ τ_c} to solidify. Within the solid
	 * regime the kind follows the registry dressing (see {@link #quantizeCold}).
	 */
	public static BlockKind quantize(float rho, float q, float eps2, BlockKind prior) {
		boolean solid = (prior == BlockKind.SOLID || prior == BlockKind.ORE)
				? rho >= TAU_C - HYSTERESIS_DELTA
				: rho >= TAU_C;
		if (!solid || eps2 >= EPS2_FLOOR) {
			return BlockKind.AIR;
		}
		return isCopperDressed(rho, q) ? BlockKind.ORE : BlockKind.SOLID;
	}

	/**
	 * The registry-dressed copper test — whether a solid-regime sample is the
	 * COPPER_ORE kind: the deep-dense metal tail ({@code ρ ≥ COPPER_THETA_C},
	 * {@link MaterialRegimeRead#isCopperRegime}) OR the coherence-precipitated
	 * q vein ({@code q ≥ Q_ORE_THRESHOLD}). Both reach the copper identity
	 * (material-regimes §1 density-θ_c and §3 the q-vein); neither re-tunes the
	 * calibrated dials — they select the kind within the solid boundary.
	 */
	private static boolean isCopperDressed(float rho, float q) {
		return dev.cassicraft.game.material.MaterialRegimeRead.isCopperRegime(rho)
				|| q >= Q_ORE_THRESHOLD;
	}

	/**
	 * Quantize a bounded region (cold pass, no hysteresis) — used by the
	 * determinism gate and as the first full pass of a re-quantized patch.
	 */
	public static QuantizedRegion quantizeRegion(FieldSnapshot snap, double[] windowCenter,
			int minX, int minY, int minZ, int sizeX, int sizeY, int sizeZ) {
		BlockKind[] cells = new BlockKind[sizeX * sizeY * sizeZ];
		for (int dz = 0; dz < sizeZ; dz++) {
			for (int dy = 0; dy < sizeY; dy++) {
				for (int dx = 0; dx < sizeX; dx++) {
					CellSample s = sampleAt(snap, windowCenter, minX + dx, minY + dy, minZ + dz);
					cells[dx + sizeX * (dy + sizeY * dz)] = quantizeCold(s.rho(), s.q(), s.eps2());
				}
			}
		}
		return new QuantizedRegion(minX, minY, minZ, sizeX, sizeY, sizeZ, cells);
	}

	private static int flat(int i, int j, int k) {
		return i + N * (j + N * k);
	}

	private static int floor(double v) {
		return (int) Math.floor(v);
	}

	private static String sha256(byte[] data) {
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(data);
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte b : h) {
				sb.append(String.format("%02x", b));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}
}
