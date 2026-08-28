#[compute]
#version 450
// GPU-side MultiMesh transform + color writer.
// Reads position buffer, writes directly to MultiMesh instance buffer.
// Each instance: Transform3D (3 vec4s) + Color (1 vec4) = 16 floats.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict buffer PositionBuf { float p[]; };
layout(set = 0, binding = 1, std430) buffer MultiMeshBuf { float mm[]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float particle_size;
    float _pad1;
    float _pad2;
} pc;

void main() {
    int N = int(pc.N_f);
    int i = int(gl_GlobalInvocationID.x);
    if (i >= N) return;

    float px = p[i*4];
    float py = p[i*4 + 1];
    float pz = p[i*4 + 2];

    // Transform3D: identity rotation, translation = particle position
    // Row 0: (1, 0, 0, px)  — but Godot's instance format is column-major
    // Godot Transform3D instance: [basis.x, 0, basis.y, 0, basis.z, 0, origin, 1]
    // Each row is stored as a vec4: (row, pad) for alignment
    // Actually the buffer layout is: Transform3D = 12 floats, Color = 4 floats = 16 total
    // Transform3D layout: [xx, xy, xz, ox,  yx, yy, yz, oy,  zx, zy, zz, oz]
    // where (xx,xy,xz) = basis.x, etc., (ox,oy,oz) = origin
    int off = i * 16;

    // Identity basis + particle origin
    mm[off + 0]  = 1.0;   // xx
    mm[off + 1]  = 0.0;   // xy
    mm[off + 2]  = 0.0;   // xz
    mm[off + 3]  = px;    // origin.x

    mm[off + 4]  = 0.0;   // yx
    mm[off + 5]  = 1.0;   // yy
    mm[off + 6]  = 0.0;   // yz
    mm[off + 7]  = py;    // origin.y

    mm[off + 8]  = 0.0;   // zx
    mm[off + 9]  = 0.0;   // zy
    mm[off + 10] = 1.0;   // zz
    mm[off + 11] = pz;    // origin.z

    // Color: gradient from inner (warm red) to outer (cool blue)
    float r2 = px*px + py*py + pz*pz;
    float r = sqrt(r2);
    // Normalized radius — need to compute max_r. For now use a fixed scale.
    // We'll compute the max radius in a second pass, or use a fixed bound.
    // For simplicity: color based on abs(r) scaled by cluster_radius
    float t = clamp(r / 10.0, 0.0, 1.0);
    float cr = mix(1.0, 0.2, t);
    float cg = mix(0.8, 0.3, t);
    float cb = mix(0.3, 1.0, t);

    mm[off + 12] = cr;
    mm[off + 13] = cg;
    mm[off + 14] = cb;
    mm[off + 15] = 0.85;  // alpha
}
