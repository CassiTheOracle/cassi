#[compute]
// Motion ABI: one texel per particle, indexed by INSTANCE_ID as
// x=(id % width), y=(id / width). xyz is live world velocity and w is the
// original particle mass (not a speed/placeholder), preserving compact and
// noncompact material paths without CPU readbacks.
#version 450
layout(local_size_x=256,local_size_y=1,local_size_z=1) in;
layout(push_constant,std430) uniform PC { float particle_count; float texture_width; float texture_height; float _pad; } pc;
layout(set=0,binding=0,std430) readonly buffer Velocities { vec4 velocities[]; } vel;
layout(set=0,binding=1,std430) readonly buffer Positions { vec4 positions[]; } pos;
layout(set=0,binding=2,rgba32f) uniform writeonly image2D motion_image;
void main(){uint id=gl_GlobalInvocationID.x;if(id>=uint(max(pc.particle_count,0.0)))return;uint w=max(1u,uint(pc.texture_width+0.5));ivec2 p=ivec2(int(id%w),int(id/w));vec4 v=vel.velocities[id],q=pos.positions[id];if(any(isnan(v))||any(isinf(v))||any(isnan(q))||any(isinf(q))||!(q.w>0.0)){imageStore(motion_image,p,vec4(0.0));return;}imageStore(motion_image,p,vec4(v.xyz,q.w));}
