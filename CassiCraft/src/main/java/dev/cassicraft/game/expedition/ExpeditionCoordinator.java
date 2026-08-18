package dev.cassicraft.game.expedition;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;

/** One-active-expedition-per-player coordinator. */
public final class ExpeditionCoordinator {
 public enum State { IDLE, OUTBOUND, ARRIVED, HARVESTED, RETURNING, COMPLETE }
 public static final int MAX_REVALIDATION_FAILURES=30;
 private final SnapshotPublisher publisher; private final Map<UUID,Active> active=new HashMap<>(); private final Map<UUID,Integer> rewards=new HashMap<>(); private Consumer<ServerPlayer> completionObserver;
 public ExpeditionCoordinator(SnapshotPublisher publisher){this.publisher=publisher;}
 public void setCompletionObserver(Consumer<ServerPlayer> observer){this.completionObserver=observer;}
 public boolean start(ServerPlayer p){FieldSnapshot s=publisher.freshest();if(s==null){p.sendSystemMessage(Component.literal("The field window is not ready."));return false;}return start(p,s.contentHash().hashCode()^p.getUUID().getLeastSignificantBits());}
 public boolean start(ServerPlayer p,long seed){if(active.containsKey(p.getUUID())){p.sendSystemMessage(Component.literal("An expedition is already active."));return false;}FieldSnapshot s=publisher.freshest();if(s==null||s.job()==null||s.job().isWindowless()){p.sendSystemMessage(Component.literal("The field window is not ready."));return false;}BlockPos b=p.blockPosition();ExpeditionPlanner.Contract c=ExpeditionPlanner.plan(s,s.job().windowCenter(),new ExpeditionPlanner.Origin(b.getX(),b.getY(),b.getZ()),seed);if(c==null){p.sendSystemMessage(Component.literal("No reachable coherent site is present in this field window."));return false;}active.put(p.getUUID(),new Active(c));p.sendSystemMessage(Component.literal("Expedition started: follow the coarse field direction, "+coarse(b,c.destination())+"."));return true;}
 public void tick(MinecraftServer server){if(server.getTickCount()%20!=0)return;FieldSnapshot s=publisher.freshest();for(ServerPlayer p:server.getPlayerList().getPlayers()){Active a=active.get(p.getUUID());if(a==null)continue;if(s==null||s.job()==null||s.job().isWindowless()){if(recordFailure(p,a))continue;continue;}double[] w=s.job().windowCenter();BlockPos b=p.blockPosition();boolean valid=true;switch(a.state){case OUTBOUND->{var d=a.contract.destination();boolean arrived=a.contract.arrivedAt(b.getX(),b.getY(),b.getZ());boolean dst=ExpeditionPlanner.standable(s,w,d.x(),d.y(),d.z());if(arrived&&dst){a.state=State.ARRIVED;a.failures=0;p.sendSystemMessage(Component.literal("Arrival confirmed. Harvesting the bounded field receipt."));}else if(!dst)valid=false;}case ARRIVED->{a.harvested=true;a.state=State.HARVESTED;p.sendSystemMessage(Component.literal("Harvest complete. Return to the departure point."));}case HARVESTED->a.state=State.RETURNING;case RETURNING->{var o=a.contract.origin();boolean ret=a.contract.returnedTo(b.getX(),b.getY(),b.getZ());boolean src=ExpeditionPlanner.standable(s,w,o.x(),o.y(),o.z());if(ret&&src)complete(p,a);else if(!src)valid=false;}default->{}}if(valid)a.failures=0;else recordFailure(p,a);}}
 private boolean recordFailure(ServerPlayer p,Active a){if(++a.failures<MAX_REVALIDATION_FAILURES)return false;active.remove(p.getUUID());p.sendSystemMessage(Component.literal("The field reorganized before the expedition could complete; the contract was voided."));return true;}
 private void complete(ServerPlayer p,Active a){if(a.state!=State.RETURNING||!a.harvested||a.rewarded)return;a.rewarded=true;a.state=State.COMPLETE;rewards.merge(p.getUUID(),1,Integer::sum);active.remove(p.getUUID());p.sendSystemMessage(Component.literal("Expedition complete. Session knowledge receipt recorded; no field energy was minted."));if(completionObserver!=null)completionObserver.accept(p);}
 public State state(UUID id){Active a=active.get(id);return a==null?State.IDLE:a.state;}public int rewardCount(UUID id){return rewards.getOrDefault(id,0);}public void teardown(){active.clear();rewards.clear();}
 private static String coarse(BlockPos p,ExpeditionPlanner.Candidate d){int dx=d.x()-p.getX(),dz=d.z()-p.getZ();return(Math.abs(dx)>=Math.abs(dz)?(dx>=0?"east":"west"):(dz>=0?"south":"north"))+" (coarse)";}private static final class Active{final ExpeditionPlanner.Contract contract;State state=State.OUTBOUND;boolean harvested,rewarded;int failures;Active(ExpeditionPlanner.Contract c){contract=c;}}
}
