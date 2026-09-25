/* Crypto/Sha256.c -- SHA-256 Hash
2010-06-11 : Igor Pavlov : Public domain
This code is based on public domain code from Wei Dai's Crypto++ library. */

#include "rotate-bits/rotate-bits.h"
#include "sha256.h"

#include <string.h>

#if defined(_M_X64) || defined(__x86_64__)
#define SHA256_X86 1
#include <immintrin.h>
#if defined(__GNUC__) || defined(__clang__)
#define SHA256_X86_TARGET __attribute__((target("sha,sse4.1,ssse3")))
#else
#define SHA256_X86_TARGET
#endif
#if defined(_MSC_VER)
#include <intrin.h>
#else
#include <cpuid.h>
#endif
#endif

/* define it for speed optimization */
#define _SHA256_UNROLL
#define _SHA256_UNROLL2

void
sha256_init(sha256_t *p)
{
  p->state[0] = 0x6a09e667;
  p->state[1] = 0xbb67ae85;
  p->state[2] = 0x3c6ef372;
  p->state[3] = 0xa54ff53a;
  p->state[4] = 0x510e527f;
  p->state[5] = 0x9b05688c;
  p->state[6] = 0x1f83d9ab;
  p->state[7] = 0x5be0cd19;
  p->count = 0;
}

#define S0(x) (ROTR32(x, 2) ^ ROTR32(x,13) ^ ROTR32(x, 22))
#define S1(x) (ROTR32(x, 6) ^ ROTR32(x,11) ^ ROTR32(x, 25))
#define s0(x) (ROTR32(x, 7) ^ ROTR32(x,18) ^ (x >> 3))
#define s1(x) (ROTR32(x,17) ^ ROTR32(x,19) ^ (x >> 10))

#define blk0(i) (W[i] = data[i])
#define blk2(i) (W[i&15] += s1(W[(i-2)&15]) + W[(i-7)&15] + s0(W[(i-15)&15]))

#define Ch(x,y,z) (z^(x&(y^z)))
#define Maj(x,y,z) ((x&y)|(z&(x|y)))

#define a(i) T[(0-(i))&7]
#define b(i) T[(1-(i))&7]
#define c(i) T[(2-(i))&7]
#define d(i) T[(3-(i))&7]
#define e(i) T[(4-(i))&7]
#define f(i) T[(5-(i))&7]
#define g(i) T[(6-(i))&7]
#define h(i) T[(7-(i))&7]


#ifdef _SHA256_UNROLL2

#define R(a,b,c,d,e,f,g,h, i) h += S1(e) + Ch(e,f,g) + K[i+j] + (j?blk2(i):blk0(i));\
  d += h; h += S0(a) + Maj(a, b, c)

#define RX_8(i) \
  R(a,b,c,d,e,f,g,h, i); \
  R(h,a,b,c,d,e,f,g, (i+1)); \
  R(g,h,a,b,c,d,e,f, (i+2)); \
  R(f,g,h,a,b,c,d,e, (i+3)); \
  R(e,f,g,h,a,b,c,d, (i+4)); \
  R(d,e,f,g,h,a,b,c, (i+5)); \
  R(c,d,e,f,g,h,a,b, (i+6)); \
  R(b,c,d,e,f,g,h,a, (i+7))

#else

#define R(i) h(i) += S1(e(i)) + Ch(e(i),f(i),g(i)) + K[i+j] + (j?blk2(i):blk0(i));\
  d(i) += h(i); h(i) += S0(a(i)) + Maj(a(i), b(i), c(i))

#ifdef _SHA256_UNROLL

#define RX_8(i) R(i+0); R(i+1); R(i+2); R(i+3); R(i+4); R(i+5); R(i+6); R(i+7);

#endif

#endif

static const uint32_t K[64] = {
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

static void
sha256_transform(uint32_t *state, const uint32_t *data)
{
  uint32_t W[16] = {0};
  unsigned j;
  #ifdef _SHA256_UNROLL2
  uint32_t a,b,c,d,e,f,g,h;
  a = state[0];
  b = state[1];
  c = state[2];
  d = state[3];
  e = state[4];
  f = state[5];
  g = state[6];
  h = state[7];
  #else
  uint32_t T[8];
  for (j = 0; j < 8; j++)
    T[j] = state[j];
  #endif

  for (j = 0; j < 64; j += 16)
  {
    #if defined(_SHA256_UNROLL) || defined(_SHA256_UNROLL2)
    RX_8(0); RX_8(8);
    #else
    unsigned i;
    for (i = 0; i < 16; i++) { R(i); }
    #endif
  }

  #ifdef _SHA256_UNROLL2
  state[0] += a;
  state[1] += b;
  state[2] += c;
  state[3] += d;
  state[4] += e;
  state[5] += f;
  state[6] += g;
  state[7] += h;
  #else
  for (j = 0; j < 8; j++)
    state[j] += T[j];
  #endif

  /* Wipe variables */
  /* memset(W, 0, sizeof(W)); */
  /* memset(T, 0, sizeof(T)); */
}

#undef S0
#undef S1
#undef s0
#undef s1

#ifdef SHA256_X86

/* SHA extensions (Intel Goldmont+/Ice Lake+, every AMD Zen): the same
   compression function, computed on the ABEF/CDGH register layout. */
SHA256_X86_TARGET static void
sha256_compress_x86(uint32_t *state, const unsigned char *data, size_t blocks)
{
  const __m128i byte_swap = _mm_set_epi64x(0x0c0d0e0f08090a0bLL, 0x0405060700010203LL);
  __m128i tmp = _mm_shuffle_epi32(_mm_loadu_si128((const __m128i *)state), 0xB1);
  __m128i state1 = _mm_shuffle_epi32(_mm_loadu_si128((const __m128i *)(state + 4)), 0x1B);
  __m128i state0 = _mm_alignr_epi8(tmp, state1, 8);
  state1 = _mm_blend_epi16(state1, tmp, 0xF0);
  for (; blocks != 0; --blocks, data += 64)
  {
    const __m128i abef = state0;
    const __m128i cdgh = state1;
    __m128i schedule[4];
    unsigned group;
    for (group = 0; group < 16; ++group)
    {
      __m128i words, message;
      if (group < 4)
        words = _mm_shuffle_epi8(_mm_loadu_si128((const __m128i *)(data + group * 16)), byte_swap);
      else
      {
        const __m128i previous = schedule[(group - 1) & 3];
        words = _mm_sha256msg1_epu32(schedule[group & 3], schedule[(group - 3) & 3]);
        words = _mm_add_epi32(words, _mm_alignr_epi8(previous, schedule[(group - 2) & 3], 4));
        words = _mm_sha256msg2_epu32(words, previous);
      }
      schedule[group & 3] = words;
      message = _mm_add_epi32(words, _mm_loadu_si128((const __m128i *)(K + group * 4)));
      state1 = _mm_sha256rnds2_epu32(state1, state0, message);
      message = _mm_shuffle_epi32(message, 0x0E);
      state0 = _mm_sha256rnds2_epu32(state0, state1, message);
    }
    state0 = _mm_add_epi32(state0, abef);
    state1 = _mm_add_epi32(state1, cdgh);
  }
  tmp = _mm_shuffle_epi32(state0, 0x1B);
  state1 = _mm_shuffle_epi32(state1, 0xB1);
  _mm_storeu_si128((__m128i *)state, _mm_blend_epi16(tmp, state1, 0xF0));
  _mm_storeu_si128((__m128i *)(state + 4), _mm_alignr_epi8(state1, tmp, 8));
}

static void
sha256_cpuid(unsigned leaf, unsigned regs[4])
{
#if defined(_MSC_VER)
  int out[4];
  unsigned i;
  __cpuidex(out, (int)leaf, 0);
  for (i = 0; i < 4; i++)
    regs[i] = (unsigned)out[i];
#else
  __cpuid_count(leaf, 0, regs[0], regs[1], regs[2], regs[3]);
#endif
}

static int
sha256_x86_available(void)
{
  /* Deterministic, so a racing first call only repeats the query. */
  static int available = -1;
  if (available < 0)
  {
    unsigned regs[4] = {0, 0, 0, 0};
    int result = 0;
    sha256_cpuid(0, regs);
    if (regs[0] >= 7)
    {
      int ssse3_sse41;
      sha256_cpuid(1, regs);
      ssse3_sse41 = (regs[2] & (1u << 9)) != 0 && (regs[2] & (1u << 19)) != 0;
      sha256_cpuid(7, regs);
      result = ssse3_sse41 && (regs[1] & (1u << 29)) != 0;
    }
    available = result;
  }
  return available;
}

#endif

static void
sha256_compress(uint32_t *state, const unsigned char *data, size_t blocks)
{
#ifdef SHA256_X86
  if (sha256_x86_available())
  {
    sha256_compress_x86(state, data, blocks);
    return;
  }
#endif
  for (; blocks != 0; --blocks, data += 64)
  {
    uint32_t data32[16];
    unsigned i;
    for (i = 0; i < 16; i++)
      data32[i] =
        ((uint32_t)(data[i * 4    ]) << 24) +
        ((uint32_t)(data[i * 4 + 1]) << 16) +
        ((uint32_t)(data[i * 4 + 2]) <<  8) +
        ((uint32_t)(data[i * 4 + 3]));
    sha256_transform(state, data32);
  }
}

static void
sha256_write_byte_block(sha256_t *p)
{
  sha256_compress(p->state, p->buffer, 1);
}


void
sha256_hash(unsigned char *buf, const unsigned char *data, size_t size)
{
  sha256_t hash;
  sha256_init(&hash);
  sha256_update(&hash, data, size);
  sha256_final(&hash, buf);
}


void
sha256_update(sha256_t *p, const unsigned char *data, size_t size)
{
  size_t pos = (size_t)(p->count & 0x3F);
  if (size == 0)
    return;
  p->count += size;
  if (pos != 0)
  {
    size_t take = 64 - pos;
    if (take > size)
      take = size;
    memcpy(p->buffer + pos, data, take);
    data += take;
    size -= take;
    if (pos + take < 64)
      return;
    sha256_write_byte_block(p);
  }
  if (size >= 64)
  {
    size_t blocks = size / 64;
    sha256_compress(p->state, data, blocks);
    data += blocks * 64;
    size -= blocks * 64;
  }
  if (size != 0)
    memcpy(p->buffer, data, size);
}


void
sha256_final(sha256_t *p, unsigned char *digest)
{
  uint64_t lenInBits = (p->count << 3);
  uint32_t curBufferPos = (uint32_t)p->count & 0x3F;
  unsigned i;
  p->buffer[curBufferPos++] = 0x80;
  while (curBufferPos != (64 - 8))
  {
    curBufferPos &= 0x3F;
    if (curBufferPos == 0)
      sha256_write_byte_block(p);
    p->buffer[curBufferPos++] = 0;
  }
  for (i = 0; i < 8; i++)
  {
    p->buffer[curBufferPos++] = (unsigned char)(lenInBits >> 56);
    lenInBits <<= 8;
  }
  sha256_write_byte_block(p);

  for (i = 0; i < 8; i++)
  {
    *digest++ = (unsigned char)(p->state[i] >> 24);
    *digest++ = (unsigned char)(p->state[i] >> 16);
    *digest++ = (unsigned char)(p->state[i] >> 8);
    *digest++ = (unsigned char)(p->state[i]);
  }
  sha256_init(p);
}
