package dev.cassicraft.game.seams;

/**
 * MODULE 2/3 — the altitude-seam determinism + honesty gate (designs/world-seams.md
 * §2.4 — the zenith is the window's boundary, not its door). Asserts, over the
 * real publish seam, that the sky above the window top reads AIR (the box's outer
 * face is the iso-surface — no altitude wrap artifact surfaces the body's stone),
 * and that the altitude profile is deterministic and seed-sensitive:
 *
 * <ol>
 *   <li><b>No-stone-in-the-sky</b> — the topmost in-box band and the sky above the
 *       window top must read AIR at every sampled Y (the honest fix; the owner's
 *       "full chunks of stone while flying in creative" is the asserted-away
 *       altitude seam).</li>
 *   <li><b>Determinism HARD</b> — two same-seed runs produce identical content
 *       fingerprints and verdicts.</li>
 *   <li><b>Seed sensitivity</b> — a different seed produces a different
 *       fingerprint (the altitude read actually follows the field, not a constant).
 *   </li>
 * </ol>
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Headless (the seams
 * probe pattern), no live client/server. Pure consumer of the publish — never
 * writes a block, never touches the domain.
 */
public final class SkyStoneDeterminismMain {

	/** The alternate seed proving sensitivity. */
	private static final long SEED_B = 43L;

	public static void main(String[] args) {
		boolean ok = true;
		SkyStoneProbeMain.SkyStoneResult run1 = null, run2 = null, runB = null;
		try {
			run1 = SkyStoneProbeMain.measure(SkyStoneProbeMain.SEED);
			run2 = SkyStoneProbeMain.measure(SkyStoneProbeMain.SEED);
			runB = SkyStoneProbeMain.measure(SEED_B);
		} catch (IllegalStateException e) {
			System.err.println("[skystone-determinism] FAILED — measurement interrupted/exhausted: " + e.getMessage());
			System.exit(1);
		}

		ok &= noStoneInSkyGate(run1);
		ok &= determinismGate(run1, run2);
		ok &= sensitivityGate(run1, runB);

		if (ok) {
			System.out.println("\n[skystone-determinism] PASS — the sky above the window top is clear (AIR), deterministic, and seed-sensitive");
		} else {
			System.err.println("\n[skystone-determinism] FAILED");
			System.exit(1);
		}
	}

	// --- Gate 1: no stone in the sky ------------------------------------------
	private static boolean noStoneInSkyGate(SkyStoneProbeMain.SkyStoneResult r) {
		System.out.println("\n[gate-1] no-stone-in-the-sky: the topmost in-box band reads AIR at the live anchor (the box's outer face is the iso-surface)");
		boolean clean = true;
		for (SkyStoneProbeMain.AnchorAlt a : r.anchors()) {
			boolean bandAir = a.topBandSolid() == 0;
			System.out.println("  anchor Y=" + String.format("%-4s", (long) a.anchorY())
					+ "  top-band solid=" + a.topBandSolid() + "/" + a.topBandTotal()
					+ "  → " + (bandAir ? "AIR (clear)" : "STONE (the altitude seam)"));
			clean &= bandAir;
		}
		System.out.println("  assert: the sky below the zenith reads air = " + clean
				+ " (the box's outer face is the iso-surface, world-seams.md §2.4)");
		if (!clean) {
			System.err.println("[gate-1] FAIL — stone is in the sky (the altitude seam artifact is present)");
		}
		return clean;
	}

	// --- Gate 2: determinism ----------------------------------------------------
	private static boolean determinismGate(SkyStoneProbeMain.SkyStoneResult a, SkyStoneProbeMain.SkyStoneResult b) {
		System.out.println("\n[gate-2] determinism: same seed=" + SkyStoneProbeMain.SEED + " → identical altitude fingerprint");
		boolean same = a.fingerprint().equals(b.fingerprint());
		boolean sameMeasure = a.anchors().size() == b.anchors().size()
				&& a.anchors().stream().allMatch(x -> b.anchors().stream()
						.anyMatch(y -> y.anchorY() == x.anchorY() && y.topBandSolid() == x.topBandSolid()
								&& y.topBandTotal() == x.topBandTotal()));
		boolean ok = same && sameMeasure;
		System.out.println("  run1 fingerprint: " + a.fingerprint());
		System.out.println("  run2 fingerprint: " + b.fingerprint());
		System.out.println("  identical fingerprint=" + same + " | same altitude measurements=" + sameMeasure);
		if (!ok) {
			System.err.println("[gate-2] FAIL — the altitude measurement is not deterministic across same-seed runs");
		}
		return ok;
	}

	// --- Gate 3: seed sensitivity -----------------------------------------------
	private static boolean sensitivityGate(SkyStoneProbeMain.SkyStoneResult a, SkyStoneProbeMain.SkyStoneResult b) {
		System.out.println("\n[gate-3] seed sensitivity: seed=" + SkyStoneProbeMain.SEED + " vs seed=" + SEED_B);
		boolean differs = !a.fingerprint().equals(b.fingerprint());
		boolean ok = differs;
		System.out.println("  seed-42 fingerprint: " + a.fingerprint());
		System.out.println("  seed-43 fingerprint: " + b.fingerprint());
		System.out.println("  fingerprints differ=" + differs
				+ " (a different world reads differently at altitude — the probe reads the field, not a constant)");
		if (!ok) {
			System.err.println("[gate-3] FAIL — different seeds produced identical altitude reads (insensitive/vacuous)");
		}
		return ok;
	}

	private SkyStoneDeterminismMain() {
	}
}
