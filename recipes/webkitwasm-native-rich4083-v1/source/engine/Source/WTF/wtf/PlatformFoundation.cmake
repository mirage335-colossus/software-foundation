# Use actual target OS services and the non-GUI Generic RunLoop. Do not define
# BUILDING_JSCONLY__: WebCore still needs its native platform/font predicates.
if (NOT CMAKE_SYSTEM_NAME MATCHES "^(Linux|Windows)$" OR NOT USE_GENERIC_EVENT_LOOP OR WTF_DEFAULT_EVENT_LOOP)
    message(FATAL_ERROR "Foundation candidate requires native Linux services and an explicitly selected Generic RunLoop")
endif ()
set(LOWERCASE_EVENT_LOOP_TYPE generic)
include("${WTF_DIR}/wtf/PlatformJSCOnly.cmake")
if (NOT WIN32)
list(APPEND WTF_PUBLIC_HEADERS unix/UnixFileDescriptor.h)
endif ()
