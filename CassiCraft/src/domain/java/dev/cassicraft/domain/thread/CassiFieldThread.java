package dev.cassicraft.domain.thread;

import dev.cassicraft.domain.engine.EngineJob;
import dev.cassicraft.domain.engine.GradientPass;
import dev.cassicraft.domain.engine.SpectralPoisson;
import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;

import java.util.concurrent.atomic.AtomicBoolean;

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
		int gen = 0;
		try {
			while (running.get()) {
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

	private void publishFull(Cfg cfg) {
		EngineJob job = new EngineJob(executed, executed, executed * TwoFluidSolver.DT, cfg.windowCenter());
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

	public boolean isRunning() {
		return running.get();
	}
}
