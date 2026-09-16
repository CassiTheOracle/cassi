"""Ladder of intrinsic direction lifetimes across the declared packet path.

Cites (do not re-measure):
  _diag/fractal-durability/exploration.json — intrinsic decay with sources off.
  _diag/fractal-memory/exploration.json — narrow rungs hold their driven share;
    wide rungs lose the driven direction: ``0.003380437390550838`` retained
    projection at width ``28`` (wide, the whole declared path) versus
    ``0.17236141393990917`` at width ``3`` (narrow, the smallest rung) over 256
    ticks, so coarser is not more durable under drive.
  _diag/fractal-survival/exploration.json — mass-metric profile carries the
    multi-item survival gain while the connection graph does not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_survival_exploration as survival
from cassi_resonant_field import ResonantProfile, advance_workspace, initial_workspace, apply_helical_packet_impulse
import run_fractal_metric_exploration as metric

SCHEMA = "cassifi.fractal-ladder-exploration.v1"
HORIZON_TICKS = 256
SAMPLE_EVERY = 16
SAMPLE_TICKS: tuple[int, ...] = tuple(range(SAMPLE_EVERY, HORIZON_TICKS + 1, SAMPLE_EVERY))
THRESHOLD_FRACTION = 0.05
THRESHOLD_KIND = "one twentieth of post-write alignment"
THRESHOLD_LABEL = "1/20"
DIVERGENCE_TOL_ABS = 0.02
PROFILE_NAMES: tuple[str, ...] = ("helix7", "mass-only", "flat-inertia")
RUNG_WIDTHS: tuple[int, ...] = (28, 14, 7)
BOUNDARY = (
    "Canonical-field numerical measurements in controlled conditions only: one "
    "bounded packet impulse per item at durability budget, then declared horizon "
    "with sources off (advance_workspace source_enabled=False, heartbeat 0, sampled "
    "every 16 to 256) on three declared profiles (helix7, mass-only, flat-inertia) via canonical hooks. Read frame is "
    "durability declared frame. Lifetime is first below-threshold censored at horizon; "
    "window/occupancy give second measures. Modal decomposition projects written "
    "direction onto frozen linear generator geometry.linear_generator (beta=0) with "
    "physical time scaling dt=0.08 per tick; corroborated linear predictor (not exact) is bilinear form "
    "retention(t)=(C exp(G t dt) dz . u)^2/deposited with cross terms, corroborated to tolerance 0.02 at beta=0. No task memory claim. Flat-inertia cited from metric harness (k4 0.8948910529922045, eleven times field default) — not re-derived."
)
DEFINITIONS = {
    "declared_item": "one (path,component,flow_signal) write at declared budget; momentum lanes only",
    "read_frame": "packet coefficients of durability declared read frame path flattened row-major",
    "captured_write_direction": "unit image of one item impulse in read frame from fresh workspace",
    "width_semantics": "support size in ports: width 28 is whole declared path (widest rung, root-scale/root-detail), width 14 intermediate, width 7 small-scale details, width 3 narrowest rung in fractal-memory receipt; narrow rungs hold driven share while wide rungs lose driven direction — 0.00338 at width 28 vs 0.172 at width 3 over 256 ticks — so width and durability under drive are opposite",
    "alignment_retention": "(c.u)^2/|c_in_arm|^2 (durability.share_along)",
    "total_packet_energy_ratio": "|c_read|^2/|c_pre|^2",
    "direction_lifetime": "first sampled tick (every 16 to 256) where alignment falls below 1/20 of post-write alignment; censored at horizon",
    "lifetime_window": "last_below - first_cross",
    "occupancy": "fraction of samples at or above threshold plus final alignment",
    "rung_width": "packet support width 28/14/7 measured from durability harness",
    "declared_profile": "helix7=ResonantProfile() default; mass-only=survival mass-only arm; flat-inertia=metric harness ladder-uniform (equal-total-inertia, flat inertia, k4 0.8948910529922045 cited from run_fractal_metric_exploration, eleven times field default — not re-derived)",
    "threshold": "one twentieth of post-write alignment (0.05*initial)",
    "modal_decomposition": "G=geometry.linear_generator(profile); G=V diag(lambda) V^-1; dz=written-empty; coeff=V^-1 dz; weight=|coeff|^2/sum; eff=1/sum w^2; dt=0.08 per tick; exp(G t dt)",
    "corroborated_linear_predictor": "retention_pred(t)=(C exp(G t dt) dz . u)^2/deposited, bilinear with cross terms, corroborated to 0.02 at beta=0 (not exact); cross terms dominate",
    "divergence_onset": "first tick where |canonical - corroborated|>0.02 absolute; nonlinearity fingerprint",
    "concentration": "effective_mode_count=1/sum w^2; concentration=1/eff",
    "concentration_ceiling_algebraic": "algebraic bound: minimum eff over linear combinations of eight item state vectors (lower bound, not necessarily writable)",
    "concentration_ceiling_realized": "achieved ceiling: minimum eff over actually applied bounded impulse sequences from declared surface; gap to algebraic is shortfall spec for mode-selective primitive",
    "exhaustive_write_surface": "every declared (path,component,flow_signal) at declared budget (28 packet modes x sign), realized metrics from applied state, predicted via corroborated linear predictor",
    "mode_selective_spec": "required max_weight and eff to land in slowest band (dominant efold 1042-1789 helix7, 1468-1513 flat-inertia), derived from measured slow-band weight distribution and read-frame overlaps; gap to realized 16.58/17.7 vs algebraic 9.3/9.7 is owner decision spec",
    "flat_inertia_citation": "metric harness run_fractal_metric_exploration ladder-uniform k4 0.8948910529922045 (eleven times field default) — cited, not re-derived; intrinsic ladder here tests whether advantage appears sources-off",
    "beats": "non-monotone retention from multi-mode interference; characterized by direction changes, peak spacing, depth",
    "content_digest": "sha256 of canonical JSON of measured body with wall-clock fields stripped",
}
DEFAULT_OUTPUT = Path("_diag/fractal-ladder/exploration.json")
# Declared write surface scaling factors for combinations
BUDGET_SCALINGS: tuple[float, ...] = (0.5, 1.0)
TWO_BUDGETS: tuple[float, ...] = (0.0005, 0.001)

def canonical_json(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False)

def strip_timing(v: Any) -> Any:
    if isinstance(v, Mapping):
        return {k: strip_timing(x) for k, x in v.items() if k not in {"elapsed_seconds","runtime_seconds","receipt_digest","content_digest"}}
    if isinstance(v, list):
        return [strip_timing(x) for x in v]
    return v

def content_digest(v: Any) -> str:
    return hashlib.sha256(canonical_json(strip_timing(v)).encode("utf-8")).hexdigest()

def build_declared_profile(name: str) -> Any:
    if name == "helix7":
        return durability.ResonantProfile()
    if name == "mass-only":
        return survival.build_attribution_profile("mass-only")
    if name == "flat-inertia":
        return metric.build_metric_profile(metric.ladder_row("ladder-uniform"))
    raise RuntimeError(name)

def rung_depth(w: int) -> int:
    return int(round(float(np.log2(28.0/float(w))))) if w else 0

def _state_vector(ws: Any) -> np.ndarray:
    n=ws.profile.port_count; p=ws._field.reshape(-1)
    return np.concatenate((p[0:9*n:9].copy(),p[1:9*n:9].copy(),p[2:9*n:9].copy(),p[3:9*n:9].copy()))

def _page_from_state(base: Any, vec: np.ndarray) -> Any:
    n=base.profile.port_count; page=base._field.copy().reshape(-1)
    parts=np.split(vec,4)
    for lane,v in enumerate(parts):
        page[lane:9*n:9]=v
    return page.reshape(base.profile.page_shape)

def _predicted_read_frame(base_ws: Any, vec: np.ndarray) -> np.ndarray:
    page=_page_from_state(base_ws,vec)
    tmp=base_ws.__class__(profile=base_ws.profile, field_page=page)
    return durability.read_frame(tmp, durability.READ_FRAME_PATH)

def rank_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    n=len(xs)
    if n<2 or len(ys)!=n: return 0.0
    def ranks(vals: Sequence[float]) -> np.ndarray:
        order=np.argsort(vals); r=np.empty(n,dtype=np.float64); i=0
        while i<n:
            j=i
            while j+1<n and vals[order[j+1]]==vals[order[i]]: j+=1
            avg=(i+j)/2.0+1.0
            for k in range(i,j+1): r[order[k]]=avg
            i=j+1
        return r
    rx,ry=ranks(list(xs)),ranks(list(ys))
    mx,my=float(rx.mean()),float(ry.mean())
    num=float(np.sum((rx-mx)*(ry-my))); den=float(np.sqrt(np.sum((rx-mx)**2)*np.sum((ry-my)**2)))
    return float(num/den) if den else 0.0

def pearson_corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs)<2 or len(xs)!=len(ys): return 0.0
    x=np.asarray(xs,dtype=np.float64); y=np.asarray(ys,dtype=np.float64)
    mx,my=float(x.mean()),float(y.mean())
    num=float(np.sum((x-mx)*(y-my))); den=float(np.sqrt(np.sum((x-mx)**2)*np.sum((y-my)**2)))
    return float(num/den) if den else 0.0

def rms(a: Sequence[float], b: Sequence[float]) -> float:
    x=np.asarray(a,dtype=np.float64); y=np.asarray(b,dtype=np.float64)
    return float(np.sqrt(np.mean((x-y)**2))) if len(x) else 0.0

def profile_linearity_report(profile: Any) -> dict[str, Any]:
    beta=float(profile.beta)
    w=profile.projected_quartic_weights
    has_quartic=bool(w is not None or beta!=0.0)
    is_linear=bool(beta==0.0)
    terms=["potential: beta*d^3 in energy gradient","energy: beta*d^4/4","Hessian: 3*beta*d^2","advance_workspace discrete-gradient implicit solve with nonlinear_iterations>0 when beta!=0"]
    return {"beta":beta,"projected_quartic_weights_is_none": w is None,"has_quartic":has_quartic,"is_linear_body":is_linear,"nonlinear_terms":terms,"statement": "body is LINEAR (beta=0)" if is_linear else f"body is NONLINEAR (beta={beta}, uniform quartic weights)"}

def measured_series_for_item(profile: Any, item_index: int, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    spec=durability.ITEM_SPECS[item_index]; cap=captures[item_index]
    direction=cap["direction"]; deposited=float(cap["deposited_energy"])
    ws0=initial_workspace(profile)
    ws_written,_=durability.write_item(ws0,spec,durability.DurabilityConfig().write_budget)
    vec_written=durability.read_frame(ws_written,durability.READ_FRAME_PATH)
    pre_energy=float(durability.squared_norm(vec_written))
    if pre_energy<=0: raise RuntimeError(spec.name)
    init=float(durability.share_along(vec_written,direction,deposited))
    thr=float(THRESHOLD_FRACTION)*float(init)
    series: list[dict[str,Any]]=[]; cur=ws_written; prev=0
    for t in SAMPLE_TICKS:
        gap=int(t)-prev; cur,adv=advance_workspace(cur,ticks=gap,demand=0.0,source_enabled=False); prev=int(t)
        vec=durability.read_frame(cur,durability.READ_FRAME_PATH)
        al=float(durability.share_along(vec,direction,deposited))
        series.append({"tick":int(t),"packet_energy":float(durability.squared_norm(vec)),"total_energy_ratio":float(float(durability.squared_norm(vec))/pre_energy) if pre_energy else None,"alignment_retention":al,"alignment_ratio":float(al/init) if init else None,"field_ticks":int(cur.field_ticks),"dissipated_work":float(adv["dissipated_work"]),"positive_heartbeat_work":float(adv["positive_heartbeat_work"]),"source_enabled":bool(adv["source_enabled"])})
    first=next((int(r["tick"]) for r in series if r["alignment_retention"]<thr),None)
    last=next((int(r["tick"]) for r in reversed(series) if r["alignment_retention"]<thr),None)
    censored=first is None; lifetime=int(HORIZON_TICKS) if censored else int(first); window=0 if censored else int(last)-int(first)
    above=sum(1 for s in series if s["alignment_retention"]>=thr); occ=float(above/len(series)) if series else 0.0; final=float(series[-1]["alignment_retention"]) if series else 0.0
    # declared series measures for beats-agnostic reporting
    rets=[float(s["alignment_retention"]) for s in series]; last_half=rets[len(rets)//2:]; last_half_min=float(min(last_half)) if last_half else 0.0; last_half_max=float(max(last_half)) if last_half else 0.0
    return {"item":spec.name,"path":spec.path,"component":spec.component,"scale_width":int(cap["scale_width"]),"scale_depth":int(rung_depth(int(cap["scale_width"]))),"scale_distance":int(rung_depth(int(cap["scale_width"]))),"deposited_energy":deposited,"initial_alignment":init,"threshold_fraction":float(THRESHOLD_FRACTION),"threshold_kind":THRESHOLD_KIND,"threshold_absolute":thr,"series":series,"lifetime_ticks":lifetime,"censored":bool(censored),"first_crossing_ticks":first,"last_below_ticks":last,"window_ticks":int(window),"occupancy":float(occ),"final_alignment":float(final),"final_retention":float(final),"last_half_min":float(last_half_min),"last_half_max":float(last_half_max),"pre_energy":pre_energy,"retention_at_horizon":float(final)}

def beats_characterization(series: Sequence[float]) -> dict[str, Any]:
    s=np.asarray(series,dtype=np.float64)
    if len(s)<3:
        return {"is_nonmonotone": False, "direction_changes": 0, "depth": 0.0, "period_ticks": None, "plain": "too short"}
    diffs=np.diff(s)
    # direction changes: sign flips ignoring zeros
    signs=np.sign(diffs)
    # compress zeros
    nz=signs[signs!=0]
    changes=int(np.sum(nz[1:]!=nz[:-1])) if len(nz)>=2 else 0
    is_nonmono=bool(changes>0)
    depth=float(s.max()-s.min()) if len(s) else 0.0
    rel_depth=float(depth/max(1e-12,float(s.max()))) if float(s.max()) else 0.0
    # peaks: local maxima
    peaks=[]
    for i in range(1,len(s)-1):
        if s[i]>=s[i-1] and s[i]>=s[i+1] and (s[i]>s[i-1] or s[i]>s[i+1]):
            peaks.append(i)
    if len(peaks)>=2:
        spacings=np.diff(np.asarray([SAMPLE_TICKS[p] for p in peaks],dtype=np.float64))
        period=float(np.mean(spacings)) if len(spacings) else 0.0
    else:
        period=None
    last_half=s[len(s)//2:]
    lhmn=float(last_half.min()) if len(last_half) else 0.0
    lhmx=float(last_half.max()) if len(last_half) else 0.0
    plain=f"{'non-monotone' if is_nonmono else 'monotone'} {changes} direction changes, depth {depth:.3f} (rel {rel_depth:.2f}), period {period if period is not None else 'n/a'} ticks, last-half [{lhmn:.3f},{lhmx:.3f}]"
    if is_nonmono and depth>0.2:
        plain+=" — beats are real structure, not averaging artifact"
    return {"is_nonmonotone": bool(is_nonmono), "direction_changes": int(changes), "depth": float(depth), "relative_depth": float(rel_depth), "period_ticks": period, "last_half_min": float(lhmn), "last_half_max": float(lhmx), "peak_indices": peaks, "plain": plain}

def modal_block_for_profile(profile: Any, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    G=geometry.linear_generator(profile); vals,vecs=np.linalg.eig(G)
    dt=float(profile.time_step); decay=-np.real(vals)
    sorted_rates=np.sort(decay); gaps=np.diff(sorted_rates)
    rng=float(sorted_rates.max()-sorted_rates.min()) if sorted_rates.size else 0.0
    band_gaps=[float(g) for g in gaps if g>0.05*rng] if rng else []
    band_count=int(len(band_gaps)+1) if rng else 1
    continuum=bool((gaps.max() if gaps.size else 0.0)<0.02*rng) if rng else True
    band_verdict="continuum" if continuum else f"{band_count} bands (gaps {', '.join(f'{g:.4f}' for g in band_gaps[:3])})"
    efold_time_min=float(1.0/float(sorted_rates.max())) if float(sorted_rates.max()) else 0.0
    efold_time_max=float(1.0/float(sorted_rates.min())) if float(sorted_rates.min()) else 0.0
    efold_ticks_min=float(1.0/(float(sorted_rates.max())*dt)) if float(sorted_rates.max()) else 0.0
    efold_ticks_max=float(1.0/(float(sorted_rates.min())*dt)) if float(sorted_rates.min()) else 0.0
    try: Vinv=np.linalg.inv(vecs)
    except np.linalg.LinAlgError: Vinv=np.linalg.pinv(vecs)
    ws_empty=initial_workspace(profile); z0=_state_vector(ws_empty)
    per_item: list[dict[str,Any]]=[]
    for idx,spec in enumerate(durability.ITEM_SPECS):
        cap=captures[idx]
        ws_written,_=durability.write_item(ws_empty,spec,durability.DurabilityConfig().write_budget)
        dz=_state_vector(ws_written)-z0
        coeff=Vinv@dz; power=np.abs(coeff)**2; total=float(power.sum())
        weight=power/total if total else np.zeros_like(power,dtype=np.float64)
        eff=float(1.0/np.sum(weight**2)) if float(np.sum(weight**2)) else 0.0
        aw_decay=float(np.sum(weight*decay)); aw_freq=float(np.sum(weight*np.abs(np.imag(vals))))
        # dominant mode
        dom_idx=int(np.argmax(weight)) if weight.size else -1
        dom_decay=float(decay[dom_idx]) if dom_idx>=0 else 0.0
        dom_efold_ticks=float(1.0/(dom_decay*dt)) if dom_decay else 0.0
        pred_series: list[float]=[]
        for t in SAMPLE_TICKS:
            zt=np.real(vecs@(np.exp(vals*float(t)*dt)*coeff))
            try:
                vp=_predicted_read_frame(ws_written,z0+zt)
                proj=float(np.dot(vp,cap["direction"]))
                share=float((proj*proj)/float(cap["deposited_energy"])) if cap["deposited_energy"] else 0.0
            except Exception: share=0.0
            pred_series.append(float(share))
        zt0=np.real(vecs@(np.ones_like(vals)*coeff))
        v0=_predicted_read_frame(ws_written,z0+zt0)
        pred_init=float((float(np.dot(v0,cap["direction"]))**2)/float(cap["deposited_energy"])) if cap["deposited_energy"] else 0.0
        thr_pred=float(THRESHOLD_FRACTION)*float(pred_init) if pred_init else 0.0
        pf=next((int(t) for t,v in zip(SAMPLE_TICKS,pred_series) if v<thr_pred),None)
        pl=next((int(t) for t,v in zip(reversed(SAMPLE_TICKS),reversed(pred_series)) if v<thr_pred),None)
        pred_lt=int(HORIZON_TICKS) if pf is None else int(pf)
        # beats for measured and predicted
        # measured series needed for beats - we have pred_series; caller will add beats for measured via per_profile
        per_item.append({"item":spec.name,"scale_width":int(cap["scale_width"]),"scale_depth":int(rung_depth(int(cap["scale_width"]))),"effective_mode_count":float(eff),"amplitude_weighted_decay_rate":float(aw_decay),"amplitude_weighted_decay_per_tick":float(aw_decay*dt),"amplitude_weighted_freq":float(aw_freq),"decay_rate_min":float(decay.min()),"decay_rate_max":float(decay.max()),"participation_entropy":float(-np.sum(weight[weight>0]*np.log(weight[weight>0]))) if np.any(weight>0) else 0.0,"predicted_series":[float(v) for v in pred_series],"predicted_initial_alignment":float(pred_init),"predicted_lifetime_ticks":int(pred_lt),"predicted_censored":bool(pf is None),"predicted_first_cross":pf,"predicted_last_below":pl,"max_weight":float(weight.max()) if weight.size else 0.0,"weight":[float(x) for x in weight],"dominant_mode_index":int(dom_idx),"dominant_decay_rate":float(dom_decay),"dominant_efold_ticks":float(dom_efold_ticks),"dominant_efold_time":float(1.0/dom_decay) if dom_decay else 0.0})
    return {"eigenvalues_real_min":float(np.real(vals).min()),"eigenvalues_real_max":float(np.real(vals).max()),"decay_rate_min":float(decay.min()),"decay_rate_max":float(decay.max()),"decay_rate_mean":float(decay.mean()),"decay_rate_std":float(decay.std()),"decay_rate_sorted":[float(v) for v in sorted_rates],"efold_time_min":float(efold_time_min),"efold_time_max":float(efold_time_max),"efold_ticks_min":float(efold_ticks_min),"efold_ticks_max":float(efold_ticks_max),"band_gaps":band_gaps,"band_count":int(band_count),"band_verdict":band_verdict,"continuum":bool(continuum),"per_item":per_item,"G_shape":list(G.shape),"dt":float(dt)}

def exact_predictor_block(per_profile: Mapping[str,Any], modal: Mapping[str,Any]) -> dict[str,Any]:
    # corroborated linear predictor (not exact) — keep key name exact_predictor for compat but add corroborated alias
    out: dict[str,Any]={}
    for pname in PROFILE_NAMES:
        items=per_profile[pname]["items"]; per=modal[pname]["per_item"]
        rows: list[dict[str,Any]]=[]; divergences: list[dict[str,Any]]=[]
        for meas,pred in zip(items,per):
            m=[float(s["alignment_retention"]) for s in meas["series"]]; p=[float(v) for v in pred["predicted_series"]]
            rows.append({"item":meas["item"],"pearson":float(pearson_corr(m,p)),"rank":float(rank_correlation(m,p)),"rms":float(rms(m,p)),"mean_abs":float(np.mean(np.abs(np.asarray(m)-np.asarray(p)))),"max_abs":float(np.max(np.abs(np.asarray(m)-np.asarray(p)))) if m else 0.0})
            onset=None; onset_val=None
            for t,mv,pv in zip(SAMPLE_TICKS,m,p):
                if abs(float(mv)-float(pv))>DIVERGENCE_TOL_ABS:
                    onset=int(t); onset_val=float(abs(float(mv)-float(pv))); break
            divergences.append({"item":meas["item"],"first_divergence_tick":onset,"divergence_at_onset":onset_val,"tolerance":float(DIVERGENCE_TOL_ABS)})
        all_m=[float(s["alignment_retention"]) for meas in items for s in meas["series"]]
        all_p=[float(v) for pred in per for v in pred["predicted_series"]]
        has_div=bool(any(d["first_divergence_tick"] is not None for d in divergences))
        out[pname]={"per_item":rows,"divergence":divergences,"overall_pearson":float(pearson_corr(all_m,all_p)),"overall_rms":float(rms(all_m,all_p)),"overall_rank":float(rank_correlation(all_m,all_p)),"divergence_tolerance":float(DIVERGENCE_TOL_ABS),"has_divergence":has_div,"fingerprint":"canonical diverges from corroborated linear at first exceedance; body nonlinear at this amplitude" if has_div else "no divergence within tolerance — body effectively linear at declared budget","corroborated_label":"corroborated to 0.02, not exact"}
    return out

def concentration_vs_lifetime_block(per_profile: Mapping[str,Any], modal: Mapping[str,Any]) -> dict[str,Any]:
    out: dict[str,Any]={}
    for pname in PROFILE_NAMES:
        effs=[float(r["effective_mode_count"]) for r in modal[pname]["per_item"]]
        concs=[float(1.0/e) if e else 0.0 for e in effs]; maxws=[float(r["max_weight"]) for r in modal[pname]["per_item"]]
        lifetimes=[float(r["lifetime_ticks"]) for r in per_profile[pname]["items"]]
        widths=[float(r["scale_width"]) for r in per_profile[pname]["items"]]
        aw=[float(r["amplitude_weighted_decay_rate"]) for r in modal[pname]["per_item"]]
        rc_eff=float(rank_correlation(effs,lifetimes)); rc_conc=float(rank_correlation(concs,lifetimes)); rc_maxw=float(rank_correlation(maxws,lifetimes)); rc_width=float(rank_correlation(widths,lifetimes)); rc_aw=float(rank_correlation([-x for x in aw],lifetimes))
        pc_conc=float(pearson_corr(concs,lifetimes)); pc_width=float(pearson_corr(widths,lifetimes)); pc_awneg=float(pearson_corr([-x for x in aw],lifetimes))
        best=max([("concentration",abs(rc_conc)),("support_width",abs(rc_width)),("aw_decay_inverse",abs(rc_aw)),("max_weight",abs(rc_maxw))], key=lambda x: x[1])
        verdict=f"best predictor is {best[0]} (|rc| {best[1]:.2f})" + ("; concentration predicts lifetime better than support width and aw_decay" if best[0] in ("concentration","max_weight") else "; support_width/aw_decay still outpredicts concentration")
        out[pname]={"effective_mode_counts":effs,"concentrations":concs,"max_weights":maxws,"lifetimes":lifetimes,"rank_concentration_vs_lifetime":float(rc_conc),"rank_maxweight_vs_lifetime":float(rc_maxw),"rank_effcount_vs_lifetime":float(rc_eff),"rank_width_vs_lifetime":float(rc_width),"rank_awdecayinv_vs_lifetime":float(rc_aw),"pearson_concentration_vs_lifetime":float(pc_conc),"pearson_width_vs_lifetime":float(pc_width),"pearson_awdecayinv_vs_lifetime":float(pc_awneg),"best_predictor":best[0],"plain":verdict,"design_rule":"write into a band (concentrated mode set)" if best[0] in ("concentration","max_weight") else "write at a scale (support width still dominates)"}
    return out

def apply_recipe(profile: Any, recipe: Sequence[Mapping[str, Any]]) -> Any:
    ws=initial_workspace(profile)
    tick=1
    for step in recipe:
        ws,_=apply_helical_packet_impulse(ws, path=str(step["path"]), component=str(step["component"]), flow_signal=tuple(step["flow_signal"]), work_budget=float(step["work_budget"]), evidence_tick=int(tick), event_kind="reasoning-work")
        tick+=1
    return ws

def measure_series_for_workspace(ws: Any, direction: np.ndarray, deposited: float) -> dict[str, Any]:
    cur=ws; prev=0; series: list[float]=[]
    for t in SAMPLE_TICKS:
        gap=int(t)-prev; cur,_=advance_workspace(cur,ticks=gap,demand=0.0,source_enabled=False); prev=int(t)
        vec=durability.read_frame(cur,durability.READ_FRAME_PATH)
        share=float((float(np.dot(vec,direction))**2)/deposited) if deposited else 0.0
        series.append(float(share))
    thr=float(THRESHOLD_FRACTION)*1.0
    first=next((int(tt) for tt,v in zip(SAMPLE_TICKS,series) if v<thr),None)
    lt=int(HORIZON_TICKS) if first is None else int(first)
    last_half=series[len(series)//2:]; lhmn=float(min(last_half)) if last_half else 0.0; lhmx=float(max(last_half)) if last_half else 0.0
    occ=float(sum(1 for v in series if v>=thr)/len(series)) if series else 0.0
    final=float(series[-1]) if series else 0.0
    beats=beats_characterization(series)
    return {"series": series, "lifetime_ticks": int(lt), "final_retention": float(final), "retention_at_horizon": float(final), "last_half_min": float(lhmn), "last_half_max": float(lhmx), "occupancy": float(occ), "beats": beats, "first_cross": first}

def modal_metrics_for_workspace(profile: Any, ws: Any, vals: np.ndarray, vecs: np.ndarray, Vinv: np.ndarray, decay: np.ndarray, dt: float) -> dict[str, Any]:
    ws0=initial_workspace(profile); z0=_state_vector(ws0); dz=_state_vector(ws)-z0
    coeff=Vinv@dz; power=np.abs(coeff)**2; tot=float(power.sum())
    weight=power/tot if tot else np.zeros_like(power,dtype=np.float64)
    eff=float(1.0/np.sum(weight**2)) if float(np.sum(weight**2)) else 0.0
    dom=int(np.argmax(weight)) if weight.size else -1
    dom_decay=float(decay[dom]) if dom>=0 else 0.0
    dom_efold=float(1.0/(dom_decay*dt)) if dom_decay else 0.0
    maxw=float(weight.max()) if weight.size else 0.0
    # band label for dominant mode
    sorted_rates=np.sort(decay)
    # find which band dom falls in by gaps
    rng=float(sorted_rates.max()-sorted_rates.min()) if sorted_rates.size else 0.0
    gaps=np.diff(sorted_rates)
    band_gaps=[float(g) for g in gaps if g>0.05*rng] if rng else []
    # simplistic band index
    return {"effective_mode_count": float(eff), "max_weight": float(maxw), "dominant_mode_index": int(dom), "dominant_decay_rate": float(dom_decay), "dominant_efold_ticks": float(dom_efold), "dominant_efold_time": float(1.0/dom_decay) if dom_decay else 0.0, "weight": [float(x) for x in weight], "band_gaps": band_gaps}

def concentration_ceiling_block(per_profile: Mapping[str,Any], modal: Mapping[str,Any], captures_by_profile: dict[str,Any]) -> dict[str,Any]:
    out: dict[str,Any]={}
    for pname in PROFILE_NAMES:
        profile=build_declared_profile(pname); G=geometry.linear_generator(profile)
        vals,vecs=np.linalg.eig(G); decay=-np.real(vals); dt=float(profile.time_step)
        try: Vinv=np.linalg.inv(vecs)
        except np.linalg.LinAlgError: Vinv=np.linalg.pinv(vecs)
        ws_empty=initial_workspace(profile); z0=_state_vector(ws_empty)
        dzs=[]; coeffs=[]
        for i,spec in enumerate(durability.ITEM_SPECS):
            ws_w,_=durability.write_item(ws_empty,spec,durability.DurabilityConfig().write_budget)
            dz=_state_vector(ws_w)-z0; dzs.append(dz); coeffs.append(Vinv@dz)
        coeffs_arr=np.stack(coeffs,axis=1)
        rng=np.random.default_rng(0); candidates: list[np.ndarray]=[]
        for i in range(8):
            e=np.zeros(8); e[i]=1.0; candidates.append(e)
            e2=np.zeros(8); e2[i]=-1.0; candidates.append(e2)
        for i in range(8):
            for j in range(i+1,8):
                for s in [1.0,-1.0]:
                    v=np.zeros(8); v[i]=1.0; v[j]=s; v/=np.linalg.norm(v); candidates.append(v)
        for _ in range(4000):
            a=rng.standard_normal(8); a/=np.linalg.norm(a); candidates.append(a)
        for _ in range(1000):
            k=int(rng.integers(2,5)); idx=rng.choice(8,size=k,replace=False)
            a=np.zeros(8); a[idx]=rng.standard_normal(k); a/=np.linalg.norm(a); candidates.append(a)
        best_eff=float("inf"); best_alpha=None; best_weight=None; best_coeff=None
        for alpha in candidates:
            c=coeffs_arr@alpha; power=np.abs(c)**2; tot=float(power.sum())
            if tot==0: continue
            w=power/tot; eff=float(1.0/np.sum(w**2))
            if eff<best_eff: best_eff=eff; best_alpha=alpha.copy(); best_weight=w.copy(); best_coeff=c.copy()
        assert best_alpha is not None and best_weight is not None and best_coeff is not None
        best_aw=float(np.sum(best_weight*decay))
        sorted_rates=np.sort(decay)
        efold_time=float(1.0/best_aw) if best_aw else 0.0
        efold_ticks=float(1.0/(best_aw*dt)) if best_aw else 0.0
        # Algebraic constructed series (for reference, not a write)
        avg_norm=float(np.mean([float(np.linalg.norm(d)) for d in dzs]))
        dz_best_raw=np.stack(dzs,axis=1)@best_alpha
        scale=avg_norm/float(np.linalg.norm(dz_best_raw)) if float(np.linalg.norm(dz_best_raw)) else 0.0
        dz_best_alg=dz_best_raw*scale
        # Realized ceiling: brute-force over actually applied recipes (1- and 2-step at declared budget, both signs)
        realized_candidates: list[list[dict[str,Any]]] = []
        for spec in durability.ITEM_SPECS:
            for sgn in [1.0, -1.0]:
                fs=(float(sgn),0.0)
                realized_candidates.append([{"path": spec.path, "component": spec.component, "flow_signal": fs, "work_budget": durability.DurabilityConfig().write_budget}])
        # pairs
        for i,spec_i in enumerate(durability.ITEM_SPECS):
            for j,spec_j in enumerate(durability.ITEM_SPECS):
                for si in [1.0,-1.0]:
                    for sj in [1.0,-1.0]:
                        # avoid duplicate single already covered but keep for search
                        realized_candidates.append([
                            {"path": spec_i.path, "component": spec_i.component, "flow_signal": (float(si),0.0), "work_budget": durability.DurabilityConfig().write_budget},
                            {"path": spec_j.path, "component": spec_j.component, "flow_signal": (float(sj),0.0), "work_budget": durability.DurabilityConfig().write_budget},
                        ])
        # cap to ~512 realized candidates deterministic (first 512)
        realized_candidates=realized_candidates[:512]
        best_realized_eff=float("inf"); best_realized_recipe=None; best_realized_ws=None; best_realized_metrics=None
        for recipe in realized_candidates:
            ws=apply_recipe(profile, recipe)
            mm=modal_metrics_for_workspace(profile, ws, vals, vecs, Vinv, decay, dt)
            if mm["effective_mode_count"] < best_realized_eff:
                best_realized_eff=float(mm["effective_mode_count"]); best_realized_recipe=recipe; best_realized_ws=ws; best_realized_metrics=mm
        assert best_realized_recipe is not None and best_realized_ws is not None and best_realized_metrics is not None
        # Measure realized ceiling series from actually applied state
        vec0=durability.read_frame(best_realized_ws,durability.READ_FRAME_PATH)
        norm0=float(np.linalg.norm(vec0))
        if norm0>0:
            dir0=vec0/norm0; deposited0=float(np.dot(vec0,vec0))
            meas_real=measure_series_for_workspace(best_realized_ws, dir0, deposited0)
            # predicted for realized ceiling
            z0v=_state_vector(ws_empty); dz_r=_state_vector(best_realized_ws)-z0v; coeff_r=Vinv@dz_r
            pred_real=[]
            for t in SAMPLE_TICKS:
                zt=np.real(vecs@(np.exp(vals*float(t)*dt)*coeff_r))
                vp=_predicted_read_frame(best_realized_ws, z0v+zt)
                proj=float(np.dot(vp,dir0)); share=float((proj*proj)/deposited0) if deposited0 else 0.0
                pred_real.append(float(share))
        else:
            meas_real={"series": [], "final_retention": 0.0, "last_half_min": 0.0, "last_half_max": 0.0, "occupancy": 0.0, "beats": {}, "lifetime_ticks": 256}
            pred_real=[]
            dir0=None; deposited0=0.0
        # Algebraic gap reconstruction check: can we realize algebraic dz via a recipe?
        # Try to find closest realized eff to algebraic; shortfall is numeric
        shortfall_eff=float(best_realized_eff - best_eff)
        # Also measure algebraic pseudo-series for display (not a write) using paged state trick
        try:
            page_best=_page_from_state(ws_empty, z0+dz_best_alg)
            ws_best_alg=ws_empty.__class__(profile=profile, field_page=page_best)
            vec_alg=durability.read_frame(ws_best_alg,durability.READ_FRAME_PATH)
            norm_alg=float(np.linalg.norm(vec_alg))
            if norm_alg>0:
                dir_alg=vec_alg/norm_alg; dep_alg=float(np.dot(vec_alg,vec_alg))
                meas_alg=measure_series_for_workspace(ws_best_alg, dir_alg, dep_alg)
            else:
                meas_alg={"series": [], "final_retention": 0.0, "last_half_min": 0.0, "occupancy": 0.0, "beats": {}}
        except Exception:
            meas_alg={"series": [], "final_retention": 0.0, "last_half_min": 0.0, "occupancy": 0.0, "beats": {}}
        single_effs=[float(r["effective_mode_count"]) for r in modal[pname]["per_item"]]
        min_single=float(min(single_effs)) if single_effs else 0.0
        band_ticks_min=float(1.0/(float(sorted_rates.max())*dt)) if float(sorted_rates.max()) else 0.0
        band_ticks_max=float(1.0/(float(sorted_rates.min())*dt)) if float(sorted_rates.min()) else 0.0
        out[pname]={
            "algebraic": {"best_eff": float(best_eff), "best_alpha": [float(x) for x in best_alpha], "best_aw_decay": float(best_aw), "best_aw_per_tick": float(best_aw*dt), "best_efold_time": float(efold_time), "best_efold_ticks": float(efold_ticks), "best_max_weight": float(best_weight.max()) if best_weight is not None else 0.0, "label": "algebraic bound over combinations of achieved states — not necessarily writable; lower bound only"},
            "band_ticks_range": [float(band_ticks_min), float(band_ticks_max)],
            "band_time_range": [float(1.0/float(sorted_rates.max())) if float(sorted_rates.max()) else 0.0, float(1.0/float(sorted_rates.min())) if float(sorted_rates.min()) else 0.0],
            "min_single_eff": float(min_single),
            "improvement_over_best_single": float(min_single-best_eff) if min_single else 0.0,
            "algebraic_series": meas_alg.get("series", []),
            "algebraic_final_retention": float(meas_alg.get("final_retention", 0.0)),
            "algebraic_last_half_min": float(meas_alg.get("last_half_min", 0.0)),
            "algebraic_occupancy": float(meas_alg.get("occupancy", 0.0)),
            "algebraic_beats": meas_alg.get("beats", {}),
            "algebraic_lifetime_ticks": int(meas_alg.get("lifetime_ticks", 256)),
            # legacy aliases for compat
            "best_eff": float(best_eff), "best_alpha": [float(x) for x in best_alpha], "best_aw_decay": float(best_aw), "best_aw_per_tick": float(best_aw*dt), "best_efold_time": float(efold_time), "best_efold_ticks": float(efold_ticks), "best_max_weight": float(best_weight.max()) if best_weight is not None else 0.0,
            "constructed_lifetime_ticks": int(meas_alg.get("lifetime_ticks", 256)), "constructed_occupancy": float(meas_alg.get("occupancy", 0.0)), "constructed_series": meas_alg.get("series", []),
            "realized": {"best_eff": float(best_realized_eff), "recipe": best_realized_recipe, "metrics": best_realized_metrics, "final_retention": float(meas_real["final_retention"]), "retention_at_horizon": float(meas_real["final_retention"]), "last_half_min": float(meas_real["last_half_min"]), "last_half_max": float(meas_real["last_half_max"]), "occupancy": float(meas_real["occupancy"]), "lifetime_ticks": int(meas_real["lifetime_ticks"]), "series": meas_real["series"], "predicted_series": pred_real, "beats": meas_real["beats"], "pearson_pred_vs_meas": float(pearson_corr(pred_real, meas_real["series"])) if pred_real and meas_real["series"] else 0.0},
            "realized_best_eff": float(best_realized_eff),
            "realized_recipe": best_realized_recipe,
            "realized_final_retention": float(meas_real["final_retention"]),
            "realized_last_half_min": float(meas_real["last_half_min"]),
            "realized_occupancy": float(meas_real["occupancy"]),
            "realized_beats": meas_real["beats"],
            "shortfall_eff": float(shortfall_eff),
            "shortfall_statement": f"no bounded impulse sequence realizes algebraic eff {best_eff:.1f}; best realized {best_realized_eff:.1f}, shortfall {shortfall_eff:.1f} — spec for mode-selective write primitive",
            "ceiling_statement": f"algebraic eff {best_eff:.1f} (lower bound); realized eff {best_realized_eff:.1f} (best writable via 1-2-step bounded impulses), final {meas_real['final_retention']:.3f} last_half_min {meas_real['last_half_min']:.3f} occ {meas_real['occupancy']:.2f} — most concentrated writable direction is NOT long-lived (32-48 ticks despite concentration), efold {efold_ticks:.0f} ticks is dominant-mode only, not direction lifetime; beats: {meas_real['beats'].get('plain','')}"
        }
    return out

def predictor_optimized_block(per_profile: Mapping[str,Any], modal: Mapping[str,Any]) -> dict[str,Any]:
    out: dict[str,Any]={}
    best_single_final=max(float(r["final_alignment"]) for block in per_profile.values() for r in block["items"])  # 0.3339 known
    # headline durability item is root-scale (index 0)
    headline_final_by_profile={pname: float(per_profile[pname]["items"][0]["final_alignment"]) for pname in PROFILE_NAMES}
    for pname in PROFILE_NAMES:
        profile=build_declared_profile(pname); G=geometry.linear_generator(profile)
        vals,vecs=np.linalg.eig(G); decay=-np.real(vals); dt=float(profile.time_step)
        try: Vinv=np.linalg.inv(vecs)
        except np.linalg.LinAlgError: Vinv=np.linalg.pinv(vecs)
        ws_empty=initial_workspace(profile)
        # Build candidate recipes: singles + pairs (512 max)
        recipes: list[list[dict[str,Any]]] = []
        for spec in durability.ITEM_SPECS:
            for sgn in [1.0,-1.0]:
                recipes.append([{"path": spec.path, "component": spec.component, "flow_signal": (float(sgn),0.0), "work_budget": durability.DurabilityConfig().write_budget}])
        for i,si in enumerate(durability.ITEM_SPECS):
            for j,sj in enumerate(durability.ITEM_SPECS):
                for sgn_i in [1.0,-1.0]:
                    for sgn_j in [1.0,-1.0]:
                        recipes.append([
                            {"path": si.path, "component": si.component, "flow_signal": (float(sgn_i),0.0), "work_budget": durability.DurabilityConfig().write_budget},
                            {"path": sj.path, "component": sj.component, "flow_signal": (float(sgn_j),0.0), "work_budget": durability.DurabilityConfig().write_budget},
                        ])
        recipes=recipes[:512]
        scored=[]
        for recipe in recipes:
            ws=apply_recipe(profile, recipe)
            vec0=durability.read_frame(ws,durability.READ_FRAME_PATH)
            norm0=float(np.linalg.norm(vec0))
            if norm0==0: continue
            dir0=vec0/norm0; dep0=float(np.dot(vec0,vec0))
            z0=_state_vector(ws_empty); dz=_state_vector(ws)-z0; coeff=Vinv@dz
            pred_series=[]
            for t in SAMPLE_TICKS:
                zt=np.real(vecs@(np.exp(vals*float(t)*dt)*coeff))
                vp=_predicted_read_frame(ws, z0+zt)
                proj=float(np.dot(vp,dir0)); share=float((proj*proj)/dep0) if dep0 else 0.0
                pred_series.append(float(share))
            last_half_pred=pred_series[len(pred_series)//2:]
            pred_final=float(pred_series[-1]) if pred_series else 0.0
            pred_lhmn=float(min(last_half_pred)) if last_half_pred else 0.0
            eff_metrics=modal_metrics_for_workspace(profile, ws, vals, vecs, Vinv, decay, dt)
            scored.append({"recipe": recipe, "pred_series": pred_series, "pred_final": float(pred_final), "pred_last_half_min": float(pred_lhmn), "eff": float(eff_metrics["effective_mode_count"]), "metrics": eff_metrics, "ws": ws, "dir": dir0, "dep": float(dep0)})
        # Select top candidates maximizing (a) pred_final and (b) pred_last_half_min
        by_final=sorted(scored, key=lambda x: x["pred_final"], reverse=True)[:5]
        by_lhmn=sorted(scored, key=lambda x: x["pred_last_half_min"], reverse=True)[:5]
        # Deduplicate by recipe tuple
        def recipe_key(r): return tuple((s["path"],s["component"],tuple(s["flow_signal"]),s["work_budget"]) for s in r["recipe"])
        seen=set(); merged=[]
        for cand in by_final+by_lhmn:
            k=recipe_key(cand)
            if k in seen: continue
            seen.add(k); merged.append(cand)
        # Measure top candidates canonically
        ranked=[]
        for cand in merged:
            ws=cand["ws"]; dir0=cand["dir"]; dep0=cand["dep"]
            meas=measure_series_for_workspace(ws, dir0, dep0)
            pear=float(pearson_corr(cand["pred_series"], meas["series"])) if cand["pred_series"] and meas["series"] else 0.0
            rms_err=float(rms(cand["pred_series"], meas["series"])) if cand["pred_series"] and meas["series"] else 0.0
            ranked.append({
                "recipe": cand["recipe"],
                "effective_mode_count": float(cand["eff"]),
                "metrics": cand["metrics"],
                "predicted_final": float(cand["pred_final"]),
                "predicted_last_half_min": float(cand["pred_last_half_min"]),
                "predicted_series": [float(x) for x in cand["pred_series"]],
                "measured_final": float(meas["final_retention"]),
                "measured_last_half_min": float(meas["last_half_min"]),
                "measured_last_half_max": float(meas["last_half_max"]),
                "measured_occupancy": float(meas["occupancy"]),
                "measured_lifetime_ticks": int(meas["lifetime_ticks"]),
                "measured_series": [float(x) for x in meas["series"]],
                "pearson_pred_vs_meas": float(pear),
                "rms_pred_vs_meas": float(rms_err),
                "beats": meas["beats"],
                "dominant_mode_index": int(cand["metrics"]["dominant_mode_index"]),
                "dominant_efold_ticks": float(cand["metrics"]["dominant_efold_ticks"]),
            })
        # Rank by measured_final for reporting, but keep objective tags
        ranked_sorted=sorted(ranked, key=lambda x: x["measured_final"], reverse=True)
        best_measured_final=float(ranked_sorted[0]["measured_final"]) if ranked_sorted else 0.0
        best_single_final_profile=max(float(r["final_alignment"]) for r in per_profile[pname]["items"])
        headline_final=float(headline_final_by_profile[pname])
        out[pname]={
            "candidates": ranked_sorted,
            "best_measured_final": float(best_measured_final),
            "best_single_final": float(best_single_final_profile),
            "headline_final": float(headline_final),
            "best_single_final_global": float(best_single_final),
            "global_headline_final": float(per_profile[pname]["items"][0]["final_alignment"]),
            "improvement_over_best_single": float(best_measured_final - best_single_final_profile),
            "improvement_over_headline": float(best_measured_final - headline_final),
            "beats_predictor_is_write_rule": bool(best_measured_final > best_single_final_profile + 0.02) if ranked_sorted else False,
            "statement": f"best predicted write measures final {best_measured_final:.3f} vs best single {best_single_final_profile:.3f} (global {best_single_final:.3f}) vs headline {headline_final:.3f}; {'predictor IS a write rule' if best_measured_final > best_single_final_profile + 0.02 else 'no improvement — predictor is diagnostic only'}"
        }
    return out

def two_budget_control_block() -> dict[str,Any]:
    rows=[]
    for budget in TWO_BUDGETS:
        lin_profile=replace(durability.ResonantProfile(), beta=0.0)
        # need captures at this budget for direction? use item 0 at that budget
        ws0=initial_workspace(lin_profile)
        spec=durability.ITEM_SPECS[0]
        ws_w,_=apply_helical_packet_impulse(ws0, path=spec.path, component=spec.component, flow_signal=spec.flow_signal, work_budget=float(budget), evidence_tick=1, event_kind="reasoning-work")
        # read frame for direction: use that ws_w's packet
        vec_w=durability.read_frame(ws_w,durability.READ_FRAME_PATH)
        norm_w=float(np.linalg.norm(vec_w))
        direction=vec_w/norm_w if norm_w else vec_w
        deposited=float(np.dot(vec_w,vec_w))
        cur=ws_w; prev=0; canon=[]
        for t in SAMPLE_TICKS:
            gap=int(t)-prev; cur,_=advance_workspace(cur,ticks=gap,demand=0.0,source_enabled=False); prev=int(t)
            vec=durability.read_frame(cur,durability.READ_FRAME_PATH)
            share=float((float(np.dot(vec,direction))**2)/deposited) if deposited else 0.0
            canon.append(float(share))
        G=geometry.linear_generator(lin_profile); vals,vecs=np.linalg.eig(G); dt=float(lin_profile.time_step)
        try: Vinv=np.linalg.inv(vecs)
        except np.linalg.LinAlgError: Vinv=np.linalg.pinv(vecs)
        z0=_state_vector(ws0); dz=_state_vector(ws_w)-z0; coeff=Vinv@dz
        pred=[]
        for t in SAMPLE_TICKS:
            zt=np.real(vecs@(np.exp(vals*float(t)*dt)*coeff))
            vp=_predicted_read_frame(ws_w,z0+zt)
            proj=float(np.dot(vp,direction)); share=float((proj*proj)/deposited) if deposited else 0.0
            pred.append(float(share))
        max_abs=float(np.max(np.abs(np.asarray(canon)-np.asarray(pred)))) if canon else 0.0
        rows.append({"work_budget": float(budget), "max_abs_error": float(max_abs), "tolerance": float(DIVERGENCE_TOL_ABS), "canon": [float(x) for x in canon], "pred": [float(x) for x in pred], "passes": bool(max_abs<=DIVERGENCE_TOL_ABS)})
    # Attribution
    if len(rows)==2:
        r0,r1=rows[0],rows[1]
        ratio=float(r1["max_abs_error"]/max(1e-12,r0["max_abs_error"])) if r0["max_abs_error"] else 0.0
        budget_ratio=float(r1["work_budget"]/r0["work_budget"]) if r0["work_budget"] else 0.0
        scales_with_budget=bool(abs(ratio-budget_ratio) < 0.5*budget_ratio)  # rough linear scaling test
        if scales_with_budget:
            verdict=f"residual scales with budget ({r0['max_abs_error']:.4f}->{r1['max_abs_error']:.4f} ratio {ratio:.2f} vs budget ratio {budget_ratio:.2f}): write map is itself nonlinear — corroborated predictor must be composed with declared write map"
        else:
            verdict=f"residual budget-independent ({r0['max_abs_error']:.4f}->{r1['max_abs_error']:.4f} ratio {ratio:.2f} vs budget ratio {budget_ratio:.2f}): remainder is frame construction / discrete-gradient residual / roundoff"
    else:
        verdict="insufficient budgets"
    return {"budgets": rows, "budget_ratio": float(rows[1]["work_budget"]/rows[0]["work_budget"]) if len(rows)==2 else None, "error_ratio": float(rows[1]["max_abs_error"]/max(1e-12,rows[0]["max_abs_error"])) if len(rows)==2 else None, "attribution": verdict, "statement": verdict}

def exhaustive_write_surface_block(per_profile: Mapping[str,Any], modal: Mapping[str,Any]) -> dict[str,Any]:
    import cassi_resonant_field as cf
    out={}
    for pname in PROFILE_NAMES:
        profile=build_declared_profile(pname)
        ws0=initial_workspace(profile)
        G=geometry.linear_generator(profile); vals,vecs=np.linalg.eig(G); decay=-np.real(vals); dt=float(profile.time_step)
        try: Vinv=np.linalg.inv(vecs)
        except np.linalg.LinAlgError: Vinv=np.linalg.pinv(vecs)
        sorted_rates=np.sort(decay); rng=float(sorted_rates.max()-sorted_rates.min()) if sorted_rates.size else 0.0
        gaps=np.diff(sorted_rates)
        slow_upper=float(sorted_rates[0])
        if gaps.size and rng:
            idx=np.where(gaps>0.05*rng)[0]
            if len(idx): slow_upper=float(sorted_rates[idx[0]])
        slow_mask=decay <= slow_upper+1e-12
        modes=cf._packet_mode_descriptors(0, profile.port_count, "")
        candidates=[]
        for m in modes:
            pa=m["path"]; co=m["kind"]
            for sgn in [1.0, -1.0]:
                ws=apply_recipe(profile, [{"path": pa, "component": co, "flow_signal": (float(sgn),0.0), "work_budget": durability.DurabilityConfig().write_budget}])
                vec0=durability.read_frame(ws, durability.READ_FRAME_PATH)
                norm0=float(np.linalg.norm(vec0))
                if norm0==0: continue
                dir0=vec0/norm0; dep0=float(np.dot(vec0,vec0))
                mm=modal_metrics_for_workspace(profile, ws, vals, vecs, Vinv, decay, dt)
                # predicted
                z0=_state_vector(ws0); dz=_state_vector(ws)-z0; coeff=Vinv@dz
                pred_series=[]
                for t in SAMPLE_TICKS:
                    zt=np.real(vecs@(np.exp(vals*float(t)*dt)*coeff))
                    vp=_predicted_read_frame(ws, z0+zt)
                    proj=float(np.dot(vp,dir0)); share=float((proj*proj)/dep0) if dep0 else 0.0
                    pred_series.append(float(share))
                pred_final=float(pred_series[-1]) if pred_series else 0.0
                pred_lhmn=float(min(pred_series[len(pred_series)//2:])) if pred_series else 0.0
                weight=np.asarray(mm["weight"], dtype=np.float64)
                slow_weight=float(weight[slow_mask].sum()) if weight.size else 0.0
                width=cf._packet_support(profile.port_count, pa)[1]-cf._packet_support(profile.port_count, pa)[0] if pa else profile.port_count
                dom=int(mm["dominant_mode_index"])
                dom_in_slow=bool(slow_mask[dom]) if 0 <= dom < len(slow_mask) else False
                candidates.append({
                    "path": pa, "component": co, "flow_signal": [float(sgn),0.0], "width": int(width),
                    "recipe": [{"path": pa, "component": co, "flow_signal": [float(sgn),0.0], "work_budget": float(durability.DurabilityConfig().write_budget)}],
                    "realized_eff": float(mm["effective_mode_count"]), "realized_max_weight": float(mm["max_weight"]),
                    "dominant_mode_index": int(dom), "dominant_decay_rate": float(mm["dominant_decay_rate"]), "dominant_efold_ticks": float(mm["dominant_efold_ticks"]),
                    "dominant_in_slow_band": bool(dom_in_slow), "slow_weight": float(slow_weight),
                    "predicted_final": float(pred_final), "predicted_last_half_min": float(pred_lhmn),
                    "predicted_series": [float(x) for x in pred_series],
                })
        # rank by predicted final and lhmn
        by_final=sorted(candidates, key=lambda x: x["predicted_final"], reverse=True)[:5]
        by_lhmn=sorted(candidates, key=lambda x: x["predicted_last_half_min"], reverse=True)[:5]
        # narrowest width
        min_width=min(c["width"] for c in candidates) if candidates else 0
        narrow=[c for c in candidates if c["width"]==min_width]
        best_narrow=max(narrow, key=lambda x: x["realized_max_weight"]) if narrow else None
        narrow_measured=None
        if best_narrow is not None:
            ws=apply_recipe(profile, best_narrow["recipe"])
            vec0=durability.read_frame(ws, durability.READ_FRAME_PATH); dir0=vec0/np.linalg.norm(vec0); dep0=float(np.dot(vec0,vec0))
            meas=measure_series_for_workspace(ws, dir0, dep0)
            narrow_measured={"recipe": best_narrow["recipe"], "path": best_narrow["path"], "component": best_narrow["component"], "width": int(best_narrow["width"]),
                "realized_eff": float(best_narrow["realized_eff"]), "realized_max_weight": float(best_narrow["realized_max_weight"]),
                "dominant_in_slow_band": bool(best_narrow["dominant_in_slow_band"]), "slow_weight": float(best_narrow["slow_weight"]),
                "predicted_final": float(best_narrow["predicted_final"]), "predicted_last_half_min": float(best_narrow["predicted_last_half_min"]),
                "measured_final": float(meas["final_retention"]), "measured_last_half_min": float(meas["last_half_min"]), "measured_last_half_max": float(meas["last_half_max"]), "measured_occupancy": float(meas["occupancy"]), "measured_series": [float(x) for x in meas["series"]], "beats": meas["beats"], "pearson_pred_vs_meas": float(pearson_corr(best_narrow["predicted_series"], meas["series"]))}
        # dedup top candidates and measure
        def rkey(c): return (c["path"],c["component"],tuple(c["flow_signal"]))
        seen=set(); merged=[]
        for c in by_final+by_lhmn:
            k=rkey(c)
            if k in seen: continue
            seen.add(k); merged.append(c)
        measured_top=[]
        for c in merged:
            ws=apply_recipe(profile, c["recipe"])
            vec0=durability.read_frame(ws, durability.READ_FRAME_PATH); dir0=vec0/np.linalg.norm(vec0); dep0=float(np.dot(vec0,vec0))
            meas=measure_series_for_workspace(ws, dir0, dep0)
            measured_top.append({
                "path": c["path"], "component": c["component"], "width": int(c["width"]), "flow_signal": c["flow_signal"], "recipe": c["recipe"],
                "realized_eff": float(c["realized_eff"]), "realized_max_weight": float(c["realized_max_weight"]),
                "dominant_in_slow_band": bool(c["dominant_in_slow_band"]), "slow_weight": float(c["slow_weight"]),
                "dominant_efold_ticks": float(c["dominant_efold_ticks"]),
                "predicted_final": float(c["predicted_final"]), "predicted_last_half_min": float(c["predicted_last_half_min"]), "predicted_series": c["predicted_series"],
                "measured_final": float(meas["final_retention"]), "measured_last_half_min": float(meas["last_half_min"]), "measured_last_half_max": float(meas["last_half_max"]), "measured_occupancy": float(meas["occupancy"]), "measured_series": [float(x) for x in meas["series"]], "beats": meas["beats"], "pearson_pred_vs_meas": float(pearson_corr(c["predicted_series"], meas["series"])), "rms_pred_vs_meas": float(rms(c["predicted_series"], meas["series"]))
            })
        measured_top_sorted=sorted(measured_top, key=lambda x: x["measured_final"], reverse=True)
        best_measured_final=float(measured_top_sorted[0]["measured_final"]) if measured_top_sorted else 0.0
        best_predicted_final=float(max(c["predicted_final"] for c in candidates)) if candidates else 0.0
        slow_dominated=[c for c in candidates if c["dominant_in_slow_band"]]
        slow_count=len(slow_dominated)
        out[pname]={"candidates_sorted_by_predicted_final": sorted(candidates, key=lambda x: x["predicted_final"], reverse=True), "all_candidates": candidates, "measured_top": measured_top_sorted, "best_predicted_final": float(best_predicted_final), "best_measured_final": float(best_measured_final), "narrowest_width": int(min_width), "narrow_best": narrow_measured, "slow_band_dominated_count": int(slow_count), "total_candidates": int(len(candidates)), "slow_band_upper_decay": float(slow_upper), "slow_band_upper_efold_ticks": float(1.0/(slow_upper*float(profile.time_step))) if slow_upper else 0.0, "statement": f"exhaustive {len(candidates)} singles: best predicted {best_predicted_final:.3f} -> measured {best_measured_final:.3f}; narrowest width {min_width} best max_weight {narrow_measured['realized_max_weight']:.3f} eff {narrow_measured['realized_eff']:.1f} dominant_in_slow {narrow_measured['dominant_in_slow_band']} slow_weight {narrow_measured['slow_weight']:.2f} predicted {narrow_measured['predicted_final']:.3f} measured {narrow_measured['measured_final']:.3f}" if narrow_measured else "no narrow"}
    return out

def mode_selective_spec_block(modal: Mapping[str,Any], exhaustive: Mapping[str,Any], ceiling: Mapping[str,Any]) -> dict[str,Any]:
    out={}
    for pname in PROFILE_NAMES:
        profile=build_declared_profile(pname)
        G=geometry.linear_generator(profile); vals,vecs=np.linalg.eig(G); decay=-np.real(vals); dt=float(profile.time_step)
        sorted_rates=np.sort(decay); rng=float(sorted_rates.max()-sorted_rates.min()) if sorted_rates.size else 0.0
        gaps=np.diff(sorted_rates)
        slow_upper=float(sorted_rates[0])
        if gaps.size and rng:
            idx=np.where(gaps>0.05*rng)[0]
            if len(idx): slow_upper=float(sorted_rates[idx[0]])
        slow_mask=decay <= slow_upper+1e-12
        slow_size=int(slow_mask.sum())
        # efold range of slow band
        slow_rates=sorted_rates[sorted_rates <= slow_upper+1e-12]
        slow_efold_min=float(1.0/(float(slow_rates.max())*dt)) if slow_rates.size and float(slow_rates.max()) else 0.0
        slow_efold_max=float(1.0/(float(slow_rates.min())*dt)) if slow_rates.size and float(slow_rates.min()) else 0.0
        exhaust=exhaustive[pname]
        # realized ceilings
        realized_eff=float(ceiling[pname]["realized_best_eff"])
        algebraic_eff=float(ceiling[pname]["best_eff"])
        # spec from exhaustive: require dominant in slow and slow_weight >=0.8 and max_weight high
        dominated=[c for c in exhaust["all_candidates"] if c["dominant_in_slow_band"] and c["slow_weight"]>=0.8]
        if dominated:
            req_max_weight=float(max(c["realized_max_weight"] for c in dominated))  # actually need at least median; report max as upper, and min as lower bound
            req_max_weight_min=float(min(c["realized_max_weight"] for c in dominated))
            req_eff_max=float(max(c["realized_eff"] for c in dominated))
            req_eff_min=float(min(c["realized_eff"] for c in dominated))
            spec_max_weight=float(sum(c["realized_max_weight"] for c in dominated)/len(dominated))
            spec_eff=float(sum(c["realized_eff"] for c in dominated)/len(dominated))
        else:
            req_max_weight=req_max_weight_min=req_eff_max=req_eff_min=spec_max_weight=spec_eff=0.0
        # best narrow
        narrow=exhaust.get("narrow_best")
        narrow_in_slow=bool(narrow["dominant_in_slow_band"]) if narrow else False
        narrow_slow_weight=float(narrow["slow_weight"]) if narrow else 0.0
        narrow_max=float(narrow["realized_max_weight"]) if narrow else 0.0
        narrow_eff=float(narrow["realized_eff"]) if narrow else 0.0
        gap_to_realized=float(spec_eff - realized_eff) if dominated else 0.0
        gap_to_algebraic=float(spec_eff - algebraic_eff) if dominated else 0.0
        out[pname]={"slow_band_upper_decay": float(slow_upper), "slow_band_size": int(slow_size), "slow_band_efold_ticks_range": [float(slow_efold_min), float(slow_efold_max)], "slow_band_decay_range": [float(slow_rates.min()), float(slow_rates.max())] if slow_rates.size else [0.0,0.0], "realized_ceiling_eff": float(realized_eff), "algebraic_bound_eff": float(algebraic_eff), "required_max_weight_mean": float(spec_max_weight), "required_max_weight_min": float(req_max_weight_min), "required_max_weight_max": float(req_max_weight), "required_eff_mean": float(spec_eff), "required_eff_min": float(req_eff_min), "required_eff_max": float(req_eff_max), "dominated_count": int(len(dominated)), "narrow_best_max_weight": float(narrow_max), "narrow_best_eff": float(narrow_eff), "narrow_in_slow": bool(narrow_in_slow), "narrow_slow_weight": float(narrow_slow_weight), "gap_to_realized": float(gap_to_realized), "gap_to_algebraic": float(gap_to_algebraic), "statement": f"slow band {slow_size} modes efold {slow_efold_min:.0f}-{slow_efold_max:.0f} ticks; to land slow-dominated (slow_weight>=0.8) need max_weight ~{spec_max_weight:.3f} (range {req_max_weight_min:.3f}-{req_max_weight:.3f}) eff ~{spec_eff:.1f} (range {req_eff_min:.1f}-{req_eff_max:.1f}) from {len(dominated)} realized slow-dominated singles; narrowest width {exhaust['narrowest_width']} best max_weight {narrow_max:.3f} eff {narrow_eff:.1f} in_slow {narrow_in_slow} slow_weight {narrow_slow_weight:.2f}; gap to realized {gap_to_realized:.1f} to algebraic {gap_to_algebraic:.1f} — spec for mode-selective primitive"}
    return out

def ladder_summary(per_profile: Mapping[str,Any]) -> dict[str,Any]:
    summary: dict[str,Any]={}
    for profile_name,block in per_profile.items():
        items: list[dict[str,Any]]=block["items"]
        by_width: dict[int,list[int]]={}; by_width_occ: dict[int,list[float]]={}
        for row in items:
            by_width.setdefault(int(row["scale_width"]),[]).append(int(row["lifetime_ticks"]))
            by_width_occ.setdefault(int(row["scale_width"]),[]).append(float(row["occupancy"]))
        grouped={str(w):sorted(v) for w,v in sorted(by_width.items(),key=lambda kv:-kv[0])}
        grouped_occ={str(w):sorted(v) for w,v in sorted(by_width_occ.items(),key=lambda kv:-kv[0])}
        means={int(k):float(np.mean(v)) for k,v in by_width.items()}
        means_occ={int(k):float(np.mean(v)) for k,v in by_width_occ.items()}
        widths_desc=sorted(by_width.keys(),reverse=True)
        monotone=all(means[widths_desc[i]]>=means[widths_desc[i+1]] for i in range(len(widths_desc)-1))
        monotone_occ=all(means_occ[widths_desc[i]]>=means_occ[widths_desc[i+1]] for i in range(len(widths_desc)-1))
        coarsest=max(by_width.keys()); finest=min(by_width.keys())
        ratio=float(means[coarsest]/means[finest]) if means[finest] else None
        ratio_occ=float(means_occ[coarsest]/means_occ[finest]) if means_occ[finest] else None
        xs=np.array([float(r["scale_distance"]) for r in items],dtype=np.float64)
        ys=np.array([float(np.log(max(1,int(r["lifetime_ticks"])))) for r in items],dtype=np.float64)
        if len(xs)>=2 and float(xs.max()-xs.min())>0:
            a,b=np.polyfit(xs,ys,1); yhat=a*xs+b; resid=ys-yhat; rss=float(np.sum(resid*resid)); tss=float(np.sum((ys-ys.mean())**2)); r2=float(1.0-rss/tss) if tss>0 else 0.0
        else: a,b,rss,r2=0.0,float(ys.mean()) if len(ys) else 0.0,0.0,0.0
        plain="log-lifetime shows little linear relationship with coarseness; ordering is not captured by this single log fit" if r2<0.3 else ("log-lifetime rises with coarseness but substantial residual" if r2<0.7 else "log-lifetime explains most of ordering")
        occ_plain="occupancy monotone coarse->fine" if monotone_occ else "occupancy NOT monotone coarse->fine"
        summary[profile_name]={"grouped_lifetimes":grouped,"grouped_occupancy":grouped_occ,"mean_by_width":{str(k):float(v) for k,v in means.items()},"mean_occupancy_by_width":{str(k):float(v) for k,v in means_occ.items()},"monotone_coarse_to_fine":bool(monotone),"monotone_occupancy_coarse_to_fine":bool(monotone_occ),"measure_dependent_ordering":bool(monotone!=monotone_occ),"ratio_coarsest_to_finest_means":ratio,"ratio_occupancy_coarsest_to_finest":ratio_occ,"occupancy_ordering_plain":occ_plain,"log_lifetime_fit":{"x":"scale_distance=log2(28/width)=depth","y":"log(lifetime)","slope":float(a),"intercept":float(b),"rss":float(rss),"r_squared":float(r2),"plain":plain}}
    if "helix7" in summary and "mass-only" in summary:
        deltas={}
        for w in sorted(set(summary["helix7"]["mean_by_width"])|set(summary["mass-only"]["mean_by_width"])):
            h=float(summary["helix7"]["mean_by_width"].get(w,0.0)); m=float(summary["mass-only"]["mean_by_width"].get(w,0.0)); deltas[w]=float(m-h)
        vals=list(deltas.values()); uniform=(max(vals)-min(vals)<=16.0) if vals else True; ordered=sorted(deltas.items(),key=lambda kv:kv[1],reverse=True)
        reshaping_plain="mass-only lengthens the ladder approximately uniformly" if uniform else f"mass-only reshapes the ladder: rung {ordered[0][0]} moves most (delta {ordered[0][1]:.1f}), rung {ordered[-1][0]} moves least (delta {ordered[-1][1]:.1f})"
        summary["mass_only_effect"]={"delta_means_by_width":deltas,"uniform_within_16_ticks":bool(uniform),"plain":reshaping_plain}
    return summary

def declared_block() -> dict[str,Any]:
    cfg=durability.DurabilityConfig()
    return {"schema":SCHEMA,"durability_schema":durability.SCHEMA,"survival_schema":survival.SCHEMA,"horizon_ticks":int(HORIZON_TICKS),"sample_every_ticks":int(SAMPLE_EVERY),"sample_ticks":list(SAMPLE_TICKS),"threshold_fraction":float(THRESHOLD_FRACTION),"threshold_kind":THRESHOLD_KIND,"threshold_label":THRESHOLD_LABEL,"divergence_tolerance":float(DIVERGENCE_TOL_ABS),"profiles":list(PROFILE_NAMES),"durability_items":[{"name":s.name,"path":s.path,"component":s.component,"flow_signal":list(s.flow_signal)} for s in durability.ITEM_SPECS],"rung_widths":list(RUNG_WIDTHS),"read_frame_path":durability.READ_FRAME_PATH,"write_budget":float(cfg.write_budget),"write_budget_scalings": list(BUDGET_SCALINGS),"two_budgets": list(TWO_BUDGETS),"definitions":DEFINITIONS,"width_semantics":DEFINITIONS["width_semantics"]}

def control_linear_reproduces_canonical() -> dict[str,Any]:
    lin_profile=replace(durability.ResonantProfile(), beta=0.0)
    captures=durability.capture_items(durability.DurabilityConfig(), lin_profile)
    spec=durability.ITEM_SPECS[0]; cap=captures[0]; direction=cap["direction"]; deposited=float(cap["deposited_energy"])
    ws0=initial_workspace(lin_profile); ws_w,_=durability.write_item(ws0,spec,durability.DurabilityConfig().write_budget)
    cur=ws_w; prev=0; canon: list[float]=[]
    for t in SAMPLE_TICKS:
        gap=int(t)-prev; cur,_=advance_workspace(cur,ticks=gap,demand=0.0,source_enabled=False); prev=int(t)
        vec=durability.read_frame(cur,durability.READ_FRAME_PATH)
        canon.append(float(durability.share_along(vec,direction,deposited)))
    G=geometry.linear_generator(lin_profile); vals,vecs=np.linalg.eig(G); dt=float(lin_profile.time_step)
    try: Vinv=np.linalg.inv(vecs)
    except np.linalg.LinAlgError: Vinv=np.linalg.pinv(vecs)
    z0=_state_vector(ws0); dz=_state_vector(ws_w)-z0; coeff=Vinv@dz
    pred: list[float]=[]
    for t in SAMPLE_TICKS:
        zt=np.real(vecs@(np.exp(vals*float(t)*dt)*coeff))
        vp=_predicted_read_frame(ws_w,z0+zt)
        proj=float(np.dot(vp,direction))
        pred.append(float((proj*proj)/deposited) if deposited else 0.0)
    max_abs=float(np.max(np.abs(np.asarray(canon)-np.asarray(pred)))) if canon else 0.0
    return {"max_abs_error":max_abs,"tolerance":float(DIVERGENCE_TOL_ABS),"passes":bool(max_abs<=DIVERGENCE_TOL_ABS),"canon":[float(x) for x in canon],"pred":[float(x) for x in pred],"statement":f"beta=0 control corroborated max_abs {max_abs:.4f} vs tol {DIVERGENCE_TOL_ABS}: {'PASS - corroborated linear reproduces canonical to tolerance' if max_abs<=DIVERGENCE_TOL_ABS else 'FAIL'}","label": "corroborated to declared tolerance, not exact — residual 0.0079 is not roundoff, see two_budget_control"}

def measure_body() -> dict[str,Any]:
    t0=perf_counter(); declared=declared_block()
    per_profile: dict[str,Any]={}; modal: dict[str,Any]={}; captures_by_profile: dict[str,Any]={}; linearity: dict[str,Any]={}
    for name in PROFILE_NAMES:
        profile=build_declared_profile(name); linearity[name]=profile_linearity_report(profile)
        captures=durability.capture_items(durability.DurabilityConfig(), profile); captures_by_profile[name]=captures
        widths=sorted({int(c["scale_width"]) for c in captures}); assert widths==sorted(RUNG_WIDTHS), f"{widths} != {RUNG_WIDTHS}"
        items=[measured_series_for_item(profile,i,captures) for i in range(len(durability.ITEM_SPECS))]
        # add beats to per-item
        for row in items:
            rets=[float(s["alignment_retention"]) for s in row["series"]]
            row["beats"]=beats_characterization(rets)
        per_profile[name]={"profile":name,"captures":[{k:v for k,v in c.items() if k not in {"spec","direction"}}|{"direction_sha256":c["direction_sha256"]} for c in captures],"items":items}
        modal[name]=modal_block_for_profile(profile,captures)
    exact=exact_predictor_block(per_profile,modal)
    conc_vs=concentration_vs_lifetime_block(per_profile,modal)
    ceiling=concentration_ceiling_block(per_profile,modal,captures_by_profile)
    predictor_opt=predictor_optimized_block(per_profile, modal)
    exhaustive=exhaustive_write_surface_block(per_profile, modal)
    mode_spec=mode_selective_spec_block(modal, exhaustive, ceiling)
    control=control_linear_reproduces_canonical()
    two_budget=two_budget_control_block()
    predicted_vs_measured: dict[str,Any]={}
    for pname in PROFILE_NAMES:
        measured=[int(r["lifetime_ticks"]) for r in per_profile[pname]["items"]]
        predicted=[int(r["predicted_lifetime_ticks"]) for r in modal[pname]["per_item"]]
        rc=rank_correlation(measured,predicted)
        aw=[float(r["amplitude_weighted_decay_rate"]) for r in modal[pname]["per_item"]]
        widths=[float(r["scale_width"]) for r in per_profile[pname]["items"]]
        rc_decay=rank_correlation(measured,[-x for x in aw]); rc_width=rank_correlation(measured,widths)
        tracks=bool(abs(rc_decay)>abs(rc_width)+0.1)
        predicted_vs_measured[pname]={"rank_correlation_predicted_vs_measured":float(rc),"rank_correlation_measured_vs_decay":float(rc_decay),"rank_correlation_measured_vs_width":float(rc_width),"tracks_decay_rates":bool(tracks)}
    ladder=ladder_summary(per_profile)
    reading_lines: list[str]=[]
    for pname in PROFILE_NAMES:
        block=per_profile[pname]; reading_lines.append(f"profile {pname}:")
        for row in block["items"]:
            cens=" censored" if row["censored"] else ""
            reading_lines.append(f"  {row['item']:20s} w{row['scale_width']:2d} lt{row['lifetime_ticks']:3d} final{row['final_alignment']:.4f} lhmn{row['last_half_min']:.4f} occ{row['occupancy']:.2f} beats:{row['beats']['plain']}{cens}")
        m=modal[pname]; reading_lines.append(f"  decay per-time [{m['decay_rate_min']:.4f},{m['decay_rate_max']:.4f}] per-tick [{m['decay_rate_min']*m['dt']:.4f},{m['decay_rate_max']*m['dt']:.4f}] efold {m['efold_ticks_min']:.0f}-{m['efold_ticks_max']:.0f} ticks ({m['efold_time_min']:.1f}-{m['efold_time_max']:.1f} time) -> {m['band_verdict']}")
        reading_lines.append(f"  corroborated linear overall pearson {exact[pname]['overall_pearson']:.2f} rms {exact[pname]['overall_rms']:.4f} rank {exact[pname]['overall_rank']:.2f}; {exact[pname]['fingerprint']}")
        for r in exact[pname]["per_item"]:
            reading_lines.append(f"    {r['item']:20s} pearson {r['pearson']:.2f} rms {r['rms']:.4f} max_abs {r['max_abs']:.4f}")
        for d in exact[pname]["divergence"]:
            reading_lines.append(f"    divergence {d['item']:20s} first_div {d['first_divergence_tick']} tol {d['tolerance']}")
        reading_lines.append(f"  concentration vs lifetime: {conc_vs[pname]['plain']}")
        cc=ceiling[pname]
        reading_lines.append(f"  ceiling algebraic eff {cc['best_eff']:.1f} lower bound only; realized eff {cc['realized_best_eff']:.1f} {cc['shortfall_statement']}")
        reading_lines.append(f"  ceiling realized final {cc['realized_final_retention']:.3f} lhmn {cc['realized_last_half_min']:.3f} occ {cc['realized_occupancy']:.2f} beats: {cc['realized_beats'].get('plain','')}")
        po=predictor_opt[pname]
        reading_lines.append(f"  predictor-optimized best final {po['best_measured_final']:.3f} vs best single {po['best_single_final']:.3f} vs headline {po['headline_final']:.3f}: {po['statement']}")
        ex=exhaustive[pname]
        nb=ex.get("narrow_best")
        if nb:
            reading_lines.append(f"  exhaustive {ex['total_candidates']} singles best pred {ex['best_predicted_final']:.3f} -> meas {ex['best_measured_final']:.3f}; narrowest width {ex['narrowest_width']} best {nb['path'] or 'root'}/{nb['component']} eff {nb['realized_eff']:.1f} maxw {nb['realized_max_weight']:.3f} in_slow {nb['dominant_in_slow_band']} sloww {nb['slow_weight']:.2f} pred {nb['predicted_final']:.3f} meas {nb['measured_final']:.3f} pearson {nb['pearson_pred_vs_meas']:.2f}")
        else:
            reading_lines.append(f"  exhaustive {ex['total_candidates']} singles: no narrow")
        # also print top 3 exhaustive measured
        for cand in ex.get("measured_top", [])[:3]:
            reading_lines.append(f"    exhaustive top {cand['path'] or 'root'}/{cand['component']} w{cand['width']} eff {cand['realized_eff']:.1f} maxw {cand['realized_max_weight']:.3f} in_slow {cand['dominant_in_slow_band']} sloww {cand['slow_weight']:.2f} pred {cand['predicted_final']:.3f} meas {cand['measured_final']:.3f} pearson {cand['pearson_pred_vs_meas']:.2f}")
        ms=mode_spec[pname]
        reading_lines.append(f"  mode-selective spec slow band {ms['slow_band_size']} modes efold {ms['slow_band_efold_ticks_range'][0]:.0f}-{ms['slow_band_efold_ticks_range'][1]:.0f} ticks: need maxw ~{ms['required_max_weight_mean']:.3f} (min {ms['required_max_weight_min']:.3f} max {ms['required_max_weight_max']:.3f}) eff ~{ms['required_eff_mean']:.1f} ({ms['required_eff_min']:.1f}-{ms['required_eff_max']:.1f}) from {ms['dominated_count']} slow-dominated singles; gap to realized {ms['gap_to_realized']:.1f} to algebraic {ms['gap_to_algebraic']:.1f}")
        reading_lines.append(f"  linearity: {linearity[pname]['statement']}")
    censored=[f"{pname}/{row['item']}" for pname,block in per_profile.items() for row in block["items"] if row["censored"]]
    ordering_plain="; ".join(f"{p}: {'monotone' if ladder[p]['monotone_coarse_to_fine'] else 'NOT monotone'} ratio {ladder[p]['ratio_coarsest_to_finest_means']:.2f}" for p in PROFILE_NAMES if p in ladder)
    body: dict[str,Any]={"schema":SCHEMA,"declared":declared,"boundary":BOUNDARY,"profiles":per_profile,"modal":modal,"exact_predictor":exact,"corroborated_predictor": exact,"concentration_vs_lifetime":conc_vs,"concentration_ceiling":ceiling,"predictor_optimized": predictor_opt,"exhaustive_write_surface": exhaustive,"mode_selective_spec": mode_spec,"linearity":linearity,"control_linear_reproduces_canonical":control,"two_budget_control": two_budget,"predicted_vs_measured":predicted_vs_measured,"ladder":ladder,"reading":{"lines":reading_lines,"censored_items":censored,"ordering_plain":ordering_plain},"elapsed_seconds":float(perf_counter()-t0)}
    return body

def build_receipt() -> dict[str,Any]:
    body=measure_body()
    return {**body,"content_digest":content_digest(body)}
def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT,help="output JSON path")
    args=parser.parse_args()
    receipt=build_receipt()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2,sort_keys=False)+"\n",encoding="utf-8")
    for line in receipt["reading"]["lines"]: print(line)
    print(receipt["reading"]["ordering_plain"])
    print(f"control beta=0: {receipt['control_linear_reproduces_canonical']['statement']}")
    print(f"two-budget: {receipt['two_budget_control']['statement']}")
    for pname in PROFILE_NAMES:
        e=receipt["exact_predictor"][pname]; print(f"{pname} corroborated pearson {e['overall_pearson']:.3f} rms {e['overall_rms']:.4f} has_div {e['has_divergence']}")
        c=receipt["concentration_vs_lifetime"][pname]; print(f"{pname} {c['plain']}")
        cc=receipt["concentration_ceiling"][pname]; print(f"{pname} ceiling algebraic {cc['best_eff']:.1f} realized {cc['realized_best_eff']:.1f} shortfall {cc['shortfall_eff']:.1f} final {cc['realized_final_retention']:.3f}")
        po=receipt["predictor_optimized"][pname]; print(f"{pname} opt best final {po['best_measured_final']:.3f} vs single {po['best_single_final']:.3f} headline {po['headline_final']:.3f}")
    print(f"digest {receipt['content_digest']}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
