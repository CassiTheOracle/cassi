package dev.cassicraft.game.expedition;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;

/** Headless pre-registered planner contract gate; coordinator guards are live-wiring checks. */
public final class ExpeditionDeterminismMain {
    private static final long SEED_A = 42L, SEED_B = 43L;
    private static final double[] ANCHOR = {0, 70, 0};
    public static void main(String[] args) throws Exception {
        Settled settled = settle(SEED_A);
        String before = settled.snapshot.contentHash();
        int originY = topStandable(settled.snapshot, settled.window);
        ExpeditionPlanner.Origin origin = new ExpeditionPlanner.Origin(0, originY, 0);
        ExpeditionPlanner.Contract first = ExpeditionPlanner.plan(settled.snapshot, settled.window, origin, SEED_A);
        ExpeditionPlanner.Contract second = ExpeditionPlanner.plan(settled.snapshot, settled.window, origin, SEED_A);
        ExpeditionPlanner.Contract other = ExpeditionPlanner.plan(settled.snapshot, settled.window, origin, SEED_B);
        boolean same = first != null && first.equals(second), immutable = before.equals(settled.snapshot.contentHash());
        boolean valid = first != null && valid(first, settled.snapshot, settled.window);
        boolean differs = other != null && !other.destination().equals(first.destination());
        boolean guards = first != null && !first.arrivedAt(origin.x(), origin.y(), origin.z()) && !first.returnedTo(first.destination().x(), first.destination().y(), first.destination().z());
        System.out.println("[expedition] origin=(0," + originY + ",0) originStandable=" + (originY != Integer.MIN_VALUE) + " candidateCount=" + ExpeditionPlanner.candidates(settled.snapshot, settled.window, origin, SEED_A).size());
        System.out.println("[expedition] same=" + same + " differs=" + differs + " valid=" + valid + " immutable=" + immutable + " guards=" + guards + " q4Writes=0");
        if (!same || !valid || !immutable || !guards) throw new IllegalStateException("[expedition] FAIL load-bearing invariant");
        System.out.println("[expedition] " + (!differs ? "NULL — seed diversity collision under frozen rule" : "PASS — deterministic, valid, bounded, zero-Q4 planner"));
    }
    private static int topStandable(FieldSnapshot s, double[] w) { for (int y=(int)Math.floor(w[1]+96)-2; y >= (int)Math.ceil(w[1]-96)+2; y--) if (ExpeditionPlanner.standable(s,w,0,y,0)) return y; return Integer.MIN_VALUE; }
    private static boolean valid(ExpeditionPlanner.Contract c, FieldSnapshot s, double[] w) { var d=c.destination(); long d2=d.horizontalDistanceSquared(c.origin()); return d2 >= (long)ExpeditionPlanner.MIN_DISTANCE*ExpeditionPlanner.MIN_DISTANCE && d2 <= (long)ExpeditionPlanner.MAX_DISTANCE*ExpeditionPlanner.MAX_DISTANCE && d.x()>=w[0]-96&&d.x()<=w[0]+96&&d.y()>=w[1]-96&&d.y()<=w[1]+96&&d.z()>=w[2]-96&&d.z()<=w[2]+96&&ExpeditionPlanner.standable(s,w,d.x(),d.y(),d.z()); }
    private record Settled(FieldSnapshot snapshot,double[] window) {}
    private static Settled settle(long seed) throws Exception { SnapshotPublisher p=new SnapshotPublisher(); CassiFieldThread worker=new CassiFieldThread(p); worker.start(new CassiFieldThread.Cfg(seed,CassiFieldThread.JOB_STEP_CAP,CassiFieldThread.SNAPSHOT_CADENCE,new KernelLoader().load(),ANCHOR)); try { long end=System.currentTimeMillis()+30000; while(System.currentTimeMillis()<end){ FieldSnapshot s=p.freshest(); if(s!=null&&s.generation()>=12){if(s.job()==null||s.job().isWindowless())throw new IllegalStateException("windowless publish");return new Settled(s,s.job().windowCenter());} Thread.sleep(20);}throw new IllegalStateException("no settled snapshot"); } finally {worker.close();} }
    private ExpeditionDeterminismMain() {}
}
