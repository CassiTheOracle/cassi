#!/usr/bin/env python3
"""Frozen REACTION contextual live-policy workflow."""
from __future__ import annotations
import argparse, base64, hashlib, json, math, re
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import numpy as np
import balance_policy_regime as regime

MODEL_SHA256="519d093e946bbb163f20f8e37b3c2cccc90d049f1cd3f150cdcf64267cbd6d59"
LIVE_SEEDS=[20260817,20260819,20260821]; ARM_NAMES=["D","A","M","P","R"]; REACTION_IDS=list(range(1,15))+[23,24,25]
N=32; CADENCE=tuple(regime.CADENCE); CONTROL_SEED=2026081701; PROTOCOL="balance-policy-reaction-live-v1"
ROOT=Path(__file__).resolve().parents[1]; REGIME_RESULT=ROOT/"_diag/balance_policy_regime/result.json"; REGIME_MANIFEST=ROOT/"_diag/balance_policy_regime/manifest.json"; PREREG=ROOT/"research/steering/balance_policy_reaction_live_prereg.md"; OUT=ROOT/"_diag/balance_policy_reaction_live"

def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def sha_bytes(v): return hashlib.sha256(v).hexdigest()
def source_hashes(): return {"live_tool":sha_bytes(Path(__file__).read_bytes()),"dependencies":regime.source_hashes(),"prereg":sha_bytes(PREREG.read_bytes()),"scene":sha_bytes((ROOT/"scenes/mind_engine_cache.tscn").read_bytes())}
def model_record(result):
    m=result["models"]["REACTION"]; return {"feature_ids":m["feature_ids"],"weights":m["weights"],"mean":m["mean"],"std":m["std"],"loss":m["loss"],"manifest_hashes":result["manifest_hashes"]}
def model_hash(result): return sha_bytes(canonical(model_record(result)))
def load_frozen():
    result=json.loads(REGIME_RESULT.read_text(encoding="utf-8")); manifest=json.loads(REGIME_MANIFEST.read_text(encoding="utf-8")); model=model_record(result); current=regime.source_hashes()
    if model_hash(result)!=MODEL_SHA256 or model["feature_ids"]!=REACTION_IDS: raise ValueError("frozen model mismatch")
    if manifest.get("feature_manifest_hash")!=model["manifest_hashes"]["feature_manifest_hash"] or manifest.get("partition_hash")!=model["manifest_hashes"]["partition_hash"] or manifest.get("source_hashes_before")!=current or manifest.get("source_hashes_after")!=current: raise ValueError("frozen receipt mismatch")
    if not np.isfinite(np.asarray(model["std"],float)).all() or np.any(np.asarray(model["std"],float)<=0) or not np.isfinite(np.asarray(model["weights"],float)).all(): raise ValueError("invalid model")
    return result,manifest,model
def check_scene(root=ROOT):
    text=(root/"scenes/mind_engine_cache.tscn").read_text(encoding="utf-8"); ext=re.search(r'^\[ext_resource\s+type="Script"\s+path="(res://[^"]+)"\s+id="([^"]+)"\]\s*$',text,re.M); node=re.search(r'^script\s*=\s*ExtResource\("([^"]+)"\)\s*$',text,re.M); props={}
    for line in text.splitlines():
        m=re.match(r'^(grid_n|auto_step|bridge_port)\s*=\s*(.+?)\s*$',line.strip())
        if m: props[m.group(1)]=m.group(2).strip().strip('"')
    if not ext or ext.group(1)!="res://scripts/cassi_mind_engine.gd" or not node or node.group(1)!=ext.group(2) or props!={"grid_n":"32","auto_step":"false","bridge_port":"7599"}: raise ValueError("pinned scene mismatch")
def logits(features,model):
    x=np.asarray(features,float); ids=np.asarray(model["feature_ids"],int)-1
    if x.shape!=(30,) or not np.isfinite(x).all(): raise ValueError("features")
    return np.concatenate(([1.0],(x[ids]-np.asarray(model["mean"],float))/np.asarray(model["std"],float)))@np.asarray(model["weights"],float)
def stable_probs(z):
    z=np.asarray(z,float)
    if z.shape!=(3,) or not np.isfinite(z).all(): raise ValueError("logits")
    e=np.exp(z-np.max(z)); return e/np.sum(e)
def choose(features,model):
    z=logits(features,model); return int(np.argmax(z)),z
def validate(reply,command,step=None,time=None):
    if not isinstance(reply,dict) or reply.get("ok") is not True or reply.get("cmd")!=command: raise ValueError(f"bad {command}")
    if step is not None:
        s=reply.get("step")
        if isinstance(s,bool) or not isinstance(s,(int,np.integer)) or int(s)!=int(step): raise ValueError("step mismatch")
    if time is not None:
        t=reply.get("t")
        if isinstance(t,bool) or not isinstance(t,(int,float,np.integer,np.floating)) or not math.isfinite(float(t)) or not math.isclose(float(t),float(time),rel_tol=0,abs_tol=1e-12): raise ValueError("time mismatch")
def decode_identity(raw):
    f=regime.decode(raw,N); req=("ey","ei","eps","rho","field_power")
    if any(k not in f for k in req) or any(np.asarray(f[k]).shape!=(N**3,) for k in req): raise ValueError("decode identity")
    return f
def finite_safety(field,baseline):
    ey,ei,eps,rho=[np.asarray(field[k],float) for k in ("ey","ei","eps","rho")]; power=ey*ey+ei*ei; qi=rho*rho/(rho*rho+regime.PHI**-2+eps*eps)
    if not all(np.isfinite(x).all() for x in (ey,ei,eps,rho,power,qi)) or np.any(qi<-1e-7) or np.any(qi>1+1e-7): raise ValueError("readout safety")
    if (baseline==0 and np.max(power)>0) or (baseline>0 and np.max(power)>100*baseline): raise ValueError("100x gate")
    return power,qi
def validate_deposit(d,c,epsilon):
    if set(d)!={"x","y","z","cy","ci","sigma"} or not all(math.isfinite(float(d[k])) for k in d) or any(not -1<=float(d[k])<=1 for k in ("x","y","z")) or float(d["sigma"])!=1 or any(abs(float(d[k])-float(c[k]))>1e-9 for k in ("x","y","z")): raise ValueError("deposit")
    if epsilon<0 and not(float(d["cy"])>=0 and float(d["ci"])==0): raise ValueError("Yin")
    if epsilon>=0 and not(float(d["ci"])>=0 and float(d["cy"])==0): raise ValueError("Yang")
def observability_field(field):
    ey,ei=np.asarray(field["ey"],float),np.asarray(field["ei"],float)
    return regime.obs.derive_arrays(ey,ei)
def heldout(field,rung,seed):
    complete=observability_field(field); o=regime.obs.observe(complete,N); c=regime.obs.matched_controls(complete,N,CONTROL_SEED+seed+rung*10); sh=regime.obs.observe(c["shuffle"],N); ph=regime.obs.observe(c["phase"],N); h=o["helix"]
    return {"H_axis":h["axis"],"H_mode":h["mode"],"H_best":h["best"],"H_shuffle_best":sh["helix"]["best"],"H_phase_best":ph["helix"]["best"],"J_proxy_rms":o["current"]["rms"]}
def run_arm(client,seed,seed_index,arm,model,baseline_digest=None):
    validate(client.request({"cmd":"clear"}),"clear"); validate(client.request({"cmd":"ping"}),"ping",0,0.0); ic=regime.obs.make_ic(seed,10)
    for d in ic: validate(client.request({"cmd":"deposit",**d}),"deposit")
    validate(client.request({"cmd":"step","n":1}),"step",1,regime.DT); raw0=client.request({"cmd":"readout"}); validate(raw0,"readout",1,regime.DT); field=decode_identity(raw0); power,_=finite_safety(field,float(np.max(field["ey"]**2+field["ei"]**2))); digest=sha_bytes(np.asarray(field["ey"],dtype="<f4").tobytes()+np.asarray(field["ei"],dtype="<f4").tobytes())
    if baseline_digest is not None and digest!=baseline_digest: raise ValueError("baseline digest")
    baseline=float(np.max(power)); previous=None; rows=[]; actions=[]; total=0.; rng=np.random.default_rng(CONTROL_SEED+seed_index)
    for rung,tau in enumerate(CADENCE):
        pre=1+sum(CADENCE[:rung]); raw=client.request({"cmd":"readout"}); validate(raw,"readout",pre,regime.DT*pre); field=decode_identity(raw); finite_safety(field,baseline); project=client.request({"cmd":"project","k":8}); validate(project,"project",pre,regime.DT*pre); cells=project.get("cells",[])
        if len(cells)!=8: raise ValueError("project count")
        payload=[regime.cell_payload(c,field,i) for i,c in enumerate(cells)]; indices=np.asarray([int(c["i"]) for c in cells],np.int64)
        if len(set(indices.tolist()))!=8: raise ValueError("indices")
        features,previous_now=regime.feature_row(field,indices,rung,previous); rec,z=choose(features,model); probs=stable_probs(z)
        if arm=="D": ac,mult=None,0.;
        elif arm=="A": ac,mult=1,1.;
        elif arm=="M": ac,mult=2,1.5
        elif arm=="P": ac,mult=rec,float(regime.CANDIDATES[rec])
        elif arm=="R": ac=int(rng.integers(3)); mult=float(regime.CANDIDATES[ac])
        else: raise ValueError("arm")
        deposits=regime.deposits(field,cells,mult) if mult else []; charge=sum(abs(float(d["cy"]))+abs(float(d["ci"])) for d in deposits)
        if (arm=="D" and deposits) or (arm!="D" and len(deposits)!=8) or not math.isfinite(charge) or charge>regime.BUDGET+1e-12: raise ValueError("charge/deposit")
        for d,c in zip(deposits,cells): validate_deposit(d,c,float(field["eps"][int(c["i"])])); validate(client.request({"cmd":"deposit",**d}),"deposit")
        post=pre+tau; validate(client.request({"cmd":"step","n":tau}),"step",post,regime.DT*post); postraw=client.request({"cmd":"readout"}); validate(postraw,"readout",post,regime.DT*post); after=decode_identity(postraw); pp,qi=finite_safety(after,baseline); total+=charge; actions.append(float(mult)); diag=heldout(after,rung,seed)
        rows.append({"rung":rung,"features":np.asarray(features).tolist(),"P_logits":z.tolist(),"P_probabilities":probs.tolist(),"P_class":rec,"action_class":ac,"multiplier":float(mult),"charge":charge,"cumulative_charge":total,"cy_total":sum(float(d["cy"]) for d in deposits),"ci_total":sum(float(d["ci"]) for d in deposits),"indices":indices.tolist(),"projection_payload":payload,"projection_digest":sha_bytes(canonical(payload)),"pre_step":pre,"pre_t":regime.DT*pre,"post_step":post,"post_t":regime.DT*post,"post_eps_rms":regime.rms(after["eps"]),"qi_mean":float(np.mean(qi)),"qi_min":float(np.min(qi)),"qi_max":float(np.max(qi)),"P_min":float(np.min(pp)),"P_mean":float(np.mean(pp)),"P_rms":regime.rms(pp),"P_max":float(np.max(pp)),**diag}); previous=previous_now
    return {"seed":seed,"arm":arm,"baseline_digest":digest,"baseline_P_max":baseline,"baseline_projection_digest":rows[0]["projection_digest"],"rungs":rows,"actions":actions,"total_charge":total,"endpoint_eps_rms":rows[-1]["post_eps_rms"],"mean_post_eps_rms":float(np.mean([r["post_eps_rms"] for r in rows])),"safe":True,"model_sha256":MODEL_SHA256,"protocol":PROTOCOL,"source_hashes":source_hashes()}
def _finite_json(v):
    try: json.dumps(v,allow_nan=False); return True
    except (TypeError,ValueError): return False
def expected_receipt():
    result,_,_=load_frozen(); src=source_hashes(); return {"protocol":PROTOCOL,"official_result_sha256":sha_bytes(REGIME_RESULT.read_bytes()),"official_manifest_sha256":sha_bytes(REGIME_MANIFEST.read_bytes()),"live_prereg_sha256":src["prereg"],"model_sha256":MODEL_SHA256,"source_hashes_before":src,"source_hashes_after":src,"seeds":LIVE_SEEDS,"arms":ARM_NAMES,"grid_n":N,"cadence":list(CADENCE),"candidates":regime.CANDIDATES.tolist(),"constants":{"phi":regime.PHI,"dt":regime.DT,"omega2":regime.OMEGA2,"extent":list(regime.EXTENT),"source_strength":regime.SOURCE_STRENGTH,"ham_completion":0.,"sigma":1.,"analytic_strength":regime.ANALYTIC_STRENGTH,"budget":regime.BUDGET,"project_k":8},"ic":"balance_spiral_observability.make_ic(seed,10)","rng":"default_rng(2026081701+seed_index)"}
def payload_ok(payload,indices):
    try:
        if not isinstance(payload,list) or len(payload)!=8 or len(set(int(p[1]) for p in payload))!=8:return False
        got=[]
        for rank,p in enumerate(payload):
            if not isinstance(p,list) or len(p)!=11 or p[0]!=rank:return False
            _,i,gx,gy,gz,x,y,z,ey,ei,q=p
            if any(isinstance(a,bool) or not isinstance(a,int) for a in (i,gx,gy,gz)) or i!=regime.projection_index(gx,gy,gz) or not all(0<=a<N for a in (gx,gy,gz)) or not all(math.isfinite(float(a)) for a in (x,y,z,ey,ei,q)) or not math.isclose(float(q),float(np.float32(ey)**2+np.float32(ei)**2),abs_tol=1e-6):return False
            got.append(i)
        return got==[int(x) for x in indices]
    except Exception:return False
def tree(rows,receipt):
    try:
        expected=expected_receipt()
        if any(receipt.get(k)!=v for k,v in expected.items()) or len(rows)!=3 or [x.get("seed") for x in rows]!=LIVE_SEEDS:return {"verdict":"INVALID—STOP"}
        for sr in rows:
            if set(sr)!=set(ARM_NAMES)|{"seed"}:return {"verdict":"INVALID—STOP"}
            vals=[sr[a] for a in ARM_NAMES]
            if len({v["baseline_digest"] for v in vals})!=1 or len({v["baseline_projection_digest"] for v in vals})!=1 or any(v["baseline_projection_digest"]!=v["rungs"][0].get("projection_digest") for v in vals):return {"verdict":"INVALID—STOP"}
            for arm,v in zip(ARM_NAMES,vals):
                if v.get("safe") is not True or v.get("protocol")!=PROTOCOL or v.get("seed")!=sr["seed"] or v.get("arm")!=arm or v.get("model_sha256")!=MODEL_SHA256 or v.get("source_hashes")!=expected["source_hashes_before"] or len(v.get("rungs",[]))!=8 or len(v.get("actions",[]))!=8 or isinstance(v.get("baseline_P_max"),bool) or not isinstance(v.get("baseline_P_max"),(int,float)) or not math.isfinite(float(v["baseline_P_max"])) or v["baseline_P_max"]<0:return {"verdict":"INVALID—STOP"}
                cumulative=0.; eps=[]
                for i,r in enumerate(v["rungs"]):
                    if not _finite_json(r) or r.get("rung")!=i or r.get("multiplier") not in {"D":{0.},"A":{1.},"M":{1.5},"P":{.5,1.,1.5},"R":{.5,1.,1.5}}[arm] or v["actions"][i]!=r["multiplier"]:return {"verdict":"INVALID—STOP"}
                    if not isinstance(r.get("P_class"),int) or isinstance(r["P_class"],bool) or not 0<=r["P_class"]<3:return {"verdict":"INVALID—STOP"}
                    z=np.asarray(r.get("P_logits"),float); p=np.asarray(r.get("P_probabilities"),float)
                    if z.shape!=(3,) or p.shape!=(3,) or not np.isfinite(z).all() or not np.isfinite(p).all() or not np.allclose(p,stable_probs(z),atol=1e-12) or int(r["P_class"])!=int(np.argmax(z)):return {"verdict":"INVALID—STOP"}
                    ac=r.get("action_class"); expected_ac=None if arm=="D" else 1 if arm=="A" else 2 if arm=="M" else int(r["P_class"]) if arm=="P" else int(np.random.default_rng(CONTROL_SEED+LIVE_SEEDS.index(sr["seed"])).integers(3,size=i+1)[-1])
                    if ac is not None and (isinstance(ac,bool) or not isinstance(ac,int) or not 0<=ac<3):return {"verdict":"INVALID—STOP"}
                    if ac!=expected_ac or (ac is None and r["multiplier"]!=0.) or (ac is not None and r["multiplier"]!=float(regime.CANDIDATES[ac])):return {"verdict":"INVALID—STOP"}
                    charge,cum=r.get("charge"),r.get("cumulative_charge")
                    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(float(x)) for x in (charge,cum)) or charge<0 or charge>regime.BUDGET+1e-12 or not math.isclose(cum,cumulative+charge,abs_tol=1e-12):return {"verdict":"INVALID—STOP"}
                    cumulative=cum; pre=1+sum(CADENCE[:i]); post=pre+CADENCE[i]
                    if any(isinstance(r.get(k),bool) or not isinstance(r.get(k),int) or r[k]!=x for k,x in (("pre_step",pre),("post_step",post))) or any(isinstance(r.get(k),bool) or not isinstance(r.get(k),(int,float)) or not math.isfinite(float(r[k])) for k in ("pre_t","post_t")) or not math.isclose(r["pre_t"],regime.DT*pre,abs_tol=1e-12) or not math.isclose(r["post_t"],regime.DT*post,abs_tol=1e-12):return {"verdict":"INVALID—STOP"}
                    if not payload_ok(r.get("projection_payload"),r.get("indices",[])) or sha_bytes(canonical(r["projection_payload"]))!=r.get("projection_digest"):return {"verdict":"INVALID—STOP"}
                    keys=("qi_mean","qi_min","qi_max","P_min","P_mean","P_rms","P_max","post_eps_rms","H_axis","H_mode","H_best","H_shuffle_best","H_phase_best","J_proxy_rms")
                    if any(isinstance(r.get(k),bool) or not isinstance(r.get(k),(int,float)) or not math.isfinite(float(r[k])) for k in keys):return {"verdict":"INVALID—STOP"}
                    tol=1e-12
                    if not(r["qi_min"]>=-1e-7 and r["qi_max"]<=1+1e-7 and r["qi_min"]<=r["qi_mean"]+tol and r["qi_mean"]<=r["qi_max"]+tol) or r["P_min"]<0 or r["P_mean"]<0 or r["P_rms"]<0 or r["P_max"]<0 or r["P_min"]>r["P_mean"]+tol or r["P_mean"]>r["P_max"]+tol or r["P_rms"]>r["P_max"]+tol or r["post_eps_rms"]<0 or (v["baseline_P_max"]==0 and r["P_max"]>0) or (v["baseline_P_max"]>0 and r["P_max"]>100*v["baseline_P_max"]):return {"verdict":"INVALID—STOP"}
                    eps.append(r["post_eps_rms"])
                if not math.isclose(v["total_charge"],cumulative,abs_tol=1e-12) or not math.isclose(v["endpoint_eps_rms"],eps[-1],abs_tol=1e-12) or not math.isclose(v["mean_post_eps_rms"],float(np.mean(eps)),abs_tol=1e-12):return {"verdict":"INVALID—STOP"}
        if all(x["P"]["actions"]==x["M"]["actions"] for x in rows):return {"verdict":"COLLAPSES TO MAJORITY"}
        pd=sum(x["P"]["endpoint_eps_rms"]<x["D"]["endpoint_eps_rms"] for x in rows); wins=[x for x in rows if x["P"]["endpoint_eps_rms"]<x["M"]["endpoint_eps_rms"]]; pm=len(wins); pa=sum(x["P"]["endpoint_eps_rms"]<x["A"]["endpoint_eps_rms"] for x in rows)
        if pd>=2 and pm>=2 and all(x["P"]["mean_post_eps_rms"]<=x["M"]["mean_post_eps_rms"] for x in wins):return {"verdict":"ADOPT","p_beats_D":pd,"p_beats_M":pm,"p_beats_A":pa}
        if pd>=2 and pa>=2:return {"verdict":"REDISCOVERS HIGH GAIN","p_beats_D":pd,"p_beats_M":pm,"p_beats_A":pa}
        if pd<2:return {"verdict":"REJECT","p_beats_D":pd,"p_beats_M":pm,"p_beats_A":pa}
        return {"verdict":"HOLD/INCONCLUSIVE","p_beats_D":pd,"p_beats_M":pm,"p_beats_A":pa}
    except Exception:return {"verdict":"INVALID—STOP"}
def self_test():
    probe=observability_field({"ey":np.full(8,.25),"ei":np.full(8,.5)})
    assert set(probe)=={"ey","ei","field_power","eps","rho","qi_coherence","theta"} and all(np.isfinite(np.asarray(probe[k],float)).all() for k in probe)
    result, _, model = load_frozen()
    check_scene(ROOT)
    assert model_hash(result) == MODEL_SHA256

    class Fake:
        calls = 0
        last = None
        def __init__(self):
            self.step = 0
            self.t = 0.0
            self.deposits = []
            self.steps = []
            self.closed = False
            Fake.last = self
        def request(self, msg):
            Fake.calls += 1
            cmd = msg["cmd"]
            if cmd == "clear":
                self.step = 0; self.t = 0.0; self.deposits = []; self.steps = []
                return {"ok": True, "cmd": "clear"}
            if cmd == "ping":
                return {"ok": True, "cmd": "ping", "step": self.step, "t": self.t}
            if cmd == "deposit":
                self.deposits.append(msg); return {"ok": True, "cmd": "deposit"}
            if cmd == "step":
                self.steps.append(msg["n"]); self.step += int(msg["n"]); self.t = regime.DT * self.step
                return {"ok": True, "cmd": "step", "step": self.step, "t": self.t}
            if cmd == "readout":
                z = np.zeros(N ** 3, dtype="<f4")
                b = base64.b64encode(z.tobytes()).decode()
                return {"ok": True, "cmd": "readout", "step": self.step, "t": self.t,
                        "ey_b64": b, "ei_b64": b, "q_b64": b, "eps2_b64": b}
            if cmd == "project":
                return {"ok": True, "cmd": "project", "step": self.step, "t": self.t,
                        "cells": [{"i": regime.projection_index(i, 0, 0), "gx": i, "gy": 0,
                                   "gz": 0, "x": 2 * i / (N - 1) - 1, "y": -1., "z": -1., "q": 0.}
                                  for i in range(8)]}
            raise AssertionError(cmd)
        def close(self):
            self.closed = True

    original = (regime.obs.make_ic, regime.decode, regime.feature_row, regime.deposits,
                regime.cell_payload, globals()["heldout"])

    def patch_helpers(held=None):
        regime.obs.make_ic = lambda seed, count: [{"x": 0., "y": 0., "z": 0., "cy": 0., "ci": 0., "sigma": 1.} for _ in range(10)]
        regime.decode = lambda raw, n: {"ey": np.ones(n ** 3), "ei": np.ones(n ** 3), "eps": np.zeros(n ** 3), "rho": np.ones(n ** 3), "field_power": np.zeros(n ** 3)}
        regime.feature_row = lambda *args: (np.zeros(30), {})
        regime.cell_payload = lambda c, f, rank: [rank, int(c["i"]), int(c["gx"]), int(c["gy"]), int(c["gz"]), float(c["x"]), float(c["y"]), float(c["z"]), 1., 1., 2.]
        regime.deposits = lambda f, cells, mult: [{"x": c["x"], "y": c["y"], "z": c["z"], "cy": 0., "ci": .01 * mult, "sigma": 1.} for c in cells] if mult else []
        globals()["heldout"] = held or (lambda *args: {"H_axis": 0, "H_mode": 0, "H_best": 0., "H_shuffle_best": 0., "H_phase_best": 0., "J_proxy_rms": 0.})

    try:
        patch_helpers()
        baseline = None
        retained = {}
        for arm_name in ARM_NAMES:
            fake = Fake()
            retained[arm_name] = fake
            record = run_arm(fake, LIVE_SEEDS[0], 0, arm_name, model, baseline if arm_name != "D" else None)
            if arm_name == "D":
                baseline = record["baseline_digest"]
            assert fake.steps == [1, *CADENCE]
            assert len(fake.deposits) == (10 if arm_name == "D" else 74)
            assert len(record["rungs"]) == len(record["actions"]) == 8
            assert record["actions"] == [r["multiplier"] for r in record["rungs"]]
            assert all(np.isclose(r["cumulative_charge"], sum(x["charge"] for x in record["rungs"][:i + 1])) for i, r in enumerate(record["rungs"]))
        expected_r = [float(regime.CANDIDATES[i]) for i in np.random.default_rng(CONTROL_SEED).integers(3, size=8)]
        assert run_arm(Fake(), LIVE_SEEDS[0], 0, "R", model, baseline)["actions"] == expected_r
        held_a = lambda *args: {"H_axis": 1, "H_mode": 2, "H_best": 3., "H_shuffle_best": 4., "H_phase_best": 5., "J_proxy_rms": 6.}
        held_b = lambda *args: {"H_axis": 91, "H_mode": 92, "H_best": 93., "H_shuffle_best": 94., "H_phase_best": 95., "J_proxy_rms": 96.}
        globals()["heldout"] = held_a
        p1 = run_arm(Fake(), LIVE_SEEDS[0], 0, "P", model, baseline)
        globals()["heldout"] = held_b
        p2 = run_arm(Fake(), LIVE_SEEDS[0], 0, "P", model, baseline)
        assert p1["actions"] == p2["actions"]
        assert [r["P_logits"] for r in p1["rungs"]] == [r["P_logits"] for r in p2["rungs"]]
        assert [r["P_class"] for r in p1["rungs"]] == [r["P_class"] for r in p2["rungs"]]
    finally:
        regime.obs.make_ic, regime.decode, regime.feature_row, regime.deposits, regime.cell_payload, globals()["heldout"] = original

    def raises(fn):
        try:
            fn()
        except (AssertionError, ValueError):
            return
        raise AssertionError("expected rejection")

    raises(lambda: validate({"ok": True, "cmd": "x", "step": True}, "x", 1, None))
    raises(lambda: validate({"ok": True, "cmd": "x", "step": 1.5}, "x", 1, None))
    raises(lambda: validate({"ok": True, "cmd": "x", "step": 1, "t": math.nan}, "x", 1, 0.0))
    raises(lambda: validate({"ok": True, "cmd": "x", "step": 1, "t": 0.2}, "x", 1, 0.1))
    safe_field = {"ey": np.ones(8), "ei": np.ones(8), "eps": np.zeros(8), "rho": np.ones(8)}
    finite_safety(safe_field, 2.)
    raises(lambda: finite_safety({**safe_field, "ey": np.full(8, np.nan)}, 2.))
    raises(lambda: finite_safety({**safe_field, "ey": np.full(8, 11.)}, 1.0))

    receipt = expected_receipt()
    def arm(seed, name, end, mean, actions):
        payload = [[r, regime.projection_index(r, 0, 0), r, 0, 0, 2 * r / (N - 1) - 1, -1., -1., 0., 0., 0.] for r in range(8)]
        rows = []
        for i, action in enumerate(actions):
            action_class = None if name == "D" else int(np.flatnonzero(regime.CANDIDATES == action)[0])
            rows.append({"rung": i, "features": [0.] * 30, "P_logits": [0., 0., 0.], "P_probabilities": [1 / 3] * 3, "P_class": 0, "action_class": action_class, "multiplier": action, "charge": 0., "cumulative_charge": 0., "pre_step": 1 + sum(CADENCE[:i]), "post_step": 1 + sum(CADENCE[:i + 1]), "pre_t": regime.DT * (1 + sum(CADENCE[:i])), "post_t": regime.DT * (1 + sum(CADENCE[:i + 1])), "post_eps_rms": ((8 * mean - end) / 7 if i < 7 else end), "indices": [regime.projection_index(r, 0, 0) for r in range(8)], "projection_payload": payload, "projection_digest": sha_bytes(canonical(payload)), "qi_mean": 0., "qi_min": 0., "qi_max": 0., "P_min": 0., "P_mean": 0., "P_rms": 0., "P_max": 0., "H_axis": 0, "H_mode": 0, "H_best": 0., "H_shuffle_best": 0., "H_phase_best": 0., "J_proxy_rms": 0.})
        return {"seed": seed, "arm": name, "baseline_digest": "b", "baseline_projection_digest": rows[0]["projection_digest"], "baseline_P_max": 0., "rungs": rows, "actions": list(actions), "total_charge": 0., "endpoint_eps_rms": end, "mean_post_eps_rms": mean, "safe": True, "model_sha256": MODEL_SHA256, "protocol": PROTOCOL, "source_hashes": source_hashes()}

    def fixture(kind):
        values = {"adopt": (.5, .5, 1., 1., 1.), "rediscover": (.5, 1.5, 1., 1., 1.), "reject": (1., 1., 1., 1., 1.), "hold": (.5, 2., 1., 1., .4)}[kind]
        out = []
        for seed in LIVE_SEEDS:
            rr = [float(regime.CANDIDATES[i]) for i in np.random.default_rng(CONTROL_SEED + LIVE_SEEDS.index(seed)).integers(3, size=8)]
            p, pm, d, m, a = values
            out.append({"seed": seed, "D": arm(seed, "D", d, 1., [0.] * 8), "A": arm(seed, "A", a, 1., [1.] * 8), "M": arm(seed, "M", m, 1., [1.5] * 8), "P": arm(seed, "P", p, pm, [.5] * 8), "R": arm(seed, "R", 1., 1., rr)})
        return out

    for kind, verdict in {"adopt": "ADOPT", "rediscover": "REDISCOVERS HIGH GAIN", "reject": "REJECT", "hold": "HOLD/INCONCLUSIVE"}.items():
        assert tree(fixture(kind), receipt)["verdict"] == verdict
    collapse = fixture("adopt")
    for seed_row in collapse:
        seed_row["P"]["actions"] = seed_row["M"]["actions"][:]
        for row in seed_row["P"]["rungs"]:
            row.update({"multiplier": 1.5, "action_class": 2, "P_class": 2, "P_logits": [0., 0., 1.], "P_probabilities": stable_probs([0., 0., 1.]).tolist()})
    assert tree(collapse, receipt)["verdict"] == "COLLAPSES TO MAJORITY"

    valid = fixture("adopt")
    mutations = []
    def mutate(label, fn):
        candidate = deepcopy(valid); fn(candidate); mutations.append(label); assert tree(candidate, receipt)["verdict"] == "INVALID—STOP"
    cases = [
        ("model/source/protocol", lambda x: x[0]["P"].__setitem__("model_sha256", "x")),
        ("action/R", lambda x: x[0]["R"]["actions"].__setitem__(0, 1.)),
        ("step/time", lambda x: x[0]["P"]["rungs"][0].__setitem__("pre_step", 1.5)),
        ("endpoint/mean", lambda x: x[0]["P"].__setitem__("endpoint_eps_rms", 9.)),
        ("integrated mean", lambda x: x[0]["P"].__setitem__("mean_post_eps_rms", 9.)),
        ("charge/cumulative", lambda x: x[0]["P"]["rungs"][0].__setitem__("charge", 1.)),
        ("payload q", lambda x: (x[0]["P"]["rungs"][0]["projection_payload"][0].__setitem__(10, 1), x[0]["P"]["rungs"][0].__setitem__("projection_digest", sha_bytes(canonical(x[0]["P"]["rungs"][0]["projection_payload"]))))),
        ("payload index", lambda x: (x[0]["P"]["rungs"][0]["projection_payload"][0].__setitem__(1, 1.5), x[0]["P"]["rungs"][0].__setitem__("projection_digest", sha_bytes(canonical(x[0]["P"]["rungs"][0]["projection_payload"]))))),
        ("baseline projection", lambda x: x[0]["P"].__setitem__("baseline_projection_digest", "x")),
        ("qi/positive 100x", lambda x: (x[0]["P"]["rungs"][0].__setitem__("qi_max", 2.), x[0]["P"].__setitem__("baseline_P_max", 1.), x[0]["P"]["rungs"][0].__setitem__("P_max", 101.))),
        ("missing heldout", lambda x: x[0]["P"]["rungs"][0].pop("H_best")),
        ("nonfinite", lambda x: x[0]["P"]["rungs"][0].__setitem__("post_t", math.nan)),
    ]
    for label, fn in cases: mutate(label, fn)
    bad = deepcopy(receipt); bad["official_result_sha256"] = "x"; assert tree(valid, bad)["verdict"] == "INVALID—STOP"
    bad = deepcopy(receipt); bad["source_hashes_before"] = dict(bad["source_hashes_before"]); bad["source_hashes_before"]["live_tool"] = "x"; assert tree(valid, bad)["verdict"] == "INVALID—STOP"
    assert len(mutations) == len(cases) == 12
    held = deepcopy(valid); held[0]["P"]["rungs"][0]["H_best"] = 99.; assert tree(held, receipt)["verdict"] == "ADOPT"

    collect_files = []
    with TemporaryDirectory() as td:
        old_out, old_bridge = OUT, regime.obs.BridgeClient
        client_box = {}
        try:
            globals()["OUT"] = Path(td); patch_helpers(); client_box["client"] = Fake(); regime.obs.BridgeClient = lambda *args: client_box["client"]
            collected = collect(SimpleNamespace(grid_n=N, host="127.0.0.1", port=7599, timeout=1, all=False))
            assert client_box["client"].closed, "client not closed"
            if collected["decision"]["verdict"] == "INVALID—STOP":
                expected_check = expected_receipt()
                receipt_diff = {k: (collected["manifest"].get(k), expected_check.get(k)) for k in expected_check if collected["manifest"].get(k) != expected_check.get(k)}
                raise AssertionError({"decision": collected["decision"], "manifest_diff": receipt_diff, "tree": tree(collected["seeds"], collected["manifest"])})
            assert all(collected["gates"].values()), collected["gates"]
            assert len(collected["seeds"]) == 3 and all(len(s) == 6 and all(len(s[a]["rungs"]) == 8 for a in ARM_NAMES) for s in collected["seeds"])
            collect_files = sorted(p.name for p in Path(td).iterdir()); assert collect_files == ["manifest.json", "raw.json", "result.json", "summary.json"]
            for path in Path(td).iterdir(): assert path.read_bytes() == canonical(json.loads(path.read_bytes()))
            raw = json.loads((Path(td) / "raw.json").read_bytes()); assert raw["receipt_sha256"] == sha_bytes(canonical(raw["receipt"]))
            manifest = json.loads((Path(td) / "manifest.json").read_bytes()); check = dict(manifest); check["final_manifest_sha256"] = None; assert manifest["final_manifest_sha256"] == sha_bytes(canonical(check)); assert json.loads((Path(td) / "result.json").read_bytes())["manifest"] == manifest
        finally:
            globals()["OUT"] = old_out; regime.obs.BridgeClient = old_bridge
            regime.obs.make_ic, regime.decode, regime.feature_row, regime.deposits, regime.cell_payload, globals()["heldout"] = original
    return {"status": "PASS", "checks": ["A-G executable assertions"], "fake_call_counts": Fake.calls, "invalid_mutation_count": len(mutations), "collect_files": collect_files}

def collect(args):
    if args.grid_n!=N:raise ValueError("grid_n")
    result,_,model=load_frozen(); check_scene(ROOT); before=source_hashes(); receipt=expected_receipt(); pre={**receipt,"source_hashes_after":None,"model_record":model_record(result),"precollection":True}; pre_bytes=canonical(pre); OUT.mkdir(parents=True,exist_ok=True); (OUT/"manifest.json").write_bytes(pre_bytes); client=regime.obs.BridgeClient(args.host,args.port,args.timeout); rows=[]
    try:
        validate(client.request({"cmd":"ping"}),"ping",0,0.); 
        for si,seed in enumerate(LIVE_SEEDS):
            sr={}; digest=None
            for arm in ARM_NAMES:sr[arm]=run_arm(client,seed,si,arm,model,digest);digest=sr[arm]["baseline_digest"]
            sr["seed"]=seed;rows.append(sr)
    finally:client.close()
    after=source_hashes();
    if after!=before:raise ValueError("source changed")
    raw={"protocol":PROTOCOL,"receipt":receipt,"receipt_sha256":sha_bytes(canonical(receipt)),"seeds":rows}; raw_bytes=canonical(raw);(OUT/"raw.json").write_bytes(raw_bytes)
    final={**receipt,"source_hashes_after":after,"model_record":model_record(result),"precollection_manifest_sha256":sha_bytes(pre_bytes),"raw_sha256":sha_bytes(raw_bytes),"final_manifest_sha256":None}; final_bytes=canonical(final); final["final_manifest_sha256"]=sha_bytes(final_bytes); final_bytes=canonical(final); (OUT/"manifest.json").write_bytes(final_bytes)
    decision=tree(rows,final); matched=[{"seed":s["seed"],"actions":{a:s[a]["actions"] for a in ARM_NAMES},"endpoint":{a:s[a]["endpoint_eps_rms"] for a in ARM_NAMES},"integrated":{a:s[a]["mean_post_eps_rms"] for a in ARM_NAMES},"safe":{a:s[a]["safe"] for a in ARM_NAMES}} for s in rows]; gates={"receipt":decision["verdict"]!="INVALID—STOP","safety":all(s[a]["safe"] for s in rows for a in ARM_NAMES),"arms":len(rows)==3 and all(set(s)==set(ARM_NAMES)|{"seed"} for s in rows)}; output={"protocol":PROTOCOL,"manifest":final,"gates":gates,"matched_seeds":matched,"seeds":rows,"decision":decision};(OUT/"result.json").write_bytes(canonical(output)); summary={"protocol":PROTOCOL,"decision":decision,"gates":gates,"matched_seeds":matched};(OUT/"summary.json").write_bytes(canonical(summary));return output
def main():
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");p.add_argument("--collect",action="store_true");p.add_argument("--all",action="store_true");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=7599);p.add_argument("--timeout",type=float,default=300.);p.add_argument("--grid-n",type=int,default=N);a=p.parse_args()
    if a.all:self_test();print(json.dumps(collect(a),indent=2));return 0
    if a.self_test:print(json.dumps(self_test(),indent=2));return 0
    if a.collect:print(json.dumps(collect(a),indent=2));return 0
    raise SystemExit("refusing ambiguous/no-action invocation")
if __name__=="__main__":raise SystemExit(main())
