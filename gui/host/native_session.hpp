#pragma once
#include "contract.hpp"
#include "file_services.hpp"
namespace foundation::host {
// Native file selectors yield paths only to this host-side content provider.
// Embedders may keep Session's adapter-only provider or inject their own.
template<class App, class Adapter, class Factory> struct NativeSessionSelection {
    using type = typename Factory::template Session<App, Adapter, FileServices>;
};
template<Application App, class Adapter> struct NativeSessionSelection<App, Adapter, void> {
    using type = Session<App, Adapter, FileServices>;
};
// The default remains the literal original Session specialization. An opt-in
// trailing factory may stage a native renderer before constructing its App.
template<class App, class Adapter, class Factory = void>
using NativeSession = typename NativeSessionSelection<App, Adapter, Factory>::type;
}
