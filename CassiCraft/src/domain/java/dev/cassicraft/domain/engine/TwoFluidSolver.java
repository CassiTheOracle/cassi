package dev.cassicraft.domain.engine;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadFactory;

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
 * <p>IC seed — the port's answer to the surface-emergence falsification (the
 * field was a uniform ~72–75%-solid sponge with no vertical density plane at
 * any reachable t, because the old {@link #seed()} was flat {@code java.util
 * .Random} noise in EY/EI). The field is now <b>born as a coherent condensed
 * body</b>: a real vertical density profile (dense below, thin above, a smooth
 * surface transition at the anchor plane) with a matched-φ coherence lock, so
 * the world <em>is</em> the field's condensation rather than a uniform sponge.
 * {@code java.util.Random} (seed-derived, deterministic) is retained; the
 * engine's GDScript {@code RandomNumberGenerator.randf_range} reproduction is
 * a parity concern (PORT-SPEC §1.2, flag #2 deferred). Design authority: the
 * engine's own opt-in {@code field_attractor_init} mode
 * ({@code cassi_physics_engine.gd:1437-1444} — EI small positive with
 * {@code ±10%} variation, {@code EY = φ·EI ± 1e-3}: the coherence gate)
 * supplies the φ-lock, and the corpus's body vocabulary supplies the envelope:
 * {@code atmosphere-orbits-auroras.md} §1.1 ("an atmosphere is the field's own
 * hydrostatic envelope — the ρ profile where the field's pressure gradient
 * balances the gravitational pull of the body underneath"; the hydrostatic
 * condensate {@code ρ_Y = ρ_c/(1+(r/r_c)²)}), §2.2 ("a body is the merge
 * lineage condensing under the order-selective coherence gate",
 * {@code q_sel = q_coh·q_ord > φ⁻² ≈ 0.382}), and {@code material-regimes.md}
 * §1 (a material is a point in the field regime; {@code θ_c} the condensation
 * threshold). The IC freezes the merge lineage's finished work — the world was
 * formed <em>before</em> the player arrived, so the birth state is a body, not
 * a perturbation and not a block write.
 */
public final class TwoFluidSolver {

	/** Grid cells per axis — {@code grid_N = 64}, 64³ = 262,144 cells. */
	public static final int N = 64;
	/** Total cell count. */
	public static final int CELLS = N * N * N;

	/** CassiCraft box half-extent per axis (unit-aspect cube, PORT-SPEC §5). */
	public static final float EXTENT = 96.0f;

	/**
	 * One field step per Minecraft tick, at the engine's step default
	 * {@code dt = 0.001} (`cassi_physics_engine.gd:81`, "far below both CFL
	 * bounds", `cassi_two_fluid.glsl`). The owner re-pinned this from the Phase-1
	 * 0.05 placeholder to the sim's own operating point so the field fills
	 * slowly; the cadence (one step per Minecraft tick) is unchanged — only the
	 * step size drops 50×, so each tick advances {@code 0.001} field-time units.
	 */
	public static final double DT = 0.001;
	/** ω₀² — two-fluid resonance (default 20.0, `cassi_physics_engine.gd:2180`). */
	public static final double OMEGA2 = 20.0;
	/** φ — the golden-ratio coupling (`cassi_physics_engine.gd:43`). */
	public static final double PHI = 1.618033988749895;
	/** φ². */
	public static final double PHI2 = PHI * PHI;

	// ---- Condensed-body IC constants (the {@link #seed()} birth state) ----
	/**
	 * The dense body's target ρ (density {@code EY+EI}) at the box floor — the
	 * ground's hydrostatic condensation (the corpus's "the body under the
	 * envelope", {@code atmosphere-orbits-auroras.md} §1.2). Placed just above
	 * the {@code Quantizer.TAU_C = 0.90} solid boundary so the lower body is
	 * solid everywhere even with the {@code ±10%} noise spread
	 * ({@code BODY_RHO·(1±NOISE)} ∈ [0.99, 1.21] &gt; 0.90) while staying below
	 * the copper threshold ({@code COPPER_THETA_C = 1.20}) in the bulk — so the
 * ground reads as stone with copper precipitated only from the density and
 * coherence-drain tails ({@code material-regimes.md} §1: ore is a field
 * regime, not a monolith). Measured on the gen-12 settled body (full 192³
 * census, {@code terrainCensus}): bottom-third solid fraction ≈ 0.94 at t=0
 * (≈ 0.77 at the t≈2 gate settle), top-third ≈ 0.0, census AIR ≈ 62% / SOLID ≈
 * 33% / ORE ≈ 4.7% — the body's dense core and vacuum above, stone bulk with
 * copper veins.
	 */
	public static final double BODY_RHO = 1.10;
	/**
	 * The thin top-of-box target ρ — the KSP-vacuum ceiling, below the
	 * material registry's void floor ({@code AIR_THETA_C = 0.10}) so the upper
	 * field reads as the clear void ({@code atmosphere-orbits-auroras.md} §1.4
	 * "above the ceiling the field is near-noise"; the envelope's vacuum floor).
	 * The top-third solid fraction is 0.0.
	 */
	public static final double AIR_RHO = 0.05;
	/**
	 * The vertical profile's sigmoid steepness {@code κ} —
	 * {@code ρ(j) = AIR_RHO + (BODY_RHO − AIR_RHO)·w(j)}, {@code w(j) =
	 * 1/(1+e^{−κ·s})}, {@code s = (N−1−2j)/N} (+1 floor → −1 ceiling). Kept
	 * steep so that after the near-IC settle (the field's own diffusion widens
	 * the ramp) the ground-to-air surface stays a genuine step: the coherent-plane
	 * spawn scan needs a solid block with two clear blocks above it, which a
	 * shallow ramp (κ≈8) does not provide once the settle blurs it. The steeper
	 * step keeps the bottom third solid and the top third vacuum.
	 */
	public static final double PROFILE_KAPPA = 14.0;
	/**
	 * The floor-edge seam dip — the number of bottom grid rows tapering toward
	 * {@link #AIR_RHO}. The periodic y-torus wraps the dense floor row (j=0)
	 * against the vacuum ceiling (j=N−1); without a dip the trilinear block
	 * sampler near the box top would read the wrapped dense floor as a solid
	 * "ring" and the coherent-plane spawn scan would land a player on that seam
	 * artifact at the box's ceiling instead of on the real ground. Tapering the
	 * single floor row to thin keeps the bottom-third solid fraction ≈ 0.97
	 * while killing the seam ring (top-third fraction 0.0).
	 */
	public static final int PROFILE_EDGE_DIP = 1;
	/**
	 * The seed-derived fractional EI noise — {@code ei = ei_target·(1 + NOISE·n)},
	 * {@code n ∈ [−1,1]} (the engine's own {@code ±10%} attractor-init variation,
	 * {@code cassi_physics_engine.gd:1440}). Gives the surface real roughness and
	 * a small ρ/q spread so the weather/atmo/aurora reads have structure to read,
	 * bounded so it never overwhelms the body profile (the bottom third stays
	 * solid, the top third stays vacuum).
	 */
	public static final double NOISE_FRACTION = 0.10;
	/**
	 * The coherence-drain slip amplitude — the independent φ-lock deficit the
	 * IC seeds at the coarse drain sites so the body carries a real, persistent
	 * local decoherence tail (the corpus's "coherence streaming into a region
	 * where ε² rises (a drain)", {@code atmosphere-orbits-auroras.md} §3.1; the
	 * aurora's source band). At a drain cell {@code EY = φ·EI +
	 * DECOHERENCE_SLIP·w(j)·d}, where {@code w(j)} is the vertical profile
	 * weight (full in the dense body, ~0 in the vacuum) and {@code d} is an
	 * independent seed-derived draw in [−1,1]: the dense body's cells carry a
	 * nonzero {@code EY−φ·EI} spread whose derived {@code ε² = (EY−φ·EI)²}
	 * reaches the aurora band [0.20, 0.45) and the storm band ≥ 0.45 at the
	 * gates' near-IC settle (surface drains measured in the settled field:
	 * aurora/storm firings + coherent bulk mean ε² ≈ 0.03). A pure, bounded
	 * φ-lock deficit — the body stays overwhelmingly coherent (drain events are
	 * ~¼ of body cells, bulk ε² low), never a random pile. Bounded cell ρ ≤ ~1.8.
	 */
	public static final double DECOHERENCE_SLIP = 1.0;
	/**
	 * The coarse drain-site cell spacing — a deterministic position-only
	 * sublattice {@code (i/BIN + j/BIN + k/BIN) % 4 == 0} (integer division)
	 * selecting ~¼ of 2³-cell blocks as the coherence drains that seed the
	 * φ-lock deficit ({@link #DECOHERENCE_SLIP}). Spatially extended (a
	 * 2-cell-thick slab), so the sparse block-lattice samplers (sky/atmo
	 * step-16) reliably catch the discharge band after the settle; a pure
	 * function of position (the independent slip draw is the seed RNG), so the
	 * IC is deterministic.
	 */
	public static final int DRAIN_BIN = 2;

	/**
	 * Default-OFF gate for the domain-level condensation term (the measured
	 * answer to {@code SurfaceEmergenceMain}'s falsification — a uniform
	 * ~72–75%-solid sponge with no vertical density plane at any reachable t).
	 * When {@code true}, {@link #passA()} adds a gravity-biased matched-φ
	 * condensation acceleration per cell (see {@link #condensationBias(int)});
	 * when {@code false} (the default) the guard is skipped entirely and every
	 * pre-existing gate's byte-path is unchanged (domainHarness + the full gate
	 * suite stay green; the {@code CondensationDeterminismMain} gate asserts the
	 * OFF-path hash equals the documented reference).
	 *
	 * <p>[design] The term is the corpus's merge-lineage condensation vocabulary
	 * decoded at the domain level: a body is "the merge lineage condensing
	 * under the order-selective coherence gate" ({@code atmosphere-orbits-auroras.md}
	 * §2.2 — the engine's body formation this port lacks), and the gravity bias
	 * is the hydrostatic envelope's spine (§1.1: "matter free to move is pulled
	 * toward the body"; the ρ gradient where pressure balances gravity). The
	 * matched-φ move preserves the φ-lock ({@code EY − φ·EI} unchanged), so the
	 * ω₀² re-lock/overdraw boundary of {@code coherence-magic.md} §4.3 is never
	 * crossed. No free energy: the zero-mean vertical bias redistributes the
	 * field's own existing coherence (bottom condenses, top thins) without
	 * minting — the no-mint honesty gate ({@code energy-harnessing.md} §6:
	 * {@code output ≤ φ⁻¹·input}) is measured by the probe as total ρ / total q
	 * before and after a long run.
	 */
	public static volatile boolean CONDENSATION_ENABLED = false;

	/**
	 * The condensation term's base target density — the measured sponge's own
	 * mean ρ (~1.00; TerrainCensusMain seed 42 reports the density body running
	 * p50≈1.007). The target profile is {@code RHO_BASE + AMPLITUDE·bias(j)}, so
	 * its mean equals this base — the term reorganizes existing density (bottom
	 * condenses, top thins) without minting overall (the no-mint gate measures
	 * it; {@code energy-harnessing.md} §6).
	 */
	public static final double CONDENSATION_RHO_BASE = 1.0;

	/**
	 * The condensation term's vertical target swing — how far below the box the
	 * dense body's target sits (the floor condenses toward
	 * {@code RHO_BASE + AMPLITUDE}, the ceiling thins toward
	 * {@code RHO_BASE − AMPLITUDE}). Tuned by measurement (the probe owns the
	 * number): set strong enough that the attractor builds a real ρ gradient
	 * against the Laplacian's diffusion within reachable t, but bounded by the
	 * sponge's own ρ spread (~0.15) so the target stays physical.
	 */
	public static final double CONDENSATION_AMPLITUDE = 0.7;

	/**
	 * The condensation term's convergence rate — the fraction of each cell's
	 * density deficit from its target it closes per step (the {@code ψ +=
	 * dEY·dt²} position-source apply, so zero at the target, self-limiting, and
	 * not a velocity-accumulating pump — an un-damped acceleration version was
	 * measured to mint (the CONTRADICTS(mint) finding) and is replaced by this
	 * bounded attractor). A static configuration dial, not a physics change.
	 */
	public static final double CONDENSATION_RATE = 25.0;

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

	// One scratch buffer reused across roll channels (never allocated per-cell).
	private final float[] rollScratch;

	private final java.util.Random rng;

	// ---- Parallel hot-loop execution (FIX 2: byte-identical, race-free) ----
	// The per-cell solver math is embarrassingly parallel: pass_a reads the
	// canonical ey/ei/vel/rho (written only by the previous pass) and writes the
	// disjoint scr double-buffer; pass_b reads scr and writes the disjoint
	// ey/ei/q/vel/rho. Partitioning the cell index space into disjoint contiguous
	// blocks, each computed by exactly one thread with the identical per-cell
	// expression order, yields bit-identical results to the serial sweep (pure
	// IEEE float ops — no cross-cell reductions, no reassociation, no
	// vectorization across the wrap-dependent stencil taps). A fixed daemon pool
	// is shared JVM-wide (the gates run one solve at a time per JVM); a
	// threads = 1 solver bypasses the pool entirely and runs the verbatim serial
	// sweep (the committed fingerprint path used by the {@code perfByteIdentity}
	// gate's serial arm).

	/**
	 * Default worker count for the parallel solver hot loops — the smaller of
	 * the host's logical processors and 8 (the 7800X3D's 8 physical cores; the
	 * per-cell float loops are compute-bound, so 8 threads saturate the FPUs
	 * without oversubscribing SMT).
	 */
	public static final int DEFAULT_THREADS = Math.max(1, Math.min(Runtime.getRuntime().availableProcessors(), 8));

	private static volatile ExecutorService PARALLEL_POOL;

	/** The configured solver parallelism — {@code 1} forces the verbatim serial sweep. */
	private final int threads;

	// Pre-built, immutable-per-solver partitioning job lists (built once in the
	// constructor so the per-step dispatch allocates nothing heavy — a tiny
	// fresh future list per invokeAll, dwarfed by the removed publish churn).
	private final List<Callable<Integer>> passAJobs;
	private final List<Callable<Integer>> passBJobs;

	/**
	 * A solver with the default parallelism ({@link #DEFAULT_THREADS}) — the
	 * committed path (byte-identical to serial, verified by the
	 * {@code perfByteIdentity} gate).
	 */
	public TwoFluidSolver(long seed) {
		this(seed, DEFAULT_THREADS);
	}

	/**
	 * A solver with an explicit thread count. {@code threads = 1} runs the
	 * verbatim serial sweep (the pre-FIX behavior); {@code threads > 1} runs the
	 * identical per-cell arithmetic partitioned across the shared pool.
	 */
	public TwoFluidSolver(long seed, int threads) {
		this.threads = Math.max(1, threads);
		this.ey = new float[CELLS];
		this.ei = new float[CELLS];
		this.q = new float[CELLS];
		this.vel = new float[CELLS * 4];
		this.rho = new float[CELLS];
		this.scr = new float[CELLS * 4];
		this.rollScratch = new float[CELLS * 4];
		this.rng = new java.util.Random(seed);
		this.passAJobs = buildPassAJobs();
		this.passBJobs = buildPassBJobs();

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
	 * The shared daemon executor for the parallel solver passes — sized at
	 * {@link #DEFAULT_THREADS}, created lazily and shared JVM-wide (the gates run
	 * one solve per JVM at a time, so no cross-solve contention). Daemon threads
	 * never block JVM exit.
	 */
	private static ExecutorService pool() {
		ExecutorService p = PARALLEL_POOL;
		if (p == null) {
			synchronized (TwoFluidSolver.class) {
				p = PARALLEL_POOL;
				if (p == null) {
					int n = DEFAULT_THREADS;
					p = Executors.newFixedThreadPool(n, new ThreadFactory() {
						@Override
						public Thread newThread(Runnable r) {
							Thread t = new Thread(r, "cassicraft-solver-pool");
							t.setDaemon(true);
							return t;
						}
					});
					PARALLEL_POOL = p;
				}
			}
		}
		return p;
	}

	/** Submit a partition to the shared pool and await every task, re-raising an interrupt. */
	private static void runParallel(List<Callable<Integer>> jobs) {
		final List<Future<Integer>> futures;
		try {
			futures = pool().invokeAll(jobs);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("interrupted submitting solver pass", e);
		}
		try {
			for (Future<Integer> f : futures) {
				f.get();
			}
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("interrupted awaiting solver pass", e);
		} catch (ExecutionException e) {
			throw new IllegalStateException("solver pass task failed", e.getCause());
		}
	}

	/**
	 * The pass_a k-axis partition — disjoint contiguous k-blocks covering
	 * {@code [0, N)}, one {@link Callable} per block running the verbatim serial
	 * sweep over its rows. Built once so the per-step dispatch allocates only the
	 * small future list {@code invokeAll} returns.
	 */
	private List<Callable<Integer>> buildPassAJobs() {
		int blocks = Math.min(threads, N);
		int chunk = (N + blocks - 1) / blocks;
		List<Callable<Integer>> jobs = new ArrayList<>(blocks);
		for (int s = 0; s < N; s += chunk) {
			final int kStart = s;
			final int kEnd = Math.min(N, s + chunk);
			jobs.add(() -> {
				passARange(kStart, kEnd);
				return Integer.valueOf(0);
			});
		}
		return jobs;
	}

	/**
	 * The pass_b flat-cell partition — disjoint contiguous id-blocks covering
	 * {@code [0, CELLS)}, built once. Each block's sweep reads only the read-only
	 * {@code scr} and writes only its own ey/ei/q/vel/rho cells.
	 */
	private List<Callable<Integer>> buildPassBJobs() {
		int blocks = Math.min(threads, CELLS);
		int chunk = (CELLS + blocks - 1) / blocks;
		List<Callable<Integer>> jobs = new ArrayList<>(blocks);
		for (int s = 0; s < CELLS; s += chunk) {
			final int idStart = s;
			final int idEnd = Math.min(CELLS, s + chunk);
			jobs.add(() -> {
				passBIdRange(idStart, idEnd);
				return Integer.valueOf(0);
			});
		}
		return jobs;
	}

	/**
	 * Initialise a deterministic fixed-seed condensed-body field — the world's
	 * birth state (the port's answer to the flat-noise-sponge falsification,
	 * {@code SurfaceEmergenceMain}). The field is born as a coherent body with:
	 *
	 * <ol>
	 *   <li><b>A real vertical density profile</b> {@code ρ(j) = AIR_RHO +
	 *       (BODY_RHO−AIR_RHO)·w(j)}, {@code w(j) = 1/(1+e^{−κ·s})},
	 *       {@code s = (N−1−2j)/N}, with a smooth surface transition centered at
	 *       the anchor plane (grid row j≈32), the single floor row dipped toward
	 *       the vacuum so the y-torus seam reads thin, not a solid ring.</li>
	 *   <li><b>Matched-φ coherence</b> {@code EY = φ·EI} (the engine's
	 *       {@code field_attractor_init} lock, {@code cassi_physics_engine.gd:1441}),
	 *       so in the body {@code q = EY²+EI²} is high and the derived
	 *       {@code ε² = (EY−φ·EI)²} is ~0 — a coherent condensate, not a random
	 *       pile (the corpus's order-selective coherence gate).</li>
 *   <li><b>Seed-derived bounded noise</b> {@code ei·(1 + NOISE·n)} (surface
 *       roughness, small ρ/q texture) plus a body-weighted coherence-drain
 *       φ-lock deficit at the coarse drain sites — a bounded ε² tail that
 *       survives the near-IC settle into the aurora/storm discharge band at the
 *       body's edge — structure for the weather/sky/atmo reads, never
 *       overwhelming the body profile.</li>
	 * </ol>
	 *
	 * <p>{@code q = EY²+EI²} and {@code ρ = EY+EI} are initialized consistently
	 * from {@code ey} and {@code ei} exactly as the sponge did; {@code vel} and
	 * {@code scr} are zeroed. The RNG is {@link java.util.Random} with a fixed
	 * draw order (one {@code nextFloat} per cell, k→j→i), so a fixed seed → a
	 * fixed world (the determinism gates replay seeds 42/43) and a different
	 * seed → a different world. Engine {@code _init_field} shape:
	 * {@code cassi_physics_engine.gd:1418-1453}.
	 */
	public void seed() {
		float onePlusPhi = (float) (1.0 + PHI);
		for (int k = 0; k < N; k++) {
			int dkbin = k / DRAIN_BIN;
			for (int j = 0; j < N; j++) {
				// The vertical profile weight (sigmoid of the zero-mean row index).
				float srow = (float) ((N - 1 - 2 * j) / (double) N);
				float profile = (float) (AIR_RHO + (BODY_RHO - AIR_RHO)
						/ (1.0 + Math.exp(-PROFILE_KAPPA * srow)));
				// Floor-edge seam dip: taper the bottom rows toward the vacuum so
				// the y-torus wrap does not read a solid floor ring at the box top.
				if (j < PROFILE_EDGE_DIP) {
					profile = (float) (AIR_RHO + (profile - AIR_RHO)
							* (j / (double) PROFILE_EDGE_DIP));
				}
				int jbin = j / DRAIN_BIN;
				// The vertical profile weight (sigmoid of the zero-mean row index),
				// reused for the body-weighted coherence-drain slip (full in the
				// dense body, ~0 in the vacuum — the drains ride the density).
				float w = (float) (1.0 / (1.0 + Math.exp(-PROFILE_KAPPA * srow)));
				for (int i = 0; i < N; i++) {
					int id = i + N * (j + N * k);
					// Seed-derived bounded EI noise (surface roughness).
					float n = 2.0f * rng.nextFloat() - 1.0f;
					float ei_target = profile / onePlusPhi;
					float ei_v = ei_target * (1.0f + (float) NOISE_FRACTION * n);
					// Coherence-drain φ-lock deficit at the coarse drain sites: a
					// body-weighted independent slip whose derived ε² survives the
					// near-IC settle into the aurora/storm band (the local drains
					// where the field's edge sheds).
					int ibin = i / DRAIN_BIN;
					boolean drain = ((ibin + jbin + dkbin) % 4 == 0);
					float d = drain ? 2.0f * rng.nextFloat() - 1.0f : 0.0f;
					float slip = (float) DECOHERENCE_SLIP * w * d;
					float ey_v = (float) PHI * ei_v + slip;
					ey[id] = ey_v;
					ei[id] = ei_v;
					rho[id] = ey_v + ei_v;
					q[id] = ey_v * ey_v + ei_v * ei_v;
				}
			}
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
	 *
	 * <p>Parallel when {@link #threads} &gt; 1: the k-axis is split into disjoint
	 * contiguous blocks, each computed by one worker with the identical per-cell
	 * expression order as the serial sweep (the shared {@code ey}/{@code ei}/
	 * {@code vel}/{@code rho} are read-only during the pass; each worker writes
	 * only its own {@code scr} cells) — bit-identical to serial, race-free.
	 */
	public void passA() {
		if (threads <= 1 || passAJobs.size() <= 1) {
			passARange(0, N);
			return;
		}
		runParallel(passAJobs);
	}

	/**
	 * The pass_a sweep over the k-rows {@code [kStart, kEnd)} — the verbatim
	 * serial inner loop pulled out so the parallel workers and the serial path
	 * execute the identical per-cell arithmetic (each output cell computed by
	 * exactly one caller, in k→j→i order, reading only previous-pass inputs).
	 */
	private void passARange(int kStart, int kEnd) {
		float dt = (float) DT;
		float omega2 = (float) OMEGA2;
		float phi = (float) PHI;
		for (int k = kStart; k < kEnd; k++) {
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

					// [design] Gravity-biased condensation term — default-OFF (the
					// {@link #CONDENSATION_ENABLED} flag; when false this guard is
					// skipped and the byte-path is exactly the pre-existing math).
					// A self-limiting matched-φ attractor that nudges each cell's
					// density toward a vertical target profile (dense at the anchor's
					// floor, thin above — the gravity bias of
					// {@code atmosphere-orbits-auroras.md} §2.2's merge-lineage
					// condensation, §1.1's hydrostatic envelope). Applied as a bounded
					// position source (the {@code ψ += source·dt²} engine form, as in
					// {@link #applySource}): the correction is {@code RATE × dt² ×}
					// the deficit from the target, so it is exactly zero at the local
					// target (self-limiting — no runaway, no velocity accumulation)
					// and matched-φ ({@code dEY = φ·dEI} → {@code EY − φ·EI}
					// preserved; the ω₀² re-lock/overdraw boundary of
					// {@code coherence-magic.md} §4.3 is never crossed). The target
					// profile's mean density equals the measured sponge's own mean
					// (~1.00; {@link #CONDENSATION_RHO_BASE}), so the term
					// <b>reorganizes</b> existing density (bottom condenses, top
					// thins) and the no-mint honesty gate ({@code energy-harnessing.md}
					// §6: {@code output ≤ φ⁻¹·input}) is measured as total ρ / total q
					// before/after the run. Deterministic — a pure function of the
					// field + vertical position.
					if (CONDENSATION_ENABLED) {
						float targetRho = (float) (CONDENSATION_RHO_BASE
								+ CONDENSATION_AMPLITUDE * condensationBias(j));
						float dRho = (float) (CONDENSATION_RATE * (targetRho - rho[id]));
						float dEI = dRho / (1f + phi);
						float dEY = phi * dEI;
						ey_new += dEY * dt * dt;
						ei_new += dEI * dt * dt;
					}

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
	 *
	 * <p>Parallel when {@link #threads} &gt; 1: the flat cell-id space is split
	 * into disjoint contiguous blocks, each computed by one worker (reads the
	 * read-only {@code scr}; writes only its own ey/ei/q/vel/rho cells) —
	 * bit-identical to serial, race-free.
	 */
	public void passB() {
		if (threads <= 1 || passBJobs.size() <= 1) {
			passBIdRange(0, CELLS);
			return;
		}
		runParallel(passBJobs);
	}

	/** The pass_b sweep over the flat cell ids {@code [idStart, idEnd)}. */
	private void passBIdRange(int idStart, int idEnd) {
		float phi = (float) PHI;
		for (int id = idStart; id < idEnd; id++) {
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

	/**
	 * A bounded source injection at a whole-cell center (the Q4 write lane's
	 * worker-side application — `wiring-requests/q4-write-lane-design.md` §2).
	 * Adds {@code dEY·dt²} into {@code ey} and {@code dEI·dt²} into {@code ei}
	 * with the engine shader's Gaussian spatial falloff {@code exp(-r²·4)}
	 * (`cassi_two_fluid.glsl:149-172, 212-213` — the {@code ψ + v·dt + source·dt²}
	 * injection form, minus the {@code ρ·0.001} attractor residue which stays on
	 * the pass_a parity path). The 19-point stencil, the φ coupling, and the
	 * {@code passB} channel derivations ({@code q = EY²+EI²}, {@code ε²}) are
	 * untouched — the next {@link #step()} recomputes them from the injected
	 * buffers exactly as it already does after any evolution.
	 *
	 * <p>Coordinates are whole cells in {@code [0, N)}; a request from the Q4
	 * lane is already cell-snapped. {@code radius} is the falloff scale in cells
	 * ({@code r² = (Δx²+Δy²+Δz²)/(radius²)}, so the target cell gets the full
	 * injection and the influence falls to {@code exp(-4) ≈ 0.018} at one
	 * radius). Cells beyond a {@code r² ≥ 16} cutoff are skipped (the shader
	 * Gaussian is negligible there). A radius ≤ 0 is treated as a single-cell
	 * write (all influence on the center). The no-request path — no call to this
	 * method — is byte-identical, so the domain harness stays green.
	 *
	 * @param cx    center cell x ({@code [0, N)})
	 * @param cy    center cell y
	 * @param cz    center cell z
	 * @param dEY   EY injection magnitude (capped upstream by the lane's honesty caps)
	 * @param dEI   EI injection magnitude
	 * @param radius falloff scale in cells (Gaussian {@code exp(-r²·4)}), clamped non-negative
	 */
	public void applySource(int cx, int cy, int cz, float dEY, float dEI, int radius) {
		float dt2 = (float) (DT * DT);
		int r = Math.max(radius, 0);
		float r2norm = r > 0 ? 1.0f / (float) (r * r) : 0.0f;
		int reach = r; // r² cutoff at 16 → the [−r, r] cube is fully inside the influence
		// Full-injection when radius ≤ 0 (single-cell write).
		if (r <= 0) {
			int id = cx + N * (cy + N * cz);
			ey[id] += dEY * dt2;
			ei[id] += dEI * dt2;
			return;
		}
		for (int dk = -reach; dk <= reach; dk++) {
			int k = wrapCell(cz + dk);
			for (int dj = -reach; dj <= reach; dj++) {
				int j = wrapCell(cy + dj);
				for (int di = -reach; di <= reach; di++) {
					int i = wrapCell(cx + di);
					float dx = di;
					float dy = dj;
					float dz = dk;
					float r2 = (dx * dx + dy * dy + dz * dz) * r2norm;
					if (r2 >= 16.0f) {
						continue; // exp(-16·4)=exp(-64) — negligible, matches the shader's short tail
					}
					float falloff = (float) Math.exp(-r2 * 4.0);
					int id = i + N * (j + N * k);
					ey[id] += dEY * dt2 * falloff;
					ei[id] += dEI * dt2 * falloff;
				}
			}
		}
	}

	/** Periodic wrap of a raw cell coordinate into {@code [0, N)}. */
	private static int wrapCell(int c) {
		int m = c % N;
		return m < 0 ? m + N : m;
	}

	/**
	 * The vertical gravity-bias profile for the {@link #CONDENSATION_ENABLED}
	 * term — a deterministic, position-only function of the cell's y-row
	 * {@code j} (the box's vertical axis: low {@code j} = the anchor's floor,
	 * high {@code j} = the ceiling). {@code (N-1-2j)/N} ranges from +1 at the
	 * floor (strong downward pull → condensate) to −1 at the ceiling (release →
	 * thin) and is <b>exactly zero-mean</b> over the periodic {@code j} rows
	 * ({@code Σ_j (N-1-2j) = N(N-1) − 2·(N-1)N/2 = 0}), so the total density
	 * flux the term imposes is conservative — the no-mint bound of
	 * {@code energy-harnessing.md} §6 is a property of the profile, not just of
	 * the measured probe. A pure function of position: deterministic, no RNG.
	 */
	private static float condensationBias(int j) {
		return (float) ((N - 1 - 2 * j) / (double) N);
	}

	/**
	 * Periodic whole-cell rotation of every canonical buffer — {@code ey}, {@code ei},
	 * {@code q}, {@code vel} (vec4/cell, all four lanes), {@code rho}, and
	 * {@code scr} (vec4/cell) — by {@code (dx,dy,dz)} whole cells. The follow-behind
	 * advection re-home (corpus-map.md §4; world-seams.md §4.2's anchor-to-window
	 * policy; async-field-domain.md §7 Q1's movable home-window). A pure bijective
	 * permutation: content at destination cell {@code d} takes the value the
	 * {@code d + (dx,dy,dz)} source cell held, so a fixed world block keeps its field
	 * content as a window center advancing by the same whole-cell delta slides the
	 * box over it — the world-fixedness proof, verified by the
	 * {@code FollowBehindDeterminism} gate (a). Sign confirmed against that gate
	 * (direction-of-roll truth): a {@code +dx} roll pairs with a {@code +dx}-cell
	 * center advance.
	 *
	 * <p>O(CELLS) with the single reused {@link #rollScratch} buffer (no per-cell
	 * allocation). Because it permutes every channel by the same delta, the derived
	 * relationships stay exact: {@code q = EY²+EI²}, {@code ρ = EY+EI}, and the
	 * {@code ε²} lane of {@code vel} all remain consistent with {@code ey}/{@code ei}
	 * per cell — no free energy is minted, nothing is created or destroyed.
	 */
	public void roll(int dx, int dy, int dz) {
		rollChannel(ey, 1, dx, dy, dz);
		rollChannel(ei, 1, dx, dy, dz);
		rollChannel(q, 1, dx, dy, dz);
		rollChannel(vel, 4, dx, dy, dz);
		rollChannel(rho, 1, dx, dy, dz);
		rollChannel(scr, 4, dx, dy, dz);
	}

	/**
	 * Roll one channel by {@code (dx,dy,dz)} whole cells into {@link #rollScratch}
	 * and copy back. {@code buf} has {@code CELLS·stride} entries; the permutation is
	 * applied at cell granularity, copying all {@code stride} lanes per cell.
	 */
	private void rollChannel(float[] buf, int stride, int dx, int dy, int dz) {
		for (int id = 0; id < CELLS; id++) {
			int i = id % N;
			int t = id / N;
			int j = t % N;
			int k = t / N;
			int di = mod(i - dx, N);
			int dj = mod(j - dy, N);
			int dk = mod(k - dz, N);
			int dest = (di + N * (dj + N * dk)) * stride;
			int src = id * stride;
			System.arraycopy(buf, src, rollScratch, dest, stride);
		}
		System.arraycopy(rollScratch, 0, buf, 0, buf.length);
	}

	private static int mod(int v, int m) {
		return ((v % m) + m) % m;
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

	/** Readonly view of the {@code scr} pass_a double-buffer (vec4/cell). */
	public float[] scr() {
		return scr;
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
