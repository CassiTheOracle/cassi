// Model-free probe of the persistent Qi memory loop.
//
// The probe carries one sequence state across a horizon of single-token events and
// reports how far the persistent half follows the wave half and how strong the
// readback is against the sense.  It runs on the CPU backend only, so no model and
// no GPU are needed.
//
//   test-cassi-qi-memory-loop STATE_FILE [EVENTS] [FLOOR] [MEMORY] [SENSE_RMS] [N_EMBD] [SEED] [BACKEND]
//
// MEMORY 1 enables the persistent deposit and the readback, MEMORY 0 leaves both off.
// BACKEND is cpu or gpu, so the two deposit implementations can be compared directly.

#include "ggml.h"
#include "ggml-backend.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static const float PHI = 1.618033988749895f;

struct Options {
    const char * state_path = nullptr;
    int events = 200;
    float floor = 1.0e-6f;
    int memory = 1;
    float sense_rms = 0.0142529f;
    int n_embd = 5120;
    uint64_t seed = 12345;
    const char * backend = "cpu";
};

static uint64_t splitmix(uint64_t & state) {
    state += 0x9E3779B97F4A7C15ull;
    uint64_t z = state;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

// Unit variance content, so the sense entry matches the model row convention.
static float unit_content(uint64_t & state) {
    const float uniform = (float) (splitmix(state) >> 11) / 9007199254740992.0f;
    return std::sqrt(3.0f) * (2.0f * uniform - 1.0f);
}

static bool read_state(const char * path, std::vector<float> & state) {
    FILE * handle = std::fopen(path, "rb");
    if (!handle) { std::fprintf(stderr, "cannot open %s\n", path); return false; }
    std::fseek(handle, 0, SEEK_END);
    const long size = std::ftell(handle);
    std::fseek(handle, 0, SEEK_SET);
    state.resize((size_t) size / sizeof(float));
    const size_t read = std::fread(state.data(), sizeof(float), state.size(), handle);
    std::fclose(handle);
    return read == state.size() && !state.empty();
}

int main(int argc, char ** argv) {
    Options opt;
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s STATE_FILE [EVENTS] [FLOOR] [MEMORY] [SENSE_RMS] [N_EMBD] [SEED]\n", argv[0]);
        return 2;
    }
    opt.state_path = argv[1];
    if (argc > 2) opt.events = (int) std::strtol(argv[2], nullptr, 10);
    if (argc > 3) opt.floor = std::strtof(argv[3], nullptr);
    if (argc > 4) opt.memory = (int) std::strtol(argv[4], nullptr, 10);
    if (argc > 5) opt.sense_rms = std::strtof(argv[5], nullptr);
    if (argc > 6) opt.n_embd = (int) std::strtol(argv[6], nullptr, 10);
    if (argc > 7) opt.seed = std::strtoull(argv[7], nullptr, 10);
    if (argc > 8) opt.backend = argv[8];

    const int scale_count = 4;
    std::vector<float> state;
    if (!read_state(opt.state_path, state)) return 3;
    const int64_t mode_count = (int64_t) state.size() / (9 * scale_count);
    if (mode_count <= 0 || mode_count % 2 != 0 || (int64_t) state.size() != 9 * mode_count * scale_count) {
        std::fprintf(stderr, "state size %zu is not 9*mode*%d\n", state.size(), scale_count);
        return 3;
    }
    const int64_t state_stride = 9 * mode_count * scale_count;
    const int64_t wave_count = mode_count / 2;
    const int64_t sense_width = 2 * wave_count;
    const int64_t read_modes = (int64_t) opt.n_embd / 2;
    if (read_modes > wave_count || opt.n_embd % 2 != 0) { std::fprintf(stderr, "n_embd too wide\n"); return 3; }
    const std::vector<float> initial = state;
    const char * file_name = std::strrchr(opt.state_path, '\\');
    file_name = file_name != nullptr ? file_name + 1 : opt.state_path;

    ggml_backend_load_all();
    const bool use_gpu = std::strcmp(opt.backend, "gpu") == 0;
    ggml_backend_t backend = ggml_backend_init_by_type(
        use_gpu ? GGML_BACKEND_DEVICE_TYPE_GPU : GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
    if (!backend) { std::fprintf(stderr, "no %s backend\n", opt.backend); return 4; }

    ggml_init_params ip = {
        /* .mem_size   = */ ggml_tensor_overhead() * 16 + ggml_graph_overhead_custom(64, false),
        /* .mem_buffer = */ nullptr,
        /* .no_alloc   = */ true,
    };
    ggml_context * ctx = ggml_init(ip);
    if (!ctx) { ggml_backend_free(backend); return 4; }
    ggml_tensor * sense = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, sense_width, 1, 1, 1);
    ggml_tensor * state_t = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, state_stride, 1, 1, 1);
    ggml_tensor * modes = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, mode_count, 1, 1, 1);
    ggml_tensor * ids = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, 1);
    ggml_tensor * out = ggml_cassi_qi_field_step(ctx, sense, state_t, modes, ids, scale_count,
        PHI, 0.005f, 0.5f, 0.01f, 0.5f, 0.618033988749895f, 4.2360679775f, opt.floor, 0.05f, 0.0f,
        false, opt.memory != 0, true, 4);
    if (!out) { std::fprintf(stderr, "op rejected the configuration\n"); ggml_free(ctx); ggml_backend_free(backend); return 5; }
    ggml_set_input(sense);
    ggml_set_input(state_t);
    ggml_set_input(modes);
    ggml_set_input(ids);
    ggml_cgraph * graph = ggml_new_graph_custom(ctx, 64, false);
    ggml_build_forward_expand(graph, out);
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    if (!buffer) { ggml_free(ctx); ggml_backend_free(backend); return 5; }

    // The shipped model profile ramps the mode symbol from damping_min to damping_max.
    std::vector<float> host_modes((size_t) mode_count);
    for (int64_t m = 0; m < mode_count; ++m) {
        const float alpha = mode_count > 1 ? (float) m / (float) (mode_count - 1) : 0.0f;
        host_modes[(size_t) m] = 0.01f + alpha * (0.5f - 0.01f);
    }
    ggml_backend_tensor_set(modes, host_modes.data(), 0, host_modes.size() * sizeof(float));
    const int32_t sequence_id = 0;
    ggml_backend_tensor_set(ids, &sequence_id, 0, sizeof(sequence_id));

    const int64_t flux_count = sense_width;
    const int64_t state_offset = flux_count;
    const int64_t diag_offset = flux_count + state_stride;
    std::vector<float> host_sense((size_t) sense_width);
    std::vector<float> host_out((size_t) (flux_count + state_stride + 10 * scale_count));

    std::printf("{\"schema\":\"cassi.qi.memory-loop.v1\",\"state_file\":\"%s\",\"mode_count\":%lld,"
                "\"wave_count\":%lld,\"read_modes\":%lld,\"events\":%d,\"floor\":%g,\"memory\":%d,"
                "\"sense_rms\":%g,\"n_embd\":%d,\"seed\":%llu,\"backend\":\"%s\",\"rows\":[",
        file_name, (long long) mode_count, (long long) wave_count, (long long) read_modes,
        opt.events, (double) opt.floor, opt.memory, (double) opt.sense_rms, opt.n_embd,
        (unsigned long long) opt.seed, ggml_backend_name(backend));
    uint64_t rng = opt.seed;
    for (int event = 0; event < opt.events; ++event) {
        double content_sq = 0.0;
        double readback_sq = 0.0;
        for (int64_t k = 0; k < sense_width; ++k) {
            const float content = opt.sense_rms * unit_content(rng);
            float value = content;
            content_sq += (double) content * content;
            if (opt.memory != 0 && k / 2 < read_modes) {
                const int64_t mirror = wave_count + k / 2;
                const float memory_value = state[(size_t) (mirror * 9 + (k % 2))];
                value += memory_value / std::sqrt((float) opt.n_embd);
                readback_sq += (double) memory_value * memory_value / (double) opt.n_embd;
            }
            host_sense[(size_t) k] = value;
        }
        ggml_backend_tensor_set(state_t, state.data(), 0, state.size() * sizeof(float));
        ggml_backend_tensor_set(sense, host_sense.data(), 0, host_sense.size() * sizeof(float));
        if (ggml_backend_graph_compute(backend, graph) != GGML_STATUS_SUCCESS) {
            std::fprintf(stderr, "compute failed at event %d\n", event);
            return 6;
        }
        ggml_backend_tensor_get(out, host_out.data(), 0, host_out.size() * sizeof(float));
        std::memcpy(state.data(), host_out.data() + state_offset, state.size() * sizeof(float));

        double wave_sq = 0.0;
        double tail_sq = 0.0;
        double delta_sq = 0.0;
        double dot = 0.0;
        double wave_norm = 0.0;
        double tail_norm = 0.0;
        for (int64_t m = 0; m < wave_count; ++m) {
            wave_sq += (double) state[(size_t) (m * 9 + 0)] * state[(size_t) (m * 9 + 0)];
            wave_sq += (double) state[(size_t) (m * 9 + 1)] * state[(size_t) (m * 9 + 1)];
            if (m < read_modes) {
                const float re = state[(size_t) (m * 9 + 0)];
                const float im = state[(size_t) (m * 9 + 1)];
                const float tre = state[(size_t) ((wave_count + m) * 9 + 0)];
                const float tim = state[(size_t) ((wave_count + m) * 9 + 1)];
                dot += (double) tre * re + (double) tim * im;
                wave_norm += (double) re * re + (double) im * im;
                tail_norm += (double) tre * tre + (double) tim * tim;
                const float dre = tre - initial[(size_t) ((wave_count + m) * 9 + 0)];
                const float dim = tim - initial[(size_t) ((wave_count + m) * 9 + 1)];
                delta_sq += (double) dre * dre + (double) dim * dim;
            }
        }
        for (int64_t m = wave_count; m < mode_count; ++m) {
            tail_sq += (double) state[(size_t) (m * 9 + 0)] * state[(size_t) (m * 9 + 0)];
            tail_sq += (double) state[(size_t) (m * 9 + 1)] * state[(size_t) (m * 9 + 1)];
        }
        double flux_sq = 0.0;
        for (int64_t k = 0; k < flux_count; ++k) {
            flux_sq += (double) host_out[(size_t) k] * host_out[(size_t) k];
        }
        const double wave_rms = std::sqrt(wave_sq / (double) (2 * wave_count));
        const double tail_rms = std::sqrt(tail_sq / (double) (2 * (mode_count - wave_count)));
        const double read_rms = std::sqrt(readback_sq / (double) (2 * read_modes));
        const double content_rms = std::sqrt(content_sq / (double) sense_width);
        const double cosine = wave_norm > 0.0 && tail_norm > 0.0 ? dot / std::sqrt(wave_norm * tail_norm) : 0.0;
        const double tail_drift = tail_norm > 0.0 ? std::sqrt(delta_sq / tail_norm) : 0.0;
        if (event == 0 || (event + 1) % 20 == 0 || event + 1 == opt.events) {
            std::printf("%s{\"event\":%d,\"wave_rms\":%.6g,\"tail_rms\":%.6g,\"tail_cos_wave\":%.6f,"
                        "\"tail_drift\":%.6g,\"flux_rms\":%.6g,\"content_rms\":%.6g,\"readback_rms\":%.6g,"
                        "\"readback_share\":%.6g,\"read_gate0\":%.6g,\"available0\":%g}",
                event == 0 ? "" : ",", event, wave_rms, tail_rms, cosine, tail_drift,
                std::sqrt(flux_sq / (double) flux_count), content_rms, read_rms,
                content_rms > 0.0 ? read_rms / content_rms : 0.0,
                (double) host_out[(size_t) (diag_offset + 5)], (double) host_out[(size_t) (diag_offset + 9)]);
        }
    }
    std::printf("]}\n");
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    ggml_backend_free(backend);
    return 0;
}
