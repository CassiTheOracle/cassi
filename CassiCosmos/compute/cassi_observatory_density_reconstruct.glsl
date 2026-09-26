#[compute]
// Converts fixed-point conservative deposits into normalized spatial density.
// bindings 0 particle u64 mass, 1 field u64 channels, 2 rgba32f density.
// PC is shared with deposit; source_mode selects particle or live-site payload.
#version 450
layout(local_size_x=8,local_size_y=8,local_size_z=8) in;
layout(push_constant,std430) uniform PC {
    vec3 bounds_min; float grid_size;
    vec3 bounds_max; float mass_scale;
    float particle_count; float site_count; float source_mode; float site_offset_x;
    float site_offset_y; float site_offset_z; float field_scale; float cell_volume;
} pc;
layout(set=0,binding=0,std430) readonly buffer ParticleAccum { uvec2 particle_acc[]; } pa;
layout(set=0,binding=1,std430) readonly buffer FieldAccum { uvec2 field_acc[]; } fa;
layout(set=0,binding=2,rgba32f) uniform writeonly image3D density_image;
float unpack_u64(uvec2 x) { return float(x.y)*4294967296.0+float(x.x); }
void main() {
    uint n=max(1u,uint(pc.grid_size+0.5)); uvec3 q=gl_GlobalInvocationID;
    if(any(greaterThanEqual(q,uvec3(n)))) return;
    uint idx=q.x*n*n+q.y*n+q.z; float cell=max(pc.cell_volume,1e-9);
    if(pc.source_mode<0.5) {
        float mass=unpack_u64(pa.particle_acc[idx])/max(pc.mass_scale,1.0);
        float rho=max(mass/cell,0.0);
        imageStore(density_image,ivec3(q),vec4(rho,0.0,0.0,0.0));
    } else {
        float op=unpack_u64(fa.field_acc[8u*idx+0u])/max(pc.field_scale,1.0);
        float ey=(unpack_u64(fa.field_acc[8u*idx+2u])-unpack_u64(fa.field_acc[8u*idx+3u]))/max(pc.field_scale,1.0);
        float ei=(unpack_u64(fa.field_acc[8u*idx+4u])-unpack_u64(fa.field_acc[8u*idx+5u]))/max(pc.field_scale,1.0);
        float coh=unpack_u64(fa.field_acc[8u*idx+6u])/max(pc.field_scale,1.0);
        float inv=max(op,1e-8);
        // G/B preserve the live site payload's EY/EI signs; A is bounded coherence.
        imageStore(density_image,ivec3(q),vec4(max(op/cell,0.0),ey/inv,ei/inv,clamp(coh/inv,0.0,1.0)));
    }
}
