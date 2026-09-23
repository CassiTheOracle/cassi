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
    cfr::PackedImage image;
};

class RuntimeState {
public:
    RuntimeState(std::string instance, std::string nonce, std::uint32_t device)
        : instance_id_(bounded_identifier(std::move(instance), "instance identity")),
          launch_nonce_(bounded_identifier(std::move(nonce), "launch nonce")),
          service_generation_(random_u64() | 1U),
          vulkan_(device),
          llama_(device) {}

    [[nodiscard]] const std::string& instance_id() const noexcept { return instance_id_; }
    [[nodiscard]] const std::string& launch_nonce() const noexcept { return launch_nonce_; }
    [[nodiscard]] std::uint64_t generation() const noexcept { return service_generation_; }
    [[nodiscard]] bool shutdown_requested() const noexcept { return shutdown_; }

    cfr::Body handle(cfr::MessageKind kind, const cfr::Body& request, std::uint32_t client_pid) {
        switch (kind) {
        case cfr::MessageKind::hello: return hello(request, client_pid);
        case cfr::MessageKind::status: return status();
        case cfr::MessageKind::import_image: return import_image(request, client_pid);
        case cfr::MessageKind::begin_candidate: return begin_candidate(request);
        case cfr::MessageKind::apply_word_ops: return apply_word_ops(request);
        case cfr::MessageKind::export_candidate: return export_candidate(request, client_pid);
        case cfr::MessageKind::confirm_cache: return confirm_cache(request);
        case cfr::MessageKind::discard_candidate: return discard_candidate(request);
        case cfr::MessageKind::probe_vulkan: return vulkan_status();
        case cfr::MessageKind::shutdown: shutdown_ = true; return cfr::Body{}.text(kStatus, "shutting-down");
        case cfr::MessageKind::detach_owner: return detach_owner(request);
        case cfr::MessageKind::register_model: return register_model(request);
        case cfr::MessageKind::step_model: return step_model(request);
        case cfr::MessageKind::drop_model_task: return drop_model_task(request);
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
    bool shutdown_{false};
    std::unordered_map<std::string, Attachment> attachments_;
    std::unordered_map<std::string, Candidate> candidates_;
    std::unordered_map<std::string, std::string> owner_candidate_;

    cfr::Body hello(const cfr::Body& request, std::uint32_t client_pid) {
        if (request.require_text(1) != instance_id_ || request.require_text(2) != launch_nonce_) throw cfr::ProtocolError("runtime authentication failed");
        if (!client_pid) throw cfr::ProtocolError("runtime client process is unavailable");
        hello_complete_ = true;
        return cfr::Body{}.text(kStatus, "authenticated").u64(kValue, service_generation_).u64(3, client_pid);
    }

    void require_hello() const { if (!hello_complete_) throw cfr::ProtocolError("authenticated hello is required"); }

    cfr::Body status() const {
        require_hello();
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
            .text(11, llama_.reason());
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

    cfr::Body import_image(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        auto owner = bounded_identifier(request.require_text(1), "owner identity");
        const auto generation = request.require_u64(2); const auto fence = request.require_u64(3);
        if (generation != service_generation_) throw cfr::ProtocolError("stale-runtime-generation");
        const auto profile = request.require_text(4); const auto state_sha = request.require_text(5); const auto catalog = request.require_text(6);
        const auto shape = cfr::decode_shape(request.require_bytes(7));
        const auto handle = request.require_u64(8); const auto size64 = request.require_u64(9);
        if (size64 > std::numeric_limits<std::size_t>::max()) throw cfr::ProtocolError("staging mapping size is outside host range");
        const auto declared = request.require_bytes(10); if (declared.size() != 32U) throw cfr::ProtocolError("staging mapping digest size is invalid");
        cfr::Digest digest{}; std::copy(declared.begin(), declared.end(), digest.begin());
        auto bytes = read_client_mapping(client_pid, handle, static_cast<std::size_t>(size64));
        auto image = cfr::pack_image(owner, generation, fence, profile, state_sha, catalog, shape, bytes, digest);
        auto current = attachments_.find(owner);
        if (current != attachments_.end() && fence < current->second.image.fence) throw cfr::ProtocolError("stale-publication-fence");
        const auto packed_sha = cfr::sha256(std::as_bytes(std::span(image.words)));
        attachments_.insert_or_assign(owner, Attachment{std::move(image), "native-cpu"});
        return cfr::Body{}.text(kStatus, "attached").text(kValue, owner).u64(3, attachments_.at(owner).image.words.size()).text(4, cfr::hex_digest(packed_sha));
    }

    cfr::Body begin_candidate(const cfr::Body& request) {
        require_hello();
        const auto owner = request.require_text(1); const auto predecessor = request.require_text(2); const auto fence = request.require_u64(3); const auto lease = bounded_identifier(request.require_text(4), "lease identity"); const auto placement = request.require_text(5);
        auto attached = attachments_.find(owner); if (attached == attachments_.end()) throw cfr::ProtocolError("owner is not resident");
        cfr::require_hex_sha256(predecessor, "predecessor_state_sha256");
        if (attached->second.image.state_sha256 != predecessor || attached->second.image.fence != fence) throw cfr::ProtocolError("stale-publication-fence");
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner already has an in-flight candidate");
        if (placement != "native-cpu" && placement != "vulkan") throw cfr::ProtocolError("candidate placement is unsupported");
        if (placement == "vulkan" && !vulkan_.available()) throw cfr::ProtocolError("vulkan-unavailable: " + vulkan_.reason());
        const auto candidate_id = owner + ":" + std::to_string(random_u64());
        Candidate candidate{candidate_id, lease, predecessor, placement, fence, 0, attached->second.image};
        candidates_.emplace(candidate_id, std::move(candidate)); owner_candidate_.emplace(owner, candidate_id);
        return cfr::Body{}.text(kStatus, "candidate-open").text(kValue, candidate_id).text(3, placement);
    }

    cfr::Body apply_word_ops(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id); if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto operations = cfr::decode_word_operations(request.require_bytes(2));
        if (found->second.logical_operations + operations.size() > 65'536U) throw cfr::ProtocolError("candidate epoch work limit exhausted");
        if (found->second.placement == "vulkan") vulkan_.apply(found->second.image, operations); else cfr::apply_word_operations(found->second.image, operations);
        found->second.logical_operations += operations.size();
        return cfr::Body{}.text(kStatus, "candidate-advanced").u64(kValue, found->second.logical_operations).text(3, cfr::hex_digest(found->second.image.canonical_bytes_sha256));
    }

    cfr::Body export_candidate(const cfr::Body& request, std::uint32_t client_pid) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id); if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto bytes = cfr::unpack_image(found->second.image); const auto digest = cfr::sha256(bytes); const auto handle = export_client_mapping(client_pid, bytes);
        return cfr::Body{}.text(kStatus, "candidate-exported").u64(kValue, handle).u64(3, bytes.size()).bytes(4, digest).text(5, found->second.predecessor_state_sha256).u64(6, found->second.logical_operations);
    }

    cfr::Body confirm_cache(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id); if (found == candidates_.end()) throw cfr::ProtocolError("candidate is unknown");
        const auto predecessor = request.require_text(2); const auto fence = request.require_u64(3); const auto lease = request.require_text(4); const auto successor = request.require_text(5); cfr::require_hex_sha256(successor, "successor_state_sha256");
        auto& candidate = found->second; if (candidate.predecessor_state_sha256 != predecessor || candidate.fence != fence || candidate.lease_id != lease) throw cfr::ProtocolError("candidate publication token is stale");
        auto attached = attachments_.find(candidate.image.owner_id); if (attached == attachments_.end() || attached->second.image.state_sha256 != predecessor || attached->second.image.fence != fence) throw cfr::ProtocolError("owner state changed before cache confirmation");
        candidate.image.state_sha256 = successor; candidate.image.fence = fence + 1U; attached->second = Attachment{candidate.image, candidate.placement};
        const auto owner = candidate.image.owner_id; owner_candidate_.erase(owner); candidates_.erase(found);
        return cfr::Body{}.text(kStatus, "cache-confirmed").text(kValue, owner).text(3, successor).u64(4, fence + 1U);
    }

    cfr::Body discard_candidate(const cfr::Body& request) {
        require_hello();
        const auto candidate_id = request.require_text(1); auto found = candidates_.find(candidate_id);
        if (found == candidates_.end()) return cfr::Body{}.text(kStatus, "already-discarded").text(kValue, candidate_id);
        owner_candidate_.erase(found->second.image.owner_id); candidates_.erase(found);
        return cfr::Body{}.text(kStatus, "discarded").text(kValue, candidate_id);
    }
    cfr::Body detach_owner(const cfr::Body& request) {
        require_hello();
        const auto owner = request.require_text(1);
        if (owner_candidate_.contains(owner)) throw cfr::ProtocolError("owner has an in-flight candidate");
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

    cfr::Body step_model(const cfr::Body& request) {
        require_hello();
        const auto task_id = bounded_identifier(request.require_text(1), "model task identity");
        const auto source_sha = request.require_text(2);
        cfr::require_hex_sha256(source_sha, "model source_sha256");
        const auto packed = request.require_bytes(3);
        if (packed.empty() || packed.size() % sizeof(std::int32_t) != 0U) throw cfr::ProtocolError("model token history encoding is invalid");
        std::vector<std::int32_t> tokens(packed.size() / sizeof(std::int32_t));
        for (std::size_t index = 0; index < tokens.size(); ++index) {
            tokens[index] = static_cast<std::int32_t>(cfr::detail::load_le32(packed.subspan(index * sizeof(std::int32_t), sizeof(std::int32_t))));
        }
        const auto mode = request.require_text(4);
        const auto temperature = require_f64(request, 5, "model temperature");
        const auto top_k64 = request.require_u64(6);
        if (top_k64 > std::numeric_limits<std::uint32_t>::max()) throw cfr::ProtocolError("model top-k exceeds its encoding");
        const auto draw = require_f64(request, 7, "model draw");
        const auto result = llama_.step(task_id, source_sha, tokens, mode, temperature, static_cast<std::uint32_t>(top_k64), draw);
        return cfr::Body{}
            .text(kStatus, "model-advanced")
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

    cfr::Body drop_model_task(const cfr::Body& request) {
        require_hello();
        const auto task_id = request.require_text(1);
        const auto removed = llama_.drop_task(task_id);
        return cfr::Body{}
            .text(kStatus, removed ? "model-task-dropped" : "model-task-absent")
            .text(kValue, task_id);
    }

    cfr::Body vulkan_status() const {
        require_hello();
        return cfr::Body{}.text(kStatus, vulkan_.available() ? "ready" : "unavailable").text(kValue, vulkan_.device_name()).text(3, vulkan_.reason()).text(4, vulkan_.available() ? "exact-word-operation-groups" : "none");
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
    const std::array<cfr::WordOperation, 2> operations{{{cfr::WordOpcode::set, 1, 0, 7, 0}, {cfr::WordOpcode::compare_set, 2, 0xffffffffU, 9, 0}}};
    cfr::apply_word_operations(image, operations);
    const auto unpacked = cfr::unpack_image(image); std::array<double, 3> result{}; std::memcpy(result.data(), unpacked.data(), unpacked.size());
    return result[0] == 0.0 && result[1] == 7.0 && result[2] == 9.0;
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
        std::string instance;std::string nonce;std::uint32_t device=0;bool test=false;
        for(int i=1;i<argc;++i){const std::string_view arg=argv[i];if(arg=="--self-test")test=true;else if(arg=="--instance"&&i+1<argc)instance=argv[++i];else if(arg=="--nonce"&&i+1<argc)nonce=argv[++i];else if(arg=="--device"&&i+1<argc){const auto text=std::string_view(argv[++i]);const auto result=std::from_chars(text.data(),text.data()+text.size(),device);if(result.ec!=std::errc{}||result.ptr!=text.data()+text.size())throw cfr::ProtocolError("device index is invalid");}else throw cfr::ProtocolError("unknown or incomplete command-line argument");}
        if(test){if(!self_test())throw cfr::ProtocolError("native self-test failed");std::cout<<"SELF_TEST_PASS protocol="<<cfr::kProtocolVersion<<" packed=u32 cpu=exact\n";return 0;}
#ifndef _WIN32
        (void)instance;(void)nonce;(void)device;throw cfr::ProtocolError("field-runtime service transport requires Windows");
#else
        if(instance.empty()||nonce.empty())throw cfr::ProtocolError("--instance and --nonce are required");RuntimeState runtime(instance,nonce,device);std::cout<<"READY instance="<<runtime.instance_id()<<" generation="<<runtime.generation()<<std::endl;return run_service(runtime);
#endif
    } catch(const std::exception& error) { std::cerr<<"field-runtime: "<<error.what()<<"\n";return 1; }
}
