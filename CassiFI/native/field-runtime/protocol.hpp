#pragma once

#include <algorithm>
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <cstring>
#include <limits>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#if defined(_M_X64) || defined(__x86_64__)
#define CASSIFI_SHA256_X86 1
#include <immintrin.h>
#if defined(__GNUC__) || defined(__clang__)
#define CASSIFI_SHA256_TARGET __attribute__((target("sha,sse4.1,ssse3")))
#else
#define CASSIFI_SHA256_TARGET
#endif
#if defined(_MSC_VER)
#include <intrin.h>
#else
#include <cpuid.h>
#endif
#endif

namespace cassifi::field_runtime {

inline constexpr std::uint32_t kFrameMagic = 0x31524643U; // "CFR1" as LE bytes
inline constexpr std::uint16_t kProtocolVersion = 2;
inline constexpr std::size_t kFrameHeaderBytes = 64;
inline constexpr std::size_t kMaxFrameBodyBytes = 8U << 20;
inline constexpr std::size_t kMaxFieldBytes = 64U << 20;
inline constexpr std::size_t kMaxLogicalFieldBytes = 1U << 30;
inline constexpr std::size_t kMaxWordOperations = 32'000;
inline constexpr std::size_t kMaxTransferChunkBytes = kMaxFieldBytes;
inline constexpr std::size_t kMaxFields = 128;

enum class MessageKind : std::uint16_t {
    hello = 1,
    status = 2,
    import_image = 3,
    begin_candidate = 4,
    apply_word_ops = 5,
    export_candidate = 6,
    confirm_cache = 7,
    discard_candidate = 8,
    probe_vulkan = 9,
    shutdown = 10,
    detach_owner = 11,
    register_model = 12,
    step_model = 13,
    drop_model_task = 14,
    import_image_info = 15,
    import_image_chunk = 16,
    finish_image_import = 17,
    cancel_image_import = 18,
    export_candidate_info = 19,
    export_candidate_chunk = 20,
    apply_candidate_page = 21,
    reduce_candidate = 22,
    create_group = 23,
    step_group = 24,
    drop_group = 25,
    graph_site_preflight = 26,
    leave_group = 27,
    join_group = 28,
    verify_model_draft = 29,
    response_bit = 0x8000,
    error = 0xffff,
};

enum class WireType : std::uint16_t { bytes = 1, utf8 = 2, u64 = 3 };

struct ProtocolError final : std::runtime_error {
    using std::runtime_error::runtime_error;
};

using Digest = std::array<std::byte, 32>;
using RequestId = std::array<std::byte, 16>;

namespace detail {
inline constexpr std::array<std::uint32_t, 64> kShaK{
    0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,
    0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,
    0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,
    0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,
    0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,
    0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,
    0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,
    0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U};

inline std::uint32_t rotr(std::uint32_t value, unsigned count) noexcept {
    return (value >> count) | (value << (32U - count));
}

inline void store_le16(std::span<std::byte> out, std::uint16_t value) {
    out[0] = std::byte(value & 0xffU); out[1] = std::byte(value >> 8U);
}
inline void store_le32(std::span<std::byte> out, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) out[i] = std::byte((value >> (8U * i)) & 0xffU);
}
inline void store_le64(std::span<std::byte> out, std::uint64_t value) {
    for (unsigned i = 0; i < 8; ++i) out[i] = std::byte((value >> (8U * i)) & 0xffU);
}
inline std::uint16_t load_le16(std::span<const std::byte> in) {
    return std::uint16_t(std::to_integer<unsigned>(in[0])) | (std::uint16_t(std::to_integer<unsigned>(in[1])) << 8U);
}
inline std::uint32_t load_le32(std::span<const std::byte> in) {
    std::uint32_t value = 0; for (unsigned i = 0; i < 4; ++i) value |= std::uint32_t(std::to_integer<unsigned>(in[i])) << (8U * i); return value;
}
inline std::uint64_t load_le64(std::span<const std::byte> in) {
    std::uint64_t value = 0; for (unsigned i = 0; i < 8; ++i) value |= std::uint64_t(std::to_integer<unsigned>(in[i])) << (8U * i); return value;
}

inline constexpr std::array<std::uint32_t, 8> kShaInitial{
    0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U};

inline void sha256_compress_portable(std::uint32_t* state, const std::byte* data, std::size_t blocks) noexcept {
    for (; blocks != 0; --blocks, data += 64) {
        std::array<std::uint32_t, 64> w;
        for (std::size_t i = 0; i < 16; ++i) {
            const auto* p = data + i * 4U;
            w[i] = (std::uint32_t(std::to_integer<unsigned>(p[0])) << 24U) |
                   (std::uint32_t(std::to_integer<unsigned>(p[1])) << 16U) |
                   (std::uint32_t(std::to_integer<unsigned>(p[2])) << 8U) |
                   std::uint32_t(std::to_integer<unsigned>(p[3]));
        }
        for (std::size_t i = 16; i < 64; ++i) {
            const auto s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >> 3U);
            const auto s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >> 10U);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        auto a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
        for (std::size_t i = 0; i < 64; ++i) {
            const auto t1 = h + (rotr(e,6)^rotr(e,11)^rotr(e,25)) + ((e&f)^((~e)&g)) + kShaK[i] + w[i];
            const auto t2 = (rotr(a,2)^rotr(a,13)^rotr(a,22)) + ((a&b)^(a&c)^(b&c));
            h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
        }
        state[0]+=a; state[1]+=b; state[2]+=c; state[3]+=d; state[4]+=e; state[5]+=f; state[6]+=g; state[7]+=h;
    }
}

#if defined(CASSIFI_SHA256_X86)
// SHA extensions (Intel Goldmont+/Ice Lake+, every AMD Zen): the same FIPS 180-4
// compression, computed by sha256rnds2/sha256msg1/sha256msg2 on the ABEF/CDGH layout.
CASSIFI_SHA256_TARGET inline void sha256_compress_x86(std::uint32_t* state, const std::byte* data, std::size_t blocks) noexcept {
    const __m128i byte_swap = _mm_set_epi64x(0x0c0d0e0f08090a0bLL, 0x0405060700010203LL);
    __m128i tmp = _mm_shuffle_epi32(_mm_loadu_si128(reinterpret_cast<const __m128i*>(state)), 0xB1);
    __m128i state1 = _mm_shuffle_epi32(_mm_loadu_si128(reinterpret_cast<const __m128i*>(state + 4)), 0x1B);
    __m128i state0 = _mm_alignr_epi8(tmp, state1, 8);
    state1 = _mm_blend_epi16(state1, tmp, 0xF0);
    for (; blocks != 0; --blocks, data += 64) {
        const __m128i abef = state0;
        const __m128i cdgh = state1;
        __m128i schedule[4];
        for (unsigned group = 0; group < 16; ++group) {
            __m128i words;
            if (group < 4) {
                words = _mm_shuffle_epi8(_mm_loadu_si128(reinterpret_cast<const __m128i*>(data + group * 16U)), byte_swap);
            } else {
                const __m128i previous = schedule[(group - 1U) & 3U];
                words = _mm_sha256msg1_epu32(schedule[group & 3U], schedule[(group - 3U) & 3U]);
                words = _mm_add_epi32(words, _mm_alignr_epi8(previous, schedule[(group - 2U) & 3U], 4));
                words = _mm_sha256msg2_epu32(words, previous);
            }
            schedule[group & 3U] = words;
            __m128i message = _mm_add_epi32(words, _mm_loadu_si128(reinterpret_cast<const __m128i*>(kShaK.data() + group * 4U)));
            state1 = _mm_sha256rnds2_epu32(state1, state0, message);
            message = _mm_shuffle_epi32(message, 0x0E);
            state0 = _mm_sha256rnds2_epu32(state0, state1, message);
        }
        state0 = _mm_add_epi32(state0, abef);
        state1 = _mm_add_epi32(state1, cdgh);
    }
    tmp = _mm_shuffle_epi32(state0, 0x1B);
    state1 = _mm_shuffle_epi32(state1, 0xB1);
    _mm_storeu_si128(reinterpret_cast<__m128i*>(state), _mm_blend_epi16(tmp, state1, 0xF0));
    _mm_storeu_si128(reinterpret_cast<__m128i*>(state + 4), _mm_alignr_epi8(state1, tmp, 8));
}

inline bool sha256_x86_available() noexcept {
    static const bool available = [] {
        unsigned regs[4]{};
        const auto query = [&regs](unsigned leaf) {
#if defined(_MSC_VER)
            int out[4]{};
            __cpuidex(out, static_cast<int>(leaf), 0);
            for (unsigned i = 0; i < 4; ++i) regs[i] = static_cast<unsigned>(out[i]);
#else
            __cpuid_count(leaf, 0, regs[0], regs[1], regs[2], regs[3]);
#endif
        };
        query(0);
        if (regs[0] < 7U) return false;
        query(1);
        const bool ssse3_sse41 = (regs[2] & (1U << 9U)) != 0 && (regs[2] & (1U << 19U)) != 0;
        query(7);
        return ssse3_sse41 && (regs[1] & (1U << 29U)) != 0;
    }();
    return available;
}
#endif

inline void sha256_compress(std::uint32_t* state, const std::byte* data, std::size_t blocks) noexcept {
#if defined(CASSIFI_SHA256_X86)
    if (sha256_x86_available()) {
        sha256_compress_x86(state, data, blocks);
        return;
    }
#endif
    sha256_compress_portable(state, data, blocks);
}
} // namespace detail

// Streaming SHA-256: whole blocks compress straight from the caller's bytes.
class Sha256Accumulator {
public:
    void update(std::span<const std::byte> input) noexcept {
        if (input.empty()) return;
        total_bytes_ += input.size();
        if (buffered_ != 0) {
            const auto count = std::min(input.size(), block_.size() - buffered_);
            std::memcpy(block_.data() + buffered_, input.data(), count);
            buffered_ += count;
            input = input.subspan(count);
            if (buffered_ < block_.size()) return;
            detail::sha256_compress(state_.data(), block_.data(), 1);
            buffered_ = 0;
        }
        const auto blocks = input.size() / block_.size();
        if (blocks != 0) {
            detail::sha256_compress(state_.data(), input.data(), blocks);
            input = input.subspan(blocks * block_.size());
        }
        if (!input.empty()) {
            std::memcpy(block_.data(), input.data(), input.size());
            buffered_ = input.size();
        }
    }

    [[nodiscard]] Digest finish() noexcept {
        const auto bit_length = total_bytes_ * 8U;
        block_[buffered_++] = std::byte{0x80};
        if (buffered_ > 56U) {
            std::fill(block_.begin() + static_cast<std::ptrdiff_t>(buffered_), block_.end(), std::byte{});
            detail::sha256_compress(state_.data(), block_.data(), 1);
            buffered_ = 0;
        }
        std::fill(block_.begin() + static_cast<std::ptrdiff_t>(buffered_), block_.begin() + 56, std::byte{});
        for (unsigned index = 0; index < 8; ++index)
            block_[56U + index] = std::byte((bit_length >> (56U - index * 8U)) & 0xffU);
        detail::sha256_compress(state_.data(), block_.data(), 1);
        Digest output{};
        for (std::size_t index = 0; index < state_.size(); ++index)
            for (unsigned byte = 0; byte < 4; ++byte)
                output[index * 4U + byte] = std::byte((state_[index] >> (24U - byte * 8U)) & 0xffU);
        return output;
    }

private:
    std::array<std::uint32_t, 8> state_{detail::kShaInitial};
    std::array<std::byte, 64> block_{};
    std::size_t buffered_{};
    std::uint64_t total_bytes_{};
};

inline Digest sha256(std::span<const std::byte> input) noexcept {
    Sha256Accumulator hash;
    hash.update(input);
    return hash.finish();
}

inline std::string hex_digest(const Digest& digest) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string result(64, '0');
    for (std::size_t i = 0; i < digest.size(); ++i) {
        const auto value = std::to_integer<unsigned>(digest[i]);
        result[i*2U] = digits[value >> 4U]; result[i*2U+1U] = digits[value & 0xfU];
    }
    return result;
}

struct FrameHeader {
    std::uint16_t version{kProtocolVersion};
    MessageKind kind{MessageKind::error};
    std::uint32_t flags{};
    std::uint32_t body_size{};
    RequestId request_id{};
    Digest body_sha256{};
};

inline std::array<std::byte, kFrameHeaderBytes> encode_header(const FrameHeader& header) {
    if (header.version != kProtocolVersion || header.body_size > kMaxFrameBodyBytes) throw ProtocolError("frame header is outside protocol bounds");
    std::array<std::byte, kFrameHeaderBytes> out{};
    detail::store_le32(std::span<std::byte>(out).subspan(0,4), kFrameMagic);
    detail::store_le16(std::span<std::byte>(out).subspan(4,2), header.version);
    detail::store_le16(std::span<std::byte>(out).subspan(6,2), static_cast<std::uint16_t>(header.kind));
    detail::store_le32(std::span<std::byte>(out).subspan(8,4), header.flags);
    detail::store_le32(std::span<std::byte>(out).subspan(12,4), header.body_size);
    std::copy(header.request_id.begin(), header.request_id.end(), out.begin()+16);
    std::copy(header.body_sha256.begin(), header.body_sha256.end(), out.begin()+32);
    return out;
}

inline FrameHeader decode_header(std::span<const std::byte> bytes) {
    if (bytes.size() != kFrameHeaderBytes) throw ProtocolError("frame header size is invalid");
    if (detail::load_le32(bytes.subspan(0,4)) != kFrameMagic) throw ProtocolError("frame magic is invalid");
    FrameHeader result{};
    result.version = detail::load_le16(bytes.subspan(4,2));
    if (result.version != kProtocolVersion) throw ProtocolError("protocol version is unsupported");
    result.kind = static_cast<MessageKind>(detail::load_le16(bytes.subspan(6,2)));
    result.flags = detail::load_le32(bytes.subspan(8,4));
    result.body_size = detail::load_le32(bytes.subspan(12,4));
    if (result.body_size > kMaxFrameBodyBytes) throw ProtocolError("frame body exceeds its bound");
    std::copy_n(bytes.begin()+16,16,result.request_id.begin());
    std::copy_n(bytes.begin()+32,32,result.body_sha256.begin());
    return result;
}

struct Field {
    std::uint16_t tag{};
    WireType type{WireType::bytes};
    std::vector<std::byte> value{};
};

class Body {
public:
    Body& bytes(std::uint16_t tag, std::span<const std::byte> value) { add(tag, WireType::bytes, value); return *this; }
    Body& text(std::uint16_t tag, std::string_view value) {
        add(tag, WireType::utf8, std::as_bytes(std::span(value.data(), value.size()))); return *this;
    }
    Body& u64(std::uint16_t tag, std::uint64_t value) {
        std::array<std::byte,8> encoded{}; detail::store_le64(encoded,value); add(tag,WireType::u64,encoded); return *this;
    }
    [[nodiscard]] std::vector<std::byte> encode() const {
        if (fields_.size() > kMaxFields) throw ProtocolError("too many body fields");
        std::vector<std::byte> out;
        std::size_t total=0; for (const auto& field:fields_) { if (field.value.size()>kMaxFieldBytes-total-8U) throw ProtocolError("body fields exceed their bound"); total += 8U+field.value.size(); }
        if (total>kMaxFrameBodyBytes) throw ProtocolError("frame body exceeds its bound");
        out.resize(total); std::size_t cursor=0;
        for (const auto& field:fields_) {
            detail::store_le16(std::span<std::byte>(out).subspan(cursor,2),field.tag);
            detail::store_le16(std::span<std::byte>(out).subspan(cursor+2,2),static_cast<std::uint16_t>(field.type));
            detail::store_le32(std::span<std::byte>(out).subspan(cursor+4,4),static_cast<std::uint32_t>(field.value.size()));
            std::copy(field.value.begin(),field.value.end(),out.begin()+static_cast<std::ptrdiff_t>(cursor+8)); cursor+=8U+field.value.size();
        }
        return out;
    }
    static Body decode(std::span<const std::byte> bytes) {
        if (bytes.size()>kMaxFrameBodyBytes) throw ProtocolError("frame body exceeds its bound");
        Body body; std::size_t cursor=0; std::uint16_t prior=0;
        while (cursor<bytes.size()) {
            if (bytes.size()-cursor<8U) throw ProtocolError("truncated body field");
            const auto tag=detail::load_le16(bytes.subspan(cursor,2)); const auto raw_type=detail::load_le16(bytes.subspan(cursor+2,2)); const auto size=detail::load_le32(bytes.subspan(cursor+4,4));
            if (!tag || tag<=prior) throw ProtocolError("body tags must be unique and ascending");
            if (raw_type<1U || raw_type>3U) throw ProtocolError("body wire type is unsupported");
            if (size>kMaxFieldBytes || size>bytes.size()-cursor-8U) throw ProtocolError("body field size is invalid");
            body.add(tag,static_cast<WireType>(raw_type),bytes.subspan(cursor+8U,size)); prior=tag; cursor+=8U+size;
            if (body.fields_.size()>kMaxFields) throw ProtocolError("too many body fields");
        }
        return body;
    }
    [[nodiscard]] const Field* find(std::uint16_t tag) const noexcept { auto it=std::lower_bound(fields_.begin(),fields_.end(),tag,[](const Field& field,std::uint16_t key){return field.tag<key;}); return it!=fields_.end()&&it->tag==tag?&*it:nullptr; }
    [[nodiscard]] std::string require_text(std::uint16_t tag) const { const auto& f=require(tag,WireType::utf8); return {reinterpret_cast<const char*>(f.value.data()),f.value.size()}; }
    [[nodiscard]] std::uint64_t require_u64(std::uint16_t tag) const { const auto& f=require(tag,WireType::u64); if(f.value.size()!=8U) throw ProtocolError("u64 body field has invalid size"); return detail::load_le64(f.value); }
    [[nodiscard]] std::span<const std::byte> require_bytes(std::uint16_t tag) const { return require(tag,WireType::bytes).value; }
private:
    std::vector<Field> fields_{};
    void add(std::uint16_t tag,WireType type,std::span<const std::byte> value) {
        if(!tag || (!fields_.empty()&&tag<=fields_.back().tag)) throw ProtocolError("body tags must be appended in ascending order");
        if(value.size()>kMaxFieldBytes) throw ProtocolError("body field exceeds its bound");
        fields_.push_back(Field{tag,type,{value.begin(),value.end()}});
    }
    [[nodiscard]] const Field& require(std::uint16_t tag,WireType type) const { const auto* f=find(tag); if(!f||f->type!=type) throw ProtocolError("required body field is missing or mistyped"); return *f; }
};

inline void verify_body(const FrameHeader& header, std::span<const std::byte> body) {
    if (body.size()!=header.body_size) throw ProtocolError("frame body size disagrees with header");
    if (sha256(body)!=header.body_sha256) throw ProtocolError("frame body digest mismatch");
}

// Group host wire codec: bounded little-endian packed row records shared by the
// service (MessageKind 23/24/25) and the native client. Request tags start at
// 21; tags 1..20 stay reserved for the stable status field set. Every record is
// a strict sequential layout with no padding; decoding must consume the blob
// exactly and rejects oversized histories, non-normalized flags and bad
// digests before the backend is ever asked for a result.
inline constexpr std::size_t kMaxGroupRows = 8;
inline constexpr std::uint64_t kMaxGroupHistoryTokens = 1'048'576;
inline constexpr std::size_t kMaxGroupSamplerBytes = 32;

struct GroupRowRequestWire {
    std::vector<std::int32_t> tokens{};
    std::int32_t next_token{};
    std::uint8_t accept_sampled{};
    std::string sampler_mode{};
    double temperature{};
    std::uint32_t top_k{};
    double draw{};
};

struct GroupRowResultWire {
    std::int32_t token{};
    std::uint8_t end_of_generation{};
    std::int32_t sampled_token{};
    std::string replay_sha256{};
    std::uint64_t token_count{};
    std::string stage_trace_sha256{};
    std::uint64_t exact_stages{};
    std::uint64_t embedding_stages{};
    std::uint64_t attention_stages{};
    std::uint64_t ffn_stages{};
    std::uint64_t head_stages{};
    std::uint64_t ggml_nodes{};
    std::uint64_t logical_weight_bytes{};
};

inline constexpr std::uint32_t kGraphSiteWireVersion = 3;
inline constexpr std::uint32_t kGraphSiteReceiptWireVersion = 3;
inline constexpr std::size_t kMaxGraphSiteDescriptors = 4096;
inline constexpr std::size_t kMaxGraphSiteTextBytes = 4096;
inline constexpr std::size_t kMaxGraphSiteVectorElements = kMaxFrameBodyBytes / sizeof(float);

struct GraphSiteDescriptorWire {
    std::uint32_t kind{};
    std::uint8_t supported{};
    std::int32_t layer{};
    std::uint32_t input_width{};
    std::uint32_t output_width{};
    std::string stage{};
    std::string site{};
    std::string specialist{};
    std::string input_tensor{};
    std::string output_tensor{};
    std::string dependencies_json{};
    std::string refusal{};
};

struct GraphSitePreflightWire {
    std::uint32_t version{kGraphSiteWireVersion};
    std::uint8_t ready{};
    std::int32_t native_seq_id{};
    std::int32_t next_position{};
    std::uint32_t context_limit{};
    std::uint32_t remaining_tokens{};
    std::uint32_t model_embedding_width{};
    std::uint32_t model_layer_count{};
    std::string task_id{};
    std::string sequence_id{};
    std::string native_operation_id{};
    std::string source_sha256{};
    std::string model_sha256{};
    std::string tokenizer_sha256{};
    std::string native_predecessor_sha256{};
    std::string native_field_epoch_sha256{};
    std::string native_preflight_sha256{};
    std::string sampler_sha256{};
    std::string sampler_mode{};
    double sampler_temperature{};
    std::uint32_t sampler_top_k{};
    double sampler_draw{};
    std::string refusal{};
    std::vector<GraphSiteDescriptorWire> sites{};
};
struct GraphSiteCandidateWire {
    std::uint32_t version{kGraphSiteWireVersion};
    std::string ticket_id{};
    std::string ticket_sha256{};
    std::string preflight_sha256{};
    std::string native_preflight_sha256{};
    std::string source_sha256{};
    std::string model_sha256{};
    std::string tokenizer_sha256{};
    std::string task_id{};
    std::string sequence_id{};
    std::string native_operation_id{};
    std::string native_predecessor_sha256{};
    std::string owner_snapshot_sha256{};
    std::string native_field_epoch_sha256{};
    std::string owner_field_epoch_sha256{};
    std::uint8_t request_sha256_pending{};
    std::string sampler_sha256{};
    std::string sampler_mode{};
    double sampler_temperature{};
    std::uint32_t sampler_top_k{};
    double sampler_draw{};
    std::uint32_t kind{};
    std::int32_t seq_id{};
    std::int32_t position{};
    std::int32_t layer{};
    std::uint64_t owner_generation{};
    std::uint64_t predecessor_generation{};
    std::string candidate_sequence_id{};
    std::string candidate_source_sha256{};
    std::string architecture{};
    std::string backend{};
    std::string input_tensor{};
    std::string output_tensor{};
    std::string tensor_dtype{};
    std::string stage{};
    std::string site{};
    std::string specialist{};
    std::string candidate_predecessor_sha256{};
    std::string request_sha256{};
    std::string invocation_sha256{};
    std::string candidate_sha256{};
    std::string intervention_order{};
    std::string dependencies_json{};
    std::string method_key{};
    std::uint64_t method_generation{};
    std::uint32_t input_width{};
    std::uint32_t rank{};
    std::uint32_t output_width{};
    std::vector<float> a{};
    std::vector<float> b{};
    std::vector<float> bias{};
    std::uint32_t conv_history_rows{};
    std::uint32_t conv_history_channels{};
    std::uint32_t recurrent_state_heads{};
    std::uint32_t recurrent_state_value_width{};
    std::uint32_t recurrent_state_key_width{};
    std::uint32_t attn_kv_heads{};
    std::uint32_t attn_kv_head_width{};
    std::uint32_t verb{};
    std::string guard_candidate_id{};
    std::string guard_owner_snapshot_sha256{};
    std::string guard_field_epoch_sha256{};
    std::string guard_native_predecessor_sha256{};
    std::string guard_native_preflight_sha256{};
    std::vector<float> input_support_anchor{};
    float input_support_radius{};
    float input_support_anchor_norm{};
    std::vector<std::int32_t> expected_expert_ids{};
};

struct GraphSiteReceiptWire {
    std::uint32_t version{kGraphSiteReceiptWireVersion};
    std::string ticket_id{};
    std::string field_candidate_id{};
    std::string ticket_sha256{};
    std::string preflight_sha256{};
    std::string native_preflight_sha256{};
    std::string source_sha256{};
    std::string model_sha256{};
    std::string tokenizer_sha256{};
    std::string task_id{};
    std::string sequence_id{};
    std::string native_operation_id{};
    std::int32_t seq_id{};
    std::int32_t position{};
    std::int32_t accepted_token_id{};
    std::uint64_t input_token_count{};
    std::string input_tokens_sha256{};
    std::string replay_sha256{};
    std::uint64_t token_count{};
    std::string stage{};
    std::int32_t layer{};
    std::string site{};
    std::string specialist{};
    std::string invocation_sha256{};
    std::string request_sha256{};
    std::string candidate_sha256{};
    std::string dependencies_json{};
    std::string method_key{};
    std::uint64_t method_generation{};
    std::string intervention_order{};
    std::string graph_predecessor_sha256{};
    std::string owner_snapshot_sha256{};
    std::string owner_field_epoch_sha256{};
    std::string native_field_epoch_sha256{};
    std::string native_predecessor_sha256{};
    std::string sampler_sha256{};
    std::string sampler_mode{};
    double sampler_temperature{};
    std::uint32_t sampler_top_k{};
    double sampler_draw{};
    std::string input_sha256{};
    std::string output_sha256{};
    std::vector<std::int32_t> expected_expert_ids{};
    std::vector<std::int32_t> actual_expert_ids{};
    std::vector<std::string> stage_trace{};
    std::string stage_trace_sha256{};
    std::string candidate_successor_sha256{};
    std::string native_successor_sha256{};
    std::string successor_state_json{};
    std::string refusal{};
    std::uint8_t attempted{};
    std::uint8_t admitted{};
    std::uint64_t owner_generation{};
    std::uint64_t operators_omitted{};
    std::uint64_t weights_omitted{};
    std::uint64_t weight_bytes_omitted{};
    std::uint64_t transfer_bytes_omitted{};
    double added_flops{};
};

struct GraphSiteReplayStepWire {
    std::uint32_t version{kGraphSiteWireVersion};
    std::uint64_t sequence_index{};
    std::string native_operation_id{};
    std::string field_candidate_id{};
    std::string owner_predecessor_sha256{};
    std::string owner_successor_sha256{};
    std::string native_predecessor_sha256{};
    std::string native_successor_sha256{};
    std::string native_preflight_sha256{};
    std::uint64_t input_token_count{};
    std::string input_tokens_sha256{};
    std::int32_t accepted_token_id{};
    std::string sampler_sha256{};
    std::string sampler_mode{};
    double sampler_temperature{};
    std::uint32_t sampler_top_k{};
    double sampler_draw{};
    std::string replay_sha256{};
    std::string stage_trace_sha256{};
    std::uint64_t token_count{};
    std::uint8_t history_complete{};
    std::string expected_ticket_sha256{};
    std::string expected_graph_receipt_sha256{};
    std::string expected_native_graph_site_receipt_sha256{};
    std::vector<std::byte> committed_candidate{};
};

namespace detail {
inline void append_raw(std::vector<std::byte>& out, std::span<const std::byte> value) {
    out.insert(out.end(), value.begin(), value.end());
}
inline void append_u32(std::vector<std::byte>& out, std::uint32_t value) {
    std::array<std::byte, 4> encoded{};
    store_le32(encoded, value);
    append_raw(out, encoded);
}
inline void append_u64(std::vector<std::byte>& out, std::uint64_t value) {
    std::array<std::byte, 8> encoded{};
    store_le64(encoded, value);
    append_raw(out, encoded);
}
inline void append_u8(std::vector<std::byte>& out, std::uint8_t value) {
    out.push_back(std::byte(value));
}
inline void append_i32(std::vector<std::byte>& out, std::int32_t value) {
    append_u32(out, std::bit_cast<std::uint32_t>(value));
}
inline void append_f32(std::vector<std::byte>& out, float value) {
    append_u32(out, std::bit_cast<std::uint32_t>(value));
}
inline void append_f64(std::vector<std::byte>& out, double value) {
    append_u64(out, std::bit_cast<std::uint64_t>(value));
}
inline void append_text(
        std::vector<std::byte>& out,
        std::string_view value,
        std::size_t bound,
        std::string_view label) {
    if (value.size() > bound || value.size() > std::numeric_limits<std::uint32_t>::max())
        throw ProtocolError(std::string(label) + " exceeds its bound");
    append_u32(out, static_cast<std::uint32_t>(value.size()));
    append_raw(out, std::as_bytes(std::span(value.data(), value.size())));
}
inline void append_float_vector(std::vector<std::byte>& out, std::span<const float> values) {
    if (values.size() > kMaxGraphSiteVectorElements || values.size() > std::numeric_limits<std::uint32_t>::max())
        throw ProtocolError("graph-site float vector exceeds its bound");
    append_u32(out, static_cast<std::uint32_t>(values.size()));
    for (const auto value : values) append_f32(out, value);
}
inline void append_i32_vector(std::vector<std::byte>& out, std::span<const std::int32_t> values) {
    if (values.size() > kMaxGraphSiteVectorElements || values.size() > std::numeric_limits<std::uint32_t>::max())
        throw ProtocolError("graph-site integer vector exceeds its bound");
    append_u32(out, static_cast<std::uint32_t>(values.size()));
    for (const auto value : values) append_i32(out, value);
}

class RowReader {
public:
    explicit RowReader(std::span<const std::byte> bytes) noexcept : bytes_(bytes) {}
    [[nodiscard]] std::span<const std::byte> take(std::size_t count) {
        if (count > bytes_.size() - cursor_) throw ProtocolError("group row encoding is truncated");
        const auto result = bytes_.subspan(cursor_, count);
        cursor_ += count;
        return result;
    }
    [[nodiscard]] std::uint8_t u8() { return std::to_integer<std::uint8_t>(take(1U)[0]); }
    [[nodiscard]] std::uint32_t u32() { return load_le32(take(4U)); }
    [[nodiscard]] std::uint64_t u64() { return load_le64(take(8U)); }
    [[nodiscard]] std::int32_t i32() { return static_cast<std::int32_t>(u32()); }
    [[nodiscard]] double f64() { return std::bit_cast<double>(u64()); }
    [[nodiscard]] float f32() { return std::bit_cast<float>(u32()); }
    [[nodiscard]] std::string text(std::size_t bound, std::string_view label) {
        const auto length = u32();
        if (length > bound) throw ProtocolError(std::string(label) + " exceeds its bound");
        const auto value = take(length);
        if (value.empty()) return {};
        return std::string(reinterpret_cast<const char*>(value.data()), value.size());
    }
    [[nodiscard]] bool done() const noexcept { return cursor_ == bytes_.size(); }
private:
    std::span<const std::byte> bytes_;
    std::size_t cursor_{};
};
inline std::vector<float> read_float_vector(RowReader& reader) {
    const auto count = reader.u32();
    if (count > kMaxGraphSiteVectorElements) throw ProtocolError("graph-site float vector exceeds its bound");
    const auto bytes = reader.take(static_cast<std::size_t>(count) * sizeof(float));
    std::vector<float> result;
    result.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        const auto chunk = bytes.subspan(static_cast<std::size_t>(index) * sizeof(float), sizeof(float));
        result.push_back(std::bit_cast<float>(load_le32(chunk)));
    }
    return result;
}
inline std::vector<std::int32_t> read_i32_vector(RowReader& reader) {
    const auto count = reader.u32();
    if (count > kMaxGraphSiteVectorElements) throw ProtocolError("graph-site integer vector exceeds its bound");
    const auto bytes = reader.take(static_cast<std::size_t>(count) * sizeof(std::int32_t));
    std::vector<std::int32_t> result;
    result.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        const auto chunk = bytes.subspan(static_cast<std::size_t>(index) * sizeof(std::int32_t), sizeof(std::int32_t));
        result.push_back(static_cast<std::int32_t>(load_le32(chunk)));
    }
    return result;
}
inline void append_graph_site_trace(std::vector<std::byte>& out,
        const std::vector<std::string>& values) {
    if (values.size() > kMaxGraphSiteDescriptors)
        throw ProtocolError("graph-site trace exceeds its bound");
    append_u32(out, static_cast<std::uint32_t>(values.size()));
    for (const auto& value : values)
        append_text(out, value, kMaxGraphSiteTextBytes, "graph-site trace entry");
}
inline std::vector<std::string> read_graph_site_trace(RowReader& reader) {
    const auto count = reader.u32();
    if (count > kMaxGraphSiteDescriptors) throw ProtocolError("graph-site trace exceeds its bound");
    std::vector<std::string> result;
    result.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index)
        result.push_back(reader.text(kMaxGraphSiteTextBytes, "graph-site trace entry"));
    return result;
}
inline bool is_hex64(std::string_view value) {
    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](char character) {
        return (character >= '0' && character <= '9') || (character >= 'a' && character <= 'f');
    });
}
inline void append_site_text(std::vector<std::byte>& out, std::string_view value) {
    append_text(out, value, kMaxGraphSiteTextBytes, "graph-site text");
}
inline std::string read_site_text(RowReader& reader) {
    return reader.text(kMaxGraphSiteTextBytes, "graph-site text");
}
inline void require_graph_digest(std::string_view value, std::string_view label) {
    if (!is_hex64(value)) throw ProtocolError(std::string(label) + " is not a SHA-256 digest");
}
inline void validate_graph_sampler(
        std::string_view sampler_sha256,
        std::string_view sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw) {
    require_graph_digest(sampler_sha256, "sampler_sha256");
    if ((sampler_mode != "greedy" && sampler_mode != "categorical") ||
            !std::isfinite(temperature) || temperature <= 0.0 ||
            !std::isfinite(draw) || draw < 0.0 || draw >= 1.0)
        throw ProtocolError("graph-site sampler tuple is invalid");
    if (sampler_mode == "greedy" && (temperature != 1.0 || top_k != 0U || draw != 0.0))
        throw ProtocolError("graph-site greedy sampler tuple is not normalized");
}
inline void check_graph_payload(const std::vector<std::byte>& bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes)
        throw ProtocolError("graph-site payload exceeds its frame bound");
}
} // namespace detail
inline std::vector<std::byte> encode_graph_site_preflight(const GraphSitePreflightWire& value) {
    if (value.version != kGraphSiteWireVersion || value.ready > 1U ||
            value.sites.size() > kMaxGraphSiteDescriptors)
        throw ProtocolError("graph-site preflight metadata is invalid");
    if (value.ready != 0U) {
        detail::require_graph_digest(value.source_sha256, "source_sha256");
        detail::require_graph_digest(value.model_sha256, "model_sha256");
        detail::require_graph_digest(value.tokenizer_sha256, "tokenizer_sha256");
        detail::require_graph_digest(value.native_predecessor_sha256, "native_predecessor_sha256");
        detail::require_graph_digest(value.native_field_epoch_sha256, "native_field_epoch_sha256");
        detail::require_graph_digest(value.native_preflight_sha256, "native_preflight_sha256");
        detail::validate_graph_sampler(value.sampler_sha256, value.sampler_mode, value.sampler_temperature, value.sampler_top_k, value.sampler_draw);
        if (value.task_id.empty() || value.sequence_id.empty() || value.native_operation_id.empty() ||
                value.native_operation_id.size() > 512U || value.native_seq_id < 0 ||
                value.next_position < 0 || value.context_limit == 0U ||
                value.model_embedding_width == 0U || value.model_layer_count == 0U ||
                static_cast<std::uint32_t>(value.next_position) >= value.context_limit ||
                value.remaining_tokens != value.context_limit - static_cast<std::uint32_t>(value.next_position))
            throw ProtocolError("ready graph-site preflight has incomplete native identity or model geometry");
    }
    std::vector<std::byte> out;
    detail::append_u32(out, value.version);
    detail::append_u8(out, value.ready);
    detail::append_i32(out, value.native_seq_id);
    detail::append_i32(out, value.next_position);
    detail::append_u32(out, value.context_limit);
    detail::append_u32(out, value.remaining_tokens);
    detail::append_u32(out, value.model_embedding_width);
    detail::append_u32(out, value.model_layer_count);
    detail::append_site_text(out, value.task_id);
    detail::append_site_text(out, value.sequence_id);
    detail::append_site_text(out, value.native_operation_id);
    detail::append_site_text(out, value.source_sha256);
    detail::append_site_text(out, value.model_sha256);
    detail::append_site_text(out, value.tokenizer_sha256);
    detail::append_site_text(out, value.native_predecessor_sha256);
    detail::append_site_text(out, value.native_field_epoch_sha256);
    detail::append_site_text(out, value.native_preflight_sha256);
    detail::append_site_text(out, value.sampler_sha256);
    detail::append_site_text(out, value.sampler_mode);
    detail::append_f64(out, value.sampler_temperature);
    detail::append_u32(out, value.sampler_top_k);
    detail::append_f64(out, value.sampler_draw);
    detail::append_site_text(out, value.refusal);
    detail::append_u32(out, static_cast<std::uint32_t>(value.sites.size()));
    for (const auto& site : value.sites) {
        if (site.supported > 1U) throw ProtocolError("graph-site descriptor support flag is invalid");
        detail::append_u32(out, site.kind);
        detail::append_u8(out, site.supported);
        detail::append_i32(out, site.layer);
        detail::append_u32(out, site.input_width);
        detail::append_u32(out, site.output_width);
        detail::append_site_text(out, site.stage);
        detail::append_site_text(out, site.site);
        detail::append_site_text(out, site.specialist);
        detail::append_site_text(out, site.input_tensor);
        detail::append_site_text(out, site.output_tensor);
        detail::append_site_text(out, site.dependencies_json);
        detail::append_site_text(out, site.refusal);
    }
    detail::check_graph_payload(out);
    return out;
}

inline GraphSitePreflightWire decode_graph_site_preflight(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes) throw ProtocolError("graph-site preflight payload size is invalid");
    detail::RowReader reader(bytes);
    GraphSitePreflightWire value{};
    value.version = reader.u32();
    value.ready = reader.u8();
    value.native_seq_id = reader.i32();
    value.next_position = reader.i32();
    value.context_limit = reader.u32();
    value.remaining_tokens = reader.u32();
    value.model_embedding_width = reader.u32();
    value.model_layer_count = reader.u32();
    value.task_id = detail::read_site_text(reader);
    value.sequence_id = detail::read_site_text(reader);
    value.native_operation_id = detail::read_site_text(reader);
    value.source_sha256 = detail::read_site_text(reader);
    value.model_sha256 = detail::read_site_text(reader);
    value.tokenizer_sha256 = detail::read_site_text(reader);
    value.native_predecessor_sha256 = detail::read_site_text(reader);
    value.native_field_epoch_sha256 = detail::read_site_text(reader);
    value.native_preflight_sha256 = detail::read_site_text(reader);
    value.sampler_sha256 = detail::read_site_text(reader);
    value.sampler_mode = detail::read_site_text(reader);
    value.sampler_temperature = reader.f64();
    value.sampler_top_k = reader.u32();
    value.sampler_draw = reader.f64();
    value.refusal = detail::read_site_text(reader);
    const auto site_count = reader.u32();
    if (site_count > kMaxGraphSiteDescriptors) throw ProtocolError("graph-site descriptor count exceeds its bound");
    value.sites.reserve(site_count);
    for (std::uint32_t index = 0; index < site_count; ++index) {
        GraphSiteDescriptorWire site{};
        site.kind = reader.u32();
        site.supported = reader.u8();
        site.layer = reader.i32();
        site.input_width = reader.u32();
        site.output_width = reader.u32();
        site.stage = detail::read_site_text(reader);
        site.site = detail::read_site_text(reader);
        site.specialist = detail::read_site_text(reader);
        site.input_tensor = detail::read_site_text(reader);
        site.output_tensor = detail::read_site_text(reader);
        site.dependencies_json = detail::read_site_text(reader);
        site.refusal = detail::read_site_text(reader);
        if (site.supported > 1U) throw ProtocolError("graph-site descriptor support flag is invalid");
        value.sites.push_back(std::move(site));
    }
    if (!reader.done() || value.version != kGraphSiteWireVersion || value.ready > 1U)
        throw ProtocolError("graph-site preflight payload is not canonical");
    if (value.ready != 0U) {
        detail::require_graph_digest(value.source_sha256, "source_sha256");
        detail::require_graph_digest(value.model_sha256, "model_sha256");
        detail::require_graph_digest(value.tokenizer_sha256, "tokenizer_sha256");
        detail::require_graph_digest(value.native_predecessor_sha256, "native_predecessor_sha256");
        detail::require_graph_digest(value.native_field_epoch_sha256, "native_field_epoch_sha256");
        detail::require_graph_digest(value.native_preflight_sha256, "native_preflight_sha256");
        detail::validate_graph_sampler(value.sampler_sha256, value.sampler_mode, value.sampler_temperature, value.sampler_top_k, value.sampler_draw);
        if (value.task_id.empty() || value.sequence_id.empty() || value.native_operation_id.empty() ||
                value.native_operation_id.size() > 512U || value.native_seq_id < 0 ||
                value.next_position < 0 || value.context_limit == 0U ||
                static_cast<std::uint32_t>(value.next_position) >= value.context_limit ||
                value.remaining_tokens != value.context_limit - static_cast<std::uint32_t>(value.next_position))
            throw ProtocolError("ready graph-site preflight has incomplete native identity");
    }
    return value;
}
namespace detail {
inline void validate_graph_site_candidate(const GraphSiteCandidateWire& value) {
    if (value.version != kGraphSiteWireVersion || value.request_sha256_pending > 1U ||
            value.kind < 1U || value.kind > 6U || value.verb > 3U ||
            value.seq_id < 0 || value.position < 0)
        throw ProtocolError("graph-site candidate metadata is invalid");
    if (value.ticket_id.empty() || value.guard_candidate_id != value.ticket_id ||
            value.task_id.empty() || value.sequence_id.empty() ||
            value.native_operation_id.empty() || value.native_operation_id.size() > 512U ||
            value.candidate_sequence_id != value.sequence_id ||
            value.candidate_source_sha256 != value.source_sha256 ||
            value.owner_snapshot_sha256 != value.guard_owner_snapshot_sha256 ||
            value.owner_field_epoch_sha256 != value.guard_field_epoch_sha256 ||
            value.native_predecessor_sha256 != value.guard_native_predecessor_sha256 ||
            value.native_preflight_sha256 != value.guard_native_preflight_sha256)
        throw ProtocolError("graph-site candidate ticket bindings disagree");
    require_graph_digest(value.ticket_sha256, "ticket_sha256");
    require_graph_digest(value.preflight_sha256, "preflight_sha256");
    require_graph_digest(value.native_preflight_sha256, "native_preflight_sha256");
    require_graph_digest(value.source_sha256, "source_sha256");
    require_graph_digest(value.model_sha256, "model_sha256");
    require_graph_digest(value.tokenizer_sha256, "tokenizer_sha256");
    require_graph_digest(value.native_predecessor_sha256, "native_predecessor_sha256");
    require_graph_digest(value.owner_snapshot_sha256, "owner_snapshot_sha256");
    require_graph_digest(value.native_field_epoch_sha256, "native_field_epoch_sha256");
    require_graph_digest(value.owner_field_epoch_sha256, "owner_field_epoch_sha256");
    require_graph_digest(value.candidate_predecessor_sha256, "candidate_predecessor_sha256");
    require_graph_digest(value.invocation_sha256, "invocation_sha256");
    require_graph_digest(value.candidate_sha256, "candidate_sha256");
    if (value.request_sha256_pending != 1U || !value.request_sha256.empty())
        throw ProtocolError("graph-site ticket must defer its request hash until native stage evaluation");
    validate_graph_sampler(value.sampler_sha256, value.sampler_mode, value.sampler_temperature, value.sampler_top_k, value.sampler_draw);
    require_graph_digest(value.guard_native_preflight_sha256, "guard.native_preflight_sha256");
    require_graph_digest(value.guard_native_predecessor_sha256, "guard.native_predecessor_sha256");
    require_graph_digest(value.guard_owner_snapshot_sha256, "guard.owner_snapshot_sha256");
    require_graph_digest(value.guard_field_epoch_sha256, "guard.field_epoch_sha256");
}
}

inline std::vector<std::byte> encode_graph_site_candidate(const GraphSiteCandidateWire& value) {
    detail::validate_graph_site_candidate(value);
    std::vector<std::byte> out;
    detail::append_u32(out, value.version);
    detail::append_site_text(out, value.ticket_id);
    detail::append_site_text(out, value.ticket_sha256);
    detail::append_site_text(out, value.preflight_sha256);
    detail::append_site_text(out, value.native_preflight_sha256);
    detail::append_site_text(out, value.source_sha256);
    detail::append_site_text(out, value.model_sha256);
    detail::append_site_text(out, value.tokenizer_sha256);
    detail::append_site_text(out, value.task_id);
    detail::append_site_text(out, value.sequence_id);
    detail::append_site_text(out, value.native_operation_id);
    detail::append_site_text(out, value.native_predecessor_sha256);
    detail::append_site_text(out, value.owner_snapshot_sha256);
    detail::append_site_text(out, value.native_field_epoch_sha256);
    detail::append_site_text(out, value.owner_field_epoch_sha256);
    detail::append_u8(out, value.request_sha256_pending);
    detail::append_site_text(out, value.sampler_sha256);
    detail::append_site_text(out, value.sampler_mode);
    detail::append_f64(out, value.sampler_temperature);
    detail::append_u32(out, value.sampler_top_k);
    detail::append_f64(out, value.sampler_draw);
    detail::append_u32(out, value.kind);
    detail::append_i32(out, value.seq_id);
    detail::append_i32(out, value.position);
    detail::append_i32(out, value.layer);
    detail::append_u64(out, value.owner_generation);
    detail::append_u64(out, value.predecessor_generation);
    detail::append_site_text(out, value.candidate_sequence_id);
    detail::append_site_text(out, value.candidate_source_sha256);
    detail::append_site_text(out, value.architecture);
    detail::append_site_text(out, value.backend);
    detail::append_site_text(out, value.input_tensor);
    detail::append_site_text(out, value.output_tensor);
    detail::append_site_text(out, value.tensor_dtype);
    detail::append_site_text(out, value.stage);
    detail::append_site_text(out, value.site);
    detail::append_site_text(out, value.specialist);
    detail::append_site_text(out, value.candidate_predecessor_sha256);
    detail::append_site_text(out, value.request_sha256);
    detail::append_site_text(out, value.invocation_sha256);
    detail::append_site_text(out, value.candidate_sha256);
    detail::append_site_text(out, value.intervention_order);
    detail::append_site_text(out, value.dependencies_json);
    detail::append_site_text(out, value.method_key);
    detail::append_u64(out, value.method_generation);
    detail::append_u32(out, value.input_width);
    detail::append_u32(out, value.rank);
    detail::append_u32(out, value.output_width);
    detail::append_float_vector(out, value.a);
    detail::append_float_vector(out, value.b);
    detail::append_float_vector(out, value.bias);
    detail::append_u32(out, value.conv_history_rows);
    detail::append_u32(out, value.conv_history_channels);
    detail::append_u32(out, value.recurrent_state_heads);
    detail::append_u32(out, value.recurrent_state_value_width);
    detail::append_u32(out, value.recurrent_state_key_width);
    detail::append_u32(out, value.attn_kv_heads);
    detail::append_u32(out, value.attn_kv_head_width);
    detail::append_u32(out, value.verb);
    detail::append_site_text(out, value.guard_candidate_id);
    detail::append_site_text(out, value.guard_owner_snapshot_sha256);
    detail::append_site_text(out, value.guard_field_epoch_sha256);
    detail::append_site_text(out, value.guard_native_predecessor_sha256);
    detail::append_site_text(out, value.guard_native_preflight_sha256);
    detail::append_float_vector(out, value.input_support_anchor);
    detail::append_f32(out, value.input_support_radius);
    detail::append_f32(out, value.input_support_anchor_norm);
    detail::append_i32_vector(out, value.expected_expert_ids);
    detail::check_graph_payload(out);
    return out;
}

inline GraphSiteCandidateWire decode_graph_site_candidate(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes) throw ProtocolError("graph-site candidate payload size is invalid");
    detail::RowReader reader(bytes);
    GraphSiteCandidateWire value{};
    value.version = reader.u32();
    value.ticket_id = detail::read_site_text(reader);
    value.ticket_sha256 = detail::read_site_text(reader);
    value.preflight_sha256 = detail::read_site_text(reader);
    value.native_preflight_sha256 = detail::read_site_text(reader);
    value.source_sha256 = detail::read_site_text(reader);
    value.model_sha256 = detail::read_site_text(reader);
    value.tokenizer_sha256 = detail::read_site_text(reader);
    value.task_id = detail::read_site_text(reader);
    value.sequence_id = detail::read_site_text(reader);
    value.native_operation_id = detail::read_site_text(reader);
    value.native_predecessor_sha256 = detail::read_site_text(reader);
    value.owner_snapshot_sha256 = detail::read_site_text(reader);
    value.native_field_epoch_sha256 = detail::read_site_text(reader);
    value.owner_field_epoch_sha256 = detail::read_site_text(reader);
    value.request_sha256_pending = reader.u8();
    value.sampler_sha256 = detail::read_site_text(reader);
    value.sampler_mode = detail::read_site_text(reader);
    value.sampler_temperature = reader.f64();
    value.sampler_top_k = reader.u32();
    value.sampler_draw = reader.f64();
    value.kind = reader.u32();
    value.seq_id = reader.i32();
    value.position = reader.i32();
    value.layer = reader.i32();
    value.owner_generation = reader.u64();
    value.predecessor_generation = reader.u64();
    value.candidate_sequence_id = detail::read_site_text(reader);
    value.candidate_source_sha256 = detail::read_site_text(reader);
    value.architecture = detail::read_site_text(reader);
    value.backend = detail::read_site_text(reader);
    value.input_tensor = detail::read_site_text(reader);
    value.output_tensor = detail::read_site_text(reader);
    value.tensor_dtype = detail::read_site_text(reader);
    value.stage = detail::read_site_text(reader);
    value.site = detail::read_site_text(reader);
    value.specialist = detail::read_site_text(reader);
    value.candidate_predecessor_sha256 = detail::read_site_text(reader);
    value.request_sha256 = detail::read_site_text(reader);
    value.invocation_sha256 = detail::read_site_text(reader);
    value.candidate_sha256 = detail::read_site_text(reader);
    value.intervention_order = detail::read_site_text(reader);
    value.dependencies_json = detail::read_site_text(reader);
    value.method_key = detail::read_site_text(reader);
    value.method_generation = reader.u64();
    value.input_width = reader.u32();
    value.rank = reader.u32();
    value.output_width = reader.u32();
    value.a = detail::read_float_vector(reader);
    value.b = detail::read_float_vector(reader);
    value.bias = detail::read_float_vector(reader);
    value.conv_history_rows = reader.u32();
    value.conv_history_channels = reader.u32();
    value.recurrent_state_heads = reader.u32();
    value.recurrent_state_value_width = reader.u32();
    value.recurrent_state_key_width = reader.u32();
    value.attn_kv_heads = reader.u32();
    value.attn_kv_head_width = reader.u32();
    value.verb = reader.u32();
    value.guard_candidate_id = detail::read_site_text(reader);
    value.guard_owner_snapshot_sha256 = detail::read_site_text(reader);
    value.guard_field_epoch_sha256 = detail::read_site_text(reader);
    value.guard_native_predecessor_sha256 = detail::read_site_text(reader);
    value.guard_native_preflight_sha256 = detail::read_site_text(reader);
    value.input_support_anchor = detail::read_float_vector(reader);
    value.input_support_radius = reader.f32();
    value.input_support_anchor_norm = reader.f32();
    value.expected_expert_ids = detail::read_i32_vector(reader);
    if (!reader.done()) throw ProtocolError("graph-site candidate payload has trailing bytes");
    detail::validate_graph_site_candidate(value);
    return value;
}
namespace detail {
inline std::string canonical_graph_site_trace_json(
        const std::vector<std::string>& trace) {
    if (trace.empty() || trace.size() > kMaxGraphSiteDescriptors)
        throw ProtocolError("graph-site trace is missing or exceeds its bound");
    std::string json{"["};
    static constexpr char hex[] = "0123456789abcdef";
    for (std::size_t index = 0; index < trace.size(); ++index) {
        const auto& entry = trace[index];
        if (entry.empty() || entry.size() > kMaxGraphSiteTextBytes)
            throw ProtocolError("graph-site trace entry is empty or exceeds its bound");
        if (index != 0U) json.push_back(',');
        json.push_back('"');
        for (const unsigned char character : entry) {
            switch (character) {
                case '"': json += "\\\""; break;
                case '\\': json += "\\\\"; break;
                case '\b': json += "\\b"; break;
                case '\f': json += "\\f"; break;
                case '\n': json += "\\n"; break;
                case '\r': json += "\\r"; break;
                case '\t': json += "\\t"; break;
                default:
                    if (character < 0x20U) {
                        json += "\\u00";
                        json.push_back(hex[(character >> 4U) & 0x0fU]);
                        json.push_back(hex[character & 0x0fU]);
                    } else {
                        json.push_back(static_cast<char>(character));
                    }
            }
        }
        json.push_back('"');
    }
    json.push_back(']');
    return json;
}
inline std::string canonical_graph_site_trace_sha256(
        const std::vector<std::string>& trace) {
    const auto json = canonical_graph_site_trace_json(trace);
    return hex_digest(sha256(std::as_bytes(std::span(json.data(), json.size()))));
}
inline void validate_graph_site_receipt(const GraphSiteReceiptWire& value) {
    const bool admitted = value.admitted == 1U;
    if (value.version != kGraphSiteReceiptWireVersion || value.seq_id < 0 || value.position < 0 ||
            value.input_token_count == 0U ||
            value.input_token_count >= static_cast<std::uint64_t>(kMaxGroupHistoryTokens) ||
            value.attempted != 1U || value.admitted > 1U || !std::isfinite(value.added_flops))
        throw ProtocolError("graph-site receipt attempt identity is invalid");
    if (admitted) {
        if (value.accepted_token_id < 0 ||
                value.token_count != value.input_token_count + 1U || !value.refusal.empty())
            throw ProtocolError("admitted graph-site receipt has an invalid token or refusal");
        require_graph_digest(value.replay_sha256, "replay_sha256");
        require_graph_digest(value.input_sha256, "input_sha256");
        require_graph_digest(value.output_sha256, "output_sha256");
        require_graph_digest(value.candidate_successor_sha256, "candidate_successor_sha256");
        require_graph_digest(value.native_successor_sha256, "native_successor_sha256");
    } else if (value.accepted_token_id != -1 || value.token_count != 0U ||
            !value.replay_sha256.empty() || value.refusal.empty() ||
            value.refusal.size() > kMaxGraphSiteTextBytes ||
            !value.candidate_successor_sha256.empty() ||
            !value.native_successor_sha256.empty() || !value.successor_state_json.empty() ||
            value.operators_omitted != 0U || value.weights_omitted != 0U ||
            value.weight_bytes_omitted != 0U || value.transfer_bytes_omitted != 0U ||
            value.added_flops != 0.0) {
        throw ProtocolError("rejected graph-site receipt contains commit-eligible state");
    }
    const bool has_stage_trace = !value.stage_trace.empty() || !value.stage_trace_sha256.empty();
    if (admitted || has_stage_trace) {
        if (value.stage_trace.empty() || value.stage_trace_sha256.empty())
            throw ProtocolError("graph-site receipt has an incomplete stage trace");
        require_graph_digest(value.stage_trace_sha256, "stage_trace_sha256");
        if (canonical_graph_site_trace_sha256(value.stage_trace) != value.stage_trace_sha256)
            throw ProtocolError("graph-site receipt stage trace digest disagrees");
    }
    require_graph_digest(value.input_tokens_sha256, "input_tokens_sha256");
    require_graph_digest(value.ticket_sha256, "ticket_sha256");
    require_graph_digest(value.preflight_sha256, "preflight_sha256");
    require_graph_digest(value.native_preflight_sha256, "native_preflight_sha256");
    require_graph_digest(value.source_sha256, "source_sha256");
    require_graph_digest(value.model_sha256, "model_sha256");
    require_graph_digest(value.tokenizer_sha256, "tokenizer_sha256");
    require_graph_digest(value.invocation_sha256, "invocation_sha256");
    if (admitted || !value.request_sha256.empty())
        require_graph_digest(value.request_sha256, "request_sha256");
    require_graph_digest(value.candidate_sha256, "candidate_sha256");
    require_graph_digest(value.graph_predecessor_sha256, "graph_predecessor_sha256");
    require_graph_digest(value.owner_snapshot_sha256, "owner_snapshot_sha256");
    require_graph_digest(value.owner_field_epoch_sha256, "owner_field_epoch_sha256");
    require_graph_digest(value.native_field_epoch_sha256, "native_field_epoch_sha256");
    require_graph_digest(value.native_predecessor_sha256, "native_predecessor_sha256");
    validate_graph_sampler(value.sampler_sha256, value.sampler_mode, value.sampler_temperature, value.sampler_top_k, value.sampler_draw);
    if (!value.input_sha256.empty()) require_graph_digest(value.input_sha256, "input_sha256");
    if (!value.output_sha256.empty()) require_graph_digest(value.output_sha256, "output_sha256");
    if (value.expected_expert_ids.size() > kMaxGraphSiteDescriptors)
        throw ProtocolError("graph-site receipt expected expert route exceeds its bound");
    for (const auto expert_id : value.expected_expert_ids) {
        if (expert_id < 0)
            throw ProtocolError("graph-site receipt expected route contains a negative ID");
    }
    if (admitted && value.expected_expert_ids != value.actual_expert_ids)
        throw ProtocolError("admitted graph-site receipt route differs from its measured expert IDs");
    if (value.actual_expert_ids.size() > kMaxGraphSiteDescriptors)
        throw ProtocolError("graph-site receipt expert route exceeds its bound");
    for (const auto expert_id : value.actual_expert_ids) {
        if (expert_id < 0)
            throw ProtocolError("graph-site receipt expert route contains a negative ID");
    }
    if (value.ticket_id.empty() || value.task_id.empty() || value.sequence_id.empty() ||
            value.native_operation_id.empty() || value.native_operation_id.size() > 512U ||
            value.stage.empty() || value.site.empty() || value.specialist.empty() ||
            value.method_key.empty())
        throw ProtocolError("graph-site receipt identity is incomplete");
    if (value.field_candidate_id.empty() || value.field_candidate_id.size() > 512U)
        throw ProtocolError("graph-site receipt field candidate identity is invalid");
}
}

inline std::vector<std::byte> encode_graph_site_receipt(const GraphSiteReceiptWire& value) {
    detail::validate_graph_site_receipt(value);
    std::vector<std::byte> out;
    detail::append_u32(out, value.version);
    detail::append_site_text(out, value.ticket_id);
    detail::append_site_text(out, value.field_candidate_id);
    detail::append_site_text(out, value.ticket_sha256);
    detail::append_site_text(out, value.preflight_sha256);
    detail::append_site_text(out, value.native_preflight_sha256);
    detail::append_site_text(out, value.source_sha256);
    detail::append_site_text(out, value.model_sha256);
    detail::append_site_text(out, value.tokenizer_sha256);
    detail::append_site_text(out, value.task_id);
    detail::append_site_text(out, value.sequence_id);
    detail::append_site_text(out, value.native_operation_id);
    detail::append_i32(out, value.seq_id);
    detail::append_i32(out, value.position);
    detail::append_i32(out, value.accepted_token_id);
    detail::append_u64(out, value.input_token_count);
    detail::append_site_text(out, value.input_tokens_sha256);
    detail::append_site_text(out, value.replay_sha256);
    detail::append_u64(out, value.token_count);
    detail::append_site_text(out, value.stage);
    detail::append_i32(out, value.layer);
    detail::append_site_text(out, value.site);
    detail::append_site_text(out, value.specialist);
    detail::append_site_text(out, value.invocation_sha256);
    detail::append_site_text(out, value.request_sha256);
    detail::append_site_text(out, value.candidate_sha256);
    detail::append_site_text(out, value.dependencies_json);
    detail::append_site_text(out, value.method_key);
    detail::append_u64(out, value.method_generation);
    detail::append_site_text(out, value.intervention_order);
    detail::append_site_text(out, value.graph_predecessor_sha256);
    detail::append_site_text(out, value.owner_snapshot_sha256);
    detail::append_site_text(out, value.owner_field_epoch_sha256);
    detail::append_site_text(out, value.native_field_epoch_sha256);
    detail::append_site_text(out, value.native_predecessor_sha256);
    detail::append_site_text(out, value.sampler_sha256);
    detail::append_site_text(out, value.sampler_mode);
    detail::append_f64(out, value.sampler_temperature);
    detail::append_u32(out, value.sampler_top_k);
    detail::append_f64(out, value.sampler_draw);
    detail::append_site_text(out, value.input_sha256);
    detail::append_site_text(out, value.output_sha256);
    detail::append_i32_vector(out, value.expected_expert_ids);
    detail::append_i32_vector(out, value.actual_expert_ids);
    detail::append_graph_site_trace(out, value.stage_trace);
    detail::append_site_text(out, value.stage_trace_sha256);
    detail::append_site_text(out, value.candidate_successor_sha256);
    detail::append_site_text(out, value.native_successor_sha256);
    detail::append_site_text(out, value.successor_state_json);
    detail::append_site_text(out, value.refusal);
    detail::append_u8(out, value.attempted);
    detail::append_u8(out, value.admitted);
    detail::append_u64(out, value.owner_generation);
    detail::append_u64(out, value.operators_omitted);
    detail::append_u64(out, value.weights_omitted);
    detail::append_u64(out, value.weight_bytes_omitted);
    detail::append_u64(out, value.transfer_bytes_omitted);
    detail::append_f64(out, value.added_flops);
    detail::check_graph_payload(out);
    return out;
}

inline GraphSiteReceiptWire decode_graph_site_receipt(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes) throw ProtocolError("graph-site receipt payload size is invalid");
    detail::RowReader reader(bytes);
    GraphSiteReceiptWire value{};
    value.version = reader.u32();
    value.ticket_id = detail::read_site_text(reader);
    value.field_candidate_id = detail::read_site_text(reader);
    value.ticket_sha256 = detail::read_site_text(reader);
    value.preflight_sha256 = detail::read_site_text(reader);
    value.native_preflight_sha256 = detail::read_site_text(reader);
    value.source_sha256 = detail::read_site_text(reader);
    value.model_sha256 = detail::read_site_text(reader);
    value.tokenizer_sha256 = detail::read_site_text(reader);
    value.task_id = detail::read_site_text(reader);
    value.sequence_id = detail::read_site_text(reader);
    value.native_operation_id = detail::read_site_text(reader);
    value.seq_id = reader.i32();
    value.position = reader.i32();
    value.accepted_token_id = reader.i32();
    value.input_token_count = reader.u64();
    value.input_tokens_sha256 = detail::read_site_text(reader);
    value.replay_sha256 = detail::read_site_text(reader);
    value.token_count = reader.u64();
    value.stage = detail::read_site_text(reader);
    value.layer = reader.i32();
    value.site = detail::read_site_text(reader);
    value.specialist = detail::read_site_text(reader);
    value.invocation_sha256 = detail::read_site_text(reader);
    value.request_sha256 = detail::read_site_text(reader);
    value.candidate_sha256 = detail::read_site_text(reader);
    value.dependencies_json = detail::read_site_text(reader);
    value.method_key = detail::read_site_text(reader);
    value.method_generation = reader.u64();
    value.intervention_order = detail::read_site_text(reader);
    value.graph_predecessor_sha256 = detail::read_site_text(reader);
    value.owner_snapshot_sha256 = detail::read_site_text(reader);
    value.owner_field_epoch_sha256 = detail::read_site_text(reader);
    value.native_field_epoch_sha256 = detail::read_site_text(reader);
    value.native_predecessor_sha256 = detail::read_site_text(reader);
    value.sampler_sha256 = detail::read_site_text(reader);
    value.sampler_mode = detail::read_site_text(reader);
    value.sampler_temperature = reader.f64();
    value.sampler_top_k = reader.u32();
    value.sampler_draw = reader.f64();
    value.input_sha256 = detail::read_site_text(reader);
    value.output_sha256 = detail::read_site_text(reader);
    value.expected_expert_ids = detail::read_i32_vector(reader);
    value.actual_expert_ids = detail::read_i32_vector(reader);
    value.stage_trace = detail::read_graph_site_trace(reader);
    value.stage_trace_sha256 = detail::read_site_text(reader);
    value.candidate_successor_sha256 = detail::read_site_text(reader);
    value.native_successor_sha256 = detail::read_site_text(reader);
    value.successor_state_json = detail::read_site_text(reader);
    value.refusal = detail::read_site_text(reader);
    value.attempted = reader.u8();
    value.admitted = reader.u8();
    value.owner_generation = reader.u64();
    value.operators_omitted = reader.u64();
    value.weights_omitted = reader.u64();
    value.weight_bytes_omitted = reader.u64();
    value.transfer_bytes_omitted = reader.u64();
    value.added_flops = reader.f64();
    if (!reader.done()) throw ProtocolError("graph-site receipt payload has trailing bytes");
    detail::validate_graph_site_receipt(value);
    return value;
}

// A one-pass draft verification admits several committed tokens (the
// already-pending target sample, the matched prefix of a proposed draft,
// and the target's own sample at the first divergence or as a bonus once
// the whole draft matches) in one native call.  Each row carries exactly
// the fields an ordinary STEP_MODEL response carries for one token, so the
// caller and the owner replay every row the same way regardless of which
// path produced it.
struct ModelDraftRowWire {
    std::int32_t token{};
    std::uint8_t end_of_generation{};
    std::string replay_sha256;
    std::uint64_t token_count{};
    std::string stage_trace_sha256;
    std::uint64_t exact_stages{};
    std::uint64_t embedding_stages{};
    std::uint64_t attention_stages{};
    std::uint64_t ffn_stages{};
    std::uint64_t head_stages{};
    std::uint64_t ggml_nodes{};
    std::uint64_t logical_weight_bytes{};
    std::string sampler_sha256;
    std::string native_predecessor_sha256;
    std::string native_successor_sha256;
    std::string input_tokens_sha256;
    std::string native_operation_id;
    std::string sequence_id;
    std::uint64_t position{};
    std::uint8_t draft_matched{};
};

inline constexpr std::size_t kMaxModelDraftRows = 16;

inline std::vector<std::byte> encode_model_draft_rows(const std::vector<ModelDraftRowWire>& rows) {
    if (rows.empty() || rows.size() > kMaxModelDraftRows)
        throw ProtocolError("model draft row batch size is invalid");
    std::vector<std::byte> out;
    detail::append_u32(out, static_cast<std::uint32_t>(rows.size()));
    for (const auto& value : rows) {
        detail::append_i32(out, value.token);
        detail::append_u8(out, value.end_of_generation);
        detail::append_site_text(out, value.replay_sha256);
        detail::append_u64(out, value.token_count);
        detail::append_site_text(out, value.stage_trace_sha256);
        detail::append_u64(out, value.exact_stages);
        detail::append_u64(out, value.embedding_stages);
        detail::append_u64(out, value.attention_stages);
        detail::append_u64(out, value.ffn_stages);
        detail::append_u64(out, value.head_stages);
        detail::append_u64(out, value.ggml_nodes);
        detail::append_u64(out, value.logical_weight_bytes);
        detail::append_site_text(out, value.sampler_sha256);
        detail::append_site_text(out, value.native_predecessor_sha256);
        detail::append_site_text(out, value.native_successor_sha256);
        detail::append_site_text(out, value.input_tokens_sha256);
        detail::append_site_text(out, value.native_operation_id);
        detail::append_site_text(out, value.sequence_id);
        detail::append_u64(out, value.position);
        detail::append_u8(out, value.draft_matched);
    }
    return out;
}

inline std::vector<ModelDraftRowWire> decode_model_draft_rows(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes)
        throw ProtocolError("model draft row batch payload size is invalid");
    detail::RowReader reader(bytes);
    const auto count = reader.u32();
    if (count == 0 || count > kMaxModelDraftRows)
        throw ProtocolError("model draft row batch count is invalid");
    std::vector<ModelDraftRowWire> rows;
    rows.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        ModelDraftRowWire value{};
        value.token = reader.i32();
        value.end_of_generation = reader.u8();
        value.replay_sha256 = detail::read_site_text(reader);
        value.token_count = reader.u64();
        value.stage_trace_sha256 = detail::read_site_text(reader);
        value.exact_stages = reader.u64();
        value.embedding_stages = reader.u64();
        value.attention_stages = reader.u64();
        value.ffn_stages = reader.u64();
        value.head_stages = reader.u64();
        value.ggml_nodes = reader.u64();
        value.logical_weight_bytes = reader.u64();
        value.sampler_sha256 = detail::read_site_text(reader);
        value.native_predecessor_sha256 = detail::read_site_text(reader);
        value.native_successor_sha256 = detail::read_site_text(reader);
        value.input_tokens_sha256 = detail::read_site_text(reader);
        value.native_operation_id = detail::read_site_text(reader);
        value.sequence_id = detail::read_site_text(reader);
        value.position = reader.u64();
        value.draft_matched = reader.u8();
        rows.push_back(std::move(value));
    }
    if (!reader.done()) throw ProtocolError("model draft row batch payload has trailing bytes");
    return rows;
}

// The request for one draft-verification round.  ``tokens`` is the
// committed history before any of this round's tokens; ``draft_tokens[0]``
// is checked with an ordinary exact-pipeline sample (the context cannot
// enter the fork's one-pass verifier without an already-pending sample),
// and ``draft_tokens[1:]`` are verified in that one native pass.  ``draws``
// and ``native_operation_ids`` each have exactly ``draft_tokens.size() + 1``
// entries: one per draft position plus one for the target's own sample at
// the first divergence or bonus.
struct ModelDraftVerifyRequestWire {
    std::string task_id;
    std::string source_sha256;
    std::vector<std::int32_t> tokens;
    std::vector<std::int32_t> draft_tokens;
    std::string sampler_mode;
    double sampler_temperature{};
    std::uint32_t sampler_top_k{};
    std::vector<double> draws;
    std::vector<std::string> native_operation_ids;
    std::string sequence_id;
};

inline std::vector<std::byte> encode_model_draft_verify_request(const ModelDraftVerifyRequestWire& value) {
    std::vector<std::byte> out;
    detail::append_site_text(out, value.task_id);
    detail::append_site_text(out, value.source_sha256);
    detail::append_u32(out, static_cast<std::uint32_t>(value.tokens.size()));
    for (auto token : value.tokens) detail::append_i32(out, token);
    detail::append_u32(out, static_cast<std::uint32_t>(value.draft_tokens.size()));
    for (auto token : value.draft_tokens) detail::append_i32(out, token);
    detail::append_site_text(out, value.sampler_mode);
    detail::append_f64(out, value.sampler_temperature);
    detail::append_u32(out, value.sampler_top_k);
    detail::append_u32(out, static_cast<std::uint32_t>(value.draws.size()));
    for (auto draw : value.draws) detail::append_f64(out, draw);
    detail::append_u32(out, static_cast<std::uint32_t>(value.native_operation_ids.size()));
    for (const auto& id : value.native_operation_ids) detail::append_site_text(out, id);
    detail::append_site_text(out, value.sequence_id);
    return out;
}

inline ModelDraftVerifyRequestWire decode_model_draft_verify_request(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes)
        throw ProtocolError("model draft verify request payload size is invalid");
    detail::RowReader reader(bytes);
    ModelDraftVerifyRequestWire value{};
    value.task_id = detail::read_site_text(reader);
    value.source_sha256 = detail::read_site_text(reader);
    const auto token_count = reader.u32();
    if (token_count == 0 || token_count > kMaxFrameBodyBytes / sizeof(std::int32_t))
        throw ProtocolError("model draft verify token history size is invalid");
    value.tokens.reserve(token_count);
    for (std::uint32_t index = 0; index < token_count; ++index) value.tokens.push_back(reader.i32());
    const auto draft_count = reader.u32();
    if (draft_count == 0 || draft_count > kMaxModelDraftRows)
        throw ProtocolError("model draft verify draft token count is invalid");
    value.draft_tokens.reserve(draft_count);
    for (std::uint32_t index = 0; index < draft_count; ++index) value.draft_tokens.push_back(reader.i32());
    value.sampler_mode = detail::read_site_text(reader);
    value.sampler_temperature = reader.f64();
    value.sampler_top_k = reader.u32();
    const auto draw_count = reader.u32();
    if (draw_count != draft_count + 1U)
        throw ProtocolError("model draft verify draw count must be one more than the draft");
    value.draws.reserve(draw_count);
    for (std::uint32_t index = 0; index < draw_count; ++index) value.draws.push_back(reader.f64());
    const auto operation_id_count = reader.u32();
    if (operation_id_count != draw_count)
        throw ProtocolError("model draft verify operation id count must match the draw count");
    value.native_operation_ids.reserve(operation_id_count);
    for (std::uint32_t index = 0; index < operation_id_count; ++index)
        value.native_operation_ids.push_back(detail::read_site_text(reader));
    value.sequence_id = detail::read_site_text(reader);
    if (!reader.done()) throw ProtocolError("model draft verify request payload has trailing bytes");
    return value;
}


namespace detail {
inline void validate_graph_site_replay_step(const GraphSiteReplayStepWire& value) {
    if (value.version != kGraphSiteWireVersion ||
            value.sequence_index >= static_cast<std::uint64_t>(kMaxGroupHistoryTokens) ||
            value.input_token_count >= static_cast<std::uint64_t>(kMaxGroupHistoryTokens) ||
            value.token_count != value.input_token_count + 1U ||
            value.accepted_token_id < 0 || value.native_operation_id.empty() ||
            value.native_operation_id.size() > 512U)
        throw ProtocolError("graph-site replay step identity is invalid");
    if (value.history_complete > 1U) throw ProtocolError("graph-site replay completion flag is invalid");
    require_graph_digest(value.input_tokens_sha256, "input_tokens_sha256");
    require_graph_digest(value.replay_sha256, "replay_sha256");
    require_graph_digest(value.stage_trace_sha256, "stage_trace_sha256");
    validate_graph_sampler(value.sampler_sha256, value.sampler_mode, value.sampler_temperature, value.sampler_top_k, value.sampler_draw);
    const bool graph_step = !value.expected_ticket_sha256.empty();
    if (graph_step) {
        if (value.field_candidate_id.empty() || value.field_candidate_id.size() > 512U)
            throw ProtocolError("graph replay step field candidate identity is invalid");
        require_graph_digest(value.owner_predecessor_sha256, "owner_predecessor_sha256");
        require_graph_digest(value.owner_successor_sha256, "owner_successor_sha256");
        require_graph_digest(value.native_predecessor_sha256, "native_predecessor_sha256");
        require_graph_digest(value.native_successor_sha256, "native_successor_sha256");
        require_graph_digest(value.native_preflight_sha256, "native_preflight_sha256");
        require_graph_digest(value.expected_ticket_sha256, "expected_ticket_sha256");
        require_graph_digest(value.expected_graph_receipt_sha256, "expected_graph_receipt_sha256");
        require_graph_digest(value.expected_native_graph_site_receipt_sha256, "expected_native_graph_site_receipt_sha256");
        if (value.committed_candidate.empty())
            throw ProtocolError("graph replay step is missing its committed candidate");
        const auto candidate = decode_graph_site_candidate(value.committed_candidate);
        if (candidate.ticket_sha256 != value.expected_ticket_sha256 ||
                candidate.native_operation_id != value.native_operation_id ||
                candidate.native_predecessor_sha256 != value.native_predecessor_sha256 ||
                candidate.native_preflight_sha256 != value.native_preflight_sha256 ||
                candidate.owner_snapshot_sha256 != value.owner_predecessor_sha256 ||
                candidate.sampler_sha256 != value.sampler_sha256 ||
                candidate.position < 0 ||
                static_cast<std::uint64_t>(candidate.position) != value.input_token_count)
            throw ProtocolError("graph replay candidate differs from its accepted-step record");
    } else if (!value.owner_predecessor_sha256.empty() || !value.owner_successor_sha256.empty() ||
            !value.native_predecessor_sha256.empty() || !value.native_successor_sha256.empty() ||
            !value.native_preflight_sha256.empty() || !value.expected_graph_receipt_sha256.empty() ||
            !value.expected_native_graph_site_receipt_sha256.empty() ||
            !value.committed_candidate.empty() || !value.field_candidate_id.empty()) {
        throw ProtocolError("ordinary replay step must not claim graph-boundary state hashes");
    }
}
} // namespace detail
inline std::vector<std::byte> encode_graph_site_replay_step(const GraphSiteReplayStepWire& value) {
    detail::validate_graph_site_replay_step(value);
    std::vector<std::byte> out;
    detail::append_u32(out, value.version);
    detail::append_u64(out, value.sequence_index);
    detail::append_site_text(out, value.native_operation_id);
    detail::append_site_text(out, value.field_candidate_id);
    detail::append_site_text(out, value.owner_predecessor_sha256);
    detail::append_site_text(out, value.owner_successor_sha256);
    detail::append_site_text(out, value.native_predecessor_sha256);
    detail::append_site_text(out, value.native_successor_sha256);
    detail::append_site_text(out, value.native_preflight_sha256);
    detail::append_u64(out, value.input_token_count);
    detail::append_site_text(out, value.input_tokens_sha256);
    detail::append_i32(out, value.accepted_token_id);
    detail::append_site_text(out, value.sampler_sha256);
    detail::append_site_text(out, value.sampler_mode);
    detail::append_f64(out, value.sampler_temperature);
    detail::append_u32(out, value.sampler_top_k);
    detail::append_f64(out, value.sampler_draw);
    detail::append_site_text(out, value.replay_sha256);
    detail::append_site_text(out, value.stage_trace_sha256);
    detail::append_u64(out, value.token_count);
    detail::append_u8(out, value.history_complete);
    detail::append_site_text(out, value.expected_ticket_sha256);
    detail::append_site_text(out, value.expected_graph_receipt_sha256);
    detail::append_site_text(out, value.expected_native_graph_site_receipt_sha256);
    if (value.committed_candidate.size() > kMaxFrameBodyBytes)
        throw ProtocolError("graph replay candidate exceeds its bound");
    detail::append_u32(out, static_cast<std::uint32_t>(value.committed_candidate.size()));
    detail::append_raw(out, value.committed_candidate);
    detail::check_graph_payload(out);
    return out;
}

inline GraphSiteReplayStepWire decode_graph_site_replay_step(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size() > kMaxFrameBodyBytes) throw ProtocolError("graph-site replay step payload size is invalid");
    detail::RowReader reader(bytes);
    GraphSiteReplayStepWire value{};
    value.version = reader.u32();
    value.sequence_index = reader.u64();
    value.native_operation_id = detail::read_site_text(reader);
    value.field_candidate_id = detail::read_site_text(reader);
    value.owner_predecessor_sha256 = detail::read_site_text(reader);
    value.owner_successor_sha256 = detail::read_site_text(reader);
    value.native_predecessor_sha256 = detail::read_site_text(reader);
    value.native_successor_sha256 = detail::read_site_text(reader);
    value.native_preflight_sha256 = detail::read_site_text(reader);
    value.input_token_count = reader.u64();
    value.input_tokens_sha256 = detail::read_site_text(reader);
    value.accepted_token_id = reader.i32();
    value.sampler_sha256 = detail::read_site_text(reader);
    value.sampler_mode = detail::read_site_text(reader);
    value.sampler_temperature = reader.f64();
    value.sampler_top_k = reader.u32();
    value.sampler_draw = reader.f64();
    value.replay_sha256 = detail::read_site_text(reader);
    value.stage_trace_sha256 = detail::read_site_text(reader);
    value.token_count = reader.u64();
    value.history_complete = reader.u8();
    value.expected_ticket_sha256 = detail::read_site_text(reader);
    value.expected_graph_receipt_sha256 = detail::read_site_text(reader);
    value.expected_native_graph_site_receipt_sha256 = detail::read_site_text(reader);
    const auto committed_candidate_size = reader.u32();
    if (committed_candidate_size > kMaxFrameBodyBytes)
        throw ProtocolError("graph replay candidate exceeds its bound");
    const auto committed_candidate = reader.take(committed_candidate_size);
    value.committed_candidate.assign(committed_candidate.begin(), committed_candidate.end());
    if (!reader.done()) throw ProtocolError("graph-site replay step payload has trailing bytes");
    detail::validate_graph_site_replay_step(value);
    return value;
}

inline std::vector<std::byte> encode_group_row_requests(std::span<const GroupRowRequestWire> rows) {
    if (rows.empty() || rows.size() > kMaxGroupRows) throw ProtocolError("group row count is outside its bound");
    std::vector<std::byte> out;
    for (const auto& row : rows) {
        if (row.tokens.size() > static_cast<std::size_t>(kMaxGroupHistoryTokens)) throw ProtocolError("group row history exceeds its bound");
        if (row.sampler_mode.size() > kMaxGroupSamplerBytes) throw ProtocolError("group row sampler encoding exceeds its bound");
        if (row.accept_sampled > 1U) throw ProtocolError("group row accept_sampled encoding is invalid");
        detail::append_u32(out, static_cast<std::uint32_t>(row.tokens.size()));
        for (const auto token : row.tokens) detail::append_u32(out, std::bit_cast<std::uint32_t>(token));
        detail::append_u32(out, std::bit_cast<std::uint32_t>(row.next_token));
        out.push_back(std::byte(row.accept_sampled));
        detail::append_u32(out, static_cast<std::uint32_t>(row.sampler_mode.size()));
        detail::append_raw(out, std::as_bytes(std::span(row.sampler_mode.data(), row.sampler_mode.size())));
        detail::append_u64(out, std::bit_cast<std::uint64_t>(row.temperature));
        detail::append_u32(out, row.top_k);
        detail::append_u64(out, std::bit_cast<std::uint64_t>(row.draw));
    }
    if (out.size() > kMaxFrameBodyBytes) throw ProtocolError("group rows exceed their frame bound");
    return out;
}

inline std::vector<GroupRowRequestWire> decode_group_row_requests(std::span<const std::byte> bytes) {
    if (bytes.empty()) throw ProtocolError("group row encoding is empty");
    detail::RowReader reader(bytes);
    std::vector<GroupRowRequestWire> rows;
    while (!reader.done()) {
        if (rows.size() >= kMaxGroupRows) throw ProtocolError("group row count exceeds its bound");
        GroupRowRequestWire row{};
        const auto token_count = reader.u32();
        if (token_count > static_cast<std::uint32_t>(kMaxGroupHistoryTokens)) throw ProtocolError("group row history exceeds its bound");
        row.tokens.resize(token_count);
        for (auto& token : row.tokens) token = reader.i32();
        row.next_token = reader.i32();
        row.accept_sampled = reader.u8();
        if (row.accept_sampled > 1U) throw ProtocolError("group row accept_sampled encoding is invalid");
        const auto sampler_length = reader.u32();
        if (sampler_length > kMaxGroupSamplerBytes) throw ProtocolError("group row sampler encoding exceeds its bound");
        const auto sampler = reader.take(sampler_length);
        row.sampler_mode.resize(sampler.size());
        for (std::size_t index = 0; index < sampler.size(); ++index) {
            const auto character = std::to_integer<unsigned char>(sampler[index]);
            if (character < 0x20U || character == 0x7fU) throw ProtocolError("group row sampler encoding is invalid");
            row.sampler_mode[index] = static_cast<char>(character);
        }
        row.temperature = reader.f64();
        row.top_k = reader.u32();
        row.draw = reader.f64();
        rows.push_back(std::move(row));
    }
    return rows;
}

inline std::vector<std::byte> encode_group_row_results(std::span<const GroupRowResultWire> rows) {
    if (rows.empty() || rows.size() > kMaxGroupRows) throw ProtocolError("group row count is outside its bound");
    std::vector<std::byte> out;
    for (const auto& row : rows) {
        if (!detail::is_hex64(row.replay_sha256) || !detail::is_hex64(row.stage_trace_sha256)) throw ProtocolError("group row digest encoding is invalid");
        if (row.end_of_generation > 1U) throw ProtocolError("group row end_of_generation encoding is invalid");
        detail::append_u32(out, std::bit_cast<std::uint32_t>(row.token));
        out.push_back(std::byte(row.end_of_generation));
        detail::append_u32(out, std::bit_cast<std::uint32_t>(row.sampled_token));
        detail::append_u32(out, static_cast<std::uint32_t>(row.replay_sha256.size()));
        detail::append_raw(out, std::as_bytes(std::span(row.replay_sha256.data(), row.replay_sha256.size())));
        detail::append_u64(out, row.token_count);
        detail::append_u32(out, static_cast<std::uint32_t>(row.stage_trace_sha256.size()));
        detail::append_raw(out, std::as_bytes(std::span(row.stage_trace_sha256.data(), row.stage_trace_sha256.size())));
        detail::append_u64(out, row.exact_stages);
        detail::append_u64(out, row.embedding_stages);
        detail::append_u64(out, row.attention_stages);
        detail::append_u64(out, row.ffn_stages);
        detail::append_u64(out, row.head_stages);
        detail::append_u64(out, row.ggml_nodes);
        detail::append_u64(out, row.logical_weight_bytes);
    }
    if (out.size() > kMaxFrameBodyBytes) throw ProtocolError("group rows exceed their frame bound");
    return out;
}

inline std::vector<GroupRowResultWire> decode_group_row_results(std::span<const std::byte> bytes) {
    if (bytes.empty()) throw ProtocolError("group row encoding is empty");
    detail::RowReader reader(bytes);
    std::vector<GroupRowResultWire> rows;
    while (!reader.done()) {
        if (rows.size() >= kMaxGroupRows) throw ProtocolError("group row count exceeds its bound");
        GroupRowResultWire row{};
        row.token = reader.i32();
        row.end_of_generation = reader.u8();
        if (row.end_of_generation > 1U) throw ProtocolError("group row end_of_generation encoding is invalid");
        row.sampled_token = reader.i32();
        const auto replay_length = reader.u32();
        if (replay_length != 64U) throw ProtocolError("group row digest encoding is invalid");
        const auto replay = reader.take(replay_length);
        row.replay_sha256.assign(reinterpret_cast<const char*>(replay.data()), replay.size());
        if (!detail::is_hex64(row.replay_sha256)) throw ProtocolError("group row digest encoding is invalid");
        row.token_count = reader.u64();
        const auto trace_length = reader.u32();
        if (trace_length != 64U) throw ProtocolError("group row digest encoding is invalid");
        const auto trace = reader.take(trace_length);
        row.stage_trace_sha256.assign(reinterpret_cast<const char*>(trace.data()), trace.size());
        if (!detail::is_hex64(row.stage_trace_sha256)) throw ProtocolError("group row digest encoding is invalid");
        row.exact_stages = reader.u64();
        row.embedding_stages = reader.u64();
        row.attention_stages = reader.u64();
        row.ffn_stages = reader.u64();
        row.head_stages = reader.u64();
        row.ggml_nodes = reader.u64();
        row.logical_weight_bytes = reader.u64();
        rows.push_back(std::move(row));
    }
    return rows;
}

} // namespace cassifi::field_runtime
