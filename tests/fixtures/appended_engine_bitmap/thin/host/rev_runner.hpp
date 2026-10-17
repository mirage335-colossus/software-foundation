// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "host/native_surface_composition.hpp"

// Declaration only; no toolkit, renderer, event loop or runtime is supplied.
namespace foundation::host {
template<NativeSurfaceApplication App>
int run_rev(int, char**, NativeSurfaceSessionFactory<App>);
}
