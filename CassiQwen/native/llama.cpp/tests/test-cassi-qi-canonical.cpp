#include "ggml-backend.h"
#include "ggml-cpp.h"
#include "ggml.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int64_t STATE_MODE_COUNT = 6144;
constexpr int64_t WAVE_MODE_COUNT = 3072;
constexpr int64_t SCALE_COUNT = 4;
constexpr int64_t BATCH_COUNT = 1;
constexpr int64_t TOKEN_COUNT = 1;
constexpr int64_t STEPS = 1;
constexpr float PHI = 1.618033988749895f;
constexpr float DT = 0.005f;
constexpr float COUPLING = 0.5f;
constexpr float DAMPING_MIN = 0.01f;
constexpr float DAMPING_MAX = 0.5f;
constexpr float EPSILON_TAU = 0.6180339887498948f;
constexpr float SCALE_RATIO = 4.23606797749979f;
constexpr float ENERGY_FLOOR = 1.0e-6f;
constexpr float READ_FLOOR = 0.05f;

struct result {
    std::vector<float> flux;
    std::vector<float> state;
    std::vector<float> diagnostics;
};

template <typename T>
std::vector<T> read_raw(const std::filesystem::path & path, size_t expected_count) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("cannot open " + path.string());
    }
    const auto bytes = stream.tellg();
    if (bytes != static_cast<std::streamoff>(expected_count * sizeof(T))) {
        throw std::runtime_error("unexpected byte count in " + path.string());
    }
    stream.seekg(0);
    std::vector<T> values(expected_count);
    stream.read(reinterpret_cast<char *>(values.data()), static_cast<std::streamsize>(bytes));
    if (!stream) {
        throw std::runtime_error("cannot read " + path.string());
    }
    return values;
}

void write_raw(const std::filesystem::path & path, const std::vector<float> & values) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("cannot write " + path.string());
    }
    stream.write(reinterpret_cast<const char *>(values.data()),
                 static_cast<std::streamsize>(values.size() * sizeof(float)));
    if (!stream) {
        throw std::runtime_error("cannot finish " + path.string());
    }
}

result run_backend(
        ggml_backend_t backend,
        const std::vector<float> & sense_data,
        const std::vector<float> & initial_state,
        const std::vector<float> & mode_data,
        const std::vector<int32_t> & sequence_ids,
        int horizon) {
    ggml_init_params params = {
        16 * 1024 * 1024,
        nullptr,
        true,
    };
    ggml_context_ptr context(ggml_init(params));
    if (!context) {
        throw std::runtime_error("ggml_init failed");
    }

    ggml_tensor * sense = ggml_new_tensor_2d(context.get(), GGML_TYPE_F32, 2 * WAVE_MODE_COUNT, TOKEN_COUNT);
    ggml_tensor * state = ggml_new_tensor_2d(context.get(), GGML_TYPE_F32, 9 * STATE_MODE_COUNT * SCALE_COUNT, BATCH_COUNT);
    ggml_tensor * modes = ggml_new_tensor_1d(context.get(), GGML_TYPE_F32, STATE_MODE_COUNT);
    ggml_tensor * ids = ggml_new_tensor_1d(context.get(), GGML_TYPE_I32, TOKEN_COUNT);
    ggml_tensor * output = ggml_cassi_qi_field_step(
        context.get(), sense, state, modes, ids,
        SCALE_COUNT, PHI, DT, COUPLING,
        DAMPING_MIN, DAMPING_MAX, EPSILON_TAU,
        SCALE_RATIO, ENERGY_FLOOR, READ_FLOOR, STEPS);

    ggml_backend_buffer_ptr buffer(ggml_backend_alloc_ctx_tensors(context.get(), backend));
    if (!buffer) {
        throw std::runtime_error("backend tensor allocation failed");
    }
    ggml_backend_tensor_set(sense, sense_data.data(), 0, sense_data.size() * sizeof(float));
    ggml_backend_tensor_set(modes, mode_data.data(), 0, mode_data.size() * sizeof(float));
    ggml_backend_tensor_set(ids, sequence_ids.data(), 0, sequence_ids.size() * sizeof(int32_t));
    ggml_cgraph * graph = ggml_new_graph_custom(context.get(), GGML_DEFAULT_GRAPH_SIZE, false);
    ggml_build_forward_expand(graph, output);


    std::vector<float> current_state = initial_state;
    const size_t flux_count = 2 * WAVE_MODE_COUNT * TOKEN_COUNT;
    const size_t state_count = 9 * STATE_MODE_COUNT * SCALE_COUNT * BATCH_COUNT;
    const size_t diagnostic_count = 10 * SCALE_COUNT * BATCH_COUNT;
    std::vector<float> packed(flux_count + state_count + diagnostic_count);
    for (int step = 0; step < horizon; ++step) {
        ggml_backend_tensor_set(state, current_state.data(), 0, current_state.size() * sizeof(float));
        const ggml_status status = ggml_backend_graph_compute(backend, graph);
        if (status != GGML_STATUS_SUCCESS) {
            throw std::runtime_error("backend graph compute failed");
        }
        ggml_backend_tensor_get(output, packed.data(), 0, packed.size() * sizeof(float));
        std::copy_n(packed.data() + flux_count, state_count, current_state.data());
    }
    if (horizon == 0) {
        packed.assign(flux_count + state_count + diagnostic_count, 0.0f);
        std::copy(current_state.begin(), current_state.end(), packed.begin() + flux_count);
    }
    return {
        std::vector<float>(packed.begin(), packed.begin() + flux_count),
        current_state,
        std::vector<float>(packed.begin() + flux_count + state_count, packed.end()),
    };
}

float max_abs_difference(const std::vector<float> & actual, const std::vector<float> & expected) {
    if (actual.size() != expected.size()) {
        throw std::runtime_error("comparison size mismatch");
    }
    float maximum = 0.0f;
    for (size_t index = 0; index < actual.size(); ++index) {
        if (!std::isfinite(actual[index]) || !std::isfinite(expected[index])) {
            return std::numeric_limits<float>::infinity();
        }
        maximum = std::max(maximum, std::abs(actual[index] - expected[index]));
    }
    return maximum;
}

void require_close(const char * label, float difference, float tolerance) {
    if (!std::isfinite(difference) || difference > tolerance) {
        throw std::runtime_error(std::string(label) + " max_abs=" + std::to_string(difference));
    }
}
}

int main(int argc, char ** argv) {
    try {
        if (argc != 2) {
            throw std::runtime_error("usage: test-cassi-qi-canonical <fixture-directory>");
        }
        const std::filesystem::path fixture = argv[1];
        ggml_backend_load_all();
        const size_t flux_count = 2 * WAVE_MODE_COUNT * TOKEN_COUNT;
        const size_t state_count = 9 * STATE_MODE_COUNT * SCALE_COUNT * BATCH_COUNT;
        const size_t diagnostic_count = 10 * SCALE_COUNT * BATCH_COUNT;
        const auto sense = read_raw<float>(fixture / "sense.f32", flux_count);
        const auto initial_state = read_raw<float>(fixture / "state-h0.f32", state_count);
        const auto modes = read_raw<float>(fixture / "mode-params.f32", STATE_MODE_COUNT);
        const auto ids = read_raw<int32_t>(fixture / "sequence-ids.i32", TOKEN_COUNT);

        ggml_backend_t cpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
        ggml_backend_t gpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_GPU, nullptr);
        if (!cpu || !gpu) {
            throw std::runtime_error("CPU and GPU backends are required");
        }

        float cpu_python_max = 0.0f;
        float gpu_python_max = 0.0f;
        float cpu_gpu_max = 0.0f;
        for (const int horizon : {1, 4}) {
            const auto expected_flux = read_raw<float>(fixture / ("flux-h" + std::to_string(horizon) + ".f32"), flux_count);
            const auto expected_state = read_raw<float>(fixture / ("state-h" + std::to_string(horizon) + ".f32"), state_count);
            const auto expected_diagnostics = read_raw<float>(fixture / ("diagnostics-h" + std::to_string(horizon) + ".f32"), diagnostic_count);
            const result cpu_result = run_backend(cpu, sense, initial_state, modes, ids, horizon);
            const result gpu_result = run_backend(gpu, sense, initial_state, modes, ids, horizon);
            cpu_python_max = std::max({
                cpu_python_max,
                max_abs_difference(cpu_result.flux, expected_flux),
                max_abs_difference(cpu_result.state, expected_state),
                max_abs_difference(cpu_result.diagnostics, expected_diagnostics),
            });
            gpu_python_max = std::max({
                gpu_python_max,
                max_abs_difference(gpu_result.flux, expected_flux),
                max_abs_difference(gpu_result.state, expected_state),
                max_abs_difference(gpu_result.diagnostics, expected_diagnostics),
            });
            cpu_gpu_max = std::max({
                cpu_gpu_max,
                max_abs_difference(cpu_result.flux, gpu_result.flux),
                max_abs_difference(cpu_result.state, gpu_result.state),
                max_abs_difference(cpu_result.diagnostics, gpu_result.diagnostics),
            });
            if (horizon == 4) {
                write_raw(fixture / "native-cpu-state-h4.f32", cpu_result.state);
                const auto reloaded = read_raw<float>(fixture / "native-cpu-state-h4.f32", state_count);
                if (reloaded != cpu_result.state) {
                    throw std::runtime_error("native save/reload is not byte exact");
                }
            }
        }
        require_close("CPU/Python parity", cpu_python_max, 5.0e-5f);
        require_close("Vulkan/Python parity", gpu_python_max, 5.0e-3f);
        require_close("CPU/Vulkan parity", cpu_gpu_max, 5.0e-3f);
        std::printf(
            "{\"schema\":\"cassi.qi.native-parity.v1\","
            "\"state_mode_count\":6144,\"wave_mode_count\":3072,"
            "\"cpu_python_max_abs\":%.9g,\"vulkan_python_max_abs\":%.9g,"
            "\"cpu_vulkan_max_abs\":%.9g,\"save_reload_exact\":true,"
            "\"verdict\":\"PASS\"}\n",
            cpu_python_max, gpu_python_max, cpu_gpu_max);
        ggml_backend_free(gpu);
        ggml_backend_free(cpu);
        return 0;
    } catch (const std::exception & error) {
        std::fprintf(stderr, "test-cassi-qi-canonical: %s\n", error.what());
        return 1;
    }
}
