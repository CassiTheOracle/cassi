package dev.cassicraft.domain.engine;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The gradient pass port of {@code CassiCosmos/compute/cassi_nbody_gravity.glsl}
 * {@code grad_pass} (`:431-472`) + {@code chord_s_at} (`:354-362`): builds the
 * cell-centered {@code ∇(g·Φ)} field. Each cell evaluates {@code S = g·Φ} whole
 * (never hand-split {@code g∇Φ + Φ(ξ−1)∇q} — the doctrine comment at
 * `cassi_nbody_gravity.glsl:46-48`), then takes second-order central differences
 * along x/y/z with periodic wraps. {@code gradient_order = 2} (the default,
 * `cassi_physics_engine.gd:107`) → the 3-point (2nd-order) stencil.
 *
 * <p>The coherence / chord law (shader `chor_d_s_at`):
 * <pre>
 *   q  = ρ² / (ρ² + φ⁻² + ε²),   ρ = EY+EI,   ε = EY − φ·EI
 *   g  = 1 + (ξ − 1)·q,          ξ = φ⁶ = 17.94427191
 *   S  = g · Φ
 *   ∇S = ((S(x+1)−S(x−1))/(2·h_x), (S(y+1)−S(y−1))/(2·h_y), (S(z+1)−S(z−1))/(2·h_z))
 * </pre>
 * with {@code h_i = extent_i / (N·0.5)} (shader `:450`).
 *
 * <p>The output is the <b>vec3 trim</b> ({@code .xyz}, {@code .w = 0} in the
 * engine) — a {@code CELLS × 3} float buffer, 3 MiB at 64³
 * (chunk-field-quantization.md §2; PORT-SPEC §3). The {@code _grad_buf} in the
 * engine is vec4/cell with `.w = 0` (shader `:469-471`); the trim is lossless.
 *
 * <p>Dual-grid note (PORT-SPEC §3.1, flag #5): the engine default
 * {@code dual_grid = true} runs a second shifted-lattice pass. The field-only
 * port pins {@code dual_grid = false} (single {@code _grad_buf}) — the engine
 * header states the default-off path is numerically bit-identical to the
 * legacy chain (`cassi_physics_engine.gd:1078-1079`). The BCC dual chain is a
 * later, non-default extension.
 */
public final class GradientPass {

	public static final int N = TwoFluidSolver.N;
	public static final int CELLS = N * N * N;

	private static final float PHI = (float) TwoFluidSolver.PHI;
	private static final float PHI_INV2 = 0.3819660112501051f;   // φ⁻² (shader :240)
	private static final float XI = 17.94427191f;                 // ξ = φ⁶ (config :82)
	private static final float EXTENT = TwoFluidSolver.EXTENT;

	/**
	 * Gradient trim buffer: {@code CELLS × 3} floats, one flat contiguous array
	 * {@code grad[cell*3 + comp]} (comp {@code 0=x,1=y,2=z}) — the vec3 trim.
	 * Contiguous per publish so the snapshot's defensive copy is a single
	 * {@code System.arraycopy} (the FIX 1 bulk-storage pattern — no 262,144
	 * small float[3] objects).
	 */
	private final float[] grad;

	public GradientPass() {
		this.grad = new float[CELLS * 3];
	}

	/**
	 * Compute {@code ∇(g·Φ)} from the potential field {@code phi} and the
	 * two-fluid fields {@code ey}/{@code ei} into the internal vec3-trim
	 * buffer ({@link #grad()}). Periodic torus wraps; second-order central
	 * differences ({@code gradient_order = 2}).
	 *
	 * @param phi potential Φ (real part of the Poisson solve)
	 * @param ey  EY field
	 * @param ei  EI field
	 */
	public void compute(float[] phi, float[] ey, float[] ei) {
		float hx = EXTENT / (N * 0.5f);   // per-axis cell size (shader :450)
		float hy = hx;
		float hz = hx;
		float denomX = 2.0f * hx;
		float denomY = 2.0f * hy;
		float denomZ = 2.0f * hz;
		for (int k = 0; k < N; k++) {
			int dkzp = N * N * ((k + 1) % N - k);
			int dkzm = N * N * ((k - 1 + N) % N - k);
			for (int j = 0; j < N; j++) {
				int djyp = N * ((j + 1) % N - j);
				int djym = N * ((j - 1 + N) % N - j);
				for (int i = 0; i < N; i++) {
					int id = i + N * (j + N * k);
					int dixp = (i + 1) % N - i;
					int dixm = (i - 1 + N) % N - i;
					float spx = sCell(id + dixp, phi, ey, ei);
					float smx = sCell(id + dixm, phi, ey, ei);
					float spy = sCell(id + djyp, phi, ey, ei);
					float smy = sCell(id + djym, phi, ey, ei);
					float spz = sCell(id + dkzp, phi, ey, ei);
					float smz = sCell(id + dkzm, phi, ey, ei);
					int gi = id * 3;
					grad[gi] = (spx - smx) / denomX;
					grad[gi + 1] = (spy - smy) / denomY;
					grad[gi + 2] = (spz - smz) / denomZ;
				}
			}
		}
	}

	/** {@code S = g·Φ} at a cell — the whole chord product (shader `chord_s_at`). */
	private static float sCell(int id, float[] phi, float[] ey, float[] ei) {
		float eyv = ey[id];
		float eiv = ei[id];
		float rhoF = eyv + eiv;
		float eps = eyv - PHI * eiv;
		float q = (rhoF * rhoF) / (rhoF * rhoF + PHI_INV2 + eps * eps);
		float g = 1.0f + (XI - 1.0f) * q;
		return g * phi[id];
	}

	/** Readonly view of the vec3-trim gradient buffer ({@code [cells*3]} flat, component-major). */
	public float[] grad() {
		return grad;
	}
}
