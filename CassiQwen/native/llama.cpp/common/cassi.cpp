#include "cassi.h"
#include "common.h"

#include "ggml-backend.h"

extern "C" {
#include "hash/sha256/sha256.h"
}

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <system_error>
#include <utility>

#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
#  include <io.h>
#else
#  include <fcntl.h>
#  include <sys/file.h>
#  include <sys/stat.h>
#  include <sys/types.h>
#  include <unistd.h>
#endif

namespace {

using clock_type = std::chrono::steady_clock;
using session_ptr = std::unique_ptr<llama_cassi_context, decltype(&llama_cassi_free)>;

std::string hex_digest(const uint8_t * data, size_t size) {
    std::ostringstream stream;
    stream << std::hex << std::setfill('0');
    for (size_t index = 0; index < size; ++index) {
        stream << std::setw(2) << static_cast<unsigned int>(data[index]);
    }
    return stream.str();
}

std::filesystem::path normalized_path(const std::filesystem::path & path) {
    std::error_code error;
    std::filesystem::path absolute = std::filesystem::absolute(path, error);
    if (error) {
        absolute = path;
    }
    return absolute.lexically_normal();
}

std::string comparable_path(const std::filesystem::path & path) {
    std::string value = normalized_path(path).generic_u8string();
#ifdef _WIN32
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
#endif
    return value;
}

bool paths_alias(const std::filesystem::path & left, const std::filesystem::path & right) {
    if (left.empty() || right.empty()) {
        return false;
    }
    std::error_code left_error;
    std::error_code right_error;
    const bool left_exists = std::filesystem::exists(left, left_error) && !left_error;
    const bool right_exists = std::filesystem::exists(right, right_error) && !right_error;
    if (left_exists && right_exists) {
        std::error_code equivalent_error;
        if (std::filesystem::equivalent(left, right, equivalent_error) && !equivalent_error) {
            return true;
        }
    }
    return comparable_path(left) == comparable_path(right);
}

bool parent_exists(const std::filesystem::path & path) {
    std::filesystem::path parent = normalized_path(path).parent_path();
    if (parent.empty()) {
        parent = std::filesystem::current_path();
    }
    std::error_code error;
    return std::filesystem::is_directory(parent, error) && !error;
}

bool read_exact_file(const std::filesystem::path & path, size_t expected, std::vector<uint8_t> & bytes) {
    std::error_code error;
    const uintmax_t size = std::filesystem::file_size(path, error);
    if (error || size != expected) {
        return false;
    }
    bytes.resize(expected);
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        return false;
    }
    if (expected != 0) {
        stream.read(reinterpret_cast<char *>(bytes.data()), static_cast<std::streamsize>(expected));
    }
    return stream.good() || (stream.eof() && static_cast<size_t>(stream.gcount()) == expected);
}

std::array<uint8_t, 32> image_digest(const std::vector<uint8_t> & image) {
    std::array<uint8_t, 32> digest = {};
    if (image.size() < digest.size()) {
        return digest;
    }
    sha256_t sha;
    sha256_init(&sha);
    sha256_update(&sha, image.data(), image.size() - digest.size());
    sha256_final(&sha, digest.data());
    return digest;
}

bool verify_checkpoint_file(
        const std::filesystem::path & path,
        size_t expected_size,
        const std::array<uint8_t, 32> & expected_digest) {
    std::error_code size_error;
    if (std::filesystem::file_size(path, size_error) != expected_size || size_error || expected_size < 32) {
        return false;
    }
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        return false;
    }
    sha256_t sha;
    sha256_init(&sha);
    std::array<unsigned char, 1 << 16> buffer = {};
    size_t remaining = expected_size - 32;
    while (remaining != 0) {
        const size_t chunk = std::min(remaining, buffer.size());
        stream.read(reinterpret_cast<char *>(buffer.data()), static_cast<std::streamsize>(chunk));
        if (static_cast<size_t>(stream.gcount()) != chunk) {
            return false;
        }
        sha256_update(&sha, buffer.data(), chunk);
        remaining -= chunk;
    }
    std::array<uint8_t, 32> stored = {};
    stream.read(reinterpret_cast<char *>(stored.data()), static_cast<std::streamsize>(stored.size()));
    if (static_cast<size_t>(stream.gcount()) != stored.size()) {
        return false;
    }
    std::array<uint8_t, 32> computed = {};
    sha256_final(&sha, computed.data());
    return stored == computed && stored == expected_digest;
}

const char * teacher_policy_name(llama_cassi_teacher_policy policy) {
    switch (policy) {
        case LLAMA_CASSI_ADAPTIVE: return "adaptive";
        case LLAMA_CASSI_ALWAYS: return "always";
        case LLAMA_CASSI_NEVER: return "never";
    }
    return "invalid";
}

const char * route_policy_name(llama_cassi_route_policy policy) {
    switch (policy) {
        case LLAMA_CASSI_AUTO: return "auto";
        case LLAMA_CASSI_PIPELINE: return "pipeline";
    }
    return "invalid";
}

nlohmann::ordered_json stats_json(const llama_cassi_stats & value) {
    return {
        {"prompt_tokens", value.prompt_tokens},
        {"committed_tokens", value.committed_tokens},
        {"field_exact_tokens", value.field_exact_tokens},
        {"field_interpolated_tokens", value.field_interpolated_tokens},
        {"teacher_guided_tokens", value.teacher_guided_tokens},
        {"native_service_calls", value.native_service_calls},
        {"full_teacher_queries", value.full_teacher_queries},
        {"teacher_failures", value.teacher_failures},
        {"teacher_audits", value.teacher_audits},
        {"audit_mismatches", value.audit_mismatches},
        {"native_prefill_tokens", value.native_prefill_tokens},
        {"native_context_creations", value.native_context_creations},
        {"native_logits_reads", value.native_logits_reads},
        {"native_replay_tokens", value.native_replay_tokens},
        {"native_decode_tokens", value.native_decode_tokens},
        {"field_observations", value.field_observations},
        {"pending_admission_payload_bytes_peak", value.pending_admission_payload_bytes_peak},
        {"pending_rollback_bytes_peak", value.pending_rollback_bytes_peak},
        {"native_ggml_nodes_executed", value.native_ggml_nodes_executed},
        {"native_ggml_nodes_skipped", value.native_nodes_skipped_known ? nlohmann::ordered_json(value.native_ggml_nodes_skipped) : nlohmann::ordered_json(nullptr)},
        {"native_output_rows_computed", value.native_output_rows_computed},
        {"native_output_rows_skipped", value.native_output_rows_skipped},
        {"logical_weight_bytes", value.logical_weight_bytes},
        {"field_steps", value.field_steps},
        {"engram_evictions", value.engram_evictions},
        {"field_bytes", value.field_bytes},
        {"loaded_model_tensor_bytes", value.loaded_model_tensor_bytes},
        {"native_cache_bytes_peak", value.native_cache_bytes_peak},
        {"native_cache_bytes_remaining", value.native_cache_bytes_remaining},
        {"native_nodes_skipped_known", value.native_nodes_skipped_known},
        {"field_ms", value.field_ms},
        {"native_service_ms", value.native_service_ms},
        {"teacher_ms", value.teacher_ms},
        {"replay_ms", value.replay_ms},
        {"checkpoint_ms", value.checkpoint_ms},
        {"wall_ms", value.wall_ms},
    };
}

#ifdef _WIN32
bool write_all(HANDLE handle, const uint8_t * data, size_t size) {
    while (size != 0) {
        const DWORD chunk = static_cast<DWORD>(std::min<size_t>(size, std::numeric_limits<DWORD>::max()));
        DWORD written = 0;
        if (!WriteFile(handle, data, chunk, &written, nullptr) || written != chunk) {
            return false;
        }
        data += chunk;
        size -= chunk;
    }
    return true;
}
#else
bool write_all(int descriptor, const uint8_t * data, size_t size) {
    while (size != 0) {
        const ssize_t written = ::write(descriptor, data, size);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }
        data += static_cast<size_t>(written);
        size -= static_cast<size_t>(written);
    }
    return true;
}
#endif

} // namespace

void common_cassi_prepare_defaults(common_params & params) {
    params.cassi_modal = false;
    params.cassi_field_step = false;
    params.cassi_qi_field = false;
    params.sampling.seed = LLAMA_DEFAULT_SEED;
    params.sampling.n_probs = 0;
    params.sampling.top_k = 0;
    params.sampling.top_p = 1.0f;
    params.sampling.min_p = 0.0f;
    params.sampling.xtc_probability = 0.0f;
    params.sampling.typ_p = 1.0f;
    params.sampling.temp = 0.0f;
    params.sampling.dynatemp_range = 0.0f;
    params.sampling.penalty_repeat = 1.0f;
    params.sampling.penalty_freq = 0.0f;
    params.sampling.penalty_present = 0.0f;
    params.sampling.dry_multiplier = 0.0f;
    params.sampling.adaptive_target = -1.0f;
    params.sampling.mirostat = 0;
    params.sampling.top_n_sigma = -1.0f;
    params.sampling.ignore_eos = false;
    params.sampling.backend_sampling = false;
    params.sampling.samplers.clear();
    params.sampling.grammar = {};
    params.sampling.grammar_lazy = false;
    params.sampling.grammar_triggers.clear();
    params.sampling.logit_bias.clear();
    params.n_parallel = 1;
    params.n_sequences = 1;
    if (params.n_ctx == 0) {
        params.n_ctx = 4096;
    }
    params.n_batch = 1;
    params.n_ubatch = 1;
    params.n_outputs_max = 1;
    params.n_outputs_max_per_seq = 1;
    params.ctx_shift = false;
    params.cache_prompt = false;
    params.cache_idle_slots = false;
    params.fit_params = false;
    params.sleep_idle_seconds = -1;
    params.path_prompt_cache.clear();
    params.prompt_cache_all = false;
    params.prompt_cache_ro = false;
    params.warmup = false;
    params.speculative.types = { COMMON_SPECULATIVE_TYPE_NONE };
}

void common_cassi_validate_params(const common_params & params) {
    if (!params.cassi_apprentice) {
        return;
    }
    const auto conflict = []() {
        throw std::invalid_argument("apprentice_configuration_conflict");
    };
    if (params.cassi_apprentice_state.empty() ||
            params.cassi_apprentice_memory_mib == 0 ||
            params.cassi_apprentice_memory_mib > std::numeric_limits<uint64_t>::max() / (1024ULL * 1024ULL) ||
            (params.cassi_apprentice_device != "CPU" && params.cassi_apprentice_device != "Vulkan0") ||
            (params.cassi_apprentice_teacher != LLAMA_CASSI_ADAPTIVE &&
             params.cassi_apprentice_teacher != LLAMA_CASSI_ALWAYS &&
             params.cassi_apprentice_teacher != LLAMA_CASSI_NEVER) ||
            (params.cassi_apprentice_route != LLAMA_CASSI_AUTO &&
             params.cassi_apprentice_route != LLAMA_CASSI_PIPELINE)) {
        conflict();
    }
    if (params.cassi_apprentice_init && params.cassi_apprentice_teacher == LLAMA_CASSI_NEVER) {
        conflict();
    }
    const auto & sampling = params.sampling;
    if (params.cassi_modal || params.cassi_field_step || params.cassi_qi_field ||
            sampling.seed != LLAMA_DEFAULT_SEED || sampling.n_probs != 0 ||
            sampling.top_k != 0 || sampling.top_p != 1.0f || sampling.min_p != 0.0f ||
            sampling.xtc_probability != 0.0f || sampling.typ_p != 1.0f ||
            sampling.temp != 0.0f || sampling.dynatemp_range != 0.0f ||
            sampling.penalty_repeat != 1.0f || sampling.penalty_freq != 0.0f ||
            sampling.penalty_present != 0.0f || sampling.dry_multiplier != 0.0f ||
            sampling.adaptive_target >= 0.0f || sampling.mirostat != 0 ||
            sampling.top_n_sigma >= 0.0f || sampling.ignore_eos ||
            sampling.backend_sampling || !sampling.samplers.empty() ||
            !sampling.grammar.empty() || sampling.grammar_lazy ||
            !sampling.grammar_triggers.empty() || !sampling.logit_bias.empty() ||
            !sampling.preserved_tokens.empty() || !sampling.generation_prompt.empty()) {
        conflict();
    }
    if (params.n_parallel != 1 || params.n_sequences != 1 ||
            params.ctx_shift || params.cache_prompt || params.cache_idle_slots ||
            params.fit_params || params.sleep_idle_seconds >= 0 ||
            !params.path_prompt_cache.empty() || params.prompt_cache_all || params.prompt_cache_ro ||
            params.embedding || params.no_perf || params.sampling.no_perf ||
            params.speculative.types != std::vector<common_speculative_type>{ COMMON_SPECULATIVE_TYPE_NONE } ||
            params.speculative.has_dft() ||
            !params.speculative.ngram_cache.lookup_cache_static.empty() ||
            !params.speculative.ngram_cache.lookup_cache_dynamic.empty() ||
            params.lora_init_without_apply || !params.lora_adapters.empty() ||
            !params.control_vectors.empty() || !params.mmproj.empty() || !params.image.empty() ||
            !params.server_base.empty() || params.hostname != "127.0.0.1") {
        conflict();
    }
    if (!params.model.path.empty()) {
        const std::filesystem::path state(params.cassi_apprentice_state);
        const std::filesystem::path model(params.model.path);
        for (const auto & path : {
                 state,
                 std::filesystem::path(state.string() + ".previous"),
                 std::filesystem::path(state.string() + ".lock"),
                 std::filesystem::path(params.cassi_apprentice_receipt) }) {
            if (!path.empty() && paths_alias(path, model)) {
                throw std::invalid_argument("apprentice_model_path_alias");
            }
        }
    }
}

struct common_cassi_owner::impl {
    std::filesystem::path state_path;
    std::filesystem::path receipt_path;
    std::filesystem::path previous_path;
    std::filesystem::path lock_path;
    bool initialize = false;
    bool read_only = false;
    bool has_published = false;
    bool write_failure = false;
    std::string error_code;
    std::string field_device;
    llama_cassi_teacher_policy teacher_policy = LLAMA_CASSI_ADAPTIVE;
    llama_cassi_route_policy route_policy = LLAMA_CASSI_AUTO;
    session_ptr session{nullptr, llama_cassi_free};
    uint64_t last_published_revision = 0;
    std::array<uint8_t, 32> checkpoint_hash = {};
    double checkpoint_ms = 0.0;
#ifdef _WIN32
    HANDLE lock_handle = INVALID_HANDLE_VALUE;
#else
    int lock_descriptor = -1;
#endif

    impl(const std::string & state, bool init, bool readonly, const std::string & receipt) :
            state_path(state), receipt_path(receipt), previous_path(state + ".previous"),
            lock_path(state + ".lock"), initialize(init), read_only(readonly) {
        if (state.empty()) {
            throw std::runtime_error("apprentice_state_path_required");
        }
        if (initialize && read_only) {
            throw std::runtime_error("apprentice_configuration_conflict");
        }
        if (!parent_exists(state_path) || (!receipt_path.empty() && !parent_exists(receipt_path))) {
            throw std::runtime_error("apprentice_checkpoint_parent_missing");
        }
        const std::array<std::filesystem::path, 4> paths = {
            state_path, previous_path, lock_path, receipt_path,
        };
        for (size_t left = 0; left < paths.size(); ++left) {
            if (paths[left].empty()) {
                continue;
            }
            for (size_t right = left + 1; right < paths.size(); ++right) {
                if (!paths[right].empty() && paths_alias(paths[left], paths[right])) {
                    throw std::runtime_error("apprentice_path_alias");
                }
            }
        }
        if (!read_only) {
#ifdef _WIN32
            lock_handle = CreateFileW(
                lock_path.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS,
                FILE_ATTRIBUTE_NORMAL, nullptr);
            if (lock_handle == INVALID_HANDLE_VALUE) {
                throw std::runtime_error("apprentice_checkpoint_locked");
            }
#else
            lock_descriptor = ::open(lock_path.c_str(), O_CREAT | O_RDWR, 0600);
            if (lock_descriptor < 0 || flock(lock_descriptor, LOCK_EX | LOCK_NB) != 0) {
                if (lock_descriptor >= 0) {
                    ::close(lock_descriptor);
                    lock_descriptor = -1;
                }
                throw std::runtime_error("apprentice_checkpoint_locked");
            }
#endif
        }
    }

    ~impl() {
        session.reset();
#ifdef _WIN32
        if (lock_handle != INVALID_HANDLE_VALUE) {
            CloseHandle(lock_handle);
            lock_handle = INVALID_HANDLE_VALUE;
        }
#else
        if (lock_descriptor >= 0) {
            flock(lock_descriptor, LOCK_UN);
            ::close(lock_descriptor);
            lock_descriptor = -1;
        }
#endif
    }

    bool set_error(const char * code, bool latch = false) {
        error_code = code;
        if (latch) {
            write_failure = true;
        }
        return false;
    }

    bool fail_publication(const char * code) {
        if (session && llama_cassi_rollback_accepted(session.get()) != 0) {
            return set_error("apprentice_checkpoint_rollback_failed", true);
        }
        return set_error(code, true);
    }

    bool validate_model_aliases(const std::filesystem::path & model_path) {
        for (const auto & path : { state_path, previous_path, lock_path, receipt_path }) {
            if (!path.empty() && paths_alias(path, model_path)) {
                return set_error("apprentice_model_path_alias");
            }
        }
        return true;
    }

    bool preflight_receipt() {
        if (receipt_path.empty()) {
            return true;
        }
        std::ofstream stream(receipt_path, std::ios::binary | std::ios::app);
        if (!stream) {
            return set_error("apprentice_receipt_write_failed", true);
        }
        stream.flush();
        if (!stream) {
            return set_error("apprentice_receipt_write_failed", true);
        }
        return true;
    }

    bool load(llama_model * model, llama_context_params native_params, llama_cassi_params params) {
        error_code.clear();
        if (session || model == nullptr || params.model_path == nullptr || params.model_path[0] == '\0') {
            return set_error("apprentice_configuration_invalid");
        }
        if (!validate_model_aliases(params.model_path) || !preflight_receipt()) {
            return false;
        }
        field_device = params.field_device == nullptr ? std::string() : params.field_device;
        teacher_policy = params.teacher_policy;
        route_policy = params.route_policy;
        session.reset(llama_cassi_init(model, native_params, params));
        if (!session) {
            const char * error = llama_cassi_last_error(nullptr);
            return set_error(error == nullptr || error[0] == '\0' ? "apprentice_initialization_failed" : error);
        }
        const size_t state_size = llama_cassi_state_size(session.get());
        if (state_size == 0) {
            session.reset();
            return set_error("apprentice_checkpoint_invalid");
        }
        std::error_code exists_error;
        const bool state_exists = std::filesystem::exists(state_path, exists_error) && !exists_error;
        if (initialize && state_exists) {
            session.reset();
            return set_error("apprentice_checkpoint_exists");
        }
        if (!state_exists && !initialize) {
            session.reset();
            return set_error("apprentice_checkpoint_missing");
        }

        std::vector<uint8_t> zero_state;
        if (initialize && std::filesystem::exists(previous_path)) {
            zero_state.resize(state_size);
            if (llama_cassi_state_get(session.get(), zero_state.data(), zero_state.size()) != zero_state.size()) {
                session.reset();
                return set_error("apprentice_checkpoint_invalid");
            }
        }
        if (std::filesystem::exists(previous_path)) {
            std::vector<uint8_t> previous;
            if (!read_exact_file(previous_path, state_size, previous) ||
                    llama_cassi_state_set(session.get(), previous.data(), previous.size()) != 0) {
                session.reset();
                return set_error("apprentice_checkpoint_invalid");
            }
        }
        if (initialize) {
            if (!zero_state.empty() && llama_cassi_state_set(session.get(), zero_state.data(), zero_state.size()) != 0) {
                session.reset();
                return set_error("apprentice_checkpoint_invalid");
            }
            if (!publish(true)) {
                session.reset();
                return false;
            }
            return true;
        }

        std::vector<uint8_t> image;
        if (!read_exact_file(state_path, state_size, image) ||
                llama_cassi_state_set(session.get(), image.data(), image.size()) != 0) {
            session.reset();
            return set_error("apprentice_checkpoint_invalid");
        }
        llama_cassi_info info = {};
        if (llama_cassi_get_info(session.get(), &info) != 0) {
            session.reset();
            return set_error("apprentice_checkpoint_invalid");
        }
        last_published_revision = info.field_revision;
        checkpoint_hash = image_digest(image);
        has_published = true;
        return true;
    }

    bool create_temp_and_write(const std::vector<uint8_t> & image, std::filesystem::path & temp_path) {
        const std::string stem = state_path.filename().u8string() + ".tmp.";
        for (uint32_t attempt = 0; attempt < 64; ++attempt) {
#ifdef _WIN32
            const std::wstring candidate_name = (state_path.parent_path() /
                (stem + std::to_string(GetCurrentProcessId()) + "." +
                 std::to_string(GetTickCount64()) + "." + std::to_string(attempt))).wstring();
            HANDLE handle = CreateFileW(candidate_name.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW,
                FILE_ATTRIBUTE_NORMAL, nullptr);
            if (handle == INVALID_HANDLE_VALUE) {
                if (GetLastError() == ERROR_FILE_EXISTS) {
                    continue;
                }
                return false;
            }
            const bool written = write_all(handle, image.data(), image.size());
            const bool flushed = written && FlushFileBuffers(handle);
            const bool closed = CloseHandle(handle);
            temp_path = candidate_name;
            if (!written || !flushed || !closed) {
                DeleteFileW(candidate_name.c_str());
                return false;
            }
#else
            temp_path = state_path.parent_path() /
                (stem + std::to_string(getpid()) + "." + std::to_string(attempt));
            const int descriptor = ::open(temp_path.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0600);
            if (descriptor < 0) {
                if (errno == EEXIST) {
                    continue;
                }
                return false;
            }
            const bool written = write_all(descriptor, image.data(), image.size());
            const bool flushed = written && fsync(descriptor) == 0;
            const bool closed = ::close(descriptor) == 0;
            if (!written || !flushed || !closed) {
                ::unlink(temp_path.c_str());
                return false;
            }
#endif
            return true;
        }
        return false;
    }

    bool replace_destination(const std::filesystem::path & temp_path, bool destination_exists) {
#ifdef _WIN32
        if (destination_exists) {
            std::error_code remove_error;
            if (std::filesystem::exists(previous_path) &&
                    (!std::filesystem::remove(previous_path, remove_error) || remove_error)) {
                return false;
            }
            return ReplaceFileW(
                state_path.c_str(), temp_path.c_str(), previous_path.c_str(),
                REPLACEFILE_WRITE_THROUGH, nullptr, nullptr) != 0;
        }
        return MoveFileExW(temp_path.c_str(), state_path.c_str(), MOVEFILE_WRITE_THROUGH) != 0;
#else
        if (destination_exists) {
            const std::filesystem::path previous_temp = previous_path.string() + ".new";
            ::unlink(previous_temp.c_str());
            if (::link(state_path.c_str(), previous_temp.c_str()) != 0 ||
                    ::rename(previous_temp.c_str(), previous_path.c_str()) != 0) {
                ::unlink(previous_temp.c_str());
                return false;
            }
        }
        if (::rename(temp_path.c_str(), state_path.c_str()) != 0) {
            return false;
        }
        const std::filesystem::path directory = state_path.parent_path().empty()
            ? std::filesystem::path(".") : state_path.parent_path();
        const int descriptor = ::open(directory.c_str(), O_RDONLY);
        if (descriptor < 0) {
            return false;
        }
        const bool durable = fsync(descriptor) == 0;
        ::close(descriptor);
        return durable;
#endif
    }

    bool publish(bool force = false) {
        if (!session) {
            return set_error("apprentice_not_initialized");
        }
        llama_cassi_info info = {};
        if (llama_cassi_get_info(session.get(), &info) != 0) {
            return fail_publication("apprentice_checkpoint_export_failed");
        }
        if (!force && !write_failure && has_published && info.field_revision == last_published_revision) {
            error_code.clear();
            return true;
        }
        if (read_only) {
            if (has_published && info.field_revision == last_published_revision) {
                error_code.clear();
                return true;
            }
            return fail_publication("apprentice_checkpoint_read_only");
        }

        const auto started = clock_type::now();
        const size_t state_size = llama_cassi_state_size(session.get());
        std::vector<uint8_t> image(state_size);
        if (state_size == 0 || llama_cassi_state_get(session.get(), image.data(), image.size()) != image.size()) {
            return fail_publication("apprentice_checkpoint_export_failed");
        }
        const std::array<uint8_t, 32> next_digest = image_digest(image);
        std::filesystem::path temp_path;
        if (!create_temp_and_write(image, temp_path)) {
            return fail_publication("apprentice_checkpoint_write_failed");
        }
        std::error_code exists_error;
        const bool destination_exists = std::filesystem::exists(state_path, exists_error) && !exists_error;
        if (!replace_destination(temp_path, destination_exists)) {
            std::error_code cleanup_error;
            std::filesystem::remove(temp_path, cleanup_error);
            return fail_publication("apprentice_checkpoint_write_failed");
        }
        if (!verify_checkpoint_file(state_path, image.size(), next_digest)) {
            return fail_publication("apprentice_checkpoint_verify_failed");
        }
        last_published_revision = info.field_revision;
        checkpoint_hash = next_digest;
        has_published = true;
        write_failure = false;
        error_code.clear();
        checkpoint_ms = std::chrono::duration<double, std::milli>(clock_type::now() - started).count();
        return true;
    }
};

common_cassi_owner::common_cassi_owner(
        const std::string & state_path,
        bool initialize,
        bool read_only,
        const std::string & receipt_path) :
    pimpl(std::make_unique<impl>(state_path, initialize, read_only, receipt_path)) {
}

common_cassi_owner::~common_cassi_owner() = default;

bool common_cassi_owner::load(
        llama_model * model,
        llama_context_params native_params,
        llama_cassi_params params) {
    return pimpl->load(model, native_params, params);
}

llama_cassi_context * common_cassi_owner::context() const {
    return pimpl->session.get();
}

bool common_cassi_owner::publish(bool force) {
    return pimpl->publish(force);
}

bool common_cassi_owner::write_failed() const {
    return pimpl->write_failure;
}

const std::string & common_cassi_owner::error() const {
    return pimpl->error_code;
}

nlohmann::ordered_json common_cassi_owner::receipt(
        const char * status,
        const char * error_code,
        const std::vector<llama_token> & emitted) const {
    nlohmann::ordered_json value = {
        {"schema", "cassi.apprentice.receipt.v1"},
        {"profile", "cassi.qi.apprentice-engram.v1"},
        {"model_sha256", nullptr},
        {"profile_sha256", nullptr},
        {"field_sha256", nullptr},
        {"checkpoint_sha256", pimpl->has_published ? nlohmann::ordered_json(hex_digest(pimpl->checkpoint_hash.data(), pimpl->checkpoint_hash.size())) : nlohmann::ordered_json(nullptr)},
        {"field_revision", nullptr},
        {"field_geometry", nullptr},
        {"field_device", pimpl->field_device.empty() ? nlohmann::ordered_json(nullptr) : nlohmann::ordered_json(pimpl->field_device)},
        {"native_backends", nullptr},
        {"teacher_policy", teacher_policy_name(pimpl->teacher_policy)},
        {"route_policy", route_policy_name(pimpl->route_policy)},
        {"execution_topology", "host_scheduled_ggml_field_and_native_services"},
        {"field_graph_outputs_live", true},
        {"single_qwen_graph_intervention", false},
        {"status", status == nullptr ? "error" : status},
        {"error_code", error_code == nullptr ? nlohmann::ordered_json(nullptr) : nlohmann::ordered_json(error_code)},
        {"durable", pimpl->has_published && !pimpl->write_failure},
        {"stats", nullptr},
        {"services", nullptr},
        {"tokens", emitted},
    };
    if (!pimpl->session) {
        return value;
    }
    llama_cassi_info info = {};
    llama_cassi_stats stats = {};
    llama_cassi_get_stats(pimpl->session.get(), &stats);
    stats.checkpoint_ms = pimpl->checkpoint_ms;
    if (llama_cassi_get_info(pimpl->session.get(), &info) != 0) {
        return value;
    }
    value["model_sha256"] = hex_digest(info.model_sha256, sizeof(info.model_sha256));
    value["profile_sha256"] = hex_digest(info.profile_sha256, sizeof(info.profile_sha256));
    value["field_sha256"] = hex_digest(info.field_sha256, sizeof(info.field_sha256));
    value["field_revision"] = info.field_revision;
    std::vector<std::string> native_backends;
    bool native_backends_known = true;
    const size_t backend_count = llama_cassi_native_backend_count(pimpl->session.get());
    for (size_t index = 0; index < backend_count; ++index) {
        const size_t length = llama_cassi_native_backend_name(
            pimpl->session.get(), index, nullptr, 0);
        std::vector<char> name(length + 1, '\0');
        if (length == 0 ||
                llama_cassi_native_backend_name(
                    pimpl->session.get(), index, name.data(), name.size()) != length) {
            native_backends_known = false;
            break;
        }
        native_backends.emplace_back(name.data(), length);
    }
    if (native_backends_known) {
        std::sort(native_backends.begin(), native_backends.end());
        value["native_backends"] = native_backends;
    } else {
        value["native_backends"] = nullptr;
    }
    value["field_geometry"] = {
        {"scales", info.scales},
        {"modes", info.modes},
        {"layers", info.layers},
        {"embedding_width", info.embedding_width},
        {"vocabulary_size", info.vocabulary_size},
        {"pages", llama_cassi_service_stats_count(pimpl->session.get())},
    };
    value["stats"] = stats_json(stats);
    const size_t service_count = llama_cassi_service_stats_count(pimpl->session.get());
    std::vector<llama_cassi_service_stats> services(service_count);
    if (service_count != 0 && llama_cassi_service_stats_get(
            pimpl->session.get(), services.data(), services.size()) != service_count) {
        value["services"] = nullptr;
        return value;
    }
    value["services"] = nlohmann::ordered_json::array();
    for (const auto & service : services) {
        value["services"].push_back({
            {"kind", service.kind},
            {"layer", service.layer},
            {"computed", service.computed},
            {"skipped", service.skipped},
            {"logical_weight_bytes", service.logical_weight_bytes},
        });
    }
    return value;
}

bool common_cassi_owner::write_receipt(const nlohmann::ordered_json & value) {
    const std::string line = value.dump() + "\n";
    if (pimpl->receipt_path.empty()) {
        if (std::fwrite(line.data(), 1, line.size(), stderr) != line.size() || std::fflush(stderr) != 0) {
            return pimpl->set_error("apprentice_receipt_write_failed", true);
        }
        return true;
    }
    std::ofstream stream(pimpl->receipt_path, std::ios::binary | std::ios::app);
    if (!stream) {
        return pimpl->set_error("apprentice_receipt_write_failed", true);
    }
    stream.write(line.data(), static_cast<std::streamsize>(line.size()));
    stream.flush();
    if (!stream) {
        return pimpl->set_error("apprentice_receipt_write_failed", true);
    }
    return true;
}
