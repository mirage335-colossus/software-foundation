// SPDX-License-Identifier: CC0-1.0
#include "appended_demo_services.hpp"

#include <algorithm>
#include <cstdint>
#include <span>

namespace foundation::ui {

std::vector<appended::NativeServiceRegistration> demo_native_services() {
    constexpr appended::SchemaId schema{
        1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
        17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32};
    return {appended::NativeServiceRegistration{
        {"demo.echo",1,0,schema,1024},
        [](std::uint32_t operation, std::span<const std::uint8_t> request,
                std::span<std::uint8_t> response) -> appended::ServiceReply {
            if (operation != 1) return {appended::ServiceStatus::unknown_operation,0};
            // A reply reservation is not a request-size limit. Reject before
            // copying, including when called with a smaller defensive span.
            if (request.size() > 1024 || request.size() > response.size())
                return {appended::ServiceStatus::limit_exceeded,0};
            std::copy(request.begin(),request.end(),response.begin());
            return {appended::ServiceStatus::ok,static_cast<std::uint32_t>(request.size())};
        }}};
}

} // namespace foundation::ui
