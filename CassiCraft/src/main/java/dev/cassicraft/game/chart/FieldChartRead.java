package dev.cassicraft.game.chart;

import java.util.Locale;
import dev.cassicraft.game.reader.FieldReader;

/** Pure comparison/presentation boundary for a stored chart observation. */
public final class FieldChartRead {
    public static final float LIVE_DELTA = 0.05f;
    public static final float FALLEN_DELTA = 0.20f;

    public enum Status { LIVE, STALE, FALLEN }

    public record Comparison(Status status, float qDelta, float eps2Delta, String text) {}

    /** Compare only the two engine-real channels, with preregistered design boundaries. */
    public static Comparison compare(FieldChartRecord record, FieldReader.FieldReadout live) {
        if (record == null || live == null) {
            throw new IllegalArgumentException("record and live readout are required");
        }
        float qDelta = Math.abs(live.q() - record.qDraw());
        float eps2Delta = Math.abs(live.eps2() - record.eps2Draw());
        Status status;
        if (qDelta <= LIVE_DELTA && eps2Delta <= LIVE_DELTA) {
            status = Status.LIVE;
        } else if (qDelta < FALLEN_DELTA && eps2Delta < FALLEN_DELTA) {
            status = Status.STALE;
        } else {
            status = Status.FALLEN;
        }
        String text = status + " [design] qDelta=" + fmt(qDelta)
                + " eps2Delta=" + fmt(eps2Delta);
        return new Comparison(status, qDelta, eps2Delta, text);
    }

    private static String fmt(float value) {
        return String.format(Locale.ROOT, "%.3f", value);
    }

    private FieldChartRead() {}
}
