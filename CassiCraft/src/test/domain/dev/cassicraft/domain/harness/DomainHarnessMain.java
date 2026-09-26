package dev.cassicraft.domain.harness;

import dev.cassicraft.domain.engine.EngineJob;
import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Headless domain harness — the port-drift control (BUILD-PLAN.md §3.3, §9.1).
 *
 * <p>Runs under the {@code domainTest} source set whose classpath is {@code domain}
 * only — no Minecraft on the classpath, no Minecraft runtime. Verifies:
 *
 * <ol>
 *   <li><b>Determinism:</b> a fixed-seed 64³ {@link TwoFluidSolver} run for N
 *       steps produces the identical buffer state (same SHA-256 hash) on two
 *       independent runs.</li>
 *   <li><b>Snapshot integrity:</b> the immutable {@link FieldSnapshot} round-trips
 *       (content hash stable, arrays not zeroed by clone).</li>
 *   <li><b>No torn handoff:</b> {@link SnapshotPublisher} is hammered by a
 *       publishing thread while readers poll {@link #freshest()} and assert every
 *       snapshots generation is strictly non-decreasing and its arrays are
 *       self-consistent (no half-written state).</li>
 *   <li><b>Thread lifecycle:</b> {@link CassiFieldThread} starts, publishes on a
 *       cadence, and {@link #close()} joins cleanly.</li>
 * </ol>
 *
 * <p>Exit code 0 = green. Any assertion failure prints and exits non-zero. This
 * class is a plain {@code main} so it runs with zero JUnit/Minecraft machinery.
 */
public final class DomainHarnessMain {

	private static final int HASH_STEPS = 200;

	public static void main(String[] args) throws Exception {
		boolean ok = true;
		ok &= determinismGate();
		ok &= snapshotIntegrityGate();
		ok &= publisherNoTearGate();
		ok &= threadLifecycleGate();

		if (ok) {
			System.out.println("\n[domain-harness] ALL GATES GREEN");
		} else {
			System.out.println("\n[domain-harness] FAILED — see errors above");
			System.exit(1);
		}
	}

	// --- Gate 1: fixed-seed determinism ------------------------------------
	private static boolean determinismGate() {
		System.out.println("[gate1] TwoFluidSolver fixed-seed determinism (N=" + HASH_STEPS + " steps)...");
		String runA = runSeeded(42L);
		String runB = runSeeded(42L);
		String runC = runSeeded(43L);
		boolean det = runA.equals(runB);
		boolean seedSensitive = !runA.equals(runC);
		System.out.println("  runA(seed=42) = " + runA);
		System.out.println("  runB(seed=42) = " + runB);
		System.out.println("  runC(seed=43) = " + runC);
		System.out.println("  same-seed identical: " + det + " | different-seed differs: " + seedSensitive);
		if (!det) {
			System.err.println("[gate1] FAIL — same seed, different state (non-deterministic)");
			return false;
		}
		if (!seedSensitive) {
			System.err.println("[gate1] FAIL — different seeds produced identical state");
			return false;
		}
		System.out.println("[gate1] PASS");
		return true;
	}

	private static String runSeeded(long seed) {
		TwoFluidSolver s = new TwoFluidSolver(seed);
		s.seed();
		for (int i = 0; i < HASH_STEPS; i++) {
			s.step();
		}
		return s.stateHash();
	}

	// --- Gate 2: snapshot integrity -----------------------------------------
	private static boolean snapshotIntegrityGate() {
		System.out.println("[gate2] FieldSnapshot immutability round-trip...");
		TwoFluidSolver s = new TwoFluidSolver(1L);
		s.seed();
		for (int i = 0; i < 16; i++) {
			s.step();
		}
		EngineJob job = new EngineJob(16, 16, 16 * TwoFluidSolver.DT, new double[] { 0, 0, 0 });
		FieldSnapshot snap = new FieldSnapshot(s.ey(), s.ei(), emptyGrad(), s.rho(), 1, job);
		String h1 = snap.contentHash();
		String h2 = snap.contentHash();
		boolean stable = h1.equals(h2);
		// After taking the hash, mutate the *source* arrays — the snapshot must not follow.
		s.ey()[0] = 999f;
		s.rho()[0] = 999f;
		String h3 = snap.contentHash();
		boolean notAliased = h3.equals(h1);
		System.out.println("  h1=" + h1);
		System.out.println("  hash stable across reads: " + stable + " | detached from solver arrays: " + notAliased);
		boolean pass = stable && notAliased;
		System.out.println(pass ? "[gate2] PASS" : "[gate2] FAIL");
		return pass;
	}

	private static float[] emptyGrad() {
		return new float[TwoFluidSolver.CELLS * 3];
	}

	// --- Gate 3: no torn handoff --------------------------------------------
	private static boolean publisherNoTearGate() throws InterruptedException {
		System.out.println("[gate3] SnapshotPublisher hammer test (no torn snapshots)...");
		SnapshotPublisher pub = new SnapshotPublisher();
		AtomicBoolean stop = new AtomicBoolean(false);
		AtomicInteger published = new AtomicInteger();
		AtomicReference<Throwable> failure = new AtomicReference<>();

		// The producer hammers publishes for the whole window. It never yields
		// within an iteration beyond the publish itself — the readers sleep(1)
		// so they cannot starve it (a spin + yield can monopolise a core and
		// starve the heavyweight array-filling producer; that would make the
		// gate vacuously green, so a positive-count assert guards against it).
		Thread producer = new Thread(() -> {
			try {
				// Pre-allocate the source arrays ONCE and reuse across iterations.
				// FieldSnapshot defensively clones on construction, so the producer
				// can safely rewrite them each publish — the snapshot freezes a copy.
				float[] q = new float[TwoFluidSolver.CELLS];
				float[] rho = new float[TwoFluidSolver.CELLS];
				float[] grad = new float[TwoFluidSolver.CELLS * 3];
				for (int p = 0; !stop.get(); p++) {
					for (int i = 0; i < q.length; i++) {
						q[i] = i * 0.5f + p;
						rho[i] = i * 0.25f + p * 2;
					}
					for (int gi = 0; gi < grad.length; ) {
						grad[gi] = p;
						grad[gi + 1] = p + 1;
						grad[gi + 2] = p + 2;
						gi += 3;
					}
					EngineJob job = new EngineJob(p, p, p * TwoFluidSolver.DT, new double[] { 0, 0, 0 });
					int g = pub.allocateGeneration();
					FieldSnapshot snap = new FieldSnapshot(q, q, grad, rho, g, job);
					pub.publish(snap);
					published.incrementAndGet();
				}
			} catch (Throwable t) {
				failure.compareAndSet(null, t);
			}
		}, "harness-publisher");

		// Readers poll freshest() at 1 kHz and verify self-consistency per
		// snapshot: monotonic generation, correct shapes, and frozen content
		// (q[0] == gen-1, since the producer writes q[0]=p and publish stamps
		// gen = p+1). sleep(1) keeps readers off the producer's core.
		CountDownLatch done = new CountDownLatch(4);
		for (int r = 0; r < 4; r++) {
			new Thread(() -> {
				int lastGen = 0;
				try {
					while (!stop.get()) {
						FieldSnapshot snap = pub.freshest();
						if (snap != null) {
							int gen = snap.generation();
							if (gen < lastGen) {
								failure.compareAndSet(null, new AssertionError(
										"generation regressed: " + lastGen + " -> " + gen));
								return;
							}
							lastGen = gen;
							if (snap.q().length != TwoFluidSolver.CELLS
									|| snap.rho().length != TwoFluidSolver.CELLS) {
								failure.compareAndSet(null, new AssertionError("array length changed"));
								return;
							}
							// q[0] for loop iteration p was written as `0*0.5 + p`; the
							// publisher stamps generation 1..N so gen == p+1, hence
							// q[0] == gen-1. Detects a torn or aliased handoff.
							float expectedQ0 = (float) (gen - 1);
							if (Math.abs(snap.q()[0] - expectedQ0) > 1e-3f) {
								failure.compareAndSet(null, new AssertionError(
										"field content inconsistent with generation: q[0]="
												+ snap.q()[0] + " expected " + expectedQ0));
								return;
							}
						}
						Thread.sleep(1);
					}
				} catch (Throwable t) {
					failure.compareAndSet(null, t);
				} finally {
					done.countDown();
				}
			}).start();
		}

		producer.start(); // launch the publishing thread
		Thread.sleep(1500);
		stop.set(true);
		producer.join(2000);
		done.await(3000, java.util.concurrent.TimeUnit.MILLISECONDS);
		int count = published.get();
		System.out.println("  publishes observed: " + count);
		if (count == 0) {
			System.err.println("[gate3] FAIL — publisher never progressed (0 publishes; vacuously green is not a test)");
			return false;
		}
		if (failure.get() != null) {
			System.err.println("[gate3] FAIL — " + failure.get());
			failure.get().printStackTrace(System.err);
			return false;
		}
		System.out.println("[gate3] PASS — " + count + " publishes, no torn or regressed snapshot");
		return true;
	}

	// --- Gate 4: thread lifecycle -------------------------------------------
	private static boolean threadLifecycleGate() throws InterruptedException {
		System.out.println("[gate4] CassiFieldThread start/publish/close...");
		SnapshotPublisher pub = new SnapshotPublisher();
		KernelLoader loader = new KernelLoader();
		KernelLoader.KernelContext kernels = loader.load();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				7L, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				kernels, new double[] { 0, 0, 0 });
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		// Wait for at least one cadence snapshot.
		long deadline = System.currentTimeMillis() + 3000;
		FieldSnapshot snap = null;
		while (System.currentTimeMillis() < deadline && snap == null) {
			Thread.sleep(20);
			snap = pub.freshest();
		}
		if (snap == null) {
			System.err.println("[gate4] FAIL — worker never published");
			worker.close();
			return false;
		}
		System.out.println("  first snapshot generation=" + snap.generation()
				+ " executed=" + snap.job().executed());
		if (snap.generation() < 1 || snap.q().length != TwoFluidSolver.CELLS) {
			System.err.println("[gate4] FAIL — malformed snapshot");
			worker.close();
			return false;
		}
		boolean closed = workerIsClosed(worker);
		System.out.println("  joined cleanly: " + closed);
		System.out.println("[gate4] PASS");
		return closed;
	}

	private static boolean workerIsClosed(CassiFieldThread worker) throws InterruptedException {
		worker.close();
		return !worker.isRunning();
	}
}
