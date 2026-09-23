#pragma once

#include <algorithm>
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace cassifi::field_runtime {

inline constexpr std::uint32_t kFrameMagic = 0x31524643U; // "CFR1" as LE bytes
inline constexpr std::uint16_t kProtocolVersion = 1;
inline constexpr std::size_t kFrameHeaderBytes = 64;
inline constexpr std::size_t kMaxFrameBodyBytes = 1U << 20;
inline constexpr std::size_t kMaxFieldBytes = 64U << 20;
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
} // namespace detail

inline Digest sha256(std::span<const std::byte> input) {
    std::array<std::uint32_t, 8> h{0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U};
    const std::uint64_t bit_length = std::uint64_t(input.size()) * 8U;
    if (input.size() > (std::numeric_limits<std::size_t>::max() - 72U)) throw ProtocolError("sha256 input is too large");
    std::vector<std::byte> padded(input.begin(), input.end());
    padded.push_back(std::byte{0x80});
    while ((padded.size() % 64U) != 56U) padded.push_back(std::byte{0});
    for (int shift = 56; shift >= 0; shift -= 8) padded.push_back(std::byte((bit_length >> unsigned(shift)) & 0xffU));
    for (std::size_t offset = 0; offset < padded.size(); offset += 64U) {
        std::array<std::uint32_t, 64> w{};
        for (std::size_t i = 0; i < 16; ++i) {
            const auto p = offset + i * 4U;
            w[i] = (std::uint32_t(std::to_integer<unsigned>(padded[p])) << 24U) |
                   (std::uint32_t(std::to_integer<unsigned>(padded[p + 1])) << 16U) |
                   (std::uint32_t(std::to_integer<unsigned>(padded[p + 2])) << 8U) |
                   std::uint32_t(std::to_integer<unsigned>(padded[p + 3]));
        }
        for (std::size_t i = 16; i < 64; ++i) {
            const auto s0 = detail::rotr(w[i-15],7) ^ detail::rotr(w[i-15],18) ^ (w[i-15] >> 3U);
            const auto s1 = detail::rotr(w[i-2],17) ^ detail::rotr(w[i-2],19) ^ (w[i-2] >> 10U);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        auto a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for (std::size_t i = 0; i < 64; ++i) {
            const auto s1=detail::rotr(e,6)^detail::rotr(e,11)^detail::rotr(e,25);
            const auto ch=(e&f)^((~e)&g);
            const auto t1=hh+s1+ch+detail::kShaK[i]+w[i];
            const auto s0=detail::rotr(a,2)^detail::rotr(a,13)^detail::rotr(a,22);
            const auto maj=(a&b)^(a&c)^(b&c);
            const auto t2=s0+maj;
            hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
    }
    Digest out{};
    for (std::size_t i = 0; i < h.size(); ++i) for (unsigned j = 0; j < 4; ++j) out[i*4U+j] = std::byte((h[i] >> (24U-8U*j)) & 0xffU);
    return out;
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

} // namespace cassifi::field_runtime
