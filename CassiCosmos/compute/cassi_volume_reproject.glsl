#[compute]
// Temporal resolve pass for the presentation fused-volume history path.
//
// Consumes the current color/depth pair produced by
// compute/cassi_voronoi_fused_volume_history.glsl plus the previous history
// pair, reprojects the previous frame into the current camera, validates it,
// and writes the resolved result plus a COMPLETE next history pair.
//
// PRIVATE binding map (owned solely by this pass; registered separately from
// the fused-volume map in scripts/contracts/layout.gd):
//  0 readonly rgba32f  current_color      current radiance/opacity (alpha = Beer-Lambert opacity)
//  1 readonly r32f     current_depth      current representative ray depth (<= 0 = no surface)
//  2 readonly rgba32f  history_color      previous resolved color (last frame's next_history_color)
//  3 readonly r32f     history_depth      previous ray depth (last frame's next_history_depth)
//  4 writeonly rgba32f resolved_output    visible result (stable Texture2DRD backing)
//  5 writeonly rgba32f next_history_color ping-pong history color for the next frame
//  6 writeonly r32f    next_history_depth ping-pong history depth for the next frame
//  7 readonly std430   history_state      previous camera basis + generation/flag state
//
// Ping-pong separation: bindings 0-3 are strictly read-only inputs and
// bindings 4-6 are distinct write-only outputs. No image is read and written
// in the same dispatch, so the resolve is free of in-place image hazards
// without a separate copy pass. The host swaps next (5/6) into previous (2/3)
// once per frame; history_state is rewritten by the host each frame with the
// state this dispatch consumed.
//
// History acceptance requires ALL of:
//  - pc.enabled > 0.5
//  - prior state record valid (flag bit 0) and no poison flag set
//    (cut / resize / mode-transition / reinit-rebuild; see STATE_*_BIT)
//  - topology generation, render-query generation and geometry/radiance key
//    all match between pc and history_state
//  - the current pixel has a valid representative depth (> 0.0, finite)
//  - the reconstructed point lies in front of the previous camera and
//    projects inside the previous image
//  - the previous history depth at that pixel is valid and agrees with the
//    reprojected depth within pc.depth_tolerance (relative to the larger one)
// Any rejection resolves to the current sample only — a stale or mismatched
// sample is never blended. The next history pair is still written completely
// (the fresh current sample), so a later frame may accept only after this
// frame settles.
//
// PC: exactly 32 floats / 128 bytes, scalar-packed (see layout.gd).
//   floats  0..2  current render-local camera origin xyz
//   float   3     current fov_y (radians)
//   floats  4..6  current camera right basis
//   float   7     current output width px
//   floats  8..10 current camera up basis
//   float  11     current output height px
//   floats 12..14 current camera forward basis
//   float  15     current topology generation
//   float  16     current render-query generation
//   float  17     current geometry/radiance key
//   float  18     history_weight (bounded blend factor 0..1 for accepted history)
//   float  19     depth_tolerance (relative depth agreement factor, e.g. 0.05)
//   float  20     enabled (0 = copy-through, feature off)
//   floats 21..31 reserved (0)
#version 450
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

const float EPS_T = 1e-5;
const float EPS_DEN = 1e-7;

// history_state.prev_state.w state-flag bits. Host stores the flag value as
// float(bits); the shader reads it back numerically with uint(...).
const uint STATE_VALID_BIT       = 1u;  // 0x001 prior record fully populated
const uint STATE_CUT_BIT         = 2u;  // 0x002 camera cut / framing reset
const uint STATE_RESIZE_BIT      = 4u;  // 0x004 viewport FOV/resize change
const uint STATE_TRANSITION_BIT  = 8u;  // 0x008 mode/profile/radiance-control change
const uint STATE_REBUILD_BIT     = 16u; // 0x010 reinit/texture-rebuild/device recovery

layout(push_constant, std430) uniform PC {
    vec3 camera_origin; float fov_y;
    vec3 camera_right; float out_width;
    vec3 camera_up; float out_height;
    vec3 camera_forward; float topology_generation;
    float render_query_generation; float geometry_radiance_key;
    float history_weight; float depth_tolerance;
    float enabled; float reserved_0;
    float reserved_1; float reserved_2;
    float reserved_3; float reserved_4;
    float reserved_5; float reserved_6;
    float reserved_7; float reserved_8;
    float reserved_9; float reserved_10;
} pc;

layout(set=0,binding=0,rgba32f) uniform restrict readonly image2D current_color;
layout(set=0,binding=1,r32f) uniform restrict readonly image2D current_depth;
layout(set=0,binding=2,rgba32f) uniform restrict readonly image2D history_color;
layout(set=0,binding=3,r32f) uniform restrict readonly image2D history_depth;
layout(set=0,binding=4,rgba32f) uniform restrict writeonly image2D resolved_output;
layout(set=0,binding=5,rgba32f) uniform restrict writeonly image2D next_history_color;
layout(set=0,binding=6,r32f) uniform restrict writeonly image2D next_history_depth;
layout(set=0,binding=7,std430) readonly buffer HistoryState {
    vec4 prev_origin;   // xyz = previous render-local origin; w = previous fov_y
    vec4 prev_right;    // xyz = previous right basis; w = previous output width px
    vec4 prev_up;       // xyz = previous up basis; w = previous output height px
    vec4 prev_forward;  // xyz = previous forward basis; w = reserved (0)
    vec4 prev_state;    // x = prev topology generation, y = prev render-query
                        // generation, z = prev geometry/radiance key,
                        // w = prev state flags (float(bits), see STATE_*_BIT)
} history_state;

// Current camera ray through the given pixel-center UV (same convention as the
// fused-volume producer: UV -1..1, pixel centers at (i+0.5)/dim).
vec3 current_ray_dir(vec2 uv) {
    float w=max(pc.out_width,1.0), h=max(pc.out_height,1.0);
    float aspect=w/h, tan_half=tan(0.5*pc.fov_y);
    return normalize(pc.camera_forward + pc.camera_right*(uv.x*aspect*tan_half)
                     + pc.camera_up*(uv.y*tan_half));
}

void main() {
    ivec2 pix=ivec2(gl_GlobalInvocationID.xy);
    ivec2 dim=imageSize(current_color);
    if (pix.x>=dim.x || pix.y>=dim.y) return;

    vec4 cur=imageLoad(current_color,pix);
    float depth=imageLoad(current_depth,pix).r; // representative ray depth; <= 0 = none

    vec4 resolved=cur;
    if (pc.enabled > 0.5 && depth > 0.0) {
        // Reconstruct the current sample point from the current camera and the
        // representative depth. Alpha is opacity and is never used as depth.
        vec2 uv=(vec2(pix)+vec2(0.5))/vec2(dim)*2.0-1.0;
        vec3 p=pc.camera_origin+current_ray_dir(uv)*depth;

        // Previous camera basis and state from the history-state record.
        vec4 po=history_state.prev_origin;
        vec4 pr=history_state.prev_right;
        vec4 pu=history_state.prev_up;
        vec4 pf=history_state.prev_forward;
        float prev_fov=po.w, prev_w=pr.w, prev_h=pu.w;
        uint flags=uint(history_state.prev_state.w);
        bool prior_ok=(flags & STATE_VALID_BIT)!=0u
                   && (flags & (STATE_CUT_BIT|STATE_RESIZE_BIT
                              |STATE_TRANSITION_BIT|STATE_REBUILD_BIT))==0u;
        bool gens_ok=pc.topology_generation==history_state.prev_state.x
                  && pc.render_query_generation==history_state.prev_state.y
                  && pc.geometry_radiance_key==history_state.prev_state.z;

        vec3 d=p-po.xyz;
        float f=dot(d,pf.xyz); // forward component in the previous camera
        if (prior_ok && gens_ok && f > EPS_T && prev_fov > 0.0
            && prev_w > 1.0 && prev_h > 1.0) {
            float tan_half=tan(0.5*prev_fov), aspect=prev_w/prev_h;
            // Inverse pinhole projection into the previous NDC.
            vec2 ndc=vec2(dot(d,pr.xyz)/max(f*tan_half*aspect,EPS_DEN),
                          dot(d,pu.xyz)/max(f*tan_half,EPS_DEN));
            vec2 pxf=(ndc*0.5+0.5)*vec2(prev_w,prev_h); // continuous previous pixel
            if (all(greaterThanEqual(pxf,vec2(0.0)))
                && all(lessThan(pxf,vec2(prev_w,prev_h)))) {
                ivec2 hpx=ivec2(pxf);
                vec4 hist=imageLoad(history_color,hpx);
                float hd=imageLoad(history_depth,hpx).r;
                // Distance of p along the previous ray through hpx.
                vec3 rd_prev=normalize(pf.xyz+pr.xyz*(ndc.x*tan_half*aspect)
                                       +pu.xyz*(ndc.y*tan_half));
                float t_prev=dot(d,rd_prev);
                // Relative depth agreement; rejects occluders/disocclusion.
                float tol=pc.depth_tolerance*max(max(t_prev,hd),1e-3);
                if (hd > 0.0 && abs(t_prev-hd) <= tol) {
                    resolved=mix(cur,hist,clamp(pc.history_weight,0.0,1.0));
                }
            }
        }
    }

    // Complete next-history pair: resolved color + CURRENT depth (the depth of
    // the resolved geometry is the current sample's depth). On rejection the
    // pair is the fresh current sample, so history resets on any affected frame.
    imageStore(resolved_output,pix,resolved);
    imageStore(next_history_color,pix,resolved);
    imageStore(next_history_depth,pix,vec4(depth,0.0,0.0,0.0));
}
