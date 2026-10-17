// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "host/native_surface_composition.hpp"

// Declaration only: syntax qualification checks the actual thin main's exact
// typed factory call, without importing FLTK or claiming a runnable backend.
namespace foundation::host {
template<NativeSurfaceApplication App>
int run_fltk(int, char**, NativeSurfaceSessionFactory<App>);
}
