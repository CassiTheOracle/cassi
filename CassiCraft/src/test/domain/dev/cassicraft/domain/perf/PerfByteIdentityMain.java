package dev.cassicraft.domain.perf;

import dev.cassicraft.domain.engine.TwoFluidSolver;

import java.nio.ByteBuffer;
import java.security.MessageDigest;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The permanent byte-identity gate for the parallel solver hot loops
 * (FIX 2): settles the same fixed-seed field once with {@code threads = 1} (the
 * verbatim serial sweep, the pre-FIX bottleneck) and once with the default
 * parallel path, then asserts the two full-buffer fingerprints are byte-identical.
 * Because every existing gate's pinned fingerprints derive from the identical
 * solve arithmetic, this gate is the standing proof that parallel execution
 * cannot drift the committed physics — a single moved float fails the gate.
 *
 * <p>Also prints a per-step timing report (serial vs parallel) so the running
 * improvement is visible on every build without a contended Gradle timing rig.
 *
 * <p>Exit code 0 = green; any fingerprint mismatch prints and exits non-zero.
 * A plain {@code main} — no JUnit/Minecraft machinery (the {@code domainTest}
 * classpath is {@code domain} only).
 */
public final class PerfByteIdentityMain {

	private static final long SEED = 42L;
	private static final int STEPS = 200;
	private static final int WARMUP = 64;

	public static void main(String[] args) throws Exception {
		boolean ok = true;

		String serial = settleFingerprint(SEED, STEPS, 1);
		String parallel = settleFingerprint(SEED, STEPS, TwoFluidSolver.DEFAULT_THREADS);
		boolean identical = serial.equals(parallel);
		ok &= identical;

		System.out.println("[perfByteIdentity] serial-42   = " + serial);
		System.out.println("[perfByteIdentity] parallel-42 = " + parallel);
		System.out.println("[perfByteIdentity] byte-identical=" + identical
				+ " (threads=" + TwoFluidSolver.DEFAULT_THREADS + ")");

		// Timing report (lock-free standalone loop in this JVM).
		double serialMs = timeStep(1);
		double parallelMs = timeStep(TwoFluidSolver.DEFAULT_THREADS);
		System.out.println(String.format("[perfByteIdentity] timing: serial %.4f ms/step, parallel %.4f ms/step%s",
				serialMs, parallelMs,
				parallelMs > 0 ? String.format(" (%.2fx)", serialMs / parallelMs) : ""));

		if (!ok) {
			System.err.println("[perfByteIdentity] FAIL — serial and parallel settle differ (byte-identity broken)");
			System.exit(1);
		}
		System.out.println("[perfByteIdentity] PASS");
	}

	/** Settle the fixed-seed field for {@code n} steps and hash every buffer. */
	private static String settleFingerprint(long seed, int n, int threads) throws Exception {
		TwoFluidSolver s = new TwoFluidSolver(seed, threads);
		s.seed();
		for (int i = 0; i < n; i++) {
			s.step();
		}
		MessageDigest md = MessageDigest.getInstance("SHA-256");
		for (float[] b : new float[][] { s.ey(), s.ei(), s.vel(), s.rho(), s.q(), s.scr() }) {
			ByteBuffer bb = ByteBuffer.allocate(b.length * 4);
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

	/** Wall-clock mean ms/step over a warm fixed-seed loop. */
	private static double timeStep(int threads) {
		TwoFluidSolver s = new TwoFluidSolver(SEED, threads);
		s.seed();
		for (int i = 0; i < WARMUP; i++) {
			s.step();
		}
		int n = 200;
		long t0 = System.nanoTime();
		for (int i = 0; i < n; i++) {
			s.step();
		}
		long t1 = System.nanoTime();
		return (t1 - t0) / 1e6 / n;
	}
}
