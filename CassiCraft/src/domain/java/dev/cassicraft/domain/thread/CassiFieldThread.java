package dev.cassicraft.domain.thread;

import dev.cassicraft.domain.engine.EngineJob;
import dev.cassicraft.domain.engine.GradientPass;
import dev.cassicraft.domain.engine.SpectralPoisson;
import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The worker thread that owns the solver (BUILD-PLAN.md §3.3). Ported from the
 * engine's threading header: a compute device/solver is created on the thread
 * that uses it; kernel/resources are loaded on the <b>main</b> thread via
 * {@link KernelLoader} and handed in ready. The worker never opens sources itself.
 *
 * <p>Lifecycle is explicit — {@link #start(Cfg)} spawns the worker once at world
 * load, {@link #close()} joins it. <b>Never a finalizer / GC hook.</b> The worker
 * drains a bounded run of steps per job ({@code JOB_STEP_CAP}) and publishes on a
 * cadence ({@code snapshot_cadence}).
 */
public final class CassiFieldThread {

	/** Engine defaults (BUILD-PLAN.md §3.3): coalesced backlog drains in bounded slices. */
	public static final int JOB_STEP_CAP = 64;
	public static final int SNAPSHOT_CADENCE = 2;

	/**
	 * World width of one whole grid cell — {@code 2·EXTENT/N} = 3 m (PORT-SPEC §5).
	 * The re-home quantizes a center displacement to this cell grid.
	 */
	public static final double CELL_WORLD_WIDTH = 2.0 * TwoFluidSolver.EXTENT / TwoFluidSolver.N;

	/**
	 * The Q4 no-mint cap — a perturbation may inject at most {@code φ⁻¹} × the
	 * target cell's settled coherence content (its field amplitude
	 * {@code sqrt(q)} ), the corpus's no-free-energy rule
	 * ({@code energy-harnessing.md} §6: {@code output ≤ φ⁻¹·input}, coded here as
	 * the write-lane's amplitude cap). A request beyond it is clamped to the cap,
	 * never silently minted.
	 */
	public static final double PERTURB_NO_MINT_PHI_INV = 1.0 / TwoFluidSolver.PHI;

	/**
	 * The Q4 overdraw bound — the ω₀² re-lock limit (`coherence-magic.md` §4.3;
	 * `wiring-requests/q4-write-lane-design.md` §1, cap 3). The restoring
	 * acceleration at a decoherence displacement {@code ε = EY − φ·EI} is
	 * {@code ω₀²·ε}; over one step it can reverse displacement {@code ω₀²·ε·dt²}.
	 * The injection adds displacement {@code (dEY − φ·dEI)·dt²} out of the
	 * φ-lock, so the lane clamps the disordering component to the re-lock
	 * ceiling the ω₀² term can counter: {@code |dEY − φ·dEI| ≤ ω₀²·|ε_local|}.
	 * A perfect φ-lock ({@code ε ≈ 0}) therefore has no room to be perturbed
	 * inward without tipping overdraw (an explosion stays an explicit future
	 * mode). A coherence-*restoring* write ({@code dEY ≈ φ·dEI}) is untouched —
	 * it has no disordering component.
	 */
	public static final double PERTURB_OVERDRAW_OMEGA2 = TwoFluidSolver.OMEGA2;

	/** Startup configuration — kernels are pre-loaded on the main thread. */
	public record Cfg(
			long seed,
			int stepsPerJob,
			int snapshotCadence,
			KernelLoader.KernelContext kernels,
			double[] windowCenter
	) {
		public Cfg {
			stepsPerJob = stepsPerJob <= 0 ? JOB_STEP_CAP : stepsPerJob;
			snapshotCadence = snapshotCadence <= 0 ? SNAPSHOT_CADENCE : snapshotCadence;
			windowCenter = windowCenter == null ? null : windowCenter.clone();
		}
	}

	private final SnapshotPublisher publisher;
	private final AtomicBoolean running = new AtomicBoolean(false);
	private Thread worker;
	private volatile TwoFluidSolver solver;
	private volatile int executed;

	// Worker-owned channel sources (created on the worker in runLoop) — the
	// solver, Poisson and gradient are all owned by the thread that uses them
	// (BUILD-PLAN.md §3.3, PORT-SPEC §6.2).
	private volatile SpectralPoisson poisson;
	private volatile GradientPass gradientPass;

	// The follow-behind re-home channel (async-field-domain.md §4.1/§7 Q1, §5.2 —
	// world-seams.md §4.2's anchor-to-window). The server submits a target center
	// here; the worker drains the pending request at job boundaries on its own
	// thread, so worker-owned buffers are only ever touched by the worker.
	// currentCenter is the live, mutable box center (the publish ships this, not
	// the fixed Cfg center).
	private final AtomicReference<double[]> pendingWindowCenter = new AtomicReference<>();
	private volatile double[] currentCenter;

	// The Q4 player-return channel (async-field-domain.md §7 Q4;
	// wiring-requests/q4-write-lane-design.md §1). A single newest-wins pending
	// coalescing slot — the rate limit (at most one drained perturbation per job).
	// The worker drains it at job boundaries on its own thread (drainPerturbation)
	// and applies the three honesty caps; the server never touches domain buffers.
	private final AtomicReference<Perturbation> pendingPerturbation = new AtomicReference<>();
	// The clamping counter — how many requests were clamped at drain by the
	// no-mint and/or overdraw caps (the gate asserts the caps engage).
	private final java.util.concurrent.atomic.AtomicLong perturbationClampCount =
			new java.util.concurrent.atomic.AtomicLong();

	/**
	 * A bounded player-return write request (the Q4 write-lane channel contract,
	 * `wiring-requests/q4-write-lane-design.md` §1). World-space target, EY/EI
	 * injection magnitudes, and the falloff scale in cells. Immutable by
	 * construction — a {@code perturb} submitter hands the store this value.
	 */
	public record Perturbation(
			double x, double y, double z,
			double dEY, double dEI,
			int radius
	) {}

	public CassiFieldThread(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Spawn the worker thread (once). Solver/Poisson/gradient are constructed on the worker. */
	public synchronized void start(Cfg cfg) {
		if (running.get()) {
			throw new IllegalStateException("CassiFieldThread already running");
		}
		running.set(true);
		worker = new Thread(() -> runLoop(cfg), "cassicraft-field-worker");
		worker.setDaemon(true);
		worker.start();
	}

	private void runLoop(Cfg cfg) {
		// Solver, Poisson and gradient owned by THIS thread (BUILD-PLAN.md §3.3 —
		// created on the user thread; PORT-SPEC §6.2 worker owns the channels).
		solver = new TwoFluidSolver(cfg.seed());
		solver.seed();
		poisson = new SpectralPoisson();
		gradientPass = new GradientPass();
		currentCenter = cfg.windowCenter() == null
				? new double[] { 0, 0, 0 }
				: cfg.windowCenter();
		int gen = 0;
		try {
			while (running.get()) {
				// Drain any pending re-home FIRST, before this job's steps, so the
				// publish that follows carries the moved center and the world-fixed
				// rolled field (async-field-domain.md §4.1 — the worker owns the touch).
				drainRehome(solver);
				// Drain any pending perturbation alongside it — the Q4 write-lane
				// worker-side application (wiring-requests/q4-write-lane-design.md
				// §2). A no-pending drain is a strict no-op, so the default
				// solver path stays byte-identical (domainHarness stays green).
				drainPerturbation(solver);
				int steps = Math.min(cfg.stepsPerJob(), Math.max(1, cfg.stepsPerJob()));
				for (int i = 0; i < steps; i++) {
					solver.step();
				}
				executed += steps;
				gen++;
				// Cadence publish: every Kth job carries a full snapshot.
				if (gen % cfg.snapshotCadence() == 1) {
					publishFull(cfg);
				}
				Thread.sleep(5);
			}
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
		}
	}

	/**
	 * The follow-behind re-home channel (async-field-domain.md §4.1, §5.2 — the
	 * movable home-window). Stored as a pending <em>target</em> (world coords,
	 * snapped to whole cells by the worker) and drained at the next job boundary
	 * on the worker thread; the server never touches domain buffers. Safe to call
	 * from any thread.
	 */
	public void rehome(double x, double y, double z) {
		pendingWindowCenter.set(new double[] { x, y, z });
	}

	/**
	 * The Q4 player-return channel (async-field-domain.md §7 Q4;
	 * `wiring-requests/q4-write-lane-design.md` §1). Submits a bounded source
	 * injection request; newest-wins coalescing (one honored per job — the rate
	 * cap), drained and capped on the worker thread at the next job boundary.
	 * Safe to call from any thread; the server never touches domain buffers. A
	 * {@code radius} ≤ 0 is treated as a single-cell write at drain.
	 */
	public void submitPerturbation(double x, double y, double z, double dEY, double dEI, int radius) {
		pendingPerturbation.set(new Perturbation(x, y, z, dEY, dEI, radius));
	}

	/** How many perturbations the worker has clamped (no-mint and/or overdraw) since start. */
	public long perturbationClampCount() {
		return perturbationClampCount.get();
	}

	/**
	 * Drain one pending re-home (worker thread): snap the target's displacement
	 * from the live center to whole cells ({@code CELL_WORLD_WIDTH} = 3 m), roll
	 * the solver by that delta if nonzero, and advance {@link #currentCenter} by
	 * the same whole-cell delta so the field stays world-fixed. A no-op with no
	 * pending request — the default solver path is untouched (domainHarness stays
	 * identical).
	 */
	private void drainRehome(TwoFluidSolver solver) {
		double[] target = pendingWindowCenter.getAndSet(null);
		if (target == null) {
			return;
		}
		double[] cur = currentCenter;
		double w = CELL_WORLD_WIDTH;
		int di = (int) Math.round((target[0] - cur[0]) / w);
		int dj = (int) Math.round((target[1] - cur[1]) / w);
		int dk = (int) Math.round((target[2] - cur[2]) / w);
		if (di == 0 && dj == 0 && dk == 0) {
			return;
		}
		solver.roll(di, dj, dk);
		currentCenter = new double[] {
				cur[0] + di * w,
				cur[1] + dj * w,
				cur[2] + dk * w,
		};
	}

	/**
	 * Drain one pending perturbation (worker thread): snap the target to whole
	 * cells, apply the three honesty caps, and hand the bounded injection to the
	 * solver's additive {@link TwoFluidSolver#applySource}. A no-pending drain is
	 * a strict no-op — the default solver path is untouched (domainHarness stays
	 * identical). The response is the field's own evolution on the next steps;
	 * the publish carries it, never the lane (the lane is input, the publish is
	 * output).
	 *
	 * <p><b>Cap (a) no-mint</b> — each of {@code dEY}, {@code dEI} is clamped to
	 * {@code φ⁻¹ × sqrt(max(q_local, 0))}, the target cell's settled coherence
	 * content ({@code energy-harnessing.md} §6). <b>Cap (c) overdraw</b> — the
	 * disordering component {@code dEY − φ·dEI} is clamped to the ω₀² re-lock
	 * ceiling {@code ω₀² × |ε_local|} (see {@link #PERTURB_OVERDRAW_OMEGA2}). An
	 * overdraw request is clamped, never silently discharged; the explicit blast
	 * stays a documented future mode. Any clamp increments
	 * {@link #perturbationClampCount()}.
	 */
	private void drainPerturbation(TwoFluidSolver solver) {
		Perturbation req = pendingPerturbation.getAndSet(null);
		if (req == null) {
			return;
		}
		double w = CELL_WORLD_WIDTH;
		double[] cur = currentCenter;
		// World → cell space: the box center is the origin of the N³ grid.
		int cx = (int) Math.floor((req.x() - cur[0]) / w) + TwoFluidSolver.N / 2;
		int cy = (int) Math.floor((req.y() - cur[1]) / w) + TwoFluidSolver.N / 2;
		int cz = (int) Math.floor((req.z() - cur[2]) / w) + TwoFluidSolver.N / 2;
		cx = ((cx % TwoFluidSolver.N) + TwoFluidSolver.N) % TwoFluidSolver.N;
		cy = ((cy % TwoFluidSolver.N) + TwoFluidSolver.N) % TwoFluidSolver.N;
		cz = ((cz % TwoFluidSolver.N) + TwoFluidSolver.N) % TwoFluidSolver.N;
		int id = cx + TwoFluidSolver.N * (cy + TwoFluidSolver.N * cz);

		double dEY = req.dEY();
		double dEI = req.dEI();

		// Cap (a) no-mint: clamp each magnitude to φ⁻¹ × the local coherence
		// content sqrt(q) at the target (energy-harnessing.md §6 — no mint).
		double amp = Math.sqrt(Math.max(solver.q()[id], 0.0));
		double mintCap = PERTURB_NO_MINT_PHI_INV * amp;
		double ney = clampMag(dEY, mintCap);
		double nei = clampMag(dEI, mintCap);
		if (ney != dEY || nei != dEI) {
			perturbationClampCount.incrementAndGet();
		}
		dEY = ney;
		dEI = nei;

		// Cap (c) overdraw: clamp the disordering component dEY − φ·dEI to the
		// ω₀² re-lock ceiling ω₀²·|ε_local| (coherence-magic.md §4.3). The
		// velocity buffer carries ε² = (EY − φ·EI)² in lane .w per cell.
		double eps2 = solver.vel()[id * 4 + 3];
		double orderDist = dEY - TwoFluidSolver.PHI * dEI;
		double lockCeiling = PERTURB_OVERDRAW_OMEGA2 * Math.sqrt(Math.max(eps2, 0.0));
		double orderMag = Math.abs(orderDist);
		if (orderMag > lockCeiling) {
			double scale = orderMag > 0 ? lockCeiling / orderMag : 0.0;
			dEY *= scale;
			dEI *= scale;
			perturbationClampCount.incrementAndGet();
		}

		solver.applySource(cx, cy, cz, (float) dEY, (float) dEI, req.radius());
	}

	/** Clamp {@code v} into {@code [-cap, cap]} preserving sign. */
	private static double clampMag(double v, double cap) {
		if (v > cap) {
			return cap;
		}
		return v < -cap ? -cap : v;
	}

	private void publishFull(Cfg cfg) {
		// Ship the LIVE box center, not the stale Cfg anchor — the sampler reads
		// the freshest center off each snapshot (async-field-domain.md §7 Q1).
		EngineJob job = new EngineJob(executed, executed, executed * TwoFluidSolver.DT, currentCenter);
		int authorityGen = publisher.allocateGeneration();
		// Wire the canonical ≈ 6 MiB field-only snapshot (PORT-SPEC §6.2,
		// chunk-field-quantization.md §2): q = EY²+EI², pot = Φ (the Poisson
		// solve over ρ = EY+EI), grad = ∇(g·Φ) vec3 trim, rho = EY+EI.
		float[] rho = solver.rho();
		float[] pot = new float[TwoFluidSolver.CELLS];
		poisson.solve(rho, pot);
		gradientPass.compute(pot, solver.ey(), solver.ei());
		FieldSnapshot snap = new FieldSnapshot(
				solver.q(), pot, gradientPass.grad(), rho,
				authorityGen, job
		);
		publisher.publish(snap);
	}

	/** Join the worker and release its solver/channels. Explicit, never a finalizer. */
	public synchronized void close() {
		running.set(false);
		if (worker != null) {
			try {
				worker.join(2000);
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
			}
			worker = null;
		}
		solver = null;
		poisson = null;
		gradientPass = null;
	}

	public int executed() {
		return executed;
	}

	/** The worker's live box center (world coords), as last rolled — a defensive copy. */
	public double[] currentCenter() {
		double[] c = currentCenter;
		return c == null ? null : c.clone();
	}

	public boolean isRunning() {
		return running.get();
	}
}
