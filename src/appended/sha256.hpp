#pragma once

// Project-owned SHA-256 implementation of FIPS 180-4. This private helper has no
// application runtime dependency; its public use is the append consistency check.
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>

namespace foundation::appended::detail {
using Digest = std::array<std::uint8_t, 32>;

class Sha256 {
public:
    void update(std::span<const std::uint8_t> input) noexcept {
        bytes_ += static_cast<std::uint64_t>(input.size());
        for (const auto byte : input) {
            buffer_[used_++] = byte;
            if (used_ == buffer_.size()) {
                transform();
                used_ = 0;
            }
        }
    }

    [[nodiscard]] Digest finish() noexcept {
        const auto bits = bytes_ * 8;
        buffer_[used_++] = 0x80;
        if (used_ > 56) {
            while (used_ < 64) buffer_[used_++] = 0;
            transform();
            used_ = 0;
        }
        while (used_ < 56) buffer_[used_++] = 0;
        for (std::size_t i = 0; i < 8; ++i)
            buffer_[56 + i] = static_cast<std::uint8_t>(bits >> ((7 - i) * 8));
        transform();
        Digest result{};
        for (std::size_t i = 0; i < state_.size(); ++i)
            for (std::size_t j = 0; j < 4; ++j)
                result[i * 4 + j] = static_cast<std::uint8_t>(state_[i] >> ((3 - j) * 8));
        return result;
    }

private:
    void transform() noexcept {
        static constexpr std::array<std::uint32_t, 64> constants{
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
        std::array<std::uint32_t, 64> words{};
        for (std::size_t i = 0; i < 16; ++i)
            for (std::size_t j = 0; j < 4; ++j)
                words[i] = (words[i] << 8) | buffer_[i * 4 + j];
        for (std::size_t i = 16; i < words.size(); ++i) {
            const auto x = words[i - 15], y = words[i - 2];
            const auto s0 = std::rotr(x, 7) ^ std::rotr(x, 18) ^ (x >> 3);
            const auto s1 = std::rotr(y, 17) ^ std::rotr(y, 19) ^ (y >> 10);
            words[i] = words[i - 16] + s0 + words[i - 7] + s1;
        }
        auto a=state_[0], b=state_[1], c=state_[2], d=state_[3];
        auto e=state_[4], f=state_[5], g=state_[6], h=state_[7];
        for (std::size_t i = 0; i < words.size(); ++i) {
            const auto sum1 = std::rotr(e, 6) ^ std::rotr(e, 11) ^ std::rotr(e, 25);
            const auto choose = (e & f) ^ (~e & g);
            const auto t1 = h + sum1 + choose + constants[i] + words[i];
            const auto sum0 = std::rotr(a, 2) ^ std::rotr(a, 13) ^ std::rotr(a, 22);
            const auto majority = (a & b) ^ (a & c) ^ (b & c);
            const auto t2 = sum0 + majority;
            h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
        }
        state_[0]+=a; state_[1]+=b; state_[2]+=c; state_[3]+=d;
        state_[4]+=e; state_[5]+=f; state_[6]+=g; state_[7]+=h;
    }

    std::array<std::uint32_t, 8> state_{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    std::array<std::uint8_t, 64> buffer_{};
    std::uint64_t bytes_{0};
    std::size_t used_{0};
};

inline Digest sha256(std::span<const std::uint8_t> input) noexcept {
    Sha256 hash;
    hash.update(input);
    return hash.finish();
}
inline std::string hex_digest(const Digest& digest) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result(64, '0');
    for (std::size_t i = 0; i < digest.size(); ++i) {
        result[2 * i] = digits[digest[i] >> 4];
        result[2 * i + 1] = digits[digest[i] & 15];
    }
    return result;
}
} // namespace foundation::appended::detail
