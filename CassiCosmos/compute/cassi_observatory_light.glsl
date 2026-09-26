#[compute]
// Ordered +X,-X,+Y,-Y,+Z,-Z single-scattering illumination cache.
// Each invocation owns one voxel in a completed layer; previous layers are
// separated by host compute barriers. No fictitious boundary light is added.
#version 450
layout(local_size_x=8,local_size_y=8,local_size_z=1) in;
layout(push_constant,std430) uniform PC {
    float direction; float layer; float grid_size; float optical_thickness;
    float cell_length; float reference_mass; float emission; float source_mode;
    float point_fraction; float field_radius; float pad0; float pad1;
} pc;
layout(set=0,binding=0,rgba32f) uniform readonly image3D density_image;
layout(set=0,binding=1,rgba32f) uniform image3D state_image;
layout(set=0,binding=2,rgba32f) uniform image3D accum_image;

void main() {
    int n=max(1,int(pc.grid_size+0.5)), direction=int(pc.direction+0.5);
    int axis=direction/2, layer=int(pc.layer+0.5);
    ivec2 uv=ivec2(gl_GlobalInvocationID.xy);
    if (any(greaterThanEqual(uv,ivec2(n))) || layer>=n) return;
    ivec3 cell=axis==0?ivec3(layer,uv):axis==1?ivec3(uv.x,layer,uv.y):ivec3(uv,layer);
    int offset=(direction%2==0)?1:-1;
    ivec3 previous=cell;
    previous[axis]+=offset;
    bool boundary=previous[axis]<0 || previous[axis]>=n;
    vec4 density=imageLoad(density_image,cell);
    float rho=max(density.r,0.0)/max(pc.reference_mass,1e-6);
    if (pc.source_mode>0.5) rho=max(density.r,0.0)/max(pc.field_radius,1e-6);
    float sigma=rho*max(pc.optical_thickness,0.0), ds=max(pc.cell_length,1e-6);
    float transmission=exp(-min(sigma*ds,80.0));
    float integral=sigma>1e-6?(1.0-transmission)/sigma:ds;
    vec3 incoming=boundary?vec3(0.0):imageLoad(state_image,previous).rgb;
    vec3 spectrum=mix(vec3(0.22,0.30,0.42),vec3(1.0,0.67,0.35),pc.point_fraction);
    vec3 emission=max(pc.emission,0.0)*rho*spectrum;
    vec3 outgoing=incoming*transmission+emission*integral;
    imageStore(state_image,cell,vec4(outgoing,1.0));
    vec3 old=imageLoad(accum_image,cell).rgb;
    // Mid-cell incident intensity; this cache contains no scattered light,
    // so the camera pass is a bounded first-scattering approximation.
    imageStore(accum_image,cell,vec4(old+(incoming+outgoing)/12.0,1.0));
}
