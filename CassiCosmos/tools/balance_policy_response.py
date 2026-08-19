#!/usr/bin/env python3
"""Measured-response contextual balance-policy experiment."""
import argparse, json, sys
from pathlib import Path
import numpy as np
import balance_spiral_observability as obs
import balance_policy_learning as base

CANDIDATES=np.array([0.5,1.0,1.5]); TRAIN=base.TRAIN_SEEDS; VAL=base.VAL_SEEDS; TEST=base.LIVE_SEEDS
CADENCE=base.CADENCE; K=base.PROJECT_K; BUDGET=base.BUDGET; EPOCHS=200; LR=.03

def feature(field,cells,prev_z,rung):
    eps=np.array([field['eps'][int(c['i'])] for c in cells]); rho=np.array([field['rho'][int(c['i'])] for c in cells])
    z,d,dz=base.features(eps,rho,prev_z)
    return np.array([1.,np.mean(abs(z)),np.sqrt(np.mean(z*z)),np.mean(d),np.mean(abs(dz)),rung/7.]),z

def deposits(field,cells,mult):
    eps=np.array([field['eps'][int(c['i'])] for c in cells]); mag=base.analytic_magnitude(eps)*mult; out=[]
    for c,e,a in zip(cells,eps,mag):
        out.append({'x':c['x'],'y':c['y'],'z':c['z'],'cy':float(a) if e<0 else 0.,'ci':float(a) if e>=0 else 0.,'sigma':1.})
    return base.normalize_budget(out)

def replay(client,seed,rung,mult,n):
    client.request({'cmd':'clear'})
    for d in obs.make_ic(seed,10): client.request({'cmd':'deposit',**d})
    client.request({'cmd':'step','n':1}); prev=np.zeros(K); feat=None; before=None
    for r,tau in enumerate(CADENCE[:rung+1]):
        field=obs.decode_readout(client.request({'cmd':'readout'}),n); cells=client.request({'cmd':'project','k':K})['cells']; feat,z=feature(field,cells,prev,r)
        if r==rung:
            before=obs.observe(field,n)['eps']['rms']**2; chosen=mult
        else: chosen=1.
        for d in deposits(field,cells,chosen): client.request({'cmd':'deposit',**d})
        client.request({'cmd':'step','n':tau}); prev=z
    after_field=obs.decode_readout(client.request({'cmd':'readout'}),n); after=obs.observe(after_field,n)['eps']['rms']**2
    return feat,before-after

def collect(args):
    client=obs.BridgeClient(args.host,args.port,args.timeout); rows=[]
    try:
        client.request({'cmd':'ping'})
        for seed in TRAIN+VAL:
            for rung in range(len(CADENCE)):
                responses=[]; feat=None
                for m in CANDIDATES:
                    feat,y=replay(client,seed,rung,float(m),args.grid_n); responses.append(y)
                best=int(np.flatnonzero(np.array(responses)==np.max(responses))[0])
                rows.append((seed,rung,*feat,best,*responses))
    finally: client.close()
    arr=np.array(rows,float); p=Path(args.dataset); p.parent.mkdir(parents=True,exist_ok=True)
    np.savez(p,seed=arr[:,0].astype(int),rung=arr[:,1].astype(int),x=arr[:,2:8],label=arr[:,8].astype(int),responses=arr[:,9:12])
    print(json.dumps({'dataset':str(p),'rows':len(rows)},indent=2))

def softmax(a):
    a=a-np.max(a,axis=1,keepdims=True); e=np.exp(a); return e/np.sum(e,axis=1,keepdims=True)

def fit(data):
    seed=data['seed']; tr=np.isin(seed,TRAIN); va=np.isin(seed,VAL); x=data['x'].astype(float); y=data['label']; resp=data['responses']
    mean=x[tr,1:].mean(0); std=x[tr,1:].std(0); std[std<1e-12]=1; xs=x.copy(); xs[:,1:]=(x[:,1:]-mean)/std
    w=np.zeros((6,3)); m=np.zeros_like(w); v=np.zeros_like(w); one=np.eye(3)[y]
    losses=[]
    for ep in range(1,EPOCHS+1):
        p=softmax(xs[tr]@w); loss=-np.mean(np.sum(one[tr]*np.log(np.maximum(p,1e-12)),axis=1)); losses.append(float(loss))
        g=xs[tr].T@(p-one[tr])/tr.sum(); m=.9*m+.1*g; v=.999*v+.001*g*g
        w-=LR*(m/(1-.9**ep))/(np.sqrt(v/(1-.999**ep))+1e-8)
    pred=np.argmax(softmax(xs@w),axis=1); counts=np.bincount(y[tr],minlength=3); majority=int(np.flatnonzero(counts==counts.max())[0])
    regret=lambda pr,mask: float(np.mean(np.max(resp[mask],axis=1)-resp[mask,pr[mask]]))
    return {'weights':w.tolist(),'mean':mean.tolist(),'std':std.tolist(),'majority':majority,'final_loss':losses[-1],
            'val_accuracy':float(np.mean(pred[va]==y[va])),'majority_accuracy':float(np.mean(majority==y[va])),
            'val_regret':regret(pred,va),'majority_regret':regret(np.full(len(y),majority),va),'classes':np.bincount(y[tr],minlength=3).tolist(),'finite':bool(np.isfinite(w).all())}

def load(path):
    with np.load(path) as d:return {k:d[k] for k in d.files}

def choose(model,x):
    xx=x.copy(); xx[1:]=(xx[1:]-model['mean'])/model['std']; return int(np.argmax(softmax((xx@np.array(model['weights'])).reshape(1,3))[0]))

def live_arm(client,seed,arm,model,n):
    client.request({'cmd':'clear'}); [client.request({'cmd':'deposit',**d}) for d in obs.make_ic(seed,10)]; client.request({'cmd':'step','n':1})
    field=obs.decode_readout(client.request({'cmd':'readout'}),n); ceiling=max(1e-30,float(np.max(field['field_power'])))*100; prev=np.zeros(K); rec=[]; total=0
    for rung,tau in enumerate([0]+CADENCE):
        met=base.metrics(field,n,obs.CONTROL_SEED+seed+rung*10); rec.append(met)
        if rung==len(CADENCE):break
        cells=client.request({'cmd':'project','k':K})['cells']; x,z=feature(field,cells,prev,rung)
        if arm=='D': mult=0.
        elif arm=='A':mult=1.
        elif arm=='M':mult=float(CANDIDATES[model['majority']])
        elif arm=='P':mult=float(CANDIDATES[choose(model,x)])
        else:mult=float(CANDIDATES[np.random.default_rng(seed+rung).integers(0,3)])
        ds=[] if arm=='D' else deposits(field,cells,mult); charge=sum(abs(d['cy'])+abs(d['ci']) for d in ds); total+=charge
        if charge>BUDGET+1e-9:raise RuntimeError('budget')
        [client.request({'cmd':'deposit',**d}) for d in ds]; client.request({'cmd':'step','n':tau}); prev=z
        field=obs.decode_readout(client.request({'cmd':'readout'}),n)
        if np.max(field['field_power'])>ceiling:raise RuntimeError('safety')
    return {'seed':seed,'arm':arm,'endpoint':rec[-1],'integrated_balance':sum(r['eps_rms'] for r in rec),'integrated_h_star':sum(r['h_star']['best'] for r in rec),'integrated_j_proxy_rms':sum(r['j_proxy_rms'] for r in rec),'total_charge':total}

def decide(model,runs):
    if len([c for c in model['classes'] if c])<2:return {'branch':3,'verdict':'NO CONTEXTUAL TARGET—CLOSE LINE'}
    if not model['finite'] or model['val_accuracy']<=model['majority_accuracy'] or model['val_regret']>=model['majority_regret']:return {'branch':4,'verdict':'CONTEXT POLICY NOT LEARNABLE'}
    by={(r['seed'],r['arm']):r for r in runs}; paired=[]
    for s in TEST:
        d,a,p=by[s,'D'],by[s,'A'],by[s,'P']; paired.append({'seed':s,'p_beats_d':p['endpoint']['eps_rms']<d['endpoint']['eps_rms'],'p_beats_a':p['endpoint']['eps_rms']<a['endpoint']['eps_rms'],'integrated_not_worse':p['integrated_balance']<=a['integrated_balance']})
    if sum(x['p_beats_d'] for x in paired)<2:return {'branch':8,'verdict':'CONTEXT POLICY REJECT','paired':paired}
    wins=[x for x in paired if x['p_beats_a'] and x['integrated_not_worse']]
    return {'branch':7 if len(wins)>=2 else 6,'verdict':'CONTEXT POLICY ADOPT' if len(wins)>=2 else 'CONTEXT POLICY REDISCOVERS BALANCE','paired':paired}

def train(args):
    model=fit(load(args.dataset)); Path(args.output).parent.mkdir(parents=True,exist_ok=True); Path(args.output).write_text(json.dumps({'model':model},indent=2)); print(json.dumps(model,indent=2))
def run_live(args):
    model=json.loads(Path(args.output).read_text())['model']; client=obs.BridgeClient(args.host,args.port,args.timeout); runs=[]
    try:
        [runs.append(live_arm(client,s,a,model,args.grid_n)) for s in TEST for a in ('D','A','M','P','R')]
    finally:client.close()
    result={'model':model,'runs':runs,'decision':decide(model,runs)}; Path(args.output).write_text(json.dumps(result,indent=2)); print(json.dumps(result['decision'],indent=2))
def self_test():
    assert int(np.flatnonzero(np.array([1.,1.,0.])==1)[0])==0
    p=base.normalize_budget([{'cy':1.,'ci':1.}]);assert sum(abs(x['cy'])+abs(x['ci']) for x in p)<=BUDGET+1e-12
    a=np.array([[1.,2.,3.]]);assert np.isclose(softmax(a).sum(),1)
    print('[self-test] PASS: ties, budget, softmax')
def main():
    p=argparse.ArgumentParser();[p.add_argument(x,action='store_true') for x in ('--self-test','--collect','--train','--live','--all')];p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=7599);p.add_argument('--timeout',type=float,default=300);p.add_argument('--grid-n',type=int,default=32);p.add_argument('--dataset',default=str(Path(__file__).resolve().parents[1]/'_diag/balance_policy_response/samples.npz'));p.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'_diag/balance_policy_response/result.json'));a=p.parse_args()
    if a.self_test:self_test();return 0
    if a.all or a.collect:collect(a)
    if a.all or a.train:train(a)
    if a.all or a.live:run_live(a)
    return 0
if __name__=='__main__':sys.exit(main())
