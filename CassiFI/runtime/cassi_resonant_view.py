from __future__ import annotations

"""Read-only local CassiFI resonant-state inspector.

This module deliberately contains no field clock, animation loop, or state
mutation. The worker supplies a bounded canonical snapshot and the page
renders exactly that snapshot, including unavailable values instead of
inventing telemetry.
"""

import time
from typing import Any, Mapping
from cassi_resonant_field import ResonantProfile, measure_body_response

VIEW_SCHEMA = "cassifi.cassipi-resonant-view.v1"
SNAPSHOT_SCHEMA = "cassifi.cassipi-resonant-snapshot.v1"
POOL_NAMES = tuple(f"pool-{index}" for index in range(1, 8))
_calibration_profile: ResonantProfile | None = None
_calibration: Mapping[str, Any] | None = None


def _body_calibration(profile: ResonantProfile) -> Mapping[str, Any]:
    """Cache only a reproducible fixed-profile diagnostic, never learned state."""
    global _calibration_profile, _calibration
    if _calibration_profile is not profile or _calibration is None:
        _calibration = measure_body_response(profile)
        _calibration_profile = profile
    return _calibration




def _indexed_value(values: Any, name: str) -> Any:
    if not isinstance(values, (list, tuple)) or len(values) != len(POOL_NAMES):
        return None
    try:
        return values[POOL_NAMES.index(name)]
    except ValueError:
        return None


def _pool_rows(resonance: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = resonance.get("pool_sample")
    by_name = {
        str(row.get("name")): row
        for row in raw
        if isinstance(row, Mapping) and row.get("name") in POOL_NAMES
    } if isinstance(raw, (list, tuple)) else {}
    rates = resonance.get("local_phase_rates")
    phases = resonance.get("local_phase")
    rows: list[Mapping[str, Any]] = []
    for name in POOL_NAMES:
        source = by_name.get(name)
        if source is None:
            rows.append({"name": name, "available": False})
            continue
        rows.append(
            {
                "name": name,
                "available": True,
                "amplitude": source.get("amplitude"),
                "power": source.get("power"),
                "local_phase_rate": (
                    source["local_phase_rate"]
                    if "local_phase_rate" in source
                    else _indexed_value(rates, name)
                ),
                "local_phase": (
                    source["local_phase"]
                    if "local_phase" in source
                    else _indexed_value(phases, name)
                ),
                "phase_defined": source.get("phase_defined"),
                "sampling": source.get("sampling", {}),
            }
        )
    return rows


def _measurement_metadata(resonance: Mapping[str, Any]) -> Mapping[str, Any]:
    assumptions = [
        "local_phase_rate is an instantaneous signed quadrature rate, not an eigenfrequency",
        "body_response is a separate frozen-rest calibration; it does not estimate live task eigenmodes",
        "phase is unavailable when the canonical amplitude threshold is not met",
    ]
    return {
        "rate_label": "instantaneous local quadrature phase rate",
        "rate_units": "radians per field-time unit",
        "is_eigenfrequency": False,
        "assumptions": assumptions,
        "sampling_limits": {
            "spectral_estimate": False,
            "source": "single canonical owner snapshot",
            **dict(resonance.get("sampling_limits", {})),
            "temporal_phase_locking_measured": False,
            "viewer_poll_interval_seconds": 2.0,
            "temporal_aliasing": "snapshots do not resolve every field step; no interpolated trajectory or temporal spectrum",
        },
    }


def _bounded_rows(rows: Any, limit: int) -> tuple[list[Any], int]:
    """Select evenly spaced viewer rows without changing owner field data."""
    if not isinstance(rows, (list, tuple)):
        return [], 0
    count = len(rows)
    if count <= limit:
        return list(rows), count
    indices = [round(index * (count - 1) / (limit - 1)) for index in range(limit)]
    return [rows[index] for index in indices], count


def _bounded_strands(strands: Any, limit: int = 256) -> tuple[dict[str, Any], dict[str, Any]]:
    result: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    if not isinstance(strands, Mapping):
        return result, coverage
    for name in ("yang", "yin"):
        strand = strands.get(name)
        rows = strand.get("samples") if isinstance(strand, Mapping) else None
        samples, total = _bounded_rows(rows, limit)
        result[name] = {"samples": samples}
        coverage[name] = {
            "source_samples": total,
            "viewer_samples": len(samples),
            "coverage": len(samples) / total if total else 0.0,
            "decimated": len(samples) < total,
        }
    return result, coverage


def snapshot(adapter: Any) -> Mapping[str, Any]:
    """Build a bounded, credential-free read-only snapshot from owner state."""
    resonance = adapter.inspect_resonance()
    if not isinstance(resonance, Mapping):
        raise RuntimeError("owner resonance inspection did not return an object")
    status = adapter.owner_status()
    calibration = _body_calibration(adapter.owner.state.resonant_workspace.profile)
    diagnostics = {
        key: resonance.get(key)
        for key in (
            "energy",
            "semantic_residual",
            "semantic_residual_norm",
            "activity",
            "mobility",
            "rail_power_yang",
            "rail_power_yin",
            "common_rail_power",
            "counterflow_rail_power",
            "cycle_power",
            "cycle_power_absolute",
        )
        if key in resonance
    }
    residual, residual_count = _bounded_rows(resonance.get("semantic_residual"), 256)
    if "semantic_residual" in diagnostics:
        diagnostics["semantic_residual"] = residual
    pool_sample = resonance.get("pool_sample")
    strands, strand_coverage = _bounded_strands(resonance.get("strands"))
    raw_edges = resonance.get("edge_powers", [])
    edge_powers, edge_count = _bounded_rows(raw_edges, 256)
    source_version = resonance.get(
        "workspace_state_sha256",
        resonance.get("state_sha256", status.get("field_state_sha256")),
    )
    captured_at = time.time()
    sampling = {
        "snapshot_age_seconds": 0.0,
        "source_version": source_version,
        "source_timestamp_unix": captured_at,
        "field_time_step": resonance.get("field_time_step"),
        "pool_sample_count": len(pool_sample) if isinstance(pool_sample, (list, tuple)) else 0,
        "ports_per_strand": resonance.get("port_count"),
        "ports_per_pool": resonance.get("ports_per_pool"),
        "strands": strand_coverage,
        "edges": {
            "source_samples": edge_count,
            "viewer_samples": len(edge_powers),
            "coverage": len(edge_powers) / edge_count if edge_count else 0.0,
            "decimated": len(edge_powers) < edge_count,
        },
        "vectors": {
            "semantic_residual": {
                "source_samples": residual_count,
                "viewer_samples": len(residual),
                "coverage": len(residual) / residual_count if residual_count else 0.0,
                "decimated": len(residual) < residual_count,
            },
        },
    }
    return {
        "schema": SNAPSHOT_SCHEMA,
        "runtime_id": status.get("runtime_id"),
        "body_response": calibration,
        "state_sha256": resonance.get("state_sha256", status.get("field_state_sha256")),
        "workspace_state_sha256": resonance.get("workspace_state_sha256"),
        "field_generation": resonance.get("field_generation"),
        "tick": resonance.get("field_ticks"),
        "evidence_tick": resonance.get("evidence_tick"),
        "heartbeat_phase": resonance.get("heartbeat_phase"),
        "breath_phase": resonance.get("breath_phase"),
        "supported_cognition": resonance.get("supported_cognition"),
        "direction": resonance.get("direction"),
        "strands": strands,
        "pools": _pool_rows(resonance),
        "edge_powers": edge_powers,
        "diagnostics": diagnostics,
        "measurement": _measurement_metadata(resonance),
        "sampling": sampling,
        "ledger": resonance.get("ledger", {}),
    }






def html() -> bytes:
    """Return the static inspector document; it performs no mutation on load."""
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CassiFI resonant field inspector</title>
<style>
:root { color-scheme: dark; font: 14px system-ui,sans-serif; } body { margin:0; background:#10141c; color:#e8edf5; }
main { max-width:1200px; margin:auto; padding:1rem; } #meta,.ledger,.pool { border:1px solid #2c394d; border-radius:.5rem; padding:.7rem; background:#151d29; }
#meta { display:grid; grid-template-columns:repeat(auto-fit,minmax(12rem,1fr)); gap:.4rem; } label { color:#9eacc2; font-size:.78rem; display:block; }
output { overflow-wrap:anywhere; } .toolbar { display:flex; flex-wrap:wrap; gap:.8rem; align-items:end; margin:1rem 0; }
select { background:#151d29; color:inherit; border:1px solid #40516d; padding:.35rem; } #helix { width:100%; height:360px; border:1px solid #2c394d; border-radius:.5rem; background:#0c1119; }
#pools { display:grid; grid-template-columns:repeat(auto-fit,minmax(15rem,1fr)); gap:.6rem; margin-top:.8rem; } .pool h2 { margin:.1rem 0 .5rem; font-size:1rem; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:.25rem .7rem; } .muted { color:#8392a9; } table { width:100%; table-layout:fixed; border-collapse:collapse; margin-top:.8rem; } th { width:24%; } td { overflow-wrap:anywhere; }
td,th { text-align:left; border-bottom:1px solid #2c394d; padding:.3rem; }
</style></head><body><main><h1>CassiFI resonant field inspector</h1>
<section id="meta" aria-label="field metadata"></section><svg id="helix" viewBox="0 0 1000 360" role="img" aria-label="canonical sampled resonant strands"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 z" fill="#e8edf5"/></marker></defs></svg><div id="strand-status" class="muted"></div>
<div class="toolbar">
<label>Pool <select id="pool-filter"><option value="all">all</option></select></label>
<label>Strand <select id="strand-filter"><option value="all">all</option><option value="yang">yang</option><option value="yin">yin</option></select></label>
<label>Response frequency <select id="frequency-filter"><option value="all">all</option><option value="low">0.15–0.6</option><option value="middle">0.6–0.9</option><option value="high">0.9–1.25</option><option value="undefined">unavailable</option></select></label>
<label>Instantaneous rate <select id="rate-filter"><option value="all">all</option><option value="negative">negative</option><option value="near-zero">near zero</option><option value="positive">positive</option><option value="undefined">undefined</option></select></label>
<label>Current sign <select id="current-filter"><option value="all">all</option><option value="positive">positive</option><option value="negative">negative</option><option value="zero">zero</option></select></label>
<label><input id="phase-overlay" type="checkbox" checked>Spatial phase coherence overlay</label>
<span id="status" class="muted">loading canonical snapshot…</span></div>
<output id="phase-coherence" class="muted" aria-live="polite"></output>
<section id="pools" aria-live="polite"></section><section class="ledger"><h2>Numeric ledger, assumptions, and sampling limits</h2><table><tbody id="ledger"></tbody></table></section></main>
<script>
const esc = value => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const val = value => value === null || value === undefined ? "—" : (typeof value === "object" ? JSON.stringify(value) : value);
const FREQ_MIN=0.15, FREQ_MAX=1.25, RATE_EPS=0.1;
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
const rateBand=rate=>rate===null||rate===undefined?"undefined":(rate< -RATE_EPS?"negative":rate>RATE_EPS?"positive":"near-zero");
const frequencyBand=frequency=>frequency===null||frequency===undefined?"undefined":(frequency<0.6?"low":frequency<0.9?"middle":"high");
const frequencyColor=frequency=>{if(frequency===null||frequency===undefined)return "#8392a9";const t=(clamp(Number(frequency),FREQ_MIN,FREQ_MAX)-FREQ_MIN)/(FREQ_MAX-FREQ_MIN);return `hsl(${240-240*t} 85% 65%)`;};
function sampleRows(s) {
  const strands=s.strands||{}, peaks=(s.body_response||{}).peaks||[], out=[];
  for(const strand of ["yang","yin"]) for(const row of ((strands[strand]||{}).samples||[])) if(row&&Array.isArray(row.coordinate)&&row.coordinate.length>=3) out.push({...row,strand,response_frequency:(peaks.find(peak=>peak.pool===row.pool)||{}).frequency??null});
  return out;
}
function pointFor(row,bounds) {
  const x=Number(row.coordinate[0]), y=Number(row.coordinate[1])+0.25*Number(row.coordinate[2]);
  if(!Number.isFinite(x)||!Number.isFinite(y))return null;
  return [20+(x-bounds.x0)*920/Math.max(1e-12,bounds.x1-bounds.x0),340-(y-bounds.y0)*300/Math.max(1e-12,bounds.y1-bounds.y0)];
}
function filtered(row, pool, strand, rate) {
  const poolIndex=pool==="all"?null:Number(pool.slice(5))-1;
  return (poolIndex===null||row.pool===poolIndex)&&(strand==="all"||row.strand===strand)&&(rate==="all"||rateBand(row.phase_rate)===rate);
}
function draw(s) {
  const svg=document.getElementById("helix"), status=document.getElementById("strand-status"), pool=document.getElementById("pool-filter").value, strand=document.getElementById("strand-filter").value, rate=document.getElementById("rate-filter").value, current=document.getElementById("current-filter").value;
  svg.querySelectorAll(".sample,.edge").forEach(node=>node.remove());
  const overlay=document.getElementById("phase-coherence");
  overlay.hidden=!document.getElementById("phase-overlay").checked;
  const frequency=document.getElementById("frequency-filter").value;
  const all=sampleRows(s), selected=all.filter(row=>filtered(row,pool,strand,rate)&&(frequency==="all"||frequencyBand(row.response_frequency)===frequency));
  const yinPhases=new Map(selected.filter(row=>row.strand==="yin"&&Number.isFinite(row.phase)).map(row=>[row.port,row.phase]));
  let phaseCount=0, phaseCos=0, phaseSin=0;
  for(const row of selected){if(row.strand!=="yang"||!Number.isFinite(row.phase)||!yinPhases.has(row.port))continue;const delta=row.phase-yinPhases.get(row.port);phaseCos+=Math.cos(delta);phaseSin+=Math.sin(delta);phaseCount++;}
  overlay.textContent=phaseCount?`Spatial pair-phase coherence R=${(Math.hypot(phaseCos,phaseSin)/phaseCount).toFixed(6)}, ${phaseCount} defined paired ports. R=|mean exp(i(theta_Y-theta_I))| in this snapshot; temporal phase locking is not inferred.`:"Spatial pair-phase coherence unavailable: select both strands with defined paired phases.";
  if(!selected.length){status.textContent="No canonical samples match the selected filters; no trajectory is synthesized.";return;}
  const bounds={x0:Math.min(...all.map(r=>Number(r.coordinate[0]))),x1:Math.max(...all.map(r=>Number(r.coordinate[0]))),y0:Math.min(...all.map(r=>Number(r.coordinate[1])+0.25*Number(r.coordinate[2]))),y1:Math.max(...all.map(r=>Number(r.coordinate[1])+0.25*Number(r.coordinate[2])))};
  const points=new Map();
  for(const row of selected){const point=pointFor(row,bounds);if(!point)continue;points.set(`${row.strand}:${row.port}`,point);const amp=Number(row.amplitude);const opacity=Number.isFinite(amp)?clamp(amp,0.15,1):0.5;svg.insertAdjacentHTML("beforeend",`<circle class="sample" cx="${point[0]}" cy="${point[1]}" r="4" fill="${frequencyColor(row.response_frequency)}" fill-opacity="${opacity}" aria-label="${esc(row.strand+" port "+row.port)}"/>`);}
  const globalCount=Number(s.sampling?.ports_per_strand);
  for(const edge of (s.edge_powers||[])){const power=Number(edge.power);if(!Number.isFinite(power))continue;const sign=power>0?"positive":power<0?"negative":"zero";if(current!=="all"&&sign!==current)continue;const source=Number(edge.source), destination=Number(edge.destination);const sourceKey=source<globalCount?`yang:${source}`:`yin:${source-globalCount}`, destinationKey=destination<globalCount?`yang:${destination}`:`yin:${destination-globalCount}`;const a=points.get(power<0?destinationKey:sourceKey),b=points.get(power<0?sourceKey:destinationKey);if(!a||!b)continue;const opacity=clamp(Math.abs(power),0.2,1);svg.insertAdjacentHTML("beforeend",`<line class="edge" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${power<0?"#ff9d72":"#70b7ff"}" stroke-opacity="${opacity}" ${power===0?"":'marker-end="url(#arrow)"'} aria-label="edge ${source} to ${destination}, signed power ${power}"/>`);}
  status.textContent=`${selected.length} canonical samples; projection (longitudinal, x+0.25y); hue: measured frozen-body transfer peak, fixed ${FREQ_MIN}..${FREQ_MAX} rad/time (blue..red); sample opacity clamps amplitude to 0.15..1; arrows show signed generalized power, not particle flow`;
}
function render(s) {
  const meta=["runtime_id","state_sha256","workspace_state_sha256","field_generation","tick","evidence_tick","heartbeat_phase","breath_phase"];
  document.getElementById("meta").innerHTML=meta.map(k=>`<div><label>${esc(k)}</label><output>${esc(val(s[k]))}</output></div>`).join("");
  const poolSel=document.getElementById("pool-filter"), previousPool=poolSel.value, pools=s.pools||[]; poolSel.innerHTML='<option value="all">all</option>'+pools.map(p=>`<option value="${esc(p.name)}">${esc(p.name)}</option>`).join(""); if([...poolSel.options].some(option=>option.value===previousPool))poolSel.value=previousPool;
  ["pool-filter","strand-filter","frequency-filter","rate-filter","current-filter","phase-overlay"].forEach(id=>document.getElementById(id).onchange=()=>{draw(s);renderPools(s);});
  renderPools(s); draw(s); const m=s.measurement||{}, sampling=s.sampling||{};
  const rows=Object.entries({...s.diagnostics||{},...s.ledger||{},rate_label:m.rate_label,rate_units:m.rate_units,is_eigenfrequency:m.is_eigenfrequency,measurement_assumptions:m.assumptions,sampling_limits:m.sampling_limits,body_response_calibration:s.body_response,source_version:sampling.source_version,source_timestamp_unix:sampling.source_timestamp_unix,snapshot_age_seconds:sampling.snapshot_age_seconds,viewer_coverage:{strands:sampling.strands,edges:sampling.edges,vectors:sampling.vectors},field_time_step:sampling.field_time_step});
  document.getElementById("ledger").innerHTML=rows.map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(val(v))}</td></tr>`).join("");
  document.getElementById("status").textContent=`canonical snapshot ${s.state_sha256}; age ${(Number(sampling.snapshot_age_seconds)||0).toFixed(2)}s; viewer coverage ${Object.entries(sampling.strands||{}).map(([k,v])=>`${k} ${v.viewer_samples}/${v.source_samples}`).join(", ")}`;
}
function renderPools(s) {
  const chosen=document.getElementById("pool-filter").value, m=s.measurement||{}, peaks=(s.body_response||{}).peaks||[], pools=(s.pools||[]).map((p,index)=>({...p,response_peak:(peaks.find(peak=>peak.pool===index)||{}).frequency??null}));
  document.getElementById("pools").innerHTML=pools.filter(p=>chosen==="all"||p.name===chosen).map(p=>`<article class="pool"><h2>${esc(p.name)}</h2>${p.available?`<div class="grid">${["response_peak","amplitude","power","local_phase_rate","local_phase","phase_defined"].map(k=>`<div><label>${esc(k==="local_phase_rate"?m.rate_label||k:k)}</label><output>${esc(val(p[k]))}</output></div>`).join("")}</div><pre>${esc(JSON.stringify(p.sampling||{},null,2))}</pre>`:'<span class="muted">unavailable in canonical owner snapshot</span>'}</article>`).join("");
}
let pollCount=0, polling=false, pollTimer=null;
async function refresh(){if(polling||pollCount>=60)return;pollCount++;polling=true;try{const response=await fetch("/v1/view/snapshot",{credentials:"same-origin",cache:"no-store"});if(!response.ok)throw Error(`snapshot HTTP ${response.status}`);render(await response.json());}catch(error){document.getElementById("status").textContent=error.message;}finally{polling=false;if(pollCount>=60){if(pollTimer!==null)clearInterval(pollTimer);document.getElementById("status").textContent+="; bounded polling complete";}}}
refresh();pollTimer=setInterval(refresh,2000);
</script></body></html>"""
    return document.encode("utf-8")


def content_type(path: str) -> str:
    return "text/html; charset=utf-8" if path == "/view" else "application/json; charset=utf-8"
