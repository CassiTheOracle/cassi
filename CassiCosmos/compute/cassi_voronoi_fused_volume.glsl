#[compute]
// Production boxless site-native volume renderer.
// Bindings are owned by the global-RD renderer wiring:
//  0 open finite-tile labels (uint site id per hash cell; invalid < 0 is encoded 0xffffffff)
//  1 symmetric adjacency bitset (ceil(site_count/32) uint words/site)
//  2 exact CSR degree (uint/site)
//  3 exact CSR offsets (uint/site + sentinel)
//  4 exact CSR neighbors (ascending site ids)
//  5 compact optical payload: vec4[2*site], first xyz+opacity, second EY/EI/coherence/gradient
//  6 immutable topology status: [generation,total,overflow,site_count]
//  7 output rgba32f image
//  8 history rgba32f image (read-only temporal hook; invalid history is transparent)
//  9 render stats uints: [overflow, miss, history_reject, topology_reject,
//                         sentinel, executed_generation, history_accepted, scheduling]
//
// Push constants are exactly eight vec4 groups: 32 floats / 128 bytes.
// Slots 0..31 are the canonical live-camera/topology/traversal contract.
#version 450
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

const uint INVALID_SITE = 0xffffffffu;
const float INF = 3.402823466e+38;
const float EPS_T = 1e-5;
const float EPS_DEN = 1e-7;
const float PHI = 1.6180339887498948482;
const float PHI_INV2 = 0.3819660112501051518;

layout(push_constant, std430) uniform PC {
    vec3 camera_origin; float fov_y;
    vec3 camera_right; float out_width;
    vec3 camera_up; float out_height;
    vec3 camera_forward; float site_count_f;
    vec3 tile_half_extents; float open_grid_n_f;
    float topology_generation; float envelope_generation;
    float coherence_mask; float gradient_mask;
    float history_weight; float max_steps;
    float transmittance_cutoff; float history_generation;
    float history_depth_reject; float scheduling_mask;
    float scheduling_threshold; float scheduling_stride;
} pc;

layout(set=0,binding=0,std430) readonly buffer OpenLabels { uint open_label[]; };
layout(set=0,binding=1,std430) readonly buffer Adjacency { uint adjacency_bits[]; };
layout(set=0,binding=2,std430) readonly buffer Degree { uint degree[]; };
layout(set=0,binding=3,std430) readonly buffer Offsets { uint offsets[]; };
layout(set=0,binding=4,std430) readonly buffer Neighbors { uint neighbors[]; };
layout(set=0,binding=5,std430) readonly buffer Optical { vec4 optical[]; };
layout(set=0,binding=6,std430) readonly buffer TopologyStatus { uint topology_status[]; };
layout(set=0,binding=7,rgba32f) uniform restrict writeonly image2D output_image;
layout(set=0,binding=8,rgba32f) uniform restrict readonly image2D history_image;
layout(set=0,binding=9,std430) coherent buffer RenderStats { uint render_stats[]; };

uint site_count() { return uint(max(0.0, pc.site_count_f)); }
uint hash_words() { return max(1u, (site_count() + 31u) >> 5u); }

// Ray / finite OPEN tile slab. Tile bounds are render-local [-E,+E].
bool slab(vec3 ro, vec3 rd, out float ta, out float tb) {
    vec3 e = max(pc.tile_half_extents, vec3(EPS_T));
    vec3 lo = -e, hi = e;
    ta = -INF; tb = INF;
    for (int a=0; a<3; ++a) {
        float o = ro[a], d = rd[a];
        if (abs(d) <= EPS_DEN) {
            if (o < lo[a] || o > hi[a]) return false;
        } else {
            float t0 = (lo[a] - o) / d;
            float t1 = (hi[a] - o) / d;
            if (t0 > t1) { float z=t0; t0=t1; t1=z; }
            ta = max(ta, t0); tb = min(tb, t1);
            if (ta > tb) return false;
        }
    }
    return tb > max(ta, 0.0) + EPS_T;
}

// Deterministic spatial hash lookup. open_label is an immutable finite tile
// raster; callers locally correct its result through the CSR walk.
uint label_lookup(vec3 p) {
    uint n = max(1u, uint(max(0.0, pc.open_grid_n_f)));
    ivec3 q = ivec3(clamp(floor((p + pc.tile_half_extents) /
                              max(pc.tile_half_extents * 2.0 / float(n), vec3(EPS_T))),
                          vec3(0.0), vec3(float(n - 1u))));
    uint idx = uint(q.x) * n * n + uint(q.y) * n + uint(q.z);
    if (idx >= uint(open_label.length())) return INVALID_SITE;
    return open_label[idx];
}


bool bit_has(uint s, uint j) {
    uint w = hash_words();
    return (adjacency_bits[s*w + (j >> 5u)] & (1u << (j & 31u))) != 0u;
}

vec3 ray_dir(ivec2 pix) {
    float w=max(pc.out_width,1.0), h=max(pc.out_height,1.0);
    vec2 uv=(vec2(pix)+vec2(0.5))/vec2(w,h)*2.0-1.0;
    float aspect=w/h, tan_half=tan(0.5*pc.fov_y);
    return normalize(pc.camera_forward + pc.camera_right*(uv.x*aspect*tan_half)
                     + pc.camera_up*(uv.y*tan_half));
}

vec3 site_pos(uint s) { return optical[2u*s].xyz; }

// Exact continuous bisector crossing against neighbor j. The candidate is
// accepted only when it advances strictly and remains inside the open slab.
float crossing(vec3 ro, vec3 rd, float tc, uint cur, uint j) {
    vec3 a=site_pos(cur), b=site_pos(j), r=b-a;
    float den=dot(r,rd);
    if (!(den > EPS_DEN)) return INF;
    vec3 p=ro+rd*tc;
    float t=tc+(dot(r,r)-2.0*dot(r,p-a))/(2.0*den);
    float eps=max(EPS_T,2e-6*max(1.0,abs(t)));
    return t > tc+eps ? t : INF;
}

vec4 integrate(vec3 ro, vec3 rd, float ta, float tb, out bool overflowed) {
    overflowed=false;
    uint ns=site_count(); if(ns==0u)return vec4(0.0);
    float tc=max(ta,0.0),trans=1.0; vec3 radiance=vec3(0.0);
    vec3 entry=ro+rd*(tc+4.0*EPS_T); uint cur=label_lookup(entry);
    if(cur==INVALID_SITE||cur>=ns)return vec4(0.0);
    bool settled=false;
    for(uint h=0u;h<16u;++h){uint best=cur;vec3 d0=site_pos(cur)-entry;float bd=dot(d0,d0);uint begin=offsets[cur],end=min(begin+degree[cur],offsets[cur+1]);for(uint k=begin;k<end;++k){uint j=neighbors[k];if(j>=ns||j==cur||!bit_has(cur,j))continue;vec3 d=site_pos(j)-entry;float dd=dot(d,d);if(dd<bd||(dd==bd&&j<best)){bd=dd;best=j;}}if(best==cur){settled=true;break;}cur=best;}
    if(!settled){overflowed=true;return vec4(0.0);}
    uint limit=max(1u,uint(max(pc.max_steps,1.0)));
    for(uint step=0u;step<limit;++step){
        if(cur>=ns||tc>=tb-EPS_T||trans<=pc.transmittance_cutoff)break;
        vec4 fs=optical[2u*cur+1u]; vec4 op=optical[2u*cur];
        uint deg=degree[cur]; uint begin=offsets[cur], end=min(begin+deg,offsets[cur+1]); float best=tb; uint next=INVALID_SITE;
        for (uint k=begin; k<end; ++k) {
            uint j=neighbors[k];
            if (j==cur || j>=ns || !bit_has(cur,j)) continue;
            float hit=crossing(ro,rd,tc,cur,j);
            if (hit < best-EPS_T || (abs(hit-best)<=EPS_T && j<next)) { best=hit; next=j; }
        }
        float ds=max(best-tc,0.0),rho=max(fs.x+fs.y,0.0),coh=clamp(fs.z,0.0,1.0);
        float sigma=max(op.w,0.0)*(0.25+0.75*coh);
        vec3 emit=vec3(max(fs.x,0.0),max(fs.y,0.0),rho)*sigma;
        float absorb=exp(-sigma*ds);
        radiance += trans*emit*(1.0-absorb)/max(sigma,1e-6);
        trans*=absorb;tc=best;
        if(next==INVALID_SITE||!(tc>0.0)||tc>=tb-EPS_T)break;
        cur=next;
    }
    // A non-terminal cap hit is explicit overflow, never silent truncation.
    if (tc < tb-EPS_T && trans > pc.transmittance_cutoff) overflowed=true;
    return vec4(radiance,1.0-trans);
}
void main() {
    ivec2 pix=ivec2(gl_GlobalInvocationID.xy);
    ivec2 dim=imageSize(output_image);
    if (pix.x>=dim.x || pix.y>=dim.y) return;
    if (pix.x==0 && pix.y==0) {
        render_stats[4]=0xC4551A5Eu;
        render_stats[5]=uint(max(pc.topology_generation,0.0)+0.5);
    }
    uint ns=site_count(), required=topology_status[1];
    uint n=uint(max(pc.open_grid_n_f,0.0)+0.5);
    uint cap=6u*n*n*max(n-1u,1u);
    bool topology_ok=ns>0u && topology_status[0]==uint(max(pc.topology_generation,0.0)+0.5)
        && topology_status[3]==ns && topology_status[2]==0u && required<=cap;
    if(!topology_ok){atomicAdd(render_stats[3],1u);imageStore(output_image,pix,vec4(0.0));return;}
    vec3 ro=pc.camera_origin,rd=ray_dir(pix);float ta,tb;
    vec4 outv=vec4(0.0);bool overflowed=false;
    if(slab(ro,rd,ta,tb))outv=integrate(ro,rd,ta,tb,overflowed);
    else atomicAdd(render_stats[1],1u);
    if(pc.history_weight>0.0&&outv.a>0.0&&pc.topology_generation==pc.envelope_generation){vec4 old=imageLoad(history_image,pix);outv=mix(outv,old,clamp(pc.history_weight,0.0,1.0));}
    else if(pc.history_weight>0.0)atomicAdd(render_stats[2],1u);
    if(overflowed)atomicAdd(render_stats[0],1u);
    imageStore(output_image,pix,outv);
}
