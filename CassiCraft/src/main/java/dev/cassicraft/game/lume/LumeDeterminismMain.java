package dev.cassicraft.game.lume;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * Headless Weatherglass-lume determinism gate (field-instruments.md §1.4). The
 * honesty proof for the always-on lume: the client receives <b>only</b>
 * already-published channel values, deterministically. Boots a fixed-seed
 * {@link CassiFieldThread} via the real publish seam, awaits the first snapshot,
 * then at a <b>fixed</b> position computes {@link Quantizer#sampleReading} and
 * encodes the six floats exactly as {@link LumePayload} would (raw float bits
 * in the payload's field order {@code rho, q, eps2, gradX, gradY, gradZ}) → a
 * SHA-256. Asserts:
 *
 * <ol>
 *   <li><b>Measurement determinism:</b> two measurements of the <b>same</b>
 *       settled field yield byte-identical hashes — the wire presentation is a
 *       pure function of the published snapshot. The two same-seed arms share
 *       <b>one</b> settle (the sample/encode path is pure {@code sampleReading} +
 *       SHA-256, never a mutation), so the run-2 arm replays the same frozen
 *       settled snapshot and must equal run-1. Settle determinism is not
 *       re-proved here — it is hard-pinned byte-identically by the domainHarness
 *       gate (and by every mutating gate that still boots fresh).</li>
 *   <li><b>Anti-vacuous sensitivity + interiority:</b> a different seed (fresh
 *       settle) yields a different hash, and the sampled position reads real
 *       interior field (not out-of-box air), so the gate actually exercised the
 *       mapping.</li>
 * </ol>
 *
 * <p>Exit 0 = green. Runs headlessly under the game runtime classpath (the
 * {@code followBehindDeterminism} pattern), no live client/server.
 */
public final class LumeDeterminismMain {

	/** Fixed seed for the determinism (identical-run) arms. */
	private static final long SEED_A = 42L;
	/** A different seed for the anti-vacuous sensitivity arm. */
	private static final long SEED_B = SEED_A + 1;
	/** The anchored box center (world coords) — puts P deep in the interior. */
	private static final double[] ANCHOR = { 0, 70, 0 };
	/** The fixed world block sampled for the payload fingerprint. */
	private static final int PX = 45, PY = 100, PZ = 60;
	/** Worker first-publish guard. */
	private static final long FIRST_TIMEOUT_MS = 12_000;

	public static void main(String[] args) {
		boolean ok = true;
		// The two same-seed arms share ONE settle: boot+settle SEED_A once, run
		// the pure sample/encode path twice from the same frozen snapshot, and
		// assert the hashes match (measurement determinism). The seed-B arm boots
		// a fresh settle for seed sensitivity.
		Settled sa = bootAndSettle(SEED_A);
		Fingerprint hA1 = measureOn(sa);
		Fingerprint hA2 = measureOn(sa);
		Fingerprint hB = fingerprintWithCount(SEED_B);

		boolean sameSeedIdentical = hA1.hash().equals(hA2.hash());
		boolean differentSeedDiffers = !hA1.hash().equals(hB.hash());
		boolean interiorField = hB.rho() != 0f || hB.q() != 0f; // the sampled block read real field, not out-of-box air
		ok = sameSeedIdentical && differentSeedDiffers && interiorField;

		System.out.println("\n[gate] lume payload determinism at fixed position (" + PX + "," + PY + "," + PZ + ")");
		System.out.println("  same-seed run1 " + hA1.hash().substring(0, 16) + "...");
		System.out.println("  same-seed run2 " + hA2.hash().substring(0, 16) + "...");
		System.out.println("  different-seed " + hB.hash().substring(0, 16) + "... (rho=" + hB.rho() + ", q=" + hB.q() + ")");
		System.out.println("  same-seed identical=" + sameSeedIdentical
				+ " | different-seed differs=" + differentSeedDiffers
				+ " | sample read interior field (not out-of-box air)=" + interiorField);

		if (ok) {
			System.out.println("\n[lume] PASS — the lume payload is a pure, deterministic function of the published field");
		} else {
			System.err.println("\n[lume] FAILED");
			System.exit(1);
		}
	}

	/** Boot a fixed-seed worker, await its first publish, sample P, encode → hash. */
	private static Fingerprint fingerprintWithCount(long seed) {
		return measureOn(bootAndSettle(seed));
	}

	/** Boot the field thread, await a settled snapshot, capture the frozen
	 * (snapshot + window-center) state, and close the worker. The returned
	 * {@link Settled} is a pure immutable datum — safe to re-read. */
	private static Settled bootAndSettle(long seed) {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), ANCHOR);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitFirst(pub);
			double[] center = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: ANCHOR;
			return new Settled(snap, center);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("interrupted waiting for first publish", e);
		} finally {
			worker.close();
		}
	}

	/** The pure-read sample+encode over a settled snapshot — never mutates the field. */
	private static Fingerprint measureOn(Settled settled) {
		Quantizer.FieldReading r = Quantizer.sampleReading(settled.snap(), settled.windowCenter(), PX, PY, PZ);
		return new Fingerprint(sha256(r.rho(), r.q(), r.eps2(), r.gradX(), r.gradY(), r.gradZ()), r.rho(), r.q());
	}

	private static FieldSnapshot awaitFirst(SnapshotPublisher pub) throws InterruptedException {
		long deadline = System.currentTimeMillis() + FIRST_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("no first snapshot within timeout");
	}

	/**
	 * SHA-256 over the six floats in the payload's exact wire order (raw float
	 * bits, {@code rho, q, eps2, gradX, gradY, gradZ}) — the same bytes
	 * {@link LumePayload#CODEC} writes.
	 */
	private static String sha256(float... values) {
		java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(values.length * 4);
		for (float v : values) {
			bb.putFloat(v);
		}
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(bb.array());
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte b : h) {
				sb.append(String.format("%02x", b));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	/** The sampled value + its hash (carries rho/q for the interior-field assert). */
	private record Fingerprint(String hash, float rho, float q) {
	}

	/** The frozen settled field (immutable snapshot + its window center) shared
	 * by the two same-seed measurement arms. */
	private record Settled(FieldSnapshot snap, double[] windowCenter) {
	}

	private LumeDeterminismMain() {
	}
}
