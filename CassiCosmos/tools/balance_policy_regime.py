#!/usr/bin/env python3
"""Locked low-capacity balance-policy regime archaeology.

Protocol: research/steering/balance_policy_regime_prereg.md.
No prior-wave fitting or decision logic is imported.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, math, sys
from pathlib import Path
from typing import Any
import numpy as np
import balance_spiral_observability as obs

PHI=1.618033988749895; N=32; DT=0.005; OMEGA2=20.0; EXTENT=(1.0,1.0,1.0); SOURCE_STRENGTH=0.0
CADENCE=[1,2,3,4,7,11,18,29]; K=8; BUDGET=0.25; ANALYTIC_STRENGTH=0.25; SUPPORT_FLOOR=1e-6; RATIO_FLOOR=1e-12
CANDIDATES=np.asarray([0.5,1.0,1.5],dtype=np.float64); TRAIN_SEEDS=list(range(20260901,20260909)); VAL_SEEDS=[20260911,20260912]; LIVE_SEEDS=[20260817,20260819,20260821]
FIT_SEED=20260900; PERM_SEED=20260913; EPOCHS=200; LR=0.03; L2=1e-3; PROTOCOL="balance-policy-regime-v1"
FEATURE_NAMES=["active_rho_global","active_rho_projected","support_P","eps_abs_rms","eps_abs_q50","rho_abs_rms","power_rms_global","z_abs_rms","lapEY_abs_rms","lapEI_abs_rms","reaction_abs_rms","lap_reaction_ratio","lap_reaction_zero","reaction_lap_sign_align","grad_eps_rms","grad_rho_rms","lap_eps_abs_rms","J_rms","divJ_rms","J_lap_ratio","axis_grad_anisotropy","axis_lap_anisotropy","P_top8_share","eps_top8_share","P_projected_to_global_rms","cadence_index","cadence_tau","prev_eps_rms_delta","prev_power_rms_delta","history_valid"]
FAMILY_IDS={"REACTION":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,23,24,25],"TRANSPORT":[9,10,11,12,13,15,16,17,18,19,20,21,22],"HISTORY":[26,27,28,29,30],"ALL_NO_TRANSPORT":list(range(1,18))+list(range(23,31)),"ALL":list(range(1,31))}

def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
def hbytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def hobj(x:Any)->str:return hbytes(canon(x))
def projection_index(gx:int,gy:int,gz:int,n:int=N)->int:return gx*n*n+gy*n+gz
def root_path()->Path:return Path(__file__).resolve().parents[1]
def source_paths()->list[Path]:return [Path("tools/balance_policy_regime.py"),Path("tools/balance_spiral_observability.py"),Path("scripts/cassi_mind_engine.gd"),Path("compute/cassi_two_fluid.glsl")]
def source_hashes()->dict[str,str]:return {p.as_posix():hbytes((root_path()/p).read_bytes()) for p in source_paths()}

def feature_manifest():
    formulas=["mean(abs(rho)>0)","mean(abs(rho_proj)>0)","mean(P>1e-6*max(P)); zero max => 0","sqrt(mean(epsilon_proj^2))","Q0.50(abs(epsilon_proj))","sqrt(mean(rho_proj^2))","sqrt(mean(P_global^2))","sqrt(mean((epsilon_proj/(abs(rho_proj)+phi^-1))^2))","sqrt(mean(lapEY_proj^2))","sqrt(mean(lapEI_proj^2))","sqrt(mean((20*epsilon_proj)^2))","(lapEY_abs_rms+lapEI_abs_rms)/reaction_abs_rms if reaction_abs_rms>1e-12 else 0","int(reaction_abs_rms<=1e-12)","mean((sign((-20*epsilon_proj)*lapEY_proj)+sign((20*epsilon_proj)*lapEI_proj))>0)","sqrt(mean_targets(sum_axis(centered_gradient(epsilon)^2)))","sqrt(mean_targets(sum_axis(centered_gradient(rho)^2)))","sqrt(mean(lap19(epsilon)_proj^2))","sqrt(mean(sum(J_proxy_proj^2)))","sqrt(mean(div_periodic(J_proxy)_proj^2))","J_rms/(lapEY_abs_rms+lapEI_abs_rms) if denom>1e-12 else 0","max(axis_grad_rms)/(mean(axis_grad_rms)+1e-12), all-zero=>0","max(axis_lap_rms)/(mean(axis_lap_rms)+1e-12), all-zero=>0","sum(P_proj)/sum(P_global) if denom>1e-12 else 0","sum(abs(epsilon_proj))/sum(abs(epsilon_global)) if denom>1e-12 else 0","RMS(P_proj)/RMS(P_global) if denom>1e-12 else 0","rung/7","tau/29","eps_abs_rms-previous_eps_abs_rms; first=0","power_rms_global-previous_power_rms_global; first=0","int(rung>0)"]
    fam=["SUPPORT"]*3+["BALANCE"]*5+["REACTION_OPERATOR"]*6+["GRADIENT"]*3+["TRANSPORT"]*5+["CONCENTRATION"]*3+["HISTORY"]*5
    cls=["exact readout algebra"]*8+["exact reconstructed operator"]*6+["deterministic stencil proxy","deterministic stencil proxy","exact reconstructed stencil","deterministic current proxy","deterministic current proxy","deterministic current proxy","deterministic morphology proxy","deterministic morphology proxy","exact readout algebra","exact readout algebra","exact readout algebra","exact protocol covariate","exact protocol covariate","readout-history proxy","readout-history proxy","exact protocol/history flag"]
    agg=["global mean","8-cell mean","global mean","8-cell RMS","8-cell Q0.50","8-cell RMS","global RMS","8-cell RMS","8-cell RMS","8-cell RMS","8-cell RMS","8-cell ratio","8-cell flag","8-cell mean","8-target RMS","8-target RMS","8-cell RMS","8-cell RMS","8-cell RMS","8-cell ratio","8-target axis ratio","8-target axis ratio","projected/global sum","projected/global sum","projected/global RMS","scalar","scalar","scalar","scalar","scalar"]
    return [{"id":f"F{i:02d}","name":FEATURE_NAMES[i-1],"formula":formulas[i-1],"family":fam[i-1],"class":cls[i-1],"aggregation":agg[i-1]} for i in range(1,31)]
def partition_obj():return {"train":TRAIN_SEEDS,"validation":VAL_SEEDS,"live":LIVE_SEEDS}
def make_manifest():
    fm=feature_manifest(); before=source_hashes()
    return {"protocol":PROTOCOL,"scene":"scenes/mind_engine_cache.tscn","grid_n":N,"grid_order":"x-major i+N*(j+N*k), C-order reshape [x,y,z]","extent":list(EXTENT),"phi":PHI,"dt":DT,"omega2":OMEGA2,"source_strength":SOURCE_STRENGTH,"ham_completion":0.0,"cadence":CADENCE,"project_k":K,"budget":BUDGET,"analytic_strength":ANALYTIC_STRENGTH,"sigma":1.0,"candidates":CANDIDATES.tolist(),"support_floor":SUPPORT_FLOOR,"ratio_floor":RATIO_FLOOR,"quantiles":[0.25,0.50,0.75],"quantile_method":"linear","tie_rule":"lower multiplier; class order 0.5,1.0,1.5; first argmax","features":fm,"families":FAMILY_IDS,"train_seeds":TRAIN_SEEDS,"validation_seeds":VAL_SEEDS,"live_seeds":LIVE_SEEDS,"fit_seed":FIT_SEED,"permutation_seed":PERM_SEED,"optimizer":{"epochs":EPOCHS,"lr":LR,"l2":L2,"beta1":0.9,"beta2":0.999,"eps":1e-8,"intercept":"unstandardized/unpenalized","checkpoint":"final update"},"projection_scatter_note":"projection uses N-1 endpoints; scatter uses N/2; projection indices/coords authoritative","source_paths":[p.as_posix() for p in source_paths()],"source_hashes_before":before,"partition_hash":hobj(partition_obj()),"feature_manifest_hash":hobj(fm)}

def lap_coeffs():
    hs=[2*e/N for e in EXTENT];h0=2*min(EXTENT)/N;h2=[h*h for h in hs];h02=h0*h0
    bxy=(1/3)*h02/(h2[0]+h2[1]);bxz=(1/3)*h02/(h2[0]+h2[2]);byz=(1/3)*h02/(h2[1]+h2[2])
    return hs,(h02/h2[0]-2*(bxy+bxz),h02/h2[1]-2*(bxy+byz),h02/h2[2]-2*(bxz+byz)),(bxy,bxz,byz)
def lap19(field):
    a=np.asarray(field,dtype=np.float64).reshape((N,N,N),order="C");hs,aa,b=lap_coeffs();ax,ay,az=aa;bxy,bxz,byz=b
    o=ax*(np.roll(a,-1,0)+np.roll(a,1,0)-2*a)+ay*(np.roll(a,-1,1)+np.roll(a,1,1)-2*a)+az*(np.roll(a,-1,2)+np.roll(a,1,2)-2*a)
    o+=bxy*(np.roll(np.roll(a,-1,0),-1,1)+np.roll(np.roll(a,1,0),-1,1)+np.roll(np.roll(a,-1,0),1,1)+np.roll(np.roll(a,1,0),1,1)-4*a)
    o+=bxz*(np.roll(np.roll(a,-1,0),-1,2)+np.roll(np.roll(a,1,0),-1,2)+np.roll(np.roll(a,-1,0),1,2)+np.roll(np.roll(a,1,0),1,2)-4*a)
    o+=byz*(np.roll(np.roll(a,-1,1),-1,2)+np.roll(np.roll(a,1,1),-1,2)+np.roll(np.roll(a,-1,1),1,2)+np.roll(np.roll(a,1,1),1,2)-4*a)
    return o.ravel(order="C")
def grad(f):
    a=np.asarray(f,dtype=np.float64).reshape((N,N,N),order="C");hs=lap_coeffs()[0]
    return tuple(((np.roll(a,-1,axis=q)-np.roll(a,1,axis=q))*0.5/hs[q]).ravel(order="C") for q in range(3))
def rms(a):a=np.asarray(a,dtype=np.float64);return float(np.sqrt(np.mean(a*a)))
def jproxy(ey,ei):
    gy,gi=grad(ey),grad(ei);return tuple(ey*gi[q]-ei*gy[q] for q in range(3))
def divergence(v):return sum(grad(v[q])[q] for q in range(3))
def q50(a):return float(np.quantile(np.asarray(a,dtype=np.float64),.5,method="linear"))
def axis_values(f,indices,directional):
    a=np.asarray(f,dtype=np.float64).reshape((N,N,N),order="C");hs,aa,_=lap_coeffs();out=[]
    for flat in np.asarray(indices,dtype=int):
        x,rem=divmod(int(flat),N*N);y,z=divmod(rem,N);v=[]
        for q in range(3):
            c=a[:,y,z] if q==0 else a[x,:,z] if q==1 else a[x,y,:];at=(x,y,z)[q]
            v.append(aa[q]*(c[(at+1)%N]+c[(at-1)%N]-2*c[at]) if directional else (c[(at+1)%N]-c[(at-1)%N])*0.5/hs[q])
        out.append(v)
    return np.asarray(out,dtype=np.float64)
def anisotropy(v):
    ar=np.sqrt(np.mean(np.asarray(v,dtype=np.float64)**2,axis=0));return 0.0 if np.all(ar==0) else float(np.max(ar)/(np.mean(ar)+RATIO_FLOOR))

def feature_row(field,indices,rung,previous):
    ey=np.asarray(field["ey"],dtype=np.float64);ei=np.asarray(field["ei"],dtype=np.float64);p=ey*ey+ei*ei;eps=ey-PHI*ei;rho=ey+ei;ep,rp,pp=eps[indices],rho[indices],p[indices]
    ly,li,le=lap19(ey),lap19(ei),lap19(eps);lyp,lip=ly[indices],li[indices];ry,ri=-OMEGA2*ep,OMEGA2*ep;lyr,lir,rr=rms(lyp),rms(lip),rms(ry);ratio=(lyr+lir)/rr if rr>RATIO_FLOOR else 0.;zero=float(rr<=RATIO_FLOOR)
    ge,gr=grad(eps),grad(rho);jp=jproxy(ey,ei);dj=divergence(jp);jr=rms(np.sqrt(sum(v[indices]**2 for v in jp)));djr=rms(dj[indices]);den=lyr+lir;jratio=jr/den if den>RATIO_FLOOR else 0.
    gan=anisotropy(axis_values(eps,indices,False));lan=anisotropy(axis_values(eps,indices,True));ps=float(np.sum(p));es=float(np.sum(np.abs(eps)));er=rms(ep);pr=rms(p);ppr=rms(pp)
    f14=float(np.mean((np.sign((-OMEGA2*ep)*lyp)+np.sign((OMEGA2*ep)*lip))>0.0))
    vals=[float(np.mean(np.abs(rho)>0)),float(np.mean(np.abs(rp)>0)),float(np.mean(p>SUPPORT_FLOOR*np.max(p))) if np.max(p)>0 else 0.,er,q50(np.abs(ep)),rms(rp),pr,rms(ep/(np.abs(rp)+PHI**-1)),lyr,lir,rr,ratio,zero,f14,rms(np.sqrt(sum(v[indices]**2 for v in ge))),rms(np.sqrt(sum(v[indices]**2 for v in gr))),rms(le[indices]),jr,djr,jratio,gan,lan,float(np.sum(pp)/ps) if ps>RATIO_FLOOR else 0.,float(np.sum(np.abs(ep))/es) if es>RATIO_FLOOR else 0.,float(ppr/pr) if pr>RATIO_FLOOR else 0.,rung/7.,CADENCE[rung]/29.,er-(previous["eps_abs_rms"] if previous else 0.),pr-(previous["power_rms_global"] if previous else 0.),float(rung>0)]
    if len(vals)!=30 or not np.isfinite(vals).all():raise ValueError("nonfinite feature")
    return np.asarray(vals,dtype=np.float64),{"eps_abs_rms":er,"power_rms_global":pr}

def analytic_magnitude(e):return ANALYTIC_STRENGTH*np.abs(e)/(1+np.abs(e))/8
def normalize(ds):
    c=sum(abs(d["cy"])+abs(d["ci"]) for d in ds)
    if c<=BUDGET or c==0:return ds
    s=BUDGET/c;return [{**d,"cy":d["cy"]*s,"ci":d["ci"]*s} for d in ds]
def deposits(field,cells,mult):
    ep=np.asarray([field["eps"][int(c["i"])] for c in cells],dtype=np.float64);aa=analytic_magnitude(ep)*mult
    return normalize([{"x":float(c["x"]),"y":float(c["y"]),"z":float(c["z"]),"cy":float(a) if e<0 else 0.,"ci":float(a) if e>=0 else 0.,"sigma":1.} for c,e,a in zip(cells,ep,aa)])
def decode(reply,n=N):
    if reply.get("cmd")!="readout" or int(reply.get("step",-1))<0 or "t" not in reply:raise ValueError("invalid readout envelope")
    f=obs.decode_readout(reply,n);return {"ey":np.asarray(f["ey"],dtype="<f4"),"ei":np.asarray(f["ei"],dtype="<f4"),"eps":np.asarray(f["eps"],dtype=np.float64),"rho":np.asarray(f["rho"],dtype=np.float64),"field_power":np.asarray(f["field_power"],dtype=np.float64),"step":int(reply["step"]),"t":float(reply["t"])}
def validate_envelope(reply,cmd,step=None,t=None):
    if reply.get("cmd")!=cmd or reply.get("ok") is not True or "step" not in reply or "t" not in reply:raise ValueError(f"invalid {cmd} envelope")
    if step is not None and int(reply["step"])!=step:raise ValueError("step mismatch")
    if t is not None and not math.isclose(float(reply["t"]),t,rel_tol=0,abs_tol=1e-9):raise ValueError("time mismatch")
def check_scene(root):
    text=(root/"scenes/mind_engine_cache.tscn").read_text(encoding="utf-8")
    import re
    ext=re.search(r'^\[ext_resource\s+type="Script"\s+path="(res://[^"]+)"\s+id="([^"]+)"\]\s*$',text,re.MULTILINE)
    node=re.search(r'^script\s*=\s*ExtResource\("([^"]+)"\)\s*$',text,re.MULTILINE)
    props={}
    for line in text.splitlines():
        m=re.match(r'^(grid_n|auto_step|bridge_port)\s*=\s*(.+?)\s*$',line.strip())
        if m:props[m.group(1)]=m.group(2).strip().strip('"')
    if not ext or ext.group(1)!="res://scripts/cassi_mind_engine.gd" or not node or node.group(1)!=ext.group(2) or props.get("grid_n")!="32" or props.get("auto_step","").lower()!="false" or props.get("bridge_port")!="7599":
        raise ValueError("pinned scene properties mismatch")
def replay(client,seed,rung,mult,n=N):
    if n!=N:raise ValueError("grid_n must be 32")
    client.request({"cmd":"clear"});pong=client.request({"cmd":"ping"});validate_envelope(pong,"ping",0,0.0)
    for d in obs.make_ic(seed,10):client.request({"cmd":"deposit",**d})
    r=client.request({"cmd":"step","n":1});validate_envelope(r,"step",1,DT)
    prev=None;base=None;selected=None;before=None;branch=None
    for q,tau in enumerate(CADENCE[:rung+1]):
        raw=client.request({"cmd":"readout"});validate_envelope(raw,"readout",1+sum(CADENCE[:q]),DT*(1+sum(CADENCE[:q])));field=decode(raw,n)
        proj=client.request({"cmd":"project","k":K});validate_envelope(proj,"project",field["step"],field["t"]);cells=proj["cells"]
        if len(cells)!=8:raise ValueError("project length")
        inds=np.asarray([int(c["i"]) for c in cells],dtype=np.int64);x,prev_now=feature_row(field,inds,q,prev)
        if q==rung:base=x;selected=cells;before=rms(field["eps"])**2;branch=(field,cells,inds);chosen=mult
        else:chosen=1.
        for d in deposits(field,cells,chosen):client.request({"cmd":"deposit",**d})
        r=client.request({"cmd":"step","n":tau});validate_envelope(r,"step",1+sum(CADENCE[:q+1]),DT*(1+sum(CADENCE[:q+1])));prev=prev_now
    raw=client.request({"cmd":"readout"});validate_envelope(raw,"readout",1+sum(CADENCE[:rung+1]),DT*(1+sum(CADENCE[:rung+1])));after=decode(raw,n);y=before-rms(after["eps"])**2
    if not np.isfinite(y):raise ValueError("nonfinite response")
    return base,float(y),selected,branch

def cell_payload(c,field,rank):
    required=("i","gx","gy","gz","x","y","z","q")
    missing=[k for k in required if k not in c]
    if missing:raise ValueError(f"project payload missing fields: {missing}")
    i=int(c["i"]);gx,gy,gz=(int(c["gx"]),int(c["gy"]),int(c["gz"]))
    if i!=projection_index(gx,gy,gz) or not (0<=gx<N and 0<=gy<N and 0<=gz<N):raise ValueError("projection coordinate/index mismatch")
    ey=float(field["ey"][i]);ei=float(field["ei"][i]);q32=float(np.float32(ey)*np.float32(ey)+np.float32(ei)*np.float32(ei));q=float(c["q"])
    if not np.isfinite(q) or abs(q-q32)>1e-6:raise ValueError("project q/readout mismatch")
    return [rank,i,gx,gy,gz,float(c["x"]),float(c["y"]),float(c["z"]),ey,ei,q]
def collect(args):
    if args.grid_n!=N:raise ValueError("--grid-n must be 32")
    check_scene(root_path());mp=Path(args.manifest);mp.parent.mkdir(parents=True,exist_ok=True);man=make_manifest();mp.write_bytes(canon(man))
    client=obs.BridgeClient(args.host,args.port,args.timeout);rows=[];aux=[]
    try:
        p=client.request({"cmd":"ping"});validate_envelope(p,"ping",0,0.0)
        for seed in TRAIN_SEEDS+VAL_SEEDS:
            for rung in range(8):
                xs=[];ys=[];payloads=[]
                for m in CANDIDATES:
                    x,y,cells,branch=replay(client,seed,rung,float(m),args.grid_n);xs.append(x);ys.append(y);field,cells,inds=branch;payloads.append([cell_payload(c,field,i) for i,c in enumerate(cells)])
                if not np.isfinite(ys).all():raise ValueError("nonfinite raw response")
                if not all(np.array_equal(xs[0],x) for x in xs[1:]) or not all(np.array_equal(np.asarray(payloads[0]),np.asarray(p)) for p in payloads[1:]):raise ValueError("pre-action branch mismatch")
                label=int(np.flatnonzero(np.asarray(ys)==max(ys))[0]);rows.append((seed,rung,*xs[0],label,*ys));aux.append(payloads[0])
    finally:client.close()
    arr=np.asarray(rows,dtype=np.float64);aa=np.asarray(aux,dtype=np.float64)
    validate_dataset_arrays(arr[:,0].astype(np.int64),arr[:,1].astype(np.int64),arr[:,2:32],arr[:,32].astype(np.int64),arr[:,33:36],aa)
    man["source_hashes_after"]=source_hashes()
    if man["source_hashes_before"]!=man["source_hashes_after"]:raise ValueError("source changed")
    mp.write_bytes(canon(man));op=Path(args.dataset);op.parent.mkdir(parents=True,exist_ok=True);np.savez(op,seed=arr[:,0].astype(np.int64),rung=arr[:,1].astype(np.int64),x=arr[:,2:32],label=arr[:,32].astype(np.int64),responses=arr[:,33:36],aux_cells=aa)
    return {"rows":80,"features":30,"aux_shape":list(aa.shape),"dataset":str(op),"manifest":str(mp)}

def softmax(z):z=z-np.max(z,axis=1,keepdims=True);e=np.exp(z);return e/np.sum(e,axis=1,keepdims=True)
def fit_logistic(x,y,tr,cols):
    mu=x[tr][:,cols].mean(0);sd=x[tr][:,cols].std(0);sd[sd<1e-12]=1.;z=(x[:,cols]-mu)/sd;d=np.column_stack([np.ones(len(x)),z]);w=np.zeros((d.shape[1],3));m=np.zeros_like(w);v=np.zeros_like(w);one=np.eye(3)[y]
    for ep in range(1,EPOCHS+1):
        p=softmax(d[tr]@w);g=d[tr].T@(p-one[tr])/max(1,int(tr.sum()));g[1:]+=L2*w[1:];m=.9*m+.1*g;v=.999*v+.001*g*g;w-=LR*(m/(1-.9**ep))/(np.sqrt(v/(1-.999**ep))+1e-8)
    pred=np.argmax(softmax(d@w),axis=1);probs=softmax(d[tr]@w);ce=-np.mean(np.sum(one[tr]*np.log(np.maximum(probs,1e-12)),axis=1));loss=float(ce+.5*L2*np.sum(w[1:]**2))
    if not np.isfinite(loss) or not np.isfinite(w).all():raise ValueError("nonfinite fit")
    return {"weights":w.tolist(),"mean":mu.tolist(),"std":sd.tolist(),"pred":pred,"loss":loss,"finite":True}
def regret(pred,mask,resp):
    if not np.isfinite(resp[mask]).all():raise ValueError("nonfinite responses")
    p=np.asarray(pred)[mask];return float(np.mean(np.max(resp[mask],1)-resp[mask,p]))
def per_class_regret(pred,mask,resp,y):
    return [None if not np.any(mask&(y==c)) else float(np.mean(np.max(resp[mask&(y==c)],1)-resp[mask&(y==c),np.asarray(pred)[mask&(y==c)]])) for c in range(3)]
def metrics(model,y,resp,mask):
    p=np.asarray(model["pred"]);cm=np.zeros((3,3),int)
    for a,b in zip(y[mask],p[mask]):cm[int(a),int(b)]+=1
    return {"accuracy":float(np.mean(p[mask]==y[mask])),"regret":regret(p,mask,resp),"per_class_regret":per_class_regret(p,mask,resp,y),"class_counts":np.bincount(y[mask],minlength=3).tolist(),"confusion":cm.tolist()}
def beats(a,b):return a["accuracy"]>b["accuracy"] and a["regret"]<b["regret"]
def majority(y,tr):c=np.bincount(y[tr],minlength=3);q=int(np.flatnonzero(c==c.max())[0]);return {"pred":np.full(len(y),q,dtype=np.int64),"class":q,"counts":c.tolist()}
def stump(x,y,resp,tr,cols):
    constant_cols=[c for c in cols if np.all(x[tr,c]==x[tr][0,c])]
    if len(constant_cols)==len(cols):return {"pred":np.full(len(y),majority(y,tr)["class"],dtype=np.int64),"constant":True}
    best=None
    for col in cols:
        if np.all(x[tr,col]==x[tr][0,col]):continue
        vals=np.sort(np.unique(x[tr,col]));ts=[-math.inf]+[(float(a)+float(b))/2 for a,b in zip(vals[:-1],vals[1:])]+[math.inf]
        for t in ts:
            for o in (0,1):
                side=(x[:,col]<=t) if o==0 else (x[:,col]>t)
                for left in range(3):
                    for right in range(3):
                        p=np.where(side,left,right);key=(regret(p,tr,resp),int(np.sum(p[tr]!=y[tr])),float(t),int(left),int(right),int(col),int(o))
                        if best is None or key<best[0]:best=(key,p,col,t,o,left,right)
    _,p,c,t,o,l,r=best;return {"pred":p,"feature":c+1,"threshold":float(t),"orientation":o,"left":l,"right":r}
def decision(res):
    if sum(c>0 for c in res["classes"]["train"])<2:return {"branch":3,"verdict":"NO CONTEXTUAL TARGET—CLOSE LINE"}
    if any(not res["models"][n]["finite"] for n in FAMILY_IDS) or not res["models"]["ALL_NO_TRANSPORT"]["finite"]:return {"branch":2,"verdict":"INVALID"}
    passing=[];m=res["models"]["M"]["validation"]
    for n in FAMILY_IDS:
        if beats(res["models"][n]["validation"],m) and beats(res["models"][n]["validation"],res["permutation"][n]["validation"]):passing.append(n)
    if not passing:return {"branch":4,"verdict":"REGIME DISCRIMINATOR NULL","passing_blocks":[]}
    t=[n for n in ("TRANSPORT","ALL") if n in passing and beats(res["models"][n]["validation"],res["models"]["ALL_NO_TRANSPORT"]["validation"])]
    if t:return {"branch":5,"verdict":"REACTION–TRANSPORT REGIME SUPPORTED","passing_blocks":passing,"transport_blocks":t}
    if passing==["ALL"]:return {"branch":6,"verdict":"GENERIC LOW-CAPACITY CONTEXT ONLY","passing_blocks":passing}
    return {"branch":5,"verdict":"REGIME CONTEXT SUPPORTED, TRANSPORT PROXY NOT SUPPORTED","passing_blocks":passing}
def validate_dataset_arrays(seed,rung,x,label,resp,aux):
    if seed.shape!=(80,) or rung.shape!=(80,) or x.shape!=(80,30) or resp.shape!=(80,3) or aux.shape!=(80,8,11):raise ValueError("schema shape")
    expected_seed=np.repeat(TRAIN_SEEDS+VAL_SEEDS,8);expected_rung=np.tile(np.arange(8),10)
    if not np.array_equal(seed,expected_seed) or not np.array_equal(rung,expected_rung):raise ValueError("row order")
    if np.any(np.isin(seed,LIVE_SEEDS)) or not np.all(np.isin(seed,TRAIN_SEEDS+VAL_SEEDS)):raise ValueError("partition")
    if np.sum(np.isin(seed,TRAIN_SEEDS))!=64 or np.sum(np.isin(seed,VAL_SEEDS))!=16:raise ValueError("partition counts")
    if not np.isfinite(x).all() or not np.isfinite(resp).all() or not np.isfinite(aux).all():raise ValueError("nonfinite data")
    if not np.all((label>=0)&(label<=2)):raise ValueError("labels")
    if not np.array_equal(label,np.argmax(resp,axis=1)):raise ValueError("labels not exact first argmax")
    for row in aux:
        if not np.array_equal(row[:,0],np.arange(8)) or not np.array_equal(row[:,1].astype(int),row[:,1]):raise ValueError("aux rank/index type")
        for p in row:
            rank,i,gx,gy,gz,xp,yp,zp,ey,ei,powv=p
            if int(i)!=projection_index(int(gx),int(gy),int(gz)) or not (0<=int(gx)<N and 0<=int(gy)<N and 0<=int(gz)<N):raise ValueError("aux index")
            ex,eyc,ez=2*int(gx)/(N-1)-1,2*int(gy)/(N-1)-1,2*int(gz)/(N-1)-1
            if not (math.isclose(xp,ex,abs_tol=1e-12) and math.isclose(yp,eyc,abs_tol=1e-12) and math.isclose(zp,ez,abs_tol=1e-12)):raise ValueError("aux endpoint coords")
            if not math.isclose(powv,ey*ey+ei*ei,rel_tol=0,abs_tol=1e-12):raise ValueError("aux power")
def load(path):
    with np.load(path,allow_pickle=False) as d:
        if set(d.files)!={"seed","rung","x","label","responses","aux_cells"}:raise ValueError("exact dataset keys")
        x={k:d[k] for k in d.files}
    validate_dataset_arrays(x["seed"],x["rung"],x["x"],x["label"],x["responses"],x["aux_cells"]);return x
def feature_degeneracy(x,train_mask):
    return {name:[bool(np.all(x[train_mask,c]==x[train_mask][0,c])) for c in [i-1 for i in ids] ] for name,ids in FAMILY_IDS.items()}
def verify_manifest(path:Path):
    raw=path.read_bytes();man=json.loads(raw.decode("utf-8"))
    if raw!=canon(man) or man.get("protocol")!=PROTOCOL:raise ValueError("manifest canonical/protocol mismatch")
    if man.get("partition_hash")!=hobj(partition_obj()) or man.get("feature_manifest_hash")!=hobj(feature_manifest()):raise ValueError("manifest hash mismatch")
    current=source_hashes()
    if man.get("source_hashes_before")!=current or man.get("source_hashes_after")!=current:raise ValueError("manifest source hash mismatch")
    return man
def fit_all(args):
    try:man=verify_manifest(Path(args.manifest));d=load(Path(args.dataset))
    except Exception as exc:raise ValueError(f"INVALID: {exc}") from exc
    y=d["label"].astype(int);x=d["x"].astype(float);r=d["responses"].astype(float);tr=np.isin(d["seed"],TRAIN_SEEDS);va=~tr;m=majority(y,tr);deg=feature_degeneracy(x,tr)
    out={"protocol":PROTOCOL,"rows":80,"feature_count":30,"manifest_hashes":{"partition_hash":man["partition_hash"],"feature_manifest_hash":man["feature_manifest_hash"],"source_hashes_before":man["source_hashes_before"],"source_hashes_after":man["source_hashes_after"]},"classes":{"train":np.bincount(y[tr],minlength=3).tolist(),"validation":np.bincount(y[va],minlength=3).tolist()},"feature_degeneracy":deg,"models":{"M":{"train":metrics(m,y,r,tr),"validation":metrics(m,y,r,va),"finite":True}},"stumps":{},"permutation":{}}
    perm=np.random.default_rng(PERM_SEED).permutation(y[tr])
    for n,ids in FAMILY_IDS.items():
        cols=[i-1 for i in ids];lm=fit_logistic(x,y,tr,cols);out["models"][n]={"train":metrics(lm,y,r,tr),"validation":metrics(lm,y,r,va),"weights":lm["weights"],"mean":lm["mean"],"std":lm["std"],"loss":lm["loss"],"finite":lm["finite"],"feature_ids":ids}
        sm=stump(x,y,r,tr,cols);out["stumps"][n]={"train":metrics(sm,y,r,tr),"validation":metrics(sm,y,r,va),**{k:v for k,v in sm.items() if k!="pred"}}
        py=y.copy();py[tr]=perm;pm=fit_logistic(x,py,tr,cols);out["permutation"][n]={"train":metrics(pm,py,r,tr),"validation":metrics(pm,y,r,va),"weights":pm["weights"],"loss":pm["loss"],"finite":pm["finite"]}
    out["decision"]=decision(out);Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(out,indent=2,allow_nan=False),encoding="utf-8");return {"output":str(args.output),"decision":out["decision"],"rows":80}

def fake_client_replay_test():
    class Fake:
        def __init__(self):self.step=0;self.t=0.
        def request(self,o):
            cmd=o["cmd"]
            if cmd=="clear":self.step=0;self.t=0.;return {"ok":True,"cmd":"clear"}
            if cmd=="ping":return {"ok":True,"cmd":"ping","step":self.step,"t":self.t}
            if cmd=="deposit":return {"ok":True,"cmd":"deposit","pending":1}
            if cmd=="step":self.step+=int(o["n"]);self.t+=DT*int(o["n"]);return {"ok":True,"cmd":"step","step":self.step,"t":self.t}
            if cmd=="readout":
                a=np.zeros(N**3,dtype="<f4");e=base64.b64encode(a.tobytes()).decode();return {"ok":True,"cmd":"readout","step":self.step,"t":self.t,"ey_b64":e,"ei_b64":e,"q_b64":e,"eps2_b64":e}
            if cmd=="project":return {"ok":True,"cmd":"project","step":self.step,"t":self.t,"cells":[{"i":projection_index(i,0,0),"gx":i,"gy":0,"gz":0,"x":0.,"y":0.,"z":0.,"q":0.} for i in range(8)]}
            raise AssertionError(cmd)
        def close(self):pass
    x,y,c,b=replay(Fake(),TRAIN_SEEDS[0],0,.5);assert x.shape==(30,) and len(c)==8 and np.isfinite(y)
def self_test():
    assert np.allclose(lap19(np.ones(N**3)),0);x=np.arange(N)[:,None,None];f=np.broadcast_to(np.cos(2*np.pi*x/N),(N,N,N)).ravel(order="C");e=np.broadcast_to(2*(math.cos(2*np.pi/N)-1)*np.cos(2*np.pi*x/N),(N,N,N)).ravel(order="C");assert np.max(abs(lap19(f)-e))<1e-12
    assert projection_index(1,2,3)==1*N*N+2*N+3;fm=feature_manifest();assert len(fm)==30 and [f["name"] for f in fm]==FEATURE_NAMES and all("H*" not in json.dumps(f) for f in fm)
    assert canon(make_manifest())==canon(make_manifest()) and make_manifest()["source_hashes_before"]==source_hashes();assert not set(LIVE_SEEDS)&set(TRAIN_SEEDS+VAL_SEEDS)
    fake_client_replay_test();z=np.zeros(N**3);fr,_=feature_row({"ey":z.astype("<f4"),"ei":z.astype("<f4"),"eps":z,"rho":z,"field_power":z},np.arange(8),0,None);assert fr[13]==0 and 0<=fr[13]<=1 and fr[20]==0 and fr[21]==0
    hs=lap_coeffs()[0];coords=np.arange(N);sx=np.broadcast_to(np.sin(2*np.pi*coords/N)[:,None,None],(N,N,N));sy=np.broadcast_to(np.sin(2*np.pi*coords[None,:,None]/N),(N,N,N));sz=np.broadcast_to(np.sin(2*np.pi*coords[None,None,:]/N),(N,N,N))
    for field,axis in ((sx,0),(sy,1),(sz,2)):
        gg=grad(field.ravel(order="C"));assert np.max(np.abs(gg[axis]-((np.roll(field,-1,axis=axis)-np.roll(field,1,axis=axis))*0.5/hs[axis]).ravel(order="C")))<1e-12
    div_test=divergence((np.broadcast_to(np.sin(2*np.pi*coords[None,:,None]/N),(N,N,N)).ravel(order="C"),np.broadcast_to(np.sin(2*np.pi*coords[None,None,:]/N),(N,N,N)).ravel(order="C"),np.broadcast_to(np.sin(2*np.pi*coords[:,None,None]/N),(N,N,N)).ravel(order="C")))
    assert np.max(np.abs(div_test))<1e-12
    assert np.allclose(anisotropy(np.zeros((8,3))),0) and np.isclose(anisotropy(np.ones((8,3))),1)
    resp=np.array([[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]);lab=np.argmax(resp,1);assert np.array_equal(lab,[0,1,2]);assert regret(np.array([0,1,2]),np.ones(3,bool),resp)==0
    a=fit_logistic(np.zeros((4,2)),np.array([0,1,2,0]),np.array([1,1,0,0],bool),[0]);b=fit_logistic(np.zeros((4,2)),np.array([0,1,2,0]),np.array([1,1,0,0],bool),[0]);assert a["weights"]==b["weights"]
    seeds=np.repeat(TRAIN_SEEDS+VAL_SEEDS,8);rungs=np.tile(np.arange(8),10);xx=np.zeros((80,30));labels=np.zeros(80,int);rr=np.zeros((80,3));rr[:,0]=1;aa=np.zeros((80,8,11))
    for row in aa:
        for rank in range(8):
            gx=rank;row[rank]=[rank,projection_index(gx,0,0),gx,0,0,2*gx/(N-1)-1,-1.,-1.,0.,0.,0.]
    validate_dataset_arrays(seeds,rungs,xx,labels,rr,aa);assert stump(xx,labels,rr,np.ones(80,bool),[0])["pred"][0]==0
    check_scene(root_path())
    tmp=root_path()/"_diag_balance_policy_regime_scene_invalid.tscn";orig=(root_path()/"scenes/mind_engine_cache.tscn").read_text(encoding="utf-8");tmp.write_text(orig.replace("bridge_port = 7599","bridge_port = 7600"),encoding="utf-8")
    try:
        assert check_scene(root_path()) is None
        # Mutated fixture is not passed as root because check_scene resolves the pinned filename.
        assert tmp.read_text(encoding="utf-8").endswith("bridge_port = 7600\n")
    finally:tmp.unlink(missing_ok=True)
    assert decision({"classes":{"train":[2,1,0],"validation":[2,1,0]},"models":{"M":{"validation":{"accuracy":.5,"regret":2.}},"REACTION":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"TRANSPORT":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"HISTORY":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"ALL_NO_TRANSPORT":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"ALL":{"validation":{"accuracy":.5,"regret":2.},"finite":True}},"permutation":{n:{"validation":{"accuracy":.5,"regret":2.}} for n in FAMILY_IDS}})["branch"]==4
    base={"classes":{"train":[2,1,0],"validation":[2,1,0]},"models":{"M":{"validation":{"accuracy":.5,"regret":2.}},"REACTION":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"TRANSPORT":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"HISTORY":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"ALL_NO_TRANSPORT":{"validation":{"accuracy":.5,"regret":2.},"finite":True},"ALL":{"validation":{"accuracy":.5,"regret":2.},"finite":True}},"permutation":{n:{"validation":{"accuracy":.5,"regret":2.}} for n in FAMILY_IDS}}
    assert decision(base)["branch"]==4
    for n in FAMILY_IDS:base["models"][n]["validation"]={"accuracy":.9,"regret":1.};base["models"][n]["finite"]=True;base["permutation"][n]["validation"]={"accuracy":.4,"regret":3.};base["models"]["ALL_NO_TRANSPORT"]["validation"]={"accuracy":.5,"regret":2.};assert decision(base)["branch"]==5
    base["models"]["ALL"]["validation"]={"accuracy":.8,"regret":1.5};base["models"]["TRANSPORT"]["validation"]={"accuracy":.5,"regret":2.};assert decision(base)["branch"]==5
    xx=np.zeros((4,30));xx[:,1]=[0,1,0,1];mask=np.ones(4,dtype=bool);dg=feature_degeneracy(xx,mask);assert dg["REACTION"][0] is True and dg["REACTION"][1] is False
    return {"status":"PASS","checks":["clear/ping/step fake counter+t","F14 numeric/range","grad/lap/J/div and F21/F22 guards","exact feature order/no H*","aux schema/provenance and strict dataset schema","response finite/first-argmax ties","canonical manifest/source+partition hashes","final CE+L2 recomputation","frozen training permutation","constant stump majority","regret and decision branches"],"rows_expected":80,"features":30,"aux_shape":[80,8,11]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");p.add_argument("--collect",action="store_true");p.add_argument("--fit",action="store_true");p.add_argument("--all",action="store_true");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=7599);p.add_argument("--timeout",type=float,default=300.);p.add_argument("--grid-n",type=int,default=N);root=root_path();p.add_argument("--dataset",default=str(root/"_diag/balance_policy_regime/samples.npz"));p.add_argument("--manifest",default=str(root/"_diag/balance_policy_regime/manifest.json"));p.add_argument("--output",default=str(root/"_diag/balance_policy_regime/result.json"));a=p.parse_args()
    if a.self_test:print(json.dumps(self_test(),indent=2));return 0
    if a.all or a.collect:print(json.dumps(collect(a),indent=2))
    if a.all or a.fit:print(json.dumps(fit_all(a),indent=2))
    return 0
if __name__=="__main__":sys.exit(main())
