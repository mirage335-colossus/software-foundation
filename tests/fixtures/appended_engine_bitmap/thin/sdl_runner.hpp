// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "host/native_surface_composition.hpp"

// Declaration only; unlike a catch-all callable, the exact opt-in factory type
// rejects accidental adapter-only/default-Session entry wiring.
namespace foundation::host {
template<NativeSurfaceApplication App>
int run_sdl(int, char**, NativeSurfaceSessionFactory<App>);
}
