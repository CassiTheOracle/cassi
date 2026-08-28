package dev.cassicraft.game.genesis;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.spawn.SurfaceSpawn;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Headless surface-genesis determinism + honesty gate. Asserts the surface
 * genesis ({@link SurfaceGenesis}, a bounded {@code SurfaceGenesis#WRITE_COUNT}-write
 * coherence-restoring deposit through the {@link CassiFieldThread#submitPerturbation}
 * lane) is deterministic at the load-bearing level, seed-sensitive, honest
 * (caps in range), and did genuinely move the field — the bounds a
 * {@code RideDownhillProbeMain}-style measurement permits, and two Q4-lane facts
 * make honest:
 *
 * <ol>
 *   <li><b>Structural determinism (same-seed identical).</b> Two fixed-seed runs
 *       of the SAME genesis produce a byte-identical post-genesis fingerprint
 *       over the <em>measured structure</em> — the full-precision top/bottom
 *       third solid fractions and the coherent-plane scan, the playable reality
 *       (a player sees the same solidity profile and the same standing surface).
 *       This is the honest determinism level the async Q4 lane supports: the
 *       single-injection response is byte-deterministic at a pinned drain step
 *       (Q4DeterminismMain gate-a), but the <em>exact per-cell grain</em> of an
 *       asynchronously-drained multi-write sequence is thread-timing sensitive
 *       (each write drains at an unpinned job boundary), so a byte-level
 *       same-seed "identical" claim over raw cells would be a false rigor. The
 *       structural fingerprint is the load-bearing contract.</li>
 *   <li><b>Different-seed differs.</b> A different seed's genesis → a different
 *       structural fingerprint (the field genuinely organized differently, not a
 *       fixed answer).</li>
 *   <li><b>Anti-vacuity — the lane moved the field.</b> The genesis band's field
 *       grain differs from the same-seed no-genesis control at the settle (the
 *       deposits are drained and nonzero), proving the genesis is not a no-op —
 *       even when, as the verdict shows, the bounded injection cannot organize a
 *       new density body out of the uniform sponge.</li>
 *   <li><b>Caps sane.</b> {@link CassiFieldThread#perturbationClampCount()} is
 *       reported and must match the expected level — for this matched-φ
 *       coherence-restoring design, <b>0</b> (the requested magnitudes are well
 *       within the no-mint cap, and the overdraw component {@code dEY−φ·dEI=0}).
 *       An unexpected clamp means the genesis exceeded its own bounds — a design
 *       bug, never a silenced counter.</li>
 * </ol>
 *
 * <p>It then prints the honest verdict (SUPPORTS / CONTRADICTS / INCONCLUSIVE with
 * its reason), asserted by the same measurement rule the probe uses — never forced.
 * Exit 0 = green. Headless (the {@code q4Determinism} pattern), no live server.
 */
public final class GenesisDeterminismMain {

	/** Fixed seed for the determinism arms. */
	private static final long SEED = 42L;
	/** A different seed for the sensitivity arm. */
	private static final long SEED_OTHER = 43L;
	/** The demo box anchor — center {0,70,0}. */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Settle to this mature field-time for the determinism fingerprint. */
	private static final double DETERMINISM_TARGET_T = 20.0;
	private static final long SETTLE_TIMEOUT_MS = 600_000;
	/** The gradient margin: real when top-third mean solid &lt; this × bottom-third. */
	private static final double GRADIENT_FRACTION = 0.25;
	/** The expected clamp level for the matched-φ design — 0 (well within the caps). */
	private static final long EXPECTED_CLAMPS = 0L;

	public static void main(String[] args) {
		boolean ok = true;
		System.out.println("=== Genesis determinism + honesty gate ===");
		System.out.println("genesisWrites=" + SurfaceGenesis.WRITE_COUNT
				+ " dEY=" + SurfaceGenesis.D_EY + " dEI=" + SurfaceGenesis.D_EI
				+ " (matched φ, coherence-restoring) | expectedClamps=" + EXPECTED_CLAMPS);

		Run gA1 = runOnce(SEED, true);
		Run gA2 = runOnce(SEED, true);
		Run gB = runOnce(SEED_OTHER, true);
		Run ctrl = runOnce(SEED, false);

		System.out.println("\n[genesis] SEED_A genesis run1:\n" + gA1.summary());
		System.out.println("[genesis] SEED_A genesis run2:\n" + gA2.summary());
		System.out.println("[genesis] SEED_B genesis run:\n" + gB.summary());
		System.out.println("[genesis] SEED_A no-genesis control (the falsified sponge):\n" + ctrl.summary());

		// Structural determinism: the playable structure (solidity profile, standing
		// plane) is byte-identical across same-seed genesis runs.
		boolean sameSeedStructural = gA1.structuralFingerprint.equals(gA2.structuralFingerprint);
		// Seed sensitivity at the structural level.
		boolean seedSensitive = !gA1.structuralFingerprint.equals(gB.structuralFingerprint);
		// Anti-vacuity at the grain level: the genesis deposit actually moved the
		// field vs the no-genesis control (both same-seed genesis runs and the
		// diff-seed genesis run differ from the control's band grain).
		boolean movedField = !gA1.bandFieldHash.equals(ctrl.bandFieldHash)
				&& !gB.bandFieldHash.equals(ctrl.bandFieldHash);
		boolean capsClean = gA1.clampCount == EXPECTED_CLAMPS
				&& gA2.clampCount == EXPECTED_CLAMPS
				&& gB.clampCount == EXPECTED_CLAMPS
				&& ctrl.clampCount == EXPECTED_CLAMPS;
		System.out.println("\n[genesis] same-seed structural identical=" + sameSeedStructural
				+ " | different-seed differs=" + seedSensitive
				+ " | genesis moved field (band grain vs control)=" + movedField
				+ " | caps at expected " + EXPECTED_CLAMPS + " (run1=" + gA1.clampCount
				+ ", run2=" + gA2.clampCount + ", seedB=" + gB.clampCount + ", ctrl=" + ctrl.clampCount + ")");

		if (!sameSeedStructural) {
			System.err.println("[genesis] FAIL — same genesis, same seed produced a different STRUCTURE (not deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[genesis] FAIL — different seeds produced an identical structure (vacuous)");
			ok = false;
		}
		if (!movedField) {
			System.err.println("[genesis] FAIL — the genesis did not move the field vs the no-genesis control (vacuous)");
			ok = false;
		}
		if (!capsClean) {
			System.err.println("[genesis] FAIL — a clamp engaged where the matched-φ design expected none; the genesis exceeded its own bounds");
			ok = false;
		}

		String verdict = verdict(gA1, ctrl);
		System.out.println("[genesis] VERDICT: " + verdict);

		if (!ok) {
			System.err.println("[genesis] FAILED — determinism/caps contract not met");
			System.exit(1);
		}
		System.out.println("[genesis] PASS — the genesis is structurally deterministic, seed-sensitive, moved the field grain, and stayed within its caps");
	}

	/** One end-to-end run: boot, optional genesis, settle to {@link #DETERMINISM_TARGET_T}, fingerprint. */
	private static Run runOnce(long seed, boolean withGenesis) {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			awaitGeneration(pub, 1, 12_000);
			int writes = 0;
			if (withGenesis) {
				SurfaceGenesis genesis = new SurfaceGenesis(worker, pub, WINDOW_CENTER);
				writes = genesis.run();
			}
			FieldSnapshot snap = awaitT(pub, DETERMINISM_TARGET_T);
			double[] wc = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: WINDOW_CENTER.clone();
			long clamps = worker.perturbationClampCount();
			double[] vert = verticalThirdProfile(snap, wc);
			int coherentY = SurfaceSpawn.findCoherentSurface(snap, wc,
					(int) Math.round(WINDOW_CENTER[0]), (int) Math.round(WINDOW_CENTER[2]),
					(int) Math.round(WINDOW_CENTER[1] + TwoFluidSolver.EXTENT));
			String structuralFp = structuralFingerprint(withGenesis, writes, clamps, vert[0], vert[1], coherentY);
			String bandHash = bandFieldHash(snap, wc);
			return new Run(seed, withGenesis, writes, clamps, structuralFp, bandHash,
					vert[0], vert[1], coherentY, coherentY != Integer.MIN_VALUE);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("genesis gate interrupted", e);
		} finally {
			worker.close();
		}
	}

	/** SHA-256 over the FULL-precision measured structure — the playable reality. */
	private static String structuralFingerprint(boolean withGenesis, int writes, long clamps,
			double top, double bottom, int coherentY) {
		StringBuilder sb = new StringBuilder();
		sb.append("genesis=").append(withGenesis).append(";writes=").append(writes)
				.append(";clamps=").append(clamps)
				.append(";top=").append(Double.doubleToLongBits(top))
				.append(";bottom=").append(Double.doubleToLongBits(bottom))
				.append(";coherentY=").append(coherentY == Integer.MIN_VALUE ? "-" : coherentY);
		return sha256(sb.toString().getBytes(StandardCharsets.UTF_8));
	}

	/** Hash the published ρ+q over the genesis band (the anchor column's lower third)
	 * — the region the writes targeted — used ONLY for the anti-vacuity check that the
	 * lane moved the field (not for the determinism assertion, which is structural). */
	private static String bandFieldHash(FieldSnapshot snap, double[] wc) {
		int ext = (int) TwoFluidSolver.EXTENT;
		int ax = (int) WINDOW_CENTER[0], az = (int) WINDOW_CENTER[2];
		int yLo = (int) WINDOW_CENTER[1] + SurfaceGenesis.Y_BAND_LO - 4;
		int yHi = (int) WINDOW_CENTER[1] + SurfaceGenesis.Y_BAND_HI + 4;
		int step = 4;
		java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
		ByteBuffer bb = ByteBuffer.allocate(8);
		for (int z = az - ext; z <= az + ext; z += step) {
			for (int x = ax - ext; x <= ax + ext; x += step) {
				for (int y = yLo; y <= yHi; y += step) {
					Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, x, y, z);
					bb.clear();
					bb.putFloat(s.rho());
					bb.putFloat(s.q());
					out.write(bb.array(), 0, 8);
				}
			}
		}
		return sha256(out.toByteArray());
	}

	/** The verdict — the same honest rule the probe uses, asserted by the measurement. */
	private static String verdict(Run genesis, Run ctrl) {
		boolean genesisGradient = genesis.topThirdFraction < GRADIENT_FRACTION * genesis.bottomThirdFraction;
		boolean controlGradient = ctrl.topThirdFraction < GRADIENT_FRACTION * ctrl.bottomThirdFraction;
		boolean plane = genesis.standable && genesis.coherentSolidY != Integer.MIN_VALUE;
		if (genesisGradient && !controlGradient && plane) {
			return "SUPPORTS — genesis organizes a real vertical gradient (top<"
					+ GRADIENT_FRACTION + "×bottom) absent in the no-genesis sponge, with a standable coherent plane";
		}
		if (!plane) {
			return "INCONCLUSIVE(no-standable-plane) — genesis measured but no coherent standable plane was found";
		}
		return "CONTRADICTS — genesis measured but did not organize a real vertical gradient"
				+ " (genesis top=" + String.format("%.3f", genesis.topThirdFraction)
				+ " bottom=" + String.format("%.3f", genesis.bottomThirdFraction)
				+ "; control top=" + String.format("%.3f", ctrl.topThirdFraction)
				+ " bottom=" + String.format("%.3f", ctrl.bottomThirdFraction)
				+ "; gradient-margin " + GRADIENT_FRACTION + ")";
	}

	private static double[] verticalThirdProfile(FieldSnapshot snap, double[] wc) {
		int ext = (int) TwoFluidSolver.EXTENT;
		int xb0 = (int) WINDOW_CENTER[0] - ext, xb1 = (int) WINDOW_CENTER[0] + ext;
		int zb0 = (int) WINDOW_CENTER[2] - ext, zb1 = (int) WINDOW_CENTER[2] + ext;
		int yb0 = (int) WINDOW_CENTER[1] - ext, yb1 = (int) WINDOW_CENTER[1] + ext;
		int sideY = yb1 - yb0;
		int third = sideY / 3;
		int step = 4;
		int[] solidCount = new int[sideY];
		int[] planeCount = new int[sideY];
		for (int z = zb0; z < zb1; z += step) {
			for (int x = xb0; x < xb1; x += step) {
				for (int dy = 0; dy < sideY; dy++) {
					int y = yb0 + dy;
					planeCount[dy]++;
					if (Quantizer.sampleAt(snap, wc, x, y, z).rho() >= Quantizer.TAU_C) {
						solidCount[dy]++;
					}
				}
			}
		}
		double topSum = 0, botSum = 0;
		int topN = 0, botN = 0;
		for (int dy = sideY - third; dy < sideY; dy++) {
			topSum += solidCount[dy] / (double) planeCount[dy];
			topN++;
		}
		for (int dy = 0; dy < third; dy++) {
			botSum += solidCount[dy] / (double) planeCount[dy];
			botN++;
		}
		return new double[] { topN > 0 ? topSum / topN : 0, botN > 0 ? botSum / botN : 0 };
	}

	private static FieldSnapshot awaitGeneration(SnapshotPublisher pub, int gen, long timeoutMs)
			throws InterruptedException {
		long deadline = System.currentTimeMillis() + timeoutMs;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() >= gen) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never reached generation " + gen);
	}

	private static FieldSnapshot awaitT(SnapshotPublisher pub, double t) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SETTLE_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.job() != null && s.job().t() >= t) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never reached t=" + t);
	}

	private static String sha256(byte[] data) {
		try {
			byte[] h = MessageDigest.getInstance("SHA-256").digest(data);
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte x : h) {
				sb.append(String.format("%02x", x));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	/** One end-to-end genesis run's structural fingerprint + band grain hash + measured structure. */
	private record Run(long seed, boolean withGenesis, int writes, long clampCount,
			String structuralFingerprint, String bandFieldHash,
			double topThirdFraction, double bottomThirdFraction, int coherentSolidY, boolean standable) {
		String summary() {
			return "  seed=" + seed + " genesis=" + withGenesis + " writes=" + writes
					+ " clamps=" + clampCount + " | topThird=" + String.format("%.3f", topThirdFraction)
					+ " bottomThird=" + String.format("%.3f", bottomThirdFraction)
					+ " coherentY=" + (coherentSolidY == Integer.MIN_VALUE ? "-" : coherentSolidY)
					+ " standable=" + standable
					+ "\n  structuralFp=" + structuralFingerprint.substring(0, 20) + "..."
					+ "\n  bandFieldHash=" + bandFieldHash.substring(0, 20) + "...";
		}
	}

	private GenesisDeterminismMain() {
	}
}
