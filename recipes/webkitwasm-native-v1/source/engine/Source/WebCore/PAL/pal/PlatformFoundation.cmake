# Native OpenSSL digest + portable clock/sound/kill-ring services. Full WebCrypto
# remains the supplier stub implementation selected by WebCore, not a claim of
# supported crypto algorithms.
list(APPEND PAL_SOURCES
    crypto/openssl/CryptoDigestOpenSSL.cpp
    system/ClockGeneric.cpp
    system/Sound.cpp
    text/KillRing.cpp
)
list(APPEND PAL_LIBRARIES OpenSSL::Crypto)
