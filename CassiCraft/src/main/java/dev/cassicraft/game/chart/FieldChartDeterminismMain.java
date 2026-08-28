package dev.cassicraft.game.chart;

import java.util.UUID;
import java.util.concurrent.TimeUnit;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.reader.FieldReader;
import net.minecraft.core.BlockPos;

/** Focused anti-vacuity and session-contract gate for Field Chart. */
public final class FieldChartDeterminismMain {
    private static final long SEED = 42L;
    private static final BlockPos POS = new BlockPos(0, 70, 0);
    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-000000000002");

    public static void main(String[] args) throws Exception {
        SnapshotPublisher live = new SnapshotPublisher();
        CassiFieldThread worker = new CassiFieldThread(live);
        worker.start(new CassiFieldThread.Cfg(SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
                new KernelLoader().load(), new double[] { 0, 70, 0 }));
        FieldSnapshot published;
        try {
            published = awaitPublish(live);
            if (published == null || published.job() == null || published.job().isWindowless()) {
                throw new IllegalStateException("[field-chart] FAIL — anti-vacuity publish missing");
            }
            SnapshotPublisher frozen = new SnapshotPublisher();
            frozen.publish(published);
            System.out.println("[field-chart] published-read anti-vacuity generation=" + published.generation() + " q/eps2 sampled at " + POS);
            runContract(frozen, published);
        } finally {
            worker.close();
        }
        if (worker.isRunning()) throw new IllegalStateException("[field-chart] FAIL — gate worker did not close");
        System.out.println("[field-chart] PASS — gate worker closed after focused work");
        System.out.println("[field-chart] PASS — bounded, deterministic, UUID-isolated, session-local, read-only chart");
    }

    private static void runContract(SnapshotPublisher publisher, FieldSnapshot frozen) {
        FieldChartCoordinator chart = new FieldChartCoordinator(() -> publisher);
        SnapshotPublisher absent = new SnapshotPublisher();
        FieldChartCoordinator dark = new FieldChartCoordinator(() -> absent);
        check(FieldChartActions.inspect(dark, A).dark() && dark.filled(A) == 0 && dark.selected(A) == 0, "no-publish inspect unchanged");
        check(FieldChartActions.draw(dark, A, POS).dark() && FieldChartActions.redraw(dark, A, POS).dark()
                && FieldChartActions.itemUse(dark, A, POS, false).dark()
                && FieldChartActions.itemUse(dark, A, POS, true).dark()
                && dark.filled(A) == 0 && dark.selected(A) == 0, "no-publish draw/redraw/item unchanged");
        check(FieldChartActions.slot(dark, A, 4).dark() && FieldChartActions.summary(dark, A).dark()
                && dark.filled(A) == 0 && dark.selected(A) == 0, "no-publish slot/summary unchanged");

        FieldChartCoordinator.Result draw = FieldChartActions.itemUse(chart, A, POS, true);
        check(draw.accepted() && chart.filled(A) == 1, "item crouch action draws selected slot");
        FieldChartRecord rec = draw.record();
        FieldChartCoordinator.Result plain = FieldChartActions.itemUse(chart, A, POS, false);
        check(plain.accepted() && plain.record().equals(rec) && chart.filled(A) == 1 && chart.selected(A) == 0, "item plain action inspects without mutation");
        FieldReader.FieldReadout exact = FieldReader.read(frozen, frozen.job().windowCenter(), POS.getX(), POS.getY(), POS.getZ());
        check(rec.generation() == frozen.generation() && rec.qDraw() == exact.q() && rec.eps2Draw() == exact.eps2(), "atomic frozen generation/q/eps2");
        FieldChartCoordinator.Result itemRedraw = FieldChartActions.itemUse(chart, A, new BlockPos(6, 70, 0), true);
        check(itemRedraw.accepted() && !itemRedraw.record().equals(rec) && itemRedraw.record().position().equals(new BlockPos(6, 70, 0)),
                "item crouch occupied action redraws selected slot with replacement");
        check(FieldChartActions.slot(chart, A, 1).accepted() && FieldChartActions.draw(chart, A, new BlockPos(3, 70, 0)).accepted(), "command slot/draw actions");
        FieldChartRecord preservedSlotOne = chart.records(A).stream().filter(r -> r.slot() == 1).findFirst().orElseThrow();
        check(FieldChartActions.inspect(chart, A).accepted(), "command inspect action");
        check(FieldChartActions.slot(chart, A, 0).accepted() && FieldChartActions.redraw(chart, A, new BlockPos(9, 70, 0)).accepted(), "command redraw action replaces slot 0");
        check(chart.records(A).stream().anyMatch(r -> r.slot() == 1 && r.equals(preservedSlotOne))
                && chart.records(A).stream().anyMatch(r -> r.slot() == 0 && r.position().equals(new BlockPos(9, 70, 0))), "command redraw preserves exact nonselected record");
        FieldChartCoordinator.Result summary = FieldChartActions.summary(chart, A);
        check(summary.accepted() && summary.message().contains("2/8") && summary.message().indexOf("  0:") < summary.message().indexOf("  1:"), "command summary ascending slots");

        FieldChartRecord comparisonRecord = chart.records(A).stream().filter(r -> r.slot() == 0).findFirst().orElseThrow();
        FieldChartRead.Comparison sameA = FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw(), comparisonRecord.eps2Draw()));
        FieldChartRead.Comparison sameB = FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw(), comparisonRecord.eps2Draw()));
        check(sameA.equals(sameB) && sameA.status() == FieldChartRead.Status.LIVE, "comparison deterministic equality");
        check(FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw() + .10f, comparisonRecord.eps2Draw())).status() == FieldChartRead.Status.STALE
                && FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw() + .20f, comparisonRecord.eps2Draw())).status() == FieldChartRead.Status.FALLEN, "q-only monotonic aging");
        check(FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw(), comparisonRecord.eps2Draw() + .10f)).status() == FieldChartRead.Status.STALE
                && FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw(), comparisonRecord.eps2Draw() + .20f)).status() == FieldChartRead.Status.FALLEN, "eps2-only monotonic aging");
        check(FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw() + .05f, comparisonRecord.eps2Draw())).status() == FieldChartRead.Status.LIVE
                && FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw() + .20f, comparisonRecord.eps2Draw())).status() == FieldChartRead.Status.FALLEN, "q inclusive boundaries");
        check(FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw(), comparisonRecord.eps2Draw() + .05f)).status() == FieldChartRead.Status.LIVE
                && FieldChartRead.compare(comparisonRecord, readout(comparisonRecord.qDraw(), comparisonRecord.eps2Draw() + .20f)).status() == FieldChartRead.Status.FALLEN, "eps2 inclusive boundaries");

        for (int i = 2; i < FieldChartCoordinator.SLOT_COUNT; i++) {
            FieldChartActions.slot(chart, A, i);
            FieldChartActions.draw(chart, A, POS);
        }
        check(chart.filled(A) == 8 && !FieldChartActions.draw(chart, A, POS).accepted(), "eight-slot occupied draw rejects without eviction");
        int aCount = chart.filled(A);
        int aSlot = chart.selected(A);
        check(FieldChartActions.slot(chart, B, 0).accepted() && FieldChartActions.draw(chart, B, POS).accepted()
                && chart.filled(B) == 1 && chart.filled(A) == aCount && chart.selected(A) == aSlot, "UUID isolation");
        chart.clearSession();
        check(chart.selected(A) == 0 && chart.filled(A) == 0 && chart.selected(B) == 0 && chart.filled(B) == 0, "clearSession resets both users");
        System.out.println("[field-chart] threshold evidence: LIVE<=0.05 [design], STALE<0.20 [design], FALLEN>=0.20 [design]");
        System.out.println("[field-chart] gate invokes the shared runtime action-policy seam used by item/command adapters");
        runBearingContract(chart, publisher);
    }
    private static void runBearingContract(FieldChartCoordinator chart, SnapshotPublisher publisher) {
        FieldChartActions.draw(chart, A, new BlockPos(9, 70, 0));
        int readySelected = chart.selected(A);
        int readyFilled = chart.filled(A);
        var readyRecords = chart.records(A);
        FieldChartBearing.Result east = FieldChartActions.bearing(chart, A, 0, 70, 0);
        check(east.ready() && east.bearing() == FieldChartBearing.Bearing.EAST, "bearing cardinal east");
        check(chart.selected(A) == readySelected && chart.filled(A) == readyFilled && chart.records(A).equals(readyRecords),
                "bearing ready immutable");
        check(FieldChartBearing.class.getPackageName().equals("dev.cassicraft.game.chart"), "bearing package");
        check(java.util.Arrays.stream(FieldChartBearing.class.getDeclaredFields())
                .noneMatch(field -> field.getType().getName().contains("FieldChartCoordinator")
                        || field.getType().getName().contains("net.minecraft")
                        || field.getType().getName().contains("dev.cassicraft.domain")
                        || field.getType().getName().contains("Session")), "bearing pure forbidden dependency surface");

        FieldChartBearing.Result west = FieldChartBearing.compute(A, 0, 9, 70, 0, 0, 70, 0);
        FieldChartBearing.Result north = FieldChartBearing.compute(A, 0, 0, 70, 0, 0, 70, -9);
        FieldChartBearing.Result south = FieldChartBearing.compute(A, 0, 0, 70, 0, 0, 70, 9);
        check(west.bearing() == FieldChartBearing.Bearing.WEST && north.bearing() == FieldChartBearing.Bearing.NORTH
                && south.bearing() == FieldChartBearing.Bearing.SOUTH, "bearing signed cardinal compute arms");

        FieldChartBearing.Result ne = FieldChartBearing.compute(A, 0, 0, 70, 0, 4, 70, -4);
        FieldChartBearing.Result se = FieldChartBearing.compute(A, 0, 0, 70, 0, 4, 70, 4);
        FieldChartBearing.Result sw = FieldChartBearing.compute(A, 0, 0, 70, 0, -4, 70, 4);
        FieldChartBearing.Result nw = FieldChartBearing.compute(A, 0, 0, 70, 0, -4, 70, -4);
        check(ne.bearing() == FieldChartBearing.Bearing.NORTH_EAST && se.bearing() == FieldChartBearing.Bearing.SOUTH_EAST
                && sw.bearing() == FieldChartBearing.Bearing.SOUTH_WEST && nw.bearing() == FieldChartBearing.Bearing.NORTH_WEST,
                "bearing all signed diagonal compute arms");
        FieldChartBearing.Result eastDominant = FieldChartBearing.compute(A, 0, 0, 70, 0, 5, 70, 3);
        FieldChartBearing.Result westDominant = FieldChartBearing.compute(A, 0, 0, 70, 0, -5, 70, -3);
        FieldChartBearing.Result southDominant = FieldChartBearing.compute(A, 0, 0, 70, 0, 3, 70, 5);
        FieldChartBearing.Result northDominant = FieldChartBearing.compute(A, 0, 0, 70, 0, -3, 70, -5);
        check(eastDominant.bearing() == FieldChartBearing.Bearing.EAST && westDominant.bearing() == FieldChartBearing.Bearing.WEST
                && southDominant.bearing() == FieldChartBearing.Bearing.SOUTH && northDominant.bearing() == FieldChartBearing.Bearing.NORTH,
                "bearing all signed dominant compute arms");
        FieldChartBearing.Result verticalHere = FieldChartBearing.compute(A, 0, 4, 70, -2, 4, 73, -2);
        check(verticalHere.bearing() == FieldChartBearing.Bearing.HERE && verticalHere.dx() == 0
                && verticalHere.dy() == 3 && verticalHere.dz() == 0
                && verticalHere.message().contains("delta=(dx=0,dy=3,dz=0) horizontal=HERE"),
                "bearing vertical-only HERE compute arm");

        check(east.message().equals("Field Chart bearing slot 0 target=(9,70,0) delta=(dx=9,dy=0,dz=0) horizontal=EAST distance2=81"),
                "bearing deterministic formatting");
        FieldChartBearing.Result same = FieldChartActions.bearing(chart, A, 0, 70, 0);
        check(east.equals(same) && east.message().equals(same.message()), "bearing deterministic equality");

        int beforeBlankSelected = chart.selected(A);
        int beforeBlankFilled = chart.filled(A);
        var beforeBlankRecords = chart.records(A);
        check(FieldChartActions.slot(chart, A, 7).accepted(), "bearing blank setup slot");
        FieldChartBearing.Result blank = FieldChartActions.bearing(chart, A, 0, 70, 0);
        check(blank.status() == FieldChartBearing.Status.BLANK && blank.message().equals("Field Chart bearing slot 7 is blank."), "bearing blank exact result");
        check(chart.selected(A) == 7 && chart.filled(A) == beforeBlankFilled && chart.records(A).equals(beforeBlankRecords),
                "bearing blank immutable");

        FieldChartCoordinator unseenDark = new FieldChartCoordinator(null);
        check(FieldChartActions.bearing(unseenDark, B, 0, 0, 0).status() == FieldChartBearing.Status.DARK
                && unseenDark.filled(B) == 0 && unseenDark.selected(B) == 0, "bearing no-publish before session");
        FieldChartCoordinator other = new FieldChartCoordinator(() -> new SnapshotPublisher());
        check(FieldChartActions.bearing(other, B, 0, 0, 0).status() == FieldChartBearing.Status.DARK
                && other.filled(B) == 0, "bearing UUID isolation no-publish");

        check(FieldChartActions.slot(chart, A, readySelected).accepted(), "bearing restore selected slot");
        check(chart.selected(A) == readySelected && chart.filled(A) == readyFilled && chart.records(A).equals(readyRecords),
                "bearing final session invariants");
        java.util.concurrent.atomic.AtomicReference<SnapshotPublisher> dynamicPublisher = new java.util.concurrent.atomic.AtomicReference<>(publisher);
        FieldChartCoordinator populatedNullFreshest = new FieldChartCoordinator(dynamicPublisher::get);
        FieldChartActions.draw(populatedNullFreshest, A, new BlockPos(2, 70, 2));
        int nullSelected = populatedNullFreshest.selected(A), nullFilled = populatedNullFreshest.filled(A);
        var nullRecords = populatedNullFreshest.records(A);
        dynamicPublisher.set(new SnapshotPublisher());
        FieldChartCoordinator nullFreshest = new FieldChartCoordinator(() -> new SnapshotPublisher());
        check(FieldChartActions.bearing(nullFreshest, A, 0, 70, 0).status() == FieldChartBearing.Status.DARK
                && nullFreshest.filled(A) == 0 && nullFreshest.selected(A) == 0, "bearing freshest-null unseen UUID");
        check(FieldChartActions.bearing(populatedNullFreshest, A, 0, 70, 0).status() == FieldChartBearing.Status.DARK
                && populatedNullFreshest.selected(A) == nullSelected && populatedNullFreshest.filled(A) == nullFilled
                && populatedNullFreshest.records(A).equals(nullRecords), "bearing freshest-null preserves populated session");
        FieldChartBearing.WideResult endpointOverflow = FieldChartBearing.computeWide(A, 0,
                java.math.BigInteger.valueOf(Long.MIN_VALUE), java.math.BigInteger.ZERO, java.math.BigInteger.ZERO,
                java.math.BigInteger.valueOf(Long.MAX_VALUE), java.math.BigInteger.ZERO, java.math.BigInteger.ZERO);
        check(endpointOverflow.dx().equals(java.math.BigInteger.ONE.shiftLeft(64).subtract(java.math.BigInteger.ONE))
                && endpointOverflow.distance2().equals(FieldChartBearing.OVERFLOW), "bearing widened endpoint overflow sentinel");
    }

    private static SnapshotPublisher publisherForBearing() {
        SnapshotPublisher publisher = new SnapshotPublisher();
        publisher.publish(new FieldSnapshot(new float[] { 0 }, new float[] { 0 }, new float[] { 0, 0, 0 }, new float[] { 0 }, 1, null));
        return publisher;
    }
    private static FieldReader.FieldReadout readout(float q, float eps2) {
        return new FieldReader.FieldReadout(0, q, eps2, 0, 0, 0, "");
    }
    private static FieldSnapshot awaitPublish(SnapshotPublisher publisher) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(12);
        do {
            FieldSnapshot snapshot = publisher.freshest();
            if (snapshot != null) return snapshot;
            Thread.sleep(10);
        } while (System.nanoTime() < deadline);
        return null;
    }
    private static void check(boolean condition, String label) {
        if (!condition) throw new IllegalStateException("[field-chart] FAIL — " + label);
        System.out.println("[field-chart] PASS — " + label);
    }
    private FieldChartDeterminismMain() {}
}
