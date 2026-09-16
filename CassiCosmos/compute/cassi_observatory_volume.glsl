#[compute]
// Camera PC: 32 floats / 128 B. Binding 5 holds radius, delta, source mode,
// shutter, source/site epochs, history reset and slice count (8 floats).
// Outputs: premultiplied HDR RGBA32F, ray-distance R32F and cumulative tau R32F.
#version 450
layout(local_size_x=8,local_size_y=8,local_size_z=1) in;
layout(push_constant,std430) uniform PC {
    vec3 camera_origin; float fov_y;
    vec3 camera_right; float out_width;
    vec3 camera_up; float out_height;
    vec3 camera_forward; float near_clip;
    vec3 bounds_min; float far_clip;
    vec3 bounds_max; float grid_size;
    float render_width; float render_height; float steps; float optical_thickness;
    float emission; float scattering; float point_fraction; float reference_mass;
} pc;
layout(set=0,binding=0,rgba32f) uniform readonly image3D density_image;
layout(set=0,binding=1,rgba32f) uniform readonly image3D light_image;
layout(set=0,binding=2,rgba32f) uniform writeonly image2D radiance_image;
layout(set=0,binding=3,r32f) uniform writeonly image2D depth_image;
layout(set=0,binding=4,r32f) uniform writeonly image3D tau_image;
layout(set=0,binding=5,std430) readonly buffer VolumeParams { float values[]; } params;

// The density texture is stored in a rectangular allocation, but the visible
// optical support must not expose that allocation as a colored cuboid. Use an
// ellipsoidal world-domain envelope (a sphere in normalized coordinates) with
// a smooth outer taper; empty rays remain transparent.
float optical_support(vec3 uv) {
    float radius = length((uv - vec3(0.5)) * 2.0);
    return 1.0 - smoothstep(0.82, 1.0, radius);
}

// Compact C2 radial reconstruction in physical world space. The 3D images
// remain rectangular storage, but anisotropic box extents now affect cell
// spacing only—not the radial distance metric or support shape.
float isotropic_weight(float distance_world, float support_radius) {
    float q = distance_world / max(support_radius, 1.0e-20);
    if (q >= 1.0) return 0.0;
    float one_minus_q = 1.0 - q;
    float square = one_minus_q * one_minus_q;
    return square * square * (1.0 + 4.0 * q);
}


vec4 sample_density(vec3 uv) {
    ivec3 dim = imageSize(density_image);
    vec3 span = max(pc.bounds_max - pc.bounds_min, vec3(1.0e-8));
    vec3 spacing = span / vec3(dim);
    // 0.75 of the cell diagonal covers every cell corner continuously while
    // remaining inside the ±2 stencil for the production φ:1:φ² aspect.
    float support_radius = 0.75 * length(spacing);
    vec3 position_grid = uv * vec3(dim) - vec3(0.5);
    vec3 position_world = pc.bounds_min + uv * span;
    ivec3 nearest = ivec3(floor(position_grid + vec3(0.5)));
    vec4 value = vec4(0.0);
    float weight_sum = 0.0;
    for (int z = -2; z <= 2; ++z)
    for (int y = -2; y <= 2; ++y)
    for (int x = -2; x <= 2; ++x) {
        ivec3 coordinate = nearest + ivec3(x, y, z);
        vec3 center_world = pc.bounds_min
            + (vec3(coordinate) + vec3(0.5)) * spacing;
        float weight = isotropic_weight(
            length(position_world - center_world), support_radius);
        bool inside = all(greaterThanEqual(coordinate, ivec3(0)))
            && all(lessThan(coordinate, dim));
        if (inside && weight > 0.0)
            value += imageLoad(density_image, coordinate) * weight;
        // Outside candidates are zero-valued ghosts. Keeping their weight in
        // the denominator avoids flat renormalized faces at the texture edge.
        weight_sum += weight;
    }
    return value / max(weight_sum, 1.0e-20) * optical_support(uv);
}

vec3 sample_light(vec3 uv) {
    ivec3 dim = imageSize(light_image);
    vec3 span = max(pc.bounds_max - pc.bounds_min, vec3(1.0e-8));
    vec3 spacing = span / vec3(dim);
    float support_radius = 0.75 * length(spacing);
    vec3 position_grid = uv * vec3(dim) - vec3(0.5);
    vec3 position_world = pc.bounds_min + uv * span;
    ivec3 nearest = ivec3(floor(position_grid + vec3(0.5)));
    vec3 value = vec3(0.0);
    float weight_sum = 0.0;
    for (int z = -2; z <= 2; ++z)
    for (int y = -2; y <= 2; ++y)
    for (int x = -2; x <= 2; ++x) {
        ivec3 coordinate = nearest + ivec3(x, y, z);
        vec3 center_world = pc.bounds_min
            + (vec3(coordinate) + vec3(0.5)) * spacing;
        float weight = isotropic_weight(
            length(position_world - center_world), support_radius);
        bool inside = all(greaterThanEqual(coordinate, ivec3(0)))
            && all(lessThan(coordinate, dim));
        if (inside && weight > 0.0)
            value += imageLoad(light_image, coordinate).rgb * weight;
        weight_sum += weight;
    }
    return value / max(weight_sum, 1.0e-20) * optical_support(uv);
}
bool intersect_box(vec3 origin,vec3 direction,out float entry,out float exit_t) {
    entry=max(pc.near_clip,0.0); exit_t=pc.far_clip;
    for (int axis=0;axis<3;++axis) {
        if (abs(direction[axis])<1e-8) {
            if (origin[axis]<pc.bounds_min[axis] || origin[axis]>pc.bounds_max[axis]) return false;
        } else {
            float a=(pc.bounds_min[axis]-origin[axis])/direction[axis];
            float b=(pc.bounds_max[axis]-origin[axis])/direction[axis];
            entry=max(entry,min(a,b)); exit_t=min(exit_t,max(a,b));
        }
    }
    return exit_t>entry;
}
float slice_distance(int slice,int count) {
    return exp(mix(log(max(pc.near_clip,1e-4)),log(max(pc.far_clip,pc.near_clip+1e-4)),(float(slice)+0.5)/float(count)));
}
void main() {
    ivec2 pixel=ivec2(gl_GlobalInvocationID.xy), dimensions=imageSize(radiance_image);
    if (any(greaterThanEqual(pixel,dimensions))) return;
    int slices=imageSize(tau_image).z;
    vec2 uv=(vec2(pixel)+0.5)/vec2(dimensions);
    vec2 ndc=vec2(uv.x*2.0-1.0,1.0-uv.y*2.0);
    vec3 ray=normalize(pc.camera_forward+tan(pc.fov_y*0.5)*(pc.camera_right*ndc.x*pc.out_width/pc.out_height+pc.camera_up*ndc.y));
    float entry,exit_t;
    if (!intersect_box(pc.camera_origin,ray,entry,exit_t)) {
        for (int z=0;z<slices;++z) imageStore(tau_image,ivec3(pixel,z),vec4(0.0));
        imageStore(radiance_image,pixel,vec4(0.0)); imageStore(depth_image,pixel,vec4(0.0)); return;
    }
    int next=0;
    while (next<slices && slice_distance(next,slices)<=entry) {
        imageStore(tau_image,ivec3(pixel,next),vec4(0.0)); ++next;
    }
    float ds=(exit_t-entry)/max(pc.steps,1.0), t=entry, tau=0.0;
    float trans=1.0, opacity=0.0, depth_sum=0.0;
    vec3 radiance=vec3(0.0);
    float radius=max(params.values[0],1e-6);
    bool field_mode=params.values[2]>0.5;
    for (int step=0;step<int(pc.steps+0.5);++step) {
        float end_t=min(t+ds,exit_t), middle=(t+end_t)*0.5;
        vec3 point=pc.camera_origin+ray*middle;
        vec3 coord=(point-pc.bounds_min)/(pc.bounds_max-pc.bounds_min);
        vec4 density=sample_density(coord);
        float rho=field_mode?max(density.r,0.0)/radius:max(density.r,0.0)*radius*radius/max(pc.reference_mass,1e-6);
        float sigma=rho*max(pc.optical_thickness,0.0);
        float segment_tau=sigma*(end_t-t), transmission=exp(-min(segment_tau,80.0));
        float absorbed=1.0-transmission;
        float integral=sigma>1e-6?absorbed/sigma:end_t-t;
        vec3 spectrum=field_mode?vec3(0.28+0.45*clamp(density.a,0.0,1.0),0.24+0.30*clamp(abs(density.g),0.0,1.0),0.32+0.42*clamp(abs(density.b),0.0,1.0)):vec3(0.22,0.30,0.42);
        vec3 source=max(pc.emission,0.0)*rho*(1.0-pc.point_fraction)*spectrum;
        if (pc.scattering>0.0 && sigma>0.0) source+=sigma*pc.scattering*sample_light(coord);
        radiance+=trans*source*integral;
        depth_sum+=trans*absorbed*middle; opacity+=trans*absorbed;
        while (next<slices && slice_distance(next,slices)<=end_t) {
            float partial=tau+sigma*max(slice_distance(next,slices)-t,0.0);
            imageStore(tau_image,ivec3(pixel,next),vec4(partial,0.0,0.0,1.0)); ++next;
        }
        tau+=segment_tau; trans*=transmission; t=end_t;
        // Keep integrating tau even after the camera image is opaque: points
        // at deeper distances must receive their complete optical column.
    }
    while (next<slices) { imageStore(tau_image,ivec3(pixel,next),vec4(tau,0.0,0.0,1.0)); ++next; }
    imageStore(radiance_image,pixel,vec4(radiance,clamp(opacity,0.0,1.0)));
    imageStore(depth_image,pixel,vec4(opacity>1e-8?depth_sum/opacity:0.0,0.0,0.0,1.0));
}
