#[compute]
// Open-tile site traversal over sampled-JFA adjacency.
// One invocation per ray. Outputs visited site IDs and boundary t values.
#version 450

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;
const int MAX_SEG = 64;
const float EPS_DEN = 1e-7;

layout(push_constant, std430) uniform PC {
    float n_rays_f, n_sites_f, words_f, max_seg_f;
    float extent_x, extent_y, extent_z, pad0;
    float window_x, window_y, window_z, pad1;
} pc;
layout(set=0,binding=0,std430) readonly buffer Sites { vec4 sites[]; };
layout(set=0,binding=1,std430) readonly buffer Adj { uint adj[]; };
layout(set=0,binding=2,std430) readonly buffer Rays { vec4 rays[]; }; // ro, then rd
layout(set=0,binding=3,std430) readonly buffer StartSite { int start_site[]; };
layout(set=0,binding=4,std430) writeonly buffer Sequence { int seq[]; };
layout(set=0,binding=5,std430) writeonly buffer HitT { float hit_t[]; };
layout(set=0,binding=6,std430) writeonly buffer Count { int counts[]; };

vec3 site_world(int i) {
    return sites[i].xyz - vec3(pc.extent_x,pc.extent_y,pc.extent_z)
        + vec3(pc.window_x,pc.window_y,pc.window_z);
}
bool connected(int a,int b,int words){
    return (adj[a*words+(b>>5)] & (1u<<uint(b&31)))!=0u;
}
void main(){
    int q=int(gl_GlobalInvocationID.x), nr=int(pc.n_rays_f), ns=int(pc.n_sites_f);
    int words=int(pc.words_f), cap=min(int(pc.max_seg_f),MAX_SEG);
    if(q>=nr)return;
    vec3 ro=rays[q*2].xyz, rd=normalize(rays[q*2+1].xyz);
    int cur=start_site[q]; float tc=0.0; int nout=0;
    for(int step=0;step<cap;++step){
        if(cur<0||cur>=ns)break;
        seq[q*MAX_SEG+nout]=cur; hit_t[q*MAX_SEG+nout]=tc; nout++;
        vec3 si=site_world(cur), p=ro+rd*tc;
        float eps=max(1e-5,2e-6*max(1.0,abs(tc)));
        float best=3.402823466e38; int nxt=-1;
        for(int j=0;j<ns;++j){
            if(j==cur||!connected(cur,j,words))continue;
            vec3 r=site_world(j)-si; float den=dot(r,rd);
            if(den<=EPS_DEN)continue;
            float f0=dot(r,r)-2.0*dot(r,p-si);
            float dt=f0/(2.0*den); float th=tc+dt;
            if(!(th>tc+eps))continue;
            if(th<best-eps||(abs(th-best)<=eps&&(nxt<0||j<nxt))){best=th;nxt=j;}
        }
        if(nxt<0)break;
        tc=best; cur=nxt;
    }
    counts[q]=nout;
}
