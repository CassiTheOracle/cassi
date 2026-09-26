#pragma once

#include "protocol.hpp"

#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string>
#include <utility>
#include <vector>

namespace cassifi::field_runtime {

inline constexpr std::size_t kPageBytes = 64U * 1024U;
inline constexpr std::size_t kMaxWords = kMaxLogicalFieldBytes / sizeof(double);

enum class WordOpcode : std::uint8_t { set = 1, copy = 2, fill = 3, compare_set = 4, add_constant = 5 };

struct WordOperation {
    WordOpcode opcode{};
    std::uint64_t destination{};
    std::uint64_t source_or_expected{};
    std::uint32_t count_or_value{};
    std::uint32_t value{};
};

struct PackedImage {
    std::string owner_id;
    std::uint64_t service_generation{};
    std::uint64_t fence{};
    std::string profile_sha256;
    std::string state_sha256;
    std::string catalog_sha256;
    std::vector<std::uint32_t> shape;
    std::vector<std::uint32_t> words;
    Digest canonical_bytes_sha256{};
    std::vector<Digest> page_sha256;
    std::uint64_t host_mutation_generation{};
    bool canonical_digest_dirty{};
    [[nodiscard]] std::size_t canonical_bytes() const noexcept { return words.size() * sizeof(double); }
    [[nodiscard]] std::size_t packed_bytes() const noexcept { return words.size() * sizeof(std::uint32_t); }
};

inline void mark_host_mutated(PackedImage& image) noexcept {
    if(image.host_mutation_generation!=std::numeric_limits<std::uint64_t>::max())
        ++image.host_mutation_generation;
    image.canonical_digest_dirty=true;
}

inline void require_hex_sha256(std::string_view value, std::string_view label) {
    if (value.size()!=64U || !std::all_of(value.begin(),value.end(),[](char c){ return (c>='0'&&c<='9')||(c>='a'&&c<='f'); })) throw ProtocolError(std::string(label)+" must be a lowercase sha256 digest");
}

inline std::size_t checked_word_count(std::span<const std::uint32_t> shape) {
    if (shape.empty() || shape.size()>8U) throw ProtocolError("field shape rank is invalid");
    std::size_t count=1;
    for (const auto extent:shape) {
        if (!extent || count > kMaxWords / extent) throw ProtocolError("field shape exceeds logical image bounds");
        count*=extent;
    }
    return count;
}

inline std::vector<std::uint32_t> decode_shape(std::span<const std::byte> bytes) {
    if (bytes.empty() || bytes.size()%4U || bytes.size()>32U) throw ProtocolError("encoded field shape is invalid");
    std::vector<std::uint32_t> result(bytes.size()/4U);
    for(std::size_t i=0;i<result.size();++i) result[i]=detail::load_le32(bytes.subspan(i*4U,4U));
    (void)checked_word_count(result);
    return result;
}

inline std::vector<std::byte> encode_shape(std::span<const std::uint32_t> shape) {
    (void)checked_word_count(shape); std::vector<std::byte> result(shape.size()*4U);
    for(std::size_t i=0;i<shape.size();++i) detail::store_le32(std::span<std::byte>(result).subspan(i*4U,4U),shape[i]);
    return result;
}

inline std::vector<Digest> page_manifest(std::span<const std::uint32_t> words) {
    const auto bytes=std::as_bytes(words); std::vector<Digest> result;
    for(std::size_t offset=0;offset<bytes.size();offset+=kPageBytes) result.push_back(sha256(bytes.subspan(offset,std::min(kPageBytes,bytes.size()-offset))));
    if(result.empty()) result.push_back(sha256({}));
    return result;
}

inline Digest canonical_image_digest(std::span<const std::uint32_t> words) noexcept {
    Sha256Accumulator hash;
    std::array<double, 1024> values;
    for (std::size_t first = 0; first < words.size(); first += values.size()) {
        const auto count = std::min(values.size(), words.size() - first);
        for (std::size_t offset = 0; offset < count; ++offset)
            values[offset] = static_cast<double>(words[first + offset]);
        hash.update(std::as_bytes(std::span<const double>(values).first(count)));
    }
    return hash.finish();
}

// Digest of the canonical float64 image bytes, computed without materializing them.
inline Digest canonical_image_sha256(const PackedImage& image) {
    if (checked_word_count(image.shape) != image.words.size()) throw ProtocolError("packed image shape is corrupt");
    return canonical_image_digest(image.words);
}

inline void refresh_changed_page_hashes(
    PackedImage& image,
    std::span<const std::uint8_t> changed_pages) {
    const auto page_count = std::max<std::size_t>(1U, (image.words.size() * sizeof(std::uint32_t) + kPageBytes - 1U) / kPageBytes);
    if (changed_pages.size() != page_count) throw ProtocolError("changed-page map does not match candidate image");
    if (image.page_sha256.size() != page_count) throw ProtocolError("candidate page manifest is corrupt");
    constexpr auto page_words = kPageBytes / sizeof(std::uint32_t);
    for (std::size_t page = 0; page < changed_pages.size(); ++page) {
        if (!changed_pages[page]) continue;
        const auto start = page * page_words;
        const auto count = std::min(page_words, image.words.size() - start);
        image.page_sha256[page] = sha256(std::as_bytes(std::span<const std::uint32_t>(image.words).subspan(start, count)));
    }
    if (image.words.empty() && changed_pages[0]) image.page_sha256[0] = sha256({});
}

inline std::vector<std::uint8_t> validate_word_operations(
    std::span<const std::uint32_t> words,
    std::span<const WordOperation> operations) {
    if (operations.size() > kMaxWordOperations) throw ProtocolError("word operation batch exceeds its bound");
    constexpr auto page_words = kPageBytes / sizeof(std::uint32_t);
    const auto page_count = std::max<std::size_t>(1U, (words.size() + page_words - 1U) / page_words);
    std::vector<std::uint8_t> changed_pages(page_count, 0);
    const auto check_range = [&](std::uint64_t start, std::uint64_t count) {
        if (start > words.size() || count > words.size() - static_cast<std::size_t>(start))
            throw ProtocolError("word operation range is outside candidate image");
    };
    const auto mark_range = [&](std::uint64_t start, std::uint64_t count) {
        if (!count) return;
        const auto first_page = static_cast<std::size_t>(start) / page_words;
        const auto last_page = static_cast<std::size_t>(start + count - 1U) / page_words;
        std::fill(changed_pages.begin() + static_cast<std::ptrdiff_t>(first_page),
            changed_pages.begin() + static_cast<std::ptrdiff_t>(last_page + 1U), std::uint8_t{1});
    };
    for (const auto& operation : operations) {
        switch (operation.opcode) {
        case WordOpcode::set:
            check_range(operation.destination, 1);
            mark_range(operation.destination, 1);
            break;
        case WordOpcode::copy:
            check_range(operation.destination, operation.count_or_value);
            check_range(operation.source_or_expected, operation.count_or_value);
            mark_range(operation.destination, operation.count_or_value);
            break;
        case WordOpcode::fill:
        case WordOpcode::add_constant:
            check_range(operation.destination, operation.count_or_value);
            mark_range(operation.destination, operation.count_or_value);
            break;
        case WordOpcode::compare_set:
            check_range(operation.destination, 1);
            mark_range(operation.destination, 1);
            break;
        default:
            throw ProtocolError("word operation opcode is unsupported");
        }
    }
    return changed_pages;
}

inline PackedImage pack_image(
    std::string owner_id,
    std::uint64_t generation,
    std::uint64_t fence,
    std::string profile_sha256,
    std::string state_sha256,
    std::string catalog_sha256,
    std::span<const std::uint32_t> shape,
    std::span<const std::byte> canonical_float64_bytes,
    const Digest& declared_payload_sha256) {
    if(owner_id.empty()||owner_id.size()>512U) throw ProtocolError("owner identity is invalid");
    require_hex_sha256(profile_sha256,"profile_sha256"); require_hex_sha256(state_sha256,"state_sha256"); require_hex_sha256(catalog_sha256,"catalog_sha256");
    const auto count=checked_word_count(shape);
    if(canonical_float64_bytes.size()!=count*sizeof(double)) throw ProtocolError("canonical image byte count does not match shape");
    if(sha256(canonical_float64_bytes)!=declared_payload_sha256) throw ProtocolError("staging payload digest mismatch");
    PackedImage image{std::move(owner_id),generation,fence,std::move(profile_sha256),std::move(state_sha256),std::move(catalog_sha256),{shape.begin(),shape.end()},{},declared_payload_sha256,{}};
    image.words.reserve(count);
    for(std::size_t index=0;index<count;++index) {
        std::uint64_t bits{}; std::memcpy(&bits,canonical_float64_bytes.data()+index*sizeof(double),sizeof(bits));
        const double value=std::bit_cast<double>(bits);
        if(!std::isfinite(value)||value<0.0||value>double(std::numeric_limits<std::uint32_t>::max())||std::floor(value)!=value||(value==0.0&&std::signbit(value))) throw ProtocolError("unsupported-image-encoding");
        image.words.push_back(static_cast<std::uint32_t>(value));
    }
    image.page_sha256=page_manifest(image.words);
    return image;
}

inline std::vector<std::byte> unpack_image(const PackedImage& image) {
    if(checked_word_count(image.shape)!=image.words.size()) throw ProtocolError("packed image shape is corrupt");
    std::vector<std::byte> result(image.canonical_bytes());
    for(std::size_t index=0;index<image.words.size();++index) {
        const double value=static_cast<double>(image.words[index]);
        std::memcpy(result.data()+index*sizeof(double),&value,sizeof(value));
    }
    return result;
}

inline std::uint64_t sum_words(std::span<const std::uint32_t> words, std::uint64_t first_word, std::uint64_t count) {
    if (count == 0) throw ProtocolError("word reduction range is empty");
    if (first_word > words.size() || count > words.size() - static_cast<std::size_t>(first_word))
        throw ProtocolError("word reduction range is outside candidate image");
    std::uint64_t total = 0;
    const auto begin = static_cast<std::size_t>(first_word);
    for (std::size_t index = begin; index < begin + static_cast<std::size_t>(count); ++index) {
        const std::uint64_t value = words[index];
        if (total > std::numeric_limits<std::uint64_t>::max() - value) throw ProtocolError("word reduction sum overflows exact u64");
        total += value;
    }
    return total;
}

inline WordOperation decode_word_operation(std::span<const std::byte> bytes) {
    // Fixed 32-byte record: opcode/reserved[7], destination, source/expected, count/value, value.
    if(bytes.size()!=32U) throw ProtocolError("word operation record size is invalid");
    const auto raw=std::to_integer<unsigned>(bytes[0]);
    if(raw<1U||raw>5U) throw ProtocolError("word operation opcode is unsupported");
    for(std::size_t i=1;i<8;++i) if(bytes[i]!=std::byte{}) throw ProtocolError("word operation reserved bytes are nonzero");
    return WordOperation{static_cast<WordOpcode>(raw),detail::load_le64(bytes.subspan(8,8)),detail::load_le64(bytes.subspan(16,8)),detail::load_le32(bytes.subspan(24,4)),detail::load_le32(bytes.subspan(28,4))};
}

inline std::vector<WordOperation> decode_word_operations(std::span<const std::byte> bytes) {
    if(bytes.size()%32U) throw ProtocolError("word operation batch is truncated");
    const auto count=bytes.size()/32U; if(count>kMaxWordOperations) throw ProtocolError("word operation batch exceeds its bound");
    std::vector<WordOperation> result; result.reserve(count);
    for(std::size_t i=0;i<count;++i) result.push_back(decode_word_operation(bytes.subspan(i*32U,32U)));
    return result;
}

inline void apply_word_operations(PackedImage& image,std::span<const WordOperation> operations) {
    if(operations.size()>kMaxWordOperations) throw ProtocolError("word operation batch exceeds its bound");
    auto successor=image.words; // candidate-private atomic publication boundary
    const auto check_range=[&](std::uint64_t start,std::uint64_t count){ if(start>successor.size()||count>successor.size()-static_cast<std::size_t>(start)) throw ProtocolError("word operation range is outside candidate image"); };
    for(const auto& operation:operations) {
        switch(operation.opcode) {
        case WordOpcode::set:
            check_range(operation.destination,1); successor[static_cast<std::size_t>(operation.destination)]=operation.count_or_value; break;
        case WordOpcode::copy: {
            const auto count=std::uint64_t(operation.count_or_value); check_range(operation.destination,count); check_range(operation.source_or_expected,count);
            std::memmove(successor.data()+operation.destination,successor.data()+operation.source_or_expected,static_cast<std::size_t>(count)*sizeof(std::uint32_t)); break;
        }
        case WordOpcode::fill: {
            const auto count=std::uint64_t(operation.count_or_value); check_range(operation.destination,count);
            std::fill_n(successor.begin()+static_cast<std::ptrdiff_t>(operation.destination),static_cast<std::size_t>(count),operation.value); break;
        }
        case WordOpcode::compare_set:
            check_range(operation.destination,1);
            if(successor[static_cast<std::size_t>(operation.destination)]!=static_cast<std::uint32_t>(operation.source_or_expected)) throw ProtocolError("word compare-set precondition is stale");
            successor[static_cast<std::size_t>(operation.destination)]=operation.count_or_value; break;
        case WordOpcode::add_constant: {
            const auto count=std::uint64_t(operation.count_or_value); check_range(operation.destination,count);
            for(std::size_t index=0;index<static_cast<std::size_t>(count);++index)
                successor[static_cast<std::size_t>(operation.destination)+index]+=operation.value;
            break;
        }
        }
    }
    mark_host_mutated(image);
    image.words.swap(successor); image.page_sha256=page_manifest(image.words); image.canonical_bytes_sha256=canonical_image_sha256(image);
    image.canonical_digest_dirty=false;
}

} // namespace cassifi::field_runtime
