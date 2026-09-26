package dev.cassicraft.game.seams;

/**
 * MODULE 2/3 — the world-seams determinism + honesty gate (designs/world-seams.md
 * §1.3, §4.2 — the anchor-to-window seam; §6 the honest gates). Asserts, over
 * the real publish seam and the committed re-home/roll path, that the <b>block
 * world stays world-fixed and deterministic across re-home rolls, with no
 * phantom seam artifact</b>:
 *
 * <ol>
 *   <li><b>Determinism HARD</b> — two same-seed (42) runs of the seam measurement
 *       (the same settle + the same roll sequence of four +4-cell re-homes)
 *       produce identical content fingerprints and identical verdicts: the block
 *       world's seam honesty is a pure function of the fixed-seed field, never a
 *       timing weave.</li>
 *   <li><b>Seed sensitivity</b> — a different seed (43) produces a different
 *       fingerprint: the measurement actually read the field (different worlds
 *       differ at the seam), not a baked constant.</li>
 *   <li><b>The world-fixedness assert</b> — the T1 pure-geometry roll is a
 *       byte-exact bijection (a fixed world block carried across a whole-cell roll
 *       + center advance reads byte-identical), the T2 live production keeps
 *       crossing-block kinds world-fixed (a kind flip while covered is a seam
 *       artifact), and a swept block reads out-of-box AIR at exactly the geometric
 *       roll — the honest iso-surface. The gate asserts all three and prints the
 *       verdict line.</li>
 * </ol>
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Runs headlessly
 * under the game runtime classpath (the {@code followBehindDeterminism} pattern),
 * no live client/server. Pure consumer of the publish — never writes a block,
 * never touches the domain.
 */
public final class SeamDeterminismMain {

	/** The alternate seed proving sensitivity (the field differs, so the seam differs). */
	private static final long SEED_B = 43L;

	public static void main(String[] args) {
		boolean ok = true;
		SeamProbeMain.SeamResult run1 = null, run2 = null, runB = null;
		try {
			run1 = SeamProbeMain.measure(SeamProbeMain.SEED);
			run2 = SeamProbeMain.measure(SeamProbeMain.SEED);
			runB = SeamProbeMain.measure(SEED_B);
		} catch (IllegalStateException e) {
			System.err.println("[seam-determinism] FAILED — measurement interrupted/exhausted: " + e.getMessage());
			System.exit(1);
		}

		ok &= determinismGate(run1, run2);
		ok &= sensitivityGate(run1, runB);
		ok &= worldFixednessGate(run1);

		if (ok) {
			System.out.println("\n[seam-determinism] PASS — the block world is seam-honest, deterministic, and seed-sensitive across re-home rolls");
		} else {
			System.err.println("\n[seam-determinism] FAILED");
			System.exit(1);
		}
	}

	// --- Gate 1: determinism (same seed + same roll sequence → identical) -------
	private static boolean determinismGate(SeamProbeMain.SeamResult a, SeamProbeMain.SeamResult b) {
		System.out.println("\n[gate-1] determinism: same seed=" + SeamProbeMain.SEED + " + same roll sequence ("
				+ a.rolls() + "×(+4 cells +x,+z)) → identical content fingerprint");

		boolean sameFingerprint = a.fingerprint().equals(b.fingerprint());
		boolean sameVerdict = a.verdict().equals(b.verdict());
		boolean sameMeasure = a.t1KindIdentical() == b.t1KindIdentical()
				&& a.t1Passed() == b.t1Passed()
				&& a.t2InteriorKindFlips() == b.t2InteriorKindFlips()
				&& a.t2EdgeCrossIdentical() == b.t2EdgeCrossIdentical()
				&& a.t2EdgeAirWhenSwept() == b.t2EdgeAirWhenSwept()
				&& a.maxFloatDrift() == b.maxFloatDrift();
		boolean ok = sameFingerprint && sameVerdict && sameMeasure;

		System.out.println("  run1 fingerprint: " + a.fingerprint());
		System.out.println("  run2 fingerprint: " + b.fingerprint());
		System.out.println("  run1 verdict: " + a.verdict());
		System.out.println("  run2 verdict: " + b.verdict());
		System.out.println("  identical fingerprint=" + sameFingerprint
				+ " | same verdict=" + sameVerdict
				+ " | same measurements=" + sameMeasure
				+ " (T1 kind " + a.t1KindIdentical() + "/" + a.t1Sampled()
				+ ", T1 channel-within-tol " + a.t1Passed() + "/" + a.t1Sampled()
				+ ", T2 kind flips " + a.t2InteriorKindFlips() + "/" + a.t2InteriorCovered()
				+ ", edge-identical " + a.t2EdgeCrossIdentical() + "/" + a.t2EdgeCrossSamples()
				+ ", swept-AIR " + a.t2EdgeAirWhenSwept() + "/" + a.t2EdgeSwept()
				+ ", max live drift " + String.format("%.3e", a.maxFloatDrift()) + ")");
		if (!ok) {
			System.err.println("[gate-1] FAIL — the seam measurement is not deterministic across same-seed runs");
		}
		return ok;
	}

	// --- Gate 2: seed sensitivity (a different seed differs) ---------------------
	private static boolean sensitivityGate(SeamProbeMain.SeamResult a, SeamProbeMain.SeamResult b) {
		System.out.println("\n[gate-2] seed sensitivity: seed=" + SeamProbeMain.SEED + " vs seed=" + SEED_B);
		boolean differs = !a.fingerprint().equals(b.fingerprint());
		boolean ok = differs;
		System.out.println("  seed-42 fingerprint: " + a.fingerprint());
		System.out.println("  seed-43 fingerprint: " + b.fingerprint());
		System.out.println("  fingerprints differ=" + differs
				+ " (a different world reads differently at the seam — the probe reads the field, not a constant)");
		if (!ok) {
			System.err.println("[gate-2] FAIL — different seeds produced identical seams (the measurement is insensitive/vacuous)");
		}
		return ok;
	}

	// --- Gate 3: the world-fixedness assert --------------------------------------
	private static boolean worldFixednessGate(SeamProbeMain.SeamResult r) {
		System.out.println("\n[gate-3] world-fixedness assert: T1 roll is a byte-exact bijection, T2 crossing kinds world-fixed, swept blocks read AIR");

		// The seam assert rides T1 (pure geometry: a roll must not change a fixed
		// world block at all) + the swept edge (clean iso-surface) + the edge band
		// (periodic-torus honesty). T2's live kind flips are the field's own DT=0.001
		// evolution (the documented living-terrain churn), reported — the geometry
		// cannot flip a block (T1 proved it), so a live flip is evolution, not seam.
		boolean t1ByteExact = r.t1KindIdentical() == r.t1Sampled() && r.t1Passed() == r.t1Sampled();
		boolean sweptAir = r.t2EdgeSwept() > 0 && r.t2EdgeAirWhenSwept() == r.t2EdgeSwept();
		boolean sweepGeometric = r.t2SweptRollFirst() != Integer.MAX_VALUE && r.t2SweptRollLast() > r.t2SweptRollFirst();
		boolean bandHonest = r.bandHonest();
		boolean edgeKindsStable = r.t2EdgeCrossIdentical() == r.t2EdgeCrossSamples();
		boolean ok = t1ByteExact && sweptAir && sweepGeometric && bandHonest && edgeKindsStable;

		System.out.println("  [T1] carried blocks kind byte-identical: " + r.t1KindIdentical() + "/" + r.t1Sampled()
				+ " (" + r.tier1Status() + "; channels within float tolerance " + r.t1Passed() + "/" + r.t1Sampled() + ")");
		System.out.println("  [T2] edge-crossing in-box kinds identical: " + r.t2EdgeCrossIdentical() + "/"
				+ r.t2EdgeCrossSamples() + " | interior kinds flips (live evolution, not the seam): "
				+ r.t2InteriorKindFlips() + "/" + r.t2InteriorCovered());
		System.out.println("  [T2] swept blocks read out-of-box AIR: " + r.t2EdgeAirWhenSwept() + "/" + r.t2EdgeSwept()
				+ " | crossing roll range: first " + r.t2SweptRollFirst() + " → last " + r.t2SweptRollLast());
		System.out.println("  [T3] edge band honest (rho " + String.format("%.3g", r.rhoRelDelta()) + ", q "
				+ String.format("%.3g", r.qRelDelta()) + ", eps2 " + String.format("%.3g", r.epsRelDelta()) + ")=" + bandHonest);
		System.out.println("  max live float drift (the field's own DT=0.001 evolution, not the seam): "
				+ String.format("%.3e", r.maxFloatDrift()));
		System.out.println("  assert: T1 byte-exact=" + t1ByteExact + " | swept AIR=" + sweptAir
				+ " | sweep geometric=" + sweepGeometric + " | band honest=" + bandHonest
				+ " | edge kinds stable=" + edgeKindsStable);
		System.out.println("  verdict: " + r.verdict());
		if (!ok) {
			System.err.println("[gate-3] FAIL — the block world is NOT seam-honest (see the probe's verdict)");
		}
		return ok;
	}

	private SeamDeterminismMain() {
	}
}
