// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "../state.hpp"
namespace foundation::host {
// Deliberate render-loop-only substitute. It does not construct PreparedApp,
// perform provider retirement or establish native Surface authority.
template<class App,class Adapter,class Factory=void>
using NativeSession=bitmap_framebuffer_fixture::Session;
}
