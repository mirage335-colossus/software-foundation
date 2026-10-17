// SPDX-License-Identifier: CC0-1.0
// Native CPU provider has no browser media host. No media bridge is linked.
#include "config.h"
#include "BibMediaPlayer.h"
#if !defined(BIB_ENGINE_PROVIDER_NATIVE) || BIB_ENGINE_PROVIDER_NATIVE != 1
#error "Disabled native media leaf requires explicit native provider composition"
#endif
namespace BIB {
bool g_mediaEnabled = false;
}
