#[compute]
// Prescribed one-way LTE continuum formal solution.
// This shader is an observer only: it writes complete sensor radiance and raw
// XYZ, and has no binding to simulation-owned writable state.
#version 450

layout(local_size_x=8,local_size_y=8,local_size_z=1) in;

// One record per visible group.
// a = group-integrated source radiance (numeric units), alpha_a [m^-1],
//     X weight / wavelength interval, Y weight / wavelength interval.
// b = Z weight / wavelength interval, wavelength width [m], frequency lo/hi.
struct GroupRecord { vec4 a; vec4 b; };
layout(set=0,binding=0,rgba32f) uniform writeonly image2D display_radiance;
layout(set=0,binding=1,rgba32f) uniform writeonly image2D raw_xyz;
layout(set=0,binding=2,r32f) uniform writeonly image2D first_depth;
layout(set=0,binding=3,std430) readonly buffer Groups { GroupRecord group[]; } groups;

layout(push_constant,std430) uniform SpectralCameraPC {
    vec3 camera_origin; float fov_y;
    vec3 camera_right; float out_width;
    vec3 camera_up; float out_height;
    vec3 camera_forward; float optical_near;
    vec3 sphere_center; float sphere_radius;
    float length_m_per_sim; float group_count; float boundary_numeric; float source_epoch;
} pc;

bool finite1(float x) { return !(isnan(x) || isinf(x)); }
bool finite3(vec3 x) { return finite1(x.x) && finite1(x.y) && finite1(x.z); }

vec3 ray_direction(vec2 ndc) {
    float aspect=max(pc.out_width,1.0)/max(pc.out_height,1.0);
    float tangent=tan(0.5*max(pc.fov_y,0.001));
    return normalize(pc.camera_forward
        +pc.camera_right*(ndc.x*aspect*tangent)
        +pc.camera_up*(ndc.y*tangent));
}

vec2 sphere_interval(vec3 origin,vec3 direction) {
    vec3 offset=origin-pc.sphere_center;
    float b=dot(offset,direction);
    float c=dot(offset,offset)-pc.sphere_radius*pc.sphere_radius;
    float discriminant=b*b-c;
    if (!(discriminant>0.0)) return vec2(1.0,-1.0);
    float root=sqrt(discriminant);
    return vec2(-b-root,-b+root);
}

float one_minus_exp_negative(float tau) {
    if (tau<1e-4) return tau*(1.0-0.5*tau+tau*tau/6.0);
    return 1.0-exp(-tau);
}

vec3 xyz_to_linear_srgb(vec3 xyz) {
    // IEC 61966-2-1 / D65 matrix. Raw XYZ is preserved in a separate image.
    return mat3(
         3.2406,-0.9689, 0.0557,
        -1.5372, 1.8758,-0.2040,
        -0.4986, 0.0415, 1.0570
    )*xyz;
}

void main() {
    ivec2 pixel=ivec2(gl_GlobalInvocationID.xy);
    ivec2 dimensions=imageSize(display_radiance);
    if (pixel.x>=dimensions.x || pixel.y>=dimensions.y || dimensions.x<=0 || dimensions.y<=0) return;
    vec2 uv=(vec2(pixel)+vec2(0.5))/vec2(dimensions);
    vec2 ndc=vec2(uv.x*2.0-1.0,1.0-uv.y*2.0);
    vec3 direction=ray_direction(ndc);
    vec2 interval=sphere_interval(pc.camera_origin,direction);
    float begin=max(interval.x,max(pc.optical_near,0.0));
    float end=interval.y;
    float distance_sim=max(end-begin,0.0);
    float distance_m=distance_sim*max(pc.length_m_per_sim,0.0);
    vec3 xyz=vec3(0.0);
    int count=clamp(int(round(pc.group_count)),0,64);
    for (int index=0;index<count;++index) {
        GroupRecord record=groups.group[index];
        float source=max(record.a.x,0.0);
        float alpha=max(record.a.y,0.0);
        float tau=alpha*distance_m;
        float transmission=exp(-tau);
        float intensity=max(pc.boundary_numeric,0.0)*transmission
            +source*one_minus_exp_negative(tau);
        xyz+=intensity*vec3(record.a.z,record.a.w,record.b.x);
    }
    if (!finite3(xyz) || any(lessThan(xyz,vec3(0.0)))) xyz=vec3(0.0);
    vec3 linear_rgb=xyz_to_linear_srgb(xyz);
    // Display gamut mapping is explicitly separate from the preserved XYZ.
    linear_rgb=max(linear_rgb,vec3(0.0));
    if (!finite3(linear_rgb)) linear_rgb=vec3(0.0);
    imageStore(display_radiance,pixel,vec4(linear_rgb,1.0));
    imageStore(raw_xyz,pixel,vec4(xyz,1.0));
    imageStore(first_depth,pixel,vec4(distance_sim>0.0?begin:0.0,0.0,0.0,0.0));
}
