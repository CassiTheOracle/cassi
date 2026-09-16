#[compute]
// Observatory source deposition ABI. Each source contributes to at most eight
// clamped cells. Fixed-point u64 emulation (low word + carry high word) avoids
// float image atomics, wraparound and mass loss at boundaries.
// bindings 0 positions vec4(xyz,mass), 1 optical sites vec4[2*site],
// 2 particle u64 accum, 3 field u64 accum (opacity,EY,EI,coherence).
// PC: bounds_min.xyz/grid, bounds_max.xyz/mass_scale,
// particle_count/site_count/source_mode/site_offset.x,
// site_offset.y/site_offset.z/field_scale/cell_volume.
#version 450
layout(local_size_x=256,local_size_y=1,local_size_z=1) in;
layout(push_constant,std430) uniform PC {
    vec3 bounds_min; float grid_size;
    vec3 bounds_max; float mass_scale;
    float particle_count; float site_count; float source_mode; float site_offset_x;
    float site_offset_y; float site_offset_z; float field_scale; float cell_volume;
} pc;
layout(set=0,binding=0,std430) readonly buffer Positions { vec4 positions[]; } pos;
layout(set=0,binding=1,std430) readonly buffer OpticalSites { vec4 sites[]; } site;
layout(set=0,binding=2,std430) buffer ParticleAccum { uvec2 particle_acc[]; } pa;
layout(set=0,binding=3,std430) buffer FieldAccum { uvec2 field_acc[]; } fa;

bool good(float x) { return !(isnan(x)||isinf(x)); }
void add_particle(uint index, uint amount) {
    uint old=atomicAdd(pa.particle_acc[index].x,amount);
    if (old > 0xffffffffu-amount) atomicAdd(pa.particle_acc[index].y,1u);
}
void add_field(uint index, uint amount) {
    uint old=atomicAdd(fa.field_acc[index].x,amount);
    if (old > 0xffffffffu-amount) atomicAdd(fa.field_acc[index].y,1u);
}
uint cell_index(ivec3 c,uint n) { return uint(c.x)*n*n+uint(c.y)*n+uint(c.z); }
void grid_coords(vec3 p,uint n,out ivec3 i0,out vec3 f) {
    vec3 span=max(pc.bounds_max-pc.bounds_min,vec3(1e-6));
    vec3 q=clamp((p-pc.bounds_min)/span*float(n)-vec3(0.5),vec3(0.0),vec3(float(n)-1.0001));
    i0=ivec3(floor(q)); f=clamp(q-vec3(i0),vec3(0.0),vec3(1.0));
}
void particle_deposit(uint id,uint n) {
    if(id>=uint(max(pc.particle_count,0.0))) return;
    vec4 p=pos.positions[id];
    if(any(isnan(p))||any(isinf(p))||!(p.w>0.0)||!good(p.w)) return;
    // Escaped particles remain individually rendered, never piled on a wall.
    if(any(lessThan(p.xyz,pc.bounds_min))||any(greaterThan(p.xyz,pc.bounds_max))) return;
    ivec3 i0; vec3 f; grid_coords(p.xyz,n,i0,f);
    uint amount_base=uint(clamp(round(p.w*max(pc.mass_scale,1.0)),0.0,4294967295.0));
    if(amount_base==0u) return;
    for(int dx=0;dx<2;++dx) for(int dy=0;dy<2;++dy) for(int dz=0;dz<2;++dz) {
        ivec3 c=clamp(i0+ivec3(dx,dy,dz),ivec3(0),ivec3(int(n)-1));
        float w=(dx==0?1.0-f.x:f.x)*(dy==0?1.0-f.y:f.y)*(dz==0?1.0-f.z:f.z);
        uint amount=uint(clamp(round(float(amount_base)*w),0.0,4294967295.0));
        if(amount>0u) add_particle(cell_index(c,n),amount);
    }
}
void site_deposit(uint id,uint n) {
    if(id>=uint(max(pc.site_count,0.0))) return;
    vec4 a=site.sites[2u*id], b=site.sites[2u*id+1u];
    vec3 p=a.xyz+vec3(pc.site_offset_x,pc.site_offset_y,pc.site_offset_z);
    float op=a.w;
    float source_volume=(pc.bounds_max.x-pc.bounds_min.x)*(pc.bounds_max.y-pc.bounds_min.y)*(pc.bounds_max.z-pc.bounds_min.z)/max(pc.site_count,1.0);
    if(any(isnan(a))||any(isinf(a))||any(isnan(b))||any(isinf(b))||!(op>0.0)) return;
    ivec3 i0; vec3 f; grid_coords(p,n,i0,f);
    float vals[4]=float[4](op,op*b.x,op*b.y,op*clamp(b.z,0.0,1.0));
    for(int dx=0;dx<2;++dx) for(int dy=0;dy<2;++dy) for(int dz=0;dz<2;++dz) {
        ivec3 c=clamp(i0+ivec3(dx,dy,dz),ivec3(0),ivec3(int(n)-1));
        float w=(dx==0?1.0-f.x:f.x)*(dy==0?1.0-f.y:f.y)*(dz==0?1.0-f.z:f.z);
        uint ci=cell_index(c,n);
        for(uint k=0u;k<4u;++k) {
            float q=vals[k]*w*source_volume*max(pc.field_scale,1.0);
            uint amount=uint(clamp(round(abs(q)),0.0,4294967040.0));
            if(amount>0u) add_field(8u*ci+2u*k+(q<0.0?1u:0u),amount);
        }
    }
}
void main() {
    uint id=gl_GlobalInvocationID.x, n=max(1u,uint(pc.grid_size+0.5));
    if(pc.source_mode<0.5) particle_deposit(id,n); else site_deposit(id,n);
}
