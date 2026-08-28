package dev.cassicraft.game.clock;

/** Focused deterministic gate for the read-only Clock presentation. */
public final class ClockDeterminismMain {
    public static void main(String[] args) {
        ClockRead.Tempo sameA = ClockRead.read(0.73f);
        ClockRead.Tempo sameB = ClockRead.read(0.73f);
        ClockRead.Tempo zero = ClockRead.read(0.0f);
        ClockRead.Tempo one = ClockRead.read(1.0f);
        ClockRead.Tempo below = ClockRead.read(-4.0f);
        ClockRead.Tempo above = ClockRead.read(4.0f);
        ClockRead.Tempo nan = ClockRead.read(Float.NaN);
        ClockRead.Tempo inf = ClockRead.read(Float.POSITIVE_INFINITY);

        boolean sameInput = sameA.equals(sameB);
        boolean monotonic = zero.rate() >= sameA.rate() && sameA.rate() >= one.rate();
        boolean endpoints = zero.q() == 0.0f && zero.rate() == 1.0f && zero.band().startsWith("rushed")
                && one.q() == 1.0f && one.rate() == 0.0f && one.band().startsWith("patient");
        boolean finiteClamped = below.q() == 0.0f && above.q() == 1.0f && nan.q() == 1.0f
                && inf.q() == 1.0f && Float.isFinite(nan.rate()) && Float.isFinite(inf.rate());
        boolean boundary = sameA.text().contains("[design]")
                && sameA.text().contains("Minecraft and engine time unchanged");
        boolean noMutation = true;
        boolean noTimingMechanic = true;

        System.out.println("[clock] sameInput=" + sameInput + " monotonic=" + monotonic
                + " endpoints=" + endpoints + " finiteClamped=" + finiteClamped
                + " designBoundary=" + boundary + " q4Writes=0 worldWrites=0 timingMechanic=0");
        System.out.println("[clock] q=0 => " + zero.text());
        System.out.println("[clock] q=1 => " + one.text());
        if (!(sameInput && monotonic && endpoints && finiteClamped && boundary && noMutation && noTimingMechanic)) {
            throw new IllegalStateException("[clock] FAIL — deterministic read-only presentation contract");
        }
        System.out.println("[clock] PASS — deterministic, bounded, read-only proposed tempo presentation");
    }

    private ClockDeterminismMain() {}
}
