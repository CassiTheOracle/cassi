package dev.cassicraft.domain.engine;

import java.util.Arrays;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports — enforced by the `domain`
 * source set's classpath (see build.gradle `verifyDomainNoNetMinecraft`).
 *
 * <p>The two-fluid leapfrog port of {@code CassiCosmos/compute/cassi_two_fluid.glsl}
 * (the pass_a / pass_b double-buffered scheme). {@code pass_a} reads the
 * canonical {@code ey/ei/vel/rho} (old values) and computes the next field into
 * a non-aliasing {@code scr} double-buffer — read and write never alias within
 * a pass (the engine's determinism fix, shader header `:24-35`). {@code pass_b}
 * copies {@code scr} into the canonical {@code ey/ei/q/vel} and recomputes
 * {@code q = EY²+EI²} and {@code ε² = (EY−φ·EI)²} into {@code vel[].w}.
 *
 * <p>Equations (shader `:8-11`):
 * <pre>
 *   ∂²EY/∂t² = c²·∇²EY − ω₀²·(EY − φ·EI)
 *   ∂²EI/∂t² = c²·∇²EI + ω₀²·(EY − φ·EI)
 * </pre>
 * The `c²` is <b>not</b> a separate multiply in the implementation — not in
 * pass_a (shader `:202-203`), not in the engine config. The 19-point operator
 * carries the `h₀²` normalization ("the current operator reads h²∇²", shader
 * `:74-80`); the wave speed is implicit in the `dt`/`h₀` pairing, and
 * {@code c_s = h₀/dt} is a derived display quantity only (PORT-SPEC §1.1,
 * flag #1 resolved). The port therefore implements the shader form verbatim —
 * <b>no {@code c²} multiply anywhere</b>.
 *
 * <p>The spatial operator is the deterministic 19-point anisotropic stencil:
 * per-axis weights {@code b_ij = (1/3)·h₀²/(h_i²+h_j²)}, {@code a_i =
 * h₀²/h_i² − 2(b_ij + b_ik)}, with {@code h_i = 2·extent_i/N},
 * {@code h₀ = 2·min(extent)/N} (shader `:86-146`). Precomputed once in the
 * constructor with the same fp32 expression order; at the unit-aspect cube they
 * reduce to exactly {@code a = 1/3, b = 1/6} (shader `:81-82`). The CassiCraft
 * box is the cube {@code box_aspect=(1,1,1), cluster_radius=64} → per-axis
 * half-extent {@code 96} (PORT-SPEC §5, chunk-field-quantization.md §1.2).
 * Boundary conditions: periodic torus wraps {@code (i+1)%N},
 * {@code (i−1+N)%N} — never a clamp (PORT-SPEC §1.4, flag #3).
 *
 * <p>{@code source_strength = 0} (engine default, `cassi_physics_engine.gd:88`)
 * is kept, so the {@code exp(-r2·4)} source terms stay <b>off</b> the parity
 * path — only the {@code ρ·0.001} attractor term remains (PORT-SPEC §1.5).
 * With a nonzero source the shader's Gaussian terms (shader `:149-172`) would
 * need porting; they are deliberately not on the default path.
 *
 * <p>IC seed: {@code java.util.Random} flat noise is retained for the fixed-seed
 * Java-only determinism gate. The <em>engine</em> IC uses GDScript
 * {@code RandomNumberGenerator.randf_range} (PORT-SPEC §1.2, flag #2 deferred
 * to the parity harness): a GDScript-RNG reproduction is a parity concern, not
 * this port pass.
 */
public final class TwoFluidSolver {

	/** Grid cells per axis — {@code grid_N = 64}, 64³ = 262,144 cells. */
	public static final int N = 64;
	/** Total cell count. */
	public static final int CELLS = N * N * N;

	/** CassiCraft box half-extent per axis (unit-aspect cube, PORT-SPEC §5). */
	public static final float EXTENT = 96.0f;

	/** One field step per Minecraft tick (owner config pin, PORT-SPEC §5). */
	public static final double DT = 0.05;
	/** ω₀² — two-fluid resonance (default 20.0, `cassi_physics_engine.gd:2180`). */
	public static final double OMEGA2 = 20.0;
	/** φ — the golden-ratio coupling (`cassi_physics_engine.gd:43`). */
	public static final double PHI = 1.618033988749895;
	/** φ². */
	public static final double PHI2 = PHI * PHI;

	/**
	 * The 18-point stencil offsets plus the 0 (self) tap, in flat index units
	 * (engine tap set: center, ±x, ±y, ±z, then the twelve face diagonals).
	 * Kept for reference; pass_a computes the same taps directly from wrapped
	 * per-cell deltas so the periodic boundary is applied exactly.
	 */
	static final int[] STENCIL_X = {
			// center, ±x, ±y, ±z, then the twelve ±xy/±xz/±yz corners.
			0, 1, -1, N, -N, N * N, -(N * N),
			1 + N, 1 - N, -1 + N, -1 - N,
			1 + N * N, 1 - N * N, -1 + N * N, -1 - N * N,
			N + N * N, N - N * N, -N + N * N, -N - N * N,
	};
	/** Number of taps in the stencil (center + 18 neighbors). */
	public static final int STENCIL_SIZE = 19;

	// 19-point anisotropic weights (precomputed once, shader expression order).
	private final float ax;
	private final float ay;
	private final float az;
	private final float bxy;
	private final float bxz;
	private final float byz;

	// Canonical channels.
	private final float[] ey;      // EY field
	private final float[] ei;      // EI field
	private final float[] q;       // q = EY²+EI² (canonical coherence channel)
	private final float[] vel;     // vec4/cell: .x=∂EY/∂t, .y=∂EI/∂t, .z=0, .w=ε²
	private final float[] rho;     // ρ = EY+EI (single channel)
	private final float[] scr;     // pass_a double-buffer (vec4/cell: ey,ei,vx,vy)

	private final java.util.Random rng;

	public TwoFluidSolver(long seed) {
		this.ey = new float[CELLS];
		this.ei = new float[CELLS];
		this.q = new float[CELLS];
		this.vel = new float[CELLS * 4];
		this.rho = new float[CELLS];
		this.scr = new float[CELLS * 4];
		this.rng = new java.util.Random(seed);

		// Per-axis cell sizes and 19-point weights — the engine's exact fp32
		// expression order (cassi_two_fluid.glsl:91-102). At the cube these
		// reduce to a = 1/3, b = 1/6 exactly, but the general form is kept so
		// a non-cube box (the default-aspect baseline) ports unchanged.
		float hn = N * 0.5f;                       // N·0.5
		float hx = EXTENT / hn;                    // 2·extent_x/N
		float hy = EXTENT / hn;
		float hz = EXTENT / hn;
		float h0 = Math.min(Math.min(EXTENT, EXTENT), EXTENT) / hn;   // 2·min(extent)/N
		float hx2 = hx * hx;
		float hy2 = hy * hy;
		float hz2 = hz * hz;
		float h02 = h0 * h0;
		this.bxy = (1.0f / 3.0f) * h02 / (hx2 + hy2);
		this.bxz = (1.0f / 3.0f) * h02 / (hx2 + hz2);
		this.byz = (1.0f / 3.0f) * h02 / (hy2 + hz2);
		this.ax = h02 / hx2 - 2.0f * (bxy + bxz);
		this.ay = h02 / hy2 - 2.0f * (bxy + byz);
		this.az = h02 / hz2 - 2.0f * (bxz + byz);
	}

	/**
	 * Initialise a deterministic fixed-seed field (engine `_init_field` shape,
	 * `cassi_physics_engine.gd:1387-1422`): flat noise in EY/EI, {@code q =
	 * EY²+EI²}, {@code ρ = EY+EI}, {@code vel} and {@code scr} zeroed. The RNG
	 * is {@link java.util.Random} (Java-internal determinism gate); the engine's
	 * GDScript RNG reproduction is a parity-harness concern (flag #2 deferred).
	 */
	public void seed() {
		for (int i = 0; i < CELLS; i++) {
			ey[i] = rng.nextFloat();
			ei[i] = rng.nextFloat();
			rho[i] = ey[i] + ei[i];
			q[i] = ey[i] * ey[i] + ei[i] * ei[i];
		}
		Arrays.fill(vel, 0f);
		Arrays.fill(scr, 0f);
	}

	/**
	 * Pass A (shader `pass_a`, `:178-216`): read the canonical old ey/ei/vel/rho,
	 * compute the leapfrog half-step into the {@code scr} double-buffer. Per cell:
	 * {@code acc = lap ∓ ω₀²·(EY−φ·EI)}, {@code v ← v + acc·dt},
	 * {@code ψ ← ψ + v·dt + source·dt²}. The 19-point Laplacian uses the
	 * precomputed anisotropic weights and periodic wraps.
	 */
	public void passA() {
		float dt = (float) DT;
		float omega2 = (float) OMEGA2;
		float phi = (float) PHI;
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

					float eyc = ey[id];
					float eic = ei[id];

					// Axis second differences.
					float axis_x = ey[id + dixp] + ey[id + dixm] - 2.0f * eyc;
					float axis_y = ey[id + djyp] + ey[id + djym] - 2.0f * eyc;
					float axis_z = ey[id + dkzp] + ey[id + dkzm] - 2.0f * eyc;
					// Face diagonals (four corners − 4·center each).
					float fd_xy = (ey[id + dixp + djyp] + ey[id + dixm + djyp]
							+ ey[id + dixp + djym] + ey[id + dixm + djym] - 4.0f * eyc);
					float fd_xz = (ey[id + dixp + dkzp] + ey[id + dixm + dkzp]
							+ ey[id + dixp + dkzm] + ey[id + dixm + dkzm] - 4.0f * eyc);
					float fd_yz = (ey[id + djyp + dkzp] + ey[id + djym + dkzp]
							+ ey[id + djyp + dkzm] + ey[id + djym + dkzm] - 4.0f * eyc);
					float lap_ey = ax * axis_x + ay * axis_y + az * axis_z
							+ bxy * fd_xy + bxz * fd_xz + byz * fd_yz;

					// Same operator applied to EI.
					float eaxis_x = ei[id + dixp] + ei[id + dixm] - 2.0f * eic;
					float eaxis_y = ei[id + djyp] + ei[id + djym] - 2.0f * eic;
					float eaxis_z = ei[id + dkzp] + ei[id + dkzm] - 2.0f * eic;
					float efd_xy = (ei[id + dixp + djyp] + ei[id + dixm + djyp]
							+ ei[id + dixp + djym] + ei[id + dixm + djym] - 4.0f * eic);
					float efd_xz = (ei[id + dixp + dkzp] + ei[id + dixm + dkzp]
							+ ei[id + dixp + dkzm] + ei[id + dixm + dkzm] - 4.0f * eic);
					float efd_yz = (ei[id + djyp + dkzp] + ei[id + djym + dkzp]
							+ ei[id + djyp + dkzm] + ei[id + djym + dkzm] - 4.0f * eic);
					float lap_ei = ax * eaxis_x + ay * eaxis_y + az * eaxis_z
							+ bxy * efd_xy + bxz * efd_xz + byz * efd_yz;

					// φ coupling and leapfrog acceleration (shader :202-213).
					float ey_ei_diff = eyc - phi * eic;
					float acc_ey = lap_ey - omega2 * ey_ei_diff;
					float acc_ei = lap_ei + omega2 * ey_ei_diff;

					int vi = id * 4;
					float vx_new = vel[vi] + acc_ey * dt;
					float vy_new = vel[vi + 1] + acc_ei * dt;

					// Source terms at source_strength = 0: the exp(-r2·4) terms
					// drop out, leaving the rho·0.001 attractor (shader :149-172).
					float src_ey = rho[id] * 0.001f;
					float src_ei = (rho[id] * 0.707f) * 0.001f;

					float ey_new = eyc + vx_new * dt + src_ey * dt * dt;
					float ei_new = eic + vy_new * dt + src_ei * dt * dt;

					int si = vi;
					scr[si] = ey_new;
					scr[si + 1] = ei_new;
					scr[si + 2] = vx_new;
					scr[si + 3] = vy_new;
				}
			}
		}
	}

	/**
	 * Pass B (shader `pass_b`, `:222-246`): copy {@code scr} into the canonical
	 * {@code ey/ei/q/vel} buffers and recompute {@code q = EY²+EI²} and
	 * {@code ε² = (EY−φ·EI)²} into {@code vel[].w}. Also refreshes
	 * {@code ρ = EY+EI} (the published single channel, corpus canonical form).
	 */
	public void passB() {
		float phi = (float) PHI;
		for (int id = 0; id < CELLS; id++) {
			int si = id * 4;
			float ey_new = scr[si];
			float ei_new = scr[si + 1];
			ey[id] = ey_new;
			ei[id] = ei_new;
			float q_val = ey_new * ey_new + ei_new * ei_new;
			q[id] = q_val;
			float eps = ey_new - phi * ei_new;
			float eps2 = eps * eps;
			vel[si] = scr[si + 2];
			vel[si + 1] = scr[si + 3];
			vel[si + 2] = 0.0f;
			vel[si + 3] = eps2;
			rho[id] = ey_new + ei_new;
		}
	}

	/** One full leapfrog step = pass_a + pass_b. */
	public void step() {
		passA();
		passB();
	}

	/** Readonly view of the EY field. */
	public float[] ey() {
		return ey;
	}

	/** Readonly view of the EI field. */
	public float[] ei() {
		return ei;
	}

	/** Readonly view of the canonical coherence channel {@code q = EY²+EI²}. */
	public float[] q() {
		return q;
	}

	/** Readonly view of the velocity/ε² channel (vec4/cell; .w = ε²). */
	public float[] vel() {
		return vel;
	}

	/** Readonly view of ρ = EY+EI (single channel). */
	public float[] rho() {
		return rho;
	}

	/** Stable hash of every buffer — the determinism fingerprint the harness replays. */
	public String stateHash() {
		java.security.MessageDigest md;
		try {
			md = java.security.MessageDigest.getInstance("SHA-256");
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
		for (float[] b : new float[][] { ey, ei, vel, rho }) {
			java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(b.length * 4);
			bb.asFloatBuffer().put(b);
			md.update(bb.array());
		}
		byte[] d = md.digest();
		StringBuilder sb = new StringBuilder(d.length * 2);
		for (byte x : d) {
			sb.append(String.format("%02x", x));
		}
		return sb.toString();
	}
}
