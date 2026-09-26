#[compute]
// Observatory density clear ABI.
// set 0: binding 0 particle fixed-point u64 emulation (uvec2/cell),
// binding 1 field fixed-point channels (4 x uvec2/cell), binding 2 density,
// binding 3 light sweep state, binding 4 light accumulation.
// Push constants: grid_size (float) in slot 0; remaining slots reserved.
#version 450
layout(local_size_x=8, local_size_y=8, local_size_z=8) in;
layout(push_constant, std430) uniform PC { float grid_size; float _pad0; float _pad1; float _pad2; } pc;
layout(set=0,binding=0,std430) buffer ParticleAccum { uvec2 particle_acc[]; } pa;
layout(set=0,binding=1,std430) buffer FieldAccum { uvec2 field_acc[]; } fa;
layout(set=0,binding=2,rgba32f) uniform writeonly image3D density_image;
layout(set=0,binding=3,rgba32f) uniform writeonly image3D light_state;
layout(set=0,binding=4,rgba32f) uniform writeonly image3D light_accum;
void main() {
    uint n=max(1u,uint(pc.grid_size+0.5));
    uvec3 q=gl_GlobalInvocationID;
    if(any(greaterThanEqual(q,uvec3(n)))) return;
    uint idx=q.x*n*n+q.y*n+q.z;
    pa.particle_acc[idx]=uvec2(0u);
    fa.field_acc[8u*idx+0u]=uvec2(0u); fa.field_acc[8u*idx+1u]=uvec2(0u);
    fa.field_acc[8u*idx+2u]=uvec2(0u); fa.field_acc[8u*idx+3u]=uvec2(0u);
    fa.field_acc[8u*idx+4u]=uvec2(0u); fa.field_acc[8u*idx+5u]=uvec2(0u);
    fa.field_acc[8u*idx+6u]=uvec2(0u); fa.field_acc[8u*idx+7u]=uvec2(0u);
    imageStore(density_image,ivec3(q),vec4(0.0));
    imageStore(light_state,ivec3(q),vec4(0.0));
    imageStore(light_accum,ivec3(q),vec4(0.0));
}
