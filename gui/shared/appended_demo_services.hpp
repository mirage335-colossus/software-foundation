// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/appended/web_services.hpp>

#include <vector>

namespace foundation::ui {

// Application-owned examples, installed independently into each composition's
// native and web service catalogs. No backend, engine or Registry is captured.
std::vector<appended::NativeServiceRegistration> demo_native_services();

} // namespace foundation::ui
