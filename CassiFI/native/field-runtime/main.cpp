#include "field_image.hpp"
#include "llama_backend.hpp"
#include "protocol.hpp"
#include "vulkan_backend.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <sddl.h>
#endif

namespace cfr = cassifi::field_runtime;

namespace {

constexpr std::uint16_t kStatus = 1;
constexpr std::uint16_t kValue = 2;
constexpr std::size_t kMaxPendingImportBytes = cfr::kMaxLogicalFieldBytes;
constexpr auto kImportIdleTimeout = std::chrono::minutes(5);


std::uint64_t random_u64() {
    std::random_device source;
    return (std::uint64_t(source()) << 32U) ^ std::uint64_t(source());
}

std::string bounded_identifier(std::string value, std::string_view label) {
    if (value.empty() || value.size() > 512U || !std::all_of(value.begin(), value.end(), [](unsigned char c) { return c >= 0x20U && c != 0x7fU; })) {
        throw cfr::ProtocolError(std::string(label) + " is invalid");
    }
    return value;
}

struct Attachment {
    cfr::PackedImage image;
    std::string placement;
};

struct Candidate {
    std::string candidate_id;
    std::string lease_id;
    std::string predecessor_state_sha256;
    std::string placement;
    std::uint64_t fence{};
    std::uint64_t logical_operations{};
    bool digest_dirty{};
    cfr::PackedImage image;
};

struct PendingImport {
    std::string transfer_id;
    std::string owner_id;
    std::uint64_t service_generation{};
    std::uint64_t fence{};
    std::string profile_sha256;
    std::string state_sha256;
    std::string catalog_sha256;
    std::vector<std::uint32_t> shape;
    cfr::Digest payload_sha256{};
    std::vector<std::byte> payload;
    std::size_t next_offset{};
    std::chrono::steady_clock::time_point last_activity{};
    // A delta transfer seeds the assembled image from the resident base and
    // carries only changed ranges; ``payload`` stays empty for it.
    bool delta{};
    cfr::Digest words_sha256{};
    std::vector<std::uint32_t> base_words;
    std::vector<cfr::Digest> base_page_sha256;
    std::vector<std::uint8_t> touched_pages;
    std::size_t accounted_bytes{};
};

class RuntimeState {
public:
    RuntimeState(std::string instance, std::string nonce, std::uint32_t device, bool cpu_only)
        : instance_id_(bounded_identifier(std::move(instance), "instance identity")),
          launch_nonce_(bounded_identifier(std::move(nonce), "launch nonce")),
          service_generation_(random_u64() | 1U),
          vulkan_(device, !cpu_only),
          llama_(device, !cpu_only),
          cpu_only_(cpu_only) {}

    [[nodiscard]] const std::string& instance_id() const noexcept { return instance_id_; }
    [[nodiscard]] const std::string& launch_nonce() const noexcept { return launch_nonce_; }
    [[nodiscard]] std::uint64_t generation() const noexcept { return service_generation_; }
    [[nodiscard]] bool shutdown_requested() const noexcept { return shutdown_; }

    cfr::Body handle(cfr::MessageKind kind, const cfr::Body& request, std::uint32_t client_pid) {
        expire_imports();
        switch (kind) {
        case cfr::MessageKind::hello: return hello(request, client_pid);
        case cfr::MessageKind::status: return status();
        case cfr::MessageKind::import_image: return import_image(request, client_pid);
        case cfr::MessageKind::import_image_info: return begin_image_import(request);
        case cfr::MessageKind::import_image_chunk: return import_image_chunk(request, client_pid);
        case cfr::MessageKind::import_image_delta: return begin_image_delta(request);
        case cfr::MessageKind::import_delta_chunk: return import_delta_chunk(request, client_pid);
        case cfr::MessageKind::finish_image_import: return finish_image_import(request);
        case cfr::MessageKind::cancel_image_import: return cancel_image_import(request);
        case cfr::MessageKind::export_candidate_info: return export_candidate_info(request);
        case cfr::MessageKind::export_candidate_chunk: return export_candidate_chunk(request, client_pid);
        case cfr::MessageKind::begin_candidate: return begin_candidate(request);
        case cfr::MessageKind::apply_word_ops: return apply_word_ops(request);
        case cfr::MessageKind::apply_candidate_page: return apply_candidate_page(request);
        case cfr::MessageKind::reduce_candidate: return reduce_candidate(request);
        case cfr::MessageKind::export_candidate: return export_candidate(request, client_pid);
        case cfr::MessageKind::confirm_cache: return confirm_cache(request);
        case cfr::MessageKind::discard_candidate: return discard_candidate(request);
        case cfr::MessageKind::probe_vulkan: return vulkan_status();
        case cfr::MessageKind::shutdown: shutdown_ = true; return cfr::Body{}.text(kStatus, "shutting-down");
        case cfr::MessageKind::detach_owner: return detach_owner(request);
        case cfr::MessageKind::register_model: return register_model(request);
        case cfr::MessageKind::graph_site_preflight: return graph_site_preflight(request);
        case cfr::MessageKind::step_model: return step_model(request);
        case cfr::MessageKind::drop_model_task: return drop_model_task(request);
        case cfr::MessageKind::create_group: return create_group(request);
        case cfr::MessageKind::step_group: return step_group(request);
        case cfr::MessageKind::drop_group: return drop_group(request);
        case cfr::MessageKind::leave_group: return leave_group(request);
        case cfr::MessageKind::join_group: return join_group(request);
        case cfr::MessageKind::verify_model_draft: return verify_model_draft(request);
        default: throw cfr::ProtocolError("request kind is unsupported");
        }
    }

private:
    std::string instance_id_;
    std::string launch_nonce_;
    std::uint64_t service_generation_{};
    cfr::VulkanBackend vulkan_;
    cfr::LlamaBackend llama_;
    bool hello_complete_{false};
    bool cpu_only_{false};
    bool shutdown_{false};
    std::unordered_map<std::string, Attachment> attachments_;
    std::unordered_map<std::string, Candidate> candidates_;
    std::unordered_map<std::string, std::string> owner_candidate_;
    std::unordered_map<std::string, PendingImport> imports_;
    std::unordered_map<std::string, std::string> owner_import_;
    std::size_t pending_import_bytes_{};

    void erase_import(std::unordered_map<std::string, PendingImport>::iterator found) {
        pending_import_bytes_ -= found->second.accounted_bytes;
        if (auto owner = owner_import_.find(found->second.owner_id);
            owner != owner_import_.end() && owner->second == found->first) owner_import_.erase(owner);
        imports_.erase(found);
    }

    void expire_imports() {
        const auto now = std::chrono::steady_clock::now();
        for (auto found = imports_.begin(); found != imports_.end();) {
            if (now - found->second.last_activity < kImportIdleTimeout) { ++found; continue; }
            auto expired = found++;
            erase_import(expired);
        }
    }

    static void apply_cpu_operations(cfr::PackedImage& image, std::span<const cfr::WordOperation> operations) {
        auto& words = image.words;
        const bool digest_was_dirty = image.canonical_digest_dirty;
        constexpr auto page_words = cfr::kPageBytes / sizeof(std::uint32_t);
        std::vector<bool> saved((words.size() + page_words - 1U) / page_words, false);
        struct PageBackup { std::size_t start; std::vector<std::uint32_t> words; };
        std::vector<PageBackup> backups;
        const auto check_range = [&](std::uint64_t start, std::uint64_t count) {
            if (start > words.size() || count > words.size() - static_cast<std::size_t>(start))
                throw cfr::ProtocolError("word operation range is outside candidate image");
        };
        const auto save_range = [&](std::size_t start, std::size_t count) {
            if (!count) return;
            for (auto page = start / page_words; page <= (start + count - 1U) / page_words; ++page) {
                if (saved[page]) continue;
                const auto first = page * page_words;
                backups.push_back(PageBackup{first, std::vector<std::uint32_t>(
                    words.begin() + static_cast<std::ptrdiff_t>(first),
                    words.begin() + static_cast<std::ptrdiff_t>(std::min(first + page_words, words.size())))});
                saved[page] = true;
            }
        };
        bool host_mutation_marked = false;
        const auto mark_mutation = [&] {
            if (!host_mutation_marked) {
                cfr::mark_host_mutated(image);
                host_mutation_marked = true;
            }
        };
        try {
            for (const auto& op : operations) {
                switch (op.opcode) {
                case cfr::WordOpcode::set:
                    check_range(op.destination, 1);
                    save_range(static_cast<std::size_t>(op.destination), 1);
                    mark_mutation();
                    words[static_cast<std::size_t>(op.destination)] = op.count_or_value;
                    break;
                case cfr::WordOpcode::copy: {
                    const auto count = static_cast<std::size_t>(op.count_or_value);
                    check_range(op.destination, count);
                    check_range(op.source_or_expected, count);
                    save_range(static_cast<std::size_t>(op.destination), count);
                    if (count != 0U) {
                        mark_mutation();
                        std::memmove(words.data() + op.destination, words.data() + op.source_or_expected,
                            count * sizeof(std::uint32_t));
                    }
                    break;
                }
                case cfr::WordOpcode::fill: {
                    const auto count = static_cast<std::size_t>(op.count_or_value);
                    check_range(op.destination, count);
                    save_range(static_cast<std::size_t>(op.destination), count);
                    if (count != 0U) {
                        mark_mutation();
                        std::fill_n(words.begin() + static_cast<std::ptrdiff_t>(op.destination), count, op.value);
                    }
                    break;
                }
                case cfr::WordOpcode::compare_set:
                    check_range(op.destination, 1);
                    if (words[static_cast<std::size_t>(op.destination)] != static_cast<std::uint32_t>(op.source_or_expected))
                        throw cfr::ProtocolError("word compare-set precondition is stale");
                    save_range(static_cast<std::size_t>(op.destination), 1);
                    mark_mutation();
                    words[static_cast<std::size_t>(op.destination)] = op.count_or_value;
                    break;
                case cfr::WordOpcode::add_constant: {
                    const auto count = static_cast<std::size_t>(op.count_or_value);
                    save_range(static_cast<std::size_t>(op.destination), count);
                    if (count != 0U) {
                        mark_mutation();
                        for (std::size_t index = 0; index < count; ++index)
                            words[static_cast<std::size_t>(op.destination) + index] += op.value;
                    }
                    break;
                }
                }
            }
        } catch (...) {
            for (const auto& backup : backups)
                std::copy(backup.words.begin(), backup.words.end(), words.begin() + static_cast<std::ptrdiff_t>(backup.start));
            if (host_mutation_marked) image.canonical_digest_dirty = digest_was_dirty;
            throw;
        }
    }

    static void finalize_candidate(Candidate& candidate) {
        if (!candidate.digest_dirty && !candidate.image.canonical_digest_dirty) return;
        candidate.image.canonical_bytes_sha256 = cfr::canonical_image_sha256(candidate.image);
        candidate.image.page_sha256 = cfr::page_manifest(candidate.image.words);
        candidate.image.canonical_digest_dirty = false;
        candidate.digest_dirty = false;
    }

    cfr::Body hello(const cfr::Body& request, std::uint32_t client_pid) {
        if (request.require_text(1) != instance_id_ || request.require_text(2) != launch_nonce_) throw cfr::ProtocolError("runtime authentication failed");
        if (!client_pid) throw cfr::ProtocolError("runtime client process is unavailable");
        hello_complete_ = true;
        return cfr::Body{}.text(kStatus, "authenticated").u64(kValue, service_generation_).u64(3, client_pid);
    }

    void require_hello() const { if (!hello_complete_) throw cfr::ProtocolError("authenticated hello is required"); }

    cfr::Body status() const {
        require_hello();
        const auto memory = vulkan_.memory_report();
        const auto memory_state = memory.budget_available ? "measured" : (memory.heaps_available ? "heap-total-only" : "unavailable");
        return cfr::Body{}
            .text(kStatus, "ready")
            .u64(kValue, service_generation_)
            .u64(3, attachments_.size())
            .u64(4, candidates_.size())
            .text(5, vulkan_.available() ? "ready" : "unavailable")
            .text(6, vulkan_.device_name())
            .text(7, vulkan_.reason())
            .text(8, llama_.available() ? "ready" : "unavailable")
            .u64(9, llama_.model_count())
            .u64(10, llama_.task_count())
            .text(11, llama_.reason())
            .text(12, cpu_only_ ? "cpu-only" : "default")
            .u64(13, vulkan_.device_index())
            .text(14, vulkan_.device_identity().empty() ? "unavailable" : vulkan_.device_identity())
            .text(15, vulkan_.device_identity_kind().empty() ? "unavailable" : vulkan_.device_identity_kind())
            .u64(16, memory.heaps_available ? memory.heap_total_bytes : 0)
            .u64(17, memory.budget_available ? memory.heap_budget_bytes : 0)
            .u64(18, memory.budget_available ? memory.heap_usage_bytes : 0)
            .text(19, memory_state)
            .text(20, memory.note)
            .u64(21, llama_.group_count())
            .u64(22, memory.gpu_field_memory_type_index)
            .u64(23, memory.gpu_field_heap_index)
            .u64(24, memory.gpu_field_memory_property_flags)
            .u64(25, memory.gpu_field_memory_heap_flags)
            .u64(26, memory.gpu_field_device_local ? 1U : 0U)
            .u64(27, memory.gpu_field_words_available ? 1U : 0U)
            .u64(28, memory.gpu_field_memory_type_available ? 1U : 0U)
            .u64(29, memory.gpu_field_batches)
            .u64(30, memory.gpu_field_host_upload_bytes)
            .u64(31, memory.gpu_field_changed_page_export_bytes)
            .u64(32, memory.gpu_field_retained_bytes);
    }

#ifdef _WIN32
    static std::vector<std::byte> read_client_mapping(std::uint32_t client_pid, std::uint64_t raw_handle, std::size_t size) {
        if (!size || size > cfr::kMaxFieldBytes) throw cfr::ProtocolError("staging mapping size is outside its bound");
        HANDLE client = OpenProcess(PROCESS_DUP_HANDLE, FALSE, client_pid);
        if (!client) throw cfr::ProtocolError("cannot open staging-map owner process");
        HANDLE local = nullptr;
        const BOOL duplicated = DuplicateHandle(client, reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(raw_handle)), GetCurrentProcess(), &local, FILE_MAP_READ, FALSE, 0);
        CloseHandle(client);
        if (!duplicated || !local) throw cfr::ProtocolError("cannot duplicate immutable staging mapping");
        const void* mapped = MapViewOfFile(local, FILE_MAP_READ, 0, 0, size);
        if (!mapped) { CloseHandle(local); throw cfr::ProtocolError("cannot map immutable staging payload"); }
        std::vector<std::byte> result(size); std::memcpy(result.data(), mapped, size);
        UnmapViewOfFile(mapped); CloseHandle(local); return result;
    }

    static std::uint64_t export_client_mapping(std::uint32_t client_pid, std::span<const std::byte> bytes) {
        HANDLE mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, static_cast<DWORD>(bytes.size()), nullptr);
        if (!mapping) throw cfr::ProtocolError("cannot allocate export staging mapping");
        void* mapped = MapViewOfFile(mapping, FILE_MAP_WRITE, 0, 0, bytes.size());
        if (!mapped) { CloseHandle(mapping); throw cfr::ProtocolError("cannot map export staging payload"); }
        std::memcpy(mapped, bytes.data(), bytes.size()); FlushViewOfFile(mapped, bytes.size()); UnmapViewOfFile(mapped);
        HANDLE client = OpenProcess(PROCESS_DUP_HANDLE, FALSE, client_pid);
        if (!client) { CloseHandle(mapping); throw cfr::ProtocolError("cannot open export-map receiver process"); }
        HANDLE remote = nullptr;
        const BOOL duplicated = DuplicateHandle(GetCurrentProcess(), mapping, client, &remote, FILE_MAP_READ, FALSE, 0);
        CloseHandle(client); CloseHandle(mapping);
        if (!duplicated || !remote) throw cfr::ProtocolError("cannot create restricted export mapping handle");
        return static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(remote));
    }
#else
    static std::vector<std::byte> read_client_mapping(std::uint32_t, std::uint64_t, std::size_t) { throw cfr::ProtocolError("shared staging mappings require Windows"); }
    static std::uint64_t export_client_mapping(std::uint32_t, std::span<const std::byte>) { throw cfr::ProtocolError("shared staging mappings require Windows"); }
#endif

    cfr::Body publish_attachment(std::string owner, cfr::PackedImage image) {
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner has an in-flight candidate");
        auto current = attachments_.find(owner);
        if (current != attachments_.end() && image.fence < current->second.image.fence) throw cfr::ProtocolError("stale-publication-fence");
        const auto packed_sha = cfr::sha256(std::as_bytes(std::span(image.words)));
        attachments_.insert_or_assign(owner, Attachment{std::move(image), "native-cpu"});
        const auto& attached = attachments_.at(owner).image;
        return cfr::Body{}.text(kStatus, "attached").text(kValue, owner).u64(3, attached.words.size()).text(4, cfr::hex_digest(packed_sha));
    }

    cfr::Body import_image(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        auto owner = bounded_identifier(request.require_text(1), "owner identity");
        const auto generation = request.require_u64(2); const auto fence = request.require_u64(3);
        if (generation != service_generation_) throw cfr::ProtocolError("stale-runtime-generation");
        if (owner_candidate_.contains(owner) || owner_import_.contains(owner)) throw cfr::ProtocolError("owner has a writable native operation in flight");
        const auto profile = request.require_text(4); const auto state_sha = request.require_text(5); const auto catalog = request.require_text(6);
        const auto shape = cfr::decode_shape(request.require_bytes(7));
        const auto handle = request.require_u64(8); const auto size64 = request.require_u64(9);
        if (size64 > std::numeric_limits<std::size_t>::max() || size64 > cfr::kMaxFieldBytes) throw cfr::ProtocolError("staging mapping size is outside its bound");
        const auto declared = request.require_bytes(10); if (declared.size() != 32U) throw cfr::ProtocolError("staging mapping digest size is invalid");
        cfr::Digest digest{}; std::copy(declared.begin(), declared.end(), digest.begin());
        auto bytes = read_client_mapping(client_pid, handle, static_cast<std::size_t>(size64));
        auto image = cfr::pack_image(owner, generation, fence, profile, state_sha, catalog, shape, bytes, digest);
        return publish_attachment(std::move(owner), std::move(image));
    }

    cfr::Body begin_image_import(const cfr::Body& request) {
        require_hello();
        auto owner = bounded_identifier(request.require_text(1), "owner identity");
        const auto generation = request.require_u64(2); const auto fence = request.require_u64(3);
        if (generation != service_generation_) throw cfr::ProtocolError("stale-runtime-generation");
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner has an in-flight candidate");
        const auto profile = request.require_text(4); const auto state_sha = request.require_text(5); const auto catalog = request.require_text(6);
        cfr::require_hex_sha256(profile, "profile_sha256"); cfr::require_hex_sha256(state_sha, "state_sha256"); cfr::require_hex_sha256(catalog, "catalog_sha256");
        const auto shape = cfr::decode_shape(request.require_bytes(7));
        const auto expected_bytes = cfr::checked_word_count(shape) * sizeof(double);
        const auto total64 = request.require_u64(8);
        if (total64 != expected_bytes || total64 > cfr::kMaxLogicalFieldBytes || total64 > std::numeric_limits<std::size_t>::max()) throw cfr::ProtocolError("logical image transfer size does not match shape");
        const auto declared = request.require_bytes(9); if (declared.size() != 32U) throw cfr::ProtocolError("logical image digest size is invalid");
        cfr::Digest digest{}; std::copy(declared.begin(), declared.end(), digest.begin());
        const auto current = attachments_.find(owner);
        if (current != attachments_.end() && fence < current->second.image.fence) throw cfr::ProtocolError("stale-publication-fence");
        if (const auto prior = owner_import_.find(owner); prior != owner_import_.end())
            erase_import(imports_.find(prior->second));
        if (total64 > kMaxPendingImportBytes - pending_import_bytes_)
            throw cfr::ProtocolError("aggregate pending image imports exceed their bound");
        std::string transfer_id;
        do { transfer_id = "image-import:" + std::to_string(random_u64()); } while (imports_.contains(transfer_id));
        PendingImport pending;
        pending.transfer_id = transfer_id;
        pending.owner_id = owner;
        pending.service_generation = generation;
        pending.fence = fence;
        pending.profile_sha256 = profile;
        pending.state_sha256 = state_sha;
        pending.catalog_sha256 = catalog;
        pending.shape = shape;
        pending.payload_sha256 = digest;
        pending.payload.resize(static_cast<std::size_t>(total64));
        pending.accounted_bytes = static_cast<std::size_t>(total64);
        pending.last_activity = std::chrono::steady_clock::now();
        owner_import_.emplace(owner, transfer_id);
        try { imports_.emplace(transfer_id, std::move(pending)); }
        catch (...) { owner_import_.erase(owner); throw; }
        pending_import_bytes_ += static_cast<std::size_t>(total64);
        return cfr::Body{}.text(kStatus, "import-open").text(kValue, transfer_id).u64(3, cfr::kMaxTransferChunkBytes);
    }

    cfr::Body begin_image_delta(const cfr::Body& request) {
        require_hello();
        auto owner = bounded_identifier(request.require_text(1), "owner identity");
        const auto generation = request.require_u64(2); const auto fence = request.require_u64(3);
        if (generation != service_generation_) throw cfr::ProtocolError("stale-runtime-generation");
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner has an in-flight candidate");
        const auto profile = request.require_text(4); const auto state_sha = request.require_text(5); const auto catalog = request.require_text(6);
        cfr::require_hex_sha256(profile, "profile_sha256"); cfr::require_hex_sha256(state_sha, "state_sha256"); cfr::require_hex_sha256(catalog, "catalog_sha256");
        const auto shape = cfr::decode_shape(request.require_bytes(7));
        const auto expected_bytes = cfr::checked_word_count(shape) * sizeof(double);
        const auto total64 = request.require_u64(8);
        if (total64 != expected_bytes || total64 > cfr::kMaxLogicalFieldBytes || total64 > std::numeric_limits<std::size_t>::max()) throw cfr::ProtocolError("logical image transfer size does not match shape");
        const auto declared = request.require_bytes(9); if (declared.size() != 32U) throw cfr::ProtocolError("logical image delta digest size is invalid");
        cfr::Digest words_digest{}; std::copy(declared.begin(), declared.end(), words_digest.begin());
        const auto base_fence = request.require_u64(10); const auto base_state = request.require_text(11);
        cfr::require_hex_sha256(base_state, "base_state_sha256");
        const auto current = attachments_.find(owner);
        if (current == attachments_.end()) throw cfr::ProtocolError("image delta requires a resident base");
        const auto& base = current->second.image;
        if (base.fence != base_fence || base.state_sha256 != base_state)
            throw cfr::ProtocolError("image delta base disagrees");
        const auto count = static_cast<std::size_t>(total64 / sizeof(double));
        const auto flat = [](std::span<const std::uint32_t> extents) {
            return extents.size() == 3U && extents.front() == 1U && extents.back() == 1U;
        };
        if (!(shape == base.shape || (flat(shape) && flat(base.shape) && count >= base.words.size())))
            throw cfr::ProtocolError("image delta base shape disagrees");
        if (fence < base.fence) throw cfr::ProtocolError("stale-publication-fence");
        if (const auto prior = owner_import_.find(owner); prior != owner_import_.end())
            erase_import(imports_.find(prior->second));
        if (total64 > kMaxPendingImportBytes - pending_import_bytes_)
            throw cfr::ProtocolError("aggregate pending image imports exceed their bound");
        std::string transfer_id;
        do { transfer_id = "image-delta:" + std::to_string(random_u64()); } while (imports_.contains(transfer_id));
        constexpr auto page_words = cfr::kPageBytes / sizeof(std::uint32_t);
        PendingImport pending;
        pending.transfer_id = transfer_id;
        pending.owner_id = owner;
        pending.service_generation = generation;
        pending.fence = fence;
        pending.profile_sha256 = profile;
        pending.state_sha256 = state_sha;
        pending.catalog_sha256 = catalog;
        pending.shape = shape;
        pending.delta = true;
        pending.words_sha256 = words_digest;
        pending.base_words.assign(count, 0U);
        std::copy(base.words.begin(), base.words.end(), pending.base_words.begin());
        pending.base_page_sha256 = base.page_sha256;
        pending.touched_pages.assign(std::max<std::size_t>(1U, (count + page_words - 1U) / page_words), 0U);
        for (auto page = pending.base_page_sha256.size(); page < pending.touched_pages.size(); ++page)
            pending.touched_pages[page] = 1U;
        pending.accounted_bytes = static_cast<std::size_t>(total64);
        pending.last_activity = std::chrono::steady_clock::now();
        owner_import_.emplace(owner, transfer_id);
        try { imports_.emplace(transfer_id, std::move(pending)); }
        catch (...) { owner_import_.erase(owner); throw; }
        pending_import_bytes_ += static_cast<std::size_t>(total64);
        return cfr::Body{}.text(kStatus, "import-open").text(kValue, transfer_id).u64(3, cfr::kMaxTransferChunkBytes);
    }

    cfr::Body import_image_chunk(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        const auto transfer_id = request.require_text(1);
        auto found = imports_.find(transfer_id);
        if (found == imports_.end()) throw cfr::ProtocolError("image import is unknown");
        auto& transfer = found->second;
        const auto offset64 = request.require_u64(2); const auto handle = request.require_u64(3); const auto size64 = request.require_u64(4);
        if (offset64 != transfer.next_offset || size64 == 0 || size64 > cfr::kMaxTransferChunkBytes || size64 > std::numeric_limits<std::size_t>::max() || size64 % sizeof(double) != 0U || size64 > transfer.payload.size() - transfer.next_offset) throw cfr::ProtocolError("image import chunk is outside its sequential bound");
        const auto declared = request.require_bytes(5); if (declared.size() != 32U) throw cfr::ProtocolError("image import chunk digest size is invalid");
        cfr::Digest digest{}; std::copy(declared.begin(), declared.end(), digest.begin());
        const auto bytes = read_client_mapping(client_pid, handle, static_cast<std::size_t>(size64));
        if (cfr::sha256(bytes) != digest) throw cfr::ProtocolError("image import chunk digest mismatch");
        std::copy(bytes.begin(), bytes.end(), transfer.payload.begin() + static_cast<std::ptrdiff_t>(transfer.next_offset));
        transfer.next_offset += static_cast<std::size_t>(size64);
        transfer.last_activity = std::chrono::steady_clock::now();
        return cfr::Body{}.text(kStatus, "import-chunk-accepted").text(kValue, transfer_id).u64(3, transfer.next_offset);
    }

    cfr::Body import_delta_chunk(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        const auto transfer_id = request.require_text(1);
        auto found = imports_.find(transfer_id);
        if (found == imports_.end()) throw cfr::ProtocolError("image import is unknown");
        auto& transfer = found->second;
        if (!transfer.delta) throw cfr::ProtocolError("image import is not a delta transfer");
        const auto offset64 = request.require_u64(2); const auto handle = request.require_u64(3); const auto size64 = request.require_u64(4);
        const auto limit = transfer.base_words.size() * sizeof(double);
        if (offset64 % sizeof(double) != 0U || offset64 < transfer.next_offset || size64 == 0 ||
                size64 > cfr::kMaxTransferChunkBytes || size64 > std::numeric_limits<std::size_t>::max() ||
                size64 % sizeof(double) != 0U || offset64 > limit || size64 > limit - static_cast<std::size_t>(offset64))
            throw cfr::ProtocolError("image delta chunk is outside its bound");
        const auto declared = request.require_bytes(5); if (declared.size() != 32U) throw cfr::ProtocolError("image delta chunk digest size is invalid");
        cfr::Digest digest{}; std::copy(declared.begin(), declared.end(), digest.begin());
        const auto bytes = read_client_mapping(client_pid, handle, static_cast<std::size_t>(size64));
        if (cfr::sha256(bytes) != digest) throw cfr::ProtocolError("image delta chunk digest mismatch");
        const auto first_word = static_cast<std::size_t>(offset64 / sizeof(double));
        const auto word_count = static_cast<std::size_t>(size64 / sizeof(double));
        for (std::size_t index = 0; index < word_count; ++index) {
            std::uint64_t bits{}; std::memcpy(&bits, bytes.data() + index * sizeof(double), sizeof(bits));
            const double value = std::bit_cast<double>(bits);
            if (!std::isfinite(value) || value < 0.0 || value > double(std::numeric_limits<std::uint32_t>::max()) ||
                    std::floor(value) != value || (value == 0.0 && std::signbit(value)))
                throw cfr::ProtocolError("unsupported-image-encoding");
            transfer.base_words[first_word + index] = static_cast<std::uint32_t>(value);
        }
        constexpr auto page_words = cfr::kPageBytes / sizeof(std::uint32_t);
        for (auto page = first_word / page_words; page <= (first_word + word_count - 1U) / page_words; ++page)
            transfer.touched_pages[page] = 1U;
        transfer.next_offset = static_cast<std::size_t>(offset64) + static_cast<std::size_t>(size64);
        transfer.last_activity = std::chrono::steady_clock::now();
        return cfr::Body{}.text(kStatus, "import-chunk-accepted").text(kValue, transfer_id).u64(3, transfer.next_offset);
    }

    cfr::Body finish_image_import(const cfr::Body& request) {
        require_hello();
        const auto transfer_id = request.require_text(1);
        auto found = imports_.find(transfer_id);
        if (found == imports_.end()) throw cfr::ProtocolError("image import is unknown");
        auto& transfer = found->second;
        if (transfer.delta) {
            if (transfer.service_generation != service_generation_ ||
                    cfr::sha256(std::as_bytes(std::span(transfer.base_words))) != transfer.words_sha256) {
                erase_import(found);
                throw cfr::ProtocolError("image delta digest or generation mismatch");
            }
            try {
                cfr::PackedImage image;
                image.owner_id = transfer.owner_id;
                image.service_generation = transfer.service_generation;
                image.fence = transfer.fence;
                image.profile_sha256 = transfer.profile_sha256;
                image.state_sha256 = transfer.state_sha256;
                image.catalog_sha256 = transfer.catalog_sha256;
                image.shape = transfer.shape;
                image.words = std::move(transfer.base_words);
                image.canonical_bytes_sha256 = cfr::canonical_image_digest(image.words);
                image.page_sha256 = std::move(transfer.base_page_sha256);
                constexpr auto page_words = cfr::kPageBytes / sizeof(std::uint32_t);
                image.page_sha256.resize(std::max<std::size_t>(1U, (image.words.size() + page_words - 1U) / page_words));
                cfr::refresh_changed_page_hashes(image, transfer.touched_pages);
                auto response = publish_attachment(transfer.owner_id, std::move(image));
                erase_import(found);
                return response;
            } catch (...) {
                erase_import(found);
                throw;
            }
        }
        if (transfer.next_offset != transfer.payload.size()) throw cfr::ProtocolError("image import is incomplete");
        if (transfer.service_generation != service_generation_ || cfr::sha256(transfer.payload) != transfer.payload_sha256) {
            erase_import(found);
            throw cfr::ProtocolError("image import canonical digest or generation mismatch");
        }
        try {
            auto image = cfr::pack_image(transfer.owner_id, transfer.service_generation, transfer.fence, transfer.profile_sha256, transfer.state_sha256, transfer.catalog_sha256, transfer.shape, transfer.payload, transfer.payload_sha256);
            auto response = publish_attachment(transfer.owner_id, std::move(image));
            erase_import(found);
            return response;
        } catch (...) {
            erase_import(found);
            throw;
        }
    }

    cfr::Body cancel_image_import(const cfr::Body& request) {
        require_hello();
        const auto transfer_id = request.require_text(1);
        auto found = imports_.find(transfer_id);
        if (found == imports_.end()) return cfr::Body{}.text(kStatus, "already-cancelled").text(kValue, transfer_id);
        erase_import(found);
        return cfr::Body{}.text(kStatus, "cancelled").text(kValue, transfer_id);
    }

    cfr::Body begin_candidate(const cfr::Body& request) {
        require_hello();
        const auto owner = request.require_text(1); const auto predecessor = request.require_text(2); const auto fence = request.require_u64(3); const auto lease = bounded_identifier(request.require_text(4), "lease identity"); const auto requested_placement = request.require_text(5);
        auto attached = attachments_.find(owner); if (attached == attachments_.end()) throw cfr::ProtocolError("owner is not resident");
        cfr::require_hex_sha256(predecessor, "predecessor_state_sha256");
        if (attached->second.image.state_sha256 != predecessor || attached->second.image.fence != fence) throw cfr::ProtocolError("stale-publication-fence");
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner already has an in-flight candidate");
        if (owner_import_.contains(owner)) throw cfr::ProtocolError("owner image import is still in flight");
        if (requested_placement != "native-cpu" && requested_placement != "vulkan") throw cfr::ProtocolError("candidate placement is unsupported");
        std::string placement = requested_placement;
        if (attached->second.image.canonical_bytes() > cfr::kMaxFieldBytes) {
            placement = "native-cpu-continuation";
        } else if (requested_placement == "vulkan" && !vulkan_.available()) {
            throw cfr::ProtocolError("vulkan-unavailable: " + vulkan_.reason());
        }
        const auto candidate_id = "candidate:" + std::to_string(random_u64());
        Candidate candidate{candidate_id, lease, predecessor, placement, fence, 0, false, attached->second.image};
        candidates_.emplace(candidate_id, std::move(candidate)); owner_candidate_.emplace(owner, candidate_id);
        return cfr::Body{}.text(kStatus, "candidate-open").text(kValue, candidate_id).text(3, placement).text(4, requested_placement);
    }

    cfr::Body apply_word_ops(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1);
        auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto operations = cfr::decode_word_operations(request.require_bytes(2));
        if (operations.size() > std::numeric_limits<std::uint64_t>::max() - found->second.logical_operations)
            throw cfr::ProtocolError("candidate logical operation count overflow");
        if (found->second.placement == "vulkan") vulkan_.apply(found->second.image, operations);
        else apply_cpu_operations(found->second.image, operations);
        found->second.logical_operations += operations.size();
        if (!operations.empty() && found->second.placement != "vulkan") found->second.digest_dirty = true;
        return cfr::Body{}.text(kStatus, "candidate-advanced").u64(kValue, found->second.logical_operations)
            .text(3, found->second.digest_dirty ? "" : cfr::hex_digest(found->second.image.canonical_bytes_sha256))
            .text(4, found->second.placement);
    }
    cfr::Body apply_candidate_page(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1);
        auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        constexpr std::size_t page_words = 4096U;
        const auto page_index64 = request.require_u64(2);
        if (page_index64 > std::numeric_limits<std::size_t>::max() / page_words)
            throw cfr::ProtocolError("candidate page index is outside its bound");
        const auto start = static_cast<std::size_t>(page_index64) * page_words;
        if (start >= found->second.image.words.size())
            throw cfr::ProtocolError("candidate page index is outside image");
        const auto count = std::min(page_words, found->second.image.words.size() - start);
        const auto expected = request.require_bytes(3);
        const auto payload = request.require_bytes(4);
        if (expected.size() != 32U || payload.size() != count * sizeof(std::uint32_t))
            throw cfr::ProtocolError("candidate page transfer size is invalid");
        cfr::Digest expected_digest{};
        std::copy(expected.begin(), expected.end(), expected_digest.begin());
        const auto current = std::as_bytes(std::span(found->second.image.words).subspan(start, count));
        if (cfr::sha256(current) != expected_digest)
            throw cfr::ProtocolError("candidate page predecessor is stale");
        cfr::mark_host_mutated(found->second.image);
        for (std::size_t index = 0; index < count; ++index)
            found->second.image.words[start + index] =
                cfr::detail::load_le32(payload.subspan(index * sizeof(std::uint32_t), sizeof(std::uint32_t)));
        found->second.digest_dirty = true;
        if (found->second.placement == "vulkan") found->second.placement = "native-cpu";
        return cfr::Body{}.text(kStatus, "candidate-page-accepted")
            .u64(kValue, found->second.logical_operations)
            .text(3, found->second.placement);
    }

    cfr::Body reduce_candidate(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = bounded_identifier(request.require_text(1), "candidate identity");
        const auto first_word = request.require_u64(2);
        const auto count = request.require_u64(3);
        if (count == 0) throw cfr::ProtocolError("word reduction range is empty");
        auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto& image = found->second.image;
        if (first_word > image.words.size() || count > image.words.size() - static_cast<std::size_t>(first_word))
            throw cfr::ProtocolError("word reduction range is outside candidate image");
        const auto reduction = vulkan_.reduce(image, first_word, count);
        return cfr::Body{}.text(kStatus, "reduced").text(kValue, std::to_string(reduction.sum))
            .u64(3, reduction.count).text(4, reduction.placement)
            .u64(5, found->second.fence).text(6, found->second.predecessor_state_sha256);
    }

    cfr::Body export_candidate(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id); if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto& image = found->second.image;
        if (image.canonical_bytes() > cfr::kMaxFieldBytes) throw cfr::ProtocolError("candidate requires chunked export");
        finalize_candidate(found->second);
        const auto bytes = cfr::unpack_image(image); const auto handle = export_client_mapping(client_pid, bytes);
        return cfr::Body{}.text(kStatus, "candidate-exported").u64(kValue, handle).u64(3, bytes.size()).bytes(4, image.canonical_bytes_sha256).text(5, found->second.predecessor_state_sha256).u64(6, found->second.logical_operations);
    }

    cfr::Body export_candidate_info(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1);
        auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        finalize_candidate(found->second);
        const auto& image = found->second.image;
        return cfr::Body{}.text(kStatus, "candidate-export-info").text(kValue, candidate_id)
            .u64(3, image.canonical_bytes()).bytes(4, image.canonical_bytes_sha256)
            .text(5, found->second.predecessor_state_sha256).u64(6, found->second.logical_operations)
            .u64(7, cfr::kMaxTransferChunkBytes);
    }

    cfr::Body export_candidate_chunk(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id); if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        if (found->second.digest_dirty) throw cfr::ProtocolError("candidate must be finalized before chunked export");
        const auto& image = found->second.image;
        const auto offset64 = request.require_u64(2); const auto size64 = request.require_u64(3); const auto expected_operations = request.require_u64(4); const auto expected_digest = request.require_bytes(5); const auto total = image.canonical_bytes();
        if (expected_digest.size() != image.canonical_bytes_sha256.size() || !std::equal(expected_digest.begin(), expected_digest.end(), image.canonical_bytes_sha256.begin()) || expected_operations != found->second.logical_operations) throw cfr::ProtocolError("candidate changed during chunked export");
        if (offset64 > total || size64 == 0 || size64 > cfr::kMaxTransferChunkBytes || size64 > std::numeric_limits<std::size_t>::max() || size64 % sizeof(double) != 0U || size64 > total - static_cast<std::size_t>(offset64)) throw cfr::ProtocolError("candidate export chunk is outside its bound");
        const auto offset = static_cast<std::size_t>(offset64); const auto size = static_cast<std::size_t>(size64);
        std::vector<std::byte> bytes(size);
        const auto first_word = offset / sizeof(double); const auto word_count = size / sizeof(double);
        for (std::size_t index = 0; index < word_count; ++index) {
            const double value = static_cast<double>(image.words[first_word + index]);
            std::memcpy(bytes.data() + index * sizeof(double), &value, sizeof(value));
        }
        const auto digest = cfr::sha256(bytes); const auto handle = export_client_mapping(client_pid, bytes);
        return cfr::Body{}.text(kStatus, "candidate-export-chunk").u64(kValue, handle).u64(3, size).bytes(4, digest).u64(5, found->second.logical_operations).bytes(6, image.canonical_bytes_sha256);
    }



    cfr::Body confirm_cache(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1);
        auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto predecessor = request.require_text(2);
        const auto fence = request.require_u64(3);
        const auto lease = request.require_text(4);
        const auto successor = request.require_text(5);
        cfr::require_hex_sha256(successor, "successor_state_sha256");
        constexpr std::array<std::uint16_t, 5> graph_tags{6, 7, 8, 9, 10};
        const bool graph_ack = std::any_of(graph_tags.begin(), graph_tags.end(),
            [&](const auto tag) { return request.find(tag) != nullptr; });
        if (graph_ack && std::any_of(graph_tags.begin(), graph_tags.end(),
                [&](const auto tag) { return request.find(tag) == nullptr; }))
            throw cfr::ProtocolError("graph-site cache confirmation is missing an exact receipt binding");
        auto& candidate = found->second;
        if (candidate.predecessor_state_sha256 != predecessor || candidate.fence != fence ||
                candidate.lease_id != lease)
            throw cfr::ProtocolError("candidate publication token is stale");
        auto attached = attachments_.find(candidate.image.owner_id);
        if (attached == attachments_.end() || attached->second.image.state_sha256 != predecessor ||
                attached->second.image.fence != fence)
            throw cfr::ProtocolError("owner state changed before cache confirmation");
        finalize_candidate(candidate);
        if (graph_ack) {
            const auto task_id = bounded_identifier(request.require_text(6), "model task identity");
            const auto canonical_receipt_sha256 = request.require_text(7);
            const auto receipt_wire_sha256 = request.require_text(8);
            const auto ticket_id = request.require_text(9);
            const auto native_operation_id = request.require_text(10);
            cfr::require_hex_sha256(canonical_receipt_sha256, "canonical graph receipt sha256");
            cfr::require_hex_sha256(receipt_wire_sha256, "graph receipt wire sha256");
            const auto accepted = llama_.confirm_graph_site_candidate(task_id, candidate_id, ticket_id,
                native_operation_id, receipt_wire_sha256, canonical_receipt_sha256);
            try {
                if (!accepted.accepted || !accepted.graph_site_receipt.has_value() ||
                        accepted.field_candidate_id != candidate_id || accepted.ticket_id != ticket_id ||
                        accepted.native_operation_id != native_operation_id ||
                        accepted.graph_receipt_wire_sha256 != receipt_wire_sha256 ||
                        accepted.native_graph_site_receipt_sha256 != canonical_receipt_sha256)
                    throw cfr::ProtocolError("native model acceptance did not echo the exact graph-site confirmation");
                cfr::Body response = cfr::Body{}
                    .text(kStatus, "cache-confirmed")
                    .text(kValue, candidate.image.owner_id)
                    .text(3, successor)
                    .u64(4, fence + 1U)
                    .u64(5, static_cast<std::uint32_t>(accepted.token))
                    .u64(6, 1U)
                    .text(7, native_operation_id)
                    .text(8, accepted.native_successor_sha256)
                    .text(9, canonical_receipt_sha256)
                    .text(10, receipt_wire_sha256)
                    .text(11, candidate_id)
                    .text(12, ticket_id);
                candidate.image.state_sha256 = successor;
                candidate.image.fence = fence + 1U;
                const auto owner = candidate.image.owner_id;
                const auto placement = candidate.placement;
                // Promotion is the final step: predecessor is the attached owner
                // image, accepted is the candidate successor (fence+1). No throw
                // can follow it, so a rolled-back confirmation never leaves a
                // promoted device image.
                vulkan_.commit_candidate(attached->second.image, candidate.image);
                attached->second = Attachment{std::move(candidate.image), placement};
                owner_candidate_.erase(owner);
                candidates_.erase(found);
                return response;
            } catch (...) {
                try {
                    llama_.rollback_accepted_graph_site_candidate(
                        task_id, candidate_id, ticket_id, native_operation_id);
                } catch (...) {
                    throw cfr::ProtocolError("graph-site confirmation failed and native model rollback failed");
                }
                throw;
            }
        }
        candidate.image.state_sha256 = successor;
        candidate.image.fence = fence + 1U;
        const auto owner = candidate.image.owner_id;
        const auto placement = candidate.placement;
        // Same promotion as the graph-ack branch: final, non-throwing step.
        vulkan_.commit_candidate(attached->second.image, candidate.image);
        attached->second = Attachment{std::move(candidate.image), placement};
        owner_candidate_.erase(owner);
        candidates_.erase(found);
        return cfr::Body{}.text(kStatus, "cache-confirmed").text(kValue, owner)
            .text(3, successor).u64(4, fence + 1U);
    }

    cfr::Body discard_candidate(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) return cfr::Body{}.text(kStatus, "already-discarded").text(kValue, candidate_id);
        // Abandoned candidate (explicit cancel or the rollback after a failed
        // confirmation): release its owner device image; a confirmed owner's
        // committed image is untouched because a confirmed id is already erased.
        vulkan_.discard_candidate(found->second.image.owner_id);
        owner_candidate_.erase(found->second.image.owner_id); candidates_.erase(found);
        return cfr::Body{}.text(kStatus, "discarded").text(kValue, candidate_id);
    }
    cfr::Body detach_owner(const cfr::Body& request) {
        require_hello();
        const auto owner = request.require_text(1);
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner has an in-flight candidate");
        if (auto transfer = owner_import_.find(owner); transfer != owner_import_.end())
            erase_import(imports_.find(transfer->second));
        const auto removed = attachments_.erase(owner);
        return cfr::Body{}
            .text(kStatus, removed ? "detached" : "already-detached")
            .text(kValue, owner);
    }


    static double require_f64(const cfr::Body& request, std::uint16_t tag, std::string_view label) {
        const auto bytes = request.require_bytes(tag);
        if (bytes.size() != sizeof(double)) throw cfr::ProtocolError(std::string(label) + " encoding is invalid");
        double value{};
        std::memcpy(&value, bytes.data(), sizeof(value));
        return value;
    }

    cfr::Body register_model(const cfr::Body& request) {
        require_hello();
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto source_sha = request.require_text(1);
        cfr::require_hex_sha256(source_sha, "model source_sha256");
        const auto path = request.require_text(2);
        const auto context64 = request.require_u64(3);
        const auto gpu64 = request.require_u64(4);
        if (context64 > std::numeric_limits<std::uint32_t>::max() || gpu64 > std::numeric_limits<std::uint32_t>::max()) {
            throw cfr::ProtocolError("model loading parameter exceeds its encoding");
        }
        const auto gpu_bits = static_cast<std::uint32_t>(gpu64);
        const auto gpu_layers = gpu_bits == 0xffffffffU ? -1 : static_cast<std::int32_t>(gpu_bits);
        const auto registered = llama_.register_model(source_sha, path, static_cast<std::uint32_t>(context64), gpu_layers);
        return cfr::Body{}
            .text(kStatus, registered.status)
            .text(kValue, registered.source_sha256)
            .text(3, registered.description.empty() ? "unknown" : registered.description)
            .u64(4, registered.vocabulary_size)
            .u64(5, registered.context_size)
            .u64(6, registered.model_bytes);
    }

    cfr::Body graph_site_preflight(const cfr::Body& request) {
        require_hello();
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto task_id = bounded_identifier(request.require_text(1), "model task identity");
        const auto source_sha = request.require_text(2);
        cfr::require_hex_sha256(source_sha, "model source_sha256");
        const auto packed = request.require_bytes(3);
        if (packed.empty() || packed.size() % sizeof(std::int32_t) != 0U)
            throw cfr::ProtocolError("graph-site preflight token history encoding is invalid");
        std::vector<std::int32_t> tokens(packed.size() / sizeof(std::int32_t));
        for (std::size_t index = 0; index < tokens.size(); ++index)
            tokens[index] = static_cast<std::int32_t>(cfr::detail::load_le32(
                packed.subspan(index * sizeof(std::int32_t), sizeof(std::int32_t))));
        const auto mode = request.require_text(4);
        const auto temperature = require_f64(request, 5, "graph-site temperature");
        const auto top_k64 = request.require_u64(6);
        if (top_k64 > std::numeric_limits<std::uint32_t>::max())
            throw cfr::ProtocolError("graph-site top-k exceeds its encoding");
        const auto draw = require_f64(request, 7, "graph-site draw");
        const auto sequence_id = request.require_text(8);
        const auto expected_sampler_sha256 = request.require_text(9);
        cfr::require_hex_sha256(expected_sampler_sha256, "graph-site sampler_sha256");
        const auto operation_id = request.require_text(10);
        const auto result = llama_.graph_site_preflight(task_id, source_sha, tokens, mode,
            temperature, static_cast<std::uint32_t>(top_k64), draw, expected_sampler_sha256,
            sequence_id, operation_id);
        const auto encoded = cfr::encode_graph_site_preflight(result);
        return cfr::Body{}
            .text(kStatus, "graph-site-preflight")
            .bytes(kValue, encoded);
    }

    cfr::Body step_model(const cfr::Body& request) {
        require_hello();
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto task_id = bounded_identifier(request.require_text(1), "model task identity");
        const auto source_sha = request.require_text(2);
        cfr::require_hex_sha256(source_sha, "model source_sha256");
        const auto packed = request.require_bytes(3);
        if (packed.empty() || packed.size() % sizeof(std::int32_t) != 0U)
            throw cfr::ProtocolError("model token history encoding is invalid");
        std::vector<std::int32_t> tokens(packed.size() / sizeof(std::int32_t));
        for (std::size_t index = 0; index < tokens.size(); ++index)
            tokens[index] = static_cast<std::int32_t>(cfr::detail::load_le32(
                packed.subspan(index * sizeof(std::int32_t), sizeof(std::int32_t))));
        const auto mode = request.require_text(4);
        const auto temperature = require_f64(request, 5, "model temperature");
        const auto top_k64 = request.require_u64(6);
        if (top_k64 > std::numeric_limits<std::uint32_t>::max())
            throw cfr::ProtocolError("model top-k exceeds its encoding");
        const auto top_k = static_cast<std::uint32_t>(top_k64);
        const auto draw = require_f64(request, 7, "model draw");
        const auto expected_sampler_sha256 = request.require_text(10);
        cfr::require_hex_sha256(expected_sampler_sha256, "model sampler_sha256");
        const auto has_operation_id = request.find(8) != nullptr;
        const auto has_sequence_id = request.find(9) != nullptr;
        const auto operation_id = has_operation_id ? request.require_text(8) : std::string{};
        const auto sequence_id = has_sequence_id ? request.require_text(9) : std::string{};
        const bool has_live_candidate = request.find(17) != nullptr;
        const bool has_replay = request.find(16) != nullptr;
        if (has_live_candidate && has_replay)
            throw cfr::ProtocolError("model step cannot carry both a live candidate and replay proof");
        cfr::ModelStepResult result{};
        if (has_live_candidate) {
            if (!has_operation_id || !has_sequence_id || request.find(14) == nullptr ||
                    request.find(15) == nullptr)
                throw cfr::ProtocolError("live graph-site step is missing its exact candidate identities");
            const auto candidate = cfr::decode_graph_site_candidate(request.require_bytes(17));
            const auto field_candidate_id = request.require_text(14);
            const auto ticket_id = request.require_text(15);
            if (candidate.sampler_sha256 != expected_sampler_sha256 ||
                    candidate.sampler_mode != mode || candidate.sampler_temperature != temperature ||
                    candidate.sampler_top_k != top_k || candidate.sampler_draw != draw)
                throw cfr::ProtocolError("live graph-site candidate sampler differs from the step request");
            result = llama_.step_graph_site_candidate(task_id, source_sha, tokens, operation_id,
                sequence_id, field_candidate_id, ticket_id, candidate);
        } else if (has_replay) {
            if (!has_operation_id || !has_sequence_id || request.find(15) != nullptr ||
                    request.find(17) != nullptr)
                throw cfr::ProtocolError("graph-site replay request has conflicting or missing identities");
            const auto replay = cfr::decode_graph_site_replay_step(request.require_bytes(16));
            const auto candidate = cfr::decode_graph_site_candidate(replay.committed_candidate);
            if (candidate.native_operation_id != operation_id || candidate.sequence_id != sequence_id ||
                    candidate.sampler_sha256 != expected_sampler_sha256 ||
                    candidate.sampler_mode != mode || candidate.sampler_temperature != temperature ||
                    candidate.sampler_top_k != top_k || candidate.sampler_draw != draw ||
                    (request.find(14) != nullptr && request.require_text(14) != replay.field_candidate_id))
                throw cfr::ProtocolError("graph-site replay request differs from its exact row metadata");
            result = llama_.replay_graph_site_step(task_id, source_sha, tokens, replay);
        } else {
            if (request.find(14) != nullptr || request.find(15) != nullptr)
                throw cfr::ProtocolError("ordinary model step cannot carry graph candidate identities");
            const auto native_sampler_sha256 = llama_.effective_sampler_sha256(
                source_sha, mode, temperature, top_k, draw);
            if (native_sampler_sha256 != expected_sampler_sha256)
                throw cfr::ProtocolError("native sampler digest differs from its exact STEP_MODEL tuple");
            result = llama_.step(task_id, source_sha, tokens, mode, temperature, top_k, draw,
                native_sampler_sha256, operation_id, sequence_id);
        }
        cfr::Body response;
        if (result.graph_site_rejected) {
            response.text(kStatus, "graph-site-rejected");
        } else {
            response.text(kStatus, result.accepted ? "model-advanced" : "model-provisional")
                .u64(kValue, static_cast<std::uint32_t>(result.token))
                .u64(3, result.end_of_generation ? 1U : 0U)
                .text(4, result.replay_sha256)
                .u64(5, result.token_count)
                .text(6, result.stage_trace_sha256)
                .u64(7, result.exact_stages)
                .u64(8, result.embedding_stages)
                .u64(9, result.attention_stages)
                .u64(10, result.ffn_stages)
                .u64(11, result.head_stages)
                .u64(12, result.ggml_nodes)
                .u64(13, result.logical_weight_bytes);
        }
        if (result.graph_site_receipt.has_value()) {
            const auto encoded_receipt = cfr::encode_graph_site_receipt(*result.graph_site_receipt);
            response.bytes(14, encoded_receipt);
            if (!result.graph_site_rejected && result.graph_site_receipt->admitted)
                response.text(28,
                    cfr::detail::canonical_graph_site_trace_json(result.graph_site_receipt->stage_trace));
        }
        response.text(15, result.sampler_sha256)
            .text(16, result.native_predecessor_sha256);
        if (!result.graph_site_rejected)
            response.text(17, result.native_successor_sha256);
        response.text(18, result.input_tokens_sha256)
            .text(19, result.native_operation_id)
            .u64(20, result.accepted ? 1U : 0U)
            .u64(21, tokens.size())
            .u64(22, static_cast<std::uint32_t>(result.seq_id))
            .u64(23, static_cast<std::uint32_t>(result.position))
            .text(24, result.graph_receipt_wire_sha256)
            .text(25, result.field_candidate_id)
            .text(26, result.sequence_id)
            .text(27, result.ticket_id);
        return response;
    }

    cfr::Body verify_model_draft(const cfr::Body& request) {
        require_hello();
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto decoded = cfr::decode_model_draft_verify_request(request.require_bytes(1));
        const auto task_id = bounded_identifier(decoded.task_id, "model task identity");
        cfr::require_hex_sha256(decoded.source_sha256, "model source_sha256");
        if (decoded.sampler_mode != "greedy" && decoded.sampler_mode != "categorical")
            throw cfr::ProtocolError("model draft verify sampler mode is unsupported");
        if (!(decoded.sampler_temperature > 0.0) || !std::isfinite(decoded.sampler_temperature))
            throw cfr::ProtocolError("model draft verify temperature is invalid");
        for (const auto draw : decoded.draws)
            if (!(draw >= 0.0 && draw < 1.0) || !std::isfinite(draw))
                throw cfr::ProtocolError("model draft verify draw is outside its bound");
        if (std::any_of(decoded.native_operation_ids.begin(), decoded.native_operation_ids.end(),
                [](const std::string& value) { return value.empty() || value.size() > 512U; }))
            throw cfr::ProtocolError("model draft verify operation identity is invalid");
        if (decoded.sequence_id.size() > 127U)
            throw cfr::ProtocolError("model draft verify sequence identity exceeds its bound");
        const auto native_sampler_sha256 = llama_.effective_sampler_sha256(decoded.source_sha256,
            decoded.sampler_mode, decoded.sampler_temperature, decoded.sampler_top_k, decoded.draws.front());
        const auto rows = llama_.verify_draft(task_id, decoded.source_sha256, decoded.tokens,
            decoded.sampler_mode, decoded.sampler_temperature, decoded.sampler_top_k, decoded.draft_tokens,
            decoded.draws, native_sampler_sha256, decoded.native_operation_ids, decoded.sequence_id);
        std::vector<cfr::ModelDraftRowWire> wire;
        wire.reserve(rows.size());
        for (const auto& row : rows) {
            cfr::ModelDraftRowWire value{};
            value.token = row.token;
            value.end_of_generation = row.end_of_generation ? 1U : 0U;
            value.replay_sha256 = row.replay_sha256;
            value.token_count = row.token_count;
            value.stage_trace_sha256 = row.stage_trace_sha256;
            value.exact_stages = row.exact_stages;
            value.embedding_stages = row.embedding_stages;
            value.attention_stages = row.attention_stages;
            value.ffn_stages = row.ffn_stages;
            value.head_stages = row.head_stages;
            value.ggml_nodes = row.ggml_nodes;
            value.logical_weight_bytes = row.logical_weight_bytes;
            value.sampler_sha256 = row.sampler_sha256;
            value.native_predecessor_sha256 = row.native_predecessor_sha256;
            value.native_successor_sha256 = row.native_successor_sha256;
            value.input_tokens_sha256 = row.input_tokens_sha256;
            value.native_operation_id = row.native_operation_id;
            value.sequence_id = row.sequence_id;
            value.position = static_cast<std::uint64_t>(row.position);
            value.draft_matched = row.draft_matched ? 1U : 0U;
            wire.push_back(std::move(value));
        }
        const auto encoded = cfr::encode_model_draft_rows(wire);
        return cfr::Body{}
            .text(kStatus, "model-draft-rows")
            .bytes(kValue, encoded);
    }

    cfr::Body drop_model_task(const cfr::Body& request) {
        require_hello();
        const auto task_id = request.require_text(1);
        const auto removed = llama_.drop_task(task_id);
        return cfr::Body{}
            .text(kStatus, removed ? "model-task-dropped" : "model-task-absent")
            .text(kValue, task_id);
    }

    cfr::Body create_group(const cfr::Body& request) {
        require_hello();
#ifndef CASSIFI_HAVE_LLAMA
        (void)request;
        throw cfr::ProtocolError("group host requires the llama.cpp backend; --cpu-only builds are unsupported");
#else
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto source_sha = request.require_text(21);
        cfr::require_hex_sha256(source_sha, "group source_sha256");
        const auto capacity = request.require_u64(22);
        if (capacity < 2U || capacity > cfr::kMaxGroupRows) throw cfr::ProtocolError("group capacity is outside its bound");
        const auto group_id = llama_.create_group(source_sha, static_cast<std::uint32_t>(capacity));
        return cfr::Body{}
            .text(kStatus, "group-created")
            .u64(kValue, group_id)
            .u64(21, capacity)
            .u64(22, llama_.group_count());
#endif
    }

    cfr::Body step_group(const cfr::Body& request) {
        require_hello();
#ifndef CASSIFI_HAVE_LLAMA
        (void)request;
        throw cfr::ProtocolError("group host requires the llama.cpp backend; --cpu-only builds are unsupported");
#else
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto group_id = request.require_u64(21);
        const auto packed = request.require_bytes(22);
        if (packed.empty()) throw cfr::ProtocolError("group row encoding is empty");
        auto wire_rows = cfr::decode_group_row_requests(packed);
        std::vector<cfr::ModelGroupRowRequest> rows;
        rows.reserve(wire_rows.size());
        for (auto& row : wire_rows) {
            rows.push_back(cfr::ModelGroupRowRequest{
                std::move(row.tokens), row.next_token, row.accept_sampled != 0U,
                std::move(row.sampler_mode), row.temperature, row.top_k, row.draw});
        }
        const auto results = llama_.step_group(group_id, rows);
        std::vector<cfr::GroupRowResultWire> wire_results;
        wire_results.reserve(results.size());
        for (const auto& result : results) {
            wire_results.push_back(cfr::GroupRowResultWire{
                result.token, result.end_of_generation ? 1U : 0U, result.sampled_token,
                result.replay_sha256, result.token_count, result.stage_trace_sha256,
                result.exact_stages, result.embedding_stages, result.attention_stages,
                result.ffn_stages, result.head_stages, result.ggml_nodes, result.logical_weight_bytes});
        }
        const auto packed_results = cfr::encode_group_row_results(wire_results);
        return cfr::Body{}
            .text(kStatus, "group-advanced")
            .u64(kValue, group_id)
            .bytes(21, packed_results)
            .u64(22, static_cast<std::uint64_t>(wire_results.size()))
            .text(23, "unavailable_native_group_candidate");
#endif
    }

    cfr::Body drop_group(const cfr::Body& request) {
        require_hello();
#ifndef CASSIFI_HAVE_LLAMA
        (void)request;
        throw cfr::ProtocolError("group host requires the llama.cpp backend; --cpu-only builds are unsupported");
#else
        const auto group_id = request.require_u64(21);
        const auto removed = llama_.drop_group(group_id);
        return cfr::Body{}
            .text(kStatus, removed ? "group-dropped" : "group-absent")
            .u64(kValue, group_id)
            .u64(21, llama_.group_count());
#endif
    }

    // Churn: a departing member frees its seat while the group context and the
    // other seats' native sequences stay resident; a newcomer takes the first
    // free seat with a wiped sequence and replays its own history from zero.
    cfr::Body leave_group(const cfr::Body& request) {
        require_hello();
#ifndef CASSIFI_HAVE_LLAMA
        (void)request;
        throw cfr::ProtocolError("group host requires the llama.cpp backend; --cpu-only builds are unsupported");
#else
        const auto group_id = request.require_u64(21);
        const auto row = request.require_u64(22);
        if (row >= cfr::kMaxGroupRows) throw cfr::ProtocolError("group row index is out of range");
        const auto left = llama_.leave_group(group_id, static_cast<std::uint32_t>(row));
        return cfr::Body{}
            .text(kStatus, left ? "group-row-left" : "group-row-idle")
            .u64(kValue, group_id)
            .u64(21, row);
#endif
    }

    cfr::Body join_group(const cfr::Body& request) {
        require_hello();
#ifndef CASSIFI_HAVE_LLAMA
        (void)request;
        throw cfr::ProtocolError("group host requires the llama.cpp backend; --cpu-only builds are unsupported");
#else
        if (!llama_.available()) throw cfr::ProtocolError("model runtime unavailable: " + llama_.reason());
        const auto group_id = request.require_u64(21);
        const auto seat = llama_.join_group(group_id);
        if (seat < 0) {
            return cfr::Body{}
                .text(kStatus, "group-full")
                .u64(kValue, group_id);
        }
        const auto identity = llama_.group_row_identity(group_id, static_cast<std::uint32_t>(seat));
        return cfr::Body{}
            .text(kStatus, "group-row-joined")
            .u64(kValue, group_id)
            .u64(21, static_cast<std::uint64_t>(seat))
            .u64(22, identity.member_generation);
#endif
    }

    cfr::Body vulkan_status() const {
        require_hello();
        const auto memory = vulkan_.memory_report();
        const auto memory_state = memory.budget_available ? "measured" : (memory.heaps_available ? "heap-total-only" : "unavailable");
        return cfr::Body{}
            .text(kStatus, vulkan_.available() ? "ready" : "unavailable")
            .text(kValue, vulkan_.device_name())
            .text(3, vulkan_.reason())
            // Authoritative capability value: exactly what
            // backend_policy.normalize_capability gates auto-selection on
            // ("exact-word-operation-groups"); "none" when unavailable.
            .text(4, vulkan_.available() ? "exact-word-operation-groups" : "none")
            .u64(5, vulkan_.device_index())
            .text(6, vulkan_.device_identity().empty() ? "unavailable" : vulkan_.device_identity())
            .text(7, vulkan_.device_identity_kind().empty() ? "unavailable" : vulkan_.device_identity_kind())
            .u64(8, memory.heaps_available ? memory.heap_total_bytes : 0)
            .u64(9, memory.budget_available ? memory.heap_budget_bytes : 0)
            .u64(10, memory.budget_available ? memory.heap_usage_bytes : 0)
            .text(11, memory_state)
            .text(12, memory.note)
            .u64(13, memory.gpu_field_memory_type_index)
            .u64(14, memory.gpu_field_heap_index)
            .u64(15, memory.gpu_field_memory_property_flags)
            .u64(16, memory.gpu_field_memory_heap_flags)
            .u64(17, memory.gpu_field_device_local ? 1U : 0U)
            .u64(18, memory.gpu_field_words_available ? 1U : 0U)
            .u64(19, memory.gpu_field_memory_type_available ? 1U : 0U)
            .u64(20, memory.gpu_field_batches)
            .u64(21, memory.gpu_field_host_upload_bytes)
            .u64(22, memory.gpu_field_changed_page_export_bytes)
            .u64(23, memory.gpu_field_retained_bytes);
    }
};

bool self_test() {
    const std::string abc = "abc";
    const auto digest = cfr::sha256(std::as_bytes(std::span(abc.data(), abc.size())));
    if (cfr::hex_digest(digest) != "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") return false;
    const auto encoded = cfr::Body{}.text(1, "alpha").u64(2, 42).encode();
    const auto decoded = cfr::Body::decode(encoded);
    if (decoded.require_text(1) != "alpha" || decoded.require_u64(2) != 42) return false;
    cfr::FrameHeader header{}; header.kind = cfr::MessageKind::status; header.body_size = static_cast<std::uint32_t>(encoded.size()); header.body_sha256 = cfr::sha256(encoded);
    const auto decoded_header = cfr::decode_header(cfr::encode_header(header)); cfr::verify_body(decoded_header, encoded);
    const std::array<std::uint32_t, 2> shape{1, 3}; const std::array<double, 3> values{0.0, 1.0, 4294967295.0}; const auto bytes = std::as_bytes(std::span(values));
    const std::string zero_sha(64, '0'); auto image = cfr::pack_image("owner", 1, 0, zero_sha, zero_sha, zero_sha, shape, bytes, cfr::sha256(bytes));
    const std::array<cfr::WordOperation, 3> operations{{
        {cfr::WordOpcode::set, 1, 0, 7, 0},
        {cfr::WordOpcode::compare_set, 2, 0xffffffffU, 9, 0},
        {cfr::WordOpcode::add_constant, 2, 0, 1, 0xffffffffU}}};
    cfr::apply_word_operations(image, operations);
    const auto unpacked = cfr::unpack_image(image); std::array<double, 3> result{}; std::memcpy(result.data(), unpacked.data(), unpacked.size());
    if (result[0] != 0.0 || result[1] != 7.0 || result[2] != 8.0) return false;
    if (cfr::sum_words(image.words, 1, 2) != 15U) return false;
    const std::array<std::pair<std::uint64_t, std::uint64_t>, 3> rejected{{{0, 0}, {2, 2}, {0, 4}}};
    for (const auto& [start, range] : rejected) {
        try { (void)cfr::sum_words(image.words, start, range); return false; } catch (const cfr::ProtocolError&) {}
    }
    const std::vector<cfr::GroupRowRequestWire> group_rows{
        {std::vector<std::int32_t>{11, 22}, -1, 0U, "greedy", 1.0, 0U, 0.0},
        {std::vector<std::int32_t>{11}, 7, 1U, "categorical", 0.8, 40U, 0.25}};
    const auto packed_rows = cfr::encode_group_row_requests(group_rows);
    const auto decoded_rows = cfr::decode_group_row_requests(packed_rows);
    if (decoded_rows.size() != 2U || decoded_rows[0].tokens.size() != 2U || decoded_rows[0].tokens[1] != 22 ||
        decoded_rows[0].next_token != -1 || decoded_rows[1].accept_sampled != 1U ||
        decoded_rows[1].sampler_mode != "categorical" || decoded_rows[1].temperature != 0.8 ||
        decoded_rows[1].top_k != 40U || decoded_rows[1].draw != 0.25) return false;
    const std::vector<cfr::GroupRowResultWire> group_results{
        {30, 0U, 30, std::string(64, 'a'), 3U, std::string(64, 'b'), 5U, 1U, 2U, 2U, 1U, 9U, 100U},
        {31, 1U, 33, std::string(64, 'c'), 2U, std::string(64, 'd'), 5U, 1U, 2U, 2U, 1U, 9U, 100U}};
    const auto packed_results = cfr::encode_group_row_results(group_results);
    const auto decoded_results = cfr::decode_group_row_results(packed_results);
    if (decoded_results.size() != 2U || decoded_results[0].token != 30 || decoded_results[0].sampled_token != 30 ||
        decoded_results[1].end_of_generation != 1U || decoded_results[1].token_count != 2U ||
        decoded_results[1].ggml_nodes != 9U || decoded_results[1].logical_weight_bytes != 100U) return false;
    auto row_rejected = false;
    try { (void)cfr::decode_group_row_requests(std::span<const std::byte>(packed_rows).subspan(0, packed_rows.size() - 1U)); }
    catch (const cfr::ProtocolError&) { row_rejected = true; }
    if (!row_rejected) return false;
    row_rejected = false;
    try {
        const std::vector<cfr::GroupRowRequestWire> oversized{{
            std::vector<std::int32_t>(static_cast<std::size_t>(cfr::kMaxGroupHistoryTokens) + 1U, 0), 0, 0U, "greedy", 1.0, 0U, 0.0}};
        (void)cfr::encode_group_row_requests(oversized);
    } catch (const cfr::ProtocolError&) { row_rejected = true; }
    if (!row_rejected) return false;
    row_rejected = false;
    try {
        const std::vector<cfr::GroupRowRequestWire> too_many(9U);
        (void)cfr::encode_group_row_requests(too_many);
    } catch (const cfr::ProtocolError&) { row_rejected = true; }
    if (!row_rejected) return false;
    row_rejected = false;
    try {
        const std::vector<cfr::GroupRowResultWire> bad_digest{{30, 0U, 30, std::string(64, 'A'), 3U, std::string(64, 'b'), 5U, 1U, 2U, 2U, 1U, 9U, 100U}};
        (void)cfr::encode_group_row_results(bad_digest);
    } catch (const cfr::ProtocolError&) { row_rejected = true; }
    if (!row_rejected) return false;
    row_rejected = false;
    try {
        auto tampered = packed_results; tampered.push_back(std::byte{0});
        (void)cfr::decode_group_row_results(tampered);
    } catch (const cfr::ProtocolError&) { row_rejected = true; }
    if (!row_rejected) return false;
    return true;
}

#ifdef _WIN32

struct LocalSecurity {
    PSECURITY_DESCRIPTOR descriptor{};
    SECURITY_ATTRIBUTES attributes{};
    LocalSecurity() {
        HANDLE token=nullptr; if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)) throw cfr::ProtocolError("cannot query service process token");
        DWORD size=0;GetTokenInformation(token,TokenUser,nullptr,0,&size);std::vector<std::byte> storage(size);
        if(!GetTokenInformation(token,TokenUser,storage.data(),size,&size)){CloseHandle(token);throw cfr::ProtocolError("cannot read service user SID");}CloseHandle(token);
        LPWSTR sid_text=nullptr;const auto* user=reinterpret_cast<const TOKEN_USER*>(storage.data());if(!ConvertSidToStringSidW(user->User.Sid,&sid_text)) throw cfr::ProtocolError("cannot encode service user SID");
        const std::wstring sddl=L"D:P(A;;GA;;;"+std::wstring(sid_text)+L")";LocalFree(sid_text);
        if(!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.c_str(),SDDL_REVISION_1,&descriptor,nullptr)) throw cfr::ProtocolError("cannot create restricted pipe security descriptor");
        attributes.nLength=sizeof(attributes);attributes.lpSecurityDescriptor=descriptor;attributes.bInheritHandle=FALSE;
    }
    ~LocalSecurity(){if(descriptor)LocalFree(descriptor);}
};

void read_exact(HANDLE pipe, std::span<std::byte> bytes) {
    std::size_t cursor=0;while(cursor<bytes.size()){DWORD read=0;const auto chunk=static_cast<DWORD>(std::min<std::size_t>(bytes.size()-cursor,1U<<20));if(!ReadFile(pipe,bytes.data()+cursor,chunk,&read,nullptr)||!read) throw cfr::ProtocolError("pipe frame is truncated");cursor+=read;}
}
void write_exact(HANDLE pipe, std::span<const std::byte> bytes) {
    std::size_t cursor=0;while(cursor<bytes.size()){DWORD written=0;const auto chunk=static_cast<DWORD>(std::min<std::size_t>(bytes.size()-cursor,1U<<20));if(!WriteFile(pipe,bytes.data()+cursor,chunk,&written,nullptr)||!written) throw cfr::ProtocolError("pipe response could not be written");cursor+=written;}
}

bool same_user_and_session(HANDLE pipe, std::uint32_t& client_pid) {
    ULONG pid=0;if(!GetNamedPipeClientProcessId(pipe,&pid)||!pid)return false;client_pid=pid;
    DWORD server_session=0,client_session=0;if(!ProcessIdToSessionId(GetCurrentProcessId(),&server_session)||!ProcessIdToSessionId(pid,&client_session)||server_session!=client_session)return false;
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);if(!process)return false;HANDLE client_token=nullptr,server_token=nullptr;
    const bool opened=OpenProcessToken(process,TOKEN_QUERY,&client_token)&&OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&server_token);CloseHandle(process);if(!opened){if(client_token)CloseHandle(client_token);if(server_token)CloseHandle(server_token);return false;}
    auto sid=[&](HANDLE token){DWORD size=0;GetTokenInformation(token,TokenUser,nullptr,0,&size);std::vector<std::byte> bytes(size);if(!GetTokenInformation(token,TokenUser,bytes.data(),size,&size))bytes.clear();return bytes;};
    const auto client=sid(client_token);const auto server=sid(server_token);CloseHandle(client_token);CloseHandle(server_token);if(client.empty()||server.empty())return false;
    return EqualSid(reinterpret_cast<const TOKEN_USER*>(client.data())->User.Sid,reinterpret_cast<const TOKEN_USER*>(server.data())->User.Sid)!=FALSE;
}

void send_response(HANDLE pipe, const cfr::FrameHeader& request, cfr::MessageKind kind, const cfr::Body& body) {
    const auto encoded=body.encode();cfr::FrameHeader response{};response.kind=kind;response.request_id=request.request_id;response.body_size=static_cast<std::uint32_t>(encoded.size());response.body_sha256=cfr::sha256(encoded);const auto header=cfr::encode_header(response);write_exact(pipe,header);write_exact(pipe,encoded);
}

int run_service(RuntimeState& runtime) {
    LocalSecurity security;
    std::wstring instance(runtime.instance_id().begin(),runtime.instance_id().end());
    const std::wstring pipe_name=L"\\\\.\\pipe\\cassi-field-runtime-"+instance;
    while(!runtime.shutdown_requested()) {
        HANDLE pipe=CreateNamedPipeW(pipe_name.c_str(),PIPE_ACCESS_DUPLEX|FILE_FLAG_FIRST_PIPE_INSTANCE,PIPE_TYPE_BYTE|PIPE_READMODE_BYTE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,1,1U<<20,1U<<20,0,&security.attributes);
        if(pipe==INVALID_HANDLE_VALUE) throw cfr::ProtocolError("cannot create restricted field-runtime pipe");
        const BOOL connected=ConnectNamedPipe(pipe,nullptr)?TRUE:(GetLastError()==ERROR_PIPE_CONNECTED);
        if(!connected){CloseHandle(pipe);continue;}
        std::uint32_t client_pid=0;
        if(!same_user_and_session(pipe,client_pid)){DisconnectNamedPipe(pipe);CloseHandle(pipe);continue;}
        bool authenticated=false;
        try {
            while(!runtime.shutdown_requested()) {
                std::array<std::byte,cfr::kFrameHeaderBytes> header_bytes{};
                read_exact(pipe,header_bytes);
                const auto header=cfr::decode_header(header_bytes);
                std::vector<std::byte> body_bytes(header.body_size);
                read_exact(pipe,body_bytes);
                cfr::verify_body(header,body_bytes);
                const auto body=cfr::Body::decode(body_bytes);
                try {
                    if(!authenticated&&header.kind!=cfr::MessageKind::hello)throw cfr::ProtocolError("authenticated hello is required");
                    auto response=runtime.handle(header.kind,body,client_pid);
                    if(header.kind==cfr::MessageKind::hello)authenticated=true;
                    const auto response_kind=static_cast<cfr::MessageKind>(static_cast<std::uint16_t>(header.kind)|static_cast<std::uint16_t>(cfr::MessageKind::response_bit));
                    send_response(pipe,header,response_kind,response);
                } catch(const std::exception& error) {
                    cfr::Body response;
                    response.text(kStatus,"error").text(kValue,error.what());
                    send_response(pipe,header,cfr::MessageKind::error,response);
                }
            }
        } catch(const std::exception&) {
        }
        FlushFileBuffers(pipe);DisconnectNamedPipe(pipe);CloseHandle(pipe);
    }
    return 0;
}
#endif

} // namespace

int main(int argc, char** argv) {
    try {
        std::string instance;std::string nonce;std::uint32_t device=0;bool test=false;bool cpu_only=false;
        for(int i=1;i<argc;++i){const std::string_view arg=argv[i];if(arg=="--self-test")test=true;else if(arg=="--cpu-only")cpu_only=true;else if(arg=="--instance"&&i+1<argc)instance=argv[++i];else if(arg=="--nonce"&&i+1<argc)nonce=argv[++i];else if(arg=="--device"&&i+1<argc){const auto text=std::string_view(argv[++i]);const auto result=std::from_chars(text.data(),text.data()+text.size(),device);if(result.ec!=std::errc{}||result.ptr!=text.data()+text.size())throw cfr::ProtocolError("device index is invalid");}else throw cfr::ProtocolError("unknown or incomplete command-line argument");}
        if(test){if(!self_test())throw cfr::ProtocolError("native self-test failed");std::cout<<"SELF_TEST_PASS protocol="<<cfr::kProtocolVersion<<" packed=u32 cpu=exact\n";return 0;}
#ifndef _WIN32
        (void)instance;(void)nonce;(void)device;(void)cpu_only;throw cfr::ProtocolError("field-runtime service transport requires Windows");
#else
        if(instance.empty()||nonce.empty())throw cfr::ProtocolError("--instance and --nonce are required");RuntimeState runtime(instance,nonce,device,cpu_only);std::cout<<"READY instance="<<runtime.instance_id()<<" generation="<<runtime.generation()<<std::endl;return run_service(runtime);
#endif
    } catch(const std::exception& error) { std::cerr<<"field-runtime: "<<error.what()<<"\n";return 1; }
}
