// SPDX-License-Identifier: CC0-1.0
#pragma once
#include <cstdint>
namespace WebCore { class Document; class UndoStep; }
namespace BIB {
// Private same-provider calls under the existing Bridge/common-VM lock.
// No pointers, tokens or functions cross the provider ABI.
enum class CompositionUndoAction { matchEmpty, closeEmpty, matchPending, commit, detach, matchRollback, consume, finish, quarantine };
std::uint64_t bibProviderCompositionUndoBegin(WebCore::Document&);
bool bibProviderCompositionUndo(WebCore::Document&, CompositionUndoAction, std::uint64_t, const WebCore::UndoStep*);
}
