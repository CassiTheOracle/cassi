#include "common.h"
#include "../src/llama-ext.h"
#include "llama.h"

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <limits>
#include <memory>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using context_ptr = std::unique_ptr<llama_context, decltype(&llama_free)>;

struct layer_capture {
    uint32_t layer = 0;
    std::vector<float> values;
    double l2_norm = 0.0;
    double difference_norm = 0.0;
    bool has_difference = false;
    bool finite = false;
    std::string path;
};

uint64_t parse_unsigned(std::string_view text, const char * name) {
    if (text.empty() || text.front() == '-') {
        throw std::runtime_error(std::string(name) + " must be a non-negative integer");
    }
    uint64_t value = 0;
    const char * first = text.data();
    const char * last = first + text.size();
    const auto result = std::from_chars(first, last, value, 10);
    if (result.ec != std::errc() || result.ptr != last) {
        throw std::runtime_error(std::string("invalid ") + name + ": " + std::string(text));
    }
    return value;
}

int32_t parse_signed(std::string_view text, const char * name) {
    if (text.empty()) {
        throw std::runtime_error(std::string("invalid ") + name + ": empty");
    }
    int32_t value = 0;
    const char * first = text.data();
    const char * last = first + text.size();
    const auto result = std::from_chars(first, last, value, 10);
    if (result.ec != std::errc() || result.ptr != last) {
        throw std::runtime_error(std::string("invalid ") + name + ": " + std::string(text));
    }
    return value;
}

float parse_float(std::string_view text, const char * name) {
    if (text.empty()) {
        throw std::runtime_error(std::string("invalid ") + name + ": empty");
    }
    std::string value(text);
    char * end = nullptr;
    errno = 0;
    const float result = std::strtof(value.c_str(), &end);
    if (end != value.c_str() + value.size() || errno == ERANGE || !std::isfinite(result)) {
        throw std::runtime_error(std::string("invalid ") + name + ": " + value);
    }
    return result;
}
bool parse_reset_flag(std::string_view text) {
    if (text == "0") {
        return false;
    }
    if (text == "1") {
        return true;
    }
    throw std::runtime_error("RESET_EACH_GENERATED_TOKEN must be 0 or 1");
}
bool parse_phase_shuffle_flag(std::string_view text) {
    if (text == "0") {
        return false;
    }
    if (text == "1") {
        return true;
    }
    throw std::runtime_error("PHASE_SHUFFLE_AFTER_PROMPT must be 0 or 1");
}


std::string read_text_file(const std::string & path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("failed to open prompt fixture: " + path);
    }
    std::ostringstream contents;
    contents << stream.rdbuf();
    if (!stream.eof() && stream.fail()) {
        throw std::runtime_error("failed to read prompt fixture: " + path);
    }
    return contents.str();
}

uint64_t fnv1a_bytes(std::string_view text) {
    uint64_t hash = 1469598103934665603ull;
    for (const char raw : text) {
        hash ^= static_cast<uint64_t>(static_cast<unsigned char>(raw));
        hash *= 1099511628211ull;
    }
    return hash;
}

// STEPS ALPHA per generated-token decode. A hold uses ALPHA 0.
std::vector<std::pair<uint32_t, float>> parse_schedule(
        const std::string & text, const std::string & path) {
    std::vector<std::pair<uint32_t, float>> entries;
    std::istringstream lines(text);
    std::string line;
    size_t line_number = 0;
    while (std::getline(lines, line)) {
        ++line_number;
        const size_t comment = line.find('#');
        if (comment != std::string::npos) {
            line = line.substr(0, comment);
        }
        std::istringstream fields(line);
        std::string steps_text;
        std::string alpha_text;
        if (!(fields >> steps_text)) {
            continue;
        }
        if (!(fields >> alpha_text)) {
            throw std::runtime_error(
                "schedule line " + std::to_string(line_number) + " of " + path +
                " needs STEPS ALPHA");
        }
        std::string extra;
        if (fields >> extra) {
            throw std::runtime_error(
                "schedule line " + std::to_string(line_number) + " of " + path +
                " has trailing fields");
        }
        const uint64_t steps = parse_unsigned(steps_text, "schedule STEPS");
        if (steps == 0) {
            throw std::runtime_error(
                "schedule STEPS must be at least 1; use ALPHA 0 to hold the field "
                "without injection");
        }
        if (steps > std::numeric_limits<uint32_t>::max()) {
            throw std::runtime_error("schedule STEPS is too large");
        }
        const float alpha = parse_float(alpha_text, "schedule ALPHA");
        if (alpha < 0.0f) {
            throw std::runtime_error("schedule ALPHA must be finite and non-negative");
        }
        entries.emplace_back(static_cast<uint32_t>(steps), alpha);
    }
    if (entries.empty()) {
        throw std::runtime_error("schedule fixture has no entries: " + path);
    }
    return entries;
}

std::vector<float> read_state_file(const std::string & path, size_t count) {
    if (count == 0 || count > std::numeric_limits<size_t>::max() / sizeof(float)) {
        throw std::runtime_error("invalid Qi state size");
    }
    const size_t bytes = count * sizeof(float);
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("failed to open Qi state fixture: " + path);
    }
    const std::streamoff end = stream.tellg();
    if (end < 0 || static_cast<uintmax_t>(end) != bytes) {
        throw std::runtime_error("Qi state fixture has the wrong byte length: " + path);
    }
    stream.seekg(0, std::ios::beg);
    std::vector<float> state(count);
    stream.read(reinterpret_cast<char *>(state.data()), static_cast<std::streamsize>(bytes));
    if (!stream || stream.gcount() != static_cast<std::streamsize>(bytes)) {
        throw std::runtime_error("failed to read Qi state fixture: " + path);
    }
    return state;
}

uint64_t fnv1a(const std::vector<float> & values) {
    constexpr uint64_t offset = UINT64_C(1469598103934665603);
    constexpr uint64_t prime = UINT64_C(1099511628211);
    uint64_t hash = offset;
    const auto * bytes = reinterpret_cast<const uint8_t *>(values.data());
    for (size_t i = 0; i < values.size() * sizeof(float); ++i) {
        hash ^= bytes[i];
        hash *= prime;
    }
    return hash;
}
void phase_shuffle(std::vector<float> & state) {
    constexpr size_t mode_count = 6144;
    constexpr size_t component_count = 9;
    constexpr size_t scale_stride = mode_count * component_count;
    if (state.empty() || state.size() % scale_stride != 0) {
        throw std::runtime_error("Qi state has incompatible phase-shuffle geometry");
    }
    const size_t scale_count = state.size() / scale_stride;
    for (size_t scale = 0; scale < scale_count; ++scale) {
        for (size_t mode = 0; mode < mode_count; ++mode) {
            const unsigned turns = static_cast<unsigned>((mode + 2 * scale) % 3 + 1);
            float * components = state.data() + scale * scale_stride + mode * component_count;
            for (size_t pair = 0; pair < 4; ++pair) {
                float & real = components[2 * pair];
                float & imag = components[2 * pair + 1];
                const float old_real = real;
                const float old_imag = imag;
                if (turns == 1) {
                    real = -old_imag;
                    imag = old_real;
                } else if (turns == 2) {
                    real = -old_real;
                    imag = -old_imag;
                } else {
                    real = old_imag;
                    imag = -old_real;
                }
            }
        }
    }
}


void require_finite(const std::vector<float> & values, const char * label) {
    for (size_t i = 0; i < values.size(); ++i) {
        if (!std::isfinite(values[i])) {
            throw std::runtime_error(std::string(label) + " contains a non-finite value at index " + std::to_string(i));
        }
    }
}

double l2_norm(const std::vector<float> & values, const char * label) {
    long double sum = 0.0L;
    for (float value : values) {
        sum += static_cast<long double>(value) * static_cast<long double>(value);
    }
    const long double norm = std::sqrt(sum);
    if (!std::isfinite(norm)) {
        throw std::runtime_error(std::string(label) + " L2 norm is non-finite");
    }
    return static_cast<double>(norm);
}

double difference_norm(const std::vector<float> & current, const std::vector<float> & previous) {
    if (current.size() != previous.size()) {
        throw std::runtime_error("captured layer widths differ");
    }
    long double sum = 0.0L;
    for (size_t i = 0; i < current.size(); ++i) {
        const long double delta = static_cast<long double>(current[i]) - static_cast<long double>(previous[i]);
        sum += delta * delta;
    }
    const long double norm = std::sqrt(sum);
    if (!std::isfinite(norm)) {
        throw std::runtime_error("captured layer difference norm is non-finite");
    }
    return static_cast<double>(norm);
}

std::string json_escape(std::string_view text) {
    static constexpr char hex[] = "0123456789abcdef";
    std::string escaped;
    escaped.reserve(text.size());
    for (unsigned char value : text) {
        switch (value) {
            case '"': escaped += "\\\""; break;
            case '\\': escaped += "\\\\"; break;
            case '\b': escaped += "\\b"; break;
            case '\f': escaped += "\\f"; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default:
                if (value < 0x20) {
                    escaped += "\\u00";
                    escaped += hex[(value >> 4) & 0x0f];
                    escaped += hex[value & 0x0f];
                } else {
                    escaped.push_back(static_cast<char>(value));
                }
                break;
        }
    }
    return escaped;
}

void write_f32_file(const std::filesystem::path & path, const std::vector<float> & values) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("failed to open capture output: " + path.string());
    }
    if (!values.empty()) {
        stream.write(reinterpret_cast<const char *>(values.data()), static_cast<std::streamsize>(values.size() * sizeof(float)));
    }
    if (!stream) {
        throw std::runtime_error("failed to write capture output: " + path.string());
    }
}

std::vector<layer_capture> capture_layers(
        llama_context * context,
        uint32_t first_layer,
        uint32_t last_layer,
        size_t n_embd,
        size_t final_row) {
    std::vector<layer_capture> captures;
    captures.reserve(static_cast<size_t>(last_layer - first_layer) + 1);
    for (uint32_t layer = first_layer;; ++layer) {
        float * raw = llama_get_embeddings_layer_inp(context, layer);
        if (raw == nullptr) {
            throw std::runtime_error("null layer capture at layer " + std::to_string(layer));
        }
        layer_capture capture;
        capture.layer = layer;
        capture.values.assign(raw + final_row * n_embd, raw + (final_row + 1) * n_embd);
        require_finite(capture.values, "layer capture");
        capture.l2_norm = l2_norm(capture.values, "layer capture");
        capture.finite = true;
        if (!captures.empty()) {
            capture.difference_norm = difference_norm(capture.values, captures.back().values);
            capture.has_difference = true;
        }
        captures.push_back(std::move(capture));
        if (layer == last_layer) {
            break;
        }
    }
    return captures;
}

// One attention dump: the per-head probability tensor of every layer that exposes one, the
// attention output of the same layers, and the head input. Shapes come from the engine, so a
// silently empty dump shows up as a zero rank instead of an absent field.
struct attention_dump {
    std::vector<std::pair<uint32_t, std::string>> probs_files;
    std::vector<std::pair<uint32_t, std::string>> delta_files;
    int64_t probs_shape[3] = { 0, 0, 0 };
    int64_t delta_shape[3] = { 0, 0, 0 };
    int64_t head_shape[3] = { 0, 0, 0 };
    std::string head_path;
};

int64_t attention_elements(const int64_t * shape, int32_t rank) {
    int64_t count = 1;
    for (int32_t index = 0; index < rank; ++index) {
        count *= shape[index];
    }
    return count;
}

void dump_attention(
        llama_context * context,
        const std::filesystem::path & dir,
        uint32_t first_layer,
        uint32_t last_layer,
        const std::string & tag,
        attention_dump & dump) {
    for (uint32_t layer = first_layer;; ++layer) {
        int64_t probs_shape[3] = { 0, 0, 0 };
        const int32_t probs_rank = llama_cassi_capture_shape(
            context, LLAMA_CASSI_CAPTURE_ATTENTION_PROBS, layer, probs_shape);
        if (probs_rank > 0) {
            const size_t count = static_cast<size_t>(attention_elements(probs_shape, probs_rank));
            std::vector<float> values(count);
            if (!llama_cassi_capture_copy(
                    context, LLAMA_CASSI_CAPTURE_ATTENTION_PROBS, layer, values.data(), count)) {
                throw std::runtime_error(
                    "failed to copy attention probabilities at layer " + std::to_string(layer));
            }
            require_finite(values, "attention probabilities");
            const std::filesystem::path path = dir /
                ("layer-" + std::to_string(layer) + "-attn-probs-" + tag + ".f32");
            write_f32_file(path, values);
            dump.probs_files.emplace_back(layer, path.string());
            for (int32_t index = 0; index < probs_rank; ++index) {
                dump.probs_shape[index] = probs_shape[index];
            }
        }
        int64_t delta_shape[3] = { 0, 0, 0 };
        const int32_t delta_rank = llama_cassi_capture_shape(
            context, LLAMA_CASSI_CAPTURE_ATTENTION_OUTPUT, layer, delta_shape);
        if (delta_rank > 0) {
            const size_t count = static_cast<size_t>(attention_elements(delta_shape, delta_rank));
            std::vector<float> values(count);
            if (!llama_cassi_capture_copy(
                    context, LLAMA_CASSI_CAPTURE_ATTENTION_OUTPUT, layer, values.data(), count)) {
                throw std::runtime_error(
                    "failed to copy attention output at layer " + std::to_string(layer));
            }
            require_finite(values, "attention output");
            const std::filesystem::path path = dir /
                ("layer-" + std::to_string(layer) + "-attn-delta-" + tag + ".f32");
            write_f32_file(path, values);
            dump.delta_files.emplace_back(layer, path.string());
            for (int32_t index = 0; index < delta_rank; ++index) {
                dump.delta_shape[index] = delta_shape[index];
            }
        }
        if (layer == last_layer) {
            break;
        }
    }
    int64_t head_shape[3] = { 0, 0, 0 };
    const int32_t head_rank = llama_cassi_capture_shape(
        context, LLAMA_CASSI_CAPTURE_HEAD_INPUT, 0, head_shape);
    if (head_rank > 0) {
        const size_t count = static_cast<size_t>(attention_elements(head_shape, head_rank));
        std::vector<float> values(count);
        if (!llama_cassi_capture_copy(
                context, LLAMA_CASSI_CAPTURE_HEAD_INPUT, 0, values.data(), count)) {
            throw std::runtime_error("failed to copy the head input capture");
        }
        require_finite(values, "head input");
        const std::filesystem::path path = dir / ("head-input-" + tag + ".f32");
        write_f32_file(path, values);
        dump.head_path = path.string();
        for (int32_t index = 0; index < head_rank; ++index) {
            dump.head_shape[index] = head_shape[index];
        }
    }
}

std::string shape_json(const int64_t * shape, size_t count) {
    std::string text = "[";
    for (size_t index = 0; index < count; ++index) {
        if (index != 0) {
            text += ',';
        }
        text += std::to_string(shape[index]);
    }
    return text + "]";
}

std::string attention_file_json(const std::vector<std::pair<uint32_t, std::string>> & files) {
    std::string text = "[";
    for (size_t index = 0; index < files.size(); ++index) {
        if (index != 0) {
            text += ',';
        }
        text += "{\"layer\":" + std::to_string(files[index].first) + ",\"name\":\"" +
            json_escape(std::filesystem::path(files[index].second).filename().string()) + "\"}";
    }
    return text + "]";
}

std::string attention_dump_json(const attention_dump & dump) {
    return "{\"probs_shape\":" + shape_json(dump.probs_shape, 3) +
        ",\"delta_shape\":" + shape_json(dump.delta_shape, 3) +
        ",\"head_shape\":" + shape_json(dump.head_shape, 3) +
        ",\"head_file\":" + (dump.head_path.empty()
            ? std::string("null")
            : "\"" + json_escape(std::filesystem::path(dump.head_path).filename().string()) + "\"") +
        ",\"probs_layers\":" + std::to_string(dump.probs_files.size()) +
        ",\"delta_layers\":" + std::to_string(dump.delta_files.size()) +
        ",\"probs_files\":" + attention_file_json(dump.probs_files) +
        ",\"delta_files\":" + attention_file_json(dump.delta_files) + "}";
}

llama_token greedy_token(const float * logits, int32_t n_vocab) {
    if (logits == nullptr || n_vocab <= 0) {
        throw std::runtime_error("logits unavailable");
    }
    llama_token best = 0;
    float best_value = -std::numeric_limits<float>::infinity();
    for (int32_t token = 0; token < n_vocab; ++token) {
        const float value = logits[token];
        if (!std::isfinite(value)) {
            throw std::runtime_error("non-finite logits at token " + std::to_string(token));
        }
        if (value > best_value) {
            best_value = value;
            best = token;
        }
    }
    if (!std::isfinite(best_value)) {
        throw std::runtime_error("logits contain no finite value");
    }
    return best;
}

void print_token_array(const std::vector<llama_token> & tokens) {
    std::cout << '[';
    for (size_t i = 0; i < tokens.size(); ++i) {
        if (i != 0) {
            std::cout << ',';
        }
        std::cout << static_cast<int64_t>(tokens[i]);
    }
    std::cout << ']';
}

void print_double(double value) {
    if (!std::isfinite(value)) {
        throw std::runtime_error("attempted to emit a non-finite JSON number");
    }
    std::cout << std::setprecision(17) << value;
}

} // namespace

int main(int argc, char ** argv) {
    if (argc < 9 || argc > 40) {
        std::cerr << "usage: " << argv[0]
                  << " MODEL STATE cpu|gpu PROMPT_FILE FIELD_LAYER STEPS ALPHA GENERATE_TOKENS [OUTPUT_DIR] [RESET_EACH_GENERATED_TOKEN] [PHASE_SHUFFLE_AFTER_PROMPT] [--schedule PATH] [--displacement N] [--substitute F] [--modulate] [--modulate-gain F] [--intervention N] [--wave-modes N] [--row-width N] [--flux-dump] [--capture-steps] [--capture-attention]"
                  << '\n';
        return 2;
    }

    try {
        const std::string model_path = argv[1];
        const std::string state_path = argv[2];
        const std::string backend_name = argv[3];
        const std::string prompt_path = argv[4];
        const int32_t field_layer_arg = parse_signed(argv[5], "FIELD_LAYER");
        const uint64_t steps_arg = parse_unsigned(argv[6], "STEPS");
        const float alpha = parse_float(argv[7], "ALPHA");
        const uint64_t generate_tokens_arg = parse_unsigned(argv[8], "GENERATE_TOKENS");
        std::optional<std::filesystem::path> output_dir;
        std::optional<std::filesystem::path> schedule_path;
        bool reset_each_generated_token = false;
        bool phase_shuffle_after_prompt = false;
        int32_t displacement = 0;
        float substitute = 0.0f;
        bool modulate = false;
        float modulate_gain = 0.0f;
        int32_t intervention_override = -1;
        bool flux_dump = false;
        bool capture_steps = false;
        bool capture_attention = false;
        bool fill_modes = false;
        bool memory_fill = false;
        float energy_floor = 0.0f;
        float read_floor = 0.0f;
        bool read_absolute = false;
        int32_t intervention_used = 0;
        uint32_t wave_modes = 0;
        uint32_t row_width = 0;
        std::vector<std::string> positional;
        for (int index = 9; index < argc; ++index) {
            const std::string argument = argv[index];
            if (argument == "--schedule") {
                if (schedule_path.has_value()) {
                    throw std::runtime_error("--schedule was supplied more than once");
                }
                if (index + 1 >= argc || std::string(argv[index + 1]).empty()) {
                    throw std::runtime_error("--schedule requires a non-empty path");
                }
                schedule_path = std::filesystem::path(argv[index + 1]);
                ++index;
                continue;
            }
            if (argument == "--displacement") {
                if (index + 1 >= argc) {
                    throw std::runtime_error("--displacement requires a value");
                }
                displacement = parse_signed(argv[index + 1], "DISPLACEMENT");
                ++index;
                continue;
            }
            if (argument == "--substitute") {
                if (index + 1 >= argc) {
                    throw std::runtime_error("--substitute requires a value");
                }
                substitute = parse_float(argv[index + 1], "SUBSTITUTE");
                ++index;
                continue;
            }
            if (argument == "--modulate") {
                modulate = true;
                continue;
            }
            if (argument == "--modulate-gain") {
                if (index + 1 >= argc) {
                    throw std::runtime_error("--modulate-gain requires a value");
                }
                modulate_gain = parse_float(argv[index + 1], "MODULATE_GAIN");
                ++index;
                continue;
            }
            if (argument == "--intervention") {
                if (index + 1 >= argc) {
                    throw std::runtime_error("--intervention requires a value");
                }
                intervention_override = parse_signed(argv[index + 1], "INTERVENTION");
                if (intervention_override < 0 || intervention_override > 1) {
                    throw std::runtime_error("INTERVENTION must be 0 or 1");
                }
                ++index;
                continue;
            }
            if (argument == "--wave-modes") {
                if (index + 1 >= argc) {
                    throw std::runtime_error("--wave-modes requires a value");
                }
                wave_modes = (uint32_t) parse_signed(argv[index + 1], "WAVE_MODES");
                if (wave_modes == 0) {
                    throw std::runtime_error("--wave-modes must be positive");
                }
                ++index;
                continue;
            }
            if (argument == "--memory-fill") {
                memory_fill = true;
                continue;
            }
            if (argument == "--energy-floor") {
                energy_floor = parse_float(argv[index + 1], "ENERGY_FLOOR");
                index += 1;
                continue;
            }
            if (argument == "--read-floor") {
                read_floor = parse_float(argv[index + 1], "READ_FLOOR");
                index += 1;
                continue;
            }
            if (argument == "--read-absolute") {
                read_absolute = true;
                continue;
            }
            if (argument == "--fill-modes") {
                fill_modes = true;
                continue;
            }
            if (argument == "--flux-dump") {
                flux_dump = true;
                continue;
            }
            if (argument == "--capture-steps") {
                capture_steps = true;
                continue;
            }
            if (argument == "--capture-attention") {
                capture_attention = true;
                continue;
            }
            if (argument == "--row-width") {
                if (index + 1 >= argc) {
                    throw std::runtime_error("--row-width requires a value");
                }
                row_width = (uint32_t) parse_signed(argv[index + 1], "ROW_WIDTH");
                if (row_width == 0) {
                    throw std::runtime_error("--row-width must be positive");
                }
                ++index;
                continue;
            }
            positional.push_back(argument);
        }
        if (positional.size() == 1) {
            const std::string optional_arg = positional[0];
            if (optional_arg == "0" || optional_arg == "1") {
                reset_each_generated_token = parse_reset_flag(optional_arg);
            } else {
                output_dir = std::filesystem::path(optional_arg);
            }
        } else if (positional.size() == 2) {
            output_dir = std::filesystem::path(positional[0]);
            reset_each_generated_token = parse_reset_flag(positional[1]);
        } else if (positional.size() == 3) {
            output_dir = std::filesystem::path(positional[0]);
            reset_each_generated_token = parse_reset_flag(positional[1]);
            phase_shuffle_after_prompt = parse_phase_shuffle_flag(positional[2]);
            if (reset_each_generated_token && phase_shuffle_after_prompt) {
                throw std::runtime_error("reset and phase-shuffle controls are mutually exclusive");
            }
        } else if (positional.size() > 3) {
            throw std::runtime_error("too many positional arguments");
        }
        if (output_dir.has_value() && output_dir->empty()) {
            throw std::runtime_error("OUTPUT_DIR must not be empty when supplied");
        }
        if ((capture_steps || capture_attention) && !output_dir.has_value()) {
            throw std::runtime_error("--capture-steps and --capture-attention require OUTPUT_DIR");
        }
        const bool use_gpu = backend_name == "gpu";
        if (!use_gpu && backend_name != "cpu") {
            throw std::runtime_error("backend must be cpu or gpu");
        }
        if (alpha < 0.0f) {
            throw std::runtime_error("ALPHA must be finite and non-negative");
        }
        if (substitute < 0.0f || substitute > 1.0f) {
            throw std::runtime_error("SUBSTITUTE must be in [0,1]");
        }
        if (substitute > 0.0f && displacement < 3) {
            // the seam fills a recurrent-state write the displacement suppressed;
            // below level 3 nothing is suppressed, so the arm would be a no-op
            throw std::runtime_error("SUBSTITUTE requires DISPLACEMENT of at least 3");
        }
        if (modulate && (displacement >= 3 || substitute > 0.0f)) {
            // modulation adds to the write it reads, so nothing may suppress that write
            throw std::runtime_error("--modulate requires DISPLACEMENT of at most 2 and no SUBSTITUTE");
        }
        if (!(modulate_gain >= 0.0f) || modulate_gain > 1.0e6f) {
            throw std::runtime_error("MODULATE_GAIN must be finite and non-negative");
        }
        if (steps_arg > std::numeric_limits<uint32_t>::max()) {
            throw std::runtime_error("STEPS is too large");
        }
        if (generate_tokens_arg > std::numeric_limits<uint32_t>::max()) {
            throw std::runtime_error("GENERATE_TOKENS is too large");
        }
        const uint32_t steps = static_cast<uint32_t>(steps_arg);
        const uint32_t generate_tokens = static_cast<uint32_t>(generate_tokens_arg);
        const bool qi_enabled = steps > 0;
        if (substitute > 0.0f && !qi_enabled) {
            throw std::runtime_error("SUBSTITUTE requires a positive STEPS coupling");
        }
        if (modulate && !qi_enabled) {
            throw std::runtime_error("--modulate requires a positive STEPS coupling");
        }

        std::vector<std::pair<uint32_t, float>> schedule;
        std::string schedule_text;
        if (schedule_path.has_value()) {
            if (!qi_enabled) {
                throw std::runtime_error("--schedule requires a positive STEPS coupling");
            }
            schedule_text = read_text_file(schedule_path->string());
            schedule = parse_schedule(schedule_text, schedule_path->string());
            if (schedule.size() < generate_tokens) {
                throw std::runtime_error(
                    "schedule fixture has fewer entries than GENERATE_TOKENS: " +
                    schedule_path->string());
            }
        }

        const std::string prompt_text = read_text_file(prompt_path);
        ggml_backend_load_all();

        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = use_gpu ? 99 : 0;
        model_ptr model(llama_model_load_from_file(model_path.c_str(), model_params), llama_model_free);
        if (!model) {
            throw std::runtime_error("failed to load model");
        }

        const int32_t n_layers = llama_model_n_layer(model.get());
        const int32_t n_embd_i = llama_model_n_embd(model.get());
        if (n_layers <= 0 || n_embd_i <= 0) {
            throw std::runtime_error("model has invalid layer or embedding dimensions");
        }
        if (field_layer_arg < 0 || field_layer_arg >= n_layers) {
            throw std::runtime_error("FIELD_LAYER must be in [0,n_layer)");
        }
        const uint32_t last_capture_layer = static_cast<uint32_t>(n_layers - 1);
        const uint32_t field_layer = static_cast<uint32_t>(field_layer_arg);
        const size_t n_embd = static_cast<size_t>(n_embd_i);
        const llama_vocab * vocab = llama_model_get_vocab(model.get());
        if (vocab == nullptr) {
            throw std::runtime_error("model vocabulary is unavailable");
        }
        std::vector<llama_token> prompt_tokens = common_tokenize(vocab, prompt_text, true, false);
        if (prompt_tokens.empty()) {
            throw std::runtime_error("prompt fixture tokenized to zero tokens");
        }
        if (prompt_tokens.size() > static_cast<size_t>(std::numeric_limits<int32_t>::max())) {
            throw std::runtime_error("prompt fixture has too many tokens");
        }
        const uint64_t required_ctx = static_cast<uint64_t>(prompt_tokens.size()) + generate_tokens + 1;
        if (required_ctx > std::numeric_limits<uint32_t>::max()) {
            throw std::runtime_error("prompt plus generation exceeds context parameter range");
        }
        const uint32_t n_ctx = static_cast<uint32_t>(std::max<uint64_t>(64, required_ctx));
        const uint32_t n_batch = static_cast<uint32_t>(std::max<size_t>(1, prompt_tokens.size()));

        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = n_ctx;
        context_params.n_batch = n_batch;
        context_params.n_ubatch = n_batch;
        context_params.n_seq_max = 1;
        context_params.cassi_modal = false;
        context_params.cassi_field_step = false;
        context_params.cassi_qi_field = qi_enabled;
        if (capture_attention) {
            // the per-head probabilities are the softmax that flash attention folds into its
            // kernel, so the capture needs the unfused path
            context_params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
        }
        if (qi_enabled) {
            context_params.cassi_qi_field_layer = field_layer;
            context_params.cassi_qi_field_scales = 4;
            context_params.cassi_qi_displacement = displacement;
            context_params.cassi_qi_substitute = substitute;
            context_params.cassi_qi_modulate = modulate;
            context_params.cassi_qi_modulate_gain = modulate_gain;
            // mid-trunk injection is the rung-2 additive mode and requires displacement 0;
            // a suppressed state write runs the field at the layer without it, and the
            // modulation seam reads that same write, so it also runs without the injection
            intervention_used = intervention_override >= 0
                ? intervention_override
                : ((displacement >= 3 || substitute > 0.0f || modulate) ? 0 : 1);
            context_params.cassi_qi_intervention = intervention_used;
            context_params.cassi_qi_field_wave_modes = wave_modes;
            context_params.cassi_qi_field_fill_modes = fill_modes;
            context_params.cassi_qi_field_memory_fill = memory_fill;
            if (energy_floor > 0.0f) {
                context_params.cassi_qi_energy_floor = energy_floor;
            }
            if (read_floor > 0.0f) {
                context_params.cassi_qi_read_floor = read_floor;
            }
            if (read_absolute) {
                context_params.cassi_qi_read_absolute = true;
            }
            context_params.cassi_qi_field_row_width = row_width;
            context_params.cassi_qi_field_steps = steps;
            context_params.cassi_qi_injection_scale = alpha;
        }

        context_ptr context(llama_init_from_model(model.get(), context_params), llama_free);
        if (!context) {
            throw std::runtime_error("failed to create context");
        }
        if (capture_attention && !llama_cassi_capture_enable(context.get())) {
            throw std::runtime_error("failed to enable the Cassi attention capture");
        }

        size_t state_count = 0;
        std::vector<float> state_before;
        uint64_t state_before_hash = 0;
        int32_t graph_nodes = 0;
        if (qi_enabled) {
            graph_nodes = llama_cassi_qi_graph_nodes(context.get());
            if (graph_nodes <= 0) {
                throw std::runtime_error("Qi graph-node count is unavailable");
            }
            state_count = llama_cassi_qi_state_size(context.get());
            if (state_count == 0) {
                throw std::runtime_error("Qi state size is zero");
            }
            state_before = read_state_file(state_path, state_count);
            require_finite(state_before, "Qi state fixture");
            state_before_hash = fnv1a(state_before);
            if (!llama_cassi_qi_state_set(context.get(), 0, state_before.data(), state_before.size())) {
                throw std::runtime_error("failed to install exact Qi state fixture");
            }
        }

        for (uint32_t layer = field_layer; layer <= last_capture_layer; ++layer) {
            llama_set_embeddings_layer_inp(context.get(), layer, true);
        }

        const int64_t start_us = ggml_time_us();
        if (llama_decode(
                context.get(),
                llama_batch_get_one(prompt_tokens.data(), static_cast<int32_t>(prompt_tokens.size()))) != 0) {
            throw std::runtime_error("prompt decode failed");
        }

        const int32_t n_vocab = llama_vocab_n_tokens(vocab);
        if (n_vocab <= 0) {
            throw std::runtime_error("model vocabulary is empty");
        }
        const float * prompt_logits_ptr = llama_get_logits_ith(context.get(), -1);
        if (prompt_logits_ptr == nullptr) {
            throw std::runtime_error("prompt logits capture is null");
        }
        std::vector<float> prompt_logits(prompt_logits_ptr, prompt_logits_ptr + n_vocab);
        require_finite(prompt_logits, "prompt logits");

        // The prompt decode is a batch, so the last prompt token is the final row.
        std::vector<layer_capture> captures = capture_layers(
            context.get(), field_layer, last_capture_layer, n_embd, prompt_tokens.size() - 1);

        std::vector<std::pair<std::string, std::string>> output_files;
        std::vector<std::pair<std::string, std::string>> flux_output_files;
        if (output_dir.has_value()) {
            std::error_code error;
            std::filesystem::create_directories(*output_dir, error);
            if (error) {
                throw std::runtime_error("failed to create OUTPUT_DIR: " + output_dir->string() + ": " + error.message());
            }
            for (layer_capture & capture : captures) {
                const std::filesystem::path path = *output_dir / ("layer-" + std::to_string(capture.layer) + ".f32");
                write_f32_file(path, capture.values);
                capture.path = path.string();
                output_files.emplace_back("layer-" + std::to_string(capture.layer) + ".f32", capture.path);
            }
            const std::filesystem::path logits_path = *output_dir / "logits.f32";
            write_f32_file(logits_path, prompt_logits);
            output_files.emplace_back("logits.f32", logits_path.string());
        }

        // the prompt pass is the only pass with more than one token, so its attention dump
        // shows the full grid; the decode dump below is the single-token row the seam reads
        attention_dump prompt_attention;
        attention_dump decode_attention;
        if (capture_attention && output_dir.has_value()) {
            dump_attention(
                context.get(), *output_dir, field_layer, last_capture_layer, "prompt", prompt_attention);
        }
        uint64_t prompt_state_before_shuffle_hash = 0;
        uint64_t prompt_state_after_shuffle_hash = 0;
        double phase_shuffle_l2_before = 0.0;
        double phase_shuffle_l2_after = 0.0;
        double phase_shuffle_relative_l2_error = 0.0;
        if (phase_shuffle_after_prompt) {
            if (!qi_enabled) {
                throw std::runtime_error("phase shuffle requires Qi");
            }
            std::vector<float> prompt_state(state_count);
            if (!llama_cassi_qi_state_get(context.get(), 0, prompt_state.data(), prompt_state.size())) {
                throw std::runtime_error("failed to retrieve prompt Qi state for phase shuffle");
            }
            require_finite(prompt_state, "prompt Qi state");
            prompt_state_before_shuffle_hash = fnv1a(prompt_state);
            phase_shuffle_l2_before = l2_norm(prompt_state, "prompt Qi state");
            phase_shuffle(prompt_state);
            require_finite(prompt_state, "phase-shuffled Qi state");
            prompt_state_after_shuffle_hash = fnv1a(prompt_state);
            phase_shuffle_l2_after = l2_norm(prompt_state, "phase-shuffled Qi state");
            phase_shuffle_relative_l2_error = std::abs(phase_shuffle_l2_after - phase_shuffle_l2_before) /
                std::max(phase_shuffle_l2_before, std::numeric_limits<double>::min());
            if (prompt_state_before_shuffle_hash == prompt_state_after_shuffle_hash ||
                    phase_shuffle_relative_l2_error > 1.0e-12) {
                throw std::runtime_error("phase shuffle did not preserve a distinct matched-norm state");
            }
            if (!llama_cassi_qi_state_set(context.get(), 0, prompt_state.data(), prompt_state.size())) {
                throw std::runtime_error("failed to install phase-shuffled Qi state");
            }
        }

        std::vector<llama_token> generation_tokens;
        generation_tokens.reserve(generate_tokens);
        std::string generation_text;
        std::vector<std::pair<uint32_t, float>> schedule_applied;
        double schedule_budget = 0.0;
        uint32_t schedule_steps_max = 0;
        std::vector<layer_capture> early_decode_captures;
        std::vector<std::pair<std::string, std::string>> early_decode_output_files;
        std::vector<std::pair<std::string, std::string>> step_output_files;
        for (uint32_t i = 0; i < generate_tokens; ++i) {
            const llama_token next = greedy_token(llama_get_logits_ith(context.get(), -1), n_vocab);
            generation_tokens.push_back(next);
            generation_text += common_token_to_piece(vocab, next, true);
            if (llama_vocab_is_eog(vocab, next)) {
                break;
            }
            llama_token mutable_token = next;
            if (!schedule.empty()) {
                if (i >= schedule.size()) {
                    throw std::runtime_error(
                        "schedule ended before generation did at token " + std::to_string(i));
                }
                const std::pair<uint32_t, float> & entry = schedule[i];
                if (!llama_cassi_qi_coupling_set(context.get(), entry.first, entry.second)) {
                    throw std::runtime_error(
                        "failed to apply scheduled Qi coupling at token " + std::to_string(i));
                }
                schedule_applied.push_back(entry);
                schedule_budget += static_cast<double>(entry.first) *
                    static_cast<double>(entry.second);
                schedule_steps_max = std::max(schedule_steps_max, entry.first);
            }
            if (qi_enabled && reset_each_generated_token &&
                    !llama_cassi_qi_state_set(context.get(), 0, state_before.data(), state_before.size())) {
                throw std::runtime_error("failed to reset Qi state before generated-token decode");
            }
            if (llama_decode(context.get(), llama_batch_get_one(&mutable_token, 1)) != 0) {
                throw std::runtime_error("generation decode failed at token " + std::to_string(i));
            }
            if (output_dir.has_value()) {
                // Per-decode logits are the pass where the seam acts, so they show what a
                // token flip cannot: how far the output distribution moves.
                const float * step_logits = llama_get_logits_ith(context.get(), -1);
                const int32_t step_vocab = llama_vocab_n_tokens(vocab);
                if (step_logits != nullptr && step_vocab > 0) {
                    std::vector<float> row(step_logits, step_logits + step_vocab);
                    const std::filesystem::path path =
                        *output_dir / ("decode-logits-" + std::to_string(i) + ".f32");
                    write_f32_file(path, row);
                    output_files.emplace_back(path.filename().string(), path.string());
                }
            }
            if (capture_steps && output_dir.has_value()) {
                // one capture per decode pass, so each state carries the token generated from it
                std::vector<layer_capture> step_captures = capture_layers(
                    context.get(), field_layer, last_capture_layer, n_embd, 0);
                for (layer_capture & capture : step_captures) {
                    const std::filesystem::path path = *output_dir / ("layer-" +
                        std::to_string(capture.layer) + "-step-" + std::to_string(i) + ".f32");
                    write_f32_file(path, capture.values);
                    capture.path = path.string();
                    step_output_files.emplace_back(path.filename().string(), capture.path);
                }
            }
            if (qi_enabled && flux_dump && output_dir.has_value()) {
                const int64_t flux_size = llama_cassi_qi_flux_size(context.get());
                const float * flux_data = llama_cassi_qi_flux_data(context.get());
                if (flux_size > 0 && flux_data != nullptr) {
                    std::vector<float> flux(flux_data, flux_data + flux_size);
                    require_finite(flux, "Qi flux");
                    const std::filesystem::path path =
                        *output_dir / ("qi-flux-" + std::to_string(i) + ".f32");
                    write_f32_file(path, flux);
                    flux_output_files.emplace_back(path.filename().string(), path.string());
                }
            }
            // Decode 0 reads the state the prefill wrote, so decode 1 is the first
            // pass that reads the seam's write with the same tokens in every arm.
            if (qi_enabled && i == 1) {
                early_decode_captures = capture_layers(context.get(), field_layer, last_capture_layer, n_embd, 0);
                if (output_dir.has_value()) {
                    for (layer_capture & capture : early_decode_captures) {
                        const std::filesystem::path path =
                            *output_dir / ("layer-" + std::to_string(capture.layer) + "-decode-early.f32");
                        write_f32_file(path, capture.values);
                        capture.path = path.string();
                        early_decode_output_files.emplace_back(
                            "layer-" + std::to_string(capture.layer) + "-decode-early.f32", capture.path);
                    }
                }
            }
        }

        // the prompt decode is a batch and the substitution seam acts on single-token
        // decodes, so the prompt captures cannot see it; capture the last decode here,
        // before any later graph pass can overwrite the embedding buffers
        if (capture_attention && output_dir.has_value() && !generation_tokens.empty()) {
            dump_attention(
                context.get(), *output_dir, field_layer, last_capture_layer, "decode", decode_attention);
        }
        std::vector<layer_capture> decode_captures;
        std::vector<std::pair<std::string, std::string>> decode_output_files;
        if (qi_enabled && !generation_tokens.empty()) {
            decode_captures = capture_layers(context.get(), field_layer, last_capture_layer, n_embd, 0);
            if (output_dir.has_value()) {
                for (layer_capture & capture : decode_captures) {
                    const std::filesystem::path path =
                        *output_dir / ("layer-" + std::to_string(capture.layer) + "-decode.f32");
                    write_f32_file(path, capture.values);
                    capture.path = path.string();
                    decode_output_files.emplace_back(
                        "layer-" + std::to_string(capture.layer) + "-decode.f32", capture.path);
                }
            }
        }

        std::vector<float> generation_scores;
        if (qi_enabled) {
            generation_scores.assign(generation_tokens.size(), 0.0f);
            if (!generation_tokens.empty() && !llama_cassi_qi_score_tokens(
                    context.get(), 0, generation_tokens.data(),
                    generation_scores.data(), generation_tokens.size())) {
                throw std::runtime_error("failed to score generated tokens against the Qi field");
            }
            for (const float score : generation_scores) {
                if (!std::isfinite(score)) {
                    throw std::runtime_error("generated-token field score is non-finite");
                }
            }
        }

        std::vector<llama_token> decoded_tokens = prompt_tokens;
        decoded_tokens.insert(decoded_tokens.end(), generation_tokens.begin(), generation_tokens.end());
        const std::string prompt_decoded_text = common_detokenize(vocab, prompt_tokens, true);
        const std::string decoded_text = common_detokenize(vocab, decoded_tokens, true);

        std::vector<float> state_after;
        uint64_t state_after_hash = 0;
        double state_max_abs_delta = 0.0;
        if (qi_enabled) {
            state_after.resize(state_count);
            if (!llama_cassi_qi_state_get(context.get(), 0, state_after.data(), state_after.size())) {
                throw std::runtime_error("failed to retrieve final Qi state");
            }
            require_finite(state_after, "final Qi state");
            state_after_hash = fnv1a(state_after);
            for (size_t i = 0; i < state_after.size(); ++i) {
                state_max_abs_delta = std::max(
                    state_max_abs_delta,
                    std::abs(static_cast<double>(state_after[i]) - static_cast<double>(state_before[i])));
            }
            if (!std::isfinite(state_max_abs_delta)) {
                throw std::runtime_error("Qi state maximum delta is non-finite");
            }
        }
        if (qi_enabled && output_dir.has_value()) {
            const std::filesystem::path state_path = *output_dir / "state-after.f32";
            write_f32_file(state_path, state_after);
            output_files.emplace_back("state-after.f32", state_path.string());
        }
        std::string flux_json;
        if (!flux_output_files.empty()) {
            flux_json = "\"qi_flux_size\":" + std::to_string(llama_cassi_qi_flux_size(context.get())) +
                ",\"qi_flux_files\":[";
            for (size_t f = 0; f < flux_output_files.size(); ++f) {
                flux_json += (f == 0 ? "" : ",") + std::string("\"") + flux_output_files[f].first + "\"";
            }
            flux_json += "],";
        }
        const double elapsed_ms = static_cast<double>(ggml_time_us() - start_us) / 1000.0;
        if (!std::isfinite(elapsed_ms)) {
            throw std::runtime_error("elapsed time is non-finite");
        }
        const double coupling_budget = schedule.empty()
            ? static_cast<double>(steps) * static_cast<double>(alpha) *
                static_cast<double>(generation_tokens.size())
            : schedule_budget;
        if (!std::isfinite(coupling_budget)) {
            throw std::runtime_error("coupling budget is non-finite");
        }
        const int32_t graph_nodes_after_coupling =
            qi_enabled ? llama_cassi_qi_graph_nodes(context.get()) : -1;
        const int64_t state_field_width_after =
            qi_enabled ? llama_cassi_qi_state_field_width(context.get()) : 0;
        const int64_t state_row_width_after =
            qi_enabled ? llama_cassi_qi_state_row_width(context.get()) : 0;

        std::cout << "{\"schema\":\"cassi.qi.latent.v1\","
                  << "\"verdict\":\"PASS\","
                  << "\"backend\":\"" << json_escape(backend_name) << "\","
                  << "\"layer\":" << field_layer_arg << ','
                  << "\"steps\":" << steps << ','
                  << "\"alpha\":";
        print_double(alpha);
        std::cout << ",\"qi_enabled\":" << (qi_enabled ? "true" : "false") << ','
                  << "\"reset_each_generated_token\":"
                  << (reset_each_generated_token ? "true" : "false") << ','
                  << "\"phase_shuffle_after_prompt\":"
                  << (phase_shuffle_after_prompt ? "true" : "false") << ','
                  << "\"prompt_state_before_shuffle_fnv1a\":" << prompt_state_before_shuffle_hash << ','
                  << "\"prompt_state_after_shuffle_fnv1a\":" << prompt_state_after_shuffle_hash << ','
                  << "\"phase_shuffle_l2_before\":";
        print_double(phase_shuffle_l2_before);
        std::cout << ",\"phase_shuffle_l2_after\":";
        print_double(phase_shuffle_l2_after);
        std::cout << ",\"phase_shuffle_relative_l2_error\":";
        print_double(phase_shuffle_relative_l2_error);
        std::cout << ','
                  << "\"displacement\":" << displacement << ','
                  << "\"substitute\":";
        print_double(static_cast<double>(substitute));
        std::cout << ','
                  << "\"intervention\":" << (qi_enabled ? std::to_string(intervention_used) : "null") << ','
                  << flux_json
                  << "\"intervention_override\":" << intervention_override << ','
                  << "\"state_field_width\":" << state_field_width_after << ','
                  << "\"state_row_width\":" << state_row_width_after << ','
                  << "\"wave_modes\":" << wave_modes << ','
                  << "\"qi_fill_modes\":" << (fill_modes ? "true" : "false") << ','
                  << "\"qi_memory_fill\":" << (memory_fill ? "true" : "false") << ','
                  << "\"qi_energy_floor\":" << energy_floor << ','
                  << "\"qi_read_floor\":" << read_floor << ','
                  << "\"qi_read_absolute\":" << (read_absolute ? "true" : "false") << ','
                  << "\"qi_modulate\":" << (modulate ? "true" : "false") << ','
                  << "\"qi_modulate_gain\":";
        print_double(static_cast<double>(modulate_gain));
        std::cout << ','
                  << "\"modulate_budget\":";
        print_double(static_cast<double>(llama_cassi_qi_seam_budget(context.get())));
        std::cout << ",\"modulate_scale\":";
        print_double(static_cast<double>(llama_cassi_qi_seam_scale(context.get())));
        std::cout << ','
                  << "\"row_width_requested\":" << row_width << ','
                  << "\"capture_steps\":" << (capture_steps ? "true" : "false") << ','
                  << "\"head_input_captured\":" << (decode_attention.head_path.empty() ? "false" : "true") << ','
                  << "\"head_input_shape\":" << shape_json(decode_attention.head_shape, 3) << ','
                  << "\"attention_prompt\":" << attention_dump_json(prompt_attention) << ','
                  << "\"attention_decode\":" << attention_dump_json(decode_attention) << ','
                  << "\"prompt_token_ids\":";
        print_token_array(prompt_tokens);
        std::cout << ",\"generation_token_ids\":";
        print_token_array(generation_tokens);
        std::cout << ",\"generated_token_scores\":[";
        for (size_t index = 0; index < generation_scores.size(); ++index) {
            if (index != 0) {
                std::cout << ',';
            }
            print_double(static_cast<double>(generation_scores[index]));
        }
        std::cout << ']';
        std::cout << ",\"prompt_text\":\"" << json_escape(prompt_text) << "\","
                  << "\"prompt_decoded_text\":\"" << json_escape(prompt_decoded_text) << "\","
                  << "\"generation_text\":\"" << json_escape(generation_text) << "\","
                  << "\"decoded_text\":\"" << json_escape(decoded_text) << "\","
                  << "\"state_floats\":" << state_count << ','
                  << "\"state_before_fnv1a\":" << state_before_hash << ','
                  << "\"state_after_fnv1a\":" << state_after_hash << ','
                  << "\"state_max_abs_delta\":";
        print_double(state_max_abs_delta);
        std::cout << ",\"graph_nodes\":" << graph_nodes << ','
                  << "\"graph_nodes_after_coupling\":" << graph_nodes_after_coupling << ','
                  << "\"schedule_path\":";
        if (schedule_path.has_value()) {
            std::cout << '"' << json_escape(schedule_path->string()) << '"';
        } else {
            std::cout << "null";
        }
        std::cout << ",\"schedule_fnv1a\":" << (schedule.empty() ? 0ull : fnv1a_bytes(schedule_text))
                  << ",\"schedule_entries\":" << schedule.size()
                  << ",\"schedule_applied_entries\":" << schedule_applied.size()
                  << ",\"schedule_steps_max\":" << schedule_steps_max
                  << ",\"coupling_budget\":";
        print_double(coupling_budget);
        std::cout << ",\"schedule_applied\":[";
        {
            const size_t listed = std::min<size_t>(schedule_applied.size(), 64);
            for (size_t index = 0; index < listed; ++index) {
                if (index != 0) {
                    std::cout << ',';
                }
                std::cout << '[' << schedule_applied[index].first << ',';
                print_double(static_cast<double>(schedule_applied[index].second));
                std::cout << ']';
            }
            if (listed != schedule_applied.size()) {
                std::cout << ",\"truncated\":" << (schedule_applied.size() - listed);
            }
        }
        std::cout << ']'
                  << ",\"elapsed_ms\":";
        print_double(elapsed_ms);
        const auto emit_captures = [](const std::vector<layer_capture> & list, bool with_difference) {
            std::cout << '[';
            for (size_t i = 0; i < list.size(); ++i) {
                if (i != 0) {
                    std::cout << ',';
                }
                const layer_capture & capture = list[i];
                std::cout << "{\"layer\":" << capture.layer << ",\"l2_norm\":";
                print_double(capture.l2_norm);
                if (with_difference) {
                    std::cout << ",\"difference_norm\":";
                    if (capture.has_difference) {
                        print_double(capture.difference_norm);
                    } else {
                        std::cout << "null";
                    }
                }
                std::cout << ",\"finite\":" << (capture.finite ? "true" : "false");
                if (capture.path.empty()) {
                    std::cout << ",\"path\":null";
                } else {
                    std::cout << ",\"path\":\"" << json_escape(capture.path) << "\"";
                }
                std::cout << '}';
            }
            std::cout << ']';
        };
        std::cout << ",\"captured_layers\":";
        emit_captures(captures, true);
        std::cout << ",\"decode_captured_layers\":";
        emit_captures(decode_captures, false);
        std::cout << ",\"early_decode_captured_layers\":";
        emit_captures(early_decode_captures, false);
        std::cout << ",\"early_decode_capture_files\":[";
        for (size_t i = 0; i < early_decode_output_files.size(); ++i) {
            if (i != 0) {
                std::cout << ',';
            }
            std::cout << "{\"name\":\"" << json_escape(early_decode_output_files[i].first)
                      << "\",\"path\":\"" << json_escape(early_decode_output_files[i].second) << "\"}";
        }
        std::cout << ']';
        std::cout << ",\"decode_capture_files\":[";
        for (size_t i = 0; i < decode_output_files.size(); ++i) {
            if (i != 0) {
                std::cout << ',';
            }
            std::cout << "{\"name\":\"" << json_escape(decode_output_files[i].first)
                      << "\",\"path\":\"" << json_escape(decode_output_files[i].second) << "\"}";
        }
        std::cout << "],\"step_capture_files\":[";
        for (size_t i = 0; i < step_output_files.size(); ++i) {
            if (i != 0) {
                std::cout << ',';
            }
            std::cout << "{\"name\":\"" << json_escape(step_output_files[i].first)
                      << "\",\"path\":\"" << json_escape(step_output_files[i].second) << "\"}";
        }
        std::cout << "],\"capture_output_dir\":";
        if (output_dir.has_value()) {
            std::cout << "\"" << json_escape(output_dir->string()) << "\"";
        } else {
            std::cout << "null";
        }
        std::cout << ",\"capture_files\":[";
        for (size_t i = 0; i < output_files.size(); ++i) {
            if (i != 0) {
                std::cout << ',';
            }
            std::cout << "{\"name\":\"" << json_escape(output_files[i].first)
                      << "\",\"path\":\"" << json_escape(output_files[i].second) << "\"}";
        }
        std::cout << "]}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
