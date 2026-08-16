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
 * <p><b>Block mapping (hypothesis thresholds, all tuneable constants):</b>
 * <table>
 *   <caption>Block mapping table</caption>
 *   <tr><th>Channel</th><th>Condition</th><th>Block</th></tr>
 *   <tr><td>ρ density</td><td>ρ ≥ τ_c = 0.5 (hysteresis band τ_c−δ..τ_c, δ=0.1)</td>
 *       <td>solid → STONE</td></tr>
 *   <tr><td>q coherence</td><td>solid and q ≥ q_ore = 1.35</td>
 *       <td>ore → COPPER_ORE</td></tr>
 *   <tr><td>ε² decoherence</td><td>solid and ε² ≥ ε_floor = 1.0</td>
 *       <td>dissolution → AIR (carved)</td></tr>
 *   <tr><td>otherwise</td><td>ρ &lt; τ_c (below hysteresis band)</td>
 *       <td>air → AIR</td></tr>
 * </table>
 * ε² is not a published array in the ported {@link FieldSnapshot} (it rides
 * the ρ read per chunk-field-quantization.md §2); it is re-derived from the
 * published ρ and q via the φ-locked branch {@code EY=max, EI=min} →
 * {@code ε² = (EY − φ·EI)²} (see {@link #eps2}). This is a deterministic pure
 * function of the published channels.
 */
public final class Quantizer {

	/** Condensation threshold — solid above this ρ (engine's τ_c default). */
	public static final float TAU_C = 0.5f;
	/** Hysteresis half-width — a solid block only dissolves below τ_c−δ. */
	public static final float HYSTERESIS_DELTA = 0.1f;
	/** Decoherence floor — at/above this ε² a region dissolves (carves to air). */
	public static final float EPS2_FLOOR = 1.0f;
	/** Coherence threshold — solid plus q ≥ this precipitates ore. */
	public static final float Q_ORE_THRESHOLD = 1.35f;

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
	 */
	public static CellSample sampleAt(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		double gx = clamp(gridCoord(blockX, windowCenter[0]));
		double gy = clamp(gridCoord(blockY, windowCenter[1]));
		double gz = clamp(gridCoord(blockZ, windowCenter[2]));
		int i0 = floor(gx);
		int j0 = floor(gy);
		int k0 = floor(gz);
		double fx = gx - i0;
		double fy = gy - j0;
		double fz = gz - k0;
		int i1 = i0 + 1;
		int j1 = j0 + 1;
		int k1 = k0 + 1;
		float[] rho = snap.rho();
		float[] q = snap.q();
		// 8-corner gather.
		float[] r = new float[8];
		float[] qv = new float[8];
		int c = 0;
		for (int kk = 0; kk < 2; kk++) {
			for (int jj = 0; jj < 2; jj++) {
				for (int ii = 0; ii < 2; ii++) {
					int cell = flat(mod(i0 + ii, N), mod(j0 + jj, N), mod(k0 + kk, N));
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
	 * Sample the Weatherglass's full read at a block center: ρ, q, derived ε²,
	 * and the published river gradient {@code ∇(g·Φ)} — one fused 8-corner walk
	 * over the rho/q/grad channels (the same fused traversal the GPU sampler
	 * uses). This is the corpus's "one extra sample at the player's position"
	 * (field-instruments §1.4); it costs the same as {@link #sampleAt} plus one
	 * vec3 per corner and presents no new channel.
	 */
	public static FieldReading sampleReading(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		double gx = clamp(gridCoord(blockX, windowCenter[0]));
		double gy = clamp(gridCoord(blockY, windowCenter[1]));
		double gz = clamp(gridCoord(blockZ, windowCenter[2]));
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
					int cell = flat(mod(i0 + ii, N), mod(j0 + jj, N), mod(k0 + kk, N));
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
	 * {@code ρ ≥ τ_c}; dissolution overrides solid; high-q overrides plain solid.
	 */
	public static BlockKind quantizeCold(float rho, float q, float eps2) {
		if (rho < TAU_C || eps2 >= EPS2_FLOOR) {
			return BlockKind.AIR;
		}
		return q >= Q_ORE_THRESHOLD ? BlockKind.ORE : BlockKind.SOLID;
	}

	/**
	 * Hysteresis-aware quantization for a re-quantized block. A {@code SOLID} or
	 * {@code ORE} block stays solid while {@code ρ ≥ τ_c − δ} (so a field
	 * jitter around the boundary does not flicker the block each tick); an
	 * {@code AIR} block must cross {@code ρ ≥ τ_c} to solidify.
	 */
	public static BlockKind quantize(float rho, float q, float eps2, BlockKind prior) {
		boolean solid = (prior == BlockKind.SOLID || prior == BlockKind.ORE)
				? rho >= TAU_C - HYSTERESIS_DELTA
				: rho >= TAU_C;
		if (!solid || eps2 >= EPS2_FLOOR) {
			return BlockKind.AIR;
		}
		return q >= Q_ORE_THRESHOLD ? BlockKind.ORE : BlockKind.SOLID;
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

	private static int mod(int v, int m) {
		return ((v % m) + m) % m;
	}

	private static double clamp(double v) {
		return v < 0 ? 0 : (v > N ? N : v);
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
