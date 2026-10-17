// SPDX-License-Identifier: CC0-1.0
#pragma once
#include <cstdint>

namespace BIB {
struct PrototypeEditorState {
    std::uint32_t revision { 1 };
    std::uint32_t compositionInvalidation { 0 };
    bool inputMethodEnabled { false };

    void changed() { revision = revision == 0x7fffffff ? 1 : revision + 1; }
    void compositionCanceled() { ++compositionInvalidation; changed(); }
};
inline PrototypeEditorState g_prototypeEditorState;
} // namespace BIB
